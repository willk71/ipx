import os
import sys
import json
import re
import datetime
import webbrowser
import hashlib
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np

# -------------------------------------------------------------
# Staff Portal Security
# Set the shared team passcode here (case-insensitive)
# -------------------------------------------------------------
TEAM_PASSCODE = os.environ.get("TEAM_PASSCODE", "ipxstaff")
PASSCODE_HASH = hashlib.sha256(TEAM_PASSCODE.strip().lower().encode("utf-8")).hexdigest()

DATA_DIR = os.path.abspath("data")
SCHEDULES_DIR = os.path.abspath("schedules")
SCHEDULES_JSON_PATH = os.path.join(DATA_DIR, "staff_schedules.json")

# Default distinct color palette for staff members
DEFAULT_PALETTE = {
    "Carlos": "#1E5F8A",
    "Carl": "#D96B27",
    "Kadeem": "#2E7D32",
    "Nicole": "#7B1FA2",
    "Johnpaul": "#C2185B",
    "Will": "#0D9488",
    "Alex": "#E11D48",
    "Sam": "#4F46E5",
    "Jordan": "#D97706",
    "Chris": "#059669",
}

EXTRA_COLORS = [
    "#0284C7", "#7C3AED", "#DB2777", "#EA580C", "#65A30D",
    "#0891B2", "#9333EA", "#C026D3", "#B45309", "#15803D"
]

def get_color_for_person(name, existing_palette):
    if name in existing_palette:
        return existing_palette[name]
    if name in DEFAULT_PALETTE:
        return DEFAULT_PALETTE[name]
    used = set(existing_palette.values())
    for c in EXTRA_COLORS:
        if c not in used:
            return c
    return "#3B82F6"


# -------------------------------------------------------------
# Text Schedule Parser
# Parses raw text (from images/OCR/spreadsheets) into shift data
# -------------------------------------------------------------
def parse_time_str(t_str, is_end=False, prev_hour=None):
    t = t_str.strip().lower()
    m = re.match(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a|p)?', t)
    if not m:
        return None
    h = int(m.group(1))
    mins = int(m.group(2) or 0)
    merid = m.group(3)
    if merid:
        if merid.startswith('p') and h < 12:
            h += 12
        elif merid.startswith('a') and h == 12:
            h = 0
    else:
        # Infer meridiem based on operating hours (8:00 AM - 11:30 PM)
        if h < 8:
            h += 12
        elif is_end and prev_hour and h < prev_hour:
            h += 12
    return h + mins / 60.0

def format_hour_decimal_label(start_dec, end_dec):
    def fmt(t):
        h = int(t)
        m = int(round((t - h) * 60))
        suffix = "AM" if h < 12 else "PM"
        display_h = h if h <= 12 else h - 12
        if display_h == 0:
            display_h = 12
        return f"{display_h}:{m:02d} {suffix}"
    return f"{fmt(start_dec)} - {fmt(end_dec)}"

