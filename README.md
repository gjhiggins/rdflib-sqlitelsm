# A SQLite LSM-backed persistence plugin store for RDFLib

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![Validation: install and test](https://github.com/gjhiggins/rdflib-sqlitelsm/actions/workflows/validate.yaml/badge.svg)](https://github.com/gjhiggins/rdflib-sqlitelsm/actions/workflows/validate.yaml)


An adaptation of RDFLib BerkeleyDB Store’s key-value approach, using SQLite’s [LSM](https://sqlite.org/src4/doc/trunk/www/lsmusr.wiki) as a back-end via the Python [lsm-db](https://github.com/coleifer/python-lsm-db) wrapper:

> “LSM is an embedded database library for key-value data, roughly similar in scope to Berkeley DB, LevelDB or KyotoCabinet. Both keys and values are specified and stored as byte arrays.”

Implemented by Graham Higgins, based on an original contribution by Drew Perttula.


## Installation options

### Install with pip from github repos

```bash
pip install git+https://github.com/RDFLib/rdflib-sqlitelsm#egg=rdflib_sqlitelsm`
```

### Install by cloning github repos, then pip install

```bash
git clone https://github.com/RDFLib/rdflib-sqlitelsm.git
cd rdflib-sqlitelsm
pip install .
# Optionally
pip install -r requirements.dev.txt
./run_tests.py
```

### Example usage:

```python
from rdflib import plugin, Graph, URIRef
from rdflib.store import Store
import tempfile
import os


def example():
    path = os.path.join(tempfile.gettempdir(), "testsqlitelsm")
    store = plugin.get("SQLiteLSM", Store)(
        identifier=URIRef("rdflib_sqlitelsm_test")
    )

    g = Graph(store)
    g.open(path, create=True)

    # Parse in an RDF file hosted on the Internet
    g.parse("http://www.w3.org/People/Berners-Lee/card")

    # Loop through each triple in the graph (subj, pred, obj)
    for subj, pred, obj in g:
        # Check if there is at least one triple in the Graph
        if (subj, pred, obj) not in g:
            raise Exception("It better be!")
    assert len(g) == 86, len(g)
    g.close()

    g.destroy(configuration=path)
```


