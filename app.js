/* app.js ― 완전한 JavaScript 로직 */
(() => {
  'use strict';

  /* ══════════════════════════════════════════════════════════════════ */
  /* 전역 설정 */
  /* ══════════════════════════════════════════════════════════════════ */
  const CFG = {
    PW: '2025',
    // 모든 API 키는 빈칸으로 두고 백엔드에서만 사용
    ALPACA_KEY: '',
    ALPACA_SEC: '',
    GEMINI_KEY: '',
    SHEET_ID: '',
    SHEET_API: ''
  };

  const PROXY = {
    alpaca: '/api/alpaca',
    sheets: '/api/sheets',
    gemini: '/api/gemini'
  };

  /* ══════════════════════════════════════════════════════════════════ */
  /* DOM 유틸리티 */
  /* ══════════════════════════════════════════════════════════════════ */
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];

  /* ══════════════════════════════════════════════════════════════════ */
  /* 전역 상태 */
  /* ══════════════════════════════════════════════════════════════════ */
  let atoms = [];
  let molecules = [];
  let performance = [];
  let watchlist = [];
  let scanTimer = null;
  let isScanning = false;
  let logCount = 0;
  let atomsDetected = 0;
  let signalsGenerated = 0;
  let highGradeSignals = 0;
  let activeMolecules = 0;

  /* ══════════════════════════════════════════════════════════════════ */
  /* 유틸리티 함수 */
  /* ══════════════════════════════════════════════════════════════════ */
  function toast(message, type = 'green') {
    const toastEl = $('#toast');
    toastEl.textContent = message;
    toastEl.className = `toast ${type}`;
    toastEl.classList.add('show');
    setTimeout(() => toastEl.classList.remove('show'), 3000);
  }

  function log(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString('ko-KR');
    const logEl = $('#log');
    const icon = type === 'error' ? '❌' : type === 'success' ? '✅' : type === 'warning' ? '⚠️' : 'ℹ️';
    logEl.insertAdjacentHTML('beforeend', 
      `[${timestamp}] ${icon} ${message}\n`
    );
    logEl.scrollTop = logEl.scrollHeight;
  }

  function sidbLog(message) {
    const timestamp = new Date().toLocaleTimeString('ko-KR');
    const logEl = $('#sidb-log');
    logEl.insertAdjacentHTML('beforeend', 
      `[${timestamp}] ${message}\n`
    );
    logEl.scrollTop = logEl.scrollHeight;
    logCount++;
    $('#log-count').textContent = logCount;
  }

  function formatNumber(num) {
    return new Intl.NumberFormat('ko-KR').format(num);
  }

  function getRandomElement(array) {
    return array[Math.floor(Math.random() * array.length)];
  }

  /* ══════════════════════════════════════════════════════════════════ */
  /* 로그인 처리 */
  /* ══════════════════════════════════════════════════════════════════ */
  $('#pw-btn').onclick = () => {
    const password = $('#pw-input').value;
    if (password === CFG.PW) {
      $('#pw-modal').style.display = 'none';
      sessionStorage.setItem('authenticated', 'true');
      toast('로그인 성공! 시스템을 초기화합니다.', 'green');
      initializeSystem();
    } else {
      toast('❌ 비밀번호가 틀렸습니다', 'red');
      $('#pw-input').value = '';
      $('#pw-input').focus();
    }
  };

  $('#pw-input').onkeypress = (e) => {
    if (e.key === 'Enter') {
      $('#pw-btn').click();
    }
  };

  // 세션 확인
  if (sessionStorage.getItem('authenticated')) {
    $('#pw-modal').style.display = 'none';
    initializeSystem();
  }

  /* ══════════════════════════════════════════════════════════════════ */
  /* 네비게이션 처리 */
  /* ══════════════════════════════════════════════════════════════════ */
  $$('.nav-btn').forEach(btn => {
    btn.onclick = (e) => {
      // 모든 섹션 숨기기
      $$('.sec').forEach(sec => sec.classList.remove('active'));
      // 모든 네비게이션 버튼 비활성화
      $$('.nav-btn').forEach(navBtn => navBtn.classList.remove('active'));
      
      // 클릭된 버튼과 해당 섹션 활성화
      e.target.classList.add('active');
      const sectionId = e.target.dataset.sec;
      $(`#${sectionId}`).classList.add('active');
      
      // 섹션별 초기화 로직
      if (sectionId === 'performance') {
        renderPerformanceChart();
      } else if (sectionId === 'explorer') {
        renderAtomTable();
      } else if (sectionId === 'settings') {
        loadSettings();
      }
    };
  });

  /* ══════════════════════════════════════════════════════════════════ */
  /* 데이터 로딩 (더미 데이터) */
  /* ══════════════════════════════════════════════════════════════════ */
  async function loadDemoData() {
    // 아톰 더미 데이터
    atoms = [
      { id: 'CTX-001', name: '시장 개장 시간', category: 'Context', description: '정규 시장 시간 확인' },
      { id: 'CTX-002', name: 'VIX 레벨', category: 'Context', description: '변동성 지수 체크' },
      { id: 'STR-001', name: '20EMA 지지', category: 'Structural', description: '20일 지수이동평균 지지선' },
      { id: 'STR-002', name: '200MA 위치', category: 'Structural', description: '200일 이동평균선 위치' },
      { id: 'STR-003', name: '볼린저 밴드', category: 'Structural', description: '볼린저 밴드 위치 확인' },
      { id: 'TRG-001', name: '거래량 폭발', category: 'Trigger', description: '평균 거래량 대비 2배 이상' },
      { id: 'TRG-002', name: 'RSI 과매도', category: 'Trigger', description: 'RSI 30 이하 진입' },
      { id: 'TRG-003', name: '브레이크아웃', category: 'Trigger', description: '저항선 돌파' }
    ];

    // 분자 더미 데이터
    molecules = [
      { 
        id: 'LOGIC-EXP-001', 
        name: '첫 번째 눌림목', 
        atoms: ['CTX-001', 'STR-001', 'TRG-001'], 
        threshold: 75 
      },
      { 
        id: 'LOGIC-EXP-002', 
        name: '볼밴 스퀴즈', 
        atoms: ['CTX-002', 'STR-003', 'TRG-003'], 
        threshold: 80 
      }
    ];

    // 성과 더미 데이터
    performance = [
      ['LOGIC-EXP-001', '15', '73.3', '2.1', '4.2', '1.8', '0.12', '2024-07-29'],
      ['LOGIC-EXP-002', '8', '62.5', '1.9', '6.1', '1.5', '0.18', '2024-07-28']
    ];

    log('데모 데이터 로드 완료', 'success');
  }

  /* ══════════════════════════════════════════════════════════════════ */
  /* 시스템 초기화 */
  /* ══════════════════════════════════════════════════════════════════ */
  async function initializeSystem() {
    try {
      log('[시스템 초기화] AI 트레이딩 어시스턴트 V5.5 가동 시작', 'info');
      
      // 저장된 설정 복원
      const savedSettings = sessionStorage.getItem('settings');
      if (savedSettings) {
        Object.assign(CFG, JSON.parse(savedSettings));
        log('저장된 설정 복원 완료', 'success');
      }

      // 데이터 로드
      await loadDemoData();
      log(`[로직 DB] ${atoms.length}개 아톰 로드 완료`, 'success');
      log(`[분자 DB] ${molecules.length}개 분자 로드 완료`, 'success');

      // KPI 업데이트
      updateKPIs();
      
      // UI 렌더링
      renderAtomTable();
      renderPerformanceTable();
      updateWatchSummary();
      
      log('[대기 중] API 키 설정 대기...', 'warning');
      log('시스템 초기화 완료 - 준비됨', 'success');
      
    } catch (error) {
      log(`초기화 오류: ${error.message}`, 'error');
      toast('시스템 초기화 중 오류가 발생했습니다', 'red');
    }
  }

  /* ══════════════════════════════════════════════════════════════════ */
  /* KPI 업데이트 */
  /* ══════════════════════════════════════════════════════════════════ */
  function updateKPIs() {
    $('#atom-cnt').textContent = atoms.length;
    $('#mol-cnt').textContent = molecules.length;
    $('#signal-cnt').textContent = signalsGenerated;
    
    // 통계 계산
    if (performance.length > 0) {
      const avgWinrate = performance.reduce((sum, row) => 
        sum + parseFloat(row[2] || 0), 0) / performance.length;
      $('#avg-winrate').textContent = avgWinrate.toFixed(1) + '%';
    }
    
    $('#total-strategies').textContent = molecules.length;
    $('#total-trades').textContent = performance.reduce((sum, row) => 
      sum + parseInt(row[1] || 0), 0);
    
    // 카테고리별 아톰 수
    const contextCount = atoms.filter(a => a.category === 'Context').length;
    const structuralCount = atoms.filter(a => a.category === 'Structural').length;
    const triggerCount = atoms.filter(a => a.category === 'Trigger').length;
    
    $('#context-count').textContent = contextCount;
    $('#structural-count').textContent = structuralCount;
    $('#trigger-count').textContent = triggerCount;

    // 스캐너 통계
    $('#atoms-detected').textContent = atomsDetected;
    $('#signals-generated').textContent = signalsGenerated;
    $('#high-grade-signals').textContent = highGradeSignals;
    $('#active-molecules').textContent = activeMolecules;
  }

  /* ══════════════════════════════════════════════════════════════════ */
  /* 아톰 테이블 렌더링 */
  /* ══════════════════════════════════════════════════════════════════ */
  function renderAtomTable() {
    const searchTerm = $('#search-atom').value.toLowerCase();
    const activeFilter = $('.filter-btn.active')?.dataset.filter || 'all';
    
    let filteredAtoms = atoms.filter(atom => {
      const matchesSearch = !searchTerm || 
        atom.id.toLowerCase().includes(searchTerm) ||
        atom.name.toLowerCase().includes(searchTerm) ||
        atom.category.toLowerCase().includes(searchTerm);
      
      const matchesFilter = activeFilter === 'all' || atom.category === activeFilter;
      
      return matchesSearch && matchesFilter;
    });

    let html = `
      <table>
        <thead>
          <tr>
            <th>아톰 ID</th>
            <th>이름</th>
            <th>카테고리</th>
            <th>설명</th>
          </tr>
        </thead>
        <tbody>
    `;

    if (filteredAtoms.length === 0) {
      html += `
        <tr>
          <td colspan="4" class="text-center py-8 text-gray-400">
            검색 결과가 없습니다.
          </td>
        </tr>
      `;
    } else {
      filteredAtoms.forEach(atom => {
        const categoryColor = 
          atom.category === 'Context' ? 'text-blue-400' :
          atom.category === 'Structural' ? 'text-green-400' : 'text-red-400';
        
        html += `
          <tr>
            <td><code class="text-xs">${atom.id}</code></td>
            <td>${atom.name}</td>
            <td><span class="${categoryColor}">${atom.category}</span></td>
            <td class="text-sm text-gray-400">${atom.description}</td>
          </tr>
        `;
      });
    }

    html += '</tbody></table>';
    $('#atom-table').innerHTML = html;
  }

  // 검색 이벤트
  $('#search-atom').oninput = renderAtomTable;

  // 필터 버튼 이벤트
  $$('.filter-btn').forEach(btn => {
    btn.onclick = (e) => {
      $$('.filter-btn').forEach(b => b.classList.remove('active'));
      e.target.classList.add('active');
      renderAtomTable();
    };
  });

  /* ══════════════════════════════════════════════════════════════════ */
  /* 성과 차트 렌더링 */
  /* ══════════════════════════════════════════════════════════════════ */
  async function renderPerformanceChart() {
    if (!window.Chart || performance.length === 0) return;

    const ctx = $('#mol-chart').getContext('2d');
    const labels = performance.map(row => row[0]);
    const winrates = performance.map(row => parseFloat(row[2] || 0));

    new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: '승률 (%)',
          data: winrates,
          backgroundColor: 'rgba(34, 197, 94, 0.8)',
          borderColor: 'rgba(34, 197, 94, 1)',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            display: false
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            ticks: {
              color: '#cbd5e1',
              callback: function(value) {
                return value + '%';
              }
            },
            grid: {
              color: '#374151'
            }
          },
          x: {
            ticks: {
              color: '#cbd5e1'
            },
            grid: {
              color: '#374151'
            }
          }
        }
      }
    });
  }

  /* ══════════════════════════════════════════════════════════════════ */
  /* 성과 테이블 렌더링 */
  /* ══════════════════════════════════════════════════════════════════ */
  function renderPerformanceTable() {
    let html = '';
    
    if (performance.length === 0) {
      html = `
        <tr>
          <td colspan="8" class="text-center py-8 text-gray-400">
            성과 데이터가 없습니다.
          </td>
        </tr>
      `;
    } else {
      performance.forEach(row => {
        const winrate = parseFloat(row[2] || 0);
        const rowClass = winrate >= 70 ? 'bg-green-900 bg-opacity-30' :
                        winrate >= 60 ? 'bg-yellow-900 bg-opacity-30' : 
                        'bg-red-900 bg-opacity-30';
        
        html += `
          <tr class="${rowClass}">
            <td><code class="text-xs">${row[0]}</code></td>
            <td class="text-center">${row[1]}</td>
            <td class="text-center font-semibold">${row[2]}%</td>
            <td class="text-center">${row[3]}</td>
            <td class="text-center">${row[4]}</td>
            <td class="text-center">${row[5]}</td>
            <td class="text-center">${row[6]}</td>
            <td class="text-center text-xs text-gray-400">${row[7]}</td>
          </tr>
        `;
      });
    }
    
    $('#perf-tbody').innerHTML = html;
    
    // 평균 RRR 계산
    if (performance.length > 0) {
      const avgRRR = performance.reduce((sum, row) => 
        sum + parseFloat(row[3] || 0), 0) / performance.length;
      $('#avg-rrr').textContent = avgRRR.toFixed(1);
    }
  }

  /* ══════════════════════════════════════════════════════════════════ */
  /* 워치리스트 관리 */
  /* ══════════════════════════════════════════════════════════════════ */
  $('#add-sym').onclick = () => {
    const symbol = $('#sym-input').value.toUpperCase().trim();
    
    if (!symbol) {
      toast('종목 코드를 입력하세요', 'red');
      return;
    }
    
    if (!/^[A-Z]{1,6}$/.test(symbol)) {
      toast('올바른 종목 코드 형식이 아닙니다', 'red');
      return;
    }
    
    if (watchlist.includes(symbol)) {
      toast('이미 추가된 종목입니다', 'red');
      return;
    }
    
    if (watchlist.length >= 10) {
      toast('최대 10개 종목까지 추가할 수 있습니다', 'red');
      return;
    }
    
    watchlist.push(symbol);
    $('#sym-input').value = '';
    renderWatchlist();
    updateWatchSummary();
    log(`종목 추가: ${symbol}`, 'success');
    toast(`${symbol} 종목을 감시 목록에 추가했습니다`, 'green');
  };

  $('#sym-input').onkeypress = (e) => {
    if (e.key === 'Enter') {
      $('#add-sym').click();
    }
  };

  function renderWatchlist() {
    const html = watchlist.map(symbol => `
      <span class="symbol-tag">
        ${symbol}
        <span class="remove-btn" onclick="removeSymbol('${symbol}')">&times;</span>
      </span>
    `).join('');
    
    $('#sym-tags').innerHTML = html;
  }

  window.removeSymbol = (symbol) => {
    watchlist = watchlist.filter(s => s !== symbol);
    renderWatchlist();
    updateWatchSummary();
    log(`종목 제거: ${symbol}`, 'info');
    toast(`${symbol} 종목을 감시 목록에서 제거했습니다`, 'blue');
  };

  function updateWatchSummary() {
    if (watchlist.length === 0) {
      $('#watch-summary').textContent = '스캐너를 시작하여 아톰 탐지를 시작하세요...';
    } else {
      $('#watch-summary').innerHTML = `
        <div class="flex flex-wrap gap-2">
          ${watchlist.map(s => `<span class="symbol-tag">${s}</span>`).join('')}
        </div>
      `;
    }
  }

  /* ══════════════════════════════════════════════════════════════════ */
  /* 스캐너 제어 */
  /* ══════════════════════════════════════════════════════════════════ */
  $('#start-scan').onclick = () => {
    if (watchlist.length === 0) {
      toast('감시할 종목을 먼저 추가해주세요', 'red');
      return;
    }
    
    if (isScanning) {
      toast('이미 스캐너가 실행 중입니다', 'blue');
      return;
    }
    
    startScanner();
  };

  $('#stop-scan').onclick = () => {
    stopScanner();
  };

  function startScanner() {
    isScanning = true;
    $('#start-scan').disabled = true;
    $('#stop-scan').disabled = false;
    $('#scanner-status').className = 'w-3 h-3 bg-green-400 rounded-full mr-2';
    $('#scanner-text').textContent = '스캔 중';
    
    const interval = parseInt($('#scan-interval')?.value || '15') * 1000;
    
    log('🚀 실시간 스캐너 시작', 'success');
    toast('스캐너가 시작되었습니다', 'green');
    
    // 즉시 첫 스캔 실행
    performScan();
    
    // 정기적 스캔 시작
    scanTimer = setInterval(performScan, interval);
  }

  function stopScanner() {
    isScanning = false;
    $('#start-scan').disabled = false;
    $('#stop-scan').disabled = true;
    $('#scanner-status').className = 'w-3 h-3 bg-gray-500 rounded-full mr-2';
    $('#scanner-text').textContent = '대기 중';
    
    if (scanTimer) {
      clearInterval(scanTimer);
      scanTimer = null;
    }
    
    log('⏹ 실시간 스캐너 정지', 'info');
    toast('스캐너가 정지되었습니다', 'blue');
  }

  async function performScan() {
    if (!isScanning || watchlist.length === 0) return;
    
    const currentTime = new Date().toLocaleTimeString('ko-KR');
    $('#last-scan').textContent = currentTime;
    
    // 랜덤 종목 선택
    const symbol = getRandomElement(watchlist);
    const price = (Math.random() * 200 + 50).toFixed(2);
    const volume = Math.floor(Math.random() * 1000000 + 100000);
    
    // 30% 확률로 아톰 탐지
    if (Math.random() < 0.3) {
      const atom = getRandomElement(atoms);
      const grades = ['A++', 'A+', 'A', 'B+', 'B', 'C+', 'C'];
      const grade = getRandomElement(grades);
      
      atomsDetected++;
      
      const message = `${symbol}: ${atom.id} (${atom.name}) | $${price} | Vol: ${formatNumber(volume)} | 등급: ${grade}`;
      sidbLog(message);
      
      // 고등급 신호 체크
      if (['A++', 'A+', 'A'].includes(grade)) {
        highGradeSignals++;
        
        // 15% 확률로 분자 신호 생성
        if (Math.random() < 0.15) {
          const molecule = getRandomElement(molecules);
          signalsGenerated++;
          activeMolecules++;
          
          log(`🔥 분자 신호 생성: ${symbol} - ${molecule.id} (${molecule.name})`, 'success');
          toast(`🔥 ${symbol} 분자 신호 발생!`, 'red');
          
          $('#molecule-status').innerHTML = `
            <div class="text-green-400">
              <strong>${molecule.id}</strong> 활성 - ${symbol} (${grade})
            </div>
          `;
        }
      }
      
      updateKPIs();
    }
  }

  // 로그 지우기
  $('#clear-log').onclick = () => {
    $('#sidb-log').innerHTML = '';
    logCount = 0;
    $('#log-count').textContent = '0';
    toast('로그가 지워졌습니다', 'blue');
  };

  /* ══════════════════════════════════════════════════════════════════ */
  /* 설정 관리 */
  /* ══════════════════════════════════════════════════════════════════ */
  function loadSettings() {
    $('#alpaca-key').value = CFG.ALPACA_KEY;
    $('#alpaca-sec').value = CFG.ALPACA_SEC;
    $('#gemini-key').value = CFG.GEMINI_KEY;
    $('#sheet-id').value = CFG.SHEET_ID;
    $('#sheet-api').value = CFG.SHEET_API;
  }

  $('#save-set').onclick = () => {
    CFG.ALPACA_KEY = $('#alpaca-key').value.trim();
    CFG.ALPACA_SEC = $('#alpaca-sec').value.trim();
    CFG.GEMINI_KEY = $('#gemini-key').value.trim();
    CFG.SHEET_ID = $('#sheet-id').value.trim();
    CFG.SHEET_API = $('#sheet-api').value.trim();
    
    sessionStorage.setItem('settings', JSON.stringify(CFG));
    
    $('#set-msg').classList.remove('hidden');
    setTimeout(() => {
      $('#set-msg').classList.add('hidden');
    }, 3000);
    
    toast('설정이 저장되었습니다', 'green');
    log('API 설정 업데이트 완료', 'success');
  };

  $('#test-connection').onclick = async () => {
    toast('연결 테스트 중...', 'blue');
    
    // 시뮬레이션된 연결 테스트
    setTimeout(() => {
      const connections = ['alpaca-status', 'sheets-status', 'gemini-status'];
      connections.forEach((id, index) => {
        setTimeout(() => {
          const statusEl = $(`#${id} .status-indicator`);
          const isConnected = Math.random() > 0.3; // 70% 성공률
          statusEl.className = `status-indicator ${isConnected ? 'bg-green-400' : 'bg-red-400'}`;
        }, index * 500);
      });
      
      toast('연결 테스트 완료', 'green');
      log('API 연결 상태 확인 완료', 'success');
    }, 1500);
  };

  // 토글 스위치 이벤트
  $('#notifications-enabled').onchange = (e) => {
    const enabled = e.target.checked;
    log(`알림 ${enabled ? '활성화' : '비활성화'}`, 'info');
  };

  $('#dark-mode').onchange = (e) => {
    const darkMode = e.target.checked;
    log(`다크모드 ${darkMode ? '활성화' : '비활성화'}`, 'info');
    // 실제로는 여기서 테마 변경 로직 구현
  };

  /* ══════════════════════════════════════════════════════════════════ */
  /* 에러 핸들링 */
  /* ══════════════════════════════════════════════════════════════════ */
  window.onerror = (message, source, lineno, colno, error) => {
    log(`JavaScript 오류: ${message}`, 'error');
    if (typeof Sentry !== 'undefined') {
      Sentry.captureException(error);
    }
  };

  /* ══════════════════════════════════════════════════════════════════ */
  /* 초기화 완료 */
  /* ══════════════════════════════════════════════════════════════════ */
  console.log('🚀 AI 트레이딩 어시스턴트 V 5.5 로드 완료');

})();
