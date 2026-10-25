# -*- coding: utf-8 -*-
"""Валідація сирого виходу LLM за схемою ExpertAnswer (ЛР01 Р4, критерій C4).

Запуск:
    python tools/validate_claims.py llm_log/session_01.jsonl
    python tools/validate_claims.py --raw path/to/raw.json

Код повернення: 0 — усе валідне, 1 — є помилки схеми (використовується в CI).
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from schemas.claim import ExpertAnswer  # noqa: E402

from pydantic import ValidationError  # noqa: E402


def load_payloads(path: pathlib.Path):
    """З jsonl-журналу беремо поле parsed кожного запису; із .json — файл цілком."""
    if path.suffix == ".jsonl":
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                rec = json.loads(line)
                yield f"{path.name}:{i} (prompt={rec.get('prompt_id')}, model={rec.get('model')})", \
                      rec.get("parsed", rec)
    else:
        yield path.name, json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="journal .jsonl або сирий .json")
    args = ap.parse_args()

    ok = True
    for label, payload in load_payloads(pathlib.Path(args.path)):
        try:
            answer = ExpertAnswer.model_validate(payload)
        except ValidationError as exc:
            ok = False
            print(f"[НЕВАЛІДНО] {label}")
            for err in exc.errors():
                loc = ".".join(str(p) for p in err["loc"])
                print(f"    {loc}: {err['msg']}")
            continue
        kinds = {}
        for c in answer.claims:
            kinds[c.kind.value] = kinds.get(c.kind.value, 0) + 1
        no_src = sum(1 for c in answer.claims if not c.sources)
        print(f"[OK] {label}: тверджень {len(answer.claims)}, "
              f"типи {kinds}, без джерела {no_src}, "
              f"середня confidence {sum(c.confidence for c in answer.claims)/len(answer.claims):.2f}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
