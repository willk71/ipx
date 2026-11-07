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
import urllib.request
import urllib.error

# Preferred physical court clusters for IPX facility layout:
# - Advanced Beginner preferred: Courts 3 & 6 (pool)
# - Intermediate preferred: Courts 4, 5, 7 (centered around 7, like 4, 5, 7)
# - High Intermediate preferred: Courts 10, 12 (back pod), then 11, 8, 9, 7
# - Advanced preferred: Courts 10, 11, 12, 8, 9
PREFERRED_PODS = {
    'Advanced Beginner': ['3', '6', '2', '1', '9'],
    'Intermediate': ['4', '5', '7', '8', '2', '1'],
    'High Intermediate': ['10', '12', '11', '8', '9', '7'],
    'Advanced': ['10', '11', '12', '8', '9', '7']
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

def load_court_rules():
    rules_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'court_rules.json')
    if not os.path.exists(rules_path):
        rules_path = 'data/court_rules.json'
    if os.path.exists(rules_path):
        try:
            with open(rules_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Notice: Failed to load {rules_path}: {e}")
    return []

def allocate_courts(levels, courts_list, event_title='', start_time=''):
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

    clean_set = set(clean_courts)
    has_1_4_7_8_10_12 = {'1', '4', '7', '8', '10', '12'}.issubset(clean_set)

    adv_count = (levels or {}).get('Advanced', 0)
    high_int_count = (levels or {}).get('High Intermediate', 0)
    adv_merged = 0 < adv_count <= 4 and high_int_count > 0

    adv_beg_count = (levels or {}).get('Advanced Beginner', 0)
    int_count = (levels or {}).get('Intermediate', 0)
    # In any group that includes 1, 4, 7, 8, 10, 12: force Court 1 as AdvBeg+ even if short on players (< 4).
    adv_beg_merged = (not has_1_4_7_8_10_12) and (0 < adv_beg_count < 4 and int_count > 0)

    effective_counts = dict(levels or {})
    if adv_merged:
        effective_counts['High Intermediate'] = effective_counts.get('High Intermediate', 0) + adv_count
        effective_counts['Advanced'] = 0
    if adv_beg_merged:
        effective_counts['Intermediate'] = effective_counts.get('Intermediate', 0) + adv_beg_count
        effective_counts['Advanced Beginner'] = 0

    standard_order = ['Advanced Beginner', 'Intermediate', 'High Intermediate', 'Advanced']
    active_levels = [lvl for lvl in standard_order if effective_counts.get(lvl, 0) > 0]
    total_effective = sum(effective_counts[lvl] for lvl in active_levels)

    # 0. Custom rules from data/court_rules.json
    rules = load_court_rules()
    for rule in rules:
        rule_courts = set(clean_court_num(c) for c in rule.get('courts', []))
        if rule_courts and rule_courts == clean_set:
            match_title = rule.get('match', '')
            match_time = rule.get('startTime', '')
            if match_title and not re.search(match_title, event_title or '', re.I):
                continue
            if match_time and match_time not in (start_time or ''):
                continue

            assigned_courts = {}
            for lvl, clist in rule.get('allocations', {}).items():
                assigned_courts[lvl] = sorted([clean_court_num(c) for c in clist], key=lambda x: int(x) if x.isdigit() else 999)

            if adv_merged and 'High Intermediate' in assigned_courts:
                assigned_courts['Advanced'] = assigned_courts['High Intermediate']
            if adv_beg_merged and 'Intermediate' in assigned_courts:
                assigned_courts['Advanced Beginner'] = assigned_courts['Intermediate']
            return assigned_courts

    # 7-Court Facility Pod Layout: Courts 1, 2, 3, 4, 5, 6, 9
    # - High Intermediate: Courts 1, 2, 5 (Bay 1 + Court 5 combo)
    # - Advanced: Court 4 (Bay 2)
    # - Intermediate: Court 3 (Bay 3 front)
    # - Advanced Beginner: Courts 6, 9 (Bay 3 back + Court 9)
    if clean_set == {'1', '2', '3', '4', '5', '6', '9'}:
        assigned_courts = {
            'Advanced Beginner': ['6', '9'],
            'Intermediate': ['3'],
            'High Intermediate': ['1', '2', '5'],
            'Advanced': ['4']
        }
        if adv_merged and 'High Intermediate' in assigned_courts:
            assigned_courts['Advanced'] = assigned_courts['High Intermediate']
        if adv_beg_merged and 'Intermediate' in assigned_courts:
            assigned_courts['Advanced Beginner'] = assigned_courts['Intermediate']
        return assigned_courts

    # Default allocation if no player choices are present and courts include 1, 4, 7, 8, 10, 12
    if total_effective == 0:
        if has_1_4_7_8_10_12:
            return {
                'Advanced Beginner': ['1'],
                'Intermediate': ['4', '7', '8'],
                'High Intermediate': ['10', '11', '12'] if '11' in clean_set else ['10', '12'],
                'Advanced': ['10', '11', '12'] if '11' in clean_set else ['10', '12']
            }
        return {}

    # Daytime 1, 4, 7, 8, 10, 12 setup rule:
    # Always force Court 1 as AdvBeg+ (even if short on players),
    # Courts 4, 7, 8 for Intermediate / Intermediate+,
    # and Courts 10, 12 (+11) for High Intermediate / High Intermediate+.
    if has_1_4_7_8_10_12:
        assigned_courts = {
            'Advanced Beginner': ['1'],
            'Intermediate': ['4', '7', '8'],
            'High Intermediate': ['10', '12']
        }

        if '5' in clean_set:
            assigned_courts['Intermediate'].append('5')
            assigned_courts['Intermediate'].sort(key=lambda x: int(x) if x.isdigit() else 999)

        if '11' in clean_set:
            assigned_courts['High Intermediate'].append('11')
            assigned_courts['High Intermediate'].sort(key=lambda x: int(x) if x.isdigit() else 999)

        if 'Advanced' in active_levels:
            if not adv_merged and 'High Intermediate' in active_levels:
                assigned_courts['High Intermediate'] = [c for c in assigned_courts['High Intermediate'] if c != '12']
                assigned_courts['Advanced'] = ['12']
            else:
                assigned_courts['Advanced'] = list(assigned_courts['High Intermediate'])
        elif adv_merged:
            assigned_courts['Advanced'] = list(assigned_courts['High Intermediate'])

        # Distribute any unassigned extra courts (e.g. 2, 3, 6, 9)
        assigned_flat = set()
        for clist in assigned_courts.values():
            assigned_flat.update(clist)
        unassigned = [c for c in clean_courts if c not in assigned_flat]
        for extra in unassigned:
            if extra in ['2', '3', '9'] and effective_counts.get('Advanced Beginner', 0) > len(assigned_courts['Advanced Beginner']) * 4:
                assigned_courts['Advanced Beginner'].append(extra)
            elif extra in ['5', '2'] and effective_counts.get('Intermediate', 0) > len(assigned_courts['Intermediate']) * 4:
                assigned_courts['Intermediate'].append(extra)
            elif extra == '6':
                # NEVER give Court 6 to AdvBeg since AdvBeg has Court 1!
                if 'Intermediate' in assigned_courts and '1' not in assigned_courts['Intermediate']:
                    assigned_courts['Intermediate'].append('6')
                else:
                    assigned_courts['High Intermediate'].append('6')
            else:
                assigned_courts['High Intermediate'].append(extra)

        for lvl in assigned_courts:
            assigned_courts[lvl] = sorted(list(set(assigned_courts[lvl])), key=lambda x: int(x) if x.isdigit() else 999)

        return assigned_courts

    # Evening 3, 4, 5, 6, 7, 8, 10 setup rule:
    # High Intermediate on 7, 8, 10, 11 (6, 7, 8, 10 is NEVER allowed)
    # Intermediate on 4, 5
    # Advanced Beginner on 3, 6
    has_3_4_5_6_7_8_10 = {'3', '4', '5', '6', '7', '8', '10'}.issubset(clean_set)
    if has_3_4_5_6_7_8_10:
        assigned_courts = {
            'Advanced Beginner': ['3', '6'],
            'Intermediate': ['4', '5'],
            'High Intermediate': ['7', '8', '10', '11'],
            'Advanced': ['7', '8', '10', '11']
        }

        # Distribute any unassigned extra courts (e.g. 1, 2, 9, 12)
        assigned_flat = set()
        for clist in assigned_courts.values():
            assigned_flat.update(clist)
        unassigned = [c for c in clean_courts if c not in assigned_flat]
        for extra in unassigned:
            if extra in ['1', '2'] and effective_counts.get('Intermediate', 0) > len(assigned_courts['Intermediate']) * 4:
                assigned_courts['Intermediate'].append(extra)
            elif extra in ['9', '12'] and effective_counts.get('High Intermediate', 0) > len(assigned_courts['High Intermediate']) * 4:
                assigned_courts['High Intermediate'].append(extra)
            elif extra == '2' and '1' not in assigned_courts['Advanced Beginner']:
                assigned_courts['Advanced Beginner'].append('2')
            elif extra == '1':
                # NEVER give Court 1 to Advanced Beginner because AdvBeg has Court 6!
                assigned_courts['Intermediate'].append('1')
            else:
                assigned_courts['High Intermediate'].append(extra)

        for lvl in assigned_courts:
            assigned_courts[lvl] = sorted(list(set(assigned_courts[lvl])), key=lambda x: int(x) if x.isdigit() else 999)

        return assigned_courts

    # Hamilton-Hare apportionment
    quotas = {lvl: (effective_counts[lvl] / total_effective) * total_courts for lvl in active_levels}
    floors = {lvl: int(quotas[lvl]) for lvl in active_levels}
    remainders = sorted([(quotas[lvl] - floors[lvl], lvl) for lvl in active_levels], reverse=True)

    unallocated = total_courts - sum(floors.values())
    for i in range(unallocated):
        floors[remainders[i][1]] += 1

    # Pod-aware court allocation
    remaining_courts = list(clean_courts)
    assigned_courts = {}

    level_priority = ['Advanced Beginner', 'Intermediate', 'High Intermediate', 'Advanced']
    active_order = [lvl for lvl in level_priority if floors.get(lvl, 0) > 0]
    for lvl in floors:
        if floors.get(lvl, 0) > 0 and lvl not in active_order:
            active_order.append(lvl)

    for lvl in active_order:
        needed = floors[lvl]
        lvl_courts = []
        rem_set = set(remaining_courts)

        # Level-specific preferred pods:
        # Advanced Beginner:
        # 1. Bay 3 pair: 3 & 6 ("try to put 3&6 together")
        # 2. Bay 1 pair: 1 & 2
        if lvl == 'Advanced Beginner':
            if needed >= 2 and {'3', '6'}.issubset(rem_set):
                lvl_courts.extend(['3', '6'])
                for c in ['3', '6']: remaining_courts.remove(c)
            elif needed >= 2 and {'1', '2'}.issubset(rem_set):
                lvl_courts.extend(['1', '2'])
                for c in ['1', '2']: remaining_courts.remove(c)
            elif needed == 1:
                if '1' in remaining_courts:
                    lvl_courts.append('1')
                    remaining_courts.remove('1')
                elif '2' in remaining_courts and '6' in remaining_courts:
                    # Prefer 2 so 3 & 6 can remain together for a 2-court tier
                    lvl_courts.append('2')
                    remaining_courts.remove('2')
                elif '3' in remaining_courts:
                    lvl_courts.append('3')
                    remaining_courts.remove('3')
                elif '2' in remaining_courts:
                    lvl_courts.append('2')
                    remaining_courts.remove('2')

        # Intermediate:
        # 1. 1, 2, 5 trio ("1,2,5 is another preferred combo")
        # 2. 4 & 5 pair ("4&5 together is good")
        # 3. 3 & 6 pair (if available and not taken)
        # 4. 1 & 2 pair
        elif lvl == 'Intermediate':
            if needed >= 3 and {'1', '2', '5'}.issubset(rem_set):
                lvl_courts.extend(['1', '2', '5'])
                for c in ['1', '2', '5']: remaining_courts.remove(c)
            elif needed >= 2 and {'4', '5'}.issubset(rem_set):
                lvl_courts.extend(['4', '5'])
                for c in ['4', '5']: remaining_courts.remove(c)
            elif needed >= 2 and {'3', '6'}.issubset(rem_set):
                lvl_courts.extend(['3', '6'])
                for c in ['3', '6']: remaining_courts.remove(c)
            elif needed >= 2 and {'1', '2'}.issubset(rem_set):
                lvl_courts.extend(['1', '2'])
                for c in ['1', '2']: remaining_courts.remove(c)
            elif needed >= 2 and {'7', '8'}.issubset(rem_set):
                lvl_courts.extend(['7', '8'])
                for c in ['7', '8']: remaining_courts.remove(c)

        # High Intermediate / Advanced:
        # 1. 7, 8, 10, 11 (back pod)
        # 2. 10, 11, 12 (back pod trio)
        # 3. 10, 12 or 10, 11 or 7, 8 (back pod pairs)
        elif lvl in ['High Intermediate', 'Advanced']:
            if needed >= 4 and {'7', '8', '10', '11'}.issubset(rem_set):
                lvl_courts.extend(['7', '8', '10', '11'])
                for c in ['7', '8', '10', '11']: remaining_courts.remove(c)
            elif needed >= 3 and {'10', '11', '12'}.issubset(rem_set):
                lvl_courts.extend(['10', '11', '12'])
                for c in ['10', '11', '12']: remaining_courts.remove(c)
            elif needed >= 2:
                if {'10', '12'}.issubset(rem_set):
                    lvl_courts.extend(['10', '12'])
                    for c in ['10', '12']: remaining_courts.remove(c)
                elif {'10', '11'}.issubset(rem_set):
                    lvl_courts.extend(['10', '11'])
                    for c in ['10', '11']: remaining_courts.remove(c)
                elif {'7', '8'}.issubset(rem_set):
                    lvl_courts.extend(['7', '8'])
                    for c in ['7', '8']: remaining_courts.remove(c)

        # Fill any remainder from preferred list (with hard 1 & 6 disallowance)
        pref_list = PREFERRED_PODS.get(lvl, [])
        for c in pref_list:
            if c in remaining_courts and len(lvl_courts) < needed:
                # Definitely NOT 1 & 6 in the same group!
                if (c == '6' and '1' in lvl_courts) or (c == '1' and '6' in lvl_courts):
                    continue
                lvl_courts.append(c)
                remaining_courts.remove(c)

        # Fill remaining slots from any available court (still obeying definitely not 1 & 6)
        i = 0
        while len(lvl_courts) < needed and i < len(remaining_courts):
            c = remaining_courts[i]
            if (c == '6' and '1' in lvl_courts) or (c == '1' and '6' in lvl_courts):
                i += 1
                continue
            lvl_courts.append(remaining_courts.pop(i))

        # If still short (only conflicting court remained), take whatever is left; post-processor will swap
        while len(lvl_courts) < needed and remaining_courts:
            lvl_courts.append(remaining_courts.pop(0))

        lvl_courts.sort(key=lambda x: int(x) if x.isdigit() else 999)
        assigned_courts[lvl] = lvl_courts

    # Universal IPX rule 1: "definitely not 1&6"
    # Court 1 and Court 6 are at opposite ends of the facility. Break any 1&6 pairing by swapping.
    for lvl, clist in list(assigned_courts.items()):
        if '1' in clist and '6' in clist:
            swapped = False
            # Priority A: swap '6' to another group that has '3' so 3 & 6 are together
            for other_lvl, other_clist in assigned_courts.items():
                if other_lvl != lvl and '3' in other_clist and '1' not in other_clist:
                    cand_courts = [c for c in other_clist if c != '3']
                    if cand_courts:
                        take_c = cand_courts[0]
                        clist.remove('6')
                        clist.append(take_c)
                        other_clist.remove(take_c)
                        other_clist.append('6')
                        swapped = True
                        break
            # Priority B: swap '6' with any other group not containing '1'
            if not swapped:
                for other_lvl, other_clist in assigned_courts.items():
                    if other_lvl != lvl and '1' not in other_clist:
                        cands = sorted(other_clist, key=lambda c: (0 if c == '2' else 1 if c in ['4', '5'] else 2))
                        if cands:
                            take_c = cands[0]
                            clist.remove('6')
                            clist.append(take_c)
                            other_clist.remove(take_c)
                            other_clist.append('6')
                            swapped = True
                            break
            # Priority C: swap '1' with any other group not containing '6'
            if not swapped:
                for other_lvl, other_clist in assigned_courts.items():
                    if other_lvl != lvl and '6' not in other_clist:
                        cands = sorted(other_clist, key=lambda c: (0 if c == '2' else 1 if c in ['4', '5'] else 2))
                        if cands:
                            take_c = cands[0]
                            clist.remove('1')
                            clist.append(take_c)
                            other_clist.remove(take_c)
                            other_clist.append('1')
                            swapped = True
                            break

    # Universal IPX rule 2: "try to put 3&6 together"
    # If Court 3 and Court 6 are separated across different groups, unite them if valid.
    lvl_3 = next((lvl for lvl, cl in assigned_courts.items() if '3' in cl), None)
    lvl_6 = next((lvl for lvl, cl in assigned_courts.items() if '6' in cl), None)
    if lvl_3 and lvl_6 and lvl_3 != lvl_6:
        c3_list = assigned_courts[lvl_3]
        c6_list = assigned_courts[lvl_6]
        if '1' not in c3_list and len(c3_list) >= 2:
            cands = [c for c in c3_list if c != '3' and not (c == '1' and '6' in c6_list)]
            if cands:
                take_c = cands[0]
                c6_list.remove('6')
                c6_list.append(take_c)
                c3_list.remove(take_c)
                c3_list.append('6')
        elif '1' not in c6_list and len(c6_list) >= 2:
            cands = [c for c in c6_list if c != '6']
            if cands:
                take_c = cands[0]
                c3_list.remove('3')
                c3_list.append(take_c)
                c6_list.remove(take_c)
                c6_list.append('3')

    # Universal IPX rule 3: 6, 7, 8, 10 group should NEVER be allowed!
    # Court 6 is in front pod and must never be grouped with back pod 7, 8, 10.
    for lvl, clist in list(assigned_courts.items()):
        c_set = set(clist)
        if {'6', '7', '8', '10'}.issubset(c_set) or ('6' in c_set and '10' in c_set and ('7' in c_set or '8' in c_set)):
            clist.remove('6')
            if '11' not in clist:
                clist.append('11')
            if 'Advanced Beginner' in assigned_courts and '1' not in assigned_courts['Advanced Beginner'] and '6' not in assigned_courts['Advanced Beginner']:
                assigned_courts['Advanced Beginner'].append('6')
            elif 'Intermediate' in assigned_courts and '1' not in assigned_courts['Intermediate'] and '6' not in assigned_courts['Intermediate']:
                assigned_courts['Intermediate'].append('6')
            assigned_courts[lvl] = sorted(list(set(clist)), key=lambda x: int(x) if x.isdigit() else 999)

    for lvl in assigned_courts:
        assigned_courts[lvl] = sorted(list(set(assigned_courts[lvl])), key=lambda x: int(x) if x.isdigit() else 999)

    # Link merged tiers to their receiving group's courts
    if adv_merged and 'High Intermediate' in assigned_courts:
        assigned_courts['Advanced'] = assigned_courts['High Intermediate']
    if adv_beg_merged and 'Intermediate' in assigned_courts:
        assigned_courts['Advanced Beginner'] = assigned_courts['Intermediate']

    return assigned_courts

def fetch_cached_choices():
    account_id = os.environ.get("CF_ACCOUNT_ID", "").strip()
    namespace_id = os.environ.get("CF_KV_NAMESPACE_ID", "").strip()
    api_token = os.environ.get("CF_API_TOKEN", "").strip()
    if account_id and namespace_id and api_token:
        try:
            url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/event_choices_latest"
            req = urllib.request.Request(
                url,
                method="GET",
                headers={
                    "Authorization": f"Bearer {api_token}",
                    "User-Agent": "IPX-Splitter"
                }
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    data = resp.read()
                    print(f"Direct KV GET: successfully retrieved event_choices_latest ({len(data)} bytes).")
                    return data
        except Exception as e:
            print(f"Notice: Direct KV fetch for event_choices_latest failed: {e}")

    # Fallback to worker API
    try:
        url = "https://ipx-sync-pinger.willkang71.workers.dev/api/event-choices"
        req = urllib.request.Request(url, headers={'User-Agent': 'IPX-Splitter'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                data = resp.read()
                print(f"Worker GET: successfully retrieved event-choices fallback ({len(data)} bytes).")
                return data
    except Exception as e:
        print(f"Notice: Worker fallback fetch for event-choices failed: {e}")

    return None

def process_schedule(schedule_path='data/schedule.json', choices_path='data/event-choices.json'):
    if not os.path.exists(schedule_path):
        return

    # If event-choices.json was not freshly generated on this run (e.g. data/.choices_fresh does not exist),
    # fetch the latest cached version directly from Cloudflare KV using authenticated CF API or worker fallback.
    fresh_marker = os.path.join(os.path.dirname(choices_path) or '.', '.choices_fresh')
    needs_fetch = not os.path.exists(choices_path) or not os.path.exists(fresh_marker)

    if needs_fetch:
        raw_choices = fetch_cached_choices()
        if raw_choices:
            try:
                os.makedirs(os.path.dirname(choices_path) or '.', exist_ok=True)
                with open(choices_path, 'wb') as f:
                    f.write(raw_choices)
                print("Fetched latest event-choices from Cloudflare KV for splitting.")
            except Exception as e:
                print(f"Notice: Could not write cached event choices from KV: {e}")

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

            court_alloc = allocate_courts(level_counts, clean_courts, event_title=e_info.get('title', ''), start_time=start_time)
            if not court_alloc:
                continue

            # Attach unified courtAllocations directly to choices session for 100% parity across all screens
            session['courtAllocations'] = court_alloc

            # Ensure session courts list includes all allocated courts (e.g. Court 11)
            all_allocated_nums = set()
            for clist in court_alloc.values():
                all_allocated_nums.update(clist)
            existing_clean = [clean_court_num(c) for c in session.get('courts', [])]
            for num in sorted(all_allocated_nums, key=lambda x: int(x) if x.isdigit() else 999):
                if num not in existing_clean:
                    session['courts'].append(num)
            session['courts'] = sorted(list(dict.fromkeys(session['courts'])), key=lambda x: int(clean_court_num(x)) if clean_court_num(x).isdigit() else 999)

            # Map players to active sub-session group
            # If Adv merges into High Int, Adv players map to High Int group
            adv_count = level_counts.get('Advanced', 0)
            high_int_count = level_counts.get('High Intermediate', 0)
            adv_merged = 0 < adv_count <= 4 and high_int_count > 0

            adv_beg_count = level_counts.get('Advanced Beginner', 0)
            int_count = level_counts.get('Intermediate', 0)
            # In 1, 4, 7, 8, 10, 12 layout, force Court 1 as AdvBeg+ even if short on players (< 4).
            clean_set_sess = set(clean_courts)
            has_1_4_7_8_10_12_sess = {'1', '4', '7', '8', '10', '12'}.issubset(clean_set_sess)
            adv_beg_merged = (not has_1_4_7_8_10_12_sess) and (0 < adv_beg_count < 4 and int_count > 0)

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
