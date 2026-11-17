"""SQL persistence for review jobs and their findings/events."""
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from backend.app.config import database_url


class Base(DeclarativeBase):
    pass


class ReviewRecord(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate: Mapped[float] = mapped_column(default=0.0)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_diff: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReviewEvent(Base):
    __tablename__ = "review_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    event: Mapped[str] = mapped_column(String(80))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FindingRecord(Base):
    __tablename__ = "findings"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    file_path: Mapped[str] = mapped_column(String(1024), default="<diff>")
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="INFO")
    category: Mapped[str] = mapped_column(String(100), default="review")
    message: Mapped[str] = mapped_column(Text)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_name: Mapped[str] = mapped_column(String(100), default="ReviewerAgent")


engine = create_engine(database_url(), connect_args={"check_same_thread": False} if database_url().startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)
