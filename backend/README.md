# DupCheck Evaluator - AI Vision Backend

This folder contains the AI-powered backend service for the DupCheck Evaluator Chrome Extension. This service securely manages the connection to the Google Gemini API and performs advanced vision-based consistency checks on product data.

## 🚀 How It Works

The overarching goal of this tool is to identify "Bad Data" (Vertical Discrepancies) where the visual information of a product (its images) contradicts the structured text attributes provided on the webpage.

1. **Frontend Extraction**: The Chrome Extension (`prajna-diff-extension`) scrapes the WALLE product page. It gathers the Product Title, structured Text Attributes, and the URLs for the Main and Secondary images.
2. **Secure Transmission**: Instead of calling the Gemini API directly from the browser (which would expose your API key and cause CORS issues), the extension sends the collected data to this local backend via a `POST` request to `/api/analyze-column`.
3. **Image Fetching**: The Flask backend asynchronously downloads the product images directly from the URLs and converts them to Base64 format.
4. **AI Vision Analysis**: The backend constructs a strict prompt and sends the images and text data to the **Gemini 1.5 Flash** model. The AI is instructed to:
   - Extract specifications directly from the images (e.g., reading labels for capacity, counting items in a pack, identifying color/brand).
   - Compare those visual findings against the provided text attributes.
   - Return a strict JSON response flagging any direct contradictions.
5. **UI Update**: The extension receives the JSON response and, if inconsistencies are found, prominently displays them in the "Vertical Discrepancy" UI panel, labeling them as an `AI Vision Mismatch`.

---

## 🛠️ Step-by-Step Implementation Journey

Here is the chronological breakdown of how we architected and implemented this upgrade:

### Step 1: Identifying the Limitations of Regex
Originally, the extension used over 600 lines of hard-coded JavaScript regex to guess discrepancies (e.g., looking for "14K" in the title vs "18K" in the attributes). This was brittle and completely ignored the product images. We decided to delete this legacy code and replace it with multimodal AI.

### Step 2: Designing the Secure Architecture
We determined that placing the Gemini API key inside the Chrome Extension's frontend code was a major security risk. We established a local backend architecture to act as a secure proxy and image processor.

### Step 3: Handling Python Environment Quirks
We initially planned to build the backend using Node.js, and then FastAPI. However, because the system was running a bleeding-edge version of Python (3.14), `pydantic` (a core requirement of FastAPI) failed to compile its Rust extensions. To bypass this and ensure maximum compatibility, we pivoted to **Flask**. Flask relies purely on standard Python libraries and runs perfectly on any environment.

### Step 4: Building the Flask API (`main.py`)
We wrote an asynchronous Flask application using `httpx` to fetch images quickly. We crafted a highly specific prompt instructing Gemini to act as a "strict data consistency checker" that only flags direct contradictions (not missing data) and forces it to reply in a pure JSON format.

### Step 5: Updating the Chrome Extension (`content.js`)
We removed the massive `checkVertical()` regex engine from `content.js`. We created a new `api-client.js` file and injected it via the extension manifest. We then modified the extension's rendering engine (`runAnalysis`) to asynchronously await the AI's response for *every* GTIN column on the page concurrently before rendering the final UI.

---

## 💻 How to Run the Backend

**Prerequisites:**
You must have Python 3 installed on your system.

**1. Set up your API Key:**
Rename the `.env.example` file to `.env` and paste your Gemini API key inside:
```ini
GEMINI_API_KEY="AIzaSyYourActualKeyGoesHere..."
```

**2. Create a Virtual Environment:**
This prevents global package conflicts (the `externally-managed-environment` error).
```bash
python3 -m venv venv
```

**3. Install Dependencies:**
```bash
./venv/bin/pip install -r requirements.txt
```

**4. Start the Server:**
```bash
./venv/bin/python main.py
```

The server will start on `http://localhost:8000`. You can test it by visiting that URL in your browser, which will return a friendly "running" status message. 

Once the server is running, simply click your Chrome Extension on a WALLE page, and the AI will take over!
