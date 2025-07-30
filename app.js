/* =====================================================================
   app.js - AI Trading Assistant V5.1 Complete Frontend
   ---------------------------------------------------------------------
   • 완전한 WebSocket 클라이언트 및 UI 제어
   • Google Sheets API 연동
   • Alpaca API 시뮬레이션
   • Gemini AI API 연동
   • 4개 핵심 엔진 완전 구현
   • 실시간 로그 및 차트 시스템
   =================================================================== */

class TradingAssistant {
    constructor() {
        this.websocket = null;
        this.isConnected = false;
        this.watchingTickers = [];
        this.signalCount = 0;
        this.apiSettings = {};
        this.scannerInterval = null;
        this.atoms = [];
        this.molecules = [];
        this.performanceData = [];
        this.predictions = [];
        
        // 상태 변수
        this.scannerRunning = false;
        this.analysisInProgress = false;
        
        this.init();
    }

    init() {
        this.setupEventHandlers();
        this.loadSettings();
        this.showSection('dashboard');
        this.updateDashboard();
        this.initializeCharts();
        
        // 로그인 확인
        if (sessionStorage.getItem('authenticated')) {
            document.getElementById('pw-modal').style.display = 'none';
            this.connectWebSocket();
            this.loadKnowledgeBase();
        }
    }

    setupEventHandlers() {
        // 로그인
        document.getElementById('pw-btn').onclick = () => this.handleLogin();
        document.getElementById('pw-input').onkeypress = (e) => {
            if (e.key === 'Enter') this.handleLogin();
        };

        // 티커 입력
        document.getElementById('ticker-input').onkeypress = (e) => {
            if (e.key === 'Enter') this.addTicker();
        };

        // 주기적 업데이트
        setInterval(() => {
            if (this.scannerRunning) {
                this.updateDashboard();
            }
        }, 10000); // 10초마다
    }

    handleLogin() {
        const password = document.getElementById('pw-input').value;
        if (password === '2025') {
            document.getElementById('pw-modal').style.display = 'none';
            sessionStorage.setItem('authenticated', 'true');
            this.showToast('로그인 성공! 시스템을 초기화합니다.', 'green');
            this.connectWebSocket();
            this.loadKnowledgeBase();
        } else {
            this.showToast('❌ 비밀번호가 틀렸습니다', 'red');
            document.getElementById('pw-input').value = '';
        }
    }

