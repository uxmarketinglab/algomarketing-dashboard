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

import asana
from asana.rest import ApiException
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
# Set to True to pull tasks from RETROSPECTIVE_START through today instead of
# just the current week. Switch back to False for normal weekly runs.
RETROSPECTIVE_MODE  = False
RETROSPECTIVE_START = "2026-03-01"  # ISO date, inclusive

# Only tasks assigned to someone whose name contains this string will appear.
ASSIGNEE_FILTER = "Christina"
# ─────────────────────────────────────────────────────────────────────────────

# ── Manual inputs — edit these each week ─────────────────────────────────────
MANUAL_INPUTS = {
    # ── Week label override ────────────────────────────────────────────────────
    # Set explicitly to override the auto-computed Mon–Sun label.
    "week_label": "Mar 20 – Apr 3, 2026",

    # ── Manual wins override ───────────────────────────────────────────────────
    # Populate this list to bypass Asana and use these as the wins this week.
    # Leave empty ([]) to pull from Asana automatically.
    "manual_wins": [
        "Evolved Worker Program: GenAI certification reached 100% adoption across the CoE — every team member has attempted the exam, with 76% fully certified. Guest hosted the Innovation Session this week, with Luke and Beatriz now briefed on the three golden rules for engagement. Innovation Afternoons are live as a dedicated weekly format.",
        "Algo Community Experience: 7 community touchpoints delivered across two weeks — nearly double the Q1 weekly cadence. Community members are now bringing their own engagement ideas unprompted, a signal the culture is self-generating.",
        "Building the CoE: In the home stretch on office infrastructure — 200 additional meeting room credits secured through end of growth planning period, and full vendor and office management handover to Eliana is complete.",
        "External Community & Brand: External community strategy is moving forward — alumni community framework and AI Enabler talent pipeline are in active planning. Recruitment event development is underway.",
        "Strategic Partnerships & BD: QBR delivered end-to-end including logistics, gifts, and client experience. Press photoshoot booked and in preparation — mood board, photographer briefed, Yomi visuals in progress.",
    ],

    # ── Score inputs ──────────────────────────────────────────────────────────
    # Tasks: Asana pulls completed count automatically; just set how many you planned.
    "tasks_planned": 6,

    # 0–100. Community-facing activities delivered this week (events, activations, sessions).
    # Will eventually connect to Google Calendar automatically.
    "community_impact_score": 88,

    # 0–100. 100 = all output was community-strategic. 50 = half strategic, half intentional
    # closeout or transition work. Never penalizes absorbed requests — measures quality of
    # output delivered, not what landed in your inbox.
    "scope_health": 60,

    # Previous week's score for trend arrow. Set to 0 on the first scored week — hides
    # the trend arrow and shows "Week 1 baseline" instead.
    "previous_score": 77,

    # One sentence. Sets the tone for the week. Sounds like you, not a template.
    "editors_note": "The focus is moving from building the CoE to activating beyond it — internal engagement is established, office infrastructure is handed over, and Q2 is about bringing the outside in.",

    # ── Narrative content ─────────────────────────────────────────────────────
    "culture_pulse": "The room is settling into its own rhythm. Spring brought a shift in energy — the EM transition closed quietly, the community absorbed it without missing a beat, and members are now bringing their own ideas to the table without being asked. QBR week tested the full range of the role and held. Going into Q2, the foundation is solid and the focus is moving outward.",

    # Exactly two items, one sentence each. What you need to move faster.
    "what_i_need": [
        "A 1-hour working session on the community roadmap — ready to present, need your input to finalize Q2 direction.",
        "Early procurement conversations for the May floor expansion — validating the concept unlocks the timeline.",
    ],

    # Links shown under "Weekly Wins & Key Actions" inside "What We Built".
    # Each entry: {"url": "...", "label": "..."}. Empty list hides the subheader entirely.
    "links": [
        {"url": "https://calendar.google.com/calendar/u/0?cid=Y183OTY4NDBiMTA2MzI1NWQzMDBhZDc2NWQ2YWQyMTg1YWYzMWZkMzhkOWNhOWViOTAyMDMzYjVkZTk4Yzg3MTdkQGdyb3VwLmNhbGVuZGFyLmdvb2dsZS5jb20", "label": "EW Community Calendar"},
        {"url": "https://drive.google.com/file/d/1kyETRYD1BUvOJ96k45s2heAoZD_q6aQj/view?usp=sharing", "label": "External Community Vision"},
        {"url": "https://www.linkedin.com/posts/ideaspaces_communitymanager-algomarketing-idea-activity-7439368983029370880-bgZ3", "label": "Strategic Community Partnerships"},
    ],

    # Each item becomes a line in Scope Evolution — frame as demand signals
    "scope_evolution": [
        "Rockstaar collaboration underway — shaping the Evolved Worker tone of voice and talent brand positioning alongside the marketing team.",
        "AI Enabler service line launching — integrating alumni community and contractor talent pipeline into the community roadmap.",
    ],
}
# ─────────────────────────────────────────────────────────────────────────────


