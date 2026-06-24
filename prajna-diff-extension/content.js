var _url = window.location.href.toLowerCase();
var _isWALLE = _url.indexOf('walle')>=0 || _url.indexOf('walmart')>=0 ||
 !!document.querySelector('[class*="review-group"],[class*="group-module"],[class*="walle"]') ||
 document.title.toLowerCase().indexOf('walle')>=0;


if(!_isWALLE){
 // not walle
} else if(window.__DupCheck_LOADED){
 if(window.__prajnaShow) window.__prajnaShow();
} else {
 window.__DupCheck_LOADED = true;
 init();
}


function init(){


var host = document.createElement('div');
host.id = 'prajna-host';
host.setAttribute('style',
 'position:fixed!important;top:60px!important;right:0!important;'+
 'width:0!important;height:calc(100vh - 60px)!important;z-index:2147483647!important;'+
 'pointer-events:none!important;margin:0!important;padding:0!important;border:none!important;'+
 'overflow:visible!important;');
document.documentElement.appendChild(host);
var shadow = host.attachShadow({mode:'open'});


var css = document.createElement('style');
css.textContent = `
*{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',system-ui,sans-serif;}
#wrap{
 width:var(--panel-w,360px);height:calc(100vh - 60px);background:#f0f2ff;
 border-left:1px solid #c8caff;
 box-shadow:-4px 0 20px rgba(0,0,0,.15);
 display:flex;flex-direction:column;overflow:hidden;
 transform:translateX(100%);
 transition:transform .3s cubic-bezier(.4,0,.2,1), width .25s ease;
 pointer-events:none;
}
#wrap.open{transform:translateX(0);pointer-events:auto;}
/* horizontal scroll for multi-GTIN tables */
.multi-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;}
.multi-scroll::-webkit-scrollbar{height:4px;}
.multi-scroll::-webkit-scrollbar-thumb{background:#c5c8ff;border-radius:2px;}
/* M shortcut hint in header */
.m-hint{font-size:8px;background:rgba(255,255,255,.15);border-radius:4px;padding:1px 5px;color:rgba(255,255,255,.7);letter-spacing:.3px;margin-left:4px;}
#hdr{
 background:linear-gradient(135deg,#3d3df5,#5b3de8);
 padding:12px 14px 10px;flex-shrink:0;
}
.hdr-row{display:flex;align-items:center;gap:10px;margin-bottom:8px;}
.logo-box{width:36px;height:36px;background:#ffcc00;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;}
.hdr-title{font-weight:800;font-size:15px;color:#fff;}
.hdr-sub{font-size:9px;color:rgba(255,255,255,.65);}
.hdr-btns{display:flex;gap:6px;}
.hdr-btn{background:rgba(255,255,255,.15);border:none;color:#fff;width:26px;height:26px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:13px;}
.hdr-btn:hover{background:rgba(255,255,255,.28);}
.analyze-btn{width:100%;padding:9px;background:rgba(255,255,255,.18);border:1.5px solid rgba(255,255,255,.35);color:#fff;font-weight:700;font-size:12px;letter-spacing:.4px;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;}
.analyze-btn:hover{background:rgba(255,255,255,.28);}
#body{flex:1;overflow-y:auto;padding:10px;}
#body::-webkit-scrollbar{width:3px;}
#body::-webkit-scrollbar-thumb{background:#c5c8ff;border-radius:2px;}
.scan-card{background:#fff;border-radius:12px;padding:32px 20px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.07);}
.scan-bars{display:flex;gap:5px;align-items:flex-end;height:32px;justify-content:center;margin-bottom:12px;}
.scan-bar{width:6px;border-radius:3px;background:#3d3df5;animation:scanbar 1s ease-in-out infinite;}
.scan-bar:nth-child(1){height:30%;animation-delay:0s;}
.scan-bar:nth-child(2){height:65%;animation-delay:.15s;}
.scan-bar:nth-child(3){height:100%;animation-delay:.3s;}
.scan-bar:nth-child(4){height:65%;animation-delay:.45s;}
.scan-bar:nth-child(5){height:30%;animation-delay:.6s;}
@keyframes scanbar{0%,100%{opacity:.25;transform:scaleY(.5)}50%{opacity:1;transform:scaleY(1)}}
.scan-txt{font-size:13px;font-weight:700;color:#333;}
.scan-sub{font-size:10px;color:#999;margin-top:4px;}
.nogtin-card{background:#fff;border-radius:12px;padding:32px 20px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.07);}
.nogtin-icon{font-size:40px;margin-bottom:10px;}
.nogtin-title{font-size:13px;font-weight:700;color:#444;margin-bottom:6px;}
.nogtin-sub{font-size:11px;color:#888;line-height:1.6;}
/* pill uses external inline styles — no shadow DOM CSS needed */
/* WARNING BANNER */
.warn-banner{
 background:#fff8e1;border:1.5px solid #f0c040;border-radius:10px;
 padding:10px 12px;margin-bottom:10px;
 animation:slideUp .4s .05s ease both;
 display:flex;align-items:flex-start;gap:8px;
}
.warn-icon{font-size:16px;flex-shrink:0;margin-top:1px;}
.warn-body{flex:1;}
.warn-title{font-size:11px;font-weight:700;color:#92400e;margin-bottom:3px;}
.warn-list{font-size:10px;color:#78350f;line-height:1.7;}
.verdict-card{border-radius:12px;padding:16px;margin-bottom:10px;text-align:center;animation:slideUp .4s cubic-bezier(.4,0,.2,1) both;}
@keyframes slideUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.verdict-card.dup{background:#e8faf0;border:2px solid #2ecc71;}
.verdict-card.nd{background:#fdecea;border:2px solid #e74c3c;}
.verdict-card.nsbd{background:#fef9e7;border:2px solid #f39c12;}
.v-icon{font-size:20px;margin-bottom:4px;}
.v-txt{font-size:22px;font-weight:900;letter-spacing:-.5px;animation:popIn .4s .1s cubic-bezier(.34,1.56,.64,1) both;}
@keyframes popIn{from{opacity:0;transform:scale(.5)}to{opacity:1;transform:scale(1)}}
.verdict-card.dup .v-txt{color:#1a7f4b;}
.verdict-card.nd .v-txt{color:#c0392b;}
.verdict-card.nsbd .v-txt{color:#d68910;}
.v-reason{font-size:11px;color:#555;margin-top:6px;line-height:1.5;animation:fadeUp .3s .2s ease both;}
@keyframes fadeUp{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.status-line{font-size:11px;font-weight:600;text-align:center;margin-bottom:8px;color:#2ecc71;animation:fadeUp .3s .05s ease both;}
.cat-row{display:flex;gap:8px;margin-bottom:10px;animation:fadeUp .3s .2s ease both;}
.cat-box{background:#fff;border-radius:8px;padding:8px 10px;flex:1;box-shadow:0 1px 4px rgba(0,0,0,.07);font-size:10px;}
.cat-lbl{font-weight:700;color:#888;text-transform:uppercase;letter-spacing:.5px;margin-bottom:2px;}
.cat-val{font-weight:700;color:#3d3df5;font-size:12px;}
.img-section{background:#fff;border-radius:10px;margin-bottom:10px;overflow:hidden;box-shadow:0 1px 6px rgba(0,0,0,.07);animation:slideUp .4s .1s ease both;}
.img-sec-hdr{padding:7px 12px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#666;border-bottom:1px solid #f0f0f0;background:#fafafa;}
.img-row{display:flex;gap:1px;background:#f0f0f0;}
.img-cell{flex:1;background:#fff;padding:8px;text-align:center;}
.img-cell img{width:72px;height:72px;object-fit:contain;border-radius:4px;}
.img-lbl{font-size:9px;color:#888;margin-bottom:4px;font-weight:600;}
.img-badge{font-size:8px;font-weight:700;margin-top:4px;padding:2px 8px;border-radius:10px;display:inline-block;}
.img-badge.diff{background:#fdecea;color:#c0392b;}
.img-badge.same{background:#e8faf0;color:#1a7f4b;}
.sop-box{background:#eef0ff;border:1px solid #c5c8ff;border-radius:10px;padding:12px;margin-bottom:10px;animation:slideUp .4s .15s ease both;}
.sop-lbl{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#3d3df5;margin-bottom:6px;}
.sop-txt{font-size:11px;color:#333;line-height:1.6;font-weight:500;}
.match-all{background:#e8faf0;border:1px solid #a9dfbf;border-radius:10px;padding:12px;margin-bottom:10px;animation:slideUp .4s .2s ease both;}
.match-all-hdr{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:#1a7f4b;margin-bottom:8px;}
.match-row{display:flex;padding:4px 0;border-bottom:1px solid rgba(0,0,0,.05);}
.match-row:last-child{border-bottom:none;}
.match-field{font-size:11px;font-weight:600;color:#444;flex:0 0 130px;}
.match-val{font-size:11px;font-weight:700;color:#1a7f4b;word-break:break-word;}
.diff-table{background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 6px rgba(0,0,0,.07);margin-bottom:10px;animation:slideUp .4s .25s ease both;}
.diff-hdr{display:flex;background:#fdecea;border-bottom:1px solid #f5b7b7;padding:7px 12px;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;color:#c0392b;align-items:center;justify-content:space-between;}
.diff-badge{background:#c0392b;color:#fff;font-size:8px;padding:2px 7px;border-radius:10px;font-weight:700;}
.diff-col-hdr{display:flex;background:#fafafa;border-bottom:1px solid #f0f0f0;}
.diff-col-hdr div{flex:1;padding:4px 10px;font-size:8px;font-weight:700;text-transform:uppercase;color:#aaa;border-right:1px solid #f0f0f0;}
.diff-col-hdr div:last-child{border-right:none;}
.drow{border-bottom:1px solid #f8f8f8;background:#fff;}
.drow:last-child{border-bottom:none;}
.dlbl{padding:4px 10px 2px;font-size:9px;font-weight:700;color:#777;text-transform:uppercase;background:#fafafa;border-bottom:1px solid #f5f5f5;}
.dvals{display:flex;}
.dval{flex:1;padding:5px 10px 6px;font-size:11px;font-weight:600;line-height:1.4;word-break:break-word;border-right:1px solid #f5f5f5;min-height:28px;}
.dval:last-child{border-right:none;}
.dval.red{background:#fff5f5;color:#c0392b;}
.dval.grn{background:#f0fff4;color:#1a7f4b;}
.dval.muted{color:#ccc;font-style:italic;font-weight:400;}
.err{background:#fff;border-radius:10px;padding:16px;color:#c0392b;font-size:11px;line-height:1.7;box-shadow:0 1px 6px rgba(0,0,0,.07);}
.dbg{background:#fff;border-radius:10px;padding:12px;margin-top:8px;font-size:9px;color:#888;line-height:1.8;word-break:break-all;box-shadow:0 1px 4px rgba(0,0,0,.05);}
#foot{padding:6px 12px;border-top:1px solid #dddeff;background:#eef0ff;flex-shrink:0;display:flex;justify-content:space-between;align-items:center;}
.finfo{font-size:9px;color:#aaa;}
.rerun{background:#3d3df5;border:none;color:#fff;padding:3px 10px;border-radius:5px;cursor:pointer;font-size:10px;font-weight:700;}
.rerun:hover{background:#2d2dcc;}
`;


var wrap = document.createElement('div');
wrap.id = 'wrap';
wrap.innerHTML =
 '<div id="hdr">'+
   '<div class="hdr-row">'+
     '<div class="logo-box">⚡</div>'+
     '<div style="flex:1"><div class="hdr-title">DupCheck</div><div class="hdr-sub">Duplicate Detection Evaluator</div></div>'+
     '<div class="hdr-btns">'+
       '<button class="hdr-btn" id="translatebtn" title="Translate to English" style="font-size:12px">A/文</button>'+
       '<button class="hdr-btn" id="minbtn" title="Minimize">—</button>'+
     '</div>'+
   '</div>'+
   '<button class="analyze-btn" id="analyzebtn">🔍  Analyze This Page</button>'+
 '</div>'+
 '<div id="body"><div class="scan-card">'+
   '<div class="scan-bars"><div class="scan-bar"></div><div class="scan-bar"></div><div class="scan-bar"></div><div class="scan-bar"></div><div class="scan-bar"></div></div>'+
   '<div class="scan-txt">Waiting for WALLE…</div>'+
   '<div class="scan-sub">Auto-analyzes when table loads</div>'+
 '</div></div>'+
 '<div id="foot"><div class="finfo">Walmart Dups SOP · Jan 2026</div><button class="rerun" id="rerun">↻ Re-run</button></div>';


shadow.appendChild(css);
shadow.appendChild(wrap);
// ── PILL (minimized state) — all styles inline, lives outside Shadow DOM ──
var pill = document.createElement('div');
pill.id = 'dupcheck-pill';


// All styles inline with !important so WALLE CSS cannot override
var PILL_BASE = [
 'position:fixed','bottom:20px','right:20px',
 'z-index:2147483647',
 'display:none',
 'align-items:center','gap:8px',
 'background:linear-gradient(135deg,#3d3df5,#5b3de8)',
 'border-radius:28px','padding:8px 14px 8px 10px',
 'box-shadow:0 4px 20px rgba(61,61,245,.5)',
 'cursor:pointer',
 'font-family:Segoe UI,system-ui,sans-serif',
 'font-size:12px','font-weight:700','color:#fff',
 'border:none','outline:none',
 'user-select:none','-webkit-user-select:none',
 'pointer-events:auto'
].join('!important;')+'!important';


pill.setAttribute('style', PILL_BASE);


pill.innerHTML =
 '<span style="background:#ffcc00;width:22px;height:22px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;">⚡</span>'+
 '<span style="color:#fff;font-weight:700;font-size:12px;">DupCheck Evaluator</span>'+
 '<span id="dupcheck-badge" style="background:rgba(255,255,255,.25);border-radius:10px;padding:2px 8px;font-size:10px;font-weight:700;color:#fff;margin-left:2px;">—</span>';


document.documentElement.appendChild(pill);


// Hover effect via JS since we can't use CSS for external element
pill.addEventListener('mouseover', function(){ pill.style.setProperty('transform','scale(1.05)','important'); });
pill.addEventListener('mouseout',  function(){ pill.style.setProperty('transform','scale(1)','important'); });


var _minimized   = false;
var _diffCount   = 0;
var _panelWidth  = 360; // auto-adjusted based on GTIN count
var _analyzed    = false; // declared here so keyboard shortcut can use it

var _translateEnabled = false;
var _originalBodyHTML = '';

async function toggleTranslate() {
  _translateEnabled = !_translateEnabled;
  var btn = shadow.getElementById('translatebtn');
  btn.style.background = _translateEnabled ? '#2ecc71' : 'rgba(255,255,255,.15)';
  var bodyEl = shadow.getElementById('body');
  
  if (_translateEnabled) {
    _originalBodyHTML = bodyEl.innerHTML;
    var scanCard = document.createElement('div');
    scanCard.className = 'scan-card';
    scanCard.style.marginTop = '10px';
    scanCard.innerHTML = '<div class="scan-txt">Translating to English...</div>';
    bodyEl.appendChild(scanCard);
    
    var walk = document.createTreeWalker(bodyEl, NodeFilter.SHOW_TEXT, null, false);
    var nodes = [];
    var n;
    while(n = walk.nextNode()) {
      var t = n.nodeValue;
      if (t.trim().length > 0 && !/^[\d\s\.,;:!@#\$%\^&\*\(\)\-_\+=\[\]\{\}\|\\<>\?\/]+$/.test(t)) {
        nodes.push({node: n, text: t});
      }
    }
    
    for(var i=0; i<nodes.length; i++) {
      try {
        var url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q=' + encodeURIComponent(nodes[i].text);
        var res = await fetch(url);
        var data = await res.json();
        if(data && data[0]) {
           nodes[i].node.nodeValue = data[0].map(function(item){return item[0];}).join('');
        }
      } catch(e) {}
    }
    if (scanCard.parentNode) scanCard.parentNode.removeChild(scanCard);
  } else {
    if (_originalBodyHTML) {
      bodyEl.innerHTML = _originalBodyHTML;
    }
  }
}


function openPanel(){
 _minimized = false;
 wrap.classList.add('open');
 var w = _panelWidth || 360;
 wrap.style.setProperty('--panel-w', w+'px');
 host.style.setProperty('width', w+'px','important');
 host.style.setProperty('pointer-events','auto','important');
 pill.style.setProperty('display','none','important');
}


function minimizePanel(){
 _minimized = true;
 wrap.classList.remove('open');
 // Wait for slide-out animation then collapse width to 0
 setTimeout(function(){
   host.style.setProperty('width','0','important');
   host.style.setProperty('pointer-events','none','important');
 }, 320); // matches transition duration
 // Show pill with flex
 pill.setAttribute('style', PILL_BASE.replace('display:none','display:flex'));
 // Update badge
 var badge = document.getElementById('dupcheck-badge');
 if(badge) badge.textContent = _diffCount > 0 ? _diffCount+' diff'+ (_diffCount>1?'s':'') : '✓ done';
}


pill.addEventListener('click', openPanel);
shadow.getElementById('minbtn').onclick    = minimizePanel;
shadow.getElementById('translatebtn').onclick = toggleTranslate;
shadow.getElementById('rerun').onclick     = function(){ runAnalysis(true); };
shadow.getElementById('analyzebtn').onclick= function(){ runAnalysis(false); };
window.__prajnaShow = function(){ openPanel(); runAnalysis(false); };


// ── Keyboard shortcuts ───────────────────────────────────────────
// M = minimize / maximize panel
// N = analyze this page
document.addEventListener('keydown', function(e){
 var tag = (document.activeElement||{}).tagName||'';
 if(tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT') return;
 if(e.ctrlKey||e.altKey||e.metaKey) return;


 // M — toggle panel
 if(e.key==='m'||e.key==='M'){
   e.preventDefault();
   if(_minimized){ openPanel(); } else { minimizePanel(); }
 }


 // N — analyze page (opens panel if minimized, re-runs analysis)
 if(e.key==='n'||e.key==='N'){
   e.preventDefault();
   _analyzed = false; // allow re-analysis
   openPanel();
   runAnalysis(false);
 }
}, true);


// ═══ HELPERS ═══════════════════════════════════════════════════
function norm(s){ return (s||'').toLowerCase().replace(/[^\w\s]/g,' ').replace(/\s+/g,' ').trim(); }
function toks(s){ return norm(s).split(' ').filter(Boolean); }
function sim(a,b){
 var ta=new Set(toks(a)),tb=new Set(toks(b));
 if(!ta.size&&!tb.size) return 1; if(!ta.size||!tb.size) return 0;
 var c=0; ta.forEach(function(t){ if(tb.has(t)) c++; });
 return c/Math.max(ta.size,tb.size);
}
function trunc(s,n){ s=s||''; return s.length>n?s.slice(0,n)+'…':s; }
function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }


// ═══ SKIP / KEY LISTS ══════════════════════════════════════════
var SKIP_LABELS = [
 'action','reason codes','grouping','brand','product id','item id','item number',
 'upc','walmart item','seller','supplier','vendor','created','updated','sku',
 'cluster',
 'defects','content audit report','image validation','item tracker','copy creation',
 'file status','report an issue','provide feedback','request access','show null data',
 'viewing','select cluster','select grouping','hs-v',
 'variant group id','variant attribute names','product net content parent',
 'product net content','flotation tire','electric vehicle tire','is run flat',
 'abstract product id','manufacturer part number','is prop 65','is resizable',
 'personal relationship','inscription','small parts warning code'
 // NOTE: 'has written warranty' REMOVED — warranty IS relevant per agent feedback
 // NOTE: 'product type' NOT skipped — needed for Rings vs Engagement Rings diffs
];
var KEY_FIELDS = [
 'color','colour','size','flavor','flavour','scent','material',
 'count per pack','count','pack','capacity','volume','wattage',
 'configuration','pattern','style','format','edition','model','platform',
 'clothing size','shoe size','ring size','weight','finish','thread count',
 'resolution','width','length','height','type','power',
 'compatible','compatibility','tire size','tire type','construction type',
 'sidewall style','vehicle type','season','load index','speed rating',
 'wheel diameter','multipack quantity','total count',
 // Jewelry
 'diamond cut','diamond color','carats','carat','gemstone','metal type',
 'metal purity','karat','ring style','number of diamonds','number of gemstones',
 'gemstone type','jewelry setting','shape',
 // Electronics
 'processor speed','processor brand','processor core','ram memory','hard drive',
 'wireless technology','operating system','gpu','graphics','storage',
 // Clothing
 'clothing neck style','clothing fit','clothing top style','pant leg','pant rise',
 'pant style','clothing occasion','sleeve length','clothing style',
 'clothing size group','upper body strap','fabric content',
 // General
 'warranty','has written warranty','assembled product','processor type',
 'input output','data storage'
];
function shouldSkip(k){
 var kl=(k||'').toLowerCase().trim();
 if(kl.length<3) return true;
 if(/^\d+$/.test(kl)) return true;
 if(kl.indexOf('http')>=0) return true;
 return SKIP_LABELS.some(function(s){ return kl===s||kl.indexOf(s)>=0; });
}
function isKey(k){
 var kl=k.toLowerCase();
 return KEY_FIELDS.some(function(v){ return kl.indexOf(v)>=0; });
}
function cleanVal(s){
 if(!s) return '';
 s=s.replace(/[\r\n\t]+/g,' ').replace(/\s{2,}/g,' ').trim();
 // Normalize × to x for dimension comparisons
 s=s.replace(/×/g,'x');
 if(s.indexOf('|')>=0){
   var p=s.split('|').map(function(x){return x.trim();}).filter(Boolean);
   s=p.filter(function(x,i){return p.indexOf(x)===i;}).join(', ');
 }
 if(s.length>400) return '';
 return s;
}
// Size alias normalization — maps extended XL labels to canonical form
// Fixes: "5XL" === "XXXXXL", "4XL" === "XXXXL", etc.
function normSize(s){
 if(!s) return '';
 var t=(s||'').toUpperCase().replace(/[^A-Z0-9\-]/g,'').trim();
 var aliases=[
   [/^(XXXXXL|5XLARGE|5XL|5X)$/,'5XL'],
   [/^(XXXXL|4XLARGE|4XL|4X)$/,'4XL'],
   [/^(XXXL|3XLARGE|3XL|3X)$/,'3XL'],
   [/^(XXL|2XLARGE|2XL|2X)$/,'2XL'],
   [/^(XXS|2XSMALL|2XS)$/,'2XS'],
   [/^(XL|XLARGE|EXTRA-?LARGE)$/,'XL'],
   [/^(XS|XSMALL|EXTRA-?SMALL)$/,'XS'],
 ];
 for(var i=0;i<aliases.length;i++) if(aliases[i][0].test(t)) return aliases[i][1];
 return t;
}


function meaningful(v1,v2,fieldKey){
 var c1=cleanVal(v1),c2=cleanVal(v2);
 if(!c1&&!c2) return false;
 // FIX(2025-06-a): size-alias normalization before comparison
 // "XXXXXL" vs "5XL" are the same — should NOT be flagged as different
 if(fieldKey && fieldKey.toLowerCase().indexOf('size')>=0){
   if(normSize(c1)===normSize(c2)) return false;
 }
 if(norm(c1)===norm(c2)) return false;
 if(!c1||!c2) return true;
 // FIX(2025-06-b): numeric-token rule — any differing 3+ digit number is always significant
 // Catches product ID differences (Workstation 1100682 vs 1100216)
 // AND year-range differences in title (2008-2011 vs 2012-2022 → tokens 2008,2011 vs 2012,2022)
 var nums1=norm(c1).split(' ').filter(function(t){return /^\d{3,}$/.test(t);}).sort();
 var nums2=norm(c2).split(' ').filter(function(t){return /^\d{3,}$/.test(t);}).sort();
 if(nums1.join(',')!==nums2.join(',')) return true;
 // IMPROVEMENT 4: cross-unit equivalence — "3 ft" and "36 in" are the same
 var equiv=measurementsEquivalent(c1,c2);
 if(equiv===true) return false;
 var s=sim(c1,c2);
 // For critical jewelry/spec fields — use strict 0.5 threshold
 // "Round Cut" vs "Round Brilliant Cut" should be flagged (sim ~0.6)
 if(fieldKey){
   var kl=fieldKey.toLowerCase();
   var isSpec=kl.indexOf('cut')>=0||kl.indexOf('speed')>=0||kl.indexOf('purity')>=0||
              kl.indexOf('carat')>=0||kl.indexOf('storage')>=0||kl.indexOf('ram')>=0||
              kl.indexOf('processor')>=0||kl.indexOf('warranty')>=0||kl.indexOf('size')>=0||
              kl.indexOf('neck')>=0||kl.indexOf('leg')>=0||kl.indexOf('fit')>=0;
   if(isSpec) return s<0.85; // more lenient threshold catches near-matches like Round vs Round Brilliant
 }
 return s<0.7;
}


// IMPROVEMENT 2: Boilerplate stripping — removes common Walmart seller boilerplate before
// computing similarity, so spec differences buried in templated text are surfaced
var BOILERPLATE_PATTERNS=[
 // Bracket-labeled sections (e.g. "[WHY FROM US] ...text until next bracket or 800 chars")
 // Stops at next [ to avoid eating spec lines that come after boilerplate sections
 /\[[A-Z][^\]]{3,60}\](?:(?!\[)[\s\S]){0,800}/g,
 /\[?\s*(?:why choose us|why from us|satisfaction guaranteed|your satisfaction is our promise)[^\[\n]{0,600}/gi,
 /\[?\s*(?:perfect gift|ideal for gift|the ideal gift)[^\[\n]{0,400}/gi,
 /\[?\s*direct from manufacturer[^\[\n]{0,300}/gi,
 /we stand behind every piece[^\[\n]{0,300}/gi,
 /if you(?:'re| are) not (?:completely |fully )?satisfied[^\[\n]{0,200}/gi,
 /fast shipping[^\[\n]{0,100}/gi,
];
function stripBoilerplate(text){
 if(!text) return '';
 var t=text;
 BOILERPLATE_PATTERNS.forEach(function(p){ t=t.replace(p,' '); });
 return t.replace(/\s+/g,' ').trim();
}


// Smart description diff — checks both raw AND boilerplate-stripped versions
function meaningfulDesc(v1,v2){
 var c1=cleanVal(v1),c2=cleanVal(v2);
 if(!c1&&!c2) return false;
 if(norm(c1)===norm(c2)) return false;
 if(!c1||!c2) return true;
 var s=sim(c1,c2);
 if(s<0.95) return true;
 // Even if raw similarity is high, check stripped versions
 // Descriptions sharing 95%+ boilerplate can still have meaningful spec differences
 var s1=stripBoilerplate(c1), s2=stripBoilerplate(c2);
 if(!s1&&!s2) return false;
 if(norm(s1)===norm(s2)) return false;
 return sim(s1,s2)<0.88;
}


// Extract key numbers/specs from a string for smart comparison
function extractSpecs(s){
 var specs={};
 // Numbers with units
 var re=/(\d+(?:\.\d+)?)\s*(v|w|kg|g|lb|oz|cm|mm|m|ft|in|inch|ml|l|pack|pcs|count|thread|tc)/gi;
 var m;
 while((m=re.exec(s))!==null) specs[m[2].toLowerCase()]=(specs[m[2].toLowerCase()]||[]). concat(parseFloat(m[1]));
 return specs;
}


// ═══ CORE EXTRACTOR — handles 2 to N GTINs ═══════════════════════
// WALLE React DOM: key-row divs, stick-attributes label, group-gtin-column-cell values
function makeProduct(idx){
 return {gtin:'GTIN#'+(idx+1),name:'',description:'',img1:'',img2:'',
         imgs_main:[],imgs_sec:[],attrs:{}};
}


function clickReadMore(){
 var allLinks = document.querySelectorAll('a,button,span,[class*="read-more"],[class*="readmore"]');
 var clicked = 0;
 for(var i=0;i<allLinks.length;i++){
   var el=allLinks[i];
   var txt=(el.innerText||el.textContent||'').trim().toLowerCase();
   if(txt==='read more'||txt==='show more'){
     try{ el.click(); clicked++; }catch(e){}
   }
 }
 return clicked;
}


// IMPROVEMENT 1: Async read-more — waits for React DOM to settle after clicking
// Fixes intermittent blank/truncated descriptions caused by React batched state updates
function waitForReadMore(cb){
 var clicked = clickReadMore();
 if(!clicked) return cb();
 var timer;
 var obs = new MutationObserver(function(){
   clearTimeout(timer);
   // Wait 150ms of DOM silence before proceeding
   timer = setTimeout(function(){ obs.disconnect(); cb(); }, 150);
 });
 obs.observe(document.body,{childList:true,subtree:true,characterData:true});
 // Hard timeout: never wait more than 2.5s regardless
 setTimeout(function(){ obs.disconnect(); cb(); }, 2500);
}


// Parse bullet-point description text into structured key-value pairs
// e.g. "STONE COLOR: D/VVS1" → {key:'STONE COLOR', val:'D/VVS1'}
function parseDescBullets(text){
 if(!text) return {};
 // FIX(2025-06): pre-split inline field patterns so single-line descriptions parse correctly
 // Handles "STONE COLOR: D/VVS1 METAL: 14K" and "Season:Spring Gender: Men Material:Polyester"
 // Step 1 — ALL-CAPS keys: "STONE COLOR: " "METAL: " "SHIPPING: "
 text = text.replace(/(\s+)([A-Z]{2,}(?:[\s\/][A-Z]+){0,5}\s*:(?=\s*\S))/g, '\n$2');
 // Step 2 — Title-Case single/double word keys: "Season:" "Material:" "What you get:"
 text = text.replace(/(\s)([A-Z][a-zA-Z]{1,24}(?:\s[a-zA-Z]+){0,2}\s*:)(?=\s*[^\s])/g, '\n$2');
 var pairs = {};
 var lines = text.split('\n');
 for(var li=0;li<lines.length;li++){
   var line = lines[li].trim();
   if(!line) continue;
   // IMPROVEMENT 3: skip size-chart lines (3+ measurements + body-part keywords)
   var measureCount=(line.match(/\d+(?:\.\d+)?\s*(?:cm|mm|in|inch|inches|\'\')\b/gi)||[]).length;
   var hasSizeKw=/\b(bust|waist|hip|sleeve|inseam|chest|thigh|shoulder|pants length)\b/i.test(line);
   if(measureCount>=3&&hasSizeKw) continue;
   // Strip leading bullet chars (•, -, *, unicode bullets)
   line = line.replace(/^[\u2022\u2023\u25E6\uff65\-\*]\s*/,'');
   var k=null, v=null;


   // Pattern 1: 【KEY】:value or 【KEY】：value  (Japanese/Chinese brackets — very common in Walmart listings)
   var m1 = line.match(/^[\u3010\[](.+?)[\u3011\]]\s*[\uff1a:]\s*(.+)$/);
   if(m1){ k=m1[1].trim(); v=m1[2].trim(); }


   // Pattern 2: KEY: value or KEY：value (any case, 2-60 char key)
   if(!k){
     var m2 = line.match(/^([A-Za-z][A-Za-z0-9\s\(\)\/\-\_\.]{1,58})\s*[\uff1a:]\s*(.+)$/);
     if(m2){ k=m2[1].trim(); v=m2[2].trim(); }
   }


   if(k && v && k.length>=2 && k.length<=60 && v.length>=1 && v.length<=500){
     var kn = k.toUpperCase().trim();
     // Skip keys that are clearly not spec fields
     if(/^[A-Z0-9\s\(\)\/\-\_\.]+$/.test(kn)){
       pairs[kn] = v;
     }
   }
 }
 return pairs;
}


function compareDescBullets(desc1, desc2){
 var b1 = parseDescBullets(desc1);
 var b2 = parseDescBullets(desc2);
 var diffs = [];
 var seen = {}, allKeys = [];
 Object.keys(b1).forEach(function(k){ if(!seen[k]){seen[k]=1;allKeys.push(k);} });
 Object.keys(b2).forEach(function(k){ if(!seen[k]){seen[k]=1;allKeys.push(k);} });
 allKeys.forEach(function(k){
   var v1 = b1[k]||'', v2 = b2[k]||'';
   if(!v1&&!v2) return;
   if(norm(v1)===norm(v2)) return;
   diffs.push({field:'Desc: '+k, v1:v1||'—', v2:v2||'—'});
 });
 return diffs;
}


function extractProducts(){
 // Note: read-more expansion is handled BEFORE this call via waitForReadMore()
 // Do NOT call clickReadMore() here — it would re-click already-expanded sections


 // ── Strategy 1: WALLE class-based selectors ───────────────────
 var keyRows = document.querySelectorAll('[class*="key-row"]');


 if(keyRows.length > 0){
   // Detect how many GTIN columns exist from first row with value cells
   var numGTINs = 0;
   for(var r=0;r<keyRows.length;r++){
     var cells = keyRows[r].querySelectorAll('[class*="group-gtin-column-cell"]:not([class*="stick"])');
     if(cells.length > numGTINs) numGTINs = cells.length;
     if(numGTINs >= 10) break; // cap
   }
   if(!numGTINs) numGTINs = 2; // fallback


   // Build product array for N GTINs
   var prods = [];
   for(var i=0;i<numGTINs;i++) prods.push(makeProduct(i));


   var getImgs = function(cell, isMainImage){
     var srcs=[];
    
     // 1. Extract strictly from the variant's table cell
     if (cell) {
       var allNodes = cell.querySelectorAll('*');
       for(var ix=0; ix<allNodes.length; ix++) {
           var n = allNodes[ix];
           var s = '';
           if (n.tagName === 'IMG') {
               s = n.getAttribute('data-src') || n.getAttribute('data-original') || n.src || '';
           } else if (n.tagName === 'SOURCE') {
               s = n.srcset || '';
           } else if (n.style && n.style.backgroundImage) {
               var m = n.style.backgroundImage.match(/url\(['"]?(.*?)['"]?\)/);
               if (m) s = m[1];
           }
          
           if(s) {
               var parts = s.split(',')[0].split(' ')[0];
               if (parts && parts.indexOf('data:')<0 && srcs.indexOf(parts)<0) {
                   srcs.push(parts);
               }
           }
       }
      
       // Regex HTML for ANY URL if empty
       if(srcs.length===0){
         var html=cell.innerHTML||'';
         var m=html.match(/https?:\/\/[^"'\s<>]+?\.(?:jpg|jpeg|png|webp)/i);
         if(m) srcs.push(m[0]);
       }
     }
     return srcs;
   };


   for(var r=0;r<keyRows.length;r++){
     var row=keyRows[r];
     var labelEl=row.querySelector('[class*="stick-attributes"]');
     if(!labelEl) continue;
     var label=labelEl.innerText.trim();
     var ll=(label||'').toLowerCase();
    
     // Bypass shouldSkip if this is an image row so we can extract the images
     if(!label||(ll.indexOf('image')<0 && shouldSkip(label))) continue;


     var valCells=row.querySelectorAll('[class*="group-gtin-column-cell"]:not([class*="stick"])');
     if(!valCells.length) valCells=row.querySelectorAll('[class*="column"]');
     if(!valCells.length) {
        // Generic fallback: grab any div that isn't the label itself and has some text
        var allDivs = Array.from(row.querySelectorAll('div')).filter(function(d){ return d !== labelEl && d.innerText.trim().length > 0; });
        if(allDivs.length > 0) valCells = allDivs;
     }


     // Image rows
     if(ll.indexOf('image')>=0){
       var isMain=ll.indexOf('secondary')<0&&ll.indexOf('main')>=0;
       var isSec=ll.indexOf('secondary')>=0;
       if(isMain||isSec){
         for(var i=0;i<prods.length;i++){
           var srcs=getImgs(valCells[i], isMain);
           console.log(`Extracted images for product ${i+1} (${isMain ? 'main' : 'secondary'}):`, srcs);
           if(isMain){ prods[i].imgs_main=srcs; if(srcs[0]) prods[i].img1=srcs[0]; }
           if(isSec){  prods[i].imgs_sec=srcs;  if(srcs[0]) prods[i].img2=srcs[0]; }
         }
       }
       continue;
     }


     // Regular attribute
     var vals=[];
     for(var i=0;i<numGTINs;i++){
       vals.push(valCells[i] ? cleanVal(valCells[i].innerText.trim()) : '');
     }
    
     console.log("🤖 DupCheck Debug: ROW | Label:", label, "| Values:", vals);


     if(vals.every(function(v){return !v;})) continue;


     for(var i=0;i<prods.length;i++){
       var v=vals[i]||'';
       if(ll==='gtin'){ if(v&&v!==label) prods[i].gtin=v; }
       else if(ll.indexOf('product name')>=0||ll.indexOf('item name')>=0) prods[i].name=v;
       else if(ll.indexOf('short desc')>=0||ll.indexOf('long desc')>=0||ll.indexOf('description')>=0){
         // Append both short and long desc for maximum coverage
         if(prods[i].description && v) prods[i].description += ' ' + v;
         else if(v) prods[i].description = v;
       }
       else prods[i].attrs[label]=v;
     }
   }


   // (Harvested image fallback removed to stabilize caching)


   // Brute force fallback for descriptions if they were missed (often outside key-row tables)
   for(var i=0;i<prods.length;i++) {
       if (!prods[i].description) {
           var allTextDivs = document.querySelectorAll('div, span, p, h2, h3, h4');
           var descText = '';
           for(var j=0; j<allTextDivs.length; j++) {
               var text = (allTextDivs[j].innerText || '').trim().toLowerCase();
               if (text === 'product short description' || text === 'product long description' || text === 'description' || text === 'about this item') {
                   // Usually the next sibling or parent's next sibling contains the actual text
                   var next = allTextDivs[j].nextElementSibling;
                   if (next) descText += '\n' + next.innerText;
               }
           }
           if (descText.trim().length > 0) prods[i].description = descText.trim();
       }
   }


   var valid=prods.filter(function(p){return p.name||Object.keys(p.attrs).length>2;});
   if(valid.length>=2){
     // Smart deep image extraction via localStorage
     for(var vIdx=0; vIdx<valid.length; vIdx++){
       var p = valid[vIdx];
       var gtin = p.gtin;
       var pid = p.attrs['Product ID'] || p.attrs['product id'] || '';
       if(gtin || pid) {
         var storedImgs = [];
         var regex = /https?:\/\/[^"'\s\\]+\.(?:jpg|jpeg|png|webp)/gi;
        
         var extractImgsFromNode = function(node) {
            var str = JSON.stringify(node);
            var matches = str.match(regex);
            if(matches) {
              for(var m=0; m<matches.length; m++){
                var url = matches[m].replace(/\\\//g, '/');
                if(storedImgs.indexOf(url) < 0) storedImgs.push(url);
              }
            }
         };


         var searchObj = function(obj) {
           if(!obj || typeof obj !== 'object') return;
           var str = JSON.stringify(obj);
           if ((!gtin || str.indexOf(gtin) < 0) && (!pid || str.indexOf(pid) < 0)) return;
           if (!str.match(regex)) return;
          
           if (Array.isArray(obj)) {
             for(var i=0; i<obj.length; i++) searchObj(obj[i]);
             return;
           }
          
           var childHasBoth = false;
           for(var key in obj) {
             if(!Object.prototype.hasOwnProperty.call(obj, key)) continue;
             var child = obj[key];
             if(typeof child === 'string' && (child.indexOf('{')===0 || child.indexOf('[')===0)) {
               try { child = JSON.parse(child); } catch(e){}
             }
             if(child && typeof child === 'object') {
                var childStr = JSON.stringify(child);
                var hasId = (gtin && childStr.indexOf(gtin) >= 0) || (pid && childStr.indexOf(pid) >= 0);
                var hasImgs = !!childStr.match(regex);
                if (hasId && hasImgs) {
                   searchObj(child);
                   childHasBoth = true;
                }
             }
           }
           if (!childHasBoth) {
             extractImgsFromNode(obj);
           }
         };


         for(var k=0; k<localStorage.length; k++){
           var val = localStorage.getItem(localStorage.key(k));
           if(val && ((gtin && val.indexOf(gtin)>=0) || (pid && val.indexOf(pid)>=0))){
             try {
               var parsed = JSON.parse(val);
               searchObj(parsed);
             } catch(e) {}
           }
         }
        
         if(storedImgs.length > 0){
           for(var j=0; j<storedImgs.length; j++){
             var sImg = storedImgs[j];
             if(p.imgs_main.indexOf(sImg) < 0 && p.imgs_sec.indexOf(sImg) < 0){
               p.imgs_sec.push(sImg);
             }
           }
         }
         console.log(`Deep localStorage images for product ${vIdx+1}:`, p.imgs_sec);
       }
     }
     return valid.length===prods.length?prods:valid;
   }
 }


 // ── Strategy 2: generic div/tr rows ────────────────────────────
 var p1=makeProduct(0), p2=makeProduct(1);
 var allDivs=document.querySelectorAll('div,tr'), found=0;
 for(var i=0;i<allDivs.length;i++){
   var el=allDivs[i], ch=el.children;
   if(ch.length<3) continue;
   var labelTxt=ch[0].innerText?ch[0].innerText.trim():ch[0].textContent.trim();
   if(!labelTxt||labelTxt.length>80||labelTxt.length<2||shouldSkip(labelTxt)) continue;
   var v1txt=ch[1].innerText?ch[1].innerText.trim():ch[1].textContent.trim();
   var v2txt=ch[2].innerText?ch[2].innerText.trim():ch[2].textContent.trim();
   if(!v1txt||labelTxt===v1txt) continue;
   var v1=cleanVal(v1txt), v2=cleanVal(v2txt), ll=labelTxt.toLowerCase();
   if(ll==='gtin'){if(v1)p1.gtin=v1;if(v2)p2.gtin=v2;found++;}
   else if(ll.indexOf('product name')>=0||ll.indexOf('item name')>=0){p1.name=v1;p2.name=v2;found++;}
   else if(ll.indexOf('short desc')>=0||ll.indexOf('long desc')>=0){p1.description=v1;p2.description=v2;found++;}
   else if(!shouldSkip(labelTxt)){p1.attrs[labelTxt]=v1;p2.attrs[labelTxt]=v2;found++;}
 }
 if(found>2||p1.name) return [p1,p2];


 // ── Nothing worked — show debug ───────────────────────────────
 var dbg=[];
 dbg.push('key-row divs: '+document.querySelectorAll('[class*="key-row"]').length);
 dbg.push('table count: '+document.querySelectorAll('table').length);
 dbg.push('tr count: '+document.querySelectorAll('tr').length);
 dbg.push('td count: '+document.querySelectorAll('td').length);
 // Sample first few elements with "key" in class
 var keySample=[];
 var allEls=document.querySelectorAll('*');
 var keyCount=0;
 for(var i=0;i<allEls.length&&keyCount<5;i++){
   var cls=(allEls[i].className||'').toString();
   if(cls.indexOf('key')>=0||cls.indexOf('row')>=0||cls.indexOf('attr')>=0){
     keySample.push(allEls[i].tagName+'.'+cls.slice(0,40)+': '+allEls[i].textContent.trim().slice(0,30));
     keyCount++;
   }
 }
 dbg.push('Classes with key/row/attr:<br>'+keySample.join('<br>'));
 showBody('<div class="err">⚠ Could not read WALLE data.<br><br>Debug:<br>'+dbg.join('<br>')+'</div>');
 return [];
}


// ═══ GTIN DETECTION ════════════════════════════════════════════
function hasGTINs(){
 // Check WALLE React DOM first (key-row divs)
 var keyRows = document.querySelectorAll('[class*="key-row"]');
 if(keyRows.length >= 3) return true;


 // Check for GTIN#1 / GTIN#2 text anywhere on page
 var body = document.body ? (document.body.innerText||document.body.textContent||'') : '';
 if(body.indexOf('GTIN#1')>=0 && body.indexOf('GTIN#2')>=0) return true;


 // Check for Product Name in any div with siblings
 var allDivs = document.querySelectorAll('div');
 for(var i=0;i<allDivs.length;i++){
   var ch = allDivs[i].children;
   if(ch.length>=3){
     var lbl=(ch[0].innerText||ch[0].textContent||'').trim().toLowerCase();
     if(lbl==='product name'||(lbl==='gtin'&&ch[1].textContent.trim().length>5)) return true;
   }
 }


 // Fallback: table-based
 var allTR=document.querySelectorAll('tr');
 for(var i=0;i<allTR.length;i++){
   var cells=allTR[i].querySelectorAll('td');
   if(cells.length<3) continue;
   var lbl=cells[0].textContent.trim().toLowerCase();
   if(lbl==='product name'||lbl==='gtin') return true;
 }
 return false;
}


// ═══ AUTO-WATCH — instant trigger in microseconds ══════════════
var _timer=null; // _analyzed declared above with panel vars


function triggerAnalysis(){
 if(_analyzed) return;
 _analyzed = true;
 clearInterval(_timer);
 if(_obs) _obs.disconnect();
 openPanel();
 runAnalysis(false);
}


// MutationObserver — fires instantly on DOM change
var _obs = new MutationObserver(function(){
 if(!_analyzed && hasGTINs()) triggerAnalysis();
});
_obs.observe(document.body, {childList:true, subtree:true, attributes:false});


// Also check immediately (page may already be loaded)
if(hasGTINs()){
 triggerAnalysis();
} else {
 // Fallback poll — fast 100ms in case MutationObserver misses it
 _timer = setInterval(function(){
   if(_analyzed){ clearInterval(_timer); return; }
   if(hasGTINs()) triggerAnalysis();
 }, 100);
 // After 30s show no-GTIN state
 setTimeout(function(){
   clearInterval(_timer);
   if(_obs) _obs.disconnect();
   if(!_analyzed){
     showBody('<div class="nogtin-card"><div class="nogtin-icon">🔍</div><div class="nogtin-title">No GTINs Found</div><div class="nogtin-sub">Open a WALLE comparison page, then click Analyze This Page.</div></div>');
     openPanel();
   }
 }, 30000);
}


// SPA URL change detector
var _lastUrl = window.location.href;
setInterval(function() {
  if (window.location.href !== _lastUrl) {
    _lastUrl = window.location.href;
    console.log("🤖 DupCheck AI: URL changed, resetting analysis state.");
    _analyzed = false;
    
    // Reset UI to waiting state
    showBody('<div class="scan-card"><div class="scan-bars"><div class="scan-bar"></div><div class="scan-bar"></div><div class="scan-bar"></div><div class="scan-bar"></div><div class="scan-bar"></div></div><div class="scan-txt">Waiting for WALLE…</div><div class="scan-sub">Auto-analyzes when table loads</div></div>');
    
    // Restart observer
    if(_obs) _obs.disconnect();
    _obs = new MutationObserver(function(){
      if(!_analyzed && hasGTINs()) triggerAnalysis();
    });
    _obs.observe(document.body, {childList:true, subtree:true, attributes:false});
    
    // Restart interval
    clearInterval(_timer);
    _timer = setInterval(function(){
      if(_analyzed){ clearInterval(_timer); return; }
      if(hasGTINs()) triggerAnalysis();
    }, 100);
  }
}, 500);

// ═══ CATEGORY + VERDICT ════════════════════════════════════════
var MANDATORY={
 books:['edition','format','isbn'],clothing:['size','color','colour','pattern'],
 footwear:['size','color','width'],electronics:['model','configuration','wattage','capacity'],
 food:['flavor','flavour','count','pack','size','weight'],rugs:['size','color','pattern'],
 bedding:['size','color','thread count'],furniture:['color','finish','configuration'],
 automotive:['tire size','size','model','type','construction','vehicle type'],
 toys:['color','size','count','pack','platform'],
 general:['size','color','type','model','count','weight','material']
};
var CAT_NAMES={books:'Books',clothing:'Clothing',footwear:'Footwear',electronics:'Electronics',
 food:'Food',rugs:'Rugs',bedding:'Bedding',furniture:'Furniture',
 automotive:'Automotive',toys:'Toys',general:'General'};


function detectCat(p1,p2){
 // IMPROVEMENT 5: check WALLE's own Product Type attribute first — it's authoritative
 var pt=((p1.attrs['Product Type']||p2.attrs['Product Type']||'')).toLowerCase();
 if(/tire|tyre|brake|rotor|automotive/.test(pt)) return 'automotive';
 if(/shoe|boot|sandal|sneaker|footwear|slipper/.test(pt)) return 'footwear';
 if(/\b(?:book|novel|textbook)\b/.test(pt)) return 'books';
 if(/laptop|phone|tablet|television|monitor|computer|camera/.test(pt)||/computer replacement/i.test(pt)) return 'electronics';
 if(/food|beverage|supplement|snack|coffee/.test(pt)) return 'food';
 if(/\b(?:rug|carpet)\b/.test(pt)) return 'rugs';
 if(/bedding|mattress|comforter|duvet/.test(pt)) return 'bedding';
 if(/furniture|sofa|chair|table/.test(pt)) return 'furniture';
 if(/\btoy|\bgame/.test(pt)) return 'toys';
 if(/apparel|clothing|shirt|pant|dress|jacket|pajama|sleepwear/.test(pt)) return 'clothing';
 if(/ring|necklace|bracelet|earring|jewelry|jewellery|engagement|wedding/.test(pt)) return 'jewelry';
 if(/picture frame|frame/.test(pt)) return 'general';
 // Fallback: keyword scan of all product text
 var t=(p1.name+' '+p1.description+' '+Object.values(p1.attrs).join(' ')+
        p2.name+' '+p2.description+' '+Object.values(p2.attrs).join(' ')).toLowerCase();
 if(/\b(tire|tyre|vehicle|motor|wheel)\b/.test(t)) return 'automotive';
 if(/shoe|boot|sandal|sneaker|footwear|slipper/.test(t)) return 'footwear';
 if(/\b(book|novel|textbook|paperback|isbn)\b/.test(t)) return 'books';
 if(/\b(laptop|phone|tablet|television|monitor|computer|camera|electronics)\b/.test(t)) return 'electronics';
 if(/\b(food|snack|drink|beverage|cereal|coffee|supplement)\b/.test(t)) return 'food';
 if(/\b(rug|carpet|runner)\b/.test(t)) return 'rugs';
 if(/\b(bedding|comforter|duvet|mattress)\b/.test(t)) return 'bedding';
 if(/\b(sofa|couch|chair|table|desk|furniture)\b/.test(t)) return 'furniture';
 if(/\b(toy|game|puzzle|doll|disc|frisbee|flying|kids|play)\b/.test(t)) return 'toys';
 if(/\b(ring|necklace|bracelet|earring|jewelry|jewellery)\b/.test(t)) return 'jewelry';
 if(/shirt|pant|dress|jacket|jeans|sweater|clothing|apparel|pajama|sleepwear/.test(t)) return 'clothing';
 return 'general';
}
function computeVerdict(keyDiffs,nameSim,cat){
 var mnd=MANDATORY[cat]||MANDATORY.general;
 for(var i=0;i<keyDiffs.length;i++){
   var kl=keyDiffs[i].field.toLowerCase();
   if(mnd.some(function(m){return kl.indexOf(m)>=0;}))
     return {cls:'nd',txt:'NOT A DUPLICATE',
       reason:'"'+keyDiffs[i].field+'" differs — '+trunc(keyDiffs[i].v1,22)+' vs '+trunc(keyDiffs[i].v2,22),
       rule:'SOP: Key variant attribute difference'};
 }
 if(keyDiffs.length>=2) return {cls:'nd',txt:'NOT A DUPLICATE',
   reason:keyDiffs.map(function(d){return d.field;}).join(', ')+' differ',rule:'SOP: Multiple variant differences'};
 if(keyDiffs.length===1&&/color|colour|finish|pattern/.test(keyDiffs[0].field.toLowerCase()))
   return {cls:'nd',txt:'NOT A DUPLICATE',reason:'"'+keyDiffs[0].field+'" — distinct color/finish',rule:'SOP: Color/finish = distinct swatches'};
 if(nameSim>=0.8&&keyDiffs.length===0) return {cls:'dup',txt:'DUPLICATE',
   reason:'Name '+Math.round(nameSim*100)+'% match · No variant differences',rule:'SOP: No distinguishing differences'};
 if(nameSim>=0.5&&keyDiffs.length===0) return {cls:'dup',txt:'DUPLICATE',
   reason:'Name '+Math.round(nameSim*100)+'% · No variant differences found',rule:'SOP: Same product listings'};
 return {cls:'nsbd',txt:'NOT SURE – BAD DATA',
   reason:'Name '+Math.round(nameSim*100)+'% · '+keyDiffs.length+' key diff(s)',rule:'Manual review required'};
}


// ═══ VERTICAL DISCREPANCY ENGINE ════════════════════════════════
// Catches inconsistencies WITHIN a single product between:
// title/name vs attributes (e.g. "220V" in name but Voltage attr = "230V")


function checkVertical(prod) { return []; }


// ═══ IMAGE SET COMPARISON ══════════════════════════════════════
// Compare two arrays of image URLs — normalize (strip query params, lowercase)
function normImgUrl(url){
 if(!url) return '';
 try{
   var u=url.split('?')[0].split('#')[0].toLowerCase();
   // Extract just the filename portion for robust comparison
   var parts=u.split('/');
   return parts[parts.length-1]||u;
 }catch(e){ return url.toLowerCase(); }
}
function compareImgSets(set1, set2){
 if(!set1.length&&!set2.length) return null; // no images at all
 if(!set1.length||!set2.length) return false; // one side missing
 // Compare normalized filenames
 var n1=set1.map(normImgUrl), n2=set2.map(normImgUrl);
 // Check if primary image matches
 if(n1[0]!==n2[0]) return false;
 // All match
 return true;
}


// ═══ WARNING BUILDER ════════════════════════════════════════════
// Generates warnings when products look completely identical
function buildWarnings(keyDiffs,otherDiffs,mainSame,secSame,p1,p2,vert1,vert2){
 var warnings=[];
 var totalDiffs=keyDiffs.length+otherDiffs.length;
 var vertCount=(vert1?vert1.length:0)+(vert2?vert2.length:0);


 // Warning: completely identical (no diffs at all)
 if(totalDiffs===0&&vertCount===0&&mainSame!==false&&secSame!==false){
   warnings.push({
     level:'high',
     title:'Products appear completely identical',
     items:[
       'No attribute differences found between GTINs',
       mainSame===true?'Main images are identical':'Main images not compared',
       secSame===true?'Secondary images are identical':'Secondary images not compared',
       'Consider marking as Duplicate'
     ]
   });
 }


 // Warning: images same but attributes differ
 if(mainSame===true&&secSame===true&&totalDiffs>0){
   warnings.push({
     level:'med',
     title:'Same images but '+totalDiffs+' attribute difference'+(totalDiffs>1?'s':''),
     items:['Both GTINs share identical product images','Attribute differences may indicate a data entry error or variant confusion']
   });
 }


 // Warning: images different but no attribute diffs
 if((mainSame===false||secSame===false)&&totalDiffs===0){
   warnings.push({
     level:'med',
     title:'Different images but no attribute differences',
     items:[
       mainSame===false?'Main images differ':'Main images match',
       secSame===false?'Secondary images differ':'Secondary images match',
       'Image difference may indicate packaging variant or photography issue'
     ]
   });
 }


 // Warning: Vertical discrepancies found
 if(vertCount>0){
   var msgs=[];
   if(vert1&&vert1.length) vert1.forEach(function(v){msgs.push(p1.gtin+': '+v.msg);});
   if(vert2&&vert2.length) vert2.forEach(function(v){msgs.push(p2.gtin+': '+v.msg);});
   warnings.push({
     level:'high',
     title:vertCount+' Vertical data inconsistenc'+(vertCount>1?'ies':'y') +' found',
     items:msgs
   });
 }


 return warnings;
}


// ═══ ANALYSIS ══════════════════════════════════════════════════
function getGTINLabel(p, i) {
  var id = '';
  if (p.gtin && p.gtin.indexOf('GTIN#') !== 0) id = p.gtin;
  else if (p.attrs && p.attrs['Product ID']) id = p.attrs['Product ID'];
  else if (p.attrs && p.attrs['product id']) id = p.attrs['product id'];
  else if (p.attrs && p.attrs['Item ID']) id = p.attrs['Item ID'];
  else if (p.attrs && p.attrs['item id']) id = p.attrs['item id'];
  return 'GTIN#' + (i+1) + (id ? ' (' + id + ')' : '');
}

function showBody(html){ 
  shadow.getElementById('body').innerHTML=html; 
  if (_translateEnabled) {
    _translateEnabled = false;
    if(shadow.getElementById('translatebtn')) {
        shadow.getElementById('translatebtn').style.background = 'rgba(255,255,255,.15)';
    }
  }
}
function setScanning(){
 showBody('<div class="scan-card"><div class="scan-bars"><div class="scan-bar"></div><div class="scan-bar"></div><div class="scan-bar"></div><div class="scan-bar"></div><div class="scan-bar"></div></div><div class="scan-txt">Analyzing…</div><div class="scan-sub">Reading comparison table</div></div>');
}
function runAnalysis(manual){
 _analyzed=true; setScanning();
 // IMPROVEMENT 1: wait for React DOM to settle after expanding descriptions
 setTimeout(function(){
   waitForReadMore(async function(){
   try{
     var products=extractProducts();
     if(!products||products.length<2) return;


     // UPDATE UI to show AI vision is running
     var scanTxt = shadow.querySelector('.scan-txt');
     var scanSub = shadow.querySelector('.scan-sub');
     if(scanTxt) scanTxt.textContent = 'AI Vision Analysis...';
     if(scanSub) scanSub.textContent = 'Checking images against text attributes';


     // Call Backend API to run Gemini Batch Analysis (pass manual flag to bypass cache)
     var apiResult = await window.analyzeBatchWithGemini(products, manual === true);
    
     // Expand panel width based on number of products
     var n = products.length;
     _panelWidth = Math.min(600, 360 + (n-2)*120);
     wrap.style.setProperty('--panel-w', _panelWidth+'px');
     host.style.setProperty('width', _panelWidth+'px','important');


     if (!apiResult) {
        showBody('<div class="err">⚠ AI Batch Analysis Failed. Check console.</div>');
        return;
     }
    
     var badDataCount = (apiResult.vertical_checks || []).filter(function(v){ return v.has_bad_data; }).length;
     var clusterCount = (apiResult.horizontal_clustering || []).length;
    
     var html = '<div class="status-line">'+n+' GTINs Analyzed by Gemini Vision AI</div>';
    
     var catKey = detectCat(products[0], products[1] || products[0]);
     var catName = CAT_NAMES[catKey] || 'General';
    
     // 1. Top Summary Pills
     html += '<div class="cat-row" style="animation:slideUp .4s .05s ease both;">';
     html += '<div class="cat-box"><div class="cat-lbl">CATEGORY</div><div class="cat-val" style="text-transform:uppercase;">'+catName+'</div></div>';
     html += '<div class="cat-box"><div class="cat-lbl">GTINS</div><div class="cat-val">'+n+'</div></div>';
     html += '<div class="cat-box"><div class="cat-lbl">BAD DATA</div><div class="cat-val" style="color:'+(badDataCount>0?'#c0392b':'#15803d')+'">'+badDataCount+'</div></div>';
     html += '<div class="cat-box"><div class="cat-lbl">CLUSTERS</div><div class="cat-val" style="color:'+(clusterCount>1?'#c0392b':'#15803d')+'">'+clusterCount+'</div></div>';
     html += '</div>';


     // 1.5 Image Specs Extracted
     html += '<div class="diff-table" style="animation:slideUp .4s .06s ease both; margin-top: 12px;">';
     html += '<div class="diff-hdr" style="background:#eef2ff;border-color:#c7d2fe;color:#4f46e5">'+
        '🖼️ Image Specifications Extracted by AI'+
      '</div>';
     (apiResult.vertical_checks || []).forEach(function(v) {
         var specs = v.extracted_image_specs || 'None';
         var specColor = (specs.toLowerCase() === 'none') ? '#9ca3af' : '#4f46e5';
         html += '<div class="drow" style="flex-direction:column; align-items:stretch;">' +
            '<div class="dlbl" style="color:#374151;">' + esc(v.product_id) + '</div>' +
            '<div style="padding:4px 10px 8px; font-size:12px; font-weight:500; color:' + specColor + ';">' + esc(specs) + '</div>' +
            '</div>';
     });
     html += '</div>';


     // 2. Verdict / AI Result AT THE TOP
     if (apiResult.horizontal_clustering && apiResult.horizontal_clustering.length > 0) {
         if (clusterCount === 1 && badDataCount === 0) {
             html += '<div class="verdict-card dup" style="animation:slideUp .4s .08s ease both;"><div class="v-icon">✓</div><div class="v-txt">All ' + n + ' GTINs are identical</div><div class="v-reason">No bad data or clustering differences found by AI.</div></div>';
         } else {
            if (clusterCount > 1) {
                html += '<div class="verdict-card nd" style="animation:slideUp .4s .08s ease both;"><div class="v-icon">❌</div><div class="v-txt">NOT A DUPLICATE</div><div class="v-reason">AI separated these products into ' + clusterCount + ' different clusters.</div></div>';
            }
            html += '<div class="diff-table" style="animation:slideUp .4s .08s ease both">';
            html += '<div class="diff-hdr" style="background:#f0f4ff;border-color:#c5c8ff;color:#3d3df5">'+
               '🤖 Phase 2: AI Duplicate Clusters <span class="diff-badge" style="background:#3d3df5">'+clusterCount+'</span>'+
             '</div>';
            
             apiResult.horizontal_clustering.forEach(function(c) {
                html += '<div class="drow" style="flex-direction:column; align-items:stretch;">' +
                    '<div class="dlbl" style="color:#3d3df5;">' + esc(c.cluster_name) + '</div>' +
                    '<div style="padding:6px 10px 2px; font-size:11px; color:#333;"><b>Products:</b> ' + esc(c.product_ids.join(', ')) + '</div>' +
                    '<div style="padding:4px 10px 8px; font-size:11px; font-style:italic; color:#666;">' + esc(c.reason) + '</div>' +
                    '</div>';
             });
             html += '</div>';
         }
     }


     // 3. Phase 1 (Bad Data)
     var badData = apiResult.vertical_checks ? apiResult.vertical_checks.filter(function(v){ return v.has_bad_data; }) : [];
     if (badData.length > 0) {
       html+='<div class="diff-table" style="animation:slideUp .4s .1s ease both">'+
         '<div class="diff-hdr" style="background:#fdecea;border-color:#f5b7b7;color:#c0392b">'+
           '🔴 Phase 1: Bad Data Detected <span class="diff-badge" style="background:#c0392b">'+badData.length+'</span>'+
         '</div>';
       badData.forEach(function(v){
           if (v.mismatch_details && v.mismatch_details.length > 0) {
             v.mismatch_details.forEach(function(m) {
                html += '<div class="drow" style="flex-direction:column; align-items:stretch;">'+
                        '<div class="dlbl" style="color:#92400e; width:100%;">' + esc(v.product_id) + ' · ' + esc(m.field) + '</div>'+
                        '<div class="dvals">'+
                          '<div class="dval red"><b>Image:</b> ' + esc(m.imageValue) + '</div>'+
                          '<div class="dval red"><b>Attr:</b> ' + esc(m.textValue) + '</div>'+
                        '</div>'+
                        '<div style="padding:4px 10px 8px; font-size:10px; font-style:italic; color:#666;">'+esc(v.reason)+'</div>'+
                        '</div>';
             });
           } else {
                html += '<div class="drow" style="flex-direction:column; align-items:stretch;">'+
                        '<div class="dlbl" style="color:#92400e; width:100%;">' + esc(v.product_id) + '</div>'+
                        '<div style="padding:8px 10px; font-size:11px; color:#c0392b;">'+esc(v.reason)+'</div>'+
                        '</div>';
           }
       });
       html+='</div>';
     }


     // 4. Attribute Table
     var allAttrs = {};
     products.forEach(function(p) { Object.keys(p.attrs||{}).forEach(function(k){ allAttrs[k]=1; }); });
     var attrKeys = Object.keys(allAttrs);
    
     var sameAttrs = [];
     var diffAttrs = [];
    
     attrKeys.forEach(function(k) {
         var vals = products.map(function(p){ return p.attrs[k] || '—'; });
         var allSame = vals.every(function(v){ return v === vals[0]; });
         if(allSame) sameAttrs.push({key: k, val: vals[0]});
         else diffAttrs.push({key: k, vals: vals});
     });
    
     if(sameAttrs.length > 0) {
         html += '<div class="match-all" style="animation:slideUp .4s .15s ease both;">';
         html += '<div class="match-all-hdr">✓ MATCHING ACROSS ALL GTINS</div>';
         sameAttrs.forEach(function(attr) {
             html += '<div class="match-row"><div class="match-field">'+esc(attr.key)+'</div><div class="match-val">'+esc(attr.val)+'</div></div>';
         });
         html += '</div>';
     }
    
     if(diffAttrs.length > 0) {
         html += '<div class="diff-table" style="animation:slideUp .4s .15s ease both;">';
         html += '<div class="diff-hdr" style="background:#fdecea;color:#c0392b;border-bottom:1px solid #f5b7b7;">⚠ DIFFERING ATTRIBUTES</div>';
         html += '<div class="diff-col-hdr"><div>Attribute</div>';
         for(var i=0;i<n;i++) html += '<div>'+esc(getGTINLabel(products[i], i))+'</div>';
         html += '</div>';
         diffAttrs.forEach(function(attr) {
             html += '<div class="drow"><div class="dvals"><div class="dval" style="color:#c0392b;font-weight:700;">'+esc(attr.key)+'</div>';
             for(var i=0;i<n;i++) html += '<div class="dval">'+esc(attr.vals[i])+'</div>';
             html += '</div></div>';
         });
         html += '</div>';
     }


     // 5. Extracted Images
     html += '<div class="img-section" style="animation:slideUp .4s .2s ease both;"><div class="img-sec-hdr">Extracted Images</div><div class="multi-scroll"><div style="display:flex;gap:1px;background:#f0f0f0;">';
     products.forEach(function(p, i){
        html += '<div class="img-cell"><div class="img-lbl">'+esc(getGTINLabel(p, i))+'</div><div style="display:flex; flex-wrap:wrap; gap:4px; justify-content:center;">';
        var allImgs = [];
        if (p.imgs_main) allImgs.push.apply(allImgs, p.imgs_main);
        else if (p.img1) allImgs.push(p.img1);
        if (p.imgs_sec) allImgs.push.apply(allImgs, p.imgs_sec);
        else if (p.img2) allImgs.push(p.img2);
        if (p.imageUrls && allImgs.length === 0) allImgs.push.apply(allImgs, p.imageUrls);


        allImgs = allImgs.filter(function(item, pos) { return allImgs.indexOf(item) === pos; });
        if(allImgs.length > 0) {
            allImgs.forEach(function(src) {
                html += '<img src="'+esc(src)+'" onerror="this.style.display=\'none\'" style="width:40px; height:40px; object-fit:contain; border-radius:4px; border:1px solid #ddd;">';
            });
        } else {
            html += '<div style="font-size:8px;color:#aaa;padding:20px 0;">NO IMAGES</div>';
        }
        html += '</div></div>';
     });
     html += '</div></div></div>';


     // 6. Descriptions
     var allDescsSame = products.every(function(p) { return p.description === products[0].description; });
     if(allDescsSame) {
         html += '<div class="match-all" style="animation:slideUp .4s .25s ease both;">';
         html += '<div class="match-all-hdr">✓ MATCHING DESCRIPTION</div>';
         html += '<div style="font-size:10px; color:#444; max-height:100px; overflow-y:auto; line-height:1.4;">' + (esc(products[0].description) || '<i style="color:#ccc">Empty</i>') + '</div>';
         html += '</div>';
     } else {
         html += '<div class="diff-table" style="animation:slideUp .4s .25s ease both;">';
         html += '<div class="diff-hdr" style="background:#fdecea;color:#c0392b;border-bottom:1px solid #f5b7b7;">⚠ DIFFERING DESCRIPTIONS</div>';
         html += '<div class="diff-col-hdr">';
         for(var i=0;i<n;i++) html += '<div>'+esc(getGTINLabel(products[i], i))+'</div>';
         html += '</div>';
         html += '<div class="drow"><div class="dvals">';
         products.forEach(function(p, i) {
             html += '<div class="dval" style="font-size:10px; max-height:100px; overflow-y:auto; border-right:1px solid #eee; padding:6px; font-weight:normal;">' + (esc(p.description) || '<i style="color:#ccc">Empty</i>') + '</div>';
         });
         html += '</div></div></div>';
     }
    
     showBody(html);


   }catch(e){
     console.error(e);
     showBody('<div class="err">⚠ Error: '+esc(e.message)+'</div>');
   }
   }); // end waitForReadMore
 },manual?100:400);
}


} // end init()



