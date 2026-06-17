const express = require('express');
const cors = require('cors');
require('dotenv').config();
const { GoogleGenerativeAI } = require('@google/generative-ai');
const https = require('https');
const http = require('http');

const app = express();
const port = 3000;

app.use(cors());
app.use(express.json({ limit: '10mb' }));

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

// Helper function to fetch image as base64
function fetchImageAsBase64(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    client.get(url, (res) => {
      if (res.statusCode !== 200) {
        return reject(new Error(`Failed to fetch image: ${res.statusCode}`));
      }
      
      const mimeType = res.headers['content-type'] || 'image/jpeg';
      const chunks = [];
      
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        const buffer = Buffer.concat(chunks);
        resolve({
          inlineData: {
            data: buffer.toString('base64'),
            mimeType: mimeType
          }
        });
      });
    }).on('error', (e) => reject(e));
  });
}

app.post('/api/analyze-column', async (req, res) => {
  try {
    const { attributes, title, imageUrls } = req.body;
    
    if (!imageUrls || imageUrls.length === 0) {
      return res.json({ status: 'no_images', message: 'No image URLs provided for analysis.' });
    }

    const prompt = `
      You are a strict data consistency checker.
      I am providing you with the text attributes and title for a product, along with its images.
      
      Product Title: ${title}
      Text Attributes: ${JSON.stringify(attributes, null, 2)}
      
      Task:
      1. Carefully examine the provided images to extract any readable specifications (e.g., size, weight, quantity/pack size, color, brand, model).
      2. Compare these visually extracted specifications against the provided 'Text Attributes' and 'Product Title'.
      3. Identify any clear contradictions. (e.g., if the image shows a "2-Pack" but the text says "Count: 1", that is a contradiction).
      4. DO NOT flag missing information as a contradiction. Only flag direct contradictions.
      
      Respond STRICTLY with a JSON object in the following format, with no markdown formatting or backticks:
      {
        "hasInconsistency": boolean,
        "inconsistencies": [
          {
            "field": "string (the attribute or spec in question)",
            "imageValue": "string (what the image shows)",
            "textValue": "string (what the text says)",
            "reason": "string (brief explanation)"
          }
        ]
      }
    `;

    // Fetch all images concurrently
    let imageParts = [];
    try {
      imageParts = await Promise.all(imageUrls.map(url => fetchImageAsBase64(url)));
    } catch (e) {
      console.error('Error fetching images:', e);
      return res.status(400).json({ status: 'error', message: 'Could not fetch one or more images from the provided URLs.' });
    }

    // Use Gemini 1.5 Flash for multimodal fast responses
    const model = genAI.getGenerativeModel({ model: "gemini-1.5-flash" });
    
    const result = await model.generateContent([prompt, ...imageParts]);
    const response = await result.response;
    let text = response.text();
    
    text = text.replace(/```json/gi, '').replace(/```/gi, '').trim();
    
    try {
      const jsonResponse = JSON.parse(text);
      res.json({ status: 'success', data: jsonResponse });
    } catch (e) {
      console.error('Failed to parse Gemini response:', text);
      res.status(500).json({ status: 'error', message: 'Invalid JSON response from AI' });
    }

  } catch (error) {
    console.error('Analysis error:', error);
    res.status(500).json({ status: 'error', message: error.message });
  }
});

app.listen(port, () => {
  console.log(`DupCheck backend running on http://localhost:${port}`);
  console.log(`Make sure GEMINI_API_KEY is set in your .env file`);
});
