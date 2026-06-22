import os
import json
import base64
import asyncio
import tempfile
import httpx
import hashlib
import io
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv

CACHE_FILE = "ai_analysis_cache.json"

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
        fd, tmp_path = tempfile.mkstemp(dir='.', prefix='.cache_tmp_', suffix='.json')
        with os.fdopen(fd, 'w') as f:
            json.dump(cache_data, f)
        os.replace(tmp_path, CACHE_FILE)
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

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    print("WARNING: GEMINI_API_KEY not found in .env file")

app = Flask(__name__)
# Restrict CORS to known origins — extension runs from Chrome on localhost
CORS(app, origins=[
    'http://localhost:8000',
    'http://localhost:8080',
    'chrome-extension://',
    'https://dupcheck.duckdns.org'
])

async def fetch_image(client: httpx.AsyncClient, url: str) -> dict:
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
                avif_response = await client.get(avif_url, timeout=10.0, headers=avif_headers)
                if avif_response.status_code == 200:
                    raw_bytes = avif_response.content
                    source_format = "AVIF"
                else:
                    print(f"⚠️  AVIF not available (HTTP {avif_response.status_code}), falling back to JPEG")
            except Exception as avif_err:
                print(f"⚠️  AVIF fetch failed ({avif_err}), falling back to JPEG")

        if raw_bytes is None:
            response = await client.get(url, timeout=10.0)
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
#  SINGLE PRODUCT ANALYSIS PROMPT  (column-level / single GTIN check)
# ─────────────────────────────────────────────────────────────────────────────
SINGLE_ANALYSIS_PROMPT_TEMPLATE = """
You are a strict product data-quality checker.
I am providing you with a product's text attributes, title, and images.

Product Title: {title}
Text Attributes: {attributes}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 0 — DETECT PRODUCT CATEGORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
First, infer the product category from the title and attributes (e.g., clothing, footwear, furniture,
rug/carpet, electronics, paint/coatings, food/beverage, bedding, pet supplies, tools, etc.).
This determines which attributes are "primary" (must be checked) and which are noise.

PRIMARY ATTRIBUTES BY CATEGORY (non-exhaustive guide):
  • Clothing / footwear  → size, color, gender, material, style name/number
  • Rugs / carpets       → size (dimensions), pile height, color, material, style
  • Furniture (bed/sofa/chair) → dimensions, color, material, style/model
  • Electronics / remotes     → model number, compatibility, voltage, capacity
  • Paint / coatings     → finish (matte/satin/gloss/semi-gloss/flat), color name + code, volume
  • Food / beverages     → flavor, count/pack size, weight/volume, dietary claims relevant to identity
  • Pet supplies (food)  → animal type, flavor, life-stage, weight
  • Bedding              → size (Twin/Full/Queen/King), material, thread count, color/pattern
  • Tools / hardware     → model number, size/dimensions, material, voltage/wattage
  • All other / General  → size/dimensions/measurements, count/pack size, model number, style name, capacity/volume

CRITICAL RULE: Size, capacity, weight, pack count, and model number are ALWAYS primary attributes for ALL products, regardless of category.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 1 — EXTRACT SPECS FROM IMAGES (OCR)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Carefully read ALL text written directly on the product or its packaging in each image.
Focus on extracting specs that are PRIMARY ATTRIBUTES for the detected category.

WHAT TO EXTRACT (concrete specs that uniquely identify or describe the product):
  ✔ Size / dimensions (e.g., "XL", "10 oz", "5'x8'", "12x24 in")
  ✔ Count / pack size  (e.g., "2-Pack", "Set of 4", "Count: 6")
  ✔ Model number / style name (e.g., "LMS04 88175", "Duchess", "Model A200")
  ✔ Color name / finish type (e.g., "Matte", "Glossy", "Semi-Gloss", "Cobalt Blue")
  ✔ Weight / volume with units (e.g., "500g", "1.5 lbs", "750ml")
  ✔ Compatibility statements (e.g., "Compatible with Samsung Series 7")
  ✔ Pile height (for rugs) (e.g., "0.5 in pile")
  ✔ Numeric identifiers visible on the product itself

WHAT TO IGNORE (do not extract or flag):
  ✗ Generic marketing slogans ("Great Value!", "New & Improved", "Best Quality")
  ✗ Subjective adjectives without numeric backing ("Natural", "Vibrant", "Pro", "Premium")
  ✗ Brand logos or retailer names
  ✗ Nutritional/ingredient details UNLESS the product IS a food and the field mismatch is on flavor or life-stage
  ✗ Background text, barcodes, or decorative patterns

CRITICAL — FINISH TYPE (paint/coatings category):
  If the product is a paint or coating, you MUST read and report the finish type (Matte, Flat, Eggshell,
  Satin, Semi-Gloss, Gloss, High-Gloss) from the image label as a primary spec. This is NOT optional.

If no spec text at all is readable on the images, write "None" and do NOT flag a contradiction.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STEP 2 — COMPARE IMAGE SPECS VS TEXT ATTRIBUTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Compare only the extracted image specs against the provided Text Attributes and Title.

FLAG as a contradiction ONLY when:
  • An extracted spec explicitly and directly contradicts an attribute (e.g., image says "2-Pack"
    but attribute says "Count: 1"; image says "Matte" but attribute says "Finish: Gloss").
  • Numeric values with the same units differ (e.g., "10 oz" on image vs "16 oz" in attributes).
  • A model number or style name on the image differs from the model/style in the attributes.

DO NOT FLAG:
  • Missing information (attribute not on image = not a contradiction).
  • Differences in marketing language or subjective descriptions.
  • Ambiguous cases where the image text could refer to a related but non-conflicting spec.

Respond STRICTLY with a JSON object — no markdown, no backticks:
{{
  "detected_category": "string (category you detected in Step 0)",
  "primary_attributes_checked": ["list of attribute names relevant for this category"],
  "extracted_image_specs": "string (concise summary of specs read from images, or 'None')",
  "hasInconsistency": boolean,
  "inconsistencies": [
    {{
      "field": "string (the attribute or spec in question)",
      "imageValue": "string (exact spec text from image)",
      "textValue": "string (exact text from product attributes)",
      "reason": "string (precise explanation of the contradiction)"
    }}
  ]
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
#  BATCH ANALYSIS PROMPT  (multi-GTIN duplicate / bad-data check)
# ─────────────────────────────────────────────────────────────────────────────
BATCH_ANALYSIS_PROMPT = """
You are a strict product data-consistency and duplicate-detection system.
I will provide multiple product listings. Each has a product_id, title, description, text attributes, and images.

