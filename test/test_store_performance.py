import os
import gc
from time import time
from random import random

import tempfile
import shutil
import logging


from rdflib import Graph, URIRef
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


store = "SQLiteLSM"

path = os.environ.get(
    "DBURI", os.path.join(tempfile.gettempdir(), f"test_{store.lower()}")
)


def process_test_data(timings):
    keys = [
        "ntriples",
        "loading",
        "opening",
        "iterating",
        "lengthing",
        "subjects",
    ]
    op = ",".join(keys) + "\n"
    for d in timings:
        row = ",".join(str(d[k]) for k in keys)
        op += row + "\n"

    logger.info(op)


def test_timing():
    results = []

    for (k, (ntriples, nfoaf)) in fixturelist:
        inputloc = os.getcwd() + f"/test/sp2b/{k}.n3"

        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)

        results.append(process_input(inputloc, k, ntriples, nfoaf))
    process_test_data(results)


def process_input(inputloc, k, ntriples, nfoaf):
    timings = dict(
        ntriples=ntriples,
        loading=0,
        opening=0,
        iterating=0,
        lengthing=0,
        subjects=0,
    )

    gcold = gc.isenabled()
    gc.collect()
    gc.disable()

    graph = Graph(store, URIRef("http://rdflib.net"))

    graph.open(path, create=True)

    t0 = time()
    graph.parse(location=inputloc, format="n3")
    t1 = time()

    timings["loading"] = t1 - t0

    graph.close()

    del graph

    graph = Graph(store, URIRef("http://rdflib.net"))

    # Read triples back into memory from store
    t0 = time()
    graph.open(path, create=False)
    t1 = time()
    assert len(graph) == ntriples, len(graph)
    timings["opening"] = t1 - t0

    t0 = time()
    for triple in graph.triples((None, None, None)):
        pass
    t1 = time()
    timings["iterating"] = t1 - t0

    t0 = time()
    assert len(list(graph.triples((None, None, None)))) == ntriples
    t1 = time()
    timings["lengthing"] = t1 - t0

    t0 = time()
    res = graph.subjects(predicate=RDF.type, object=FOAF.Person)
    t1 = time()
    timings["subjects"] = t1 - t0
    assert len(list(res)) == nfoaf

    graph.close()
    graph.destroy(path)

    if gcold:
        gc.enable()
    del graph

    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)

    return timings
