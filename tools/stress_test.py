# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "httpx",
#   "beautifulsoup4",
# ]
# ///
"""
Stress test script for diminumero.com.

Usage:
    uv run tools/stress_test.py --url http://127.0.0.1:5000 --users 5 --duration 60
    uv run tools/stress_test.py --url https://diminumero.com --users 3 --duration 30 --mode mixed --language random
"""

import argparse
import asyncio
import json
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

AVAILABLE_LANGUAGES = ["es", "de", "fr", "ne"]
AVAILABLE_MODES = ["easy", "advanced", "hardcore"]

DEFAULT_RESULTS_DIR = Path("/home/stefan/Documents/stress_test_results")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stress test script for diminumero.com"
    )
    parser.add_argument(
        "--url", default="https://diminumero.com", help="Target base URL"
    )
    parser.add_argument("--users", type=int, default=5, help="Concurrent virtual users")
    parser.add_argument(
        "--duration", type=float, default=60.0, help="Test duration in seconds"
    )
    parser.add_argument(
        "--mode",
        default="easy",
        choices=[*AVAILABLE_MODES, "mixed"],
        help="Quiz mode (easy/advanced/hardcore/mixed)",
    )
    parser.add_argument(
        "--language",
        default="es",
        choices=[*AVAILABLE_LANGUAGES, "random"],
        help="Language to practice (es/de/fr/ne/random)",
    )
    parser.add_argument(
        "--think-time",
        type=float,
        default=0.5,
        help="Simulated pause between requests (seconds)",
    )
    parser.add_argument(
        "--ramp-up",
        type=float,
        default=0.0,
        help="Seconds to linearly ramp up all users",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path (default: stress_test_{timestamp}.json in results dir)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass
class RequestRecord:
    timestamp: float
    user_id: int
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    success: bool
    error: str | None = None


@dataclass
class MetricsCollector:
    records: list[RequestRecord] = field(default_factory=list)
    quizzes_completed: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def add(self, record: RequestRecord) -> None:
        async with self._lock:
            self.records.append(record)

    async def increment_quizzes(self) -> None:
        async with self._lock:
            self.quizzes_completed += 1

    async def snapshot(self) -> tuple[int, int, int]:
        """Return (total, successful, failed) counts — lock-free read is fine for progress."""
        total = len(self.records)
        successful = sum(1 for r in self.records if r.success)
        return total, successful, total - successful


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    idx = (p / 100) * (len(sorted_values) - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= len(sorted_values):
        return sorted_values[-1]
    frac = idx - lo
    return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])


def url_path(url: str) -> str:
    """Extract the path component from a URL string."""
    try:
        from urllib.parse import urlparse

        return urlparse(url).path or "/"
    except Exception:
        return url


def parse_easy_options(html: str) -> list[str]:
    """Return list of answer values from <button name="answer" value="...">."""
    soup = BeautifulSoup(html, "html.parser")
    buttons = soup.find_all("button", {"name": "answer"})
    return [btn["value"] for btn in buttons if btn.get("value")]


def parse_correct_answer(html: str) -> str | None:
    """Return data-correct-answer attribute from the input element (hardcore mode)."""
    soup = BeautifulSoup(html, "html.parser")
    inp = soup.find("input", attrs={"data-correct-answer": True})
    if inp:
        return inp.get("data-correct-answer")
    return None


def is_on_fragment(response: httpx.Response, fragment: str) -> bool:
    return fragment in str(response.url)


def pick_language(language_arg: str) -> str:
    if language_arg == "random":
        return random.choice(AVAILABLE_LANGUAGES)
    return language_arg


def pick_mode(mode_arg: str) -> str:
    if mode_arg == "mixed":
        return random.choice(AVAILABLE_MODES)
    return mode_arg


# ---------------------------------------------------------------------------
# Virtual user
# ---------------------------------------------------------------------------


