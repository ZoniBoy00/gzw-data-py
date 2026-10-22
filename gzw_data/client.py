"""Small, dependency-free client built on urllib."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Iterator, Optional, Sequence

DEFAULT_BASE_URL = "https://gzw-data.dev/api/v1"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class GzwApiError(Exception):
    """Raised when the API returns an error or cannot be reached."""

    def __init__(
        self, message: str, *, status: int = 0, code: str = "UNKNOWN", url: str = "", retry_after: Optional[float] = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.url = url
        self.retry_after = retry_after  # seconds, from the Retry-After header when present


class GzwDataClient:
    """Read-only client. No API key is needed.

    >>> client = GzwDataClient()
    >>> client.get("weapons", "ak-12")["name"]
    'AK-12'
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 10.0,
        retries: int = 2,
        user_agent: str = "gzw-data-python/0.2.0",
        max_retry_wait: float = 65.0,
        opener: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.user_agent = user_agent
        self.max_retry_wait = max_retry_wait
        self._open = opener or urllib.request.urlopen

    # -- low level ---------------------------------------------------------

    def request(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """GET a path and return the full JSON envelope."""
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = f"{self.base_url}/{path.lstrip('/')}" + (f"?{query}" if query else "")
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": self.user_agent})
        last: Optional[GzwApiError] = None
        for attempt in range(self.retries + 1):
            try:
                with self._open(req, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last = self._from_http_error(exc, url)
                if exc.code not in RETRYABLE_STATUS:
                    raise last from None
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = GzwApiError(f"Request failed: {exc}", code="NETWORK_ERROR", url=url)
            if attempt < self.retries:
                delay = last.retry_after if last.retry_after is not None else min(0.4 * 2**attempt, 4.0)
                time.sleep(min(delay, self.max_retry_wait))
        assert last is not None
        raise last

    @staticmethod
    def _from_http_error(exc: urllib.error.HTTPError, url: str) -> GzwApiError:
        code, message = "HTTP_ERROR", f"HTTP {exc.code}"
        retry_after: Optional[float] = None
        try:
            retry_after = float(exc.headers.get("Retry-After")) if exc.headers and exc.headers.get("Retry-After") else None
        except (TypeError, ValueError):
            pass
        try:
            error = json.loads(exc.read().decode("utf-8")).get("error", {})
            code = error.get("code", code)
            message = error.get("message", message)
        except (ValueError, AttributeError):
            pass
        return GzwApiError(message, status=exc.code, code=code, url=url, retry_after=retry_after)

    # -- API ---------------------------------------------------------------

    def datasets(self) -> dict[str, int]:
        """Dataset name -> record count."""
        stats = self.request("stats")["data"]
        return {name: int(info.get("total", 0)) for name, info in stats.items()}

    def list(self, dataset: str, *, page: int = 1, per_page: int = 50, search: Optional[str] = None, **filters: Any) -> dict[str, Any]:
        """One page of a dataset. Returns the envelope (``data``, ``total``, ``totalPages`` ...)."""
        return self.request(dataset, {"page": page, "per_page": per_page, "search": search, **filters})

    def iterate(self, dataset: str, *, per_page: int = 100, search: Optional[str] = None, **filters: Any) -> Iterator[dict[str, Any]]:
        """Yield every record of a dataset, following pagination."""
        page = 1
        while True:
            payload = self.list(dataset, page=page, per_page=per_page, search=search, **filters)
            yield from payload["data"]
            if page >= int(payload.get("totalPages", 1)) or not payload["data"]:
                return
            page += 1

    def get(self, dataset: str, record_id: str) -> Optional[dict[str, Any]]:
        """One record by id, or ``None`` if it does not exist."""
        try:
            return self.request(f"{dataset}/{urllib.parse.quote(record_id, safe='')}")["data"]
        except GzwApiError as exc:
            if exc.code == "RECORD_NOT_FOUND":
                return None
            raise

    def search(
        self,
        query: str,
        *,
        datasets: Optional[Sequence[str]] = None,
        fields: Optional[Sequence[str]] = None,
        fuzzy: Optional[bool] = None,
        limit: Optional[int] = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Search all datasets. Returns dataset name -> matching records.

        ``datasets`` limits the search to those datasets, ``fields`` to those record
        fields, ``fuzzy`` enables typo-tolerant matching and ``limit`` caps results.
        """
        params = {
            "q": query,
            "dataset": ",".join(datasets) if datasets else None,
            "fields": ",".join(fields) if fields else None,
            "fuzzy": None if fuzzy is None else str(fuzzy).lower(),
            "limit": limit,
        }
        return self.request("search", params)["data"]["results"]

    def export(self, dataset: str, *, search: Optional[str] = None, limit: Optional[int] = None, sort: Optional[str] = None, **filters: Any) -> dict[str, Any]:
        """Bounded export of one dataset (at most 500 matching records).

        Returns the envelope with ``data`` and an ``export`` object (``dataset``,
        ``count``, ``maxRecords``). A larger match raises ``GzwApiError`` with code
        ``EXPORT_TOO_LARGE``; narrow it with ``search``, ``limit`` or filters.
        """
        return self.request(f"export/{urllib.parse.quote(dataset, safe='')}", {"search": search, "limit": limit, "sort": sort, **filters})

    def item_context(self, item_id: str) -> Optional[dict[str, Any]]:
        """An item with its vendors and textual references, or ``None`` if it does not exist."""
        try:
            return self.request(f"items/{urllib.parse.quote(item_id, safe='')}/context")["data"]
        except GzwApiError as exc:
            if exc.code == "RECORD_NOT_FOUND":
                return None
            raise

    def armor(self) -> list[dict[str, Any]]:
        """Smart route: vests, helmets and glasses combined (all pages)."""
        return list(self.iterate("armor"))

    def weapon_parts(self) -> list[dict[str, Any]]:
        """Smart route: all weapon parts combined (all pages)."""
        return list(self.iterate("weapon_parts"))

    def helmet_mods(self) -> list[dict[str, Any]]:
        """Smart route: night vision and helmet mounts (all pages)."""
        return list(self.iterate("helmet_mods"))

    # -- metadata and status -----------------------------------------------

    def metadata(self, dataset: Optional[str] = None) -> dict[str, Any]:
        """Field metadata and capabilities for one dataset, or for all datasets."""
        if dataset:
            return self.request(f"metadata/{urllib.parse.quote(dataset, safe='')}")["data"]
        return self.request("metadata", {"full": "true"})["data"]

    def schema(self, dataset: str) -> dict[str, Any]:
        """Machine-readable schema for one dataset."""
        return self.request(f"schema/{urllib.parse.quote(dataset, safe='')}")["data"]

    def version(self) -> dict[str, Any]:
        """API version, implementation version, data version and latest snapshot."""
        return self.request("version")["data"]

    def changes(self) -> dict[str, Any]:
        """Dataset count changes since the previous stored snapshot."""
        return self.request("changes")["data"]

    def health(self) -> dict[str, Any]:
        """Lightweight liveness check."""
        return self.request("health")["data"]

    def ready(self) -> dict[str, Any]:
        """Readiness probe; raises ``GzwApiError`` (503) until datasets are loaded."""
        return self.request("ready")["data"]
