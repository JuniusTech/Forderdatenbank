# Data Sources — Förderdatenbank

Son doğrulama: 06.07.2026

---

## 1. Resmi Veri Seti

| Alan | Değer |
|------|-------|
| Ad | Förderdatenbank des Bundes und der Länder |
| Operatör | moysies & partners GmbH (Redaktion) |
| Kapsam | Bund + 16 Bundesland + EU programları |
| Kayıt sayısı | 2.488 Förderprogramm (05.07.2026 ölçümü) |
| Ana URL | https://www.foerderdatenbank.de |

---

## 2. Erişim Yöntemi

### Birincil: Resmi XML ZIP Export — MEVCUT ✅

| Alan | Değer |
|------|-------|
| Endpoint | `GET https://www.foerderdatenbank.de/FDB/WS/export` |
| Auth | Yok |
| Filtre | Yok — her çağrı **full snapshot** |
| Format | ZIP → repository-yol tabanlı tekil `.xml` dosyaları |
| Program sayısı | 2.488 (`FDB/Content/DE/Foerderprogramm/**/*.xml`) |
| Toplam dosya | ~10.352 XML |
| Şema PDF | `BMWI/schnittstellenbeschreibung-download-xml.pdf` (lokal) |
| Detaylı şema notları | `docs/xml-schema-notes.md` |

