# -*- coding: utf-8 -*-
import tempfile
import os
from rdflib import URIRef
from rdflib.graph import Graph


path = os.path.join(tempfile.gettempdir(), "test_sqlitelsm")


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
    # Parse in an RDF file hosted on the Internet
    g.parse("http://www.w3.org/People/Berners-Lee/card")

    # Loop through each triple in the graph (subj, pred, obj)
    for subj, pred, obj in g:
        # Check if there is at least one triple in the Graph
        if (subj, pred, obj) not in g:
            raise Exception("It better be!")

    assert len(g) == 86, len(g)

    # Print out the entire Graph in the RDF Turtle format
    # print(g.serialize(format="turtle"))
    g.close()
    g.destroy(configuration=path)
