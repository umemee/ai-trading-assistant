/**
 * app.js - AI Trading Assistant V6.0 (기능 완전 복원 버전)
 * - LogicDiscoverer, MetaLearner, ApprovalWorkflow UI 및 백엔드 연동
 * - 누락되었던 핵심 기능(로그, 알림, 신호관리, WebSocket, 설정 등) 모두 복원
 * - 2025-08-01 최종 통합본
 */

// ⚡️ 전역 컨텍스트
class TradingAssistant {
    constructor() {
        this.websocket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.isScanning = false;
        this.watchlist = [];
        this.systemInitialized = false;
        this.apiSettings = {};
        this.logBuffer = [];
        this.maxLogEntries = 500;
        this.moleculesTriggered = 0;
        this.atomsDetected = 0;
        this.startTime = new Date();

        // UI 상태
        this.approvalQueue = [];
        this.pendingPredictions = [];

        console.log('🚀 TradingAssistant V6.0 초기화 시작');

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    detectServerUrl() {
        const hostname = window.location.hostname;
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            return 'http://localhost:8000';
        } else if (hostname.includes('github.io')) {
            // TODO: 실제 배포된 백엔드 URL로 변경해야 합니다.
            return 'https://umemee.github.io/ai-trading-assistant/ws';
        } else {
            return 'http://localhost:8000';
        }
    }

    init() {
        try {
            this.serverUrl = this.detectServerUrl();
            this.websocketUrl = this.serverUrl.replace('http', 'ws') + '/ws';
            this.setupEventHandlers();
            this.loadSettings();
            this.showSection('dashboard');
            this.startStatusUpdates();
            this.addLog('시스템 초기화 완료', 'info');

            // 추가: 초기 Approval/MetaLearner 데이터 로딩
            this.refreshApprovalQueue();
            this.refreshPendingPredictions();

            console.log('✅ TradingAssistant V6.0 초기화 완료');
        } catch (error) {
            console.error('❌ 초기화 오류:', error);
            this.addLog(`초기화 오류: ${error.message}`, 'error');
        }
    }

    setupEventHandlers() {
        try {
            document.getElementById('pw-btn')?.addEventListener('click', () => this.handleLogin());
            document.getElementById('pw-input')?.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.handleLogin();
            });

