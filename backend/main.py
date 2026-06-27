# import os
# import json
# import base64
# import tempfile
# import asyncio
# import httpx
# import hashlib
# import io
# import atexit
# import datetime
# from PIL import Image
# from flask import Flask, request, jsonify
# from flask_cors import CORS
# from google import genai
# from google.genai import types
# from dotenv import load_dotenv

# from rule_compiler import compile_rules, get_compiled_rules_stats

# # ─────────────────────────────────────────────────────────────────────────────
# #  CONFIGURATION
# # ─────────────────────────────────────────────────────────────────────────────
# CACHE_FILE = "ai_analysis_cache.json"
# GEMINI_MODEL = "gemini-2.5-flash"
# CACHE_TTL_HOURS = 4  # How long the context cache stays alive

# load_dotenv()

# api_key = os.getenv("GEMINI_API_KEY")
# if not api_key:
#     print("WARNING: GEMINI_API_KEY not found in .env file")

# # Initialize the new google-genai client
# client = genai.Client(api_key=api_key)


# # ─────────────────────────────────────────────────────────────────────────────
# #  CONTEXT CACHE MANAGEMENT
# # ─────────────────────────────────────────────────────────────────────────────
# _cached_content = None  # Module-level reference to the active cache


# def create_rule_cache():
#     """
#     Compile rules.json into compact text and create a Gemini context cache.
#     This is called ONCE at server startup. The cache persists for CACHE_TTL_HOURS.
#     """
#     global _cached_content

#     print("\n" + "=" * 60)
#     print("📦 COMPILING RULES & CREATING CONTEXT CACHE...")
#     print("=" * 60)

#     # Step 1: Compile rules into compact text
#     compiled_rules = compile_rules()
#     stats = get_compiled_rules_stats(compiled_rules)

#     print(f"  ✅ Compiled rules: {stats['char_count']:,} chars, ~{stats['approx_tokens']:,} tokens")
#     print(f"  ✅ Meets 32K minimum: {stats['meets_32k_minimum']}")
#     print(f"  💰 Est. cache cost: ${stats['estimated_cache_cost_per_hour']}/hour")

#     # Step 2: Create the context cache with Gemini
#     try:
#         _cached_content = client.caches.create(
#             model=GEMINI_MODEL,
#             config=types.CreateCachedContentConfig(
#                 contents=[
#                     types.Content(
#                         role="user",
#                         parts=[types.Part.from_text(text=compiled_rules)]
#                     )
#                 ],
#                 system_instruction=types.Content(
#                     parts=[types.Part.from_text(
#                         text=(
#                             "You are a Walmart product data quality evaluator. "
#                             "The SOP rules provided in the cached context are your ONLY source of truth. "
#                             "When comparing products, find the matching rule by category/product type, "
#                             "check which scenario's conditions apply, and return that scenario's decision. "
#                             "Always respond with valid JSON only — no markdown, no backticks."
#                         )
#                     )]
#                 ),
#                 ttl=f"{CACHE_TTL_HOURS * 3600}s",
#                 display_name="walmart-sop-rules"
#             )
#         )

#         print(f"  ✅ Cache created: {_cached_content.name}")
#         print(f"  ⏰ TTL: {CACHE_TTL_HOURS} hours (expires ~{datetime.datetime.now() + datetime.timedelta(hours=CACHE_TTL_HOURS):%H:%M})")
#         print("=" * 60 + "\n")

#     except Exception as e:
#         print(f"  ❌ Cache creation FAILED: {e}")
#         print("  ⚠️  Falling back to non-cached mode (rules sent per request)")
#         print("=" * 60 + "\n")
#         _cached_content = None


# def delete_rule_cache():
#     """Delete the context cache on shutdown to stop billing."""
#     global _cached_content
#     if _cached_content:
#         try:
#             client.caches.delete(name=_cached_content.name)
#             print(f"🗑️  Context cache deleted: {_cached_content.name}")
#         except Exception as e:
#             print(f"⚠️  Failed to delete cache (may have expired): {e}")
#         _cached_content = None


# def get_model():
#     """
#     Return a model reference — cached if available, fallback otherwise.
#     When using the cached model, rules are NOT sent per request.
#     """
#     if _cached_content:
#         return _cached_content.name
#     return None


# def generate_with_cache(contents: list) -> str:
#     """
#     Generate content using the cached context if available.
#     Falls back to sending rules inline if cache is not available.
#     """
#     cache_name = get_model()

#     if cache_name:
#         # Cached mode — rules are already in the cache, just send product data
#         response = client.models.generate_content(
#             model=GEMINI_MODEL,
#             contents=contents,
#             config=types.GenerateContentConfig(
#                 cached_content=cache_name,
#                 temperature=0.0,
#                 seed=42
#             )
#         )
#     else:
#         # Fallback — send compiled rules inline (more expensive)
#         compiled_rules = compile_rules()
#         full_contents = [compiled_rules] + contents
#         response = client.models.generate_content(
#             model=GEMINI_MODEL,
#             contents=full_contents,
#             config=types.GenerateContentConfig(
#                 temperature=0.0,
#                 seed=42
#             )
#         )

#     # Log cache usage stats
#     if hasattr(response, 'usage_metadata') and response.usage_metadata:
#         um = response.usage_metadata
#         cached_tokens = getattr(um, 'cached_content_token_count', 0) or 0
#         total_input = getattr(um, 'prompt_token_count', 0) or 0
#         output_tokens = getattr(um, 'candidates_token_count', 0) or 0
#         print(f"  📊 Tokens — Input: {total_input} (cached: {cached_tokens}) | Output: {output_tokens}")
#         if cached_tokens > 0:
#             savings_pct = (cached_tokens / total_input * 100) if total_input > 0 else 0
#             print(f"  💰 Cache hit: {savings_pct:.1f}% of input tokens served from cache")

#     return response.text


# # ─────────────────────────────────────────────────────────────────────────────
# #  LOCAL RESPONSE CACHE  (unchanged from original)
# # ─────────────────────────────────────────────────────────────────────────────
# def get_cache():
#     if os.path.exists(CACHE_FILE):
#         try:
#             with open(CACHE_FILE, 'r') as f:
#                 return json.load(f)
#         except Exception:
#             return {}
#     return {}

# def save_cache(cache_data):
#     try:
#         fd, tmp_path = tempfile.mkstemp(dir='.', prefix='.cache_tmp_', suffix='.json')
#         with os.fdopen(fd, 'w') as f:
#             json.dump(cache_data, f)
#         os.replace(tmp_path, CACHE_FILE)
#     except Exception as e:
#         print("Failed to save cache:", e)

