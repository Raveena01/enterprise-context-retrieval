"""
mcp_server.py
-------------
Expose the provenance-aware retrieval layer to AI agents over MCP
(Model Context Protocol), so any MCP-compatible host (Claude Desktop,
Cursor, an agent runtime, etc.) can query this knowledge at runtime and
receive answers WITH their provenance. This is the "MCP-based context
delivery" idea: the graph stops being a script and becomes a live context
source an agent can call.

Built on the official MCP Python SDK, stable 1.x line, using its FastMCP
decorator API. (Note: the SDK's 2.x line renames FastMCP to MCPServer; we
pin mcp>=1.28,<2 for stability, per the SDK's own guidance.)

Two tools are exposed:
  - get_fact(subject, predicate): a precise, typed answer from the knowledge
    graph, returned with its source document, URL, and retrieval date.
  - search_documents(query): passages from the corpus relevant to a query,
    each tagged with the document it came from.

Both return provenance, so whatever the agent consumes, it can cite where it
came from.

Run the server (stdio transport, which is what MCP hosts launch):
    python src/mcp_server.py

Inspect it interactively without an agent:
    pip install "mcp[cli]"
    mcp dev src/mcp_server.py      # opens the MCP Inspector
"""

from mcp.server.fastmcp import FastMCP

from build_graph import build_dataset          # graph + provenance
from build_vectors import VectorRetriever       # vector baseline

mcp = FastMCP("enterprise-context")

# Build the knowledge sources once, when the server starts.
_ds = build_dataset()
_retriever = VectorRetriever()

_FACT_QUERY = """
PREFIX ex: <http://example.org/kb/>
PREFIX rel: <http://example.org/rel/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX prov: <http://www.w3.org/ns/prov#>
SELECT ?answer ?title ?source ?retrieved WHERE {{
    GRAPH ?doc {{ ex:{subject} rel:{predicate} ?answer }}
    ?doc dcterms:title ?title ;
         dcterms:source ?source ;
         prov:generatedAtTime ?retrieved .
}}
"""


def _localname(term):
    s = str(term)
    return s.rsplit("/", 1)[-1] if s.startswith("http") else s


@mcp.tool()
def get_fact(subject: str, predicate: str) -> list[dict]:
    """Look up a fact in the provenance-aware knowledge graph.

    Returns each matching answer together with the source document it came
    from, that document's URL, and the date it was retrieved. Use knowledge-base
    vocabulary, e.g. subject="SPARQL", predicate="queryLanguageFor", or
    subject="RDF", predicate="developedBy". Returns an empty list if the fact
    is not in the graph (a clean "not found").
    """
    query = _FACT_QUERY.format(subject=subject, predicate=predicate)
    results = []
    for row in _ds.query(query):
        results.append({
            "answer": _localname(row.answer),
            "source_document": str(row.title),
            "source_url": str(row.source),
            "retrieved_at": str(row.retrieved),
        })
    return results


@mcp.tool()
def search_documents(query: str, top_k: int = 3) -> list[dict]:
    """Search the corpus for passages relevant to a free-text query.

    Returns the most similar passages (lexical TF-IDF similarity), each tagged
    with the source document it came from and a relevance score. A top score
    near zero means nothing in the corpus is relevant.
    """
    hits = _retriever.search(query, top_k=top_k)
    return [{
        "passage": h["text"],
        "source_document": h["doc_id"],
        "score": h["score"],
    } for h in hits]


if __name__ == "__main__":
    # stdio is the transport MCP hosts use to launch a local server.
    mcp.run()
