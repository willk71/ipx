def clean_event_title(title):
    if not title:
        return ''
    t = str(title).strip()
    t = re.sub(r'^\s*Play\s*(?:til|until|till)\s*1(?::00)?\s*am\s*[-–—|:]*\s*', '', t, flags=re.I)
    t = re.sub(r'\s*\(\s*Play\s*(?:til|until|till)\s*1(?::00)?\s*am\s*\)', '', t, flags=re.I)
    t = re.sub(r'\s*[-–—|/]\s*Play\s*(?:til|until|till)\s*1(?::00)?\s*am\b', '', t, flags=re.I)
    t = re.sub(r'\bPlay\s*(?:til|until|till)\s*1(?::00)?\s*am\b', '', t, flags=re.I)
    t = re.sub(r'\s*[-–—|/:]\s*$', '', t).strip()
    t = re.sub(r'^\s*[-–—|/:]\s*', '', t).strip()
    t = re.sub(r'\s{2,}', ' ', t).strip()
    return t

import json
import os
import re
from datetime import datetime, timezone

IGNORED_QUESTION_TERMS = [
    'emergency', 'contact', 'phone', 'zip', 'postal', 'address',
    'wellhub', 'gympass', 'waiver', 'medical', 'email', 'name', 'relationship'
]

def is_ignored_question(q_title):
    q_lower = str(q_title).lower().strip()
    return any(term in q_lower for term in IGNORED_QUESTION_TERMS)

def normalize_choice(raw_answer, q_title=''):
    if not raw_answer:
        return None
    
    clean = str(raw_answer).strip()
    lower = clean.lower()
    
    # Specific level matching for playing level questions
    if any(term in q_title.lower() for term in ['level', 'self-rate', 'self rating', 'rating', 'playing', 'skill']):
        if 'high intermediate' in lower or 'high-intermediate' in lower:
            return 'High Intermediate'
        if ('adv' in lower and 'beg' in lower) or 'advanced beginner' in lower:
            return 'Advanced Beginner'
        if 'intermediate' in lower and 'high' not in lower:
            return 'Intermediate'
        if 'advanced' in lower and 'beg' not in lower:
            return 'Advanced'
        # Drop old numeric rating strings like 3.0-3.49
        return None
        
    # Generic fallback: if choice has a colon like "Choice: description", take the title
    if ':' in clean:
        return clean.split(':', 1)[0].strip()
        
    return clean

def extract_answers_from_item(item):
    """
    Extract all question-answer pairs from a registrant object.
    Only pulls event-specific custom fields, ignoring member profile fields.
    """
    qa_list = []
    
    # Search ONLY event-specific custom field containers
    containers = [
        'UserDefinedFields', 'CustomFieldValues', 'CustomFields',
        'RegistrationQuestions', 'Questions', 'EventCustomFields',
        'Answers', 'UserDefinedFieldValues', 'CustomFieldsValues'
    ]
    
    for c_key in containers:
        container = item.get(c_key)
        if isinstance(container, list):
            for entry in container:
                if isinstance(entry, dict):
                    q = (entry.get('FieldName') or entry.get('CustomFieldName') or 
                         entry.get('UserDefinedFieldName') or entry.get('Name') or 
                         entry.get('Label') or entry.get('FieldLabel') or
                         entry.get('Question') or entry.get('QuestionName') or entry.get('Title') or '')
                    a = (entry.get('Value') or entry.get('FieldValue') or entry.get('Answer') or 
                         entry.get('SelectedValue') or entry.get('Text') or 
                         entry.get('Choice') or entry.get('Option') or entry.get('SelectedOption') or '')
                    if isinstance(a, list):
                        a = ", ".join(str(x.get('Name', x) if isinstance(x, dict) else x) for x in a)
                    elif isinstance(a, dict):
                        a = a.get('Name') or a.get('Value') or str(a)
                    if a and not is_ignored_question(q):
                        qa_list.append((str(q).strip(), str(a).strip()))
        elif isinstance(container, dict):
            for q, a in container.items():
                if isinstance(a, list):
                    a = ", ".join(str(x.get('Name', x) if isinstance(x, dict) else x) for x in a)
                elif isinstance(a, dict):
                    a = a.get('Name') or a.get('Value') or str(a)
                if a and not is_ignored_question(q):
                    qa_list.append((str(q).strip(), str(a).strip()))
                        
    return qa_list

