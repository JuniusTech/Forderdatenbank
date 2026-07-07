"""Bekleyen SQL migration dosyalarını uygula."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from db.session import engine

_REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = _REPO_ROOT / "infra" / "migrations"


def apply_migrations() -> None:
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    # Sadece henüz uygulanmamış migration'ları çalıştır (idempotent SQL varsayımı)
    with engine.begin() as conn:
        for path in files:
            sql = path.read_text(encoding="utf-8")
            for statement in sql.split(";"):
                stmt = statement.strip()
                if stmt:
                    conn.execute(text(stmt))
            print(f"  applied: {path.name}")


def main() -> None:
    print("Migrations uygulanıyor...")
    apply_migrations()
    print("Tamam.")


if __name__ == "__main__":
    main()
