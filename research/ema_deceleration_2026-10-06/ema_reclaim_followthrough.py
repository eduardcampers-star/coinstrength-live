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

    start = event_time - timedelta(minutes=5)
    end = event_time + timedelta(minutes=65)

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
# 5. EMA20 MARKET-TURN BATCH
# ============================================================

HORIZONS = [5, 10, 15, 30]
RECLAIM_MINUTES = [1, 2, 3, 5]

results = []

for nr, event in enumerate(events, 1):

    event_time = event["time"]
    direction = event["direction"]

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

        rows = sorted(
            by_time.values(),
            key=lambda x: x["time"]
        )

        # Alleen geldige closes
        clean = []
        for r in rows:
            try:
                close = float(r["close"])
            except (TypeError, ValueError):
                continue

            rr = dict(r)
            rr["close"] = close
            clean.append(rr)

        rows = clean

        before = [r for r in rows if r["time"] <= event_time]

        # Minimaal 20 candles nodig voor EMA-context
        if len(before) < 20:
            continue

        # EMA20 over volledige beschikbare chronologische reeks
        alpha = 2 / (20 + 1)
        ema = None

        for r in rows:
            if ema is None:
                ema = r["close"]
            else:
                ema = alpha * r["close"] + (1 - alpha) * ema

            r["ema20"] = ema

        # Candle op of direct vóór event = referentie
        event_row = max(
            (r for r in rows if r["time"] <= event_time),
            key=lambda r: r["time"],
            default=None,
        )

        if event_row is None:
            continue

        entry_close = event_row["close"]
        entry_ema = event_row["ema20"]

        # EMA-richting: vergelijk met EMA ~3 minuten eerder
        prior_rows = [
            r for r in rows
            if r["time"] <= event_row["time"] - timedelta(minutes=3)
        ]

        if not prior_rows:
            continue

        prior = prior_rows[-1]
        ema_slope_pct = (entry_ema / prior["ema20"] - 1) * 100

        # Richting-normalisatie:
        # positief = gunstig voor het marktsignaal
        sign = 1 if direction == "LONG" else -1

        entry_vs_ema_pct = (
            (entry_close / entry_ema - 1) * 100 * sign
        )

        ema_slope_dir_pct = ema_slope_pct * sign

        # Was/is koers aan goede kant EMA binnen 1/2/3/5 min?
        reclaim = {}

        for mins in RECLAIM_MINUTES:
            limit = event_time + timedelta(minutes=mins)

            future = [
                r for r in rows
                if event_time < r["time"] <= limit
            ]

            reclaim[mins] = any(
                ((r["close"] / r["ema20"] - 1) * sign) > 0
                for r in future
            )

        # Exacte eerste EMA20-reclaim binnen 3 minuten
        first_reclaim = None

        for r in rows:
            if not (
                event_time < r["time"] <= event_time + timedelta(minutes=3)
            ):
                continue

            directional_vs_ema = (
                (r["close"] / r["ema20"] - 1) * sign
            )

            if directional_vs_ema > 0:
                first_reclaim = {
                    "time": r["time"],
                    "close": r["close"],
                    "ema20": r["ema20"],
                    "minute": (
                        r["time"] - event_time
                    ).total_seconds() / 60,
                }
                break

        # Follow-through NA de eerste reclaim
        reclaim_follow = {}
        reclaim_horizons = [1, 2, 3, 5, 10, 15, 30]

        if first_reclaim is not None:
            for mins in reclaim_horizons:
                target = first_reclaim["time"] + timedelta(minutes=mins)

                candidates = [
                    r for r in rows
                    if r["time"] >= target
                ]

                if not candidates:
                    reclaim_follow[mins] = None
                    continue

                target_row = candidates[0]

                delta = (
                    target_row["time"] - target
                ).total_seconds() / 60

                if delta > 2:
                    reclaim_follow[mins] = None
                    continue

                reclaim_follow[mins] = (
                    (target_row["close"] / first_reclaim["close"] - 1)
                    * 100
                    * sign
                )
        else:
            for mins in reclaim_horizons:
                reclaim_follow[mins] = None

        # Follow-through op vaste horizons
        follow = {}

        for mins in HORIZONS:
            target = event_time + timedelta(minutes=mins)

            candidates = [
                r for r in rows
                if r["time"] >= target
            ]

            if not candidates:
                follow[mins] = None
                continue

            target_row = candidates[0]

            # Niet accepteren als dichtstbijzijnde candle te ver weg ligt
            delta = (
                target_row["time"] - target
            ).total_seconds() / 60

            if delta > 2:
                follow[mins] = None
                continue

            follow[mins] = (
                (target_row["close"] / entry_close - 1)
                * 100
                * sign
            )

        # Alleen situaties met ten minste +5 bruikbaar
        if follow[5] is None:
            continue

        results.append({
            "event_time": event_time,
            "direction": direction,
            "coin": coin,
            "entry_vs_ema_pct": entry_vs_ema_pct,
            "ema_slope_dir_pct": ema_slope_dir_pct,
            "reclaim": reclaim,
            "first_reclaim": first_reclaim,
            "reclaim_follow": reclaim_follow,
            "follow": follow,
        })

    if nr % 20 == 0:
        print(f"Verwerkt {nr:3d}/{len(events)} events...")

# ============================================================
# 6. RAPPORT
# ============================================================

print()
print("=" * 92)
print("EMA20 MARKET-TURN BATCH")
print("=" * 92)
print(f"MARKTEVENTS       : {len(events)}")
print(f"BRUIKBARE CASES   : {len(results)}")
print()