# def get_cache_key(products):
#     normalized_products = []
#     for p in products:
#         norm_p = p.copy()
#         if 'imageUrls' in norm_p and isinstance(norm_p['imageUrls'], list):
#             norm_p['imageUrls'] = sorted(list(set(norm_p['imageUrls'])))
#         normalized_products.append(norm_p)
#     payload_str = json.dumps(normalized_products, sort_keys=True)
#     return hashlib.md5(payload_str.encode('utf-8')).hexdigest()


# # ─────────────────────────────────────────────────────────────────────────────
# #  IMAGE FETCHING  (unchanged from original)
# # ─────────────────────────────────────────────────────────────────────────────
# async def fetch_image(client_http: httpx.AsyncClient, url: str) -> dict:
#     try:
#         response = await client_http.get(url, timeout=10.0)
#         response.raise_for_status()
#         raw_bytes = response.content
#         source_format = "ORIGINAL"

#         original_size_kb = len(raw_bytes) / 1024
#         img = Image.open(io.BytesIO(raw_bytes))
#         original_dims = img.size
#         img.thumbnail((600, 600), Image.LANCZOS)
#         new_dims = img.size
#         output = io.BytesIO()
#         img.save(output, format='WEBP', quality=85, method=6)
#         output.seek(0)
#         final_bytes = output.read()
#         final_size_kb = len(final_bytes) / 1024
#         reduction_pct = (1 - final_size_kb / original_size_kb) * 100
#         print(
#             f"🖼️  [{source_format}] "
#             f"{original_dims[0]}x{original_dims[1]}px → {new_dims[0]}x{new_dims[1]}px (color WebP) | "
#             f"Downloaded: {original_size_kb:.1f} KB  →  Final: {final_size_kb:.1f} KB  "
#             f"({reduction_pct:.1f}% reduced)"
#         )
#         return {
#             "mime_type": "image/webp",
#             "data": base64.b64encode(final_bytes).decode('utf-8')
#         }
#     except Exception as e:
#         print(f"Error fetching image {url}: {e}")
#         return None


# # ─────────────────────────────────────────────────────────────────────────────
# #  PROMPTS  (streamlined — rules are in the cache, prompts only define TASK)
# # ─────────────────────────────────────────────────────────────────────────────

# SINGLE_ANALYSIS_PROMPT_TEMPLATE = """
# TASK: Analyze this single product for internal data consistency (vertical check).

# Product Title: {title}
# Text Attributes: {attributes}

# INSTRUCTIONS:
# 1. Detect the product category from title + attributes
# 2. Find matching SOP rules from the cached rules for this category
# 3. Extract specs from the provided images (OCR) — focus on primary attributes for the category
# 4. Compare extracted image specs against the text attributes
# 5. Flag contradictions ONLY (not missing data)

# Use the SOP rules from the cached context to determine which attributes matter for this category
# and which should be ignored.

# Respond with JSON only (no markdown, no backticks):
# {{
#   "detected_category": "string",
#   "matched_sop_rules": ["list of scenario_ids that were consulted"],
#   "primary_attributes_checked": ["list of attribute names relevant for this category"],
#   "extracted_image_specs": "string (concise summary of specs from images, or 'None')",
#   "hasInconsistency": boolean,
#   "inconsistencies": [
#     {{
#       "field": "string",
#       "imageValue": "string",
#       "textValue": "string",
#       "reason": "string"
#     }}
#   ]
# }}
# """


# BATCH_ANALYSIS_PROMPT = """
# TASK: Perform a full duplicate/non-duplicate/bad-data analysis on the following products.

# INSTRUCTIONS:
# 1. For each product, detect its category and find matching SOP rules from the cached context
# 2. PHASE 1 (Vertical Check): For each product individually, extract image specs via OCR and
#    check for contradictions against text attributes. Apply the SOP rules to determine if
#    attributes should be ignored for the category.
# 3. PHASE 2 (Horizontal Check): Compare products that pass Phase 1 against each other.
#    Apply the SOP rules for clustering decisions — check which scenario matches and use
#    its DECISION (Duplicate / Not a Duplicate / Not sure - Bad data).

# Before performing ANY comparison, independently extract the following attributes from BOTH the structured text and the product images.

# Extract each attribute separately. Do NOT combine or normalize different attributes into a single value.

# - Brand
# - Product Name
# - Model Number
# - Size / Dimensions
# - Capacity
# - Weight
# - Color
# - Finish
# - Material
# - Flavor
# - Scent
# - Dosage Strength
# - Formulation
# - Package Type
# - Package Count
# - Units Per Package
# - Total Units
# - Compatibility
# - Warranty

# Rules:

# - Keep Package Count, Units Per Package, and Total Units as separate attributes.
# - Never merge multiple quantity attributes into a single "Count".
# - Preserve packaging hierarchy exactly as shown.
# - If an attribute cannot be confidently extracted from either text or image, return it as "Unknown". Never infer missing values.

# CRITICAL RULES FROM SOP:
# - Attributes listed as "Ignore Attributes" in matching SOP rules must NOT affect decisions
# - Do not flag 'Bad Data' just because a specific attribute is missing (-) if that information is clearly stated in the title, description, or under a synonymous attribute name.
# - When a rule specifies visual_check=REQUIRED, images MUST be verified
# - COUNT VERIFICATION (ALL CATEGORIES): Pay extremely close attention to the Unit of Measurement (UOM) in images and text. Distinguish between 'Package-Level Count' (e.g., 1 Box, 1 Case), 'Item-Level Count' (e.g., 60 Pills, 80 Pellets), and 'Weight/Volume' (e.g., 0.3 Ounces, 50ml). Do NOT flag different types of measurements as contradictions (e.g., 'Net Content: 0.3 Ounces' vs 'Count Per Pack: 80'). If an attribute like 'Total Count' or 'Multipack Quantity' is '1', it almost always refers to '1 retail package being sold'. Do NOT flag 'Total Count: 1' as a contradiction against 'Count Per Pack: 80' or a product image showing '80 Ct'. As long as the measurements describe different aspects (weight vs count vs packages), it is a PERFECT match, not Bad Data.
# - PACKAGING HORIZONTAL RULES: A 2x30 configuration (2 bottles of 30) is NOT a duplicate of a 1x60 configuration (1 bottle of 60). Even if total units are the same, different package structures must be clustered separately (e.g., 'Not a Duplicate - Variant').
# - PACKAGING TYPE RULES: Pay attention to the physical container type. A bottle is NOT a duplicate of a blister pack, and a blister pack is NOT a duplicate of a strip. Cluster these separately.
# - COMPATIBILITY OVERRIDES BAD DATA: If attributes like 'Actual Color' or 'Color' contain vehicle compatibility data (e.g. 'For 2022-2023 Chevrolet Silverado'), do NOT flag this as a color contradiction or 'Bad Data' in the vertical check. Treat it as valid compatibility information.
# - CLUSTERING LOGIC - IDENTICALS: Group identical/duplicate products together in the SAME cluster.
# - CLUSTERING LOGIC - VARIANTS & UNIQUE: If a product is a variant, a completely unique item, or "Not a Duplicate", it MUST be placed in its OWN SEPARATE, STANDALONE cluster. Do NOT group variants or non-duplicates together with the primary product or with each other. Each gets its own cluster.
# - CLUSTERING LOGIC - BAD DATA: Bad data products MUST be separated into their own individual clusters, never merged with any other product.
# - CLUSTERING LOGIC - DIFFERENT ATTRIBUTES: Different sizes, model numbers, finish types, or compatibilities = SEPARATE clusters always.
# - You MUST assign exactly ONE of the following official actions to each cluster:
#   ACTION SELECTION HIERARCHY (MANDATORY)

