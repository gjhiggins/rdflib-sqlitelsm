import pytest
import os
import tempfile
import shutil
from rdflib_sqlitelsm.sqlitelsmstore import readable_index
from rdflib.graph import Graph, ConjunctiveGraph, Literal, URIRef
from rdflib.namespace import XSD, RDFS
from rdflib.store import VALID_STORE, NO_STORE
import logging

logging.basicConfig(level=logging.ERROR, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

storename = "SQLiteLSM"
storetest = True

michel = URIRef("urn:michel")
bob = URIRef("urn:bob")
cheese = URIRef("urn:cheese")
likes = URIRef("urn:likes")
pizza = URIRef("urn:pizza")
context1 = URIRef("urn:graph1")
context2 = URIRef("urn:graph2")

store = "SQLiteLSM"
path = os.path.join(tempfile.gettempdir(), f"test_{store.lower()}")


@pytest.fixture
def get_graph():

    try:
        shutil.rmtree(path)
    except Exception:
        pass
    graph = Graph(store=store)
    rt = graph.open(configuration=path, create=True)
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
    assert (
        len(graph) == 3
    ), "There must be three triples in the graph after the first data chunk parse"

    yield graph

    graph.close()
    graph.destroy(configuration=path)


@pytest.fixture
def get_conjunctive_graph():

    graph = ConjunctiveGraph(store=store)
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
    assert (
        len(graph) == 3
    ), "There must be three triples in the graph after the first data chunk parse"

    yield graph

    graph.close()
    graph.destroy(configuration=path)


def test_sqlitelsm_graph_create_db(get_graph):
    graph = get_graph
    graph.add((michel, likes, pizza))
    graph.add((michel, likes, cheese))
    graph.commit()
    assert (
        len(graph) == 5
    ), f"There must be five triples in the graph after the above data chunk parse, not {len(graph)}"


def test_sqlitelsm_graph_escape_quoting(get_graph):
    graph = get_graph
    test_string = "That’s a Literal!!"
    graph.add(
        (
            URIRef("http://example.org/foo"),
            RDFS.label,
            Literal(test_string, datatype=XSD.string),
        )
    )
    graph.commit()
    assert ("That’s a Literal!!") in graph.serialize(format="xml")


def test_sqlitelsm_graph_namespaces(get_graph):
    graph = get_graph
    no_of_default_namespaces = len(list(graph.namespaces()))
    graph.bind("exorg", "http://example.org/")
    graph.bind("excom", "http://example.com/")
    assert (
        len(list(graph.namespaces())) == no_of_default_namespaces + 2
    ), f"expected {no_of_default_namespaces + 2}, got {len(list(graph.namespaces()))}"
    assert ("exorg", URIRef("http://example.org/")) in list(graph.namespaces())


def test_sqlitelsm_graph_readable_index():
    assert readable_index(111) == "s,p,o"


def test_sqlitelsm_graph_reopening_db(get_graph):
    graph = get_graph
    graph.add((michel, likes, pizza))
    graph.add((michel, likes, cheese))
    graph.commit()
    graph.store.close()
    graph.store.open(path, create=False)
    ntriples = list(graph.triples((None, None, None)))
    assert len(ntriples) == 5, f"Expected 5 not {len(ntriples)}"


def test_sqlitelsm_graph_missing_db_returns_no_store(get_graph):
    graph = get_graph
    graph.store.close()
    shutil.rmtree(path)
    assert graph.store.open(path, create=False) == NO_STORE


def test_sqlitelsm_graph_reopening_missing_db_returns_no_store(get_graph):
    graph = get_graph
    graph.store.close()
    graph.store.destroy()
    assert graph.open(path, create=False) == NO_STORE


def test_sqlitelsm_graph_isopen_db(get_graph):
    graph = get_graph
    assert graph.store.is_open() is True
    graph.store.close()
    assert graph.store.is_open() is False


def test_sqlitelsm_conjunctive_graph_namespaces(get_conjunctive_graph):
    graph = get_conjunctive_graph
    no_of_default_namespaces = len(list(graph.namespaces()))
    graph.bind("exorg", "http://example.org/")
    graph.bind("excom", "http://example.com/")
    assert (
        len(list(graph.namespaces())) == no_of_default_namespaces + 2
    ), f"expected {no_of_default_namespaces + 2}, got {len(list(graph.namespaces()))}"
    assert ("exorg", URIRef("http://example.org/")) in list(graph.namespaces())


def test_sqlitelsm_conjunctive_graph_readable_index(get_conjunctive_graph):
    assert repr(readable_index(111)) == "'s,p,o'"


def test_sqlitelsm_conjunctive_graph_triples_context_reset(
    get_conjunctive_graph,
):
    graph = get_conjunctive_graph
    # I don't think this is doing what it says on the tin
    graph.add((michel, likes, pizza))
    graph.add((michel, likes, cheese))
    graph.commit()
    ntriples = list(
        graph.triples((None, None, None), context=next(graph.contexts()))
    )
    assert len(ntriples) == 0, len(ntriples)


def test_sqlitelsm_conjunctive_graph_remove_context_reset(
    get_conjunctive_graph,
):
    cg = get_conjunctive_graph
    graph = cg.get_context(identifier=context1)

    graph.add((michel, likes, pizza))
    graph.add((michel, likes, cheese))
    graph.commit()

    triples = list(graph.triples((None, None, None)))

    assert len(triples) == 2, len(triples)

    graph.remove((michel, likes, cheese))
    graph.remove((michel, likes, pizza))

    graph.commit()

    triples = list(graph.triples((None, None, None)))

    assert len(triples) == 0, len(triples)


def test_sqlitelsm_conjunctive_graph_default_remove_triples(
    get_conjunctive_graph,
):
    graph = get_conjunctive_graph
    graph.add((michel, likes, pizza))
    graph.add((michel, likes, cheese))
    graph.commit()
    ntriples = list(
        graph.triples((None, None, None), context=next(graph.contexts()))
    )
    assert len(ntriples) == 0, len(ntriples)


def test_sqlitelsm_conjunctive_graph_nquads_default_graph(
    get_conjunctive_graph,
):
    data = """
    <http://example.org/s1> <http://example.org/p1> <http://example.org/o1> .
    <http://example.org/s2> <http://example.org/p2> <http://example.org/o2> .
    <http://example.org/s3> <http://example.org/p3> <http://example.org/o3> <http://example.org/g3> .
    """

    publicID = URIRef("http://example.org/g0")

    graph = get_conjunctive_graph
    graph.parse(data=data, format="nquads", publicID=publicID)

    assert len(graph) == 6, len(graph)

    # Three contexts@ the default, the publicID and one from the quad
    assert (
        len(list(graph.contexts())) == 3
    ), f"contexts:\n{pformat(list(graph.contexts()))}"

    assert len(graph.get_context(publicID)) == 2, len(
        graph.get_context(publicID)
    )


def test_sqlitelsm_conjunctive_graph_serialize(get_conjunctive_graph):
    graph = get_conjunctive_graph
    graph.get_context(context1).add((bob, likes, pizza))
    graph.get_context(context2).add((bob, likes, pizza))
    s = graph.serialize(format="nquads")
    assert len([x for x in s.split("\n") if x.strip()]) == 5

    g2 = ConjunctiveGraph(store="SQLiteLSM")
    g2.open(tempfile.mktemp(prefix="sqlitelsmstoretest"), create=True)
    g2.parse(data=s, format="nquads")

    assert len(graph) == len(g2)
    # default graphs are unique to each ConjunctiveGraph, so exclude
    assert (
        sorted(x.identifier for x in graph.contexts())[1:]
        == sorted(x.identifier for x in g2.contexts())[1:]
    )
