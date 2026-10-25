# -*- coding: utf-8 -*-
"""Золотий набір тестів бази правил (ЛР04 Р4).

Набір складається з трьох частин:
* сценарії, запропоновані моделлю (tc1–tc6 у models/rules.json);
* граничні випадки, дописані людиною: значення рівно на порозі правила;
* негативні випадки: ситуації, у яких не повинно спрацювати жодне правило.

Запуск: pytest tests/ -v
"""
import json
import pathlib
import sys

import pytest

HUB = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HUB))

from engine.engine import RuleEngine, load_rules  # noqa: E402

RULES = load_rules()
ENGINE = RuleEngine(RULES)
MODEL_TESTS = json.loads((HUB / "models/rules.json").read_text(encoding="utf-8"))["tests"]

NORMAL = {
    "object_class": "movable", "material": "wood_panel", "object_type": "painting",
    "rh": 50, "rh_duration_days": 0, "temperature": 20, "illuminance_lux": 150,
    "daily_rh_swing": 3, "daylight_direct": False, "condition_grade": "good",
    "damage_area_cm2": 0, "last_treatment_years": 4, "mold_signs": False,
    "insect_signs": False, "visitors_per_hour": 20, "sensor_silence_hours": 0,
    "air_circulation": "normal",
}


def fired(facts: dict) -> set[str]:
    return set(ENGINE.run(facts).fired_ids)


# ---------------------------------------------------------------- сценарії моделі
@pytest.mark.parametrize("case", MODEL_TESTS, ids=[t["id"] for t in MODEL_TESTS])
def test_model_scenarios(case):
    """Сценарії, які запропонувала модель разом із правилами."""
    got = fired(case["facts"])
    expected = set(case["expect_fired"])
    assert got == expected, (f'{case["id"]}: очікували {sorted(expected)}, '
                             f'отримали {sorted(got)} — {case["note"]}')


# ---------------------------------------------------------------- граничні випадки
def test_boundary_rh_exactly_60():
    """RH рівно 60 % — межа коридору. Правило r01 має умову «> 60», тому не спрацьовує."""
    facts = NORMAL | {"rh": 60}
    assert "r01" not in fired(facts)


def test_boundary_rh_just_above_60():
    """RH 60,1 % — на крок вище межі: r01 має спрацювати."""
    facts = NORMAL | {"rh": 60.1}
    assert "r01" in fired(facts)


def test_boundary_rh_exactly_75_not_damp():
    """RH рівно 75 % — межа вогкості. r02 вимагає «> 75», тому стан вогкості не оголошується."""
    facts = NORMAL | {"rh": 75, "rh_duration_days": 3}
    out = fired(facts)
    assert "r02" not in out and "r01" in out


def test_boundary_sensor_silence_exactly_6h():
    """Тиша датчика рівно 6 годин: умова «>= 6», тому правило r21 спрацьовує."""
    facts = NORMAL | {"sensor_silence_hours": 6}
    assert "r21" in fired(facts)


def test_boundary_illuminance_painting_exactly_200():
    """200 лк для живопису — верхня межа орієнтиру; умова «> 200» не виконується."""
    facts = NORMAL | {"illuminance_lux": 200}
    assert "r09" not in fired(facts)


# ---------------------------------------------------------------- негативні випадки
def test_negative_normal_storage():
    """Еталонні умови зберігання: жодне правило не повинно спрацювати."""
    assert fired(NORMAL) == set()


def test_negative_immovable_in_order():
    """Облікована пам'ятка в доброму стані без робіт поблизу: тиша."""
    facts = {"object_class": "immovable", "heritage_category": "local",
             "heritage_status": "registered", "in_protection_zone": True,
             "construction_works_nearby": False, "new_building_height_m": 6,
             "condition_grade": "good"}
    assert fired(facts) == set()


def test_negative_empty_facts():
    """Порожні факти: рушій не повинен падати й не повинен нічого вивести."""
    assert fired({}) == set()


