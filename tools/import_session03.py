# -*- coding: utf-8 -*-
"""ЛР03 Р3: перенесення правил і спірних термінів у claims.csv + збереження models/rules.json.

Правила зберігаються двічі: у машинному вигляді (models/rules.json — для рушія в ЛР 4) і як
читабельні твердження в claims.csv, бо таблиця тверджень має містити ВСІ знання, отримані від
моделі, незалежно від подальшої форми.
"""
import csv
import datetime as dt
import hashlib
import json
import pathlib

HUB = pathlib.Path(__file__).resolve().parents[1]
OPS = {"=": "=", "!=": "≠", ">": ">", "<": "<", ">=": "≥", "<=": "≤",
       "in": "серед", "contains": "містить"}


def human_rule(rule: dict) -> str:
    conds = " І ".join(
        f'{c["slot"]} {OPS.get(c["op"], c["op"])} '
        f'{", ".join(map(str, c["value"])) if isinstance(c["value"], list) else c["value"]}'
        for c in rule["if"])
    acts = "; ".join(rule["then"])
    text = f"ЯКЩО {conds}, ТО {acts}"
    if rule.get("exception"):
        text += f" ВИНЯТОК: {rule['exception']}"
    return text


def log_session(session: str, role: str, model: str, prompt: str, raw: pathlib.Path) -> dict:
    raw_text = raw.read_text(encoding="utf-8")
    prompt_text = (HUB / prompt).read_text(encoding="utf-8")
    rec = {
        "session": session, "role": role,
        "date": dt.datetime.now().isoformat(timespec="seconds"),
        "model": model, "prompt_id": pathlib.Path(prompt).stem,
        "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16],
        "params": {"temperature": None, "seed": None,
                   "note": "інтерфейс Claude Code не дає задати параметри семплювання"},
        "raw": raw_text, "parsed": json.loads(raw_text),
        "human_decision": "перенесено в claims.csv і models/rules.json; статуси виставляє людина",
    }
    with (HUB / "llm_log" / f"{session}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec["parsed"]


def main() -> None:
    rules_data = log_session("session_03", "A", "claude-opus-5",
                             "prompts/pack_v1/03_rules.md",
                             HUB / "tmp/raw_session03_rules_A.json")
    gloss = log_session("session_03", "A", "claude-opus-5",
                        "prompts/pack_v1/01_glossary.md",
                        HUB / "tmp/raw_session03_glossary_A.json")

    groups = {g["id"]: g["name"] for g in rules_data["groups"]}
    json.dump({"groups": rules_data["groups"], "rules": rules_data["rules"],
               "tests": rules_data["tests"]},
              open(HUB / "models/rules.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    path = HUB / "claims/claims.csv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
        cols = list(rows[0].keys())
    seen_id = {r["id"] for r in rows}
    seen_text = {r["statement"].strip().lower() for r in rows}

    added, dupes = [], []
    for r in rules_data["rules"]:
        cid = f'rule-{r["id"]}'
        text = human_rule(r)
        if cid in seen_id:
            continue
        if text.strip().lower() in seen_text:
            dupes.append(cid)
            continue
        seen_text.add(text.strip().lower())
        added.append({
            "id": cid, "statement": text, "kind": "rule", "sources_model": "",
            "scope": f'група: {groups.get(r["group"], r["group"])}; пріоритет {r["priority"]}',
            "confidence": "", "model": "claude-opus-5", "session": "session_03",
            "source_verified": "", "verification_level": "V2",
            "status": "pending",
            "comment": f'Обґрунтування моделі: {r["rationale"]} Перевірка — золотим набором тестів у ЛР 4.',
        })

    for t in gloss["terms"]:
        if not t["disputed"]:
            continue
        cid = f'term-{t["id"]}'
        if cid in seen_id:
            continue
        added.append({
            "id": cid,
            "statement": f'Термін «{t["label"]}» уживається неоднозначно: {t["definition"]}',
            "kind": "hypothesis", "sources_model": "",
            "scope": f'словник, група {t["group"]}', "confidence": "",
            "model": "claude-opus-5", "session": "session_03",
            "source_verified": "потребує експерта", "verification_level": "V4",
            "status": "pending",
            "comment": f'Запитання до експерта: {t["question_for_expert"]}',
        })

    rows += added
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    s3 = [r for r in rows if r["session"] == "session_03"]
    print(f"models/rules.json: {len(rules_data['rules'])} правил, "
          f"{len(rules_data['groups'])} груп, {len(rules_data['tests'])} тестів")
    print(f"claims.csv: +{len(added)} тверджень сесії 03, разом {len(rows)}")
    print(f"  типи сесії 03: {dict(Counter(r['kind'] for r in s3))}")
    print(f"  усього унікальних id: {len({r['id'] for r in rows})}")
    print(f"  дублікатів відсіяно: {len(dupes)}")
    print(f"  гіпотез у базі: {sum(1 for r in rows if r['kind'] == 'hypothesis')}")


if __name__ == "__main__":
    main()
