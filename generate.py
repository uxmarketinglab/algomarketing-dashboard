#!/usr/bin/env python3
"""
Algomarketing Community Pulse — weekly leadership dashboard generator.

Edit MANUAL_INPUTS each week, then run:
    python generate.py
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
RETROSPECTIVE_MODE  = False
RETROSPECTIVE_START = "2026-03-01"
# ─────────────────────────────────────────────────────────────────────────────

# ── Manual inputs — edit these each week ─────────────────────────────────────
MANUAL_INPUTS = {
    # ── Week label ────────────────────────────────────────────────────────────
    "week_label": "Apr 14 – 18, 2026",

    # ── Wins — paste Gemini-refined Asana AI output here each week ────────────
    # Each string is one initiative: "Initiative Name: One sentence summary."
    "manual_wins": [
        "Evolved Worker Program: GenAI certification reached 100% adoption across the CoE — every team member has attempted the exam, with 76% fully certified.",
        "Algo Community Experience: 7 community touchpoints delivered across two weeks — nearly double the Q1 weekly cadence, with members now bringing their own engagement ideas unprompted.",
        "Building the CoE: Office infrastructure handover to Eliana complete — 200 additional meeting room credits secured through end of growth planning period.",
        "External Community & Brand: External community strategy moving forward — alumni community framework and AI Enabler talent pipeline in active planning.",
        "Strategic Partnerships & BD: QBR delivered end-to-end — logistics, gifting, and client experience all ran smoothly.",
    ],

    # ── Score inputs ──────────────────────────────────────────────────────────
    # How many tasks did you plan this week
    "tasks_planned": 6,

    # 0–100. Community-facing activities delivered this week.
    # From Gemini Prompt 3.
    "community_impact_score": 80,

    # 0–100. 100 = all output was community-strategic.
    # 50 = half strategic, half operational. From Gemini Prompt 3.
    "scope_health": 70,

    # Last week's published score. Set to 0 on first week.
    "previous_score": 80,

    # ── Narrative content — from Gemini Prompt 3 ──────────────────────────────
    "editors_note": "Update this each week — one sentence, your voice, sets the tone.",

    "culture_pulse": "Update this each week — 2-3 sentences on community energy and intangible wins.",

    # Exactly two items, one sentence each.
    "what_i_need": [
        "First item — what would most accelerate your impact right now.",
        "Second item — direct, no softening.",
    ],

    # Up to 3 expanding influence signals.
    "scope_evolution": [
        "First signal — framed as opportunity, not complaint.",
        "Second signal — factual and forward-looking.",
    ],

    # Links for Weekly Wins & Key Actions. Empty list hides the section.
    "links": [
        {"url": "https://uxmarketinglab.github.io/algomarketing-dashboard/", "label": "Live Dashboard"},
    ],
}
# ─────────────────────────────────────────────────────────────────────────────


def week_bounds() -> tuple[str, str]:
    """Return ISO strings for the current week window (Mon–Sun)."""
    today = datetime.now(tz=timezone.utc)
    monday = today - timedelta(days=today.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    start = monday - timedelta(hours=1)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return start.isoformat(), sunday.isoformat()


def calculate_score(inputs: dict) -> dict:
    """
    Community Pulse Score (0–100).

    Components:
      +40  Community Impact   (community_impact_score / 100) × 40
      +35  Program Delivery   (len(manual_wins) / tasks_planned) × 35
      +25  Scope Health       (scope_health / 100) × 25
    """
    wins_count = len(inputs.get("manual_wins", []))
    planned = max(inputs["tasks_planned"], 1)

    community_pts = (inputs["community_impact_score"] / 100) * 40
    delivery_pts  = min(wins_count / planned, 1.0) * 35
    scope_pts     = (inputs["scope_health"] / 100) * 25

    score = round(max(0, min(100, community_pts + delivery_pts + scope_pts)))

    prev = inputs.get("previous_score")
    baseline = (prev == 0)

    if baseline or prev is None:
        trend = "neutral"
        delta = None
    elif score > prev:
        trend = "up"
        delta = score - prev
    elif score < prev:
        trend = "down"
        delta = prev - score
    else:
        trend = "neutral"
        delta = 0

    return {
        "score": score,
        "trend": trend,
        "delta": delta,
        "baseline": baseline,
        "breakdown": {
            "community_impact": round(community_pts, 1),
            "program_delivery": round(delivery_pts, 1),
            "scope_health":     round(scope_pts, 1),
        },
    }


def render_dashboard(context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=True,
    )
    template = env.get_template("dashboard.html.j2")
    return template.render(**context)


def main() -> None:
    wins = MANUAL_INPUTS.get("manual_wins", [])

    score_data = calculate_score(MANUAL_INPUTS)

    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_label = MANUAL_INPUTS.get("week_label") or \
        f"{monday.strftime('%b %-d')} – {sunday.strftime('%-d, %Y')}"

    context = {
        "week_label": week_label,
        "generated_at": today.strftime("%Y-%m-%d %H:%M"),
        "score": score_data,
        "wins": wins,
        "culture_pulse": MANUAL_INPUTS["culture_pulse"],
        "scope_evolution": MANUAL_INPUTS["scope_evolution"],
        "editors_note": MANUAL_INPUTS.get("editors_note", ""),
        "what_i_need": MANUAL_INPUTS.get("what_i_need", []),
        "links": MANUAL_INPUTS.get("links", []),
        "retrospective_mode": RETROSPECTIVE_MODE,
        "retrospective_start": RETROSPECTIVE_START,
        "tasks_completed": len(wins),
        "tasks_planned": MANUAL_INPUTS["tasks_planned"],
    }

    html = render_dashboard(context)

    out_path = Path(__file__).parent / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"\nDashboard written to: {out_path}")
    print(f"  Score this week: {score_data['score']}/100  (trend: {score_data['trend']})")


if __name__ == "__main__":
    main()