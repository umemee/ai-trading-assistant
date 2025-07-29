/* app.js ― 모든 UI·데이터 로직 (ES Module) */
(() => {

  /* ▽ 0. 사용자 설정 (민감 값은 빈칸으로 두기) */
  const CFG = {
    PW         : '2025',   // 로그인 비밀번호 (직접 변경)
    ALPACA_KEY : 'PKMM3D2Y4KLMQZFC9XJK',       // 클라이언트에 보관 ❌ → 데모에서는 비움
    ALPACA_SEC : 'ciqIeRyOsPpQwxVIWnjTab05CGnlohkdSolFZmo1',
    GEMINI_KEY : 'AIzaSyAHylP36yV4AHDlaf9GxQIWzSfU1jHIlDQ',
    SHEET_ID   : '1TaSyGB-0LY678_-pqmXdrkycQNexauZBJ6fM9SCJXaE',
    SHEET_API  : 'AIzaSyDbvEEX2OgoWE7ForvvCsZSF3JgQX_cD-U'
  };

  /* ▽ 0-B. 백엔드 프록시 경로 (실 운영 시 수정) */
  const PROXY = {
    alpaca : '/api/alpaca',    // 예:  GET /api/alpaca?symbol=AAPL
    sheets : '/api/sheets'     // 예: POST /api/sheets {range,row}
  };

  /* ▽ 1. DOM 예약어 */
  const $  = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];

  /* ▽ 2. 토스트 & 로그 */
  function toast(msg, type = 'green') {
    const t = $('#toast');
    t.textContent = msg;
    t.className   = `toast ${type}`;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2600);
  }
  function log(msg) {
    $('#log').insertAdjacentHTML('beforeend',
      `${new Date().toLocaleTimeString()} | ${msg}\n`);
    $('#log').scrollTop = $('#log').scrollHeight;
  }

  /* ▽ 3. 로그인 절차 */
  $('#pw-btn').onclick = () => {
    if ($('#pw-input').value === CFG.PW) {
      $('#pw-modal').style.display = 'none';
      sessionStorage.setItem('ok', 'true');
      init();
    } else toast('❌ 비밀번호가 틀렸습니다', 'red');
  };
  if (sessionStorage.getItem('ok')) {
    $('#pw-modal').style.display = 'none';
    init();
  }

  /* ▽ 4. 섹션 전환 */
  $$('.nav-btn').forEach(btn => {
    btn.onclick = e => {
      $$('.sec').forEach(s => s.classList.remove('active'));
      $('.nav-btn.active')?.classList.remove('active');
      e.target.classList.add('active');
      $('#' + e.target.dataset.sec).classList.add('active');
    };
  });

  /* ▽ 5. 전역 상태 */
  let atoms = [], molecules = [], perf = [],
      watch = [], timer = null;

  /* ▽ 6. Google Sheets I/O (데모는 로컬 JSON 대체) */
  async function gsRead(range) {
    if (!CFG.SHEET_ID || !CFG.SHEET_API) return demoRows(range);
    const url = `https://sheets.googleapis.com/v4/spreadsheets/${CFG.SHEET_ID}/values/${range}?key=${CFG.SHEET_API}`;
    const r   = await fetch(url);
    if (!r.ok) throw new Error('Sheets read error');
    return (await r.json()).values || [];
  }
  async function gsAppend(range, row) {
    if (!CFG.SHEET_ID || !CFG.SHEET_API) return;
    const url = `https://sheets.googleapis.com/v4/spreadsheets/${CFG.SHEET_ID}/values/${range}:append?valueInputOption=RAW&key=${CFG.SHEET_API}`;
    await fetch(url, {
      method : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body   : JSON.stringify({ values: [row] })
    });
  }

  /* → demoRows: Sheets가 없을 때 로컬 더미 데이터 */
  function demoRows(range) {
    if (range.startsWith('Atom_DB'))      return [
      ['STR-003','1분 20EMA 지지','','','Structural'],
      ['TRG-003','거래량 폭발','','','Trigger']
    ];
    if (range.startsWith('Molecule_DB'))  return [
      ['LOGIC-EXP-004','첫 눌림목','','STR-003,TRG-003','80']
    ];
    if (range.startsWith('Performance'))  return [
      ['LOGIC-EXP-004','12','65','2.1','8.5','1.8','0.85','2024-07-29']
    ];
    return [];
  }

  /* ▽ 7. 초기화 */
  async function init() {
    /* 7-A. 저장돼 있던 개인 API 키 복원 */
    const saved = sessionStorage.getItem('cfg');
    if (saved) Object.assign(CFG, JSON.parse(saved));
    $('#alpaca-key').value = CFG.ALPACA_KEY;
    $('#alpaca-sec').value = CFG.ALPACA_SEC;
    $('#gemini-key').value = CFG.GEMINI_KEY;
    $('#sheet-id').value   = CFG.SHEET_ID;
    $('#sheet-api').value  = CFG.SHEET_API;

    /* 7-B. 데이터 로드 */
    try {
      atoms     = (await gsRead('Atom_DB!A2:F'))
                    .map(r => ({ id:r, name:r[1], desc:r[2], cat:r }));
      molecules = (await gsRead('Molecule_DB!A2:F'))
                    .map(r => ({ id:r, name:r[1],
                                 need:(r[3]||'').split(',').map(s=>s.trim()),
                                 thr :parseFloat(r||80) }));
      perf      = await gsRead('Performance_Dashboard!A2:H');
      log('✅ Google Sheets 연결 성공');
    } catch (e) {
      log('⚠️ Sheets 연결 실패 → 데모 데이터 사용');
      atoms     = demoRows('Atom_DB');
      molecules = demoRows('Molecule_DB');
      perf      = demoRows('Performance');
    }

    /* 7-C. KPI 표시 */
    $('#atom-cnt').textContent  = atoms.length;
    $('#mol-cnt').textContent   = molecules.length;
    $('#trade-cnt').textContent = perf.length;
    if (perf.length) {
      const avg = perf.reduce((s,r)=>s+parseFloat(r[2]||0),0) / perf.length;
      $('#winrate').textContent = avg.toFixed(1) + '%';
    }

    renderAtomTable();
    renderPerf();
    renderWatch();
  }

  /* ▽ 8. 지식 탐색기 */
  function renderAtomTable() {
    const kw   = $('#search-atom').value.trim().toLowerCase();
    const rows = atoms.filter(a =>
      !kw || a.name.toLowerCase().includes(kw) || a.id.toLowerCase().includes(kw));

    let html = `<table class="min-w-full text-sm border-collapse border">
      <thead><tr class="bg-gray-200 text-left">
        <th class="border px-3 py-2">ID</th>
        <th class="border px-3 py-2">이름</th>
        <th class="border px-3 py-2">카테고리</th>
        <th class="border px-3 py-2">설명</th>
      </tr></thead><tbody>`;
    rows.forEach(r => {
      html += `<tr class="hover:bg-gray-50">
        <td class="border px-3 py-2 font-mono text-xs">${r.id}</td>
        <td class="border px-3 py-2">${r.name}</td>
        <td class="border px-3 py-2">
          <span class="px-2 py-1 text-xs rounded
            ${r.cat==='Context'   ?'bg-blue-100 text-blue-800' :
              r.cat==='Structural'?'bg-green-100 text-green-800':
                                    'bg-yellow-100 text-yellow-800'}">${r.cat}</span>
        </td>
        <td class="border px-3 py-2 text-xs">${r.desc||'-'}</td>
      </tr>`;
    });
    $('#atom-table').innerHTML = html + '</tbody></table>';
  }
  $('#search-atom').oninput = renderAtomTable;

  /* ▽ 9. 성과 분석 (Chart.js 동적 로딩) */
  async function renderPerf() {
    if (!perf.length) return;

    // Chart.js 로드 확인
    if (typeof Chart === 'undefined') {
      await import('https://cdn.jsdelivr.net/npm/chart.js');
    }

    const labels = perf.map(r => r);
    const wins   = perf.map(r => parseFloat(r[2]||0));
    const ctx    = $('#mol-chart').getContext('2d');

    new Chart(ctx, {
      type : 'bar',
      data : { labels,
        datasets:[{ label:'승률 %', data:wins, backgroundColor:'#14b8a6' }] },
      options: {
        responsive:true, plugins:{ legend:{display:false} },
        scales:{ y:{ beginAtZero:true, max:100 } }
      }
    });

    /* 9-B. 테이블 */
    let t = `<thead><tr class="bg-gray-200 text-sm">
      <th class="border px-3 py-2">분자 ID</th>
      <th class="border px-3 py-2">총 거래</th>
      <th class="border px-3 py-2">승률 %</th>
      <th class="border px-3 py-2">평균 RRR</th>
      <th class="border px-3 py-2">평균 보유시간</th>
      <th class="border px-3 py-2">Profit Factor</th>
    </tr></thead><tbody>`;
    perf.forEach(r => {
      const win = parseFloat(r[2]||0);
      t += `<tr class="${win>=60?'bg-green-50':win>=40?'bg-yellow-50':'bg-red-50'}">
        <td class="border px-3 py-2 font-mono text-xs">${r}</td>
        <td class="border px-3 py-2 text-center">${r[1]}</td>
        <td class="border px-3 py-2 text-center font-semibold">${r[2]}%</td>
        <td class="border px-3 py-2 text-center">${r[3]}</td>
        <td class="border px-3 py-2 text-center">${r}</td>
        <td class="border px-3 py-2 text-center">${r}</td>
      </tr>`;
    });
    $('#perf-table').innerHTML = t + '</tbody>';
  }

  /* ▽ 10. 종목 워치리스트 */
  $('#add-sym').onclick = () => {
    const sym = $('#sym-input').value.toUpperCase().trim();
    if (!sym)                return toast('티커를 입력하세요','red');
    if (watch.includes(sym)) return toast('이미 추가된 종목','red');
    if (watch.length >= 10)  return toast('최대 10개까지','red');

    watch.push(sym);
    $('#sym-input').value = '';
    renderWatch();
    log(`📈 종목 추가: ${sym}`);
    toast(`${sym} 추가완료`);
  };

  function renderWatch() {
    $('#sym-tags').innerHTML = watch.map(s =>
      `<span class="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-sm">
         ${s}
         <button onclick="removeSym('${s}')" class="ml-1 text-red-500 hover:text-red-700">×</button>
       </span>`
    ).join('');
  }
  window.removeSym = sym => {
    watch = watch.filter(s => s !== sym);
    renderWatch();
    log(`📉 종목 제거: ${sym}`);
  };

  /* ▽ 11. 스캐너 시뮬레이션 */
  $('#start-scan').onclick = () => {
    if (!watch.length) return toast('감시할 종목이 없습니다','red');
    if (timer)         return toast('이미 실행 중입니다','blue');

    $('#start-scan').disabled = true;
    $('#stop-scan').disabled  = false;

    timer = setInterval(scanTick, 15000);
    log('🚀 스캐너 시작');
    toast('스캐너 시작','blue');
    scanTick();              // 즉시 1회
  };
  $('#stop-scan').onclick = () => {
    clearInterval(timer);
    timer = null;
    $('#start-scan').disabled = false;
    $('#stop-scan').disabled  = true;
    log('⏹ 스캐너 정지');
    toast('스캐너 정지','blue');
  };

  async function scanTick() {
    const sym   = watch[Math.floor(Math.random()*watch.length)];
    const price = (50 + Math.random()*200).toFixed(2);
    const vol   = Math.floor(Math.random()*1e6);

    /* 실제 환경: fetch(`${PROXY.alpaca}?symbol=${sym}`) 등으로 교체 */
    /* 랜덤 아톰 탐지 30% 확률 */
    if (Math.random() < 0.3) {
      const at   = atoms[Math.floor(Math.random()*atoms.length)];
      const grade = ['A++','A+','B+','C','F'][Math.floor(Math.random()*5)];
      $('#sidb-log').insertAdjacentHTML('beforeend',
        `[${new Date().toLocaleTimeString()}] ${sym}: ${at.id} (${at.name}) | $${price} | Vol: ${vol.toLocaleString()} | 등급: ${grade}\n`);
      $('#sidb-log').scrollTop = $('#sidb-log').scrollHeight;

      /* Sheets 기록 (프록시 or 직접) */
      try {
        await gsAppend('SIDB!A:H',
          [Date.now(), new Date().toISOString(), sym, at.id, '1m', price, vol, `등급:${grade}`]);
      } catch(e){ /* 오프라인이면 무시 */ }

      /* 분자 매칭 15% 확률 */
      if (Math.random() < 0.15 && grade !== 'F') {
        const mol = molecules[Math.floor(Math.random()*molecules.length)];
        log(`🔥 분자 신호: ${sym} - ${mol.id}`);
        toast(`🔥 ${sym} 신호!`,'red');
      }
    }
  }

  /* ▽ 12. 설정 저장 */
  $('#save-set').onclick = () => {
    CFG.ALPACA_KEY = $('#alpaca-key').value.trim();
    CFG.ALPACA_SEC = $('#alpaca-sec').value.trim();
    CFG.GEMINI_KEY = $('#gemini-key').value.trim();
    CFG.SHEET_ID   = $('#sheet-id').value.trim();
    CFG.SHEET_API  = $('#sheet-api').value.trim();

    sessionStorage.setItem('cfg', JSON.stringify(CFG));
    $('#set-msg').textContent = '✅ 설정 저장 완료';
    toast('설정이 저장되었습니다','blue');
  };

})();