════════════════════════════════════════════════════════════════
STEP 0 — DETECT PRODUCT CATEGORY FOR EACH PRODUCT
════════════════════════════════════════════════════════════════
Before any other analysis, infer the product category for each product_id from its title and attributes.
Use the category to determine which attributes are PRIMARY (essential for identity checks) and which are NOISE.

PRIMARY ATTRIBUTES BY CATEGORY (use as your checklist — non-exhaustive):
  • Clothing / footwear       → size, color, gender, material, style name/number
  • Rugs / carpets            → dimensions (length × width), pile height, color, material, style name
  • Furniture (beds/sofas/chairs) → dimensions, color, material, style/model name
  • Electronics / remotes     → model number, compatibility (device/brand), voltage, capacity
  • Paint / coatings          → finish type (Matte/Flat/Eggshell/Satin/Semi-Gloss/Gloss), color name + code, volume/size
  • Food / beverages          → flavor, count/pack size, weight/volume
  • Pet supplies (food/treats)→ animal type, flavor/variety, life-stage, weight
  • Bedding                   → size (Twin/Full/Queen/King), material, thread count, color/pattern
  • Tools / hardware          → model number, dimensions, material, voltage/wattage
  • All other / General       → size/dimensions/measurements, count/pack size, model number, style name, capacity/volume

CRITICAL RULE: Size, capacity, weight, pack count, and model number are ALWAYS primary attributes for ALL products, regardless of category.

