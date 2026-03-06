import asyncio
import os
import re
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import jwt

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PASSWORD_SALT = os.environ.get("PASSWORD_SALT", "change-me-in-production")
ACCESS_TOKEN_SECRET = os.environ.get("ACCESS_TOKEN_SECRET") or ""
REFRESH_TOKEN_SECRET = os.environ.get("REFRESH_TOKEN_SECRET") or ""
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.environ.get("ACCESS_TOKEN_EXPIRE_SECONDS", "900"))  
REFRESH_TOKEN_EXPIRE_SECONDS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_SECONDS", "108000"))


def hash_password(password: str) -> str:
    return sha256((PASSWORD_SALT + password).encode()).hexdigest()

def send_verification_code(email: str, verification_code: str):
    print(f"Sending verification code to {email}: {verification_code}")

_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


def is_valid_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    return _EMAIL_PATTERN.match(email) is not None


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME", "login_data"),
    "user": os.environ.get("DB_USER", "10"),
    "password": os.environ.get("DB_PASSWORD", "10101010"),
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", "5432"),
}

DATABASE_URL = (
    f"postgresql+asyncpg://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
)


@asynccontextmanager
async def lifespan(app: "FastAPI"):
    loop = asyncio.get_running_loop()
    if not getattr(app.state, "_loop_db", None):
        app.state._loop_db = {}
    engine = create_async_engine(DATABASE_URL, echo=False)
    app.state._loop_db[loop] = {
        "engine": engine,
        "factory": async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        ),
    }
    yield
    await engine.dispose()


class Base(DeclarativeBase):
    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)
    password: Mapped[str] = mapped_column(nullable=False)


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(nullable=False, index=True)
    code: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=text("NOW()"), 
    )


def _get_session_factory(app: "FastAPI"):
    loop = asyncio.get_running_loop()
    if not getattr(app.state, "_loop_db", None):
        app.state._loop_db = {}
    if loop not in app.state._loop_db:
        engine = create_async_engine(DATABASE_URL, echo=False)
        app.state._loop_db[loop] = {
            "engine": engine,
            "factory": async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
            ),
        }
    return app.state._loop_db[loop]["factory"]


async def get_db(request: "Request") -> AsyncSession:
    factory = _get_session_factory(request.app)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class APIException(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


app = FastAPI(lifespan=lifespan)


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.message},
    )


class User(BaseModel):
    id_: str
    username: str

class UserData(BaseModel):
    message: str
    user: User

class RegisterData(BaseModel):
    username: str
    email: str
    password: str
    verificationCode: str

class ResetPasswordData(BaseModel):
    email: str
    password: str
    verificationCode: str

def generate_verification_code() -> str:
    return str(random.randint(100000, 999999))


def _jwt_payload(user_id: int, expire_seconds: int) -> dict:
    now = int(time.time())
    return {"user_id": user_id, "iat": now, "exp": now + expire_seconds}


def generate_access_token(user_id: int) -> str:
    if not ACCESS_TOKEN_SECRET:
        raise APIException(status_code=500, message="Internal server error")
    payload = _jwt_payload(user_id, ACCESS_TOKEN_EXPIRE_SECONDS)
    return jwt.encode(payload, ACCESS_TOKEN_SECRET, algorithm="HS256")


def generate_refresh_token(user_id: int) -> str:
    if not REFRESH_TOKEN_SECRET:
        raise APIException(status_code=500, message="Internal server error")
    payload = _jwt_payload(user_id, REFRESH_TOKEN_EXPIRE_SECONDS)
    return jwt.encode(payload, REFRESH_TOKEN_SECRET, algorithm="HS256")


def verify_access_token(token: str) -> dict:
    if not ACCESS_TOKEN_SECRET:
        raise APIException(status_code=500, message="Internal server error")
    return jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=["HS256"])


def verify_refresh_token(token: str) -> dict:
    if not REFRESH_TOKEN_SECRET:
        raise APIException(status_code=500, message="Internal server error")
    return jwt.decode(token, REFRESH_TOKEN_SECRET, algorithms=["HS256"])

@app.post("/auth/register/captcha")
async def send_captcha(email: str, db: AsyncSession = Depends(get_db)):
    if not is_valid_email(email):
        raise APIException(status_code=400, message="Invalid email format")
    try:
        fifteen_min_ago = _utc_now_naive() - timedelta(minutes=15)
        stmt = (
            select(EmailVerification)
            .where(
                and_(
                    EmailVerification.email == email,
                    EmailVerification.created_at > fifteen_min_ago,
                )
            )
        )
        result = await db.execute(stmt)
        verification = result.scalar_one_or_none()
        if verification:
            await db.delete(verification)
        verification = EmailVerification(
            email=email,
            code=generate_verification_code(),
        )
        send_verification_code(email, verification.code)
        db.add(verification)
        await db.flush()
        
    except APIException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise APIException(status_code=500, message=detail)
    return {"message": "Verification code sent"}

