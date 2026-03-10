import asyncio
from math import log
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
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.environ.get("ACCESS_TOKEN_EXPIRE_SECONDS", "10800")) 


def hash_password(password: str) -> str:
    return sha256((PASSWORD_SALT + password).encode()).hexdigest()

_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


def is_valid_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    return _EMAIL_PATTERN.match(email) is not None

def is_valid_password(password: str) -> bool:
    if not password:
        return False
    if not 6 <= len(password) <= 16:
        return False
    if re.fullmatch(r"[A-Za-z0-9]+", password) is None:
        return False
    if re.search(r"[A-Za-z]", password) is None:
        return False
    if re.search(r"[0-9]", password) is None:
        return False
    return True

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


def send_verification_code(email: str, verification_code: str):
    try:
        from send_verify import send_verification_email
        send_verification_email(email, verification_code)
    except Exception as e:
        detail = "Failed to send verification email"
        if os.environ.get("DEBUG"):
            detail = f"Failed to send verification email: {e}"
        raise APIException(status_code=500, message=detail)


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


class RegisterCaptchaData(BaseModel):
    email: str

class SendPasswordResetCaptchaData(BaseModel):
    email: str

class LoginData(BaseModel):
    email: str
    password: str


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


def verify_access_token(token: str) -> dict:
    if not ACCESS_TOKEN_SECRET:
        raise APIException(status_code=500, message="Internal server error")
    return jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=["HS256"])


def verify_refresh_token(token: str) -> dict:
    if not REFRESH_TOKEN_SECRET:
        raise APIException(status_code=500, message="Internal server error")
    return jwt.decode(token, REFRESH_TOKEN_SECRET, algorithms=["HS256"])


@app.post("/auth/register/captcha")
async def send_captcha(body: RegisterCaptchaData, db: AsyncSession = Depends(get_db)):
    email = body.email
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
            if verification.created_at < _utc_now_naive() - timedelta(minutes=1):
                await db.delete(verification)
            else:
                raise APIException(status_code=429, message="Too many requests")
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
    body: RegisterData,
    db: AsyncSession = Depends(get_db),
):
    register_data = body
    if not is_valid_email(register_data.email):
        raise APIException(status_code=400, message="Invalid email format")
    if not is_valid_password(register_data.password):
        raise APIException(status_code=400, message="Invalid password format")
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

@app.post("/auth/password/reset")
async def reset_password(body: ResetPasswordData, db: AsyncSession = Depends(get_db)):
    reset_password_data = body
    if not is_valid_email(reset_password_data.email):
        raise APIException(status_code=400, message="Invalid email format")
    if not is_valid_password(reset_password_data.password):
        raise APIException(status_code=400, message="Invalid password format")
    try:
        fifteen_min_ago = _utc_now_naive() - timedelta(minutes=15)
        stmt = (
            select(EmailVerification)
            .where(
                and_(
                    EmailVerification.email == reset_password_data.email,
                    EmailVerification.code == reset_password_data.verificationCode,
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

        stmt = select(UserModel).where(UserModel.email == reset_password_data.email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise APIException(status_code=400, message="Email not registered")
        user.password = hash_password(reset_password_data.password)
        await db.flush()
    except APIException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise APIException(status_code=500, message=detail)
    return {"message": "Password reset successfully"}


@app.post("/auth/password/captcha")
async def send_password_reset_captcha(body: SendPasswordResetCaptchaData, db: AsyncSession = Depends(get_db)):
    email = body.email
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
            if verification.created_at < _utc_now_naive() - timedelta(minutes=1):
                await db.delete(verification)
            else:
                raise APIException(status_code=429, message="Too many requests")
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
async def login(body: LoginData, db: AsyncSession = Depends(get_db)):
    login_data = body
    try:
        stmt = select(UserModel).where(UserModel.email == login_data.email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise APIException(status_code=400, message="Email not registered")
        if user.password != hash_password(login_data.password):
            raise APIException(status_code=400, message="Invalid password")
    except APIException:
        raise
    except Exception as e:
        detail = str(e) if os.environ.get("DEBUG") else "Internal server error"
        raise APIException(status_code=500, message=detail)
    access_token = generate_access_token(user.id)
    return {
        "message": "Login successfully",
        "email": login_data.email,
        "access_token": access_token,
    }
