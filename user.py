"""
Skills Hub - 用户认证与技能管理后端 (MVP)
数据库: SQLite
"""

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import asyncio
import os
import re
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import jwt
from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============== 配置 ==============
PASSWORD_SALT = os.environ.get("PASSWORD_SALT", "change-me-in-production")
ACCESS_TOKEN_SECRET = os.environ.get(
    "ACCESS_TOKEN_SECRET") or "dev-secret-change-in-production"
REFRESH_TOKEN_SECRET = os.environ.get(
    "REFRESH_TOKEN_SECRET") or "dev-refresh-secret"
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.environ.get(
    "ACCESS_TOKEN_EXPIRE_SECONDS", 604800))  # 7天
MAX_PENDING_SKILLS = 5
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB
MAX_SKILL_NAME_LENGTH = 50
MAX_TAG_NAME_LENGTH = 6

DB_PATH = os.environ.get("DB_PATH", "skills_hub.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# ============== 密码与邮箱验证 ==============


def hash_password(password: str) -> str:
    return sha256((PASSWORD_SALT + password).encode()).hexdigest()


_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def is_valid_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    if not _EMAIL_PATTERN.match(email):
        return False
    # 必须为 .edu.cn 域名
    return email.lower().endswith('.edu.cn')


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

# ============== 数据库模型 ==============


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password: Mapped[str] = mapped_column(nullable=False)
    username: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(default='user')
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"))


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(nullable=False, index=True)
    code: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"))


class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=True)
    markdown_content: Mapped[str] = mapped_column(nullable=False)
    user_id: Mapped[int] = mapped_column(nullable=False)
    # pending/approved/rejected/archived
    status: Mapped[str] = mapped_column(default='pending')
    rejection_reason: Mapped[str] = mapped_column(nullable=True)
    download_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text(
        "CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))


class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)


class SkillTag(Base):
    __tablename__ = "skill_tags"
    skill_id: Mapped[int] = mapped_column(primary_key=True)
    tag_id: Mapped[int] = mapped_column(primary_key=True)


# ============== 数据库连接 ==============

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # 插入默认管理员
        admin = db.query(User).filter(User.email == "admin@edu.cn").first()
        if not admin:
            admin = User(
                email="admin@edu.cn",
                password=hash_password("admin123"),
                username="Administrator",
                role="admin"
            )
            db.add(admin)

        # 插入预设标签
        default_tags = ["编程辅助", "数据分析", "文档生成",
                        "图像处理", "自然语言处理", "自动化", "机器学习", "Web开发"]
        for tag_name in default_tags:
            if not db.query(Tag).filter(Tag.name == tag_name).first():
                db.add(Tag(name=tag_name))

        # 清理超长标签（超过 6 个字），并清理关联关系
        overlong_tags = db.query(Tag).all()
        for tag in overlong_tags:
            if len(tag.name) > MAX_TAG_NAME_LENGTH:
                db.query(SkillTag).filter(SkillTag.tag_id == tag.id).delete()
                db.delete(tag)

        db.commit()
    finally:
        db.close()

# ============== JWT 工具 ==============


def _jwt_payload(user_id: int, role: str, expire_seconds: int) -> dict:
    now = int(time.time())
    return {"user_id": user_id, "role": role, "iat": now, "exp": now + expire_seconds}


def generate_access_token(user_id: int, role: str = "user") -> str:
    payload = _jwt_payload(user_id, role, ACCESS_TOKEN_EXPIRE_SECONDS)
    return jwt.encode(payload, ACCESS_TOKEN_SECRET, algorithm="HS256")


def verify_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, ACCESS_TOKEN_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """从请求中获取当前用户"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header[7:]
    payload = verify_access_token(token)
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_current_admin(user: User = Depends(get_current_user)):
    """验证管理员权限"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# ============== 验证码工具 ==============


def generate_verification_code() -> str:
    return str(random.randint(100000, 999999))


