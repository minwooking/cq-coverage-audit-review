# Brick Ontology Python package

Documentation available at readthedocs

## Installation

The brickschema package requires Python >= 3.11. It can be installed with pip:

brickschema ships two OWL 2 RL reasoners, both installed by default:

- reasonable is a fast OWL 2 RL reasoner written in
Rust. It is the default backend.
- OWLRL is a pure-Python implementation. It
delivers correct results but performs poorly on large or complex ontologies
(we have observed minutes to hours).

Pick one explicitly with the backend argument to expand:

## Quickstart

The main Graph object is just a subclass of the excellent RDFlib Graph library, so all features on rdflib.Graph will also work here.

Brief overview of the main features of the brickschema package:

## Features

brickschema supports a number of optional features:

- [all]: install all features below
- [brickify]: install the brickify command for converting metadata from existing sources
- [web]: allow serving of Brick models over HTTP + web interface
- [merge]: initial support for merging Brick models with different identifiers together
- [persistence]: support for saving and loading Brick models to/from disk
- [orm]: SQLAlchemy ORM over a Brick model
- [networkx]: export a Brick model as a NetworkX digraph
- [bacnet]: scan a BACnet network into a Brick model
- [topquadrant]: use the TopQuadrant SHACL engine

The shifty and pyshacl SHACL engines and both OWL 2 RL reasoners
(reasonable and owlrl) are installed by default, so no extra is needed for
validation, compile() or expand().

### Inference

brickschema makes it easier to employ reasoning on your graphs. Simply call the expand method on the Graph object with one of the following profiles:
- "rdfs": RDFS reasoning
- "owlrl": OWL-RL reasoning (using 1 of 3 implementations below)
- "vbis": add VBIS tags to Brick entities

SHACL-AF rules (which is how Brick infers classes from tags, among other
things) are applied with compile() rather than expand():

For the owlrl profile the package defaults to the fastest available
implementation, reasonable.
- OWLRL (default, native Python implementation): pip install brickschema

To use a specific reasoner, specify "reasonable" or "owlrl" as the value for the backend argument to graph.expand.

### Haystack Translation

brickschema can produce a Brick model from a JSON export of a Haystack model.
Then you can use this package as follows:

### VBIS Translation

brickschema can add VBIS tags to a Brick model easily

### Web-based Interaction

brickschema now supports interacting with a Graph object in a web browser. Executing g.serve( ) on a graph object from your Python script or interpreter will start a webserver listening (by default) at . This uses Yasgui to provide a simple web interface supporting SPARQL queries and inference.

To use this feature, install brickschema with the web feature enabled:

### Brick model validation

validate() checks a model against the Brick shapes bundled in the graph plus
any shapes you supply. It does not modify the graph.

### SHACL engines

Both validate() and compile() are backed by a pluggable SHACL engine,
selected with the engine= keyword. When you do not name one, the first
installed engine from this list is used:

engine | package | notes
"shifty" | pyshifty (installed by default) | default; Rust SHACL/SHACL-AF engine, runs rules to a fixed point
"topquadrant" | brickschema[topquadrant] | TopQuadrant's Java implementation
"pyshacl" | pyshacl (installed by default) | pure-Python reference implementation

min_iterations and max_iterations bound how many rule passes are made; they
apply to the pyshacl and topquadrant engines only, since shifty always
runs to a fixed point.

## Brickify

To use brickify, install brickschema with the [brickify] feature enabled:

Usage:

Arguments:

* SOURCE: Path/URL to the source file [required]

Options:

* --input-type TEXT: Supported input types: rac, table, rdf, haystack-v4
* --brick PATH: Brick.ttl
* --config PATH: Custom configuration file
* --output PATH: Path to the output file
* --serialization-format TEXT: Supported serialization formats: turtle, xml, n3, nt, pretty-xml, trix, trig and nquads [default: turtle]
* --minify / --no-minify: Remove inferable triples [default: False]
* --input-format TEXT: Supported input formats: xls, csv, tsv, url, turtle, xml, n3, nt, pretty-xml, trix, trig and nquads [default: turtle]
* --building-prefix TEXT: Prefix for the building namespace [default: bldg]
* --building-namespace TEXT: The building namespace [default: ]
* --site-prefix TEXT: Prefix for the site namespace [default: site]
* --site-namespace TEXT: The site namespace [default: ]
* --install-completion: Install completion for the current shell.
* --show-completion: Show completion for the current shell, to copy it or customize the installation.
* --help: Show this message and exit.

Usage examples: brickify.

## Development

Brick requires Python >= 3.11. We use pre-commit hooks to automatically run code formatters and style checkers when you commit.

Use uv to manage packaging and dependencies. After installing uv, create the environment and install all dependencies with:

uv run executes a command inside that environment, so there is no
separate activation step:

On first setup, make sure to install the pre-commit hooks for running the formatting and linting tools:

Run tests to make sure the build is not broken:

Build the distribution artifacts with:

uv.lock is committed and is the source of truth for the development
environment. If you change a dependency in pyproject.toml, refresh it with:

The uv-lock pre-commit hook does this automatically, and CI runs
uv sync --locked, which fails if uv.lock and pyproject.toml disagree.

### Docs

Docs are written in reStructured Text. Add any packages the docs need to the docs dependency group in pyproject.toml
