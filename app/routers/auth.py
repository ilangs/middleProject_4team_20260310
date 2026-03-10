"""
routers/auth.py
"""

import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from dotenv import load_dotenv

from app.utils.db_manager import get_user, verify_password, create_user

load_dotenv()

# ─────────────────────────────────────────────────────────
# ① JWT 설정값
#
# SECRET_KEY : 토큰 서명에 사용하는 비밀키
#              → .env 파일에 저장해야 하며, 절대 코드에 하드코딩 금지
#              → 터미널에서 생성: python -c "import secrets; print(secrets.token_hex(32))"
#
# ALGORITHM  : 서명 알고리즘. HS256이 가장 보편적
#
# ACCESS_TOKEN_EXPIRE_MINUTES : 토큰 만료 시간
#              → 너무 길면 탈취 시 위험, 너무 짧으면 자주 로그인해야 함
#              → 교육용 서비스이므로 60분으로 설정
# ─────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# ─────────────────────────────────────────────────────────
# ② Pydantic 스키마 정의
#
# [Pydantic이란?]
# FastAPI가 요청/응답 데이터의 타입과 구조를 검증하는 라이브러리.
# BaseModel을 상속하면 자동으로 유효성 검사 + Swagger 문서 생성.
# ─────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    """
    로그인 성공 시 클라이언트에게 반환하는 응답 형식.
    
    HTML에서 받는 방법:
        const data = await res.json();
        // { access_token: "eyJhb...", token_type: "bearer", username: "student01" }
        sessionStorage.setItem("token", data.access_token);
    """
    access_token: str
    token_type: str = "bearer"
    username: str


class UserInfo(BaseModel):
    """GET /auth/me 응답 형식."""
    username: str
    current_unit: str
    nickname: str | None = None
    character: str | None = None
    
class RegisterRequest(BaseModel):
    username: str
    password: str
    nickname: str
    character: str

# ─────────────────────────────────────────────────────────
# ③ OAuth2PasswordBearer 설정
#
# HTML에서 요청 시 헤더에 아래 형식으로 토큰을 담아 보냅니다:
#   Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
#
# oauth2_scheme 은 이 헤더를 자동으로 파싱해주는 FastAPI 유틸입니다.
# ─────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ─────────────────────────────────────────────────────────
# ④ JWT 토큰 생성 함수 (내부 유틸)
# ─────────────────────────────────────────────────────────
def create_access_token(data: dict) -> str:
    """
    주어진 데이터(payload)로 JWT 토큰을 생성합니다.
    
    동작 흐름:
        1. payload에 만료 시간(exp) 추가
        2. SECRET_KEY로 서명하여 토큰 문자열 반환
    
    사용 예시:
        token = create_access_token({"sub": "student01"})
        # → "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzdHVkZW50MDEifQ.xxxx"
    """
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ─────────────────────────────────────────────────────────
# ⑤ 토큰 검증 Dependency (핵심!)
#
# [FastAPI Dependency란?]
# 엔드포인트 함수의 인자에 Depends()를 선언하면,
# FastAPI가 해당 함수를 먼저 실행하고 결과를 주입해 줍니다.
#
# 보호가 필요한 모든 엔드포인트에 아래처럼 선언하면
# 토큰 검증이 자동으로 수행됩니다:
#
#   @router.get("/api/units")
#   async def get_units(current_user = Depends(get_current_user)):
#       ...  # 여기 도달했다면 토큰이 유효한 사용자
# ─────────────────────────────────────────────────────────
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Authorization 헤더의 JWT 토큰을 검증하고 유저 정보를 반환합니다.
    
    검증 실패 시 → HTTP 401 Unauthorized 자동 반환
    검증 성공 시 → {"username": "student01", "current_unit": "분수"} 반환
    
    [토큰 검증 흐름]
    
    클라이언트 요청
        │  Header: Authorization: Bearer eyJhb...
        ▼
    oauth2_scheme  →  토큰 문자열 추출
        │
        ▼
    jwt.decode()   →  서명 검증 + 만료 시간 확인
        │  성공 → payload에서 username(sub) 추출
        │  실패 → JWTError 발생
        ▼
    get_user()     →  DB에서 유저 존재 여부 재확인
        │  존재 → 유저 정보 반환
        │  없음 → 401 반환
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="로그인이 필요합니다. 토큰이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user(username)
    if user is None:
        raise credentials_exception

    return user


# ─────────────────────────────────────────────────────────
# ⑥ 라우터 생성
# ─────────────────────────────────────────────────────────
router = APIRouter()


# ─────────────────────────────────────────────────────────
# ⑦ POST /auth/login  ─  로그인 & JWT 발급
# ─────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    아이디와 비밀번호를 받아 JWT 토큰을 발급합니다.
    
    get_user()로 유저 조회 → verify_password()로 bcrypt 해시 비교

    HTML fetch 예시:
        const res = await fetch("http://localhost:8000/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ username: "student01", password: "1234" })
        });
        const data = await res.json();
        sessionStorage.setItem("token", data.access_token);
    
    [왜 application/x-www-form-urlencoded?]
    OAuth2 표준이 form 형식을 사용하기 때문.
    OAuth2PasswordRequestForm 이 이 형식을 자동으로 파싱해 줍니다.
    """
    # 1. DB에서 유저 조회
    user = get_user(form_data.username)

    # 2. 유저가 없거나 비밀번호 불일치 시 → 동일한 에러 메시지 반환
    #    (어느 쪽이 틀렸는지 노출하지 않는 것이 보안상 올바름)
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 일치하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. JWT 토큰 생성
    #    "sub" (subject) 는 JWT 표준 필드명 → 유저 식별자를 담는 관례
    access_token = create_access_token(data={"sub": user["username"]})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        username=user["username"]
    )
    