def unpack_registrants(raw_items):
    """
    Expands raw items into a flat list of registrant dicts.
    Handles both top-level registrant items and any nested guest/partner structures
    (e.g., PartnersInfo, Guests, EventRegistrationGuests, Partners).
    """
    flat_list = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        flat_list.append(item)
        for guest_container_key in ['PartnersInfo', 'Guests', 'EventRegistrationGuests', 'Partners']:
            nested = item.get(guest_container_key)
            if isinstance(nested, list) and len(nested) > 0:
                for sub in nested:
                    if not isinstance(sub, dict):
                        continue
                    sub_copy = dict(sub)
                    for inherit_key in ['EventId', 'eventId', 'EventDateId', 'StartTime', 'startTime', 
                                        'EndTime', 'endTime', 'Courts', 'courts', 'DivisionName', 
                                        'EventName', 'title', 'IsPublic', 'IsHidden']:
                        if inherit_key not in sub_copy and inherit_key in item:
                            sub_copy[inherit_key] = item[inherit_key]
                    if 'IsGuest' not in sub_copy:
                        sub_copy['IsGuest'] = True
                    flat_list.append(sub_copy)
    return flat_list

def process_events(input_path='data/events_10d.json', output_path='data/event-choices.json', schedule_path='data/schedule.json'):
    items = []
    if os.path.exists(input_path):
        with open(input_path, 'r', encoding='utf-8') as f:
            try:
                raw_data = json.load(f)
                items = raw_data.get('Data', raw_data) if isinstance(raw_data, dict) else raw_data
                if not isinstance(items, list):
                    items = []
            except Exception as e:
                print(f"Error reading JSON from {input_path}: {e}")
                items = []
        print(f"Processing {len(items)} event registrant records from {input_path}...")
    else:
        print(f"Input file {input_path} not found. Will preserve/backfill events from schedule and previous cache.")

    items = unpack_registrants(items)

    # Group by EventId and StartTime
    # key: (eventId, startTime)
    events_by_id = {}
    seen_players_per_session = set()
    seen_player_answers = set()

    for item in items:
        # Ignore private / hidden
        if item.get('IsPublic') is False or item.get('IsHidden') is True:
            continue

        e_id = str(item.get('EventId') or item.get('eventId') or '').strip()
        if not e_id:
            continue

        raw_title = item.get('DivisionName') or item.get('EventName') or item.get('title') or 'Event'
        title = clean_event_title(raw_title)
        start_time = item.get('StartTime') or item.get('startTime') or ''
        end_time = item.get('EndTime') or item.get('endTime') or ''
        courts = item.get('Courts') or item.get('courts') or []
        court_names = []
        if isinstance(courts, list):
            for c in courts:
                name = c.get('CourtName', '') if isinstance(c, dict) else str(c)
                clean_c = re.sub(r'\s*\([^)]*\)', '', name)
                clean_c = re.sub(r'^Court\s*', '', clean_c, flags=re.I).strip()
                if clean_c and clean_c not in court_names:
                    court_names.append(clean_c)
        court_names.sort(key=lambda x: int(x) if x.isdigit() else 999)
        
        # Unique session key
        session_key = f"{e_id}_{start_time}"

        if session_key not in events_by_id:
            events_by_id[session_key] = {
                'eventId': e_id,
                'title': title,
                'startTime': start_time,
                'endTime': end_time,
                'courts': court_names,
                'totalRegistered': 0,
                'questions': {},
                'registrants': []
            }

        is_guest = bool(
            item.get('IsGuest') is True or 
            str(item.get('IsGuest')).lower() == 'true' or
            item.get('GuestName') or
            re.search(r'\b\(g\)\b|\bguest\b', str(item.get('LastName', '')), re.I) or
            re.search(r'\b\(g\)\b|\bguest\b', str(item.get('FirstName', '')), re.I) or
            re.search(r'\b\(g\)\b|\bguest\b', str(item.get('MemberName', '')), re.I)
        )

        org_id = item.get('OrganizationMemberId') or item.get('MemberId')
        email = item.get('Email') or item.get('MemberEmail')
        
        first_raw = item.get('FirstName') or item.get('MemberFirstName') or item.get('UserFirstName') or ''
        last_raw = item.get('LastName') or item.get('MemberLastName') or item.get('UserLastName') or ''
        
        guest_name_field = item.get('GuestName')
        if guest_name_field and not (first_raw or last_raw):
            g_parts = str(guest_name_field).strip().split(None, 1)
            first_raw = g_parts[0]
            last_raw = g_parts[1] if len(g_parts) > 1 else ''

        f_clean = re.sub(r'\s*\([^)]*\)', '', str(first_raw)).strip()
        l_clean = re.sub(r'\s*\([^)]*\)', '', str(last_raw)).strip()
        
        if f_clean and not l_clean and ' ' in f_clean:
            parts = f_clean.split(None, 1)
            f_clean = parts[0]
            l_clean = parts[1]

        norm_name = f"{f_clean.lower()}_{l_clean.lower()}".strip('_')
        reg_id = item.get('EventRegistrationId') or item.get('Id') or item.get('EventRegistrationGuestId')
        
        has_real_player = bool(org_id or email or norm_name or item.get('MemberName') or reg_id)
        if not has_real_player:
            continue

        if f_clean and l_clean:
            display_name = f"{f_clean.title()} {l_clean[:1].upper()}."
        elif f_clean:
            display_name = f_clean.title()
        elif item.get('MemberName'):
            m_clean = re.sub(r'\s*\([^)]*\)', '', str(item.get('MemberName'))).strip()
            parts = m_clean.split()
            if len(parts) >= 2:
                display_name = f"{parts[0].title()} {parts[1][:1].upper()}."
            else:
                display_name = parts[0].title() if parts else "Player"
        else:
            display_name = "Player"

        # Construct distinct player_id
        # Crucial: Guests must NEVER collide with host members sharing OrganizationMemberId or Email!
        if is_guest:
            if norm_name:
                player_id = f"guest_{norm_name}_{org_id or 'noorg'}"
            elif reg_id:
                player_id = f"guest_reg_{reg_id}"
            else:
                player_id = f"guest_{org_id or 'noorg'}_{id(item)}"
        else:
            if org_id:
                player_id = f"mem_{org_id}"
            elif email:
                player_id = f"mem_{email.lower()}"
            elif norm_name:
                player_id = f"mem_{norm_name}"
            else:
                player_id = f"mem_{reg_id or id(item)}"

        session_player_key = f"{session_key}_{player_id}"

        if session_player_key not in seen_players_per_session:
            seen_players_per_session.add(session_player_key)
            events_by_id[session_key]['totalRegistered'] += 1
            events_by_id[session_key]['registrants'].append(display_name)

        # Extract QA
        qa_pairs = extract_answers_from_item(item)
        for q, a in qa_pairs:
            if is_ignored_question(q):
                continue

            q_title = q if q else 'Playing Level'
            if any(term in q_title.lower() for term in ['level', 'self-rate', 'self rating', 'rating', 'playing', 'skill']):
                q_title = 'Selected Playing Levels'

            norm_a = normalize_choice(a, q_title)
            if not norm_a:
                continue

            # Ensure each player is only tallied once per question per session
            player_q_key = f"{session_key}_{player_id}_{q_title}"
            if player_q_key in seen_player_answers:
                continue
            seen_player_answers.add(player_q_key)

            if q_title not in events_by_id[session_key]['questions']:
                events_by_id[session_key]['questions'][q_title] = {
                    'question': q_title,
                    'totalResponses': 0,
                    'tallies': {},
                    'playersByChoice': {}
                }

            q_obj = events_by_id[session_key]['questions'][q_title]
            q_obj['totalResponses'] += 1
            q_obj['tallies'][norm_a] = q_obj['tallies'].get(norm_a, 0) + 1
            if norm_a not in q_obj['playersByChoice']:
                q_obj['playersByChoice'][norm_a] = []
            q_obj['playersByChoice'][norm_a].append(display_name)

    # 1. Preserve any upcoming sessions from existing output_path that weren't in events_10d
    if output_path and os.path.exists(output_path):
        try:
            with open(output_path, 'r', encoding='utf-8') as prev_f:
                prev_data = json.load(prev_f)
                now_iso = datetime.now(timezone.utc).isoformat()
                for prev_id, prev_ev in prev_data.get('events', {}).items():
                    for s in prev_ev.get('sessions', []):
                        s_time = s.get('startTime') or ''
                        e_time = s.get('endTime') or s_time
                        if e_time and e_time > now_iso:
                            s_key = f"{prev_id}_{s_time}"
                            if s_key not in events_by_id:
                                events_by_id[s_key] = {
                                    'eventId': prev_id,
                                    'title': clean_event_title(prev_ev.get('title') or 'Event'),
                                    'startTime': s_time,
                                    'endTime': s.get('endTime') or '',
                                    'courts': s.get('courts') or [],
                                    'totalRegistered': s.get('totalRegistered') or 0,
                                    'questions': {
                                        q['question']: {
                                            'question': q['question'],
                                            'totalResponses': q['totalResponses'],
                                            'tallies': {c['choice']: c['count'] for c in q.get('choices', [])},
                                            'playersByChoice': {c['choice']: c.get('players', []) for c in q.get('choices', [])}
                                        } for q in s.get('questions', [])
                                    },
                                    'registrants': s.get('registrants') or []
                                }
        except Exception as ex:
            print(f"Error preserving existing sessions from {output_path}: {ex}")

    # 2. Backfill events and registrants from schedule.json
    if schedule_path and os.path.exists(schedule_path):
        try:
            with open(schedule_path, 'r', encoding='utf-8') as sf:
                sched_data = json.load(sf)
                for e in sched_data.get('events', []):
                    raw_eid = str(e.get('eventId') or '').split('_')[0].strip()
                    if not raw_eid:
                        continue
                    s_time = e.get('startTime') or ''
                    e_time = e.get('endTime') or ''
                    s_key = f"{raw_eid}_{s_time}"
                    if s_key not in events_by_id:
                        c_list = e.get('courts') or []
                        clean_c_list = []
                        for c in c_list:
                            clean_c = re.sub(r'\s*\([^)]*\)', '', str(c))
                            clean_c = re.sub(r'^Court\s*', '', clean_c, flags=re.I).strip()
                            if clean_c and clean_c not in clean_c_list:
                                clean_c_list.append(clean_c)
                        clean_c_list.sort(key=lambda x: int(x) if x.isdigit() else 999)
                        
                        events_by_id[s_key] = {
                            'eventId': raw_eid,
                            'title': clean_event_title(e.get('title') or 'Event'),
                            'startTime': s_time,
                            'endTime': e_time,
                            'courts': clean_c_list,
                            'totalRegistered': 0,
                            'questions': {},
                            'registrants': []
                        }
                    
                    # Also backfill any player names present in schedule.json
                    p_name = str(e.get('playerName') or '').strip()
                    if p_name and s_key in events_by_id:
                        p_clean = re.sub(r'\s*\([^)]*\)', '', p_name).strip()
                        parts = p_clean.split()
                        if len(parts) >= 2:
                            norm_p = f"{parts[0].title()} {parts[1][:1].upper()}."
                        elif len(parts) == 1:
                            norm_p = parts[0].title()
                        else:
                            norm_p = p_clean
                        if norm_p and norm_p not in events_by_id[s_key]['registrants']:
                            events_by_id[s_key]['registrants'].append(norm_p)
                            events_by_id[s_key]['totalRegistered'] = max(
                                events_by_id[s_key]['totalRegistered'],
                                len(events_by_id[s_key]['registrants'])
                            )
        except Exception as ex:
            print(f"Error backfilling from {schedule_path}: {ex}")

    # Format into a clean output dictionary mapped by eventId
    # Since an eventId may have multiple occurrences across the 10 days, store a list of sessions
    result = {
        'lastUpdated': datetime.now(timezone.utc).isoformat() + 'Z',
        'events': {}
    }

    for session_key, s_data in events_by_id.items():
        e_id = s_data['eventId']
        if e_id not in result['events']:
            result['events'][e_id] = {
                'eventId': e_id,
                'title': s_data['title'],
                'sessions': []
            }
        
        # Calculate percentages for each question
        q_list = []
        for q_title, q_data in s_data['questions'].items():
            tot = q_data['totalResponses']
            tallies_with_pct = []
            players_by_choice = q_data.get('playersByChoice', {})
            
            is_level_q = any(term in q_title.lower() for term in ['level', 'self-rate', 'self rating', 'rating', 'playing', 'skill'])
            if is_level_q:
                standard_levels = ['Advanced Beginner', 'Intermediate', 'High Intermediate', 'Advanced']
                for lvl in standard_levels:
                    cnt = q_data['tallies'].get(lvl, 0)
                    pct = round((cnt / tot * 100), 1) if tot > 0 else 0
                    tallies_with_pct.append({
                        'choice': lvl,
                        'count': cnt,
                        'percentage': pct,
                        'players': sorted(players_by_choice.get(lvl, []))
                    })
            else:
                for choice, count in q_data['tallies'].items():
                    pct = round((count / tot * 100), 1) if tot > 0 else 0
                    tallies_with_pct.append({
                        'choice': choice,
                        'count': count,
                        'percentage': pct,
                        'players': sorted(players_by_choice.get(choice, []))
                    })
                tallies_with_pct.sort(key=lambda x: -x['count'])

            q_list.append({
                'question': q_title,
                'totalResponses': tot,
                'choices': tallies_with_pct
            })

        result['events'][e_id]['sessions'].append({
            'startTime': s_data['startTime'],
            'endTime': s_data['endTime'],
            'courts': s_data['courts'],
            'totalRegistered': s_data['totalRegistered'],
            'questions': q_list,
            'registrants': sorted(s_data.get('registrants', []))
        })

    # Sort sessions by startTime for each event
    for e_id in result['events']:
        result['events'][e_id]['sessions'].sort(key=lambda s: s['startTime'])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as out:
        json.dump(result, out, indent=2)

    print(f"Successfully generated {output_path} with {len(result['events'])} unique events.")

if __name__ == '__main__':
    process_events()
