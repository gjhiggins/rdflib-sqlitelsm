#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
import codecs
from setuptools import setup, find_packages

kwargs = {}
kwargs["install_requires"] = [
    "setuptools",
    "rdflib>=6.0",
    "Cython",
    "lsm-db",
    "importlib-metadata; python_version < '3.8.0'",
]

kwargs["dependency_links"] = [
    "git+https://github.com/RDFLib/rdflib.git#egg=rdflib",
    "git+https://github.com/coleifer/python-lsm-db.git#egg=lsm-db"
]

kwargs["tests_require"] = [
    "pytest",
    "pytest-cov",
    "pytest-subtests",
]

kwargs["extras_require"] = {
    "tests": kwargs["tests_require"],
    "docs": ["sphinx < 5", "sphinxcontrib-apidoc"],
}


def find_version(filename):
    _version_re = re.compile(r'__version__ = "(.*)"')
    for line in open(filename):
        version_match = _version_re.match(line)
        if version_match:
            return version_match.group(1)


def open_local(paths, mode="r", encoding="utf8"):
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)), *paths)
    return codecs.open(path, mode, encoding)


# long_description="""
# An adaptation of RDFLib BerkeleyDB Store’s key-value approach, using Leveldb as a back-end.

# Based on an original contribution by Drew Perttula.
# """
with open_local(["README.md"], encoding="utf-8") as readme:
    long_description = readme.read()

version = find_version("rdflib_sqlitelsm/__init__.py")

packages = find_packages(exclude=("examples*", "test*"))

if os.environ.get("READTHEDOCS", None):
    # if building docs for RTD
    # install examples, to get docstrings
    packages.append("examples")

setup(
    name="rdflib-sqlitelsm",
    version=version,
    description="rdflib extension adding SQLite’s LSM as back-end store",
    author="RDFLib team",
    maintainer="Graham Higgins",
    maintainer_email="gjhiggins@gmail.com",
    url="https://github.com/RDFLib/rdflib-sqlitelsm",
    license="bsd-3-clause",
    platforms=["any"],
    python_requires=">=3.7",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: BSD License",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Operating System :: OS Independent",
        "Natural Language :: English",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=packages,
    entry_points={
        "rdf.plugins.store": [
            "SQLiteLSM = rdflib_sqlitelsm.sqlitelsmstore:SQLiteLSMStore",
        ],
    },
    **kwargs,
)
