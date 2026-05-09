"""Generate a human-readable UK Lotto report (Markdown) from a draw CSV.

Sections:
  1. Summary
  2. Main numbers - most / least common (with how often), full frequency table
  3. Bonus ball - most / least common (with how often), full frequency table
  4. Co-occurrence - most common pairs / triplets
  5. Sum of six main balls
  6. Odd / even split
  7. Low (1-30) / High (31-59) split
  8. Consecutive numbers
  9. Position-by-position (sorted) statistics
 10. Gap analysis - current absence and mean gap
 11. Machine and ball-set usage
 12. Repeats from one draw to the next

Usage:
  python3 lotto_report.py --csv data/lotto-merged.csv --out data/report-5y.md
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from itertools import combinations
from pathlib import Path
from statistics import mean, median, pstdev

LOTTO_MIN, LOTTO_MAX = 1, 59


@dataclass(frozen=True)
class Draw:
    draw_date: date
    main: tuple[int, int, int, int, int, int]
    bonus: int
    machine: str
    ball_set: str
    draw_number: int | None


def parse_date(s: str) -> date:
    s = s.strip()
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date {s!r}")


def load(path: Path) -> list[Draw]:
    out: list[Draw] = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            d = parse_date(row["DrawDate"])
            mains = tuple(int(row[f"Ball {i}"]) for i in range(1, 7))
            bonus = int(row["Bonus Ball"])
            machine = (row.get("Machine") or "").strip()
            ball_set = (row.get("Ball Set") or "").strip()
            dn = row.get("DrawNumber") or ""
            out.append(Draw(d, mains, bonus, machine, ball_set, int(dn) if dn.strip() else None))
    out.sort(key=lambda x: x.draw_date)
    return out


def pct(n: int, total: int) -> str:
    return f"{(n / total * 100):.2f}%" if total else "n/a"


def freq_table(freq: Counter[int], total_draws: int, picks_per_draw: int) -> list[str]:
    expected_pct = picks_per_draw / (LOTTO_MAX - LOTTO_MIN + 1) * 100
    expected_count = total_draws * picks_per_draw / (LOTTO_MAX - LOTTO_MIN + 1)
    rows = ["| Number | Times drawn | % of draws | vs uniform |", "|---:|---:|---:|---:|"]
    for n in range(LOTTO_MIN, LOTTO_MAX + 1):
        c = freq.get(n, 0)
        share = c / total_draws * 100 if total_draws else 0.0
        delta = c - expected_count
        rows.append(f"| {n} | {c} | {share:.2f}% | {delta:+.1f} |")
    rows.append("")
    rows.append(
        f"_Expected per number under a perfectly uniform draw: "
        f"{expected_count:.1f} appearances ({expected_pct:.2f}% of draws)._"
    )
    return rows


def top_table(freq: Counter[int], total_draws: int, k: int, *, reverse: bool) -> list[str]:
    items = sorted(freq.items(), key=lambda kv: (-kv[1] if reverse else kv[1], kv[0]))[:k]
    rows = ["| Rank | Number | Times drawn | % of draws |", "|---:|---:|---:|---:|"]
    for i, (n, c) in enumerate(items, 1):
        rows.append(f"| {i} | **{n}** | {c} | {c / total_draws * 100:.2f}% |")
    return rows


def hist_section(title: str, counts: Counter[int], total: int, labels: dict[int, str]) -> list[str]:
    out = [f"### {title}", "", "| Split | Draws | Share |", "|:---|---:|---:|"]
    for k in sorted(labels):
        out.append(f"| {labels[k]} | {counts.get(k, 0)} | {pct(counts.get(k, 0), total)} |")
    out.append("")
    return out


def build_report(draws: list[Draw]) -> str:
    n = len(draws)
    if n == 0:
        return "# UK Lotto report\n\nNo draws in the supplied data.\n"

    main_freq: Counter[int] = Counter()
    bonus_freq: Counter[int] = Counter()
    sums: list[int] = []
    odd_counts: Counter[int] = Counter()
    low_counts: Counter[int] = Counter()
    consec_counts: Counter[int] = Counter()
    position_values: dict[int, list[int]] = defaultdict(list)
    pair_freq: Counter[tuple[int, int]] = Counter()
    triple_freq: Counter[tuple[int, int, int]] = Counter()
    last_seen: dict[int, date] = {}
    gaps: dict[int, list[int]] = defaultdict(list)
    last_seen_bonus: dict[int, date] = {}
    bonus_gaps: dict[int, list[int]] = defaultdict(list)
    machine_freq: Counter[str] = Counter()
    ball_set_freq: Counter[str] = Counter()
    prev_main: set[int] | None = None
    main_repeats: list[int] = []  # how many of the previous draw's six numbers repeat
    bonus_in_main_next = 0  # bonus that became a main on the next draw

    midpoint = (LOTTO_MIN + LOTTO_MAX) / 2  # 30

    for draw in draws:
        sorted_main = sorted(draw.main)
        main_freq.update(sorted_main)
        bonus_freq[draw.bonus] += 1
        sums.append(sum(sorted_main))
        odd_counts[sum(1 for x in sorted_main if x % 2)] += 1
        low_counts[sum(1 for x in sorted_main if x <= midpoint)] += 1
        cpairs = sum(1 for a, b in zip(sorted_main, sorted_main[1:]) if b - a == 1)
        consec_counts[cpairs] += 1
        for i, v in enumerate(sorted_main, 1):
            position_values[i].append(v)
        for a, b in combinations(sorted_main, 2):
            pair_freq[(a, b)] += 1
        for trip in combinations(sorted_main, 3):
            triple_freq[trip] += 1
        for x in sorted_main:
            if x in last_seen:
                gaps[x].append((draw.draw_date - last_seen[x]).days)
            last_seen[x] = draw.draw_date
        b = draw.bonus
        if b in last_seen_bonus:
            bonus_gaps[b].append((draw.draw_date - last_seen_bonus[b]).days)
        last_seen_bonus[b] = draw.draw_date
        if draw.machine:
            machine_freq[draw.machine] += 1
        if draw.ball_set:
            ball_set_freq[draw.ball_set] += 1
        if prev_main is not None:
            shared = len(prev_main & set(sorted_main))
            main_repeats.append(shared)
        prev_main = set(sorted_main)

    today = draws[-1].draw_date

    out: list[str] = []
    out.append("# UK Lotto - statistical report")
    out.append("")
    out.append(
        f"Window analysed: **{draws[0].draw_date} -> {draws[-1].draw_date}**  \n"
        f"Draws covered: **{n}**  \n"
        f"Format: 6 main balls drawn from 1-59 plus 1 bonus ball, twice weekly."
    )
    out.append("")
    out.append(
        "> Each draw is independent and uniformly random. "
        "Past frequencies describe what happened, they do not predict what will happen. "
        "Differences from the uniform expectation are mostly noise at this sample size."
    )
    out.append("")

    # 1. Main numbers
    out.append("## 1. Main numbers (1-59)")
    out.append("")
    out.append(f"Each draw produces 6 main numbers, so the total main-ball appearances is **{n * 6}**.")
    out.append(f"Under a perfectly uniform draw each number would appear about **{n * 6 / 59:.1f}** times "
               f"(**{600/59:.2f}%** of draws).")
    out.append("")

    out.append("### Most common main numbers (top 10)")
    out.append("")
    out.extend(top_table(main_freq, n, 10, reverse=True))
    out.append("")

    out.append("### Least common main numbers (bottom 10)")
    out.append("")
    out.extend(top_table(main_freq, n, 10, reverse=False))
    out.append("")

    out.append("### Full frequency table - all 59 numbers")
    out.append("")
    out.extend(freq_table(main_freq, n, picks_per_draw=6))
    out.append("")

    # 2. Bonus ball
    out.append("## 2. Bonus ball")
    out.append("")
    out.append(f"One bonus ball per draw, so total bonus appearances is **{n}**.")
    out.append(f"Under a uniform draw each number would appear about **{n / 59:.1f}** times "
               f"(**{100/59:.2f}%** of draws).")
    out.append("")

    out.append("### Most common bonus balls (top 10)")
    out.append("")
    out.extend(top_table(bonus_freq, n, 10, reverse=True))
    out.append("")

    out.append("### Least common bonus balls (bottom 10)")
    out.append("")
    out.extend(top_table(bonus_freq, n, 10, reverse=False))
    out.append("")

    never_bonus = [x for x in range(LOTTO_MIN, LOTTO_MAX + 1) if x not in bonus_freq]
    if never_bonus:
        out.append(f"Numbers that were **never** the bonus ball in this window: {never_bonus}")
        out.append("")

    out.append("### Full bonus-ball frequency table")
    out.append("")
    out.extend(freq_table(bonus_freq, n, picks_per_draw=1))
    out.append("")

    # 3. Co-occurrence
    out.append("## 3. Co-occurrence")
    out.append("")
    out.append("### Most common pairs of main numbers (top 15)")
    out.append("")
    out.append("| Pair | Times drawn together | % of draws |")
    out.append("|:---:|---:|---:|")
    for (a, b), c in pair_freq.most_common(15):
        out.append(f"| {a}, {b} | {c} | {c / n * 100:.2f}% |")
    out.append("")

    out.append("### Most common triplets (top 10)")
    out.append("")
    out.append("| Triplet | Times drawn together | % of draws |")
    out.append("|:---:|---:|---:|")
    for trip, c in triple_freq.most_common(10):
        out.append(f"| {', '.join(map(str, trip))} | {c} | {c / n * 100:.2f}% |")
    out.append("")

    # 4. Sum of six main balls
    out.append("## 4. Sum of the six main balls")
    out.append("")
    out.append(f"- Minimum: **{min(sums)}**")
    out.append(f"- Maximum: **{max(sums)}**")
    out.append(f"- Mean:    **{mean(sums):.1f}**")
    out.append(f"- Median:  **{median(sums)}**")
    out.append(f"- Std dev: **{pstdev(sums):.1f}**")
    out.append("")
    out.append(f"_Expected mean for uniform 6-of-59 = {6 * (LOTTO_MIN + LOTTO_MAX) / 2:.0f}._")
    out.append("")

    # 5. Odd / even
    out.append("## 5. Odd / even split")
    out.append("")
    odd_labels = {k: f"{k} odd / {6-k} even" for k in range(7)}
    out.extend(hist_section("Distribution", odd_counts, n, odd_labels))

    # 6. Low / high
    out.append("## 6. Low (1-30) / High (31-59) split")
    out.append("")
    low_labels = {k: f"{k} low / {6-k} high" for k in range(7)}
    out.extend(hist_section("Distribution", low_counts, n, low_labels))

    # 7. Consecutive
    out.append("## 7. Consecutive numbers")
    out.append("")
    out.append("Number of *consecutive pairs* within each draw (e.g. 14 and 15 in the same draw counts as one pair).")
    out.append("")
    out.append("| Consecutive pairs in draw | Draws | Share |")
    out.append("|:---:|---:|---:|")
    for k in sorted(consec_counts):
        out.append(f"| {k} | {consec_counts[k]} | {pct(consec_counts[k], n)} |")
    out.append("")
    no_consec = consec_counts.get(0, 0)
    out.append(f"Draws with **no consecutive numbers at all**: {no_consec} ({pct(no_consec, n)}).")
    out.append(f"Draws with **at least one consecutive pair**: {n - no_consec} ({pct(n - no_consec, n)}).")
    out.append("")

    # 8. Position-by-position
    out.append("## 8. Position-by-position (sorted-ascending)")
    out.append("")
    out.append("After sorting the six main balls ascending, the first number is the lowest, the sixth is the highest.")
    out.append("")
    out.append("| Position | Min | Mean | Median | Max |")
    out.append("|:---:|---:|---:|---:|---:|")
    for i in range(1, 7):
        vs = position_values[i]
        out.append(f"| {i} | {min(vs)} | {mean(vs):.1f} | {median(vs)} | {max(vs)} |")
    out.append("")

    # 9. Gap analysis
    out.append("## 9. Gap analysis - main numbers")
    out.append("")
    out.append("### Longest current absence (days since last drawn, as of last draw in window)")
    out.append("")
    out.append("| Number | Days since last drawn |")
    out.append("|---:|---:|")
    absence = []
    for x in range(LOTTO_MIN, LOTTO_MAX + 1):
        if x in last_seen:
            absence.append((x, (today - last_seen[x]).days))
    absence.sort(key=lambda t: -t[1])
    for x, d in absence[:10]:
        out.append(f"| {x} | {d} |")
    out.append("")

    out.append("### Mean gap between appearances (days)")
    out.append("")
    mean_gaps = []
    for x in range(LOTTO_MIN, LOTTO_MAX + 1):
        g = gaps.get(x, [])
        if g:
            mean_gaps.append((x, mean(g)))
    mean_gaps.sort(key=lambda t: t[1])
    out.append("**Most regular (shortest mean gap):**")
    out.append("")
    out.append("| Number | Mean gap (days) |")
    out.append("|---:|---:|")
    for x, mg in mean_gaps[:10]:
        out.append(f"| {x} | {mg:.1f} |")
    out.append("")
    out.append("**Most irregular (longest mean gap):**")
    out.append("")
    out.append("| Number | Mean gap (days) |")
    out.append("|---:|---:|")
    for x, mg in mean_gaps[-10:][::-1]:
        out.append(f"| {x} | {mg:.1f} |")
    out.append("")

    # Bonus gap
    out.append("### Bonus ball - longest current absence")
    out.append("")
    out.append("| Bonus | Days since last drawn |")
    out.append("|---:|---:|")
    babsence = []
    for x in range(LOTTO_MIN, LOTTO_MAX + 1):
        if x in last_seen_bonus:
            babsence.append((x, (today - last_seen_bonus[x]).days))
    babsence.sort(key=lambda t: -t[1])
    for x, d in babsence[:10]:
        out.append(f"| {x} | {d} |")
    out.append("")

    # 10. Machines / ball sets
    if machine_freq or ball_set_freq:
        out.append("## 10. Machine and ball-set usage")
        out.append("")
        if machine_freq:
            out.append("**Machines used:**")
            out.append("")
            out.append("| Machine | Draws | Share |")
            out.append("|:---|---:|---:|")
            for m, c in machine_freq.most_common():
                out.append(f"| {m} | {c} | {pct(c, n)} |")
            out.append("")
        if ball_set_freq:
            out.append("**Ball sets used:**")
            out.append("")
            out.append("| Ball set | Draws | Share |")
            out.append("|:---|---:|---:|")
            for m, c in ball_set_freq.most_common():
                out.append(f"| {m} | {c} | {pct(c, n)} |")
            out.append("")

    # 11. Repeats from previous draw
    if main_repeats:
        out.append("## 11. Repeats from one draw to the next")
        out.append("")
        out.append("How many of a draw's six main numbers also appeared in the immediately previous draw.")
        out.append("")
        rep_counts = Counter(main_repeats)
        total_pairs = sum(rep_counts.values())
        out.append("| Numbers repeated | Draw-to-draw count | Share |")
        out.append("|:---:|---:|---:|")
        for k in sorted(rep_counts):
            out.append(f"| {k} | {rep_counts[k]} | {pct(rep_counts[k], total_pairs)} |")
        out.append("")
        out.append(f"Average overlap with the previous draw: **{mean(main_repeats):.2f}** numbers.")
        out.append("")

    out.append("---")
    out.append("")
    out.append(
        f"Window: {draws[0].draw_date} -> {draws[-1].draw_date} ({n} draws). "
        "Source CSVs in `data/`. Run with `python3 lotto_report.py --csv data/lotto-merged.csv`."
    )
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="UK Lotto Markdown report")
    p.add_argument("--csv", required=True, help="Path to draw-history CSV")
    p.add_argument("--out", help="Output Markdown path (default: stdout)")
    p.add_argument("--start", help="ISO start date (filter)")
    p.add_argument("--end", help="ISO end date (filter)")
    args = p.parse_args(argv)

    draws = load(Path(args.csv))
    if args.start:
        s = date.fromisoformat(args.start)
        draws = [d for d in draws if d.draw_date >= s]
    if args.end:
        e = date.fromisoformat(args.end)
        draws = [d for d in draws if d.draw_date <= e]

    report = build_report(draws)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"wrote {args.out} ({len(report):,} bytes)")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
