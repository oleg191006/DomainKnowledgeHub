---
id: DOC-TEST-REPORT
title: Звіт про прогін автоматичних перевірок таксономії
owner: інженер знань
status: затверджено
version: 1
updated: 2026-10-25
lab: lab05
---

# Звіт про прогін автоматичних перевірок

Середовище прогону: Python 3.12.6, Windows 10,
pytest, rdflib, scikit-learn. Ті самі команди виконуються в CI на кожен push —
`.github/workflows/lint.yml`, кроки «Тести правил і таксономії» та «Метрики таксономії».

Команда: `pytest tests/ -v`

## 1. Що перевіряє кожен тест таксономії

| Тест | Що саме перевіряє | Критерій ЛР |
|---|---|---|
| `test_every_concept_has_preflabel` | у кожного концепту рівно один `skos:prefLabel` з міткою `@uk` | Р5 C1 |
| `test_no_cycles` | підйом від будь-якого вузла завершується коренем | Р4 C3 |
| `test_single_parent` | ідентифікатори унікальні, кожен батько існує | Р4 C3 |
| `test_levels_consistent` | рівень вузла дорівнює рівню батька плюс один | Р4 C3 |
| `test_no_junk_categories` | немає категорій «Інше», «Різне», «Додаткове» | Р3 C1 |
| `test_definitions_for_upper_levels` | вузли рівнів 1–2 мають визначення або принцип поділу | Р4 C2 |
| `test_division_principle_on_parents` | кожен вузол з дітьми оголошує принцип їх поділу | Р4 C3 |
| `test_no_single_child_splits` | немає поділу, що дає рівно одну дитину | Р3 C1 |
| `test_broader_matches_csv` | кожен `skos:broader` відповідає батьківському зв'язку таблиці | Р5 C1 |
| `test_external_links_verified` | ≥ 5 зовнішніх зв'язків, усі на простір імен Getty AAT | Р5 C4 |
| `test_external_links_have_note` | кожен зовнішній зв'язок має пояснення типу відповідності | Р5 C4 |
| `test_top_concepts` | верхні поняття оголошені в обидва боки | Р5 C1 |
| `test_every_node_has_definition` | визначення має кожен із 182 вузлів | Р4 C2 |
| `test_definition_in_skos` | усі визначення перенесено в граф із міткою `@uk` | Р5 C1 |

До них додаються 24 тести золотого набору правил із ЛР 4 (`tests/test_gold.py`), які
лишаються в тому самому прогоні: зміна таксономії не повинна ламати базу правил.

## 2. Повний вивід прогону