# When multiple conditions apply, ALWAYS select exactly ONE action using the following priority order:

# 1. "Not Duplicate - Different Compatibility"
#    Use when compatibility differs (vehicle, device, model, application, etc.), regardless of other variant differences or missing data.

# 2. "Not Sure - Bad Data"
#    Use if:
#    - Required attributes cannot be verified.
#    - Image and text contain unresolved contradictions.
#    - OCR evidence is insufficient for required verification.
#    - Critical product information is missing and prevents reliable comparison.

# 3. "Not Duplicate - Different Warranty"
#    Use when warranty is the only material differentiator and SOP specifies warranty as variant-driving.

# 4. "Not a Duplicate - Incorrect Variant Attribute Name Data Not Available"
#    Use when variant attribute names are incorrect and the actual variant values cannot be determined.

# 5. "Not a Duplicate - Incorrect Variant Attribute Names"
#    Use when products differ only because variant information is stored under incorrect attribute names.

# 6. "Not a Duplicate - Variant Attribute Data Not Available"
#    Use when variant-driving attributes are missing and variant status cannot be determined.

# 7. "Not a Duplicate - Variant"
#    Use when products belong to the same product family but differ in one or more variant-driving attributes.

# 8. "Duplicate"
#    Use when every critical attribute matches after applying SOP ignore rules.

# 9. "Not a Duplicate"
#    Use only when the products belong to completely different product families and are not variants of each other.

# GENERALIZED METADATA NOISE & TRUTH HIERARCHY:
# To handle messy marketplace seller-submitted data, apply the following "common sense" hierarchy over the raw rules:
# - CORE IDENTITY TIERS:
#   * Tier 1 (Core Identity): Brand, capacity/volume (e.g. 32oz, 1 Liter), model number, and packaging structures (e.g. 1-pack vs 2-pack). Discrepancies here are critical and drive "Not a Duplicate" / "Variant" decisions.
#   * Tier 2 (Visual Specs): Color, Finish, Material. If these differ, use the Image as the absolute tie-breaker. If the image shows them as identical, ignore the text discrepancy (e.g., ignore 'Multicolor' vs 'Matte Black' if visually identical).
#   * Tier 3 (Logistics/Marketing Noise): Assembled Product dimensions (Length, Width, Height, Weight), Bulk Size, target audience, subjective benefits (e.g. "Hair Product Form" cream vs liquid, or "Hair Type" fine vs damaged). Completely IGNORE discrepancies in Tier 3 attributes. Do NOT flag 'Bad Data' or 'Variant' based on Tier 3 differences.
# - VISUAL GROUNDING: If the primary product images are identical, you must maintain a "Duplicate" decision unless there is a clear, un-ignorable mismatch in a Tier 1 Core Identity attribute (different Model Numbers, or different Capacity).
# - DATA ASYMMETRY TOLERANCE: Missing attributes (e.g., `-` or `None` on one side but present on the other) are data gaps, not contradictions. Never flag "Bad Data" or "Variant" based on missing data.
# - ACTION HIERARCHY OVERRIDE: If there is clear proof that the items are variants or completely different (e.g., different Model Numbers, different Native Resolutions), choose "Not a Duplicate - Variant" or "Not a Duplicate". Choosing "Not a Duplicate" or "Variant" overrides any minor "Bad Data" triggers.

# Respond with JSON only (no markdown, no backticks):
# {
#   "vertical_checks": [
#     {
#       "product_id": "Exact string from the PRODUCT ID header (e.g. 'GTIN#1 (007...)')",
#       "detected_category": "string",
#       "matched_sop_rules": ["scenario_ids consulted"],
#       "extracted_image_summary": "string (ultra-brief 5-10 word summary of key visual specs seen in the image)",
#       "has_bad_data": boolean,
#       "reason": "string (ULTRA-SHORT 1-2 sentence summary. Focus only on the main difference or missing attribute. DO NOT write long paragraphs.)",
#       "mismatch_details": [
#         {
#           "field": "string (only include fields that actually contradict)",
#           "imageValue": "string",
#           "textValue": "string"
#         }
#       ]
#     }
#   ],
#   "horizontal_clustering": [
#     {
#       "cluster_name": "string (descriptive label)",
#       "product_ids": ["string"],
#       "cluster_type": "string (duplicate|variant|unique|bad_data)",
#       "recommended_action": "Exact string from the official actions list above",
#       "matched_sop_rule": "scenario_id that determined this clustering",
#       "reason": "string (ULTRA-SHORT 1-2 sentence summary. Focus only on the main difference or missing attribute. DO NOT write long paragraphs.)"
#     }
#   ]
# }
# """


# # ─────────────────────────────────────────────────────────────────────────────
# #  ANALYSIS FUNCTIONS
# # ─────────────────────────────────────────────────────────────────────────────

# def _build_image_parts(image_data_list: list) -> list:
#     """Convert fetched image dicts to genai Part objects."""
#     parts = []
#     for img in image_data_list:
#         if img:
#             parts.append(
#                 types.Part.from_bytes(
#                     data=base64.b64decode(img["data"]),
#                     mime_type=img["mime_type"]
#                 )
#             )
#     return parts


# async def process_analysis(title, attributes, imageUrls):
#     prompt = SINGLE_ANALYSIS_PROMPT_TEMPLATE.format(
#         title=title,
#         attributes=json.dumps(attributes, indent=2)
#     )

#     image_parts = []
#     async with httpx.AsyncClient() as http_client:
#         tasks = [fetch_image(http_client, url) for url in imageUrls]
#         fetched_images = await asyncio.gather(*tasks)
#         for img in fetched_images:
#             if img:
#                 image_parts.append(img)

#     if not image_parts:
#         return {"status": "error", "message": "Could not fetch any images."}

