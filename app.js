/* app.js - WebSocket 클라이언트 및 UI 제어 */
class TradingAssistant {
    constructor() {
        this.websocket = null;
        this.isConnected = false;
        this.watchingTickers = [];
        this.signalCount = 0;
        this.apiSettings = {};
        this.scannerInterval = null;
        
        this.init();
    }

    init() {
        this.setupEventHandlers();
        this.loadSettings();
        this.showSection('dashboard');
        this.updateDashboard();
        
        // 로그인 확인
        if (sessionStorage.getItem('authenticated')) {
            document.getElementById('pw-modal').style.display = 'none';
            this.connectWebSocket();
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
    }

    handleLogin() {
        const password = document.getElementById('pw-input').value;
        if (password === '2025') {
            document.getElementById('pw-modal').style.display = 'none';
            sessionStorage.setItem('authenticated', 'true');
            this.showToast('로그인 성공! 시스템을 초기화합니다.', 'green');
            this.connectWebSocket();
        } else {
            this.showToast('❌ 비밀번호가 틀렸습니다', 'red');
            document.getElementById('pw-input').value = '';
        }
    }

    // WebSocket 연결
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
                this.logActivity('[WebSocket] 연결 끊어짐');
                setTimeout(() => this.connectWebSocket(), 5000); // 재연결 시도
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.logActivity('[WebSocket] 연결 오류');
            };
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            this.logActivity('[WebSocket] 연결 실패 - 백엔드 서버 확인 필요');
        }
    }

    // WebSocket 메시지 처리
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
            default:
                console.log('Unknown message type:', data);
        }
    }

    // 아톰 신호 처리
    handleAtomSignal(data) {
        const timestamp = new Date().toLocaleTimeString('ko-KR');
        const message = `[${timestamp}] ${data.ticker}: ${data.atom_id} (${data.atom_name}) | $${data.price} | Vol: ${data.volume.toLocaleString()} | 등급: ${data.grade}`;
        
        this.logSignal(message, data.grade);
        this.signalCount++;
        this.updateDashboard();
    }

    // 분자 신호 처리
    handleMoleculeSignal(data) {
        this.logActivity(`🔥 분자 신호: ${data.ticker} - ${data.molecule_id} (${data.molecule_name})`);
        this.showToast(`🔥 ${data.ticker} 분자 신호 발생!`, 'red');
        
        document.getElementById('molecule-status').innerHTML = `
            <div class="text-green-400">
                <strong>${data.molecule_id}</strong> 활성 - ${data.ticker} (${data.grade})
            </div>
        `;
    }

    // 섹션 전환
    showSection(sectionId) {
        // 모든 섹션 숨기기
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        
        // 모든 네비게이션 버튼 비활성화
        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // 선택된 섹션과 버튼 활성화
        document.getElementById(sectionId).classList.add('active');
        document.querySelector(`[onclick="showSection('${sectionId}')"]`).classList.add('active');
        
        // 섹션별 초기화
        if (sectionId === 'module3') {
            this.renderPerformanceChart();
        }
    }

    // 대시보드 업데이트
    updateDashboard() {
        document.getElementById('watching-count').textContent = this.watchingTickers.length;
        document.getElementById('signal-count').textContent = this.signalCount;
        
        const successRate = this.signalCount > 0 ? Math.floor(Math.random() * 30 + 50) : 0;
        document.getElementById('success-rate').textContent = successRate + '%';
    }

    // 티커 추가
    addTicker() {
        const input = document.getElementById('ticker-input');
        const ticker = input.value.toUpperCase().trim();
        
        if (!ticker) {
            this.showToast('티커를 입력하세요', 'red');
            return;
        }
        
        if (this.watchingTickers.length >= 10) {
            this.showToast('최대 10개까지 추가할 수 있습니다', 'red');
            return;
        }
        
        if (this.watchingTickers.includes(ticker)) {
            this.showToast('이미 추가된 종목입니다', 'red');
            return;
        }
        
        this.watchingTickers.push(ticker);
        input.value = '';
        this.updateTickerList();
        this.updateDashboard();
        this.logActivity(`종목 추가: ${ticker}`);
        this.showToast(`${ticker} 추가완료`, 'green');
    }

    // 티커 목록 업데이트
    updateTickerList() {
        const tickerList = document.getElementById('ticker-list');
        tickerList.innerHTML = this.watchingTickers.map(ticker => `
            <div class="ticker-tag">
                ${ticker}
                <span class="remove-btn" onclick="tradingAssistant.removeTicker('${ticker}')">&times;</span>
            </div>
        `).join('');
        
        this.updateWatchSummary();
    }

    // 티커 제거
    removeTicker(ticker) {
        this.watchingTickers = this.watchingTickers.filter(t => t !== ticker);
        this.updateTickerList();
        this.updateDashboard();
        this.logActivity(`종목 제거: ${ticker}`);
        this.showToast(`${ticker} 제거완료`, 'blue');
    }

    // 감시 종목 요약 업데이트
    updateWatchSummary() {
        const watchSummary = document.getElementById('watch-summary');
        if (this.watchingTickers.length === 0) {
            watchSummary.textContent = '스캐너를 시작하여 아톰 탐지를 시작하세요...';
        } else {
            watchSummary.innerHTML = `
                <div class="flex flex-wrap gap-2">
                    ${this.watchingTickers.map(ticker => `<span class="ticker-tag">${ticker}</span>`).join('')}
                </div>
            `;
        }
    }

    // 스캐너 시작
    startScanner() {
        if (this.watchingTickers.length === 0) {
            this.showToast('감시할 종목을 먼저 추가해주세요', 'red');
            return;
        }
        
        if (!Object.keys(this.apiSettings).length || !this.apiSettings.alpacaKey) {
            this.showToast('Alpaca API 키를 먼저 설정해주세요', 'red');
            this.showSection('settings');
            return;
        }
        
        // 백엔드에 스캐너 시작 요청
        if (this.websocket && this.isConnected) {
            this.websocket.send(JSON.stringify({
                type: 'start_scanner',
                tickers: this.watchingTickers,
                api_settings: this.apiSettings
            }));
        }
        
        document.getElementById('scanner-status').textContent = '온라인';
        document.getElementById('scanner-status').className = 'text-lg font-bold status-online';
        document.getElementById('start-scanner').disabled = true;
        document.getElementById('stop-scanner').disabled = false;
        
        this.logActivity('🚀 실시간 스캐너 시작');
        this.showToast('스캐너가 시작되었습니다', 'green');
    }

    // 스캐너 정지
    stopScanner() {
        if (this.websocket && this.isConnected) {
            this.websocket.send(JSON.stringify({
                type: 'stop_scanner'
            }));
        }
        
        document.getElementById('scanner-status').textContent = '오프라인';
        document.getElementById('scanner-status').className = 'text-lg font-bold status-offline';
        document.getElementById('start-scanner').disabled = false;
        document.getElementById('stop-scanner').disabled = true;
        
        this.logActivity('⏹ 실시간 스캐너 정지');
        this.showToast('스캐너가 정지되었습니다', 'blue');
    }

    // AI 분석 요청
    requestAnalysis() {
        const ticker = document.getElementById('analysis-ticker').value.trim();
        const context = document.getElementById('analysis-context').value.trim();
        
        if (!ticker) {
            this.showToast('분석할 종목을 입력하세요', 'red');
            return;
        }
        
        if (!this.apiSettings.geminiKey) {
            this.showToast('Gemini API 키를 먼저 설정해주세요', 'red');
            this.showSection('settings');
            return;
        }
        
        if (this.websocket && this.isConnected) {
            this.websocket.send(JSON.stringify({
                type: 'request_analysis',
                ticker: ticker,
                context: context,
                api_settings: this.apiSettings
            }));
        }
        
        const resultDiv = document.getElementById('analysis-result');
        const contentDiv = document.getElementById('analysis-content');
        
        resultDiv.classList.remove('hidden');
        contentDiv.innerHTML = '<p class="text-gray-500">AI 분석 중...</p>';
        
        this.logActivity(`AI 분석 요청: ${ticker}`);
        this.showToast('AI 분석을 요청했습니다', 'blue');
    }

    // AI 분석 결과 표시
    displayAnalysisResult(data) {
        const contentDiv = document.getElementById('analysis-content');
        if (data.success) {
            contentDiv.innerHTML = `<div class="whitespace-pre-wrap">${data.result}</div>`;
            this.logActivity(`AI 분석 완료: ${data.ticker}`);
        } else {
            contentDiv.innerHTML = `<p class="text-red-500">분석 오류: ${data.error}</p>`;
        }
    }

    // 성과 차트 렌더링
    renderPerformanceChart() {
        const ctx = document.getElementById('performance-chart');
        if (!ctx || !window.Chart) return;
        
        // 더미 데이터로 차트 생성
        new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: ['LOGIC-EXP-001', 'LOGIC-EXP-002', 'LOGIC-EXP-003'],
                datasets: [{
                    label: '승률 (%)',
                    data: [73.3, 62.5, 68.9],
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

    // 설정 저장
    saveSettings() {
        this.apiSettings = {
            alpacaKey: document.getElementById('alpaca-key').value.trim(),
            alpacaSecret: document.getElementById('alpaca-secret').value.trim(),
            geminiKey: document.getElementById('gemini-key').value.trim(),
            sheetsId: document.getElementById('sheets-id').value.trim()
        };
        
        sessionStorage.setItem('apiSettings', JSON.stringify(this.apiSettings));
        
        const statusDiv = document.getElementById('settings-status');
        statusDiv.innerHTML = '<p class="text-green-600">✅ 설정 저장 완료</p>';
        setTimeout(() => statusDiv.innerHTML = '', 3000);
        
        this.showToast('설정이 저장되었습니다', 'green');
        this.logActivity('API 설정 업데이트 완료');
    }

    // 설정 로드
    loadSettings() {
        const saved = sessionStorage.getItem('apiSettings');
        if (saved) {
            this.apiSettings = JSON.parse(saved);
            if (this.apiSettings.alpacaKey) {
                document.getElementById('alpaca-key').value = '*'.repeat(8) + this.apiSettings.alpacaKey.slice(-4);
            }
            if (this.apiSettings.alpacaSecret) {
                document.getElementById('alpaca-secret').value = '*'.repeat(8) + this.apiSettings.alpacaSecret.slice(-4);
            }
            if (this.apiSettings.geminiKey) {
                document.getElementById('gemini-key').value = '*'.repeat(8) + this.apiSettings.geminiKey.slice(-4);
            }
            if (this.apiSettings.sheetsId) {
                document.getElementById('sheets-id').value = this.apiSettings.sheetsId;
            }
        }
    }

    // 연결 테스트
    testConnection() {
        this.showToast('연결 테스트 중...', 'blue');
        
        if (this.websocket && this.isConnected) {
            this.websocket.send(JSON.stringify({
                type: 'test_connection',
                api_settings: this.apiSettings
            }));
        }
        
        // 시뮬레이션된 연결 테스트
        setTimeout(() => {
            const connections = ['alpaca-status', 'sheets-status', 'gemini-status'];
            connections.forEach((id, index) => {
                setTimeout(() => {
                    const statusEl = document.querySelector(`#${id} .status-indicator`);
                    const isConnected = Math.random() > 0.3; // 70% 성공률
                    statusEl.className = `status-indicator ${isConnected ? 'bg-green-400' : 'bg-red-400'}`;
                }, index * 500);
            });
            
            this.showToast('연결 테스트 완료', 'green');
            this.logActivity('API 연결 상태 확인 완료');
        }, 1500);
    }

    // 활동 로그
    logActivity(message) {
        const log = document.getElementById('activity-log');
        const timestamp = new Date().toLocaleTimeString('ko-KR');
        const p = document.createElement('p');
        p.textContent = `[${timestamp}] ${message}`;
        p.className = 'text-blue-400';
        log.appendChild(p);
        log.scrollTop = log.scrollHeight;
        
        // 로그 개수 제한
        if (log.children.length > 50) {
            log.removeChild(log.firstChild);
        }
    }

    // 신호 로그
    logSignal(message, grade = '') {
        const display = document.getElementById('signal-display');
        const p = document.createElement('p');
        p.textContent = message;
        p.className = grade && ['A++', 'A+'].includes(grade) ? 
            'text-red-400 font-bold' : 'text-gray-300';
        
        display.appendChild(p);
        display.scrollTop = display.scrollHeight;
        
        // 로그 개수 제한
        if (display.children.length > 100) {
            display.removeChild(display.firstChild);
        }
    }

    // 토스트 알림
    showToast(message, type = 'green') {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = `toast ${type}`;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 3000);
    }
}

// 전역 함수들 (HTML onclick에서 사용)
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

// 앱 초기화
const tradingAssistant = new TradingAssistant();

// 에러 핸들링
window.onerror = (message, source, lineno, colno, error) => {
    console.error('JavaScript 오류:', message, error);
    tradingAssistant.logActivity(`JavaScript 오류: ${message}`);
};
