"""List wrong_url targets for SH / LfA / WiBank."""
import json
from collections import defaultdict

hosts = {"schleswig-holstein.de", "lfa.de", "foerderportal.wibank.de", "portal.nbank.de"}
by = defaultdict(list)
with open("kalan_unknown.jsonl", encoding="utf-8") as f:
    for line in f:
        o = json.loads(line)
        h = o.get("host") or ""
        if h in hosts:
            by[h].append(o)

for h, items in sorted(by.items(), key=lambda x: -len(x[1])):
    print(f"\n=== {h} ({len(items)}) ===")
    for o in items:
        print(f"  TITLE: {o['title'][:80]}")
        print(f"  URL:   {o['url']}")
        print(f"  bucket={o.get('bucket')}")
