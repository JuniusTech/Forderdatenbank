# Culinary Funding OS — Architecture & Build Primer

Bu doküman ana brief'tir. Amaç: Almanya'daki teşvik/hibe/kredi programlarını Förderdatenbank'ın **resmi XML ZIP export**'undan çeken, referans linklerini çözerek yapılandıran, firma profilini eşleştiren ve AI ile başvuru taslağı üreten uçtan uca bir sistem kurmak.

**Stack:** Node.js/TypeScript API + Python AI/ETL worker.

**Sınır:** Sistem yazılım + danışmanlık aracıdır; kredi aracılığı / komisyon YAPMAZ (§34c/§34i GewO, KWG). AI asla "uygunsun / bu hibeyi alırsın" demez — "aday program, danışman doğrulaması gerekli" der.

---

## 0. Kesin Gerçekler (varsayım değil, doğrulanmış — 06.07.2026)

| Konu | Değer |
|------|-------|
| Resmi veri seti | Förderdatenbank (BMWE/BMWK) — Bund + 16 Land + AB programları |
| Kapsam (ölçüm) | 2.488 Förderprogramm XML + ~10.352 toplam dosya |
| **Birincil erişim** | `GET /FDB/WS/export` → ZIP, auth yok, full snapshot |
| Format | Tekil `.xml` dosyaları, repository-yol klasör yapısı (`BMWI/FDB/...`) |
| `region` | Dosya yolundan: `Foerderprogramm/Bund/`, `Land/<Land>/`, `EU/` |
| Alanlar | `gsb:title`, `gsb:summary`, `gsb:bodyText`, `gsb:regulatoryFWork`, `gsb:procDescription`, `gsb:keywords`, `gsb:dateOfIssue` |
| Kategoriler / iletişim | Ana dosyada değil — `target:/BMWI/...` linkleriyle ayrı XML'lerde; parser link resolution yapmalı |
| Şema dokümanı | `BMWI/schnittstellenbeschreibung-download-xml.pdf` + `docs/xml-schema-notes.md` |
| Yedek erişim | HTML crawler (Playwright) — Radware CAPTCHA riski, ikincil kaynak |
| robots.txt (HTML) | `Crawl-delay: 30` — yalnızca HTML crawler için geçerli |
| Lisans | **CC BY-ND 4.0 DE** — hukuki teyit gerekir (Faz 0) |
| Yetkili kaynak uyarısı | *"Maßgeblich sind die Angaben auf den offiziellen Webseiten der fördergebenden Stellen"* |
| Güncellik | Full snapshot sync (artımlı API yok); günlük ZIP yeniden indir |

**İlk iş:** XML ingestor — `docs/xml-schema-notes.md` spesifikasyonuna göre 2.488 programı parse et, linkleri çöz, `funding_programs`'a yaz.

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
  Förderdatenbank  ───►  │  [1] XML Ingestor  (scheduled, daily)  │
  ZIP export             │       - download + unzip                 │
                         │       - parse gsb:* fields               │
                         │       - resolve target:/ links           │
                         │       - upsert → funding_programs        │
                         │                                          │
  Web (yedek/ek)   ───►  │  [1b] HTML Crawler (fallback)           │
  Playwright             │       - raw_pages archive                │
                         │                                          │
  Web (eksik alan) ───►  │  [2] Enrichment Worker (targeted)        │
                         │       - only fields XML still lacks        │
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
│   ├── xml-schema-notes.md        # gsb:* alan haritası + link resolution
│   ├── html-field-map.md          # Playwright selector haritası (yedek)
│   ├── legal-boundaries.md        # §1 sınırların gerekçesi
│   ├── data-sources.md            # endpoint, lisans, sync sıklığı
│   └── correspondence/            # moysies yazışma taslakları
├── packages/
│   ├── api/                       # Node.js + TypeScript
│   ├── ai-worker/                 # Python
│   │   ├── ingest/
│   │   │   ├── xml_ingestor.py     # [1] ZIP/XML parse + link resolve
│   │   │   ├── link_resolver.py
│   │   │   ├── catalog_crawler.py  # [1b] HTML yedek
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

