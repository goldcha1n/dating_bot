from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False, default=16)  # 16..99
    age_filter_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)  # 'M' or 'F'
    looking_for: Mapped[str] = mapped_column(String(1), nullable=False)  # 'M'/'F'/'A'
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    about: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # True => search in any city; False => only in own city
    search_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # False => hidden profile (pause)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    photos: Mapped[List["Photo"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    messages: Mapped[List["Message"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("age BETWEEN 16 AND 99", name="ck_users_age"),
        CheckConstraint("gender IN ('M','F')", name="ck_users_gender"),
        CheckConstraint("looking_for IN ('M','F','A')", name="ck_users_looking_for"),
        Index("ix_users_city", "city"),
        Index("ix_users_username", "username"),
    )


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[str] = mapped_column(String(256), nullable=False)
    is_main: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped["User"] = relationship(back_populates="photos")

    __table_args__ = (
        Index("ix_photos_user_main", "user_id", "is_main"),
    )


class Like(Base):
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # True => like, False => skip (we store view history in one table)
    is_like: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("from_user_id", "to_user_id", name="uq_likes_from_to"),
        Index("ix_likes_pair", "from_user_id", "to_user_id"),
    )


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Normalized pair: user1_id < user2_id
    user1_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    user2_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user1_id", "user2_id", name="uq_matches_pair"),
        Index("ix_matches_user1", "user1_id"),
        Index("ix_matches_user2", "user2_id"),
    )


class ActionLog(Base):
    """Action log used for rate limiting (SQLite-friendly)."""

    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_action_logs_user_action_time", "user_id", "action", "created_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(3), nullable=False)  # in/out
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="messages")


class AdminAction(Base):
    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_username: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(String(64))
    target_id: Mapped[Optional[int]] = mapped_column(Integer)
    payload_json: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
