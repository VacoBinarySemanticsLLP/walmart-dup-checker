"""
Static prompt content for Walmart Duplicate Checker.
Compiled into the Gemini context cache via rule_compiler.py.
Edit this file → call /api/cache-refresh to make prompt changes live.
"""

TASK_FRAMING = """
TASK: Perform a full duplicate/non-duplicate/bad-data analysis on the following products.

INSTRUCTIONS:
1. PHASE 1 (Extraction & Vertical Check): For each product individually, extract image specs via OCR and check for contradictions against text attributes. If there are unresolved contradictions or missing data that prevents comparison, flag it as "Not sure bad data".
2. PHASE 2 (Horizontal Check - Duplicate): For products that pass the vertical check, compare them against each other. If every critical attribute matches after applying SOP rules, mark them as "Duplicate".
3. PHASE 3 (Horizontal Check - Non-Duplicates): If the products are NOT duplicates, evaluate them for the following cases:
   - "Not duplicate warranty": if they differ only by warranty.
   - "Not duplicate compatibility": if they differ by vehicle/device compatibility.
   - "Not duplicate": for all other variant or non-matching product differences.

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
"""

CRITICAL_SOP_RULES = """
CRITICAL RULES FROM SOP:
- Attributes listed as "Ignore Attributes" in matching SOP rules must NOT affect decisions
- Do not flag 'Bad Data' just because a specific attribute is missing (-) if that information is clearly stated in the title, description, or under a synonymous attribute name.
- When a rule specifies visual_check=REQUIRED, images MUST be verified
- COUNT VERIFICATION (ALL CATEGORIES): Pay extremely close attention to the Unit of Measurement (UOM) in images and text. Distinguish between 'Package-Level Count' (e.g., 1 Box, 1 Case), 'Item-Level Count' (e.g., 60 Pills, 80 Pellets), and 'Weight/Volume' (e.g., 0.3 Ounces, 50ml). Do NOT flag different types of measurements as contradictions (e.g., 'Net Content: 0.3 Ounces' vs 'Count Per Pack: 80'). If an attribute like 'Total Count' or 'Multipack Quantity' is '1', it almost always refers to '1 retail package being sold'. Do NOT flag 'Total Count: 1' as a contradiction against 'Count Per Pack: 80' or a product image showing '80 Ct'. As long as the measurements describe different aspects (weight vs count vs packages), it is a PERFECT match, not Bad Data.
- PACKAGING HORIZONTAL RULES: A 2x30 configuration (2 bottles of 30) is NOT a duplicate of a 1x60 configuration (1 bottle of 60). Even if total units are the same, different package structures must be clustered separately (e.g., 'Not duplicate').
- PACKAGING TYPE RULES: Pay attention to the physical container type. A bottle is NOT a duplicate of a blister pack, and a blister pack is NOT a duplicate of a strip. Cluster these separately.
- COMPATIBILITY OVERRIDES BAD DATA: If ANY attribute (including 'Actual Color', 'Color', 'Style', 'Model', 'Size', 'Theme', or any other field) contains vehicle, device, or application compatibility data (e.g. 'For 2022-2023 Chevrolet Silverado', 'For iPhone 15 Pro', 'Fits Model XYZ-100'), do NOT flag this as a contradiction or 'Bad Data' in the vertical check, regardless of which field the compatibility data appears in. Treat it as valid compatibility information.
- DIMENSIONS & WEIGHT ARE JUNK DATA: 'Assembled Product Width', 'Assembled Product Length', 'Assembled Product Height', 'Assembled Product Weight' (and variations like 'Width', 'Length', 'Height', 'Weight'), 'Product Net Content Parent', and 'Product Net Content' MUST be completely ignored in all cases. Do not check, extract, or flag contradictions based on them; treat them entirely as junk data. Note: 'Product Net Content' and 'Product Net Content Parent' are packaging quantity fields (e.g. "1 Piece") — if a seller has entered a size-like value such as "1 Inch" into these fields, it is a data entry error and must be ignored entirely.
- SIZE RANGE TOLERANCE: When a product title or attribute contains a size RANGE (e.g., "16-22 inch", "30-40 cm", "S-XL"), any specific size value found in another attribute, the image, or OCR that falls WITHIN or reasonably near that range is NOT a contradiction. Example: title says "16-22 inch" and the Theme attribute says "16 inch" and the image shows "20 inch" — all three are consistent because 16 and 20 are both within the 16-22 range. Do NOT flag bad data when a specific value is within a stated range. Treat the range as a set of valid values, not a conflicting measurement.
- METRIC/IMPERIAL EQUIVALENCE: Metric and imperial size values that refer to the same measurement MUST be treated as identical. Use the conversion 1 inch = 2.54 cm with a rounding tolerance of ±1 inch (±2.54 cm). Examples: 40 CM ≈ 16 inches, 50 CM ≈ 20 inches, 30 CM ≈ 12 inches. If two size values differ only by unit of measurement and are equivalent within this tolerance, they are NOT a contradiction. Do NOT flag 'Not sure bad data' when a metric value and an imperial value describe the same physical size. This applies across all fields — title, attributes, and image OCR.
- MISPLACED SIZE DATA IN NON-SIZE FIELDS: Sellers frequently enter size/dimension information into the wrong attribute field. For decorative, seasonal, and home decor items (wreaths, ornaments, lanterns, etc.), if a non-size attribute such as 'Theme', 'Pattern', 'Style', 'Light Bulb Color', or similar contains a value matching the pattern '[number] CM / [number] inch', '[number]"', '[number] inch', or '[number] cm', treat it as a MISPLACED SIZE DESCRIPTOR — seller data entry error, not a thematic value. Do NOT use this misplaced size data to contradict the product title, other size attributes, or image measurements. Completely ignore it as a source of contradiction.
- LAZY METADATA & PLACEHOLDERS: Sellers frequently use lazy generic terms. The LAZY METADATA rule applies when the text attribute contains ANY of these recognized generic placeholders: "As Picture", "As Shown", "Other", "Multicolor", "Standard", "Default", "N/A", "NA", "Various", "See Description", "Same as Image", "Not Specified", "Unspecified", "See Image", "Mixed", or "-" (blank/dash). In these cases, you MUST assume they agree with the visual evidence (e.g., 'N/A' does NOT contradict any specific value; 'Various' does NOT contradict a specific value in an image; 'Other' does NOT contradict 'Clear'). Furthermore, if text is missing (-) and OCR finds the value (e.g., a Model Number), this is data enrichment, NOT a contradiction. IMPORTANT LIMIT: This rule does NOT apply when the text attribute contains a specific, definitive value (e.g., 'Yellow', 'Red', 'Blue') — a specific text value is always subject to visual verification.
- COLOR CONTRADICTION RULE (VERTICAL CHECK): When a SOP rule lists 'Color' as a core attribute under test for a category (e.g., Bedding, Fashion, Home), you MUST verify each product's Color attribute against the product image independently in the vertical check. If the text attribute states a specific, definitive color (e.g., 'Yellow') but the product image clearly shows a different color or a multicolor/mixed design, this is a REAL contradiction and must be flagged as 'Not sure bad data' for that product. Do NOT treat a specific wrong color as a placeholder. Exception: if the text says 'Multicolor' and the image is multicolor, that is consistent — no contradiction. Exception: if compatibility data is stored in the Color field (e.g., vehicle make/model), apply the COMPATIBILITY OVERRIDES BAD DATA rule instead. Exception: ACTUAL COLOR OVERRIDES COLOR — If a product has BOTH a 'Color' attribute AND an 'Actual Color' attribute, treat 'Actual Color' as the authoritative color source and verify the image against 'Actual Color' ONLY. The 'Color' attribute is a seller-supplied general label (often a vague or approximate term like 'Beige', 'Silver', 'Grey') and MUST NOT be independently cross-checked against the image or against 'Actual Color'. If 'Actual Color' is consistent with the image (e.g., 'Titanium Silverblue' matches a light silver/blueish-grey phone), the product passes the vertical color check — do NOT flag it as 'Not sure bad data' solely because 'Color' appears to differ from 'Actual Color' or the image. The perceived surface-level mismatch between a vague 'Color' and a precise manufacturer 'Actual Color' is a known data enrichment pattern, not a contradiction.
- SOP RULE MATCHING — PRODUCT TYPE MUST MATCH: When consulting SOP rules from the cached context, BOTH the category AND the product type must closely match the product being evaluated. NEVER apply a rule for one product type to a completely different product type within the same category (e.g., do NOT apply a 'USB Charger' rule to a 'TV Remote'; do NOT apply a 'Ketchup' rule to a 'Tea' product; do NOT apply a 'Sand Toys' rule to a 'Pool Float'). If only the category matches but the product type is clearly different, treat the rule as non-applicable and do NOT cite it as the matched_sop_rule. When no exact SOP rule match exists, apply the GENERALIZED METADATA NOISE & TRUTH HIERARCHY instead and cite no matched rule.
- WARRANTY TEXT IN DESCRIPTION IS NOT A CONTRADICTION: The 'Has Written Warranty' structured attribute and any warranty mention found in the product title, short description, or long description are TWO DIFFERENT data sources. Sellers commonly write warranty language in free-text descriptions (e.g., "one-year warranty", "12-month guarantee", "lifetime warranty") while leaving the structured 'Has Written Warranty' attribute as 'No' or blank. This is a well-known seller data entry pattern — NOT a contradiction. NEVER flag 'Not sure bad data' based solely on a mismatch between the 'Has Written Warranty' attribute value and warranty mentions anywhere in description text fields.
- TOYS CATEGORY — AGE ATTRIBUTES ARE IGNORED: For ALL products in the Toys category (including pool toys, floats, action figures, building sets, sand toys, bath toys, dolls, etc.), the 'Minimum Recommended Age' and 'Maximum Recommended Age' attributes MUST be completely ignored for both the vertical check AND the horizontal duplicate/non-duplicate determination. These fields are frequently entered incorrectly by sellers and do NOT distinguish between product variants. Never flag 'Not sure bad data' or 'Not duplicate' based on age attribute differences for Toys products.
"""

