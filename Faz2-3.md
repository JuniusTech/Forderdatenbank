# Culinary Funding OS — MVP Uçtan Uca Görev Listesi (Faz 2–3 demo)

> **Durum (07.07.2026):** Faz A–E **tamamlandı**. Faz F (semantik) opsiyonel, bekliyor.
> Çalıştır: `cd packages/ai-worker && python -m scripts.apply_migrations && python -m api.main` → :3009

| Faz | Durum |
|-----|--------|
| A Profil + seed | ✅ |
| B Hard filter | ✅ |
| C Keyword skor | ✅ |
| D AI taslak | ✅ (template; Claude opsiyonel) |
| E Demo UI | ✅ |
| F Semantik | ⏸️ |

---

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

## Faz A — Firma profili (temel) ✅

**A1.** `companies` tablosu — `003_demo_mvp.sql` (sadeleştirilmiş alanlar; demo için yeterli)

**A2.** `seeds/demo_company.json` + `POST /api/seeds/demo-company` + UI "Demo-Restaurant Berlin"

---

## Faz B — Kural tabanlı filtre ✅

**B1.** `matcher/hard_filter.py` — region, target_groups (KMU/Unternehmen), status=active

---

## Faz C — Keyword skoru + neden-skoru ✅

**C1.** `matcher/keyword_score.py`
**C2.** `score_breakdown` + `matched_terms` her match'te
**C3.** `004_matches_applications.sql` — matches genişletildi
**C4.** `POST /api/companies/{id}/match` — top 8 (FastAPI)

---

## Faz D — AI başvuru taslağı ✅

**D1.** `ai/draft/generator.py` — template fallback + Claude (ANTHROPIC_API_KEY)
**D2.** `applications` tablosu
**D3.** `POST /api/matches/{id}/draft` + SSE stream

---

## Faz E — Demo arayüzü ✅

**E1.** 4 sekme: Katalog · Profil · Treffer · Antragsentwurf
**E2.** Loading state, SSE streaming, ENTWURF filigranı

---

## Faz F — SEMANTİK (OPSİYONEL) ⏸️

pgvector + embedding — demo sonrası.

---

## Uygulama dosyaları

```
seeds/demo_company.json
matcher/hard_filter.py
matcher/keyword_score.py
matcher/pipeline.py
ai/draft/generator.py
ai/draft/prompts/system_de.txt
api/main.py + api/static/
infra/migrations/004_matches_applications.sql
```

Detaylı orijinal spec ve API listesi: `docs/mvp-demo.md`
