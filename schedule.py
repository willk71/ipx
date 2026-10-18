import os
import webbrowser
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np

# 1. Schedule Data
data = [
    # Mon 19
    {"name": "Carlos", "day": 0, "start": 16.0, "end": 23.0, "label": "4:00 PM - 11:00 PM"},
    {"name": "Johnpaul", "day": 0, "start": 9.0, "end": 13.5, "label": "9:00 AM - 1:30 PM"},
    {"name": "Johnpaul", "day": 0, "start": 18.5, "end": 23.0, "label": "6:30 PM - 11:00 PM"},
    # Tue 20
    {"name": "Carlos", "day": 1, "start": 11.0, "end": 19.0, "label": "11:00 AM - 7:00 PM"},
    {"name": "Carl", "day": 1, "start": 13.5, "end": 23.0, "label": "1:30 PM - 11:00 PM"},
    {"name": "Kadeem", "day": 1, "start": 15.5, "end": 22.0, "label": "3:30 PM - 10:00 PM"},
    {"name": "Johnpaul", "day": 1, "start": 9.0, "end": 13.5, "label": "9:00 AM - 1:30 PM"},
    # Wed 21
    {"name": "Carl", "day": 2, "start": 13.5, "end": 23.0, "label": "1:30 PM - 11:00 PM"},
    {"name": "Nicole", "day": 2, "start": 15.5, "end": 22.0, "label": "3:30 PM - 10:00 PM"},
    {"name": "Johnpaul", "day": 2, "start": 9.0, "end": 13.5, "label": "9:00 AM - 1:30 PM"},
    # Thu 22
    {"name": "Carlos", "day": 3, "start": 14.0, "end": 22.0, "label": "2:00 PM - 10:00 PM"},
    {"name": "Kadeem", "day": 3, "start": 15.5, "end": 22.0, "label": "3:30 PM - 10:00 PM"},
    # Fri 23
    {"name": "Nicole", "day": 4, "start": 15.5, "end": 23.0, "label": "3:30 PM - 11:00 PM"},
    {"name": "Johnpaul", "day": 4, "start": 15.5, "end": 23.0, "label": "3:30 PM - 11:00 PM"},
    # Sat 24
    {"name": "Carlos", "day": 5, "start": 11.0, "end": 19.0, "label": "11:00 AM - 7:00 PM"},
    {"name": "Kadeem", "day": 5, "start": 9.0, "end": 15.5, "label": "9:00 AM - 3:30 PM"},
    # Sun 25
    {"name": "Carlos", "day": 6, "start": 9.0, "end": 15.0, "label": "9:00 AM - 3:00 PM"},
    {"name": "Nicole", "day": 6, "start": 9.0, "end": 15.5, "label": "9:00 AM - 3:30 PM"},
    {"name": "Johnpaul", "day": 6, "start": 15.0, "end": 22.5, "label": "3:00 PM - 10:30 PM"},
]

days = ["Mon 19", "Tue 20", "Wed 21", "Thu 22", "Fri 23", "Sat 24", "Sun 25"]
people = ["Carlos", "Carl", "Kadeem", "Nicole", "Johnpaul"]

# 2. Distinct color palette for each person
palette = {
    "Carlos": "#1E5F8A",
    "Carl": "#D96B27",
    "Kadeem": "#2E7D32",
    "Nicole": "#7B1FA2",
    "Johnpaul": "#C2185B",
}

# 3. Group shifts by day
day_shifts = {d: [] for d in range(7)}
for shift in data:
    day_shifts[shift["day"]].append(shift)

fig, ax = plt.subplots(figsize=(18, 12), dpi=150)
fig.patch.set_facecolor("#F8F9FA")
ax.set_facecolor("#FFFFFF")

# 4. Contrasting alternating day background columns
for day_idx in range(7):
    bg_color = "#EBF0F5" if day_idx % 2 == 1 else "#FFFFFF"
    ax.axvspan(day_idx, day_idx + 1, facecolor=bg_color, alpha=0.9, zorder=0)

# 5. Half-hour grid lines
y_half_hours = np.arange(8.0, 24.5, 0.5)
for y in y_half_hours:
    if y % 1.0 == 0:
        ax.axhline(y, color="#CBD5E1", linestyle="-", linewidth=0.8, alpha=0.8, zorder=1)
    else:
        ax.axhline(y, color="#E2E8F0", linestyle=":", linewidth=0.6, alpha=0.7, zorder=1)

