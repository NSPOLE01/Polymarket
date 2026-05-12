from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class UserPosition:
    address: str
    user_name: str
    profile_image: str
    size: float
    avg_price: float
    current_value: float
    cash_pnl: float


@dataclass
class ConsensusMarket:
    condition_id: str
    title: str
    outcome: str
    agreeing_users: list[UserPosition]
    agreeing_count: int
    avg_price: float
    cur_price: float
    total_size: float
    market_url: str
    slug: str
    end_date: str
    icon: str


def find_consensus_bets(
    positions_by_user: dict[str, list[dict]],
    market_details: dict[str, dict],
    user_info: dict[str, dict],
    top_n: int = 5,
) -> list[ConsensusMarket]:
    """
    For each (conditionId, outcome) pair, count how many top earners hold that position.
    Returns the top_n pairs with the most agreeing users.
    """
    agreement: dict[tuple[str, str], list[tuple[str, dict]]] = defaultdict(list)

    now = datetime.now(timezone.utc)

    for user_addr, positions in positions_by_user.items():
        seen: dict[tuple[str, str], dict] = {}
        for pos in positions:
            cid = pos.get("conditionId", "")
            outcome = pos.get("outcome", "")
            if not cid or not outcome:
                continue

            # Skip markets whose end date has passed
            end_date_str = pos.get("endDate", "")
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                    if end_date.tzinfo is None:
                        end_date = end_date.replace(tzinfo=timezone.utc)
                    if end_date <= now:
                        continue
                except ValueError:
                    pass

            # Skip markets that have effectively resolved — current price near 0
            # means the outcome has already been determined against this position
            # (e.g. a team eliminated from a tournament)
            if pos.get("curPrice", 1) < 0.02:
                continue
            key = (cid, outcome)
            if key not in seen or pos.get("size", 0) > seen[key].get("size", 0):
                seen[key] = pos
        for key, pos in seen.items():
            agreement[key].append((user_addr, pos))

    ranked = sorted(
        agreement.items(),
        key=lambda x: (len(x[1]), sum(p.get("size", 0) for _, p in x[1])),
        reverse=True,
    )

    results: list[ConsensusMarket] = []
    for (cid, outcome), user_positions in ranked[:top_n]:
        detail = market_details.get(cid, {})
        positions_list = [pos for _, pos in user_positions]

        avg_price = (
            sum(p.get("avgPrice", 0) for p in positions_list) / len(positions_list)
            if positions_list else 0.0
        )
        cur_price = positions_list[0].get("curPrice", 0.0) if positions_list else 0.0
        total_size = sum(p.get("size", 0) for p in positions_list)
        title = positions_list[0].get("title", "") or detail.get("question", cid)
        slug = positions_list[0].get("slug", "") or detail.get("slug", "")
        event_slug = positions_list[0].get("eventSlug", "") or slug
        end_date = positions_list[0].get("endDate", "") or detail.get("endDate", "")
        icon = positions_list[0].get("icon", "") or detail.get("icon", "")
        market_url = f"https://polymarket.com/event/{event_slug}" if event_slug else ""

        # Build enriched per-user list, sorted by position size descending
        agreeing_users = sorted(
            [
                UserPosition(
                    address=addr,
                    user_name=user_info.get(addr, {}).get("userName") or addr[:10] + "…",
                    profile_image=user_info.get(addr, {}).get("profileImage") or "",
                    size=round(pos.get("size", 0), 2),
                    avg_price=round(pos.get("avgPrice", 0), 4),
                    current_value=round(pos.get("currentValue", 0), 2),
                    cash_pnl=round(pos.get("cashPnl", 0), 2),
                )
                for addr, pos in user_positions
            ],
            key=lambda u: u.size,
            reverse=True,
        )

        results.append(
            ConsensusMarket(
                condition_id=cid,
                title=title,
                outcome=outcome,
                agreeing_users=agreeing_users,
                agreeing_count=len(agreeing_users),
                avg_price=round(avg_price, 4),
                cur_price=round(cur_price, 4),
                total_size=round(total_size, 2),
                market_url=market_url,
                slug=slug,
                end_date=end_date,
                icon=icon,
            )
        )

    return results