#     try:
#         print("\n" + "=" * 50)
#         print("🚀 SENDING REQUEST TO GEMINI (Single Analysis — Context Cached)")
#         print("=" * 50)

#         # Build content parts: text prompt + images
#         content_parts = [types.Part.from_text(text=prompt)]
#         content_parts.extend(_build_image_parts(image_parts))

#         contents = [types.Content(role="user", parts=content_parts)]

#         response_text = generate_with_cache(contents)

#         if not response_text:
#             return {"status": "error", "message": "no response by ai"}

#         text = response_text.strip()
#         print("\n" + "=" * 50)
#         print("✅ RECEIVED RESPONSE FROM GEMINI (Single Analysis)")
#         print("=" * 50)
#         print(f"{text}")
#         print("=" * 50 + "\n")
#         text = text.replace("```json", "").replace("```", "").strip()

#         return {"status": "success", "data": json.loads(text)}

#     except json.JSONDecodeError:
#         print("Failed to parse JSON:", text)
#         return {"status": "error", "message": "Invalid JSON response from AI"}
#     except Exception as e:
#         print("Analysis Error:", e)
#         return {"status": "error", "message": str(e)}


# MAX_RETRIES = 1


# async def process_batch_analysis(products):
#     n = len(products)

#     # Inject cardinality constraint into the prompt so Gemini knows EXACTLY
#     # how many products to output.  Without this the model occasionally drops
#     # one product from vertical_checks or horizontal_clustering.
#     cardinal_prompt = BATCH_ANALYSIS_PROMPT + (
#         f"\n\nCRITICAL — You are analyzing EXACTLY {n} products.  "
#         f"Your vertical_checks array MUST contain EXACTLY {n} entries — "
#         f"one for each product_id listed above.  "
#         f"Do NOT skip, merge, or omit ANY product."
#     )
#     content_parts = [types.Part.from_text(text=cardinal_prompt)]

#     async with httpx.AsyncClient() as http_client:
#         seen_image_sets = {}      # url_signature → first_prod_id
#         image_cache = {}          # url_signature → [fetched_image_dict, ...]

#         for p in products:
#             prod_id = p.get('id', 'Unknown')
#             prod_text = (
#                 f"\n\n--- PRODUCT ID: {prod_id} ---\n"
#                 f"Title: {p.get('title')}\n"
#                 f"Description: {p.get('description', '')}\n"
#                 f"Attributes: {json.dumps(p.get('attributes', {}), indent=2)}\n"
#                 f"Images for {prod_id}:"
#             )
#             content_parts.append(types.Part.from_text(text=prod_text))

#             urls = p.get('imageUrls', [])

#             if not urls:
#                 content_parts.append(types.Part.from_text(text="[No Images Provided for this product]"))
#                 continue

#             url_signature = tuple(sorted(list(set(urls))))

#             if url_signature in image_cache:
#                 # Images already fetched for a previous product — reuse cached
#                 # bytes instead of fetching again AND instead of sending a text
#                 # placeholder. This saves network round-trips while still giving
#                 # Gemini the actual images so it can independently analyze every
#                 # product (not dropping deduped entries).
#                 cached = image_cache[url_signature]
#                 has_img = False
#                 for img in cached:
#                     if img:
#                         content_parts.append(
#                             types.Part.from_bytes(
#                                 data=base64.b64decode(img["data"]),
#                                 mime_type=img["mime_type"]
#                             )
#                         )
#                         has_img = True
#                 if not has_img:
#                     content_parts.append(types.Part.from_text(
#                         text="[No Images Could Be Fetched for this product]"
#                     ))
#             else:
#                 seen_image_sets[url_signature] = prod_id
#                 tasks = [fetch_image(http_client, url) for url in urls]
#                 fetched_images = await asyncio.gather(*tasks)
#                 # Cache the result so duplicate image-sets don't re-fetch
#                 image_cache[url_signature] = fetched_images

#                 has_img = False
#                 for img in fetched_images:
#                     if img:
#                         content_parts.append(
#                             types.Part.from_bytes(
#                                 data=base64.b64decode(img["data"]),
#                                 mime_type=img["mime_type"]
#                             )
#                         )
#                         has_img = True

#                 if not has_img:
#                     content_parts.append(types.Part.from_text(
#                         text="[No Images Could Be Fetched — treat extracted_image_specs as 'None' for this product]"
#                     ))

#     try:
#         print("\n" + "=" * 50)
#         print("🚀 SENDING REQUEST TO GEMINI (Batch Analysis — Context Cached)")
#         print("=" * 50)

#         # Log what we're sending (text parts only, not image bytes)
#         for idx, part in enumerate(content_parts):
#             if hasattr(part, 'text') and part.text:
#                 print(f"--- Text Part {idx} ---\n{part.text[:200]}...\n")
#             else:
#                 print(f"--- Image Part {idx} ---")
#         print("=" * 50 + "\n")

#         contents = [types.Content(role="user", parts=content_parts)]
#         response_text = generate_with_cache(contents)

#         if not response_text:
#             return {"status": "error", "message": "no response by ai"}

#         text = response_text.strip().replace("```json", "").replace("```", "").strip()
#         print("\n" + "=" * 50)
#         print("✅ RECEIVED RESPONSE FROM GEMINI (Batch Analysis)")
#         print("=" * 50)
#         print(f"{text}")
#         print("=" * 50 + "\n")

#         data = json.loads(text)
#         output_ids = {v['product_id'] for v in data.get('vertical_checks', [])}
#         input_ids = {p.get('id', 'Unknown') for p in products}
        
#         missing_ids = set()
#         for i_id in input_ids:
#             if not any(i_id in o_id or o_id in i_id for o_id in output_ids):
#                 missing_ids.add(i_id)

#         retries_left = MAX_RETRIES
#         while missing_ids and retries_left > 0:
#             retries_left -= 1
#             print(f"\n⚠ Retrying — Gemini returned {len(output_ids)}/{n} products. "
#                   f"Missing: {missing_ids}")

#             correction = (
#                 f"\n\n--- CORRECTION ---\n"
#                 f"You only returned {len(output_ids)} vertical_checks entries, "
#                 f"but there are {n} products.  "
#                 f"You MISSED product(s): {missing_ids}.  "
#                 f"Please output the COMPLETE analysis for ALL {n} products "
#                 f"— vertical_checks MUST contain exactly {n} entries.  "
#                 f"Every product_id below MUST appear exactly once."
#             )
#             content_parts.append(types.Part.from_text(text=correction))
#             contents = [types.Content(role="user", parts=content_parts)]
#             retry_text = generate_with_cache(contents)

#             if not retry_text:
#                 print("  Retry gave empty response, keeping original.")
#                 break

