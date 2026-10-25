# -*- coding: utf-8 -*-
"""Метрики надійності експертних сесій (ЛР03 Р5).

Рахує: частки статусів, κ Коена між моделями, точність вердикту кожної моделі відносно
остаточного рішення людини, вартість сесій у токенах і секундах.

Вартість узята з повідомлень про завершення підзадач (виміряні значення, не оцінки);
час роботи людини хронометражем не вимірювався — його оцінка наведена окремо й позначена.
"""
import csv
import json
import pathlib
from collections import Counter

HUB = pathlib.Path(__file__).resolve().parents[1]

# виміряно середовищем виконання підзадач: (токени, секунди)
SESSION_COST = {
    "session_01 expert A (opus)":   (47_240, 230),
    "session_02 auditor A (opus)":  (43_185, 160),
    "session_02 auditor B (haiku)": (46_388, 48),
    "session_03 glossary A (opus)": (54_859, 301),
    "session_03 rules A (opus)":    (49_549, 202),
    "session_03 judge A (opus)":    (50_244, 161),
    "session_03 judge B (haiku)":   (61_305, 91),
    "session_03 cove plan A":       (42_384, 137),
    "session_03 cove answers A":    (47_358, 199),
}

# оцінка часу людини: кількість дій × середня тривалість дії (не хронометраж)
HUMAN_TIME = {
    "V1 для 22 тверджень (4 пошукові запити + 22 рішення)": 45,
    "V3: звірка вердиктів двох моделей, 22 твердження": 15,
    "CoVe: розбір 10 відповідей і переписування трьох документів": 40,
}


def main() -> None:
    rows = list(csv.DictReader(open(HUB / "claims/claims.csv", encoding="utf-8")))
    ver = list(csv.DictReader(open(HUB / "claims/verification.csv", encoding="utf-8")))

    s1 = [r for r in rows if r["session"] == "session_01"]
    n = len(s1)
    cnt = Counter(r["status"] for r in s1)
    print("=== 1. Частки статусів (експертна сесія 01, після V1+V3+CoVe)")
    for st in ("verified", "rejected", "pending"):
        print(f"    {st:9}: {cnt[st]:2}  ({cnt[st]/n*100:.1f} %)")
    print(f"    разом    : {n:2}  ({sum(cnt.values())/n*100:.1f} %)")

    print("\n=== 2. κ Коена між моделями A і B (22 твердження)")
    la = [r["model_A_verdict"] for r in ver]
    lb = [r["model_B_verdict"] for r in ver]
    m = len(ver)
    po = sum(x == y for x, y in zip(la, lb)) / m
    ca, cb = Counter(la), Counter(lb)
    pe = sum((ca[k] / m) * (cb[k] / m) for k in set(la) | set(lb))
    k = (po - pe) / (1 - pe)
    print(f"    Po = {po:.3f}; Pe = {pe:.3f}; κ = {k:.3f}")

    print("\n=== 3. Точність вердикту «support» відносно рішення людини")
    final = {r["id"]: r["status"] for r in s1}
    for name, labels in (("модель A (opus)", la), ("модель B (haiku)", lb)):
        sup = [v["id"] for v, lab in zip(ver, labels) if lab == "support"]
        hit = sum(1 for i in sup if final.get(i) == "verified")
        print(f"    {name:18}: support для {len(sup):2} тверджень, "
              f"з них людина підтвердила {hit:2} → точність {hit/len(sup)*100:.1f} %")
        rej = [v["id"] for v, lab in zip(ver, labels) if lab == "reject"]
        hit_r = sum(1 for i in rej if final.get(i) == "rejected")
        print(f"    {'':18}  reject для {len(rej):2}, збіг із людиною {hit_r}")

    print("\n=== 4. Вартість сесій (виміряно)")
    tot_t = tot_s = 0
    for label, (tok, sec) in SESSION_COST.items():
        print(f"    {label:32} {tok:7,} токенів  {sec:4} с")
        tot_t += tok
        tot_s += sec
    print(f"    {'РАЗОМ':32} {tot_t:7,} токенів  {tot_s:4} с "
          f"({tot_s/60:.1f} хв машинного часу)")

    print("\n=== 5. Час верифікації людиною (оцінка, не хронометраж)")
    tot_h = sum(HUMAN_TIME.values())
    for label, mins in HUMAN_TIME.items():
        print(f"    {label}: {mins} хв")
    print(f"    разом {tot_h} хв на {n} тверджень → "
          f"{tot_h/n:.1f} хв на твердження")

    out = {
        "statuses": dict(cnt), "n_claims_session01": n,
        "kappa": round(k, 3), "po": round(po, 3), "pe": round(pe, 3),
        "cost_tokens_total": tot_t, "cost_seconds_total": tot_s,
        "human_minutes_total": tot_h,
        "human_minutes_per_claim": round(tot_h / n, 1),
    }
    (HUB / "tmp/metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                          encoding="utf-8")


if __name__ == "__main__":
    main()
