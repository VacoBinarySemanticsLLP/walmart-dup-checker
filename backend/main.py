import os
import json
import base64
import asyncio
import httpx
import hashlib
import io
import atexit
import datetime
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from dotenv import load_dotenv

from rule_compiler import compile_rules, get_compiled_rules_stats

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
CACHE_FILE = "ai_analysis_cache.json"
GEMINI_MODEL = "gemini-2.5-flash"
CACHE_TTL_HOURS = 4  # How long the context cache stays alive

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("WARNING: GEMINI_API_KEY not found in .env file")

# Initialize the new google-genai client
client = genai.Client(api_key=api_key)


# ─────────────────────────────────────────────────────────────────────────────
#  CONTEXT CACHE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────
_cached_content = None  # Module-level reference to the active cache


def create_rule_cache():
    """
    Compile rules.json into compact text and create a Gemini context cache.
    This is called ONCE at server startup. The cache persists for CACHE_TTL_HOURS.
    """
    global _cached_content

    print("\n" + "=" * 60)
    print("📦 COMPILING RULES & CREATING CONTEXT CACHE...")
    print("=" * 60)

    # Step 1: Compile rules into compact text
    compiled_rules = compile_rules()
    stats = get_compiled_rules_stats(compiled_rules)

    print(f"  ✅ Compiled rules: {stats['char_count']:,} chars, ~{stats['approx_tokens']:,} tokens")
    print(f"  ✅ Meets 32K minimum: {stats['meets_32k_minimum']}")
    print(f"  💰 Est. cache cost: ${stats['estimated_cache_cost_per_hour']}/hour")

    # Step 2: Create the context cache with Gemini
    try:
        _cached_content = client.caches.create(
            model=GEMINI_MODEL,
            config=types.CreateCachedContentConfig(
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=compiled_rules)]
                    )
                ],
                system_instruction=types.Content(
                    parts=[types.Part.from_text(
                        text=(
                            "You are a Walmart product data quality evaluator. "
                            "The SOP rules provided in the cached context are your ONLY source of truth. "
                            "When comparing products, find the matching rule by category/product type, "
                            "check which scenario's conditions apply, and return that scenario's decision. "
                            "Always respond with valid JSON only — no markdown, no backticks."
                        )
                    )]
                ),
                ttl=f"{CACHE_TTL_HOURS * 3600}s",
                display_name="walmart-sop-rules"
            )
        )

        print(f"  ✅ Cache created: {_cached_content.name}")
        print(f"  ⏰ TTL: {CACHE_TTL_HOURS} hours (expires ~{datetime.datetime.now() + datetime.timedelta(hours=CACHE_TTL_HOURS):%H:%M})")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"  ❌ Cache creation FAILED: {e}")
        print("  ⚠️  Falling back to non-cached mode (rules sent per request)")
        print("=" * 60 + "\n")
        _cached_content = None


def delete_rule_cache():
    """Delete the context cache on shutdown to stop billing."""
    global _cached_content
    if _cached_content:
        try:
            client.caches.delete(name=_cached_content.name)
            print(f"🗑️  Context cache deleted: {_cached_content.name}")
        except Exception as e:
            print(f"⚠️  Failed to delete cache (may have expired): {e}")
        _cached_content = None


def get_model():
    """
    Return a model reference — cached if available, fallback otherwise.
    When using the cached model, rules are NOT sent per request.
    """
    if _cached_content:
        return _cached_content.name
    return None


def generate_with_cache(contents: list) -> str:
    """
    Generate content using the cached context if available.
    Falls back to sending rules inline if cache is not available.
    """
    cache_name = get_model()

    if cache_name:
        # Cached mode — rules are already in the cache, just send product data
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                cached_content=cache_name
            )
        )
    else:
        # Fallback — send compiled rules inline (more expensive)
        compiled_rules = compile_rules()
        full_contents = [compiled_rules] + contents
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=full_contents
        )

    # Log cache usage stats
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        um = response.usage_metadata
        cached_tokens = getattr(um, 'cached_content_token_count', 0) or 0
        total_input = getattr(um, 'prompt_token_count', 0) or 0
        output_tokens = getattr(um, 'candidates_token_count', 0) or 0
        print(f"  📊 Tokens — Input: {total_input} (cached: {cached_tokens}) | Output: {output_tokens}")
        if cached_tokens > 0:
            savings_pct = (cached_tokens / total_input * 100) if total_input > 0 else 0
            print(f"  💰 Cache hit: {savings_pct:.1f}% of input tokens served from cache")

    return response.text


