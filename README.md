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
## 📋 개발 환경

- Python 3.12
- Windows 11
- VS Code + Live Server 확장


## 📄 라이선스

본 프로젝트는 교육 목적으로 제작되었습니다.