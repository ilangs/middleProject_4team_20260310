/**
 * ============================================================
 * section2.js  -  AI 자유학습 (🤖 free) 섹션
 * ============================================================
 *
 * [역할]
 *   학생이 수학 관련 질문을 입력하면, AI 튜터 '루미'가
 *   로컬 벡터DB(RAG) 검색 결과를 참고하여 친절하게 답변합니다.
 *   벡터DB에 적절한 내용이 없으면 LLM이 직접 답변합니다.
 *
 * [사용 페이지] frontend/app.html (id="page-free" 섹션)
 *
 * [주요 기능]
 *   1. 채팅 UI (학생 메시지 → 오른쪽, AI 메시지 → 왼쪽)
 *   2. 수학 외 질문 필터링 (서버에서 LLM으로 판별)
 *   3. TTS 음성 듣기/중지 토글 버튼 (각 AI 답변마다)
 *   4. 답변 복사 버튼 (클립보드에 복사)
 *   5. 대화 기록 DB 저장 및 복원
 *
 * [RAG(Retrieval-Augmented Generation)란?]
 *   질문에 답하기 전에 먼저 로컬 문서 데이터베이스(벡터DB)에서
 *   관련 내용을 검색하고, 그 내용을 참고해 답변을 생성하는 기술.
 *   "교과서를 먼저 찾아보고 답하는 AI" 라고 생각하면 됩니다.
 *
 * [사용되는 외부 함수 - app.js에 정의]
 *   - apiFetch(path, options) : 인증 헤더가 포함된 API 호출 헬퍼
 *   - renderMath(targetId)    : MathJax 수식 렌더링
 *
 * [학습 포인트 - 3주차 AI 에이전트 과정]
 *   - 채팅 대화 기록(chat_history) 관리 패턴
 *   - TTS(Text-to-Speech) 상태 머신 구현
 *   - Clipboard API를 이용한 텍스트 복사
 *   - 로딩 말풍선 UX 패턴
 * ============================================================
 */

// ========================================================
// 전역 변수
// ========================================================

// 채팅 기록을 메모리에 보관 (서버 전송 시 컨텍스트로 사용)
// 형식: [{ role: "user", content: "..." }, { role: "assistant", content: "..." }, ...]
// → AI가 이전 대화를 기억하면서 맥락에 맞는 답변을 하기 위해 필요합니다
var freeChatHistory = [];

// 초기화 완료 여부 (이벤트 중복 바인딩 방지)
// true이면 bindFreeChatEvents()를 다시 실행하지 않습니다
var freeInited = false;

// 현재 재생 중인 TTS 오디오 객체와 버튼을 추적
// → 새로운 음성 재생 시 기존 재생을 먼저 중지하기 위함
var freeCurrentAudio = null;       // 현재 재생 중인 Audio 객체
var freeCurrentTtsBtn = null;      // 현재 활성화된 TTS 버튼 (상태 리셋용)


// ========================================================
// 초기화 함수 - goPage("free") 호출 시 실행됨
// ========================================================

/**
 * initFreeChat()
 * ─────────────────────────────────────
 * [역할] 자유학습 채팅 섹션이 처음 열릴 때 초기화 작업을 수행합니다.
 *        goPage("free")에서 호출됩니다.
 *
 * [초기화 순서]
 *   1. 이벤트 바인딩 (최초 1회만 실행)
 *   2. 서버에서 이전 대화 기록 불러와 화면에 복원
 *   3. 입력창에 자동 포커스 (바로 타이핑 가능)
 *
 * [freeInited 패턴]
 *   goPage("free")를 여러 번 호출해도 이벤트 리스너가
 *   중복으로 등록되지 않도록 방지합니다.
 */
async function initFreeChat() {
    // 이벤트 바인딩은 최초 1회만 실행 (중복 방지)
    if (!freeInited) {
        bindFreeChatEvents();  // 버튼 클릭, Enter 키 이벤트 등록
        freeInited = true;
    }

    // 서버에서 이전 대화 기록을 불러와 화면에 표시
    await loadFreeChatHistory();

    // 입력창에 자동 포커스 (바로 타이핑 가능)
    var input = document.getElementById("free-chat-input");
    if (input) input.focus();
}


// ========================================================
// 이벤트 바인딩 (전송 버튼 + Enter 키)
// ========================================================

/**
 * bindFreeChatEvents()
 * ─────────────────────────────────────
 * [역할] 채팅 전송 버튼과 Enter 키에 메시지 전송 이벤트를 등록합니다.
 *        initFreeChat()에서 최초 1회 호출됩니다.
 *
 * [이벤트 등록 대상]
 *   - id="free-chat-send-btn" 클릭 → handleFreeChatSend()
 *   - id="free-chat-input" Enter 키 → handleFreeChatSend()
 *     (Shift+Enter는 줄바꿈으로 처리, 전송 안 함)
 *
 * [e.preventDefault() / e.stopPropagation() 사용 이유]
 *   preventDefault(): 브라우저 기본 동작 방지 (폼 제출로 페이지 리로드 방지)
 *   stopPropagation(): 이벤트 버블링 차단 (상위 요소에 이벤트 전파 방지)
 */
