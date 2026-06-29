import os
import json
import base64
import asyncio
import httpx
import hashlib
import io
import atexit
import datetime
import tempfile
import threading
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
_is_rebuilding_cache = False  # Lock to prevent concurrent background rebuilds


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
    global _cached_content, _is_rebuilding_cache
    cache_name = get_model()

    response = None
    if cache_name:
        # Cached mode — rules are already in the cache, just send product data
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    cached_content=cache_name,
                    response_mime_type="application/json"
                )
            )
        except Exception as e:
            if "CachedContent not found" in str(e) or "403" in str(e) or "PERMISSION_DENIED" in str(e):
                print(f"⚠️  Cache error detected (likely expired): {e}")
                print("🔄  Falling back to inline rules...")
                _cached_content = None  # Clear invalid cache
                
                if not _is_rebuilding_cache:
                    _is_rebuilding_cache = True
                    def rebuild():
                        global _is_rebuilding_cache
                        try:
                            create_rule_cache()
                        finally:
                            _is_rebuilding_cache = False
                    threading.Thread(target=rebuild, daemon=True).start()
            else:
                raise e

    if not response:
        # Fallback — send compiled rules inline (more expensive)
        compiled_rules = compile_rules()
        full_contents = [compiled_rules] + contents
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=full_contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
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

    # Safely extract text — response.text raises ValueError when Gemini blocks
    # the response (safety filter, recitation, etc.), which shows as Output: 0.
    def _safe_text(resp):
        try:
            return resp.text
        except (ValueError, Exception):
            return None

    text = _safe_text(response)
    if text is not None:
        return text

    # ── Retry with relaxed safety settings ───────────────────────────────────
    # Gemini RECITATION / SAFETY blocks fire when products have identical titles
    # or when content resembles training data. Retrying with BLOCK_NONE bypasses
    # the filter for product comparison tasks which are never harmful.
    finish_reason = "UNKNOWN"
    try:
        finish_reason = response.candidates[0].finish_reason.name
    except Exception:
        pass
    print(f"  ⚠️  Gemini blocked response (finish_reason={finish_reason}). Retrying with relaxed safety settings...")

    relaxed_safety = [
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT",        threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH",       threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
        types.SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY",   threshold="BLOCK_NONE"),
    ]

    cache_name = get_model()
    try:
        if cache_name:
            retry_response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    cached_content=cache_name,
                    safety_settings=relaxed_safety,
                    response_mime_type="application/json"

                )
            )
        else:
            compiled_rules = compile_rules()
            full_contents = [compiled_rules] + contents
            retry_response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_contents,
                config=types.GenerateContentConfig(
                    safety_settings=relaxed_safety,
                    response_mime_type="application/json"
                )
            )

        retry_text = _safe_text(retry_response)
        if retry_text:
            print(f"  ✅ Retry with relaxed safety succeeded.")
            return retry_text
    except Exception as retry_err:
        print(f"  ❌ Retry also failed: {retry_err}")

    print(f"  ❌ Gemini returned no text even after retry. Finish reason was: {finish_reason}")
    raise Exception(f"Gemini API blocked response or returned no text. Finish reason: {finish_reason}")




# ─────────────────────────────────────────────────────────────────────────────
#  IMAGE FETCHING  (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────
async def fetch_image(client_http: httpx.AsyncClient, url: str) -> dict:
    try:
        response = await client_http.get(url, timeout=10.0)
        response.raise_for_status()
        raw_bytes = response.content
        source_format = "ORIGINAL"

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

Before performing ANY comparison, independently extract the following attributes from BOTH the structured text and the product images.

Extract each attribute separately. Do NOT combine or normalize different attributes into a single value.

- Brand
- Product Name
- Model Number
- Size / Dimensions
- Capacity
- Weight
- Color
- Finish
- Material
- Flavor
- Scent
- Dosage Strength
- Formulation
- Package Type
- Package Count
- Units Per Package
- Total Units
- Compatibility
- Warranty

Rules:

- Keep Package Count, Units Per Package, and Total Units as separate attributes.
- Never merge multiple quantity attributes into a single "Count".
- Preserve packaging hierarchy exactly as shown.
- If an attribute cannot be confidently extracted from either text or image, return it as "Unknown". Never infer missing values.