def send_verification_email(email: str, code: str):
    """发送验证码邮件（复用飞书 SMTP）"""
    try:
        from send_verify import send_verification_email as feishu_send
        feishu_send(email, code)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to send email: {e}")


def send_notification_email_safe(email: str, content: str):
    """后台发送通知邮件，失败时吞掉异常，避免影响主流程"""
    try:
        from send_verify import send_verification_email
        send_verification_email(email, content)
    except Exception:
        pass

# ============== 技能格式校验 ==============


def validate_markdown(content: str) -> tuple[bool, str, str, str]:
    """校验 Markdown 格式，返回 (是否有效, name, description, error_msg)"""
    if len(content.encode()) > MAX_FILE_SIZE:
        return False, "", "", "文件大小超过 1MB"

    if "## Name" not in content:
        return False, "", "", "缺少 ## Name 标题"
    if "## Description" not in content:
        return False, "", "", "缺少 ## Description 标题"
    if "## Usage" not in content:
        return False, "", "", "缺少 ## Usage 标题"

    # 检查禁止的可执行代码块
    forbidden_blocks = ["```bash", "```python",
                        "```sh", "```powershell", "```cmd"]
    for block in forbidden_blocks:
        if block in content.lower():
            return False, "", "", f"禁止的可执行代码块: {block}"

    # 解析二级标题区块，兼容两种写法：
    # 1) ## Name My Skill
    # 2) ## Name\nMy Skill
    sections: dict[str, str] = {}
    current_header = ""
    current_lines: list[str] = []
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            if current_header:
                sections[current_header] = "\n".join(current_lines).strip()
            current_header = line[3:].strip()
            current_lines = []
            continue

        if current_header:
            current_lines.append(line)

    if current_header:
        sections[current_header] = "\n".join(current_lines).strip()

    # 支持 "## Name xxx" 这种标题同一行有内容的写法
    name_match = re.search(r"^##\s+Name\s+(.+)$", content, flags=re.MULTILINE)
    desc_match = re.search(r"^##\s+Description\s+(.+)$",
                           content, flags=re.MULTILINE)

    name = ""
    desc = ""

    if name_match and name_match.group(1).strip():
        name = name_match.group(1).strip()
    elif sections.get("Name"):
        name = sections["Name"].splitlines()[0].strip()

    if desc_match and desc_match.group(1).strip():
        desc = desc_match.group(1).strip()
    elif sections.get("Description"):
        desc = sections["Description"].splitlines()[0].strip()

    if not name:
        return False, "", "", "技能名称不能为空（请在 ## Name 下填写）"
    if len(name) > MAX_SKILL_NAME_LENGTH:
        return False, "", "", f"技能名称不能超过 {MAX_SKILL_NAME_LENGTH} 个字符"

    return True, name, desc, ""


# ============== FastAPI 应用 ==============
app = FastAPI(title="Skills Hub", version="1.0.0")

# 静态文件和模板
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# ============== Pydantic 模型 ==============


class RegisterCaptchaData(BaseModel):
    email: str


class RegisterData(BaseModel):
    username: str
    email: str
    password: str
    verificationCode: str


class LoginData(BaseModel):
    email: str
    password: str


class SkillUploadData(BaseModel):
    tag_ids: list[int]


class SkillUpdateData(BaseModel):
    description: str | None = None
    tag_ids: list[int] | None = None


class RejectData(BaseModel):
    reason: str = ""

# ============== 认证 API ==============


@app.post("/auth/register/captcha")
async def send_captcha(body: RegisterCaptchaData, db: Session = Depends(get_db)):
    email = body.email
    if not is_valid_email(email):
        raise HTTPException(status_code=400, detail="仅支持 .edu.cn 邮箱")

    # 检查频率
    fifteen_min_ago = datetime.now() - timedelta(minutes=15)
    existing = db.query(EmailVerification).filter(
        EmailVerification.email == email,
        EmailVerification.created_at > fifteen_min_ago
    ).first()

    if existing:
        if existing.created_at > datetime.now() - timedelta(minutes=1):
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
        db.delete(existing)

    code = generate_verification_code()
    verification = EmailVerification(email=email, code=code)
    db.add(verification)
    db.commit()

    send_verification_email(email, code)
    return {"message": "验证码已发送"}