function bindFreeChatEvents() {
    // 전송 버튼 요소 가져오기
    var sendBtn = document.getElementById("free-chat-send-btn");
    // 입력창 요소 가져오기
    var input = document.getElementById("free-chat-input");

    // 전송 버튼 클릭 시 → 메시지 전송 처리
    if (sendBtn) {
        sendBtn.addEventListener("click", function (e) {
            e.preventDefault();        // 기본 동작 방지
            e.stopPropagation();       // 이벤트 버블링 차단
            handleFreeChatSend();
        });
    }

    // Enter 키 입력 시 → 메시지 전송 (Shift+Enter는 무시)
    if (input) {
        input.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();        // 기본 동작(폼 제출) 방지
                e.stopPropagation();       // 이벤트 버블링 차단
                handleFreeChatSend();
            }
        });
    }
}


// ========================================================
// 대화 기록 불러오기 (서버 → 화면 복원)
// ========================================================

/**
 * loadFreeChatHistory()
 * ─────────────────────────────────────
 * [역할] 서버 DB에 저장된 이전 채팅 기록을 불러와 화면에 복원합니다.
 *        자유학습 페이지를 다시 열어도 대화 내용이 유지됩니다.
 *
 * [호출 시점] initFreeChat() 내에서 호출
 *
 * [API 호출]
 *   엔드포인트: GET /api/free/history
 *   응답 예시: {
 *     history: [
 *       { role: "user", content: "분수가 뭐야?" },
 *       { role: "assistant", content: "분수는 전체를 나눈..." }
 *     ]
 *   }
 *
 * [성능 최적화 - skipScroll 패턴]
 *   여러 메시지를 복원할 때 각 메시지마다 스크롤하면 느립니다.
 *   모든 메시지 추가 후 마지막에 한 번만 스크롤합니다.
 */
async function loadFreeChatHistory() {
    // 메시지가 표시될 컨테이너 요소
    var container = document.getElementById("free-chat-messages");
    if (!container) return;

    // 화면과 메모리 초기화 (이전 내용 지우기)
    container.innerHTML = "";
    freeChatHistory = [];

    try {
        // GET /api/free/history: 서버에서 채팅 기록 가져오기
        var res = await apiFetch("/api/free/history");

        if (!res.ok) {
            console.error("채팅 기록 로드 실패:", res.status);
            return;
        }

        var data = await res.json();
        var history = data.history || [];  // 배열 형태의 메시지 목록

        // 메모리에 대화 기록 복원 (다음 질문 시 컨텍스트로 전송)
        history.forEach(function (msg) {
            freeChatHistory.push({
                role: msg.role,       // "user" 또는 "assistant"
                content: msg.content  // 메시지 내용
            });
        });

        // 화면에 말풍선 복원 (skipScroll = true → 각 추가 시 스크롤 안 함)
        history.forEach(function (msg) {
            appendChatBubble(msg.role, msg.content, true);  // skipScroll = true
        });

        // 모든 말풍선 추가 후 → 최하단으로 스크롤 (마지막 메시지 보이게)
        scrollToBottom();

    } catch (err) {
        console.error("채팅 기록 불러오기 오류:", err);
    }
}


// ========================================================
// 메시지 전송 처리 (핵심 함수)
// ========================================================

/**
 * handleFreeChatSend()
 * ─────────────────────────────────────
 * [역할] 학생이 입력한 질문을 서버에 전송하고, AI 답변을 받아 화면에 표시합니다.
 *        채팅의 핵심 로직을 담당합니다.
 *
 * [호출 시점]
 *   - 전송 버튼 클릭 시
 *   - 입력창에서 Enter 키 입력 시
 *
 * [처리 순서]
 *   1. 입력값 가져오기 (빈 입력 무시)
 *   2. 학생 메시지를 화면에 즉시 표시 (오른쪽 말풍선)
 *   3. 로딩 말풍선 표시 ("루미가 생각하는 중...")
 *   4. POST /api/free/chat 로 질문 전송 (이전 대화 기록 포함)
 *   5. 서버 응답(AI 답변) 받기
 *   6. AI 답변 말풍선 화면에 표시 (왼쪽 말풍선 + TTS 버튼 + 복사 버튼)
 *   7. 전송 버튼 다시 활성화
 *
 * [API 호출]
 *   엔드포인트: POST /api/free/chat
 *   전송 데이터: {
 *     question: "학생 질문",
 *     chat_history: [{ role: "user", content: "..." }, ...]  // 이전 대화 기록
 *   }
 *   응답 예시: {
 *     answer: "분수는 전체를 나눈 부분이에요...",
 *     tts_text: "음성으로 읽어줄 한글 텍스트" (LaTeX 기호 제거 버전)
 *   }
 */
