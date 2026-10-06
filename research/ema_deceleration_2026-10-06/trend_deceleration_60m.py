#!/usr/bin/env python3

import json
import subprocess
from datetime import datetime, timedelta, timezone

REPO = "/home/edje/coinstrength-live"
SUMMARY_FILE = "film60_summary.json"
FILM_FILE = "film60m.json"

SPONSOR = "/home/edje/coinbot_lab/shadow_bitvavo_sponsor.py"

PRE_MINUTES = 20
HORIZONS = [5, 10, 15, 30, 60]
POST_MINUTES = max(HORIZONS)
COOLDOWN_MINUTES = 15


def git(args):
    return subprocess.check_output(
        ["git", "-C", REPO] + args,
        text=True,
        stderr=subprocess.DEVNULL
    )


def parse_time(x):
    return datetime.fromisoformat(x.replace("Z", "+00:00"))


def get_film_eps():
    with open(SPONSOR, "r") as f:
        for line in f:
            s = line.strip()
            if s.startswith("FILM_EPS"):
                return float(s.split("=", 1)[1].strip())

    raise RuntimeError("FILM_EPS niet gevonden")


FILM_EPS = get_film_eps()


def breadth(coins, field):
    green = red = flat = 0

    for vals in coins.values():
        v = float(vals.get(field, 0.0) or 0.0)

        if v > FILM_EPS:
            green += 1
        elif v < -FILM_EPS:
            red += 1
        else:
            flat += 1

    return green, red, flat


# ============================================================
# 1. HISTORISCHE V0.4 MARKTGATES
# ============================================================

summary_lines = git([
    "log",
    "--reverse",
    "--format=%H|%ci",
    "--",
    SUMMARY_FILE
]).splitlines()

turns = []

for line in summary_lines:
    sha, commit_time = line.split("|", 1)

    try:
        film = json.loads(
            git(["show", f"{sha}:{SUMMARY_FILE}"])
        )

        coins = film.get("coins", film)

        if len(coins) != 27:
            continue

        g5, r5, _ = breadth(coins, "ret_5m_pct")
        g15, r15, _ = breadth(coins, "ret_15m_pct")
        g60, r60, _ = breadth(coins, "ret_60m_pct")

        direction = None

        if g15 >= 16 and g5 > g15 and r60 >= 16:
            direction = "LONG"

        elif r15 >= 16 and r5 > r15 and g60 >= 16:
            direction = "SHORT"

        if direction:
            t = parse_time(
                film.get("generated_at", commit_time)
            )

            turns.append({
                "time": t,
                "direction": direction,
                "sha": sha,
            })

    except Exception:
        continue


# ============================================================
# 2. 15-MINUTEN COOLDOWN
# ============================================================

events = []

for x in turns:

    if not events:
        events.append(x)
        continue

    prev = events[-1]

    delta = (
        x["time"] - prev["time"]
    ).total_seconds() / 60.0

    if x["direction"] != prev["direction"]:
        events.append(x)

    elif delta > COOLDOWN_MINUTES:
        events.append(x)


# ============================================================
# 3. FILM60M GIT-HISTORIE INDEXEREN
# ============================================================

film_commits = git([
    "log",
    "--reverse",
    "--format=%H|%ct",
    "--",
    FILM_FILE
]).splitlines()

film_index = []

for line in film_commits:
    sha, unix_time = line.split("|", 1)

    t = datetime.fromtimestamp(
        int(unix_time),
        tz=timezone.utc
    )

    film_index.append((t, sha))


# ============================================================
# 4. ZOEK BESTE FILM-SNAPSHOT VOOR EVENT
#
# film60m bevat ~60 minuten historie.
# Voor 20 min vóór + 60 min ná hebben we daarom snapshots
# rond event+60 nodig en combineren we beschikbare candles.
# ============================================================

def candidate_shas(event_time):

    start = event_time - timedelta(minutes=15)
    end = event_time + timedelta(minutes=80)

    return [
        (t, sha)
        for t, sha in film_index
        if start <= t <= end
    ]


def extract_rows(obj):

    coins = obj.get("coins", obj)

    result = {}

    for coin, vals in coins.items():

        film = vals.get("film", [])

        rows = []

        for candle in film:

            ts = candle.get("time_utc")

            if not ts:
                continue

            try:
                ct = parse_time(ts)
            except Exception:
                continue

            rows.append({
                "time": ct,
                "open": candle.get("open"),
                "high": candle.get("high"),
                "low": candle.get("low"),
                "close": candle.get("close"),
                "volume": candle.get("volume"),
                "taker_buy_volume": candle.get("taker_buy_volume"),
                "taker_ratio": candle.get("taker_ratio"),
            })

        result[coin] = rows

    return result


# ============================================================
# 5. 60M TREND DECELERATION
# ============================================================

FOLLOW_HORIZONS = [5, 15, 30, 45, 60]
results = []

