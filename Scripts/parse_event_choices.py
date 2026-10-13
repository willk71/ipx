import json
import os
import re
from datetime import datetime

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
    if any(term in q_title.lower() for term in ['level', 'self-rate', 'playing']):
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
        'RegistrationQuestions', 'Questions', 'EventCustomFields'
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
                         entry.get('Choice') or entry.get('Option') or '')
                    if a and not is_ignored_question(q):
                        qa_list.append((str(q).strip(), str(a).strip()))
        elif isinstance(container, dict):
            for q, a in container.items():
                if a and not is_ignored_question(q):
                    qa_list.append((str(q).strip(), str(a).strip()))
                        
    return qa_list

def process_events(input_path='data/events_10d.json', output_path='data/event-choices.json'):
    if not os.path.exists(input_path):
        print(f"Input file {input_path} not found.")
        return
        
    with open(input_path, 'r', encoding='utf-8') as f:
        try:
            raw_data = json.load(f)
        except Exception as e:
            print(f"Error reading JSON from {input_path}: {e}")
            return

    items = raw_data.get('Data', raw_data) if isinstance(raw_data, dict) else raw_data
    if not isinstance(items, list):
        items = []

    print(f"Processing {len(items)} event registrant records from {input_path}...")

    # PII-Free Diagnostic logging for target event 2160558
    target_558 = [it for it in items if str(it.get('EventId') or it.get('eventId') or '') == '2160558']
    if target_558:
        print(f"=== [NO-PII] DIAGNOSTIC for Event 2160558: {len(target_558)} registrants found ===")
        for idx, it in enumerate(target_558):
            udf = it.get('UserDefinedFields')
            mudf = it.get('MemberUserDefinedFields')
            qa = extract_answers_from_item(it)
            print(f"  Reg #{idx+1}: UDF={udf} | MUDF={mudf} | Extracted QA={qa}")

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

        title = item.get('DivisionName') or item.get('EventName') or item.get('title') or 'Event'
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

        org_id = item.get('OrganizationMemberId') or item.get('MemberId')
        email = item.get('Email') or item.get('MemberEmail')
        first_raw = item.get('FirstName') or item.get('MemberFirstName') or item.get('UserFirstName') or ''
        last_raw = item.get('LastName') or item.get('MemberLastName') or item.get('UserLastName') or ''
        name = f"{first_raw}_{last_raw}".strip('_')
        reg_id = item.get('EventRegistrationId') or item.get('Id')
        player_id = str(org_id or email or name or reg_id or id(item)).strip()
        session_player_key = f"{session_key}_{player_id}"

        # Format registrant label: First Name Last Init (e.g., "John D.")
        f_clean = str(first_raw).strip()
        l_clean = str(last_raw).strip()
        if f_clean and l_clean:
            display_name = f"{f_clean.title()} {l_clean[:1].upper()}."
        elif f_clean:
            display_name = f_clean.title()
        elif item.get('MemberName'):
            parts = str(item.get('MemberName')).strip().split()
            if len(parts) >= 2:
                display_name = f"{parts[0].title()} {parts[1][:1].upper()}."
            else:
                display_name = parts[0].title() if parts else "Player"
        else:
            display_name = "Player"

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
            if any(term in q_title.lower() for term in ['level', 'playing level', 'self-rate']):
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

    # Format into a clean output dictionary mapped by eventId
    # Since an eventId may have multiple occurrences across the 10 days, store a list of sessions
    result = {
        'lastUpdated': datetime.utcnow().isoformat() + 'Z',
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
            
            is_level_q = any(term in q_title.lower() for term in ['level', 'playing level', 'self-rate'])
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

