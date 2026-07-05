# Culinary Funding OS — TODO

Son güncelleme: 05.07.2026

---

## Faz 0 — Keşif & Hukuki ← NEREDEYSE BİTTİ

| ID | Görev | Durum | Kim |
|----|-------|-------|-----|
| f0-01 | ReadMe.md güncellemelerini ana metne entegre et | ✅ | Agent |
| f0-02 | `docs/legal-boundaries.md` | ✅ | Agent |
| f0-03 | `docs/data-sources.md` | ✅ | Agent |
| f0-04 | `docs/html-field-map.md` | ✅ | Agent |
| f0-05 | moysies yazışma taslağı (Almanca) | ✅ | Agent |
| f0-06 | Yazışmayı gönder, yazılı yanıt bekle | ⏳ | **Sen** |

**Faz 0 çıkış kriteri:** 4 doküman ✅ + yazışma taslağı ✅ + e-posta gönderilmiş ⏳

**Senin sıradaki adım:** `docs/correspondence/moysies-anfrage-de.md` — köşeli parantezleri doldur, gönder.

---

## Faz 1 — Backfill Crawler ← SIRADAKİ

**Altyapı (f1-01 → f1-05)**
- [ ] f1-01 Monorepo iskeleti
- [ ] f1-02 Docker Compose (PostgreSQL 16)
- [ ] f1-03 Migration: raw_pages
- [ ] f1-04 Migration: crawl_runs
- [ ] f1-05 SQLAlchemy modelleri

**Crawler modülleri (f1-06 → f1-14)**
- [ ] f1-06 selectors.py
- [ ] f1-07 hash_utils.py
- [ ] f1-08 session.py
- [ ] f1-09 list_parser.py
- [ ] f1-10 pagination.py
- [ ] f1-11 detail_fetcher.py
- [ ] f1-12 rate_limiter.py
- [ ] f1-13 catalog_crawler.py
- [ ] f1-14 crawl_logger.py

**Test & backfill (f1-15 → f1-19)**
- [ ] f1-15 CLI entrypoint
- [ ] f1-16 Smoke test: 1 sayfa
- [ ] f1-17 Smoke test: 3 sayfa pagination
- [ ] f1-18 Tam backfill (~21+ saat)
- [ ] f1-19 Doğrulama: ~2.488 satır

---

## Faz 2 — Günlük Incremental

- [ ] f2-01 content_hash karşılaştırma
- [ ] f2-02 Erken durdurma (3 sayfa)
- [ ] f2-03 Sağlık kontrolü (toplam kayıt)
- [ ] f2-04 Selector hata alarmı
- [ ] f2-05 Cron 03:00 CET
- [ ] f2-06 2 günlük doğrulama

---

## Faz 3 — Enrichment + AI Normalizer

- [ ] f3-01 ⚠️ Faz 0 hukuki teyit tamamlanmış olmalı
- [ ] f3-02 HTML parser → funding_programs
- [ ] f3-03 DB migration: funding_programs, funding_organisations
- [ ] f3-04 pgvector + embedding
- [ ] f3-05 Normalizer: etiketleme
- [ ] f3-06 Normalizer: eligibility_rules
- [ ] f3-07 Normalizer: embedding
- [ ] f3-08 Enrichment worker
- [ ] f3-09 license_attribution
- [ ] f3-10 expired işaretleme

---

## Faz 4 — MVP

- [ ] f4-01 API iskeleti
- [ ] f4-02 companies modülü
- [ ] f4-03 programs modülü
- [ ] f4-04 matcher.py
- [ ] f4-05 matches tablosu
- [ ] f4-06 CC seed eşleşmeleri
- [ ] f4-07 applications state machine
- [ ] f4-08 human review guard
- [ ] f4-09 draft_generator.py
- [ ] f4-10 RabbitMQ
- [ ] f4-11 Danışman UI
- [ ] f4-12 E2E test

---

## Faz 5 — CC Entegrasyonu

- [ ] f5-01 ERP/CRM profil beslemesi
- [ ] f5-02 funding_match vs cc_upsell
- [ ] f5-03 CC hizmet önerisi
- [ ] f5-04 DSGVO şifreli documents

---

## Bağımlılık zinciri

```
Faz 0 (docs + hukuk) ← f0-06 senin tarafında
  └─► Faz 1 (backfill crawler) ← SIRADAKİ
        └─► Faz 2 (incremental)
              └─► Faz 3 (AI — hukuki teyit şart)
                    └─► Faz 4 (MVP)
                          └─► Faz 5 (CC)
```
