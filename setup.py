from setuptools import setup

setup(
    name = "libmft",
    version = "0.5",
    author = "Julio Dantas"
    description = "A pure python library to parse MFT entries",
    url = "https://github.com/jldantas/libmft",
    license = "BSD 3-Clause",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
         "Development Status :: 2 - Pre-Alpha",
         "Intended Audience :: Developers",
         "License :: OSI Approved :: BSD License",
         "Operating System :: OS Independent",
         "Programming Language :: Python :: 3.6",
    ],
    keywords = "mft parser python",
    python_requires = ">=3.6",
    packages = ["libmft"],
)