CRITICAL RULES FROM SOP:
- Attributes listed as "Ignore Attributes" in matching SOP rules must NOT affect decisions
- Do not flag 'Bad Data' just because a specific attribute is missing (-) if that information is clearly stated in the title, description, or under a synonymous attribute name.
- When a rule specifies visual_check=REQUIRED, images MUST be verified
- COUNT VERIFICATION (ALL CATEGORIES): Pay extremely close attention to the Unit of Measurement (UOM) in images and text. Distinguish between 'Package-Level Count' (e.g., 1 Box, 1 Case), 'Item-Level Count' (e.g., 60 Pills, 80 Pellets), and 'Weight/Volume' (e.g., 0.3 Ounces, 50ml). Do NOT flag different types of measurements as contradictions (e.g., 'Net Content: 0.3 Ounces' vs 'Count Per Pack: 80'). If an attribute like 'Total Count' or 'Multipack Quantity' is '1', it almost always refers to '1 retail package being sold'. Do NOT flag 'Total Count: 1' as a contradiction against 'Count Per Pack: 80' or a product image showing '80 Ct'. As long as the measurements describe different aspects (weight vs count vs packages), it is a PERFECT match, not Bad Data.
- PACKAGING HORIZONTAL RULES: A 2x30 configuration (2 bottles of 30) is NOT a duplicate of a 1x60 configuration (1 bottle of 60). Even if total units are the same, different package structures must be clustered separately (e.g., 'Not a Duplicate - Variant').
- PACKAGING TYPE RULES: Pay attention to the physical container type. A bottle is NOT a duplicate of a blister pack, and a blister pack is NOT a duplicate of a strip. Cluster these separately.
- COMPATIBILITY OVERRIDES BAD DATA: If attributes like 'Actual Color' or 'Color' contain vehicle compatibility data (e.g. 'For 2022-2023 Chevrolet Silverado'), do NOT flag this as a color contradiction or 'Bad Data' in the vertical check. Treat it as valid compatibility information.
- DIMENSIONS & WEIGHT ARE JUNK DATA: 'Assembled Product Width', 'Assembled Product Length', 'Assembled Product Height', and 'Assembled Product Weight' (and variations like 'Width', 'Length', 'Height', 'Weight') MUST be completely ignored in all cases. Do not check, extract, or flag contradictions based on them; treat them entirely as junk data.
- LAZY METADATA & PLACEHOLDERS: Sellers frequently use lazy generic terms. If text attributes state "As Picture", "As Shown", "Other", or "Multicolor", you MUST assume they agree with the visual evidence. Never flag these placeholders as contradicting specific OCR values (e.g., 'Other' does NOT contradict 'Clear'). Furthermore, if text is missing (-) and OCR finds the value (e.g., a Model Number), this is data enrichment, NOT a contradiction.
- CLUSTERING LOGIC - IDENTICALS: Group identical/duplicate products together in the SAME cluster.
- CLUSTERING LOGIC - VARIANTS & UNIQUE: If a product is a variant, a completely unique item, or "Not a Duplicate", it MUST be placed in its OWN SEPARATE, STANDALONE cluster. Do NOT group variants or non-duplicates together with the primary product or with each other. Each gets its own cluster.
- CLUSTERING LOGIC - BAD DATA: Bad data products MUST be separated into their own individual clusters, never merged with any other product.
- CLUSTERING LOGIC - DIFFERENT ATTRIBUTES: Different sizes, model numbers, finish types, or compatibilities = SEPARATE clusters always.
- You MUST assign exactly ONE of the following official actions to each cluster:
  ACTION SELECTION HIERARCHY (MANDATORY)

When multiple conditions apply, ALWAYS select exactly ONE action using the following priority order:

1. "Not Duplicate - Different Compatibility"
   Use when compatibility differs (vehicle, device, model, application, etc.), regardless of other variant differences or missing data.

2. "Not Sure - Bad Data"
   Use if:
   - Required attributes cannot be verified.
   - Image and text contain unresolved contradictions.
   - OCR evidence is insufficient for required verification.
   - Critical product information is missing and prevents reliable comparison.

3. "Not Duplicate - Different Warranty"
   Use when warranty is the only material differentiator and SOP specifies warranty as variant-driving.

4. "Not a Duplicate - Incorrect Variant Attribute Name Data Not Available"
   Use when variant attribute names are incorrect and the actual variant values cannot be determined.

