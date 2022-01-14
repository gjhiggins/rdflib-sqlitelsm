import pytest
import tempfile
import shutil
import os
from rdflib import ConjunctiveGraph, URIRef
from rdflib.store import VALID_STORE


tmpdir = tempfile.gettempdir()
path = os.path.join(tmpdir, "test_sqlitelsm")

try:
    shutil.rmtree(path)
except Exception:
    pass


@pytest.fixture
def get_conjunctive_graph():

    try:
        shutil.rmtree(path)
    except Exception:
        pass

    store_name = "SQLiteLSM"
    graph = ConjunctiveGraph(store=store_name)
    rt = graph.open(path, create=True)
    assert rt == VALID_STORE, "The underlying store is corrupt"
    assert (
        len(graph) == 0
    ), "There must be zero triples in the graph just after store (file) creation"
    data = """
            PREFIX : <https://example.org/>

            :a :b :c .
            :d :e :f .
            :d :g :h .
            """
    graph.parse(data=data, format="ttl")

    yield graph

    graph.close()
    graph.store.destroy(configuration=path)

    try:
        shutil.rmtree(path)
    except Exception:
        pass


def test_write(get_conjunctive_graph):
    graph = get_conjunctive_graph
    assert (
        len(graph) == 3
    ), "There must be three triples in the graph after the first data chunk parse"
    data2 = """
            PREFIX : <https://example.org/>

            :d :i :j .
            """
    graph.parse(data=data2, format="ttl")
    assert (
        len(graph) == 4
    ), "There must be four triples in the graph after the second data chunk parse"
    data3 = """
            PREFIX : <https://example.org/>

            :d :i :j .
            """
    graph.parse(data=data3, format="ttl")
    assert (
        len(graph) == 4
    ), "There must still be four triples in the graph after the thrd data chunk parse"


def test_read(get_conjunctive_graph):
    graph = get_conjunctive_graph
    sx = None
    for s in graph.subjects(
        predicate=URIRef("https://example.org/e"),
        object=URIRef("https://example.org/f"),
    ):
        sx = s
    assert sx == URIRef("https://example.org/d")


def test_sparql_query(get_conjunctive_graph):
    graph = get_conjunctive_graph
    q = r"""
        PREFIX : <https://example.org/>

        SELECT (COUNT(*) AS ?c)
        WHERE {
            :d ?p ?o .
        }"""

    c = 0
    for row in graph.query(q):
        c = int(row.c)
    assert c == 2, "SPARQL COUNT must return 2"


def test_sparql_insert(get_conjunctive_graph):
    graph = get_conjunctive_graph
    q = r"""
        PREFIX : <https://example.org/>

        INSERT DATA {
            :x :y :z .
        }"""

    graph.update(q)
    assert len(graph) == 4, "After extra triple insert, length must be 4"


def test_multigraph(get_conjunctive_graph):
    graph = get_conjunctive_graph
    q = r"""
        PREFIX : <https://example.org/>

        INSERT DATA {
            GRAPH :m {
                :x :y :z .
            }
            GRAPH :n {
                :x :y :z .
            }
        }"""

    graph.update(q)

    q = """
        SELECT (COUNT(?g) AS ?c)
        WHERE {
            SELECT DISTINCT ?g
            WHERE {
                GRAPH ?g {
                    ?s ?p ?o
                }
            }
        }
        """
    c = 0
    for row in graph.query(q):
        c = int(row.c)
    assert c == 3, "SPARQL COUNT must return 3 (default, :m & :n)"


def test_open_shut(get_conjunctive_graph):
    graph = get_conjunctive_graph
    assert len(graph) == 3, "Initially we must have 3 triples from setUp"
    graph.close()
    graph = None

    # reopen the graph
    graph2 = ConjunctiveGraph("SQLiteLSM")
    graph2.open(path, create=False)

    assert (
        len(graph2) == 3
    ), "After close and reopen, we should still have the 3 originally added triples"
    graph2.close()
    graph2.store.destroy(configuration=path)