#             retry_text = retry_text.strip().replace("```json", "").replace("```", "").strip()
#             try:
#                 retry_data = json.loads(retry_text)
#             except json.JSONDecodeError:
#                 print("  Retry JSON parse failed, keeping original.")
#                 break

#             retry_ids = {v['product_id'] for v in retry_data.get('vertical_checks', [])}
#             newly_missing = set()
#             for i_id in input_ids:
#                 if not any(i_id in o_id or o_id in i_id for o_id in retry_ids):
#                     newly_missing.add(i_id)
                    
#             recovered = len(missing_ids) - len(newly_missing)
#             if recovered > 0:
#                 print(f"  ✅ Retry recovered {recovered} product(s) "
#                       f"({len(retry_ids)} total, still missing {newly_missing})")
#                 # Merge: keep all retry entries + any original entries that
#                 # the retry omitted (product_id collision → prefer retry).
#                 original_vc = data.get('vertical_checks', [])
#                 seen_ids = set()
#                 merged = []
#                 for entry in retry_data.get('vertical_checks', []):
#                     merged.append(entry)
#                     seen_ids.add(entry['product_id'])
#                 for entry in original_vc:
#                     if entry['product_id'] not in seen_ids:
#                         merged.append(entry)
#                         seen_ids.add(entry['product_id'])
#                 # Re-sort to match input product order
#                 id_order = [p.get('id', 'Unknown') for p in products]
#                 merged.sort(key=lambda v: id_order.index(v['product_id'])
#                             if v['product_id'] in id_order else len(id_order))
#                 data['vertical_checks'] = merged
#                 # Use retry's clustering (it should be more complete)
#                 data['horizontal_clustering'] = retry_data.get(
#                     'horizontal_clustering',
#                     data.get('horizontal_clustering', [])
#                 )
#                 # Update tracking for the loop guard
#                 output_ids = input_ids - newly_missing
#                 missing_ids = newly_missing
#             else:
#                 print("  Retry did not improve, keeping original response.")
#                 break

#         if missing_ids:
#             print(f"⚠ FINAL: {len(missing_ids)} product(s) still missing after retries: {missing_ids}")

#         return {"status": "success", "data": data}

#     except json.JSONDecodeError:
#         print("Failed to parse JSON:", text)
#         return {"status": "error", "message": "Invalid JSON response from AI"}
#     except Exception as e:
#         print("Batch Analysis Error:", e)
#         return {"status": "error", "message": str(e)}


# # ─────────────────────────────────────────────────────────────────────────────
# #  FLASK APP & ROUTES
# # ─────────────────────────────────────────────────────────────────────────────
# app = Flask(__name__)
# CORS(app)


# @app.route("/", methods=["GET"])
# def index():
#     cache_status = "active" if _cached_content else "inactive (fallback mode)"
#     return jsonify({
#         "status": "running",
#         "message": "DupCheck Backend is active and listening.",
#         "context_cache": cache_status,
#         "cache_name": _cached_content.name if _cached_content else None,
#     })


# @app.route("/api/cache-status", methods=["GET"])
# def cache_status():
#     """Check the current state of the context cache."""
#     if _cached_content:
#         return jsonify({
#             "cached": True,
#             "cache_name": _cached_content.name,
#             "model": GEMINI_MODEL,
#             "ttl_hours": CACHE_TTL_HOURS,
#         })
#     else:
#         return jsonify({
#             "cached": False,
#             "message": "No active context cache. Rules sent inline per request.",
#         })


# @app.route("/api/cache-refresh", methods=["POST"])
# def cache_refresh():
#     """Force-refresh the context cache (e.g., after updating rules.json)."""
#     delete_rule_cache()
#     create_rule_cache()
#     if _cached_content:
#         return jsonify({"status": "success", "cache_name": _cached_content.name})
#     else:
#         return jsonify({"status": "error", "message": "Cache creation failed"}), 500


# @app.route("/test-ai", methods=["GET"])
# def test_ai():
#     title = "Bulbasaur"
#     attributes = {"Type": "Grass", "Color": "Blue"}
#     imageUrls = ["https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png"]
#     result = asyncio.run(process_analysis(title, attributes, imageUrls))
#     html_response = f"""
#     <html>
#         <body style="font-family: monospace; background: #1e1e1e; color: #00ff00; padding: 20px;">
#             <h2>AI Vision Test Result</h2>
#             <pre>{json.dumps(result, indent=4)}</pre>
#         </body>
#     </html>
#     """
#     return html_response


# @app.route("/api/analyze-column", methods=["POST"])
# def analyze_column():
#     req_data = request.get_json()
#     title = req_data.get("title", "")
#     attributes = req_data.get("attributes", {})
#     imageUrls = req_data.get("imageUrls", [])

#     if not imageUrls:
#         return jsonify({"status": "no_images", "message": "No image URLs provided for analysis."})

#     result = asyncio.run(process_analysis(title, attributes, imageUrls))

#     if result.get("status") == "error":
#         return jsonify(result), 500

#     return jsonify(result)


# @app.route("/api/analyze-batch", methods=["POST"])
# def analyze_batch():
#     req_data = request.get_json()
#     products = req_data.get("products", [])
#     force_refresh = req_data.get("forceRefresh", False)

#     print(f"Received batch analysis request for {len(products)} products (Force Refresh: {force_refresh})")

#     if not products:
#         return jsonify({"status": "error", "message": "No products provided for analysis."}), 400

#     cache_key = get_cache_key(products)
#     cache = get_cache()

#     if not force_refresh and cache_key in cache:
#         print(f"✅ Cache HIT! Returning cached AI result for key: {cache_key}")
#         return jsonify(cache[cache_key])

#     print(f"❌ Cache MISS (or forced refresh). Running AI analysis...")
#     import time
#     start_time = time.time()
#     result = asyncio.run(process_batch_analysis(products))
#     elapsed_time = time.time() - start_time
#     print(f"⏱️ AI batch analysis for {len(products)} products completed in {elapsed_time:.2f} seconds.")

#     if result.get("status") == "success":
#         cache[cache_key] = result
#         save_cache(cache)
#     elif result.get("status") == "error":
#         return jsonify(result), 500

#     return jsonify(result)


# # ─────────────────────────────────────────────────────────────────────────────
# #  STARTUP & SHUTDOWN
# # ─────────────────────────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     # Create context cache on startup
#     create_rule_cache()

#     # Register cleanup on shutdown (delete cache to stop billing)
#     atexit.register(delete_rule_cache)

#     print("DupCheck backend running on http://localhost:8080")
#     app.run(host="0.0.0.0", port=8080, debug=True)

