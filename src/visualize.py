"""
visualize.py
------------
Render the knowledge graph as a readable, interactive network you open in a
browser.

What it draws:
  - Entities (RDF, SPARQL, W3C, ...) are circular nodes; literal values
    ("1999", "subject-predicate-object") are light boxes.
  - Each fact is an arrow labelled with its relationship (developedBy,
    queryLanguageFor, ...).
  - Each arrow is COLOURED by the source document the fact came from, and
    hovering it shows that document's title, URL, and retrieval date. So the
    provenance you built into the graph becomes visible: you can see, and
    audit, where every fact originated.

Reads the same dataset build_graph.py builds, so it always reflects real data.

Run:  python src/visualize.py    ->  open results/graph.html in a browser
"""

import json
from pathlib import Path

from rdflib import URIRef
from rdflib.namespace import RDF, RDFS
from pyvis.network import Network

from build_graph import build_dataset

ROOT = Path(__file__).resolve().parent.parent
PROV = json.loads((ROOT / "data" / "provenance.json").read_text())["documents"]

# one distinct colour per source document, generated so any number of
# documents (and domains) gets its own colour automatically
import colorsys


def _make_colors(doc_ids):
    ids = sorted(doc_ids)
    colors = {}
    for i, d in enumerate(ids):
        h = i / max(len(ids), 1)
        r, g, b = colorsys.hsv_to_rgb(h, 0.58, 0.75)
        colors[d] = "#%02X%02X%02X" % (int(r * 255), int(g * 255), int(b * 255))
    return colors


DOC_COLORS = _make_colors(PROV.keys())

ENTITY_FILL = "#5B8FF9"
LITERAL_FILL = "#F2F2F2"

# vis.js options: big readable labels with a white halo, thick coloured edges,
# a calm spread-out physics layout, hover tooltips, and zoom buttons.
OPTIONS = """
{
  "nodes": {
    "font": {"size": 22, "color": "#141414", "strokeWidth": 4,
             "strokeColor": "#ffffff", "face": "arial"},
    "borderWidth": 2, "size": 18
  },
  "edges": {
    "font": {"size": 15, "color": "#333333", "strokeWidth": 6,
             "strokeColor": "#ffffff", "align": "middle"},
    "width": 2.5,
    "color": {"inherit": false},
    "smooth": {"type": "dynamic"},
    "arrows": {"to": {"enabled": true, "scaleFactor": 0.6}}
  },
  "physics": {
    "barnesHut": {"gravitationalConstant": -14000, "springLength": 160,
                  "springConstant": 0.025, "centralGravity": 0.3,
                  "damping": 0.09, "avoidOverlap": 0.4},
    "minVelocity": 0.75,
    "stabilization": {"iterations": 400}
  },
  "interaction": {"hover": true, "navigationButtons": true, "tooltipDelay": 120,
                  "keyboard": true},
  "layout": {"improvedLayout": true}
}
"""


def _local(term):
    s = str(term)
    return s.rsplit("/", 1)[-1] if s.startswith("http") else s


def _pred_label(p):
    if p == RDF.type:
        return "type"
    if p == RDFS.label:
        return "label"
    return _local(p)


def build_network():
    ds = build_dataset()
    net = Network(height="820px", width="100%", directed=True,
                  bgcolor="#ffffff", cdn_resources="in_line")
    net.set_options(OPTIONS)

    seen = set()

    def add_entity(term):
        nid = "ent:" + _local(term)
        if nid not in seen:
            net.add_node(nid, label=_local(term), shape="dot", size=18,
                         color={"background": ENTITY_FILL, "border": "#2C5AA0"},
                         title="entity: " + _local(term))
            seen.add(nid)
        return nid

    def add_literal(term):
        nid = "lit:" + str(term)
        if nid not in seen:
            net.add_node(nid, label=str(term), shape="box",
                         color={"background": LITERAL_FILL, "border": "#BBBBBB"},
                         font={"size": 18, "color": "#333333"},
                         title="literal value")
            seen.add(nid)
        return nid

    for g in ds.graphs():
        gid = str(g.identifier)
        if not gid.startswith("urn:doc:"):
            continue
        doc_id = gid.replace("urn:doc:", "")
        meta = PROV[doc_id]
        color = DOC_COLORS.get(doc_id, "#333333")
        tip = (f"source: {meta['title']} | {meta['source_url']} | "
               f"retrieved {meta['retrieved_at']}")
        for s, p, o in g:
            s_id = add_entity(s)
            o_id = add_entity(o) if isinstance(o, URIRef) else add_literal(o)
            net.add_edge(s_id, o_id, label=_pred_label(p),
                         color=color, title=tip)
    return net


def _legend_html():
    rows = "".join(
        f'<div style="margin:2px 0"><span style="display:inline-block;'
        f'width:16px;height:16px;background:{c};border-radius:3px;'
        f'vertical-align:middle;margin-right:8px"></span>{PROV[d]["title"]}</div>'
        for d, c in DOC_COLORS.items()
    )
    return f"""
<div style="position:absolute;top:14px;left:14px;z-index:999;background:#fff;
     border:1px solid #d0d0d0;border-radius:10px;padding:12px 14px;
     font-family:arial;font-size:14px;box-shadow:0 2px 8px rgba(0,0,0,.12);
     max-width:320px;max-height:340px;overflow:auto">
  <div style="font-weight:bold;margin-bottom:8px">Edge colour = source document</div>
  {rows}
  <div style="margin-top:8px;color:#666;font-size:12px">
    &#9679; entity &nbsp;&nbsp; &#9645; literal &nbsp;&nbsp;
    hover an edge for its source URL &amp; date &middot; scroll to zoom
  </div>
</div>
"""


def main():
    net = build_network()
    out = ROOT / "results" / "graph.html"
    html = net.generate_html(notebook=False)
    # pin a proper legend into the page and write UTF-8 (Windows-safe)
    html = html.replace("<body>", "<body>\n" + _legend_html(), 1)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote interactive graph -> {out}")
    print("Open results/graph.html. Labels are readable now; edges are coloured "
          "by source document; hover an edge for provenance; scroll to zoom.")


if __name__ == "__main__":
    main()
