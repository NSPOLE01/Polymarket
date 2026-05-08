import httpx
import asyncio
import logging
import time

logger = logging.getLogger("polymarket")

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

HEADERS = {"User-Agent": "polymarket-consensus-bot/1.0"}

# Max concurrent position fetches — keeps us under rate limits
_SEMAPHORE = asyncio.Semaphore(10)


async def get_top_earners(client: httpx.AsyncClient, limit: int = 50) -> list[dict]:
    resp = await client.get(
        f"{DATA_API}/v1/leaderboard",
        params={"timePeriod": "MONTH", "orderBy": "PNL", "limit": limit},
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


async def get_open_positions(client: httpx.AsyncClient, address: str) -> list[dict]:
    # Single request — limit=500 covers any realistic open position count.
    # Pagination was adding unnecessary round trips for most accounts.
    async with _SEMAPHORE:
        resp = await client.get(
            f"{DATA_API}/positions",
            params={"user": address, "limit": 500, "sizeThreshold": 0.01},
            headers=HEADERS,
        )
        resp.raise_for_status()
        return resp.json() or []


async def fetch_all_positions(addresses: list[str]) -> dict[str, list[dict]]:
    t0 = time.perf_counter()
    logger.info("Fetching positions for %d accounts (semaphore=10)…", len(addresses))

    async with httpx.AsyncClient(timeout=15.0) as client:
        tasks = [get_open_positions(client, addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    positions_by_user: dict[str, list[dict]] = {}
    errors = 0
    total_positions = 0
    for addr, result in zip(addresses, results):
        if isinstance(result, Exception):
            logger.warning("  positions fetch failed for %s: %s", addr[:10], result)
            positions_by_user[addr] = []
            errors += 1
        else:
            positions_by_user[addr] = result
            total_positions += len(result)

    elapsed = time.perf_counter() - t0
    logger.info(
        "Positions fetched in %.2fs — %d positions across %d accounts (%d errors)",
        elapsed, total_positions, len(addresses) - errors, errors,
    )
    return positions_by_user