**Not:** Tarayıcıdan doğrudan URL açılınca ana sayfaya yönlendirme olabilir; ZIP indirme tarayıcı veya `curl -L` ile çalışıyor. Lokal snapshot: `BMWI/` (gitignore'da).

**Önemli:** İletişim, kategoriler (Förderart, Foerdergebiet vb.) ve dış linkler ana program dosyasında değil — `target:/BMWI/...` referanslarıyla ayrı XML dosyalarına bağlı. Parser **link resolution** adımı içermeli.

### Yedek: Session-aware HTML Crawler

**Arama başlangıç URL'si:**
```
https://www.foerderdatenbank.de/SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html?submit=Suchen&filterCategories=FundingProgram&sortOrder=dateOfIssue_dt+desc
```

**Detay sayfası URL deseni:**
```
/FDB/Content/DE/Foerderprogramm/{Bund|Land/<Land>|EU}/{slug}.html
```

**Sayfalama:** Oturum tabanlı token'lar (`resourceId`, `input_*`, `gtp`). Sonraki sayfa linkinin `href`'i takip edilir — manuel URL üretilmez.

---

## 3. robots.txt Uyumu

Kaynak: `https://www.foerderdatenbank.de/robots.txt`

| Kural | Değer |
|-------|-------|
| Disallow | `/FDB/SiteGlobals/` (SiteGlobals formları farklı path'te — izinli) |
| Crawl-delay | **30 saniye** |
| Arama sonuçları yolu | `/SiteGlobals/FDB/Forms/Suche/...` — izinli |

**Zorunlu uygulama:** Her HTTP isteği arasında minimum 30 saniye bekleme.

---

## 4. Lisans

### CC BY-ND 4.0 DE (Namensnennung – Keine Bearbeitung)

Doğrulama: Förderdatenbank Impressum sayfası.

| İzin | Kısıtlama |
|------|-----------|
| Kaynak göstererek paylaşma | Metni değiştirme (Bearbeitung) |
| Ticari kullanım (Namensnennung ile) | ND: türev eser oluşturma yasak |
| Olduğu gibi arşivleme | Public-facing düzenlenmiş/özetlenmiş metin sunma |

### Zorunlu attribution (her kayıt)

```
Quelle: Förderdatenbank des Bundes und der Länder
(https://www.foerderdatenbank.de)
Lizenz: CC BY-ND 4.0 DE
```

### Yetkili kaynak uyarısı (her kayıt + UI)

```
Maßgeblich sind die Angaben auf den offiziellen Webseiten der fördergebenden Stellen.
```

Bu veritabanı **ikincil kaynaktır**. Asıl referans fon kurumunun kendi web sitesidir.

---

## 5. Sync Stratejisi

### Birincil: XML full snapshot (Faz 1b)
- `GET /FDB/WS/export` → ZIP indir → aç → parse
- Her sync tam veri seti (artımlı API yok)
- `source_id` (document `@name`) ile idempotent upsert → `funding_programs`
- Tahmini süre: indirme + parse dakikalar (HTML crawler'ın ~21 saatine karşı)

### Yedek: HTML crawler (Faz 1a — tamamlandı, artık ikincil)
- Radware CAPTCHA riski; yalnızca XML'de eksik kalan alanlar için enrichment
- `raw_pages` tablosu ham HTML arşivi olarak kalır

### Günlük incremental (Faz 2 — HTML, opsiyonel)
- Cron: gece 03:00 CET
- XML sync ile birlikte veya yerine: günlük ZIP yeniden indir + diff
- HTML incremental: tarihe göre azalan liste, `content_hash` karşılaştırması

### Değişiklik tespiti
- **XML:** `source_id` + içerik hash (raw_text birleşimi) veya tam snapshot replace
- **HTML:** `content_hash` — `dl` + `#tab1/2/3` (SHA-256)
- Sağlık kontrolü: program sayısı ~2.488 ±%5

---

## 6. Veritabanı Tabloları

### raw_pages
Ham HTML saklama — ND lisansı gereği değiştirilmeden.

| Kolon | Tip | Açıklama |
|-------|-----|----------|
| url | text PK | Detay sayfası tam URL |
| raw_html | text | Ham HTML (değiştirilmemiş) |
| content_hash | text | Anlamlı blok hash (SHA-256) |
| first_seen_at | timestamptz | İlk keşif |
| last_synced_at | timestamptz | Son sync |
| source_valid_until | date | Opsiyonel geçerlilik |

### crawl_runs
Her crawler çalışmasının özeti — sessiz bozulma tespiti için kritik.

| Kolon | Tip | Açıklama |
|-------|-----|----------|
| run_id | uuid PK | |
| started_at | timestamptz | |
| finished_at | timestamptz | |
| pages_checked | int | |
| new_count | int | |
| changed_count | int | |
| stopped_early_at_page | int | null = tam tarama |
| errors | jsonb | Selector hataları, timeout vb. |

---

## 7. İletişim (Hukuki Teyit)

| Rol | İletişim |
|-----|----------|
| Redaktion / Betreiber | moysies & partners GmbH |
| E-posta | foerderdatenbank@moysies.de |

Yazışma taslağı: `docs/correspondence/moysies-anfrage-de.md`

---

## 9. Bot-Schutz (Radware) — Stand 05.07.2026 Abend

Automatisierter Zugriff (Playwright headless, requests, curl) kann mit **Radware CAPTCHA** blockiert werden.
Symptom: Seitentitel „Radware Captcha Page“, HTML < 2 KB, keine `.card--fundingprogram`-Elemente.

### Erkennung im Code
- `ingest/captcha_detect.py` — prüft HTML auf Block-Marker
- `crawl_runs.errors` — `{ "type": "bot_blocked", ... }`
- Exit code **2** bei Bot-Block

### Workarounds (Priorität)
1. `--no-headless` — sichtbarer Browser, manuelles CAPTCHA-Lösen
2. Cookie-Export aus manuellem Browser in Playwright-Context laden (TODO: Faz 1.1)
3. Offiziellen API-Zugang via moysies anfragen (Faz 0 Schreiben)
4. Backfill von erlaubter IP / Büronetzwerk ausführen

### Offline-Tests (ohne Netzwerk)
```bash
cd packages/ai-worker
source .venv/bin/activate
pytest tests/ -q
python -m ingest.catalog_crawler --mode fixture
```

---

## 10. Monitoring Gereksinimleri

- `crawl_runs.errors` boş değilse → alarm
- `last_synced_at` > 48 saat eskiyse → uyarı
- Toplam kayıt sayısı ±%5 saparsa → uyarı
- Beklenen selector bulunamazsa → hata (sessizce yutma yasak)
