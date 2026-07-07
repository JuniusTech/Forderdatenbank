# Culinary Funding OS — MVP Demo

Sunum için tam demo: katalog → profil → eşleştirme → **AI taslak**.

## Hızlı başlat

```bash
cd packages/ai-worker
source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.apply_migrations
python -m api.main
```

Tarayıcı: **http://localhost:3009**

## Demo akışı (Faz2-3.md A–E)

1. **Demo-Restaurant Berlin** — tek tık seed
2. **Profil speichern** → **Matching starten** (max 8 treffer)
3. Treffer kartında **Warum passend?** — matched_terms + breakdown
4. **Entwurf erstellen** — SSE streaming, ENTWURF filigranı
5. (Opsiyonel) Katalog sekmesinde 2.488 program ara

## API

| Endpoint | Açıklama |
|----------|----------|
| `GET /api/seeds/demo-company` | Berlin restoran seed |
| `POST /api/seeds/demo-company` | Seed'i DB'ye kaydet |
| `POST /api/companies/{id}/match` | Hard filter + keyword skor |
| `POST /api/matches/{id}/draft` | Taslak JSON kaydet |
| `GET /api/matches/{id}/draft/stream` | SSE streaming metin |

## Claude (opsiyonel)

`ANTHROPIC_API_KEY` yoksa template tabanlı Almanca taslak üretilir — demo için yeterli.

