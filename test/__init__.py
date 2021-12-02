from rdflib import plugin

from rdflib import store

plugin.register(
    "SQLiteLSM",
    store.Store,
    "rdflib_sqlitelsm.sqlitelsmstore",
    "SQLiteLSMStore",
)
