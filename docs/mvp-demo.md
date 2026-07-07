# Culinary Funding OS — MVP Demo

Sunum için minimal demo: 2.488 program kataloğu + firma profili + kural tabanlı eşleştirme.

## Hızlı başlat

```bash
# 1. Bağımlılıklar (ilk kez)
cd packages/ai-worker
source .venv/bin/activate
pip install -r requirements.txt

# 2. Tablolar (companies + matches dahil)
python -m scripts.init_db

# 3. Demo API + UI
python -m api.main
```

Tarayıcı: **http://localhost:3009**

## Demo akışı (müşteri sunumu)

1. **Katalog** — 2.488 program, arama + bölge/Förderart filtresi
2. **Unternehmensprofil** — "Demo-Profil laden" veya hazır senaryo (Gastronomie KMU)
3. **Profil speichern** → **Matching starten** → skorlu treffer listesi
4. Treffer veya katalog kartına tıkla → program detayı + başvuru linki

## API uçları

| Method | Path | Açıklama |
|--------|------|----------|
| GET | `/api/health` | Durum + program sayısı |
| GET | `/api/stats` | Özet istatistikler |
| GET | `/api/programs` | Liste (q, region, funding_type, page) |
| GET | `/api/programs/{id}` | Detay |
| POST | `/api/companies` | Profil kaydet |
| POST | `/api/companies/{id}/match` | Eşleştirme çalıştır |
| GET | `/api/companies/{id}/matches` | Son eşleşmeler |

## Notlar

- AI/LLM yok — kural tabanlı skor (bölge, büyüklük, sektör, yatırım ihtiyacı)
- Her treffer: `human_review_required` + disclaimer (demo UI'da görünür)
- Hukuki teyit (moysies) MVP sonrası; sunumda "Pilot / unverbindlich" olarak konumlandır
- Veri: uzak PostgreSQL'deki `funding_programs` (2.488 kayıt)
