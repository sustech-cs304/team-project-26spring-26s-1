"""SQLAlchemy ORM models mapped from schema_v2.sql."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from api.db.base import Base


class ConversationORM(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("is_active IN (0,1)", name="ck_conversations_is_active"),
        CheckConstraint("is_pinned IN (0,1)", name="ck_conversations_is_pinned"),
        CheckConstraint("json_valid(context)", name="ck_conversations_context_json_valid"),
        CheckConstraint("json_valid(metadata)", name="ck_conversations_metadata_json_valid"),
        Index("idx_conversations_updated_at", "updated_at"),
        Index("idx_conversations_pinned_updated", "is_pinned", "updated_at"),
    )

    conversation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_pinned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    context: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    metadata_json: Mapped[str] = mapped_column("metadata", Text, nullable=False, default="{}")
    last_message_id: Mapped[Optional[str]] = mapped_column(Text)
    last_message_at: Mapped[Optional[int]] = mapped_column(Integer)


class AttachmentORM(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded','ready','deleted')",
            name="ck_attachments_status",
        ),
        CheckConstraint("json_valid(metadata)", name="ck_attachments_metadata_json_valid"),
        Index("idx_attachments_created_at", "created_at"),
        Index(
            "uq_attachments_sha256",
            "sha256",
            unique=True,
            sqlite_where=text("sha256 IS NOT NULL AND sha256 <> ''"),
        ),
    )

    attachment_id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(Text)
    byte_size: Mapped[Optional[int]] = mapped_column(Integer)
    sha256: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="ready")
    metadata_json: Mapped[str] = mapped_column("metadata", Text, nullable=False, default="{}")


class MessageORM(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "status IN ('streaming','final','error')",
            name="ck_messages_status",
        ),
        CheckConstraint("json_valid(thought_steps)", name="ck_messages_thought_steps_json_valid"),
        CheckConstraint("json_valid(history_context)", name="ck_messages_history_context_json_valid"),
        CheckConstraint("json_valid(metadata)", name="ck_messages_metadata_json_valid"),
        UniqueConstraint("conversation_id", "seq", name="uq_message_conversation_seq"),
        Index("idx_messages_conversation_seq", "conversation_id", "seq"),
        Index("idx_messages_conversation_created", "conversation_id", "created_at"),
    )

    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="final")
    attachment_id: Mapped[Optional[str]] = mapped_column(
        Text,
        ForeignKey("attachments.attachment_id", ondelete="SET NULL"),
    )
    thought_steps: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    history_context: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[str] = mapped_column("metadata", Text, nullable=False, default="{}")


class SkillORM(Base):
    __tablename__ = "skills"
    __table_args__ = (
        CheckConstraint(
            "status IN ('enabled','disabled','deprecated')",
            name="ck_skills_status",
        ),
        CheckConstraint("json_valid(metadata)", name="ck_skills_metadata_json_valid"),
        Index("idx_skills_status", "status"),
    )

    skill_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="enabled")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[str] = mapped_column("metadata", Text, nullable=False, default="{}")
