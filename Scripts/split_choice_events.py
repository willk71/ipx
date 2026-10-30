def clean_event_title(title):
    if not title:
        return ''
    t = str(title).strip()
    t = re.sub(r'^\s*Play\s*(?:til|until|till)\s*1(?::00)?\s*am\s*[-–—|:]*\s*', '', t, flags=re.I)
    t = re.sub(r'\s*\(\s*Play\s*(?:til|until|till)\s*1(?::00)?\s*am\s*\)', '', t, flags=re.I)
    t = re.sub(r'\s*[-–—|/]\s*Play\s*(?:til|until|till)\s*1(?::00)?\s*am\b', '', t, flags=re.I)
    t = re.sub(r'\bPlay\s*(?:til|until|till)\s*1(?::00)?\s*am\b', '', t, flags=re.I)
    t = re.sub(r'[\s\-–—|/:]+$', '', t).strip()
    t = re.sub(r'^[\s\-–—|/:]+', '', t).strip()
    t = re.sub(r'\s{2,}', ' ', t).strip()
    return t

import json
import os
import re

# Preferred physical court clusters for IPX facility layout:
# - Intermediate preferred: Courts 3 & 6 (physically paired)
# - High Intermediate preferred: Courts 4, 5, 7, 8 (contiguous quad pod)
# - Advanced Beginner preferred: Courts 1 & 2
# - Advanced preferred: Courts 8, 7, 10, 11, 12, 13
PREFERRED_PODS = {
    'Intermediate': ['3', '6', '1', '2', '9'],
    'High Intermediate': ['4', '5', '7', '8', '10', '11', '12'],
    'Advanced': ['8', '7', '10', '11', '12', '4', '5'],
    'Advanced Beginner': ['1', '2', '3', '6', '9']
}


def clean_court_num(c_name):
    clean = re.sub(r'\s*\([^)]*\)', '', str(c_name))
    clean = re.sub(r'^Court\s*', '', clean, flags=re.I).strip()
    return clean

def is_court_excluded_from_allocation(c_name):
    if not c_name:
        return True
    clean = clean_court_num(c_name).lower()
    return clean == '13' or 'event space' in clean

def normalize_player_name(raw_name):
    if not raw_name:
        return ''
    # Normalize: e.g. "Will K." or "Will K" -> "will k"
    name = str(raw_name).strip().lower()
    name = re.sub(r'\s*\([^)]*\)', '', name)
    name = re.sub(r'\.', '', name)
    return re.sub(r'\s+', ' ', name)