import os
import json
import base64
import tempfile
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
CACHE_TTL_HOURS = 720  # How long the context cache stays alive (30 days)

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
_cache_creation_time = None  # Track when the cache was created


def create_rule_cache():
    """
    Compile rules.json into compact text and create a Gemini context cache.
    Called ONCE at server startup. The cache persists for CACHE_TTL_HOURS.
    """
    global _cached_content, _cache_creation_time

    print("\n" + "=" * 60)
    print("📦 COMPILING RULES & CREATING CONTEXT CACHE...")
    print("=" * 60)

    compiled_rules = compile_rules()
    stats = get_compiled_rules_stats(compiled_rules)

    print(f"  ✅ Compiled rules: {stats['char_count']:,} chars, ~{stats['approx_tokens']:,} tokens")
    print(f"  ✅ Meets 32K minimum: {stats['meets_32k_minimum']}")
    print(f"  💰 Est. cache cost: ${stats['estimated_cache_cost_per_hour']}/hour")

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

        _cache_creation_time = datetime.datetime.now()
        print(f"  ✅ Cache created: {_cached_content.name}")
        print(f"  ⏰ TTL: {CACHE_TTL_HOURS} hours (30 Days) - Auto-deleted on backend shutdown")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"  ❌ Cache creation FAILED: {e}")
        print("  ⚠️  Falling back to non-cached mode (rules sent per request)")
        print("=" * 60 + "\n")
        _cached_content = None
        _cache_creation_time = None


def delete_rule_cache():
    """Delete the context cache on shutdown to stop billing."""
    global _cached_content, _cache_creation_time
    if _cached_content:
        try:
            client.caches.delete(name=_cached_content.name)
            print(f"🗑️  Context cache deleted: {_cached_content.name}")
        except Exception as e:
            print(f"⚠️  Failed to delete cache (may have expired): {e}")
        _cached_content = None
        _cache_creation_time = None


def get_model():
    """
    Return a model reference — cached if available, fallback otherwise.
    When using the cached model, rules are NOT sent per request.
    Automatically recreates the cache if it is close to expiration (3.5 hours).
    """
    global _cached_content, _cache_creation_time
    if _cached_content:
        if _cache_creation_time:
            elapsed = (datetime.datetime.now() - _cache_creation_time).total_seconds()
            # Recreate every 24 hours (86400 seconds) to ensure freshness
            if elapsed > 86400:
                print("🔄 Context cache is being refreshed (24-hour cycle)...")
                delete_rule_cache()
                create_rule_cache()
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
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                cached_content=cache_name,
                temperature=0.0,
                seed=42
            )
        )
    else:
        compiled_rules = compile_rules()
        full_contents = [compiled_rules] + contents
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=full_contents,
            config=types.GenerateContentConfig(
                temperature=0.0,
                seed=42
            )
        )

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
#  LOCAL RESPONSE CACHE
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
    
    # Invalidate cache when prompts or rules change
    payload = {
        "products": normalized_products,
        "batch_prompt_hash": hashlib.md5(BATCH_ANALYSIS_PROMPT.encode('utf-8')).hexdigest(),
        "single_prompt_hash": hashlib.md5(SINGLE_ANALYSIS_PROMPT_TEMPLATE.encode('utf-8')).hexdigest()
    }
    try:
        from rule_compiler import RULES_FILE
        if os.path.exists(RULES_FILE):
            with open(RULES_FILE, 'r') as f:
                payload["rules_json_hash"] = hashlib.md5(f.read().encode('utf-8')).hexdigest()
    except Exception:
        pass

    payload_str = json.dumps(payload, sort_keys=True)
    return hashlib.md5(payload_str.encode('utf-8')).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
#  IMAGE FETCHING
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
#  PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

