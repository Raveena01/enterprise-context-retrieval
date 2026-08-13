"""
build_graph.py
--------------
Build a provenance-aware RDF knowledge graph from the curated facts.

Design idea (the whole point of the project):
  - Each source document's facts live in their own NAMED GRAPH.
  - A separate provenance graph records, for each named graph, where it
    came from (source URL), when it was retrieved, and under what license,
    using the standard PROV-O and Dublin Core (dcterms) vocabularies.
  - Because every fact sits inside a named graph, any SPARQL answer can be
    joined back to that graph's provenance. The graph doesn't just return
    an answer, it returns the answer WITH its source.

Run directly to build the dataset and see a traceable query:
    python src/build_graph.py
"""

import json
from pathlib import Path

from rdflib import Dataset, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, DCTERMS, PROV, XSD

# --- namespaces -------------------------------------------------------------
EX = Namespace("http://example.org/kb/")     # entities (RDF, SPARQL, W3C, ...)
REL = Namespace("http://example.org/rel/")   # predicates (developedBy, ...)
LICENSE_URI = URIRef("https://creativecommons.org/licenses/by-sa/4.0/")

ROOT = Path(__file__).resolve().parent.parent
FACTS_PATH = ROOT / "facts" / "facts.json"
PROV_PATH = ROOT / "data" / "provenance.json"

DT = {"gYear": XSD.gYear, "date": XSD.date, "string": XSD.string}


def _term(obj):
    """Turn a facts.json object dict into an rdflib term (IRI or Literal)."""
    if "id" in obj:
        return EX[obj["id"]]
    if "lit" in obj:
        dt = DT.get(obj.get("dt"))
        return Literal(obj["lit"], datatype=dt) if dt else Literal(obj["lit"])
    raise ValueError(f"Bad object in facts.json: {obj}")


def doc_graph_iri(doc_id: str) -> URIRef:
    return URIRef(f"urn:doc:{doc_id}")


def build_dataset() -> Dataset:
    facts = json.loads(FACTS_PATH.read_text())["facts"]
    prov = json.loads(PROV_PATH.read_text())["documents"]

    # default_union=True lets patterns outside a GRAPH{} block match across
    # every named graph, so we can join a fact to its provenance easily.
    ds = Dataset(default_union=True)
    prov_graph = ds.graph(URIRef("urn:provenance"))

    for doc_id, triples in facts.items():
        g_iri = doc_graph_iri(doc_id)
        g = ds.graph(g_iri)
        for t in triples:
            p = RDF.type if t["p"] == "type" else (
                RDFS.label if t["p"] == "label" else REL[t["p"]])
            g.add((EX[t["s"]], p, _term(t["o"])))

        # provenance about this named graph
        meta = prov[doc_id]
        prov_graph.add((g_iri, RDF.type, PROV.Entity))
        prov_graph.add((g_iri, DCTERMS.title, Literal(meta["title"])))
        prov_graph.add((g_iri, DCTERMS.source, URIRef(meta["source_url"])))
        prov_graph.add((g_iri, DCTERMS.publisher, Literal(meta["publisher"])))
        prov_graph.add((g_iri, DCTERMS.license, LICENSE_URI))
        prov_graph.add((g_iri, PROV.wasDerivedFrom, URIRef(meta["source_url"])))
        prov_graph.add((g_iri, PROV.generatedAtTime,
                        Literal(meta["retrieved_at"], datatype=XSD.date)))

    return ds


# A query that asks a question AND demands the source of the answer.
TRACEABLE_QUERY = """
PREFIX ex: <http://example.org/kb/>
PREFIX rel: <http://example.org/rel/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prov: <http://www.w3.org/ns/prov#>

SELECT ?answer ?title ?source ?retrieved WHERE {
    GRAPH ?doc { ex:SPARQL rel:queryLanguageFor ?answer }
    ?doc dcterms:title ?title ;
         dcterms:source ?source ;
         prov:generatedAtTime ?retrieved .
}
"""


def main():
    ds = build_dataset()

    n_facts = sum(len(g) for g in ds.graphs()
                  if g.identifier != URIRef("urn:provenance"))
    print(f"Built dataset: {len(list(ds.graphs()))} named graphs, "
          f"{n_facts} facts + provenance.\n")

    out = ROOT / "results" / "graph.trig"
    ds.serialize(destination=out, format="trig")
    print(f"Serialized full dataset (facts + provenance) -> {out}\n")

    print("Q: What is SPARQL a query language for, and where does that fact come from?")
    for row in ds.query(TRACEABLE_QUERY):
        answer = str(row.answer).split("/")[-1]
        print(f"  answer   : {answer}")
        print(f"  source   : {row.title}  <{row.source}>")
        print(f"  retrieved: {row.retrieved}")


if __name__ == "__main__":
    main()
