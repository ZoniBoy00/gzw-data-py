# gzw-data (Python)

[![PyPI](https://img.shields.io/pypi/v/gzw-data?label=PyPI&c=1)](https://pypi.org/project/gzw-data/)
[![Python versions](https://img.shields.io/pypi/pyversions/gzw-data?c=1)](https://pypi.org/project/gzw-data/)
[![CI](https://github.com/ZoniBoy00/gzw-data-py/actions/workflows/ci.yml/badge.svg)](https://github.com/ZoniBoy00/gzw-data-py/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/ZoniBoy00/gzw-data-py)](LICENSE)

Dependency-free Python client for the free [Gray Zone Warfare data API](https://gzw-data.dev). Fan-made and not affiliated with the game's developer.

- **PyPI:** <https://pypi.org/project/gzw-data/>
- **Guide:** <https://gzw-data.dev/docs/python/>
- **API reference:** <https://gzw-data.dev/docs/>

```bash
pip install gzw-data
```

```python
from gzw_data import GzwDataClient

client = GzwDataClient()                       # no API key needed
print(client.datasets())                       # {'ammo': 79, 'weapons': 44, ...}
print(client.get("weapons", "ak-12")["name"])  # AK-12
for ammo in client.iterate("ammo", search="5.56"):
    print(ammo["name"])
print(list(client.search("AK")))               # dataset names that matched
```

More methods:

```python
client.search("ak", datasets=["weapons", "ammo"], fuzzy=True, limit=5)
client.export("weapons", search="ak", limit=25)   # bounded export, max 500 records
client.item_context("advanced-tracking-tag")      # item + vendors + references, or None
client.armor()                                    # smart routes: armor(), weapon_parts(), helmet_mods()
client.metadata("weapons"), client.schema("weapons")
client.version(), client.changes(), client.health(), client.ready()
```

Errors raise `GzwApiError` (`.status`, `.code`, `.url`, `.retry_after`). Rate-limit (honouring `Retry-After`) and 5xx responses are retried with backoff.

Game data comes from the community wiki and has its own terms: see the [data license](https://github.com/ZoniBoy00/gzw-data/blob/main/DATA_LICENSE.md). Code is MIT.

## Development

```bash
python -m unittest discover -s tests
```

Releases are automatic: bump the version and push to `main`. See [RELEASING.md](RELEASING.md).