class VirtualUser:
    def __init__(
        self,
        user_id: int,
        base_url: str,
        mode_arg: str,
        language_arg: str,
        think_time: float,
        metrics: MetricsCollector,
    ) -> None:
        self.user_id = user_id
        self.base_url = base_url.rstrip("/")
        self.mode_arg = mode_arg
        self.language_arg = language_arg
        self.think_time = think_time
        self.metrics = metrics
        self.client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Low-level request wrapper
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict | None = None,
        json_body: dict | None = None,
    ) -> httpx.Response | None:
        url = self.base_url + path
        start = time.perf_counter()
        status_code = 0
        error_msg: str | None = None
        response: httpx.Response | None = None

        try:
            if method == "GET":
                response = await self.client.get(url)
            elif method == "POST":
                if json_body is not None:
                    response = await self.client.post(url, json=json_body)
                else:
                    response = await self.client.post(url, data=data or {})
            status_code = response.status_code
        except httpx.TimeoutException as exc:
            error_msg = f"Timeout: {exc}"
        except httpx.RequestError as exc:
            error_msg = f"RequestError: {exc}"
        except Exception as exc:
            error_msg = f"Unexpected: {exc}"

        elapsed_ms = (time.perf_counter() - start) * 1000
        success = 200 <= status_code < 400

        record = RequestRecord(
            timestamp=time.time(),
            user_id=self.user_id,
            endpoint=path,
            method=method,
            status_code=status_code,
            response_time_ms=elapsed_ms,
            success=success,
            error=error_msg,
        )
        await self.metrics.add(record)
        return response

    async def _get(self, path: str) -> httpx.Response | None:
        return await self._request("GET", path)

    async def _post(self, path: str, data: dict) -> httpx.Response | None:
        return await self._request("POST", path, data=data)

    async def _post_json(self, path: str, body: dict) -> httpx.Response | None:
        return await self._request("POST", path, json_body=body)

    # ------------------------------------------------------------------
    # Quiz flow steps
    # ------------------------------------------------------------------

    async def init_quiz(self, lang: str, mode: str) -> bool:
        """Steps 1–3: GET /, GET /{lang}, POST /{lang}/start."""
        r = await self._get("/")
        if r is None:
            return False

        r = await self._get(f"/{lang}")
        if r is None:
            return False

        r = await self._post(f"/{lang}/start", {"mode": mode})
        if r is None or not r.is_success:
            return False

        return True

    async def do_easy_question(self, lang: str) -> bool:
        """GET quiz page, parse options, sleep, POST answer. Returns False to signal reinit."""
        r = await self._get(f"/{lang}/quiz/easy")
        if r is None:
            return False
        if not is_on_fragment(r, "/quiz/easy"):
            return False  # session expired or redirected away

        options = parse_easy_options(r.text)
        if not options:
            return False  # can't parse → reinit

        await asyncio.sleep(self.think_time)

        answer = random.choice(options)
        r = await self._post(f"/{lang}/quiz/easy", {"answer": answer})
        return r is not None

    async def do_advanced_question(self, lang: str) -> bool:
        """GET quiz page, validate endpoint, sleep, POST give_up."""
        r = await self._get(f"/{lang}/quiz/advanced")
        if r is None:
            return False
        if not is_on_fragment(r, "/quiz/advanced"):
            return False

        # Exercise the validate endpoint (best-effort; 400 is recorded but non-fatal)
        await self._post_json("/api/validate", {"input": "test"})

        await asyncio.sleep(self.think_time)

        r = await self._post(f"/{lang}/quiz/advanced", {"give_up": "1"})
        return r is not None

    async def do_hardcore_question(self, lang: str) -> bool:
        """GET quiz page, parse correct answer, sleep, POST it."""
        r = await self._get(f"/{lang}/quiz/hardcore")
        if r is None:
            return False
        if not is_on_fragment(r, "/quiz/hardcore"):
            return False

        correct = parse_correct_answer(r.text)
        if correct is None:
            return False  # can't parse → reinit

        await asyncio.sleep(self.think_time)

        r = await self._post(f"/{lang}/quiz/hardcore", {"answer": correct})
        return r is not None

    async def run_quiz(self, lang: str, mode: str) -> bool:
        """Run a full quiz (10 questions). Returns True if completed."""
        ok = await self.init_quiz(lang, mode)
        if not ok:
            return False

        do_question = {
            "easy": self.do_easy_question,
            "advanced": self.do_advanced_question,
            "hardcore": self.do_hardcore_question,
        }[mode]

        for _ in range(10):
            ok = await do_question(lang)
            if not ok:
                return False

        # Fetch results page
        await self._get(f"/{lang}/results")
        await self.metrics.increment_quizzes()
        return True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self, deadline: float, ramp_delay: float) -> None:
        await asyncio.sleep(ramp_delay)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
        ) as client:
            self.client = client
            while time.time() < deadline:
                lang = pick_language(self.language_arg)
                mode = pick_mode(self.mode_arg)
                await self.run_quiz(lang, mode)


# ---------------------------------------------------------------------------
# Progress reporter
# ---------------------------------------------------------------------------


async def progress_reporter(metrics: MetricsCollector, deadline: float) -> None:
    prev_total = 0
    prev_time = time.time()

    while time.time() < deadline:
        await asyncio.sleep(1.0)
        now = time.time()
        total, successful, failed = await metrics.snapshot()
        elapsed = now - prev_time
        rps = (total - prev_total) / elapsed if elapsed > 0 else 0.0
        prev_total = total
        prev_time = now

        quizzes = metrics.quizzes_completed
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"RPS: {rps:.1f} | Total: {total} | OK: {successful} | "
            f"Err: {failed} | Quizzes: {quizzes}",
            flush=True,
        )


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------


