import io
import json
import unittest
import urllib.error

from gzw_data import GzwApiError, GzwDataClient


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def envelope(data, **extra):
    return FakeResponse(json.dumps({"data": data, **extra}).encode())


def http_error(req, status, code, message="err"):
    body = json.dumps({"error": {"code": code, "message": message}}).encode()
    return urllib.error.HTTPError(req.full_url, status, message, {}, io.BytesIO(body))


class ClientTests(unittest.TestCase):
    def test_list_builds_query_and_skips_none(self):
        seen = []

        def opener(req, timeout):
            seen.append(req.full_url)
            return envelope([{"id": "a"}], totalPages=1)

        GzwDataClient(opener=opener).list("weapons", page=2, per_page=5, caliber="5.56")
        self.assertEqual(len(seen), 1)
        self.assertIn("/weapons?", seen[0])
        self.assertIn("page=2", seen[0])
        self.assertIn("caliber=5.56", seen[0])
        self.assertNotIn("search", seen[0])

    def test_iterate_follows_pages(self):
        pages = {"1": [{"id": 1}, {"id": 2}], "2": [{"id": 3}]}

        def opener(req, timeout):
            page = req.full_url.split("page=")[1].split("&")[0]
            return envelope(pages[page], totalPages=2)

        ids = [r["id"] for r in GzwDataClient(opener=opener).iterate("ammo")]
        self.assertEqual(ids, [1, 2, 3])

    def test_get_returns_none_when_missing(self):
        def opener(req, timeout):
            raise http_error(req, 404, "RECORD_NOT_FOUND")

        self.assertIsNone(GzwDataClient(opener=opener).get("weapons", "x"))

    def test_retries_then_raises_structured_error(self):
        calls = []

        def opener(req, timeout):
            calls.append(1)
            raise http_error(req, 429, "RATE_LIMITED")

        client = GzwDataClient(opener=opener, retries=1)
        with self.assertRaises(GzwApiError) as ctx:
            client.request("stats")
        self.assertEqual(len(calls), 2)
        self.assertEqual(ctx.exception.code, "RATE_LIMITED")
        self.assertEqual(ctx.exception.status, 429)

    def test_does_not_retry_client_errors(self):
        calls = []

        def opener(req, timeout):
            calls.append(1)
            raise http_error(req, 400, "BAD_REQUEST")

        with self.assertRaises(GzwApiError):
            GzwDataClient(opener=opener).request("weapons")
        self.assertEqual(len(calls), 1)

    def test_datasets_maps_counts(self):
        def opener(req, timeout):
            return envelope({"ammo": {"total": 79}, "weapons": {"total": 44}})

        self.assertEqual(GzwDataClient(opener=opener).datasets(), {"ammo": 79, "weapons": 44})


if __name__ == "__main__":
    unittest.main()
