# -*- coding: utf-8 -*-
"""Фрейми предметної області з наслідуванням і значеннями за замовчуванням (ЛР04 Р3).

Ієрархія (три рівні наслідування):

    HeritageItem                     — спільний корінь
    ├── MovableItem                  — рухома спадщина
    │   ├── PaintingItem             — станковий живопис
    │   │   └── IconItem             — ікона на дерев'яній основі
    │   └── PaperItem                — графіка, акварель, документи
    └── ImmovableMonument            — нерухома пам'ятка
        └── ArchitecturalMonument    — пам'ятка архітектури

Значення за замовчуванням успадковуються і перевизначаються нижчими рівнями: наприклад,
допустима освітленість у корені не задана, у живопису — 200 лк, у графіки — 50 лк.

Фрейми й правила пов'язані через слоти: метод `to_facts()` перетворює екземпляр фрейма на
словник фактів, який подається рушію (`engine/engine.py`), тому правила оперують саме
слотами фреймів, а не довільними іменами.

Запуск самоперевірки: python models/frames.py
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ConditionGrade = Literal["good", "fair", "poor", "critical"]


class HeritageItem(BaseModel):
    """Корінь ієрархії: те, що є спільним для будь-якого об'єкта спадщини."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    uid: str = Field(pattern=r"^[a-z]{3}-\d{3}$", description="незмінний технічний ключ (ADR-002)")
    registry_number: str = Field(min_length=1, description="обліковий номер із документів")
    title: str = Field(min_length=2)
    condition_grade: ConditionGrade = "good"
    object_class: Literal["movable", "immovable"] = "movable"

    # значення за замовчуванням, які перевизначають нащадки
    rh_min: float = 40.0
    rh_max: float = 60.0
    temp_min: float = 16.0
    temp_max: float = 25.0
    illuminance_max_lux: Optional[float] = None
    material: Optional[str] = None

    @model_validator(mode="after")
    def corridor_is_sane(self):
        if self.rh_min >= self.rh_max:
            raise ValueError(f"{self.uid}: rh_min має бути менший за rh_max")
        if self.temp_min >= self.temp_max:
            raise ValueError(f"{self.uid}: temp_min має бути менший за temp_max")
        return self

    def to_facts(self, **measured: Any) -> dict:
        """Слоти фрейма + поточні виміряні значення → факти для рушія правил."""
        facts = {
            "object_class": self.object_class,
            "condition_grade": self.condition_grade,
            "rh_min": self.rh_min, "rh_max": self.rh_max,
            "temp_min": self.temp_min, "temp_max": self.temp_max,
        }
        if self.material:
            facts["material"] = self.material
        if self.illuminance_max_lux is not None:
            facts["illuminance_max_lux"] = self.illuminance_max_lux
        facts.update(measured)
        return facts


class MovableItem(HeritageItem):
    """Рухома спадщина: має місце зберігання й історію втручань."""

    object_class: Literal["movable", "immovable"] = "movable"
    storage_room: str = "фондосховище"
    last_treatment_years: int = Field(default=0, ge=0, le=500)
    damage_area_cm2: float = Field(default=0.0, ge=0.0)

    def to_facts(self, **measured: Any) -> dict:
        facts = super().to_facts()
        facts.update({"last_treatment_years": self.last_treatment_years,
                      "damage_area_cm2": self.damage_area_cm2})
        facts.update(measured)
        return facts


class PaintingItem(MovableItem):
    """Станковий живопис: вужчий температурний коридор і межа освітленості 200 лк."""

    object_type: Literal["painting"] = "painting"
    illuminance_max_lux: Optional[float] = 200.0
    temp_min: float = 18.0
    temp_max: float = 22.0
    support: Literal["wood_panel", "canvas"] = "canvas"

    def to_facts(self, **measured: Any) -> dict:
        facts = super().to_facts()
        facts["object_type"] = self.object_type
        facts.setdefault("material", self.support)
        facts.update(measured)
        return facts


class IconItem(PaintingItem):
    """Ікона: дерев'яна основа, вужчий коридор вологості, обов'язковий шар ґрунту."""

    support: Literal["wood_panel", "canvas"] = "wood_panel"
    material: Optional[str] = "wood_panel"
    rh_min: float = 45.0
    rh_max: float = 55.0
    ground_layer: Literal["левкас", "емульсійний", "невідомо"] = "левкас"

    @model_validator(mode="after")
    def icon_is_on_wood(self):
        if self.support != "wood_panel":
            raise ValueError(f"{self.uid}: ікона за визначенням має дерев'яну основу")
        return self


class PaperItem(MovableItem):
    """Графіка, акварель, документи: світлочутливі, межа 50 лк."""

    illuminance_max_lux: Optional[float] = 50.0
    material: Optional[str] = "paper"


class ImmovableMonument(HeritageItem):
    """Нерухома пам'ятка: має категорію, зону охорони та обліковий статус."""

    object_class: Literal["movable", "immovable"] = "immovable"
    heritage_category: Literal["national", "local", "none"] = "local"
    heritage_status: Literal["registered", "not_registered"] = "registered"
    in_protection_zone: bool = True
    illuminance_max_lux: Optional[float] = None

    @model_validator(mode="after")
    def category_matches_status(self):
        if self.heritage_category != "none" and self.heritage_status == "not_registered":
            # не помилка даних, а стан, який має породити дію: правило r20
            object.__setattr__(self, "_needs_registration", True)
        return self

    def to_facts(self, **measured: Any) -> dict:
        facts = super().to_facts()
        facts.update({"heritage_category": self.heritage_category,
                      "heritage_status": self.heritage_status,
                      "in_protection_zone": self.in_protection_zone})
        facts.update(measured)
        return facts