def allocate_courts(levels, courts_list):
    """
    Allocates courts proportionally across playing levels using Hamilton-Hare apportionment.
    Merges Advanced <= 4 into High Intermediate, and Adv Beg < 4 into Intermediate.
    Excludes Court 13 and Event Space from assignment calculations.
    Returns: dict of level_name -> list_of_court_numbers
    """
    clean_courts = [clean_court_num(c) for c in courts_list if clean_court_num(c) and not is_court_excluded_from_allocation(c)]
    total_courts = len(clean_courts)
    if total_courts == 0:
        return {}

    adv_count = levels.get('Advanced', 0)
    high_int_count = levels.get('High Intermediate', 0)
    adv_merged = 0 < adv_count <= 4 and high_int_count > 0

    adv_beg_count = levels.get('Advanced Beginner', 0)
    int_count = levels.get('Intermediate', 0)
    adv_beg_merged = 0 < adv_beg_count < 4 and int_count > 0

    effective_counts = dict(levels)
    if adv_merged:
        effective_counts['High Intermediate'] = effective_counts.get('High Intermediate', 0) + adv_count
        effective_counts['Advanced'] = 0
    if adv_beg_merged:
        effective_counts['Intermediate'] = effective_counts.get('Intermediate', 0) + adv_beg_count
        effective_counts['Advanced Beginner'] = 0

    standard_order = ['Advanced Beginner', 'Intermediate', 'High Intermediate', 'Advanced']
    active_levels = [lvl for lvl in standard_order if effective_counts.get(lvl, 0) > 0]
    total_effective = sum(effective_counts[lvl] for lvl in active_levels)
    if total_effective == 0:
        return {}

    # Fixed IPX Facility Pod Setup:
    # When 6-court Open Play uses courts 3, 4, 5, 6, 7, 8:
    # Always keep physical pods together:
    # - Intermediate: Courts 3 and 6 (2-court pod)
    # - High Intermediate: Courts 4, 5, 7, 8 (4-court pod)
    clean_set = set(clean_courts)
    if clean_set == {'3', '4', '5', '6', '7', '8'} and 'Intermediate' in active_levels and 'High Intermediate' in active_levels:
        assigned_courts = {
            'Intermediate': ['3', '6'],
            'High Intermediate': ['4', '5', '7', '8']
        }
        if adv_merged and 'High Intermediate' in assigned_courts:
            assigned_courts['Advanced'] = assigned_courts['High Intermediate']
        elif 'Advanced' in active_levels:
            # If Advanced has its own full court, place on Court 8 within the 4,5,7,8 pod
            assigned_courts['High Intermediate'] = ['4', '5', '7']
            assigned_courts['Advanced'] = ['8']
        if adv_beg_merged and 'Intermediate' in assigned_courts:
            assigned_courts['Advanced Beginner'] = assigned_courts['Intermediate']
        return assigned_courts

    # Hamilton-Hare apportionment
    quotas = {lvl: (effective_counts[lvl] / total_effective) * total_courts for lvl in active_levels}
    floors = {lvl: int(quotas[lvl]) for lvl in active_levels}
    remainders = sorted([(quotas[lvl] - floors[lvl], lvl) for lvl in active_levels], reverse=True)

    unallocated = total_courts - sum(floors.values())
    for i in range(unallocated):
        floors[remainders[i][1]] += 1

    # Assign courts respecting IPX physical pods (Intermediate: 3 & 6; High Intermediate: 4, 5, 7, 8)
    remaining_courts = list(clean_courts)
    assigned_courts = {}

    level_priority = ['Intermediate', 'High Intermediate', 'Advanced Beginner', 'Advanced']
    active_order = [lvl for lvl in level_priority if floors.get(lvl, 0) > 0]
    for lvl in floors:
        if floors.get(lvl, 0) > 0 and lvl not in active_order:
            active_order.append(lvl)

    for lvl in active_order:
        needed = floors[lvl]
        pref_list = PREFERRED_PODS.get(lvl, [])
        lvl_courts = []

        # 1. Take available courts matching preferred list
        for c in pref_list:
            if c in remaining_courts and len(lvl_courts) < needed:
                lvl_courts.append(c)
                remaining_courts.remove(c)

        # 2. Fill any remainder from remaining available courts
        while len(lvl_courts) < needed and remaining_courts:
            lvl_courts.append(remaining_courts.pop(0))

        lvl_courts.sort(key=lambda x: int(x) if x.isdigit() else 999)
        assigned_courts[lvl] = lvl_courts

    # Link merged tiers to their receiving group's courts
    if adv_merged and 'High Intermediate' in assigned_courts:
        assigned_courts['Advanced'] = assigned_courts['High Intermediate']
    if adv_beg_merged and 'Intermediate' in assigned_courts:
        assigned_courts['Advanced Beginner'] = assigned_courts['Intermediate']

    return assigned_courts