5. "Not a Duplicate - Incorrect Variant Attribute Names"
   Use when products differ only because variant information is stored under incorrect attribute names.

6. "Not a Duplicate - Variant Attribute Data Not Available"
   Use when variant-driving attributes are missing and variant status cannot be determined.

7. "Not a Duplicate - Variant"
   Use when products belong to the same product family but differ in one or more variant-driving attributes.

8. "Duplicate"
   Use when every critical attribute matches after applying SOP ignore rules.

9. "Not a Duplicate"
   Use only when the products belong to completely different product families and are not variants of each other.

GENERALIZED METADATA NOISE & TRUTH HIERARCHY:
To handle messy marketplace seller-submitted data, apply the following "common sense" hierarchy over the raw rules:
- CORE IDENTITY TIERS:
  * Tier 1 (Core Identity): Brand, capacity/volume (e.g. 32oz, 1 Liter), model number, and packaging structures (e.g. 1-pack vs 2-pack). Discrepancies here are critical and drive "Not a Duplicate" / "Variant" decisions.
  * Tier 2 (Visual Specs): Color, Finish, Material. If these differ, use the Image as the absolute tie-breaker. If the image shows them as identical, ignore the text discrepancy (e.g., ignore 'Multicolor' vs 'Matte Black' if visually identical).
  * Tier 3 (Logistics/Marketing Noise): "Is Assembly Required", assembly instructions, Assembled Product dimensions (Length, Width, Height, Weight), Bulk Size, target audience, subjective benefits (e.g. "Hair Product Form" cream vs liquid, or "Hair Type" fine vs damaged). Completely IGNORE discrepancies in Tier 3 attributes. Do NOT flag 'Bad Data' or 'Variant' based on Tier 3 differences.
- VISUAL GROUNDING: If the primary product images are identical, you must maintain a "Duplicate" decision unless there is a clear, un-ignorable mismatch in a Tier 1 Core Identity attribute (different Model Numbers, or different Capacity). HOWEVER, for products featuring printed artwork, graphics, or painted scenes (e.g., printed lanterns, decorative items), you MUST perform a strict micro-level visual comparison of the artwork itself (e.g., character poses, direction, background elements, specific graphic designs). If the artwork/graphic differs in ANY way, the images are NOT identical, and you must flag it as 'Not a Duplicate - Variant'.
- DATA ASYMMETRY TOLERANCE: Missing attributes (e.g., `-` or `None` on one side but present on the other) are data gaps, not contradictions. Never flag "Bad Data" or "Variant" based on missing data.
- ACTION HIERARCHY OVERRIDE: If there is clear proof that the items are variants or completely different (e.g., different Model Numbers, different Native Resolutions), choose "Not a Duplicate - Variant" or "Not a Duplicate". Choosing "Not a Duplicate" or "Variant" overrides any minor "Bad Data" triggers.

