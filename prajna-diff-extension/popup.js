document.getElementById('activateBtn').addEventListener('click', async () => {
  var statusEl = document.getElementById('status');
  statusEl.textContent = 'Injecting…';
  statusEl.className = 'status';

  var tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  var tab  = tabs[0];

  if (!tab || !tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('about:')) {
    statusEl.textContent = 'Open a WALLE page first';
    statusEl.className = 'status err';
    return;
  }

  try {
    await chrome.scripting.executeScript({ target:{tabId:tab.id}, files:['api-client.js', 'content.js'], world: 'MAIN' });
  } catch(e) {
    statusEl.textContent = 'Inject error: ' + e.message;
    statusEl.className = 'status err';
    return;
  }

  await new Promise(r => setTimeout(r, 400));

  try {
    var results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: 'MAIN',
      func: function() {
        if (typeof window.__prajnaShow === 'function') {
          window.__prajnaShow();
          return 'ok';
        }
        return 'fn_missing';
      }
    });
    var r = results && results[0] && results[0].result;
    if (r === 'ok') {
      statusEl.textContent = '✓ Panel opened!';
      statusEl.className = 'status ok';
      setTimeout(function(){ window.close(); }, 700);
    } else {
      statusEl.textContent = 'Error: ' + r;
      statusEl.className = 'status err';
    }
  } catch(e) {
    statusEl.textContent = 'Call error: ' + e.message;
    statusEl.className = 'status err';
  }
});
