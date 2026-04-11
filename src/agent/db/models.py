from __future__ import annotations

import uuid
import datetime as dt
from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey, Text, UniqueConstraint
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
