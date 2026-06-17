# DupCheck Evaluator - Architecture & Workflow Documentation

The **DupCheck Evaluator** is a comprehensive AI-driven tool designed to automatically identify bad data and duplicate product listings (GTINs) within the Walmart (WALLE) catalog interface. It operates via a two-part system: a Chrome Browser Extension (Frontend) and a Flask API (Backend) powered by the Google Gemini Vision model.

---

## 1. High-Level Architecture

*   **Frontend (Chrome Extension)**: Injected directly into the WALLE web application. It handles DOM manipulation, UI rendering, robust data scraping (including interacting with React-based carousels), and payload generation.
*   **Backend (Flask API)**: A Python-based server that receives the scraped payload, hashes it for caching, downloads all associated images via HTTPX, and constructs a highly complex prompt to run through the Gemini 3.5 Flash Vision model.

---

## 2. The Complete Execution Flow

### Step 1: Initialization & Injection (`content.js`)
When the user clicks the extension icon on a valid WALLE page:
1. The extension injects its isolated Shadow DOM UI onto the page.
2. The user clicks **"Analyze This Page"**, which triggers `runAnalysis()`.

### Step 2: The Async Data Harvester
Because WALLE is a complex React application, data is often hidden behind carousels or expandable menus.
1. **DOM Settlement (`waitForReadMore`)**: The extension immediately clicks all "Read More" links.
2. **Carousel Harvester**: It initiates a 3-second background loop. Every 300ms, it extracts all currently visible `<img>` tags in the comparison table, stores their source URLs, and *clicks the right arrow* on the image carousel. This forces React to load the next set of secondary images.
3. **Memory Cleanup**: The harvester explicitly resets `window.__dupHarvestedImages` on every run to ensure old page data does not contaminate new analyses.

### Step 3: DOM Scraping (`extractProducts`)
Once the UI is stable and all images have been harvested, the synchronous scraper runs:
1. **GTIN Detection**: It scans `[class*="key-row"]` elements to determine how many products are being compared.
2. **Attribute Mapping**: It loops through each row. If the row contains "description", it grabs the text. If it contains "image", it merges the freshly harvested carousel images. Otherwise, it maps the row's label as an attribute key (e.g., `Actual Color`) and extracts the value for each GTIN column.
3. **Brute-Force Description Fallback**: If the standard table scrape misses the descriptions, it does a document-wide scan for headers like `Product Short Description` and explicitly rips the text from their siblings.

### Step 4: Payload Transmission & Caching (`api-client.js` -> `main.py`)
1. The extension bundles the `products` array and POSTs it to the Flask backend (`http://localhost:8000/api/analyze-batch`).
2. **MD5 Hashing**: The backend immediately serializes the JSON payload and generates an MD5 hash.
3. **Cache Check**: It checks `ai_analysis_cache.json`. If the hash exists, it instantly returns the stored AI JSON response (bypassing rate limits). If it's a miss, it continues to Step 5.

### Step 5: Gemini AI Analysis (`main.py`)
The backend downloads all image URLs into memory and sends them, along with the text attributes, to the Gemini 3.5 Flash Vision model. The AI is strictly prompted to act purely as an **OCR (Optical Character Recognition)** engine and ignore the visual shape/color of the physical items.

The AI operates in two phases:
*   **Phase 1: Vertical Check (Bad Data)**: The AI strictly reads the text written on the packaging/image and compares it against the WALLE attributes. If the image text says "2-Pack" but the attribute says "Total Count: 1", it flags a mismatch.
*   **Phase 2: Horizontal Check (Clustering)**: The AI compares the text attributes and OCR image-text *across* all valid GTINs to determine which ones are identical duplicates versus completely distinct variants. It assigns them to numbered Clusters.

### Step 6: UI Rendering (`content.js`)
The extension receives the JSON response from the backend and builds the UI:
1. **Top Summary Pills**: Displays the total count of GTINs, Bad Data flags, and Clusters.
2. **Verdict Cards**: Renders the AI's final conclusion at the very top (either a green "Identical" card, or a blue "Clusters" breakdown with highly descriptive reasoning).
3. **Phase 1 Warnings**: Highlights any bad data mismatches side-by-side (Image Text vs Attribute Text).
4. **Smart Attribute Tables**: Automatically splits attributes into a green `✓ MATCHING` table (if all GTINs share the exact same value) and a red `⚠ DIFFERING` multi-column table (if there are contradictions).
5. **Images & Descriptions**: Displays all harvested images and descriptions for manual human verification.

---

## 3. UI Tag Definitions & Key Sections

*   `scan-card` / `scan-bar`: The animated loading UI displayed while the extension harvests carousels and waits for the AI.
*   `cat-row` / `cat-box`: The styling classes for the 4 Top Summary Pills (Category, GTINS, Bad Data, Clusters).
*   `verdict-card (dup / nd / nsbd)`: The massive, colored final result cards at the top of the UI.
*   `match-all`: The layout container used to merge identical attributes or identical descriptions into a single, clean vertical list.
*   `diff-table`: The standard multi-column layout used when GTIN attributes, descriptions, or images diverge and need side-by-side visual comparison.
*   `dval red`: The explicit red-highlighted styling used to show a direct contradiction between an Image's text and a Database Attribute in Phase 1.