# 6. Render Gantt bars (side-by-side sub-columns for concurrent shifts)
track_padding = 0.04
for day_idx, shifts in day_shifts.items():
    shifts.sort(key=lambda s: (s["start"], s["name"]))
    columns = []
    shift_col = {}
    for shift in shifts:
        placed = False
        for c_idx, col in enumerate(columns):
            if col[-1]["end"] <= shift["start"]:
                col.append(shift)
                shift_col[id(shift)] = c_idx
                placed = True
                break
        if not placed:
            shift_col[id(shift)] = len(columns)
            columns.append([shift])

    num_cols = max(len(columns), 1)
    col_width = (1.0 - 2 * track_padding) / num_cols

    for shift in shifts:
        c_idx = shift_col[id(shift)]
        x_left = day_idx + track_padding + c_idx * col_width + 0.015
        width = col_width - 0.03
        y_bottom = shift["start"]
        height = shift["end"] - shift["start"]
        color = palette[shift["name"]]

        box = patches.FancyBboxPatch(
            (x_left, y_bottom), width, height,
            boxstyle="round,pad=0.01,rounding_size=0.06",
            facecolor=color, edgecolor="#1E293B", linewidth=1.2, alpha=0.92, zorder=3
        )
        ax.add_patch(box)

        label_text = f"{shift['name']}\n{shift['label']}"
        y_center = y_bottom + (height / 2.0)
        x_center = x_left + (width / 2.0)

        # Flipped vertical orientation (rotation=90)
        ax.text(
            x_center, y_center, label_text,
            color="#FFFFFF", weight="bold", fontsize=9.5,
            rotation=90,
            ha="center", va="center", linespacing=1.2, zorder=4
        )

# 7. Left axis: half-hour increments, 8:00 AM at top to 11:30 PM at bottom
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
ax.set_yticklabels([format_half_hour(t) for t in time_ticks], fontsize=9.5, fontweight="bold", color="#334155")
ax.set_ylabel("Time of Day (Half-Hour Increments)", fontsize=12, fontweight="bold", color="#0F172A", labelpad=12)

# 8. Top axis: Days
ax.set_xlim(0, 7)
ax.xaxis.tick_top()
ax.xaxis.set_label_position("top")
ax.set_xticks([i + 0.5 for i in range(7)])
ax.set_xticklabels(days, fontsize=12.5, fontweight="bold", color="#0F172A")
ax.tick_params(axis="x", which="both", pad=12)

for x in range(8):
    ax.axvline(x, color="#94A3B8", linestyle="-", linewidth=1.2, zorder=2)

for spine in ax.spines.values():
    spine.set_edgecolor("#94A3B8")
    spine.set_linewidth(1.2)

# Title & Legend
plt.title("Team Schedule — Week of October 19, 2026 to October 25, 2026", fontsize=16, fontweight="bold", pad=25, color="#0F172A")

legend_handles = [patches.Patch(facecolor=palette[p], edgecolor="#334155", label=p, linewidth=0.8, alpha=0.95) for p in people]
ax.legend(
    handles=legend_handles, loc="lower center", bbox_to_anchor=(0.5, -0.075),
    ncol=5, frameon=True, facecolor="#FFFFFF", edgecolor="#CBD5E1",
    fontsize=10.5, title="Team Members", title_fontsize=11.5
)

plt.tight_layout()
plt.subplots_adjust(bottom=0.08, top=0.89)

output_path = os.path.abspath("team_schedule_gantt.png")
plt.savefig(output_path, dpi=150, bbox_inches="tight")
plt.close(fig)

print(f"Chart saved to: {output_path}")

# 9. Calculate stats and generate/update schedule.html for ipxbk.com/schedule
stats = {p: {"hours": 0.0, "shifts": 0} for p in people}
for s in data:
    name = s["name"]
    if name in stats:
        stats[name]["hours"] += s["end"] - s["start"]
        stats[name]["shifts"] += 1

total_hours = sum(st["hours"] for st in stats.values())
total_shifts = sum(st["shifts"] for st in stats.values())

cards_html = []
for p in people:
    c = palette.get(p, "#ffd60a")
    h = stats[p]["hours"]
    sh = stats[p]["shifts"]
    cards_html.append(f"""      <div class="stat-card">
        <div class="stat-chip" style="background-color: {c};"></div>
        <div class="stat-info">
          <span class="stat-name">{p}</span>
          <span class="stat-hours"><strong>{h:.1f}h</strong> &bull; {sh} {('shift' if sh == 1 else 'shifts')}</span>
        </div>
      </div>""")

