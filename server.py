
##### 서버실행 : python -m uvicorn server:app --reload --port 8000
##
"""
server.py  ─  FastAPI 애플리케이션 진입점

[기존 main.py와의 역할 비교]
┌─────────────────────┬──────────────────────────────────┐
│    기존 main.py      │      새 server.py (FastAPI)      │
├─────────────────────┼──────────────────────────────────┤
│ Streamlit UI 렌더링  │  ❌ UI 없음 (HTML이 담당)         │
│ 세션 상태 관리        │  ✅ JWT 토큰으로 대체             │
│ 함수 직접 호출        │  ✅ HTTP API 엔드포인트로 노출     │
│ DB 직접 접근         │  ✅ db_manager 통해 간접 접근      │
└─────────────────────┴──────────────────────────────────┘

[전체 아키텍처 흐름]
브라우저(HTML/JS)
    │  HTTP 요청 (fetch)
    ▼
server.py  ← 지금 이 파일 (진입점, 라우터 연결, 미들웨어 설정)
    │
    ├── /auth/*   → app/routers/auth.py   (로그인, 회원가입, JWT 발급)
    └── /api/*    → app/routers/tutor.py  (AI 튜터 기능 전체)
                        │
                        └── app/services/tutor_service.py (비즈니스 로직)
                                │
                                └── app/tutor/integration.py (LangChain 체인 실행)
"""

# ─────────────────────────────────────────────────────────
# [임포트 섹션]
# FastAPI: 파이썬 웹 프레임워크. Flask보다 빠르고, 타입 힌트 기반 자동 문서화 지원.
# CORSMiddleware: 브라우저의 교차 출처 요청 차단을 허용하는 미들웨어.
# TrustedHostMiddleware: 허용된 호스트 이름의 요청만 수락하는 보안 미들웨어.
# StaticFiles: HTML/CSS/JS 같은 정적 파일을 특정 URL 경로에 연결.
# FileResponse: 파일 자체를 HTTP 응답으로 전송 (HTML 파일 서빙에 사용).
# ─────────────────────────────────────────────────────────
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# init_db: 서버 시작 시 SQLite DB 테이블을 생성하는 초기화 함수
from app.utils.db_manager import init_db

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# ─────────────────────────────────────────────────────────
# ① FastAPI 앱 인스턴스 생성
#
# [FastAPI란?]
# 파이썬으로 RESTful API 서버를 만드는 웹 프레임워크입니다.
# - 타입 힌트(type hints) 기반으로 자동 유효성 검사를 수행합니다.
# - /docs 경로로 접속하면 Swagger UI (자동 API 문서)를 볼 수 있습니다.
# - async/await 를 기본 지원하여 비동기 처리에 최적화되어 있습니다.
#
# [FastAPI vs Flask 비교]
# Flask : 동기 방식, 수동 문서화, 가볍고 오래된 프레임워크
# FastAPI: 비동기 방식, 자동 문서화(Swagger), 타입 검증, 최신 트렌드
#
# [HTTPBearer란?]
# HTTP Authorization 헤더에서 "Bearer <토큰>" 형식을 파싱합니다.
# Swagger UI의 자물쇠 아이콘을 통해 토큰을 직접 입력할 수 있게 해 줍니다.
# ─────────────────────────────────────────────────────────
from fastapi.security import HTTPBearer

# Swagger UI에서 Bearer 토큰 직접 입력을 위한 보안 스키마 인스턴스
security = HTTPBearer()

# LangSmith(LangChain 트레이싱) 비활성화 - API 할당량 초과 에러 방지
# 운영 환경에서는 .env 파일로 관리하는 것을 권장합니다.
os.environ["LANGCHAIN_TRACING_V2"] = "false" 

# FastAPI 앱 인스턴스 생성
# title, description, version은 /docs Swagger 문서에 표시됩니다.
# persistAuthorization: True → 브라우저 새로고침 후에도 Swagger의 인증 토큰이 유지됨
app = FastAPI(
    title="AI Math Tutor API",
    description="초등학교 5학년 수학 AI 튜터 백엔드 API",
    version="1.0.0",
    swagger_ui_parameters={"persistAuthorization": True},  # 새로고침 후에도 토큰 유지
)

