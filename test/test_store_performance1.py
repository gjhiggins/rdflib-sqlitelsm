import pytest
import os
import gc
from time import time
from random import random

import tempfile
import shutil
import logging

from typing import Optional

from rdflib import Graph, ConjunctiveGraph, URIRef, plugin
from rdflib import FOAF, RDF

logging.basicConfig(level=logging.ERROR, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def random_uri():
    return URIRef("%s" % random())


fixturelist = [
    ("500triples", (691, 58)),
    ("1ktriples", (1285, 121)),
    ("2ktriples", (2006, 191)),
    ("3ktriples", (3095, 289)),
    ("5ktriples", (5223, 497)),
    ("10ktriples", (10303, 949)),
    ("25ktriples", (25161, 2162)),
    ("50ktriples", (50168, 4165)),
    ("100ktriples", (100073, 8254)),
    ("250ktriples", (250128, 20144)),
    ("500ktriples", (500043, 40434)),
]


q1 = """PREFIX rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX dc:      <http://purl.org/dc/elements/1.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX bench:   <http://localhost/vocabulary/bench/>
PREFIX xsd:     <http://www.w3.org/2001/XMLSchema#>

SELECT ?yr
WHERE {
  ?journal rdf:type bench:Journal .
  ?journal dc:title "Journal 1 (1940)"^^xsd:string .
  ?journal dcterms:issued ?yr
}

"""

q2 = """PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>

SELECT DISTINCT ?predicate
WHERE {
  {
    ?person rdf:type foaf:Person .
    ?subject ?predicate ?person
  } UNION {
    ?person rdf:type foaf:Person .
    ?person ?predicate ?object
  }
}
"""

q3 = """PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#>
PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX dc:   <http://purl.org/dc/elements/1.1/>

SELECT DISTINCT ?name
WHERE {
  ?erdoes rdf:type foaf:Person .
  ?erdoes foaf:name "Paul Erdoes"^^xsd:string .
  {
    ?document dc:creator ?erdoes .
    ?document dc:creator ?author .
    ?document2 dc:creator ?author .
    ?document2 dc:creator ?author2 .
    ?author2 foaf:name ?name
    FILTER (?author!=?erdoes &&
            ?document2!=?document &&
            ?author2!=?erdoes &&
            ?author2!=?author)
  } UNION {
    ?document dc:creator ?erdoes.
    ?document dc:creator ?author.
    ?author foaf:name ?name
    FILTER (?author!=?erdoes)
  }
}
"""


@pytest.fixture(scope="function")
def get_graph(request):
    store = "SQLiteLSM"

    path = os.environ.get(
        "DBURI", os.path.join(tempfile.gettempdir(), f"test_{store.lower()}")
    )

    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)

    gcold = gc.isenabled()
    gc.collect()
    gc.disable()

    graph = Graph(store=store)

    graph.open(path, create=True)

    yield graph, path

    graph.close()
    if gcold:
        gc.enable()
    del graph

    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def test_timing(get_graph):
    graph, path = get_graph

    for (k, (ntriples, nfoaf)) in fixturelist:
        inputloc = os.getcwd() + f"/test/sp2b/{k}.n3"
        # Clean up graphs so that BNodes in input data
        # won't create random results

        graph.remove((None, None, None))

        t0 = time()
        graph.parse(location=inputloc, format="n3")
        t1 = time()
        print("%.3g" % (t1 - t0), end=" ")

        res = f"{t1 - t0:.5f}"

        logger.debug(f"Loaded {len(graph):5d} triples in {res.strip()}s")

        assert len(graph) == ntriples, len(graph)

        graph.close()

        # Read triples back into memory from store
        t0 = time()
        graph.open(path, create=False)
        t1 = time()
        assert len(graph) == ntriples, len(graph)
        logger.debug(
            f"Opening store containing {ntriples} triples: {t1 - t0:.5f}s"
        )

        t0 = time()
        for triple in graph.triples((None, None, None)):
            pass
        t1 = time()
        logger.debug(f"Iterating over triples: {t1 - t0:.5f}s")

        t0 = time()
        assert len(list(graph.triples((None, None, None)))) == ntriples
        t1 = time()
        logger.debug(f"Getting length of graph: {t1 - t0:.5f}s")

        t0 = time()
        res = graph.subjects(predicate=RDF.type, object=FOAF.Person)
        t1 = time()
        logger.debug(
            f"Getting subjects of rdf:type foaf:Person: {t1 - t0:.5f}s"
        )
        assert len(list(res)) == nfoaf

        t0 = time()
        res = graph.query(
            "SELECT (count(?s) as ?nfoaf) WHERE {?s rdf:type foaf:Person .}"
        )
        t1 = time()
        logger.debug(
            f"SELECTing COUNT of subjects of rdf:type foaf:Person: {t1 - t0:.5f}s"
        )
        assert list(res)[0].nfoaf.toPython() == nfoaf

        t0 = time()
        res = graph.query(q1)
        t1 = time()
        logger.debug(f"SPARQL Query 1 {t1 - t0:.5f}s")
        assert list(res)[0].yr.toPython() == 1940

        t0 = time()
        res = graph.query(q2)
        t1 = time()
        logger.debug(f"SPARQL Query 2 {t1 - t0:.5f}s")
        assert (
            list(res)[0].predicate.toPython()
            == "http://purl.org/dc/elements/1.1/creator"
        )

        t0 = time()
        res = graph.query(q3)
        t1 = time()
        logger.debug(f"SPARQL Query 3 {t1 - t0:.5f}s")
        assert sorted(list(res))[0].name.toPython() in [
            "Adamanta Schlitt",
            "Aandranee Sakamaki",
        ]