def process_schedule(schedule_path='data/schedule.json', choices_path='data/event-choices.json'):
    if not os.path.exists(schedule_path):
        return

    # If event-choices.json was not freshly generated on this run, fetch latest cached from Cloudflare KV
    if not os.path.exists(choices_path):
        try:
            import urllib.request
            url = "https://ipx-sync-pinger.willkang71.workers.dev/api/event-choices"
            req = urllib.request.Request(url, headers={'User-Agent': 'IPX-Splitter'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    with open(choices_path, 'wb') as f:
                        f.write(resp.read())
                    print("Fetched latest event-choices from Cloudflare KV for splitting.")
        except Exception as e:
            print(f"Notice: Could not fetch cached event choices from KV: {e}")

    if not os.path.exists(choices_path):
        return

    try:
        with open(schedule_path, 'r', encoding='utf-8') as f:
            schedule = json.load(f)
        with open(choices_path, 'r', encoding='utf-8') as f:
            choices = json.load(f)
    except Exception as e:
        print(f"Error loading files for splitting: {e}")
        return

    events_choice_data = choices.get('events', {})
    if not events_choice_data:
        return

    # Build split plan per (eventId, startTime)
    # split_plan[(e_id, start_time)] = {
    #     'active_groups': ['Intermediate', 'High Intermediate'],
    #     'court_map': {'Intermediate': ['1', '4', '7'], 'High Intermediate': ['8', '10', '12']},
    #     'player_to_group': {'will k': 'High Intermediate', ...},
    #     'default_group': 'Intermediate'
    # }
    split_plans = {}

    for e_id, e_info in events_choice_data.items():
        for session in e_info.get('sessions', []):
            start_time = session.get('startTime')
            if not start_time:
                continue

            # Look for a level question
            level_q = None
            for q in session.get('questions', []):
                q_text = str(q.get('question', '')).lower()
                if any(term in q_text for term in ['level', 'self-rate', 'playing']):
                    level_q = q
                    break

            if not level_q or not level_q.get('choices'):
                continue

            # Build counts & player lookups
            level_counts = {}
            player_to_choice = {}

            for c in level_q.get('choices', []):
                lvl = c.get('choice')
                cnt = c.get('count', 0)
                level_counts[lvl] = cnt
                for p in c.get('players', []):
                    player_to_choice[normalize_player_name(p)] = lvl

            # Only split if there is more than 1 choice with players
            non_zero_choices = [lvl for lvl, cnt in level_counts.items() if cnt > 0]
            if len(non_zero_choices) < 2:
                continue

            # Clean and sort available courts
            raw_courts = session.get('courts', [])
            clean_courts = sorted(list(dict.fromkeys([clean_court_num(c) for c in raw_courts if clean_court_num(c) and not is_court_excluded_from_allocation(c)])),
                                  key=lambda x: int(x) if x.isdigit() else 999)

            if len(clean_courts) < 2:
                continue

            court_alloc = allocate_courts(level_counts, clean_courts)
            if not court_alloc:
                continue

            # Attach unified courtAllocations directly to choices session for 100% parity across all screens
            session['courtAllocations'] = court_alloc

            # Map players to active sub-session group
            # If Adv merges into High Int, Adv players map to High Int group
            adv_count = level_counts.get('Advanced', 0)
            high_int_count = level_counts.get('High Intermediate', 0)
            adv_merged = 0 < adv_count <= 4 and high_int_count > 0

            adv_beg_count = level_counts.get('Advanced Beginner', 0)
            int_count = level_counts.get('Intermediate', 0)
            adv_beg_merged = 0 < adv_beg_count < 4 and int_count > 0

            group_for_level = {}
            for lvl in ['Advanced Beginner', 'Intermediate', 'High Intermediate', 'Advanced']:
                if lvl == 'Advanced' and adv_merged:
                    group_for_level[lvl] = 'High Intermediate'
                elif lvl == 'Advanced Beginner' and adv_beg_merged:
                    group_for_level[lvl] = 'Intermediate'
                else:
                    group_for_level[lvl] = lvl

            player_to_group = {}
            for p_norm, lvl in player_to_choice.items():
                player_to_group[p_norm] = group_for_level.get(lvl, lvl)

            # Determine default group for unassigned players (the group with fewer players per court)
            active_groups = sorted(list(court_alloc.keys()), key=lambda g: len(court_alloc[g]))
            default_group = 'Intermediate' if 'Intermediate' in court_alloc else (active_groups[0] if active_groups else 'Default')

            split_plans[(str(e_id).strip(), start_time.strip())] = {
                'court_alloc': court_alloc,
                'player_to_group': player_to_group,
                'group_for_level': group_for_level,
                'default_group': default_group
            }

    if not split_plans:
        return

    # Transform events in schedule.json
    new_events = []
    modified_count = 0

    group_slugs = {
        'Advanced Beginner': 'advbeg',
        'Intermediate': 'int',
        'High Intermediate': 'highint',
        'Advanced': 'adv'
    }

    for item in schedule.get('events', []):
        title = item.get('title', '')
        courts = item.get('courts', [])
        if re.search(r'\b(hosts?|guests?)\b', str(title), re.I) or any(re.search(r'\b(hosts?|guests?)\b', str(c), re.I) for c in courts):
            continue

        raw_id = str(item.get('eventId', '')).strip()
        base_id = re.sub(r'_[a-z0-9]+$', '', raw_id)
        start_time = str(item.get('startTime', '')).strip()
        plan_key = (base_id, start_time)

        if plan_key not in split_plans:
            item_copy = dict(item)
            item_copy['title'] = clean_event_title(item.get('title', ''))
            new_events.append(item_copy)
            continue

        plan = split_plans[plan_key]
        court_alloc = plan['court_alloc']
        player_to_group = plan['player_to_group']
        default_group = plan['default_group']

        p_name = normalize_player_name(item.get('playerName', ''))
        assigned_group = player_to_group.get(p_name, default_group)

        # Fallback if assigned_group has no courts
        if assigned_group not in court_alloc:
            valid_groups = [g for g in court_alloc if court_alloc[g]]
            assigned_group = valid_groups[0] if valid_groups else assigned_group

        assigned_court_nums = set(court_alloc.get(assigned_group, []))

        # Build courts for this sub-session matching assigned courts
        orig_courts = item.get('courts', [])
        new_courts = []
        found_nums = set()
        for c in orig_courts:
            c_num = clean_court_num(c)
            if c_num in assigned_court_nums and c_num not in found_nums:
                new_courts.append(c)
                found_nums.add(c_num)
        for num in sorted(assigned_court_nums, key=lambda x: int(x) if x.isdigit() else 999):
            if num not in found_nums:
                new_courts.append(f"Court {num}")
        new_courts.sort(key=lambda x: int(clean_court_num(x)) if clean_court_num(x).isdigit() else 999)

        slug = group_slugs.get(assigned_group, 'group')
        orig_title = clean_event_title(item.get('title', 'Event'))
        base_title = re.sub(r'\s*[-–—]\s*(Intermediate|High Intermediate|Advanced|Adv Beg).*', '', orig_title, flags=re.I).strip()
        base_title = re.sub(r'^[\s\-–—|/:]+', '', base_title).strip()
        base_title = re.sub(r'[\s\-–—|/:]+$', '', base_title).strip()
        if base_title:
            new_title = f"{base_title} - {assigned_group}"
        else:
            new_title = assigned_group

        new_item = dict(item)
        new_item['eventId'] = f"{base_id}_{slug}"
        new_item['title'] = new_title
        new_item['courts'] = new_courts
        new_events.append(new_item)
        modified_count += 1

    schedule['events'] = new_events

    with open(schedule_path, 'w', encoding='utf-8') as out:
        json.dump(schedule, out, indent=2)

    try:
        with open(choices_path, 'w', encoding='utf-8') as out_c:
            json.dump(choices, out_c, indent=2)
        print(f"Updated {choices_path} with unified courtAllocations.")
    except Exception as e:
        print(f"Notice: Could not write courtAllocations to {choices_path}: {e}")

    print(f"Successfully split choice events: updated {modified_count} registrant records in {schedule_path}.")

if __name__ == '__main__':
    process_schedule()