def build_summary(
    records: list[RequestRecord],
    quizzes_completed: int,
    duration: float,
    config: dict,
    start_dt: datetime,
    end_dt: datetime,
) -> dict:
    total = len(records)
    successful = sum(1 for r in records if r.success)
    failed = total - successful
    rps = total / duration if duration > 0 else 0.0
    error_rate = (failed / total * 100) if total > 0 else 0.0

    all_times = sorted(r.response_time_ms for r in records)
    avg_ms = sum(all_times) / len(all_times) if all_times else 0.0

    # Per-endpoint breakdown
    by_endpoint: dict[str, list[float]] = {}
    by_endpoint_success: dict[str, int] = {}
    for r in records:
        by_endpoint.setdefault(r.endpoint, []).append(r.response_time_ms)
        by_endpoint_success.setdefault(r.endpoint, 0)
        if r.success:
            by_endpoint_success[r.endpoint] += 1

    endpoint_stats = {}
    for ep, times in by_endpoint.items():
        st = sorted(times)
        endpoint_stats[ep] = {
            "count": len(st),
            "success_count": by_endpoint_success.get(ep, 0),
            "avg_ms": round(sum(st) / len(st), 2),
            "p50_ms": round(percentile(st, 50), 2),
            "p95_ms": round(percentile(st, 95), 2),
            "p99_ms": round(percentile(st, 99), 2),
        }

    return {
        "config": config,
        "start_time": start_dt.isoformat(),
        "end_time": end_dt.isoformat(),
        "duration_seconds": round(duration, 2),
        "summary": {
            "total_requests": total,
            "successful_requests": successful,
            "failed_requests": failed,
            "requests_per_second": round(rps, 2),
            "avg_response_time_ms": round(avg_ms, 2),
            "median_response_time_ms": round(percentile(all_times, 50), 2),
            "p95_response_time_ms": round(percentile(all_times, 95), 2),
            "p99_response_time_ms": round(percentile(all_times, 99), 2),
            "error_rate_percent": round(error_rate, 2),
            "total_quizzes_completed": quizzes_completed,
        },
        "by_endpoint": endpoint_stats,
        "requests": [
            {
                "timestamp": r.timestamp,
                "user_id": r.user_id,
                "endpoint": r.endpoint,
                "method": r.method,
                "status_code": r.status_code,
                "response_time_ms": round(r.response_time_ms, 2),
                "success": r.success,
                "error": r.error,
            }
            for r in records
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = args.output or str(
        DEFAULT_RESULTS_DIR / f"stress_test_{timestamp}.json"
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    config = {
        "url": args.url,
        "users": args.users,
        "duration": args.duration,
        "mode": args.mode,
        "language": args.language,
        "think_time": args.think_time,
        "ramp_up": args.ramp_up,
    }

    print(f"Starting stress test: {args.users} users × {args.duration}s → {args.url}")
    print(
        f"Mode: {args.mode} | Language: {args.language} | Think time: {args.think_time}s"
    )
    if args.ramp_up > 0:
        print(f"Ramp-up: {args.ramp_up}s")
    print()

    metrics = MetricsCollector()
    start_dt = datetime.now(timezone.utc)
    start_time = time.time()
    deadline = start_time + args.duration

    users = [
        VirtualUser(
            user_id=i,
            base_url=args.url,
            mode_arg=args.mode,
            language_arg=args.language,
            think_time=args.think_time,
            metrics=metrics,
        )
        for i in range(args.users)
    ]

    ramp_delays = [
        i * (args.ramp_up / args.users) if args.users > 1 else 0.0
        for i in range(args.users)
    ]

    tasks = [
        asyncio.create_task(user.run(deadline, ramp_delays[i]))
        for i, user in enumerate(users)
    ]
    tasks.append(asyncio.create_task(progress_reporter(metrics, deadline)))

    await asyncio.gather(*tasks, return_exceptions=True)

    end_dt = datetime.now(timezone.utc)
    actual_duration = time.time() - start_time

    print()
    print("Test complete. Building report...")

    result = build_summary(
        records=metrics.records,
        quizzes_completed=metrics.quizzes_completed,
        duration=actual_duration,
        config=config,
        start_dt=start_dt,
        end_dt=end_dt,
    )

    Path(output_path).write_text(json.dumps(result, indent=2))

    # Print summary to stdout
    s = result["summary"]
    print()
    print("=" * 60)
    print(f"  Total requests:      {s['total_requests']}")
    print(f"  Successful:          {s['successful_requests']}")
    print(f"  Failed:              {s['failed_requests']}")
    print(f"  Error rate:          {s['error_rate_percent']}%")
    print(f"  Requests/sec:        {s['requests_per_second']}")
    print(f"  Avg response time:   {s['avg_response_time_ms']} ms")
    print(f"  Median (p50):        {s['median_response_time_ms']} ms")
    print(f"  p95:                 {s['p95_response_time_ms']} ms")
    print(f"  p99:                 {s['p99_response_time_ms']} ms")
    print(f"  Quizzes completed:   {s['total_quizzes_completed']}")
    print("=" * 60)
    print()
    print(f"Full results written to: {output_path}")


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(1)
