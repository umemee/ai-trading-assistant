// app.js ─ 실사용용 V5.4 전체 로직
(() =>{
/* ─────── 사용자 세팅 ─────── */
const CONFIG = {
  PW           : '2025',                 // 🔧 수정①
  ALPACA_KEY   : 'PKMM3D2Y4KLMQZFC9XJK',                         // 🔧 수정②
  ALPACA_SEC   : 'ciqIeRyOsPpQwxVIWnjTab05CGnlohkdSolFZmo1',
  GEMINI_KEY   : 'AIzaSyAHylP36yV4AHDlaf9GxQIWzSfU1jHIlDQ',                         // 🔧 수정③
  SHEET_ID     : '1TaSyGB-0LY678_-pqmXdrkycQNexauZBJ6fM9SCJXaE',                         // 🔧 수정④-a
  SHEET_APIKEY : 'AIzaSyDbvEEX2OgoWE7ForvvCsZSF3JgQX_cD-U'                          // 🔧 수정④-b
};
/* ─────── 전역 상태 ─────── */
let atoms=[], molecules=[], sidbRange='SIDB!A2:H', predRange='예측오답노트!A2:S';
let watch=[], predictions=[], scanTimer=null;
/* ─────── DOM 헬퍼 ─────── */
const $ = s => document.querySelector(s);
const $$= s => [...document.querySelectorAll(s)];
function toast(msg,type='green'){const t=$('#toast');t.textContent=msg;t.style.background=`#${type==='red'?'ef4444':type==='blue'?'3b82f6':'10b981'}`;t.classList.remove('hidden');t.classList.add('show');setTimeout(()=>t.classList.add('hidden'),2800);}
function log(txt){const l=$('#dash');l.insertAdjacentHTML('beforeend',`<p class="font-mono text-xs">${new Date().toLocaleTimeString()} | ${txt}</p>`);}
function switchSec(id){$$('.sec').forEach(s=>s.classList.remove('active'));$(`#${id}`).classList.add('active');
  $$('.nav').forEach(n=>n.classList.remove('active'));$(`.nav[data-sec=${id}]`).classList.add('active');}
/* ─────── 로그인 모달 ─────── */
$('#pw-btn').onclick=()=>{if($('#pw-input').value===CONFIG.PW){$('#pw-modal').classList.add('hidden');init();}else toast('비밀번호 오류','red');};
/* ─────── 네비게이션 클릭 ─────── */
$$('.nav').forEach(btn=>btn.onclick=e=>switchSec(e.target.dataset.sec));

/* ─────── 구글 시트 Fetch 유틸 ─────── */
async function gSheetRead(range){
  const url=`https://sheets.googleapis.com/v4/spreadsheets/${CONFIG.SHEET_ID}/values/${range}?key=${CONFIG.SHEET_APIKEY}`;
  const r=await fetch(url);if(!r.ok)throw'GS read';return (await r.json()).values||[];
}
async function gSheetAppend(range,row){
  const url=`https://sheets.googleapis.com/v4/spreadsheets/${CONFIG.SHEET_ID}/values/${range}:append?valueInputOption=RAW&key=${CONFIG.SHEET_APIKEY}`;
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({values:[row]})});
  if(!r.ok)throw'GS append';
}
/* ─────── DB 로드 (아톰/분자) ─────── */
async function loadLogicDB(){
  try{
    const atomRows=await gSheetRead('Atom_DB!A2:F');
    atoms=atomRows.map(r=>({id:r[0],name:r[1],cat:r[4]}));
    const molRows=await gSheetRead('분자 DB!A2:F');
    molecules=molRows.map(r=>({id:r[0],name:r[1],need:r[3]?.split(',').map(s=>s.trim())||[],thr:parseFloat(r[4])}));
    toast(`아톰 ${atoms.length} / 분자 ${molecules.length} 로드`);
    $('#dash').innerHTML=`<div class="grid grid-cols-4 gap-2 mb-3">
      <div class="card text-center"><div class="text-2xl font-bold">${atoms.length}</div><div>아톰</div></div>
      <div class="card text-center"><div class="text-2xl font-bold">${molecules.length}</div><div>분자</div></div>
      <div class="card text-center"><div id="sigcnt" class="text-2xl font-bold">0</div><div>신호</div></div>
      <div class="card text-center"><div id="growst" class="text-2xl font-bold">대기</div><div>성장</div></div>
    </div><h3 class="font-bold mb-1">활동 로그</h3>`;
  }catch(e){toast('시트 로드 실패','red');}
}

