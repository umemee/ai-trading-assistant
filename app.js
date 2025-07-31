/**
 * app.js - AI Trading Assistant V5.5 Complete Frontend
 * GitHub Pages 완전 호환 버전 - 모든 초기화 문제 해결
 */

class TradingAssistant {
    constructor() {
        // 기본 설정
        this.websocket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.isScanning = false;
        this.watchlist = [];
        
        // 서버 URL 설정 (환경에 따라 자동 감지)
        this.serverUrl = this.detectServerUrl();
        this.websocketUrl = this.serverUrl.replace('http', 'ws') + '/ws';
        
        // 통계
        this.atomsDetected = 0;
        this.moleculesTriggered = 0;
        this.startTime = new Date();
        
        // 상태 관리
        this.systemInitialized = false;
        this.apiSettings = {};
        
        // 로그 버퍼
        this.logBuffer = [];
        this.maxLogEntries = 500;
        
        console.log('🚀 TradingAssistant V5.5 초기화 시작');
        
        // DOM이 준비되면 초기화
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    detectServerUrl() {
        // GitHub Pages vs 로컬 개발 환경 자동 감지
        const hostname = window.location.hostname;
        
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            return 'http://localhost:8000';
        } else if (hostname.includes('github.io')) {
            // GitHub Actions에서 배포된 백엔드 URL (환경에 따라 수정 필요)
            return 'https://your-backend-service.herokuapp.com'; // 실제 배포 URL로 변경
        } else {
            return 'http://localhost:8000';
        }
    }

    init() {
        try {
            console.log('🔧 DOM 초기화 시작');
            
            // 이벤트 핸들러 설정
            this.setupEventHandlers();
            
            // 저장된 설정 로드
            this.loadSettings();
            
            // 초기 화면 표시
            this.showSection('dashboard');
            
            // 상태 업데이트 시작
            this.startStatusUpdates();
            
            // 로그 시작
            this.addLog('시스템 초기화 완료', 'info');
            
            console.log('✅ TradingAssistant V5.5 초기화 완료');
            
        } catch (error) {
            console.error('❌ 초기화 오류:', error);
            this.addLog(`초기화 오류: ${error.message}`, 'error');
        }
    }

    setupEventHandlers() {
        try {
            // 패스워드 입력 관련
            const pwBtn = document.getElementById('pw-btn');
            if (pwBtn) {
                pwBtn.addEventListener('click', () => this.handleLogin());
            }
            
            const pwInput = document.getElementById('pw-input');
            if (pwInput) {
                pwInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') this.handleLogin();
                });
            }
            
            // API 설정 관련
            const testConnectionBtn = document.getElementById('test-connection-btn');
            if (testConnectionBtn) {
                testConnectionBtn.addEventListener('click', () => this.testAllConnections());
            }
            
            const saveApiBtn = document.getElementById('save-api-btn');
            if (saveApiBtn) {
                saveApiBtn.addEventListener('click', () => this.saveApiSettings());
            }
            
            // 스캐너 관련
            const startScannerBtn = document.getElementById('start-scanner-btn');
            if (startScannerBtn) {
                startScannerBtn.addEventListener('click', () => this.startScanner());
            }
            
            const stopScannerBtn = document.getElementById('stop-scanner-btn');
            if (stopScannerBtn) {
                stopScannerBtn.addEventListener('click', () => this.stopScanner());
            }
            
            // 종목 관리
            const addTickerBtn = document.getElementById('add-ticker-btn');
            if (addTickerBtn) {
                addTickerBtn.addEventListener('click', () => this.addTicker());
            }
            
