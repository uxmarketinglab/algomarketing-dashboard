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
    "week_label": "Apr 6 – 10, 2026",

    # ── Wins — paste Gemini-refined Asana AI output here each week ────────────
    # Each string is one initiative: "Initiative Name: One sentence summary."
    "manual_wins": [
        "Community Roadmap: Delivered the full 2026 community strategy roadmap covering all segments, alumni criteria, and engagement plan — shared with Lola, review session scheduled for Monday.",
        "QBR Delivery: Executed the client QBR end-to-end — logistics, gifting, and client experience all ran smoothly. A DHL supply chain issue was pivoted in real time with a local champagne toast that landed well with the partner and the room.",
        "Office Design: Soft validation secured from Yomi on the Studio D two-zone concept — focused work zone and creative/innovation space with terrace views moving forward.",
        "CoreSync Presentation: Prepared notes for the CoreSync presentation — ready for when the meeting is rescheduled.",
        "Asana Migration: Completed board cleanup following the EM transition — legacy tasks flagged and organized for Lola review.",
    ],

    # ── Score inputs ──────────────────────────────────────────────────────────
    # How many initiatives/tasks you planned this week
    "tasks_planned": 5,

    # 0–100. Community-facing activities delivered this week.
    # From Gemini Prompt 3.
    "community_impact_score": 92,

    # 0–100. 100 = all output was community-strategic.
    # 50 = half strategic, half operational. From Gemini Prompt 3.
    "scope_health": 55,

    # Last week's published score. Set to 0 on first week.
    "previous_score": 79,

    # ── Narrative content — from Gemini Prompt 3 ──────────────────────────────
    "editors_note": "The roadmap is delivered, the QBR was a success, and the office design has Yomi's concept approval — we start fresh on Monday with a full agenda and a team that showed up for the big moment.",

    "culture_pulse": "The QBR day became something more than a client event. From the luncheon to the press photoshoot, almost the entire team participated — and what started as a scheduled shoot turned into an impromptu innovation session. Going into Q2, the foundation is solid, the community roadmap is in review, and the team is ready to move from building to showcasing.",

    # Exactly two items, one sentence each.
    "what_i_need": [
        "Asana board review — flagged legacy EM tasks need your input to close or reassign for Q2 clarity.",
        "Monday roadmap session scheduled — ready to align on Q2 priorities and community segment sequencing.",
    ],

    # Up to 3 expanding influence signals.
    "scope_evolution": [
        "AI Enabler service line launching — integrating alumni community into the community roadmap.",
        "Heavy CS event production support this week for QBR week — Lola is looped in and aware.",
    ],

    # Links for Weekly Wins & Key Actions. Empty list hides the section.
    "links": [
        {"url": "https://app.asana.com/1/1204309477846342/project/1212909024041187/list/1213985937025315", "label": "EM Transition — Outstanding Tasks for Review"},
        {"url": "https://drive.google.com/drive/u/0/folders/1EMOQCF5qsqMHrHOCkcEQHO-AMrwx7N4H", "label": "QBR Day — Video & Photo Content (professional photos coming soon)"},
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