def nearest_before(rows, target):
    x = [r for r in rows if r["time"] <= target]
    return x[-1] if x else None

def nearest_after(rows, target):
    x = [r for r in rows if r["time"] >= target]
    return x[0] if x else None

for nr, event in enumerate(events, 1):

    event_time = event["time"]
    direction = event["direction"]
    sign = 1 if direction == "LONG" else -1

    merged = {}

    for _, sha in candidate_shas(event_time):
        try:
            obj = json.loads(
                git(["show", f"{sha}:{FILM_FILE}"])
            )
        except Exception:
            continue

        data = extract_rows(obj)

        for coin, rows in data.items():
            if coin not in merged:
                merged[coin] = {}

            for row in rows:
                merged[coin][row["time"]] = row

    for coin, by_time in merged.items():

        rows = sorted(by_time.values(), key=lambda x: x["time"])

        clean = []
        for r in rows:
            try:
                rr = dict(r)
                rr["close"] = float(r["close"])
                clean.append(rr)
            except (TypeError, ValueError):
                continue

        rows = clean

        points = {}
        valid = True

        for mins in [60, 40, 20, 0]:
            target = event_time - timedelta(minutes=mins)
            r = nearest_before(rows, target)

            if r is None:
                valid = False
                break

            age = abs((r["time"] - target).total_seconds()) / 60
            if age > 2:
                valid = False
                break

            points[mins] = r

        if not valid:
            continue

        p60 = points[60]["close"]
        p40 = points[40]["close"]
        p20 = points[20]["close"]
        p0 = points[0]["close"]

        # Positief = koers bewoog TEGEN het nieuwe marktsignaal.
        # LONG verwacht dus voorafgaande daling; SHORT voorafgaande stijging.
        block1 = (p40 / p60 - 1) * 100 * -sign
        block2 = (p20 / p40 - 1) * 100 * -sign
        block3 = (p0 / p20 - 1) * 100 * -sign
        move60 = (p0 / p60 - 1) * 100 * -sign

        # Ratio's < 1 betekenen: latere beweging zwakker dan eerdere.
        ratio_2_vs_1 = (
            abs(block2) / abs(block1)
            if abs(block1) > 1e-12 else None
        )

        ratio_3_vs_2 = (
            abs(block3) / abs(block2)
            if abs(block2) > 1e-12 else None
        )

        follow = {}

        for mins in FOLLOW_HORIZONS:
            target = event_time + timedelta(minutes=mins)
            r = nearest_after(rows, target)

            if r is None:
                follow[mins] = None
                continue

            gap = (r["time"] - target).total_seconds() / 60

            if gap > 2:
                follow[mins] = None
                continue

            follow[mins] = (
                (r["close"] / p0 - 1) * 100 * sign
            )

        results.append({
            "event_time": event_time,
            "direction": direction,
            "coin": coin,
            "move60": move60,
            "block1": block1,
            "block2": block2,
            "block3": block3,
            "ratio_2_vs_1": ratio_2_vs_1,
            "ratio_3_vs_2": ratio_3_vs_2,
            "follow": follow,
        })

    if nr % 20 == 0:
        print(f"Verwerkt {nr:3d}/{len(events)} events...")

print()
print("=" * 92)
print("60M TREND DECELERATION - RUWE METING")
print("=" * 92)
print(f"MARKTEVENTS      : {len(events)}")
print(f"BRUIKBARE CASES  : {len(results)}")
print()

print("VERDELING 20M BLOKKEN")
print("-" * 72)

for key, label in [
    ("block1", "-60 -> -40"),
    ("block2", "-40 -> -20"),
    ("block3", "-20 -> EVENT"),
    ("move60", "TOTAAL 60M"),
]:
    vals = sorted(r[key] for r in results)
    n = len(vals)

    print(
        f"{label:14s} | "
        f"P10 {vals[int(n*0.10)]:+.3f}% | "
        f"P25 {vals[int(n*0.25)]:+.3f}% | "
        f"MED {vals[int(n*0.50)]:+.3f}% | "
        f"P75 {vals[int(n*0.75)]:+.3f}% | "
        f"P90 {vals[int(n*0.90)]:+.3f}%"
    )

print()
print("FOLLOW-THROUGH DEKKING")
print("-" * 72)

for h in FOLLOW_HORIZONS:
    vals = [
        r["follow"][h]
        for r in results
        if r["follow"][h] is not None
    ]

    print(
        f"+{h:2d} min | "
        f"{len(vals):4d}/{len(results)} | "
        f"{len(vals)/len(results)*100:5.1f}%"
    )

print()
print("Nog GEEN vertraging-regel toegepast.")
print("Gemeten per case: -60/-40/-20/event + vervolg +5/+15/+30/+45/+60.")
print("Geen shadow- of productiebestanden gewijzigd.")
