import unittest
import os
import tempfile
import shutil
import rdflib
from rdflib_sqlitelsm.sqlitelsmstore import readable_index, NoopMethods
from rdflib.graph import Graph, ConjunctiveGraph, Literal, URIRef
from rdflib.namespace import XSD, RDFS
from rdflib.store import VALID_STORE
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
uri1 = URIRef("urn:graph1")
uri2 = URIRef("urn:graph2")


class TestSQLiteLSMGraphCore(unittest.TestCase):
    rt = None

    def setUp(self):
        store = "SQLiteLSM"
        self.graph = Graph(store=store)
        self.path = os.path.join(
            tempfile.gettempdir(), f"test_{store.lower()}"
        )
        self.rt = self.graph.open(self.path, create=True)
        assert self.rt == VALID_STORE, "The underlying store is corrupt"
        assert (
            len(self.graph) == 0
        ), "There must be zero triples in the graph just after store (file) creation"
        data = """
                PREFIX : <https://example.org/>

                :a :b :c .
                :d :e :f .
                :d :g :h .
                """
        self.graph.parse(data=data, format="ttl")
        assert (
            len(self.graph) == 3
        ), "There must be three triples in the graph after the first data chunk parse"

    def tearDown(self):
        self.graph.close()
        self.graph.destroy(configuration=self.path)

    def test_create_db(self):
        self.graph.add((michel, likes, pizza))
        self.graph.add((michel, likes, cheese))
        self.graph.commit()
        assert (
            len(self.graph) == 5
        ), f"There must be three triples in the graph after the first data chunk parse, not {len(self.graph)}"

    # @unittest.skip("WIP")
    # def test_dumpdb(self):
    #     logger.debug(self.graph.store.dumpdb())

    def test_escape_quoting(self):
        assert (
            len(self.graph) == 3
        ), "There must be three triples in the graph after the first data chunk parse"
        test_string = "That’s a Literal!!"
        self.graph.add(
            (
                URIRef("http://example.org/foo"),
                RDFS.label,
                Literal(test_string, datatype=XSD.string),
            )
        )
        self.graph.commit()
        assert ("That’s a Literal!!") in self.graph.serialize(format="xml")

    def test_namespaces(self):
        self.graph.bind("dc", "http://http://purl.org/dc/elements/1.1/")
        self.graph.bind("foaf", "http://xmlns.com/foaf/0.1/")
        self.assertEqual(
            len(list(self.graph.namespaces())),
            7,
            f"expected 6, got {len(list(self.graph.namespaces()))}",
        )
        self.assertIn(
            ("foaf", URIRef("http://xmlns.com/foaf/0.1/")),
            list(self.graph.namespaces()),
        )

    def test_readable_index(self):
        assert readable_index(111) == "s,p,o"

    def test_missing_db_exception(self):
        self.graph.store.close()
        if getattr(self, "path", False) and self.path is not None:
            if os.path.exists(self.path):
                if os.path.isdir(self.path):
                    shutil.rmtree(self.path)
                elif len(self.path.split(":")) == 1:
                    os.unlink(self.path)
                else:
                    os.remove(self.path)
        self.graph.store.open(self.path, create=True)
        ntriples = self.graph.triples((None, None, None))
        self.assertTrue(len(list(ntriples)) == 0)

    def test_reopening_db(self):
        self.graph.add((michel, likes, pizza))
        self.graph.add((michel, likes, cheese))
        self.graph.commit()
        self.graph.store.close()
        self.graph.store.open(self.path, create=False)
        ntriples = self.graph.triples((None, None, None))
        listntriples = list(ntriples)
        self.assertEqual(
            len(listntriples), 5, f"Expected 2 not {len(listntriples)}"
        )

    def test_reopening_missing_db(self):
        self.graph.store.close()
        with self.assertRaises(Exception):
            self.graph.store.open("NotAnExistingDB", create=False)

    def test_isopen_db(self):
        self.assertTrue(self.graph.store.is_open() is True)
        self.graph.store.close()
        self.assertTrue(self.graph.store.is_open() is False)


class TestSQLiteLSMConjunctiveGraphCore(unittest.TestCase):
    def setUp(self):
        store = "SQLiteLSM"
        self.graph = ConjunctiveGraph(store=store)
        self.path = tempfile.mktemp(prefix="testsqlite")
        self.graph.open(self.path, create=True)

    def tearDown(self):
        self.graph.close()
        self.graph.destroy(self.path)

    def test_namespaces(self):
        self.graph.bind("dc", "http://http://purl.org/dc/elements/1.1/")
        self.graph.bind("foaf", "http://xmlns.com/foaf/0.1/")
        self.assertTrue(len(list(self.graph.namespaces())) == 6)
        self.assertIn(
            ("foaf", rdflib.term.URIRef("http://xmlns.com/foaf/0.1/")),
            list(self.graph.namespaces()),
        )

    def test_readable_index(self):
        self.assertEqual(repr(readable_index(111)), "'s,p,o'")

    def test_triples_context_reset(self):
        # I don't think this is doing what it says on the tin
        self.graph.add((michel, likes, pizza))
        self.graph.add((michel, likes, cheese))
        self.graph.commit()
        ntriples = list(
            self.graph.triples(
                (None, None, None), context=next(self.graph.contexts())
            )
        )
        self.assertTrue(len(ntriples) == 2, len(ntriples))

    def test_remove_context_reset(self):
        self.graph.add((michel, likes, pizza))
        self.graph.add((michel, likes, cheese))
        self.graph.commit()
        self.graph.remove((michel, likes, cheese, next(self.graph.contexts())))
        self.graph.commit()
        ntriples = list(self.graph.triples((None, None, None)))
        self.assertTrue(len(ntriples) == 1, len(ntriples))

    def test_remove_db_exception(self):
        self.graph.add((michel, likes, pizza))
        self.graph.add((michel, likes, cheese))
        self.graph.commit()
        ntriples = list(
            self.graph.triples(
                (None, None, None), context=next(self.graph.contexts())
            )
        )
        self.assertTrue(len(ntriples) == 2, len(ntriples))

    def test_nquads_default_graph(self):
        data = """
        <http://example.org/s1> <http://example.org/p1> <http://example.org/o1> .
        <http://example.org/s2> <http://example.org/p2> <http://example.org/o2> .
        <http://example.org/s3> <http://example.org/p3> <http://example.org/o3> <http://example.org/g3> .
        """

        publicID = URIRef("http://example.org/g0")

        self.graph.parse(data=data, format="nquads", publicID=publicID)

        assert len(self.graph) == 3, len(self.graph)
        assert len(list(self.graph.contexts())) == 2, len(
            list(self.graph.contexts())
        )
        assert len(self.graph.get_context(publicID)) == 2, len(
            self.graph.get_context(publicID)
        )

    def test_serialize(self):
        self.graph.get_context(uri1).add((bob, likes, pizza))
        self.graph.get_context(uri2).add((bob, likes, pizza))
        s = self.graph.serialize(format="nquads")
        self.assertEqual(len([x for x in s.split("\n") if x.strip()]), 2)

        g2 = ConjunctiveGraph(store="SQLiteLSM")
        g2.open(tempfile.mktemp(prefix="sqlitelsmstoretest"), create=True)
        g2.parse(data=s, format="nquads")

        self.assertEqual(len(self.graph), len(g2))
        self.assertEqual(
            sorted(x.identifier for x in self.graph.contexts()),
            sorted(x.identifier for x in g2.contexts()),
        )


def test_NoopMethods():
    obj = NoopMethods()
    res = obj.__getattr__("amethod")
    assert res() is None


if __name__ == "__main__":
    unittest.main()
