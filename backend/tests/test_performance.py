"""Performance and load tests for OmniGuard backend APIs."""

import time
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed


class TestAPIPerformance:
    """Measure response times of critical API endpoints."""

    ENDPOINTS = [
        ("GET", "/api/auth/login"),
        ("GET", "/api/dashboard/stats"),
        ("GET", "/api/zones"),
        ("GET", "/api/cameras"),
        ("GET", "/api/alarms"),
    ]

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_endpoint_response_time(self, client, method, path):
        """Assert that each endpoint responds within 500 ms."""
        start = time.perf_counter()
        if method == "GET":
            resp = client.get(path)
        elif method == "POST":
            resp = client.post(path, json={})
        elif method == "PUT":
            resp = client.put(path, json={})
        elif method == "DELETE":
            resp = client.delete(path)
        elapsed = (time.perf_counter() - start) * 1000  # ms

        assert elapsed < 500, (
            f"{method} {path} took {elapsed:.1f} ms (limit: 500 ms)"
        )
        # Even if it responds fast, it should not be a server error
        assert resp.status_code < 500, (
            f"{method} {path} returned {resp.status_code}"
        )

    def test_concurrent_requests(self, client):
        """Verify the server handles 10 concurrent requests without failure."""
        def make_request(_):
            return client.get("/api/dashboard/stats")

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(make_request, i) for i in range(10)]
            for future in as_completed(futures):
                resp = future.result()
                assert resp.status_code < 500

    def test_sequential_bulk_events(self, client):
        """Send 50 lightweight requests in sequence and measure total time."""
        start = time.perf_counter()
        for _ in range(50):
            resp = client.get("/api/dashboard/stats")
            assert resp.status_code < 500
        total = (time.perf_counter() - start) * 1000
        avg = total / 50
        assert avg < 300, (
            f"Average response time {avg:.1f} ms exceeds 300 ms"
        )

    @pytest.mark.parametrize("payload_size", [100, 1024, 10240])
    def test_payload_handling(self, client, payload_size):
        """Ensure that endpoints can handle moderate-sized payloads."""
        large_payload = {"data": "x" * payload_size}
        resp = client.post("/api/auth/login", json=large_payload)
        # The endpoint may reject invalid data, but should not crash
        assert resp.status_code in (200, 400, 401, 422)
