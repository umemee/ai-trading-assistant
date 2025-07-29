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

/* ▽ 1. DOM helpers ▽ */
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

/* ▽ 2. 로그인 ▽ */
$('#pw-btn').onclick = ()=>{ 
  if($('#pw-input').value===CFG.PW){ 
    $('#pw-modal').style.display='none'; 
    sessionStorage.setItem('ok','true');
    init(); 
  } else toast('❌ 비밀번호','red'); 
};
if(sessionStorage.getItem('ok')) { $('#pw-modal').style.display='none'; init(); }

/* ▽ 3. 섹션 스위치 ▽ */
$$('.nav-btn').forEach(btn=>{
  btn.onclick=e=>{ 
    $$('.sec').forEach(s=>s.classList.remove('active'));
    $('.nav-btn.active')?.classList.remove('active'); 
    e.target.classList.add('active');
    $('#'+e.target.dataset.sec).classList.add('active');
  };
});

/* ▽ 4. 전역 상태 ▽ */
let atoms=[], molecules=[], perf=[], watch=[], timer=null, signals=0;

/* ▽ 5. Google Sheets I/O ▽ */
const gURL = (range)=>`https://sheets.googleapis.com/v4/spreadsheets/${CFG.SHEET_ID}/values/${range}?key=${CFG.SHEET_API}`;
async function gsRead(range){
  const r=await fetch(gURL(range));
  if(!r.ok)throw 'GS read error';
  return (await r.json()).values||[];
}
async function gsAppend(range,row){
  const url=`https://sheets.googleapis.com/v4/spreadsheets/${CFG.SHEET_ID}/values/${range}:append?valueInputOption=RAW&key=${CFG.SHEET_API}`;
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({values:[row]})});
  if(!r.ok)throw 'GS append error';
}

async function gsRows(){ 
  try{
    atoms = (await gsRead('Atom_DB!A2:F')).map(r=>({id:r[0],name:r[1],desc:r[2],cat:r[4]}));
    molecules = (await gsRead('Molecule_DB!A2:F')).map(r=>({id:r[0],name:r[1],need:r[3]?.split(',').map(s=>s.trim())||[],thr:parseFloat(r[4]||80)}));
    perf = (await gsRead('Performance_Dashboard!A2:H')); 
  }catch(e){
    toast('시트 연결 실패 - 데모 데이터 사용','red');
    atoms = [{id:'STR-003',name:'1분_20EMA_지지',cat:'Structural'},{id:'TRG-003',name:'거래량_폭발',cat:'Trigger'}];
    molecules = [{id:'LOGIC-EXP-004',name:'첫_눌림목',need:['STR-003','TRG-003'],thr:80}];
    perf = [['LOGIC-EXP-004','12','65','2.1','8.5','1.8','0.85','2024-07-29']];
  }
}

/* ▽ 6. 초기화 흐름 ▽ */
async function init(){
  // 설정 복원
  const ss=sessionStorage.getItem('cfg'); 
  if(ss) Object.assign(CFG, JSON.parse(ss));
  $('#alpaca-key').value=CFG.ALPACA_KEY; 
  $('#alpaca-sec').value=CFG.ALPACA_SEC;
  $('#gemini-key').value=CFG.GEMINI_KEY; 
  $('#sheet-id').value=CFG.SHEET_ID;
  $('#sheet-api').value=CFG.SHEET_API;

  // DB 로드
  await gsRows(); 
  $('#atom-cnt').textContent=atoms.length; 
  $('#mol-cnt').textContent=molecules.length;
  $('#trade-cnt').textContent=perf.length;
  if(perf.length>0){
    const avgWin = perf.reduce((sum,r)=>sum+parseFloat(r[2]||0),0)/perf.length;
    $('#winrate').textContent=avgWin.toFixed(1)+'%';
  }
  
  log(`✅ 시스템 초기화: 아톰 ${atoms.length}개, 분자 ${molecules.length}개`);
  renderAtomTable(); 
  renderPerf(); 
  renderWatch();
  
  // 네비 첫 버튼 활성화
  $('.nav-btn').classList.add('active');
}

