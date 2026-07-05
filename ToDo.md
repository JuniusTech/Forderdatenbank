# Culinary Funding OS — TODO

Son güncelleme: 05.07.2026

---

## Faz 0 — Keşif & Hukuki

| ID | Görev | Durum |
|----|-------|-------|
| f0-01 | ReadMe.md entegrasyonu | ✅ |
| f0-02 | docs/legal-boundaries.md | ✅ |
| f0-03 | docs/data-sources.md | ✅ |
| f0-04 | docs/html-field-map.md | ✅ |
| f0-05 | moysies yazışma taslağı | ✅ |
| f0-06 | E-posta gönder | ⏳ **Sen** |

---

## Faz 1 — Backfill Crawler ← BÜYÜK ÖLÇÜDE TAMAM

| ID | Görev | Durum |
|----|-------|-------|
| f1-01 | Monorepo iskeleti | ✅ |
| f1-02 | Docker Compose (port 15432) | ✅ |
| f1-03 | Migration: raw_pages | ✅ |
| f1-04 | Migration: crawl_runs | ✅ |
| f1-05 | SQLAlchemy modelleri | ✅ |
| f1-06 | selectors.py | ✅ |
| f1-07 | hash_utils.py | ✅ |
| f1-08 | session.py | ✅ |
| f1-09 | list_parser.py | ✅ |
| f1-10 | pagination.py | ✅ |
| f1-11 | detail_fetcher.py | ✅ |
| f1-12 | rate_limiter.py | ✅ |
| f1-13 | catalog_crawler.py | ✅ |
| f1-14 | crawl_logger.py | ✅ |
| f1-15 | CLI entrypoint | ✅ |
| f1-16 | Smoke test | ⚠️ Fixture + unit test OK; canlı site Radware CAPTCHA |
| f1-17 | 3 sayfa pagination test | ⏳ Canlı erişim gerekli |
| f1-18 | Tam backfill (~21+ saat) | ⏳ Canlı erişim gerekli |
| f1-19 | Backfill doğrulama (~2.488) | ⏳ f1-18 sonrası |

**Radware notu:** Otomatik erişim şu an CAPTCHA ile bloklanıyor. `--no-headless` veya moysies API teyidi gerekli. Bkz. `docs/data-sources.md#bot-schutz`

---

## Faz 2 — Günlük Incremental

- [ ] f2-01 … f2-06 (henüz başlanmadı)

---

## Faz 3–5

Değişmedi — Faz 1 canlı backfill tamamlanınca Faz 2'ye geç.

---

## Hızlı komutlar

```bash
# DB başlat
cd infra && docker compose up -d

# Offline doğrulama
cd packages/ai-worker && source .venv/bin/activate
pytest tests/ -q
python -m ingest.catalog_crawler --mode fixture

# Canlı smoke (CAPTCHA riski)
python -m ingest.catalog_crawler --mode smoke --no-headless
```
