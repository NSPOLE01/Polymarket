import asyncio
from dataclasses import asdict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

from polymarket_client import get_top_earners, fetch_all_positions, get_market_details
from analyzer import find_consensus_bets

app = FastAPI(title="Polymarket Consensus Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/consensus")
async def consensus(top_earners: int = 20, top_bets: int = 5):
    """
    1. Fetch the top `top_earners` accounts by all-time PnL.
    2. Fetch their open (unsettled) positions.
    3. Return the `top_bets` markets where the most top earners agree on an outcome.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            leaderboard = await get_top_earners(client, limit=top_earners)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Leaderboard fetch failed: {e}")

    addresses = [entry["proxyWallet"] for entry in leaderboard if entry.get("proxyWallet")]

    positions_by_user = await fetch_all_positions(addresses)

    # Collect unique condition IDs to enrich with market metadata
    all_condition_ids = list(
        {
            pos["conditionId"]
            for positions in positions_by_user.values()
            for pos in positions
            if pos.get("conditionId")
        }
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            market_details = await get_market_details(client, all_condition_ids[:200])
    except Exception as e:
        print(f"Market details fetch failed (non-fatal): {e}")
        market_details = {}

    consensus_bets = find_consensus_bets(positions_by_user, market_details, top_n=top_bets)

    return {
        "top_earners_analyzed": len(addresses),
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


@app.get("/health")
async def health():
    return {"status": "ok"}