def parse_schedule_text(raw_text, start_date_str="2026-10-19"):
    """
    Parses unstructured or structured schedule text into shifts.
    Accepts text grouped by day (e.g. 'Mon 19', 'Monday', 'Tuesday')
    with lines like:
      Carlos 4:00 PM - 11:00 PM
      Johnpaul: 9:00 AM - 1:30 PM, 6:30 PM - 11:00 PM
    """
    day_map = {
        'mon': 0, 'monday': 0,
        'tue': 1, 'tues': 1, 'tuesday': 1,
        'wed': 2, 'wednesday': 2,
        'thu': 3, 'thur': 3, 'thurs': 3, 'thursday': 3,
        'fri': 4, 'friday': 4,
        'sat': 5, 'saturday': 5,
        'sun': 6, 'sunday': 6
    }

    shifts = []
    current_day = 0
    time_pattern = re.compile(
        r'(\d{1,2}(?::\d{2})?\s*(?:am|pm|a|p)?)\s*[-–—to]+\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|a|p)?)',
        re.I
    )

    day_header_pattern = re.compile(
        r'^(mon|tue|wed|thu|fri|sat|sun)\w*\s*(\d+)?',
        re.I
    )

    lines = raw_text.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for tab-separated row (e.g. from copy-pasting an ADP table or spreadsheet)
        if '\t' in line:
            parts = [p.strip() for p in line.split('\t')]
            name_cell = parts[0]
            # Ignore header or title rows
            if re.match(r'^(people|employee|staff|name|week|printed)', name_cell, re.I):
                continue

            # Clean employee name (strip "Draft", trailing punctuation, and format "Last, First" -> First)
            name_clean = re.sub(r'\b\(?draft\)?\b', '', name_cell, flags=re.I).strip()
            name_clean = re.sub(r'[:\-\*\•\d\.]+$', '', name_clean).strip()
            if ',' in name_clean:
                p_parts = [p.strip() for p in name_clean.split(',')]
                if len(p_parts) >= 2 and p_parts[1]:
                    name_clean = p_parts[1].split()[0]
            name = name_clean.title() if name_clean else "Staff"

            # Parse columns 1 through 7 for Mon-Sun
            col_cells = parts[1:]
            for col_idx, cell in enumerate(col_cells[:7]):
                cell_clean = re.sub(r'\b\(?draft\)?\b', '', cell, flags=re.I).strip()
                t_matches = list(time_pattern.finditer(cell_clean))
                for tm in t_matches:
                    start_raw, end_raw = tm.group(1), tm.group(2)
                    s_dec = parse_time_str(start_raw)
                    e_dec = parse_time_str(end_raw, is_end=True, prev_hour=s_dec)
                    if s_dec is not None and e_dec is not None and e_dec > s_dec:
                        lbl = format_hour_decimal_label(s_dec, e_dec)
                        shifts.append({
                            "name": name,
                            "day": col_idx,
                            "start": s_dec,
                            "end": e_dec,
                            "label": lbl
                        })
            continue

        # Clean line of "draft" tag
        line_clean = re.sub(r'\b\(?draft\)?\b', '', line, flags=re.I).strip()

        # Check for day header
        dh_match = day_header_pattern.match(line_clean)
        if dh_match and not time_pattern.search(line_clean):
            d_name = dh_match.group(1).lower()
            if d_name in day_map:
                current_day = day_map[d_name]
                continue

        # Find all time ranges on this line
        time_matches = list(time_pattern.finditer(line_clean))
        if not time_matches:
            # Check if line indicates day header without standard word boundary
            for d_key, d_idx in day_map.items():
                if line_clean.lower().startswith(d_key):
                    current_day = d_idx
                    break
            continue

        # Extract name from preceding text
        first_time_idx = time_matches[0].start()
        prefix = line_clean[:first_time_idx].strip()
        prefix = re.sub(r'\b\(?draft\)?\b', '', prefix, flags=re.I).strip()
        name_clean = re.sub(r'[:\-\*\•\d\.]+$', '', prefix).strip()
        # Remove leading day names if present in the same line (e.g. "Mon Carlos 4pm-11pm")
        for d_key in sorted(day_map.keys(), key=len, reverse=True):
            if name_clean.lower().startswith(d_key):
                current_day = day_map[d_key]
                name_clean = name_clean[len(d_key):].strip(" :-–—\t\r\n")
                break

        # Handle "Last, First" in line format
        if ',' in name_clean:
            p_parts = [p.strip() for p in name_clean.split(',')]
            if len(p_parts) >= 2 and p_parts[1]:
                name_clean = p_parts[1].split()[0]

        name = name_clean.title() if name_clean else "Staff"

        # Parse each shift on this line
        for tm in time_matches:
            start_raw, end_raw = tm.group(1), tm.group(2)
            s_dec = parse_time_str(start_raw)
            e_dec = parse_time_str(end_raw, is_end=True, prev_hour=s_dec)
            if s_dec is not None and e_dec is not None and e_dec > s_dec:
                lbl = format_hour_decimal_label(s_dec, e_dec)
                shifts.append({
                    "name": name,
                    "day": current_day,
                    "start": s_dec,
                    "end": e_dec,
                    "label": lbl
                })

    # Compute day date labels based on start_date_str
    try:
        dt_start = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except Exception:
        dt_start = datetime.date(2026, 10, 19)

    days = []
    day_abbrs = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i in range(7):
        cur_d = dt_start + datetime.timedelta(days=i)
        days.append(f"{day_abbrs[i]} {cur_d.day}")

    return shifts, days


# -------------------------------------------------------------
# Gantt Chart Renderer
# High-DPI, large-text, publication-quality shift schedule chart
# -------------------------------------------------------------
def render_gantt_chart(week_id, shifts, days, title, output_path, palette):
    day_shifts = {d: [] for d in range(7)}
    for s in shifts:
        day_shifts[s["day"]].append(s)

    # High-resolution figure with comfortable margins for readability
    fig, ax = plt.subplots(figsize=(20, 11.8), dpi=180)
    fig.patch.set_facecolor("#F8F9FA")
    ax.set_facecolor("#FFFFFF")

    # Alternating day background columns
    for day_idx in range(7):
        bg_color = "#EBF0F5" if day_idx % 2 == 1 else "#FFFFFF"
        ax.axvspan(day_idx, day_idx + 1, facecolor=bg_color, alpha=0.9, zorder=0)

    # Half-hour grid lines
    y_half_hours = np.arange(8.0, 24.5, 0.5)
    for y in y_half_hours:
        if y % 1.0 == 0:
            ax.axhline(y, color="#CBD5E1", linestyle="-", linewidth=0.9, alpha=0.85, zorder=1)
        else:
            ax.axhline(y, color="#E2E8F0", linestyle=":", linewidth=0.7, alpha=0.75, zorder=1)

    # Side-by-side sub-columns for overlapping shifts
    track_padding = 0.035
    for day_idx, d_shifts in day_shifts.items():
        d_shifts.sort(key=lambda s: (s["start"], s["name"]))
        columns = []
        shift_col = {}
        for s in d_shifts:
            placed = False
            for c_idx, col in enumerate(columns):
                if col[-1]["end"] <= s["start"]:
                    col.append(s)
                    shift_col[id(s)] = c_idx
                    placed = True
                    break
            if not placed:
                shift_col[id(s)] = len(columns)
                columns.append([s])

        num_cols = max(len(columns), 1)
        col_width = (1.0 - 2 * track_padding) / num_cols

        for s in d_shifts:
            c_idx = shift_col[id(s)]
            x_left = day_idx + track_padding + c_idx * col_width + 0.015
            width = col_width - 0.03
            y_bottom = s["start"]
            height = s["end"] - s["start"]
            color = palette.get(s["name"], "#1E5F8A")

            # Shift bar with rounded corners
            box = patches.FancyBboxPatch(
                (x_left, y_bottom), width, height,
                boxstyle="round,pad=0.015,rounding_size=0.07",
                facecolor=color, edgecolor="#0F172A", linewidth=1.4, alpha=0.94, zorder=3
            )
            ax.add_patch(box)

            # Enhanced typography: larger, bolder text for crisp legibility
            label_text = f"{s['name']}\n{s['label']}"
            y_center = y_bottom + (height / 2.0)
            x_center = x_left + (width / 2.0)

            # Scale font slightly if many columns share the day
            font_size = 11.5 if num_cols <= 2 else (10.5 if num_cols == 3 else 9.5)

            ax.text(
                x_center, y_center, label_text,
                color="#FFFFFF", weight="bold", fontsize=font_size,
                rotation=90,
                ha="center", va="center", linespacing=1.25, zorder=4
            )

    # Left Y-axis: 8:00 AM at top to 11:30 PM at bottom
    ax.set_ylim(23.5, 8.0)
    time_ticks = np.arange(8.0, 24.0, 0.5)

    def format_half_hour(t):
        h = int(t)
        m = int(round((t - h) * 60))
        suffix = "AM" if h < 12 else "PM"
        display_h = h if h <= 12 else h - 12
        if display_h == 0:
            display_h = 12
        return f"{display_h}:{m:02d} {suffix}"

    ax.set_yticks(time_ticks)
    ax.set_yticklabels(
        [format_half_hour(t) for t in time_ticks],
        fontsize=11.5, fontweight="bold", color="#334155"
    )
    ax.set_ylabel(
        "Time of Day (Half-Hour Increments)",
        fontsize=13.5, fontweight="bold", color="#0F172A", labelpad=14
    )

    # Top X-axis: Days of the week
    ax.set_xlim(0, 7)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_xticks([i + 0.5 for i in range(7)])
    ax.set_xticklabels(days, fontsize=14.5, fontweight="bold", color="#0F172A")
    ax.tick_params(axis="x", which="both", pad=14)

    for x in range(8):
        ax.axvline(x, color="#94A3B8", linestyle="-", linewidth=1.4, zorder=2)

    for spine in ax.spines.values():
        spine.set_edgecolor("#94A3B8")
        spine.set_linewidth(1.3)

    # Title & Legend
    plt.title(title, fontsize=18, fontweight="bold", pad=28, color="#0F172A")

    people_in_shifts = sorted(list(set(s["name"] for s in shifts)))
    legend_handles = [
        patches.Patch(
            facecolor=palette.get(p, "#3B82F6"),
            edgecolor="#1E293B",
            label=p,
            linewidth=1.0,
            alpha=0.95
        ) for p in people_in_shifts
    ]

    ax.legend(
        handles=legend_handles, loc="lower center", bbox_to_anchor=(0.5, -0.075),
        ncol=min(len(people_in_shifts), 6), frameon=True,
        facecolor="#FFFFFF", edgecolor="#CBD5E1",
        fontsize=12, title="Team Members", title_fontsize=13
    )

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.07, top=0.91)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


