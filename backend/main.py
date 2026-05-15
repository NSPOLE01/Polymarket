import asyncio
import logging
import time
from dataclasses import asdict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

from polymarket_client import get_top_earners, fetch_all_positions
from analyzer import find_consensus_bets

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# ── Cache ──────────────────────────────────────────────────────────────────────
_CACHE: dict = {}
_CACHE_AT: float = 0.0
CACHE_TTL = 300  # seconds — refresh data at most once every 5 minutes

app = FastAPI(title="Polymarket Consensus Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Vercel URL after deploying
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/consensus")
async def consensus(top_earners: int = 50, top_bets: int = 20, force: bool = False):
    """
    1. Fetch the top `top_earners` accounts by this month's PnL.
    2. Fetch their open (unsettled) positions.
    3. Return the `top_bets` markets where the most top earners agree on an outcome.

    Results are cached for 5 minutes. Pass ?force=true to bypass the cache.
    """
    global _CACHE, _CACHE_AT

    cache_key = (top_earners, top_bets)
    age = time.time() - _CACHE_AT

    if not force and _CACHE.get(cache_key) and age < CACHE_TTL:
        logger.info("Cache hit (age=%.0fs) — returning cached result", age)
        return _CACHE[cache_key]

    request_start = time.perf_counter()
    logger.info("=== Consensus request started (top_earners=%d, top_bets=%d) ===", top_earners, top_bets)

    # Step 1: leaderboard
    t = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            leaderboard = await get_top_earners(client, limit=top_earners)
    except httpx.HTTPError as e:
        logger.error("Leaderboard fetch failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Leaderboard fetch failed: {e}")
    logger.info("Leaderboard fetched in %.2fs — %d entries", time.perf_counter() - t, len(leaderboard))

    addresses = [e["proxyWallet"] for e in leaderboard if e.get("proxyWallet")]
    user_info = {e["proxyWallet"]: e for e in leaderboard if e.get("proxyWallet")}

    # Step 2: open positions (concurrent, semaphore-limited)
    positions_by_user = await fetch_all_positions(addresses)

    # Step 3: consensus analysis
    t = time.perf_counter()
    consensus_bets = find_consensus_bets(positions_by_user, {}, user_info, top_n=top_bets)
    logger.info(
        "Consensus analysis done in %.2fs — top %d bets found",
        time.perf_counter() - t, len(consensus_bets),
    )
    for i, bet in enumerate(consensus_bets, 1):
        logger.info(
            "  #%d  %d traders agree  %-4s  %s",
            i, bet.agreeing_count, bet.outcome, bet.title[:60],
        )


    total_elapsed = time.perf_counter() - request_start
    logger.info("=== Request complete in %.2fs ===", total_elapsed)

    result = {
        "top_earners_analyzed": len(addresses),
        "cache_age_seconds": None,
        "leaderboard": [
            {
                "rank": e.get("rank"),
                "userName": e.get("userName"),
                "proxyWallet": e.get("proxyWallet"),
                "pnl": e.get("pnl"),
                "vol": e.get("vol"),
                "xUsername": e.get("xUsername"),
                "profileImage": e.get("profileImage"),
            }
            for e in leaderboard
        ],
        "consensus_bets": [asdict(bet) for bet in consensus_bets],
    }

    _CACHE[cache_key] = result
    _CACHE_AT = time.time()
    return result


@app.get("/health")
async def health():
    age = time.time() - _CACHE_AT
    return {
        "status": "ok",
        "cache_age_seconds": round(age) if _CACHE_AT else None,
        "cache_ttl_seconds": CACHE_TTL,
    }
