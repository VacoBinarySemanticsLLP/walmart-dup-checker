import os, json, base64, asyncio, httpx, io, atexit, datetime, threading
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from dotenv import load_dotenv
from rule_compiler import compile_rules, get_compiled_rules_stats

GEMINI_MODEL = "gemini-2.5-flash"
CACHE_TTL_HOURS = 4

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("WARNING: GEMINI_API_KEY not found in .env file")
client = genai.Client(api_key=api_key)

_cached_content = None
_is_rebuilding_cache = False

BASE_GEN_CONFIG = dict(response_mime_type="application/json", temperature=0, seed=42)

def _gen_config(**kw):
    c = dict(BASE_GEN_CONFIG)
    c.update(kw)
    return types.GenerateContentConfig(**c)

def _generate(model, contents, config):
    return client.models.generate_content(model=model, contents=contents, config=config)

def create_rule_cache():
    global _cached_content
    print("\n" + "=" * 40)
    print("COMPILING RULES & CREATING CONTEXT CACHE...")
    print("=" * 40)
    compiled_rules = compile_rules()
    stats = get_compiled_rules_stats(compiled_rules)
    print(f"  Rules: {stats['char_count']:,} chars, ~{stats['approx_tokens']:,} tokens | Meets 32K min: {stats['meets_32k_minimum']} | Est. cost: ${stats['estimated_cache_cost_per_hour']}/hr")
    try:
        _cached_content = client.caches.create(
            model=GEMINI_MODEL,
            config=types.CreateCachedContentConfig(
                contents=[types.Content(role="user", parts=[types.Part.from_text(text=compiled_rules)])],
                system_instruction=types.Content(parts=[types.Part.from_text(text="You are a Walmart product data quality evaluator. The SOP rules provided in the cached context are your ONLY source of truth. When comparing products, find the matching rule by category/product type, check which scenario's conditions apply, and return that scenario's decision. Always respond with valid JSON only — no markdown, no backticks.")]),
                ttl=f"{CACHE_TTL_HOURS * 3600}s",
                display_name="walmart-sop-rules"
            )
        )
        print(f"  Cache created: {_cached_content.name} | TTL: {CACHE_TTL_HOURS}h (expires ~{datetime.datetime.now() + datetime.timedelta(hours=CACHE_TTL_HOURS):%H:%M})")
    except Exception as e:
        print(f"  Cache creation FAILED: {e}")
        print("  Falling back to non-cached mode (rules sent per request)")
        _cached_content = None
    print("=" * 40 + "\n")

def delete_rule_cache():
    global _cached_content
    if _cached_content:
        try:
            client.caches.delete(name=_cached_content.name)
            print(f"Context cache deleted: {_cached_content.name}")
        except Exception as e:
            print(f"Failed to delete cache: {e}")
        _cached_content = None

def _safe_text(resp):
    try:
        return resp.text
    except (ValueError, Exception):
        return None

def _build_relaxed_safety():
    cats = ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT", "HARM_CATEGORY_CIVIC_INTEGRITY"]
    return [types.SafetySetting(category=c, threshold="BLOCK_NONE") for c in cats]

def _send(contents, use_cache=True, relaxed=False):
    config_kw = dict(BASE_GEN_CONFIG)
    if relaxed:
        config_kw["safety_settings"] = _build_relaxed_safety()
    if use_cache and _cached_content:
        config_kw["cached_content"] = _cached_content.name
        return _generate(GEMINI_MODEL, contents, _gen_config(**config_kw))
    else:
        compiled = compile_rules()
        full = [compiled] + contents
        return _generate(GEMINI_MODEL, full, _gen_config(**config_kw))

def generate_with_cache(contents: list) -> str:
    global _cached_content, _is_rebuilding_cache
    response = None
    if _cached_content:
        try:
            response = _send(contents, use_cache=True)
        except Exception as e:
            estr = str(e)
            if "CachedContent not found" in estr or "403" in estr or "PERMISSION_DENIED" in estr:
                print(f"Cache error (likely expired): {e}")
                print("Falling back to inline rules...")
                _cached_content = None
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
        response = _send(contents, use_cache=False)

    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        um = response.usage_metadata
        ct = getattr(um, 'cached_content_token_count', 0) or 0
        ti = getattr(um, 'prompt_token_count', 0) or 0
        ot = getattr(um, 'candidates_token_count', 0) or 0
        print(f"  Tokens — Input: {ti} (cached: {ct}) | Output: {ot}")
        if ct > 0 and ti > 0:
            print(f"  Cache hit: {ct / ti * 100:.1f}% of input from cache")

    text = _safe_text(response)
    if text is not None:
        return text

    finish_reason = "UNKNOWN"
    try:
        finish_reason = response.candidates[0].finish_reason.name
    except Exception:
        pass
    print(f"Gemini blocked (finish_reason={finish_reason}). Retrying with relaxed safety...")

    try:
        retry = _send(contents, use_cache=bool(_cached_content), relaxed=True)
        retry_text = _safe_text(retry)
        if retry_text:
            print("Retry with relaxed safety succeeded.")
            return retry_text
    except Exception as retry_err:
        print(f"Retry also failed: {retry_err}")

    raise Exception(f"Gemini API blocked response or returned no text. Finish reason: {finish_reason}")

