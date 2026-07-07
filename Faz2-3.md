# Culinary Funding OS — MVP Uçtan Uca Görev Listesi (Faz 2–3 demo)

> **Hedef:** CC sahibine/yatırımcıya gösterilecek çalışan demo.
> Zincir: firma profili → kural+keyword eşleştirme → neden-skoru → AI başvuru taslağı → basit arayüz.
> **Sıralama ilkesi: ÖNCE ÇALIŞIR (keyword), SONRA AKILLI (semantik).** Semantik katman opsiyonel/son adım.
> Faz 1b bitti: `funding_programs` tablosunda 2.488 kayıt var, kullan.
>
> **DEMO SINIRI (koda gömülecek, tartışılmaz):** Sistem "uygunsunuz" / "hibeyi alırsınız" DEMEZ.
> Her sonuç "profilinize uyabilecek program — danışman teyidi gerekli" dilinde. Her `match` ve her
> `draft` bir `disclaimer` taşır: "Nihai karar ilgili kuruma aittir." Bu, hukuki teyit gelmeden
> demoyu güvenli tutar ve sonradan sistemi yeniden yazmayı önler.

---

## Faz A — Firma profili (temel)

**A1. `companies` tablosu migration'ı** (`infra/migrations/003_companies.sql`)
Alanlar: `id`, `cc_erp_id` (nullable), `name`, `legal_form`, `founded_year`, `region` (Land — eşleştirmede kritik),
`employees`, `annual_revenue`, `sector`, `digital_maturity` jsonb, `investment_need` jsonb
(ne için para lazım: dijitalleşme/ekipman/enerji/şube), `growth_plan` jsonb, `bank_relation`, `created_at`.

**A2. Profil giriş yolu — iki mod:**
- Manuel: basit form / JSON (demoda kullanıcı canlı girebilsin).
- Seed: 1 gerçek (veya temsili) CC üyesi restoran profilini `seeds/demo_company.json`'a koy.
  Demo bu profili tek tıkla yükleyebilmeli. (Gerçek profil verisi kullanıcıdan gelecek; yoksa
  temsili Berlin restoranı: 8 çalışan, ~600k€ ciro, POS/webshop eksik, dijitalleşme + ekipman ihtiyacı.)

---

## Faz B — Kural tabanlı filtre (hard filter, AI YOK)

**B1. `ai/matcher/rules.py` — deterministik eleme.**
Firma profili vs `funding_programs`. Elemede kullanılacak sinyaller:
- **region:** program `region` = firma Land'i VEYA `bundesweit`/`Bund`/`EU` → geçer, aksi elenir.
- **target_groups:** program KMU/Unternehmen/Gründung içeriyor mu (restoran = KMU).
- **eligible_costs / keywords:** firma `investment_need` (dijitalleşme, ekipman, enerji, şube)
  program metniyle örtüşüyor mu (ilk turda basit anahtar kelime eşleşmesi yeterli).
- **status = 'active'** olmayanları at.

Çıktı: elenmemiş program havuzu (tipik 40–80 program). Bu havuz semantik/skor adımına girer.
**Not:** hard filter yanlış-pozitifi baştan keser; skor sadece kalanları sıralar.

---

## Faz C — Keyword skoru + neden-skoru (DEMO'NUN KALBİ)

**C1. `ai/matcher/keyword_score.py`.**
Havuzdaki her program için 0–100 skor. Basit ama açıklanabilir:
- firma ihtiyaç terimleri (Digitalisierung, POS, Kasse, Energieeffizienz, Investition, Filiale...)
  program `raw_text`/`keywords` içinde kaç kez / hangi ağırlıkta geçiyor.