# -------------------------------------------------------------
# Multi-Week Data Storage & HTML Generation
# -------------------------------------------------------------
def load_all_weeks():
    if os.path.exists(SCHEDULES_JSON_PATH):
        try:
            with open(SCHEDULES_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"current_week": "", "weeks": {}}

def save_all_weeks(master_data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCHEDULES_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(master_data, f, indent=2)

def register_week(week_id, shifts, days, title, label, palette=None):
    master = load_all_weeks()
    if palette is None:
        palette = dict(DEFAULT_PALETTE)

    # Compute people and palette
    people = sorted(list(set(s["name"] for s in shifts)))
    for p in people:
        if p not in palette:
            palette[p] = get_color_for_person(p, palette)

    # Calculate employee stats
    stats = {}
    for s in shifts:
        n = s["name"]
        if n not in stats:
            stats[n] = {"hours": 0.0, "shifts": 0, "color": palette.get(n, "#3B82F6")}
        stats[n]["hours"] += s["end"] - s["start"]
        stats[n]["shifts"] += 1

    total_hours = sum(st["hours"] for st in stats.values())
    total_shifts = sum(st["shifts"] for st in stats.values())

    # Generate image for this week
    week_img_filename = f"schedule_{week_id}.png"
    week_img_path = os.path.join(SCHEDULES_DIR, week_img_filename)
    render_gantt_chart(week_id, shifts, days, title, week_img_path, palette)

    # Also update root team_schedule_gantt.png to point to this week
    root_img_path = os.path.abspath("team_schedule_gantt.png")
    render_gantt_chart(week_id, shifts, days, title, root_img_path, palette)

    week_entry = {
        "week_id": week_id,
        "label": label,
        "title": title,
        "image": f"schedules/{week_img_filename}",
        "days": days,
        "people": people,
        "palette": palette,
        "total_hours": total_hours,
        "total_shifts": total_shifts,
        "stats": stats,
        "shifts": shifts
    }

    master["weeks"][week_id] = week_entry
    master["current_week"] = week_id
    save_all_weeks(master)
    print(f"Registered week {week_id}: {label}")
    print(f"Chart saved to: {week_img_path}")
    return master


def generate_schedule_html():
    master = load_all_weeks()
    weeks = master.get("weeks", {})
    if not weeks:
        print("No weeks available to generate HTML.")
        return

    # Automatically set current_week based on today's date
    today = datetime.date.today()
    sorted_ids = sorted(weeks.keys())
    active_week = sorted_ids[0]
    for wId in sorted_ids:
        try:
            dt_s = datetime.datetime.strptime(wId, "%Y-%m-%d").date()
            dt_e = dt_s + datetime.timedelta(days=6)
            if dt_s <= today <= dt_e:
                active_week = wId
                break
            elif dt_s <= today:
                active_week = wId
        except Exception:
            pass
    master["current_week"] = active_week

    # Embed data JSON directly into HTML so page works instantly without extra fetch latency
    weeks_json_str = json.dumps(master, indent=2)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="robots" content="noindex, nofollow" />
  <title>Staff Portal &mdash; IPX Operations</title>
  <link rel="stylesheet" href="css/common.css?v=2.2.7" />
  <style>
    body {{
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      padding: 1.5vh 2vw;
      background: var(--bg-gradient);
      color: var(--text-main);
      overflow-x: hidden;
    }}

    /* Auth Overlay */
    .auth-overlay {{
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: radial-gradient(circle at 50% 30%, #1a1a1c 0%, #0d0d0f 65%, #000000 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      padding: 20px;
    }}

    .auth-card {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 20px;
      padding: 4vh 2.5vw;
      width: 100%;
      max-width: 420px;
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.65);
      text-align: center;
      display: flex;
      flex-direction: column;
      gap: 1.8vh;
    }}

    .auth-icon {{
      font-size: 3rem;
      line-height: 1;
    }}

    .auth-title {{
      font-size: clamp(1.5rem, 2vw, 2.1rem);
      font-weight: 800;
      color: #ffffff;
      letter-spacing: -0.02em;
      margin: 0;
    }}

    .auth-subtitle {{
      font-size: 0.95rem;
      color: var(--text-sub);
      opacity: 0.8;
      margin: 0;
    }}

    .auth-input-group {{
      position: relative;
      display: flex;
      align-items: center;
      margin-top: 1vh;
    }}

    .auth-input {{
      width: 100%;
      background: rgba(0, 0, 0, 0.45);
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: #ffffff;
      font-size: 1.25rem;
      padding: 1.3vh 48px 1.3vh 16px;
      border-radius: 12px;
      outline: none;
      transition: all 0.2s ease;
      text-align: center;
      letter-spacing: 0.12em;
    }}

    .auth-input:focus {{
      border-color: var(--theme-accent);
      box-shadow: 0 0 0 3px rgba(255, 214, 10, 0.25);
    }}

    .btn-toggle-vis {{
      position: absolute;
      right: 12px;
      background: transparent;
      border: none;
      color: rgba(255, 255, 255, 0.55);
      cursor: pointer;
      font-size: 1.2rem;
      padding: 4px;
    }}

    .btn-toggle-vis:hover {{
      color: #ffffff;
    }}

    .auth-error {{
      color: #ff453a;
      font-size: 0.9rem;
      font-weight: 600;
      background: rgba(255, 69, 58, 0.12);
      border: 1px solid rgba(255, 69, 58, 0.3);
      border-radius: 8px;
      padding: 0.8vh 1vw;
    }}

    .auth-remember {{
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.9rem;
      color: var(--text-muted);
      cursor: pointer;
      user-select: none;
    }}

    .auth-remember label {{
      display: inline-flex;
      align-items: center;
      gap: 0.6vw;
      cursor: pointer;
    }}

    .btn-unlock {{
      background: var(--theme-accent);
      color: #000000;
      font-size: 1.1rem;
      font-weight: 700;
      border: none;
      border-radius: 12px;
      padding: 1.4vh 1.5vw;
      cursor: pointer;
      transition: all 0.2s ease;
      margin-top: 0.5vh;
    }}

    .btn-unlock:hover {{
      background: #ffe14d;
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(255, 214, 10, 0.35);
    }}

    /* Protected Content Layout */
    #schedule-content {{
      display: flex;
      flex-direction: column;
      flex: 1;
    }}

    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 1.5vh;
      border-bottom: 1px solid var(--card-border);
      flex-wrap: wrap;
      gap: 1vh;
    }}

    .header-left h1 {{
      font-size: clamp(1.4rem, 2vw, 2.3rem);
      font-weight: 800;
      letter-spacing: -0.02em;
      margin: 0;
      white-space: nowrap;
      color: #ffffff;
    }}

    .header-badge {{
      background: rgba(255, 214, 10, 0.15);
      border: 1px solid rgba(255, 214, 10, 0.4);
      color: var(--theme-accent);
      font-size: clamp(0.85rem, 0.95vw, 1.15rem);
      font-weight: 700;
      padding: 0.4vh 1vw;
      border-radius: 999px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}

    .badge-internal {{
      background: rgba(255, 69, 58, 0.15) !important;
      border-color: rgba(255, 69, 58, 0.4) !important;
      color: #ff6961 !important;
    }}

    /* Compact Integrated Yellow Week Nav Pill */
    .week-pill-badge {{
      display: inline-flex;
      align-items: center;
      background: rgba(255, 214, 10, 0.15);
      border: 1px solid rgba(255, 214, 10, 0.45);
      border-radius: 999px;
      padding: 0.2vh 0.4vw;
      gap: 0.2vw;
      transition: all 0.2s ease;
      box-shadow: 0 2px 10px rgba(255, 214, 10, 0.12);
    }}

    .week-pill-badge:hover {{
      border-color: rgba(255, 214, 10, 0.7);
      background: rgba(255, 214, 10, 0.22);
    }}

    .week-arrow-btn {{
      background: transparent;
      border: none;
      color: var(--theme-accent);
      font-size: 1.45rem;
      font-weight: 800;
      line-height: 1;
      cursor: pointer;
      padding: 0.2vh 0.6vw;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      transition: all 0.15s ease;
    }}

    .week-arrow-btn:hover:not(:disabled) {{
      background: rgba(255, 214, 10, 0.35);
      color: #ffffff;
      transform: scale(1.15);
    }}

    .week-arrow-btn:disabled {{
      opacity: 0.25;
      cursor: not-allowed;
      transform: none;
    }}

    .week-pill-center {{
      position: relative;
      display: inline-flex;
      align-items: center;
      cursor: pointer;
    }}

    .week-pill-label {{
      color: var(--theme-accent);
      font-size: clamp(0.85rem, 0.95vw, 1.15rem);
      font-weight: 700;
      letter-spacing: 0.03em;
      white-space: nowrap;
      pointer-events: none;
      padding: 0 0.2vw;
    }}

    .week-pill-select {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      opacity: 0;
      cursor: pointer;
    }}

    .header-actions {{
      display: flex;
      align-items: center;
      gap: 0.8vw;
    }}

    .btn-action {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      color: var(--text-sub);
      text-decoration: none;
      font-size: clamp(0.85rem, 0.95vw, 1.15rem);
      font-weight: 600;
      padding: 0.6vh 1.2vw;
      border-radius: 8px;
      transition: all 0.2s ease;
      display: inline-flex;
      align-items: center;
      gap: 0.4vw;
      cursor: pointer;
    }}

    .btn-action:hover {{
      background: rgba(255, 255, 255, 0.12);
      border-color: rgba(255, 255, 255, 0.25);
      color: #ffffff;
      transform: translateY(-1px);
    }}

    .main-content {{
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 1.2vh;
      margin-top: 1.2vh;
      min-height: 0;
    }}

    /* Stats Overview Grid - Compact */
    .stats-bar {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 0.8vw;
      flex-shrink: 0;
    }}

    .stat-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 0.7vh 0.9vw;
      display: flex;
      align-items: center;
      gap: 0.7vw;
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }}

    .stat-chip {{
      width: 10px;
      height: 30px;
      border-radius: 3px;
      flex-shrink: 0;
    }}

    .stat-info {{
      display: flex;
      flex-direction: column;
      min-width: 0;
    }}

    .stat-name {{
      font-size: clamp(0.95rem, 1.05vw, 1.25rem);
      font-weight: 700;
      color: #ffffff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .stat-hours {{
      font-size: clamp(0.78rem, 0.85vw, 1.05rem);
      color: var(--text-muted);
      font-weight: 500;
    }}

    .stat-hours strong {{
      color: var(--theme-accent);
      font-weight: 700;
    }}

    /* Chart Container - Auto-resized so bottom 11:30 PM & legend always show */
    .schedule-wrapper {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 1vh 1vw;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
      overflow: hidden;
      flex: 1;
      min-height: 0;
    }}

    .schedule-img-container {{
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      text-align: center;
    }}

    .schedule-img {{
      max-width: 100%;
      max-height: calc(100vh - 195px); /* Entire image always fits; bottom 11:30 PM & legend always visible */
      width: auto;
      height: auto;
      object-fit: contain;
      display: block;
      border-radius: 8px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }}

    footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: clamp(0.8rem, 0.85vw, 1.05rem);
      color: var(--text-muted);
      padding-top: 1.2vh;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      margin-top: 1.2vh;
      flex-wrap: wrap;
      gap: 1vh;
      flex-shrink: 0;
    }}

    .footer-left {{
      display: flex;
      align-items: center;
      gap: 0.8vw;
    }}

    @keyframes shake {{
      0%, 100% {{ transform: translateX(0); }}
      20%, 60% {{ transform: translateX(-8px); }}
      40%, 80% {{ transform: translateX(8px); }}
    }}

    .shake {{
      animation: shake 0.35s ease-in-out;
    }}

    @media (max-width: 768px) {{
      .schedule-wrapper {{
        max-height: none;
        overflow-x: auto;
      }}
      .schedule-img {{
        max-height: none;
        min-width: 850px;
      }}
    }}
  </style>