NOISE ATTRIBUTES (ignore these in ALL categories — do not use them to flag differences or similarities):
  • Generic marketing words: "Natural", "Premium", "Pro", "Max", "New", "Improved", "Best", "Clear"
  • Subjective descriptors not tied to a concrete spec: "Vibrant", "Soft", "Durable", "Fresh"
  • Nutritional breakdowns (calories, sugar, fat) UNLESS product IS a food and flavor is the question
  • Certifications / awards (unless directly part of a claimed identity spec)
  • Background decorative text, barcodes, retailer tags in images

════════════════════════════════════════════════════════════════
PHASE 1 — VERTICAL CHECK (BAD DATA — per product)
════════════════════════════════════════════════════════════════
For each product individually:

A) IMAGE OCR — EXTRACT PRIMARY SPECS FROM IMAGES
   Read ALL text written directly on the product or packaging in every image provided.
   You MUST attempt to read:
     ✔ Size / dimensions with units (e.g., "XL", "5'x8'", "10 oz", "750ml", "500g", "29/64\"", "3/8\"")
     ✔ Count / pack size (e.g., "2-Pack", "Set of 4", "6 Count")
     ✔ Model number / style name (e.g., "LMS04 88175", "Duchess", "A200")
     ✔ Color name (e.g., "Cobalt Blue", "Charcoal Grey")
     ✔ FINISH TYPE — MANDATORY for paint/coatings: read and report "Matte", "Flat", "Eggshell",
       "Satin", "Semi-Gloss", "Gloss", or "High-Gloss" exactly as printed on the can/label.
     ✔ Compatibility text (e.g., "For Samsung Series 7")
     ✔ Pile height for rugs (e.g., "0.5\" pile", "Low pile")
     ✔ Numeric identifiers physically printed on the product

   IMPORTANT — DO NOT report:
     ✗ Marketing slogans or subjective phrases (see NOISE list above)
     ✗ Ingredients / nutritional panels (unless flavor/variety is in question for food products)
     ✗ Logos, brand names, retailer labels
     ✗ If genuinely no spec text is readable, set extracted_image_specs = "None" — this is valid and does NOT trigger bad_data.

B) CONTRADICTION CHECK
   Compare the extracted image specs against the product's Text Attributes and Title.
   
   FLAG has_bad_data = true ONLY when an extracted spec DIRECTLY contradicts an attribute:
     ✔ Different size/count on image vs attributes (e.g., "2-Pack" image, "Count: 1" attribute)
     ✔ Different model number (e.g., "LMS04" image vs "LMS01" attribute)
     ✔ Different finish type for paint (e.g., "Matte" image vs "Gloss" attribute)
     ✔ Different numeric value with same unit (e.g., "10 oz" image vs "16 oz" attribute)
     ✔ Different style/variant name (e.g., "Duchess" image vs "Noblesse" attribute)

   DO NOT flag has_bad_data for:
     ✗ Missing info (spec not on image = no contradiction)
     ✗ Junk/marketing text differences
     ✗ Ambiguous cases that could be consistent with a different reading

════════════════════════════════════════════════════════════════
PHASE 2 — HORIZONTAL CHECK (DUPLICATE CLUSTERING)
════════════════════════════════════════════════════════════════
For products that PASS Phase 1 (has_bad_data = false), compare them against each other.
Also include products with bad data in their own separate cluster (they cannot be merged with clean products).

CLUSTERING RULES — apply in strict priority order:

RULE 1 — EXTRACTED IMAGE SPECS TAKE ABSOLUTE PRIORITY:
  If the extracted_image_specs of two products contain ANY differing size, dimensions, count, capacity, volume, model number, finish type, style name, color, or other primary attribute, those products MUST be placed in SEPARATE clusters — even if ALL table attributes are identical.
  Any differing numeric measurement or size (such as "29/64\"" vs "3/8\"") means they are NOT DUPLICATES.
  Identical table attributes alone are NEVER sufficient to call two products duplicates if their image specs differ.

RULE 2 — TEXT ATTRIBUTE DIFFERENCES ON PRIMARY ATTRIBUTES:
  If two products have different values for any PRIMARY ATTRIBUTE in their text attributes
  (e.g., different model, different size, different compatibility), place them in SEPARATE clusters,
  even if the extracted image specs are both "None".

