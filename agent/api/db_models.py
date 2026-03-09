"""SQLAlchemy ORM models mirroring the database schema."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Integer,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.types import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class ConversationRow(Base):
    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    is_pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    context: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="'{}'")
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSON, nullable=False, server_default="'{}'"
    )
    last_message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_message_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # One-to-many: a conversation owns many messages
    messages: Mapped[list[MessageRow]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MessageRow.created_at",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ConversationRow {self.conversation_id!r}>"


class MessageRow(Base):
    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="final")
    attachment_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    thought_steps: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default="'[]'"
    )
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSON, nullable=False, server_default="'{}'"
    )

    # Relationships
    conversation: Mapped[ConversationRow] = relationship(
        back_populates="messages",
    )
    __table_args__ = (
        UniqueConstraint("conversation_id", "seq", name="uq_messages_conversation_seq"),
        UniqueConstraint("conversation_id", "parent_id", name="uq_messages_one_child_per_parent"),
        Index("idx_messages_conversation_seq", "conversation_id", "seq"),
        Index("idx_messages_conversation_created", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<MessageRow {self.message_id!r}>"
