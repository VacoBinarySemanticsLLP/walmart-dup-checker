import os
import json
import base64
import asyncio
import httpx
import hashlib
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
from dotenv import load_dotenv
import hashlib

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
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
    except Exception as e:
        print("Failed to save cache:", e)

def get_cache_key(products):
    # Normalize products to ensure imageUrls order doesn't break the cache hash
    normalized_products = []
    for p in products:
        norm_p = p.copy()
        if 'imageUrls' in norm_p and isinstance(norm_p['imageUrls'], list):
            norm_p['imageUrls'] = sorted(list(set(norm_p['imageUrls'])))
        normalized_products.append(norm_p)
        
    payload_str = json.dumps(normalized_products, sort_keys=True)
    return hashlib.md5(payload_str.encode('utf-8')).hexdigest()

# Load environment variables from .env file
load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    print("WARNING: GEMINI_API_KEY not found in .env file")

app = Flask(__name__)
# Allow CORS for Chrome Extension
CORS(app)

async def fetch_image(client: httpx.AsyncClient, url: str) -> dict:
    try:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        mime_type = response.headers.get("content-type", "image/jpeg")
        base64_data = base64.b64encode(response.content).decode('utf-8')
        return {
            "mime_type": mime_type,
            "data": base64_data
        }
    except Exception as e:
        print(f"Error fetching image {url}: {e}")
        return None

async def process_analysis(title, attributes, imageUrls):
    prompt = f"""
      You are a strict data consistency checker.
      I am providing you with the text attributes and title for a product, along with its images.
      
      Product Title: {title}
      Text Attributes: {json.dumps(attributes, indent=2)}
      
      Task:
      1. Carefully examine the provided images to extract any readable specifications (e.g., size, weight, quantity/pack size, color, brand, model).
      2. Compare these visually extracted specifications against the provided 'Text Attributes' and 'Product Title'.
      3. Identify any clear contradictions. (e.g., if the image shows a "2-Pack" but the text says "Count: 1", that is a contradiction).
      4. DO NOT flag missing information as a contradiction. Only flag direct contradictions.
      
      Respond STRICTLY with a JSON object in the following format, with no markdown formatting or backticks:
      {{
        "hasInconsistency": boolean,
        "inconsistencies": [
          {{
            "field": "string (the attribute or spec in question)",
            "imageValue": "string (what the image shows)",
            "textValue": "string (what the text says)",
            "reason": "string (brief explanation)"
          }}
        ]
      }}
    """

    # Fetch images concurrently
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
        model = genai.GenerativeModel('gemini-3.5-flash')
        
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
            print("AI Raw Response: no response by ai")
            return {"status": "error", "message": "no response by ai"}
            
        # Clean up potential markdown formatting
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

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "running", "message": "DupCheck Backend is active and listening."})

@app.route("/test-ai", methods=["GET"])
def test_ai():
    # Dummy data for testing the AI directly in the browser
    title = "Bulbasaur"
    attributes = {"Type": "Grass", "Color": "Blue"}
    imageUrls = ["https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/1.png"]
    
    result = asyncio.run(process_analysis(title, attributes, imageUrls))
    
    # Return formatted HTML to view easily in the browser
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
        
    # Run async logic inside Flask's sync route
    result = asyncio.run(process_analysis(title, attributes, imageUrls))
    
    if result.get("status") == "error":
        return jsonify(result), 500
        
    return jsonify(result)