Respond with JSON only (no markdown, no backticks):
{
  "vertical_checks": [
    {
      "product_id": "Exact string from the PRODUCT ID header (e.g. 'GTIN#1 (007...)')",
      "detected_category": "string",
      "matched_sop_rules": ["scenario_ids consulted"],
      "extracted_image_summary": "string (ultra-brief 5-10 word summary of key visual specs. If printed artwork is present, explicitly describe its specific orientation/elements like 'Cardinal facing left with pine trees' to capture differences)",
      "has_bad_data": boolean,
      "reason": "string (ULTRA-SHORT 1-2 sentence summary. Focus only on the main difference or missing attribute. DO NOT write long paragraphs.)",
      "mismatch_details": [
        {
          "field": "string (only include fields that actually contradict)",
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
      "reason": "string (ULTRA-SHORT 1-2 sentence summary. Focus only on the main difference or missing attribute. DO NOT write long paragraphs.)"
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


def format_error(e: Exception) -> tuple[int, str]:
    err_str = str(e)
    code = getattr(e, 'code', 500)
    msg = getattr(e, 'message', err_str)
    
    if "RECITATION" in err_str:
        return 400, f"[API 400] Gemini blocked the response due to a Recitation/Copyright filter."
    elif "SAFETY" in err_str or "HARM_CATEGORY" in err_str:
        return 400, f"[API 400] Gemini blocked the response due to Safety filters."
    elif "Quota" in err_str or "429" in err_str:
        return 429, f"[HTTP 429] Gemini API Quota Exceeded or Rate Limited."
    elif "403" in err_str or "PERMISSION_DENIED" in err_str:
        return 403, f"[HTTP 403] Gemini API Authentication or Permission Error."
    
    return code, f"[HTTP {code}] {msg}"


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
        return {"status": "error", "message": "[HTTP 400] Could not fetch any images.", "status_code": 400}

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
            raise Exception("Gemini API returned an empty response.")

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
        return {"status": "error", "message": "[API 422] Invalid JSON response from AI.", "status_code": 422}
    except Exception as e:
        print("Analysis Error:", e)
        code, msg = format_error(e)
        return {"status": "error", "message": msg, "status_code": code}


MAX_RETRIES = 1


async def process_batch_analysis(products):
    n = len(products)

    # Append cardinality + clustering reminder to ensure Gemini outputs all
    # products and applies the correct clustering rules.
    cardinal_prompt = BATCH_ANALYSIS_PROMPT + (
        f"\n\n══════════════════════════════════════════════════════════════════\n"
        f"FINAL REMINDERS BEFORE YOU RESPOND\n"
        f"══════════════════════════════════════════════════════════════════\n"
        f"• You are analyzing EXACTLY {n} products.\n"
        f"• Your vertical_checks array MUST contain EXACTLY {n} entries —\n"
        f"  one for each product_id listed above. Do NOT skip, merge, or omit ANY product.\n"
        f"• CLUSTERING REMINDER:\n"
        f"  - Each BAD DATA product → its OWN standalone cluster.\n"
        f"  - DUPLICATE products → ONE shared cluster.\n"
        f"  - Each VARIANT / NOT A DUPLICATE product → its OWN standalone cluster.\n"
        f"  - Following this rule: if you have 2 bad data + 3 duplicates + 1 not a duplicate,\n"
        f"    you MUST output exactly 4 clusters.\n"
        f"• 'Not Sure – Bad Data' is LAST RESORT. Use actions 1–8 first.\n"
        f"  Do NOT use Bad Data for missing attributes or OCR gaps.\n"
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
            raise Exception("Gemini API returned an empty response.")

        text = response_text.strip().replace("```json", "").replace("```", "").strip()
        print("\n" + "=" * 50)
        print("✅ RECEIVED RESPONSE FROM GEMINI (Batch Analysis)")
        print("=" * 50)
        print(f"{text}")
        print("=" * 50 + "\n")

        data = json.loads(text)
        output_ids = {v['product_id'] for v in data.get('vertical_checks', [])}
        input_ids = {p.get('id', 'Unknown') for p in products}
        
        missing_ids = set()
        for i_id in input_ids:
            if not any(i_id in o_id or o_id in i_id for o_id in output_ids):
                missing_ids.add(i_id)

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
                f"Every product_id below MUST appear exactly once.\n"
                f"Also recheck your clustering: bad data products must each have "
                f"their own standalone cluster."
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
            newly_missing = set()
            for i_id in input_ids:
                if not any(i_id in o_id or o_id in i_id for o_id in retry_ids):
                    newly_missing.add(i_id)
                    
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

        return {"status": "success", "data": data}

    except json.JSONDecodeError:
        print("Failed to parse JSON:", text)
        return {"status": "error", "message": "[API 422] Invalid JSON response from AI.", "status_code": 422}
    except Exception as e:
        print("Batch Analysis Error:", e)
        code, msg = format_error(e)
        return {"status": "error", "message": msg, "status_code": code}


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
        return jsonify({"status": "error", "message": "[HTTP 400] No image URLs provided for analysis.", "status_code": 400}), 400

    result = asyncio.run(process_analysis(title, attributes, imageUrls))

    if result.get("status") == "error":
        return jsonify(result), result.get("status_code", 500)

    return jsonify(result)


@app.route("/api/analyze-batch", methods=["POST"])
def analyze_batch():
    req_data = request.get_json()
    products = req_data.get("products", [])

    print(f"Received batch analysis request for {len(products)} products")

    if not products:
        return jsonify({"status": "error", "message": "[HTTP 400] No products provided for analysis.", "status_code": 400}), 400

    print(f"🚀 Running AI batch analysis...")
    result = asyncio.run(process_batch_analysis(products))

    if result.get("status") == "error":
        return jsonify(result), result.get("status_code", 500)

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