# ─────────────────────────────────────────────────────────────────────────────
#  LOCAL RESPONSE CACHE  (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────
def get_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache_data):
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
    except Exception as e:
        print("Failed to save cache:", e)

def get_cache_key(products):
    normalized_products = []
    for p in products:
        norm_p = p.copy()
        if 'imageUrls' in norm_p and isinstance(norm_p['imageUrls'], list):
            norm_p['imageUrls'] = sorted(list(set(norm_p['imageUrls'])))
        normalized_products.append(norm_p)
    payload_str = json.dumps(normalized_products, sort_keys=True)
    return hashlib.md5(payload_str.encode('utf-8')).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
#  IMAGE FETCHING  (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────
async def fetch_image(client_http: httpx.AsyncClient, url: str) -> dict:
    try:
        avif_headers = {"Accept": "image/avif,image/webp,image/jpeg,*/*"}
        raw_bytes = None
        source_format = "JPEG"

        avif_url = url
        if url.lower().endswith('.jpeg'):
            avif_url = url[:-5] + '.avif'
        elif url.lower().endswith('.jpg'):
            avif_url = url[:-4] + '.avif'

        if avif_url != url:
            try:
                avif_response = await client_http.get(avif_url, timeout=10.0, headers=avif_headers)
                if avif_response.status_code == 200:
                    raw_bytes = avif_response.content
                    source_format = "AVIF"
                else:
                    print(f"⚠️  AVIF not available (HTTP {avif_response.status_code}), falling back to JPEG")
            except Exception as avif_err:
                print(f"⚠️  AVIF fetch failed ({avif_err}), falling back to JPEG")

        if raw_bytes is None:
            response = await client_http.get(url, timeout=10.0)
            response.raise_for_status()
            raw_bytes = response.content
            source_format = "JPEG"

        original_size_kb = len(raw_bytes) / 1024
        img = Image.open(io.BytesIO(raw_bytes))
        original_dims = img.size
        img.thumbnail((600, 600), Image.LANCZOS)
        new_dims = img.size
        output = io.BytesIO()
        img.save(output, format='WEBP', quality=85, method=6)
        output.seek(0)
        final_bytes = output.read()
        final_size_kb = len(final_bytes) / 1024
        reduction_pct = (1 - final_size_kb / original_size_kb) * 100
        print(
            f"🖼️  [{source_format}] "
            f"{original_dims[0]}x{original_dims[1]}px → {new_dims[0]}x{new_dims[1]}px (color WebP) | "
            f"Downloaded: {original_size_kb:.1f} KB  →  Final: {final_size_kb:.1f} KB  "
            f"({reduction_pct:.1f}% reduced)"
        )
        return {
            "mime_type": "image/webp",
            "data": base64.b64encode(final_bytes).decode('utf-8')
        }
    except Exception as e:
        print(f"Error fetching image {url}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  PROMPTS  (streamlined — rules are in the cache, prompts only define TASK)
# ─────────────────────────────────────────────────────────────────────────────

SINGLE_ANALYSIS_PROMPT_TEMPLATE = """
TASK: Analyze this single product for internal data consistency (vertical check).

Product Title: {title}
Text Attributes: {attributes}

INSTRUCTIONS:
1. Detect the product category from title + attributes
2. Find matching SOP rules from the cached rules for this category
3. Extract specs from the provided images (OCR) — focus on primary attributes for the category
4. Compare extracted image specs against the text attributes
5. Flag contradictions ONLY (not missing data)

Use the SOP rules from the cached context to determine which attributes matter for this category
and which should be ignored.

Respond with JSON only (no markdown, no backticks):
{{
  "detected_category": "string",
  "matched_sop_rules": ["list of scenario_ids that were consulted"],
  "primary_attributes_checked": ["list of attribute names relevant for this category"],
  "extracted_image_specs": "string (concise summary of specs from images, or 'None')",
  "hasInconsistency": boolean,
  "inconsistencies": [
    {{
      "field": "string",
      "imageValue": "string",
      "textValue": "string",
      "reason": "string"
    }}
  ]
}}
"""


BATCH_ANALYSIS_PROMPT = """
TASK: Perform a full duplicate/non-duplicate/bad-data analysis on the following products.

INSTRUCTIONS:
1. For each product, detect its category and find matching SOP rules from the cached context
2. PHASE 1 (Vertical Check): For each product individually, extract image specs via OCR and
   check for contradictions against text attributes. Apply the SOP rules to determine if
   attributes should be ignored for the category.
3. PHASE 2 (Horizontal Check): Compare products that pass Phase 1 against each other.
   Apply the SOP rules for clustering decisions — check which scenario matches and use
   its DECISION (Duplicate / Not a Duplicate / Not sure - Bad data).

CRITICAL RULES FROM SOP:
- Attributes listed as "Ignore Attributes" in matching SOP rules must NOT affect decisions
- When a rule specifies visual_check=REQUIRED, images MUST be verified
- Bad data products go in their own cluster, never merged with others
- Different sizes, model numbers, or finish types = SEPARATE clusters always
- If items are 'Not a Duplicate' or 'unique', they MUST be placed in completely separate cluster objects. NEVER place unique items in the same product_ids array.
- You MUST assign exactly ONE of the following official actions to each cluster:
  * "Duplicate"
  * "Not a Duplicate"
  * "Not a Duplicate - Variant"
  * "Not a Duplicate - Variant Attribute Data Not Available"
  * "Not a Duplicate - Incorrect Variant Attribute Names"
  * "Not a Duplicate - Incorrect Variant Attribute Name Data Not Available"
  * "Not Duplicate - Different Compatibility"
  * "Not Duplicate - Different Warranty"
  * "Not Sure - Bad Data"

Respond with JSON only (no markdown, no backticks):
{
  "vertical_checks": [
    {
      "product_id": "string",
      "detected_category": "string",
      "matched_sop_rules": ["scenario_ids consulted"],
      "primary_attributes_checked": ["attribute names"],
      "has_bad_data": boolean,
      "reason": "string (concise explanation of what is different and why)",
      "mismatch_details": [
        {
          "field": "string",
          "imageValue": "string",
          "textValue": "string"
        }
      ]
    }
  ],
  "horizontal_clustering": [
    {
      "cluster_name": "string (descriptive label)",
      "product_ids": ["string"],
      "cluster_type": "string (duplicate|variant|unique|bad_data)",
      "recommended_action": "Exact string from the official actions list above",
      "matched_sop_rule": "scenario_id that determined this clustering",
      "reason": "string (concise explanation of what is different and why)"
    }
  ]
}
"""


# ─────────────────────────────────────────────────────────────────────────────
#  ANALYSIS FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _build_image_parts(image_data_list: list) -> list:
    """Convert fetched image dicts to genai Part objects."""
    parts = []
    for img in image_data_list:
        if img:
            parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(img["data"]),
                    mime_type=img["mime_type"]
                )
            )
    return parts