/* ─────── Alpaca 1분봉 Fetch ─────── */
async function alpacaBar(sym){
  try{
    const r=await fetch(`https://data.alpaca.markets/v2/stocks/${sym}/bars?timeframe=1Min&limit=1`,{
      headers:{'APCA-API-KEY-ID':CONFIG.ALPACA_KEY,'APCA-API-SECRET-KEY':CONFIG.ALPACA_SEC}});
    const j=await r.json();return j.bars[0];
  }catch(e){return null;}
}

/* ─────── 스캐너 루프 ─────── */
async function scanLoop(){
  if(!watch.length)return;
  for(const sym of watch){
    const bar=await alpacaBar(sym);
    if(!bar)continue;
    // 아톰 탐지 예시: 1분봉 Close>Open → TRG-008
    const detected=[];
    if(bar.c>bar.o) detected.push('TRG-008');
    if(Math.random()<.2) detected.push('STR-003');
    detected.forEach(a=>{
      $('#scan .atom-card')?.remove(); // scroll 유지
      $('#atom-log').insertAdjacentHTML('beforeend',`<div class="atom-card">${sym} ${a} $${bar.c}</div>`);
      log(`${sym} 아톰 ${a}`);
      gSheetAppend(sidbRange,[Date.now(),sym,a,'1m',bar.c,bar.v]); // SIDB 기록
    });
    // 분자 매칭
    molecules.forEach(m=>{
      if(m.need.every(n=>detected.includes(n))){
        $('#molecule-log').insertAdjacentHTML('beforeend',`<div class="molecule-signal">${sym} ${m.id} 신호!</div>`);
        const predID='P'+Date.now();
        predictions.push({id:predID,ticker:sym,molecule:m.id,entry:bar.c});
        $('#sigcnt').textContent=parseInt($('#sigcnt').textContent)+1;
        gSheetAppend(predRange,[predID,new Date().toISOString(),sym,m.id,`Entry $${bar.c}`,m.need.join(','),'','','']);
      }
    });
  }
}

/* ─────── 훈련 (Gemini) ─────── */
$('#btn-train').onclick=async ()=>{
  const tk=$('#train-ticker').value.trim(), dt=$('#train-date').value, note=$('#train-note').value.trim();
  if(!tk||!dt||!note) return toast('모든 입력','red');
  const prompt=`Ticker:${tk},Date:${dt},Insight:${note}\n아톰·분자 제안 JSON`;
  const r=await fetch(`https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key=${CONFIG.GEMINI_KEY}`,
    {method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({contents:[{parts:[{text:prompt}]}]})});
  const j=await r.json();
  $('#train-result').classList.remove('hidden');
  $('#train-result').textContent=j.candidates?.[0]?.content.parts[0].text||'오류';
};

/* ─────── 설정 저장 버튼 ─────── */
$('#btn-save-settings').onclick=()=>{
  CONFIG.ALPACA_KEY=$('#inp-alpaca-key').value.trim();
  CONFIG.ALPACA_SEC=$('#inp-alpaca-secret').value.trim();
  CONFIG.GEMINI_KEY=$('#inp-gemini-key').value.trim();
  CONFIG.SHEET_ID=$('#inp-sheet-id').value.trim();
  CONFIG.SHEET_APIKEY=$('#inp-sheet-api-key').value.trim();
  sessionStorage.setItem('cfg',JSON.stringify(CONFIG));
  toast('설정 저장','blue');
  loadLogicDB();
};

/* ─────── 스캔 버튼 ─────── */
$('#btn-start-scan').onclick=()=>{
  if(scanTimer){toast('이미 실행중','info');return;}
  scanTimer=setInterval(scanLoop,60000); // 1분마다 루프
  toast('스캐너 ON');
};
$('#btn-stop-scan').onclick=()=>{
  clearInterval(scanTimer);scanTimer=null;toast('스캐너 OFF','blue');
};
/* ─────── 종목 추가/제거 ─────── */
$('#btn-add-ticker').onclick=()=>{
  let v=$('#scan-ticker-input').value.toUpperCase().trim();
  if(v&&watch.length<10&&!watch.includes(v)){watch.push(v);renderWatch();}
};
function renderWatch(){
  $('#watchlist').innerHTML=watch.map(t=>`<span class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full mr-1">${t}</span>`).join('');
}
/* ─────── 초기 설정 복구 ─────── */
function init(){
  const s=sessionStorage.getItem('cfg');if(s)Object.assign(CONFIG,JSON.parse(s));
  loadLogicDB();
}
})();