            const tickerInput = document.getElementById('ticker-input');
            if (tickerInput) {
                tickerInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') this.addTicker();
                });
            }
            
            // AI 분석 관련
            const analyzeBtn = document.getElementById('analyze-btn');
            if (analyzeBtn) {
                analyzeBtn.addEventListener('click', () => this.requestAiAnalysis());
            }
            
            // WebSocket 연결 버튼
            const connectWsBtn = document.getElementById('connect-ws-btn');
            if (connectWsBtn) {
                connectWsBtn.addEventListener('click', () => this.connectWebSocket());
            }
            
            // 시스템 초기화 버튼
            const initSystemBtn = document.getElementById('init-system-btn');
            if (initSystemBtn) {
                initSystemBtn.addEventListener('click', () => this.initializeSystem());
            }
            
            console.log('📋 모든 이벤트 핸들러 설정 완료');
            
        } catch (error) {
            console.error('❌ 이벤트 핸들러 설정 오류:', error);
        }
    }

    // ================== 로그인 및 인증 ==================
    handleLogin() {
        try {
            const pwInput = document.getElementById('pw-input');
            const password = pwInput ? pwInput.value : '';
            
            // 간단한 패스워드 체크 (실제 운영에서는 더 강화된 인증 필요)
            if (password === 'admin123' || password === 'trading2025') {
                this.showSection('main');
                this.addLog('로그인 성공', 'success');
                
                // 자동으로 WebSocket 연결 시도
                setTimeout(() => this.connectWebSocket(), 1000);
            } else {
                alert('잘못된 패스워드입니다.');
                this.addLog('로그인 실패', 'error');
            }
        } catch (error) {
            console.error('로그인 오류:', error);
            this.addLog(`로그인 오류: ${error.message}`, 'error');
        }
    }

    // ================== WebSocket 연결 관리 ==================
    async connectWebSocket() {
        try {
            if (this.websocket) {
                this.websocket.close();
            }
            
            this.addLog(`WebSocket 연결 시도: ${this.websocketUrl}`, 'info');
            this.updateConnectionStatus('연결 중...', 'warning');
            
            this.websocket = new WebSocket(this.websocketUrl);
            
            this.websocket.onopen = () => {
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('연결됨', 'success');
                this.addLog('WebSocket 연결 성공', 'success');
                
                // 연결 후 시스템 상태 요청
                this.sendWebSocketMessage({
                    type: 'get_system_status'
                });
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (error) {
                    console.error('메시지 파싱 오류:', error);
                }
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket 오류:', error);
                this.addLog('WebSocket 연결 오류', 'error');
                this.updateConnectionStatus('연결 실패', 'error');
            };
            
            this.websocket.onclose = () => {
                this.isConnected = false;
                this.updateConnectionStatus('연결 끊어짐', 'error');
                this.addLog('WebSocket 연결 종료', 'warning');
                
                // 자동 재연결
                if (this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    setTimeout(() => {
                        this.addLog(`재연결 시도 ${this.reconnectAttempts}/${this.maxReconnectAttempts}`, 'info');
                        this.connectWebSocket();
                    }, 3000);
                }
            };
            
        } catch (error) {
            console.error('WebSocket 연결 실패:', error);
            this.addLog(`WebSocket 연결 실패: ${error.message}`, 'error');
            this.updateConnectionStatus('연결 실패', 'error');
        }
    }

    sendWebSocketMessage(message) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(message));
            return true;
        } else {
            this.addLog('WebSocket이 연결되지 않음', 'error');
            return false;
        }
    }

    handleWebSocketMessage(data) {
        try {
            const messageType = data.type;
            
            switch (messageType) {
                case 'system_status':
                    this.handleSystemStatus(data);
                    break;
                    
                case 'atom_signal':
                    this.handleAtomSignal(data);
                    break;
                    
                case 'molecule_signal':
                    this.handleMoleculeSignal(data);
                    break;
                    
                case 'system_initialized':
                    this.handleSystemInitialized(data);
                    break;
                    
                case 'scanner_started':
                    this.handleScannerStarted(data);
                    break;
                    
                case 'scanner_stopped':
                    this.handleScannerStopped(data);
                    break;
                    
                case 'connection_test_result':
                    this.handleConnectionTestResult(data);
                    break;
                    
                case 'analysis_result':
                    this.handleAnalysisResult(data);
                    break;
                    
                case 'error':
                    this.addLog(`서버 오류: ${data.message}`, 'error');
                    break;
                    
                default:
                    console.log('알 수 없는 메시지:', data);
            }
            
        } catch (error) {
            console.error('메시지 처리 오류:', error);
            this.addLog(`메시지 처리 오류: ${error.message}`, 'error');
        }
    }

    // ================== 메시지 핸들러들 ==================
    handleSystemStatus(data) {
        try {
            const status = data.system || data.status;
            
            // 시스템 상태 업데이트
            const isInitializedEl = document.getElementById('system-initialized');
            if (isInitializedEl) {
                isInitializedEl.textContent = status.is_initialized ? '✅ 완료' : '⏳ 대기중';
            }
            
            const isScanningEl = document.getElementById('system-scanning');
            if (isScanningEl) {
                isScanningEl.textContent = status.is_scanning ? '🟢 활성' : '🔴 비활성';
            }
            
            const tickerCountEl = document.getElementById('ticker-count');
            if (tickerCountEl) {
                tickerCountEl.textContent = status.watched_tickers ? status.watched_tickers.length : 0;
            }
            
            // 통계 업데이트
            const atomsCountEl = document.getElementById('atoms-count');
            if (atomsCountEl) {
                atomsCountEl.textContent = status.atoms_detected_total || 0;
            }
            
            const moleculesCountEl = document.getElementById('molecules-count');
            if (moleculesCountEl) {
                moleculesCountEl.textContent = status.molecules_triggered_total || 0;
            }
            
            // 업타임 업데이트
            const uptimeEl = document.getElementById('system-uptime');
            if (uptimeEl && status.uptime_seconds) {
                const hours = Math.floor(status.uptime_seconds / 3600);
                const minutes = Math.floor((status.uptime_seconds % 3600) / 60);
                uptimeEl.textContent = `${hours}시간 ${minutes}분`;
            }
            
            // 서비스 상태 업데이트
            if (status.services) {
                this.updateServiceStatus('sheets', status.services.sheets);
                this.updateServiceStatus('gemini', status.services.gemini);
                this.updateServiceStatus('alpaca', status.services.alpaca);
            }
            
            this.systemInitialized = status.is_initialized;
            this.isScanning = status.is_scanning;
            
        } catch (error) {
            console.error('시스템 상태 처리 오류:', error);
        }
    }

    handleAtomSignal(data) {
        try {
            this.atomsDetected++;
            
            // 시그널 표시 영역에 추가
            this.addSignalToDisplay({
                type: 'atom',
                ticker: data.ticker,
                id: data.atom_id,
                name: data.atom_name || data.atom_id,
                grade: data.grade,
                price: data.price,
                volume: data.volume,
                timestamp: data.timestamp
            });
            
            this.addLog(`🔴 아톰 신호: ${data.ticker} - ${data.atom_id} (${data.grade})`, 'atom');
            
            // 알림 재생 (선택사항)
            this.playNotificationSound('atom');
            
        } catch (error) {
            console.error('아톰 신호 처리 오류:', error);
        }
    }

    handleMoleculeSignal(data) {
        try {
            this.moleculesTriggered++;
            
            // 분자 신호 표시
            this.addSignalToDisplay({
                type: 'molecule',
                id: data.molecule_id,
                name: data.molecule_name,
                atoms: data.matched_atoms,
                grade: data.grade,
                match_ratio: data.match_ratio,
                timestamp: data.timestamp
            });
            
            this.addLog(`🔥 분자 신호: ${data.molecule_id} - ${data.molecule_name} (${data.grade})`, 'molecule');
            
            // 중요한 분자 신호는 강한 알림
            this.playNotificationSound('molecule');
            
            // 분자 신호는 더 강조해서 표시
            this.highlightMoleculeSignal(data);
            
        } catch (error) {
            console.error('분자 신호 처리 오류:', error);
        }
    }

    handleSystemInitialized(data) {
        try {
            this.systemInitialized = data.success;
            
            if (data.success) {
                this.addLog('✅ 시스템 초기화 성공', 'success');
                
                // 초기화 결과 표시
                if (data.results) {
                    Object.keys(data.results).forEach(service => {
                        const result = data.results[service];
                        const status = result.status === 'success' ? 'success' : 'error';
                        this.addLog(`${service}: ${result.message}`, status);
                    });
                }
            } else {
                this.addLog('❌ 시스템 초기화 실패', 'error');
            }
            
        } catch (error) {
            console.error('시스템 초기화 결과 처리 오류:', error);
        }
    }

    handleScannerStarted(data) {
        try {
            this.isScanning = true;
            this.watchlist = data.tickers || [];
            
            this.addLog(`🟢 스캐너 시작됨: ${this.watchlist.join(', ')}`, 'success');
            this.updateScannerButtons();
            this.updateWatchlist();
            
        } catch (error) {
            console.error('스캐너 시작 처리 오류:', error);
        }
    }

    handleScannerStopped(data) {
        try {
            this.isScanning = false;
            
            this.addLog('🔴 스캐너 정지됨', 'warning');
            this.updateScannerButtons();
            
        } catch (error) {
            console.error('스캐너 정지 처리 오류:', error);
        }
    }

    handleConnectionTestResult(data) {
        try {
            this.addLog('📡 연결 테스트 결과:', 'info');
            
            if (data.results) {
                Object.keys(data.results).forEach(service => {
                    const result = data.results[service];
                    const status = result.status === 'success' ? 'success' : 'error';
                    this.addLog(`${service}: ${result.message}`, status);
                    this.updateServiceStatus(service, result.status === 'success');
                });
            }
            
        } catch (error) {
            console.error('연결 테스트 결과 처리 오류:', error);
        }
    }

    handleAnalysisResult(data) {
        try {
            const result = data.result;
            
            if (result.success) {
                this.addLog(`🧠 AI 분석 완료: ${data.ticker}`, 'success');
                this.displayAnalysisResult(result);
            } else {
                this.addLog(`❌ AI 분석 실패: ${result.error}`, 'error');
            }
            
        } catch (error) {
            console.error('분석 결과 처리 오류:', error);
        }
    }

    // ================== API 설정 관리 ==================
    saveApiSettings() {
        try {
            const settings = {
                alpacaKey: document.getElementById('alpaca-key')?.value || '',
                alpacaSecret: document.getElementById('alpaca-secret')?.value || '',
                geminiKey: document.getElementById('gemini-key')?.value || '',
                sheetsId: document.getElementById('sheets-id')?.value || '',
                googleServiceAccountJson: document.getElementById('google-service-account')?.value || ''
            };
            
            // 로컬 스토리지에 저장 (암호화 권장)
            localStorage.setItem('tradingApiSettings', JSON.stringify(settings));
            this.apiSettings = settings;
            
            this.addLog('API 설정이 저장되었습니다', 'success');
            
            // 저장 후 자동으로 시스템 초기화 시도
            if (this.validateApiSettings(settings)) {
                setTimeout(() => this.initializeSystem(), 1000);
            }
            
        } catch (error) {
            console.error('API 설정 저장 오류:', error);
            this.addLog(`API 설정 저장 실패: ${error.message}`, 'error');
        }
    }

    loadSettings() {
        try {
            const savedSettings = localStorage.getItem('tradingApiSettings');
            if (savedSettings) {
                const settings = JSON.parse(savedSettings);
                this.apiSettings = settings;
                
                // UI에 설정값 복원
                if (document.getElementById('alpaca-key')) {
                    document.getElementById('alpaca-key').value = settings.alpacaKey || '';
                }
                if (document.getElementById('alpaca-secret')) {
                    document.getElementById('alpaca-secret').value = settings.alpacaSecret || '';
                }
                if (document.getElementById('gemini-key')) {
                    document.getElementById('gemini-key').value = settings.geminiKey || '';
                }
                if (document.getElementById('sheets-id')) {
                    document.getElementById('sheets-id').value = settings.sheetsId || '';
                }
                if (document.getElementById('google-service-account')) {
                    document.getElementById('google-service-account').value = settings.googleServiceAccountJson || '';
                }
                
                this.addLog('저장된 API 설정을 불러왔습니다', 'info');
            }
        } catch (error) {
            console.error('설정 로드 오류:', error);
            this.addLog(`설정 로드 실패: ${error.message}`, 'error');
        }
    }

    validateApiSettings(settings) {
        const required = ['alpacaKey', 'geminiKey', 'sheetsId'];
        const missing = required.filter(key => !settings[key] || settings[key].trim() === '');
        
        if (missing.length > 0) {
            this.addLog(`필수 설정 누락: ${missing.join(', ')}`, 'error');
            return false;
        }
        
        return true;
    }

    // ================== 시스템 제어 ==================
    async testAllConnections() {
        try {
            if (!this.isConnected) {
                this.addLog('WebSocket이 연결되지 않음', 'error');
                return;
            }
            
            this.addLog('📡 모든 연결 테스트 시작...', 'info');
            
            const success = this.sendWebSocketMessage({
                type: 'test_connection',
                api_settings: this.apiSettings
            });
            
            if (!success) {
                this.addLog('연결 테스트 요청 실패', 'error');
            }
            
        } catch (error) {
            console.error('연결 테스트 오류:', error);
            this.addLog(`연결 테스트 오류: ${error.message}`, 'error');
        }
    }

    async initializeSystem() {
        try {
            if (!this.isConnected) {
                this.addLog('WebSocket이 연결되지 않음 - 먼저 연결하세요', 'error');
                return;
            }
            
            if (!this.validateApiSettings(this.apiSettings)) {
                this.addLog('API 설정을 먼저 저장하세요', 'error');
                return;
            }
            
            this.addLog('🔧 시스템 초기화 시작...', 'info');
            
            const success = this.sendWebSocketMessage({
                type: 'initialize_system',
                api_settings: this.apiSettings
            });
            
            if (!success) {
                this.addLog('시스템 초기화 요청 실패', 'error');
            }
            
        } catch (error) {
            console.error('시스템 초기화 오류:', error);
            this.addLog(`시스템 초기화 오류: ${error.message}`, 'error');
        }
    }

    async startScanner() {
        try {
            if (!this.isConnected) {
                this.addLog('WebSocket이 연결되지 않음', 'error');
                return;
            }
            
            if (!this.systemInitialized) {
                this.addLog('시스템이 초기화되지 않음 - 먼저 초기화하세요', 'error');
                return;
            }
            
            if (this.watchlist.length === 0) {
                this.addLog('감시할 종목을 추가하세요', 'warning');
                return;
            }
            
            this.addLog(`🟢 스캐너 시작: ${this.watchlist.join(', ')}`, 'info');
            
            const success = this.sendWebSocketMessage({
                type: 'start_scanner',
                tickers: this.watchlist,
                api_settings: this.apiSettings
            });
            
            if (!success) {
                this.addLog('스캐너 시작 요청 실패', 'error');
            }
            
        } catch (error) {
            console.error('스캐너 시작 오류:', error);
            this.addLog(`스캐너 시작 오류: ${error.message}`, 'error');
        }
    }

    async stopScanner() {
        try {
            if (!this.isConnected) {
                this.addLog('WebSocket이 연결되지 않음', 'error');
                return;
            }
            
            this.addLog('🔴 스캐너 정지 요청...', 'info');
            
            const success = this.sendWebSocketMessage({
                type: 'stop_scanner'
            });
            
            if (!success) {
                this.addLog('스캐너 정지 요청 실패', 'error');
            }
            
        } catch (error) {
            console.error('스캐너 정지 오류:', error);
            this.addLog(`스캐너 정지 오류: ${error.message}`, 'error');
        }
    }

    // ================== 종목 관리 ==================
    addTicker() {
        try {
            const tickerInput = document.getElementById('ticker-input');
            if (!tickerInput) return;
            
            const ticker = tickerInput.value.trim().toUpperCase();
            if (!ticker) {
                this.addLog('종목 심볼을 입력하세요', 'warning');
                return;
            }
            
            if (this.watchlist.includes(ticker)) {
                this.addLog(`${ticker}는 이미 추가되어 있습니다`, 'warning');
                return;
            }
            
            this.watchlist.push(ticker);
            tickerInput.value = '';
            
            this.updateWatchlist();
            this.addLog(`${ticker} 추가됨`, 'success');
            
        } catch (error) {
            console.error('종목 추가 오류:', error);
            this.addLog(`종목 추가 오류: ${error.message}`, 'error');
        }
    }

    removeTicker(ticker) {
        try {
            const index = this.watchlist.indexOf(ticker);
            if (index > -1) {
                this.watchlist.splice(index, 1);
                this.updateWatchlist();
                this.addLog(`${ticker} 제거됨`, 'info');
            }
        } catch (error) {
            console.error('종목 제거 오류:', error);
        }
    }

    updateWatchlist() {
        try {
            const watchlistEl = document.getElementById('watchlist');
            if (!watchlistEl) return;
            
            watchlistEl.innerHTML = '';
            
            this.watchlist.forEach(ticker => {
                const tickerEl = document.createElement('div');
                tickerEl.className = 'ticker-item';
                tickerEl.innerHTML = `
                    <span class="ticker-symbol">${ticker}</span>
                    <button class="remove-ticker-btn" onclick="tradingAssistant.removeTicker('${ticker}')">×</button>
                `;
                watchlistEl.appendChild(tickerEl);
            });
            
            // 종목 수 업데이트
            const tickerCountEl = document.getElementById('ticker-count');
            if (tickerCountEl) {
                tickerCountEl.textContent = this.watchlist.length;
            }
            
        } catch (error) {
            console.error('감시 목록 업데이트 오류:', error);
        }
    }

    // ================== AI 분석 요청 ==================
    async requestAiAnalysis() {
        try {
            if (!this.isConnected) {
                this.addLog('WebSocket이 연결되지 않음', 'error');
                return;
            }
            
            const ticker = document.getElementById('analysis-ticker')?.value || '';
            const date = document.getElementById('analysis-date')?.value || new Date().toISOString().split('T')[0];
            const context = document.getElementById('analysis-context')?.value || '';
            
            if (!ticker || !context) {
                this.addLog('종목과 분석 컨텍스트를 입력하세요', 'warning');
                return;
            }
            
            this.addLog(`🧠 AI 분석 요청: ${ticker}`, 'info');
            
            const success = this.sendWebSocketMessage({
                type: 'request_analysis',
                ticker: ticker.toUpperCase(),
                date: date,
                context: context
            });
            
            if (!success) {
                this.addLog('AI 분석 요청 실패', 'error');
            }
            
        } catch (error) {
            console.error('AI 분석 요청 오류:', error);
            this.addLog(`AI 분석 요청 오류: ${error.message}`, 'error');
        }
    }

    displayAnalysisResult(result) {
        try {
            const analysisResultEl = document.getElementById('analysis-result');
            if (!analysisResultEl) return;
            
            let resultHtml = '<div class="analysis-result">';
            
            if (result.analysis) {
                resultHtml += `<h4>📊 분석 결과</h4>`;
                resultHtml += `<p>${result.analysis}</p>`;
            }
            
            if (result.suggested_atoms && result.suggested_atoms.length > 0) {
                resultHtml += `<h4>🔬 제안된 아톰</h4>`;
                result.suggested_atoms.forEach(atom => {
                    resultHtml += `
                        <div class="suggested-atom">
                            <strong>${atom.atom_id}</strong>: ${atom.atom_name}
                            <br><small>${atom.description}</small>
                        </div>
                    `;
                });
            }
            
            if (result.suggested_molecule) {
                const molecule = result.suggested_molecule;
                resultHtml += `<h4>🧬 제안된 분자</h4>`;
                resultHtml += `
                    <div class="suggested-molecule">
                        <strong>${molecule.molecule_id}</strong>: ${molecule.molecule_name}
                        <br><small>필요 아톰: ${molecule.required_atom_ids?.join(', ')}</small>
                        <br><small>매치 임계값: ${molecule.match_threshold}%</small>
                    </div>
                `;
            }
            
            resultHtml += '</div>';
            
            analysisResultEl.innerHTML = resultHtml;
            
        } catch (error) {
            console.error('분석 결과 표시 오류:', error);
        }
    }

    // ================== UI 업데이트 메서드들 ==================
    updateConnectionStatus(status, type) {
        try {
            const statusEl = document.getElementById('connection-status');
            if (statusEl) {
                statusEl.textContent = status;
                statusEl.className = `status-${type}`;
            }
        } catch (error) {
            console.error('연결 상태 업데이트 오류:', error);
        }
    }

    updateServiceStatus(serviceName, isConnected) {
        try {
            const statusEl = document.getElementById(`${serviceName}-status`);
            if (statusEl) {
                statusEl.textContent = isConnected ? '✅ 연결됨' : '❌ 오류';
                statusEl.className = isConnected ? 'status-success' : 'status-error';
            }
        } catch (error) {
            console.error('서비스 상태 업데이트 오류:', error);
        }
    }

    updateScannerButtons() {
        try {
            const startBtn = document.getElementById('start-scanner-btn');
            const stopBtn = document.getElementById('stop-scanner-btn');
            
            if (startBtn) {
                startBtn.disabled = this.isScanning;
            }
            if (stopBtn) {
                stopBtn.disabled = !this.isScanning;
            }
        } catch (error) {
            console.error('스캐너 버튼 업데이트 오류:', error);
        }
    }

    addSignalToDisplay(signal) {
        try {
            const signalsEl = document.getElementById('signals-display');
            if (!signalsEl) return;
            
            const signalEl = document.createElement('div');
            signalEl.className = `signal-item signal-${signal.type}`;
            
            const timestamp = new Date().toLocaleTimeString();
            
            if (signal.type === 'atom') {
                signalEl.innerHTML = `
                    <div class="signal-header">
                        <span class="signal-type">🔴 아톰</span>
                        <span class="signal-timestamp">${timestamp}</span>
                    </div>
                    <div class="signal-content">
                        <strong>${signal.ticker}</strong> - ${signal.name} (${signal.grade})
                        <br><small>가격: $${signal.price} | 거래량: ${signal.volume?.toLocaleString()}</small>
                    </div>
                `;
            } else if (signal.type === 'molecule') {
                signalEl.innerHTML = `
                    <div class="signal-header">
                        <span class="signal-type">🔥 분자</span>
                        <span class="signal-timestamp">${timestamp}</span>
                    </div>
                    <div class="signal-content">
                        <strong>${signal.name}</strong> (${signal.grade})
                        <br><small>매치율: ${signal.match_ratio?.toFixed(1)}% | 아톰: ${signal.atoms?.join(', ')}</small>
                    </div>
                `;
            }
            
            signalsEl.insertBefore(signalEl, signalsEl.firstChild);
            
            // 최대 50개 신호만 유지
            while (signalsEl.children.length > 50) {
                signalsEl.removeChild(signalsEl.lastChild);
            }
            
        } catch (error) {
            console.error('신호 표시 오류:', error);
        }
    }

    highlightMoleculeSignal(data) {
        try {
            // 중요한 분자 신호는 브라우저 알림 표시
            if (data.grade && ['A++', 'A+', 'A'].includes(data.grade)) {
                if (Notification.permission === 'granted') {
                    new Notification(`🔥 분자 신호: ${data.molecule_name}`, {
                        body: `등급: ${data.grade} | 매치율: ${data.match_ratio?.toFixed(1)}%`,
                        icon: '/favicon.ico'
                    });
                }
                
                // 화면 강조 효과
                document.body.style.backgroundColor = '#ffe6e6';
                setTimeout(() => {
                    document.body.style.backgroundColor = '';
                }, 2000);
            }
        } catch (error) {
            console.error('분자 신호 강조 오류:', error);
        }
    }

    playNotificationSound(type) {
        try {
            // 간단한 비프음 (Web Audio API 사용)
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            // 신호 타입별 다른 음색
            if (type === 'atom') {
                oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
            } else if (type === 'molecule') {
                oscillator.frequency.setValueAtTime(1200, audioContext.currentTime);
            }
            
            gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.3);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.3);
            
        } catch (error) {
            // 오디오 재생 실패는 무시 (권한 문제 등)
            console.log('알림음 재생 실패:', error.message);
        }
    }

    // ================== 로그 관리 ==================
    addLog(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = {
            timestamp,
            message,
            type
        };
        
        this.logBuffer.unshift(logEntry);
        
        // 최대 로그 개수 제한
        if (this.logBuffer.length > this.maxLogEntries) {
            this.logBuffer = this.logBuffer.slice(0, this.maxLogEntries);
        }
        
        this.updateLogDisplay();
        
        // 콘솔에도 출력
        console.log(`[${timestamp}] ${message}`);
    }

    updateLogDisplay() {
        try {
            const logEl = document.getElementById('log-display');
            if (!logEl) return;
            
            logEl.innerHTML = '';
            
            this.logBuffer.slice(0, 100).forEach(entry => {
                const logItemEl = document.createElement('div');
                logItemEl.className = `log-item log-${entry.type}`;
                logItemEl.innerHTML = `
                    <span class="log-timestamp">${entry.timestamp}</span>
                    <span class="log-message">${entry.message}</span>
                `;
                logEl.appendChild(logItemEl);
            });
            
            // 자동 스크롤
            logEl.scrollTop = 0;
            
        } catch (error) {
            console.error('로그 표시 오류:', error);
        }
    }

    // ================== 유틸리티 메서드들 ==================
    startStatusUpdates() {
        // 1초마다 상태 업데이트
        setInterval(() => {
            if (this.isConnected) {
                this.sendWebSocketMessage({ type: 'get_system_status' });
            }
        }, 10000); // 10초마다
        
        // 알림 권한 요청
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }

    exportLogs() {
        try {
            const logsText = this.logBuffer.map(entry => 
                `[${entry.timestamp}] ${entry.type.toUpperCase()}: ${entry.message}`
            ).join('\n');
            
            const blob = new Blob([logsText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = `trading_logs_${new Date().toISOString().split('T')[0]}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
            URL.revokeObjectURL(url);
            
            this.addLog('로그를 다운로드했습니다', 'success');
            
        } catch (error) {
            console.error('로그 내보내기 오류:', error);
            this.addLog(`로그 내보내기 실패: ${error.message}`, 'error');
        }
    }

    clearLogs() {
        this.logBuffer = [];
        this.updateLogDisplay();
        this.addLog('로그가 삭제되었습니다', 'info');
    }
}

// ================== 전역 함수들 ==================
// DOM 로드 완료 후 TradingAssistant 인스턴스 생성 및 전역 함수 정의
document.addEventListener('DOMContentLoaded', function() {
    // 전역 TradingAssistant 인스턴스 생성
    window.tradingAssistant = new TradingAssistant();
    
    // 전역 함수들 정의 (HTML에서 onclick 등으로 사용)
    window.showSection = function(sectionId) {
        try {
            // 모든 섹션 숨기기
            const sections = document.querySelectorAll('.section');
            sections.forEach(section => {
                section.style.display = 'none';
            });
            
            // 모든 네비게이션 버튼 비활성화
            const navButtons = document.querySelectorAll('.nav-btn');
            navButtons.forEach(btn => {
                btn.classList.remove('active');
            });
            
            // 선택된 섹션 표시
            const targetSection = document.getElementById(`${sectionId}-section`);
            if (targetSection) {
                targetSection.style.display = 'block';
            }
            
            // 해당 네비게이션 버튼 활성화
            const navButton = document.querySelector(`[onclick="showSection('${sectionId}')"]`);
            if (navButton) {
                navButton.classList.add('active');
            }
            
        } catch (error) {
            console.error('섹션 표시 오류:', error);
        }
    };
    
    window.addTicker = function() {
        if (window.tradingAssistant) {
            window.tradingAssistant.addTicker();
        }
    };
    
    window.exportLogs = function() {
        if (window.tradingAssistant) {
            window.tradingAssistant.exportLogs();
        }
    };
    
    window.clearLogs = function() {
        if (window.tradingAssistant && confirm('모든 로그를 삭제하시겠습니까?')) {
            window.tradingAssistant.clearLogs();
        }
    };
    
    // 초기 화면 설정
    showSection('dashboard');
    
    console.log('✅ 모든 전역 함수 및 TradingAssistant 준비 완료');
});

// 페이지 언로드 시 WebSocket 연결 정리
window.addEventListener('beforeunload', function() {
    if (window.tradingAssistant && window.tradingAssistant.websocket) {
        window.tradingAssistant.websocket.close();
    }
});

// 에러 처리
window.addEventListener('error', function(event) {
    console.error('전역 오류:', event.error);
    if (window.tradingAssistant) {
        window.tradingAssistant.addLog(`시스템 오류: ${event.error.message}`, 'error');
    }
});

// 미처리 Promise 에러 처리
window.addEventListener('unhandledrejection', function(event) {
    console.error('미처리 Promise 거부:', event.reason);
    if (window.tradingAssistant) {
        window.tradingAssistant.addLog(`Promise 오류: ${event.reason}`, 'error');
    }
});

console.log('🚀 AI Trading Assistant V5.5 Frontend - 모든 모듈 로드 완료');