@app.post("/auth/register")
async def register(body: RegisterData, db: Session = Depends(get_db)):
    if not is_valid_email(body.email):
        raise HTTPException(status_code=400, detail="仅支持 .edu.cn 邮箱")
    if not is_valid_password(body.password):
        raise HTTPException(status_code=400, detail="密码需6-16位，包含字母和数字")

    # 验证验证码
    fifteen_min_ago = datetime.now() - timedelta(minutes=15)
    verification = db.query(EmailVerification).filter(
        EmailVerification.email == body.email,
        EmailVerification.code == body.verificationCode,
        EmailVerification.created_at > fifteen_min_ago
    ).order_by(EmailVerification.created_at.desc()).first()

    if not verification:
        raise HTTPException(status_code=422, detail="验证码无效或已过期")

    db.delete(verification)

    # 检查邮箱是否已注册
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="邮箱已注册")

    user = User(
        username=body.username,
        email=body.email,
        password=hash_password(body.password),
        role="user"
    )
    db.add(user)
    db.commit()

    return {"message": "注册成功", "email": body.email}


@app.post("/auth/login")
async def login(body: LoginData, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(status_code=400, detail="邮箱或密码错误")
    if user.password != hash_password(body.password):
        raise HTTPException(status_code=400, detail="邮箱或密码错误")

    token = generate_access_token(user.id, user.role)
    return {
        "message": "登录成功",
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "access_token": token
    }


@app.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role
    }

# ============== 客户端 API (公开) ==============


@app.get("/api/skills")
async def get_skills(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tag_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db)
):
    """获取已上架技能列表"""
    query = db.query(Skill).filter(Skill.status == "approved")

    if tag_id:
        query = query.join(SkillTag).filter(SkillTag.tag_id == tag_id)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Skill.name.ilike(search_pattern),
                Skill.description.ilike(search_pattern)
            )
        )

    total = query.count()
    skills = query.order_by(Skill.created_at.desc()).offset(
        (page-1)*page_size).limit(page_size).all()

    result = []
    for skill in skills:
        tags = db.query(Tag).join(SkillTag, Tag.id == SkillTag.tag_id).filter(
            SkillTag.skill_id == skill.id).all()
        result.append({
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "download_count": skill.download_count,
            "tags": [{"id": t.id, "name": t.name} for t in tags],
            "created_at": skill.created_at.isoformat() if skill.created_at else None
        })

    return {"total": total, "page": page, "page_size": page_size, "skills": result}


@app.get("/api/skills/me")
async def get_my_skills(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """获取我的提交"""
    skills = db.query(Skill).filter(Skill.user_id == user.id).order_by(
        Skill.created_at.desc()).all()
    result = []
    for skill in skills:
        tags = db.query(Tag).join(SkillTag, Tag.id == SkillTag.tag_id).filter(
            SkillTag.skill_id == skill.id).all()
        result.append({
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "status": skill.status,
            "rejection_reason": skill.rejection_reason,
            "download_count": skill.download_count,
            "tags": [{"id": t.id, "name": t.name} for t in tags],
            "created_at": skill.created_at.isoformat() if skill.created_at else None
        })
    return result


@app.get("/api/skills/{skill_id}")
async def get_skill_detail(skill_id: int, db: Session = Depends(get_db)):
    """获取技能详情"""
    skill = db.query(Skill).filter(Skill.id == skill_id,
                                   Skill.status == "approved").first()
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    tags = db.query(Tag).join(SkillTag, Tag.id == SkillTag.tag_id).filter(
        SkillTag.skill_id == skill.id).all()
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "markdown_content": skill.markdown_content,
        "download_count": skill.download_count,
        "tags": [{"id": t.id, "name": t.name} for t in tags],
        "created_at": skill.created_at.isoformat() if skill.created_at else None
    }