            document.getElementById('test-connection-btn')?.addEventListener('click', () => this.testAllConnections());
            document.getElementById('save-api-btn')?.addEventListener('click', () => this.saveApiSettings());
            document.getElementById('start-scanner-btn')?.addEventListener('click', () => this.startScanner());
            document.getElementById('stop-scanner-btn')?.addEventListener('click', () => this.stopScanner());
            document.getElementById('add-ticker-btn')?.addEventListener('click', () => this.addTicker());
            document.getElementById('ticker-input')?.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.addTicker();
            });

            document.getElementById('analyze-btn')?.addEventListener('click', () => this.requestAiAnalysis());
            document.getElementById('connect-ws-btn')?.addEventListener('click', () => this.connectWebSocket());
            document.getElementById('init-system-btn')?.addEventListener('click', () => this.initializeSystem());

            // ApprovalWorkflow & MetaLearner의 동적 버튼 이벤트는 각 render 함수에서 바인딩됩니다.

            console.log('📋 모든 이벤트 핸들러 설정 완료');
        } catch (error) {
            console.error('❌ 이벤트 핸들러 설정 오류:', error);
        }
    }

    handleLogin() {
        try {
            const pwInput = document.getElementById('pw-input');
            const password = pwInput ? pwInput.value : '';

            if (password === 'admin123' || password === '2025') {
                this.showSection('main');
                this.addLog('로그인 성공', 'success');
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

    async connectWebSocket() {
        try {
            if (this.websocket) this.websocket.close();

            this.addLog(`WebSocket 연결 시도: ${this.websocketUrl}`, 'info');
            this.updateConnectionStatus('연결 중...', 'warning');

            this.websocket = new WebSocket(this.websocketUrl);

            this.websocket.onopen = () => {
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus('연결됨', 'success');
                this.addLog('WebSocket 연결 성공', 'success');
                this.sendWebSocketMessage({ type: 'get_system_status' });
                this.refreshApprovalQueue();
                this.refreshPendingPredictions();
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
                case 'approval_queue':
                    this.handleApprovalQueue(data);
                    break;
                case 'pending_predictions':
                    this.handlePendingPredictions(data);
                    break;
                case 'prediction_review_result':
                    this.handlePredictionReviewResult(data);
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

    // ================== WebSocket 메시지 핸들러들 ==================

    handleSystemStatus(data) {
        const status = data.system || data.status;
        if (!status) return;

        document.getElementById('system-initialized').textContent = status.is_initialized ? '✅ 완료' : '⏳ 대기중';
        document.getElementById('system-scanning').textContent = status.is_scanning ? '🟢 활성' : '🔴 비활성';
        document.getElementById('ticker-count').textContent = status.watched_tickers ? status.watched_tickers.length : 0;
        document.getElementById('atoms-count').textContent = status.atoms_detected_total || 0;
        document.getElementById('molecules-count').textContent = status.molecules_triggered_total || 0;

        if (status.uptime_seconds) {
            const hours = Math.floor(status.uptime_seconds / 3600);
            const minutes = Math.floor((status.uptime_seconds % 3600) / 60);
            document.getElementById('system-uptime').textContent = `${hours}시간 ${minutes}분`;
        }

        if (status.services) {
            this.updateServiceStatus('sheets', status.services.sheets);
            this.updateServiceStatus('gemini', status.services.gemini);
            this.updateServiceStatus('alpaca', status.services.alpaca);
        }

        this.systemInitialized = status.is_initialized;
        this.isScanning = status.is_scanning;
    }

    handleAtomSignal(data) {
        this.atomsDetected++;
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
        this.playNotificationSound('atom');
    }

    handleMoleculeSignal(data) {
        this.moleculesTriggered++;
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
        this.playNotificationSound('molecule');
        this.highlightMoleculeSignal(data);
    }

    handleSystemInitialized(data) {
        this.systemInitialized = data.success;
        this.addLog(data.success ? '✅ 시스템 초기화 성공' : '❌ 시스템 초기화 실패', data.success ? 'success' : 'error');

        if (data.results) {
            Object.keys(data.results).forEach(service => {
                const result = data.results[service];
                this.addLog(`${service}: ${result.message}`, result.status);
            });
        }
    }

    handleScannerStarted(data) {
        this.isScanning = true;
        this.watchlist = data.tickers || [];
        this.addLog(`🟢 스캐너 시작됨: ${this.watchlist.join(', ')}`, 'success');
        this.updateScannerButtons();
        this.updateWatchlist();
    }

    handleScannerStopped(data) {
        this.isScanning = false;
        this.addLog('🔴 스캐너 정지됨', 'warning');
        this.updateScannerButtons();
    }

    handleConnectionTestResult(data) {
        this.addLog('📡 연결 테스트 결과:', 'info');
        if (data.results) {
            Object.keys(data.results).forEach(service => {
                const result = data.results[service];
                this.updateServiceStatus(service, result.status === 'success');
                this.addLog(`${service}: ${result.message}`, result.status);
            });
        }
    }

    // ================== ApprovalWorkflow (검역 큐) ==================

    async refreshApprovalQueue() {
        if (!this.isConnected) return;
        this.sendWebSocketMessage({ type: 'get_approval_queue' });
    }

    handleApprovalQueue(data) {
        if (!data.queue) return;
        this.approvalQueue = data.queue;
        this.renderApprovalQueue();
    }

    renderApprovalQueue() {
        const approvalTableBody = document.querySelector('#approval-table tbody');
        if (!approvalTableBody) return;

        approvalTableBody.innerHTML = '';

        const queue = this.approvalQueue;
        if (!queue.length) {
            approvalTableBody.innerHTML = '<tr><td colspan="6" class="text-center text-gray-500">검토할 분자가 없습니다</td></tr>';
            return;
        }

        queue.forEach(item => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';

            const priorityBadge = this.getPriorityBadge(item.priority);
            const statusBadge = this.getStatusBadge(item.wfo_status);

            row.innerHTML = `
                <td class="px-4 py-3 text-sm font-medium text-gray-900">${item.molecule_id}</td>
                <td class="px-4 py-3 text-sm text-gray-700">${item.molecule_name || '이름 없음'}</td>
                <td class="px-4 py-3 text-sm">${statusBadge}</td>
                <td class="px-4 py-3 text-sm">${priorityBadge}</td>
                <td class="px-4 py-3 text-sm text-gray-600">${this.formatDate(item.created_date)}</td>
                <td class="px-4 py-3 text-sm space-x-2">
                    <button onclick="tradingAssistant.approveMolecule('${item.molecule_id}')" 
                            class="btn-sm btn-green">승인</button>
                    <button onclick="tradingAssistant.rejectMolecule('${item.molecule_id}')" 
                            class="btn-sm btn-red">거부</button>
                    <button onclick="tradingAssistant.viewMoleculeDetails('${item.molecule_id}')" 
                            class="btn-sm btn-blue">상세</button>
                </td>
            `;

            approvalTableBody.appendChild(row);
        });
    }

    async approveMolecule(moleculeId) {
        const reviewer = prompt('승인자 이름을 입력하세요:');
        if (!reviewer) return;

        const notes = prompt('승인 사유 (선택사항):') || '';

        this.sendWebSocketMessage({
            type: 'approve_molecule',
            molecule_id: moleculeId,
            reviewer: reviewer,
            notes: notes
        });

        this.addLog(`분자 승인 요청: ${moleculeId}`, 'info');
    }

    async rejectMolecule(moleculeId) {
        const reviewer = prompt('검토자 이름을 입력하세요:');
        if (!reviewer) return;

        const reason = prompt('거부 사유를 입력하세요 (필수):');
        if (!reason) {
            alert('거부 사유는 필수입니다.');
            return;
        }

        this.sendWebSocketMessage({
            type: 'reject_molecule',
            molecule_id: moleculeId,
            reviewer: reviewer,
            reason: reason
        });

        this.addLog(`분자 거부 요청: ${moleculeId}`, 'warning');
    }

    viewMoleculeDetails(moleculeId) {
        const molecule = this.approvalQueue.find(m => m.molecule_id === moleculeId);
        if (!molecule) return;

        const detailsHtml = `
            <div class="molecule-details">
                <h4>분자 상세 정보</h4>
                <p><strong>ID:</strong> ${molecule.molecule_id}</p>
                <p><strong>이름:</strong> ${molecule.molecule_name || '없음'}</p>
                <p><strong>필수 아톰:</strong> ${molecule.required_atoms?.join(', ') || '없음'}</p>
                <p><strong>매치 임계값:</strong> ${molecule.match_threshold}%</p>
                <p><strong>번역 노트:</strong> ${molecule.translation_notes || '없음'}</p>
                <p><strong>WFO 점수:</strong> ${molecule.wfo_score || 'N/A'}</p>
                <p><strong>생성일:</strong> ${this.formatDate(molecule.created_date)}</p>
            </div>
        `;

        this.showModal('분자 상세 정보', detailsHtml);
    }

    // ================== MetaLearner (예측 복기) ==================

    async refreshPendingPredictions() {
        if (!this.isConnected) return;
        this.sendWebSocketMessage({ type: 'get_pending_predictions' });
    }

    handlePendingPredictions(data) {
        if (!data.predictions) return;
        this.pendingPredictions = data.predictions;
        this.renderPendingPredictions();
    }

    renderPendingPredictions() {
        const predictionTableBody = document.querySelector('#prediction-table tbody');
        if (!predictionTableBody) return;

        predictionTableBody.innerHTML = '';

        const predictions = this.pendingPredictions;
        if (!predictions.length) {
            predictionTableBody.innerHTML = '<tr><td colspan="6" class="text-center text-gray-500">복기할 예측이 없습니다</td></tr>';
            return;
        }

        predictions.forEach(prediction => {
            const row = document.createElement('tr');
            row.className = 'hover:bg-gray-50';

            row.innerHTML = `
                <td class="px-4 py-3 text-sm font-medium text-gray-900">${prediction.ticker}</td>
                <td class="px-4 py-3 text-sm text-gray-700">${prediction.molecule_id}</td>
                <td class="px-4 py-3 text-sm text-gray-600">${prediction.prediction_summary}</td>
                <td class="px-4 py-3 text-sm text-gray-600">${prediction.key_atoms?.join(', ') || ''}</td>
                <td class="px-4 py-3 text-sm text-gray-600">${this.formatDate(prediction.timestamp)}</td>
                <td class="px-4 py-3 text-sm space-x-2">
                    <button onclick="tradingAssistant.reviewPrediction('${prediction.prediction_id}')" 
                            class="btn-sm btn-purple">복기</button>
                </td>
            `;

            predictionTableBody.appendChild(row);
        });
    }

    async reviewPrediction(predictionId) {
        const prediction = this.pendingPredictions.find(p => p.prediction_id === predictionId);
        if (!prediction) return;

        const actualOutcome = prompt('실제 결과를 입력하세요 (성공/실패 및 상세 설명):');
        if (!actualOutcome) return;

        const humanFeedback = prompt('인간의 추가 피드백 (선택사항):') || '';

        this.sendWebSocketMessage({
            type: 'review_prediction',
            prediction_id: predictionId,
            actual_outcome: actualOutcome,
            human_feedback: humanFeedback
        });

        this.addLog(`예측 복기 요청: ${prediction.ticker} - ${prediction.molecule_id}`, 'info');
    }

    handlePredictionReviewResult(data) {
        if (!data.success) {
            this.addLog(`예측 복기 실패: ${data.error}`, 'error');
            return;
        }

        const result = data.result;
        let resultHtml = `
            <div class="prediction-review-result">
                <h4>AI 복기 분석 결과</h4>
                <div class="ai-analysis">
                    <h5>AI 진단 리포트</h5>
                    <p>${result.analysis.replace(/\n/g, '<br>')}</p>
                </div>
        `;

        if (result.review_summary) {
            resultHtml += `
                <div class="review-summary">
                    <h5>복기 요약</h5>
                    <p>${data.review_summary}</p>
                </div>
            `;
        }

        if (data.improvement_suggestions?.new_avoidance_molecule) {
            const molecule = data.improvement_suggestions.new_avoidance_molecule;
            resultHtml += `
                <div class="new-molecule-suggestion">
                    <h5>신규 회피 분자 제안</h5>
                    <p><strong>ID:</strong> ${molecule.Molecule_ID}</p>
                    <p><strong>이름:</strong> ${molecule.Molecule_Name}</p>
                    <p><strong>설명:</strong> ${molecule.Translation_Notes}</p>
                </div>
            `;
        }

        resultHtml += '</div>';

        this.showModal('예측 복기 결과', resultHtml);
        this.addLog('✅ 예측 복기 완료', 'success');
        this.refreshPendingPredictions();
    }

    // ================== 분석 (LogicDiscoverer) ==================

    async requestAiAnalysis() {
        const ticker = document.getElementById('analysis-ticker')?.value?.trim();
        const date = document.getElementById('analysis-date')?.value;
        const insight = document.getElementById('analysis-insight')?.value?.trim();

        if (!ticker || !date || !insight) {
            alert('모든 필드를 입력해주세요.');
            return;
        }

        this.sendWebSocketMessage({
            type: 'request_analysis',
            ticker: ticker,
            date: date,
            user_insight: insight
        });

        this.addLog(`AI 분석 요청: ${ticker} (${date})`, 'info');
        
        // UI 업데이트
        const resultDiv = document.getElementById('analysis-result');
        if (resultDiv) {
            resultDiv.innerHTML = '<div class="loading">AI가 분석 중입니다...</div>';
            resultDiv.style.display = 'block';
        }
    }

    handleAnalysisResult(data) {
        const resultDiv = document.getElementById('analysis-result');
        if (!resultDiv) return;

        if (!data.success) {
            resultDiv.innerHTML = `<div class="error">분석 실패: ${data.error}</div>`;
            this.addLog(`AI 분석 실패: ${data.error}`, 'error');
            return;
        }

        const result = data.result;
        let resultHtml = `
            <div class="analysis-result">
                <h4>AI 분석 결과</h4>
                <div class="analysis-content">
                    <h5>통찰 번역</h5>
                    <p>${result.analysis.replace(/\n/g, '<br>')}</p>
                </div>
        `;

        if (result.suggested_atoms && result.suggested_atoms.length) {
            resultHtml += '<div class="suggested-atoms"><h5>제안된 아톰들</h5><ul>';
            result.suggested_atoms.forEach(atom => {
                resultHtml += `<li><strong>${atom.atom_id}:</strong> ${atom.atom_name} - ${atom.description}</li>`;
            });
            resultHtml += '</ul></div>';
        }

        if (result.suggested_molecule) {
            const molecule = result.suggested_molecule;
            resultHtml += `
                <div class="suggested-molecule">
                    <h5>제안된 분자</h5>
                    <p><strong>ID:</strong> ${molecule.Molecule_ID}</p>
                    <p><strong>이름:</strong> ${molecule.Molecule_Name}</p>
                    <p><strong>카테고리:</strong> ${molecule.Category}</p>
                    <p><strong>필수 아톰:</strong> ${molecule.Required_Atom_IDs.join(', ')}</p>
                    <p><strong>번역 노트:</strong> ${molecule.Translation_Notes}</p>
                    <p><strong>상태:</strong> ${molecule.Status}</p>
                </div>
            `;
        }

        resultHtml += '</div>';
        resultDiv.innerHTML = resultHtml;

        this.addLog('✅ AI 분석 완료', 'success');
    }

    // ================== 스캐닝 관리 ==================

    addTicker() {
        const input = document.getElementById('ticker-input');
        if (!input) return;

        const ticker = input.value.toUpperCase().trim();
        if (!ticker) {
            alert('티커를 입력해주세요.');
            return;
        }

        if (this.watchlist.includes(ticker)) {
            alert('이미 추가된 티커입니다.');
            return;
        }

        this.watchlist.push(ticker);
        input.value = '';
        this.updateWatchlist();
        this.addLog(`티커 추가: ${ticker}`, 'info');
    }

    removeTicker(ticker) {
        this.watchlist = this.watchlist.filter(t => t !== ticker);
        this.updateWatchlist();
        this.addLog(`티커 제거: ${ticker}`, 'info');
    }

    updateWatchlist() {
        const container = document.getElementById('watchlist-container');
        if (!container) return;

        container.innerHTML = '';

        this.watchlist.forEach(ticker => {
            const tag = document.createElement('span');
            tag.className = 'ticker-tag';
            tag.innerHTML = `
                ${ticker}
                <button onclick="tradingAssistant.removeTicker('${ticker}')" class="remove-ticker-btn">×</button>
            `;
            container.appendChild(tag);
        });

        document.getElementById('watchlist-count').textContent = this.watchlist.length;
    }

    startScanner() {
        if (!this.watchlist.length) {
            alert('감시할 티커를 먼저 추가해주세요.');
            return;
        }

        this.sendWebSocketMessage({
            type: 'start_scanner',
            tickers: this.watchlist
        });
    }

    stopScanner() {
        this.sendWebSocketMessage({ type: 'stop_scanner' });
    }

    updateScannerButtons() {
        const startBtn = document.getElementById('start-scanner-btn');
        const stopBtn = document.getElementById('stop-scanner-btn');

        if (startBtn && stopBtn) {
            startBtn.disabled = this.isScanning;
            stopBtn.disabled = !this.isScanning;
        }

        const statusSpan = document.getElementById('scanner-status');
        if (statusSpan) {
            statusSpan.textContent = this.isScanning ? '🟢 활성' : '🔴 비활성';
            statusSpan.className = this.isScanning ? 'status-success' : 'status-error';
        }
    }

    // ================== 시스템 관리 ==================

    async testAllConnections() {
        this.sendWebSocketMessage({ type: 'test_connections' });
        this.addLog('🧪 연결 테스트 시작', 'info');
    }

    async initializeSystem() {
        this.sendWebSocketMessage({ 
            type: 'initialize_system',
            api_settings: this.apiSettings
        });
        this.addLog('🔧 시스템 초기화 시작', 'info');
    }

    saveApiSettings() {
        const settings = {
            alpaca_key: document.getElementById('alpaca-key')?.value || '',
            alpaca_secret: document.getElementById('alpaca-secret')?.value || '',
            gemini_key: document.getElementById('gemini-key')?.value || '',
            sheets_id: document.getElementById('sheets-id')?.value || '',
            service_account_json: document.getElementById('service-account-json')?.value || ''
        };

        this.apiSettings = settings;
        localStorage.setItem('api_settings', JSON.stringify(settings));

        this.addLog('⚙️ API 설정 저장됨', 'success');
        this.showToast('설정이 저장되었습니다.', 'success');
    }

    loadSettings() {
        try {
            const saved = localStorage.getItem('api_settings');
            if (saved) {
                this.apiSettings = JSON.parse(saved);
                
                // 마스킹된 값으로 UI 업데이트
                if (this.apiSettings.alpaca_key) {
                    document.getElementById('alpaca-key').value = '*'.repeat(8);
                }
                if (this.apiSettings.alpaca_secret) {
                    document.getElementById('alpaca-secret').value = '*'.repeat(8);
                }
                if (this.apiSettings.gemini_key) {
                    document.getElementById('gemini-key').value = '*'.repeat(8);
                }
                if (this.apiSettings.sheets_id) {
                    document.getElementById('sheets-id').value = this.apiSettings.sheets_id;
                }
            }
        } catch (error) {
            console.error('설정 로드 오류:', error);
        }
    }

    // ================== UI 유틸리티 ==================

    showSection(sectionId) {
        // 모든 섹션 숨기기
        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });

        // 모든 네비게이션 항목에서 active 클래스 제거
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });

        // 요청된 섹션 표시
        const targetSection = document.getElementById(sectionId);
        if (targetSection) {
            targetSection.classList.add('active');
        }

        // 해당 네비게이션 항목에 active 클래스 추가
        const navItem = document.querySelector(`[onclick="tradingAssistant.showSection('${sectionId}')"]`);
        if (navItem) {
            navItem.classList.add('active');
        }
    }

    addSignalToDisplay(signal) {
        const container = document.getElementById('signals-container');
        if (!container) return;

        const signalDiv = document.createElement('div');
        signalDiv.className = `signal-item ${signal.type}`;

        let content = '';
        if (signal.type === 'atom') {
            content = `
                <div class="signal-header">
                    <span class="signal-type">🔴 ATOM</span>
                    <span class="signal-grade grade-${signal.grade.replace('+', 'plus')}">${signal.grade}</span>
                    <span class="signal-time">${this.formatTime(signal.timestamp)}</span>
                </div>
                <div class="signal-content">
                    <strong>${signal.ticker}</strong> - ${signal.name}
                    <br>Price: $${signal.price} | Volume: ${signal.volume?.toLocaleString()}
                </div>
            `;
        } else if (signal.type === 'molecule') {
            content = `
                <div class="signal-header">
                    <span class="signal-type">🔥 MOLECULE</span>
                    <span class="signal-grade grade-${signal.grade.replace('+', 'plus')}">${signal.grade}</span>
                    <span class="signal-time">${this.formatTime(signal.timestamp)}</span>
                </div>
                <div class="signal-content">
                    <strong>${signal.id}</strong> - ${signal.name}
                    <br>Match: ${signal.match_ratio}% | Atoms: ${signal.atoms?.join(', ')}
                </div>
            `;
        }

        signalDiv.innerHTML = content;
        container.insertBefore(signalDiv, container.firstChild);

        // 최대 100개까지만 유지
        while (container.children.length > 100) {
            container.removeChild(container.lastChild);
        }

        // 새 신호 하이라이트 애니메이션
        signalDiv.classList.add('signal-new');
        setTimeout(() => signalDiv.classList.remove('signal-new'), 3000);
    }

    addLog(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = {
            timestamp,
            message,
            type
        };

        this.logBuffer.push(logEntry);

        // 최대 로그 수 제한
        if (this.logBuffer.length > this.maxLogEntries) {
            this.logBuffer.shift();
        }

        // UI 업데이트
        this.updateLogDisplay();
    }

    updateLogDisplay() {
        const container = document.getElementById('logs-container');
        if (!container) return;

        // 최근 50개 로그만 표시
        const recentLogs = this.logBuffer.slice(-50);
        
        container.innerHTML = recentLogs.map(log => 
            `<div class="log-entry log-${log.type}">
                <span class="log-time">${log.timestamp}</span>
                <span class="log-message">${log.message}</span>
            </div>`
        ).join('');

        // 스크롤을 아래로
        container.scrollTop = container.scrollHeight;
    }

    updateConnectionStatus(status, type) {
        const indicator = document.getElementById('connection-status');
        if (indicator) {
            indicator.textContent = status;
            indicator.className = `status-indicator status-${type}`;
        }
    }

    updateServiceStatus(service, isConnected) {
        const indicator = document.getElementById(`${service}-status`);
        if (indicator) {
            indicator.textContent = isConnected ? '🟢 연결됨' : '🔴 끊어짐';
            indicator.className = isConnected ? 'status-success' : 'status-error';
        }
    }

    startStatusUpdates() {
        setInterval(() => {
            if (this.isConnected) {
                this.sendWebSocketMessage({ type: 'get_system_status' });
            }
        }, 5000); // 5초마다 상태 업데이트
    }

    showModal(title, content) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-box">
                <div class="modal-header">
                    <h3 class="modal-title">${title}</h3>
                    <button class="modal-close" onclick="this.closest('.modal').remove()">×</button>
                </div>
                <div class="modal-body">
                    ${content}
                </div>
                <div class="modal-footer">
                    <button class="btn-gray" onclick="this.closest('.modal').remove()">닫기</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => toast.classList.add('show'), 100);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    playNotificationSound(type) {
        try {
            const audio = new Audio();
            audio.volume = 0.3;
            
            if (type === 'atom') {
                audio.src = 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcQDQESCdOQUyBBEkNUmKAAQABAAEANjVgodDbq2EcGj9';  // 짧은 삐 소리
            } else if (type === 'molecule') {
                audio.src = 'data:audio/wav;base64,UklGRiQDAABXQVZFZm10IBAAAAABAAEASLwAAEi8AAABAAgAZGF0YQAAAAABAAAAAAEAAAEAAAEAAAEAAAEAAAEAAAEAAAEAAAEAAAEAAAEAAE+8AAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcTJEE'; // 긴 벨 소리
            }
            
            audio.play().catch(e => console.log('오디오 재생 실패:', e));
        } catch (error) {
            console.log('알림음 재생 실패:', error);
        }
    }

    highlightMoleculeSignal(data) {
        // 중요한 분자 신호의 경우 화면을 깜빡이는 효과
        if (data.grade === 'A++' || data.grade === 'A+') {
            document.body.style.backgroundColor = '#fef3c7';
            setTimeout(() => {
                document.body.style.backgroundColor = '';
            }, 1000);
        }
    }

    // ================== 유틸리티 함수들 ==================

    formatTime(timestamp) {
        return new Date(timestamp).toLocaleTimeString();
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleString();
    }

    getPriorityBadge(priority) {
        const level = parseFloat(priority) || 0;
        if (level >= 0.8) return '<span class="badge badge-red">높음</span>';
        if (level >= 0.5) return '<span class="badge badge-yellow">중간</span>';
        return '<span class="badge badge-green">낮음</span>';
    }

    getStatusBadge(status) {
        const statusMap = {
            'PENDING': '<span class="badge badge-gray">대기</span>',
            'RUNNING': '<span class="badge badge-blue">실행중</span>',
            'READY_FOR_REVIEW': '<span class="badge badge-green">검토준비</span>',
            'FAILED_WFO': '<span class="badge badge-red">WFO실패</span>',
            'ERROR': '<span class="badge badge-red">오류</span>'
        };
        return statusMap[status] || '<span class="badge badge-gray">알수없음</span>';
    }

    // ================== 로그 관리 ==================

    exportLogs() {
        const logs = this.logBuffer.map(log => 
            `${log.timestamp} [${log.type.toUpperCase()}] ${log.message}`
        ).join('\n');

        const blob = new Blob([logs], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `trading_logs_${new Date().toISOString().split('T')[0]}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    }

    clearLogs() {
        if (confirm('모든 로그를 삭제하시겠습니까?')) {
            this.logBuffer = [];
            this.updateLogDisplay();
            this.addLog('로그가 삭제되었습니다', 'info');
        }
    }
}

// ================== 전역 객체 초기화 ==================

// 전역 인스턴스 생성
let tradingAssistant;

// DOM 로드 완료 시 초기화
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        tradingAssistant = new TradingAssistant();
    });
} else {
    tradingAssistant = new TradingAssistant();
}

// ================== 전역 함수들 (HTML에서 직접 호출) ==================

function showSection(sectionId) {
    if (tradingAssistant) {
        tradingAssistant.showSection(sectionId);
    }
}

function exportLogs() {
    if (tradingAssistant) {
        tradingAssistant.exportLogs();
    }
}

function clearLogs() {
    if (tradingAssistant) {
        tradingAssistant.clearLogs();
    }
}

// ================== 브라우저 호환성 체크 ==================

// WebSocket 지원 확인
if (!window.WebSocket) {
    console.error('WebSocket을 지원하지 않는 브라우저입니다.');
    alert('이 브라우저는 WebSocket을 지원하지 않습니다. 최신 브라우저를 사용해주세요.');
}

// localStorage 지원 확인
if (!window.localStorage) {
    console.error('localStorage를 지원하지 않는 브라우저입니다.');
    alert('이 브라우저는 로컬 저장소를 지원하지 않습니다.');
}

// ================== 에러 핸들링 ==================

window.addEventListener('error', (event) => {
    console.error('전역 오류:', event.error);
    if (tradingAssistant) {
        tradingAssistant.addLog(`전역 오류: ${event.error.message}`, 'error');
    }
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('처리되지 않은 Promise 거부:', event.reason);
    if (tradingAssistant) {
        tradingAssistant.addLog(`Promise 오류: ${event.reason}`, 'error');
    }
});

// ================== 페이지 언로드 시 정리 ==================

window.addEventListener('beforeunload', () => {
    if (tradingAssistant && tradingAssistant.websocket) {
        tradingAssistant.websocket.close();
    }
});

console.log('✅ app.js 로드 완료 - AI Trading Assistant V6.0');
