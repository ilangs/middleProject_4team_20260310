
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
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.utils.db_manager import init_db

# ─────────────────────────────────────────────────────────
# ① FastAPI 앱 인스턴스 생성
# ─────────────────────────────────────────────────────────
from fastapi.security import HTTPBearer

# ✅ Swagger UI에서 Bearer 토큰 직접 입력란을 표시하기 위한 설정
# Swagger Authorize 팝업 하단에 "BearerAuth (http, Bearer)" 입력란이 생김.

security = HTTPBearer()

app = FastAPI(
    title="AI Math Tutor API",
    description="초등학교 5학년 수학 AI 튜터 백엔드 API",
    version="1.0.0",
    swagger_ui_parameters={"persistAuthorization": True},  # 새로고침 후에도 토큰 유지
)

# ─────────────────────────────────────────────────────────
# ② CORS 설정
#
# [CORS가 왜 필요한가?]
# 브라우저는 기본적으로 "다른 출처(Origin)"의 서버로 요청을 막습니다.
# (예: HTML은 http://localhost:5500 에서 열리고,
#      FastAPI는 http://localhost:8000 에서 실행 → 포트가 달라 다른 Origin)
#
# ┌──────────────────────────────────────────────────────┐
# │  Origin = 프로토콜 + 도메인 + 포트 세 가지가 모두 동일해야 같은 Origin │
# │  http://localhost:5500  ≠  http://localhost:8000     │
# └──────────────────────────────────────────────────────┘
#
# CORS 미들웨어를 설정하면 FastAPI가 응답 헤더에
# "Access-Control-Allow-Origin: ..." 를 추가하여 브라우저가 허용합니다.
# ─────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:5500",    # VS Code Live Server (HTML 개발 시 기본 포트)
    "http://127.0.0.1:5500",
    "http://localhost:3000",    # 추후 React 등 프론트 프레임워크 사용 시
    "http://127.0.0.1:3000",
    # 배포 시: "https://your-domain.com" 추가
]

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
# ─────────────────────────────────────────────────────────
from app.routers.auth  import router as auth_router    # ✅ 4단계 완료
from app.routers.tutor import router as tutor_router   # ✅ 5단계 완료

app.include_router(auth_router,  prefix="/auth", tags=["인증"])
app.include_router(tutor_router, prefix="/api",  tags=["튜터"])


# ─────────────────────────────────────────────────────────
# ④ 앱 시작 이벤트 (서버 실행 시 최초 1회 자동 실행)
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

app.openapi = custom_openapi


# ─────────────────────────────────────────────────────────
# ⑤ 헬스체크 엔드포인트
#
# GET /health 를 호출하면 서버 상태를 확인할 수 있습니다.
# HTML 프론트에서 서버가 살아있는지 ping 용도로 사용합니다.
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
# ⑥ 루트 엔드포인트
# ─────────────────────────────────────────────────────────
@app.get("/", tags=["헬스체크"])
async def root():
    return {
        "message": "AI Math Tutor API 서버입니다.",
        "docs": "http://localhost:8000/docs",
    }


# ─────────────────────────────────────────────────────────
# ⑦ 서버 직접 실행 진입점
#
# 실행 방법:
#   uvicorn app:app --reload --port 8000
#
#   --reload: 코드 수정 시 서버 자동 재시작 (개발용)
#   --port:   포트 번호 (기본 8000)
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)