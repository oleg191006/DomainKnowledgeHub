# -*- coding: utf-8 -*-
"""ЛР05 Р2: експертна таксономія та таксономія за кластеризацією.

Експертна версія будується за заздалегідь оголошеним принципом поділу на кожному рівні.
Версія «знизу вгору» отримується кластеризацією векторів термінів.

Про вектори. Завдання передбачає sentence-transformers, однак завантаження нейронної моделі
в цьому середовищі неможливе, тому використано TF-IDF на символьних n-грамах (3–5 символів)
над полем «термін + синоніми + визначення». Для української морфології символьні n-грами
працюють передбачувано: вони зближують словоформи одного кореня без словника. Це свідоме
відхилення, і воно впливає на результат: кластери групуються радше за спільним коренем,
ніж за значенням. Seed і версії зафіксовано для відтворюваності.

Запуск: python tools/build_taxonomies.py
"""
import csv
import pathlib

import numpy as np
import sklearn
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

HUB = pathlib.Path(__file__).resolve().parents[1]
SEED = 20261025
N_CLUSTERS = 8

# --- експертна таксономія: принцип поділу оголошується для кожного рівня ----
EXPERT = {
    "Об'єкт спадщини": {
        "__principle__": "за юридичним режимом об'єкта",
        "Нерухома пам'ятка": ["нерухома пам'ятка", "пам'ятка архітектури", "охоронна зона",
                              "історичний ареал", "візуальний вплив", "протиаварійні роботи"],
        "Рухомий предмет": ["музейний предмет", "ікона на дерев'яній основі", "панельний живопис",
                            "станковий живопис", "гравюра", "акварель", "рукопис", "стародрук",
                            "археологічна знахідка", "музейна колекція", "музейний фонд",
                            "комплект предметів", "частина предмета"],
        "Матеріальна структура": ["дерев'яна основа", "левкас", "фарбовий шар", "полотно",
                                  "рама", "паркетаж", "шпуга", "позолота", "темпера",
                                  "олійний живопис"],
        "Цифровий замінник": ["цифрова копія", "фотофіксація", "оцифрування"],
    },
    "Умови та чинники": {
        "__principle__": "за фізичною природою чинника",
        "Кліматичний чинник": ["температурно-вологісний режим", "відносна вологість повітря",
                               "вогкість", "пересушення", "добові коливання", "сезонний дрейф",
                               "рівноважна вологість", "конденсація", "застій повітря"],
        "Світловий чинник": ["світловий режим", "кумулятивна доза", "люкс-година",
                             "ультрафіолет", "вицвітання"],
        "Біологічний чинник": ["біологічне ураження", "біоураження", "ксерофільний гриб",
                               "активність води"],
        "Механічний і антропогенний чинник": ["експозиційне навантаження", "вібраційний вплив",
                                              "деформація основи", "кракелюр",
                                              "здуття фарбового шару", "осипання"],
    },
    "Дія з об'єктом": {
        "__principle__": "за метою втручання",
        "Облік і документування": ["фондовий облік", "інвентаризація", "паспортизація",
                                   "звірка наявності", "перенумерація", "видача предмета"],
        "Запобігання руйнуванню": ["превентивна консервація", "моніторинг стану збереженості",
                                   "карантин", "акліматизація", "ротація експонування"],
        "Втручання в матеріал": ["консервація", "реставрація", "укріплення фарбового шару",
                                 "підведення ґрунту", "тонування втрат", "дезінсекція",
                                 "аноксія", "заморожування"],
        "Повернення в обіг": ["експонування", "музеєфікація", "реабілітація"],
    },
    "Суб'єкт і відповідальність": {
        "__principle__": "за роллю щодо об'єкта",
        "Фахівець установи": ["хранитель фондів", "реставратор", "куратор колекції",
                              "головний зберігач", "науковий співробітник", "інженер знань",
                              "інженер з експлуатації"],
        "Колегіальний орган": ["фондово-закупівельна комісія", "реставраційна рада"],
        "Зовнішня сторона": ["орган охорони культурної спадщини", "відвідувач",
                             "місцева громада", "балансоутримувач", "фахівець з біопошкоджень"],
    },
    "Запис знання": {
        "__principle__": "за способом подання знання",
        "Обліковий документ": ["облікова картка музейного предмета", "книга надходжень",
                               "інвентарна книга", "акт приймання-передавання",
                               "акт технічного стану", "акт вилучення", "топографічний опис",
                               "паспорт нерухомої пам'ятки", "реставраційний паспорт",
                               "експертний висновок", "охоронний договір",
                               "науково-проєктна документація", "план евакуації"],
        "Формальна модель": ["онтологія предметної області", "тезаурус", "контрольований словник",
                             "метадані", "схема метаданих", "дескриптор", "граф знань",
                             "класифікатор", "авторитетний запис"],
        "Правило і процедура": ["продукційне правило", "слот", "фрейм", "метаправило",
                                "пряме ланцюжкування", "стратегія розв'язання конфліктів",
                                "компетентнісне питання", "золотий набір"],
        "Ідентифікація": ["інвентарний номер", "постійний ідентифікатор", "гриф доступу",
                          "рівень верифікації"],
    },
}