### [1] XML Ingestor — birincil, deterministik, AI YOK

Resmi ZIP export. Auth yok, her sync full snapshot.

**Akış:**
1. `GET /FDB/WS/export` → ZIP indir → `BMWI/` altına aç
2. `FDB/Content/DE/Foerderprogramm/**/*.xml` dosyalarını gez
3. Her program: `gsb:*` alanlarını parse et (RichText/CDATA → düz metin)
4. `gsb:cl2Processes`, `gsb:cl2Contacts`, `gsb:cl2CustServices` içindeki `target:/BMWI/...` linklerini çöz
5. `region` = dosya yolu (`Bund/`, `Land/<Name>/`, `EU/`)
6. `source_id` = `document@name` ile idempotent upsert → `funding_programs`
7. Attribution + "Maßgeblich sind..." her kayda yaz

Detaylı şema: `docs/xml-schema-notes.md`

### [1b] HTML Crawler — yedek (mevcut, Faz 1a tamamlandı)

Playwright ile ham HTML arşivi (`raw_pages`). Radware CAPTCHA riski. XML'de olmayan alanlar için enrichment desteği.

Detaylı selector haritası: `docs/html-field-map.md`

### [2] Enrichment Worker — hedefli, minimum bot

Sadece XML + link resolution sonrası hâlâ eksik alanlar (nadir deadline, dinamik form URL'leri).

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
| **0** | Hukuki teyit (moysies & partners) + docs | Yazışma gönderildi; şema dokümanları hazır |
| **1a** | HTML Crawler (yedek) | ✅ Smoke + pagination; `raw_pages` arşivi |
| **1b** | **XML Ingestor** | ~2.488 satır `funding_programs`, linkler çözülmüş |
| **2** | Günlük XML sync (+ opsiyonel HTML incremental) | Günlük job çalışıyor; program sayısı stabil |
| **3** | AI Normalizer + embedding | `eligibility_rules` + pgvector dolu |
| **4** | Matcher + State Machine + Draft | profil → eşleşme → taslak → danışman onayı |
| **5** | CC entegrasyonu | ERP profil beslemesi + şeffaf upsell |

**Faz 0 (kod dışı):** foerderdatenbank@moysies.de ile ticari kullanım ve AI-yapılandırma teyidi. Faz 3 öncesi zorunlu. Taslak: `docs/correspondence/moysies-anfrage-de.md`

---

## 11. İlk Komut (Faz 1b — XML Ingestor)

```
Culinary Funding OS — Faz 1b XML ingestor.
Kaynak: foerderdatenbank.de ZIP export (GET /FDB/WS/export).
Lokal snapshot: BMWI/ klasörü (2.488 program XML).
Parse gsb:* alanları, target:/ linklerini çöz (kategori, kontakt, externer link).
region dosya yolundan. source_id = document@name.
Upsert → funding_programs. AI/LLM adımı YOK.
Spesifikasyon: docs/xml-schema-notes.md
```

HTML crawler yedek olarak kalır:
```
python -m ingest.catalog_crawler --mode fixture  # offline test
```

---

## 12. Riskler

- **Veri tazeliği:** Sync bozulursa sessizce yanlış bilgi. `last_synced_at` + monitoring şart.
- **Almanca hukuki metin:** AI taslağı = taslak. İmza = insan.
- **KWG/GewO:** Komisyonlu aracılık ayrı lisanslı şirket gerektirir.
- **PII/DSGVO:** `companies.documents` şifreli saklama.
- **BY-ND lisans:** Public-facing AI özeti hukuki teyit olmadan yapılmaz.
- **Selector kırılganlığı:** CMS değişirse crawler kırılır → `crawl_runs.errors` + alarm.
