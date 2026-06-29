import re

with open('backend/main.py', 'r') as f:
    content = f.read()

# Replace ACTION SELECTION HIERARCHY
old_actions = """1. "Not Duplicate - Different Compatibility"
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
   Use only when the products belong to completely different product families and are not variants of each other."""

new_actions = """1. "Not sure bad data"
   Use if:
   - Required attributes cannot be verified.
   - Image and text contain unresolved contradictions.
   - OCR evidence is insufficient for required verification.
   - Critical product information is missing and prevents reliable comparison.

2. "Duplicate"
   Use when every critical attribute matches after applying SOP ignore rules.

3. "Not duplicate"
   Use only when the products belong to completely different product families and are not variants of each other, or if they are variants but differ in one or more variant-driving attributes.

4. "Not duplicate warranty"
   Use when warranty is the only material differentiator and SOP specifies warranty as variant-driving.

5. "Not duplicate compatibility"
   Use when compatibility differs (vehicle, device, model, application, etc.), regardless of other variant differences or missing data."""

content = content.replace(old_actions, new_actions)

content = content.replace("its DECISION (Duplicate / Not a Duplicate / Not sure - Bad data).",
                          "its DECISION (Duplicate / Not duplicate / Not sure bad data / etc).")
content = content.replace("e.g., 'Not a Duplicate - Variant'", "e.g., 'Not duplicate'")
content = content.replace("or \"Not a Duplicate\"", "or \"Not duplicate\"")
content = content.replace("\"Not a Duplicate\" / \"Variant\" decisions", "\"Not duplicate\" decisions")
content = content.replace("flag 'Bad Data' or 'Variant' based on", "flag 'Not sure bad data' or 'Not duplicate' based on")
content = content.replace("\"Not a Duplicate - Variant\" or \"Not a Duplicate\"", "\"Not duplicate\"")
content = content.replace("Choosing \"Not a Duplicate\" or \"Variant\" overrides any minor \"Bad Data\" triggers.",
                          "Choosing \"Not duplicate\" overrides any minor \"Not sure bad data\" triggers.")
content = content.replace("cluster_type\": \"string (duplicate|variant|unique|bad_data)", "cluster_type\": \"string (duplicate|not_duplicate|bad_data)")
content = content.replace("Each VARIANT / NOT A DUPLICATE product", "Each NOT DUPLICATE product")
content = content.replace("duplicate|variant|unique|bad_data", "duplicate|not_duplicate|bad_data")

with open('backend/main.py', 'w') as f:
    f.write(content)