/* ▽ 7. 지식 탐색기 테이블 ▽ */
function renderAtomTable(){
  const kw=$('#search-atom').value.trim().toLowerCase();
  const rows=atoms.filter(a=>!kw||a.name.toLowerCase().includes(kw)||a.id.toLowerCase().includes(kw));
  let html=`<table class="min-w-full text-sm border-collapse border">
    <thead><tr class="bg-gray-200 text-left">
      <th class="border px-3 py-2">ID</th>
      <th class="border px-3 py-2">이름</th>
      <th class="border px-3 py-2">카테고리</th>
      <th class="border px-3 py-2">설명</th>
    </tr></thead><tbody>`;
  rows.forEach(r=>{
    html+=`<tr class="hover:bg-gray-50">
      <td class="border px-3 py-2 font-mono text-xs">${r.id}</td>
      <td class="border px-3 py-2">${r.name}</td>
      <td class="border px-3 py-2">
        <span class="px-2 py-1 text-xs rounded ${r.cat==='Context'?'bg-blue-100 text-blue-800':r.cat==='Structural'?'bg-green-100 text-green-800':'bg-yellow-100 text-yellow-800'}">${r.cat}</span>
      </td>
      <td class="border px-3 py-2 text-xs">${r.desc||'-'}</td>
    </tr>`;
  });
  html+='</tbody></table>';
  $('#atom-table').innerHTML=html;
}
$('#search-atom').oninput=renderAtomTable;

/* ▽ 8. 전략 성과 분석 (Chart.js) ▽ */
function renderPerf(){
  if(perf.length===0) return;
  
  // Chart.js 로드 확인
  if(typeof Chart === 'undefined'){
    $('#mol-chart').outerHTML='<p class="text-gray-500">Chart.js 로딩 중...</p>';
    setTimeout(renderPerf, 1000);
    return;
  }
  
  const labels = perf.map(r=>r[0]);
  const wins = perf.map(r=>parseFloat(r[2]||0));
  const ctx = $('#mol-chart').getContext('2d');
  
  new Chart(ctx,{
    type:'bar',
    data:{
      labels,
      datasets:[{
        label:'승률 %',
        data:wins,
        backgroundColor:'#14b8a6',
        borderColor:'#0f766e',
        borderWidth:1
      }]
    },
    options:{
      responsive:true,
      plugins:{legend:{display:false}},
      scales:{y:{beginAtZero:true,max:100}}
    }
  });
  
  // 성과 테이블
  let t=`<thead><tr class="bg-gray-200 text-sm">
    <th class="border px-3 py-2">분자 ID</th>
    <th class="border px-3 py-2">총 거래</th>
    <th class="border px-3 py-2">승률 %</th>
    <th class="border px-3 py-2">평균 RRR</th>
    <th class="border px-3 py-2">평균 보유시간(분)</th>
    <th class="border px-3 py-2">Profit Factor</th>
  </tr></thead><tbody>`;
  
  perf.forEach(r=>{
    const winRate = parseFloat(r[2]||0);
    const rowClass = winRate >= 60 ? 'bg-green-50' : winRate >= 40 ? 'bg-yellow-50' : 'bg-red-50';
    t+=`<tr class="${rowClass}">
      <td class="border px-3 py-2 font-mono text-xs">${r[0]}</td>
      <td class="border px-3 py-2 text-center">${r[1]}</td>
      <td class="border px-3 py-2 text-center font-semibold">${r[2]}%</td>
      <td class="border px-3 py-2 text-center">${r[3]}</td>
      <td class="border px-3 py-2 text-center">${r[4]}</td>
      <td class="border px-3 py-2 text-center">${r[5]}</td>
    </tr>`;
  });
  t+='</tbody>';
  $('#perf-table').innerHTML=t;
}

/* ▽ 9. 종목 관리 ▽ */
$('#add-sym').onclick=()=>{
  const v=$('#sym-input').value.toUpperCase().trim();
  if(!v) return toast('티커 입력하세요','red');
  if(watch.includes(v)) return toast('이미 추가됨','red');
  if(watch.length>=10) return toast('최대 10개까지','red');
  
  watch.push(v);
  $('#sym-input').value='';
  renderWatch();
  log(`📈 종목 추가: ${v}`);
  toast(`${v} 추가완료`);
};

function renderWatch(){
  $('#sym-tags').innerHTML = watch.map(t=>
    `<span class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm">
      ${t} <button onclick="removeSym('${t}')" class="ml-1 text-red-500 hover:text-red-700">×</button>
    </span>`
  ).join('');
}

