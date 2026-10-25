# -*- coding: utf-8 -*-
"""Запис сесії з LLM у журнал і перенесення тверджень у claims.csv (ЛР01 Р4).

Журнал (llm_log/*.jsonl) — один рядок на виклик моделі: метадані + сирий вихід + розібраний JSON.
claims.csv — робоча таблиця тверджень, яку далі заповнює людина під час верифікації.

Запуск:
    python tools/log_session.py --session session_01 --model claude-opus-5 \
        --prompt prompts/expert_v1.md --raw tmp/raw_a.json --role A
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import pathlib

HUB = pathlib.Path(__file__).resolve().parents[1]
CLAIM_COLS = ["id", "statement", "kind", "sources_model", "scope", "confidence",
              "model", "session", "source_verified", "verification_level", "status", "comment"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True, help="файл підказки")
    ap.add_argument("--raw", required=True, help="файл із сирим виходом моделі")
    ap.add_argument("--role", default="A", help="A або B (друга модель для V3)")
    ap.add_argument("--params", default='{"temperature": null, "seed": null}')
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    raw_text = pathlib.Path(args.raw).read_text(encoding="utf-8")
    prompt_text = pathlib.Path(HUB / args.prompt).read_text(encoding="utf-8")
    parsed = json.loads(raw_text)

    record = {
        "session": args.session,
        "role": args.role,
        "date": dt.datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "prompt_id": pathlib.Path(args.prompt).stem,
        "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16],
        "params": json.loads(args.params),
        "raw": raw_text,
        "parsed": parsed,
        "human_decision": args.note or "перенесено до claims.csv, статуси виставляє людина на етапі V1",
    }
    log_path = HUB / "llm_log" / f"{args.session}.jsonl"
    log_path.parent.mkdir(exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    claims_path = HUB / "claims" / "claims.csv"
    claims_path.parent.mkdir(exist_ok=True)
    existing = []
    if claims_path.exists():
        with claims_path.open(encoding="utf-8", newline="") as f:
            existing = list(csv.DictReader(f))
    seen = {r["id"] for r in existing}

    rows = []
    for c in parsed["claims"]:
        cid = c["id"] if args.role == "A" else f'{c["id"]}B'
        if cid in seen:
            continue
        rows.append({
            "id": cid,
            "statement": c["statement"],
            "kind": c["kind"],
            "sources_model": "; ".join(c.get("sources", [])),
            "scope": c.get("scope", ""),
            "confidence": c.get("confidence", ""),
            "model": args.model,
            "session": args.session,
            "source_verified": "",
            "verification_level": "",
            "status": "pending",
            "comment": "",
        })

    with claims_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CLAIM_COLS)
        w.writeheader()
        w.writerows(existing + rows)

    print(f"журнал: {log_path.name} (+1 запис, модель {args.model})")
    print(f"claims.csv: +{len(rows)} тверджень, разом {len(existing) + len(rows)}")


if __name__ == "__main__":
    main()
