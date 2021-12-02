"""
SQLite3 LSM (http://www.sqlite.org/src4/doc/trunk/www/lsmusr.wiki) in use as a persistent Graph store.
via the lsm-db LSM-Python interface (https://github.com/coleifer/python-lsm-db)

The store is named and referenced as "SQLiteLSM".

Example 1: simple actions

* creating a ConjunctiveGraph using the SQLiteLSM Store
* adding triples to it
* counting them
* closing the store, emptying the graph
* re-opening the store using the same DB files
* getting the same count of triples as before

Example 2: larger data

* loads multiple graphs downloaded from GitHub into a SQLiteLSM-baked graph stored in the folder gsq_vocabs.
* does not delete the DB at the end so you can see it on disk
"""
import os
from rdflib import plugin, Graph, ConjunctiveGraph, Namespace, Literal, URIRef
from rdflib.store import Store, NO_STORE, VALID_STORE
import tempfile


def example_1():
    """Creates a ConjunctiveGraph and performs some SQLiteLSM tasks with it"""

    print(f"\n{80 * '*'}\nExample 1: creates a ConjunctiveGraph and perform some SQLiteLSM tasks with it ...\n\n")
    # Declare we are using a SQLiteLSM Store
    store = plugin.get("SQLiteLSM", Store)(
        identifier=URIRef("rdflib_sqlitelsm_test")
    )
    graph = ConjunctiveGraph(store)
    path = os.path.join(tempfile.gettempdir(), "test_sqlitelsm")

    # Open previously created store, or create it if it doesn't exist yet
    # (always doesn't exist in this example as using temp file location)
    rt = graph.open(path, create=False)

    if rt == NO_STORE:
        # There is no underlying BerkeleyDB infrastructure, so create it
        print("Creating new DB\n")
        graph.open(path, create=True)
    else:
        print("Using existing DB\n")
        assert rt == VALID_STORE, "The underlying store is corrupt"

    print(f"Triples in graph before add: {len(graph)} (will always be 0 when using temp file for DB)\n")

    # Now we'll add some triples to the graph & commit the changes
    EG = Namespace("http://example.net/test/")
    graph.bind("eg", EG)

    graph.add((EG["pic:1"], EG.name, Literal("Jane & Bob")))
    graph.add((EG["pic:2"], EG.name, Literal("Squirrel in Tree")))

    graph.commit()

    print(f"Triples in graph after add: {len(graph)} (Should be 2)\n")

    # display the graph in Turtle
    print(graph.serialize())

    # close when done, otherwise BerkeleyDB will leak lock entries.
    graph.close()

    graph = None

    # reopen the graph
    graph = ConjunctiveGraph("SQLiteLSM")

    graph.open(path, create=False)

    print(f"\n\nTriples still in graph: {len(graph)} (should still be 2)\n")

    graph.close()

    # Clean up the temp folder to remove the BerkeleyDB database files...
    for f in os.listdir(path):
        os.unlink(path + "/" + f)
    os.rmdir(path)
    print(f"Example 1 completed\n{80 * '*'}\n\n")