async def process_analysis(title, attributes, imageUrls):
    prompt = SINGLE_ANALYSIS_PROMPT_TEMPLATE.format(
        title=title,
        attributes=json.dumps(attributes, indent=2)
    )

    image_parts = []
    async with httpx.AsyncClient() as http_client:
        tasks = [fetch_image(http_client, url) for url in imageUrls]
        fetched_images = await asyncio.gather(*tasks)
        for img in fetched_images:
            if img:
                image_parts.append(img)

    if not image_parts:
        return {"status": "error", "message": "Could not fetch any images."}

    try:
        print("\n" + "=" * 50)
        print("🚀 SENDING REQUEST TO GEMINI (Single Analysis — Context Cached)")
        print("=" * 50)

        # Build content parts: text prompt + images
        content_parts = [types.Part.from_text(text=prompt)]
        content_parts.extend(_build_image_parts(image_parts))

        contents = [types.Content(role="user", parts=content_parts)]

        response_text = generate_with_cache(contents)

        if not response_text:
            return {"status": "error", "message": "no response by ai"}

        text = response_text.strip()
        print("\n" + "=" * 50)
        print("✅ RECEIVED RESPONSE FROM GEMINI (Single Analysis)")
        print("=" * 50)
        print(f"{text}")
        print("=" * 50 + "\n")
        text = text.replace("```json", "").replace("```", "").strip()

        return {"status": "success", "data": json.loads(text)}

    except json.JSONDecodeError:
        print("Failed to parse JSON:", text)
        return {"status": "error", "message": "Invalid JSON response from AI"}
    except Exception as e:
        print("Analysis Error:", e)
        return {"status": "error", "message": str(e)}


