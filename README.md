# 🐰 AI Math Tutor — 루미와 함께하는 초등 수학

> **3주 AI Agent 과정 팀 프로젝트 | 4팀**
> 초등학교 5학년 학생을 위한 AI 기반 1:1 수학 튜터링 서비스
> LangChain · LangGraph · FastAPI · ChromaDB · OpenAI GPT-4o

---

## 📌 프로젝트 개요

| 항목 | 내용 |
|------|------|
| **프로젝트명** | AI Math Tutor — 루미와 함께하는 초등 수학 |
| **팀명** | 4팀 |
| **대상** | 초등학교 5학년 학생 |
| **목적** | AI를 활용한 개인 맞춤형 수학 튜터링으로 학습 효율 극대화 |
| **개발 기간** | 2025년 3월 (3주) |
| **기술 과정** | 3주 AI Agent 과정 중간 프로젝트 |

### 서비스 소개

루미(Lumi)는 초등학교 5학년 학생의 수학 학습을 돕는 AI 튜터 캐릭터입니다.
단순 문제 풀이를 넘어 **개념 설명 → 이해도 확인 → 문제 풀기 → AI 채점**의 완전한 학습 사이클을 제공하며,
RAG(Retrieval-Augmented Generation) 기반 자유 질문과 시험 기능, 성적 대시보드까지 갖춘 종합 학습 플랫폼입니다.

---

## ✨ 주요 기능

### 1. 오늘의 학습 (단계별 학습 사이클)

```
단원 선택 → AI 개념 설명 → 이해도 평가 → 문제 풀기 → AI 채점
```

- **단원 선택**: CSV 데이터셋에서 추출한 실제 5학년 수학 단원 목록 제공
- **AI 개념 설명**: GPT-4o가 루미 캐릭터로 해당 단원 개념을 초등학생 눈높이에 맞게 설명
- **보충 설명**: "다시 설명해줘" 버튼으로 더 쉬운 추가 설명 요청 가능
- **이해도 평가**: 학생이 자신의 말로 개념을 설명하면 AI가 [PASS] / [FAIL] 판정 + 격려 피드백 제공
- **문제 풀기**: 선택 단원에서 무작위 문제 1개 출제 (이미지 문제 포함)
- **AI 채점**: 학생 답변을 GPT-4o가 채점하고 [정답] / [오답] + 상세 풀이 피드백 제공
- **TTS 음성**: OpenAI TTS(nova 목소리)로 개념 설명과 피드백을 음성으로 재생

---

### 2. AI 자유학습 채팅 (RAG + LLM)

```
학생 질문 입력 → 수학 질문 분류 → ChromaDB RAG 검색 → GPT-4o 맞춤 답변
```

- 정해진 단원 없이 **자유롭게 수학 관련 질문** 가능
- **수학 질문 필터링**: LLM이 먼저 수학 관련 질문인지 분류 (비관련 질문 차단)
- **RAG 기반 답변**: ChromaDB에서 의미적으로 유사한 기출 문제·풀이를 검색하여 맥락 있는 힌트 제공
- **대화 기록 유지**: 이전 대화 컨텍스트를 포함하여 연속 질문 가능
- **채팅 기록 저장**: 대화 내용이 DB에 저장되어 재접속 시 이전 대화 복원

---

### 3. 단원 시험 (자동 출제 → 채점 → 결과 저장)

```
단원 선택 → 10문제 자동 출제 → 일괄 제출 → AI 병렬 채점 → 결과 저장
```

- **자동 출제**: 선택 단원에서 10문제를 무작위로 추출 (CSV 직접 조회)
- **일괄 채점**: `asyncio.gather()`로 10문제를 **병렬 처리**하여 채점 속도 최적화
- **결과 저장**: 점수, 오답 번호, AI 피드백을 DB에 저장
- **시험 이력 조회**: 성적 대시보드에서 과거 시험 이력 확인 가능

---

### 4. 성적 대시보드 (학습 이력 · 정답률 · 오답노트)

- **학습 이력**: 오늘의 학습에서 푼 문제 기록 (단원, 정오답, 일시)
- **정답률 통계**: 전체 학습 기록 기반 정답률(%) 계산 및 시각화
- **시험 이력**: 단원별 시험 점수 추이 및 과거 시험 결과 목록
- **오답노트**: 한 번도 정답을 맞히지 못한 문제 목록 자동 생성

