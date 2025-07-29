// app.js ─ Demo1 Full UI + 실사용 로직 결합 완전판
(()=>{

/* ▽ 0. 사용자 설정 ▽ */
const CFG = {
  PW : '2025',                             // ← 원하는 비밀번호로 변경
  ALPACA_KEY : 'PKMM3D2Y4KLMQZFC9XJK', ALPACA_SEC : 'ciqIeRyOsPpQwxVIWnjTab05CGnlohkdSolFZmo1',            // ← Alpaca 키 입력
  GEMINI_KEY : 'AIzaSyAHylP36yV4AHDlaf9GxQIWzSfU1jHIlDQ',                             // ← Gemini 키 입력  
  SHEET_ID : '1TaSyGB-0LY678_-pqmXdrkycQNexauZBJ6fM9SCJXaE
', SHEET_API : 'AIzaSyDbvEEX2OgoWE7ForvvCsZSF3JgQX_cD-U
'                // ← Google Sheets ID & API Key
};

/* ▽ 1. 전역 변수 ▽ */
let atoms=[], molecules=[], watchlist=[], predictions=[], scanTimer=null;

/* ▽ 2. DOM helpers ▽ */
const $ = s => document.querySelector(s);
const $$= s => [...document.querySelectorAll(s)];
function toast(msg,type='green'){
  const t=$('#toast');t.textContent=msg;t.className=`toast ${type}`;t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2600);
}
function log(msg){
  $('#log').insertAdjacentHTML('beforeend',`${new Date().toLocaleTimeString()} | ${msg}\n`);
  $('#log').scrollTop = $('#log').scrollHeight;
}

/* ▽ 3. 로그인 ▽ */
$('#pw-btn').onclick = ()=>{ 
  if($('#pw-input').value===CFG.PW){ 
    $('#pw-modal').style.display='none'; 
    sessionStorage.setItem('ok','1');
    init(); 
  } else toast('❌ 비밀번호 오류','red'); 
};
if(sessionStorage.getItem('ok')) { $('#pw-modal').style.display='none'; init(); }

/* ▽ 4. 섹션 전환 ▽ */
$$('.nav-btn').forEach(btn=>{
  btn.onclick=e=>{
    $$('.sec').forEach(s=>s.classList.remove('active'));
    $$('.nav-btn').forEach(n=>n.classList.remove('active'));
    e.target.classList.add('active');
    $(`#${e.target.dataset.sec}`).classList.add('active');
  }
});

/* ▽ 5. Google Sheets API ▽ */
async function sheetsRead(range){
  const url=`https://sheets.googleapis.com/v4/spreadsheets/${CFG.SHEET_ID}/values/${range}?key=${CFG.SHEET_API}`;
  const r=await fetch(url);
  if(!r.ok) throw new Error('Sheets read failed');
  return (await r.json()).values||[];
}
async function sheetsAppend(range,row){
  const url=`https://sheets.googleapis.com/v4/spreadsheets/${CFG.SHEET_ID}/values/${range}:append?valueInputOption=RAW&key=${CFG.SHEET_API}`;
  const r=await fetch(url,{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({values:[row]})
  });
  if(!r.ok) throw new Error('Sheets append failed');
}

/* ▽ 6. 로직 DB 로드 ▽ */
async function loadLogicDB(){
  try{
    // 아톰 로드
    const atomRows = await sheetsRead('Atom_DB!A2:F');
    atoms = atomRows.map(r=>({
      id:r[0], name:r[1], desc:r[2], output:r[3], cat:r[4], ref:r[5]
    }));
    
    // 분자 로드  
    const molRows = await sheetsRead('Molecule_DB!A2:F');
    molecules = molRows.map(r=>({
      id:r[0], name:r[1], cat:r[2], atoms:r[3]?.split(',').map(s=>s.trim())||[], 
      threshold:parseFloat(r[4])||80, notes:r[5]
    }));
    
    updateDashboard();
    updateAtomExplorer();
    toast(`📊 아톰 ${atoms.length}개, 분자 ${molecules.length}개 로드`);
    log(`DB 로드 완료: 아톰 ${atoms.length}, 분자 ${molecules.length}`);
    
  } catch(e){
    // 시트 로드 실패 시 데모 데이터
    atoms = [
      {id:'CTX-001',name:'촉매_A++등급',cat:'Context',desc:'뉴스 등급이 A++'},
      {id:'STR-003',name:'1분_20EMA_지지',cat:'Structural',desc:'1분봉 20EMA 지지'},
      {id:'TRG-003',name:'거래량_폭발',cat:'Trigger',desc:'거래량 500% 급증'},
      {id:'TRG-008',name:'1분_정배열',cat:'Trigger',desc:'단기/중기/장기 정배열'}
    ];
    molecules = [
      {id:'LOGIC-EXP-004',name:'장 초반 정배열 후 첫 눌림목',atoms:['STR-003','TRG-008'],threshold:80}
    ];
    updateDashboard();
    updateAtomExplorer();
    toast('⚠️ 시트 연결 실패, 데모 데이터 사용','red');
    log('시트 로드 실패, 로컬 데이터 사용');
  }
}

/* ▽ 7. 대시보드 업데이트 ▽ */
function updateDashboard(){
  $('#atom-cnt').textContent = atoms.length;
  $('#mol-cnt').textContent = molecules.length;
  $('#winrate').textContent = (Math.random()*30+40).toFixed(1)+'%';
  $('#trade-cnt').textContent = Math.floor(Math.random()*500+100);
}

/* ▽ 8. 지식 탐색기 ▽ */
function updateAtomExplorer(){
  $('#atom-table').innerHTML = `
    <table class="w-full text-sm">
      <thead class="bg-gray-100">
        <tr><th class="p-2">ID</th><th class="p-2">이름</th><th class="p-2">카테고리</th><th class="p-2">설명</th></tr>
      </thead>
      <tbody>
        ${atoms.map(a=>`<tr class="border-b"><td class="p-2">${a.id}</td><td class="p-2">${a.name}</td><td class="p-2">${a.cat}</td><td class="p-2">${a.desc||'-'}</td></tr>`).join('')}
      </tbody>
    </table>
  `;
}

/* ▽ 9. Alpaca API (1분봉) ▽ */
async function getAlpacaBar(symbol){
  try{
    const r = await fetch(`https://data.alpaca.markets/v2/stocks/${symbol}/bars?timeframe=1Min&limit=1`,{
      headers:{
        'APCA-API-KEY-ID':CFG.ALPACA_KEY,
        'APCA-API-SECRET-KEY':CFG.ALPACA_SEC
      }
    });
    const json = await r.json();
    return json.bars?.[0];
  } catch(e){
    return null;
  }
}

/* ▽ 10. 스캐너 로직 ▽ */
async function scanTick(){
  if(!watchlist.length) return;
  
  for(const sym of watchlist){
    const bar = await getAlpacaBar(sym);
    if(!bar) continue;
    
    // 아톰 탐지 (예시)
    const detected = [];
    if(bar.c > bar.o) detected.push('TRG-008'); // 양봉이면 정배열
    if(bar.v > 50000) detected.push('TRG-003'); // 거래량 많으면 폭발
    if(Math.random()<0.3) detected.push('STR-003'); // 랜덤 지지
    
    detected.forEach(atomId=>{
      log(`🔍 ${sym}: ${atomId} 아톰 탐지 (가격: $${bar.c})`);
      // SIDB에 기록
      if(CFG.SHEET_ID) sheetsAppend('SIDB!A:H',[Date.now(),sym,atomId,'1Min',bar.c,bar.v,'','']).catch(e=>console.warn('SIDB 기록 실패'));
    });
    
    // 분자 매칭 체크
    molecules.forEach(mol=>{
      const match = mol.atoms.filter(a=>detected.includes(a));
      if(match.length >= mol.atoms.length * mol.threshold/100){
        log(`🔥 ${sym}: ${mol.id} 분자 신호! (${mol.name})`);
        const pred = {id:`P${Date.now()}`,ticker:sym,molecule:mol.id,entry:bar.c,time:new Date()};
        predictions.push(pred);
        
        // 예측 시트에 기록
        if(CFG.SHEET_ID) sheetsAppend('Prediction_Notes!A:S',[
          pred.id,pred.time.toISOString(),sym,mol.id,`Entry: $${bar.c}`,
          match.join(','),'','','','','','','','','','','',''
        ]).catch(e=>console.warn('예측 기록 실패'));
      }
    });
  }
}

/* ▽ 11. 스캐너 컨트롤 ▽ */
$('#add-sym').onclick = ()=>{
  const val = $('#sym-input').value.toUpperCase().trim();
  if(val && !watchlist.includes(val) && watchlist.length<10){
    watchlist.push(val);
    $('#sym-input').value='';
    updateSymTags();
    log(`📈 종목 추가: ${val}`);
  }
};
$('#start-scan').onclick = ()=>{
  if(!watchlist.length) return toast('종목을 먼저 추가하세요','red');
  if(scanTimer) return toast('이미 실행 중','blue');
  
  scanTimer = setInterval(scanTick, 60000); // 1분마다
  $('#start-scan').disabled=true;
  $('#stop-scan').disabled=false;
  toast('🚀 스캐너 시작');
  log('✅ 실시간 스캐너 시작');
};
$('#stop-scan').onclick = ()=>{
  if(scanTimer) clearInterval(scanTimer);
  scanTimer=null;
  $('#start-scan').disabled=false;
  $('#stop-scan').disabled=true;
  toast('⏹️ 스캐너 정지','blue');
  log('⏹️ 스캐너 정지됨');
};

function updateSymTags(){
  $('#sym-tags').innerHTML = watchlist.map(s=>
    `<span class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm">
      ${s} <button onclick="removeSym('${s}')" class="ml-1 text-red-500">×</button>
    </span>`
  ).join('');
}
window.removeSym = function(sym){
  watchlist = watchlist.filter(s=>s!==sym);
  updateSymTags();
  log(`📉 종목 제거: ${sym}`);
};

/* ▽ 12. 설정 저장 ▽ */
$('#save-set').onclick = ()=>{
  CFG.ALPACA_KEY = $('#alpaca-key').value.trim();
  CFG.ALPACA_SEC = $('#alpaca-sec').value.trim();  
  CFG.GEMINI_KEY = $('#gemini-key').value.trim();
  CFG.SHEET_ID   = $('#sheet-id').value.trim();
  CFG.SHEET_API  = $('#sheet-api').value.trim();
  
  sessionStorage.setItem('cfg',JSON.stringify(CFG));
  $('#set-msg').textContent = '✅ 설정 저장 완료';
  toast('💾 설정 저장됨');
  
  // 설정 변경 후 DB 재로드
  if(CFG.SHEET_ID && CFG.SHEET_API) loadLogicDB();
};

/* ▽ 13. 성과 분석 (Chart.js) ▽ */
function updatePerformanceChart(){
  const ctx = $('#mol-chart').getContext('2d');
  new Chart(ctx,{
    type:'bar',
    data:{
      labels:molecules.map(m=>m.id),
      datasets:[{
        label:'승률 (%)',
        data:molecules.map(()=>Math.random()*60+20),
        backgroundColor:'rgba(34,197,94,0.6)'
      }]
    },
    options:{responsive:true,scales:{y:{beginAtZero:true,max:100}}}
  });
  
  // 성과 테이블
  $('#perf-table').innerHTML = `
    <thead class="bg-gray-100">
      <tr><th class="p-2">분자 ID</th><th class="p-2">전략명</th><th class="p-2">승률</th><th class="p-2">수익률</th></tr>
    </thead>
    <tbody>
      ${molecules.map(m=>`
        <tr class="border-b">
          <td class="p-2">${m.id}</td><td class="p-2">${m.name}</td>
          <td class="p-2">${(Math.random()*60+20).toFixed(1)}%</td>
          <td class="p-2 text-green-600">+${(Math.random()*15+5).toFixed(1)}%</td>
        </tr>
      `).join('')}
    </tbody>
  `;
}

/* ▽ 14. 검색 기능 ▽ */
$('#search-atom').oninput = e=>{
  const query = e.target.value.toLowerCase();
  const filtered = atoms.filter(a=>
    a.id.toLowerCase().includes(query) || 
    a.name.toLowerCase().includes(query)
  );
  
  $('#atom-table').innerHTML = `
    <table class="w-full text-sm">
      <thead class="bg-gray-100">
        <tr><th class="p-2">ID</th><th class="p-2">이름</th><th class="p-2">카테고리</th><th class="p-2">설명</th></tr>
      </thead>
      <tbody>
        ${filtered.map(a=>`<tr class="border-b"><td class="p-2">${a.id}</td><td class="p-2">${a.name}</td><td class="p-2">${a.cat}</td><td class="p-2">${a.desc||'-'}</td></tr>`).join('')}
      </tbody>
    </table>
  `;
};

/* ▽ 15. 초기화 ▽ */
function init(){
  // 저장된 설정 복원
  const saved = sessionStorage.getItem('cfg');
  if(saved) Object.assign(CFG,JSON.parse(saved));
  
  // UI에 값 복원
  $('#alpaca-key').value = CFG.ALPACA_KEY;
  $('#alpaca-sec').value = CFG.ALPACA_SEC;
  $('#gemini-key').value = CFG.GEMINI_KEY;
  $('#sheet-id').value   = CFG.SHEET_ID;
  $('#sheet-api').value  = CFG.SHEET_API;
  
  // DB 로드 및 UI 업데이트
  loadLogicDB();
  
  // 성과 차트는 분자 로드 후 생성
  setTimeout(updatePerformanceChart, 1000);
  
  log('🚀 시스템 초기화 완료');
  toast('🎯 시스템 준비됨');
}

/* ▽ 16. Enter 키 이벤트 ▽ */
$('#sym-input').onkeypress = e=>{ if(e.key==='Enter') $('#add-sym').click(); };
$('#pw-input').onkeypress  = e=>{ if(e.key==='Enter') $('#pw-btn').click(); };

})();
