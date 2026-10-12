import json
import os
import re
from datetime import datetime

def normalize_choice(raw_answer):
    if not raw_answer:
        return 'Unspecified'
    
    clean = str(raw_answer).strip()
    lower = clean.lower()
    
    # Specific level matching for Afternoon Open Play & similar sessions
    if 'high intermediate' in lower or 'high-intermediate' in lower:
        return 'High Intermediate'
    if ('adv' in lower and 'beg' in lower) or 'advanced beginner' in lower:
        return 'Advanced Beginner'
    if 'intermediate' in lower:
        return 'Intermediate'
    if 'advanced' in lower:
        return 'Advanced'
        
    # Generic fallback: if choice has a colon like "Choice: description", take the title
    if ':' in clean:
        return clean.split(':', 1)[0].strip()
        
    return clean

def extract_answers_from_item(item):
    """
    Extract all question-answer pairs from a registrant object.
    CourtReserve may store questions under various container keys.
    """
    qa_list = []
    
    # 1. Search known array containers
    containers = [
        'CustomFieldValues', 'CustomFields', 'RegistrationQuestions',
        'Questions', 'MemberUserDefinedFields', 'UserDefinedFields',
        'Answers', 'EventCustomFields', 'RegistrantCustomFields'
    ]
    
    for c_key in containers:
        container = item.get(c_key)
        if isinstance(container, list):
            for entry in container:
                if isinstance(entry, dict):
                    q = (entry.get('FieldName') or entry.get('CustomFieldName') or 
                         entry.get('Name') or entry.get('Label') or entry.get('FieldLabel') or
                         entry.get('Question') or entry.get('QuestionName') or entry.get('Title') or '')
                    a = (entry.get('Value') or entry.get('FieldValue') or entry.get('Answer') or 
                         entry.get('SelectedValue') or entry.get('Text') or 
                         entry.get('Choice') or entry.get('Option') or '')
                    if a:
                        qa_list.append((str(q).strip(), str(a).strip()))
        elif isinstance(container, dict):
            for q, a in container.items():
                if a:
                    qa_list.append((str(q).strip(), str(a).strip()))
                        
    # 2. Search direct keys on item (in case CourtReserve flattens fields)
    for k, v in item.items():
        if isinstance(v, (str, int, float)) and v:
            k_lower = k.lower()
            if any(term in k_lower for term in ['self-rate', 'playinglevel', 'playing_level', 'levelchoice', 'customchoice', 'question', 'answer']):
                qa_list.append((k, str(v).strip()))
                
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

    # Group by EventId and StartTime
    # key: (eventId, startTime)
    events_by_id = {}

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
                'questions': {}
            }

        events_by_id[session_key]['totalRegistered'] += 1

        # Extract QA
        qa_pairs = extract_answers_from_item(item)
        for q, a in qa_pairs:
            q_title = q if q else 'Playing Level'
            # Check question similarity or default
            if any(term in q_title.lower() for term in ['level', 'playing level', 'self-rate']):
                q_title = 'Self-Rated Playing Level'

            if q_title not in events_by_id[session_key]['questions']:
                events_by_id[session_key]['questions'][q_title] = {
                    'question': q_title,
                    'totalResponses': 0,
                    'tallies': {}
                }

            q_obj = events_by_id[session_key]['questions'][q_title]
            norm_a = normalize_choice(a)

            q_obj['totalResponses'] += 1
            q_obj['tallies'][norm_a] = q_obj['tallies'].get(norm_a, 0) + 1

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
            for choice, count in q_data['tallies'].items():
                pct = round((count / tot * 100), 1) if tot > 0 else 0
                tallies_with_pct.append({
                    'choice': choice,
                    'count': count,
                    'percentage': pct
                })
            
            # Sort tallies: standard skill order if present, otherwise by count descending
            level_order = {'Advanced Beginner': 1, 'Intermediate': 2, 'High Intermediate': 3, 'Advanced': 4}
            tallies_with_pct.sort(key=lambda x: (level_order.get(x['choice'], 99), -x['count']))

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
            'questions': q_list
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

