```bash
python -m scripts.enrich_unknown_status --limit 50 --dry-run --ai
# memnunsan:
python -m scripts.enrich_unknown_status --limit 50 --apply --ai
```

## Ne yapmalısın?

**1. Askıdaki işi durdur:**

```bash
kill %1
# veya
kill 18573
```

**2. Ön planda çalıştır** (nohup kullanma):

```bash
cd packages/ai-worker && source .venv/bin/activate

python -m ingest.catalog_crawler \
  --mode backfill \
  --no-headless \
  --channel chrome \
  --wait-for-human \
  --crawl-delay 30
```

**3. Akış:**
1. Chrome açılır
2. CAPTCHA'yı çöz
3. Arama sonuçları görününce terminale dön → **ENTER**
4. Crawler çalışmaya devam eder (`List page 2`, `NEW: ...` logları)

**4. İlerlemeyi izle** (başka bir terminalde):

```bash
cd packages/ai-worker && source .venv/bin/activate
python3 -c "
from db.session import get_session
from sqlalchemy import text
with get_session() as s:
    print('raw_pages:', s.execute(text('SELECT COUNT(*) FROM raw_pages')).scalar())
"
```

---

## Önemli notlar

| Yanlış | Doğru |
|--------|--------|
| `nohup` + `--wait-for-human` | Ön planda çalıştır |
| CAPTCHA sonrası terminali kapatma | Terminal açık kalsın (~21 saat) |
| `cd packages/ai-worker` (zaten içindeyken) | Sadece `source .venv/bin/activate` |

Uzun süre çalışması için CAPTCHA + ENTER'dan **sonra** `tmux` veya `screen` kullanabilirsin:

```bash
tmux new -s backfill
# yukarıdaki python komutunu çalıştır
# CAPTCHA + ENTER
# Ctrl+B, D ile detach
```

Özet: Askıdaki job'ı öldür, **ön planda** yeniden başlat, CAPTCHA + ENTER yap — o zaman sayılar artmaya başlar.