@app.get("/api/skills/{skill_id}/download")
async def download_skill(skill_id: int, db: Session = Depends(get_db)):
    """下载技能文件"""
    skill = db.query(Skill).filter(Skill.id == skill_id,
                                   Skill.status == "approved").first()
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    skill.download_count += 1
    db.commit()

    return Response(
        content=skill.markdown_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename={skill.name}.md"}
    )


@app.get("/api/tags")
async def get_tags(db: Session = Depends(get_db)):
    """获取所有标签"""
    tags = db.query(Tag).order_by(Tag.name).all()
    return [{"id": t.id, "name": t.name} for t in tags]

# ============== 用户技能 API ==============


@app.post("/api/skills")
async def upload_skill(
    request: Request,
    file: UploadFile = Form(...),
    tag_ids: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """上传技能"""
    # 检查 pending 数量限制
    pending_count = db.query(Skill).filter(
        Skill.user_id == user.id,
        Skill.status == "pending"
    ).count()
    if pending_count >= MAX_PENDING_SKILLS:
        raise HTTPException(
            status_code=400, detail=f"同时最多 {MAX_PENDING_SKILLS} 个待审核技能")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 1MB")

    markdown = content.decode("utf-8")
    valid, name, desc, error = validate_markdown(markdown)
    if not valid:
        raise HTTPException(status_code=400, detail=f"格式校验失败: {error}")

    skill = Skill(
        name=name or (file.filename or "skill.md").replace(".md", ""),
        description=desc,
        markdown_content=markdown,
        user_id=user.id,
        status="pending"
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)

    # 关联标签
    if tag_ids:
        for tag_id in tag_ids.split(","):
            if tag_id.strip():
                db.add(SkillTag(skill_id=skill.id, tag_id=int(tag_id.strip())))
        db.commit()

    return {"message": "上传成功", "skill_id": skill.id, "status": skill.status}


# ============== 管理员 API ==============


@app.get("/admin/dashboard")
async def get_dashboard(user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """数据概览"""
    pending_count = db.query(Skill).filter(Skill.status == "pending").count()
    total_skills = db.query(Skill).filter(Skill.status == "approved").count()
    total_downloads = db.query(func.sum(Skill.download_count)).scalar() or 0

    # 本周新增
    week_ago = datetime.now() - timedelta(days=7)
    week_new = db.query(Skill).filter(
        Skill.status == "approved",
        Skill.created_at > week_ago
    ).count()

    return {
        "pending_count": pending_count,
        "approved_count": total_skills,
        "week_new": week_new,
        "total_downloads": total_downloads
    }


@app.get("/admin/skills/pending")
async def get_pending_skills(
    sort: str = "desc",
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """待审核列表"""
    query = db.query(Skill).filter(Skill.status == "pending")
    if sort == "asc":
        query = query.order_by(Skill.created_at.asc())
    else:
        query = query.order_by(Skill.created_at.desc())

    skills = query.all()
    result = []
    for skill in skills:
        u = db.query(User).filter(User.id == skill.user_id).first()
        tags = db.query(Tag).join(SkillTag, Tag.id == SkillTag.tag_id).filter(
            SkillTag.skill_id == skill.id).all()
        result.append({
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "markdown_content": skill.markdown_content,
            "status": skill.status,
            "user_email": u.email if u else "未知",
            "tags": [{"id": t.id, "name": t.name} for t in tags],
            "created_at": skill.created_at.isoformat() if skill.created_at else None
        })
    return result


@app.post("/admin/skills/{skill_id}/approve")
async def approve_skill(
    skill_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """批准技能"""
    skill = db.query(Skill).filter(Skill.id == skill_id,
                                   Skill.status == "pending").first()
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在或不在待审核状态")

    skill.status = "approved"
    db.commit()

    # 后台发送邮件通知，不阻塞接口返回
    u = db.query(User).filter(User.id == skill.user_id).first()
    if u:
        background_tasks.add_task(
            send_notification_email_safe,
            u.email,
            f"您的技能「{skill.name}」已通过审核并上架！"
        )

    return {"message": "已批准", "skill_id": skill_id}


@app.post("/admin/skills/{skill_id}/reject")
async def reject_skill(
    skill_id: int,
    body: RejectData,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """拒绝技能"""
    if not body.reason or not body.reason.strip():
        raise HTTPException(status_code=400, detail="拒绝原因不能为空")
    skill = db.query(Skill).filter(Skill.id == skill_id,
                                   Skill.status == "pending").first()
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在或不在待审核状态")

    skill.status = "rejected"
    skill.rejection_reason = body.reason
    db.commit()

    # 后台发送邮件通知，不阻塞接口返回
    u = db.query(User).filter(User.id == skill.user_id).first()
    if u:
        background_tasks.add_task(
            send_notification_email_safe,
            u.email,
            f"您的技能「{skill.name}」未通过审核。原因: {body.reason}"
        )

    return {"message": "已拒绝", "skill_id": skill_id}


@app.get("/admin/skills/approved")
async def get_approved_skills(
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """已上架技能列表"""
    skills = db.query(Skill).filter(Skill.status == "approved").order_by(
        Skill.created_at.desc()).all()
    result = []
    for skill in skills:
        tags = db.query(Tag).join(SkillTag, Tag.id == SkillTag.tag_id).filter(
            SkillTag.skill_id == skill.id).all()
        result.append({
            "id": skill.id,
            "name": skill.name,
            "description": skill.description,
            "download_count": skill.download_count,
            "tags": [{"id": t.id, "name": t.name} for t in tags],
            "created_at": skill.created_at.isoformat() if skill.created_at else None
        })
    return result


@app.put("/admin/skills/{skill_id}")
async def update_skill(
    skill_id: int,
    body: SkillUpdateData,
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """编辑技能（标签和描述）"""
    skill = db.query(Skill).filter(Skill.id == skill_id,
                                   Skill.status == "approved").first()
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    if body.description is not None:
        skill.description = body.description

    if body.tag_ids is not None:
        # 删除旧关联
        db.query(SkillTag).filter(SkillTag.skill_id == skill_id).delete()
        # 添加新关联
        for tag_id in body.tag_ids:
            db.add(SkillTag(skill_id=skill_id, tag_id=tag_id))

    db.commit()
    return {"message": "更新成功"}


@app.post("/admin/skills/{skill_id}/archive")
async def archive_skill(
    skill_id: int,
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """下架技能"""
    skill = db.query(Skill).filter(Skill.id == skill_id,
                                   Skill.status == "approved").first()
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    skill.status = "archived"
    db.commit()
    return {"message": "已下架"}


@app.get("/admin/tags")
async def get_admin_tags(user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """获取所有标签"""
    tags = db.query(Tag).order_by(Tag.name).all()
    return [{"id": t.id, "name": t.name} for t in tags]


@app.post("/admin/tags")
async def create_tag(name: str = Form(...), user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """创建标签"""
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="标签名不能为空")
    normalized_name = name.strip()
    if len(normalized_name) > MAX_TAG_NAME_LENGTH:
        raise HTTPException(
            status_code=400, detail=f"标签名不能超过 {MAX_TAG_NAME_LENGTH} 个字")
    if db.query(Tag).filter(Tag.name == normalized_name).first():
        raise HTTPException(status_code=409, detail="标签已存在")
    tag = Tag(name=normalized_name)
    db.add(tag)
    db.commit()
    return {"message": "标签已创建", "id": tag.id}

# ============== 前端页面 ==============


@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/admin/pending", response_class=HTMLResponse)
async def admin_pending_page(request: Request):
    return templates.TemplateResponse("admin_pending.html", {"request": request})


@app.get("/admin/skills", response_class=HTMLResponse)
async def admin_skills_page(request: Request):
    return templates.TemplateResponse("admin_skills.html", {"request": request})

# ============== 启动 ==============


@app.on_event("startup")
async def startup():
    init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
