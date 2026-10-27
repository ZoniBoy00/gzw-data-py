"""Python client for the free Gray Zone Warfare data API (https://gzw-data.dev)."""

from .client import GzwApiError, GzwDataClient

__all__ = ["GzwApiError", "GzwDataClient"]
__version__ = "0.3.0"
