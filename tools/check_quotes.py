# -*- coding: utf-8 -*-
"""Перевірка цитат, наведених у правилах (ЛР04 Р2, критерій C2).

Для кожного правила з непорожнім полем `source_quote` скрипт шукає цю цитату в тексті
вказаного файлу-джерела. Збіг шукається після нормалізації пробілів, щоб перенесення рядка
в markdown не ламало перевірку. Правило без цитати має мати статус `draft`.

Код повернення: 0 — усі цитати знайдено і статуси узгоджені; 1 — є розбіжності.
"""
import json
import pathlib
import re
import sys

HUB = pathlib.Path(__file__).resolve().parents[1]


def norm(text: str) -> str:
    """Нормалізація для порівняння: прибираємо markdown-цитування і зайві пробіли."""
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip().lower()


def main() -> int:
    data = json.loads((HUB / "models/rules.json").read_text(encoding="utf-8"))
    rules = data["rules"]
    cache: dict[str, str] = {}
    ok, missing, draft_ok, draft_bad = [], [], [], []

    for r in rules:
        quote = (r.get("source_quote") or "").strip()
        src = (r.get("source_file") or "").strip()
        status = r.get("status", "draft")

        if not quote:
            (draft_ok if status == "draft" else draft_bad).append(r["id"])
            continue

        if src not in cache:
            path = HUB / src
            if not path.exists():
                missing.append((r["id"], f"немає файлу-джерела {src}"))
                continue
            cache[src] = norm(path.read_text(encoding="utf-8"))

        if norm(quote) in cache[src]:
            ok.append((r["id"], src))
        else:
            missing.append((r["id"], f"цитати немає в {src}: «{quote[:60]}…»"))

    print(f"правил: {len(rules)}")
    print(f"  з цитатою, знайденою в джерелі: {len(ok)}")
    for rid, src in ok:
        print(f"    ✓ {rid} ← {src}")
    print(f"  без цитати зі статусом draft: {len(draft_ok)}"
          + (f" ({', '.join(draft_ok)})" if draft_ok else ""))
    if draft_bad:
        print(f"  ПОМИЛКА — без цитати, але статус не draft: {', '.join(draft_bad)}")
    if missing:
        print(f"  ПОМИЛКА — цитату не знайдено: {len(missing)}")
        for rid, why in missing:
            print(f"    ✗ {rid}: {why}")

    return 1 if (missing or draft_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
