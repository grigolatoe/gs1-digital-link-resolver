"""GS1 Digital Link Resolver — open-source EU DPP routing infrastructure."""

#: Single source of truth for the release version. pyproject.toml reads it from
#: here, app.py re-exports it, and the Dockerfile label is checked against it in
#: CI — so a release bumps this line and nothing else.
__version__ = "1.2.0"
