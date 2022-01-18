# -*- coding: utf-8 -*-
"""
An adaptation of the BerkeleyDB Store's key-value approach to use the
Python sqlite3 module with a key-value interface as a back-end.

Based on an original contribution by Drew Perttula: `TokyoCabinet Store
<http://bigasterisk.com/darcs/?r=tokyo;a=tree>`_.

and then a Kyoto Cabinet version by Graham Higgins <gjh@bel-epa.com>

this one by Graham Higgins

berkeleydb uses the default API get and put, so has to handle
string-to-bytes conversion in the args provided to every call
on get/put. By using a store-specific _get/_put which takes an
additional "dbname" argument, not only can store-specific
differences in get/put call be coded for but it is also offers
the opportunity to do the string-bytes conversion at the point
of db API and so the calls can be expunged of conversion cruft.

The cost is a difference of model:

Berkeleydb:

# def namespace(self, prefix):
#     prefix = prefix.encode("utf-8")
#     ns = self.__namespace.get(prefix, None)
#     if ns is not None:
#         return URIRef(ns.decode("utf-8"))
#     return None
vs.

# def namespace(self, prefix):
#     ns = _get(self.__namespace, prefix)
#     if ns is not None:
#         return URIRef(ns)
#     return None

There is also a difference in the API w.r.t. accessing a range.
BerkeleyDB takes a cursor-based approach:

# index = self.__indices[0]
# cursor = index.cursor()
# current = cursor.set_range(prefix)
# count = 0
# while current:
#    key, value = current
#    if key.startswith(prefix):
#        count += 1
#        # Hack to stop 2to3 converting this to next(cursor)
#        current = getattr(cursor, "next")()
#    else:
#        break
# cursor.close()
# return count

whereas LSM offers an interator:

# return len(
#   [key for key in self.__indices[0][prefix:])
#

"""
import logging
import os
from threading import Thread
from functools import lru_cache
from urllib.request import pathname2url

from lsm import LSM
from rdflib.store import NO_STORE, VALID_STORE, Store
from rdflib.term import URIRef