SINGLE_ANALYSIS_PROMPT_TEMPLATE = """
TASK: Analyze this single product for internal data consistency (vertical check).

Product Title: {title}
Text Attributes: {attributes}

INSTRUCTIONS:
1. Detect the product category from title + attributes.
2. Find matching SOP rules from the cached rules for this category.
3. Extract specs from the provided images (OCR) — focus on primary attributes for the category.
4. Compare extracted image specs against the text attributes.
5. Flag CONTRADICTIONS ONLY (not missing data).
   - A contradiction means the same product's own title, image, and attribute give
     irreconcilable conflicting values for the same field.
   - Missing data on one side is a data gap, NOT a contradiction.
   - Minor measurement rounding or UOM conversion differences (e.g., 15cm vs 16cm, or under 10% difference) are NOT contradictions.
   - For multi-piece kits or sets, singular attributes describing a subset (e.g., 'Tip Style: Loop' for a set containing both loops and pointy tools) are NOT contradictions.
   - For sets, kits, or hardware (e.g., sets of legs, brackets, shelves, or tools), a structured count of '1' (or '1 Pack', '1 Set') represents the retail package and is NOT a contradiction against a title, description, or image indicating multiple pieces (e.g., 'Set of 2 legs').
   - 'Assembled Product Width' (and its variations like 'Width', 'Assembled Width') and 'Assembled Product Length' (and its variations like 'Length', 'Assembled Length') MUST be completely ignored in all cases. Do not check, extract, or flag contradictions based on them.
   - MATERIAL CONFLICT RULES: Treat different subtypes/alloys of steel (e.g., 'Stainless Steel', 'Carbon Steel', 'Alloy Steel', 'Solid Steel', 'Steel') as the SAME compatible material. A discrepancy between these steel subtypes (e.g., 'Stainless Steel' in attributes vs 'Carbon Steel' in description/image) is NOT a contradiction and MUST NOT trigger inconsistencies or bad data. Only flag material contradictions if they belong to completely different material classes (e.g., 'Steel' vs 'Brass', 'Metal' vs 'Plastic').

Use the SOP rules from the cached context to determine which attributes matter for this
category and which should be ignored.

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

══════════════════════════════════════════════════════════════════
PHASE INSTRUCTIONS
══════════════════════════════════════════════════════════════════

PHASE 1 — Vertical Check (per-product internal consistency):
  For each product individually, extract image specs via OCR and check for
  contradictions against text attributes. Apply SOP rules to determine which
  attributes to ignore for the category.

  ⚠ VERTICAL CHECK RULE — set has_bad_data=true ONLY when ALL of these apply:
    (a) The same product's own data has an irreconcilable intra-GTIN contradiction:
        its title, image, and structured attribute give CONFLICTING values for the
        SAME field in a way no SOP rule resolves.
        Example: title says "2'x4'" but Rug Size attribute says "2'x3'" → contradiction.
    (b) The contradiction is about a critical identifying attribute, AND a SOP rule
        explicitly mandates Bad Data for this scenario, OR it makes it impossible to
        identify what the product actually is.

  NEVER set has_bad_data=true for:
    • Missing attributes on one or both sides — these are data gaps, not contradictions.
    • OCR failure on a non-critical attribute.
    • One product has more complete data than another (asymmetry is normal).
    • General uncertainty about a non-critical attribute value.
    • Minor measurement rounding or UOM conversion differences (e.g., 15cm vs 16cm, or under 10% difference).
    • Multi-piece kits/sets where a singular attribute describes a subset of the kit's contents (e.g., 'Tip Style: Loop' for a kit containing both loop and pointy tools).
    • Discrepancies in 'Assembled Product Width' or 'Assembled Product Length' (or any of their variations like 'Width', 'Length') — these columns MUST be ignored in all cases.
    • MATERIAL CONFLICT RULES: Treat different subtypes/alloys of steel (e.g., 'Stainless Steel', 'Carbon Steel', 'Alloy Steel', 'Solid Steel', 'Steel') as the SAME compatible material. A discrepancy between these steel subtypes (e.g., 'Stainless Steel' in attributes vs 'Carbon Steel' in description/image) is NOT a contradiction and MUST NOT trigger 'has_bad_data=true'. Only flag material contradictions if they belong to completely different material classes (e.g., 'Steel' vs 'Brass', 'Metal' vs 'Plastic').

PHASE 2 — Horizontal Check (cross-product comparison):
  Compare products against each other and apply the matching SOP scenario.

  ⚠ CRITICAL SEPARATION RULE:
  The vertical_checks result (has_bad_data) is INFORMATIONAL ONLY about that
  individual product's internal data quality. It does NOT determine the
  horizontal_clustering action.
  The horizontal_clustering decision is made INDEPENDENTLY by comparing products
  against each other. A product with has_bad_data=true CAN still be correctly
  classified as "Duplicate" or "Not a Duplicate - Variant" in the horizontal
  clustering if the cross-product comparison is clear.
  Only assign "Not Sure - Bad Data" to a cluster when the comparison itself —
  not the vertical check result — cannot be resolved.

══════════════════════════════════════════════════════════════════
ATTRIBUTE EXTRACTION
══════════════════════════════════════════════════════════════════

Before any comparison, independently extract the following attributes from BOTH
the structured text and the product images. Extract each attribute separately.
Do NOT combine or normalize different attributes into a single value.

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

Extraction rules:
  • Keep Package Count, Units Per Package, and Total Units as SEPARATE attributes.
  • Never merge multiple quantity attributes into a single "Count".
  • Preserve packaging hierarchy exactly as shown.
  • If an attribute cannot be confidently extracted, return "Unknown". Never infer.
  • NEVER extract or evaluate 'Assembled Product Width' or 'Assembled Product Length' (or any variations like 'Width', 'Length'). Ignore them completely.

══════════════════════════════════════════════════════════════════
CRITICAL MATCHING RULES
══════════════════════════════════════════════════════════════════

• Attributes listed as "Ignore Attributes" in matching SOP rules MUST NOT affect decisions.
• Do not flag Bad Data just because a specific attribute is missing (-) if the information
  is stated in the title, description, or under a synonymous attribute name.
• When a rule specifies visual_check=REQUIRED, images MUST be verified.

COUNT VERIFICATION (ALL CATEGORIES):
  Pay close attention to the Unit of Measurement (UOM). Distinguish between:
    - Package-Level Count (e.g., 1 Box, 1 Case, 1 Pack, 1 Set)
    - Item-Level Count (e.g., 60 Pills, 2 Legs, 4 Brackets)
    - Weight/Volume (e.g., 0.3 Ounces, 50ml)
  Do NOT flag different types of measurements as contradictions.
  - 'Total Count: 1' or 'Count: 1' almost always means 1 retail package/set. Do NOT flag it as a contradiction against a title, description, or image indicating multiple individual items (e.g., 'Set of 2 legs', 'Pack of 4 brackets', '80 Ct').
  - As long as measurements describe different levels (package count vs item count), it is a PERFECT match, not Bad Data.

PACKAGING HORIZONTAL RULES:
  A 2x30 configuration (2 bottles of 30) is NOT a duplicate of a 1x60 configuration
  (1 bottle of 60). Different package structures must be clustered separately.

PACKAGING TYPE RULES:
  A bottle is NOT a duplicate of a blister pack.

COMPATIBILITY OVERRIDES BAD DATA:
  If 'Actual Color' or 'Color' contains vehicle compatibility data (e.g., 'For 2022-2023
  Chevrolet Silverado'), do NOT flag this as a color contradiction or Bad Data.
  Treat it as valid compatibility information.

══════════════════════════════════════════════════════════════════
ACTION SELECTION HIERARCHY  (MANDATORY)
══════════════════════════════════════════════════════════════════

"Not Sure – Bad Data" is the ABSOLUTE LAST RESORT.
Before assigning Bad Data, you MUST have genuinely tried and ruled out every action
above it (actions 1–8). Select EXACTLY ONE action using this priority order:

1. "Not Duplicate - Different Compatibility"
   Use when compatibility explicitly differs (vehicle, device, model, application, etc.),
   regardless of other variant differences or missing data. Compatibility difference is
   always the top priority.

2. "Not Duplicate - Different Warranty"
   Use when warranty is the only material differentiator AND the SOP specifies warranty
   as variant-driving for this category.

3. "Not a Duplicate - Incorrect Variant Attribute Name Data Not Available"
   Use when variant attribute names are incorrect AND the actual variant values cannot
   be determined from any other source.

4. "Not a Duplicate - Incorrect Variant Attribute Names"
   Use when products differ only because variant information is stored under incorrect
   attribute names.

5. "Not a Duplicate - Variant Attribute Data Not Available"
   Use when variant-driving attributes are missing and variant status cannot be
   determined.

6. "Not a Duplicate - Variant"
   Use when products belong to the same product family but differ in one or more
   variant-driving attributes (size, color, capacity, model, etc.).

7. "Duplicate"
   Use when every critical attribute matches after applying SOP ignore rules.

8. "Not a Duplicate"
   Use only when products belong to completely different product families and are
   not variants of each other.

9. "Not Sure - Bad Data"  ← LAST RESORT — only after exhausting actions 1–8
   Use ONLY when ALL THREE conditions are true:
     (a) You have genuinely tried and cannot assign any of actions 1–8.
     (b) A SOP rule for this specific category/attribute combination explicitly
         states Bad Data for this exact scenario — search by scenario_id in the
         cached rules before using this action.
     (c) There is an intra-GTIN contradiction: the SAME product's own data
         contradicts itself in a way that makes the comparison impossible to resolve.

   NEVER use "Not Sure - Bad Data" for:
     • Missing attributes on one or both sides (these are data gaps, not contradictions)
     • OCR failure on a non-critical attribute
     • General uncertainty about which Duplicate/Variant action applies
     • Products where images are unavailable but text data is consistent
     • Any situation where actions 1–8 can be applied

══════════════════════════════════════════════════════════════════
CLUSTERING RULES  (MANDATORY)
══════════════════════════════════════════════════════════════════

After determining each product's classification, form clusters using these rules:

RULE 1 — BAD DATA → OWN CLUSTER (always standalone):
  Each product classified as "Not Sure - Bad Data" MUST be placed in its own
  individual, standalone cluster. Never group two bad data products together.
  Never merge a bad data product with any non-bad-data product, regardless of
  any similarity.

RULE 2 — DUPLICATES → ONE SHARED CLUSTER:
  All products that are duplicates of each other go into the SAME cluster with
  action "Duplicate".

RULE 3 — NOT A DUPLICATE / VARIANT / UNIQUE → OWN CLUSTER (always standalone):
  Each product that is a variant, not a duplicate, or unique MUST be placed in
  its own individual, standalone cluster. Do NOT group variants or non-duplicates
  together with each other or with any other product.

RULE 4 — DIFFERENT ATTRIBUTES = SEPARATE CLUSTERS:
  Different sizes, model numbers, finish types, or compatibilities always require
  separate clusters.

──────────────────────────────────────────────────────────────────
WORKED EXAMPLE — 6 GTINs: 2 bad data, 3 duplicates, 1 not a duplicate:
  Input:  GTIN_A (bad data), GTIN_B (bad data),
          GTIN_C (duplicate), GTIN_D (duplicate), GTIN_E (duplicate),
          GTIN_F (not a duplicate)

  Output → 4 clusters:
    Cluster 1: product_ids=["GTIN_A"]           action="Not Sure - Bad Data"  (standalone)
    Cluster 2: product_ids=["GTIN_B"]           action="Not Sure - Bad Data"  (standalone)
    Cluster 3: product_ids=["GTIN_C","GTIN_D","GTIN_E"]  action="Duplicate"  (grouped)
    Cluster 4: product_ids=["GTIN_F"]           action="Not a Duplicate"      (standalone)
──────────────────────────────────────────────────────────────────

══════════════════════════════════════════════════════════════════
GENERALIZED METADATA NOISE & TRUTH HIERARCHY
══════════════════════════════════════════════════════════════════

Apply the following tiers to handle messy marketplace seller-submitted data:

CORE IDENTITY TIERS:
  Tier 1 (Core Identity): Brand, capacity/volume (e.g. 32oz, 1 Liter), model number,
    and packaging structure (e.g. 1-pack vs 2-pack). Discrepancies here are critical
    and drive "Not a Duplicate" / "Variant" decisions.
  Tier 2 (Visual Specs): Color, Finish, Material. If these differ, use the image as
    the absolute tie-breaker. If the images show them as identical, ignore the text
    discrepancy (e.g. ignore 'Multicolor' vs 'Matte Black' if visually identical).
  Tier 3 (Logistics/Marketing Noise): Assembled product dimensions (Length, Width,
    Height, Weight), Bulk Size, target audience, subjective benefits. COMPLETELY
    IGNORE Tier 3 discrepancies. Do NOT flag Bad Data or Variant based on Tier 3.
    * CRITICAL DIMENSION IGNORE RULE: 'Assembled Product Width' and 'Assembled Product Length' (and their variations like 'Width', 'Length') MUST be completely ignored in ALL cases. Do NOT extract, compare, or use them to flag bad data or variants.

VISUAL GROUNDING:
  If primary product images are identical, maintain a "Duplicate" decision unless
  there is a clear, un-ignorable mismatch in a Tier 1 Core Identity attribute
  (different Model Numbers or different Capacity).

DATA ASYMMETRY TOLERANCE:
  Missing attributes (e.g. `-` or `None` on one side but present on the other)
  are data gaps, NOT contradictions. Do NOT flag "Bad Data" or "Variant" based
  on missing data UNLESS a specific SOP rule for that category/attribute explicitly
  states that one-side-missing equals Bad Data.
  Examples where SOP explicitly requires Bad Data for one-side-missing:
    • SOP-PAGE-217-S1 — Shoe Width missing in footwear
    • SOP-PAGE-181-S3 — Warranty missing in Electronics
    • SOP-PAGE-213-S1 — Inseam missing in clothing (when not in any other field)
  SOP-specific rules always take precedence over this general guidance.

ACTION HIERARCHY OVERRIDE:
  If there is clear proof that items are variants or completely different (e.g.
  different Model Numbers, different Native Resolutions), always choose
  "Not a Duplicate - Variant" or "Not a Duplicate" over any Bad Data trigger.
  A justified Duplicate/Variant/Not a Duplicate decision overrides any minor
  Bad Data signal.

══════════════════════════════════════════════════════════════════
RESPONSE FORMAT
══════════════════════════════════════════════════════════════════

Respond with JSON only (no markdown, no backticks):
{
  "vertical_checks": [
    {
      "product_id": "Exact string from the PRODUCT ID header (e.g. 'GTIN#1 (007...)')",
      "detected_category": "string",
      "matched_sop_rules": ["scenario_ids consulted"],
      "extracted_image_summary": "string (ultra-brief 5-10 word summary of key visual specs, or 'No image available')",
      "has_bad_data": boolean,
      "reason": "string (ULTRA-SHORT 1-2 sentence summary. If has_bad_data=false, write 'No internal contradiction found.' If true, describe the specific intra-GTIN conflict.)",
      "mismatch_details": [
        {
          "field": "string (ONLY fields with genuine intra-GTIN contradictions — not missing data)",
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
                content_parts.append(types.Part.from_text(
                    text="[No Images Provided for this product]"
                ))
                continue

            url_signature = tuple(sorted(list(set(urls))))

            if url_signature in image_cache:
                # Images already fetched — reuse cached bytes so Gemini still
                # gets the actual images for independent per-product analysis.
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

        # ── Completeness check: ensure all input products appear in output ──
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
                # Merge: keep retry entries + any originals the retry omitted.
                # product_id collision → prefer retry.
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
                # Use retry's clustering (should be more complete)
                data['horizontal_clustering'] = retry_data.get(
                    'horizontal_clustering',
                    data.get('horizontal_clustering', [])
                )
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
    import time
    start_time = time.time()
    result = asyncio.run(process_batch_analysis(products))
    elapsed_time = time.time() - start_time
    print(f"⏱️ AI batch analysis for {len(products)} products completed in {elapsed_time:.2f} seconds.")

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

    print("DupCheck backend running on http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=True)