def example_2():
    """Loads a number of SKOS vocabularies from GitHub into a SQLiteLSM-backed graph stored in the local folder
    'gsq_vocabs'

    Should print out the number of triples after each load, e.g.:
        177
        248
        289
        379
        421
        628
        764
        813
        965
        1381
        9666
        9719
        ...
    """
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
    import json
    import base64
    import time

    print(f"\n{80 * '*'}\nExample 2, loading a number of SKOS vocabularies from GitHub into a SQLiteLSM-backed graph\n")

    store = plugin.get("SQLiteLSM", Store)(
        identifier=URIRef("rdflib_sqlitelsm_test")
    )
    g = ConjunctiveGraph(store)

    path = os.path.join(tempfile.gettempdir(), "gsg_vocabs")
    g.open(path, create=True)

    # gsq_vocabs = "https://api.github.com/repos/geological-survey-of-queensland/vocabularies/git/trees/master"
    gsq_vocabs = "https://api.github.com/repos/geological-survey-of-queensland/vocabularies/git/trees/cd7244d39337c1f4ef164b1cf1ea1f540a7277db"
    try:
        res = urlopen(
            Request(gsq_vocabs, headers={"Accept": "application/json"})
        )
    except HTTPError as e:
        return e.code, str(e), None

    data = res.read()
    encoding = res.info().get_content_charset("utf-8")
    j = json.loads(data.decode(encoding))
    try:
        for v in j["tree"][:12]:
            time.sleep(1)
            # process the element in GitHub result if it's a Turtle file
            if v["path"].endswith(".ttl"):
                # for each file, call it by URL, decode it and parse it into the graph
                r = urlopen(v["url"])
                content = json.loads(r.read().decode())["content"]
                g.parse(data=base64.b64decode(content).decode(), format="turtle")
                print(len(g))
    except Exception as e:
        raise Exception(f"{e} with {v}")
    print("loading complete")
    # Clean up the temp folder to remove the BerkeleyDB database files...
    for f in os.listdir(path):
        os.unlink(path + "/" + f)
    os.rmdir(path)
    print(f"Example 2 completed\n{80 * '*'}\n\n")


def example_3():
    """Loads into tempory storage'

    """
    from urllib.error import HTTPError
    from time import time
    import gc

    def cleanup(path):
        # Clean up the temp folder to remove the BerkeleyDB database files...
        for f in os.listdir(path):
            os.unlink(path + "/" + f)
        os.rmdir(path)

    print(f"\n{80 * '*'}\nExample 3, loading 45K triples from GitHub into memory and then adding them to a\nSQLiteLSM-backed ConjunctiveGraph...\n")

    doacc_abox = "https://raw.githubusercontent.com/DOACC/individuals/master/cryptocurrency.nt"
    path = os.path.join(tempfile.gettempdir(), "doacc")

    store = plugin.get("SQLiteLSM", Store)(
        identifier=URIRef("rdflib_sqlitelsm_test")
    )
    # Create an in-memory Graph into which to load the data
    memgraph = Graph("Memory", URIRef("http://rdflib.net"))

    # Factor out any gc-related lags
    gcold = gc.isenabled()
    gc.collect()
    gc.disable()

    # Load memgraph with remote data
    # 
    print("Downloading and parsing data\n")
    try:
        t0 = time()
        memgraph.parse(location=doacc_abox, format="nt")
        t1 = time()
    except HTTPError as e:
        cleanup(path)
        return e.code, str(e), None
    print(f"Time taken to download and parse {len(memgraph)} triples to in-memory graph: {t1 - t0:.4f}s\n")

    if os.path.exists(path):
        cleanup(path)

    # Create ConjunctiveGraph with LSM-backed Stg
    sqlitelsmgraph = ConjunctiveGraph(store)
    sqlitelsmgraph.open(path, create=True)

    # Step through the memgraph triples, adding to the LSM-backed ConjunctiveGraph

    t0 = time()
    for triple in memgraph.triples((None, None, None)):
        sqlitelsmgraph.add(triple)
    t1 = time()

    # Check total and report time
    assert len(sqlitelsmgraph) == 44947, len(sqlitelsmgraph)
    print(f"Time to add {len(sqlitelsmgraph)} triples to LSM-backed graph: {t1 - t0:.4f}s\n")

    # Close the graphs
    memgraph.close()
    sqlitelsmgraph.close()

    # Re-open (with “create=False”) sqlitelsmgraph with saved store:

    t0 = time()
    sqlitelsmgraph.open(path, create=False)
    t1 = time()
    print(f"Time to load {len(sqlitelsmgraph)} triples from LSM-backed store: {t1 - t0:.4f}s\n")

    if gcold:
        gc.enable()

    print(f"Example 3 completed\n{80 * '*'}\n\n")


if __name__ == "__main__":
    example_1()
    # example_2()
    example_3()
