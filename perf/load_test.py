"""零依赖压测脚本：并发打 /api/chat，输出 p50/p95/p99 与错误率。

用法：
    uv run python perf/load_test.py --concurrency 20 --total 200
    uv run python perf/load_test.py --all      # 依次跑 5 / 20 / 50 并发

只依赖 httpx（项目已有）。Locust 版本见 perf/locustfile.py。
"""

import argparse
import asyncio
import json
import statistics
import time
import uuid
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:18082"
RESULT_FILE = Path(__file__).resolve().parents[1] / "perf" / "result.json"


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(ratio * (len(ordered) - 1))))
    return ordered[index]


async def one_request(
    client: httpx.AsyncClient,
    index: int,
    mode: str = "chat",
) -> tuple[float, bool]:
    started = time.perf_counter()
    try:
        if mode == "health":
            response = await client.get(f"{BASE}/healthz")
        else:
            response = await client.post(
                f"{BASE}/api/chat",
                json={
                    "sender_id": f"perf-{index}",
                    "text": "你好",
                    "message_id": str(uuid.uuid4()),
                },
            )
        ok = response.status_code == 200
    except Exception:
        ok = False
    return (time.perf_counter() - started) * 1000, ok


async def run_round(
    concurrency: int,
    total: int,
    mode: str = "chat",
) -> dict:
    per_user = max(1, total // concurrency)
    actual_total = per_user * concurrency

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 预热，排除首个请求的建连与缓存开销
        await one_request(client, 0, mode)

        started = time.perf_counter()

        async def worker(worker_id: int):
            results = []
            for _ in range(per_user):
                results.append(
                    await one_request(
                        client, worker_id * 1000 + len(results), mode
                    )
                )
            return results

        batches = await asyncio.gather(
            *(worker(i) for i in range(concurrency))
        )
        elapsed = time.perf_counter() - started

    results = [item for batch in batches for item in batch]
    latencies = [latency for latency, _ in results]
    errors = sum(1 for _, ok in results if not ok)

    return {
        "concurrency": concurrency,
        "requests": actual_total,
        "duration_s": round(elapsed, 2),
        "rps": round(actual_total / elapsed, 1),
        "p50_ms": round(percentile(latencies, 0.50), 1),
        "p95_ms": round(percentile(latencies, 0.95), 1),
        "p99_ms": round(percentile(latencies, 0.99), 1),
        "avg_ms": round(statistics.fmean(latencies), 1),
        "errors": errors,
        "error_rate": round(errors / actual_total, 4),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="ShopMate 压测")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--total", type=int, default=200)
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--mode",
        choices=["chat", "health"],
        default="chat",
        help="chat=完整对话链路，health=仅测应用层开销",
    )
    args = parser.parse_args()

    rounds = (
        [(5, 100), (20, 200), (50, 300)]
        if args.all
        else [(args.concurrency, args.total)]
    )

    results = []
    for concurrency, total in rounds:
        result = await run_round(concurrency, total, args.mode)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False))

    RESULT_FILE.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"saved: {RESULT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