print("RECLAIM / GOEDE KANT EMA")
print("-" * 92)
print("VENSTER | N JA | +5 JA% | +10 JA% | +15 JA% | +30 JA% | N NEE")

for mins in RECLAIM_MINUTES:

    yes = [r for r in results if r["reclaim"][mins]]
    no = [r for r in results if not r["reclaim"][mins]]

    vals = []

    for h in HORIZONS:
        usable = [
            r["follow"][h]
            for r in yes
            if r["follow"][h] is not None
        ]

        if usable:
            pct_positive = sum(v > 0 for v in usable) / len(usable) * 100
            vals.append(f"{pct_positive:6.1f}%")
        else:
            vals.append("   n/a ")

    print(
        f"{mins:>3d}m    | "
        f"{len(yes):4d} | "
        f"{vals[0]} | {vals[1]} | {vals[2]} | {vals[3]} | "
        f"{len(no):4d}"
    )

print()
print("EMA-POSITIE BIJ EVENT")
print("-" * 92)

good_side = [r for r in results if r["entry_vs_ema_pct"] > 0]
wrong_side = [r for r in results if r["entry_vs_ema_pct"] <= 0]

for name, group in [
    ("GOEDE KANT", good_side),
    ("VERKEERDE KANT", wrong_side),
]:
    print(f"{name:15s} N={len(group):4d}", end="")

    for h in HORIZONS:
        usable = [
            r["follow"][h]
            for r in group
            if r["follow"][h] is not None
        ]

        if usable:
            avg = sum(usable) / len(usable)
            hit = sum(v > 0 for v in usable) / len(usable) * 100
            print(f" | +{h}: {avg:+.3f}% / {hit:.1f}%", end="")
        else:
            print(f" | +{h}: n/a", end="")

    print()

print()
print("EMA-RICHTING BIJ EVENT")
print("-" * 92)

slope_good = [r for r in results if r["ema_slope_dir_pct"] > 0]
slope_bad = [r for r in results if r["ema_slope_dir_pct"] <= 0]

for name, group in [
    ("MEE MET SIGNAAL", slope_good),
    ("TEGEN SIGNAAL", slope_bad),
]:
    print(f"{name:15s} N={len(group):4d}", end="")

    for h in HORIZONS:
        usable = [
            r["follow"][h]
            for r in group
            if r["follow"][h] is not None
        ]

        if usable:
            avg = sum(usable) / len(usable)
            hit = sum(v > 0 for v in usable) / len(usable) * 100
            print(f" | +{h}: {avg:+.3f}% / {hit:.1f}%", end="")
        else:
            print(f" | +{h}: n/a", end="")

    print()


print()
print("EMA-RICHTING x RECLAIM BINNEN 3 MIN")
print("-" * 92)

groups = [
    (
        "TEGEN + RECLAIM",
        [r for r in results
         if r["ema_slope_dir_pct"] <= 0 and r["reclaim"][3]]
    ),
    (
        "TEGEN + GEEN",
        [r for r in results
         if r["ema_slope_dir_pct"] <= 0 and not r["reclaim"][3]]
    ),
    (
        "MEE + RECLAIM",
        [r for r in results
         if r["ema_slope_dir_pct"] > 0 and r["reclaim"][3]]
    ),
    (
        "MEE + GEEN",
        [r for r in results
         if r["ema_slope_dir_pct"] > 0 and not r["reclaim"][3]]
    ),
]

print("GROEP              | N    | +5 AVG/HIT | +10 AVG/HIT | +15 AVG/HIT | +30 AVG/HIT")
print("-" * 92)

for name, group in groups:
    line = f"{name:18s} | {len(group):4d}"

    for h in HORIZONS:
        usable = [
            r["follow"][h]
            for r in group
            if r["follow"][h] is not None
        ]

        if usable:
            avg = sum(usable) / len(usable)
            hit = sum(v > 0 for v in usable) / len(usable) * 100
            line += f" | {avg:+.3f}%/{hit:4.1f}%"
        else:
            line += " | n/a"

    print(line)


print()
print("FOLLOW-THROUGH VANAF EERSTE RECLAIM <=3 MIN")
print("-" * 92)

reclaim_cases = [
    r for r in results
    if r["ema_slope_dir_pct"] <= 0
    and r["first_reclaim"] is not None
]

print(f"TEGEN + RECLAIM CASES : {len(reclaim_cases)}")
print()
print("NA RECLAIM | N    | GEMIDDELD | HITRATE")
print("-" * 46)

for h in [1, 2, 3, 5, 10, 15, 30]:
    vals = [
        r["reclaim_follow"][h]
        for r in reclaim_cases
        if r["reclaim_follow"][h] is not None
    ]

    if vals:
        avg = sum(vals) / len(vals)
        hit = sum(v > 0 for v in vals) / len(vals) * 100

        print(
            f"+{h:2d} min     | "
            f"{len(vals):4d} | "
            f"{avg:+8.3f}% | "
            f"{hit:6.1f}%"
        )

print()
print("RECLAIM-TIMING")
print("-" * 46)

for minute in [1, 2, 3]:
    group = [
        r for r in reclaim_cases
        if minute - 1 < r["first_reclaim"]["minute"] <= minute
    ]

    print(f"MINUUT {minute}: {len(group)} cases")

print()
print("Observer-analyse. Geen strategie- of productiebestanden gewijzigd.")