</head>
<body class="page-schedule theme-apple">

  <!-- Lock / Authentication Overlay -->
  <div id="auth-overlay" class="auth-overlay">
    <div class="auth-card">
      <div class="auth-icon">&#x1F512;</div>
      <h2 class="auth-title">IPX Staff Portal</h2>
      <p class="auth-subtitle">Restricted Access &bull; Team Operations</p>
      <form id="auth-form" onsubmit="handleAuthSubmit(event)">
        <div class="auth-input-group">
          <input
            type="password"
            id="passcode-input"
            class="auth-input"
            placeholder="Enter team passcode"
            autocomplete="current-password"
            required
          />
          <button type="button" class="btn-toggle-vis" onclick="togglePasscodeVis()" title="Show/Hide">&#x1F441;</button>
        </div>
        <div id="auth-error" class="auth-error" style="display: none;">Incorrect passcode. Please try again.</div>
        <div class="auth-remember" style="margin-top: 1vh;">
          <label>
            <input type="checkbox" id="remember-me" checked />
            <span>Remember this device</span>
          </label>
        </div>
        <button type="submit" class="btn-unlock" style="width: 100%;">Unlock Schedule</button>
      </form>
    </div>
  </div>

  <!-- Protected Schedule Content -->
  <div id="schedule-content" style="display: none;">
    <header>
      <div class="header-left">
        <h1 id="header-title" style="white-space: nowrap; margin: 0; font-size: clamp(1.4rem, 2vw, 2.3rem); font-weight: 800; letter-spacing: -0.02em;">
          IPX Staff Schedule
        </h1>
        <div class="week-pill-badge">
          <button id="btn-prev-week" class="week-arrow-btn" onclick="stepWeek(-1)" title="Previous Week">&#x2039;</button>
          <div class="week-pill-center" title="Click to choose a week">
            <span id="active-week-badge" class="week-pill-label">--</span>
            <select id="week-dropdown" class="week-pill-select" onchange="onWeekDropdownChange(this.value)"></select>
          </div>
          <button id="btn-next-week" class="week-arrow-btn" onclick="stepWeek(1)" title="Next Week">&#x203A;</button>
        </div>
        <span class="header-badge badge-internal">Internal Only</span>
      </div>

      <div class="header-actions">
        <button type="button" class="btn-action" onclick="lockSchedule()" title="Lock Screen">
          <span>&#x1F512;</span> Lock
        </button>
        <a id="btn-full-size" href="team_schedule_gantt.png" target="_blank" class="btn-action" title="View Full Resolution">
          <span>&#x2922;</span> Full Size
        </a>
        <a id="btn-download" href="team_schedule_gantt.png" download="IPX_Team_Schedule.png" class="btn-action" title="Download Image">
          <span>&#x21E9;</span> Download
        </a>
        <a href="https://ipxbk.com" class="btn-action" title="Go to Public Court Display">
          <span>&#x2190;</span> Court Display
        </a>
      </div>
    </header>

    <main class="main-content">
      <!-- Dynamic Stats Grid -->
      <section id="stats-container" class="stats-bar"></section>

      <!-- Dynamic Schedule Chart -->
      <section class="schedule-wrapper">
        <div class="schedule-img-container">
          <img
            id="schedule-chart"
            alt="IPX Team Staff Schedule"
            class="schedule-img"
          />
        </div>
      </section>
    </main>

    <footer>
      <div class="footer-left">
        <span>IPX Staff Operations System</span>
        <span>&bull;</span>
        <span id="sync-indicator">Auto-refreshed</span>
      </div>
      <div class="footer-right">
        <span id="host-url-display">staff.ipxbk.com</span>
      </div>
    </footer>
  </div>

  <script>
    const SCHEDULE_DATA = {weeks_json_str};
    const TARGET_HASH = "{PASSCODE_HASH}";
    let activeWeekId = SCHEDULE_DATA.current_week || Object.keys(SCHEDULE_DATA.weeks || {{}})[0];

    const overlay = document.getElementById('auth-overlay');
    const content = document.getElementById('schedule-content');
    const chartImg = document.getElementById('schedule-chart');
    const errorBox = document.getElementById('auth-error');
    const passInput = document.getElementById('passcode-input');
    const weekDropdown = document.getElementById('week-dropdown');
    const activeBadge = document.getElementById('active-week-badge');
    const statsContainer = document.getElementById('stats-container');
    const btnFullSize = document.getElementById('btn-full-size');
    const btnDownload = document.getElementById('btn-download');
    const btnPrevWeek = document.getElementById('btn-prev-week');
    const btnNextWeek = document.getElementById('btn-next-week');

    async function computeHash(text) {{
      const enc = new TextEncoder();
      const data = enc.encode(text.trim().toLowerCase());
      const hash = await crypto.subtle.digest('SHA-256', data);
      return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
    }}

    function getSortedWeekIds() {{
      return Object.keys(SCHEDULE_DATA.weeks || {{}}).sort();
    }}

    function populateWeekDropdown() {{
      const sortedIds = getSortedWeekIds();
      weekDropdown.innerHTML = '';
      sortedIds.forEach(wId => {{
        const opt = document.createElement('option');
        opt.value = wId;
        opt.textContent = SCHEDULE_DATA.weeks[wId].label || wId;
        if (wId === activeWeekId) opt.selected = true;
        weekDropdown.appendChild(opt);
      }});
    }}

    function renderActiveWeek() {{
      const week = SCHEDULE_DATA.weeks[activeWeekId];
      if (!week) return;

      // Update badge and dropdown
      if (activeBadge) activeBadge.textContent = week.label;
      if (weekDropdown) weekDropdown.value = activeWeekId;

      // Update image and action links
      const imgPath = `${{week.image}}?v=${{Date.now()}}`;
      chartImg.src = imgPath;
      chartImg.alt = week.title || `Schedule for ${{week.label}}`;
      btnFullSize.href = week.image;
      btnDownload.href = week.image;
      btnDownload.download = `IPX_Schedule_${{activeWeekId}}.png`;

      // Update stats cards
      statsContainer.innerHTML = '';
      const stats = week.stats || {{}};
      Object.keys(stats).forEach(name => {{
        const s = stats[name];
        const card = document.createElement('div');
        card.className = 'stat-card';
        card.innerHTML = `
          <div class="stat-chip" style="background-color: ${{s.color}};"></div>
          <div class="stat-info">
            <span class="stat-name">${{name}}</span>
            <span class="stat-hours"><strong>${{s.hours.toFixed(1)}}h</strong> &bull; ${{s.shifts}} ${{s.shifts === 1 ? 'shift' : 'shifts'}}</span>
          </div>
        `;
        statsContainer.appendChild(card);
      }});

      // Total team card
      const totalCard = document.createElement('div');
      totalCard.className = 'stat-card';
      totalCard.style.borderColor = 'rgba(255, 214, 10, 0.35)';
      totalCard.style.background = 'rgba(255, 214, 10, 0.05)';
      totalCard.innerHTML = `
        <div class="stat-chip" style="background-color: var(--theme-accent);"></div>
        <div class="stat-info">
          <span class="stat-name" style="color: var(--theme-accent);">Total Team</span>
          <span class="stat-hours"><strong style="color: #ffffff;">${{week.total_hours.toFixed(1)}}h</strong> &bull; ${{week.total_shifts}} shifts</span>
        </div>
      `;
      statsContainer.appendChild(totalCard);

      // Update prev/next button disabled state
      const sortedIds = getSortedWeekIds();
      const curIdx = sortedIds.indexOf(activeWeekId);
      btnPrevWeek.disabled = (curIdx <= 0);
      btnNextWeek.disabled = (curIdx === -1 || curIdx >= sortedIds.length - 1);
    }}

    function onWeekDropdownChange(newWeekId) {{
      if (newWeekId && SCHEDULE_DATA.weeks[newWeekId]) {{
        activeWeekId = newWeekId;
        renderActiveWeek();
        updateUrlWeekParam();
      }}
    }}

    function stepWeek(offset) {{
      const sortedIds = getSortedWeekIds();
      const curIdx = sortedIds.indexOf(activeWeekId);
      if (curIdx === -1) return;
      const targetIdx = curIdx + offset;
      if (targetIdx >= 0 && targetIdx < sortedIds.length) {{
        activeWeekId = sortedIds[targetIdx];
        renderActiveWeek();
        updateUrlWeekParam();
      }}
    }}

    function updateUrlWeekParam() {{
      const params = new URLSearchParams(window.location.search);
      params.set('w', activeWeekId);
      const cleanUrl = `${{window.location.pathname}}?${{params.toString()}}`;
      window.history.replaceState({{}}, document.title, cleanUrl);
    }}

    // Keyboard navigation: Left & Right arrows flip through weeks
    window.addEventListener('keydown', (e) => {{
      if (content.style.display !== 'none' && document.activeElement.tagName !== 'INPUT') {{
        if (e.key === 'ArrowLeft') stepWeek(-1);
        if (e.key === 'ArrowRight') stepWeek(1);
      }}
    }});

    function unlockUI() {{
      overlay.style.display = 'none';
      content.style.display = 'flex';
      populateWeekDropdown();
      renderActiveWeek();
    }}

    function showLockUI() {{
      content.style.display = 'none';
      overlay.style.display = 'flex';
      chartImg.removeAttribute('src');
      if (errorBox) errorBox.style.display = 'none';
      if (passInput) {{
        passInput.value = '';
        passInput.focus();
      }}
    }}

    function lockSchedule() {{
      localStorage.removeItem('ipx_staff_auth');
      showLockUI();
    }}

    function togglePasscodeVis() {{
      if (passInput) {{
        passInput.type = passInput.type === 'password' ? 'text' : 'password';
      }}
    }}

    async function handleAuthSubmit(e) {{
      if (e) e.preventDefault();
      const entered = (passInput ? passInput.value : '').trim();
      if (!entered) return;

      try {{
        const hash = await computeHash(entered);
        if (hash === TARGET_HASH) {{
          const remember = document.getElementById('remember-me')?.checked;
          if (remember) {{
            localStorage.setItem('ipx_staff_auth', TARGET_HASH);
          }}
          if (errorBox) errorBox.style.display = 'none';
          unlockUI();
        }} else {{
          if (errorBox) {{
            errorBox.style.display = 'block';
            errorBox.textContent = 'Incorrect passcode. Please try again.';
          }}
          passInput.classList.add('shake');
          setTimeout(() => passInput.classList.remove('shake'), 400);
        }}
      }} catch (err) {{
        if (entered.toLowerCase() === '{TEAM_PASSCODE}'.toLowerCase()) {{
          localStorage.setItem('ipx_staff_auth', TARGET_HASH);
          unlockUI();
        }} else {{
          if (errorBox) errorBox.style.display = 'block';
        }}
      }}
    }}

    // Check auth and URL on load
    (async function initAuth() {{
      const params = new URLSearchParams(window.location.search);
      const urlWeek = params.get('w') || params.get('week');
      if (urlWeek && SCHEDULE_DATA.weeks[urlWeek]) {{
        activeWeekId = urlWeek;
      }}

      const urlKey = params.get('pin') || params.get('key') || params.get('pass') || params.get('auth');
      if (urlKey) {{
        try {{
          const urlHash = await computeHash(urlKey);
          if (urlHash === TARGET_HASH) {{
            localStorage.setItem('ipx_staff_auth', TARGET_HASH);
            const p = new URLSearchParams(window.location.search);
            p.delete('pin'); p.delete('key'); p.delete('pass'); p.delete('auth');
            const cleanUrl = window.location.pathname + (p.toString() ? `?${{p.toString()}}` : '');
            window.history.replaceState({{}}, document.title, cleanUrl);
            unlockUI();
            return;
          }}
        }} catch (_) {{}}
      }}

      const saved = localStorage.getItem('ipx_staff_auth');
      if (saved === TARGET_HASH) {{
        unlockUI();
      }} else {{
        showLockUI();
      }}

      const hostSpan = document.getElementById('host-url-display');
      if (hostSpan && window.location.host) {{
        hostSpan.textContent = window.location.host;
      }}
    }})();

    setInterval(() => {{
      if (content.style.display !== 'none' && chartImg.getAttribute('src')) {{
        const curWeek = SCHEDULE_DATA.weeks[activeWeekId];
        if (curWeek) {{
          chartImg.src = `${{curWeek.image}}?v=${{Date.now()}}`;
        }}
      }}
    }}, 300000);
  </script>
