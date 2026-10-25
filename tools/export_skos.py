# -*- coding: utf-8 -*-
"""ЛР05 Р5: експорт підсумкової таксономії у SKOS (models/taxonomy.ttl).

Будує ConceptScheme, Concept для кожного вузла, prefLabel/altLabel з мовною міткою @uk,
broader для зв'язку з батьком, definition і зовнішні зв'язки exactMatch/closeMatch/broadMatch
до Getty AAT.

Зовнішні зв'язки наведено лише для тих понять, ідентифікатор яких підтверджено в самому
тезаурусі (сторінка концепту відкривалася під час верифікації). Жоден ідентифікатор не
вгадувався.

Запуск: python tools/export_skos.py
"""
import csv
import pathlib

from rdflib import DCTERMS, SKOS, Graph, Literal, Namespace, RDF, URIRef

HUB = pathlib.Path(__file__).resolve().parents[1]
BASE = Namespace("https://example.org/dkh/taxonomy/")
AAT = Namespace("http://vocab.getty.edu/aat/")
SCHEME = BASE["scheme"]

# ідентифікатори, перевірені в тезаурусі; поруч — тип відповідності й підстава
EXTERNAL = {
    "панельний живопис": (SKOS.exactMatch, "300178675",
                          "panel painting (image-making) — та сама техніка"),
    "темпера": (SKOS.closeMatch, "300389785",
                "tempera paintings — у AAT це твори, у нас техніка й матеріал"),
    "відносна вологість повітря": (SKOS.closeMatch, "300055370",
                                   "humidity — у AAT ширше поняття вологості"),
    "станковий живопис": (SKOS.closeMatch, "300054216",
                          "painting (image-making) — ширше за станковий"),
    "Дія з об'єктом": (SKOS.broadMatch, "300053001",
                       "processes and techniques — верхня категорія процесів AAT"),
}


def main() -> None:
    rows = list(csv.DictReader(open(HUB / "models/taxonomy_final.csv", encoding="utf-8")))
    terms = {r["term"]: r for r in csv.DictReader(
        open(HUB / "models/terms.csv", encoding="utf-8"))}

    g = Graph()
    g.bind("skos", SKOS)
    g.bind("dcterms", DCTERMS)
    g.bind("aat", AAT)
    g.bind("dkh", BASE)

    g.add((SCHEME, RDF.type, SKOS.ConceptScheme))
    g.add((SCHEME, SKOS.prefLabel,
           Literal("Таксономія понять управління знаннями культурної спадщини", lang="uk")))
    g.add((SCHEME, DCTERMS.creator, Literal("Чапля О., ФеІ-42")))
    g.add((SCHEME, DCTERMS.created, Literal("2026-10-25")))

    uri = {r["id"]: BASE[r["id"]] for r in rows}
    for r in rows:
        c = uri[r["id"]]
        g.add((c, RDF.type, SKOS.Concept))
        g.add((c, SKOS.inScheme, SCHEME))
        g.add((c, SKOS.prefLabel, Literal(r["label"], lang="uk")))

        if r["parent_id"]:
            g.add((c, SKOS.broader, uri[r["parent_id"]]))
            g.add((uri[r["parent_id"]], SKOS.narrower, c))
        else:
            g.add((SCHEME, SKOS.hasTopConcept, c))
            g.add((c, SKOS.topConceptOf, SCHEME))

        definition = r.get("definition") or terms.get(r["label"], {}).get("definition", "")
        if definition:
            g.add((c, SKOS.definition, Literal(definition, lang="uk")))
        if r.get("division_principle"):
            g.add((c, SKOS.scopeNote,
                   Literal(f'Принцип поділу дітей: {r["division_principle"]}', lang="uk")))

        for alt in filter(None, (terms.get(r["label"], {}).get("alt_labels", "")).split("; ")):
            g.add((c, SKOS.altLabel, Literal(alt, lang="uk")))

        if r["label"] in EXTERNAL:
            prop, aat_id, why = EXTERNAL[r["label"]]
            g.add((c, prop, AAT[aat_id]))
            g.add((c, SKOS.editorialNote,
                   Literal(f"Зв'язок із AAT {aat_id}: {why}", lang="uk")))

    out = HUB / "models/taxonomy.ttl"
    g.serialize(destination=out, format="turtle")

    print(f"вузлів у таксономії: {len(rows)}")
    print(f"тріплетів у графі: {len(g)}")
    print(f"верхніх понять: {sum(1 for _ in g.subjects(SKOS.topConceptOf, SCHEME))}")
    print(f"altLabel: {sum(1 for _ in g.triples((None, SKOS.altLabel, None)))}")
    print(f"definition: {sum(1 for _ in g.triples((None, SKOS.definition, None)))}")
    ext = sum(1 for p in (SKOS.exactMatch, SKOS.closeMatch, SKOS.broadMatch)
              for _ in g.triples((None, p, None)))
    print(f"зовнішніх зв'язків: {ext}")
    print(f"файл: {out.relative_to(HUB)}")


if __name__ == "__main__":
    main()