async function handleFreeChatSend() {
    // 입력창과 전송 버튼 요소 가져오기
    var input = document.getElementById("free-chat-input");
    var sendBtn = document.getElementById("free-chat-send-btn");

    if (!input) return;

    // 입력 내용 가져오기 (앞뒤 공백 제거)
    var question = input.value.trim();

    // 빈 입력은 무시
    if (!question) return;

    // ── 입력창 비우기 + 버튼 비활성화 (중복 전송 방지) ──
    input.value = "";
    if (sendBtn) sendBtn.disabled = true;

    // ── 1. 학생 메시지를 화면에 표시 (오른쪽 말풍선) ──
    appendChatBubble("user", question);

    // ── 2. 로딩 표시 (AI가 생각하는 중...) ──
    var loadingId = showLoadingBubble();

    try {
        // ── 3. 서버에 질문 전송 ──
        var res = await apiFetch("/api/free/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question: question,
                chat_history: freeChatHistory   // 이전 대화 기록 함께 전송 (맥락 유지)
            })
        });

        // 로딩 말풍선 제거 (AI 답변 또는 오류 표시 전에 제거)
        removeLoadingBubble(loadingId);

        // 서버 오류 처리 (4xx, 5xx 응답)
        if (!res.ok) {
            var errData = await res.json().catch(function () { return {}; });
            appendChatBubble(
                "assistant",
                errData.detail || "서버 오류가 발생했어요. 다시 시도해 주세요."
            );
            return;
        }

        // ── 4. 서버 응답 처리 ──
        var data = await res.json();
        console.log("⭐ 서버 응답 데이터:", data); // 데이터가 잘 오는지 확인!

        var answer = data.answer || "답변을 생성하지 못했어요.";
        var ttsText = data.tts_text || answer; // 서버에서 받은 TTS 전용 텍스트 (LaTeX 기호 없는 버전)

        // 메모리에 대화 기록 추가 (다음 질문의 컨텍스트로 사용)
        freeChatHistory.push({ role: "user", content: question });
        freeChatHistory.push({ role: "assistant", content: answer });

        // ── 5. AI 응답을 화면에 표시 ──
        // appendChatBubble 호출 시 ttsText도 함께 전달
        appendChatBubble("assistant", answer, false, ttsText);

    } catch (err) {
        // 로딩 말풍선 제거 (오류 시에도 제거)
        removeLoadingBubble(loadingId);

        console.error("자유학습 채팅 오류:", err);
        appendChatBubble(
            "assistant",
            "네트워크 오류가 발생했어요. 인터넷 연결을 확인해 주세요."
        );

    } finally {
        // ── 6. 전송 버튼 다시 활성화 (성공/실패 모두) ──
        if (sendBtn) sendBtn.disabled = false;

        // ── 7. 입력창에 포커스 복귀 (바로 다음 질문 입력 가능) ──
        if (input) input.focus();
    }
}


// ========================================================
// 말풍선 추가 (화면에 메시지 렌더링)
// ========================================================

/**
 * appendChatBubble(role, content, skipScroll, ttsText)
 * ─────────────────────────────────────
 * [역할] 채팅 메시지를 화면에 말풍선 형태로 추가합니다.
 *        학생 메시지는 오른쪽, AI 메시지는 왼쪽에 표시됩니다.
 *
 * [말풍선 구조]
 *   학생(user):
 *     [말풍선]                       (오른쪽 정렬)
 *
 *   AI(assistant):
 *     [말풍선]                       (왼쪽 정렬)
 *     [🔊 음성 듣기] [📋 답변 복사]  (버튼 행)
 *
 * [ttsText 파라미터]
 *   서버에서 받은 TTS용 텍스트(LaTeX 기호 제거 버전)를 음성으로 읽어줍니다.
 *   없으면 cleanTextForCopy()로 정제한 content를 사용합니다.
 *
 * [MathJax 렌더링]
 *   말풍선 추가 후 수식(\frac{} 등)을 예쁘게 렌더링합니다.
 *
 * @param {string}      role       - "user" 또는 "assistant"
 * @param {string}      content    - 표시할 메시지 내용
 * @param {boolean}     skipScroll - true이면 스크롤 안 함 (대량 복원 시)
 * @param {string|undefined} ttsText - TTS로 읽어줄 텍스트 (없으면 content 사용)
 */