stat_cards_rendered = "\n".join(cards_html)

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="robots" content="noindex, nofollow" />
  <title>Team Schedule &mdash; IPX</title>
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
      font-size: clamp(1.6rem, 2.2vw, 2.8rem);
      font-weight: 800;
      letter-spacing: -0.02em;
      margin: 0;
      display: flex;
      align-items: center;
      gap: 0.6vw;
      flex-wrap: wrap;
    }}

    .header-separator {{
      color: var(--theme-accent);
      opacity: 0.7;
    }}

    .header-badge {{
      background: rgba(255, 214, 10, 0.15);
      border: 1px solid rgba(255, 214, 10, 0.4);
      color: var(--theme-accent);
      font-size: clamp(0.85rem, 1.0vw, 1.2rem);
      font-weight: 700;
      padding: 0.4vh 1vw;
      border-radius: 999px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
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
      gap: 2vh;
      margin-top: 1.8vh;
    }}

    /* Stats Overview Grid */
    .stats-bar {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 1vw;
    }}

    .stat-card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.2vh 1.2vw;
      display: flex;
      align-items: center;
      gap: 1vw;
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }}

    .stat-chip {{
      width: 14px;
      height: 38px;
      border-radius: 4px;
      flex-shrink: 0;
    }}

    .stat-info {{
      display: flex;
      flex-direction: column;
      min-width: 0;
    }}

    .stat-name {{
      font-size: clamp(1rem, 1.1vw, 1.35rem);
      font-weight: 700;
      color: #ffffff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .stat-hours {{
      font-size: clamp(0.85rem, 0.95vw, 1.15rem);
      color: var(--text-muted);
      font-weight: 500;
    }}

    .stat-hours strong {{
      color: var(--theme-accent);
      font-weight: 700;
    }}

    /* Chart Container */
    .schedule-wrapper {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 1.5vh 1.5vw;
      display: flex;
      flex-direction: column;
      align-items: center;
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
      overflow: hidden;
    }}

    .schedule-img-container {{
      width: 100%;
      overflow-x: auto;
      text-align: center;
      -webkit-overflow-scrolling: touch;
    }}

    .schedule-img {{
      max-width: 100%;
      height: auto;
      display: inline-block;
      border-radius: 8px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }}

    footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: clamp(0.8rem, 0.85vw, 1.05rem);
      color: var(--text-muted);
      padding-top: 1.5vh;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      margin-top: 2vh;
      flex-wrap: wrap;
      gap: 1vh;
    }}

    .footer-left {{
      display: flex;
      align-items: center;
      gap: 0.8vw;
    }}

    @media (max-width: 768px) {{
      .schedule-img {{
        min-width: 800px;
      }}
    }}
  </style>
</head>
<body class="page-schedule theme-apple">
  <header>
    <div class="header-left">
      <h1 id="header-title">
        <span>Welcome to IPX!</span>
        <span class="header-separator">&ndash;</span>
        <span>Team Schedule</span>
      </h1>
      <span class="header-badge">Oct 19 &ndash; Oct 25, 2026</span>
    </div>

    <div class="header-actions">
      <a href="team_schedule_gantt.png" target="_blank" class="btn-action" title="View Full Resolution">
        <span>&#x2922;</span> Full Size
      </a>
      <a href="team_schedule_gantt.png" download="IPX_Team_Schedule_Oct19-25.png" class="btn-action" title="Download Image">
        <span>&#x21E9;</span> Download
      </a>
      <a href="/" class="btn-action" title="Back to Court Sessions">
        <span>&#x2190;</span> Sessions
      </a>
    </div>
  </header>

  <main class="main-content">
    <section class="stats-bar">
{stat_cards_rendered}
      <div class="stat-card" style="border-color: rgba(255, 214, 10, 0.35); background: rgba(255, 214, 10, 0.05);">
        <div class="stat-chip" style="background-color: var(--theme-accent);"></div>
        <div class="stat-info">
          <span class="stat-name" style="color: var(--theme-accent);">Total Team</span>
          <span class="stat-hours"><strong style="color: #ffffff;">{total_hours:.1f}h</strong> &bull; {total_shifts} shifts</span>
        </div>
      </div>
    </section>

    <section class="schedule-wrapper">
      <div class="schedule-img-container">
        <img
          id="schedule-chart"
          src="team_schedule_gantt.png"
          alt="IPX Team Staff Schedule — Week of Oct 19 to Oct 25, 2026"
          class="schedule-img"
        />
      </div>
    </section>
  </main>

  <footer>
    <div class="footer-left">
      <span>IPX Court Schedule System</span>
      <span>&bull;</span>
      <span id="sync-indicator">Auto-refreshed</span>
    </div>
    <div class="footer-right">
      <span>ipxbk.com/schedule</span>
    </div>
  </footer>

  <script>
    const chartImg = document.getElementById('schedule-chart');
    if (chartImg) {{
      chartImg.src = `team_schedule_gantt.png?v=${{Date.now()}}`;
    }}

    setInterval(() => {{
      if (chartImg) {{
        chartImg.src = `team_schedule_gantt.png?v=${{Date.now()}}`;
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
print(f"Live website URL: https://ipxbk.com/schedule")

# Open local web page in browser
webbrowser.open(f"file:///{html_path}")