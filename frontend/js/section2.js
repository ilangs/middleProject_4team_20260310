// ─────────────────────────────────────────────────────────
// section2.js  ─  AI 자유학습 (🤖 free) 섹션
//
// [역할]
//   학생이 수학 관련 질문을 입력하면, AI 튜터 '루미'가
//   로컬 벡터DB(RAG) 검색 결과를 참고하여 친절하게 답변합니다.
//   벡터DB에 적절한 내용이 없으면 LLM이 직접 답변합니다.
//
// [주요 기능]
//   1. 채팅 UI (학생 메시지 → 오른쪽, AI 메시지 → 왼쪽)
//   2. 수학 외 질문 필터링 (서버에서 LLM으로 판별)
//   3. TTS 음성 듣기/중지 토글 버튼 (각 AI 답변마다)
//   4. 답변 복사 버튼 (클립보드에 복사)
//   5. 대화 기록 DB 저장 및 복원
//
// [사용되는 외부 함수]
//   - apiFetch(path, options) : app.js에 정의된 API 호출 헬퍼
//   - renderMath(targetId)    : app.js에 정의된 MathJax 렌더링
// ─────────────────────────────────────────────────────────

// ========================================================
// 전역 변수
// ========================================================

// 채팅 기록을 메모리에 보관 (서버 전송 시 컨텍스트로 사용)
var freeChatHistory = [];

// 초기화 완료 여부 (이벤트 중복 바인딩 방지)
var freeInited = false;

// 현재 재생 중인 TTS 오디오 객체와 버튼을 추적
// → 새로운 음성 재생 시 기존 재생을 먼저 중지하기 위함
var freeCurrentAudio = null;       // 현재 재생 중인 Audio 객체
var freeCurrentTtsBtn = null;      // 현재 활성화된 TTS 버튼


// ========================================================
// 초기화 함수 ─ goPage("free") 호출 시 실행됨
// ========================================================

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

async function loadFreeChatHistory() {
    // 메시지가 표시될 컨테이너 요소
    var container = document.getElementById("free-chat-messages");
    if (!container) return;

    // 화면과 메모리 초기화
    container.innerHTML = "";
    freeChatHistory = [];

    try {
        // 서버에서 채팅 기록 가져오기 (GET /api/free/history)
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
                role: msg.role,
                content: msg.content
            });
        });

        // 화면에 말풍선 복원 (스크롤은 마지막에 한 번만)
        history.forEach(function (msg) {
            appendChatBubble(msg.role, msg.content, true);  // skipScroll = true
        });

        // 모든 말풍선 추가 후 → 최하단으로 스크롤
        scrollToBottom();

    } catch (err) {
        console.error("채팅 기록 불러오기 오류:", err);
    }
}


// ========================================================
// 메시지 전송 처리 (핵심 함수)
// ========================================================

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

    // ── 1. 학생 메시지를 화면에 표시 ──
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
                chat_history: freeChatHistory   // 이전 대화 기록 함께 전송
            })
        });

        // 로딩 말풍선 제거
        removeLoadingBubble(loadingId);

        // 서버 오류 처리
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
        var ttsText = data.tts_text || answer; // 서버에서 받은 TTS 전용 텍스트

        // 메모리에 대화 기록 추가 (다음 질문의 컨텍스트로 사용)
        freeChatHistory.push({ role: "user", content: question });
        freeChatHistory.push({ role: "assistant", content: answer });

        // ── 5. AI 응답을 화면에 표시 ──
        // appendChatBubble 호출 시 ttsText도 함께 전달
        appendChatBubble("assistant", answer, false, ttsText);

    } catch (err) {
        // 로딩 말풍선 제거
        removeLoadingBubble(loadingId);

        console.error("자유학습 채팅 오류:", err);
        appendChatBubble(
            "assistant",
            "네트워크 오류가 발생했어요. 인터넷 연결을 확인해 주세요."
        );

    } finally {
        // ── 6. 전송 버튼 다시 활성화 ──
        if (sendBtn) sendBtn.disabled = false;

        // ── 7. 입력창에 포커스 복귀 (바로 다음 질문 입력 가능) ──
        if (input) input.focus();
    }
}


// ========================================================
// 말풍선 추가 (화면에 메시지 렌더링)
// ========================================================