class ArchitecturalMonument(ImmovableMonument):
    """Пам'ятка архітектури: додає висоту навколишньої забудови як чинник впливу."""

    new_building_height_m: float = Field(default=0.0, ge=0.0)
    construction_works_nearby: bool = False

    def to_facts(self, **measured: Any) -> dict:
        facts = super().to_facts()
        facts.update({"new_building_height_m": self.new_building_height_m,
                      "construction_works_nearby": self.construction_works_nearby})
        facts.update(measured)
        return facts


# ------------------------------------------------------------------ екземпляри
INSTANCES: list[HeritageItem] = [
    IconItem(uid="icn-001", registry_number="Ж-1043", title="Ікона «Одигітрія», XVII ст.",
             condition_grade="poor", damage_area_cm2=12.0, last_treatment_years=18,
             storage_room="зал 3"),
    IconItem(uid="icn-002", registry_number="Ж-1044", title="Ікона «Спас у славі»",
             ground_layer="емульсійний", storage_room="фондосховище 1"),
    IconItem(uid="icn-003", registry_number="Ж-1101", title="Намісна ікона, XVIII ст.",
             condition_grade="critical", damage_area_cm2=240.0, last_treatment_years=35),
    PaintingItem(uid="pnt-001", registry_number="Ж-2051", title="Портрет невідомого, XIX ст.",
                 support="canvas", condition_grade="fair"),
    PaintingItem(uid="pnt-002", registry_number="Ж-2052", title="Пейзаж з млином",
                 support="canvas", last_treatment_years=3),
    PaperItem(uid="ppr-001", registry_number="Гр-311", title="Акварель «Краєвид Львова»"),
    PaperItem(uid="ppr-002", registry_number="Гр-312", title="Гравюра, XVIII ст.",
              condition_grade="fair"),
    MovableItem(uid="mov-001", registry_number="ДУ-77", title="Різьблений свічник",
                material="wood", storage_room="фондосховище 2"),
    ArchitecturalMonument(uid="arc-001", registry_number="1/1-Лв",
                          title="Собор святого Юра", heritage_category="national",
                          new_building_height_m=18.0, construction_works_nearby=True),
    ArchitecturalMonument(uid="arc-002", registry_number="1/2-Лв",
                          title="Кам'яниця на пл. Ринок", heritage_category="local",
                          condition_grade="critical"),
    ImmovableMonument(uid="imm-001", registry_number="б/н",
                      title="Крипта під костелом", heritage_category="local",
                      heritage_status="not_registered"),
    ArchitecturalMonument(uid="arc-003", registry_number="1/3-Лв",
                          title="Дзвіниця", heritage_category="local",
                          in_protection_zone=True, new_building_height_m=6.0),
]


def self_check() -> None:
    import sys
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from engine.engine import RuleEngine, load_rules

    print(f"екземплярів: {len(INSTANCES)} — усі пройшли валідацію схеми")
    for cls in (HeritageItem, MovableItem, PaintingItem, IconItem, PaperItem,
                ImmovableMonument, ArchitecturalMonument):
        n = sum(1 for i in INSTANCES if isinstance(i, cls))
        print(f"  {cls.__name__:22} екземплярів (з нащадками): {n}")

    print("\nуспадкування значень за замовчуванням:")
    icon, paint, paper = INSTANCES[0], INSTANCES[3], INSTANCES[5]
    for item in (icon, paint, paper):
        print(f"  {item.uid}: RH {item.rh_min}–{item.rh_max} %, "
              f"t {item.temp_min}–{item.temp_max} °C, "
              f"освітленість ≤ {item.illuminance_max_lux} лк")

    def why(exc: Exception) -> str:
        """Перший змістовний рядок помилки без службового посилання pydantic."""
        for line in str(exc).splitlines():
            line = line.strip()
            if line and not line.startswith(("For further", "http")) and "validation error" not in line:
                return line.split(" [type=")[0][:95]
        return str(exc)[:95]

    print("\nперевірка обмежень:")
    checks = (
        ("ікона на полотні", lambda: IconItem(uid="icn-009", registry_number="X",
                                              title="Ікона на полотні", support="canvas")),
        ("коридор RH навиворіт", lambda: HeritageItem(uid="bad-001", registry_number="X",
                                                      title="Тест", rh_min=70, rh_max=50)),
        ("uid не за шаблоном", lambda: HeritageItem(uid="XX1", registry_number="X", title="Тест")),
        ("невідомий стан", lambda: MovableItem(uid="mov-009", registry_number="X",
                                               title="Тест", condition_grade="жахливий")),
    )
    for label, make in checks:
        try:
            make()
            print(f"  ПОМИЛКА: «{label}» не відхилено")
        except Exception as exc:
            print(f"  «{label}» відхилено: {why(exc)}")

    print("\nзв'язок фреймів і правил: слоти фрейма подаються рушію як факти")
    eng = RuleEngine(load_rules())
    facts = icon.to_facts(rh=78, rh_duration_days=2, temperature=21, mold_signs=False)
    out = eng.run(facts)
    print(f"  {icon.uid} ({icon.title}) за RH 78 % → спрацювали: {', '.join(out.fired_ids)}")
    print(f"  правило r15 використовує слот damage_area_cm2 фрейма MovableItem "
          f"(значення {icon.damage_area_cm2} см²)")
    facts2 = INSTANCES[2].to_facts(rh=50, temperature=20)
    out2 = eng.run(facts2)
    print(f"  {INSTANCES[2].uid} (стан critical, {INSTANCES[2].damage_area_cm2} см²) → "
          f"{', '.join(out2.fired_ids)}")


if __name__ == "__main__":
    self_check()
