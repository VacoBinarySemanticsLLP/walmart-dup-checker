// prajna-diff-extension/api-client.js

/**
 * Sends product data to the local backend for Gemini Vision analysis.
 * Extracts image URLs and text attributes to verify consistency.
 */
window.analyzeProductWithGemini = async function(product) {
  console.log('🤖 DupCheck AI: Preparing to analyze product...', product.name || 'Unknown');
  try {
    // Collect image URLs
    const imageUrls = [];
    if (product.img1) imageUrls.push(product.img1);
    if (product.img2) imageUrls.push(product.img2);
    
    // If no images, we can't do vision analysis
    if (imageUrls.length === 0) {
      console.warn('🤖 DupCheck AI: No images found for product, skipping vision analysis.');
      return null;
    }

    console.log(`🤖 DupCheck AI: Extracted ${imageUrls.length} images. Sending request to backend...`);

    const payload = {
      title: product.name || '',
      attributes: product.attrs || {},
      imageUrls: imageUrls
    };

    const response = await fetch('http://127.0.0.1:8000/api/analyze-column', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      let errMsg = `Backend responded with status ${response.status}`;
      try {
        const errJson = await response.json();
        if (errJson.message) errMsg = errJson.message;
      } catch (e) {}
      throw new Error(errMsg);
    }

    const result = await response.json();
    console.log('🤖 DupCheck AI: Received response from backend:', result);
    
    if (result.status === 'success') {
      return result.data; // { hasInconsistency: true/false, inconsistencies: [...] }
    } else {
      throw new Error(result.message || 'Gemini Analysis failed');
    }
  } catch (error) {
    console.error('Failed to communicate with backend:', error);
    throw error;
  }
};

/**
 * Sends a batch of products to the backend for two-phase AI analysis.
 */
window.analyzeBatchWithGemini = async function(products, forceRefresh = false) {
  console.log(`🤖 DupCheck AI: Preparing to send batch of ${products.length} products to AI...`);
  try {
    const payloadProducts = products.map((p, idx) => {
      const imageUrls = [];
      if (p.imgs_main && p.imgs_main.length > 0) {
          imageUrls.push(...p.imgs_main);
      } else if (p.img1) {
          imageUrls.push(p.img1);
      }
      
      if (p.imgs_sec && p.imgs_sec.length > 0) {
          imageUrls.push(...p.imgs_sec);
      } else if (p.img2) {
          imageUrls.push(p.img2);
      }
      
      let finalDesc = p.description || '';
      // Fallback: If description was parsed as a regular attribute by mistake, extract it here
      for (const [key, value] of Object.entries(p.attrs || {})) {
          if (key.toLowerCase().includes('desc')) {
              finalDesc += '\n' + value;
          }
      }

      // Deduplicate images exactly
      const uniqueImageUrls = Array.from(new Set(imageUrls));

      let prodId = p.gtin || '';
      if (!prodId || prodId.startsWith('GTIN#')) {
        const pid = p.attrs['Product ID'] || p.attrs['product id'] || '';
        if (pid) {
          prodId = pid;
        } else {
          const itemId = p.attrs['Item ID'] || p.attrs['item id'] || '';
          if (itemId) {
            prodId = itemId;
          } else {
            prodId = p.gtin || p.name || 'Unknown';
          }
        }
      }

      let finalId = 'GTIN#' + (idx + 1);
      if (prodId && !prodId.startsWith('GTIN#')) finalId += ' (' + prodId + ')';

      return {
        id: finalId,
        title: p.name || '',
        description: finalDesc.trim(),
        attributes: p.attrs || {},
        imageUrls: uniqueImageUrls
      };
    });

    const payload = { products: payloadProducts, forceRefresh: forceRefresh };
    const payloadStr = JSON.stringify(payload);
    
    console.log(`🤖 DupCheck AI: Sending batch request to backend (Force Refresh: ${forceRefresh}):`, payload);

    const response = await fetch('http://127.0.0.1:8000/api/analyze-batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payloadStr
    });

    if (!response.ok) {
      let errMsg = `Backend responded with status ${response.status}`;
      try {
        const errJson = await response.json();
        if (errJson.message) errMsg = errJson.message;
      } catch (e) {}
      throw new Error(errMsg);
    }

    const result = await response.json();
    console.log('🤖 DupCheck AI: Received batch response:', result);
    
    if (result.status === 'success') {
      return result.data;
    } else {
      throw new Error(result.message || 'Gemini Batch Analysis failed');
    }
  } catch (error) {
    console.error('Failed to communicate with backend:', error);
    throw error;
  }
};
