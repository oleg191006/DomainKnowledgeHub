# -*- coding: utf-8 -*-
"""Лінтер метаданих документів знань (ЛР02 Р4).

Перевіряє front matter кожного markdown-документа в kb/ за сімома правилами.
Повертає 0, якщо порушень немає, і 1, якщо є — тому придатний для CI та pre-commit.

Запуск:
    python tools/lint_meta.py kb/
    python tools/lint_meta.py kb/ --max-age-days 365
"""
import argparse
import datetime as dt
import pathlib
import re
import sys

REQUIRED = ["id", "type", "owner", "reviewed", "sources", "sensitivity"]
ALLOWED_TYPES = {"adr", "runbook", "glossary", "policy", "checklist", "howto"}
ALLOWED_SENSITIVITY = {"public", "internal", "restricted", "personal"}
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_front_matter(text: str):
    """Мінімальний розбір front matter: пари ключ-значення та списки з дефісами."""
    m = FM_RE.match(text)
    if not m:
        return None
    data, key = {}, None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith("  - ") and key:
            data.setdefault(key, [])
            if isinstance(data[key], list):
                data[key].append(line[4:].strip())
        elif ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            data[key] = value if value else []
    return data


def lint_file(path: pathlib.Path, seen_ids: dict, max_age_days: int):
    problems = []
    text = path.read_text(encoding="utf-8")
    fm = parse_front_matter(text)

    # R1: front matter присутній
    if fm is None:
        return [f"{path.name}: [R1] немає front matter (блоку між --- на початку файлу)"]

    # R2: усі обов'язкові поля заповнені
    for field in REQUIRED:
        if field not in fm or fm[field] in ("", [], None):
            problems.append(f"{path.name}: [R2] відсутнє або порожнє обов'язкове поле «{field}»")

    # R3: id унікальний і збігається з іменем файлу
    doc_id = fm.get("id")
    if isinstance(doc_id, str) and doc_id:
        if doc_id != path.stem:
            problems.append(f"{path.name}: [R3] id «{doc_id}» не збігається з іменем файлу «{path.stem}»")
        if doc_id in seen_ids:
            problems.append(f"{path.name}: [R3] дублікат id «{doc_id}» (уже є у {seen_ids[doc_id]})")
        else:
            seen_ids[doc_id] = path.name

    # R4: дата reviewed у форматі ISO і не застаріла
    reviewed = fm.get("reviewed")
    if isinstance(reviewed, str) and reviewed:
        try:
            d = dt.date.fromisoformat(reviewed)
            age = (dt.date.today() - d).days
            if age > max_age_days:
                problems.append(f"{path.name}: [R4] документ не переглядався {age} днів "
                                f"(ліміт {max_age_days})")
            if age < 0:
                problems.append(f"{path.name}: [R4] дата reviewed у майбутньому: {reviewed}")
        except ValueError:
            problems.append(f"{path.name}: [R4] дата reviewed не у форматі YYYY-MM-DD: «{reviewed}»")

    # R5: тип документа з дозволеного переліку
    typ = fm.get("type")
    if isinstance(typ, str) and typ and typ not in ALLOWED_TYPES:
        problems.append(f"{path.name}: [R5] невідомий type «{typ}»; дозволені: "
                        f"{', '.join(sorted(ALLOWED_TYPES))}")

    # R6: гриф доступу з дозволеного переліку
    sens = fm.get("sensitivity")
    if isinstance(sens, str) and sens and sens not in ALLOWED_SENSITIVITY:
        problems.append(f"{path.name}: [R6] невідомий sensitivity «{sens}»; дозволені: "
                        f"{', '.join(sorted(ALLOWED_SENSITIVITY))}")

    # R7: щонайменше одне джерело
    sources = fm.get("sources")
    if isinstance(sources, list) and len(sources) == 0:
        problems.append(f"{path.name}: [R7] не вказано жодного джерела")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="kb", help="каталог із документами знань")
    ap.add_argument("--max-age-days", type=int, default=365)
    args = ap.parse_args()

    root = pathlib.Path(args.path)
    files = sorted(root.glob("*.md"))
    if not files:
        print(f"[ПОМИЛКА] у {root} немає markdown-документів")
        return 1

    seen_ids, all_problems = {}, []
    for f in files:
        all_problems += lint_file(f, seen_ids, args.max_age_days)

    print(f"перевірено документів: {len(files)}; правил: 7")
    if all_problems:
        print(f"знайдено порушень: {len(all_problems)}")
        for p in all_problems:
            print("  ✗", p)
        return 1
    print("порушень немає")
    return 0


if __name__ == "__main__":
    sys.exit(main())