- funding_type uyumu (firma "hibe istiyorum" derse Zuschuss'a bonus).
- region tam eşleşme (Land) > bundesweit bonusu.

**C2. `score_breakdown` — HER match'te zorunlu.**
Skorun NEDEN o olduğu jsonb olarak: hangi terim eşleşti, region durumu, funding_type uyumu.
Demo ekranında "bu program neden size uygun?" bunu gösterecek — yatırımcıya en çok bunu satacaksın.

**C3. `matches` tablosu** (`infra/migrations/004_matches.sql`):
`id`, `company_id`, `program_id`, `score`, `score_breakdown` jsonb, `matched_terms` text[],
`estimated_amount_range` (programdan çekilen tutar), `human_review_required bool DEFAULT true`,
`disclaimer text DEFAULT 'Nihai karar ilgili kuruma aittir.'`, `created_at`.

**C4. Match endpoint (Node API):** `POST /companies/{id}/match` → filtre + skor çalıştır,
top N (ör. 5–8) match'i `score_breakdown` ile döndür.

---

## Faz D — AI başvuru taslağı üretici (EN ÇOK "VAY" ETKİSİ)

**D1. `ai/draft/generator.py`.**
Girdi: seçilmiş bir `match` + `company` + `program` detayı.
Çıktı: yapısal `draft` jsonb — proje açıklaması, yatırım planı, bütçe tablosu,
dijitalleşme/verimlilik etkisi, gerekçe, ve **Almanca** başvuru metni taslağı.

Kurallar (koda gömülü):
- Her iddia firma profilinden veya program şartından türetilebilir olmalı. Uydurma rakam YOK.
- Eksik veri → `[DANIŞMAN DOLDURACAK: ...]` placeholder.
- Çıktı "TASLAK" damgası taşır; "gönderime hazır" değildir.
- Prompt'lar `ai/draft/prompts/` altında versiyonlanır.
- LLM: Anthropic API (claude). Response'u güvenli parse et (JSON bekleniyorsa fence temizle).

**D2. `applications` tablosu (minimal demo sürümü)** (`infra/migrations/005_applications.sql`):
`id`, `company_id`, `program_id`, `match_id`, `state` (demo için: `draft_ready`),
`draft` jsonb, `created_at`. (Tam state machine + insan onayı Faz sonrası; demoda taslak üretimi yeterli.)

**D3. Draft endpoint:** `POST /matches/{id}/draft` → generator çağır, draft'ı sakla + döndür.

---

## Faz E — Basit demo arayüzü (cila, akıcılık > sağlamlık)

**E1. Tek sayfalık akış (frontend-design skill'ini oku, öyle başla):**
1. **Profil ekranı:** "Demo restoranı yükle" tek tık + görünür özet (isim, Land, çalışan, ihtiyaç).
2. **Eşleşme ekranı:** top 5–8 program kartı. Her kartta: başlık, funding_type rozeti,
   tahmini tutar, skor, ve **"neden uygun?" açılır kutusu** (`score_breakdown`). Üstte sabit
   disclaimer: "Aday programlar — danışman teyidi gerekli."
3. **Taslak ekranı:** bir programda "Başvuru taslağı oluştur" → AI çıktısı akarak görünür
   (streaming hissi ver, yatırımcı "canlı yazılıyor" görsün). "TASLAK" filigranı + disclaimer.

**E2. Akıcılık > kapsam.** Demo takılmasın: loading state'ler, hata durumunda zarif geri düşüş.
Yatırımcı sunumunda tek risk akıcılığın bozulması. Edge-case'lere değil, akışa yatırım yap.

---

## Faz F — SEMANTİK KATMAN (OPSİYONEL / SON — vakit kalırsa)

> Buraya sadece A–E çalışıyorsa gel. Demo semantik olmadan da tam görünür.

**F1. Embedding:** kural filtresinden GEÇEN havuzu (2.488'in tamamı DEĞİL, ~40–80 program) embed et.
Firma ihtiyaç metnini embed et. pgvector cosine similarity ile keyword skorunu **destekle** (değiştirme).
**F2.** Final skor = ağırlıklı(keyword_score, semantic_score). `score_breakdown`'a semantik payını ekle.
**F3.** Küçük havuzda çalıştığı için hızlı; demo akıcılığını bozmaz.

---

## Yürütme sırası (Claude Code için)
1. Faz A (profil) → 2. Faz B (filtre) → 3. Faz C (skor + breakdown) → 4. Faz D (AI taslak)
→ 5. Faz E (arayüz). **Buraya kadar = tam çalışan demo.**
6. Faz F (semantik) yalnızca vakit kalırsa.

## İlk komut (kopyala)
> "Read MVP_TASKS.md fully. Build Faz A through E in order — do NOT start Faz F until A–E run
> end to end. Start with Faz A: write migration 003_companies.sql and a seed loader for
> seeds/demo_company.json. Before writing any UI, read the frontend-design SKILL.md. Every match
> and draft must carry the disclaimer 'Nihai karar ilgili kuruma aittir.' and the system must never
> claim eligibility — only 'aday program, danışman teyidi gerekli'. Confirm the plan, then proceed."