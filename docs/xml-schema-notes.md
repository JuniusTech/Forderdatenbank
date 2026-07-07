# XML Export — Şema Notları (gerçek veri, 06.07.2026)

Kaynak: `BMWI/` klasörü — `GET https://www.foerderdatenbank.de/FDB/WS/export` ZIP çıktısı.  
Şema PDF: `BMWI/schnittstellenbeschreibung-download-xml.pdf`

## Özet sayılar

| Metrik | Değer |
|--------|-------|
| Förderprogramm XML | **2.488** |
| Toplam XML dosyası | **10.352** |
| Program tipi | `gsb:ServiceOffer` / `ServiceOffer-FundingProgram` |

---

## Export formatı

- **ZIP** içinde repository-yol tabanlı klasör ağacı (tek düz XML değil)
- **Auth yok**, filtre yok — her sync **full snapshot**
- Kök prefix: `/BMWI/` (ZIP içinde `BMWI/` klasörü)

### Program dosya yolu → `region`

```
FDB/Content/DE/Foerderprogramm/Bund/BMU/palu-modul4-....xml     → Bund
FDB/Content/DE/Foerderprogramm/Land/Thueringen/....xml        → Thueringen
FDB/Content/DE/Foerderprogramm/EU/....xml                      → EU
FDB/Content/DE/Foerderprogramm/zusammenarbeit-....xml         → (kök — kontrol et)
```

`region` alanını dosya yolundan bedava al: `Land/<Name>/` veya `Bund/` veya `EU/`.

---

## Program dosyası (`gsb:ServiceOffer`)

Örnek: `FDB/Content/DE/Foerderprogramm/Bund/BMU/palu-modul4-massnahmen-wiedervernaessung.xml`

### Doğrudan alanlar (`<property name="gsb:...">`)

| XML property | Tip | DB alanı | Not |
|--------------|-----|----------|-----|
| `gsb:title` | RichText | `title` | HTML içinde `<p>`, strip et |
| `gsb:teaserText` | RichText | — | Kısa özet |
| `gsb:summary` | RichText | `raw_text` (birleşim) | Uzun özet |
| `gsb:bodyText` | RichText | `raw_text` (birleşim) | Tam metin + yasal dayanak |
| `gsb:regulatoryFWork` | RichText | `raw_text` + `eligibility_rules` | Uygunluk şartları ("Antragsberechtigt...") |
| `gsb:procDescription` | RichText | — | Süreç açıklaması |
| `gsb:procMethod` | RichText | — | Başvuru adımları |
| `gsb:procInfluence` | RichText | — | Başvuru dönemi / etki |
| `gsb:competenceDescr` | RichText | — | Gerekli belgeler |
| `gsb:keywords` | String | `eligible_costs` (seed) | Virgülle ayrılmış |
| `gsb:dateOfIssue` | Date | `last_synced_at` / yayın tarihi | ISO 8601 |
| `gsb:subType` | String | — | `ServiceOffer-FundingProgram` |

### Link ile çözülen alanlar (`gsb:cl2*`)

Ana dosyada değer yok — `xlink:href="target:/BMWI/..."` referansları var.

#### `gsb:cl2Processes` — sınıflandırmalar

| Classifier | Örnek link | DB alanı |
|------------|-----------|----------|
| Foerderart | `SiteGlobals/Categories/FDB/Foerderart/zuschuss` | `funding_type[]` |
| Foerdergebiet | `.../Foerdergebiet/_bundesweit` | `region` |
| Foerdergeber | `.../Foerdergeber/bund` | kategori |
| Foerderberechtigte | `.../unternehmen`, `kmu`... | `target_groups[]` |
| Foerderbereich | `.../umwelt_naturschutz` | `eligible_costs[]` |
| Foerderorganisation | `FDB/Content/DE/Foerdergeber/B/bmukn-...` | `provider_id` |
| Unternehmensgroesse | `.../kleines_unternehmen` | eligibility |

#### `gsb:cl2Contacts` — iletişim

```
target:/BMWI/FDB/Content/DE/Kontakt/R/rentenbank-landwirtschaftliche
  → gsb:ContactData
    → gsb:email, gsb:phone, gsb:fax
    → gsb:cl2Addresses → Adresse/*.xml (gsb:road, gsb:city, gsb:zipCode)
    → gsb:website → ExternerLink/*.xml (gsb:url)
```

#### `gsb:cl2CustServices` — dış linkler

```
target:/BMWI/FDB/Content/DE/ExternerLink/P/palu-infoseite
  → gsb:ExternalLink
    → gsb:url  (ör: https://www.rentenbank.de/kontakt/)
```