ACTION_HIERARCHY = """
- CLUSTERING LOGIC - IDENTICALS: Group identical/duplicate products together in the SAME cluster.
- CLUSTERING LOGIC - VARIANTS & UNIQUE: If a product is a variant, a completely unique item, or "Not duplicate", it MUST be placed in its OWN SEPARATE, STANDALONE cluster. Do NOT group variants or non-duplicates together with the primary product or with each other. Each gets its own cluster.
- CLUSTERING LOGIC - BAD DATA: Bad data products MUST be separated into their own individual clusters, never merged with any other product.
- CLUSTERING LOGIC - DIFFERENT ATTRIBUTES: Different sizes, model numbers, finish types, or compatibilities = SEPARATE clusters always.
- You MUST assign exactly ONE of the following official actions to each cluster:
  ACTION SELECTION HIERARCHY (MANDATORY)

Follow this exact required flow when assigning actions:

STEP 1: "Not sure bad data" (Vertical Check)
   Evaluate this FIRST. Use if:
   - Required attributes cannot be verified.
   - Image and text contain unresolved contradictions.
   - OCR evidence is insufficient for required verification.
   - Critical product information is missing and prevents reliable comparison.
   OVERRIDE CHECK (MANDATORY before finalizing): Before you output 'Not sure bad data', ask:
     "Are the product images clearly and visually different?" If YES — the products are different
     items and you MUST choose 'Not duplicate' instead. Clear visual difference between products
     ALWAYS overrides a bad data flag. See ACTION HIERARCHY OVERRIDE below.

STEP 2: "Duplicate" (Horizontal Check)
   If it is NOT bad data, evaluate for Duplicate.
   Use when every critical attribute matches after applying SOP ignore rules.

STEP 3: Evaluate all other cases (If NOT Duplicate)
   If products are not duplicates, you MUST assign one of the following:

   - "Not duplicate warranty"
     Use when warranty is the only material differentiator and SOP specifies warranty as variant-driving.

   - "Not duplicate compatibility"
     Use when compatibility differs (vehicle, device, model, application, etc.), regardless of other variant differences or missing data.

   - "Not duplicate"
     Use for all other cases where products belong to different families, or are variants differing in one or more variant-driving attributes not covered above.
"""

