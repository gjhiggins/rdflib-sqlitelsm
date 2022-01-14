# -*- coding: utf-8 -*-
import tempfile
import os
from rdflib import URIRef
from rdflib.graph import ConjunctiveGraph, Graph

timblcardn3 = open(
    os.path.join(
        os.path.dirname(__file__),
        "consistent_test_data",
        "timbl-card.n3",
    )
).read()

path = os.path.join(tempfile.gettempdir(), "test_sqlitelsm")

if os.path.exists(path):
    if os.path.isdir(path):
        import shutil

        shutil.rmtree(path)
    else:
        os.remove(path)


def test_create():
    g = Graph("SQLiteLSM", URIRef("http://rdflib.net"))
    g.open(path, create=True)
    assert repr(g.identifier) == "rdflib.term.URIRef('http://rdflib.net')"
    assert (
        str(g)
        == "<http://rdflib.net> a rdfg:Graph;rdflib:storage [a rdflib:Store;rdfs:label 'SQLiteLSMStore']."
    )
    g.close()
    g.destroy(configuration=path)


def test_reuse():
    g = Graph("SQLiteLSM", URIRef("http://rdflib.net"))
    g.open(path, create=True)
    assert repr(g.identifier) == "rdflib.term.URIRef('http://rdflib.net')"
    assert (
        str(g)
        == "<http://rdflib.net> a rdfg:Graph;rdflib:storage [a rdflib:Store;rdfs:label 'SQLiteLSMStore']."
    )
    g.close()

    g = Graph("SQLiteLSM", URIRef("http://rdflib.net"))
    g.open(path, create=False)
    assert repr(g.identifier) == "rdflib.term.URIRef('http://rdflib.net')"
    assert (
        str(g)
        == "<http://rdflib.net> a rdfg:Graph;rdflib:storage [a rdflib:Store;rdfs:label 'SQLiteLSMStore']."
    )
    g.close()
    g.destroy(configuration=path)


def test_example():
    g = Graph("SQLiteLSM", URIRef("http://rdflib.net"))
    g.open(path, create=True)
    # Parse in an RDF file hosted locally
    g.parse(data=timblcardn3, format="n3")

    # Loop through each triple in the graph (subj, pred, obj)
    for subj, pred, obj in g:
        # Check if there is at least one triple in the Graph
        if (subj, pred, obj) not in g:
            raise Exception("It better be!")

    assert len(g) == 86, len(g)

    # Print out the entire Graph in the RDF Turtle format
    # print(g.serialize(format="turtle"))

    assert "b'4': b''" in g.store.dumpdb()

    g.close()
    g.destroy(configuration=path)


def test_basic():
    g = ConjunctiveGraph("SQLiteLSM", URIRef("http://rdflib.net"))
    g.open(path, create=True)

    assert g.identifier == URIRef("http://rdflib.net")

    try:
        g.open(path, create=True)
    except Exception:
        pass

    context1 = URIRef("urn:example:context-1")
    context2 = URIRef("urn:example:context-2")

    subgraph1 = g.get_context(context1)
    subgraph2 = g.get_context(context1)

    triple = (
        URIRef("urn:example:bob"),
        URIRef("urn:example:likes"),
        URIRef("urn:example:michel"),
    )

    assert subgraph1.identifier == context1

    subgraph1.add(triple)

    g.store.add_graph(subgraph1)

    assert len(list(g.triples(triple, context=context1))) == 1

    assert len(list(g.triples(triple, context=g.identifier))) == 1

    assert (
        str(list(g.store.contexts(triple)))
        == "[<Graph identifier=urn:example:context-1 (<class 'rdflib.graph.Graph'>)>]"
    )

    assert g.store.__len__(context=context1) == 0

    assert g.store.__len__(context=g.store) == 1

    assert len(list(g.store.contexts(triple))) == 1

    g.store.remove(triple, context1)

    g.store.remove((None, None, None), context1)

    g.store.remove((None, None, None), context1)

    g.store.remove((None, None, None), URIRef("urn:example:context-2"))

    assert len(list(g.contexts())) == 1

    g.store.remove_graph(subgraph1)

    assert len(list(g.contexts())) == 0

    g.store.add_graph(subgraph2)

    g.store.add(triple, context2)
    g.store.add(
        (
            URIRef("urn:example:michel"),
            URIRef("urn:example:likes"),
            URIRef("urn:example:bob"),
        ),
        context2,
        True,
    )

    assert len(list(g.contexts())) == 1

    g.store.remove_graph(g.store)

    g.close()
    g.destroy(configuration=path)