# ─────────────────────────────────────────────────────────
# [정적 파일 경로 설정]
#
# os.path.abspath(__file__): 현재 파일(server.py)의 절대 경로
# os.path.dirname(...)      : 파일이 있는 디렉토리 경로
# os.path.join(...)         : 경로를 OS에 맞게 조합 (Windows/Linux 호환)
#
# 결과 예시:
#   current_dir  = "C:/workAI/middleProject_4team_202603_modified"
#   frontend_dir = "C:/workAI/middleProject_4team_202603_modified/frontend"
#
# 절대 경로를 사용하는 이유:
#   서버를 어느 디렉토리에서 실행하더라도 파일을 올바르게 찾기 위함입니다.
# ─────────────────────────────────────────────────────────
# 프론트엔드 정적 파일 경로 설정 (절대 경로)
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.join(current_dir, "frontend")

# ─────────────────────────────────────────────────────────
# [라우트 순서 중요!]
#
# FastAPI(그리고 내부적으로 사용하는 Starlette)는 라우트를
# 위에서 아래로 순서대로 매칭합니다.
#
# GET /main → frontend/app.html 반환 (로그인 후 메인 화면)
# GET /     → frontend/login.html 반환 (루트 접속 시 로그인 화면)
#
# [FileResponse란?]
# 지정한 파일 경로의 내용을 HTTP 응답으로 그대로 전송합니다.
# 브라우저는 이 HTML 파일을 받아 렌더링(화면에 표시)합니다.
#
# [왜 /main과 / 두 가지 경로가 필요한가?]
# "/" : 처음 접속하는 사용자를 로그인 화면으로 안내
# "/main": 로그인 완료 후 JS에서 window.location.href = "/main"으로 이동
# ─────────────────────────────────────────────────────────
# /main 경로: 로그인 완료 후 이동하는 메인 애플리케이션 화면
@app.get("/main")
async def read_main():
    file_path = os.path.join(frontend_dir, "app.html")
    return FileResponse(file_path)

# / 경로: 루트 URL 접속 시 로그인 화면으로 연결 (가장 먼저 보이는 화면)
@app.get("/")
async def read_index():
    return FileResponse(os.path.join(frontend_dir, "login.html"))

# ─────────────────────────────────────────────────────────
# [정적 파일 마운트 (Static Files Mount)]
#
# app.mount()는 특정 URL 경로를 실제 폴더와 연결합니다.
# 브라우저에서 /js/app.js 를 요청하면 → frontend/js/app.js 파일을 반환합니다.
#
# 마운트 경로별 역할:
#   /assets → 이미지, 아이콘 등 미디어 파일
#   /css    → 스타일시트 (.css 파일)
#   /js     → 자바스크립트 파일 (.js 파일)
#
# [주의: 정적 파일 마운트는 동적 라우트 아래에 배치해야 합니다]
# app.mount()는 경로 접두사(prefix)가 일치하면 무조건 해당 디렉토리에서 파일을 찾습니다.
# 만약 /js 마운트가 위에 있으면 /js로 시작하는 동적 라우트가 가려질 수 있습니다.
# 따라서 동적 라우트(@app.get)를 먼저 선언하고, 정적 마운트는 아래에 배치합니다.
# ─────────────────────────────────────────────────────────
# 2. 정적 파일 마운트는 맨 아래로 내리세요.
app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dir, "assets")), name="assets")
app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")

