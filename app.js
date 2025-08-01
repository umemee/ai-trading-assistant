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
            return 'https://your-backend-service.herokuapp.com';
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
            // ApprovalWorkflow & MetaLearner 의 동적 버튼 이벤트는 각 render 함수에서 바인딩됩니다.
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
                case 'system_status': this.handleSystemStatus(data); break;
                case 'atom_signal': this.handleAtomSignal(data); break;
                case 'molecule_signal': this.handleMoleculeSignal(data); break;
                case 'system_initialized': this.handleSystemInitialized(data); break;
                case 'scanner_started': this.handleScannerStarted(data); break;
                case 'scanner_stopped': this.handleScannerStopped(data); break;
                case 'connection_test_result': this.handleConnectionTestResult(data); break;
                case 'analysis_result': this.handleAnalysisResult(data); break;
                case 'approval_queue': this.handleApprovalQueue(data); break;
                case 'pending_predictions': this.handlePendingPredictions(data); break;
                case 'prediction_review_result': this.handlePredictionReviewResult(data); break;
                case 'error': this.addLog(`서버 오류: ${data.message}`, 'error'); break;
                default: console.log('알 수 없는 메시지:', data);
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
            approvalTableBody.innerHTML = '<tr><td colspan="7" class="text-center p-4">검토 대기 중인 분자가 없습니다.</td></tr>';
            return;
        }
        queue.forEach(molecule => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="p-2 border-b border-gray-700">${molecule.Molecule_ID}</td>
                <td class="p-2 border-b border-gray-700">${molecule.Molecule_Name}</td>
                <td class="p-2 border-b border-gray-700">${molecule.Category}</td>
                <td class="p-2 border-b border-gray-700">${Number(molecule.WFO_Score || 0).toFixed(2)}</td>
                <td class="p-2 border-b border-gray-700">${molecule.Created_Date ? new Date(molecule.Created_Date).toLocaleDateString() : ''}</td>
                <td class="p-2 border-b border-gray-700">${molecule.Status}</td>
                <td class="p-2 border-b border-gray-700">
                    <button class="btn-sm btn-green approve-btn" data-id="${molecule.Molecule_ID}">승인</button>
                    <button class="btn-sm btn-red reject-btn" data-id="${molecule.Molecule_ID}">거부</button>
                </td>
            `;
            approvalTableBody.appendChild(row);
        });
        approvalTableBody.querySelectorAll('.approve-btn').forEach(btn => {
            btn.onclick = () => this.approveMolecule(btn.dataset.id);
        });
        approvalTableBody.querySelectorAll('.reject-btn').forEach(btn => {
            btn.onclick = () => {
                const reason = prompt('거부 사유를 입력하세요:');
                if (reason) this.rejectMolecule(btn.dataset.id, reason);
            };
        });
    }

    approveMolecule(moleculeId) {
        if (!this.isConnected) return;
        const approver = 'head_chef'; // 실제 운영에서는 사용자 정보 사용
        this.sendWebSocketMessage({
            type: 'approve_molecule',
            molecule_id: moleculeId,
            approver: approver,
            approval_notes: 'WFO 결과 검토 후 승인'
        });
        this.addLog(`분자 승인 요청: ${moleculeId}`, 'info');
        setTimeout(() => this.refreshApprovalQueue(), 1500);
    }

    rejectMolecule(moleculeId, reason) {
        if (!this.isConnected) return;
        const reviewer = 'head_chef';
        this.sendWebSocketMessage({
            type: 'reject_molecule',
            molecule_id: moleculeId,
            reviewer: reviewer,
            rejection_reason: reason
        });
        this.addLog(`분자 거부 요청: ${moleculeId} / 사유: ${reason}`, 'warning');
        setTimeout(() => this.refreshApprovalQueue(), 1500);
    }

    // ================== LogicDiscoverer ==================
    async requestAiAnalysis() {
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
        this.sendWebSocketMessage({
            type: 'request_analysis',
            ticker: ticker.toUpperCase(),
            date: date,
            context: context
        });
    }
    
    handleAnalysisResult(data) {
        this.addLog(`AI 분석 결과 수신: ${data.ticker}`, 'info');
        const result = data.result;
        if (result.success) {
            this.displayAnalysisResult(result);
            // 분석 성공 후 검역 큐 새로고침
            this.refreshApprovalQueue();
        } else {
            this.addLog(`AI 분석 실패: ${result.error}`, 'error');
        }
    }

    displayAnalysisResult(result) {
        const analysisResultEl = document.getElementById('analysis-result');
        if (!analysisResultEl) return;
        let resultHtml = '<div class="p-4 bg-gray-800 rounded-lg">';
        if (result.analysis) {
            resultHtml += `<h4 class="text-lg font-semibold mb-2">📊 분석 결과</h4><p class="text-sm text-gray-300">${result.analysis.replace(/\n/g, '<br>')}</p>`;
        }
        if (result.suggested_atoms && result.suggested_atoms.length > 0) {
            resultHtml += `<h4 class="text-lg font-semibold mt-4 mb-2">🔬 제안된 아톰</h4>`;
            result.suggested_atoms.forEach(atom => {
                resultHtml += `<div class="p-2 bg-gray-700 rounded mb-2"><strong class="text-blue-400">${atom.atom_id}</strong>: ${atom.atom_name}<br><small class="text-gray-400">${atom.description}</small></div>`;
            });
        }
        if (result.suggested_molecule) {
            const molecule = result.suggested_molecule;
            resultHtml += `<h4 class="text-lg font-semibold mt-4 mb-2">🧬 제안된 분자 (검역소로 이동)</h4>`;
            resultHtml += `<div class="p-2 bg-gray-700 rounded"><strong class="text-green-400">${molecule.molecule_id}</strong>: ${molecule.molecule_name}<br><small class="text-gray-400">필요 아톰: ${molecule.required_atom_ids?.join(', ')}</small></div>`;
        }
        resultHtml += '</div>';
        analysisResultEl.innerHTML = resultHtml;
    }

    // ================== MetaLearner ==================
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
        const predictionTableBody = document.querySelector('#meta-table tbody');
        if (!predictionTableBody) return;
        predictionTableBody.innerHTML = '';
        const preds = this.pendingPredictions;
        if (!preds.length) {
            predictionTableBody.innerHTML = '<tr><td colspan="7" class="text-center p-4">복기 대기 중인 예측이 없습니다.</td></tr>';
            return;
        }
        preds.forEach(pred => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="p-2 border-b border-gray-700 text-xs">${pred.Prediction_ID.substring(0, 8)}</td>
                <td class="p-2 border-b border-gray-700">${pred.Ticker}</td>
                <td class="p-2 border-b border-gray-700">${pred.Triggered_Molecule_ID}</td>
                <td class="p-2 border-b border-gray-700 text-sm">${pred.Prediction_Summary}</td>
                <td class="p-2 border-b border-gray-700 text-xs">${new Date(pred.Timestamp_UTC).toLocaleString()}</td>
                <td class="p-2 border-b border-gray-700">
                    <select class="result-select bg-gray-700 rounded p-1 text-sm" data-id="${pred.Prediction_ID}">
                        <option value="">선택</option><option value="success">성공</option><option value="fail">실패</option>
                    </select>
                </td>
                <td class="p-2 border-b border-gray-700">
                    <button class="btn-sm btn-purple review-btn" data-id="${pred.Prediction_ID}">복기</button>
                </td>
            `;
            predictionTableBody.appendChild(row);
        });
        predictionTableBody.querySelectorAll('.review-btn').forEach(btn => {
            btn.onclick = () => {
                const predId = btn.dataset.id;
                const select = predictionTableBody.querySelector(`.result-select[data-id="${predId}"]`);
                const outcome = select ? select.value : '';
                if (!outcome) {
                    alert('실제 결과를 먼저 선택해주세요.');
                    return;
                }
                this.startPredictionReview(predId, outcome);
            };
        });
    }

    startPredictionReview(predictionId, outcome) {
        if (!this.isConnected) return;
        const humanFeedback = prompt("복기에 참고할 만한 추가적인 피드백이 있나요? (선택사항)") || "";
        this.sendWebSocketMessage({
            type: 'start_prediction_review',
            prediction_id: predictionId,
            actual_outcome: outcome,
            human_feedback: humanFeedback
        });
        this.addLog(`복기 분석 요청: ${predictionId} (${outcome})`, 'info');
    }
    
    handlePredictionReviewResult(data) {
        const modalBody = document.getElementById('review-modal-body');
        const modal = document.getElementById('review-modal');
        if (!modalBody || !modal) return;
        
        let resultHtml = ``;
        if (data.review_summary) {
            resultHtml += `<h4 class="text-lg font-semibold mb-2">📜 AI 복기 리포트</h4><p class="text-sm text-gray-300 mb-4">${data.review_summary}</p>`;
        }
        if (data.improvement_suggestions?.new_avoidance_molecule) {
            const molecule = data.improvement_suggestions.new_avoidance_molecule;
            resultHtml += `<h4 class="text-lg font-semibold mt-4 mb-2">🛡️ 신규 회피(AVD) 분자 제안</h4>`;
            resultHtml += `<div class="p-2 bg-gray-700 rounded"><strong class="text-red-400">${molecule.molecule_id}</strong>: ${molecule.molecule_name}<br><small class="text-gray-400">${molecule.translation_notes}</small></div>`;
        }
        
        modalBody.innerHTML = resultHtml;
        modal.style.display = 'flex';
        
        // 모달 닫기 버튼
        document.getElementById('review-modal-close').onclick = () => {
            modal.style.display = 'none';
            this.refreshPendingPredictions(); // 복기 후 목록 새로고침
        };
    }


    // ================== 기존 로그, 알림, UI, 기타 핵심 기능 ==================
    addLog(message, type = 'info') {
        const logEl = document.getElementById('log-display');
        if (!logEl) return;
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = { timestamp, message, type };
        this.logBuffer.unshift(logEntry);
        if (this.logBuffer.length > this.maxLogEntries) {
            this.logBuffer.pop();
        }
        this.updateLogDisplay();
    }
    updateLogDisplay() {
        const logEl = document.getElementById('log-display');
        if (!logEl) return;
        logEl.innerHTML = this.logBuffer.slice(0, 100).map(entry =>
            `<div class="log-item log-${entry.type}"><span class="log-timestamp">${entry.timestamp}</span><span class="log-message">${entry.message}</span></div>`
        ).join('');
    }
    exportLogs() {
        const logsText = this.logBuffer.map(e => `[${e.timestamp}] ${e.type.toUpperCase()}: ${e.message}`).join('\n');
        const blob = new Blob([logsText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `trading_logs_${new Date().toISOString().split('T')[0]}.txt`;
        a.click();
        URL.revokeObjectURL(url);
        this.addLog('로그를 다운로드했습니다', 'success');
    }
    clearLogs() {
        this.logBuffer = [];
        this.updateLogDisplay();
        this.addLog('로그가 삭제되었습니다', 'info');
    }
    updateConnectionStatus(status, type) {
        const statusEl = document.getElementById('connection-status');
        if (statusEl) {
            statusEl.textContent = status;
            statusEl.className = `status-${type}`;
        }
    }
    updateServiceStatus(serviceName, isConnected) {
        const statusEl = document.getElementById(`${serviceName}-status`);
        if (statusEl) {
            statusEl.textContent = isConnected ? '✅ 연결됨' : '❌ 오류';
            statusEl.className = isConnected ? 'status-success' : 'status-error';
        }
    }
    updateScannerButtons() {
        document.getElementById('start-scanner-btn').disabled = this.isScanning;
        document.getElementById('stop-scanner-btn').disabled = !this.isScanning;
    }
    addSignalToDisplay(signal) {
        const signalsEl = document.getElementById('signals-display');
        if (!signalsEl) return;
        const signalEl = document.createElement('div');
        signalEl.className = `signal-item signal-${signal.type}`;
        const timestamp = new Date().toLocaleTimeString();
        if (signal.type === 'atom') {
            signalEl.innerHTML = `<div class="signal-header"><span class="signal-type">🔴 아톰</span><span class="signal-timestamp">${timestamp}</span></div><div class="signal-content"><strong>${signal.ticker}</strong> - ${signal.name} (${signal.grade})<br><small>가격: $${signal.price} | 거래량: ${signal.volume?.toLocaleString()}</small></div>`;
        } else if (signal.type === 'molecule') {
            signalEl.innerHTML = `<div class="signal-header"><span class="signal-type">🔥 분자</span><span class="signal-timestamp">${timestamp}</span></div><div class="signal-content"><strong>${signal.name}</strong> (${signal.grade})<br><small>매치율: ${signal.match_ratio?.toFixed(1)}% | 아톰: ${signal.atoms?.join(', ')}</small></div>`;
        }
        signalsEl.insertBefore(signalEl, signalsEl.firstChild);
        while (signalsEl.children.length > 50) {
            signalsEl.removeChild(signalsEl.lastChild);
        }
    }
    highlightMoleculeSignal(data) {
        if (data.grade && ['A++', 'A+', 'A'].includes(data.grade)) {
            if (Notification.permission === 'granted') {
                new Notification(`🔥 분자 신호: ${data.molecule_name}`, { body: `등급: ${data.grade} | 매치율: ${data.match_ratio?.toFixed(1)}%` });
            }
        }
    }
    playNotificationSound(type) {
        try {
            const audioContext = new(window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            oscillator.frequency.setValueAtTime(type === 'atom' ? 800 : 1200, audioContext.currentTime);
            gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.3);
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.3);
        } catch (error) {
            console.log('알림음 재생 실패:', error.message);
        }
    }
    startStatusUpdates() {
        setInterval(() => {
            if (this.isConnected) {
                this.sendWebSocketMessage({ type: 'get_system_status' });
            }
        }, 10000);
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }
    addTicker() {
        const tickerInput = document.getElementById('ticker-input');
        if (!tickerInput) return;
        const ticker = tickerInput.value.trim().toUpperCase();
        if (!ticker) { this.addLog('종목 심볼을 입력하세요', 'warning'); return; }
        if (this.watchlist.includes(ticker)) { this.addLog(`${ticker}는 이미 추가되어 있습니다`, 'warning'); return; }
        this.watchlist.push(ticker);
        tickerInput.value = '';
        this.updateWatchlist();
        this.addLog(`${ticker} 추가됨`, 'success');
    }
    removeTicker(ticker) {
        const index = this.watchlist.indexOf(ticker);
        if (index > -1) {
            this.watchlist.splice(index, 1);
            this.updateWatchlist();
            this.addLog(`${ticker} 제거됨`, 'info');
        }
    }
    updateWatchlist() {
        const watchlistEl = document.getElementById('watchlist');
        if (!watchlistEl) return;
        watchlistEl.innerHTML = '';
        this.watchlist.forEach(ticker => {
            const tickerEl = document.createElement('div');
            tickerEl.className = 'ticker-item bg-gray-700 rounded-full px-3 py-1 text-sm flex items-center';
            tickerEl.innerHTML = `<span class="font-bold text-blue-400 mr-2">${ticker}</span><button class="text-red-500 hover:text-red-400" onclick="tradingAssistant.removeTicker('${ticker}')">&times;</button>`;
            watchlistEl.appendChild(tickerEl);
        });
        document.getElementById('ticker-count').textContent = this.watchlist.length;
    }
    async startScanner() {
        if (!this.isConnected) { this.addLog('WebSocket이 연결되지 않음', 'error'); return; }
        if (!this.systemInitialized) { this.addLog('시스템이 초기화되지 않음 - 먼저 초기화하세요', 'error'); return; }
        if (this.watchlist.length === 0) { this.addLog('감시할 종목을 추가하세요', 'warning'); return; }
        this.addLog(`🟢 스캐너 시작: ${this.watchlist.join(', ')}`, 'info');
        this.sendWebSocketMessage({
            type: 'start_scanner',
            tickers: this.watchlist,
            api_settings: this.apiSettings
        });
    }
    async stopScanner() {
        if (!this.isConnected) { this.addLog('WebSocket이 연결되지 않음', 'error'); return; }
        this.addLog('🔴 스캐너 정지 요청...', 'info');
        this.sendWebSocketMessage({ type: 'stop_scanner' });
    }
    saveApiSettings() {
        const settings = {
            alpacaKey: document.getElementById('alpaca-key')?.value || '',
            alpacaSecret: document.getElementById('alpaca-secret')?.value || '',
            geminiKey: document.getElementById('gemini-key')?.value || '',
            sheetsId: document.getElementById('sheets-id')?.value || '',
            googleServiceAccountJson: document.getElementById('google-service-account')?.value || ''
        };
        localStorage.setItem('tradingApiSettings', JSON.stringify(settings));
        this.apiSettings = settings;
        this.addLog('API 설정이 저장되었습니다', 'success');
        if (this.validateApiSettings(settings)) {
            setTimeout(() => this.initializeSystem(), 1000);
        }
    }
    loadSettings() {
        const savedSettings = localStorage.getItem('tradingApiSettings');
        if (savedSettings) {
            const settings = JSON.parse(savedSettings);
            this.apiSettings = settings;
            document.getElementById('alpaca-key').value = settings.alpacaKey || '';
            document.getElementById('alpaca-secret').value = settings.alpacaSecret || '';
            document.getElementById('gemini-key').value = settings.geminiKey || '';
            document.getElementById('sheets-id').value = settings.sheetsId || '';
            document.getElementById('google-service-account').value = settings.googleServiceAccountJson || '';
            this.addLog('저장된 API 설정을 불러왔습니다', 'info');
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
    async testAllConnections() {
        if (!this.isConnected) { this.addLog('WebSocket이 연결되지 않음', 'error'); return; }
        this.addLog('📡 모든 연결 테스트 시작...', 'info');
        this.sendWebSocketMessage({
            type: 'test_connection',
            api_settings: this.apiSettings
        });
    }
    async initializeSystem() {
        if (!this.isConnected) { this.addLog('WebSocket이 연결되지 않음', 'error'); return; }
        if (!this.validateApiSettings(this.apiSettings)) { this.addLog('API 설정을 먼저 저장하세요', 'error'); return; }
        this.addLog('🔧 시스템 초기화 시작...', 'info');
        this.sendWebSocketMessage({
            type: 'initialize_system',
            api_settings: this.apiSettings
        });
    }
}

// ========= 전역 함수 및 이벤트 =========
document.addEventListener('DOMContentLoaded', function() {
    window.tradingAssistant = new TradingAssistant();

    window.showSection = function(sectionId, navBtn) {
        try {
            const sections = document.querySelectorAll('.section');
            sections.forEach(section => { section.style.display = 'none'; });
            if (sectionId === 'main') {
                const mainSection = document.getElementById('main');
                if (mainSection) mainSection.style.display = 'block';
                const pwModal = document.getElementById('pw-modal');
                if (pwModal) pwModal.style.display = 'none';
            } else {
                const mainSection = document.getElementById('main');
                if (mainSection) mainSection.style.display = 'block';
                const contentSections = document.querySelectorAll('.content-section');
                contentSections.forEach(section => {
                    section.classList.remove('active');
                    section.style.display = 'none';
                });
                const navButtons = document.querySelectorAll('.nav-item');
                navButtons.forEach(btn => { btn.classList.remove('active'); });
                const targetSection = document.getElementById(sectionId);
                if (targetSection) {
                    targetSection.classList.add('active');
                    targetSection.style.display = 'block';
                }
                if (navBtn) navBtn.classList.add('active');
                else {
                    const navButton = document.querySelector(`.nav-item[onclick="showSection('${sectionId}', this)"]`);
                    if (navButton) navButton.classList.add('active');
                }
            }
        } catch (error) {
            console.error('섹션 표시 오류:', error);
        }
    };

    window.addTicker = function() { window.tradingAssistant.addTicker(); };
    window.exportLogs = function() { window.tradingAssistant.exportLogs(); };
    window.clearLogs = function() {
        if (window.tradingAssistant && confirm('모든 로그를 삭제하시겠습니까?')) {
            window.tradingAssistant.clearLogs();
        }
    };
    showSection('dashboard');
});

window.addEventListener('beforeunload', function() {
    if (window.tradingAssistant && window.tradingAssistant.websocket) {
        window.tradingAssistant.websocket.close();
    }
});
window.addEventListener('error', function(event) {
    console.error('전역 오류:', event.error);
    if (window.tradingAssistant) {
        window.tradingAssistant.addLog(`시스템 오류: ${event.error.message}`, 'error');
    }
});
window.addEventListener('unhandledrejection', function(event) {
    console.error('미처리 Promise 거부:', event.reason);
    if (window.tradingAssistant) {
        window.tradingAssistant.addLog(`Promise 오류: ${event.reason}`, 'error');
    }
});
console.log('🚀 AI Trading Assistant V6.0 Frontend - 모든 모듈 로드 완료');
}