METADATA_HIERARCHY = """
GENERALIZED METADATA NOISE & TRUTH HIERARCHY:
To handle messy marketplace seller-submitted data, apply the following "common sense" hierarchy over the raw rules:
- CORE IDENTITY TIERS:
  * Tier 1 (Core Identity): Brand, capacity/volume (e.g. 32oz, 1 Liter), model number, and packaging structures (e.g. 1-pack vs 2-pack). Discrepancies here are critical and drive "Not duplicate" decisions.
  * Tier 2 (Visual Specs): Color, Finish, Material. If these differ, use the Image as the absolute tie-breaker. If the image shows them as identical, ignore the text discrepancy (e.g., ignore 'Multicolor' vs 'Matte Black' if visually identical).
  * Tier 3 (Logistics/Marketing Noise): "Is Assembly Required", assembly instructions, Assembled Product dimensions (Length, Width, Height, Weight), Bulk Size, target audience, subjective benefits (e.g. "Hair Product Form" cream vs liquid, or "Hair Type" fine vs damaged), 'Fabric Care Instructions', 'Fiction/Nonfiction' classification, 'Pant Rise', 'Age Group', 'Season', 'Clothing Size Group', 'Has Written Warranty' (the structured attribute field — warranty text in description is marketing copy and does not override this), 'Academic Institution' (when misused as a clothing size field), 'Minimum Recommended Age' and 'Maximum Recommended Age' (especially for Toys), 'Condition' (New vs New — identical values are never contradictions). Completely IGNORE discrepancies in Tier 3 attributes. Do NOT flag 'Not sure bad data' or 'Not duplicate' based on Tier 3 differences.
- VISUAL GROUNDING: If the primary product images are identical, you must maintain a "Duplicate" decision unless there is a clear, un-ignorable mismatch in a Tier 1 Core Identity attribute (different Model Numbers, or different Capacity). HOWEVER, for products featuring printed artwork, graphics, or painted scenes (e.g., printed lanterns, decorative items), you MUST perform a strict micro-level visual comparison of the artwork itself (e.g., character poses, direction, background elements, specific graphic designs). If the artwork/graphic differs in ANY way, the images are NOT identical, and you must flag it as 'Not duplicate'.
- DATA ASYMMETRY TOLERANCE: Missing attributes (e.g., `-` or `None` on one side but present on the other) are data gaps, not contradictions. Never flag "Not sure bad data" or "Not duplicate" based on missing data.
- ACTION HIERARCHY OVERRIDE: If there is clear proof that the items are variants or completely different (e.g., different Model Numbers, different Native Resolutions, or their primary product images are clearly different visually), choose "Not duplicate". Choosing "Not duplicate" based on explicit visual differences OVERRIDES any "Not sure bad data" triggers, including vertical check contradictions.
"""