---

### 5. 토큰 사용 로그 (LLM API 비용 추적)

- **실시간 기록**: LLM 호출마다 `get_openai_callback()`으로 토큰 수·비용을 캡처
- **로컬 DB 저장**: LangSmith 의존 없이 로컬 SQLite(`token_logs` 테이블)에 저장
- **기능별 분류**: 개념설명 / 이해도평가 / 채점 / Q&A / AI자유학습 / 시험채점 등 action별 집계
- **비용 환산**: 프롬프트·컴플리션 토큰을 달러($) 및 원화(₩)로 환산하여 표시

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (HTML / JS)                          │
│   login.html · app.html · section1~5.js                         │
│   - 로그인/회원가입 UI                                            │
│   - 섹션별 기능 화면 (학습/채팅/시험/대시보드/토큰로그)             │
└──────────────────────────┬──────────────────────────────────────┘
                           │  HTTP fetch (JWT Bearer Token)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│               FastAPI Server (server.py)                         │
│                                                                  │
│   /auth/*  → routers/auth.py   (로그인·회원가입·JWT 발급)         │
│   /api/*   → routers/tutor.py  (AI 튜터 기능 전체)               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│             Service Layer (app/services/tutor_service.py)        │
│                      비즈니스 로직 처리                            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│          LangChain Integration (app/tutor/integration.py)        │
│                                                                  │
│   explain_chain · reexplain_chain · concept_chain               │
│   answer_chain · rag_chain · classify_chain                      │
│   generate_speech_with_cache (TTS + MD5 캐싱)                    │
└────────┬───────────────────────────────┬────────────────────────┘
         │                               │
         ▼                               ▼
┌─────────────────┐         ┌────────────────────────────────────┐
│  OpenAI GPT-4o  │         │         Two-Track 데이터 조회        │
│  (LLM + TTS)    │         │                                    │
│                 │         │  Track 1: CSV / SQLite 직접 조회    │
│  text-embedding │         │  - 오늘의 학습 (정확한 단원 필터링)   │
│  -3-small       │         │  - 단원 시험 (무작위 10문제 추출)    │
│  (RAG Embed)    │         │                                    │
└─────────────────┘         │  Track 2: ChromaDB RAG 검색        │
                            │  - AI 자유학습 채팅                 │
                            │  - 시맨틱(의미) 유사도 검색          │
                            └────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Layer                                    │
│   database/user_db.sqlite   - 사용자·학습·시험·채팅·토큰 로그     │
│   database/vector_store/    - ChromaDB 벡터 인덱스               │
│   data/processed/*.csv      - 수학 문제 데이터셋                  │
└─────────────────────────────────────────────────────────────────┘
```

### Two-Track 데이터 조회 구조

실제 AI 교육 서비스에서도 사용하는 안정적인 하이브리드 아키텍처입니다.

| 구분 | Track 1 (CSV / SQLite) | Track 2 (ChromaDB RAG) |
|------|------------------------|------------------------|
| **사용 기능** | 오늘의 학습, 단원 시험 | AI 자유학습 채팅 |
| **쿼리 방식** | 단원·난이도 조건 정확 필터링 | 의미(semantic) 유사도 검색 |
| **장점** | 빠른 속도, 정확한 단원 보장 | 자유로운 자연어 질문 처리 |
| **비유** | 교과서 목차로 페이지 바로 찾기 | 선생님이 비슷한 예제 찾아주기 |

---

## 🛠️ 기술 스택

| 분류 | 기술 | 버전 | 사용 이유 |
|------|------|------|-----------|
| **Web Framework** | FastAPI | latest | 비동기 처리, 자동 Swagger 문서, 타입 기반 유효성 검사 |
| **LLM Orchestration** | LangChain | latest | LLM 체인 구성, 프롬프트 관리, 콜백 처리 |
| **Agent Workflow** | LangGraph | latest | 상태 기반 워크플로우, 노드 간 조건 분기 처리 |
| **LLM Monitoring** | LangSmith | latest | 에이전트 실행 추적 및 디버깅 (선택적 사용) |
| **Vector DB** | ChromaDB | latest | 로컬 벡터 저장소, 시맨틱 검색, 별도 서버 불필요 |
| **LLM** | OpenAI GPT-4o | latest | 고성능 추론, 초등 눈높이 맞춤 설명, 한국어 우수 |
| **TTS** | OpenAI TTS (nova) | latest | 자연스러운 한국어 음성 합성 |
| **Embedding** | text-embedding-3-small | latest | RAG 벡터 생성, 비용 효율적 |
| **Database** | SQLite | 3.x | 별도 DB 서버 불필요, 로컬 개발에 적합 |
| **인증** | JWT (python-jose) | latest | Stateless 인증, 세션 서버 불필요 |
| **비밀번호 보안** | bcrypt (passlib) | latest | 단방향 해시, 솔트(salt) 자동 처리 |
| **Frontend** | Vanilla HTML/JS | - | 프레임워크 의존 없이 빠른 프로토타이핑 |
| **Runtime** | Python | 3.12 | LangChain 생태계 호환성 |

---

## 🔄 데이터 파이프라인 (RAG 구축 4단계)

```
원본 ZIP (JSON 파일들)
         │
         ▼
[1단계] collect_data_tutor.py
  - ZIP 내부 JSON 순회 → OCR 텍스트 추출
  - 문제(question) : 정답(answer) 1:1 매칭
  - 출력: 초기 통합 CSV (풀이및정답 컬럼)
         │
         ▼
[2단계] csv_refiner.py
  - OpenAI GPT-4o로 데이터 정제
  - '풀이및정답' → '정답' + '친절한 풀이' 컬럼 분리
  - 초등학생 눈높이 언어로 변환
  - 출력: 최종 학습용 CSV (math_tutor_dataset.csv)
         │
         ▼
[3단계] rag_helper.py
  - 임베딩 모델 설정 (text-embedding-3-small)
  - ChromaDB 연결 및 배치(Batch) 저장 도구 정의
  - RAG 검색 함수 정의
         │
         ▼
[4단계] build_vector_db.py  ← 실행 진입점
  - python build_vector_db.py 명령으로 실행
  - CSV 읽기 → rag_helper 호출 → ChromaDB 벡터 저장
  - 출력: database/vector_store/ (ChromaDB 인덱스)
         │
         ▼
ChromaDB 벡터 DB 완성
(AI 자유학습 채팅에서 RAG 검색에 사용)
```

---

## 📁 프로젝트 구조

```
middleProject_4team_202603_modified/
│
├── server.py                     # FastAPI 앱 진입점, 미들웨어·라우터 등록
├── requirements.txt              # Python 패키지 의존성 목록
├── .env                          # 환경변수 (API 키, JWT 시크릿 등)
│
├── app/                          # 백엔드 애플리케이션 코어
│   ├── routers/
│   │   ├── auth.py               # 로그인·회원가입·JWT 발급 API (/auth/*)
│   │   └── tutor.py              # AI 튜터 기능 전체 API (/api/*)
│   ├── services/
│   │   └── tutor_service.py      # 비즈니스 로직 (LLM 호출 조율)
│   ├── tutor/
│   │   └── integration.py        # LangChain 체인 정의, TTS 캐싱
│   └── utils/
│       └── db_manager.py         # SQLite CRUD, bcrypt 비밀번호 관리
│
├── frontend/                     # 프론트엔드 정적 파일
│   ├── login.html                # 로그인·회원가입 화면
│   ├── app.html                  # 메인 앱 화면 (로그인 후)
│   ├── js/
│   │   ├── app.js                # 공통 JS (인증, API fetch 유틸)
│   │   ├── section1.js           # 오늘의 학습
│   │   ├── section2.js           # AI 자유학습 채팅
│   │   ├── section3.js           # 단원 시험
│   │   ├── section4.js           # 성적 대시보드
│   │   └── section5.js           # 토큰 사용 로그
│   ├── css/                      # 스타일시트
│   └── assets/                   # 이미지·아이콘 등 미디어 파일
│
├── RAG_sys/                      # RAG 데이터 파이프라인
│   ├── collect_data_tutor.py     # [1단계] 원본 데이터 수집·병합
│   ├── csv_refiner.py            # [2단계] AI 기반 데이터 정제
│   ├── rag_helper.py             # [3단계] ChromaDB 저장 모듈 정의
│   └── build_vector_db.py        # [4단계] 벡터 DB 구축 실행 스크립트
│
├── data/
│   └── processed/
│       └── math_tutor_dataset.csv  # 정제된 최종 수학 문제 데이터셋
│
└── database/
    ├── user_db.sqlite              # SQLite DB (사용자·학습·시험·채팅·토큰)
    └── vector_store/
        └── chroma.sqlite3          # ChromaDB 벡터 인덱스
```

---

## 🔌 주요 API 엔드포인트

### 인증 (Authentication)

| Method | Path | 설명 | 인증 필요 |
|--------|------|------|-----------|
| `POST` | `/auth/login` | 로그인 → JWT 토큰 발급 | ❌ |
| `POST` | `/auth/register` | 회원가입 | ❌ |
| `GET` | `/auth/me` | 현재 로그인 사용자 정보 조회 | ✅ |
| `POST` | `/auth/logout` | 로그아웃 (클라이언트 토큰 삭제 안내) | ✅ |

### 오늘의 학습

| Method | Path | 설명 | LLM 사용 |
|--------|------|------|-----------|
| `GET` | `/api/units` | 단원 목록 조회 (CSV에서 추출) | ❌ |
| `GET` | `/api/problem?unit=...` | 단원별 무작위 문제 1개 조회 | ❌ |
| `POST` | `/api/explain` | AI 개념 설명 생성 | ✅ |
| `POST` | `/api/reexplain` | AI 보충(재) 설명 생성 | ✅ |
| `POST` | `/api/explain/evaluate` | 학생 이해도 평가 (PASS/FAIL) | ✅ |
| `POST` | `/api/ask` | 학습 중 Q&A 질문 | ✅ |
| `POST` | `/api/evaluate` | 학생 답변 채점 | ✅ |
| `POST` | `/api/history` | 학습 기록 저장 | ❌ |
| `GET` | `/api/history` | 학습 기록·정답률 조회 | ❌ |
| `GET` | `/api/history/incorrect` | 오답 문제 목록 조회 | ❌ |

### AI 자유학습 채팅

| Method | Path | 설명 | LLM 사용 |
|--------|------|------|-----------|
| `POST` | `/api/free/chat` | RAG + LLM 자유 학습 채팅 | ✅ (최대 2회) |
| `GET` | `/api/free/history` | 채팅 기록 조회 (최근 50건) | ❌ |

### 단원 시험

| Method | Path | 설명 | LLM 사용 |
|--------|------|------|-----------|
| `POST` | `/api/exam/generate` | 단원별 시험 문제 10개 출제 | ❌ |
| `POST` | `/api/exam/submit` | 시험 일괄 채점 (병렬 처리) | ✅ (×문제 수) |
| `POST` | `/api/exam/save-result` | 시험 결과 저장 | ❌ |
| `GET` | `/api/exam/results` | 시험 이력 조회 | ❌ |

### 기타

| Method | Path | 설명 | LLM 사용 |
|--------|------|------|-----------|
| `POST` | `/api/tts` | 텍스트 → 음성 변환 (MD5 캐싱) | ✅ (TTS) |
| `GET` | `/api/token/logs` | 토큰 사용량 통계 조회 | ❌ |
| `GET` | `/health` | 서버 상태 확인 (헬스체크) | ❌ |

> 모든 `/api/*` 엔드포인트는 `Authorization: Bearer <JWT>` 헤더 필요
> Swagger 문서: `http://localhost:8000/docs`

---

## 🚀 실행 방법

### 1. 저장소 클론

```bash
git clone https://github.com/ilangs/middleProject_4team_20260311
cd middleProject_4team_20260311
```

### 2. 가상환경 생성 및 활성화

```bash
# 가상환경 생성
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 아래 값을 채워주세요. (아래 [환경변수 설정] 섹션 참고)

### 5. 서버 실행

```bash
uvicorn server:app --reload --port 8000
```

### 6. 브라우저 접속

```
http://127.0.0.1:8000/
```

> **참고**: LangSmith 의존 없이 실행됩니다. 서버 시작 시 `LANGCHAIN_TRACING_V2=false`가 자동 적용되어
> LangSmith API 할당량 초과 에러를 방지합니다. 토큰 사용량은 로컬 SQLite DB에 저장됩니다.

---

## ⚙️ 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성합니다:

```bash
# ── OpenAI API ───────────────────────────────────────────
OPENAI_API_KEY="sk-..."           # OpenAI API 키 (필수)

# ── JWT 인증 ─────────────────────────────────────────────
# 아래 명령으로 생성:
#   python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY="여기에_발급된_시크릿_키_입력"

# ── LangSmith 설정 (선택적) ──────────────────────────────
# 에이전트 로그 추적이 필요한 경우에만 설정합니다.
# 미설정 시 서버가 자동으로 tracing을 비활성화합니다.
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_PROJECT="Project_4team"
# LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
# LANGCHAIN_API_KEY="lsv2_pt_..."
```

> **주의**: `.env` 파일은 절대 git에 커밋하지 마세요. `.gitignore`에 추가하여 관리합니다.

---

## 📊 토큰 사용량 추적 방식

LangSmith 없이도 LLM API 비용을 정확하게 추적하는 로컬 기반 방식을 채택했습니다.

### 작동 원리

```python
# routers/tutor.py 에서 LLM 호출마다 적용
from langchain_community.callbacks import get_openai_callback

with get_openai_callback() as cb:
    result = await some_llm_function(...)   # LLM 호출

# with 블록 종료 후 cb에 토큰 정보가 자동 집계됨
save_token_usage(
    username=current_user["username"],
    action="개념설명",                       # 기능명 분류
    prompt=cb.prompt_tokens,               # 입력 토큰 수
    completion=cb.completion_tokens,       # 출력 토큰 수
    total=cb.total_tokens,                 # 합계 토큰 수
    cost=cb.total_cost,                    # 달러 비용
)
```

### DB 테이블 구조 (`token_logs`)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | INTEGER | PK (자동 증가) |
| `username` | TEXT | 사용자 아이디 |
| `action` | TEXT | 기능 분류 (개념설명/채점/Q&A 등) |
| `prompt_tokens` | INTEGER | 입력(프롬프트) 토큰 수 |
| `completion_tokens` | INTEGER | 출력(컴플리션) 토큰 수 |
| `total_tokens` | INTEGER | 합계 토큰 수 |
| `cost_usd` | REAL | 달러 환산 비용 |
| `created_at` | TIMESTAMP | 호출 시각 |

### 비용 환산 기준 (GPT-4o)

| 구분 | 단가 |
|------|------|
| 입력 토큰 | $0.000005 / token |
| 출력 토큰 | $0.000015 / token |
| 달러→원 환율 | 1,350원/$ (고정값) |

> **기존 방식 대비 개선**: LangSmith API 할당량 초과 시 항상 0이 반환되던 문제를
> 로컬 SQLite 직접 저장 방식으로 전환하여 **항상 정확한 토큰 데이터**를 보장합니다.

---

## 👥 팀 구성

| 이름 | 역할 | 담당 영역 |
|------|------|-----------|
| 팀장	| Project Leader	| 프로젝트 총괄, 발표 및 LangChain 워크플로우(Chain) 설계 |
| 팀원 1	| Data Engineer	| 데이터 파이프라인(수집·정제) 구축, RAG 최적화 및 Vector DB |
| 팀원 2	| Backend Developer	| FastAPI 기반 API 서버 설계, JWT 보안 인증, DB 설계 |
| 팀원 3	| Frontend Developer	| UI/UX 구현(HTML/JS), 프론트-백엔드 기능 연동 |
| 팀원 4	| QA & DevRel	| 시스템 통합 테스트, 사용자 피드백 분석, 프로젝트 시연 자료 제작 |
| 팀원 5	| Product Planner	| 프로젝트 아이데이션(Ideation), 컨셉 및 비즈니스 로직 기획 |

---

## 📋 개발 환경

- **Python** 3.12
- **OS** Windows 11
- **IDE** VS Code
- **API 문서** `http://localhost:8000/docs` (Swagger UI 자동 생성)

---

## 📄 라이선스

본 프로젝트는 교육 목적으로 제작되었습니다.
3주 AI Agent 과정 중간 프로젝트 결과물입니다.
