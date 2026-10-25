# -*- coding: utf-8 -*-
"""ЛР05 Р3: метрики якості таксономій і їх порівняння.

Метрики:
* покриття — частка термінів корпусу, що потрапили в листки таксономії;
* частка «Інше» — частка термінів у категоріях-смітниках (Інше, Різне, Додаткове);
* глибина і ширина — максимальний рівень і середня кількість дітей у вузла-батька;
* MECE-порушення — терміни, що трапляються більш ніж в одній гілці, і вузли з одним дитям
  (поділ, який нічого не розділяє);
* κ Коена між двома розмітниками на 30 термінах;
* скоригований індекс Ренда (ARI) між розбиттям кожної версії та експертною.

Запуск: python tools/taxonomy_metrics.py
"""
import csv
import json
import pathlib
from collections import Counter, defaultdict

from sklearn.metrics import adjusted_rand_score, cohen_kappa_score

HUB = pathlib.Path(__file__).resolve().parents[1]
JUNK = {"інше", "різне", "додаткове", "інші", "other"}


def read_csv_tax(path: pathlib.Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [{"id": r["id"], "parent_id": r["parent_id"], "label": r["label"],
                 "level": int(r["level"])} for r in csv.DictReader(f)]


def read_llm_tax(path: pathlib.Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))["nodes"]
    return [{"id": n["id"], "parent_id": n.get("parent_id") or "", "label": n["label"],
             "level": int(n["level"])} for n in data]


def metrics(nodes: list[dict], terms: set[str], name: str) -> dict:
    by_id = {n["id"]: n for n in nodes}
    children = defaultdict(list)
    for n in nodes:
        children[n["parent_id"]].append(n["id"])

    max_level = max(n["level"] for n in nodes)
    leaves = [n for n in nodes if not children[n["id"]]]
    leaf_labels = [n["label"] for n in leaves]

    covered = {lbl for lbl in leaf_labels if lbl in terms}
    coverage = len(covered) / len(terms)

    junk_nodes = {n["id"] for n in nodes if n["label"].strip().lower() in JUNK}
    junk_terms = sum(1 for n in nodes if n["parent_id"] in junk_nodes)
    junk_share = junk_terms / max(len(leaf_labels), 1)

    # MECE: той самий термін у кількох гілках
    dup = [t for t, c in Counter(leaf_labels).items() if c > 1]
    # поділ, що нічого не розділяє: у батька рівно одна дитина
    single = [by_id[p]["label"] for p in children if p and len(children[p]) == 1]

    # лише вузли, що справді мають дітей: defaultdict створює порожні записи для листків
    parents = [p for p in children if p and children[p]]
    width = sum(len(children[p]) for p in parents) / max(len(parents), 1)

    return {"name": name, "nodes": len(nodes), "leaves": len(leaves), "depth": max_level,
            "width": round(width, 2), "coverage": round(coverage, 3),
            "junk_share": round(junk_share, 3), "dup_terms": dup, "single_child": single,
            "mece_violations": len(dup) + len(single)}


def assignment_map(nodes: list[dict]) -> dict[str, str]:
    """Термін-листок → назва його кореневої категорії."""
    by_id = {n["id"]: n for n in nodes}
    children = defaultdict(list)
    for n in nodes:
        children[n["parent_id"]].append(n["id"])
    out = {}
    for n in nodes:
        if children[n["id"]]:
            continue
        cur = n
        while cur["parent_id"]:
            cur = by_id[cur["parent_id"]]
        out[n["label"]] = cur["label"]
    return out


def main() -> None:
    terms = {r["term"] for r in csv.DictReader(open(HUB / "models/terms.csv", encoding="utf-8"))}
    versions = [("експертна", read_csv_tax(HUB / "models/tax_expert.csv")),
                ("кластеризація", read_csv_tax(HUB / "models/tax_cluster.csv"))]
    llm_path = HUB / "models/tax_llm.json"
    if llm_path.exists():
        versions.insert(1, ("LLM", read_llm_tax(llm_path)))
    final_path = HUB / "models/taxonomy_final.csv"
    if final_path.exists():
        versions.append(("підсумкова", read_csv_tax(final_path)))

    print("=== 1. Метрики версій")
    print(f"{'версія':16} {'вузлів':>7} {'листків':>8} {'глибина':>8} {'ширина':>7} "
          f"{'покриття':>9} {'«Інше»':>7} {'MECE':>5}")
    results = []
    for name, nodes in versions:
        m = metrics(nodes, terms, name)
        results.append(m)
        print(f"{m['name']:16} {m['nodes']:7} {m['leaves']:8} {m['depth']:8} {m['width']:7} "
              f"{m['coverage']*100:8.1f}% {m['junk_share']*100:6.1f}% {m['mece_violations']:5}")
    for m in results:
        if m["dup_terms"]:
            print(f"  [{m['name']}] термін у кількох гілках: {', '.join(m['dup_terms'][:5])}")
        if m["single_child"]:
            print(f"  [{m['name']}] поділ з однією дитиною: {', '.join(m['single_child'][:5])}")

    print("\n=== 2. ARI відносно експертної версії")
    exp_map = assignment_map(versions[0][1])
    for name, nodes in versions[1:]:
        other = assignment_map(nodes)
        common = sorted(set(exp_map) & set(other))
        if len(common) < 10:
            print(f"  {name}: спільних термінів лише {len(common)} — ARI не обчислюється")
            continue
        a = [exp_map[t] for t in common]
        b = [other[t] for t in common]
        print(f"  {name}: ARI = {adjusted_rand_score(a, b):.3f} (на {len(common)} спільних термінах)")

    dump = {"versions": results, "ari": {}, "kappa": None}
    exp_map2 = assignment_map(versions[0][1])
    for name, nodes in versions[1:]:
        other = assignment_map(nodes)
        common = sorted(set(exp_map2) & set(other))
        if len(common) >= 10:
            dump["ari"][name] = {
                "value": round(adjusted_rand_score([exp_map2[t] for t in common],
                                                   [other[t] for t in common]), 3),
                "n": len(common)}

    print("\n=== 3. κ Коена між двома розмітниками (30 термінів)")
    hp = HUB / "tmp/annotation_human.json"
    mp = HUB / "tmp/annotation_model.json"
    if hp.exists() and mp.exists():
        human = {a["term"]: a["category"] for a in json.loads(hp.read_text(encoding="utf-8"))["assignments"]}
        model = {a["term"]: a["category"] for a in json.loads(mp.read_text(encoding="utf-8"))["assignments"]}
        common = sorted(set(human) & set(model))
        a = [human[t] for t in common]
        b = [model[t] for t in common]
        k = cohen_kappa_score(a, b)
        agree = sum(x == y for x, y in zip(a, b))
        print(f"  термінів: {len(common)}; збігів: {agree} ({agree/len(common)*100:.1f} %)")
        print(f"  κ Коена = {k:.3f}")
        dis = [(t, human[t], model[t]) for t in common if human[t] != model[t]]
        for t, h, m_ in dis:
            print(f"    розбіжність: «{t}» — розмітник 1: {h} | розмітник 2: {m_}")
        dump["kappa"] = {"value": round(k, 3), "n": len(common), "agree": agree,
                         "disagreements": [{"term": t, "a": h, "b": m_} for t, h, m_ in dis]}
    else:
        print("  файли розмітки ще не готові")

    (HUB / "tmp/taxonomy_metrics.json").write_text(
        json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nметрики збережено: tmp/taxonomy_metrics.json")


if __name__ == "__main__":
    main()
