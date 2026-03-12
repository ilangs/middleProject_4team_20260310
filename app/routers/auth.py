"""
routers/auth.py  ─  인증(Authentication) 관련 API 라우터

[이 파일의 역할]
사용자 로그인, 회원가입, 로그아웃 및 JWT 토큰 발급/검증을 담당합니다.

[인증 흐름 전체 요약]
  1. 클라이언트가 POST /auth/login 으로 아이디/비밀번호를 전송
  2. 서버가 DB에서 유저를 찾고, bcrypt로 비밀번호 해시를 비교
  3. 일치하면 JWT 토큰을 생성하여 클라이언트에 반환
  4. 이후 모든 API 요청 시, 클라이언트는 헤더에 토큰을 담아 전송
     Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
  5. 서버는 get_current_user()로 토큰을 검증하고 사용자를 식별

[JWT란? (JSON Web Token)]
서버가 "이 사람이 로그인했음"을 증명하는 디지털 통행증입니다.
세션(Session)과 달리 서버에 상태를 저장하지 않는 Stateless 방식입니다.

JWT 토큰 구조: header.payload.signature (점(.)으로 구분된 3부분)

  [Header]   알고리즘 및 토큰 타입 정보
  예시:       {"alg": "HS256", "typ": "JWT"}
  base64url 인코딩 → eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9

  [Payload]  실제 데이터 (클레임, Claims)
  예시:       {"sub": "student01", "exp": 1710000000}
  "sub"은 subject(주체=사용자 식별자)의 JWT 표준 필드명
  base64url 인코딩 → eyJzdWIiOiJzdHVkZW50MDEifQ

  [Signature] 위조 방지 서명
  HMAC-SHA256(base64(header) + "." + base64(payload), SECRET_KEY)
  SECRET_KEY 없이는 서명 위조 불가능

완성된 토큰 예시:
  eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJzdHVkZW50MDEifQ.xxxx

주의: Payload는 base64 인코딩일 뿐 암호화가 아닙니다.
     누구든 디코딩하여 내용을 볼 수 있으므로 비밀번호 등 민감 정보를 담으면 안 됩니다.
"""

import os
from datetime import datetime, timedelta

# APIRouter: 라우트들을 그룹화하는 FastAPI 클래스 (이 파일의 라우트 묶음을 만들 때 사용)
# Depends: 의존성 주입(Dependency Injection) - 함수 실행 전에 다른 함수를 먼저 실행
# HTTPException: HTTP 에러 응답을 발생시키는 클래스
# status: HTTP 상태 코드 상수 모음 (status.HTTP_401_UNAUTHORIZED = 401)
from fastapi import APIRouter, Depends, HTTPException, status

# OAuth2PasswordBearer: Authorization 헤더에서 Bearer 토큰을 추출하는 유틸
# OAuth2PasswordRequestForm: form-urlencoded 형식의 username/password를 파싱
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# jose: JWT 토큰 생성 및 검증 라이브러리 (python-jose)
# JWTError: 토큰이 유효하지 않을 때 발생하는 예외
# jwt: 토큰 생성(encode)과 해독(decode) 함수 제공
from jose import JWTError, jwt

# BaseModel: Pydantic의 기본 클래스 - 요청/응답 데이터 구조 정의에 사용
from pydantic import BaseModel
from dotenv import load_dotenv

# DB 관련 유틸 함수 임포트
# get_user: 사용자명으로 DB에서 유저 정보를 조회
# verify_password: 입력 비밀번호와 DB의 bcrypt 해시를 비교
# create_user: 새 사용자를 DB에 등록 (비밀번호는 bcrypt로 해시하여 저장)
from app.utils.db_manager import get_user, verify_password, create_user

# .env 파일에서 환경 변수를 로드합니다.
# JWT_SECRET_KEY 같은 민감한 값을 코드에 직접 작성하지 않기 위함입니다.
load_dotenv()

