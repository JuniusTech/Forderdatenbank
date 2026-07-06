#!/usr/bin/env python3
"""Tabloları oluştur — ilk kurulumda bir kez çalıştır.

Kullanım (packages/ai-worker dizininden):
    python -m scripts.init_db
"""

from db.session import init_db, get_session
from sqlalchemy import text


def main() -> None:
    print("Tablolar oluşturuluyor...")
    init_db()

    with get_session() as s:
        tables = s.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
        ).fetchall()
        print("Mevcut tablolar:", [t[0] for t in tables])

        for name in ("raw_pages", "crawl_runs"):
            count = s.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar()
            print(f"  {name}: {count} satır")


if __name__ == "__main__":
    main()
