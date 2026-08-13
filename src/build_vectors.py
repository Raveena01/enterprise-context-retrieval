"""
build_vectors.py
----------------
The vector-retrieval baseline, to compare against the graph (build_graph.py).

Idea:
  - Split every corpus document into small chunks (here, one sentence each).
  - Turn each chunk into a TF-IDF vector. TF-IDF = "term frequency x inverse
    document frequency": a chunk is represented by which words it contains,
    weighted so that rare, distinctive words count more than common ones.
    This is LEXICAL (word-overlap) retrieval, NOT semantic embeddings, so it
    matches on shared words, not on meaning. Be honest about that.
  - To answer a query, vectorize it the same way and return the chunks whose
    vectors are most similar (cosine similarity).

What to notice versus the graph:
  - The graph returns a precise, typed fact plus clean provenance.
  - This returns a passage of text and the document it sits in. You still have
    to read the passage to find the answer, and the "source" is only as precise
    as the chunk. It also always returns its top matches, even when the corpus
    has no real answer (watch the score, not just the rank).

Run directly to see it retrieve:
    python src/build_vectors.py
"""

import re
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "data" / "corpus"


def load_chunks():
    """Return two parallel lists: chunk texts, and (doc_id, sentence_index)."""
    chunks, meta = [], []
    for path in sorted(CORPUS_DIR.glob("*.txt")):
        doc_id = path.stem
        text = path.read_text(encoding="utf-8").strip()
        # naive sentence split; fine for this small, clean corpus
        sentences = [s.strip() for s in re.split(r"(?<=[.])\s+", text) if s.strip()]
        for i, sentence in enumerate(sentences):
            chunks.append(sentence)
            meta.append((doc_id, i))
    return chunks, meta


class VectorRetriever:
    def __init__(self):
        self.chunks, self.meta = load_chunks()
        # lowercase + drop very common English stop-words so matches are
        # driven by content words like "sparql", "rdf", "query"
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.matrix = self.vectorizer.fit_transform(self.chunks)

    def search(self, query, top_k=3):
        """Return top_k matches as dicts: doc_id, score, text."""
        q_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self.matrix)[0]
        ranked = scores.argsort()[::-1][:top_k]
        results = []
        for idx in ranked:
            doc_id, sent_i = self.meta[idx]
            results.append({
                "doc_id": doc_id,
                "score": round(float(scores[idx]), 3),
                "text": self.chunks[idx],
            })
        return results


def _demo(retriever, question):
    print(f"Q: {question}")
    hits = retriever.search(question, top_k=3)
    for rank, h in enumerate(hits, 1):
        print(f"  {rank}. [{h['doc_id']}]  score={h['score']}")
        print(f"     {h['text']}")
    print()


def main():
    r = VectorRetriever()
    print(f"Indexed {len(r.chunks)} chunks from "
          f"{len(set(m[0] for m in r.meta))} documents.\n")

    # 1) a question the corpus can answer
    _demo(r, "What is SPARQL a query language for?")
    # 2) another answerable one
    _demo(r, "Who proposed Linked Data?")
    # 3) a question the corpus CANNOT answer: notice it still returns
    #    something, just with low scores. It does not cleanly say "I don't know".
    _demo(r, "What is the price of a BMW electric car?")


if __name__ == "__main__":
    main()
