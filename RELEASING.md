# Releasing to PyPI

Releases use PyPI **Trusted Publishing** (GitHub Actions OIDC), so no API token is stored anywhere.

## One-time setup

1. Create an account on <https://pypi.org> and enable 2FA.
2. Open <https://pypi.org/manage/account/publishing/> and add a **pending publisher**:
   - PyPI project name: `gzw-data`
   - Owner: `ZoniBoy00`, repository: `gzw-data-py`
   - Workflow file: `publish.yml`
   - Environment: `pypi`
3. In the GitHub repo, create an environment named `pypi` (Settings → Environments). Optionally require your approval for deployments.

## Each release

1. Bump `version` in `pyproject.toml` and `gzw_data/__init__.py`, and update the README if needed.
2. Run `python -m unittest discover -s tests` and commit to `main`.
3. Tag and push: `git tag -a v0.1.2 -m "v0.1.2" && git push origin v0.1.2`.
4. The `Publish to PyPI` workflow checks that the tag matches the version, runs the tests, builds, publishes, and creates a GitHub release.
5. Verify in a clean environment: `pip install gzw-data==0.1.2`.

Versions on PyPI are immutable: a published version can never be replaced, only superseded.
