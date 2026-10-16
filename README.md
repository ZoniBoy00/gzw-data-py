# gzw-data (Python)

Dependency-free Python client for the free [Gray Zone Warfare data API](https://gzw-data.dev). Fan-made and not affiliated with the game's developer.

```bash
pip install git+https://github.com/ZoniBoy00/gzw-data-py
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

Errors raise `GzwApiError` (`.status`, `.code`, `.url`). Rate-limit (honouring `Retry-After`) and 5xx responses are retried with backoff.

Game data comes from the community wiki and has its own terms: see the [data license](https://github.com/ZoniBoy00/gzw-data/blob/main/DATA_LICENSE.md). Code is MIT.

## Development

```bash
python -m unittest discover -s tests
```