```
============================= test session starts =============================
collecting ... collected 38 items

tests/test_gold.py::test_model_scenarios[tc1] PASSED                     [  2%]
tests/test_gold.py::test_model_scenarios[tc2] PASSED                     [  5%]
tests/test_gold.py::test_model_scenarios[tc3] PASSED                     [  7%]
tests/test_gold.py::test_model_scenarios[tc4] PASSED                     [ 10%]
tests/test_gold.py::test_model_scenarios[tc5] PASSED                     [ 13%]
tests/test_gold.py::test_model_scenarios[tc6] PASSED                     [ 15%]
tests/test_gold.py::test_boundary_rh_exactly_60 PASSED                   [ 18%]
tests/test_gold.py::test_boundary_rh_just_above_60 PASSED                [ 21%]
tests/test_gold.py::test_boundary_rh_exactly_75_not_damp PASSED          [ 23%]
tests/test_gold.py::test_boundary_sensor_silence_exactly_6h PASSED       [ 26%]
tests/test_gold.py::test_boundary_illuminance_painting_exactly_200 PASSED [ 28%]
tests/test_gold.py::test_negative_normal_storage PASSED                  [ 31%]
tests/test_gold.py::test_negative_immovable_in_order PASSED              [ 34%]
tests/test_gold.py::test_negative_empty_facts PASSED                     [ 36%]
tests/test_gold.py::test_mold_rules_fire_before_climate PASSED           [ 39%]
tests/test_gold.py::test_mold_in_dry_room_does_not_order_drying PASSED   [ 42%]
tests/test_gold.py::test_exception_blocks_rule PASSED                    [ 44%]
tests/test_gold.py::test_planted_conflict_is_reachable PASSED            [ 47%]
tests/test_gold.py::test_insects_isolate_any_material PASSED             [ 50%]
tests/test_gold.py::test_stale_sensor_blocks_climate_rules PASSED        [ 52%]
tests/test_gold.py::test_visual_impact_needs_actual_works PASSED         [ 55%]
tests/test_gold.py::test_immovable_rules_do_not_touch_movable PASSED     [ 57%]
tests/test_gold.py::test_explanation_contains_chain PASSED               [ 60%]
tests/test_gold.py::test_unknown_slot_is_not_an_error PASSED             [ 63%]
tests/test_taxonomy.py::test_every_concept_has_preflabel PASSED          [ 65%]
tests/test_taxonomy.py::test_no_cycles PASSED                            [ 68%]
tests/test_taxonomy.py::test_single_parent PASSED                        [ 71%]
tests/test_taxonomy.py::test_levels_consistent PASSED                    [ 73%]
tests/test_taxonomy.py::test_no_junk_categories PASSED                   [ 76%]
tests/test_taxonomy.py::test_definitions_for_upper_levels PASSED         [ 78%]
tests/test_taxonomy.py::test_division_principle_on_parents PASSED        [ 81%]
tests/test_taxonomy.py::test_no_single_child_splits PASSED               [ 84%]
tests/test_taxonomy.py::test_broader_matches_csv PASSED                  [ 86%]
tests/test_taxonomy.py::test_external_links_verified PASSED              [ 89%]
tests/test_taxonomy.py::test_external_links_have_note PASSED             [ 92%]
tests/test_taxonomy.py::test_top_concepts PASSED                         [ 94%]
tests/test_taxonomy.py::test_every_node_has_definition PASSED            [ 97%]
tests/test_taxonomy.py::test_definition_in_skos PASSED                   [100%]

============================= 38 passed in 0.48s ==============================
```

## 3. Експорт SKOS

Команда: `python tools/export_skos.py`

```
вузлів у таксономії: 182
тріплетів у графі: 1240
верхніх понять: 5
altLabel: 101
definition: 182
зовнішніх зв'язків: 5
файл: models\taxonomy.ttl
```

## 4. Метрики

Команда: `python tools/taxonomy_metrics.py`

```
=== 1. Метрики версій
версія            вузлів  листків  глибина  ширина  покриття  «Інше»  MECE
експертна            150      126        3    6.04     84.0%    0.0%     0
LLM                  187      146        3    4.39     96.7%    0.0%     0
кластеризація        158      150        2   18.75    100.0%    0.0%     0
підсумкова           182      149        4    5.36     99.3%    0.0%     0

=== 2. ARI відносно експертної версії
  LLM: ARI = 0.719 (на 122 спільних термінах)
  кластеризація: ARI = 0.066 (на 126 спільних термінах)
  підсумкова: ARI = 0.936 (на 126 спільних термінах)

=== 3. κ Коена між двома розмітниками (30 термінів)
  термінів: 30; збігів: 26 (86.7 %)
  κ Коена = 0.829
    розбіжність: «аноксія» — розмітник 1: Дія з об'єктом | розмітник 2: Умови та чинники
    розбіжність: «золотий набір» — розмітник 1: Запис знання | розмітник 2: Об'єкт спадщини
    розбіжність: «охоронний договір» — розмітник 1: Запис знання | розмітник 2: Суб'єкт і відповідальність
    розбіжність: «цифрова копія» — розмітник 1: Об'єкт спадщини | розмітник 2: Запис знання

метрики збережено: tmp/taxonomy_metrics.json
```

## 5. Висновок

Усі 38 тестів проходять. Жодна перевірка не позначена як пропущена чи очікувано
неуспішна (`skip`, `xfail`) — це свідомо: тест, який дозволено не проходити, не є
перевіркою.

Найкориснішими виявилися не ті тести, що перевіряють формат, а два структурні:
`test_no_single_child_splits` і `test_division_principle_on_parents`. Саме вони
не пропускають типову помилку — створення категорії «для галочки», у якій лежить
один термін і принцип поділу якої не сформульовано.
