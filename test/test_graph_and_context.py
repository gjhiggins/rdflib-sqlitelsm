try:
    import plyvel

    assert plyvel
except ImportError:
    from nose import SkipTest

    raise SkipTest("SQLiteLSM not installed")

# import unittest
from . import context_case
from . import graph_case
import tempfile
import os

storename = "SQLiteLSM"
storetest = True
configString = os.path.join(tempfile.gettempdir(), "test_sqlite")


# @unittest.skip("WIP")
class SQLiteLSMGraphTestCase(graph_case.GraphTestCase):
    store_name = storename
    path = configString
    storetest = True


# @unittest.skip("WIP")
class SQLiteLSMContextTestCase(context_case.ContextTestCase):
    store_name = storename
    path = configString
    storetest = True