logging.basicConfig(level=logging.ERROR, format="%(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


__all__ = ["SQLiteLSMStore"]


dbparams = dict(
    page_size=4096,
    block_size=1024,
    multiple_processes=True,
    safety=0,
    autoflush=1024,
    autocheckpoint=2048,
    use_log=False,
    binary=False,
)


class SQLiteLSMStore(Store):
    """
    A store that allows for on-disk persistent using sqlite3 as a
    key/value DB.

    This store allows for quads as well as triples. See examples of use
    in both the `examples.sqlitelsm_example` and `test.test_slitelsm_store`
    files.

    """

    context_aware = True
    formula_aware = True
    transaction_aware = False
    graph_aware = True
    db_env = None
    should_create = True

    def __init__(self, configuration=None, identifier=None):
        self.__open = False
        self._terms = 0
        self.__identifier = identifier
        super(SQLiteLSMStore, self).__init__(configuration)
        self._loads = self.node_pickler.loads
        self._dumps = self.node_pickler.dumps
        self.dbdir = configuration
        self.__needs_sync = None

        self.__indices = None
        self.__indices_info = None
        self.__lookup_dict = None
        self.__contexts = None
        self.__namespace = None
        self.__prefix = None
        self.__k2i = None
        self.__i2k = None

    def __get_identifier(self):
        return self.__identifier  # pragma: no cover

    identifier = property(__get_identifier)

    def is_open(self):
        return self.__open

    def _init_db_environment(self, path, create=True):
        """
        Initialise the database environment prior to creating the files
        """
        dbpathname = os.path.abspath(self.path)
        # Help the user to avoid writing over an existing database

        if self.should_create:
            if os.path.exists(dbpathname):
                if os.listdir(dbpathname) != []:
                    raise Exception(f"Database {dbpathname} aready exists, please move or delete it.")
                else:
                    self.dbdir = dbpathname
            else:
                os.mkdir(dbpathname)
                self.dbdir = dbpathname
        else:
            if not os.path.exists(dbpathname):
                return NO_STORE
            else:
                self.dbdir = dbpathname

        self.__indices = [
            None,
        ] * 3
        self.__indices_info = [
            None,
        ] * 3
        for i in range(0, 3):
            index_name = to_key_func(i)(
                (
                    "s",
                    "p",
                    "o",
                ),
                "c",
            )
            index = LSM(os.path.join(self.dbdir, index_name + ".ldb"), **dbparams)
            self.__indices[i] = index
            self.__indices_info[i] = (index, to_key_func(i), from_key_func(i))

        lookup = {}
        for i in range(0, 8):
            results = []
            for start in range(0, 3):
                score = 1
                _len = 0
                for j in range(start, start + 3):
                    if i & (1 << (j % 3)):
                        score = score << 1
                        _len += 1
                    else:
                        break
                tie_break = 2 - start
                results.append(((score, tie_break), start, _len))

            results.sort()
            score, start, _len = results[-1]

            def get_prefix_func(start, end):
                def get_prefix(triple, context):
                    if context is None:
                        yield ""
                    else:
                        yield context
                    i = start
                    while i < end:
                        yield triple[i % 3]
                        i += 1
                    yield ""

                return get_prefix

            lookup[i] = (
                self.__indices[start],
                get_prefix_func(start, start + _len),
                from_key_func(start),
                results_from_key_func(start, self._from_string),
            )

        self.__lookup_dict = lookup
        self.__contexts = LSM(os.path.join(self.dbdir, "contexts.ldb"), **dbparams)
        self.__namespace = LSM(os.path.join(self.dbdir, "namespace.ldb"), **dbparams)
        self.__prefix = LSM(os.path.join(self.dbdir, "prefix.ldb"), **dbparams)
        self.__k2i = LSM(os.path.join(self.dbdir, "k2i.ldb"), **dbparams)
        self.__i2k = LSM(os.path.join(self.dbdir, "i2k.ldb"), **dbparams)

    def open(self, path, create=True):
        self.should_create = create
        self.path = path

        if self.__identifier is None:
            self.__identifier = URIRef(pathname2url(os.path.abspath(path)))

        db_env = self._init_db_environment(path, create)
        if db_env == NO_STORE:
            return NO_STORE
        self.db_env = db_env

        for db in self.__indices:
            assert db.open() is True
        assert self.__contexts.open() is True
        assert self.__namespace.open() is True
        assert self.__prefix.open() is True
        assert self.__k2i.open() is True
        assert self.__i2k.open() is True

        try:
            self._terms = int(self.__k2i["__terms__"])
            assert isinstance(self._terms, int)
        except KeyError:
            pass  # new store, no problem

        self.__open = True

        self.__needs_sync = False
        t = Thread(target=self.__sync_run)
        t.setDaemon(True)
        t.start()
        self.__sync_thread = t
        return VALID_STORE

    def __sync_run(self):
        from time import sleep, time

        try:
            min_seconds, max_seconds = 10, 300
            while self.__open:
                if self.__needs_sync:
                    t0 = t1 = time()
                    self.__needs_sync = False
                    while self.__open:
                        sleep(0.1)
                        if self.__needs_sync:
                            t1 = time()
                            self.__needs_sync = False
                        if time() - t1 > min_seconds or time() - t0 > max_seconds:
                            self.__needs_sync = False
                            logger.debug("sync")
                            self.sync()
                            break
                else:
                    sleep(1)
        except Exception as e:  # pragma: no cover
            logger.exception(e)  # pragma: no cover

    def sync(self):
        if self.__open:
            for i in self.__indices:
                i.sync()
            self.__contexts.sync()
            self.__namespace.sync()
            self.__prefix.sync()
            self.__i2k.sync()
            self.__k2i.sync()

    def close(self, commit_pending_transaction=False):
        self.__open = False
        self.__sync_thread.join()
        for i in self.__indices:
            i.close()
        self.__contexts.close()
        self.__namespace.close()
        self.__prefix.close()
        self.__i2k.close()
        self.__k2i.close()

    def dumpdb(self):

        dump = "\n"
        dbs = {
            "self.__contexts": self.__contexts,
            "self.__namespace": self.__namespace,
            "self.__prefix": self.__prefix,
            "self.__k2i": self.__k2i,
            "self.__i2k": self.__i2k,
        }

        for k, v in dbs.items():
            dump += f"db: {k}\n"
            for key, value in v:
                dump += f"\t{key}: {value.encode('utf-8')}\n"
        return dump

    def close(self, commit_pending_transaction=False):
        for i in self.__indices:
            i.close()
        self.__contexts.close()
        self.__namespace.close()
        self.__prefix.close()
        self.__i2k.close()
        self.__k2i.close()
        self.__open = False

    def destroy(self, configuration=""):
        assert self.__open is False, "The Store must be closed."

        path = configuration or self.dbdir
        # logger.warning(f"path for destruction: {path}")
        if os.path.exists(path):
            import shutil

            shutil.rmtree(path)

    def add(self, triple, context, quoted=False):
        """
        Add a triple to the store of triples.
        """
        (subject, predicate, object) = triple
        assert self.__open, "The Store must be open."
        assert context != self, "Can not add triple directly to store"
        # Add the triple to the Store, triggering TripleAdded events
        Store.add(self, (subject, predicate, object), context, quoted)

        _to_string = self._to_string

        s = _to_string(subject)
        p = _to_string(predicate)
        o = _to_string(object)
        c = _to_string(context)

        cspo, cpos, cosp = self.__indices

        try:
            value = cspo[f"{c}^{s}^{p}^{o}^"]
        except KeyError:
            value = None

        if value is None:
            self.__contexts[c] = ""

            try:
                contexts_value = cspo[f"{''}^{s}^{p}^{o}^"]
            except KeyError:
                contexts_value = ""

            contexts = set(contexts_value.split("^"))
            contexts.add(c)

            contexts_value = "^".join(contexts)
            assert contexts_value is not None

            cspo[f"{c}^{s}^{p}^{o}^"] = ""
            cpos[f"{c}^{p}^{o}^{s}^"] = ""
            cosp[f"{c}^{o}^{s}^{p}^"] = ""
            if not quoted:  # pragma: no cover
                cspo[f"^{s}^{p}^{o}^"] = contexts_value
                cpos[f"^{p}^{o}^{s}^"] = contexts_value
                cosp[f"^{o}^{s}^{p}^"] = contexts_value

            self.__needs_sync = True

    def __clear(self):
        dbs = [
            self.__contexts,
            self.__namespace,
            self.__prefix,
            self.__k2i,
            self.__i2k,
        ] + self.__indices

        for db in dbs:
            with db.cursor() as cursor:
                for key, value in cursor:
                    db.delete(key)

    def __remove(self, spo, c, quoted=False):
        s, p, o = spo
        cspo, cpos, cosp = self.__indices
        try:
            contexts_value = cspo["^{s}^{p}^{o}^"]
        except KeyError:
            contexts_value = ""
        contexts = set(contexts_value.split("^"))
        contexts.discard(c)
        contexts_value = "^".join(contexts)
        for i, _to_key, _from_key in self.__indices_info:
            i.delete(_to_key((s, p, o), c))

        if contexts_value:
            for i, _to_key, _from_key in self.__indices_info:
                i[_to_key((s, p, o), "")] = contexts_value

        else:
            for i, _to_key, _from_key in self.__indices_info:
                i.delete(_to_key((s, p, o), ""))

    def remove(self, spo, context):
        subject, predicate, object = spo
        assert self.__open, "The Store must be open."
        Store.remove(self, (subject, predicate, object), context)
        _to_string = self._to_string

        if context is not None:
            if context == self:
                context = None
        needs_sync = False
        if subject is None and predicate is None and object is None and context is None:
            self.__clear()
            needs_sync = True

        elif subject is not None and predicate is not None and object is not None and context is not None:
            s = _to_string(subject)
            p = _to_string(predicate)
            o = _to_string(object)
            c = _to_string(context)
            try:
                value = self.__indices[0][f"{c}^{s}^{p}^{o}^"]
            except KeyError:
                value = None

            if value is not None:
                self.__remove((s, p, o), c)
                needs_sync = True
        else:
            index, prefix, from_key, results_from_key = self.__lookup((subject, predicate, object), context)
            for key, value in index[prefix:]:
                if key.startswith(prefix):
                    c, s, p, o = from_key(key)
                    if context is None:
                        contexts_value = value or ""
                        # remove triple from all non quoted contexts
                        contexts = set(contexts_value.split("^"))
                        # and from the conjunctive index
                        contexts.add("")
                        for c in contexts:
                            for i, _to_key, _ in self.__indices_info:
                                i.delete(_to_key((s, p, o), c))
                    else:
                        self.__remove((s, p, o), c)
                    needs_sync = True

            if context is not None:
                if subject is None and predicate is None and object is None:
                    self.__contexts.delete(_to_string(context))
                    needs_sync = True

            self.__needs_sync = needs_sync

    def triples(self, spo, context=None):
        """A generator over all the triples matching"""
        assert self.__open, "The Store must be open."
        subject, predicate, object = spo

        if context is not None:
            if context in [self.identifier, self]:
                context = None  # pragma: no cover

        # _from_string = self._from_string ## UNUSED
        index, prefix, from_key, results_from_key = self.__lookup((subject, predicate, object), context)

        for key, value in index[prefix:]:
            if key.startswith(prefix):
                yield results_from_key(key, subject, predicate, object, value)

    def __len__(self, context=None):
        assert self.__open, "The Store must be open."
        if context is not None:
            if context == self:
                context = None

        if context is None:
            prefix = "^"
            return len(list(self.__indices[0][prefix:]))
        else:
            prefix = f"{self._to_string(context)}^"
            return len(list(self.__indices[0][prefix : prefix + "xxxx"]))

    def bind(self, prefix, namespace):
        try:
            bound_prefix = self.__prefix[namespace]
            self.__namespace.delete(bound_prefix)
        except KeyError:
            self.__prefix[namespace] = prefix
            self.__namespace[prefix] = namespace

    def unbind(self, prefix):
        self.__namespace.delete(prefix)

    def namespace(self, prefix):
        try:
            ns = self.__namespace[prefix]
            return URIRef(ns)
        except KeyError:
            return None

    def prefix(self, namespace):
        try:
            prefix = self.__prefix[namespace]
            return prefix
        except KeyError:
            return None

    def namespaces(self):
        for prefix, namespace in self.__namespace.items():
            yield prefix, URIRef(namespace)

    def contexts(self, triple=None):
        _from_string = self._from_string
        _to_string = self._to_string

        if triple:
            s, p, o = triple
            s = _to_string(s)
            p = _to_string(p)
            o = _to_string(o)
            contexts = self.__indices[0][f"^{s}^{p}^{o}^"]

            if contexts:
                for c in contexts.split("^"):
                    if c:
                        yield _from_string(c)
        else:
            for k in self.__contexts.keys():
                yield _from_string(k)

    @lru_cache(maxsize=5000)
    def add_graph(self, graph):
        self.__contexts[self._to_string(graph)] = ""

    def remove_graph(self, graph):
        self.remove((None, None, None), graph)

    @lru_cache(maxsize=5000)
    def _from_string(self, i):
        """
        rdflib term from index number (as a string)
        """
        k = self.__i2k[str(int(i))]
        if k is not None:
            val = self._loads(k.encode("latin-1"))
            return val
        else:
            raise Exception(f"Key for {i} is None")  # pragma: no cover

    @lru_cache(maxsize=5000)
    def _to_string(self, term):
        """
        index number (as a string) from rdflib term
        """
        k = self._dumps(term).decode("latin-1")
        try:
            i = self.__k2i[k]
        except KeyError:  # pragma: no cover
            i = None  # pragma: no cover

        if i is None:  # (from BdbApi)
            # Does not yet exist, increment refcounter and create
            self._terms += 1
            i = str(self._terms)
            self.__i2k[i] = k
            self.__k2i[k] = i
            self.__k2i["__terms__"] = str(self._terms)
        return i

    def __lookup(self, spo, context):
        subject, predicate, object = spo
        _to_string = self._to_string
        if context is not None:
            context = _to_string(context)
        i = 0
        if subject is not None:
            i += 1
            subject = _to_string(subject)
        if predicate is not None:
            i += 2
            predicate = _to_string(predicate)
        if object is not None:
            i += 4
            object = _to_string(object)
        index, prefix_func, from_key, results_from_key = self.__lookup_dict[i]
        prefix = "^".join(prefix_func((subject, predicate, object), context))
        return index, prefix, from_key, results_from_key


def to_key_func(i):
    def to_key(triple, context):
        "Takes a string; returns key"
        return "^".join(
            (
                context,
                triple[i % 3],
                triple[(i + 1) % 3],
                triple[(i + 2) % 3],
                "",
            )
        )  # "" to tac on the trailing ^

    return to_key


def from_key_func(i):
    def from_key(key):
        "Takes a key; returns string"
        parts = key.split("^")
        return (
            parts[0],
            parts[(3 - i + 0) % 3 + 1],
            parts[(3 - i + 1) % 3 + 1],
            parts[(3 - i + 2) % 3 + 1],
        )

    return from_key


def results_from_key_func(i, from_string):
    def from_key(key, subject, predicate, object, contexts_value):
        "Takes a key and subject, predicate, object; returns tuple for yield"
        parts = key.split("^")
        if subject is None:
            # TODO: i & 1: # dis assemble and/or measure to see which is faster
            # subject is None or i & 1
            s = from_string(parts[(3 - i + 0) % 3 + 1])
        else:
            s = subject
        if predicate is None:  # i & 2:
            p = from_string(parts[(3 - i + 1) % 3 + 1])
        else:
            p = predicate
        if object is None:  # i & 4:
            o = from_string(parts[(3 - i + 2) % 3 + 1])
        else:
            o = object
        return (  # pragma: no cover
            (s, p, o),
            (from_string(c) for c in contexts_value.split("^") if c),
        )

    return from_key


def readable_index(i):
    s, p, o = "?" * 3
    if i & 1:
        s = "s"
    if i & 2:
        p = "p"
    if i & 4:
        o = "o"
    return f"{s},{p},{o}"