function appendChatBubble(role, content, skipScroll, ttsText) {
    // skipScroll: true이면 스크롤 안 함 (대량 복원 시 사용)
    // ttsText: (선택) 음성으로 읽어줄 한글 텍스트. 없으면 content 사용

    // 메시지 컨테이너 요소
    var container = document.getElementById("free-chat-messages");
    if (!container) return;

    // 메시지 행 요소 생성
    var row = document.createElement("div");
    row.className = "free-msg-row " + role;

    // 말풍선 요소 생성
    var bubble = document.createElement("div");
    bubble.className = "free-msg-bubble";
    bubble.innerText = content;  

    if (role === "assistant") {
        var wrapper = document.createElement("div");
        wrapper.className = "free-msg-wrapper";
        wrapper.appendChild(bubble);

        var btnRow = document.createElement("div");
        btnRow.className = "free-btn-row";

        var ttsBtn = document.createElement("button");
        ttsBtn.type = "button";               
        ttsBtn.className = "free-tts-btn";
        ttsBtn.innerText = "🔊 음성 듣기";
        ttsBtn.dataset.ttsState = "idle";     

        // ⭐ ttsText가 넘어오지 않으면(과거 대화 등), 정제 함수를 거친 텍스트를 읽도록 설정
        var textToRead = ttsText || cleanTextForCopy(content);

        ttsBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();               
            toggleFreeTTS(textToRead, ttsBtn);
        });

        var copyBtn = document.createElement("button");
        copyBtn.type = "button";               
        copyBtn.className = "free-copy-btn";
        copyBtn.innerText = "📋 답변 복사";

        // ⭐ 복사 버튼 클릭 이벤트
        copyBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            
            // ⭐ 이 부분이 추가되었습니다! (위에서 만든 함수 적용)
            var textToCopy = cleanTextForCopy(content);
            
            // 원본 content 대신 textToCopy를 클립보드로 전송
            copyAnswerToClipboard(textToCopy, copyBtn);
        });

        btnRow.appendChild(ttsBtn);
        btnRow.appendChild(copyBtn);
        wrapper.appendChild(btnRow);

        row.appendChild(wrapper);

    } else {
        row.appendChild(bubble);
    }

    container.appendChild(row);

    if (typeof MathJax !== "undefined" && MathJax.typesetPromise) {
        MathJax.typesetPromise([row]).catch(function (err) {
            console.error("MathJax 렌더링 오류:", err);
        });
    }

    if (!skipScroll) {
        scrollToBottom();
    }
}


// ========================================================
// 로딩 말풍선 표시 / 제거
// ========================================================

function showLoadingBubble() {
    // 메시지 컨테이너
    var container = document.getElementById("free-chat-messages");
    if (!container) return null;

    // 고유 ID 생성 (나중에 제거할 때 사용)
    var id = "free-loading-" + Date.now();

    // AI 위치(왼쪽)에 로딩 말풍선 생성
    var row = document.createElement("div");
    row.className = "free-msg-row assistant";
    row.id = id;

    var bubble = document.createElement("div");
    bubble.className = "free-msg-bubble";
    // 점이 깜빡이는 로딩 애니메이션
    bubble.innerHTML =
        '<span class="free-loading-dot" style="animation-delay:0s">●</span> ' +
        '<span class="free-loading-dot" style="animation-delay:0.2s">●</span> ' +
        '<span class="free-loading-dot" style="animation-delay:0.4s">●</span> ' +
        " 루미가 생각하는 중...";

    row.appendChild(bubble);
    container.appendChild(row);

    // 로딩 표시 후 스크롤
    scrollToBottom();

    return id;  // 제거 시 사용할 ID 반환
}


function removeLoadingBubble(loadingId) {
    // loadingId에 해당하는 로딩 말풍선을 화면에서 제거
    if (!loadingId) return;

    var el = document.getElementById(loadingId);
    if (el) el.remove();
}


// ========================================================
// TTS 음성 재생/중지 토글 (핵심 수정)
//
// [동작 흐름]
//   - "음성 듣기" 클릭 → API로 음성 생성 → 재생 시작 → 버튼이 "음성 중지"로 변경
//   - "음성 중지" 클릭 → 일시정지 → 버튼이 "음성 듣기"로 변경
//   - "음성 듣기" 다시 클릭 → 멈춘 지점부터 이어서 재생
//   - 재생이 끝까지 완료되면 → 자동으로 "음성 듣기"로 리셋
// ========================================================