async def fetch_image(client_http: httpx.AsyncClient, url: str) -> dict:
    try:
        resp = await client_http.get(url, timeout=10.0)
        resp.raise_for_status()
        raw = resp.content
        orig_kb = len(raw) / 1024
        img = Image.open(io.BytesIO(raw))
        orig_dims = img.size
        img.thumbnail((600, 600), Image.LANCZOS)
        new_dims = img.size
        buf = io.BytesIO()
        img.save(buf, format='WEBP', quality=85, method=6)
        buf.seek(0)
        final = buf.read()
        final_kb = len(final) / 1024
        pct = (1 - final_kb / orig_kb) * 100
        print(f"  Image {url.split('/')[-1][:30]}: {orig_dims[0]}x{orig_dims[1]}px->{new_dims[0]}x{new_dims[1]}px {orig_kb:.1f}KB->{final_kb:.1f}KB ({pct:.1f}% reduced)")
        return {"mime_type": "image/webp", "data": base64.b64encode(final).decode('utf-8')}
    except Exception as e:
        print(f"Error fetching image {url}: {e}")
        return None

def _build_image_parts(image_data_list: list) -> list:
    parts = []
    for img in image_data_list:
        if img:
            parts.append(types.Part.from_bytes(data=base64.b64decode(img["data"]), mime_type=img["mime_type"]))
    return parts

def format_error(e: Exception) -> tuple[int, str]:
    err_str = str(e)
    code = getattr(e, 'code', 500)
    msg = getattr(e, 'message', err_str)
    patterns = [
        ("RECITATION", (400, "Gemini blocked response due to Recitation/Copyright filter.")),
        ("SAFETY", (400, "Gemini blocked response due to Safety filters.")),
        ("HARM_CATEGORY", (400, "Gemini blocked response due to Safety filters.")),
        ("429", (429, "Gemini API Quota Exceeded or Rate Limited.")),
        ("Quota", (429, "Gemini API Quota Exceeded or Rate Limited.")),
        ("403", (403, "Gemini API Authentication or Permission Error.")),
        ("PERMISSION_DENIED", (403, "Gemini API Authentication or Permission Error.")),
    ]
    for substr, (sc, sm) in patterns:
        if substr in err_str:
            return sc, f"[HTTP {sc}] {sm}"
    return code, f"[HTTP {code}] {msg}"

# Static rules are now in the Gemini context cache (via system_prompt.py + rule_compiler.py).
# These framing prompts only contain dynamic per-request content.
SINGLE_ANALYSIS_FRAMING = "TASK: Analyze this product for internal data consistency (vertical check).\nProduct Title: {title}\nText Attributes: {attributes}\n\nUse the SOP rules and instructions from the cached context. Respond with JSON only."

BATCH_FRAMING = "TASK: Analyze these {n} products for duplicate/non-duplicate/bad-data.\nBelow are the products to analyze:\n"

def _append_images_to_parts(content_parts, image_data_list, fallback_text="[No Images Could Be Fetched — treat extracted_image_specs as 'None' for this product]"):
    has_img = False
    for img in image_data_list:
        if img:
            content_parts.append(types.Part.from_bytes(data=base64.b64decode(img["data"]), mime_type=img["mime_type"]))
            has_img = True
    if not has_img:
        content_parts.append(types.Part.from_text(text=fallback_text))

