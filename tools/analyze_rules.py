# -*- coding: utf-8 -*-
"""Аналіз бази правил: надлишковість, суперечності, недосяжність (ЛР04 Р5).

Перевірки:
1. ДУБЛІКАТИ — правила з однаковою множиною умов.
2. ПОГЛИНАННЯ — умови одного правила є підмножиною умов іншого (специфічніше правило
   ніколи не додає нічого нового, якщо дії збігаються).
3. СУПЕРЕЧНОСТІ — правила, що можуть спрацювати разом, але дають протилежні дії
   (пара «заборонити X» / «увімкнути X»).
4. НЕДОСЯЖНІСТЬ — умови, які не можуть справдитися одночасно (напр. rh > 75 І rh < 40).
5. СИРОТИ-СЛОТИ — слоти, що використовуються лише в одному правилі: ознака друкарської
   помилки в імені слота.

Запуск: python tools/analyze_rules.py
"""
import json
import pathlib
import re
from collections import defaultdict
from itertools import combinations

HUB = pathlib.Path(__file__).resolve().parents[1]
NEGATION = [("заборонити", "увімкнути"), ("заборонити", "знизити"),
            ("обмежити", "збільшити"), ("зняти", "залишити")]
NUMERIC_OPS = {">", ">=", "<", "<="}


def cond_key(c: dict) -> tuple:
    v = tuple(c["value"]) if isinstance(c["value"], list) else c["value"]
    return (c["slot"], c["op"], v)


def intervals_conflict(conds: list[dict]) -> str | None:
    """Чи можуть числові умови одного правила справдитися одночасно."""
    bounds: dict[str, list[float]] = defaultdict(lambda: [float("-inf"), float("inf")])
    for c in conds:
        if c["op"] not in NUMERIC_OPS or not isinstance(c["value"], (int, float)):
            continue
        lo, hi = bounds[c["slot"]]
        if c["op"] in (">", ">="):
            lo = max(lo, float(c["value"]))
        else:
            hi = min(hi, float(c["value"]))
        bounds[c["slot"]] = [lo, hi]
    for slot, (lo, hi) in bounds.items():
        if lo > hi:
            return f"слот {slot}: вимагається одночасно > {lo} і < {hi}"
    return None


def may_cofire(a: dict, b: dict) -> bool:
    """Груба перевірка сумісності умов двох правил за числовими межами й рівностями."""
    merged = a["if"] + b["if"]
    if intervals_conflict(merged):
        return False
    eq: dict[str, set] = defaultdict(set)
    for c in merged:
        if c["op"] == "=" and not isinstance(c["value"], list):
            eq[c["slot"]].add(c["value"])
    return all(len(v) <= 1 for v in eq.values())


def stems(text: str, after: str, take: int = 4) -> set[str]:
    """Основи перших слів після ключового дієслова: порівнюємо предмет дії, а не порядок слів."""
    tail = re.sub(rf".*?{after}\s*", "", text, count=1).split()[:take]
    return {w.strip(".,;:«»").lower()[:6] for w in tail if len(w) > 3}


def opposite(then_a: list[str], then_b: list[str]) -> str | None:
    """Пара дій, що скасовують одна одну: «заборонити X» проти «увімкнути X».

    Порівнюємо не перше слово після дієслова, а перетин основ кількох перших слів:
    «заборонити інтенсивне осушення» і «увімкнути осушення в інтенсивному режимі»
    описують ту саму дію різним порядком слів.
    """
    for sa in then_a:
        for sb in then_b:
            for neg, pos in NEGATION:
                if neg in sa and pos in sb:
                    if stems(sa, neg) & stems(sb, pos):
                        return f"«{sa}» ↔ «{sb}»"
    return None



MODIFIERS = [("повільн", "інтенсивн"), ("повільн", "негайн"), ("обмежити", "збільшити"),
             ("знизити", "підняти"), ("заборонити", "дозволити")]


def incompatible_modifiers(then_a: list[str], then_b: list[str]) -> str | None:
    """Обидва правила велять робити те саме, але з протилежними характеристиками.

    Це окремий і найнебезпечніший вид конфлікту: формально дії не суперечать (обидва
    приписують осушення), тому пара не ловиться перевіркою «заборонити / увімкнути»,
    але виконавець отримує взаємовиключні вказівки щодо темпу або обсягу.
    """
    for sa in then_a:
        for sb in then_b:
            common = {w.strip(".,;:«»").lower()[:6] for w in sa.split() if len(w) > 4} &                      {w.strip(".,;:«»").lower()[:6] for w in sb.split() if len(w) > 4}
            if not common:
                continue
            for m1, m2 in MODIFIERS:
                if (m1 in sa.lower() and m2 in sb.lower()) or (m2 in sa.lower() and m1 in sb.lower()):
                    return f"«{sa}» ↔ «{sb}» (спільний предмет дії: {', '.join(sorted(common))})"
    return None


def main() -> None:
    data = json.loads((HUB / "models/rules.json").read_text(encoding="utf-8"))
    rules = data["rules"]
    problems: list[tuple[str, str, str]] = []

    # 1. дублікати та поглинання
    for a, b in combinations(rules, 2):
        ka, kb = {cond_key(c) for c in a["if"]}, {cond_key(c) for c in b["if"]}
        if ka == kb:
            problems.append(("дублікат", f'{a["id"]} / {b["id"]}', "однакові умови"))
        elif ka < kb and set(a["then"]) >= set(b["then"]):
            problems.append(("поглинання", f'{b["id"]} ⊂ {a["id"]}',
                             f'{b["id"]} специфічніше, але не додає нових дій'))

    # 2. суперечності
    for a, b in combinations(rules, 2):
        if not may_cofire(a, b):
            continue
        conflict = opposite(a["then"], b["then"]) or opposite(b["then"], a["then"])
        if conflict:
            problems.append(("суперечність", f'{a["id"]} / {b["id"]}', conflict))
            continue
        mod = incompatible_modifiers(a["then"], b["then"])
        if mod:
            problems.append(("несумісні характеристики", f'{a["id"]} / {b["id"]}', mod))

    # 3. недосяжні правила
    for r in rules:
        why = intervals_conflict(r["if"])
        if why:
            problems.append(("недосяжне", r["id"], why))

    # 4. слоти-сироти
    usage: dict[str, list[str]] = defaultdict(list)
    for r in rules:
        for c in r["if"]:
            usage[c["slot"]].append(r["id"])
    orphans = [(slot, ids[0]) for slot, ids in sorted(usage.items()) if len(ids) == 1]

    print(f"проаналізовано правил: {len(rules)}; знайдено проблем: {len(problems)}")
    by_kind: dict[str, int] = defaultdict(int)
    for kind, where, why in problems:
        by_kind[kind] += 1
        print(f"  [{kind}] {where}: {why}")
    print("\nпідсумок за типами:", dict(by_kind))

    out = HUB / "tmp" / "rules_analysis.json"
    out.write_text(json.dumps(
        [{"kind": k, "where": w, "why": y} for k, w, y in problems],
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"збережено: {out.relative_to(HUB)}")


if __name__ == "__main__":
    main()
