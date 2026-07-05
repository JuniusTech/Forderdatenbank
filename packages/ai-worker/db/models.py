import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawPage(Base):
    __tablename__ = "raw_pages"

    url: Mapped[str] = mapped_column(Text, primary_key=True)
    raw_html: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source_valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pages_checked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    changed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stopped_early_at_page: Mapped[int | None] = mapped_column(Integer)
    total_hits: Mapped[int | None] = mapped_column(Integer)
    errors: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