function appendChatBubble(role, content, skipScroll, ttsText) {
    // skipScroll: true이면 스크롤 안 함 (대량 복원 시 사용)
    // ttsText: (선택) 음성으로 읽어줄 한글 텍스트. 없으면 content 사용

    // 메시지 컨테이너 요소 (모든 말풍선이 담기는 div)
    var container = document.getElementById("free-chat-messages");
    if (!container) return;

    // 메시지 행(row) 요소 생성 (학생=오른쪽, AI=왼쪽 정렬 CSS 적용)
    var row = document.createElement("div");
    row.className = "free-msg-row " + role;  // CSS: .free-msg-row.user → 오른쪽, .assistant → 왼쪽

    // 말풍선(bubble) 요소 생성
    var bubble = document.createElement("div");
    bubble.className = "free-msg-bubble";
    bubble.innerText = content;   // 내용 설정 (innerHTML 대신 innerText로 XSS 방지)

    if (role === "assistant") {
        // AI 메시지: 말풍선 + 버튼들을 묶는 wrapper div 생성
        var wrapper = document.createElement("div");
        wrapper.className = "free-msg-wrapper";
        wrapper.appendChild(bubble);  // 말풍선 추가

        // 버튼 행(btnRow) 생성: TTS 버튼 + 복사 버튼
        var btnRow = document.createElement("div");
        btnRow.className = "free-btn-row";

        // TTS(Text-to-Speech) 버튼 생성
        var ttsBtn = document.createElement("button");
        ttsBtn.type = "button";               // 폼 제출 방지
        ttsBtn.className = "free-tts-btn";
        ttsBtn.innerText = "🔊 음성 듣기";
        ttsBtn.dataset.ttsState = "idle";     // 초기 상태: 대기 중

        // ⭐ ttsText가 넘어오지 않으면(과거 대화 등), 정제 함수를 거친 텍스트를 읽도록 설정
        // LaTeX 기호를 제거해 TTS 엔진이 제대로 읽을 수 있는 텍스트로 변환
        var textToRead = ttsText || cleanTextForCopy(content);

        // TTS 버튼 클릭 이벤트 등록
        ttsBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            // 클릭 시 재생/일시정지 토글
            toggleFreeTTS(textToRead, ttsBtn);
        });

        // 복사 버튼 생성
        var copyBtn = document.createElement("button");
        copyBtn.type = "button";               // 폼 제출 방지
        copyBtn.className = "free-copy-btn";
        copyBtn.innerText = "📋 답변 복사";

        // ⭐ 복사 버튼 클릭 이벤트
        copyBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();

            // ⭐ 이 부분이 추가되었습니다! (위에서 만든 함수 적용)
            // LaTeX 기호를 일반 텍스트로 변환 후 복사
            var textToCopy = cleanTextForCopy(content);

            // 원본 content 대신 textToCopy를 클립보드로 전송
            copyAnswerToClipboard(textToCopy, copyBtn);
        });

        // 버튼들을 행에 추가
        btnRow.appendChild(ttsBtn);
        btnRow.appendChild(copyBtn);
        wrapper.appendChild(btnRow);  // 버튼 행을 wrapper에 추가

        row.appendChild(wrapper);  // wrapper를 메시지 행에 추가

    } else {
        // 학생 메시지: 말풍선만 추가 (버튼 없음)
        row.appendChild(bubble);
    }

    // 메시지 행을 컨테이너에 추가
    container.appendChild(row);

    // MathJax 수식 렌더링 (라이브러리가 로드된 경우에만)
    if (typeof MathJax !== "undefined" && MathJax.typesetPromise) {
        MathJax.typesetPromise([row]).catch(function (err) {
            console.error("MathJax 렌더링 오류:", err);
        });
    }

    // skipScroll이 false이면 최하단으로 스크롤
    if (!skipScroll) {
        scrollToBottom();
    }
}


// ========================================================
// 로딩 말풍선 표시 / 제거
// ========================================================

/**
 * showLoadingBubble()
 * ─────────────────────────────────────
 * [역할] AI가 응답을 생성하는 동안 "루미가 생각하는 중..." 로딩 표시를 합니다.
 *        점이 깜빡이는 CSS 애니메이션이 적용된 말풍선입니다.
 *
 * [호출 시점] handleFreeChatSend()에서 서버 요청 직전에 호출
 *
 * [고유 ID 패턴]
 *   Date.now()를 이용해 고유한 ID를 생성합니다.
 *   나중에 removeLoadingBubble()에서 이 ID로 정확히 해당 말풍선을 찾아 제거합니다.
 *
 * @returns {string} 생성된 로딩 말풍선의 고유 ID (제거 시 사용)
 */
