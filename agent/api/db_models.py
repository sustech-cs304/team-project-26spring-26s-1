"""SQLAlchemy ORM models mirroring the database schema."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
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
    parent: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("messages.message_id", ondelete="SET NULL"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    thought_steps: Mapped[list | dict] = mapped_column(
        JSON, nullable=False, server_default="'[]'"
    )

    # Relationships
    conversation: Mapped[ConversationRow] = relationship(
        back_populates="messages",
    )
    parent_message: Mapped[MessageRow | None] = relationship(
        remote_side=[message_id],
        foreign_keys=[parent],
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_messages_conversation_created", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<MessageRow {self.message_id!r}>"
