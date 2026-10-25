# -*- coding: utf-8 -*-
"""Журналювання сесій аудитора (ЛР02 Р5) і перенесення ризиків/покращень у claims.csv.

Вихід аудитора має іншу структуру, ніж вихід експерта (criteria / risks / improvements),
тому для нього окремий конвертер. Статуси і рівні верифікації виставляє людина в VERDICTS.
"""
import csv
import datetime as dt
import hashlib
import json
import pathlib

HUB = pathlib.Path(__file__).resolve().parents[1]
CLAIM_COLS = ["id", "statement", "kind", "sources_model", "scope", "confidence", "model", "session",
              "source_verified", "verification_level", "status", "comment"]

GIT_DOC = "https://git-scm.com/docs/git-filter-branch"

# id -> (статус, рівень, джерело/друга модель, коментар людини)
VERDICTS = {
    "a-r1": ("rejected", "V4", "не підтверджено",
             "Механізм правдоподібний, але кількісне твердження «на порядки вища» нічим не "
             "підтверджене: вимірювань пропускної здатності команди немає. Ризик "
             "переформульовано без кількісної оцінки."),
    "a-r2": ("verified", "V3", "модель B, ризик r3",
             "Підтверджено незалежно моделлю B («обхід прав у векторному пошуку»): обидві моделі "
             "вказали на те саме місце — індекс без міток доступу."),
    "a-r3": ("verified", "V3", "модель B, ризик r2",
             "Підтверджено незалежно моделлю B («розсинхронізація джерела і похідних сховищ»)."),
    "a-r4": ("pending", "V4", "потрібне рішення експерта",
             "Ризик стосується проєктного рішення, а не факту; виноситься на обговорення з "
             "головним зберігачем разом з ADR про нормалізацію."),
    "a-r5": ("verified", "V3", "модель B, ризик r5",
             "Підтверджено незалежно моделлю B («мовчазний збій датчиків»); закрито runbook rb-002."),
    "b-r1": ("verified", "V4", "рішення керівника установи",
             "Ризик передавання чутливих даних зовнішній моделі визнано дійсним; закрито політикою "
             "POL-002, технічний фільтр — у плані."),
    "b-r4": ("verified", "V1", GIT_DOC,
             "Підтверджено документацією Git: видалення файлу з робочого дерева не прибирає його з "
             "історії комітів, потрібне переписування історії. Закрито ADR-003."),
    "a-i1": ("accepted", "V4", "рішення інженера знань", "Прийнято: рівень довіри стає обов'язковою "
             "властивістю твердження; частково вже реалізовано в claims.csv."),
    "a-i2": ("accepted", "V4", "рішення керівника установи", "Прийнято з пониженням пріоритету: "
             "повна єдина точка авторизації потребує платформи, якої ще немає."),
    "a-i3": ("accepted", "V4", "рішення інженера знань", "Прийнято частково: канонічний ключ уже "
             "введено ADR-002, подієва синхронізація — у плані."),
    "a-i4": ("accepted", "V4", "рішення інженера знань", "Прийнято: нормалізація зберігає вихідний "
             "текст і версію тезауруса."),
    "a-i5": ("accepted", "V4", "рішення інженера з експлуатації", "Прийнято й реалізовано: "
             "runbook rb-002 про тишу датчика."),
    "b-i1": ("accepted", "V4", "рішення керівника установи", "Дублює a-i2 у частині фільтра перед "
             "LLM; зведено в один пункт плану."),
    "b-i5": ("accepted", "V4", "рішення керівника установи", "Прийнято: розділення публічного й "
             "приватного репозиторіїв, оформлено ADR-003."),
}


def log(session: str, role: str, model: str, prompt: str, raw_path: pathlib.Path) -> dict:
    raw_text = raw_path.read_text(encoding="utf-8")
    prompt_text = (HUB / prompt).read_text(encoding="utf-8")
    parsed = json.loads(raw_text)
    rec = {
        "session": session, "role": role,
        "date": dt.datetime.now().isoformat(timespec="seconds"),
        "model": model, "prompt_id": pathlib.Path(prompt).stem,
        "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:16],
        "params": {"temperature": None, "seed": None,
                   "note": "інтерфейс Claude Code не дозволяє задати параметри семплювання"},
        "raw": raw_text, "parsed": parsed,
        "human_decision": "ризики та покращення перенесено до claims.csv; статуси виставлено людиною",
    }
    with (HUB / "llm_log" / f"{session}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return parsed


def main() -> None:
    a = log("session_02", "A", "claude-opus-5", "prompts/auditor_v1.md",
            HUB / "tmp" / "raw_session02_A.json")
    b = log("session_02", "B", "claude-haiku-4-5-20251001", "prompts/auditor_v1.md",
            HUB / "tmp" / "raw_session02_B.json")

    rows = []
    for role, data, model in (("a", a, "claude-opus-5"), ("b", b, "claude-haiku-4-5-20251001")):
        for item in data["risks"]:
            rows.append((f'{role}-{item["id"]}', item["statement"], "risk",
                         item.get("layer", ""), model))
        for item in data["improvements"]:
            rows.append((f'{role}-{item["id"]}', item["statement"], "improvement",
                         "addresses: " + ", ".join(item.get("addresses", [])), model))

    claims_path = HUB / "claims" / "claims.csv"
    with claims_path.open(encoding="utf-8", newline="") as f:
        existing = list(csv.DictReader(f))
    seen = {r["id"] for r in existing}

    added = 0
    for cid, statement, kind, scope, model in rows:
        if cid in seen or cid not in VERDICTS:
            continue
        status, level, src, comment = VERDICTS[cid]
        existing.append({
            "id": cid, "statement": statement, "kind": kind, "sources_model": "",
            "scope": scope, "confidence": "", "model": model, "session": "session_02",
            "source_verified": src, "verification_level": level, "status": status,
            "comment": comment,
        })
        added += 1

    with claims_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CLAIM_COLS)
        w.writeheader()
        w.writerows(existing)

    s2 = [r for r in existing if r["session"] == "session_02"]
    print(f"journal: session_02.jsonl (2 записи: моделі A і B)")
    print(f"claims.csv: +{added} тверджень сесії 02, разом {len(existing)}")
    for st in ("verified", "accepted", "pending"):
        print(f"  {st}: {sum(1 for r in s2 if r['status'] == st)}")
    print(f"  підтверджено другою моделлю (V3): {sum(1 for r in s2 if r['verification_level'] == 'V3')}")


if __name__ == "__main__":
    main()