function showLoadingBubble() {
    // 메시지 컨테이너
    var container = document.getElementById("free-chat-messages");
    if (!container) return null;

    // 고유 ID 생성 (나중에 제거할 때 사용)
    // Date.now() → 현재 시각(밀리초) → 고유한 숫자
    var id = "free-loading-" + Date.now();

    // AI 위치(왼쪽)에 로딩 말풍선 생성
    var row = document.createElement("div");
    row.className = "free-msg-row assistant";  // AI 메시지(왼쪽 정렬)
    row.id = id;                               // 고유 ID 부여

    var bubble = document.createElement("div");
    bubble.className = "free-msg-bubble";
    // 점이 깜빡이는 로딩 애니메이션 (CSS에서 @keyframes로 구현)
    bubble.innerHTML =
        '<span class="free-loading-dot" style="animation-delay:0s">●</span> ' +
        '<span class="free-loading-dot" style="animation-delay:0.2s">●</span> ' +
        '<span class="free-loading-dot" style="animation-delay:0.4s">●</span> ' +
        " 루미가 생각하는 중...";

    row.appendChild(bubble);
    container.appendChild(row);

    // 로딩 표시 후 스크롤 (사용자가 로딩 표시를 볼 수 있게)
    scrollToBottom();

    return id;  // 제거 시 사용할 ID 반환
}


/**
 * removeLoadingBubble(loadingId)
 * ─────────────────────────────────────
 * [역할] showLoadingBubble()이 만든 로딩 말풍선을 화면에서 제거합니다.
 *
 * [호출 시점]
 *   - 서버 응답을 정상적으로 받은 후
 *   - 서버 오류가 발생한 후
 *   - 네트워크 오류가 발생한 후
 *
 * @param {string} loadingId - showLoadingBubble()이 반환한 고유 ID
 */
function removeLoadingBubble(loadingId) {
    // loadingId에 해당하는 로딩 말풍선을 화면에서 제거
    if (!loadingId) return;

    var el = document.getElementById(loadingId);
    if (el) el.remove();  // DOM에서 완전히 제거
}


// ========================================================
// TTS 음성 재생/중지 토글 (핵심 수정)
//
// [TTS 상태 머신]
//   idle     : 아무것도 재생하지 않는 초기/완료 상태
//   loading  : 서버에서 오디오 파일 생성 중
//   playing  : 음성 재생 중
//   paused   : 일시정지 상태
//
// [동작 흐름]
//   - "음성 듣기" 클릭 → API로 음성 생성 → 재생 시작 → 버튼이 "음성 중지"로 변경
//   - "음성 중지" 클릭 → 일시정지 → 버튼이 "음성 듣기"로 변경
//   - "음성 듣기" 다시 클릭 → 멈춘 지점부터 이어서 재생
//   - 재생이 끝까지 완료되면 → 자동으로 "음성 듣기"로 리셋
// ========================================================

/**
 * toggleFreeTTS(text, btn)
 * ─────────────────────────────────────
 * [역할] TTS 버튼 클릭 시 현재 상태에 따라 재생/일시정지/이어서재생을 처리합니다.
 *
 * [상태별 동작]
 *   - playing  → pauseFreeTTS()  : 일시정지
 *   - paused   → resumeFreeTTS() : 멈춘 지점부터 이어서 재생
 *   - loading  → 무시 (이미 처리 중)
 *   - idle     → TTS 생성 후 재생 시작
 *
 * [API 호출]
 *   엔드포인트: POST /api/tts
 *   전송 데이터: { text: "읽어줄 텍스트" }
 *   응답 예시:  { audio_b64: "base64MP3데이터" }
 *
 * [폴백(Fallback) 처리]
 *   서버 TTS API 호출 실패 시 → 브라우저 내장 Web Speech API로 대체
 *   Web Speech API: window.speechSynthesis (현대 브라우저 대부분 지원)
 *
 * [safeText 전처리]
 *   TTS 엔진이 수학 기호를 읽지 못하거나 이상하게 읽는 문제 해결:
 *   · ÷ → " 나누기 "
 *   · × → " 고파기 " (TTS 발음 교정)
 *   · + → " 더하기 "
 *   · - → " 빼기 "
 *   · = → " 은 "
 *
 * @param {string}      text - 읽어줄 텍스트 내용
 * @param {HTMLElement} btn  - 클릭한 TTS 버튼 (상태 표시용)
 */
