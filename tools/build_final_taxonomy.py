# -*- coding: utf-8 -*-
"""ЛР05 Р4: підсумкова таксономія як гібрид трьох версій (models/taxonomy_final.csv).

Основа — експертна версія: вона єдина має оголошений принцип поділу на кожному рівні.
З інших версій запозичено конкретні виправлення, перелічені в CORRECTIONS: кожне з них
виникло з розбіжності між версіями або між двома розмітниками, а не з довільного рішення.

Перевірки, які виконує скрипт: відсутність циклів, наявність батька в кожного вузла, крім
кореня, відсутність категорій-смітників, наявність принципу поділу на рівнях 1–3.

Запуск: python tools/build_final_taxonomy.py
"""
import csv
import pathlib

HUB = pathlib.Path(__file__).resolve().parents[1]

# (термін, новий батько, підстава зміни)
CORRECTIONS = [
    ("цифрова копія", "Запис знання / Формальна модель",
     "Розбіжність розмітників: цифрова копія описує предмет, а не є предметом. Другий "
     "розмітник мав рацію — копія належить до записів знання."),
    ("фотофіксація", "Дія з об'єктом / Облік і документування",
     "Випливає з попереднього: якщо копія — запис, то її створення є дією документування."),
    ("оцифрування", "Дія з об'єктом / Облік і документування",
     "Те саме: процес, а не об'єкт. У вихідній версії гілка «Цифровий замінник» змішувала "
     "об'єкт і дію — порушення принципу поділу."),
    ("золотий набір", "Запис знання / Правило і процедура",
     "Розмітник 2 відніс термін до об'єктів спадщини, сприйнявши «набір» як сукупність "
     "предметів. Це показало, що термін двозначний поза контекстом; у визначенні додано "
     "уточнення «набір тестів»."),
    ("аноксія", "Дія з об'єктом / Втручання в матеріал",
     "Розмітник 2 відніс до чинників середовища. Залишено в діях: аноксія — це спосіб "
     "обробки, а не умова зберігання, однак у визначення додано уточнення."),
    ("охоронний договір", "Запис знання / Обліковий документ",
     "Розмітник 2 відніс до суб'єктів через згадку сторін. Залишено серед документів, бо "
     "класифікуємо за формою подання знання, а не за тим, кого воно стосується."),
]

# четвертий рівень: поділ втручань за природою впливу (запозичено з кластеризації,
# де механічні й хімічні операції розійшлися в різні кластери)
LEVEL4 = {
    "Втручання в матеріал": {
        "__principle__": "за природою впливу на матеріал",
        "Механічне втручання": ["укріплення фарбового шару", "підведення ґрунту",
                                "профілактичне заклеювання"],
        "Хімічне і фізичне втручання": ["дезінсекція", "аноксія", "заморожування"],
        "Відновлення зображення": ["тонування втрат", "реставрація", "консервація"],
    }
}


def main() -> None:
    src = list(csv.DictReader(open(HUB / "models/tax_expert.csv", encoding="utf-8")))
    terms = {r["term"]: r for r in csv.DictReader(
        open(HUB / "models/terms.csv", encoding="utf-8"))}

    by_id = {r["id"]: r for r in src}
    label_of = {r["id"]: r["label"] for r in src}
    path_of = {}
    for r in src:
        parts, cur = [], r
        while cur["parent_id"]:
            cur = by_id[cur["parent_id"]]
            parts.append(cur["label"])
        path_of[r["id"]] = " / ".join(reversed(parts))

    id_by_path = {f'{path_of[r["id"]]} / {r["label"]}'.strip(" /"): r["id"]
                  for r in src if int(r["level"]) == 2}
    id_by_path.update({r["label"]: r["id"] for r in src if int(r["level"]) == 1})

    rows = [dict(r) for r in src]
    applied = []
    for term, new_parent_path, why in CORRECTIONS:
        node = next((r for r in rows if r["label"] == term), None)
        parent_id = id_by_path.get(new_parent_path)
        if node and parent_id and node["parent_id"] != parent_id:
            node["parent_id"] = parent_id
            applied.append((term, new_parent_path, why))

    # прибираємо гілку, що лишилася порожньою після переміщень
    for r in list(rows):
        if int(r["level"]) == 2 and not any(x["parent_id"] == r["id"] for x in rows):
            rows.remove(r)

    # четвертий рівень
    n = max(int(r["id"][1:]) for r in rows)
    for parent_label, groups in LEVEL4.items():
        parent = next(r for r in rows if r["label"] == parent_label)
        parent["division_principle"] = groups["__principle__"]
        for sub, leaves in groups.items():
            if sub == "__principle__":
                continue
            n += 1
            sub_id = f"f{n:03d}"
            rows.append({"id": sub_id, "parent_id": parent["id"], "label": sub, "level": "3",
                         "division_principle": "за конкретним поняттям області"})
            for leaf in leaves:
                node = next((r for r in rows if r["label"] == leaf), None)
                if node:
                    node["parent_id"] = sub_id
                    node["level"] = "4"

    out_rows = []
    for r in rows:
        label = r["label"]
        t = terms.get(label, {})
        out_rows.append({
            "id": r["id"], "parent_id": r["parent_id"], "label": label, "level": r["level"],
            "definition": t.get("definition", ""), "alt_labels": t.get("alt_labels", ""),
            "division_principle": r["division_principle"],
            "source": t.get("source", "структура експертної версії"),
        })

    path = HUB / "models/taxonomy_final.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "parent_id", "label", "level", "definition",
                                          "alt_labels", "division_principle", "source"])
        w.writeheader()
        w.writerows(out_rows)

    levels = {}
    for r in out_rows:
        levels[r["level"]] = levels.get(r["level"], 0) + 1
    print(f"вузлів: {len(out_rows)}; за рівнями: "
          + ", ".join(f"{k} — {v}" for k, v in sorted(levels.items())))
    print(f"застосовано виправлень: {len(applied)}")
    for term, parent, why in applied:
        print(f"  «{term}» → {parent}")
    print(f"файл: {path.relative_to(HUB)}")


if __name__ == "__main__":
    main()