RULE 3 — JUNK ATTRIBUTE DIFFERENCES ARE IGNORED:
  Differences ONLY in NOISE attributes (marketing words, junk descriptions, extra irrelevant fields)
  must NOT be used to separate products into different clusters.
  If two products are identical on all PRIMARY attributes, they are duplicates even if their
  description contains different filler text.

RULE 4 — PRODUCTS WITH BAD DATA:
  Any product with has_bad_data = true goes into its own individual cluster labeled "Bad Data — [product_id]".
  It must NEVER be merged with another product, even if table attributes look identical.

RULE 5 — FINISH TYPE FOR PAINT (mandatory separation):
  Two paint products with the same color but DIFFERENT finish types (e.g., Matte vs Semi-Gloss)
  are VARIANTS, not duplicates. They MUST be in separate clusters.

RULE 6 — SIZE UNITS AWARENESS:
  When comparing sizes, normalize units before comparing (e.g., "10 oz" ≠ "16 oz"; "5'x8'" ≠ "8'x10'"; "29/64\"" ≠ "3/8\"").
  If a size or dimension difference exists in the image specs, that alone is sufficient to separate clusters.

DEFINING A CLUSTER:
  A "cluster" represents a group of products that are identical duplicates and can be merged.
  - True duplicates MUST be grouped in the same cluster.
  - Products that are VARIANTS (e.g. different size, color, finish, count) or UNIQUE products MUST be placed in SEPARATE clusters (each in its own object in the `horizontal_clustering` array).
  - If you have 2 products and they are variants of each other, you MUST output 2 separate clusters in the array, each containing exactly one product ID. Do NOT group them into a single cluster.

CLUSTER LABELS:
  Use descriptive names:
    • "Duplicates — [shared product type/color/model]"   (for a cluster containing multiple identical product IDs)
    • "Variant — [product_id] ([what differs])"           (for a cluster containing exactly ONE product ID)
    • "Unique — [product_id]"                            (for a cluster containing exactly ONE product ID)
    • "Bad Data — [product_id]"                          (for Phase 1 failures, containing exactly ONE product ID)

