"""UK Lotto statistical analysis over a configurable date window.

Default window: the 5 years up to today.

Data source priority:
  1. --csv <path>           Local CSV (same schema as the official download)
  2. UK_LOTTO_CSV env var    Path to a local CSV
  3. Network download        https://www.national-lottery.co.uk/results/lotto/draw-history/csv

Expected CSV header (official format):
  DrawDate,Ball 1,Ball 2,Ball 3,Ball 4,Ball 5,Ball 6,Bonus Ball,Ball Set,Machine,Raffles,DrawNumber

Run:
  python3 lotto_stats.py --csv lotto-draw-history.csv
  python3 lotto_stats.py --years 5
  python3 lotto_stats.py --start 2021-05-09 --end 2026-05-09
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

OFFICIAL_CSV_URL = "https://www.national-lottery.co.uk/results/lotto/draw-history/csv"
LOTTO_MIN, LOTTO_MAX = 1, 59  # current UK Lotto range (since Oct 2015)


@dataclass(frozen=True)
class Draw:
    draw_date: date
    main: tuple[int, int, int, int, int, int]
    bonus: int
    draw_number: int | None


def parse_draw_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {raw!r}")


def load_csv(text: str) -> list[Draw]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")
    cols = {name.strip().lower(): name for name in reader.fieldnames}

    def col(*candidates: str) -> str:
        for c in candidates:
            if c.lower() in cols:
                return cols[c.lower()]
        raise KeyError(f"Missing column; tried {candidates}")

    date_c = col("DrawDate", "Draw Date", "Date")
    ball_cs = [col(f"Ball {i}", f"Ball{i}", f"N{i}") for i in range(1, 7)]
    bonus_c = col("Bonus Ball", "Bonus", "BonusBall")
    try:
        draw_no_c = col("DrawNumber", "Draw Number", "Draw No")
    except KeyError:
        draw_no_c = None

    draws: list[Draw] = []
    for row in reader:
        d = parse_draw_date(row[date_c])
        main = tuple(int(row[c]) for c in ball_cs)
        bonus = int(row[bonus_c])
        draw_no = int(row[draw_no_c]) if draw_no_c and row[draw_no_c].strip() else None
        draws.append(Draw(d, main, bonus, draw_no))
    draws.sort(key=lambda x: x.draw_date)
    return draws


def fetch_csv(url: str = OFFICIAL_CSV_URL, timeout: float = 20.0) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (lotto-stats analysis script)",
            "Accept": "text/csv,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def filter_window(draws: Iterable[Draw], start: date, end: date) -> list[Draw]:
    return [d for d in draws if start <= d.draw_date <= end]


def fmt_pct(n: int, total: int) -> str:
    return f"{(n / total * 100):5.2f}%" if total else "  n/a"


def analyse(draws: list[Draw], start: date, end: date) -> str:
    out: list[str] = []
    n = len(draws)
    if n == 0:
        return f"No draws found in window {start}..{end}."

    expected_per_number = (n * 6) / (LOTTO_MAX - LOTTO_MIN + 1)

    main_freq: Counter[int] = Counter()
    bonus_freq: Counter[int] = Counter()
    sums: list[int] = []
    odd_counts: Counter[int] = Counter()
    low_counts: Counter[int] = Counter()
    consecutive_pairs = 0
    last_seen: dict[int, date] = {}
    gaps: dict[int, list[int]] = defaultdict(list)
    pair_freq: Counter[tuple[int, int]] = Counter()

    midpoint = (LOTTO_MIN + LOTTO_MAX) / 2  # 30

    for draw in draws:
        nums = sorted(draw.main)
        main_freq.update(nums)
        bonus_freq[draw.bonus] += 1
        sums.append(sum(nums))
        odd_counts[sum(1 for x in nums if x % 2 == 1)] += 1
        low_counts[sum(1 for x in nums if x <= midpoint)] += 1
        for a, b in zip(nums, nums[1:]):
            if b - a == 1:
                consecutive_pairs += 1
        for i, a in enumerate(nums):
            for b in nums[i + 1 :]:
                pair_freq[(a, b)] += 1
        for x in nums:
            if x in last_seen:
                gaps[x].append((draw.draw_date - last_seen[x]).days)
            last_seen[x] = draw.draw_date

    out.append(f"UK Lotto statistical analysis")
    out.append(f"Window:        {start.isoformat()} → {end.isoformat()}")
    out.append(f"Draws covered: {n}")
    out.append(f"First draw:    {draws[0].draw_date}  (#{draws[0].draw_number})")
    out.append(f"Last draw:     {draws[-1].draw_date}  (#{draws[-1].draw_number})")
    out.append("")

    out.append("Main-ball frequency (1–59)")
    out.append(f"  expected per number if uniform: {expected_per_number:.1f}")
    most = main_freq.most_common(10)
    least = sorted(main_freq.items(), key=lambda kv: (kv[1], kv[0]))[:10]
    missing = [x for x in range(LOTTO_MIN, LOTTO_MAX + 1) if x not in main_freq]
    out.append("  Top 10 hot:    " + ", ".join(f"{k:>2}×{v}" for k, v in most))
    out.append("  Top 10 cold:   " + ", ".join(f"{k:>2}×{v}" for k, v in least))
    if missing:
        out.append(f"  Never drawn:   {missing}")
    out.append("")

    out.append("Bonus-ball frequency")
    out.append("  Top 10:        " + ", ".join(f"{k:>2}×{v}" for k, v in bonus_freq.most_common(10)))
    out.append("")

    out.append("Sum of the six main balls")
    out.append(f"  min / max:     {min(sums)} / {max(sums)}")
    out.append(f"  mean / median: {sum(sums)/len(sums):.1f} / {sorted(sums)[len(sums)//2]}")
    out.append("")

    out.append("Odd / even split (out of 6)")
    for k in range(7):
        out.append(f"  {k} odd : {6-k} even   {odd_counts[k]:>4}  {fmt_pct(odd_counts[k], n)}")
    out.append("")

    out.append("Low (1–30) / high (31–59) split")
    for k in range(7):
        out.append(f"  {k} low : {6-k} high   {low_counts[k]:>4}  {fmt_pct(low_counts[k], n)}")
    out.append("")

    out.append("Consecutive numbers")
    out.append(f"  draws with at least one consecutive pair: see pair table; total consecutive pairs across draws: {consecutive_pairs}")
    out.append("")

    out.append("Top 10 most common pairs")
    for (a, b), c in pair_freq.most_common(10):
        out.append(f"  ({a:>2},{b:>2})  ×{c}")
    out.append("")

    out.append("Longest current absence (days since last draw)")
    today = end
    absence = []
    for x in range(LOTTO_MIN, LOTTO_MAX + 1):
        if x in last_seen:
            absence.append((x, (today - last_seen[x]).days))
        else:
            absence.append((x, (today - start).days))
    absence.sort(key=lambda t: -t[1])
    for x, days in absence[:10]:
        out.append(f"  {x:>2}: {days} days")
    out.append("")

    out.append("Mean gap between appearances (days)")
    mean_gaps = []
    for x in range(LOTTO_MIN, LOTTO_MAX + 1):
        g = gaps.get(x, [])
        if g:
            mean_gaps.append((x, sum(g) / len(g)))
    mean_gaps.sort(key=lambda t: t[1])
    out.append("  Shortest mean gap (most regular):")
    for x, mg in mean_gaps[:5]:
        out.append(f"    {x:>2}: {mg:.1f} d")
    out.append("  Longest mean gap (most irregular):")
    for x, mg in mean_gaps[-5:][::-1]:
        out.append(f"    {x:>2}: {mg:.1f} d")
    out.append("")

    out.append("Reminder: each draw is independent and uniformly random. Past frequencies do not predict future draws.")

    return "\n".join(out)


def resolve_data(args: argparse.Namespace) -> str:
    if args.csv:
        with open(args.csv, encoding="utf-8") as fh:
            return fh.read()
    env_path = os.environ.get("UK_LOTTO_CSV")
    if env_path:
        with open(env_path, encoding="utf-8") as fh:
            return fh.read()
    return fetch_csv()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="UK Lotto stats over a date window")
    p.add_argument("--csv", help="Path to a local draw-history CSV")
    p.add_argument("--years", type=int, default=5, help="Window size in years (default 5)")
    p.add_argument("--start", help="ISO start date (overrides --years)")
    p.add_argument("--end", help="ISO end date (defaults to today)")
    args = p.parse_args(argv)

    end = date.fromisoformat(args.end) if args.end else date.today()
    if args.start:
        start = date.fromisoformat(args.start)
    else:
        start = end - timedelta(days=int(round(args.years * 365.25)))

    try:
        text = resolve_data(args)
    except Exception as exc:  # noqa: BLE001
        print(
            f"error: could not load draw data ({exc}).\n"
            "Pass --csv <path> with the official UK Lotto draw-history CSV "
            f"(downloadable from {OFFICIAL_CSV_URL}).",
            file=sys.stderr,
        )
        return 2

    draws = load_csv(text)
    window = filter_window(draws, start, end)
    print(analyse(window, start, end))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
