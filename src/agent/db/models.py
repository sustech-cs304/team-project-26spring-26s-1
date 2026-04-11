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


class TaskRun(Base):
    """Single execution of a scheduled task."""

    __tablename__ = "task_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    task_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
    )
    trigger: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual",
    )
    override_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: dt.datetime.now(dt.timezone.utc),
    )
    finished_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    logs: Mapped[list["TaskRunLog"]] = relationship(
        "TaskRunLog",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="TaskRunLog.seq",
    )

    __table_args__ = (
        Index("ix_task_runs_task_started", "task_id", "started_at"),
    )


class TaskRunLog(Base):
    """Single log line belonging to a :class:`TaskRun`."""

    __tablename__ = "task_run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task_runs.id", ondelete="CASCADE"), nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(
        String(10), nullable=False, default="stdout",
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    entry_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["TaskRun"] = relationship("TaskRun", back_populates="logs")

    __table_args__ = (
        Index("ix_task_run_logs_run_seq", "run_id", "seq"),
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
    event_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="#3b82f6")
    need_inform: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    inform_way: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source.id"), nullable=True, default=None)

    source: Mapped["RoutineSource | None"] = relationship(
        "RoutineSource", back_populates="events", lazy="joined"
    )