async def process_analysis(title, attributes, imageUrls):
    prompt = SINGLE_ANALYSIS_FRAMING.format(title=title, attributes=json.dumps(attributes, indent=2))
    image_parts = []
    async with httpx.AsyncClient() as http_client:
        fetched = await asyncio.gather(*[fetch_image(http_client, url) for url in imageUrls])
        for img in fetched:
            if img:
                image_parts.append(img)
    if not image_parts:
        return {"status": "error", "message": "[HTTP 400] Could not fetch any images.", "status_code": 400}
    try:
        print("\n" + "=" * 40)
        print("SENDING REQUEST TO GEMINI (Single Analysis)")
        print("=" * 40)
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)] + _build_image_parts(image_parts))]
        response_text = generate_with_cache(contents)
        if not response_text:
            raise Exception("Gemini API returned an empty response.")
        text = response_text.strip()
        print("\n" + "=" * 40)
        print("RECEIVED RESPONSE FROM GEMINI")
        print("=" * 40)
        print(text)
        print("=" * 40 + "\n")
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

    # Build per-request framing — just product data + cardinal reminders.
    # All static rules/instructions are in the cache.
    prompt = BATCH_FRAMING.format(n=n)
    prompt += (
        f"\nFINAL REMINDERS BEFORE YOU RESPOND\n"
        f"• You are analyzing EXACTLY {n} products.\n"
        f"• Your vertical_checks array MUST contain EXACTLY {n} entries —\n"
        f"  one for each product_id listed above. Do NOT skip, merge, or omit ANY product.\n"
        f"• CLUSTERING REMINDER:\n"
        f"  - Each BAD DATA product → its OWN standalone cluster.\n"
        f"  - DUPLICATE products → ONE shared cluster.\n"
        f"  - Each NOT DUPLICATE product → its OWN standalone cluster.\n"
        f"  - Following this rule: if you have 2 bad data + 3 duplicates + 1 not a duplicate,\n"
        f"    you MUST output exactly 4 clusters.\n"
        f"• 'Not sure bad data' is LAST RESORT. Use actions 2-5 first.\n"
        f"  Do NOT use Bad Data for missing attributes or OCR gaps.\n"
    )
    if n == 2:
        prompt += (
            f"• SPECIAL RULE FOR EXACTLY 2 PRODUCTS:\n"
            f"  - If ANY ONE of the 2 products evaluates to 'Not sure bad data' in the vertical check, you MUST classify ALL of them as 'Not sure bad data' in horizontal clustering.\n"
            f"  - EXCEPTION: If the images of the 2 products are clearly different visually (e.g., different shapes, colors, or structural designs), you MUST force mark them as 'Not duplicate', completely overriding the Bad Data rule above.\n"
            f"  - If they are duplicates, classify the cluster as 'Duplicate'.\n"
            f"  - Otherwise, use the standard rules.\n"
        )

    content_parts = [types.Part.from_text(text=prompt)]
    async with httpx.AsyncClient() as http_client:
        image_cache = {}
        for p in products:
            prod_id = p.get('id', 'Unknown')
            content_parts.append(types.Part.from_text(text=(
                f"\n\n--- PRODUCT ID: {prod_id} ---\n"
                f"Title: {p.get('title')}\n"
                f"Description: {p.get('description', '')}\n"
                f"Attributes: {json.dumps(p.get('attributes', {}), indent=2)}\n"
                f"Images for {prod_id}:"
            )))
            urls = p.get('imageUrls', [])
            if not urls:
                content_parts.append(types.Part.from_text(text="[No Images Provided for this product]"))
                continue
            sig = tuple(sorted(set(urls)))
            if sig in image_cache:
                _append_images_to_parts(content_parts, image_cache[sig], "[No Images Could Be Fetched for this product]")
            else:
                fetched = await asyncio.gather(*[fetch_image(http_client, url) for url in urls])
                image_cache[sig] = fetched
                _append_images_to_parts(content_parts, fetched)

    try:
        print("\n" + "=" * 40)
        print("SENDING REQUEST TO GEMINI (Batch Analysis)")
        print("=" * 40)
        for idx, part in enumerate(content_parts):
            if hasattr(part, 'text') and part.text:
                print(f"--- Text Part {idx} ---\n{part.text[:200]}...\n")
            else:
                print(f"--- Image Part {idx} ---")
        print("=" * 40 + "\n")
        contents = [types.Content(role="user", parts=content_parts)]
        response_text = generate_with_cache(contents)
        if not response_text:
            raise Exception("Gemini API returned an empty response.")
        text = response_text.strip().replace("```json", "").replace("```", "").strip()
        print("\n" + "=" * 40)
        print("RECEIVED RESPONSE FROM GEMINI")
        print("=" * 40)
        print(text)
        print("=" * 40 + "\n")
        data = json.loads(text)
        output_ids = {v['product_id'] for v in data.get('vertical_checks', [])}
        input_ids = {p.get('id', 'Unknown') for p in products}
        missing_ids = {i_id for i_id in input_ids if not any(i_id in o_id or o_id in i_id for o_id in output_ids)}
        retries_left = MAX_RETRIES
        while missing_ids and retries_left > 0:
            retries_left -= 1
            print(f"\nRetrying — Gemini returned {len(output_ids)}/{n}. Missing: {missing_ids}")
            correction = f"\n\n--- CORRECTION ---\nYou only returned {len(output_ids)} vertical_checks entries, but there are {n} products. You MISSED: {missing_ids}. Output COMPLETE analysis for ALL {n} — vertical_checks MUST contain exactly {n} entries. Every product_id MUST appear once.\nAlso recheck clustering: bad data products each get their own standalone cluster."
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
            newly_missing = {i_id for i_id in input_ids if not any(i_id in o_id or o_id in i_id for o_id in retry_ids)}
            recovered = len(missing_ids) - len(newly_missing)
            if recovered > 0:
                print(f"  Retry recovered {recovered} product(s) ({len(retry_ids)} total, still missing {newly_missing})")
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
                id_order = [p.get('id', 'Unknown') for p in products]
                merged.sort(key=lambda v: id_order.index(v['product_id']) if v['product_id'] in id_order else len(id_order))
                data['vertical_checks'] = merged
                data['horizontal_clustering'] = retry_data.get('horizontal_clustering', data.get('horizontal_clustering', []))
                output_ids = input_ids - newly_missing
                missing_ids = newly_missing
            else:
                print("  Retry did not improve, keeping original response.")
                break
        if missing_ids:
            print(f"FINAL: {len(missing_ids)} product(s) still missing after retries: {missing_ids}")
        return {"status": "success", "data": data}
    except json.JSONDecodeError:
        print("Failed to parse JSON:", text)
        return {"status": "error", "message": "[API 422] Invalid JSON response from AI.", "status_code": 422}
    except Exception as e:
        print("Batch Analysis Error:", e)
        code, msg = format_error(e)
        return {"status": "error", "message": msg, "status_code": code}