async function toggleFreeTTS(text, btn) {
    // text: 읽어줄 텍스트 내용
    // btn: 클릭한 TTS 버튼

    if (!text || !btn) return;

    // 현재 버튼의 상태 확인
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

    // 다른 버튼에서 재생 중인 음성이 있으면 먼저 중지
    stopOtherTTS(btn);

    // 버튼 상태를 "생성 중"으로 변경
    btn.dataset.ttsState = "loading";
    btn.innerText = "🔊 생성 중...";
    btn.disabled = true;

    // ⭐ 추가: TTS 엔진이 헷갈리는 기호와 특정 단어의 발음을 완벽한 한글로 강제 교정
    var safeText = text.replace(/÷/g, " 나누기 ")
                       .replace(/=/g, " 은 ")
                       .replace(/×/g, " 고파기 ")
                       .replace(/\+/g, " 더하기 ")
                       .replace(/-/g, " 빼기 ")
                       .replace(/\\div/g, " 나누기 ")
                       .replace(/\\times/g, " 고파기 ")
                       .replace(/나눗셈/g, "나누쎔"); // 나눅셈으로 읽히는 버그 방지

    try {
        // TTS API 호출 (POST /api/tts)
        var res = await apiFetch("/api/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            // ⭐ 기존의 text 대신 교정된 safeText를 백엔드로 전송하도록 수정
            body: JSON.stringify({ text: safeText })
        });

        if (!res.ok) throw new Error("TTS API 오류");

        var data = await res.json();

        if (!data.audio_b64) throw new Error("오디오 데이터 없음");

        // Audio 객체 생성
        var audio = new Audio("data:audio/mp3;base64," + data.audio_b64);

        // 버튼에 Audio 객체 연결 (나중에 일시정지/재개에 사용)
        btn._audioObj = audio;

        // 재생 완료 시 → 버튼을 "음성 듣기"로 리셋
        audio.addEventListener("ended", function () {
            btn.dataset.ttsState = "idle";
            btn.innerText = "🔊 음성 듣기";
            btn._audioObj = null;  // 참조 해제

            // 전역 추적 변수 초기화
            if (freeCurrentTtsBtn === btn) {
                freeCurrentAudio = null;
                freeCurrentTtsBtn = null;
            }
        });

        // 전역 추적 변수 업데이트
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
        if (window.speechSynthesis) {
            window.speechSynthesis.cancel();  // 이전 재생 중지

            var utt = new SpeechSynthesisUtterance(text);
            utt.lang = "ko-KR";  // 한국어 음성

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
            btn._useBrowserTTS = true;

            // 전역 추적
            freeCurrentTtsBtn = btn;

            window.speechSynthesis.speak(utt);

            btn.disabled = false;
            btn.dataset.ttsState = "playing";
            btn.innerText = "⏸️ 음성 중지";

        } else {
            // 음성 기능 자체를 사용할 수 없는 브라우저
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

function pauseFreeTTS(btn) {
    if (btn._useBrowserTTS) {
        // 브라우저 TTS 일시정지
        if (window.speechSynthesis && window.speechSynthesis.speaking) {
            window.speechSynthesis.pause();
        }
    } else if (btn._audioObj) {
        // OpenAI TTS Audio 객체 일시정지
        btn._audioObj.pause();
    }

    // 버튼 상태 업데이트
    btn.dataset.ttsState = "paused";
    btn.innerText = "🔊 음성 듣기";
}


// ────────────────────────────────────────
// TTS 이어서 재생 (멈춘 지점부터)
// ────────────────────────────────────────

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

function stopOtherTTS(currentBtn) {
    // 현재 재생 중인 다른 버튼이 있으면 완전히 중지
    if (freeCurrentTtsBtn && freeCurrentTtsBtn !== currentBtn) {
        var otherBtn = freeCurrentTtsBtn;

        if (otherBtn._useBrowserTTS) {
            // 브라우저 TTS 중지
            if (window.speechSynthesis) {
                window.speechSynthesis.cancel();
            }
        } else if (otherBtn._audioObj) {
            // Audio 객체 중지 + 참조 해제
            otherBtn._audioObj.pause();
            otherBtn._audioObj.currentTime = 0;
            otherBtn._audioObj = null;
        }

        // 이전 버튼을 대기 상태로 리셋
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
            // 2초 후 원래 텍스트로 복원
            setTimeout(function () {
                btn.innerText = "📋 답변 복사";
            }, 2000);
        }

    } catch (err) {
        // clipboard API 실패 시 fallback (구형 브라우저 지원)
        console.warn("Clipboard API 실패, fallback 사용:", err);

        try {
            // textarea를 임시로 만들어 복사하는 방법
            var textarea = document.createElement("textarea");
            textarea.value = text;
            textarea.style.position = "fixed";
            textarea.style.opacity = "0";
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand("copy");
            document.body.removeChild(textarea);

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

// 복사용 텍스트 정제 함수 (수식 기호를 일반 문자로 변환)
function cleanTextForCopy(text) {
    if (!text) return "";
    var res = text;
    
    // 1. 분수 변환 (\frac{a}{b} -> a / b)
    res = res.replace(/\\frac{([^}]+)}{([^}]+)}/g, "$2분의 $1");

    // 2. 자주 쓰이는 수학 기호를 실제 기호로 변경
    res = res.replace(/\\pi/g, "π");
    res = res.replace(/\\times/g, "×");
    res = res.replace(/\\div/g, "÷");
    res = res.replace(/\\sqrt/g, "√");
    
    // 3. 수식 묶음 괄호 및 $ 기호 제거
    res = res.replace(/\\\[/g, "");
    res = res.replace(/\\\]/g, "");
    res = res.replace(/\\\(/g, "");
    res = res.replace(/\\\)/g, "");
    res = res.replace(/\$/g, "");

    // 4. 남은 백슬래시(\) 모두 제거 (메모장 ₩ 표시 방지)
    res = res.replace(/\\/g, "");
    
    return res.trim();
}

// ========================================================
// 스크롤 최하단 이동
// ========================================================

function scrollToBottom() {
    var container = document.getElementById("free-chat-messages");
    if (!container) return;

    // DOM 렌더링 완료 후 스크롤하기 위해 약간의 지연 추가
    setTimeout(function () {
        container.scrollTop = container.scrollHeight;
    }, 50);
}
