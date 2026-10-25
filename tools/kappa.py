# -*- coding: utf-8 -*-
"""κ Коена між оцінками двох моделей і зведення верифікації (ЛР03 Р4–Р5).

Формула: κ = (Po − Pe) / (1 − Pe), де
  Po — спостережувана частка збігів,
  Pe — очікувана випадкова частка збігів = Σ_k p_A(k) · p_B(k) за категоріями k.

Запуск: python tools/kappa.py
Читає tmp/raw_session03_judge_A.json і ..._B.json, пише claims/verification.csv.
"""
import csv
import json
import pathlib
from collections import Counter

HUB = pathlib.Path(__file__).resolve().parents[1]
LABELS = ["support", "reject", "uncertain"]


def cohen_kappa(a: list[str], b: list[str]) -> tuple[float, float, float]:
    assert len(a) == len(b) and a, "оцінки мають бути однакової ненульової довжини"
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in LABELS)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    return po, pe, kappa


def interpret(k: float) -> str:
    # шкала Landis & Koch (1977)
    for bound, label in ((0.0, "немає згоди"), (0.20, "незначна"), (0.40, "слабка"),
                         (0.60, "помірна"), (0.80, "істотна"), (1.01, "майже повна")):
        if k < bound:
            return label
    return "майже повна"


def main() -> None:
    A = {j["id"]: j for j in json.load(open(HUB / "tmp/raw_session03_judge_A.json",
                                            encoding="utf-8"))["judgements"]}
    B = {j["id"]: j for j in json.load(open(HUB / "tmp/raw_session03_judge_B.json",
                                            encoding="utf-8"))["judgements"]}
    human = {r["id"]: r["status"] for r in csv.DictReader(
        open(HUB / "claims/claims.csv", encoding="utf-8"))}

    ids = sorted(set(A) & set(B))
    la = [A[i]["verdict"] for i in ids]
    lb = [B[i]["verdict"] for i in ids]
    po, pe, k = cohen_kappa(la, lb)

    rows = []
    for i in ids:
        va, vb = A[i]["verdict"], B[i]["verdict"]
        rows.append({
            "id": i,
            "model_A_verdict": va,
            "model_B_verdict": vb,
            "models_agree": "так" if va == vb else "ні",
            "human_v1_status": human.get(i, ""),
            "model_A_reason": A[i]["reason"],
            "model_B_reason": B[i]["reason"],
        })
    out = HUB / "claims/verification.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"тверджень оцінено обома моделями: {len(ids)}")
    print(f"  розподіл A: {dict(Counter(la))}")
    print(f"  розподіл B: {dict(Counter(lb))}")
    print(f"  Po (спостережувана згода) = {po:.3f}")
    print(f"  Pe (випадкова згода)      = {pe:.3f}")
    print(f"  κ Коена                   = {k:.3f}  ({interpret(k)} згода за Landis & Koch)")
    dis = [r["id"] for r in rows if r["models_agree"] == "ні"]
    print(f"  розбіжності ({len(dis)}): {', '.join(dis)}")

    # де обидві моделі суперечать висновку людини на етапі V1
    conflict = [r["id"] for r in rows
                if r["model_A_verdict"] == r["model_B_verdict"] == "reject"
                and r["human_v1_status"] == "verified"]
    print(f"  обидві моделі відхилили те, що людина підтвердила на V1: "
          f"{', '.join(conflict) if conflict else 'немає'}")
    print(f"файл: {out.relative_to(HUB)}")


if __name__ == "__main__":
    main()
