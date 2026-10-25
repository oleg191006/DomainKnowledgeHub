# -*- coding: utf-8 -*-
"""Автоматичні перевірки підсумкової таксономії та її SKOS-подання (ЛР05 Р5).

Запуск: pytest tests/test_taxonomy.py -v
"""
import csv
import pathlib
from collections import Counter, defaultdict

import pytest
from rdflib import SKOS, Graph, Literal, RDF

HUB = pathlib.Path(__file__).resolve().parents[1]
JUNK = {"інше", "різне", "додаткове", "other"}


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    with (HUB / "models/taxonomy_final.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def graph() -> Graph:
    g = Graph()
    g.parse(HUB / "models/taxonomy.ttl", format="turtle")
    return g


# ------------------------------------------------------------------ структура
def test_every_concept_has_preflabel(graph):
    """Кожен концепт має рівно один prefLabel з мовною міткою @uk."""
    concepts = list(graph.subjects(RDF.type, SKOS.Concept))
    assert concepts, "у графі немає жодного концепту"
    for c in concepts:
        labels = list(graph.objects(c, SKOS.prefLabel))
        assert len(labels) == 1, f"{c}: prefLabel має бути рівно один, а не {len(labels)}"
        assert isinstance(labels[0], Literal) and labels[0].language == "uk", \
            f"{c}: prefLabel без мовної мітки @uk"


def test_no_cycles(rows):
    """У дереві немає циклів: підйом від кожного вузла завершується коренем."""
    parent = {r["id"]: r["parent_id"] for r in rows}
    for start in parent:
        seen, cur = set(), start
        while parent.get(cur):
            assert cur not in seen, f"цикл через вузол {cur}"
            seen.add(cur)
            cur = parent[cur]


def test_single_parent(rows):
    """Кожен вузол має не більше одного батька, а ідентифікатори унікальні."""
    ids = [r["id"] for r in rows]
    dup = [i for i, c in Counter(ids).items() if c > 1]
    assert not dup, f"неунікальні id: {dup}"
    known = set(ids)
    for r in rows:
        if r["parent_id"]:
            assert r["parent_id"] in known, f'{r["id"]}: батька {r["parent_id"]} не існує'


def test_levels_consistent(rows):
    """Рівень вузла дорівнює рівню батька плюс один."""
    by_id = {r["id"]: r for r in rows}
    for r in rows:
        if r["parent_id"]:
            assert int(r["level"]) == int(by_id[r["parent_id"]]["level"]) + 1, \
                f'{r["id"]} ({r["label"]}): рівень не узгоджений із батьком'
        else:
            assert int(r["level"]) == 1


# ------------------------------------------------------------------ зміст
def test_no_junk_categories(rows):
    """У таксономії немає категорій-смітників «Інше» чи «Різне»."""
    junk = [r["label"] for r in rows if r["label"].strip().lower() in JUNK]
    assert not junk, f"категорії-смітники: {junk}"


def test_definitions_for_upper_levels(rows):
    """Вузли рівнів 1–2 мають визначення або оголошений принцип поділу."""
    for r in rows:
        if int(r["level"]) <= 2:
            assert r["definition"].strip() or r["division_principle"].strip(), \
                f'{r["label"]}: немає ні визначення, ні принципу поділу'


def test_division_principle_on_parents(rows):
    """Кожен вузол, що має дітей, оголошує принцип їх поділу."""
    children = defaultdict(list)
    for r in rows:
        children[r["parent_id"]].append(r)
    by_id = {r["id"]: r for r in rows}
    for pid, kids in children.items():
        if pid and len(kids) > 1:
            assert by_id[pid]["division_principle"].strip(), \
                f'{by_id[pid]["label"]}: {len(kids)} дітей без оголошеного принципу поділу'


def test_no_single_child_splits(rows):
    """Поділ, що дає рівно одну дитину, нічого не розділяє."""
    children = defaultdict(list)
    for r in rows:
        children[r["parent_id"]].append(r["label"])
    by_id = {r["id"]: r for r in rows}
    bad = [by_id[p]["label"] for p, kids in children.items() if p and len(kids) == 1]
    assert not bad, f"вузли з однією дитиною: {bad}"


# ------------------------------------------------------------------ SKOS
def test_broader_matches_csv(rows, graph):
    """Кожен зв'язок broader у графі відповідає батьківському зв'язку в таблиці."""
    expected = {(r["id"], r["parent_id"]) for r in rows if r["parent_id"]}
    got = set()
    for s, o in graph.subject_objects(SKOS.broader):
        got.add((str(s).rsplit("/", 1)[-1], str(o).rsplit("/", 1)[-1]))
    assert got == expected, f"розбіжність broader: {len(got ^ expected)} пар"


def test_external_links_verified(graph):
    """Зовнішніх зв'язків щонайменше п'ять, усі ведуть на простір імен Getty AAT."""
    links = []
    for prop in (SKOS.exactMatch, SKOS.closeMatch, SKOS.broadMatch):
        links += [str(o) for _, o in graph.subject_objects(prop)]
    assert len(links) >= 5, f"зовнішніх зв'язків лише {len(links)}"
    assert all(u.startswith("http://vocab.getty.edu/aat/") for u in links), \
        "є зв'язок поза простором імен AAT"
    for u in links:
        assert u.rsplit("/", 1)[-1].isdigit(), f"ідентифікатор AAT не числовий: {u}"


def test_external_links_have_note(graph):
    """Кожен зовнішній зв'язок супроводжується поясненням, чому саме такий тип відповідності."""
    for prop in (SKOS.exactMatch, SKOS.closeMatch, SKOS.broadMatch):
        for s, _ in graph.subject_objects(prop):
            notes = [str(n) for n in graph.objects(s, SKOS.editorialNote)]
            assert any("AAT" in n for n in notes), f"{s}: зовнішній зв'язок без пояснення"


def test_top_concepts(graph):
    """Верхні поняття оголошені в обидва боки: hasTopConcept і topConceptOf."""
    scheme = next(graph.subjects(RDF.type, SKOS.ConceptScheme))
    has_top = set(graph.objects(scheme, SKOS.hasTopConcept))
    top_of = set(graph.subjects(SKOS.topConceptOf, scheme))
    assert has_top == top_of and len(has_top) >= 4


def test_every_node_has_definition(rows):
    """Кожен вузол підсумкової таксономії має визначення (ЛР05 Р4, критерій C2)."""
    bad = [r["label"] for r in rows if not r["definition"].strip()]
    assert not bad, f"вузли без визначення: {len(bad)} — {bad[:5]}"


def test_definition_in_skos(graph):
    """Кожне визначення з таблиці перенесено в граф із мовною міткою @uk."""
    defs = list(graph.subject_objects(SKOS.definition))
    assert len(defs) >= 180, f"у графі лише {len(defs)} визначень"
    for _, o in defs:
        assert isinstance(o, Literal) and o.language == "uk", f"визначення без @uk: {o}"