async def process_batch_analysis(products):
    prompt = """
    You are a strict data consistency and duplicate checker.
    I am providing you with multiple product listings. Each product has a product_id, title, description, text attributes, and images.
    
    Task Phase 1: Vertical Check (Bad Data)
    For each product individually, perform OCR to extract ONLY the VALUABLE TEXT SPECIFICATIONS written on its images (such as size, count, weight, model number, color, flavor, brand). 
    CRITICAL INSTRUCTION: Ignore irrelevant background text, logos, or marketing fluff (e.g., "New", "Sale", "Great Taste!"). ONLY evaluate whether the valid spec text extracted from the image matches or contradicts the Product Attributes and Title.
    If there is NO valuable spec text written on the image, consider the image check to have PASSED and do not flag it.
    
    IMPORTANT RULE AGAINST INFERENCE & MARKETING FLUFF: Do NOT flag contradictions based on subjective adjectives, brand names, or ambiguous marketing claims (e.g., "Natural", "Vibrant", "Pro", "Max", "Clear"). You must ONLY flag a mismatch if the text on the image provides an EXACT, EXPLICIT specification (e.g., "10g", "Blue", "2-Pack") that directly and undeniably contradicts a hard attribute in the table. Never make logical leaps, assumptions, or interpret promotional slogans as technical specifications.

    Identify any clear contradictions (e.g., text on the image says "2-Pack" but text attributes say "Count: 1", or description mentions "Stainless Steel" but text on the image says "Plastic"). If there is a contradiction, flag it as having 'bad data'.

    Task Phase 2: Horizontal Check (Duplicate Clustering)
    For all products that DO NOT have bad data (i.e., they passed Phase 1), compare them against each other using their Titles, Descriptions, Attributes, and the TEXT extracted from their Images.
    CRITICAL INSTRUCTION FOR PHASE 2: Just like Phase 1, you must remain COMPLETELY BLIND to the visual objects, colors, or patterns in the images. ONLY use the literal text written on the images to differentiate them.
    Determine if they are identical items (duplicates), variants, or completely different items.
    Group similar/identical items into clusters. If a product is unique, it goes into its own cluster.
    
    Respond STRICTLY with a JSON object in the following format, with no markdown formatting:
    {
      "vertical_checks": [
        {
          "product_id": "string",
          "extracted_image_specs": "string (A concise summary of the valid spec text extracted from the images, e.g. 'Size: Large, Count: 2'. If no valuable specs were found, put 'None')",
          "has_bad_data": boolean,
          "reason": "string (A HIGHLY DESCRIPTIVE explanation of exactly what text was read from the image, what text was read from the table/description, and exactly where the contradiction lies. Be specific and wordy.)",
          "mismatch_details": [
            {
              "field": "string (the exact attribute or description field in question)",
              "imageValue": "string (the exact spec text read from the image)",
              "textValue": "string (the exact text from the product attributes)"
            }
          ]
        }
      ],
      "horizontal_clustering": [
        {
          "cluster_name": "string (e.g., 'Cluster 1')",
          "product_ids": ["string", "string"],
          "reason": "string (A HIGHLY DESCRIPTIVE explanation of exactly why these products belong together, and exactly what specific attributes/text in the table differentiate them from the OTHER clusters. Explicitly name the table fields that differ, e.g., 'These items share Size X, whereas Cluster 2 has Size Y in the Size attribute field.')"
        }
      ]
    }
    """
    
    contents = [prompt]
    
    async with httpx.AsyncClient() as client:
        # Keep track of unique image sets to avoid sending duplicates to Gemini
        # Dictionary mapping a sorted tuple of URLs -> the Product ID that first used them
        seen_image_sets = {}
        
        for p in products:
            prod_id = p.get('id', 'Unknown')
            prod_text = f"\n\n--- PRODUCT ID: {prod_id} ---\nTitle: {p.get('title')}\nDescription: {p.get('description', '')}\nAttributes: {json.dumps(p.get('attributes', {}), indent=2)}\nImages for {prod_id}:"
            contents.append(prod_text)
            
            urls = p.get('imageUrls', [])
            
            if not urls:
                contents.append("[No Images Provided for this product]")
                continue
                
            # Create a deterministic hashable signature for this product's image set
            url_signature = tuple(sorted(list(set(urls))))
            
            if url_signature in seen_image_sets:
                first_prod_id = seen_image_sets[url_signature]
                contents.append(f"[The images for this product are EXACTLY identical to the images provided above for PRODUCT ID: {first_prod_id}. Please reference those images.]")
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
                    contents.append("[No Images Provided for this product]")

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

        model = genai.GenerativeModel('gemini-3.5-flash')
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
    # Run Flask on port 8000 to match previous FastAPI config
    app.run(host="0.0.0.0", port=8000, debug=True)