def week_bounds() -> tuple[str, str]:
    """Return ISO strings for Monday 00:00 and Sunday 23:59:59 of the current week."""
    today = datetime.now(tz=timezone.utc)
    monday = today - timedelta(days=today.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday = monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return monday.isoformat(), sunday.isoformat()


def _asana_client(pat: str) -> tuple:
    configuration = asana.Configuration()
    configuration.access_token = pat
    api_client = asana.ApiClient(configuration)
    return asana.TasksApi(api_client), asana.ProjectsApi(api_client)


def _fetch_project_info(projects_api, project_gid: str):
    try:
        return projects_api.get_project(project_gid, {"opt_fields": "name,permalink_url"})
    except ApiException as exc:
        print(f"[error] Could not fetch project {project_gid} ({exc.status}): {exc.reason}", file=sys.stderr)
        return None


def _fetch_all_tasks(tasks_api, project_gid: str) -> list[dict]:
    try:
        response = tasks_api.get_tasks_for_project(
            project_gid,
            {"opt_fields": "name,completed,completed_at,due_on,assignee.name"},
        )
        return list(response)
    except ApiException as exc:
        print(f"[error] Could not fetch tasks for {project_gid} ({exc.status}): {exc.reason}", file=sys.stderr)
        return []


def debug_asana(pat: str, project_gids: list[str]) -> None:
    """Print project names and all tasks from each project, then show the merged win list."""
    tasks_api, projects_api = _asana_client(pat)

    def fmt(t: dict, source: str) -> str:
        due       = t.get("due_on") or "no due date"
        completed = t.get("completed_at", "")[:10] if t.get("completed_at") else ""
        assignee  = (t.get("assignee") or {}).get("name", "unassigned")
        tag = f"completed {completed}" if completed else f"due {due}"
        return f"    · {t['name']}  [{assignee}]  {tag}  (source: {source})"

    all_tasks_by_project = {}

    for gid in project_gids:
        project = _fetch_project_info(projects_api, gid)
        if not project:
            continue
        name = project["name"]
        url  = project.get("permalink_url", "n/a")
        print(f"\n  Project : {name}")
        print(f"  URL     : {url}")
        print(f"  GID     : {gid}")

        tasks = _fetch_all_tasks(tasks_api, gid)
        all_tasks_by_project[name] = tasks

        done   = [t for t in tasks if t.get("completed")]
        active = [t for t in tasks if not t.get("completed")]

        print(f"\n  ── Active tasks ({len(active)}) ──────────────────────────────")
        for t in active:
            print(fmt(t, name))

        print(f"\n  ── Completed tasks ({len(done)}) ───────────────────────────")
        for t in done:
            print(fmt(t, name))

        print(f"\n  Subtotal: {len(tasks)} tasks ({len(done)} completed, {len(active)} active)")
        print()

    # Show merged wins preview using the same window as the main fetch
    if RETROSPECTIVE_MODE:
        since_iso = datetime.fromisoformat(RETROSPECTIVE_START).replace(tzinfo=timezone.utc).isoformat()
        window_label = f"since {RETROSPECTIVE_START}"
    else:
        since_iso, _ = week_bounds()
        window_label = "this week"
    merged = _merge_wins(all_tasks_by_project, since_iso)
    print(f"  ── Merged wins {window_label} ({len(merged)}) — {ASSIGNEE_FILTER} only, deduplicated, newest first ──")
    if merged:
        for w in merged:
            print(f"    ✓ {w['name']}  [completed {w['completed_at'][:10]}]  (from: {w['source']})")
    else:
        print("    None found this week.")
    print()


def _merge_wins(tasks_by_project: dict[str, list[dict]], since_iso: str) -> list[dict]:
    """
    Combine completed tasks from all projects since since_iso.
    Only includes tasks assigned to ASSIGNEE_FILTER.
    Deduplicates by task name (case-insensitive), keeping the most recent.
    Sorts newest completion first.
    """
    seen: dict[str, dict] = {}  # normalised name → task dict with 'source'

    for project_name, tasks in tasks_by_project.items():
        for task in tasks:
            if not task.get("completed"):
                continue
            completed_at = task.get("completed_at") or ""
            if completed_at < since_iso:
                continue
            assignee_name = (task.get("assignee") or {}).get("name", "")
            if ASSIGNEE_FILTER.lower() not in assignee_name.lower():
                continue
            key = task["name"].strip().lower()
            enriched = {**task, "source": project_name}
            if key not in seen or completed_at > seen[key].get("completed_at", ""):
                seen[key] = enriched

    return sorted(seen.values(), key=lambda t: t.get("completed_at", ""), reverse=True)


def fetch_asana_wins(pat: str, project_gids: list[str]) -> list[dict]:
    """Return deduplicated completed tasks across all projects, filtered and sorted newest first."""
    tasks_api, projects_api = _asana_client(pat)

    if RETROSPECTIVE_MODE:
        since_iso = datetime.fromisoformat(RETROSPECTIVE_START).replace(tzinfo=timezone.utc).isoformat()
        window_label = f"since {RETROSPECTIVE_START} (retrospective)"
    else:
        since_iso, _ = week_bounds()
        window_label = "this week"

    tasks_by_project: dict[str, list[dict]] = {}

    for gid in project_gids:
        project = _fetch_project_info(projects_api, gid)
        project_name = project["name"] if project else gid
        try:
            response = tasks_api.get_tasks_for_project(
                gid,
                {
                    "completed_since": since_iso,
                    "opt_fields": "name,completed,completed_at,assignee.name",
                },
            )
            tasks_by_project[project_name] = list(response)
            count = sum(
                1 for t in tasks_by_project[project_name]
                if t.get("completed")
                and ASSIGNEE_FILTER.lower() in (t.get("assignee") or {}).get("name", "").lower()
            )
            print(f"  [{project_name}] {count} matching completed task(s) {window_label}")
        except ApiException as exc:
            print(f"[warn] Asana error on {project_name} ({exc.status}): {exc.reason}", file=sys.stderr)

    return _merge_wins(tasks_by_project, since_iso)


def calculate_score(inputs: dict, tasks_completed: int) -> dict:
    """
    Community Pulse Score (0–100).

    Components:
      +40  Community Impact   (community_impact_score / 100) * 40
      +35  Program Delivery   (tasks_completed / tasks_planned) * 35
      +25  Scope Health       (scope_health / 100) * 25
    """
    p = inputs
    planned = max(p["tasks_planned"], 1)

    community_pts = (p["community_impact_score"] / 100) * 40
    delivery_pts  = min(tasks_completed / planned, 1.0) * 35
    scope_pts     = (p["scope_health"] / 100) * 25

    score = round(max(0, min(100, community_pts + delivery_pts + scope_pts)))

    prev = p.get("previous_score")
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
    debug = "--debug" in sys.argv
    pat = os.getenv("ASANA_PAT", "")

    # Collect all configured project GIDs (GID_1, GID_2, … up to GID_9)
    project_gids = [
        v for v in (
            os.getenv(f"ASANA_PROJECT_GID_{i}") for i in range(1, 10)
        )
        if v and v != "your_second_project_gid_here"
    ]

    manual_wins = MANUAL_INPUTS.get("manual_wins", [])

    if debug:
        print("── Debug: Asana project inspection ─────────────────────────────")
        debug_asana(pat, project_gids)
        print("────────────────────────────────────────────────────────────────")
        sys.exit(0)
    elif manual_wins:
        print(f"Using {len(manual_wins)} manually specified win(s) — skipping Asana fetch.")
        wins = manual_wins
    elif not pat or not project_gids:
        print("[warn] ASANA_PAT or no valid ASANA_PROJECT_GID_* found — skipping Asana fetch.")
        wins = []
    else:
        print(f"Fetching completed tasks from {len(project_gids)} Asana project(s)…")
        raw_wins = fetch_asana_wins(pat, project_gids)
        wins = [w["name"] for w in raw_wins]
        mode = f"since {RETROSPECTIVE_START}" if RETROSPECTIVE_MODE else "this week"
        print(f"  {len(wins)} unique completed task(s) {mode} (assigned to {ASSIGNEE_FILTER}).")

    score_data = calculate_score(MANUAL_INPUTS, tasks_completed=len(wins))

    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_label = MANUAL_INPUTS.get("week_label") or f"{monday.strftime('%b %-d')} – {sunday.strftime('%-d, %Y')}"

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
