/* =====================================================================
   app.js - AI Trading Assistant V5.5 Complete Frontend
   - WebSocket 클라이언트 및 UI 제어
   - 승인 워크플로우 기능 완전 구현
   =================================================================== */

class TradingAssistant {
    constructor() {
        this.websocket = null;
        this.apiBaseUrl = `${window.location.protocol}//${window.location.hostname}:8000/api`;
        this.init();
    }

    init() {
        // 기존 init 내용 유지
        document.getElementById('pw-btn').onclick = () => this.handleLogin();
        // ... (기타 핸들러)

        if (sessionStorage.getItem('authenticated')) {
            document.getElementById('pw-modal').style.display = 'none';
        }
    }
    
    // ✅ 2단계 수정: 승인 워크플로우 관련 함수 추가
    
    // 검토 대기 목록 새로고침
    async refreshQuarantineQueue() {
        this.showToast('검토 대기 목록을 새로고침합니다...', 'blue');
        try {
            const response = await fetch(`${this.apiBaseUrl}/quarantine/list`);
            if (!response.ok) {
                throw new Error(`서버 오류: ${response.statusText}`);
            }
            const queue = await response.json();
            this.displayQuarantineQueue(queue);
            this.showToast('검토 대기 목록을 업데이트했습니다.', 'green');
        } catch (error) {
            console.error("검역 큐 조회 실패:", error);
            this.showToast('검토 목록 로딩에 실패했습니다.', 'red');
            const queueListDiv = document.getElementById('quarantine-list');
            queueListDiv.innerHTML = `<p class="text-red-400">데이터를 불러오는 데 실패했습니다. 백엔드 서버 상태를 확인하세요.</p>`;
        }
    }

    // 검토 대기 목록을 화면에 표시
    displayQuarantineQueue(queue) {
        const queueListDiv = document.getElementById('quarantine-list');
        if (queue.length === 0) {
            queueListDiv.innerHTML = `<p class="text-gray-500">검토 대기 중인 전략이 없습니다.</p>`;
            return;
        }

        queueListDiv.innerHTML = queue.map(item => `
            <div class="bg-gray-700 p-4 rounded-lg shadow-md flex items-center justify-between">
                <div>
                    <h4 class="font-bold text-lg text-yellow-400">${item.Molecule_ID}</h4>
                    <p class="text-sm text-gray-300">${item.Molecule_Name || '이름 없음'}</p>
                    <div class="flex items-center space-x-4 mt-2 text-xs text-gray-400">
                        <span><strong>생성일:</strong> ${new Date(item.Created_Date).toLocaleDateString()}</span>
                        <span><strong>WFO 점수:</strong> ${parseFloat(item.WFO_Score).toFixed(3)}</span>
                    </div>
                </div>
                <div class="flex space-x-2">
                    <button class="btn-green" onclick="tradingAssistant.approveMolecule('${item.Molecule_ID}')">
                        <i class="fas fa-check mr-1"></i>승인
                    </button>
                    <button class="btn-red" onclick="tradingAssistant.rejectMolecule('${item.Molecule_ID}')">
                        <i class="fas fa-times mr-1"></i>거부
                    </button>
                </div>
            </div>
        `).join('');
    }

    // 분자 승인 처리
    async approveMolecule(moleculeId) {
        const reviewer = prompt("승인자 이름을 입력하세요:", "admin");
        if (!reviewer) return;
        
        const notes = prompt("승인 노트를 남겨주세요 (선택사항):");

        try {
            const response = await fetch(`${this.apiBaseUrl}/quarantine/approve/${moleculeId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reviewer, notes })
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || '승인 실패');

            this.showToast(`${moleculeId}가 성공적으로 승인되었습니다.`, 'green');
            this.refreshQuarantineQueue(); // 목록 새로고침
        } catch (error) {
            console.error("승인 실패:", error);
            this.showToast(`승인 실패: ${error.message}`, 'red');
        }
    }

    // 분자 거부 처리
    async rejectMolecule(moleculeId) {
        const reviewer = prompt("거부자 이름을 입력하세요:", "admin");
        if (!reviewer) return;

        const reason = prompt("거부 사유를 반드시 입력해주세요:");
        if (!reason) {
            this.showToast('거부 시에는 사유를 반드시 입력해야 합니다.', 'red');
            return;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/quarantine/reject/${moleculeId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reviewer, reason })
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || '거부 실패');

            this.showToast(`${moleculeId}가 거부 처리되었습니다.`, 'blue');
            this.refreshQuarantineQueue(); // 목록 새로고침
        } catch (error) {
            console.error("거부 실패:", error);
            this.showToast(`거부 실패: ${error.message}`, 'red');
        }
    }
    
    // 섹션 표시 함수 수정
    showSection(sectionId, element) {
        document.querySelectorAll('.content-section').forEach(section => section.classList.remove('active'));
        document.getElementById(sectionId).classList.add('active');
        
        document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
        element.classList.add('active');

        // 승인 워크플로우 탭을 누르면 자동으로 목록 새로고침
        if (sectionId === 'approval') {
            this.refreshQuarantineQueue();
        }
    }
    
    // --- 기존의 다른 함수들은 여기에 그대로 유지 ---
    // handleLogin, showToast 등...
    // (이 예제에서는 생략되었지만, 실제 파일에서는 기존 함수들을 모두 포함해야 합니다)
}

// 전역 인스턴스 생성 및 함수 연결
const tradingAssistant = new TradingAssistant();

function showSection(sectionId, element) {
    tradingAssistant.showSection(sectionId, element);
}

// (기타 전역 함수들)

console.log('🚀 AI Trading Assistant V5.5 Frontend Loaded');