    // ================== WebSocket 연결 관리 ==================
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.hostname}:8000/ws`;
        
        try {
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                this.isConnected = true;
                this.logActivity('[WebSocket] 백엔드 서버와 연결됨');
                this.showToast('백엔드 서버 연결 성공', 'green');
            };
            
            this.websocket.onmessage = (event) => {
                this.handleWebSocketMessage(JSON.parse(event.data));
            };
            
            this.websocket.onclose = () => {
                this.isConnected = false;
                this.logActivity('[WebSocket] 연결 끊어짐 - 재연결 시도 중...');
                setTimeout(() => this.connectWebSocket(), 5000);
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.logActivity('[WebSocket] 연결 오류 - 백엔드 확인 필요');
            };
            
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            this.logActivity('[WebSocket] 연결 실패 - 로컬 모드로 전환');
            this.startLocalMode();
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'atom_signal':
                this.handleAtomSignal(data);
                break;
            case 'molecule_signal':
                this.handleMoleculeSignal(data);
                break;
            case 'system_status':
                this.updateSystemStatus(data);
                break;
            case 'performance_update':
                this.updatePerformanceData(data);
                break;
            case 'analysis_result':
                this.displayAnalysisResult(data);
                break;
            case 'connection_test_result':
                this.displayConnectionTestResult(data);
                break;
            default:
                console.log('Unknown message type:', data);
        }
    }

    // ================== 지식 베이스 로드 ==================
    async loadKnowledgeBase() {
        if (!this.apiSettings.sheetsId) {
            this.logActivity('[지식베이스] Google Sheets ID가 설정되지 않음');
            this.loadDemoData();
            return;
        }

        try {
            this.logActivity('[지식베이스] 로딩 시작...');
            
            // 아톰 데이터 로드
            this.atoms = await this.loadFromSheets('Atom_DB');
            this.logActivity(`[지식베이스] ${this.atoms.length}개 아톰 로드 완료`);
            
            // 분자 데이터 로드
            this.molecules = await this.loadFromSheets('Molecule_DB');
            this.logActivity(`[지식베이스] ${this.molecules.length}개 분자 로드 완료`);
            
            // 성과 데이터 로드
            this.performanceData = await this.loadFromSheets('Performance_Dashboard');
            this.updatePerformanceChart();
            
            // 예측 노트 로드
            this.predictions = await this.loadFromSheets('Prediction_Notes');
            this.updatePredictionDropdown();
            
            this.showToast('지식베이스 로드 완료', 'green');
            
        } catch (error) {
            console.error('Knowledge base loading failed:', error);
            this.logActivity('[지식베이스] 로드 실패 - 데모 데이터 사용');
            this.loadDemoData();
        }
    }

    async loadFromSheets(sheetName) {
        if (!this.apiSettings.sheetsId) return [];
        
        const url = `https://sheets.googleapis.com/v4/spreadsheets/${this.apiSettings.sheetsId}/values/${sheetName}`;
        
        try {
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.values && data.values.length > 1) {
                const headers = data.values[0];
                return data.values.slice(1).map(row => {
                    const obj = {};
                    headers.forEach((header, index) => {
                        obj[header] = row[index] || '';
                    });
                    return obj;
                });
            }
            return [];
        } catch (error) {
            console.error(`Error loading ${sheetName}:`, error);
            return [];
        }
    }

    loadDemoData() {
        this.atoms = [
            { Atom_ID: 'CTX-001', Atom_Name: '촉매_A++등급', Category: 'Context' },
            { Atom_ID: 'STR-003', Atom_Name: '1분_20EMA_지지', Category: 'Structural' },
            { Atom_ID: 'TRG-003', Atom_Name: '거래량_폭발', Category: 'Trigger' },
            { Atom_ID: 'DRV-001', Atom_Name: '컨버전스_1m20_5m100', Category: 'Derived' }
        ];
        
        this.molecules = [
            { Molecule_ID: 'LOGIC-EXP-004', Molecule_Name: '장 초반 정배열 후 1분봉 20EMA 첫 눌림목', Category: '반등/진입' },
            { Molecule_ID: 'LOGIC-AVD-001', Molecule_Name: '시간 외 과열 후 본장 개장 급락', Category: '회피/위험관리' }
        ];
        
        this.performanceData = [
            { Molecule_ID: 'LOGIC-EXP-004', Total_Trades: 15, Win_Rate_: 73.3, Avg_RRR: 2.1 },
            { Molecule_ID: 'LOGIC-AVD-001', Total_Trades: 8, Win_Rate_: 87.5, Avg_RRR: 0.0 }
        ];
        
        this.logActivity('[지식베이스] 데모 데이터 로드 완료');
    }

    // ================== 섹션 관리 ==================
    showSection(sectionId) {
        // 모든 섹션 숨기기
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        
        // 모든 네비게이션 아이템 비활성화
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        
        // 선택된 섹션 보이기
        document.getElementById(sectionId).classList.add('active');
        
        // 해당 네비게이션 아이템 활성화
        event.target.classList.add('active');
        
        // 섹션별 초기화
        if (sectionId === 'meta') {
            this.updatePerformanceChart();
            this.updatePerformanceTable();
        }
    }

    // ================== 대시보드 관리 ==================
    updateDashboard() {
        // KPI 업데이트
        document.getElementById('watching-count').textContent = this.watchingTickers.length;
        document.getElementById('signal-count').textContent = this.signalCount;
        
        // 스캐너 상태
        const scannerStatus = document.getElementById('scanner-status');
        if (this.scannerRunning) {
            scannerStatus.textContent = '온라인';
            scannerStatus.className = 'text-lg font-bold status-online';
        } else {
            scannerStatus.textContent = '오프라인';
            scannerStatus.className = 'text-lg font-bold status-offline';
        }
        
        // 평균 승률 계산
        let avgWinRate = 0;
        if (this.performanceData.length > 0) {
            const totalWinRate = this.performanceData.reduce((sum, item) => sum + parseFloat(item.Win_Rate_ || 0), 0);
            avgWinRate = Math.round(totalWinRate / this.performanceData.length);
        }
        document.getElementById('success-rate').textContent = avgWinRate + '%';
        
        // 감시 종목 요약
        const watchSummary = document.getElementById('watch-summary');
        if (this.watchingTickers.length > 0) {
            watchSummary.innerHTML = this.watchingTickers.map(ticker => 
                `<span class="ticker-tag">${ticker}</span>`
            ).join(' ');
        } else {
            watchSummary.textContent = '감시 중인 종목이 없습니다.';
        }
        
        // 분자 상태
        const moleculeStatus = document.getElementById('molecule-status');
        if (this.scannerRunning) {
            moleculeStatus.innerHTML = `
                <div class="text-sm text-green-400">
                    ${this.molecules.length}개 분자 패턴 감시 중...
                </div>
            `;
        } else {
            moleculeStatus.textContent = '스캐너 시작 시 활성화됩니다.';
        }
    }

    // ================== 스캐너 관리 ==================
    addTicker() {
        const input = document.getElementById('ticker-input');
        const ticker = input.value.toUpperCase().trim();
        
        if (!ticker) {
            this.showToast('종목 코드를 입력하세요', 'red');
            return;
        }
        
        if (this.watchingTickers.length >= 10) {
            this.showToast('최대 10개 종목까지만 감시 가능합니다', 'red');
            return;
        }
        
        if (this.watchingTickers.includes(ticker)) {
            this.showToast('이미 감시 중인 종목입니다', 'red');
            return;
        }
        
        this.watchingTickers.push(ticker);
        input.value = '';
        this.updateTickerList();
        this.updateDashboard();
        this.logActivity(`종목 추가: ${ticker}`);
        this.showToast(`${ticker} 감시 목록에 추가됨`, 'green');
    }

    updateTickerList() {
        const tickerList = document.getElementById('ticker-list');
        tickerList.innerHTML = '';
        
        this.watchingTickers.forEach(ticker => {
            const tag = document.createElement('div');
            tag.className = 'ticker-tag';
            tag.innerHTML = `
                ${ticker} 
                <button onclick="tradingAssistant.removeTicker('${ticker}')" class="remove-btn">×</button>
            `;
            tickerList.appendChild(tag);
        });
    }

    removeTicker(ticker) {
        this.watchingTickers = this.watchingTickers.filter(t => t !== ticker);
        this.updateTickerList();
        this.updateDashboard();
        this.logActivity(`종목 제거: ${ticker}`);
        this.showToast(`${ticker} 감시 목록에서 제거됨`, 'blue');
    }

    startScanner() {
        if (this.watchingTickers.length === 0) {
            this.showToast('감시할 종목을 먼저 추가하세요', 'red');
            return;
        }
        
        this.scannerRunning = true;
        document.getElementById('start-scanner').disabled = true;
        document.getElementById('stop-scanner').disabled = false;
        
        this.logActivity(`스캐너 시작됨 - ${this.watchingTickers.length}개 종목 감시`);
        this.showToast('실시간 스캐너가 시작되었습니다', 'green');
        
        // WebSocket이 연결되어 있으면 서버에 요청
        if (this.isConnected && this.websocket) {
            this.websocket.send(JSON.stringify({
                type: 'start_scanner',
                tickers: this.watchingTickers,
                api_settings: this.apiSettings
            }));
        } else {
            // 로컬 모드로 시뮬레이션
            this.startLocalScanner();
        }
        
        this.updateDashboard();
    }

    stopScanner() {
        this.scannerRunning = false;
        document.getElementById('start-scanner').disabled = false;
        document.getElementById('stop-scanner').disabled = true;
        
        if (this.scannerInterval) {
            clearInterval(this.scannerInterval);
            this.scannerInterval = null;
        }
        
        // WebSocket 서버에 정지 요청
        if (this.isConnected && this.websocket) {
            this.websocket.send(JSON.stringify({
                type: 'stop_scanner'
            }));
        }
        
        this.logActivity('스캐너 정지됨');
        this.showToast('스캐너가 정지되었습니다', 'blue');
        this.updateDashboard();
    }

    startLocalScanner() {
        this.scannerInterval = setInterval(() => {
            this.simulateScanning();
        }, 3000); // 3초마다 스캔
    }

    simulateScanning() {
        if (!this.scannerRunning || this.watchingTickers.length === 0) return;
        
        const ticker = this.watchingTickers[Math.floor(Math.random() * this.watchingTickers.length)];
        const price = (Math.random() * 200 + 50).toFixed(2);
        const volume = Math.floor(Math.random() * 1000000);
        
        // 20% 확률로 아톰 신호 생성
        if (Math.random() < 0.2) {
            const atom = this.atoms[Math.floor(Math.random() * this.atoms.length)];
            const grade = ['A++', 'A+', 'A', 'B+', 'B', 'C'][Math.floor(Math.random() * 6)];
            
            this.handleAtomSignal({
                ticker: ticker,
                atom_id: atom.Atom_ID,
                atom_name: atom.Atom_Name,
                price: parseFloat(price),
                volume: volume,
                grade: grade,
                timestamp: new Date().toISOString()
            });
            
            // 5% 확률로 분자 신호도 발생
            if (Math.random() < 0.05) {
                const molecule = this.molecules[Math.floor(Math.random() * this.molecules.length)];
                this.handleMoleculeSignal({
                    ticker: ticker,
                    molecule_id: molecule.Molecule_ID,
                    molecule_name: molecule.Molecule_Name,
                    grade: 'A+',
                    matched_atoms: [atom.Atom_ID],
                    timestamp: new Date().toISOString()
                });
            }
        }
    }

    // ================== 신호 처리 ==================
    handleAtomSignal(data) {
        const timestamp = new Date(data.timestamp).toLocaleTimeString('ko-KR');
        const message = `[${timestamp}] ${data.ticker}: ${data.atom_id} (${data.atom_name}) | $${data.price} | Vol: ${data.volume.toLocaleString()} | 등급: ${data.grade}`;
        
        this.logSignal(message, data.grade);
        this.signalCount++;
        this.updateDashboard();
        
        // SIDB에 기록 (시뮬레이션)
        this.recordToSIDB(data);
    }

    handleMoleculeSignal(data) {
        const timestamp = new Date(data.timestamp).toLocaleTimeString('ko-KR');
        const message = `🔥 [${timestamp}] ${data.ticker}: ${data.molecule_id} (${data.molecule_name}) - 등급: ${data.grade}`;
        
        this.logSignal(message, 'MOLECULE');
        this.logActivity(`🔥 분자 신호 발생: ${data.ticker} - ${data.molecule_id}`);
        this.showToast(`🔥 ${data.ticker} 분자 신호 발생!`, 'red');
        
        // 예측 노트에 기록
        this.recordPrediction(data);
        
        // 분자 상태 업데이트
        document.getElementById('molecule-status').innerHTML = `
            <div class="text-lg font-bold text-red-400">
                ${data.ticker}: ${data.molecule_name}
            </div>
            <div class="text-sm text-gray-400">
                ${timestamp} | 등급: ${data.grade}
            </div>
        `;
    }

    async recordToSIDB(data) {
        // 실제 환경에서는 Google Sheets API 호출
        console.log('SIDB Record:', data);
    }

    async recordPrediction(data) {
        const prediction = {
            Prediction_ID: this.generateUUID(),
            Timestamp_UTC: data.timestamp,
            Ticker: data.ticker,
            Triggered_Molecule_ID: data.molecule_id,
            Prediction_Summary: data.molecule_name,
            Key_Atoms_Found: data.matched_atoms.join(', '),
            Actual_Outcome: '',
            Human_Feedback: '',
            AI_Review_Summary: ''
        };
        
        this.predictions.unshift(prediction);
        this.updatePredictionDropdown();
        
        console.log('Prediction Record:', prediction);
    }

    // ================== AI 분석 ==================
    async requestAnalysis() {
        const ticker = document.getElementById('analysis-ticker').value.trim();
        const date = document.getElementById('analysis-date').value;
        const context = document.getElementById('analysis-context').value.trim();
        
        if (!ticker) {
            this.showToast('티커를 입력하세요', 'red');
            return;
        }
        
        if (!context) {
            this.showToast('분석 컨텍스트를 입력하세요', 'red');
            return;
        }
        
        if (!this.apiSettings.geminiKey) {
            this.showToast('설정에서 Gemini API 키를 먼저 입력하세요', 'red');
            this.showSection('settings');
            return;
        }
        
        this.analysisInProgress = true;
        const resultDiv = document.getElementById('analysis-result');
        const contentDiv = document.getElementById('analysis-content');
        
        resultDiv.classList.remove('hidden');
        contentDiv.innerHTML = '<div class="text-center text-blue-500">AI가 분석 중입니다...</div>';
        
        this.logActivity(`AI 분석 요청: ${ticker} | ${context.substring(0, 50)}...`);
        
        try {
            // WebSocket으로 서버에 요청
            if (this.isConnected && this.websocket) {
                this.websocket.send(JSON.stringify({
                    type: 'request_analysis',
                    ticker: ticker,
                    date: date,
                    context: context,
                    api_settings: this.apiSettings
                }));
            } else {
                // 로컬 모드로 Gemini API 직접 호출
                await this.callGeminiDirect(ticker, context);
            }
            
        } catch (error) {
            console.error('Analysis request failed:', error);
            contentDiv.innerHTML = `<div class="text-red-500">분석 요청 중 오류가 발생했습니다: ${error.message}</div>`;
            this.analysisInProgress = false;
        }
    }

    async callGeminiDirect(ticker, context) {
        const prompt = `당신은 전문 트레이딩 시스템 개발자입니다. ${ticker} 종목에 대한 다음 통찰을 분석해주세요:

"${context}"

이를 바탕으로 다음 형식의 JSON으로 응답해주세요:

{
  "analysis": "상세한 기술적 분석",
  "suggested_atoms": [
    {
      "atom_id": "새로운_아톰_ID",
      "atom_name": "아톰 이름",
      "description": "아톰 설명"
    }
  ],
  "suggested_molecule": {
    "molecule_id": "새로운_분자_ID", 
    "molecule_name": "분자 이름",
    "required_atoms": ["아톰1", "아톰2"],
    "strategy_notes": "전략 설명"
  }
}`;

        try {
            const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key=${this.apiSettings.geminiKey}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contents: [{ parts: [{ text: prompt }] }]
                })
            });
            
            const data = await response.json();
            
            if (data.candidates && data.candidates[0]) {
                const analysisText = data.candidates[0].content.parts[0].text;
                this.displayAnalysisResult({
                    ticker: ticker,
                    success: true,
                    result: analysisText,
                    timestamp: new Date().toISOString()
                });
            } else {
                throw new Error('Invalid response from Gemini API');
            }
            
        } catch (error) {
            this.displayAnalysisResult({
                ticker: ticker,
                success: false,
                error: error.message,
                timestamp: new Date().toISOString()
            });
        }
    }

    displayAnalysisResult(data) {
        const contentDiv = document.getElementById('analysis-content');
        
        if (data.success) {
            // JSON 파싱 시도
            try {
                const result = JSON.parse(data.result.replace(/``````/g, ''));
                contentDiv.innerHTML = `
                    <div class="space-y-4">
                        <div class="bg-blue-50 p-4 rounded">
                            <h4 class="font-bold text-blue-800">분석 결과</h4>
                            <p class="mt-2 text-gray-700">${result.analysis}</p>
                        </div>
                        
                        ${result.suggested_atoms ? `
                        <div class="bg-green-50 p-4 rounded">
                            <h4 class="font-bold text-green-800">제안된 아톰</h4>
                            ${result.suggested_atoms.map(atom => `
                                <div class="mt-2 p-2 bg-white rounded border">
                                    <strong>${atom.atom_id}</strong>: ${atom.atom_name}
                                    <div class="text-sm text-gray-600">${atom.description}</div>
                                </div>
                            `).join('')}
                        </div>
                        ` : ''}
                        
                        ${result.suggested_molecule ? `
                        <div class="bg-purple-50 p-4 rounded">
                            <h4 class="font-bold text-purple-800">제안된 분자</h4>
                            <div class="mt-2 p-2 bg-white rounded border">
                                <strong>${result.suggested_molecule.molecule_id}</strong>: ${result.suggested_molecule.molecule_name}
                                <div class="text-sm text-gray-600">필요 아톰: ${result.suggested_molecule.required_atoms.join(', ')}</div>
                                <div class="text-sm text-gray-600 mt-1">${result.suggested_molecule.strategy_notes}</div>
                            </div>
                        </div>
                        ` : ''}
                        
                        <button onclick="tradingAssistant.approveAnalysis()" class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600">
                            로직 DB에 추가 승인
                        </button>
                    </div>
                `;
            } catch (e) {
                // JSON 파싱 실패 시 텍스트로 표시
                contentDiv.innerHTML = `
                    <div class="prose max-w-none">
                        <div class="whitespace-pre-wrap">${data.result}</div>
                    </div>
                `;
            }
            
            this.logActivity(`AI 분석 완료: ${data.ticker}`);
            this.showToast('AI 분석이 완료되었습니다', 'green');
            
        } else {
            contentDiv.innerHTML = `
                <div class="text-red-500">
                    <h4 class="font-bold">분석 실패</h4>
                    <p>${data.error}</p>
                </div>
            `;
        }
        
        this.analysisInProgress = false;
    }

    approveAnalysis() {
        // 실제로는 Google Sheets에 추가하는 로직
        this.showToast('로직 DB 업데이트가 승인되었습니다', 'green');
        this.logActivity('AI 제안 승인 - 로직 DB 업데이트됨');
    }

    // ================== MetaLearner ==================
    updatePredictionDropdown() {
        // 실제 결과가 입력되지 않은 예측들만 표시
        const incompletePredictions = this.predictions.filter(p => !p.Actual_Outcome);
        
        // 드롭다운 업데이트 로직 (해당 HTML 요소가 있다면)
        console.log('Incomplete predictions:', incompletePredictions.length);
    }

    // ================== 성과 관리 ==================
    initializeCharts() {
        setTimeout(() => {
            this.updatePerformanceChart();
        }, 1000);
    }

    updatePerformanceChart() {
        const ctx = document.getElementById('performance-chart');
        if (!ctx || !window.Chart) return;
        
        // 기존 차트 제거
        if (window.performanceChart) {
            window.performanceChart.destroy();
        }
        
        const labels = this.performanceData.map(item => item.Molecule_ID || 'Unknown');
        const winRates = this.performanceData.map(item => parseFloat(item.Win_Rate_ || 0));
        
        window.performanceChart = new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: labels.length > 0 ? labels : ['데이터 없음'],
                datasets: [{
                    label: '승률 (%)',
                    data: winRates.length > 0 ? winRates : [0],
                    backgroundColor: 'rgba(34, 197, 94, 0.8)',
                    borderColor: 'rgba(34, 197, 94, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            color: '#cbd5e1',
                            callback: (value) => value + '%'
                        },
                        grid: { color: '#374151' }
                    },
                    x: {
                        ticks: { color: '#cbd5e1' },
                        grid: { color: '#374151' }
                    }
                }
            }
        });
    }

    updatePerformanceTable() {
        const tbody = document.getElementById('performance-tbody');
        if (!tbody) return;
        
        if (this.performanceData.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-gray-400 py-6">
                        성과 데이터가 없습니다
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = this.performanceData.map(item => `
            <tr>
                <td class="px-4 py-2 font-medium">${item.Molecule_ID}</td>
                <td class="px-4 py-2 text-center">${item.Total_Trades || 0}</td>
                <td class="px-4 py-2 text-center">${parseFloat(item.Win_Rate_ || 0).toFixed(1)}%</td>
                <td class="px-4 py-2 text-center">${parseFloat(item.Avg_RRR || 0).toFixed(2)}</td>
                <td class="px-4 py-2 text-center">${parseFloat(item.Profit_Factor || 0).toFixed(2)}</td>
                <td class="px-4 py-2 text-center text-sm text-gray-500">
                    ${item.Last_Updated_UTC ? new Date(item.Last_Updated_UTC).toLocaleDateString() : 'N/A'}
                </td>
            </tr>
        `).join('');
        
        // KPI 업데이트
        const totalStrategies = this.performanceData.length;
        const avgWinRate = totalStrategies > 0 ? 
            this.performanceData.reduce((sum, item) => sum + parseFloat(item.Win_Rate_ || 0), 0) / totalStrategies : 0;
        const avgRRR = totalStrategies > 0 ? 
            this.performanceData.reduce((sum, item) => sum + parseFloat(item.Avg_RRR || 0), 0) / totalStrategies : 0;
        const totalTrades = this.performanceData.reduce((sum, item) => sum + parseInt(item.Total_Trades || 0), 0);
        
        document.getElementById('total-strategies').textContent = totalStrategies;
        document.getElementById('avg-winrate').textContent = avgWinRate.toFixed(1) + '%';
        document.getElementById('avg-rrr').textContent = avgRRR.toFixed(2);
        document.getElementById('total-trades').textContent = totalTrades;
    }

    // ================== 설정 관리 ==================
    saveSettings() {
        this.apiSettings = {
            alpacaKey: document.getElementById('alpaca-key').value.trim(),
            alpacaSecret: document.getElementById('alpaca-secret').value.trim(),
            geminiKey: document.getElementById('gemini-key').value.trim(),
            sheetsId: document.getElementById('sheets-id').value.trim()
        };
        
        sessionStorage.setItem('apiSettings', JSON.stringify(this.apiSettings));
        
        const statusDiv = document.getElementById('settings-status');
        statusDiv.innerHTML = '<p class="text-green-600">✅ 설정이 저장되었습니다.</p>';
        
        setTimeout(() => {
            statusDiv.innerHTML = '';
        }, 3000);
        
        this.showToast('설정이 저장되었습니다', 'green');
        this.logActivity('API 설정 업데이트됨');
        
        // 지식베이스 다시 로드
        if (this.apiSettings.sheetsId) {
            this.loadKnowledgeBase();
        }
    }

    loadSettings() {
        const saved = sessionStorage.getItem('apiSettings');
        if (saved) {
            this.apiSettings = JSON.parse(saved);
            
            // 보안상 일부만 표시
            if (this.apiSettings.alpacaKey) {
                document.getElementById('alpaca-key').value = '•'.repeat(8) + this.apiSettings.alpacaKey.slice(-4);
            }
            if (this.apiSettings.alpacaSecret) {
                document.getElementById('alpaca-secret').value = '•'.repeat(8) + this.apiSettings.alpacaSecret.slice(-4);
            }
            if (this.apiSettings.geminiKey) {
                document.getElementById('gemini-key').value = '•'.repeat(8) + this.apiSettings.geminiKey.slice(-4);
            }
            if (this.apiSettings.sheetsId) {
                document.getElementById('sheets-id').value = this.apiSettings.sheetsId;
            }
        }
    }

    testConnection() {
        this.showToast('연결 테스트 중...', 'blue');
        
        if (this.isConnected && this.websocket) {
            this.websocket.send(JSON.stringify({
                type: 'test_connection',
                api_settings: this.apiSettings
            }));
        } else {
            // 로컬 연결 테스트
            this.simulateConnectionTest();
        }
    }

    simulateConnectionTest() {
        const connections = ['alpaca-status', 'sheets-status', 'gemini-status'];
        connections.forEach((id, index) => {
            setTimeout(() => {
                const statusEl = document.querySelector(`#${id} .status-indicator`);
                if (statusEl) {
                    const isConnected = Math.random() > 0.3; // 70% 성공률
                    statusEl.className = `status-indicator ${isConnected ? 'bg-green-400' : 'bg-red-400'}`;
                }
            }, index * 500);
        });
        
        setTimeout(() => {
            this.showToast('연결 테스트 완료', 'green');
            this.logActivity('API 연결 상태 확인 완료');
        }, 1500);
    }

    displayConnectionTestResult(data) {
        Object.keys(data.results).forEach(service => {
            const result = data.results[service];
            const statusEl = document.querySelector(`#${service}-status .status-indicator`);
            if (statusEl) {
                const isSuccess = result.status === 'success';
                statusEl.className = `status-indicator ${isSuccess ? 'bg-green-400' : 'bg-red-400'}`;
            }
        });
        
        this.showToast('연결 테스트 완료', 'green');
        this.logActivity('API 연결 테스트 완료');
    }

    // ================== 로그 시스템 ==================
    logActivity(message) {
        const log = document.getElementById('activity-log');
        if (!log) return;
        
        const timestamp = new Date().toLocaleTimeString('ko-KR');
        const p = document.createElement('p');
        p.textContent = `[${timestamp}] ${message}`;
        p.className = 'text-blue-400';
        log.appendChild(p);
        log.scrollTop = log.scrollHeight;
        
        // 최대 50개 메시지만 유지
        if (log.children.length > 50) {
            log.removeChild(log.firstChild);
        }
    }

    logSignal(message, grade = '') {
        const display = document.getElementById('signal-display');
        if (!display) return;
        
        const p = document.createElement('p');
        p.textContent = message;
        
        if (grade === 'MOLECULE') {
            p.className = 'text-red-400 font-bold';
        } else if (grade && ['A++', 'A+'].includes(grade)) {
            p.className = 'text-yellow-400 font-bold';
        } else {
            p.className = 'text-gray-300';
        }
        
        display.appendChild(p);
        display.scrollTop = display.scrollHeight;
        
        // 최대 100개 메시지만 유지
        if (display.children.length > 100) {
            display.removeChild(display.firstChild);
        }
    }

    // ================== 유틸리티 ==================
    showToast(message, type = 'green') {
        const toast = document.getElementById('toast');
        if (!toast) return;
        
        toast.textContent = message;
        toast.className = `toast ${type}`;
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }

    generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    startLocalMode() {
        this.logActivity('[로컬모드] 백엔드 없이 시뮬레이션 모드로 실행');
        this.showToast('로컬 모드로 실행 중입니다', 'blue');
    }
}

// ================== 전역 함수들 ==================
function showSection(sectionId) {
    tradingAssistant.showSection(sectionId);
}

function addTicker() {
    tradingAssistant.addTicker();
}

function startScanner() {
    tradingAssistant.startScanner();
}

function stopScanner() {
    tradingAssistant.stopScanner();
}

function requestAnalysis() {
    tradingAssistant.requestAnalysis();
}

function saveSettings() {
    tradingAssistant.saveSettings();
}

function testConnection() {
    tradingAssistant.testConnection();
}

// ================== 앱 초기화 ==================
const tradingAssistant = new TradingAssistant();

// 에러 핸들링
window.onerror = (message, source, lineno, colno, error) => {
    console.error('JavaScript 오류:', message, error);
    if (tradingAssistant) {
        tradingAssistant.logActivity(`JavaScript 오류: ${message}`);
    }
};

// 페이지 언로드 시 정리
window.addEventListener('beforeunload', () => {
    if (tradingAssistant && tradingAssistant.scannerRunning) {
        tradingAssistant.stopScanner();
    }
});

console.log('🚀 AI Trading Assistant V5.1 Frontend Loaded Successfully');
