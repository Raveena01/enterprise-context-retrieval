"""
add_solar_system.py
-------------------
GROW the knowledge base with a second domain (the Solar System) WITHOUT
touching the existing semantic-web data. It loads the current provenance,
facts, and questions, adds the new domain, and writes them back. It also
drops new corpus files. Running it twice is safe: it skips if solar-system
data is already present.

Every fact is a stable, uncontroversial astronomy fact, attributed to the
real Wikipedia article for that body (real per-source provenance, same
principle as the rest of the project).

Run once:  python scripts/add_solar_system.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "corpus"
PROV_PATH = ROOT / "data" / "provenance.json"
FACTS_PATH = ROOT / "facts" / "facts.json"
QUESTIONS_PATH = ROOT / "facts" / "questions.json"

WIKI = "https://en.wikipedia.org/wiki/"

# ---- provenance (real source per document) --------------------------------
PROV = {
    "sun":     {"title": "Sun",     "source_url": WIKI + "Sun"},
    "mercury": {"title": "Mercury", "source_url": WIKI + "Mercury_(planet)"},
    "venus":   {"title": "Venus",   "source_url": WIKI + "Venus"},
    "earth":   {"title": "Earth",   "source_url": WIKI + "Earth"},
    "mars":    {"title": "Mars",    "source_url": WIKI + "Mars"},
    "jupiter": {"title": "Jupiter", "source_url": WIKI + "Jupiter"},
    "saturn":  {"title": "Saturn",  "source_url": WIKI + "Saturn"},
    "uranus":  {"title": "Uranus",  "source_url": WIKI + "Uranus"},
    "neptune": {"title": "Neptune", "source_url": WIKI + "Neptune"},
}

# ---- short factual summaries for the vector side --------------------------
CORPUS_TEXT = {
    "sun": "The Sun is the star at the center of the Solar System. All eight "
           "planets orbit the Sun.",
    "mercury": "Mercury is the first planet from the Sun and the smallest "
               "planet in the Solar System. It is a terrestrial planet with a "
               "rocky surface and has no moons.",
    "venus": "Venus is the second planet from the Sun. It is a terrestrial "
             "planet similar in size to Earth and has no natural moons.",
    "earth": "Earth is the third planet from the Sun and the only known planet "
             "to support life. Earth orbits the Sun and has one natural moon, "
             "the Moon.",
    "mars": "Mars is the fourth planet from the Sun and is often called the Red "
            "Planet. Mars is a terrestrial planet and has two small moons, "
            "Phobos and Deimos.",
    "jupiter": "Jupiter is the fifth planet from the Sun and the largest planet "
               "in the Solar System. Jupiter is a gas giant with a faint ring "
               "system and many moons, including the four large Galilean moons "
               "Io, Europa, Ganymede, and Callisto.",
    "saturn": "Saturn is the sixth planet from the Sun and is a gas giant known "
              "for its prominent ring system. Its largest moon is Titan.",
    "uranus": "Uranus is the seventh planet from the Sun. It is an ice giant "
              "and has a faint ring system.",
    "neptune": "Neptune is the eighth planet from the Sun and is the most "
               "distant planet in the Solar System. It is an ice giant, and its "
               "largest moon is Triton.",
}


def _ent(x):
    return {"id": x}


def _lit(x):
    return {"lit": x}


# ---- facts, grouped by the document (source) they come from ---------------
def _planet(name, ptype, position, moons=(), rings=False):
    facts = [
        {"s": name, "p": "type", "o": _ent(ptype)},
        {"s": name, "p": "label", "o": _lit(name)},
        {"s": name, "p": "orbits", "o": _ent("Sun")},
        {"s": name, "p": "positionFromSun", "o": _lit(str(position))},
    ]
    if rings:
        facts.append({"s": name, "p": "hasRingSystem", "o": _lit("true")})
    for m in moons:
        facts.append({"s": name, "p": "hasMoon", "o": _ent(m)})
        facts.append({"s": m, "p": "type", "o": _ent("NaturalSatellite")})
    return facts


FACTS = {
    "sun": [{"s": "Sun", "p": "type", "o": _ent("Star")},
            {"s": "Sun", "p": "label", "o": _lit("Sun")}],
    "mercury": _planet("Mercury", "TerrestrialPlanet", 1),
    "venus": _planet("Venus", "TerrestrialPlanet", 2),
    "earth": _planet("Earth", "TerrestrialPlanet", 3, moons=["Moon"]),
    "mars": _planet("Mars", "TerrestrialPlanet", 4, moons=["Phobos", "Deimos"]),
    "jupiter": _planet("Jupiter", "GasGiant", 5, rings=True,
                       moons=["Io", "Europa", "Ganymede", "Callisto"]),
    "saturn": _planet("Saturn", "GasGiant", 6, rings=True, moons=["Titan"]),
    "uranus": _planet("Uranus", "IceGiant", 7, rings=True),
    "neptune": _planet("Neptune", "IceGiant", 8, rings=True, moons=["Triton"]),
}

# ---- evaluation questions for the new domain ------------------------------
QUESTIONS = [
    {"question": "What does Earth orbit?",
     "subject": "Earth", "predicate": "orbits",
     "graph_expected": ["Sun"], "text_expected": ["Sun"],
     "source": "earth", "answerable": True},
    {"question": "What is Mars's position from the Sun?",
     "subject": "Mars", "predicate": "positionFromSun",
     "graph_expected": ["4"], "text_expected": ["fourth"],
     "source": "mars", "answerable": True},
    {"question": "Name a moon of Jupiter.",
     "subject": "Jupiter", "predicate": "hasMoon",
     "graph_expected": ["Io", "Europa", "Ganymede", "Callisto"],
     "text_expected": ["Io", "Europa", "Ganymede", "Callisto"],
     "source": "jupiter", "answerable": True},
    {"question": "Name a moon of Mars.",
     "subject": "Mars", "predicate": "hasMoon",
     "graph_expected": ["Phobos", "Deimos"],
     "text_expected": ["Phobos", "Deimos"],
     "source": "mars", "answerable": True},
    {"question": "How many people live on Mars?",
     "subject": "MarsColony", "predicate": "population",
     "graph_expected": [], "text_expected": [],
     "source": None, "answerable": False},
]


def main():
    prov = json.loads(PROV_PATH.read_text())
    facts = json.loads(FACTS_PATH.read_text())
    questions = json.loads(QUESTIONS_PATH.read_text())

    if "jupiter" in prov["documents"]:
        print("Solar-system data already present. Nothing to add.")
        return

    # add provenance (keeping existing entries untouched)
    for doc_id, meta in PROV.items():
        prov["documents"][doc_id] = {
            "title": meta["title"], "source_url": meta["source_url"],
            "retrieved_at": "2026-08-13", "publisher": "Wikipedia",
        }

    # add facts
    for doc_id, doc_facts in FACTS.items():
        facts["facts"][doc_id] = doc_facts

    # add questions
    questions["questions"].extend(QUESTIONS)

    # add corpus files
    for doc_id, text in CORPUS_TEXT.items():
        (CORPUS / f"{doc_id}.txt").write_text(text + "\n", encoding="utf-8")

    PROV_PATH.write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    FACTS_PATH.write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    QUESTIONS_PATH.write_text(json.dumps(questions, indent=2) + "\n",
                              encoding="utf-8")

    n_new_facts = sum(len(v) for v in FACTS.values())
    print(f"Added {len(PROV)} documents, {n_new_facts} facts, "
          f"{len(QUESTIONS)} questions, {len(CORPUS_TEXT)} corpus files.")
    print("Existing semantic-web data left untouched.")


if __name__ == "__main__":
    main()