@app.post("/auth/register")
async def register(
    register_data: RegisterData,
    db: AsyncSession = Depends(get_db),
):
    if not is_valid_email(register_data.email):
        raise APIException(status_code=400, message="Invalid email format")
    try:
        fifteen_min_ago = _utc_now_naive() - timedelta(minutes=15)
        stmt = (
            select(EmailVerification)
            .where(
                and_(
                    EmailVerification.email == register_data.email,
                    EmailVerification.code == register_data.verificationCode,
                    EmailVerification.created_at > fifteen_min_ago,
                )
            )
            .order_by(EmailVerification.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        verification = result.scalar_one_or_none()
        if not verification:
            raise APIException(
                status_code=422,
                message="Verification code is invalid or expired",
            )
        await db.delete(verification)

        exists_stmt = select(1).where(UserModel.email == register_data.email)
        exists_result = await db.execute(exists_stmt)
        if exists_result.scalar_one_or_none():
            raise APIException(
                status_code=409,
                message="Email already exists",
            )

        user = UserModel(
            username=register_data.username,
            email=register_data.email,
            password=hash_password(register_data.password),
        )
        db.add(user)
        await db.flush()  
    except APIException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise APIException(status_code=500, message=detail)
    return {"message": "registered", "email": register_data.email}

@app.post("/auth/password")
async def reset_password(ResetPasswordData: ResetPasswordData, db: AsyncSession = Depends(get_db)):
    if not is_valid_email(ResetPasswordData.email):
        raise APIException(status_code=400, message="Invalid email format")
    try:
        fifteen_min_ago = _utc_now_naive() - timedelta(minutes=15)
        stmt = (
            select(EmailVerification)
            .where(
                and_(
                    EmailVerification.email == ResetPasswordData.email,
                    EmailVerification.code == ResetPasswordData.verificationCode,
                    EmailVerification.created_at > fifteen_min_ago,
                )
            )
            .order_by(EmailVerification.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        verification = result.scalar_one_or_none()
        if not verification:
            raise APIException(
                status_code=422,
                message="Verification code is invalid or expired",
            )
        await db.delete(verification)

        stmt = select(UserModel).where(UserModel.email == ResetPasswordData.email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise APIException(status_code=400, message="Email not registered")
        user.password = hash_password(ResetPasswordData.password)
        await db.flush()
    except APIException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise APIException(status_code=500, message=detail)
    return {"message": "Password reset successfully", "email": ResetPasswordData.email}


@app.post("/auth/password/captcha")
async def send_password_reset_captcha(email: str, db: AsyncSession = Depends(get_db)):
    if not is_valid_email(email):
        raise APIException(status_code=400, message="Invalid email format")
    try:
        fifteen_min_ago = _utc_now_naive() - timedelta(minutes=15)
        stmt = (
            select(EmailVerification)
            .where(
                and_(
                    EmailVerification.email == email,
                    EmailVerification.created_at > fifteen_min_ago,
                )
            )
        )
        result = await db.execute(stmt)
        verification = result.scalar_one_or_none()
        if verification:
            await db.delete(verification)
        verification = EmailVerification(
            email=email,
            code=generate_verification_code(),
        )
        send_verification_code(email, verification.code)
        db.add(verification)
        await db.flush()
    except APIException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise APIException(status_code=500, message=detail)
    return {"message": "Verification code sent"}


@app.post("/auth/login")
async def login(email: str, password: str, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise APIException(status_code=400, message="Email not registered")
        if user.password != hash_password(password):
            raise APIException(status_code=400, message="Invalid password")
    except APIException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise APIException(status_code=500, message=detail)
    access_token = generate_access_token(user.id)
    refresh_token = generate_refresh_token(user.id)
    return {
        "message": "Login successfully",
        "email": email,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

#####################以下都是ai生的测试###########################
def _run_tests() -> None:
    """用 TestClient 本地测试认证接口。发送验证码会打印到控制台，可输入该验证码完成注册测试。"""
    import os as _os
    _os.environ["DEBUG"] = "1"
    from fastapi.testclient import TestClient

    client = TestClient(app)
    ok, fail = 0, 0

    def check(name: str, r, expect: int) -> None:
        nonlocal ok, fail
        j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        print(f"  {r.status_code}  {j}")
        if r.status_code == expect:
            ok += 1
        else:
            fail += 1
            print(f"  → 期望 {expect}")

    # ---------- 注册验证码 ----------
    print("========== 注册验证码 ==========")
    r = client.post("/auth/register/captcha", params={"email": "not-an-email"})
    print("  非法邮箱:")
    check("register_captcha_invalid", r, 400)

    r = client.post("/auth/register/captcha", params={"email": "test@example.com"})
    print("  合法邮箱:")
    check("register_captcha_ok", r, 200)
    if r.status_code != 200:
        print("  (500 时请检查数据库与表)")

    # ---------- 注册 ----------
    print("\n========== 注册 ==========")
    r = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "bad",
            "password": "password123",
            "verificationCode": "123456",
        },
    )
    print("  非法邮箱:")
    check("register_invalid_email", r, 400)

    r = client.post(
        "/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
            "verificationCode": "000000",
        },
    )
    print("  验证码错误/过期 (期望 422):")
    check("register_bad_code", r, 422)
    if r.status_code == 500:
        print("  (500 时请检查数据库)")

    # 再次发送验证码，验证码会紧挨着下面一行输出，便于复制
    print("\n  正在发送注册验证码，请根据下方输出输入验证码（直接回车跳过）:")
    client.post("/auth/register/captcha", params={"email": "test@example.com"})
    code = input("  验证码: ").strip()
    if code:
        r = client.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123",
                "verificationCode": code,
            },
        )
        print(f"  注册结果: {r.status_code}  {r.json() if r.headers.get('content-type', '').startswith('application/json') else ''}")
        if r.status_code == 200:
            ok += 1
        elif r.status_code == 409:
            print("  (该邮箱已注册过，可继续后续登录测试，不记失败)")
        else:
            fail += 1
    else:
        print("  已跳过注册成功测试。")

    # ---------- 重置密码验证码 ----------
    print("\n========== 重置密码验证码 ==========")
    r = client.post("/auth/password/captcha", params={"email": "invalid"})
    print("  非法邮箱:")
    check("password_captcha_invalid", r, 400)

    r = client.post("/auth/password/captcha", params={"email": "test@example.com"})
    print("  合法邮箱:")
    check("password_captcha_ok", r, 200)

    # ---------- 重置密码 ----------
    print("\n========== 重置密码 ==========")
    r = client.post(
        "/auth/password",
        json={
            "email": "bad",
            "password": "newpass",
            "verificationCode": "123456",
        },
    )
    print("  非法邮箱:")
    check("reset_password_invalid_email", r, 400)

    r = client.post(
        "/auth/password",
        json={
            "email": "test@example.com",
            "password": "newpass",
            "verificationCode": "000000",
        },
    )
    print("  验证码错误/过期 (期望 422):")
    check("reset_password_bad_code", r, 422)

    # ---------- 登录 ----------
    print("\n========== 登录 ==========")
    r = client.post("/auth/login", params={"email": "nonexist@example.com", "password": "x"})
    print("  邮箱未注册:")
    check("login_not_found", r, 400)

    r = client.post(
        "/auth/login",
        params={"email": "test@example.com", "password": "wrong_password"},
    )
    print("  密码错误 (若该邮箱未注册则可能 400):")
    check("login_wrong_password", r, 400)

    r = client.post(
        "/auth/login",
        params={"email": "test@example.com", "password": "password123"},
    )
    print("  登录成功 (test@example.com / password123，若未注册则可能 400):")
    if r.status_code == 200:
        j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        print(f"  {r.status_code}  message={j.get('message')}")
        print(f"  access_token: {j.get('access_token', '')}")
        print(f"  refresh_token: {j.get('refresh_token', '')}")
        ok += 1
    else:
        print(f"  {r.status_code}  {r.json() if r.headers.get('content-type', '').startswith('application/json') else ''}")
        print("  (若未用验证码完成注册，该账号不存在，可忽略)")
        fail += 1

    # ---------- 汇总 ----------
    print("\n========== 汇总 ==========")
    print(f"  通过: {ok}  与期望不符: {fail}")
    if fail > 0:
        print("  部分用例依赖数据库与正确验证码，500 或与期望不符时请检查 DB 与 .env。")
    print("  完整流程: 先调验证码接口 -> 从 DB 或邮件取 code -> 再调注册/重置密码。")


if __name__ == "__main__":
    print("运行前请确保: pip install -r requirements.txt")
    print("PostgreSQL 已启动、表已创建、.env 中 JWT 密钥已配置。\n")
    _run_tests()