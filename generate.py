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
     "week_label": "Apr 11 – 17, 2026",

    # ── Wins — paste Gemini-refined Asana AI output here each week ────────────
    # Each string is one initiative: "Initiative Name: One sentence summary."
    "manual_wins": [
        "Evolved Worker Program: Expanded the GenAI certification strategy to T3 — all Algos worldwide — and built an n8n automation workflow to support the rollout.",
        "Algo Community Experience: CoE All-Hands delivered Q1 results to senior leadership — 82% GenAI certification rate inside CoE, with Core CoE booked in before 28th of April. Office expansion is cleared on the IDEA Spaces side, awaiting internal decision on our side.",
        "External Community & Brand: Recruiting event live on Luma with 10 RSVPs in the first week — 60/40 split between Algos and external community members. Invite-only format with waitlist in place.",
        "Strategic Partnerships & BD: Bespokely gifting program briefed on the Evolved Worker philosophy — proposal with pricing expected by Wednesday. Potential community partnership on the horizon with Web Summit as a north star/tentpole.",
    ],


    # ── Score inputs ──────────────────────────────────────────────────────────
    # How many initiatives/tasks you planned this week
    "tasks_planned": 4,

    # 0–100. Community-facing activities delivered this week.
    # From Gemini Prompt 3.
    "community_impact_score": 75,

    # 0–100. 100 = all output was community-strategic.
    # 50 = half strategic, half operational. From Gemini Prompt 3.
    "scope_health": 75,

    # Last week's published score. Set to 0 on first week.
    "previous_score": 80,

    # ── Narrative content — from Gemini Prompt 3 ──────────────────────────────
    "editors_note": "The gap between vision and execution is closing — this week felt like proof.",

    "culture_pulse": "This was a seed-planting week — less visible than QBR week but arguably more important. The GenAI impact is expanding beyond the CoE. The recruiting event already has external community members on the waitlist. A lot of conversation, relationship-building, and future-planning this week — including an early-stage partnership that's worth a dedicated conversation next week.",

    # Exactly two items, one sentence each.
   "what_i_need": [
        "Office expansion decision needed urgently — IDEA Spaces is holding the space now and will start showing it to others if we don't confirm this ASAP.",
        "Continued conversation on community roadmap/vision and next steps for activation as a part of our Monday sync",
    ],

    # Up to 3 expanding influence signals.
    "scope_evolution": [
        "Monthly digest initiative requires careful coordination with the CS team — audience and content overlap with Shamai's existing Evolved Worker newsletter.",
        "Innovation support challenges — Luke's focus has shifted primarily to vendors, creating a resource constraint for weekly sessions and future hackathons.",
    ],

    # Links for Weekly Wins & Key Actions. Empty list hides the section.
    "links": [
        {"url": "https://luma.com/5jywjh6u", "label": "Recruiting Event RSVP live on Luma and Linkedin"},
        {"url": "https://n8n.algomarketing.com/workflow/YvmaivrbtiG6wwFQ", "label": "Created an N8N workflow to automate GenAI Certification offering to wider team"},
        {"url": "https://app.asana.com/1/1204309477846342/project/1212909024041187/list/1213985937025315", "label": "EM Transition — Outstanding Tasks for Review"},
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