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
      throw new Error(`Backend responded with status ${response.status}`);
    }

    const result = await response.json();
    console.log('🤖 DupCheck AI: Received response from backend:', result);
    
    if (result.status === 'success') {
      return result.data; // { hasInconsistency: true/false, inconsistencies: [...] }
    } else {
      console.warn('🤖 DupCheck AI: Gemini Analysis failed:', result.message);
      return null;
    }
  } catch (error) {
    console.error('Failed to communicate with backend:', error);
    return null;
  }
};

/**
 * Sends a batch of products to the backend for two-phase AI analysis.
 */
window.analyzeBatchWithGemini = async function(products, forceRefresh = false) {
  console.log(`🤖 DupCheck AI: Preparing to send batch of ${products.length} products to AI...`);
  try {
    const payloadProducts = products.map(p => {
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

      return {
        id: p.gtin || p.name || 'Unknown',
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
      throw new Error(`Backend responded with status ${response.status}`);
    }

    const result = await response.json();
    console.log('🤖 DupCheck AI: Received batch response:', result);
    
    if (result.status === 'success') {
      return result.data;
    } else {
      console.warn('🤖 DupCheck AI: Gemini Batch Analysis failed:', result.message);
      return null;
    }
  } catch (error) {
    console.error('Failed to communicate with backend:', error);
    return null;
  }
};
