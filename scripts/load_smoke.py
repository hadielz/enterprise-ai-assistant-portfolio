#!/usr/bin/env python3
"""Bounded, non-destructive HTTP load smoke for R4 acceptance.

Defaults target /ready and never invoke chat, RAG indexing, MCP, or ticket actions.
This is a release smoke check, not a capacity benchmark.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    status: int | None
    latency_ms: float
    error: str | None = None


def _request(url: str, timeout: float, bearer_token: str | None) -> Result:
    headers = {}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            return Result(response.status, (time.perf_counter() - started) * 1000)
    except urllib.error.HTTPError as exc:
        return Result(exc.code, (time.perf_counter() - started) * 1000, str(exc))
    except Exception as exc:
        return Result(None, (time.perf_counter() - started) * 1000, type(exc).__name__)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True, help="Service root, e.g. http://localhost:8000")
    parser.add_argument("--path", default="/ready")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument("--max-p95-ms", type=float, default=3000.0)
    parser.add_argument("--bearer-token", default=None)
    args = parser.parse_args()

    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")
    if not 0.0 <= args.max_error_rate <= 1.0:
        parser.error("--max-error-rate must be between 0 and 1")

    url = args.base_url.rstrip("/") + "/" + args.path.lstrip("/")

    # Warm one request so a serverless cold start is not misrepresented as
    # steady-state latency in this intentionally small smoke check.
    warm = _request(url, args.timeout, args.bearer_token)
    if warm.status is None or not 200 <= warm.status < 400:
        print(f"Warm-up failed: status={warm.status} error={warm.error}")
        return 1

    results: list[Result] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(_request, url, args.timeout, args.bearer_token)
            for _ in range(args.requests)
        ]
        for future in as_completed(futures):
            results.append(future.result())

    failures = [
        result
        for result in results
        if result.status is None or not 200 <= result.status < 400
    ]
    latencies = [result.latency_ms for result in results]
    error_rate = len(failures) / len(results)
    p50 = statistics.median(latencies)
    p95 = _percentile(latencies, 0.95)

    print(f"URL: {url}")
    print(f"Requests: {len(results)}; concurrency: {args.concurrency}")
    print(f"Errors: {len(failures)}; error_rate={error_rate:.3f}")
    print(f"Latency ms: p50={p50:.1f}; p95={p95:.1f}; max={max(latencies):.1f}")

    if error_rate > args.max_error_rate:
        print("FAIL: error rate exceeded threshold")
        return 1
    if p95 > args.max_p95_ms:
        print("FAIL: p95 latency exceeded threshold")
        return 1

    print("PASS: bounded load smoke completed within thresholds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