APO = "ʼ"


def canon(term: str) -> str:
    """Та сама нормалізація апострофа, що й у build_terms.py."""
    return term.replace("'", APO).replace("’", APO).strip()


def load_terms() -> list[dict]:
    with (HUB / "models/terms.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_nodes(path: pathlib.Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "parent_id", "label", "level", "division_principle"])
        w.writeheader()
        w.writerows(rows)


def build_expert(terms: list[dict]) -> list[dict]:
    known = {t["term"] for t in terms}
    rows, n = [], 0
    missing = []
    for top, subs in EXPERT.items():
        n += 1
        top_id = f"e{n:02d}"
        rows.append({"id": top_id, "parent_id": "", "label": top, "level": 1,
                     "division_principle": subs["__principle__"]})
        for sub, leaves in subs.items():
            if sub == "__principle__":
                continue
            n += 1
            sub_id = f"e{n:02d}"
            rows.append({"id": sub_id, "parent_id": top_id, "label": sub, "level": 2,
                         "division_principle": "за конкретним поняттям області"})
            for leaf in map(canon, leaves):
                if leaf not in known:
                    missing.append(leaf)
                    continue
                n += 1
                rows.append({"id": f"e{n:02d}", "parent_id": sub_id, "label": leaf, "level": 3,
                             "division_principle": ""})
    if missing:
        print(f"  увага: {len(missing)} листків немає в terms.csv і їх пропущено: "
              + ", ".join(missing[:6]) + ("…" if len(missing) > 6 else ""))
    return rows


def build_cluster(terms: list[dict]) -> list[dict]:
    texts = [f'{t["term"]} {t["alt_labels"]} {t["definition"]}'.strip() for t in terms]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True)
    X_sparse = vec.fit_transform(texts)
    # зниження розмірності перед кластеризацією: на сирих TF-IDF символьних n-грамах
    # average-linkage давав зчеплення — один кластер на 139 термінів і сім одинаків
    svd = TruncatedSVD(n_components=40, random_state=SEED)
    X = normalize(svd.fit_transform(X_sparse))
    model = AgglomerativeClustering(n_clusters=N_CLUSTERS, linkage="ward")
    labels = model.fit_predict(X)

    # назва кластера — термін, найближчий до центроїда (пропозиція для людини на затвердження)
    rows, n = [], 0
    for c in range(N_CLUSTERS):
        idx = np.where(labels == c)[0]
        centroid = X[idx].mean(axis=0)
        head = idx[int(np.argmax(X[idx] @ centroid))]
        n += 1
        cid = f"c{n:02d}"
        rows.append({"id": cid, "parent_id": "", "label": f'кластер {c + 1}: {terms[head]["term"]}',
                     "level": 1, "division_principle": "подібність символьних n-грам (TF-IDF)"})
        for i in idx:
            n += 1
            rows.append({"id": f"c{n:02d}", "parent_id": cid, "label": terms[i]["term"],
                         "level": 2, "division_principle": ""})
    return rows


def main() -> None:
    terms = load_terms()
    print(f"термінів у корпусі: {len(terms)}")

    print("експертна таксономія:")
    exp = build_expert(terms)
    write_nodes(HUB / "models/tax_expert.csv", exp)
    print(f"  вузлів: {len(exp)} (рівень 1: {sum(1 for r in exp if r['level'] == 1)}, "
          f"рівень 2: {sum(1 for r in exp if r['level'] == 2)}, "
          f"рівень 3: {sum(1 for r in exp if r['level'] == 3)})")

    print(f"кластеризація (seed={SEED}, sklearn {sklearn.__version__}, "
          f"TF-IDF char_wb 3–5, {N_CLUSTERS} кластерів):")
    clu = build_cluster(terms)
    write_nodes(HUB / "models/tax_cluster.csv", clu)
    sizes = {}
    for r in clu:
        if r["level"] == 1:
            sizes[r["label"]] = 0
        else:
            sizes[[x for x in clu if x["id"] == r["parent_id"]][0]["label"]] += 1
    print(f"  вузлів: {len(clu)}")
    for name, size in sorted(sizes.items(), key=lambda kv: -kv[1]):
        print(f"    {name}: {size} термінів")


if __name__ == "__main__":
    main()
