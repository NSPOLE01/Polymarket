import httpx
import asyncio
from typing import Optional

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

HEADERS = {"User-Agent": "polymarket-consensus-bot/1.0"}


async def get_top_earners(client: httpx.AsyncClient, limit: int = 20) -> list[dict]:
    resp = await client.get(
        f"{DATA_API}/v1/leaderboard",
        params={"timePeriod": "ALL", "orderBy": "PNL", "limit": limit},
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()


async def get_open_positions(client: httpx.AsyncClient, address: str) -> list[dict]:
    positions = []
    offset = 0
    limit = 500
    while True:
        resp = await client.get(
            f"{DATA_API}/positions",
            params={"user": address, "limit": limit, "offset": offset, "sizeThreshold": 0.01},
            headers=HEADERS,
        )
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        positions.extend(page)
        if len(page) < limit:
            break
        offset += limit
    return positions


async def get_market_details(client: httpx.AsyncClient, condition_ids: list[str]) -> dict[str, dict]:
    if not condition_ids:
        return {}
    resp = await client.get(
        f"{GAMMA_API}/markets",
        params={"condition_id": ",".join(condition_ids), "limit": len(condition_ids)},
        headers=HEADERS,
    )
    resp.raise_for_status()
    markets = resp.json()
    return {m["conditionId"]: m for m in markets if "conditionId" in m}


async def fetch_all_positions(addresses: list[str]) -> dict[str, list[dict]]:
    """Fetch open positions for all addresses concurrently."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [get_open_positions(client, addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    positions_by_user = {}
    for addr, result in zip(addresses, results):
        if isinstance(result, Exception):
            print(f"Error fetching positions for {addr}: {result}")
            positions_by_user[addr] = []
        else:
            positions_by_user[addr] = result
    return positions_by_user