MAX_RETRIES = 1


async def process_batch_analysis(products):
    n = len(products)

    # Inject cardinality constraint into the prompt so Gemini knows EXACTLY
    # how many products to output.  Without this the model occasionally drops
    # one product from vertical_checks or horizontal_clustering.
    cardinal_prompt = BATCH_ANALYSIS_PROMPT + (
        f"\n\nCRITICAL — You are analyzing EXACTLY {n} products.  "
        f"Your vertical_checks array MUST contain EXACTLY {n} entries — "
        f"one for each product_id listed above.  "
        f"Do NOT skip, merge, or omit ANY product."
    )
    content_parts = [types.Part.from_text(text=cardinal_prompt)]

    async with httpx.AsyncClient() as http_client:
        seen_image_sets = {}      # url_signature → first_prod_id
        image_cache = {}          # url_signature → [fetched_image_dict, ...]

        for p in products:
            prod_id = p.get('id', 'Unknown')
            prod_text = (
                f"\n\n--- PRODUCT ID: {prod_id} ---\n"
                f"Title: {p.get('title')}\n"
                f"Description: {p.get('description', '')}\n"
                f"Attributes: {json.dumps(p.get('attributes', {}), indent=2)}\n"
                f"Images for {prod_id}:"
            )
            content_parts.append(types.Part.from_text(text=prod_text))

            urls = p.get('imageUrls', [])

            if not urls:
                content_parts.append(types.Part.from_text(text="[No Images Provided for this product]"))
                continue

            url_signature = tuple(sorted(list(set(urls))))

            if url_signature in image_cache:
                # Images already fetched for a previous product — reuse cached
                # bytes instead of fetching again AND instead of sending a text
                # placeholder. This saves network round-trips while still giving
                # Gemini the actual images so it can independently analyze every
                # product (not dropping deduped entries).
                cached = image_cache[url_signature]
                has_img = False
                for img in cached:
                    if img:
                        content_parts.append(
                            types.Part.from_bytes(
                                data=base64.b64decode(img["data"]),
                                mime_type=img["mime_type"]
                            )
                        )
                        has_img = True
                if not has_img:
                    content_parts.append(types.Part.from_text(
                        text="[No Images Could Be Fetched for this product]"
                    ))
            else:
                seen_image_sets[url_signature] = prod_id
                tasks = [fetch_image(http_client, url) for url in urls]
                fetched_images = await asyncio.gather(*tasks)
                # Cache the result so duplicate image-sets don't re-fetch
                image_cache[url_signature] = fetched_images

                has_img = False
                for img in fetched_images:
                    if img:
                        content_parts.append(
                            types.Part.from_bytes(
                                data=base64.b64decode(img["data"]),
                                mime_type=img["mime_type"]
                            )
                        )
                        has_img = True

                if not has_img:
                    content_parts.append(types.Part.from_text(
                        text="[No Images Could Be Fetched — treat extracted_image_specs as 'None' for this product]"
                    ))

    try:
        print("\n" + "=" * 50)
        print("🚀 SENDING REQUEST TO GEMINI (Batch Analysis — Context Cached)")
        print("=" * 50)

        # Log what we're sending (text parts only, not image bytes)
        for idx, part in enumerate(content_parts):
            if hasattr(part, 'text') and part.text:
                print(f"--- Text Part {idx} ---\n{part.text[:200]}...\n")
            else:
                print(f"--- Image Part {idx} ---")
        print("=" * 50 + "\n")

        contents = [types.Content(role="user", parts=content_parts)]
        response_text = generate_with_cache(contents)

        if not response_text:
            return {"status": "error", "message": "no response by ai"}

        text = response_text.strip().replace("```json", "").replace("```", "").strip()
        print("\n" + "=" * 50)
        print("✅ RECEIVED RESPONSE FROM GEMINI (Batch Analysis)")
        print("=" * 50)
        print(f"{text}")
        print("=" * 50 + "\n")

        data = json.loads(text)
        output_ids = {v['product_id'] for v in data.get('vertical_checks', [])}
        input_ids = {p.get('id', 'Unknown') for p in products}
        missing_ids = input_ids - output_ids

        retries_left = MAX_RETRIES
        while missing_ids and retries_left > 0:
            retries_left -= 1
            print(f"\n⚠ Retrying — Gemini returned {len(output_ids)}/{n} products. "
                  f"Missing: {missing_ids}")

            correction = (
                f"\n\n--- CORRECTION ---\n"
                f"You only returned {len(output_ids)} vertical_checks entries, "
                f"but there are {n} products.  "
                f"You MISSED product(s): {missing_ids}.  "
                f"Please output the COMPLETE analysis for ALL {n} products "
                f"— vertical_checks MUST contain exactly {n} entries.  "
                f"Every product_id below MUST appear exactly once."
            )
            content_parts.append(types.Part.from_text(text=correction))
            contents = [types.Content(role="user", parts=content_parts)]
            retry_text = generate_with_cache(contents)

            if not retry_text:
                print("  Retry gave empty response, keeping original.")
                break

            retry_text = retry_text.strip().replace("```json", "").replace("```", "").strip()
            try:
                retry_data = json.loads(retry_text)
            except json.JSONDecodeError:
                print("  Retry JSON parse failed, keeping original.")
                break

            retry_ids = {v['product_id'] for v in retry_data.get('vertical_checks', [])}
            newly_missing = input_ids - retry_ids
            recovered = len(missing_ids) - len(newly_missing)
            if recovered > 0:
                print(f"  ✅ Retry recovered {recovered} product(s) "
                      f"({len(retry_ids)} total, still missing {newly_missing})")
                # Merge: keep all retry entries + any original entries that
                # the retry omitted (product_id collision → prefer retry).
                original_vc = data.get('vertical_checks', [])
                seen_ids = set()
                merged = []
                for entry in retry_data.get('vertical_checks', []):
                    merged.append(entry)
                    seen_ids.add(entry['product_id'])
                for entry in original_vc:
                    if entry['product_id'] not in seen_ids:
                        merged.append(entry)
                        seen_ids.add(entry['product_id'])
                # Re-sort to match input product order
                id_order = [p.get('id', 'Unknown') for p in products]
                merged.sort(key=lambda v: id_order.index(v['product_id'])
                            if v['product_id'] in id_order else len(id_order))
                data['vertical_checks'] = merged
                # Use retry's clustering (it should be more complete)
                data['horizontal_clustering'] = retry_data.get(
                    'horizontal_clustering',
                    data.get('horizontal_clustering', [])
                )
                # Update tracking for the loop guard
                output_ids = input_ids - newly_missing
                missing_ids = newly_missing
            else:
                print("  Retry did not improve, keeping original response.")
                break

        if missing_ids:
            print(f"⚠ FINAL: {len(missing_ids)} product(s) still missing after retries: {missing_ids}")

        # ── INTERCEPTOR: Auto-Split "Not a Duplicate" Clusters ──
        # Gemini often groups non-duplicates to write a shared comparison reason.
        # We forcibly split them here so the frontend sees distinct clusters.
        if "horizontal_clustering" in data:
            new_clusters = []
            for cluster in data.get("horizontal_clustering", []):
                action = cluster.get("recommended_action", "")
                p_ids = cluster.get("product_ids", [])
                
                # If it's NOT a Duplicate but has multiple products, split them!
                if action and action != "Duplicate" and len(p_ids) > 1:
                    print(f"  🔪 INTERCEPTOR: Auto-splitting '{action}' cluster with {len(p_ids)} items.")
                    for pid in p_ids:
                        new_clusters.append({
                            "cluster_name": cluster.get("cluster_name", "Unique Item"),
                            "product_ids": [pid],
                            "cluster_type": cluster.get("cluster_type", "unique"),
                            "recommended_action": action,
                            "matched_sop_rule": cluster.get("matched_sop_rule", ""),
                            "reason": cluster.get("reason", "")
                        })
                else:
                    new_clusters.append(cluster)
            data["horizontal_clustering"] = new_clusters

        return {"status": "success", "data": data}

    except json.JSONDecodeError:
        print("Failed to parse JSON:", text)
        return {"status": "error", "message": "Invalid JSON response from AI"}
    except Exception as e:
        print("Batch Analysis Error:", e)
        return {"status": "error", "message": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
#  FLASK APP & ROUTES
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def index():
    cache_status = "active" if _cached_content else "inactive (fallback mode)"
    return jsonify({
        "status": "running",
        "message": "DupCheck Backend is active and listening.",
        "context_cache": cache_status,
        "cache_name": _cached_content.name if _cached_content else None,
    })


@app.route("/api/cache-status", methods=["GET"])
def cache_status():
    """Check the current state of the context cache."""
    if _cached_content:
        return jsonify({
            "cached": True,
            "cache_name": _cached_content.name,
            "model": GEMINI_MODEL,
            "ttl_hours": CACHE_TTL_HOURS,
        })
    else:
        return jsonify({
            "cached": False,
            "message": "No active context cache. Rules sent inline per request.",
        })


@app.route("/api/cache-refresh", methods=["POST"])
def cache_refresh():
    """Force-refresh the context cache (e.g., after updating rules.json)."""
    delete_rule_cache()
    create_rule_cache()
    if _cached_content:
        return jsonify({"status": "success", "cache_name": _cached_content.name})
    else:
        return jsonify({"status": "error", "message": "Cache creation failed"}), 500


@app.route("/test-ai", methods=["GET"])
def test_ai():
    title = "Bulbasaur"
    attributes = {"Type": "Grass", "Color": "Blue"}
    imageUrls = ["https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png"]
    result = asyncio.run(process_analysis(title, attributes, imageUrls))
    html_response = f"""
    <html>
        <body style="font-family: monospace; background: #1e1e1e; color: #00ff00; padding: 20px;">
            <h2>AI Vision Test Result</h2>
            <pre>{json.dumps(result, indent=4)}</pre>
        </body>
    </html>
    """
    return html_response


@app.route("/api/analyze-column", methods=["POST"])
def analyze_column():
    req_data = request.get_json()
    title = req_data.get("title", "")
    attributes = req_data.get("attributes", {})
    imageUrls = req_data.get("imageUrls", [])

    if not imageUrls:
        return jsonify({"status": "no_images", "message": "No image URLs provided for analysis."})

    result = asyncio.run(process_analysis(title, attributes, imageUrls))

    if result.get("status") == "error":
        return jsonify(result), 500

    return jsonify(result)


@app.route("/api/analyze-batch", methods=["POST"])
def analyze_batch():
    req_data = request.get_json()
    products = req_data.get("products", [])
    force_refresh = req_data.get("forceRefresh", False)

    print(f"Received batch analysis request for {len(products)} products (Force Refresh: {force_refresh})")

    if not products:
        return jsonify({"status": "error", "message": "No products provided for analysis."}), 400

    cache_key = get_cache_key(products)
    cache = get_cache()

    if not force_refresh and cache_key in cache:
        print(f"✅ Cache HIT! Returning cached AI result for key: {cache_key}")
        return jsonify(cache[cache_key])

    print(f"❌ Cache MISS (or forced refresh). Running AI analysis...")
    result = asyncio.run(process_batch_analysis(products))

    if result.get("status") == "success":
        cache[cache_key] = result
        save_cache(cache)
    elif result.get("status") == "error":
        return jsonify(result), 500

    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
#  STARTUP & SHUTDOWN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Create context cache on startup
    create_rule_cache()

    # Register cleanup on shutdown (delete cache to stop billing)
    atexit.register(delete_rule_cache)

    print("DupCheck backend running on http://localhost:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)