# ─────────────────────────────────────────────────────────
# ① JWT 설정값
#
# SECRET_KEY : 토큰 서명에 사용하는 비밀키
#              → .env 파일에 저장해야 하며, 절대 코드에 하드코딩 금지
#              → 터미널에서 생성: python -c "import secrets; print(secrets.token_hex(32))"
#              → 이 키가 노출되면 누구든 유효한 JWT 토큰을 위조할 수 있습니다!
#
# ALGORITHM  : 서명 알고리즘. HS256이 가장 보편적
#              HS256 = HMAC + SHA-256 (대칭키 방식: 서명과 검증에 같은 키 사용)
#              RS256 = RSA (비대칭키 방식: 서명은 개인키, 검증은 공개키 - 대규모 서비스에 적합)
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
#
# [역할 정리]
# TokenResponse  : 로그인 성공 시 클라이언트로 보내는 응답 구조
# UserInfo       : GET /auth/me 에서 반환하는 사용자 정보 구조
# RegisterRequest: POST /auth/register 에서 받는 회원가입 요청 구조
# ─────────────────────────────────────────────────────────
class TokenResponse(BaseModel):
    """
    로그인 성공 시 클라이언트에게 반환하는 응답 형식.

    HTML에서 받는 방법:
        const data = await res.json();
        // { access_token: "eyJhb...", token_type: "bearer", username: "student01" }
        sessionStorage.setItem("token", data.access_token);

    [access_token]
    클라이언트가 저장하고 이후 모든 API 요청 헤더에 담아 보내는 JWT 문자열입니다.
    sessionStorage 또는 localStorage에 저장하며,
    보안상 sessionStorage(탭 닫으면 삭제)가 더 안전합니다.

    [token_type]
    항상 "bearer"입니다. OAuth2 표준에서 Bearer 토큰 방식임을 명시합니다.
    클라이언트는 Authorization: Bearer <토큰> 형식으로 헤더를 구성해야 합니다.
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
    """
    회원가입 요청 데이터 구조.
    POST /auth/register 에서 JSON body로 받습니다.

    HTML에서 보내는 방법:
        const res = await fetch("/auth/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: "student01",
                password: "1234",
                nickname: "수학왕",
                character: "cat"
            })
        });
    """
    username: str
    password: str
    nickname: str
    character: str

# ─────────────────────────────────────────────────────────
# ③ OAuth2PasswordBearer 설정
#
# [OAuth2PasswordBearer란?]
# FastAPI에서 Bearer 토큰 인증을 처리하는 의존성(Dependency) 클래스입니다.
# 요청의 Authorization 헤더에서 토큰을 자동으로 추출합니다.
#
# HTML에서 요청 시 헤더에 아래 형식으로 토큰을 담아 보냅니다:
#   Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
#
# oauth2_scheme 은 이 헤더를 자동으로 파싱해주는 FastAPI 유틸입니다.
#
# [tokenUrl 파라미터]
# Swagger UI가 "토큰을 발급받는 URL이 어디인가?"를 알 수 있도록 명시합니다.
# 실제 토큰 발급 로직은 아래의 /login 엔드포인트에서 처리합니다.
#
# [동작 방식]
# Depends(oauth2_scheme)를 함수 파라미터로 선언하면,
# FastAPI가 요청 헤더에서 "Bearer <토큰>" 부분을 자동으로 추출하여
# 해당 파라미터에 토큰 문자열만 전달합니다.
# 헤더가 없으면 자동으로 HTTP 401 에러를 반환합니다.
# ─────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ─────────────────────────────────────────────────────────
# ④ JWT 토큰 생성 함수 (내부 유틸)
#
# [함수 역할]
# 사용자 정보(data)를 받아서 서명된 JWT 토큰 문자열을 반환합니다.
# 로그인 성공 시 이 함수를 호출하여 토큰을 생성합니다.
#
# [bcrypt와의 관계]
# bcrypt는 비밀번호를 해시할 때 사용하는 알고리즘입니다.
# JWT는 로그인 성공 후 사용자를 식별하는 토큰을 만들 때 사용합니다.
# 두 기술은 서로 다른 목적으로 사용됩니다:
#   - bcrypt: "비밀번호가 맞는지 확인" (verify_password에서 사용)
#   - JWT:    "로그인한 사용자임을 증명" (이 함수에서 생성)
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

    [exp 클레임이란?]
    JWT 표준에 정의된 만료 시간(expiration) 필드입니다.
    이 시간이 지나면 jwt.decode() 가 자동으로 ExpiredSignatureError를 발생시킵니다.
    datetime.utcnow() + timedelta(minutes=60) → 현재 UTC 시각에서 60분 뒤를 만료 시각으로 설정합니다.
    """
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload.update({"exp": expire})
    # jwt.encode(payload, 비밀키, 알고리즘) → 서명된 JWT 토큰 문자열 반환
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ─────────────────────────────────────────────────────────
# ⑤ 토큰 검증 Dependency (핵심!)
#
# [FastAPI Dependency(의존성 주입)란?]
# 엔드포인트 함수의 인자에 Depends()를 선언하면,
# FastAPI가 해당 함수를 먼저 실행하고 결과를 주입해 줍니다.
# 공통 로직(토큰 검증, DB 연결 등)을 재사용할 때 매우 유용합니다.
#
# [사용 예시]
# 보호가 필요한 모든 엔드포인트에 아래처럼 선언하면
# 토큰 검증이 자동으로 수행됩니다:
#
#   @router.get("/api/units")
#   async def get_units(current_user = Depends(get_current_user)):
#       ...  # 여기 도달했다면 토큰이 유효한 사용자
#
# [Depends()의 실행 순서]
# 1. 클라이언트가 /api/units 에 요청을 보냄
# 2. FastAPI가 Depends(get_current_user) 를 감지
# 3. get_current_user() 함수를 먼저 실행
#    - 토큰 유효 → 사용자 정보 dict 반환 → current_user 에 주입
#    - 토큰 무효 → HTTP 401 반환 → 엔드포인트 함수 실행 안 됨
# 4. 검증 성공 시에만 get_units() 본문 실행
#
# [왜 Depends()를 쓰는가?]
# 인증 코드를 모든 엔드포인트에 복사하지 않아도 되어 중복을 제거합니다.
# 인증 로직이 바뀌어도 get_current_user() 한 곳만 수정하면 됩니다.
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
    oauth2_scheme  →  토큰 문자열 추출 (Depends(oauth2_scheme)가 처리)
        │
        ▼
    jwt.decode()   →  서명 검증 + 만료 시간 확인
        │  성공 → payload에서 username(sub) 추출
        │  실패 → JWTError 발생 (위조된 토큰 또는 만료)
        ▼
    get_user()     →  DB에서 유저 존재 여부 재확인
        │  존재 → 유저 정보 dict 반환
        │  없음 → 401 반환 (탈퇴한 유저 등 예외 처리)

    [왜 DB를 재확인하는가?]
    JWT 토큰 자체는 유효하더라도, 사용자가 탈퇴했거나
    관리자가 계정을 비활성화했을 수 있습니다.
    DB를 재확인하여 현재 유효한 사용자인지 검증합니다.
    """
    # 인증 실패 시 반환할 HTTP 예외 객체를 미리 정의
    # WWW-Authenticate 헤더: 클라이언트에게 Bearer 토큰 방식으로 인증하라고 안내
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="로그인이 필요합니다. 토큰이 유효하지 않거나 만료되었습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # jwt.decode(): 토큰의 서명을 SECRET_KEY로 검증하고 payload를 반환
        # 토큰이 위조되었거나 만료되었으면 JWTError 예외 발생
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # payload에서 사용자명 추출 ("sub" 클레임)
        username: str = payload.get("sub")
        if username is None:
            # "sub" 필드가 없는 비정상적인 토큰
            raise credentials_exception
    except JWTError:
        # 서명 검증 실패, 만료, 형식 오류 등 모든 JWT 관련 에러 처리
        raise credentials_exception

    # DB에서 유저 재확인 (탈퇴/비활성화 계정 처리)
    user = get_user(username)
    if user is None:
        raise credentials_exception

    return user


# ─────────────────────────────────────────────────────────
# ⑥ 라우터 생성
#
# APIRouter(): 이 파일의 엔드포인트들을 묶는 라우터 인스턴스
# server.py에서 app.include_router(auth_router, prefix="/auth")로 등록됩니다.
# 이 파일 내에서 router.post("/login")은 최종 URL /auth/login 이 됩니다.
# ─────────────────────────────────────────────────────────
router = APIRouter()


# ─────────────────────────────────────────────────────────
# ⑦ POST /auth/login  ─  로그인 & JWT 발급
#
# [로그인 전체 흐름]
# 1. 클라이언트가 form 형식으로 username, password를 전송
# 2. OAuth2PasswordRequestForm이 자동으로 파싱
# 3. DB에서 유저 조회 (get_user)
# 4. bcrypt로 비밀번호 해시 비교 (verify_password)
# 5. 검증 성공 → JWT 토큰 생성 (create_access_token)
# 6. TokenResponse(access_token, token_type, username) 반환
#
# [bcrypt 비밀번호 해싱이란?]
# 비밀번호를 그대로 DB에 저장하면 DB가 해킹당할 때 비밀번호가 노출됩니다.
# bcrypt는 비밀번호를 단방향 해시로 변환하여 저장합니다.
# 단방향이므로 해시에서 원본 비밀번호를 역산할 수 없습니다.
#
# 저장 시: plain_password → bcrypt → "$2b$12$abc...xyz" (해시값을 DB에 저장)
# 검증 시: 입력 비밀번호를 같은 방식으로 해시하여 DB의 해시값과 비교
#          (verify_password 함수가 이 과정을 처리합니다)
#
# [salt란?]
# bcrypt는 같은 비밀번호라도 매번 다른 해시값이 나오도록 무작위 salt를 사용합니다.
# 이를 통해 레인보우 테이블 공격(사전에 계산된 해시값으로 역산하는 공격)을 방어합니다.
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

    [JSON이 아닌 form 형식을 쓰는 이유]
    OAuth2 표준 스펙(RFC 6749)이 username/password를
    form-urlencoded 형식으로 전송하도록 정의하고 있습니다.
    FastAPI의 OAuth2PasswordRequestForm은 이 표준을 따릅니다.
    """
    # 1. DB에서 유저 조회
    user = get_user(form_data.username)

    # 2. 유저가 없거나 비밀번호 불일치 시 → 동일한 에러 메시지 반환
    #    (어느 쪽이 틀렸는지 노출하지 않는 것이 보안상 올바름)
    #    "아이디가 없습니다" vs "비밀번호가 틀렸습니다"를 구분하면
    #    공격자가 유효한 아이디를 알아낼 수 있습니다.
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 일치하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. JWT 토큰 생성
    #    "sub" (subject) 는 JWT 표준 필드명 → 유저 식별자를 담는 관례
    #    이후 get_current_user()에서 payload.get("sub")으로 사용자명을 추출합니다.
    access_token = create_access_token(data={"sub": user["username"]})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        username=user["username"]
    )

