# -*- coding: utf-8 -*-
"""Прогін ситуацій-пасток через рушій: до і після виправлень (ЛР04 Р5).

Запуск:
    python tools/run_traps.py                 # на поточній базі правил
    python tools/run_traps.py --rules models/rules_v1.json   # на початковій версії
"""
import argparse
import json
import pathlib
import sys

HUB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUB))
from engine.engine import RuleEngine  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default="models/rules.json")
    args = ap.parse_args()

    rules = json.loads((HUB / args.rules).read_text(encoding="utf-8"))["rules"]
    eng = RuleEngine(rules)
    traps = json.loads((HUB / "tmp/raw_session04_traps.json").read_text(encoding="utf-8"))["traps"]

    print(f"база правил: {args.rules} ({len(rules)} правил)\n")
    for t in traps:
        out = eng.run(t["facts"])
        got = out.fired_ids
        exp = t["expected_fired"]
        mark = "збіг" if set(got) == set(exp) else "РОЗБІЖНІСТЬ"
        print(f"{t['id']} [{t['problem_type']}] — {mark}")
        print(f"   очікувала модель : {', '.join(exp) or '—'}")
        print(f"   спрацювало       : {', '.join(got) or '—'}")
        if out.suppressed:
            print(f"   придушено        : {', '.join(r for r, _ in out.suppressed)}")
        print()


if __name__ == "__main__":
    main()