════════════════════════════════════════════════════════════════
OUTPUT FORMAT
════════════════════════════════════════════════════════════════
Respond STRICTLY with this JSON — no markdown, no backticks:
{
  "vertical_checks": [
    {
      "product_id": "string",
      "detected_category": "string (category from Step 0)",
      "primary_attributes_checked": ["list of attribute names relevant for this category"],
      "extracted_image_specs": "string (concise summary of readable spec text from images, or 'None')",
      "has_bad_data": boolean,
      "reason": "string (HIGHLY DESCRIPTIVE — state exactly what text was read from the image, what text was in the table/description, and precisely where the contradiction is. If no bad data, explain why the product passes.)",
      "mismatch_details": [
        {
          "field": "string (exact attribute name)",
          "imageValue": "string (exact spec text from image)",
          "textValue": "string (exact text from product attributes)"
        }
      ]
    }
  ],
  "horizontal_clustering": [
    {
      "cluster_name": "string (descriptive label per CLUSTER LABELS above)",
      "product_ids": ["string", "string"],
      "cluster_type": "string (one of: 'duplicate', 'variant', 'unique', 'bad_data')",
      "reason": "string (HIGHLY DESCRIPTIVE — state exactly which PRIMARY attributes were compared, what the values were for each product_id, and specifically WHY they are together or apart. If separated due to image spec differences, name the exact spec text and product IDs. If merged as duplicates, confirm both primary attribute match AND image spec match or both are 'None'.)"
    }
  ]
}
"""


async def process_analysis(title, attributes, imageUrls):
    prompt = SINGLE_ANALYSIS_PROMPT_TEMPLATE.format(
        title=title,
        attributes=json.dumps(attributes, indent=2)
    )

    image_parts = []
    async with httpx.AsyncClient() as client:
        tasks = [fetch_image(client, url) for url in imageUrls]
        fetched_images = await asyncio.gather(*tasks)
        for img in fetched_images:
            if img:
                image_parts.append(img)

    if not image_parts:
        return {"status": "error", "message": "Could not fetch any images."}

    try:
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        contents = [prompt]
        for img in image_parts:
            contents.append(img)

        print("\n" + "="*50)
        print("🚀 SENDING REQUEST TO GEMINI (Single Analysis)")
        print("="*50)
        for idx, item in enumerate(contents):
            if isinstance(item, str):
                print(f"--- Text Part {idx} ---\n{item}\n")
            elif isinstance(item, dict):
                print(f"--- Image Part {idx} --- [Mime Type: {item.get('mime_type')}, Data Length: {len(item.get('data', ''))}]")
        print("="*50 + "\n")

        response = model.generate_content(contents)

        if not response.text:
            return {"status": "error", "message": "no response by ai"}

        text = response.text.strip()
        print("\n" + "="*50)
        print("✅ RECEIVED RESPONSE FROM GEMINI (Single Analysis)")
        print("="*50)
        print(f"{text}")
        print("="*50 + "\n")
        text = text.replace("```json", "").replace("```", "").strip()

        return {"status": "success", "data": json.loads(text)}

    except json.JSONDecodeError:
        print("Failed to parse JSON:", text)
        return {"status": "error", "message": "Invalid JSON response from AI"}
    except Exception as e:
        print("Analysis Error:", e)
        return {"status": "error", "message": str(e)}


async def process_batch_analysis(products):
    contents = [BATCH_ANALYSIS_PROMPT]

    async with httpx.AsyncClient() as client:
        seen_image_sets = {}

        for p in products:
            prod_id = p.get('id', 'Unknown')
            prod_text = (
                f"\n\n--- PRODUCT ID: {prod_id} ---\n"
                f"Title: {p.get('title')}\n"
                f"Description: {p.get('description', '')}\n"
                f"Attributes: {json.dumps(p.get('attributes', {}), indent=2)}\n"
                f"Images for {prod_id}:"
            )
            contents.append(prod_text)

            urls = p.get('imageUrls', [])

            if not urls:
                contents.append("[No Images Provided for this product]")
                continue

            url_signature = tuple(sorted(list(set(urls))))

            if url_signature in seen_image_sets:
                first_prod_id = seen_image_sets[url_signature]
                contents.append(
                    f"[The images for this product are EXACTLY identical to the images provided above "
                    f"for PRODUCT ID: {first_prod_id}. Please reference those images and use the same "
                    f"extracted_image_specs for this product as you determined for {first_prod_id}.]"
                )
            else:
                seen_image_sets[url_signature] = prod_id
                tasks = [fetch_image(client, url) for url in urls]
                fetched_images = await asyncio.gather(*tasks)

                has_img = False
                for img in fetched_images:
                    if img:
                        contents.append(img)
                        has_img = True

                if not has_img:
                    contents.append("[No Images Could Be Fetched — treat extracted_image_specs as 'None' for this product]")

    try:
        print("\n" + "="*50)
        print("🚀 SENDING REQUEST TO GEMINI (Batch Analysis)")
        print("="*50)
        for idx, item in enumerate(contents):
            if isinstance(item, str):
                print(f"--- Text Part {idx} ---\n{item}\n")
            elif isinstance(item, dict):
                print(f"--- Image Part {idx} --- [Mime Type: {item.get('mime_type')}, Data Length: {len(item.get('data', ''))}]")
        print("="*50 + "\n")

        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        response = model.generate_content(contents)

        if not response.text:
            return {"status": "error", "message": "no response by ai"}

        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        print("\n" + "="*50)
        print("✅ RECEIVED RESPONSE FROM GEMINI (Batch Analysis)")
        print("="*50)
        print(f"{text}")
        print("="*50 + "\n")
        return {"status": "success", "data": json.loads(text)}

    except json.JSONDecodeError:
        print("Failed to parse JSON:", text)
        return {"status": "error", "message": "Invalid JSON response from AI"}
    except Exception as e:
        print("Batch Analysis Error:", e)
        return {"status": "error", "message": str(e)}


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "running", "message": "DupCheck Backend is active and listening."})


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


if __name__ == "__main__":
    print("DupCheck backend running on http://localhost:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)