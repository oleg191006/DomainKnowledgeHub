# -*- coding: utf-8 -*-
"""Рушій прямого ланцюжкування для бази правил культурної спадщини (ЛР04 Р4).

Особливості:
* пряме ланцюжкування з повторними проходами: дії правил записують нові факти у слот
  `conclusions`, тому правила можуть спрацьовувати від висновків попередніх;
* стратегія розв'язання конфліктів: спершу за пріоритетом (менше число — вище),
  далі за специфічністю (більше умов — важливіше), далі за порядком у базі;
* пояснення: для кожного висновку зберігається ланцюжок правил, які до нього призвели;
* винятки: правило з непорожнім полем `exception` не спрацьовує, якщо у фактах стоїть
  прапорець `exception_<rule_id>` зі значенням true — так виняток лишається явним
  рішенням людини, а не прихованою умовою.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any

HUB = pathlib.Path(__file__).resolve().parents[1]


def _as_number(x: Any) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def evaluate(cond: dict, facts: dict) -> bool:
    """Істинність однієї умови. Невідомий слот означає «умова не виконана»,
    а не помилку: база правил має працювати на неповних даних."""
    slot, op, want = cond["slot"], cond["op"], cond["value"]
    if slot not in facts:
        return False
    got = facts[slot]

    if op == "=":
        return got == want
    if op == "!=":
        return got != want
    if op == "in":
        return got in want if isinstance(want, (list, tuple, set)) else False
    if op == "contains":
        return isinstance(got, str) and str(want) in got

    a, b = _as_number(got), _as_number(want)
    if a is None or b is None:
        return False
    return {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]


@dataclass
class Firing:
    rule_id: str
    priority: int
    specificity: int
    actions: list[str]
    cycle: int


@dataclass
class Result:
    fired: list[Firing] = field(default_factory=list)
    conclusions: list[str] = field(default_factory=list)
    suppressed: list[tuple[str, str]] = field(default_factory=list)   # (rule_id, причина)

    @property
    def fired_ids(self) -> list[str]:
        return [f.rule_id for f in self.fired]


class RuleEngine:
    def __init__(self, rules: list[dict], max_cycles: int = 5):
        self.rules = rules
        self.max_cycles = max_cycles

    # ---- стратегія розв'язання конфліктів ----
    @staticmethod
    def _order_key(rule: dict) -> tuple[int, int, str]:
        # 1) пріоритет (менше = важливіше); 2) специфічність (більше умов = важливіше);
        # 3) id для детермінованості
        return (rule.get("priority", 3), -len(rule["if"]), rule["id"])

    # слоти, значення яких походять із системи моніторингу
    SENSOR_SLOTS = {"rh", "temperature", "daily_rh_swing", "illuminance_lux"}
    STALE_AFTER_HOURS = 6

    def _is_stale(self, rule: dict, facts: dict) -> bool:
        """Метаправило достовірності даних (пріоритет 0, вище за будь-яке правило бази).

        Якщо датчик мовчить довше за STALE_AFTER_HOURS, показники rh/temperature — це останні
        відомі, тобто застарілі значення. Правила, що на них спираються, призупиняються до
        підтвердження ручним заміром: інакше рушій запускає осушення за показом, якого вже
        кілька годин не існує (ситуація trap5).
        """
        if facts.get("sensor_silence_hours", 0) < self.STALE_AFTER_HOURS:
            return False
        return any(c["slot"] in self.SENSOR_SLOTS for c in rule["if"])

    def run(self, facts: dict) -> Result:
        facts = dict(facts)
        facts.setdefault("conclusions", [])
        res = Result()
        done: set[str] = set()

        for cycle in range(1, self.max_cycles + 1):
            agenda = []
            for rule in self.rules:
                if rule["id"] in done:
                    continue
                if not all(evaluate(c, facts) for c in rule["if"]):
                    continue
                if self._is_stale(rule, facts):
                    res.suppressed.append((rule["id"], "дані моніторингу застарілі "
                                           f'({facts.get("sensor_silence_hours")} год без показів)'))
                    done.add(rule["id"])
                    continue
                if rule.get("exception") and facts.get(f'exception_{rule["id"]}') is True:
                    res.suppressed.append((rule["id"], "спрацював виняток правила"))
                    done.add(rule["id"])
                    continue
                agenda.append(rule)

            if not agenda:
                break

            agenda.sort(key=self._order_key)
            for rule in agenda:
                done.add(rule["id"])
                res.fired.append(Firing(rule["id"], rule.get("priority", 3),
                                        len(rule["if"]), list(rule["then"]), cycle))
                for action in rule["then"]:
                    res.conclusions.append(action)
                    facts["conclusions"].append(action)
        return res

    def explain(self, facts: dict, result: Result) -> str:
        """Текстове пояснення: які умови справдилися і що з цього випливло."""
        if not result.fired:
            return "Жодне правило не спрацювало: усі умови бази хибні на цих фактах."
        lines = []
        by_id = {r["id"]: r for r in self.rules}
        for f in result.fired:
            rule = by_id[f.rule_id]
            conds = [f'{c["slot"]} {c["op"]} {c["value"]} '
                     f'(факт: {facts.get(c["slot"], "—")})' for c in rule["if"]]
            lines.append(f'[прохід {f.cycle}] {f.rule_id} (пріоритет {f.priority}, '
                         f'умов {f.specificity})')
            lines.append("   умови: " + "; ".join(conds))
            lines.append("   висновки: " + "; ".join(f.actions))
        for rid, why in result.suppressed:
            lines.append(f"[придушено] {rid}: {why}")
        return "\n".join(lines)


def load_rules(path: pathlib.Path | None = None) -> list[dict]:
    p = path or HUB / "models" / "rules.json"
    return json.loads(p.read_text(encoding="utf-8"))["rules"]


if __name__ == "__main__":
    eng = RuleEngine(load_rules())
    demo_facts = {"object_class": "movable", "material": "wood_panel", "rh": 78,
                  "rh_duration_days": 2, "temperature": 22, "mold_signs": False}
    out = eng.run(demo_facts)
    print("спрацювали:", ", ".join(out.fired_ids) or "—")
    print(eng.explain(demo_facts, out))
