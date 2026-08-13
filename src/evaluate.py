"""
evaluate.py
-----------
Run every question through BOTH retrieval methods and score them the same way,
so the comparison is fair and every mark is explainable.

For each question we record, per method:
  - answer_ok  : did it return the right answer?
                 (for unanswerable questions, "right" means it abstained /
                  returned nothing)
  - source_ok  : did it point to the correct source document?

How each method is scored (kept deliberately simple and transparent):

  GRAPH (SPARQL):
    Look up the fact (subject, predicate) in the graph, returning objects plus
    the source document of each. answer_ok = a returned object is in the
    expected set; source_ok = the expected document is among the sources.
    For an unanswerable question, the lookup returns nothing, which is the
    correct behaviour, so answer_ok = True (it abstained).

  VECTOR (TF-IDF):
    Retrieve the top 3 chunks for the question text. answer_ok = one of the
    expected answer strings appears in those chunks (a generous proxy, since
    the method returns passages, not extracted answers). source_ok = the
    top-1 chunk comes from the expected document. For an unanswerable
    question we want it to abstain: abstain = top-1 score < THRESHOLD, and
    answer_ok = abstained.

Run:  python src/evaluate.py
"""

import csv
import json
from pathlib import Path

from rdflib import Namespace, URIRef
from rdflib.namespace import DCTERMS

from build_graph import build_dataset            # graph side
from build_vectors import VectorRetriever        # vector side

EX = Namespace("http://example.org/kb/")
REL = Namespace("http://example.org/rel/")

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = json.loads((ROOT / "facts" / "questions.json").read_text())["questions"]
ABSTAIN_THRESHOLD = 0.15   # vector: below this top score, treat as "don't know"


def localname(term):
    """'http://example.org/kb/RDF' -> 'RDF'; literals -> their string value."""
    s = str(term)
    return s.rsplit("/", 1)[-1] if s.startswith("http") else s


GRAPH_TEMPLATE = """
PREFIX ex: <http://example.org/kb/>
PREFIX rel: <http://example.org/rel/>
PREFIX dcterms: <http://purl.org/dc/terms/>
SELECT ?answer ?doc ?source WHERE {{
    GRAPH ?docg {{ ex:{subject} rel:{predicate} ?answer }}
    ?docg dcterms:title ?doc ; dcterms:source ?source .
}}
"""


def ask_graph(ds, q):
    """Return (answers, sources) for a question's (subject, predicate)."""
    query = GRAPH_TEMPLATE.format(subject=q["subject"], predicate=q["predicate"])
    answers, sources = [], []
    for row in ds.query(query):
        answers.append(localname(row.answer))
        # source doc id from the graph name is cleaner; derive from title match
        sources.append(str(row.doc))
    return answers, sources


def score_graph(q, answers, source_titles):
    if not q["answerable"]:
        # correct behaviour is to return nothing
        return {"answer_ok": len(answers) == 0, "source_ok": None,
                "returned": ", ".join(answers) or "(nothing)"}
    answer_ok = any(a in q["graph_expected"] for a in answers)
    # map expected doc id -> its human title to compare against query output
    source_ok = any(_title_matches(q["source"], t) for t in source_titles)
    return {"answer_ok": answer_ok, "source_ok": source_ok,
            "returned": ", ".join(answers) or "(nothing)"}


DOC_TITLES = {
    d: m["title"] for d, m in
    json.loads((ROOT / "data" / "provenance.json").read_text())["documents"].items()
}


def _title_matches(doc_id, title):
    return doc_id is not None and DOC_TITLES.get(doc_id) == title


def score_vector(q, hits):
    top = hits[0]
    if not q["answerable"]:
        abstained = top["score"] < ABSTAIN_THRESHOLD
        return {"answer_ok": abstained, "source_ok": None,
                "returned": f"top=[{top['doc_id']}] score={top['score']}"}
    joined = " ".join(h["text"].lower() for h in hits)
    answer_ok = any(exp.lower() in joined for exp in q["text_expected"])
    source_ok = top["doc_id"] == q["source"]
    return {"answer_ok": answer_ok, "source_ok": source_ok,
            "returned": f"top=[{top['doc_id']}] score={top['score']}"}


def main():
    ds = build_dataset()
    retriever = VectorRetriever()

    rows = []
    for q in QUESTIONS:
        g_answers, g_sources = ask_graph(ds, q)
        g = score_graph(q, g_answers, g_sources)
        v = score_vector(q, retriever.search(q["question"], top_k=3))
        rows.append((q, g, v))

    # ---- print a readable table -------------------------------------------
    def mark(x):
        return "-" if x is None else ("PASS" if x else "FAIL")

    print(f"{'Question':52} | GRAPH ans src | VECTOR ans src")
    print("-" * 92)
    for q, g, v in rows:
        print(f"{q['question'][:52]:52} |   "
              f"{mark(g['answer_ok']):4} {mark(g['source_ok']):4}|   "
              f"{mark(v['answer_ok']):4} {mark(v['source_ok']):4}")

    # ---- tallies -----------------------------------------------------------
    def rate(sel):
        vals = [sel(r) for r in rows if sel(r) is not None]
        return f"{sum(vals)}/{len(vals)}"

    print("\nTotals")
    print(f"  Answer correct   graph {rate(lambda r: r[1]['answer_ok'])}"
          f"   vector {rate(lambda r: r[2]['answer_ok'])}")
    print(f"  Source correct   graph {rate(lambda r: r[1]['source_ok'])}"
          f"   vector {rate(lambda r: r[2]['source_ok'])}")

    # ---- write CSV + markdown ---------------------------------------------
    out_csv = ROOT / "results" / "comparison.csv"
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["question", "answerable",
                    "graph_answer_ok", "graph_source_ok", "graph_returned",
                    "vector_answer_ok", "vector_source_ok", "vector_returned"])
        for q, g, v in rows:
            w.writerow([q["question"], q["answerable"],
                        g["answer_ok"], g["source_ok"], g["returned"],
                        v["answer_ok"], v["source_ok"], v["returned"]])

    out_md = ROOT / "results" / "summary.md"
    with out_md.open("w") as f:
        f.write("# Comparison results\n\n")
        f.write("| Question | Graph ans | Graph src | Vector ans | Vector src |\n")
        f.write("|---|:--:|:--:|:--:|:--:|\n")
        for q, g, v in rows:
            f.write(f"| {q['question']} | {mark(g['answer_ok'])} | "
                    f"{mark(g['source_ok'])} | {mark(v['answer_ok'])} | "
                    f"{mark(v['source_ok'])} |\n")
        f.write(f"\n- Answer correct: graph {rate(lambda r: r[1]['answer_ok'])}, "
                f"vector {rate(lambda r: r[2]['answer_ok'])}\n")
        f.write(f"- Source correct: graph {rate(lambda r: r[1]['source_ok'])}, "
                f"vector {rate(lambda r: r[2]['source_ok'])}\n")

    print(f"\nWrote {out_csv.name} and {out_md.name} to results/")


if __name__ == "__main__":
    main()