CORRECTION_RULES = """
CORRECTION RULES — DECISION LOGIC OVERRIDES
Apply these rules IN ORDER. They override general attribute comparison logic.
First matching rule wins.
PRIORITY ORDER (updated):
1. Images clearly different → DIFFERENT
2. Both GTINs have ALL same internal contradictions + images identical
   → DUPLICATE (applies even if contradictions are multiple/severe)  <- UPDATED
3. Genuine valid size difference → NOT DUPLICATE
4. Missing warranty / compatibility / quantity (one-sided) → NSBD
5. Size has no valid unit → BAD DATA
6. SET product with count mismatch + description states set clearly
   → Ignore count mismatch, continue evaluation  <- ADD
7. Title marketing language contradicts color/material
   BUT attribute + image agree → Ignore title, use attribute + image  <- ADD
8. 10x size difference between description and attribute → IGNORE (unit format)
9. Junk info present → IGNORE, re-evaluate without it
10. Brand difference → IGNORE
11. Near-match color names → Treat as SAME  <- ADD
12. Color in set context or Multicolor with visible colors → NOT a contradiction
13. Internal description conflicts only → DUPLICATE if core attributes match
RULE 1: JUNK INFORMATION — IGNORE
If title or image contains junk, filler, or irrelevant text, discard it entirely.
Do NOT use junk content to trigger Bad Data or NSBD.
If all essential attributes are valid and consistent → proceed with normal decision.

RULE 2: SIZE HANDLING
  2a. SIZE WITH NO VALID UNIT OR MEASUREMENT:
      If a size value exists but has no proper unit (e.g., no cm/in/mm/ft/oz/g/etc.),
      treat it as MISSING information → mark as "Not sure bad data", NOT "Not duplicate".
  2b. SIZE ORDER DOES NOT MATTER:
      "10x5" and "5x10" are the SAME. Do not flag dimensional order differences as a discrepancy.
  2c. GENUINE SIZE DIFFERENCE ACROSS GTINs:
      If size attributes are clearly and validly different across GTINs → "Not duplicate".
      Do not override this with other matching attributes.

RULE 3: ONE-SIDED OR MISSING CRITICAL INFORMATION → NSBD
If any of the following is present on only ONE GTIN, or is entirely absent on either:
  - Warranty information
  - Compatibility information
  - Quantity per pack
→ Decision MUST be "Not sure bad data" (NSBD), regardless of other matching attributes.
Do NOT call it "Not duplicate" or "Duplicate" in these cases.

RULE 4: BRAND — DO NOT USE AS A DECIDING FACTOR
Ignore brand differences entirely when comparing GTINs.
If all other essential attributes match → proceed as "Duplicate".

RULE 5: IMAGE COMPARISON — HIGHEST PRIORITY
If main images are clearly and visually different from each other:
  → Decision is "Not duplicate", regardless of attribute similarity.
  → Do NOT let attribute matches, vertical discrepancy, or weight differences override this.
Vertical discrepancy alone is NEVER a reason to mark as different — always ignore vertical discrepancy.

RULE 6: COLOR HANDLING
  6a. COLOR IN A SET/MULTI-ITEM CONTEXT:
      If a color (e.g., silver, blue) appears as part of a set or bundle,
      it is NOT a color contradiction even if the main label says multicolor.
      If all other attributes match → "Duplicate".
  6b. NON-SPECIFIC COLOR IN NATURAL OR VARIABLE PRODUCTS (e.g., plants, animals):
      If secondary images show bulk/variety specimens with no single identifiable color
      → mark as "Not sure bad data", NOT "Not duplicate".
  6c. COLOR VISUALLY PRESENT IN IMAGE:
      If actual_color attribute says "white" (or any color) and the main image appears multicolor,
      but that color IS visibly present somewhere in the image alongside others
      → this is NOT a contradiction. Do not mark as "Not sure bad data" for this reason alone.

### RULE 6 — ADD 6d: MULTICOLOR IS NOT A CONTRADICTION WITH A SINGLE COLOR
If actual_color or color attribute is "Multicolor" and the image shows
one dominant color PLUS any other colors (LEDs, accents, trim, lighting effects)
→ NOT a contradiction. Multicolor is valid when multiple colors are visible anywhere.
Only flag as contradiction if image shows strictly one solid color
AND absolutely no other colors exist in the product or its components.

RULE 7: INTERNAL DESCRIPTION-ATTRIBUTE CONFLICTS
If there is a conflict between description text and attribute values within a single GTIN,
but the actual product information across BOTH GTINs is otherwise the same
→ Decision is "Duplicate", NOT "Not sure bad data".
Internal formatting or copy inconsistency alone is not sufficient for Bad Data.

### RULE 8: SYMMETRIC INTERNAL CONTRADICTIONS — IDENTICAL IMAGES → DUPLICATE
If BOTH GTINs share the SAME type of internal contradiction
(e.g., both have color vs image mismatch, both have description size vs
attribute size mismatch of the same pattern),
AND the main images of both GTINs are visually IDENTICAL
→ Mark as DUPLICATE.
Shared contradictions across both GTINs indicate a systemic data entry issue,
NOT a product difference.
Do NOT apply NSBD solely because both products individually have
the same internal data issues.

---

### RULE 9: SIZE — 10X UNIT FORMAT INCONSISTENCY IS NOT A DISCREPANCY
If a size value in description (e.g., 89*69*89) and size value in attribute
(e.g., 8.9X6.9X8.9CM) differ by exactly 10x across all dimensions,
treat them as the SAME measurement in different unit notations (mm vs cm).
This is a formatting inconsistency in copy, NOT a real size discrepancy.
Do NOT flag as bad data based on this alone.

---
### RULE 10: MULTIPLE SHARED CONTRADICTIONS — STILL DUPLICATE IF IMAGES IDENTICAL
Rule 8 applies regardless of HOW MANY contradictions are shared.
If every identified internal contradiction (color, count, material, size, etc.)
exists on BOTH GTINs — not just one GTIN —
AND main images are visually identical
→ Mark as DUPLICATE.
The number of shared contradictions does NOT override this.
Quantity of shared issues only confirms a systemic catalog entry problem,
NOT a product difference.
Do NOT escalate to NSBD simply because there are multiple types
of shared bad data.

---

### RULE 11: SET / BUNDLE PRODUCTS — COUNT ATTRIBUTE MISMATCH
If the product title OR description explicitly identifies the product as a
SET or BUNDLE with a specific stated quantity
(e.g., "12 Pairs Earrings Sets", "6-Pack", "Set of 4"):
  - Trust the description's stated quantity as ground truth for set size
  - Do NOT flag Total Count or Count Per Pack discrepancy as bad data
    when those attributes clearly reflect a different counting unit
    (e.g., 2 = earring types per pair, while description says 12 pairs total)
  - If BOTH GTINs have the same count mismatch pattern
    → systemic catalog issue, not a differentiating factor
  - Only flag count as bad data if the SET NATURE of the product
    is itself unclear or missing

---

### RULE 12: TITLE MARKETING LANGUAGE — ATTRIBUTE + IMAGE AGREEMENT OVERRIDES TITLE
If the product title contains marketing/descriptive terms
(e.g., "14K Gold Plated", "Heavy Duty", "Premium Stainless")
that conflict with the actual_color or material attribute,
BUT the actual_color attribute AND main image AGREE with each other:
  → The title contains marketing or aspirational language
  → Do NOT flag this as a color or material contradiction
  → Use actual_color attribute and image as the ground truth pair
  → Title alone CANNOT trigger bad data when attribute + image are consistent

---

### RULE 13: NEAR-MATCH COLOR NAMES — TREAT AS SAME
The following color name pairs must be treated as identical:
  - Silver = Silver Plated = Silver-A = Silver/Steel = Steel
  - Gold = Gold Plated = 14K Gold = Golden
  - White = Off-White = Cream = Pearl White
  - Black = Matte Black = Jet Black
  - Multicolor = Multi = Multi-Color = Multi-Colored
Do NOT flag a contradiction when two values from the same group appear
across attribute and image verification.
"""

RESPONSE_SCHEMA = """
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
      "cluster_type": "string (duplicate|not_duplicate|bad_data)",
      "recommended_action": "Exact string from the official actions list above",
      "matched_sop_rule": "scenario_id that determined this clustering",
      "reason": "string (ULTRA-SHORT 1-2 sentence summary. Focus only on the main difference or missing attribute. DO NOT write long paragraphs.)"
    }
  ]
}
"""
