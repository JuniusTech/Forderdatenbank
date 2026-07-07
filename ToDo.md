# Culinary Funding OS — TODO

Son güncelleme: 06.07.2026

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
| f0-07 | docs/xml-schema-notes.md (gerçek ZIP'ten) | ✅ |
| f0-08 | ReadMe + data-sources XML-first güncelleme | ✅ |

---

## Faz 1a — HTML Crawler (yedek, büyük ölçüde tamam)

| ID | Görev | Durum |
|----|-------|-------|
| f1-01 … f1-15 | Monorepo, DB, crawler iskeleti | ✅ |
| f1-16 | Smoke test | ✅ |
| f1-17 | 3 sayfa pagination | ✅ |
| f1-18 | Tam HTML backfill (~21+ saat) | ⏸️ **Gerekli değil** — XML export birincil |
| f1-19 | Backfill doğrulama | ⏸️ XML ingestor ile değişti |

---

## Faz 1b — XML Ingestor ← ŞİMDİ BURADAYIZ

| ID | Görev | Durum |
|----|-------|-------|
| f1b-01 | Migration: funding_programs tablosu | ✅ |
| f1b-02 | ingest/link_resolver.py — target:/ çözümleme | ✅ |
| f1b-03 | ingest/xml_ingestor.py — gsb:* parse + RichText | ✅ |
| f1b-04 | Kategori etiketleri (_config/Labels) | ✅ |
| f1b-05 | ZIP indirme + extract (export_downloader.py) | ⏳ |
| f1b-06 | Smoke test: 10 program parse + DB upsert | ✅ |
| f1b-07 | Full ingest: 2.488 program | ✅ |
| f1b-08 | Doğrulama: program sayısı, contact/url doluluk oranı | ✅ |

**Lokal veri:** `BMWI/` (~10.352 XML, gitignore'da)

---

## Faz 2 — Günlük Sync

- [ ] f2-01: Günlük ZIP indir + full snapshot diff
- [ ] f2-02: (opsiyonel) HTML incremental crawler
- [ ] f2-03: Program sayısı sağlık kontrolü (~2.488 ±%5)
- [ ] f2-04: APScheduler/cron gece 03:00 CET

---

## Faz 3–5

Değişmedi — Faz 1b tamamlanınca Faz 3 (AI Normalizer) öncesi Faz 0 hukuki teyit zorunlu.

---

## Hızlı komutlar

```bash
# DB başlat
cd infra && docker compose up -d

# HTML crawler offline test (yedek)
cd packages/ai-worker && source .venv/bin/activate
pytest tests/ -q
python -m ingest.catalog_crawler --mode fixture

# XML ingestor (Faz 1b — henüz yazılmadı)
python -m ingest.xml_ingestor --source ../../BMWI --limit 10
```
