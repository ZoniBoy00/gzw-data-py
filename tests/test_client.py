import io
import json
import unittest
import urllib.error
import urllib.parse

from gzw_data import GzwApiError, GzwDataClient


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def envelope(data, **extra):
    return FakeResponse(json.dumps({"data": data, **extra}).encode())


def http_error(req, status, code, message="err", headers=None):
    body = json.dumps({"error": {"code": code, "message": message}}).encode()
    return urllib.error.HTTPError(req.full_url, status, message, headers or {}, io.BytesIO(body))


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

    def test_honours_retry_after_header(self):
        from unittest import mock

        calls = []

        def opener(req, timeout):
            calls.append(1)
            if len(calls) == 1:
                raise http_error(req, 429, "RATE_LIMITED", headers={"Retry-After": "7"})
            return envelope({"ok": True})

        with mock.patch("gzw_data.client.time.sleep") as sleep:
            result = GzwDataClient(opener=opener).request("health")
        sleep.assert_called_once_with(7.0)
        self.assertEqual(result["data"], {"ok": True})

    def test_retry_after_is_capped(self):
        from unittest import mock

        def opener(req, timeout):
            raise http_error(req, 429, "RATE_LIMITED", headers={"Retry-After": "600"})

        with mock.patch("gzw_data.client.time.sleep") as sleep, self.assertRaises(GzwApiError) as ctx:
            GzwDataClient(opener=opener, retries=1, max_retry_wait=30).request("health")
        sleep.assert_called_once_with(30)
        self.assertEqual(ctx.exception.retry_after, 600.0)

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

    def test_search_builds_options(self):
        seen = []

        def opener(req, timeout):
            seen.append(urllib.parse.urlparse(req.full_url))
            return envelope({"results": {"weapons": [{"id": "ak-12"}]}})

        results = GzwDataClient(opener=opener).search("ak", datasets=["weapons", "ammo"], fields=["name"], fuzzy=True, limit=5)
        self.assertEqual(results, {"weapons": [{"id": "ak-12"}]})
        self.assertEqual(seen[0].path, "/api/v1/search")
        query = urllib.parse.parse_qs(seen[0].query)
        self.assertEqual(query, {"q": ["ak"], "dataset": ["weapons,ammo"], "fields": ["name"], "fuzzy": ["true"], "limit": ["5"]})

    def test_search_without_options_sends_only_query(self):
        seen = []

        def opener(req, timeout):
            seen.append(req.full_url)
            return envelope({"results": {}})

        GzwDataClient(opener=opener).search("ak")
        self.assertTrue(seen[0].endswith("/search?q=ak"))

    def test_export_returns_envelope_and_encodes_dataset(self):
        seen = []

        def opener(req, timeout):
            seen.append(req.full_url)
            return envelope([{"id": "ak-12"}], export={"dataset": "weapons", "count": 1, "maxRecords": 500})

        payload = GzwDataClient(opener=opener).export("weapons", search="ak", limit=1, caliber="5.45x39mm")
        self.assertEqual(payload["export"]["maxRecords"], 500)
        self.assertEqual(payload["data"], [{"id": "ak-12"}])
        self.assertIn("/export/weapons?", seen[0])
        self.assertIn("search=ak", seen[0])
        self.assertIn("limit=1", seen[0])
        self.assertIn("caliber=5.45x39mm", seen[0])

    def test_export_too_large_raises(self):
        def opener(req, timeout):
            raise http_error(req, 413, "EXPORT_TOO_LARGE")

        with self.assertRaises(GzwApiError) as ctx:
            GzwDataClient(opener=opener).export("items")
        self.assertEqual(ctx.exception.code, "EXPORT_TOO_LARGE")

    def test_item_context_returns_data_or_none(self):
        seen = []

        def found(req, timeout):
            seen.append(req.full_url)
            return envelope({"item": {"id": "a b"}, "vendors": [], "references": []})

        def missing(req, timeout):
            raise http_error(req, 404, "RECORD_NOT_FOUND")

        self.assertEqual(GzwDataClient(opener=found).item_context("a b")["item"]["id"], "a b")
        self.assertTrue(seen[0].endswith("/items/a%20b/context"))
        self.assertIsNone(GzwDataClient(opener=missing).item_context("x"))

    def test_status_and_metadata_helpers_unwrap_data(self):
        seen = []

        def opener(req, timeout):
            seen.append(req.full_url)
            return envelope({"ok": True})

        client = GzwDataClient(opener=opener)
        for call in (client.health, client.ready, client.version, client.changes):
            self.assertEqual(call(), {"ok": True})
        client.metadata()
        client.metadata("weapons")
        client.schema("weapons")
        paths = [url.split("/api/v1/")[1] for url in seen]
        self.assertEqual(paths, ["health", "ready", "version", "changes", "metadata?full=true", "metadata/weapons", "schema/weapons"])

    def test_smart_routes_follow_all_pages(self):
        seen = []

        def opener(req, timeout):
            seen.append(req.full_url.split("/api/v1/")[1].split("?")[0])
            page = int(req.full_url.split("page=")[1].split("&")[0])
            return envelope([{"id": f"x{page}"}], totalPages=2)

        client = GzwDataClient(opener=opener)
        self.assertEqual(client.armor(), [{"id": "x1"}, {"id": "x2"}])
        client.weapon_parts()
        client.helmet_mods()
        self.assertEqual(seen, ["armor", "armor", "weapon_parts", "weapon_parts", "helmet_mods", "helmet_mods"])


class RootHelperTests(unittest.TestCase):
    def test_endpoints_spec_and_images(self):
        seen = []

        def opener(req, timeout):
            seen.append(req.full_url)
            if req.full_url.endswith("/spec"):
                return FakeResponse(json.dumps({"openapi": "3.0.0"}).encode())
            if req.full_url.endswith("/images"):
                return envelope({"AK-12": "https://example.test/ak.png"})
            return envelope({"endpoints": ["weapons"]})

        client = GzwDataClient(base_url="https://example.test/api/v1", opener=opener)
        self.assertEqual(client.endpoints()["endpoints"], ["weapons"])
        self.assertEqual(client.spec()["openapi"], "3.0.0")
        self.assertEqual(client.images()["AK-12"], "https://example.test/ak.png")
        self.assertEqual(seen[0], "https://example.test/api/v1/")
        self.assertEqual(seen[1], "https://example.test/api/v1/spec")
        self.assertEqual(seen[2], "https://example.test/api/v1/images")


if __name__ == "__main__":
    unittest.main()