→ `application_url` ve ek kaynak linkleri

---

## Referans dosya tipleri

| type | Örnek path | Çıkarılan |
|------|------------|-----------|
| `gsb:DocumentCategory` | `SiteGlobals/Categories/FDB/Foerderart/zuschuss.xml` | Kategori adı (`gsb:title`) |
| `gsb:ContactData` | `FDB/Content/DE/Kontakt/R/rentenbank-....xml` | email, phone, fax |
| `gsb:Address` | `FDB/Content/DE/Adresse/L/landwirtschaftliche-rentenbank-lr.xml` | adres |
| `gsb:ExternalLink` | `FDB/Content/DE/ExternerLink/R/rentenbank-de-kontakt.xml` | `gsb:url` |
| `gsb:ConfigResLabel` | `_config/ResourceBundleEntries/Labels/FDB/zuschuss.xml` | DE etiket: "Zuschuss" |

### Kategori etiket çözümleme

Kategori XML'de `gsb:title` = `zuschuss` (slug). İnsan okunur etiket için:
- `_config/ResourceBundleEntries/Labels/FDB/{slug}.xml` → `gsb:value` tablosunda `de` = **Zuschuss**

---

## RichText / CDATA formatı

Metin alanları HTML escape + CDATA içinde:

```xml
<property name="gsb:title" type="RichText">
  <text>&lt;![CDATA[&lt;div&gt;&lt;p&gt;Programm Titel&lt;/p&gt;&lt;/div&gt;]]&gt;</text>
</property>
```

Parser adımları:
1. `text` node'unu al
2. HTML entity decode (`&lt;` → `<`)
3. CDATA wrapper'ı çıkar
4. HTML parse → düz metin (BeautifulSoup `get_text`)

---

## target: link çözümleme

```
xlink:href="target:/BMWI/SiteGlobals/Categories/FDB/Foerderart/zuschuss"
```

→ ZIP kökünde: `BMWI/SiteGlobals/Categories/FDB/Foerderart/zuschuss.xml`

Algoritma:
```python
def target_to_path(href: str) -> Path:
    # "target:/BMWI/..." → "BMWI/....xml"
    rel = href.removeprefix("target:/")
    return export_root / f"{rel}.xml"
```

Cache: tüm XML'leri `dict[path, parsed_doc]` olarak önceden indexle (10k dosya).

---

## `source_id` (idempotent upsert)

```python
source_id = document.get("name")  # örn: "palu-modul4-massnahmen-wiedervernaessung"
# veya tam path:
source_id = document.get("path") + "/" + document.get("name")
```

---

## Önerilen PostgreSQL DDL (funding_programs)

```sql
-- xml ingest sonrası (Faz 1b)
funding_programs (
  id uuid pk,
  source_id text unique not null,       -- document@name veya path+name
  source_path text not null,            -- /BMWI/FDB/Content/DE/Foerderprogramm/Bund/BMU/...
  title text not null,
  funding_type text[],
  provider_id uuid fk,
  region text,                          -- dosya yolundan + Foerdergebiet kategori
  target_groups text[],
  eligible_costs text[],
  application_url text,                 -- ExternerLink çözümlemesi
  contact jsonb,                        -- Kontakt zinciri
  raw_text text,                        -- summary + bodyText + regulatoryFWork birleşimi
  eligibility_rules jsonb,              -- Faz 3 AI normalizer
  embedding vector(1536),
  status text default 'active',
  date_of_issue timestamptz,
  last_synced_at timestamptz,
  license_attribution text
)
```

---

## Ingest pipeline (yeni Faz 1b)

```
[1a] ZIP indir     GET /FDB/WS/export → unzip → BMWI/
[1b] XML Parser    2488 program XML → link resolve → funding_programs upsert
[1c] (opsiyonel)   HTML crawler yalnızca ZIP'te olmayan alanlar için
[2]  AI Normalizer (Faz 3)
```

HTML crawler artık **birincil kaynak değil** — yedek/enrichment.

---

## Doğrulanmış örnek dosyalar

| Dosya | İçerik |
|-------|--------|
| `.../palu-modul4-massnahmen-wiedervernaessung.xml` | Tam program — tüm gsb:* alanları |
| `SiteGlobals/Categories/FDB/Foerderart/zuschuss.xml` | Kategori referansı |
| `FDB/Content/DE/Kontakt/R/rentenbank-landwirtschaftliche.xml` | İletişim zinciri |
| `FDB/Content/DE/ExternerLink/R/rentenbank-de-kontakt.xml` | Dış URL |
| `_config/.../Labels/FDB/zuschuss.xml` | DE etiket: "Zuschuss" |