# ─────────────────────────────────────────────────────────
# CORS 설정
#
# [CORS(Cross-Origin Resource Sharing)란?]
# 브라우저 보안 정책 중 하나로, 다른 출처(Origin)의 서버에
# 자바스크립트로 HTTP 요청을 보내는 것을 기본적으로 차단합니다.
#
# [출처(Origin)의 구성]
# 프로토콜(http/https) + 도메인(localhost/example.com) + 포트(8000/3000)
# 세 가지 중 하나라도 다르면 "다른 출처"로 간주합니다.
#
# [왜 CORS가 필요한가?]
# 예를 들어 프론트엔드가 http://localhost:3000 에서,
# 백엔드 API가 http://localhost:8000 에서 실행 중이라면,
# 포트(3000 ≠ 8000)가 달라 "다른 출처"이므로 브라우저가 요청을 차단합니다.
# CORSMiddleware를 설정하면 서버가 "이 출처에서 오는 요청은 허용한다"는
# 응답 헤더(Access-Control-Allow-Origin)를 추가해 줍니다.
#
# [ALLOWED_ORIGINS 설명]
# - http://localhost:8000, http://127.0.0.1:8000 : 현재 개발 서버
# - http://localhost:3000, http://127.0.0.1:3000 : React 등 프론트 프레임워크 사용 시
# - 배포 시: "https://your-domain.com" 형태로 실제 도메인을 추가합니다.
# ─────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",    # 추후 React 등 프론트 프레임워크 사용 시
    "http://127.0.0.1:3000",
    # 배포 시: "https://your-domain.com" 추가
]

# CORSMiddleware 등록
# 미들웨어(Middleware): 요청이 라우터에 도달하기 전/후에 실행되는 처리 레이어
# 모든 HTTP 요청에 대해 CORS 허용 헤더를 자동으로 추가합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # 허용할 출처 목록
    allow_credentials=True,         # 쿠키/인증 헤더 허용 (JWT Bearer 토큰 전송에 필요)
    allow_methods=["*"],            # GET, POST, PUT, DELETE 등 모든 메서드 허용
    allow_headers=["*"],            # Authorization 헤더 등 모든 헤더 허용
)

# ─────────────────────────────────────────────────────────
# ③ 라우터 등록 (4단계, 5단계에서 파일 생성 후 주석 해제)
#
# [라우터란?]
# 엔드포인트들을 기능별로 파일을 나눠 관리하는 방법.
# auth_router  → 로그인/인증 관련  (/auth/...)
# tutor_router → 튜터 기능 관련   (/api/...)
#
# [include_router의 prefix 옵션]
# prefix="/auth" → auth_router 내의 모든 경로 앞에 "/auth"가 자동으로 붙습니다.
#   예: router.post("/login") → 실제 URL: POST /auth/login
#
# prefix="/api"  → tutor_router 내의 모든 경로 앞에 "/api"가 자동으로 붙습니다.
#   예: router.get("/units") → 실제 URL: GET /api/units
#
# [tags 옵션]
# Swagger UI(/docs)에서 엔드포인트를 그룹으로 묶어 보여줄 때 사용합니다.
#
# [라우터 등록 순서]
# auth_router를 먼저 등록하는 것이 관례입니다.
# 인증(auth) 없이는 튜터(tutor) 기능을 사용할 수 없으므로
# 인증 라우터를 앞에 배치하여 의존성 흐름을 명확히 합니다.
# ─────────────────────────────────────────────────────────
from app.routers.auth  import router as auth_router    # ✅ 4단계 완료
from app.routers.tutor import router as tutor_router   # ✅ 5단계 완료

# auth_router: /auth/login, /auth/me, /auth/logout 등 인증 관련 엔드포인트
app.include_router(auth_router,  prefix="/auth", tags=["인증"])
# tutor_router: /api/units, /api/explain, /api/exam 등 튜터 기능 엔드포인트
app.include_router(tutor_router, prefix="/api",  tags=["튜터"])