app = Flask(__name__)
CORS(app)

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "running",
        "message": "DupCheck Backend is active and listening.",
        "context_cache": "active" if _cached_content else "inactive (fallback mode)",
        "cache_name": _cached_content.name if _cached_content else None,
    })

@app.route("/api/cache-status", methods=["GET"])
def cache_status():
    if _cached_content:
        return jsonify({"cached": True, "cache_name": _cached_content.name, "model": GEMINI_MODEL, "ttl_hours": CACHE_TTL_HOURS})
    return jsonify({"cached": False, "message": "No active context cache. Rules sent inline per request."})

@app.route("/api/cache-refresh", methods=["POST"])
def cache_refresh():
    delete_rule_cache()
    create_rule_cache()
    if _cached_content:
        return jsonify({"status": "success", "cache_name": _cached_content.name})
    return jsonify({"status": "error", "message": "Cache creation failed"}), 500

@app.route("/test-ai", methods=["GET"])
def test_ai():
    result = asyncio.run(process_analysis(
        "Bulbasaur",
        {"Type": "Grass", "Color": "Blue"},
        ["https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png"]
    ))
    return f"""
    <html><body style="font-family:monospace;background:#1e1e1e;color:#00ff00;padding:20px;">
    <h2>AI Vision Test Result</h2><pre>{json.dumps(result, indent=4)}</pre>
    </body></html>
    """

@app.route("/api/analyze-column", methods=["POST"])
def analyze_column():
    req = request.get_json()
    if not req.get("imageUrls"):
        return jsonify({"status": "error", "message": "[HTTP 400] No image URLs provided for analysis.", "status_code": 400}), 400
    result = asyncio.run(process_analysis(req.get("title", ""), req.get("attributes", {}), req.get("imageUrls", [])))
    if result.get("status") == "error":
        return jsonify(result), result.get("status_code", 500)
    return jsonify(result)

@app.route("/api/analyze-batch", methods=["POST"])
def analyze_batch():
    products = request.get_json().get("products", [])
    print(f"Received batch analysis request for {len(products)} products")
    if not products:
        return jsonify({"status": "error", "message": "[HTTP 400] No products provided for analysis.", "status_code": 400}), 400
    print("Running AI batch analysis...")
    result = asyncio.run(process_batch_analysis(products))
    if result.get("status") == "error":
        return jsonify(result), result.get("status_code", 500)
    return jsonify(result)

if __name__ == "__main__":
    create_rule_cache()
    atexit.register(delete_rule_cache)
    print("DupCheck backend running on http://localhost:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)