# ─────────────────────────────────────────────────────────
# POST /auth/register  ─  회원가입
#
# [회원가입 흐름]
# 1. 클라이언트가 JSON으로 username, password, nickname, character 전송
# 2. RegisterRequest Pydantic 모델이 자동으로 유효성 검사
# 3. create_user()로 DB에 저장 (내부에서 bcrypt 해시 처리)
# 4. 이미 존재하는 아이디면 False 반환 → HTTP 400 에러
# 5. 성공 시 완료 메시지 반환
# ─────────────────────────────────────────────────────────
@router.post("/register")
async def register(user: RegisterRequest):
    # create_user(): 내부에서 bcrypt로 비밀번호를 해시하여 DB에 저장
    # 이미 같은 username이 있으면 False 반환
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
#
# [이 엔드포인트의 역할]
# 클라이언트가 "내가 누구인지" 확인할 때 사용합니다.
# 페이지를 새로고침하거나 앱을 재시작했을 때,
# sessionStorage의 토큰이 아직 유효한지 확인하고
# 로그인된 사용자 정보를 다시 불러올 때 주로 호출합니다.
#
# [Depends(get_current_user)의 동작]
# 이 엔드포인트에 요청이 오면:
# 1. FastAPI가 Depends(get_current_user) 감지
# 2. get_current_user() 실행 → 토큰 검증
# 3. 검증 성공 → current_user dict 를 get_me() 함수에 주입
# 4. 검증 실패 → HTTP 401 반환 (get_me() 본문 실행 안 됨)
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
# 서버는 토큰이 유효한지만 확인하고, 실제 무효화는 클라이언트가 수행합니다.
#
# [로그아웃 처리 방식]
# 서버: 토큰이 유효한지만 확인 (Depends(get_current_user))
# 클라이언트: sessionStorage/localStorage에서 토큰을 삭제
#
# [보안 강화 방법 - 참고용]
# 완전한 로그아웃을 구현하려면 "토큰 블랙리스트"를 관리해야 합니다.
# 로그아웃된 토큰을 Redis 등에 저장하고, 이후 요청 시 블랙리스트를 확인합니다.
# 이 프로젝트는 교육용이므로 클라이언트 측 삭제 방식을 사용합니다.
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
