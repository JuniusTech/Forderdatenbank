import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.models import CrawlRun

logger = logging.getLogger(__name__)


class CrawlLogger:
    def __init__(self, session: Session, mode: str):
        self.session = session
        self.run = CrawlRun(run_id=uuid.uuid4(), mode=mode, errors=[])
        self.session.add(self.run)
        self.session.flush()

    @property
    def run_id(self) -> uuid.UUID:
        return self.run.run_id

    def record_page_checked(self) -> None:
        self.run.pages_checked += 1

    def record_new(self) -> None:
        self.run.new_count += 1

    def record_changed(self) -> None:
        self.run.changed_count += 1

    def record_skipped(self) -> None:
        self.run.skipped_count += 1

    def record_total_hits(self, total: int | None) -> None:
        if total is not None:
            self.run.total_hits = total

    def record_error(self, error: dict) -> None:
        errors = list(self.run.errors or [])
        errors.append(error)
        self.run.errors = errors
        logger.warning("Crawl error: %s", error)

    def finish(self, stopped_early_at_page: int | None = None) -> CrawlRun:
        self.run.finished_at = datetime.now(timezone.utc)
        self.run.stopped_early_at_page = stopped_early_at_page
        self.session.flush()
        logger.info(
            "Crawl run %s finished: pages=%s new=%s changed=%s skipped=%s errors=%s",
            self.run.run_id,
            self.run.pages_checked,
            self.run.new_count,
            self.run.changed_count,
            self.run.skipped_count,
            len(self.run.errors or []),
        )
        return self.run