# ─────────────────────────────────────────────────────────
# ④ 앱 시작 이벤트 (서버 실행 시 최초 1회 자동 실행)
#
# [@app.on_event("startup")란?]
# uvicorn 서버가 처음 실행될 때 단 한 번 자동으로 호출됩니다.
# 서버가 요청을 받기 전에 반드시 완료되어야 하는 초기화 작업에 사용합니다.
#
# [init_db()의 역할]
# app/utils/db_manager.py 에 정의된 함수로,
# SQLite 데이터베이스 파일을 열고 필요한 테이블을 생성합니다.
# (users 테이블, chat_history 테이블 등)
# 테이블이 이미 존재하면 건너뜁니다 (CREATE TABLE IF NOT EXISTS).
#
# [startup vs shutdown 이벤트]
# @app.on_event("startup")  : 서버 시작 시 실행 (DB 초기화, 캐시 준비 등)
# @app.on_event("shutdown") : 서버 종료 시 실행 (DB 연결 종료, 리소스 정리 등)
# ─────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """
    서버가 시작될 때 DB를 초기화하고 Swagger Bearer 스키마를 등록합니다.
    """
    print("🚀 서버 시작 중... DB 초기화 중입니다.")
    init_db()
    print("✅ DB 초기화 완료. 서버가 준비되었습니다.")


def custom_openapi():
    """
    Swagger UI에 BearerAuth 입력란을 추가합니다.

    [적용 결과]
    Authorize 팝업에 아래 두 가지가 모두 표시됨:
      1. OAuth2PasswordBearer (기존) - username/password 입력
      2. BearerAuth (신규) ← 여기에 토큰을 직접 붙여넣기

    [왜 커스텀 OpenAPI가 필요한가?]
    FastAPI의 기본 Swagger UI는 OAuth2 방식(username/password 입력)만 지원합니다.
    개발 중 /auth/login 에서 발급받은 토큰을 Swagger에서 바로 붙여넣어
    테스트하려면 BearerAuth 스키마를 수동으로 추가해야 합니다.
    """
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Bearer 토큰 직접 입력 스키마 추가
    schema.setdefault("components", {})
    schema["components"].setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "🔑 /auth/login 에서 발급받은 access_token을 입력하세요",
    }

    # 모든 보호된 엔드포인트에 BearerAuth 적용
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            if isinstance(operation, dict):
                operation.setdefault("security", []).append({"BearerAuth": []})

    app.openapi_schema = schema
    return schema

# FastAPI의 기본 openapi() 함수를 커스텀 함수로 교체
app.openapi = custom_openapi


# ─────────────────────────────────────────────────────────
# 헬스체크 엔드포인트
#
# GET /health 를 호출하면 서버 상태를 확인할 수 있습니다.
# HTML 프론트에서 서버가 살아있는지 ping 용도로 사용합니다.
#
# [헬스체크를 사용하는 이유]
# 1. 프론트엔드에서 서버 연결 여부를 확인할 때
# 2. Docker/Kubernetes 같은 컨테이너 환경에서 서비스 상태를 모니터링할 때
# 3. 로드밸런서가 서버가 정상인지 주기적으로 확인할 때 (운영 환경)
# ─────────────────────────────────────────────────────────
@app.get("/health", tags=["헬스체크"])
async def health_check():
    """
    서버 상태 확인용 엔드포인트.

    HTML에서 사용 예시:
        const res = await fetch("http://localhost:8000/health");
        const data = await res.json();
        // { "status": "ok", "message": "AI Math Tutor 서버가 정상 동작 중입니다." }
    """
    return {
        "status": "ok",
        "message": "AI Math Tutor 서버가 정상 동작 중입니다."
    }

# ─────────────────────────────────────────────────────────
# 서버 직접 실행 진입점
#
# [uvicorn이란?]
# FastAPI 앱을 실행하는 ASGI(비동기) 웹 서버입니다.
# Flask의 개발 서버(Werkzeug)와 같은 역할이지만 비동기 처리를 지원합니다.
#
# 실행 방법:
#   uvicorn server:app --reload --port 8000
#
#   server:app  → "server.py 파일 안의 app 객체"를 실행
#   --reload    → 코드 수정 시 서버 자동 재시작 (개발용, 운영에서는 제거)
#   --port 8000 → 포트 번호 (기본 8000, 필요 시 변경 가능)
#   host="0.0.0.0" → 모든 네트워크 인터페이스에서 접속 허용
#                    (127.0.0.1은 로컬에서만 접속 가능)
#
# [이 블록이 실행되는 경우]
# python server.py 로 직접 실행할 때만 동작합니다.
# uvicorn server:app 명령으로 실행하면 이 블록은 실행되지 않습니다.
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