async function toggleFreeTTS(text, btn) {
    // text: 읽어줄 텍스트 내용
    // btn: 클릭한 TTS 버튼

    if (!text || !btn) return;

    // 버튼의 data-tts-state 속성으로 현재 상태 확인
    var state = btn.dataset.ttsState || "idle";

    // ── 상태별 분기 처리 ──

    if (state === "playing") {
        // ── [재생 중] → 일시정지 ──
        pauseFreeTTS(btn);
        return;
    }

    if (state === "paused") {
        // ── [일시정지] → 멈춘 지점부터 이어서 재생 ──
        resumeFreeTTS(btn);
        return;
    }

    if (state === "loading") {
        // ── [생성 중] → 아직 로딩 중이므로 무시 ──
        return;
    }

    // ── [idle: 대기 상태] → 음성 생성 후 재생 시작 ──

    // 다른 버튼에서 재생 중인 음성이 있으면 먼저 중지 (한 번에 하나만 재생)
    stopOtherTTS(btn);

    // 버튼 상태를 "생성 중"으로 변경
    btn.dataset.ttsState = "loading";
    btn.innerText = "🔊 생성 중...";
    btn.disabled = true;  // 생성 완료 전까지 버튼 비활성화

    // ⭐ 추가: TTS 엔진이 헷갈리는 기호와 특정 단어의 발음을 완벽한 한글로 강제 교정
    var safeText = text.replace(/÷/g, " 나누기 ")
                       .replace(/=/g, " 은 ")
                       .replace(/×/g, " 고파기 ")
                       .replace(/\+/g, " 더하기 ")
                       .replace(/-/g, " 빼기 ")
                       .replace(/\\div/g, " 나누기 ")
                       .replace(/\\times/g, " 고파기 ")
                       .replace(/나눗셈/g, "나누쎔"); // 나눗셈이 "나눅셈"으로 읽히는 버그 방지

    try {
        // TTS API 호출 (POST /api/tts): 텍스트 → MP3 변환
        var res = await apiFetch("/api/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: safeText })
        });

        if (!res.ok) throw new Error("TTS API 오류");

        var data = await res.json();

        // ⭐ 핵심 수정: section1.js와 동일하게 문자열/객체 응답을 모두 안전하게 커버합니다!
        // 응답이 문자열 → 그 자체가 base64
        // 응답이 객체 → data.audio_b64 에서 추출
        var audioData = typeof data === "string" ? data : data.audio_b64;

        if (!audioData) throw new Error("오디오 데이터 없음");

        // base64 MP3 데이터로 Audio 객체 생성
        var audio = new Audio("data:audio/mp3;base64," + audioData);

        // 버튼에 Audio 객체 연결 (나중에 일시정지/재개에 사용)
        btn._audioObj = audio;

        // 재생 완료 시 → 버튼을 "음성 듣기"로 리셋
        audio.addEventListener("ended", function () {
            btn.dataset.ttsState = "idle";
            btn.innerText = "🔊 음성 듣기";
            btn._audioObj = null;  // 참조 해제 (메모리 정리)

            // 전역 추적 변수 초기화
            if (freeCurrentTtsBtn === btn) {
                freeCurrentAudio = null;
                freeCurrentTtsBtn = null;
            }
        });

        // 전역 추적 변수 업데이트 (다른 버튼 클릭 시 이 오디오를 중지하기 위해)
        freeCurrentAudio = audio;
        freeCurrentTtsBtn = btn;

        // 재생 시작
        audio.play();

        // 버튼 상태를 "재생 중"으로 변경
        btn.disabled = false;
        btn.dataset.ttsState = "playing";
        btn.innerText = "⏸️ 음성 중지";

    } catch (err) {
        console.warn("TTS 실패, 브라우저 음성으로 대체:", err);

        // 브라우저 기본 음성 합성으로 대체 (Web Speech API)
        // 서버 TTS 실패 시에도 최소한 음성은 들려주기 위한 폴백
        if (window.speechSynthesis) {
            window.speechSynthesis.cancel();  // 이전 재생 중지

            var utt = new SpeechSynthesisUtterance(text);
            utt.lang = "ko-KR";  // 한국어 음성으로 설정

            // 브라우저 TTS 종료 시 버튼 리셋
            utt.addEventListener("end", function () {
                btn.dataset.ttsState = "idle";
                btn.innerText = "🔊 음성 듣기";
                if (freeCurrentTtsBtn === btn) {
                    freeCurrentAudio = null;
                    freeCurrentTtsBtn = null;
                }
            });

            // 브라우저 TTS는 pause/resume을 위해 _utterance에 저장
            btn._utterance = utt;
            btn._useBrowserTTS = true;  // 브라우저 TTS 사용 중 표시

            // 전역 추적
            freeCurrentTtsBtn = btn;

            // 브라우저 TTS 재생 시작
            window.speechSynthesis.speak(utt);

            btn.disabled = false;
            btn.dataset.ttsState = "playing";
            btn.innerText = "⏸️ 음성 중지";

        } else {
            // 음성 기능 자체를 사용할 수 없는 구형 브라우저
            btn.disabled = false;
            btn.dataset.ttsState = "idle";
            btn.innerText = "🔊 음성 듣기";
            alert("이 브라우저에서는 음성 기능을 사용할 수 없습니다.");
        }
    }
}


// ────────────────────────────────────────
// TTS 일시정지
// ────────────────────────────────────────

/**
 * pauseFreeTTS(btn)
 * ─────────────────────────────────────
 * [역할] 현재 재생 중인 TTS 음성을 일시정지합니다.
 *        버튼 상태를 "paused"로 변경합니다.
 *
 * [브라우저 TTS vs 서버 TTS]
 *   - 서버 TTS:   btn._audioObj.pause() → 정확한 위치에서 일시정지
 *   - 브라우저 TTS: speechSynthesis.pause() → 일시정지 (브라우저마다 지원 차이 있음)
 *
 * @param {HTMLElement} btn - 클릭된 TTS 버튼
 */
