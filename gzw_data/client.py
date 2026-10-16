"""Small, dependency-free client built on urllib."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Iterator, Optional

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
        user_agent: str = "gzw-data-python/0.1.1",
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

    def search(self, query: str) -> dict[str, list[dict[str, Any]]]:
        """Search all datasets. Returns dataset name -> matching records."""
        return self.request("search", {"q": query})["data"]["results"]
