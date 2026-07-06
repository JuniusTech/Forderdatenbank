# ai-worker — Förderdatenbank Crawler

Python ETL worker: catalog crawler, enrichment, AI normalizer.

## Kurulum

```bash
# Yerel Docker (dev) — opsiyonel
cd ../../infra && docker compose up -d

# 2. Python env
cd ../packages/ai-worker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 3. Env — repo kökündeki .env
cp ../../.env.example ../../.env

# 4. Tabloları oluştur (ilk kurulum)
python -m scripts.init_db
```

## Çalıştırma

```bash
# Offline test (ağ yok, DB pipeline doğrulama)
python -m ingest.catalog_crawler --mode fixture

# Unit testler
pytest tests/ -q

# Smoke test (canlı site — Radware CAPTCHA olabilir)
python -m ingest.catalog_crawler --mode smoke --crawl-delay 2

# Tam backfill (~21+ saat, 30 sn/istek)
python -m ingest.catalog_crawler --mode backfill
```

## Radware Bot Koruması

Canlı sitede otomatik erişim Radware CAPTCHA ile engellenebilir.

### Önerilen smoke komutu
```bash
python -m ingest.catalog_crawler --mode smoke --no-headless --channel chrome --wait-for-human
```
1. Chrome açılır
2. CAPTCHA'yı elle çöz
3. Arama sonuçları görününce terminale dön, ENTER'a bas
4. Crawler devam eder

### Diğer seçenekler
- `--cookies-file cookies.json` — tarayıcıdan export edilmiş cookie
- moysies resmi API yazışması (Faz 0)
- Detay: `docs/data-sources.md#bot-schutz`

## Modül yapısı

```
ingest/
  catalog_crawler.py   # orchestrator + CLI
  selectors.py         # CSS sabitleri
  hash_utils.py        # content_hash
  list_parser.py       # arama sonuçları
  pagination.py        # href takibi
  detail_fetcher.py    # detay sayfası
  rate_limiter.py      # 30 sn bekleme
  crawl_logger.py      # crawl_runs
db/
  models.py            # RawPage, CrawlRun
  session.py           # SQLAlchemy
```
