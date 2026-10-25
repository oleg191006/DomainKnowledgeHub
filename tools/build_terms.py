# -*- coding: utf-8 -*-
"""ЛР05 Р1: корпус термінів предметної області з частотами (models/terms.csv).

Корпус — це реальні документи репозиторію: документи знань kb/, аналітичні документи docs/,
витяги з джерел sources/, база правил і таблиця тверджень. Кандидати в терміни беруться зі
словника ЛР 3 (канонічні назви й синоніми) та з переліку, доповненого вручну за матеріалами
правил і фреймів. Частота — кількість входжень у корпус з урахуванням словозміни за основою.

Правила нормалізації зафіксовано в README репозиторію й продубльовано нижче в коментарях.

Запуск: python tools/build_terms.py
"""
import csv
import json
import pathlib
import re
import unicodedata

HUB = pathlib.Path(__file__).resolve().parents[1]

# --- правила нормалізації ---------------------------------------------------
# 1. Нижній регістр, крім абревіатур у верхньому регістрі (RH, CIDOC CRM, SKOS, AAT).
# 2. Однина, називний відмінок для канонічної форми.
# 3. Апостроф уніфіковано до U+02BC; дефіси — до звичайного «-».
# 4. Синоніми не стають окремими термінами: вони йдуть у колонку alt_labels.
# 5. Терміни коротші за 3 символи та службові слова відкидаються.
# 6. Частота рахується за основою слова (перші 6 символів кореня), щоб «пам'ятки»,
#    «пам'яток» і «пам'ятка» зараховувалися одному терміну.

ABBREV = {"RH", "CIDOC CRM", "SKOS", "AAT", "OWL", "RDF", "ADR", "CSV", "JSON", "ISO", "LOD",
          "ICOM", "ICCROM", "CCI", "UUID", "SPARQL", "MQTT", "OCR", "LLM", "CoVe", "KMS",
          "MECE", "TF-IDF", "ARI"}
APO = "ʼ"

# терміни, додані вручну за матеріалами правил, фреймів і документів знань
EXTRA = {
    "object": ["панельний живопис", "станковий живопис", "полотно", "рама", "паркетаж",
               "шпуга", "позолота", "темпера", "олійний живопис", "гравюра", "акварель",
               "рукопис", "стародрук", "археологічна знахідка", "монументальний живопис",
               "комплект предметів", "частина предмета", "науково-допоміжний матеріал",
               "пам'ятка архітектури", "охоронна зона", "історичний ареал"],
    "document": ["акт технічного стану", "акт вилучення", "книга реєстрації актів",
                 "охоронний договір", "науково-проєктна документація", "реставраційне завдання",
                 "журнал навчань", "журнал калібрувань", "план евакуації", "облікова база даних"],
    "condition": ["вогкість", "пересушення", "добові коливання", "сезонний дрейф",
                  "рівноважна вологість", "конденсація", "деформація основи", "осипання",
                  "вицвітання", "кумулятивна доза", "люкс-година", "ультрафіолет",
                  "біоураження", "ксерофільний гриб", "активність води", "застій повітря",
                  "експозиційне навантаження", "вібраційний вплив", "візуальний вплив"],
    "process": ["акліматизація", "карантин", "аноксія", "заморожування", "тонування втрат",
                "підведення ґрунту", "профілактичне заклеювання", "звірка наявності",
                "паспортизація", "нормалізація термінів", "дедуплікація", "верифікація",
                "кластеризація", "перенумерація", "ротація експонування", "протиаварійні роботи",
                "музеєфікація", "реабілітація"],
    "actor": ["інженер з експлуатації", "головний зберігач", "науковий співробітник",
              "інженер знань", "відвідувач", "місцева громада", "балансоутримувач",
              "фахівець з біопошкоджень"],
    "descriptor": ["слот", "фрейм", "продукційне правило", "пряме ланцюжкування",
                   "стратегія розв'язання конфліктів", "метаправило", "золотий набір",
                   "компетентнісне питання", "рівень верифікації", "гриф доступу",
                   "front matter", "канонічний термін", "принцип поділу", "MECE",
                   "коефіцієнт згоди", "скоригований індекс Ренда", "покриття таксономії"],
}


def canon(term: str) -> str:
    """Канонічна форма: нижній регістр (крім абревіатур), уніфіковані апостроф і дефіс."""
    t = unicodedata.normalize("NFC", term.strip())
    t = t.replace("'", APO).replace("’", APO).replace("‐", "-").replace("–", "-")
    t = re.sub(r"\s+", " ", t)
    return t if t in ABBREV else (t[0].lower() + t[1:] if t else t)


def stem(word: str) -> str:
    return canon(word).lower()[:6]


def load_corpus() -> str:
    parts = []
    for folder in ("kb", "docs", "sources"):
        for p in (HUB / folder).glob("*.md"):
            parts.append(p.read_text(encoding="utf-8"))
    for f in ("models/rules.json", "claims/claims.csv", "models/glossary.json"):
        parts.append((HUB / f).read_text(encoding="utf-8"))
    return canon(" ".join(parts)).lower()


def main() -> None:
    corpus = load_corpus()
    gloss = json.loads((HUB / "models/glossary.json").read_text(encoding="utf-8"))["terms"]

    rows, seen = [], set()

    def add(label: str, group: str, definition: str, alts: list[str], source: str) -> None:
        c = canon(label)
        key = c.lower()
        if key in seen or len(c) < 3:
            return
        seen.add(key)
        # частота за основою першого слова терміна, щоб ловити словозміну
        head = stem(c.split()[0])
        freq = len(re.findall(re.escape(head), corpus))
        rows.append({"term": c, "alt_labels": "; ".join(canon(a) for a in alts),
                     "group": group, "definition": definition, "source": source, "freq": freq})

    for t in gloss:
        add(t["label"], t["group"], t["definition"], t["alt_labels"], "glossary (ЛР 3)")

    for group, items in EXTRA.items():
        for label in items:
            add(label, group, "", [], "правила, фрейми та документи знань")

    rows.sort(key=lambda r: (-r["freq"], r["term"]))
    out = HUB / "models/terms.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["term", "alt_labels", "group", "definition",
                                          "source", "freq"])
        w.writeheader()
        w.writerows(rows)

    with_def = sum(1 for r in rows if r["definition"])
    with_alt = sum(1 for r in rows if r["alt_labels"])
    print(f"канонічних термінів: {len(rows)}")
    print(f"  з визначенням: {with_def}")
    print(f"  із синонімами: {with_alt}")
    print(f"  сумарна частота: {sum(r['freq'] for r in rows)}")
    print(f"  найчастіші: " + ", ".join(f"{r['term']} ({r['freq']})" for r in rows[:6]))
    print(f"файл: {out.relative_to(HUB)}")


if __name__ == "__main__":
    main()
