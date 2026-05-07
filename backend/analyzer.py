from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class ConsensusMarket:
    condition_id: str
    title: str
    outcome: str          # e.g. "Yes" or "No"
    agreeing_users: list[str]
    agreeing_count: int
    avg_price: float      # average entry price across agreeing users
    total_size: float     # total tokens held across agreeing users
    market_url: str
    slug: str
    end_date: str
    icon: str


def find_consensus_bets(
    positions_by_user: dict[str, list[dict]],
    market_details: dict[str, dict],
    top_n: int = 5,
) -> list[ConsensusMarket]:
    """
    For each (conditionId, outcome) pair, count how many top earners hold that position.
    Returns the top_n pairs with the most agreeing users.
    """
    # (condition_id, outcome) -> list of (user_address, position)
    agreement: dict[tuple[str, str], list[tuple[str, dict]]] = defaultdict(list)

    for user_addr, positions in positions_by_user.items():
        # Deduplicate by (conditionId, outcome) per user — keep the one with largest size
        seen: dict[tuple[str, str], dict] = {}
        for pos in positions:
            cid = pos.get("conditionId", "")
            outcome = pos.get("outcome", "")
            if not cid or not outcome:
                continue
            key = (cid, outcome)
            if key not in seen or pos.get("size", 0) > seen[key].get("size", 0):
                seen[key] = pos
        for key, pos in seen.items():
            agreement[key].append((user_addr, pos))

    # Sort by number of agreeing users descending, then total size as tiebreaker
    ranked = sorted(
        agreement.items(),
        key=lambda x: (len(x[1]), sum(p.get("size", 0) for _, p in x[1])),
        reverse=True,
    )

    results: list[ConsensusMarket] = []
    for (cid, outcome), user_positions in ranked[:top_n]:
        detail = market_details.get(cid, {})
        agreeing_users = [addr for addr, _ in user_positions]
        positions_list = [pos for _, pos in user_positions]

        avg_price = (
            sum(p.get("avgPrice", 0) for p in positions_list) / len(positions_list)
            if positions_list else 0.0
        )
        total_size = sum(p.get("size", 0) for p in positions_list)
        title = positions_list[0].get("title", "") or detail.get("question", cid)
        slug = positions_list[0].get("slug", "") or detail.get("slug", "")
        end_date = positions_list[0].get("endDate", "") or detail.get("endDate", "")
        icon = positions_list[0].get("icon", "") or detail.get("icon", "")
        market_url = f"https://polymarket.com/event/{slug}" if slug else ""

        results.append(
            ConsensusMarket(
                condition_id=cid,
                title=title,
                outcome=outcome,
                agreeing_users=agreeing_users,
                agreeing_count=len(agreeing_users),
                avg_price=round(avg_price, 4),
                total_size=round(total_size, 2),
                market_url=market_url,
                slug=slug,
                end_date=end_date,
                icon=icon,
            )
        )

    return results