window.removeSym = function(sym){
  watch = watch.filter(s=>s!==sym);
  renderWatch();
  log(`📉 종목 제거: ${sym}`);
};

/* ▽ 10. 스캐너 (시뮬레이션) ▽ */
$('#start-scan').onclick=()=>{
  if(watch.length===0) return toast('감시할 종목이 없습니다','red');
  if(timer) return toast('이미 실행 중','blue');
  
  $('#start-scan').disabled=true;
  $('#stop-scan').disabled=false;
  signals=0;
  
  timer = setInterval(scanTick, 15000); // 15초마다
  log('🚀 스캐너 시작');
  toast('스캐너 시작');
  scanTick(); // 즉시 1회 실행
};

$('#stop-scan').onclick=()=>{
  if(timer) clearInterval(timer);
  timer=null;
  $('#start-scan').disabled=false;
  $('#stop-scan').disabled=true;
  log('⏹ 스캐너 정지');
  toast('스캐너 정지','blue');
};

async function scanTick(){
  const sym = watch[Math.floor(Math.random()*watch.length)];
  const price = (50 + Math.random()*200).toFixed(2);
  const vol = Math.floor(Math.random()*1000000);
  
  // 실제 환경에서는 Alpaca API 호출
  // const bar = await alpacaBar(sym);
  
  // 랜덤 아톰 탐지 (30% 확률)
  if(Math.random() < 0.3){
    const detectedAtom = atoms[Math.floor(Math.random()*atoms.length)];
    const grade = ['A++','A+','B+','C','F'][Math.floor(Math.random()*5)];
    
    $('#sidb-log').insertAdjacentHTML('beforeend',
      `[${new Date().toLocaleTimeString()}] ${sym}: ${detectedAtom.id} (${detectedAtom.name}) | $${price} | Vol: ${vol.toLocaleString()} | 호재: ${grade}\n`
    );
    $('#sidb-log').scrollTop = $('#sidb-log').scrollHeight;
    
    // SIDB 시트에 기록
    try{
      await gsAppend('SIDB!A:H', [Date.now(), new Date().toISOString(), sym, detectedAtom.id, '1m', price, vol, `호재등급:${grade}`]);
    }catch(e){
      console.log('SIDB 기록 실패:', e);
    }
    
    // 분자 매칭 (15% 확률)
    if(Math.random() < 0.15 && grade !== 'F'){
      const mol = molecules[Math.floor(Math.random()*molecules.length)];
      signals++;
      log(`🔥 분자 신호: ${sym} - ${mol.id}`);
      toast(`🔥 ${sym} 신호!`,'red');
      
      // 예측 노트에 기록
      try{
        const predId = 'PRED_' + Date.now();
        const entry = parseFloat(price);
        const stopLoss = (entry * 0.97).toFixed(2);
        const takeProfit = (entry * 1.06).toFixed(2);
        
        await gsAppend('Prediction_Notes!A:S', [
          predId, new Date().toISOString(), sym, mol.id, 
          entry, stopLoss, takeProfit, '2.0', grade, 
          detectedAtom.id, `${mol.name} 신호 발생`, 
          '', '', '', '', '', '', '', ''
        ]);
      }catch(e){
        console.log('예측 기록 실패:', e);
      }
    }
  }
}

/* ▽ 11. 설정 저장 ▽ */
$('#save-set').onclick=()=>{
  CFG.ALPACA_KEY = $('#alpaca-key').value.trim();
  CFG.ALPACA_SEC = $('#alpaca-sec').value.trim();
  CFG.GEMINI_KEY = $('#gemini-key').value.trim();
  CFG.SHEET_ID = $('#sheet-id').value.trim();
  CFG.SHEET_API = $('#sheet-api').value.trim();
  
  sessionStorage.setItem('cfg', JSON.stringify(CFG));
  $('#set-msg').textContent = '✅ 설정 저장 완료';
  toast('설정 저장 완료');
  
  // DB 재로드
  gsRows().then(()=>{
    $('#atom-cnt').textContent=atoms.length;
    $('#mol-cnt').textContent=molecules.length;
    renderAtomTable();
    renderPerf();
  });
};

/* ▽ 12. Chart.js 동적 로드 ▽ */
if(!window.Chart){
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
  script.onload = () => setTimeout(renderPerf, 100);
  document.head.appendChild(script);
}

})();