# ---------------------------------------------------------------- змістовні перевірки
def test_mold_rules_fire_before_climate():
    """Правила групи біоризиків (пріоритет 1) мають випереджати кліматичні.

    Після виправлення пастки trap2 правило r11 відповідає лише за ізоляцію, а приведення
    вологості винесено в r25 з умовою rh > 50, тому першим спрацьовує специфічніше r25.
    """
    facts = NORMAL | {"rh": 68, "mold_signs": True}
    out = ENGINE.run(facts)
    assert out.fired_ids[0] in {"r11", "r25"}, f"першим спрацювало {out.fired_ids[0]}"
    assert out.fired_ids.index("r11") < out.fired_ids.index("r01")


def test_mold_in_dry_room_does_not_order_drying():
    """Пастка trap2: у пересушеному сховищі правило біоризиків не повинно вимагати осушення."""
    facts = NORMAL | {"rh": 37, "mold_signs": True}
    out = fired(facts)
    assert "r11" in out, "ізоляція має спрацювати"
    assert "r25" not in out, "приведення вологості вниз у пересушеному приміщенні — помилка"
    assert "r04" in out, "натомість має спрацювати зволоження"


def test_exception_blocks_rule():
    """Явно виставлений виняток придушує правило, і це видно у звіті рушія."""
    facts = NORMAL | {"rh": 30, "exception_r04": True}
    out = ENGINE.run(facts)
    assert "r04" not in out.fired_ids
    assert any(rid == "r04" for rid, _ in out.suppressed)


def test_planted_conflict_is_reachable():
    """Закладений конфлікт r02/r03 справді відтворюється на тих самих фактах."""
    facts = NORMAL | {"rh": 78, "rh_duration_days": 2}
    out = fired(facts)
    assert {"r02", "r03"} <= out, "конфліктна пара не спрацювала разом"


def test_insects_isolate_any_material():
    """Пастка trap4: ізоляція при комахах має спрацьовувати за будь-якого матеріалу.

    У початковій редакції r12 вимагало material contains «wood», тому база мовчала при
    ураженні тканини чи паперу. Після виправлення ізоляція (r12) спрацьовує завжди, а спосіб
    обробки обирають похідні правила: r23 для деревини, r24 для органіки іншого типу.
    """
    wood = fired(NORMAL | {"material": "wood_panel", "insect_signs": True})
    assert {"r12", "r23"} <= wood and "r24" not in wood

    for material in ("textile", "paper", "canvas"):
        out = fired(NORMAL | {"material": material, "insect_signs": True})
        assert "r12" in out, f"база мовчить при комахах у матеріалі {material}"
        assert "r24" in out and "r23" not in out


def test_stale_sensor_blocks_climate_rules():
    """Пастка trap5: при мовчанні датчика кліматичні правила призупиняються."""
    facts = NORMAL | {"rh": 79, "rh_duration_days": 2, "temperature": 26,
                      "sensor_silence_hours": 8}
    out = ENGINE.run(facts)
    assert out.fired_ids == ["r21"], f"спрацювало зайве: {out.fired_ids}"
    assert {"r01", "r02"} <= {rid for rid, _ in out.suppressed}


def test_visual_impact_needs_actual_works():
    """Пастка trap3: оцінка візуального впливу не вимагається без фактичних робіт."""
    base = {"object_class": "immovable", "heritage_category": "local",
            "heritage_status": "registered", "in_protection_zone": True,
            "new_building_height_m": 16, "condition_grade": "good"}
    assert "r18" not in fired(base | {"construction_works_nearby": False})
    assert "r18" in fired(base | {"construction_works_nearby": True})


def test_immovable_rules_do_not_touch_movable():
    """Правила для нерухомих пам'яток не повинні спрацьовувати на музейному предметі."""
    facts = NORMAL | {"in_protection_zone": True, "construction_works_nearby": True}
    out = fired(facts)
    assert "r17" not in out, "правило для пам'яток спрацювало на рухомому предметі"


def test_explanation_contains_chain():
    """Функція пояснення показує і умови, і висновки."""
    facts = NORMAL | {"rh": 78, "rh_duration_days": 2}
    out = ENGINE.run(facts)
    text = ENGINE.explain(facts, out)
    assert "умови:" in text and "висновки:" in text and "r02" in text


def test_unknown_slot_is_not_an_error():
    """Невідомий слот не ламає рушій: умова просто вважається невиконаною."""
    facts = {"material": "wood_panel"}            # немає жодного числового слота
    assert fired(facts) == set()
