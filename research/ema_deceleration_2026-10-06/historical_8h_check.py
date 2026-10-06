import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path("/home/edje/coinstrength-live")
FILE = "latest.json"

# Eerste proefmoment midden in onze onderzoeksperiode
TARGET = datetime.fromisoformat("2026-10-03T12:17:00+02:00")


def git(args):
    return subprocess.check_output(
        ["git", "-C", str(REPO)] + args,
        text=True
    ).strip()


def parse_time(x):
    return datetime.fromisoformat(x.replace("Z", "+00:00"))


print("Git-history latest.json laden...")

shas = git([
    "log", "--all",
    "--format=%H",
    "--", FILE
]).splitlines()

snapshots = []

for sha in shas:
    try:
        obj = json.loads(
            git(["show", f"{sha}:{FILE}"])
        )
        ts = parse_time(obj["timestamp"])
        snapshots.append((ts, sha, obj))
    except Exception:
        continue

print(f"Snapshots gelezen: {len(snapshots)}")


def nearest(target):
    return min(
        snapshots,
        key=lambda x: abs(
            (x[0] - target).total_seconds()
        )
    )


now_ts, now_sha, now_obj = nearest(TARGET)
old_target = TARGET - timedelta(hours=8)
old_ts, old_sha, old_obj = nearest(old_target)

print()
print("GEVRAAGD")
print("T      :", TARGET.isoformat())
print("T-8H   :", old_target.isoformat())

print()
print("GEVONDEN")
print(
    "T      :", now_ts.isoformat(),
    "| afwijking",
    f"{abs((now_ts-TARGET).total_seconds())/60:.1f} min"
)
print(
    "T-8H   :", old_ts.isoformat(),
    "| afwijking",
    f"{abs((old_ts-old_target).total_seconds())/60:.1f} min"
)

old_coins = old_obj["coins"]
now_coins = now_obj["coins"]

if isinstance(old_coins, dict):
    old_coins = list(old_coins.values())

if isinstance(now_coins, dict):
    now_coins = list(now_coins.values())

old_prices = {
    c["symbol"]: float(c["price"])
    for c in old_coins
    if c.get("symbol") and c.get("price") is not None
}

ranking = []

for c in now_coins:
    symbol = c.get("symbol")
    price_now = c.get("price")

    if not symbol or price_now is None:
        continue

    if symbol not in old_prices:
        continue

    p0 = old_prices[symbol]
    p1 = float(price_now)

    if p0 <= 0:
        continue

    move8 = (p1 / p0 - 1) * 100

    ranking.append(
        (abs(move8), move8, symbol, p0, p1)
    )

ranking.sort(reverse=True)

print()
print("TOP 10 ABSOLUTE 8H MOVERS")
print("-" * 72)
print("RANK | COIN       | 8H MOVE   | PRIJS -8H | PRIJS NU")

for rank, (_, move, symbol, p0, p1) in enumerate(
    ranking[:10], 1
):
    print(
        f"{rank:4d} | "
        f"{symbol:10s} | "
        f"{move:+8.3f}% | "
        f"{p0:10.6g} | "
        f"{p1:10.6g}"
    )
