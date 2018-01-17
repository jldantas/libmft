# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name = "libmft",
    version = "0.7",
    author = "Julio Dantas",
    description = "A pure python library to parse MFT entries",
    url = "https://github.com/jldantas/libmft",
    license = "BSD 3-Clause",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
         "Development Status :: 5 - Production/Stable",
         "Intended Audience :: Developers",
         "Intended Audience :: Information Technology",
         "License :: OSI Approved :: BSD License",
         "Operating System :: OS Independent",
         "Programming Language :: Python :: 3.6",
         "Topic :: Security",
         "Topic :: Software Development :: Libraries :: Python Modules"
    ],
    keywords = "mft parser library python",
    python_requires = ">=3.6",
    packages = find_packages(exclude=['contrib', 'docs', 'tests*']),
)