function pauseFreeTTS(btn) {
    if (btn._useBrowserTTS) {
        // 브라우저 TTS 일시정지 (Web Speech API)
        if (window.speechSynthesis && window.speechSynthesis.speaking) {
            window.speechSynthesis.pause();
        }
    } else if (btn._audioObj) {
        // OpenAI TTS Audio 객체 일시정지
        btn._audioObj.pause();
    }

    // 버튼 상태 업데이트
    btn.dataset.ttsState = "paused";
    btn.innerText = "🔊 음성 듣기";  // "이어서 듣기" 대신 동일 텍스트 유지
}


// ────────────────────────────────────────
// TTS 이어서 재생 (멈춘 지점부터)
// ────────────────────────────────────────

/**
 * resumeFreeTTS(btn)
 * ─────────────────────────────────────
 * [역할] 일시정지된 TTS 음성을 멈춘 지점부터 이어서 재생합니다.
 *        버튼 상태를 "playing"으로 변경합니다.
 *
 * @param {HTMLElement} btn - 클릭된 TTS 버튼
 */
function resumeFreeTTS(btn) {
    if (btn._useBrowserTTS) {
        // 브라우저 TTS 이어서 재생
        if (window.speechSynthesis && window.speechSynthesis.paused) {
            window.speechSynthesis.resume();
        }
    } else if (btn._audioObj) {
        // OpenAI TTS Audio 객체 이어서 재생
        btn._audioObj.play();
    }

    // 버튼 상태 업데이트
    btn.dataset.ttsState = "playing";
    btn.innerText = "⏸️ 음성 중지";
}


// ────────────────────────────────────────
// 다른 버튼의 TTS 재생 중지
// (새 음성을 재생하기 전에 기존 재생을 정리)
// ────────────────────────────────────────

/**
 * stopOtherTTS(currentBtn)
 * ─────────────────────────────────────
 * [역할] 새로운 TTS 버튼이 클릭될 때, 이전에 재생 중이던 다른 버튼의
 *        음성을 완전히 중지하고 초기화합니다.
 *        한 번에 하나의 음성만 재생되도록 보장합니다.
 *
 * [호출 시점]
 *   - toggleFreeTTS()에서 idle 상태일 때 (새 음성 재생 시작 전)
 *   - section1.js의 toggleModalTTS()에서도 호출
 *
 * @param {HTMLElement} currentBtn - 현재 클릭된 버튼 (이 버튼 외의 버튼을 중지)
 */
function stopOtherTTS(currentBtn) {
    // 현재 재생 중인 다른 버튼이 있으면 완전히 중지
    if (freeCurrentTtsBtn && freeCurrentTtsBtn !== currentBtn) {
        var otherBtn = freeCurrentTtsBtn;

        if (otherBtn._useBrowserTTS) {
            // 브라우저 TTS 중지 (cancel: 완전 종료, pause와 다름)
            if (window.speechSynthesis) {
                window.speechSynthesis.cancel();
            }
        } else if (otherBtn._audioObj) {
            // Audio 객체 중지 + 처음으로 되감기 + 참조 해제
            otherBtn._audioObj.pause();
            otherBtn._audioObj.currentTime = 0;
            otherBtn._audioObj = null;
        }

        // 이전 버튼을 대기 상태로 리셋 (사용자가 다시 재생할 수 있게)
        otherBtn.dataset.ttsState = "idle";
        otherBtn.innerText = "🔊 음성 듣기";
        otherBtn._useBrowserTTS = false;
    }

    // 전역 추적 변수 초기화
    freeCurrentAudio = null;
    freeCurrentTtsBtn = null;
}


// ========================================================
// 답변 복사 (클립보드에 텍스트 복사)
// ========================================================

/**
 * copyAnswerToClipboard(text, btn)
 * ─────────────────────────────────────
 * [역할] AI 답변을 클립보드에 복사합니다.
 *        복사 성공 시 버튼 텍스트를 "✅ 복사 완료!"로 일시 변경합니다.
 *
 * [Clipboard API]
 *   navigator.clipboard.writeText() : 최신 브라우저의 표준 클립보드 API
 *   HTTPS 환경에서만 동작합니다.
 *
 * [Fallback 처리]
 *   Clipboard API 실패 시 → 임시 textarea를 생성해 document.execCommand("copy")로
 *   구형 방식으로 복사합니다. 구형 브라우저도 지원하기 위한 호환성 처리입니다.
 *
 * @param {string}      text - 복사할 텍스트 내용
 * @param {HTMLElement} btn  - 클릭된 복사 버튼 (상태 표시용)
 */
