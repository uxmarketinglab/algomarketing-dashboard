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
RETROSPECTIVE_MODE  = True
RETROSPECTIVE_START = "2026-03-01"  # ISO date, inclusive

# Only tasks assigned to someone whose name contains this string will appear.
ASSIGNEE_FILTER = "Christina"
# ─────────────────────────────────────────────────────────────────────────────

# ── Manual inputs — edit these each week ─────────────────────────────────────
MANUAL_INPUTS = {
    # ── Manual wins override ───────────────────────────────────────────────────
    # Populate this list to bypass Asana and use these as the wins this week.
    # Leave empty ([]) to pull from Asana automatically.
    "manual_wins": [
        "Evolved Worker Program: Mapped the full EW curriculum journey and designed the L&D certification pitch with cost framework — GenAI certification is now at 75% adoption across the CoE, with Study Groups launched using certified Algos as peer mentors.",
        "Algo Community Experience: Moved Innovation Sessions to Thursdays, invited leadership, and increased attendance by 75% — Post-Shift Drinks became self-organizing this quarter, with Algos now hosting independently without facilitation.",
        "Building the CoE: Selected office design partner at 60% under initial budget and completed handover of IT/office management to FinOps & PeopleOps — including IT FAQ, issues tracker, and vendor accounts.",
        "External Community & Brand: Engaged at four external events this quarter including the Lovable Hackathon, IDEA Networking Breakfast, XPAT Student Event, and AI Unicorn Factory — membership strategy and application framework for The Evolved is now designed and ready to launch.",
        "Strategic Partnerships & BD: Developed external community value proposition and began outreach for event partnerships — now looped into the Harmon x Algomarketing partnership with Lisbon execution expected in Q2.",
    ],

    # ── Score inputs ──────────────────────────────────────────────────────────
    # Tasks: Asana pulls completed count automatically; just set how many you planned.
    "tasks_planned": 6,

    # Community-building activities (workshops, calls, campaigns, etc.)
    "community_activities_executed": 3,
    "community_activities_planned": 4,

    # In-scope service requests (support tickets, member requests, etc.)
    "in_scope_handled": 16,
    "in_scope_received": 18,

    # Communication posture this week
    "proactive_actions": 9,   # You initiated: newsletters, check-ins, reports
    "reactive_actions": 2,    # You responded: unplanned requests, fires

    # Out-of-scope requests received (used for penalty AND Scope Evolution list)
    "out_of_scope_count": 2,

    # Previous week's score for trend arrow (set to None to hide arrow)
    "previous_score": 50,

    # One sentence. Sets the tone for the week. Sounds like you, not a template.
   "editors_note": "Q1 was about building something from nothing — the infrastructure is in place, the community is moving on its own, and this is what that looks like.",

    # ── Narrative content ─────────────────────────────────────────────────────
    "culture_pulse": (
    "The most telling sign this quarter wasn't an attendance number — it was watching community members start hosting their own gatherings without being asked. "
    "Post-Shift Drinks went from a managed event to something people claimed as their own. "
    "The Innovation Sessions followed the same arc: moving to Thursdays, inviting leadership, team inputs to structure, and doubling attendance shifted to a collaborative ownership over the learning agenda. "
"Senior leadership visits from Yomi, Dele, Lola, and Gillian weren't just check-ins — each one was a designed experience, and the feedback reflected that."   
 "The room's energy this week is focused and forward-looking — Q2 planning is live, the Evolved Worker curriculum has a shape, and the team knows what's coming next."
),

    # Each item becomes a line in "What I Need to Move Faster" — frame as accelerators, not complaints
    "accelerators": [
"Formal introduction to the broader Algomarketing organization — visibility gaps are slowing community foundations work",    
"External community brand identity alignment — sense check on direction will unlock tri-dimensional communication channel",    
],

    # Each item becomes a line in Scope Evolution — frame as demand signals
    "scope_evolution": [
    "Led full CoE office design from vendor sourcing to partner selection — a facilities and procurement initiative absorbed into community scope as the operational anchor of the CoE launch",
    "Became the de facto IT coordinator/office manager for the Lisbon team, creating the FAQ, managing the issues tracker strategy, and directing Algos on support protocols — now formally handed over to FinOps & PeopleOps",
"Looped into the Harmon x Algomarketing PR partnership — supporting the client acquisition events remotely in preparation for leading Lisbon events execution",
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
    Community Engagement Score (0–100).

    Components:
      +30  Task completion rate        (completed / planned)
      +25  Community activities rate   (executed / planned)
      +20  In-scope handling rate      (handled / received)
      +15  Proactive communication     (proactive / total actions)
      −10  Out-of-scope penalty        (scales with count, max −10)

    Base is normalised to 100, then the penalty is applied.
    """
    p = inputs
    planned = max(p["tasks_planned"], 1)
    act_planned = max(p["community_activities_planned"], 1)
    inscope_recv = max(p["in_scope_received"], 1)
    total_actions = max(p["proactive_actions"] + p["reactive_actions"], 1)

    task_rate       = min(tasks_completed / planned, 1.0)
    activity_rate   = min(p["community_activities_executed"] / act_planned, 1.0)
    inscope_rate    = min(p["in_scope_handled"] / inscope_recv, 1.0)
    proactive_rate  = p["proactive_actions"] / total_actions

    base = (
        task_rate      * 30
        + activity_rate  * 25
        + inscope_rate   * 20
        + proactive_rate * 15
    )  # max 90

    # Normalise to 100, then apply out-of-scope penalty (each request = 2 pts, max 10)
    normalised = (base / 90) * 100
    penalty = min(10, p["out_of_scope_count"] * 2)
    score = round(max(0, min(100, normalised - penalty)))

    # Trend vs previous week
    prev = p.get("previous_score")
    if prev is None:
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
        "breakdown": {
            "task_completion":   round(task_rate * 30, 1),
            "community_activities": round(activity_rate * 25, 1),
            "inscope_handling":  round(inscope_rate * 20, 1),
            "proactive_comms":   round(proactive_rate * 15, 1),
            "oos_penalty":       -penalty,
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
    week_label = f"{monday.strftime('%b %-d')} – {sunday.strftime('%-d, %Y')}"

    context = {
        "week_label": week_label,
        "generated_at": today.strftime("%Y-%m-%d %H:%M"),
        "score": score_data,
        "wins": wins,
        "culture_pulse": MANUAL_INPUTS["culture_pulse"],
        "scope_evolution": MANUAL_INPUTS["scope_evolution"],
        "editors_note": MANUAL_INPUTS.get("editors_note", ""),
        "accelerators": MANUAL_INPUTS.get("accelerators", []),
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
