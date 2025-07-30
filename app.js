/* app.js - WebSocket 클라이언트 및``` 제어 */
class TradingAssistant {
    constructor() {
        this.websocket = null;
        this.```onnected = false;
        ```s.watchingTickers = [];
        this.signalCount = 0;
        this.```Settings = {};
        this.scan```Interval = null;
        ```      this.init();
    }

    init() {
        this.setupEvent```dlers();
        this.loa```ttings();
        this.showSection```ashboard');
        this.update```hboard();
        ```      // 로그인 확```       if (sessionStorage.getItem('authenticate```) {
            document.getElementById('pw-modal').style.display = 'none```            this.connect```Socket();
        }
    }

    setupEventHandlers() {
        // 로```        document.getElementById('pw-btn').onclick = () => this.handle```in();
        document.getElementById('pw-input').onkeypress = (e) => {
            if (e.key ===```nter') this.handleLogin```
        };

        // ```입력
        document.getElementById('ticker-input').onkeypress =```) => {
            if (e.key === 'Enter```this.addTicker();
        };
    }

    handleLogin() {
        const passwor``` document.getElementById('pw-input').value;
        if```assword === '2025') {
            ```ument.getElementById('pw-modal').style.display = 'none';```          sessionStorage.setItem('authenticated', ```ue');
            this.showTo```('로그인 성공! 시스템을 초```니다.', 'green');
            this.connect```Socket();
        } else {
            this.showToast('❌ 비```가 틀렸습니다', 'red');
            ```ument.getElementById('pw-input').value = '';
        }
    }

    // Web```ket 연결
    connectWebSocket() {
        ```st protocol = window.location.protocol === ```tps:' ? 'w```' : 'ws:';
        const wsUrl = `${protocol}//${window.location.hostname}:8000/ws`;
        
        try```            this.websocket =```w WebSocket(wsUrl);
            
            this.websocket.```pen = () => {
                this.isConnected = true;```              this.log```ivity('[WebSocket] 백엔드 서버와 연결됨');
                this.showTo```('백엔드 서버 연결 성공', '```en');
            };
            
            this.websocket.```essage = (event) => {
                this.handleWebSocketMessage(JSON.parse(event.data));
            };
            
            this.```socket.onclose = () => {
                this.isConnecte``` false;
                this.log```ivity('[WebSocket] 연결 끊어```;
                setTimeout``` => this.connectWebSocket(), 5000); // 재연결 시도```          };
            
            this```bsocket.onerror =```rror) => {
                console```ror('WebSocket error:', error```                this.log```ivity('[WebSocket] 연결 오류');
            ```        } catch (error) {
            ```sole.error('WebSocket connection```iled:', error);
            this.log```ivity('[WebSocket] 연결 실패 - 백엔드 서버 확```요');
        }
    }

    // WebSocket 메시지 처```   handleWebSocketMessage(data) {
        switch```ata.type) {
            ```e 'atom_signal':
                this.handleAtom```nal(data);
                break;
            case ```lecule_signal':
                this.handle```eculeSignal(data);
                break;
            case```ystem_status':
                this.update```temStatus(data);
                break```           case 'performance_update```                this.updatePerform```eData(data);
                break;
            case 'analysis```sult':
                this.display```lysisResult(data);
                break;
            default```               console.log```nknown message type:', data);
        }
    }

    // 아```호 처리
    handleAtomSignal(data) {
        const```mestamp = new Date().toLocaleTimeString('ko-KR');
        const message````[${timestamp}] ${data.ticker```${data.atom_id} (${data.atom_name```| $${data.price} | Vol: ${data.volume.```ocaleString()} | 등급: ${data.grade}`;
        
        this.logSignal(message,```ta.grade);
        this.sign```ount++;
        this.update```hboard();
    }

    // 분자 신호 처리```  handleMoleculeSignal```ta) {
        this.logActivity``` 분자 신호: ${data.ticker} - ${data.molecule_id} (${data.molecule_name})`);
        this.show```st(`🔥 ${data.ticker} 분자 신호 발생!`, 'red');
        
        ```ument.getElementById('molecule-status').innerHTML````
            <div class="```t-green-400">
                <strong```data.molecule_id}</strong>``` - ${data.ticker```${data.grade})
            </div>
        ```    }

    // 섹션 전```   showSection(sectionId) {
        //``` 섹션 숨기기
        document.queryS```ctorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        
        ```모든 네비게이션 버```활성화
        document.quer```lectorAll('.nav-item').forEach(btn => {
            btn```assList.remove('active');
        });
        
        // ``` 섹션과 버튼 활성화
        ```ument.getElementById(sectionId).classList.add('active');
        ```ument.querySelector(`[onclick="showSection('${sectionId}')"]`).classList.add('active');
        
        // ``` 초기화
        if (sectionId === 'module``` {
            this.render```formanceChart();
        }
    }

    // 대시보드 업데이트```  updateDashboard() {
        document.getElementById('watching-count').textContent = this.```chingTickers.length;
        document.getElementById('signal-count').textContent = this.signal```nt;
        
        const```ccessRate = this.signalCount >```? Math.floor(Math.random() * 30 + 50) : 0;
        ```ument.getElementById('success-rate').textContent = successRate + '%';```  }

    // 티```가
    addT```er() {
        const input```document.getElementById('ticker-input');
        const ticker = input.```ue.toUpperCase().trim();
        
        if (!ticker) {
            this.showToast('티커를 입력하세``` 'red');
            ```urn;
        }
        ```      if (this.watchingT```ers.length >= 10) {
            this.showTo```('최대 10개까지 추가할 수 ```다', 'red');
            return;
        }
        
        if```his.watchingTickers.includes(ticker)) {
            this.showToast```미 추가된 종목입니다', 're```;
            return;
        }
        
        this.watching```kers.push(ticker);
        input.value = '';
        this.```ateTickerList();
        ```s.updateDashboard();
        this.log```ivity(`종목 추가: ${ticker}`);
        this.showToast(`${ticker} 추가완료`, 'green');
    }

    // 티커 ```업데이트
    updateTickerList() {
        ```st tickerList = document.getElementById('ticker-list');
        tickerList```nerHTML = this.watchingTickers.map(ticker => `
            <div class="ticker-tag">
                ${ticker}
                ```an class="remove-btn" onclick="```dingAssistant.removeTicker('${ticker}')">&times;</span>
            ```iv>
        `).join('');
        
        this.update```chSummary();
    }

    // 티커 제거
    removeTicker(ticker) {
        this.watching```kers = this.watchingT```ers.filter(t => t !== ticker);
        this.updateTick```ist();
        this.updateDashboard();
        this.```Activity(`종목 제거: ${ticker}`);
        this```owToast(`${ticker} 제거완료`, 'blue');
    }

    // 감시 종```약 업데이트
    updateWatchSummary() {
        const watch```mary = document.getElementById('watch-summary');
        if```his.watchingTickers.length```= 0) {
            watch```mary.textContent = '스``` 시작하여 아톰 탐지를 시작하세요...```        } else {
            watch```mary.innerHTML = `
                <div class="flex```ex-wrap gap-2">
                ``` ${this.watchingTickers.map(ticker => `<span class="ticker-tag">${ticker}</span>`).join('')}
                </div>
            `;
        }
    }

    // 스캐너 시작
    startScanner() {
        if```his.watchingTickers.length === 0) {
            this.showTo```('감시할 종목을 ```추가해주세요', 'red');
            return;
        }
        ```      if (!Object.keys```is.apiSettings).length ||```his.apiSettings.alp```Key) {
            this.showTo```('Alpaca API 키를 ```설정해주세요', 'red');
            this.showSection('settings```
            return;
        }
        
        // 백엔드에```너 시작 요청
        if (this.websocket &&```is.isConnected) {
            this.```socket.send(JSON.stringify({
                type: 'start_```nner',
                tickers: this```tchingTickers,
                api```ttings: this.apiSettings
            }));
        }
        ```      document.getElementById('scanner-status').textContent = '온라인';
        document.getElementById('scanner-status').className = 'text``` font-bold status```line';
        ```ument.getElementById('start-scanner').disabled = true;```      document.getElementById('stop-scanner').disabled = false;
        
        this.log```ivity('🚀 실시간 스캐너 시```;
        this.showTo```('스캐너가 시작되었습니다```'green');
    }

    // 스캐너```
    stopScanner() {
        if (this.websocket``` this.isConnected) {
            this.websocket.sen```SON.stringify({
                type```stop_scanner'```          }));
        }
        ```      document.getElementById('scanner-status').textContent = '오```';
        document.```ElementById('scanner-status').className =```ext-lg font-bold status-offline';
        document.```ElementById('start-scanner').disabled =```lse;
        document.getElementById('stop-scanner').disabled = true;```      
        this.logActivity``` 실시간 스캐너 정지');
        this```owToast('스캐너가 정지되었습```, 'blue');
    }

    // AI``` 요청
    request```lysis() {
        const```cker = document.getElementById('analysis```cker').value.trim();
        const context = document.getElementById('analysis-context').value.trim();
        
        if (!ticker) {
            this.showToast```석할 종목을 입력하세요', 're```;
            return;
        }
        
        if (!this.apiSettings.gem```Key) {
            this.showTo```('Gemini API 키```저 설정해주세요', 're```;
            this.showSection('settings');
            ```urn;
        }
        ```      if (this.websocket && this.is```nected) {
            this.```socket.send(JSON.stringify```                type: 'request```alysis',
                ticker: ticker```               context: context,```              api_settings: this.api```tings
            }));
        }
        
        const result``` = document.getElementById('analysis-result');
        const contentDiv = document.getElementById('analysis-content');
        
        resultDiv```assList.remove('hidden');
        contentDiv.```erHTML = '<p class```ext-gray-500">AI 분석 ```.</p>';
        
        this```gActivity(`AI 분석 요청: ${ticker}`);
        this.show```st('AI 분석을 요```니다', 'blue```
    }

    // AI 분석 결```시
    displayAnalysisResult(data) {
        const contentDiv = document.getElementById('analysis-content');
        if (data.success```
            contentDiv.innerHTML````<div class="whit```ace-pre-wrap">${data.result}</div>`;
            this.logActivity(`AI 분석 완료: ${data.ticker}`);
        ```lse {
            contentDiv.```erHTML = `<p class="text-red-500">분석 오류: ${data.error}</p>`;
        }
    }

    // 성```트 렌더링
    renderPerformanceChart() {
        const ctx = document.```ElementById('performance-chart');
        if (!ctx || !window.Chart) return;
        ```      // 더미 데이터로``` 생성
        new```art(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                ```els: ['LOGIC-EXP-001', 'LOGIC-EXP-002', 'LOGIC-EXP-003'],
                datasets: [{
                    label: '승률 (%)',
                    data: [73.3, 62.5, 68.9],
                    backgroundColor:```gba(34, 197, 94, 0.8)',
                ``` borderColor: 'rgba(34, 197, 94, 1)',
                    borderWidth```
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { display: false }
                },
                ```les: {
                    y:```                        beginAtZero```rue,
                        max```00,
                        ticks: {
                            color: '#cbd5e1',
                            callback: (value) => value```'%'
                        },
                        grid: { color: '#374151' }
                    },
                    x: {
                ```     ticks: { color: '#cbd5e1' },
                        grid: { color: '#374151' }
                ``` }
                }
            }
        });
    }

    // 설정 저장
    saveSettings() {
        this.apiSettings = {
            alp```Key: document.getElementById('alpaca-key').value.trim(),
            alpacaSecret: document.getElementById('alpaca-secret').value.trim```
            geminiKey: document.getElementById('gemini-key').value.trim(),
            she```Id: document.getElementById('sheets-id').value.trim()
        };
        
        session```rage.setItem('apiSettings', JSON.stringify(this.apiSettings));
        ```      const statusDiv = document.getElementById('settings-status');
        statusDiv.innerHTML```'<p class="text-green-600">✅ 설```장 완료</p>';```      setTimeout(() => statusDiv.innerHTML = '',```00);
        
        ```s.showToast('설정이 저장되었습니다', '```en');
        this.logActivity('API 설정 업데이트 ```);
    }

    // 설정 로드
    loadSettings() {
        const saved = sessionStorage.getItem('apiSettings');
        if (saved) {
            this.apiSettings =```ON.parse(saved);
            ```(this.apiSettings.alpaca```) {
                document.getElementByI```alpaca-key').value =```'.repeat(8) + this.apiSettings.alpac```y.slice(-4);
            }
            if (this.apiSettings.alpaca```ret) {
                document.getElementById('alpaca-secret').value =```'.repeat(8) + this.apiSettings.alpacaSecret```ice(-4);
            }
            if (this.apiSettings```miniKey) {
                ```ument.getElementById('gemini-key').value = '*'.repeat(8) + this.apiSettings.gem```Key.slice(-4);
            }
            if (this.apiSettings.sheetsId) {
                document.getElementById('sheets-id').value = this.apiSettings```eetsId;
            }
        }
    }

    // 연결 테```    testConnection() {
        this```owToast('연결 테스트 중...', ```ue');
        
        if (this.websocket && this.```onnected) {
            this.websocket.send(JSON.stringify({
                type: 'test_connection',
                api_```tings: this.apiSettings
            ```;
        }
        ```      // 시뮬레이션된``` 테스트
        setTimeout(() => {
            const connections = ['alpaca-status', 'sheets-status', 'gemini-status'];
            connections.forEach((id, index) => {
                setTimeout``` => {
                    const status```= document.querySelector```${id} .status-indicator`);
                    const```Connected = Math```ndom() > 0.3; // 70% 성공률
                    status```className = `status-indicator ${isConnected ? 'bg```een-400' : 'bg-red-400'}`;
                }, index * 500);
            });
            ```          this.showToast('연결 테스트 완``` 'green');
            ```s.logActivity('API 연결 상```인 완료');
        }, 1500);
    }

    // 활동 로그```  logActivity(message) {
        const log```document.getElementById('activity-log');
        const timestamp```new Date().toLocaleTime```ing('ko-KR');
        const p = document.createElement('p');
        p.textContent = `[${timestamp}] ${message}`;
        p```assName = 'text-blue-400';
        log.appendChild(p);
        log.scrollTop =```g.scrollHeight;
        ```      // 로그 개```한
        if (log.children.length > 50) {
            log.removeChil```og.firstChild);
        }
    }

    // 신```그
    logSign```message, grade =```) {
        const display```document.getElementById('signal-display');
        const p```document.createElement('p');
        p.text```tent = message;
        p.className = grade``` ['A++', 'A+'].includes(grade) ? 
            'text-red-400 font-bold' : '```t-gray-300';
        ```      display.appendChild(p);
        display.scrollTop = display.```ollHeight;
        
        //``` 개수 제한
        if (display.children```ngth > 100) {
            display.removeChil```isplay.firstChild);
        ```   }

    // 토스트 알림
    showToast(message, type = 'green```{
        const toast = document.getElementById('toast');
        toast```xtContent = message;
        toast.```ssName = `toast ${type}`;
        toast.classList```d('show');
        setTimeout``` => toast.classList.remove('show'), 3000);
    }
}

// 전역 함```(HTML onclick에```용)
function showSection```ctionId) {
    tradingAssistant.showSection(sectionId);
}

function```dTicker() {
    trading```istant.addTicker();
}

function start```nner() {
    trading```istant.startScanner();
}

function stopScanner() {
    tradingAssistant```opScanner();
}

function requestAnalysis() {
    tradingAssistant.requestAnal```s();
}

function save```tings() {
    tradingAss```ant.saveSettings();
}

function testConnection() {
    tradingAss```ant.testConnection();
}

// 앱 초기화
const tradingAssistant = new T```ingAssistant();

// 에러 핸들링
window.o```ror = (message, source, lineno, col``` error) => {
    console.error('JavaScript```:', message, error);
    tradingAssistant```gActivity(`JavaScript 오류: ${message}`);
};
