# Playwright Crawler — Veri Çıkarım Spesifikasyonu

Culinary Funding OS, Faz 1-2. Son doğrulama: 05.07.2026 (canlı DOM sorgusu).

Bu belge crawler implementasyonunun tek doğruluk kaynağıdır.

---

## 1. Oturum ve Sayfa Dolaşımı

Site klasik form tabanlı devlet CMS'i (Government Site Builder benzeri), SPA değil. Tüm veri ilk HTML yanıtında hazır — JS render beklenmez.

### Başlangıç URL

```
https://www.foerderdatenbank.de/SiteGlobals/FDB/Forms/Suche/Startseitensuche_Formular.html?submit=Suchen&filterCategories=FundingProgram&sortOrder=dateOfIssue_dt+desc
```

`resourceId`/`input_` token'ı olmadan da sonuçlar gelir (2.488 Beiträge doğrulandı).

### Sayfalama kuralı

1. Her gün taze oturumla başla (yeni BrowserContext)
2. "weiter" veya sayfa numarası linklerinin `href`'ini oku
3. `urljoin(current_url, href)` ile bir sonraki sayfaya git
4. **Asla** manuel URL/token üretme
5. Link'e tıklama yerine `href` çıkar + `page.goto()` — daha stabil

### Oturum yönetimi

- Aynı `BrowserContext` gün boyunca tek tarama koşusunda korunur
- Her günün başında yeni context — eski token saklanmaz

---

## 2. Liste Sayfası (Arama Sonuçları)

### Sağlık kontrolü

| Selector | İçerik | Kullanım |
|----------|--------|----------|
| `div.search--hits` | `"2.488 Beiträge"` | Toplam kayıt sayısı; önceki günle karşılaştır |

### Program kartları

| Selector | Alan | Not |
|----------|------|-----|
| `div.card.card--horizontal.card--fundingprogram` | Kart container | `page.locator(...).all()` |
| `.card--title a[href*="Foerderprogramm"]` | Detay linki | href göreli path |
| `dl.document-info-fundingprogram dt:nth-child(1)` | "Wer wird gefördert?:" | |
| `dl.document-info-fundingprogram dd:nth-child(2)` | Hedef grup değeri | |
| `dl.document-info-fundingprogram dt:nth-child(3)` | "Was wird gefördert?:" | |
| `dl.document-info-fundingprogram dd:nth-child(4)` | Fonlanan alan değeri | |

### Sayfalama

| Selector | Kullanım |
|----------|----------|
| `a:has-text("weiter")` | Sonraki sayfa var mı kontrolü |
| Sayfa numarası linkleri (`"2"`, `"3"`...) | href'te `gtp` parametresi |

---

## 3. Detay Sayfası

### Meta bilgiler

| Selector | Alan |
|----------|------|
| `h1.title` | Program başlığı |
| `dl.document-info-fundingprogram` | 5 satırlık meta blok |

**dl satır sırası (detay sayfası):**

| Sıra | dt etiketi | dd içeriği |
|------|------------|------------|
| 1 | Förderart | Kredi/Hibe türü |
| 2 | Förderbereich | Fon alanı |
| 3 | Fördergebiet | Bölge (Bund/Land/EU) |
| 4 | Förderberechtigte | Uygun grup |
| 5 | Ansprechpunkt | İletişim kartı |

### Ansprechpunkt (iletişim) alt blokları

| Selector | Alan |
|----------|------|
| `dd.card .card--title` | Kurum adı (link olabilir) |
| `dd.card .address p.adr` | Adres satırı 1 |
| `dd.card .address p.locality` | PLZ + şehir |
| `dd.card .person-contact` | Telefon/faks düz metin |
| `dd.card a[href^="mailto:"]` | E-posta |
| `dd.card a[href^="http"]` | Web sitesi |

### İçerik sekmeleri (tab tıklamaya gerek yok)

Tüm tab'lar DOM'da mevcut — CSS/JS ile gizlenir. `page.content()` tek seferde hepsini verir.

| Selector | İçerik | AI işleme |
|----------|--------|-----------|
| `#tab1` | Kurztext + Volltext | Kısa/uzun açıklama |
| `#tab2` | Rechtliche Voraussetzungen | Uygunluk şartları (`<ul><li>`) |
| `#tab3` | Richtlinie | Tam hukuki metin — Normalizer'ın ana girdisi |

---

## 4. content_hash Hesaplama

Tüm sayfa HTML'i hashlenmez (CSRF token, tarih damgası gürültüsü).

**Hashlenecek bloklar (sırayla birleştir, SHA-256):**

1. `dl.document-info-fundingprogram` — inner text
2. `#tab1` — inner text
3. `#tab2` — inner text
4. `#tab3` — inner text

```python
import hashlib

def compute_content_hash(doc_info: str, tab1: str, tab2: str, tab3: str) -> str:
    combined = "\n".join([doc_info, tab1, tab2, tab3])
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
```

Hash aynı → içerik değişmemiş → detay sayfası yeniden çekilmez (incremental mod).

---

## 5. Rate Limiting

| Kural | Değer |
|-------|-------|
| Minimum istek aralığı | 30 saniye |
| Kaynak | robots.txt `Crawl-delay: 30` |
| Uygulama | Her `page.goto()` sonrası `asyncio.sleep(30)` |

---

## 6. Hata Yönetimi

### Selector bulunamadı

```python
# YANLIŞ — sessizce devam etme
if not element:
    continue

# DOĞRU — crawl_runs.errors'a yaz
if not element:
    errors.append({"url": url, "selector": selector, "type": "selector_not_found"})
```

### Kırılganlık uyarısı

Class isimleri (`card--fundingprogram`, `document-info-fundingprogram`, `content--tab-text`, `tab1/tab2/tab3`) 05.07.2026'da doğrulandı ancak resmi sözleşmeye dayanmıyor. CMS değişirse selector'lar kırılabilir.

**Zorunlu:** Her günlük koşuda selector health check → hata varsa alarm.

---

## 7. Crawler Modları

### backfill (Faz 1)
- Erken durdurma: **kapalı**
- Hedef: tüm ~2.488 kayıt
- CLI: `python -m ingest.catalog_crawler --mode backfill`

### incremental (Faz 2)
- Erken durdurma: 3 ardışık sayfada yeni/değişen yok → dur
- content_hash karşılaştırması
- Cron: 03:00 CET
- CLI: `python -m ingest.catalog_crawler --mode incremental`

---

## 8. Python Modül Haritası

| Modül | Sorumluluk |
|-------|------------|
| `selectors.py` | Bu belgedeki CSS sabitleri |
| `hash_utils.py` | content_hash hesaplama |
| `session.py` | Playwright BrowserContext yönetimi |
| `list_parser.py` | Arama sonuçları parse |
| `pagination.py` | href takibi, urljoin |
| `detail_fetcher.py` | Detay sayfası çek + selector check |
| `rate_limiter.py` | 30 sn bekleme |
| `catalog_crawler.py` | Orchestrator |
| `crawl_logger.py` | crawl_runs özeti |
