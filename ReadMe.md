# Culinary Funding OS — Architecture & Build Primer

Bu doküman ana brief'tir. Amaç: Almanya'daki teşvik/hibe/kredi programlarını Förderdatenbank'tan session-aware HTML crawler ile çeken, eksik alanları hedefli enrichment ile tamamlayan, firma profilini eşleştiren ve AI ile başvuru taslağı üreten uçtan uca bir sistem kurmak.

**Stack:** Node.js/TypeScript API + Python AI/ETL worker.

**Sınır:** Sistem yazılım + danışmanlık aracıdır; kredi aracılığı / komisyon YAPMAZ (§34c/§34i GewO, KWG). AI asla "uygunsun / bu hibeyi alırsın" demez — "aday program, danışman doğrulaması gerekli" der.

---

## 0. Kesin Gerçekler (varsayım değil, doğrulanmış — 05.07.2026)

| Konu | Değer |
|------|-------|
| Resmi veri seti | Förderdatenbank (BMWE/BMWK) — Bund + 16 Land + AB programları |
| Kapsam (ölçüm) | "Förderprogramm" kategorisinde 2.488 kayıt, 10/sayfa × 249 sayfa |
| Erişim | **Resmi API/export YOK.** `/FDB/WS/export` denendi, ana sayfaya yönlendiriyor |
| Alternatif erişim | Arama sonuçları HTML'i, `sortOrder=dateOfIssue_dt+desc` ile tarihe göre azalan sıralama |
| Detay sayfası URL | `/FDB/Content/DE/Foerderprogramm/{Bund\|Land/<Land>\|EU}/{slug}.html` — listeleme sayfalarından keşfedilir |
| Sayfalama | Oturum tabanlı (`resourceId` + `input_` + `gtp` token'ları) — href takibi, manuel URL üretme yok |
| robots.txt | `Crawl-delay: 30` — istekler arası 30 sn zorunlu. Arama yolu izinli |
| Lisans | **CC BY-ND 4.0 DE** — kaynak gösterip olduğu gibi paylaşmak serbest; metin değiştirip yeniden yayınlamak (public-facing AI özeti) lisans dışına çıkabilir → hukuki teyit gerekir |
| Yetkili kaynak uyarısı | Impressum: *"Maßgeblich sind die Angaben auf den offiziellen Webseiten der fördergebenden Stellen"* |
| Güncellik kanalı | RSS/export yok. `content_hash` karşılaştırması + tarihe-göre-azalan liste (bkz. §5) |
| Enrichment hedefi | Dış linkler, iletişim (Kontakt), Förderorganisation detayları |

**İlk iş:** Playwright crawler spesifikasyonu `docs/html-field-map.md`'de. Parser bu belgeye göre kurulur. Önce veriyi TANI.

---

## 1. Sistem Sınırları — Bunları Koda Göm (negotiable değil)

Bunlar mimarinin parçası; sonradan "pazarlama dili" olarak eklenmez, çekirdeğe girer. Detaylı gerekçe: `docs/legal-boundaries.md`.

1. **Kredi aracılığı yok.** Sistem kredi/leasing/kefalet kaynağına yönlendirir ama komisyon almaz, sözleşme yapmaz.
2. **AI garanti vermez.** Her eşleştirme: confidence skoru + disclaimer. UI'da sabit metin: *"Nihai karar ilgili kuruma aittir."* Her Match: `human_review_required: true` default.
3. **İnsan-in-the-loop zorunlu.** AI taslağı → danışman onayı olmadan `ready_to_submit` statüsüne GEÇEMEZ (bkz. §6).
4. **Çıkar çatışması şeffaflığı.** `recommendation.type: "funding_match" | "cc_upsell"`.
5. **Veri tazeliği görünür.** Her programda `last_synced_at` ve `source_valid_until`. Expired programlar eşleştirmede gösterilmez.

---

## 2. Yüksek Seviye Mimari

```
                         ┌─────────────────────────────────────────┐
                         │            DATA LAYER (Python)           │
                         │                                          │
  Förderdatenbank  ───►  │  [1] Catalog Crawler  (scheduled, daily) │
  HTML (Playwright)      │       - session-aware fetch              │
                         │       - parse (selector-driven)          │
                         │       - upsert → raw_pages table         │
                         │                                          │
  Web (eksik alan) ───►  │  [2] Enrichment Worker (targeted)        │
  Playwright             │       - only fields HTML lacks           │
                         │       - links, contacts, deadlines       │
                         │                                          │
                         │  [3] AI Normalizer                       │
                         │       - free-text → structured tags      │
                         │       - eligibility → machine rules      │
                         │       - embeddings for semantic match    │
                         └───────────────┬──────────────────────────┘
                                         │ writes
                                         ▼
                         ┌─────────────────────────────────────────┐
                         │        PostgreSQL  (single source)       │
                         │  raw_pages · programs · orgs · companies │
                         │  matches · applications · pgvector     │
                         └───────────────┬──────────────────────────┘
                                         │ reads/writes
                         ┌───────────────┴──────────────────────────┐
                         │           API LAYER (Node/TS)            │
                         │  - REST/tRPC for frontend                │
                         │  - company profile CRUD                  │
                         │  - match request → calls AI worker       │
                         │  - application lifecycle / state machine │
                         │  - CRM/ERP integration hooks             │
                         └───────────────┬──────────────────────────┘
                                         │
                         ┌───────────────┴──────────────────────────┐
                         │      AI WORKER  (Python, queue-driven)   │
                         │  - matching engine (rules + semantic)    │
                         │  - application draft generator (LLM)     │
                         │  - German-language output + citations    │
                         └──────────────────────────────────────────┘
```

Node API = ürün katmanı. Python worker = veri işleme, crawling, embeddings, LLM. İkisi RabbitMQ ile konuşur.

---

## 3. Repo Yapısı (monorepo)

```
culinary-funding-os/
├── docs/
│   ├── html-field-map.md          # Playwright selector haritası
│   ├── legal-boundaries.md        # §1 sınırların gerekçesi
│   ├── data-sources.md            # endpoint, lisans, sync sıklığı
│   └── correspondence/            # moysies yazışma taslakları
├── packages/
│   ├── api/                       # Node.js + TypeScript
│   ├── ai-worker/                 # Python
│   │   ├── ingest/
│   │   │   ├── catalog_crawler.py  # [1] HTML çek + parse + upsert
│   │   │   ├── selectors.py
│   │   │   └── hash_utils.py
│   │   ├── enrichment/
│   │   ├── ai/
│   │   └── db/
│   └── shared/
├── infra/
│   ├── docker-compose.yml
│   └── migrations/
├── ReadMe.md
└── ToDo.md
```

---

## 4. Veri Modeli (PostgreSQL — çekirdek tablolar)

### Crawler tabloları (Faz 1)

```sql
raw_pages (
  url text pk,
  raw_html text,
  content_hash text,
  first_seen_at timestamptz,
  last_synced_at timestamptz,
  source_valid_until date
)

crawl_runs (
  run_id uuid pk,
  started_at timestamptz,
  finished_at timestamptz,
  pages_checked int,
  new_count int,
  changed_count int,
  stopped_early_at_page int,
  errors jsonb
)
```

### İş mantığı tabloları (Faz 3+)

```sql
funding_programs (
  id uuid pk,
  source_id text unique,
  title text,
  funding_type text[],
  provider_id uuid fk,
  region text,
  target_groups text[],
  eligible_costs text[],
  amount_min numeric, amount_max numeric,
  deadline_type text,
  deadline_date date,
  application_url text,
  contact jsonb,
  raw_text text,
  eligibility_rules jsonb,
  embedding vector(1536),
  status text,                      -- active | expired | closed
  source_valid_until date,
  last_synced_at timestamptz,
  license_attribution text
)

funding_organisations ( id, name, type, region, website, contact jsonb )

companies (
  id uuid pk, cc_erp_id text,
  legal_form text, founded_year int, region text,
  employees int, annual_revenue numeric, sector text,
  digital_maturity jsonb, investment_need jsonb, growth_plan jsonb,
  bank_relation text, documents jsonb
)

matches (
  id uuid pk, company_id fk, program_id fk,
  score numeric, score_breakdown jsonb,
  missing_documents text[], difficulty text,
  human_review_required bool default true,
  disclaimer text default 'Nihai karar ilgili kuruma aittir.',
  created_at timestamptz
)

applications (
  id uuid pk, company_id fk, program_id fk, match_id fk,
  state text, draft jsonb,
  reviewed_by text, reviewed_at timestamptz,
  submitted_at timestamptz, outcome text
)

pipeline_events ( id, application_id fk, from_state, to_state, actor, at )
```

---

## 5. Üç ETL Aşaması

### [1] Catalog Crawler — deterministik, AI YOK

Session-aware, rate-limited HTML crawler. Veri kaynağı XML değil; Playwright ile çekilen HTML.

**Günlük akış:**
1. Yeni oturum aç, arama formunu `filterCategories=FundingProgram&sortOrder=dateOfIssue_dt+desc` ile gönder
2. Sayfa 1'den sonuç listesini gez; detay linklerini al
3. Her link için DB'de var mı ve `content_hash` aynı mı kontrol et
4. 3 ardışık sayfada yeni/değişen yoksa dur (incremental mod)
5. Yeni/değişenlerin detay HTML'ini `raw_pages`'e yaz (değiştirilmeden — ND lisansı)
6. İstekler arası min 30 sn bekle
7. Özeti `crawl_runs`'a yaz

**Backfill (tek seferlik):** Erken durdurma olmadan 249 sayfa + ~2.488 detay sayfası.

Detaylı selector haritası: `docs/html-field-map.md`

### [2] Enrichment Worker — hedefli, minimum bot

Sadece eksik alanlar (application_url, contact, deadline). Rate-limit + retry + hash karşılaştırma.

### [3] AI Normalizer — asıl AI değeri

- Etiketleme: raw_text → kapalı taksonomi (funding_type, target_groups, eligible_costs)
- Uygunluk kuralları: eligibility_rules JSON
- Embedding: pgvector

**Önkoşul:** Faz 0 hukuki teyit (moysies & partners) tamamlanmış olmalı.

---

## 6. Başvuru State Machine

```
draft_generating → draft_ready → under_human_review
  │                              ├─► needs_changes ──► draft_generating
  │                              └─► approved ──► ready_to_submit ──► submitted
  └─(AI hata)─► failed                                              ▼
                                                          in_agency_review
                                                          ├─► info_requested ──► under_human_review
                                                          ├─► approved ──► expense_tracking ──► closed
                                                          └─► rejected ──► closed
```

**Kritik kural:** `under_human_review → approved` yalnızca `reviewed_by` (gerçek danışman) set edildiğinde. Guard: `if (!event.actor.isHuman) throw ForbiddenTransition`

---

## 7. Eşleştirme Motoru — hibrit

1. **Hard filter:** eligibility_rules vs company profili → uymayan elenir
2. **Soft rank:** embedding cosine similarity

`score_breakdown` her zaman doldurulur. CC seed eşleşmeleri: KfW, BAFA, Forschungszulage, Bürgschaft, IBB, NRW.BANK.

---

## 8. AI Başvuru Taslağı Üretici

Girdi: onaylanmış match + company + program. Çıktı: yapısal draft JSON.

- Her iddia kaynaktan türetilebilir; uydurma rakam yok
- Eksik veri: `[DANIŞMAN DOLDURACAK: ...]` placeholder
- Çıktı "taslak" damgası taşır

---

## 9. CC Ekosistem Entegrasyonu

`recommendation.type = "cc_upsell"` — program eşleştirmesinden görsel ve verisel olarak ayrı sunulur.

---

## 10. Faz Planı

| Faz | İçerik | Başarı kriteri |
|-----|--------|----------------|
| **0** | Hukuki teyit (moysies & partners) + docs | Yazışma gönderildi; 4 doküman hazır |
| **1** | Backfill Crawler | ~2.488 satır `raw_pages`, geçerli `content_hash` |
| **2** | Günlük Incremental Crawler | 2. gün birkaç dakikada biter; `crawl_runs` kanıtlar |
| **3** | Enrichment + AI Normalizer | `funding_programs` dolu; embedding'ler üretildi |
| **4** | Matcher + State Machine + Draft | profil → eşleşme → taslak → danışman onayı |
| **5** | CC entegrasyonu | ERP profil beslemesi + şeffaf upsell |

**Faz 0 (kod dışı):** foerderdatenbank@moysies.de ile ticari kullanım ve AI-yapılandırma teyidi. Faz 3 öncesi zorunlu. Taslak: `docs/correspondence/moysies-anfrage-de.md`

---

## 11. İlk Komut (Faz 1)

```
Culinary Funding OS — Faz 1 backfill catalog crawler.
Kaynak: foerderdatenbank.de HTML (resmi export/API yok).
Playwright ile arama sonuçlarını sayfa sayfa gez (~249 sayfa).
Detay HTML'ini raw_pages'e yaz. 30 sn crawl-delay. Erken durdurma YOK.
AI/LLM adımı YOK. crawl_runs özeti kaydet.
Spesifikasyon: docs/html-field-map.md
```

---

## 12. Riskler

- **Veri tazeliği:** Sync bozulursa sessizce yanlış bilgi. `last_synced_at` + monitoring şart.
- **Almanca hukuki metin:** AI taslağı = taslak. İmza = insan.
- **KWG/GewO:** Komisyonlu aracılık ayrı lisanslı şirket gerektirir.
- **PII/DSGVO:** `companies.documents` şifreli saklama.
- **BY-ND lisans:** Public-facing AI özeti hukuki teyit olmadan yapılmaz.
- **Selector kırılganlığı:** CMS değişirse crawler kırılır → `crawl_runs.errors` + alarm.