@router.post("/register")
async def register(user: RegisterRequest):
    success = create_user(
        username=user.username,
        plain_password=user.password,
        nickname=user.nickname,
        character=user.character
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="이미 존재하는 아이디입니다."
        )

    return {"message": "회원가입이 완료되었습니다."}

# ─────────────────────────────────────────────────────────
# ⑧ GET /auth/me  ─  현재 로그인 유저 정보 조회
# ─────────────────────────────────────────────────────────
@router.get("/me", response_model=UserInfo)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    현재 JWT 토큰의 주인인 유저 정보를 반환합니다.
    
    Depends(get_current_user) 덕분에 토큰 검증은 자동으로 처리됩니다.
    
    HTML fetch 예시:
        const token = sessionStorage.getItem("token");
        const res = await fetch("http://localhost:8000/auth/me", {
            headers: { "Authorization": "Bearer " + token }
        });
        const user = await res.json();
        // { username: "student01", current_unit: "분수" }
    """
    return UserInfo(
        username=current_user["username"],
        current_unit=current_user.get("current_unit", "None"),
        nickname=current_user.get("nickname"),
        character=current_user.get("character")
    )


# ─────────────────────────────────────────────────────────
# ⑨ POST /auth/logout  ─  로그아웃
#
# [JWT 로그아웃의 특성]
# JWT는 Stateless이므로 서버에서 토큰을 "삭제"할 수 없습니다.
# 로그아웃은 클라이언트가 보관 중인 토큰을 삭제하는 방식으로 처리합니다.
# ─────────────────────────────────────────────────────────
@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    로그아웃 처리.

    서버는 토큰이 유효한지만 확인하고, 실제 삭제는 클라이언트가 수행합니다.

    HTML fetch 예시:
        const token = sessionStorage.getItem("token");
        await fetch("http://localhost:8000/auth/logout", {
            method: "POST",
            headers: { "Authorization": "Bearer " + token }
        });
        sessionStorage.removeItem("token");   // ← 실제 로그아웃 처리
        window.location.href = "/login.html"; // ← 로그인 페이지로 이동
    """
    return {
        "message": f"{current_user['username']}님이 로그아웃되었습니다.",
        "instruction": "클라이언트에서 토큰을 삭제해 주세요."
    }
