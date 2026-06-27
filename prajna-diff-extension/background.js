chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'fetch_backend') {
    fetch(request.url, request.options)
      .then(response => {
        if (!response.ok) {
           return response.text().then(text => { throw new Error(`Backend responded with status ${response.status}: ${text}`) });
        }
        return response.json();
      })
      .then(data => sendResponse({ status: 'success', data: data }))
      .catch(error => sendResponse({ status: 'error', message: error.toString() }));
    return true; // Indicates async response
  }
});