async function copyAnswerToClipboard(text, btn) {
    // text: 복사할 AI 답변 텍스트
    // btn: 클릭한 복사 버튼 (상태 표시용)

    if (!text) return;

    try {
        // 클립보드에 텍스트 복사 (navigator.clipboard API 사용)
        await navigator.clipboard.writeText(text);

        // 복사 성공 → 버튼 텍스트를 잠시 "복사 완료!"로 변경
        if (btn) {
            btn.innerText = "✅ 복사 완료!";
            // 2초 후 원래 텍스트로 복원 (setTimeout으로 지연 처리)
            setTimeout(function () {
                btn.innerText = "📋 답변 복사";
            }, 2000);
        }

    } catch (err) {
        // clipboard API 실패 시 fallback (구형 브라우저 지원)
        console.warn("Clipboard API 실패, fallback 사용:", err);

        try {
            // 임시 textarea를 DOM에 추가해 복사하는 구형 방법
            var textarea = document.createElement("textarea");
            textarea.value = text;
            textarea.style.position = "fixed";  // 화면 위치 고정
            textarea.style.opacity = "0";        // 사용자에게 보이지 않게
            document.body.appendChild(textarea);
            textarea.select();                   // 전체 선택
            document.execCommand("copy");        // 복사 명령 실행
            document.body.removeChild(textarea); // 임시 textarea 제거

            if (btn) {
                btn.innerText = "✅ 복사 완료!";
                setTimeout(function () {
                    btn.innerText = "📋 답변 복사";
                }, 2000);
            }

        } catch (fallbackErr) {
            console.error("복사 실패:", fallbackErr);
            alert("복사에 실패했습니다. 직접 텍스트를 선택하여 복사해 주세요.");
        }
    }
}

/**
 * cleanTextForCopy(text)
 * ─────────────────────────────────────
 * [역할] LaTeX 수식 기호가 포함된 텍스트를 복사하거나 TTS로 읽기 적합한
 *        일반 텍스트로 변환합니다.
 *
 * [변환 내용]
 *   1. \frac{a}{b} → "b분의 a" (분수 표현)
 *   2. \pi → π (파이 기호)
 *   3. \times → × (곱셈 기호)
 *   4. \div → ÷ (나눗셈 기호)
 *   5. \sqrt → √ (루트 기호)
 *   6. 수식 묶음 괄호 (\[, \], \(, \)), $ 기호 제거
 *   7. 남은 백슬래시(\) 모두 제거 (Windows 메모장에서 ₩로 표시되는 버그 방지)
 *
 * @param {string} text - LaTeX 기호가 포함된 텍스트
 * @returns {string} 정제된 일반 텍스트
 */
// 복사용 텍스트 정제 함수 (수식 기호를 일반 문자로 변환)
function cleanTextForCopy(text) {
    if (!text) return "";
    var res = text;

    // 1. 분수 변환 (\frac{a}{b} -> a / b)
    // 예: \frac{1}{2} → 2분의 1
    res = res.replace(/\\frac{([^}]+)}{([^}]+)}/g, "$2분의 $1");

    // 2. 자주 쓰이는 수학 기호를 실제 기호로 변경
    res = res.replace(/\\pi/g, "π");          // 원주율 기호
    res = res.replace(/\\times/g, "×");       // 곱셈 기호
    res = res.replace(/\\div/g, "÷");         // 나눗셈 기호
    res = res.replace(/\\sqrt/g, "√");        // 루트 기호

    // 3. 수식 묶음 괄호 및 $ 기호 제거 (LaTeX 구분자)
    res = res.replace(/\\\[/g, "");   // \[ 제거 (블록 수식 시작)
    res = res.replace(/\\\]/g, "");   // \] 제거 (블록 수식 끝)
    res = res.replace(/\\\(/g, "");   // \( 제거 (인라인 수식 시작)
    res = res.replace(/\\\)/g, "");   // \) 제거 (인라인 수식 끝)
    res = res.replace(/\$/g, "");     // $ 제거 (수식 구분자)

    // 4. 남은 백슬래시(\) 모두 제거 (메모장에서 ₩ 표시 방지)
    res = res.replace(/\\/g, "");

    return res.trim();
}

// ========================================================
// 스크롤 최하단 이동
// ========================================================

/**
 * scrollToBottom()
 * ─────────────────────────────────────
 * [역할] 채팅 메시지 컨테이너를 맨 아래로 스크롤합니다.
 *        새 메시지가 추가될 때 자동으로 최신 메시지가 보이도록 합니다.
 *
 * [setTimeout 사용 이유]
 *   DOM 업데이트(appendChild)는 즉시 반영되지만,
 *   브라우저의 레이아웃 재계산에 약간의 시간이 걸립니다.
 *   50ms 대기 후 스크롤하면 정확한 scrollHeight를 얻을 수 있습니다.
 */
function scrollToBottom() {
    var container = document.getElementById("free-chat-messages");
    if (!container) return;

    // DOM 렌더링 완료 후 스크롤하기 위해 약간의 지연 추가
    setTimeout(function () {
        // scrollTop을 scrollHeight로 설정하면 맨 아래로 스크롤
        container.scrollTop = container.scrollHeight;
    }, 50);
}
