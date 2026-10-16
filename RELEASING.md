# Releasing to PyPI

Releases are automatic. A push to `main` that changes the version in `pyproject.toml` publishes it to [PyPI](https://pypi.org/project/gzw-data/) through PyPI **Trusted Publishing** (GitHub Actions OIDC), so no API token is stored anywhere.

## Each release

1. Bump `version` in `pyproject.toml` **and** `__version__` in `gzw_data/__init__.py`, and the `user_agent` default in `gzw_data/client.py`. A test fails if they disagree.
2. Run `python -m unittest discover -s tests` and push to `main`.
3. The `Publish to PyPI` workflow then:
   - reads the version and checks whether it is already on PyPI (if it is, it stops without error),
   - runs the tests and builds the sdist and wheel,
   - publishes to PyPI from the protected `pypi` environment,
   - creates the `vX.Y.Z` tag and a GitHub release with generated notes.
4. Verify in a clean environment: `pip install gzw-data==X.Y.Z`.

You can also run the workflow manually from the Actions tab (`workflow_dispatch`); it only publishes versions that are not on PyPI yet.

Versions on PyPI are immutable: a published version can never be replaced, only superseded. Fix a bad release with a new patch version.

## Setup (already done)

- PyPI trusted publisher for project `gzw-data`: owner `ZoniBoy00`, repository `gzw-data-py`, workflow `publish.yml`, environment `pypi`.
- GitHub environment named `pypi` (Settings → Environments).
- Keep the workflow file name and environment name unchanged, or update the publisher entry on PyPI to match.