</body>
</html>
"""

    html_path = os.path.abspath("schedule.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Web page generated: {html_path}")
    print(f"Live website URL: https://staff.ipxbk.com (or https://ipxbk.com/schedule)")
    print(f"Team Passcode: {TEAM_PASSCODE}")
    return html_path


RAW_SCHEDULE_INPUT = os.path.join(DATA_DIR, "raw_schedule.txt")
ARCHIVE_RAW_DIR = os.path.join(DATA_DIR, "raw_schedules")

RAW_SCHEDULE_TEMPLATE = """# =============================================================
# IPX Staff Schedule Input File
# =============================================================
# Paste any future schedule text or ADP table below this line.
# Then run: python schedule.py
# The script will parse the shifts, append the new week to
# data/staff_schedules.json, generate the chart, and update the website.
# =============================================================
"""


# -------------------------------------------------------------
# Main Execution / CLI Handler
# -------------------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description="IPX Staff Schedule Generator")
    parser.add_argument("--week", type=str, default="", help="Week start date (YYYY-MM-DD, e.g. 2026-10-19)")
    parser.add_argument("--input", type=str, default="", help="Path to schedule text file")
    parser.add_argument("--text", type=str, default="", help="Raw schedule text string")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser")
    args = parser.parse_args()

    # Determine input source: CLI text, CLI input file, or data/raw_schedule.txt
    raw_text = args.text
    source_is_default_input = False

    if args.input and os.path.exists(args.input):
        with open(args.input, "r", encoding="utf-8") as f:
            raw_text = f.read()
    elif not raw_text and os.path.exists(RAW_SCHEDULE_INPUT):
        with open(RAW_SCHEDULE_INPUT, "r", encoding="utf-8") as f:
            content = f.read()
        # Check if file has non-comment schedule content
        non_comment_lines = [l for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
        if non_comment_lines:
            raw_text = content
            source_is_default_input = True

    if raw_text:
        # Determine week start date
        week_start_str = args.week.strip() if args.week else ""
        if not week_start_str:
            # Check for month name in text (e.g. "Week of October 26, 2026" or "Oct 26, 2026")
            m_month = re.search(r'(?:week\s+of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(202\d))?', raw_text, re.I)
            if m_month:
                month_names = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
                m_num = month_names.index(m_month.group(1).lower()[:3]) + 1
                d_num = int(m_month.group(2))
                y_num = int(m_month.group(3)) if m_month.group(3) else datetime.date.today().year
                try:
                    dt = datetime.date(y_num, m_num, d_num)
                    week_start_str = (dt - datetime.timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
                except Exception:
                    pass

            # Check if there is an explicit date in the text (ISO or US format)
            if not week_start_str:
                m_iso = re.search(r'\b(202\d[-/]\d{1,2}[-/]\d{1,2})\b', raw_text)
                m_us = re.search(r'\b(\d{1,2})[/-](\d{1,2})[/-](202\d)\b', raw_text)
                if m_iso:
                    d_cand = m_iso.group(1).replace('/', '-')
                    try:
                        dt = datetime.datetime.strptime(d_cand, "%Y-%m-%d").date()
                        week_start_str = (dt - datetime.timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
                    except Exception:
                        pass
                elif m_us:
                    try:
                        dt = datetime.date(int(m_us.group(3)), int(m_us.group(1)), int(m_us.group(2)))
                        week_start_str = (dt - datetime.timedelta(days=dt.weekday())).strftime("%Y-%m-%d")
                    except Exception:
                        pass

        if not week_start_str:
            # Default to the next sequential week after the latest week registered
            master = load_all_weeks()
            sorted_weeks = sorted(master.get("weeks", {}).keys())
            if sorted_weeks:
                last_dt = datetime.datetime.strptime(sorted_weeks[-1], "%Y-%m-%d").date()
                week_start_str = (last_dt + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            else:
                today = datetime.date.today()
                monday = today - datetime.timedelta(days=today.weekday())
                week_start_str = monday.strftime("%Y-%m-%d")

        try:
            dt_start = datetime.datetime.strptime(week_start_str, "%Y-%m-%d").date()
        except Exception:
            dt_start = datetime.date.today()

        dt_end = dt_start + datetime.timedelta(days=6)
        label = f"{dt_start.strftime('%b %d')} - {dt_end.strftime('%b %d, %Y')}"
        title = f"Team Schedule — Week of {dt_start.strftime('%B %d, %Y')} to {dt_end.strftime('%B %d, %Y')}"

        shifts, days = parse_schedule_text(raw_text, start_date_str=week_start_str)
        print(f"Parsed {len(shifts)} shifts from text for week {week_start_str}")
        register_week(week_start_str, shifts, days, title, label)

        # Archive raw text and reset default input file
        if source_is_default_input:
            os.makedirs(ARCHIVE_RAW_DIR, exist_ok=True)
            arch_path = os.path.join(ARCHIVE_RAW_DIR, f"{week_start_str}.txt")
            with open(arch_path, "w", encoding="utf-8") as f:
                f.write(raw_text)
            with open(RAW_SCHEDULE_INPUT, "w", encoding="utf-8") as f:
                f.write(RAW_SCHEDULE_TEMPLATE)
            print(f"Raw input archived to: {arch_path}")

    else:
        # No new text input: load existing weeks from data/staff_schedules.json
        master = load_all_weeks()
        if not master.get("weeks"):
            print("No weeks found in data/staff_schedules.json.")
            print(f"To add a week, paste schedule text into: {RAW_SCHEDULE_INPUT}")
            return

        # Re-render all registered weeks with current font & styling settings
        for wId, wData in master["weeks"].items():
            w_img_path = os.path.join(SCHEDULES_DIR, f"schedule_{wId}.png")
            render_gantt_chart(
                wId,
                wData["shifts"],
                wData["days"],
                wData["title"],
                w_img_path,
                wData.get("palette", DEFAULT_PALETTE)
            )
            # Re-render root image for current week
            cur = master.get("current_week")
            if cur and cur in master["weeks"]:
                cw = master["weeks"][cur]
                render_gantt_chart(
                    cur,
                    cw["shifts"],
                    cw["days"],
                    cw["title"],
                    os.path.abspath("team_schedule_gantt.png"),
                    cw.get("palette", DEFAULT_PALETTE)
                )

    html_path = generate_schedule_html()
    if not args.no_browser:
        webbrowser.open(f"file:///{html_path}")

if __name__ == "__main__":
    main()