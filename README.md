"# middleProject_4team_202603" 

# 🐰 AI Math Tutor — 루미와 함께하는 초등 수학

> 초등학교 5학년 학생을 위한 AI 기반 1:1 수학 튜터링 서비스  
> LangGraph 워크플로우 + FastAPI 백엔드 + HTML/JS 프론트엔드

---

## 🚀 시작하기

### 1. 환경 설정
``` bash

# 저장소 클론
git clone https://github.com/ilangs/middleProject_4team_20260311

# 가상환경 생성 및 활성화
python -m venv .venv
.venv\Scripts\activate        # Windows

# 패키지 설치
pip install -r requirements.txt

```
### 2. 환경변수 설정

`.env` 파일에 아래 값을 채워 주세요:
```bash

OPENAI_API_KEY="sk-..."

# LangSmith 설정 (에이전트 로그 및 추적용)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT="Project_4team" # 4팀 2차 프로젝트명
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_VERBOSE=true

# 랭스미스 API 키 (https://smith.langchain.com 에서 발급받은 키 입력)
LANGCHAIN_API_KEY="lsv2_pt_..." # 본인 발급키

## JWT 서명용 비밀키
# Terminal에 아래 명령어로 생성:
#   python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY="본인 발급키"


```
### 3. 서버 실행
```bash

uvicorn server:app --reload --port 8000


```
### 4. 프론트엔드 실행
```bash

`frontend/login.html`에서 오른쪽 클릭 → **Open with Live Server** (기본 포트: 5500)

```

### 🔄 AI 수학 튜터 데이터 전처리 및 RAG 파이프라인

# 1단계: 원본 데이터 수집 및 병합 (collect_data_tutor.py)

- 역할: 압축 파일(ZIP) 내부에 흩어져 있는 수많은 JSON 파일들을 순회하며, OCR로 인식된 '문제 텍스트'와 '정답 텍스트'를 추출합니다.
- 결과물: 문제와 정답이 1:1로 매칭된 초기 형태의 통합 CSV 파일을 생성합니다. (이때 컬럼은 풀이및정답 형태로 묶여 있습니다.)

# 2단계: AI 기반 데이터 정제 (csv_refiner.py)

- 역할: 1단계에서 만들어진 초기 CSV를 읽어 들여, OpenAI LLM(gpt-4o)을 활용해 데이터를 가공합니다.
- 결과물: 단순했던 풀이및정답을 명확한 정답과 초등학생 눈높이에 맞춘 친절한 풀이 컬럼으로 분리 및 변환하여 최종 학습용 CSV 데이터셋을 완성합니다.

# 3단계: 벡터 DB 저장 모듈 (rag_helper.py)

- 역할: 2단계에서 완성된 최종 CSV 데이터를 어떻게 쪼개고(Batch), 어떤 임베딩 모델(text-embedding-3-small)을 사용하여 ChromaDB에 넣을지 '기능과 도구'를 정의해 두는 핵심 모듈입니다.

# 4단계: 벡터 DB 구축 실행 (build_vector_db.py)

- 역할: 실제 터미널에서 실행(python build_vector_db.py)하여 3단계의 도구를 작동시키는 '실행 버튼(Caller)' 역할을 합니다. 이 파일이 실행되면 최종적으로 RAG 시스템이 참고할 수 있는 벡터 데이터베이스가 완성됩니다.


## 투트랙(Two-Track) 데이터 조회 구조
실제 상용 AI 교육 서비스에서도 사용하는 매우 훌륭하고 안정적인 아키텍처

# 1. 오늘의 학습 & 시험 (CSV/SQLite 직접 조회)
- 목적: "1-1단원 문제 중 난이도 하 5개를 가져와라"처럼 아주 정확한 조건이 필요합니다.
- 장점: 벡터 검색을 쓰면 엉뚱한 단원의 비슷한 문제가 섞일 수 있지만, DB에서 직접 꺼내오면 정확하게 원하는 문제만 가져올 수 있어서 속도도 훨씬 빠르고 에러 확률도 없습니다. 마치 교과서 목차를 보고 정확한 페이지를 펴는 것과 같습니다.

# 2. AI 자유학습 채팅 (ChromaDB RAG 검색)
- 목적: 학생이 "받아올림이 있는 덧셈이 너무 헷갈려요"라거나 "사과 3개랑 배 5개 더하는 거 어떻게 해요?"처럼 정해지지 않은 형태로 질문합니다.
- 장점: 이때는 정확한 단원명이나 ID를 모르기 때문에, 학생의 질문과 '가장 의미가 비슷한' 과거 문제와 풀이를 찾아야 합니다. 이때 ChromaDB의 시맨틱(의미) 검색 능력이 과거의 비슷한 문제 풀이를 참조하여 맞춤형 힌트를 줄 수 있습니다.


## 📋 개발 환경

- Python 3.12
- Windows 11
- VS Code + Live Server 확장


## 📄 라이선스

본 프로젝트는 교육 목적으로 제작되었습니다.