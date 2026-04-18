from __future__ import annotations

import uuid
import datetime as dt
from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    time_last_used: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        index=True,
    )
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    messages: Mapped[list["Message"]] = relationship("Message", back_populates="conversation")
    im_session_binding: Mapped["IMSessionBinding | None"] = relationship("IMSessionBinding", back_populates="conversation")

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    langchain_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    attachments: Mapped[list["MessageAttachment"]] = relationship("MessageAttachment", back_populates="message", passive_deletes=True, cascade="all, delete-orphan")

class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    mineru_id: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    message_links: Mapped[list["MessageAttachment"]] = relationship("MessageAttachment", back_populates="attachment")

class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=True)
    attachment_id: Mapped[str] = mapped_column(String(36), ForeignKey("attachments.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    message: Mapped["Message"] = relationship("Message", back_populates="attachments")
    attachment: Mapped["Attachment"] = relationship("Attachment", back_populates="message_links")

class IMSessionBinding(Base):
    __tablename__ = "im_session_bindings"
    __table_args__ = (
        UniqueConstraint("conversation_id"),
    )

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chat_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="im_session_binding")

class IMPermission(Base):
    __tablename__ = "im_permissions"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chat_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    is_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=lambda: dt.datetime.now(dt.timezone.utc))


class ScheduledTask(Base):
    """Scheduled task definition plus current/latest execution state."""

    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cron_expression: Mapped[str | None] = mapped_column(String(255), nullable=True)
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="script")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="enabled", index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="")
    env_var_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )
    last_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    last_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_run_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_run_trigger: Mapped[str | None] = mapped_column(String(20), nullable=True)

    logs: Mapped[list["TaskLog"]] = relationship(
        "TaskLog",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskLog.seq",
    )

    __table_args__ = (
        Index("ix_tasks_status_updated", "status", "updated_at"),
    )


class TaskLog(Base):
    """Per-log entry storage with denormalized run metadata."""

    __tablename__ = "task_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(String(10), nullable=False, default="info")
    log_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entry_status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    input_params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    run_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    run_trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    run_override_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    run_finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped["ScheduledTask"] = relationship("ScheduledTask", back_populates="logs")

    __table_args__ = (
        Index("ix_task_logs_task_run_seq", "task_id", "run_id", "seq"),
        Index("ix_task_logs_task_started", "task_id", "run_started_at"),
        Index("ix_task_logs_run_started", "run_id", "run_started_at"),
    )


class LocalSkill(Base):
    """Downloaded skill cached in local storage."""

    __tablename__ = "local_skills"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    cloud_skill_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    markdown_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    downloaded_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )

    __table_args__ = (
        Index("ix_local_skills_cloud_skill_id", "cloud_skill_id"),
    )



class RoutineSource(Base):
    """Calendar source row (e.g. BB stream); table name matches legacy ``routine.py``."""

    __tablename__ = "source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="#808080")
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    events: Mapped[list["RoutineEvent"]] = relationship(
        "RoutineEvent", back_populates="source", lazy="selectin"
    )


class RoutineEvent(Base):
    """One schedule row; ``time_`` is Unix seconds; ``color`` is event display color (see Downloads ``routine.py``)."""

    __tablename__ = "routine"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    time_: Mapped[int] = mapped_column(Integer, nullable=False)
    end_time_: Mapped[int] = mapped_column(Integer, nullable=False)
    event_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="#3b82f6")
    need_inform: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    inform_way: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source.id"), nullable=True, default=None)

    source: Mapped["RoutineSource | None"] = relationship(
        "RoutineSource", back_populates="events", lazy="joined"
    )


class Credential(Base):
    __tablename__ = "credentials"

    credential_type: Mapped[str] = mapped_column("type", String(64), primary_key=True)
    credential_key: Mapped[str] = mapped_column("key", String(1024), primary_key=True)
    value_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
        nullable=False,
    )
