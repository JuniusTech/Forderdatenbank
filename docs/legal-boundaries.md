# Legal Boundaries — Culinary Funding OS

Bu belge ReadMe §1'deki sistem sınırlarının gerekçesini ve kod karşılıklarını tanımlar. Bu sınırlar **negotiable değildir** — mimarinin çekirdeğine gömülür.

Son güncelleme: 05.07.2026

---

## 1. Kredi Aracılığı Yapılmaz

### Kural
Sistem kredi, leasing ve kefalet programlarına **yönlendirir** ancak:
- Komisyon almaz
- Finansal sözleşme yapmaz
- Kredi kararı vermez veya garanti etmez

### Hukuki dayanak
- **§34c GewO** — Finanzdienstleistungen (kredi aracılığı lisansı)
- **§34i GewO** — Immobiliardarlehensvermittlung
- **KWG (Kreditwesengesetz)** — Bankenlizenz gereksinimleri

### Kod karşılığı
- MVP kapsamında komisyonlu aracılık modülü **yok**
- `recommendation.type` yalnızca bilgilendirme amaçlı program eşleştirmesi veya CC upsell içerir
- Gelecekte komisyonlu aracılık eklenirse: ayrı lisanslı tüzel kişilik + hukuk görüşü zorunlu

---

## 2. AI Garanti Vermez

### Kural
AI asla şunları söylemez:
- "Bu programa uygunsunuz"
- "Bu hibeyi alırsınız"
- "Başvurunuz onaylanır"

AI şunu söyler:
- "Bu program aday olabilir — danışman doğrulaması gerekli"

### Kod karşılığı

```typescript
interface Match {
  score: number;                    // 0-100, bilgilendirme amaçlı
  human_review_required: true;      // default, override edilemez
  disclaimer: "Nihai karar ilgili kuruma aittir.";
  score_breakdown: object;          // açıklanabilirlik zorunlu
}
```

- UI'da sabit disclaimer metni her eşleştirme ekranında görünür
- Confidence skoru "uygunluk garantisi" olarak sunulmaz

---

## 3. İnsan-in-the-Loop Zorunlu

### Kural
AI üretimi başvuru taslağı, danışman onayı olmadan "gönderime hazır" statüsüne geçemez.

### Kod karşılığı — State Machine Guard

```typescript
// under_human_review → approved geçişi
if (!event.actor.isHuman || !application.reviewed_by) {
  throw new ForbiddenTransition();
}
```

- AI `approved`, `ready_to_submit`, `submitted` geçişlerini **yapamaz**
- `reviewed_by` gerçek danışman kimliği (auth sisteminden) olmalıdır
- `pipeline_events` tablosu tüm geçişleri denetlenebilir şekilde kaydeder

---

## 4. Çıkar Çatışması Şeffaflığı

### Kural
Culinary Collective (CC) ekosistem hizmetleri (ERP, webshop, marka aktivasyonu vb.) program eşleştirmesinden **görsel ve verisel olarak ayrı** sunulur.

### Kod karşılığı

```typescript
type RecommendationType = "funding_match" | "cc_upsell";

interface Recommendation {
  type: RecommendationType;
  // cc_upsell: ayrı UI bölümü, farklı renk/etiket
  // funding_match: tarafsız eşleştirme sonucu
}
```

- Firma, danışmanın aynı zamanda CC hizmet satıcısı olduğunu görür
- Upsell önerileri başvuru onayı sonrası tetiklenir, eşleştirme skoruna karışmaz

---

## 5. Veri Tazeliği Görünür

### Kural
Her program kaydında veri yaşı görünür olmalıdır. Tarihi geçmiş programlar eşleştirmede kullanılmaz.

### Kod karşılığı
- `last_synced_at`: son crawler/normalizer çalışması
- `source_valid_until`: programın geçerlilik tarihi (varsa)
- `status`: `active | expired | closed`
- UI uyarısı: "Veri N gün eski" (sync bozulduğunda)
- Eşleştirme sorgusu: `WHERE status = 'active'`

---

## 6. Förderdatenbank Lisansı — CC BY-ND 4.0 DE

### Kural
Förderdatenbank içeriği **Creative Commons BY-ND 4.0 DE** (Namensnennung – Keine Bearbeitung) lisansı altındadır.

| İzin verilen | İzin verilmeyen (teyit gerekli) |
|--------------|--------------------------------|
| Kaynak göstererek olduğu gibi saklama | Metni değiştirip public-facing olarak sunma |
| Ham HTML'i DB'de saklama (ND uyumlu) | AI-üretimi "özet" metni kullanıcıya doğrudan gösterme |
| Yapılandırılmış metadata çıkarma (iç kullanım) | Lisans metnini atlamadan yeniden yayınlama |

### Kod karşılığı
- `raw_pages.raw_html`: değiştirilmeden saklanır
- `license_attribution`: her `funding_programs` kaydında zorunlu
- Public-facing metin: yalnızca fon kurumunun resmi sitesinden veya danışman onaylı taslaktan

### Zorunlu attribution metni (taslak)

```
Quelle: Förderdatenbank des Bundes und der Länder
(https://www.foerderdatenbank.de)
Lizenz: CC BY-ND 4.0 DE
Maßgeblich sind die Angaben auf den offiziellen Webseiten der fördergebenden Stellen.
```

### Açık soru (Faz 0 — moysies teyidi)
AI Normalizer'ın serbest metinden **yapılandırılmış etiket** (funding_type, target_groups) çıkarması BY-ND kapsamında mı? Yazılı teyit alınmadan Faz 3 canlıya alınmaz.

---

## 7. DSGVO / PII

### Kural
Firma finansal belgeleri ve kişisel veriler hassas veridir.

### Kod karşılığı
- `companies.documents`: şifreli saklama (at-rest encryption)
- Erişim logu: kim, ne zaman, hangi belgeye erişti
- Silme hakkı (Art. 17 DSGVO): firma profili silme endpoint'i
- Veri minimizasyonu: yalnızca eşleştirme için gerekli alanlar toplanır

---

## 8. Referanslar

| Konu | Kaynak |
|------|--------|
| Förderdatenbank Impressum | https://www.foerderdatenbank.de/FDB/Content/DE/Service/Impressum/impressum.html |
| CC BY-ND 4.0 DE | https://creativecommons.org/licenses/by-nd/4.0/deed.de |
| GewO §34c/§34i | https://www.gesetze-im-internet.de/gewo/ |
| KWG | https://www.gesetze-im-internet.de/kwg/ |
| DSGVO | https://dsgvo-gesetz.de/ |
