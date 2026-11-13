#!/usr/bin/env python3
"""
Extract Event & Reservation Guests from CourtReserve Data.
Filters active event registrations and court reservations for guests,
associating them with their session, host member, and check-in status.
Output: data/event-guests.json
"""

import os
import sys
import json
import re
from datetime import datetime, timezone

def clean_name(str_val):
    if not str_val:
        return ''
    s = str(str_val).strip()
    s = re.sub(r'^["]+|["]+$', '', s)
    s = re.sub(r'\s*\([^)]*\)', '', s)
    s = re.sub(r'\s*\[[^\]]*\]', '', s)
    if ',' in s:
        parts = [p.strip() for p in s.split(',', 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            s = f"{parts[1]} {parts[0]}"
    s = re.sub(r'\b[A-Za-z]\.\s+', '', s)
    s = re.sub(r'\b(Jr\.?|Sr\.?|III|II|IV)\b', '', s, flags=re.I)
    return re.sub(r'\s+', ' ', s).strip()

def is_guest_record(item):
    if not isinstance(item, dict):
        return False
    if item.get('IsGuest') is True or str(item.get('IsGuest', '')).strip().lower() == 'true':
        return True
    if item.get('GuestName'):
        return True
    member_type = str(item.get('MemberType') or item.get('MembershipType') or '').lower()
    if 'guest' in member_type:
        return True
    first = str(item.get('FirstName') or item.get('MemberFirstName') or '')
    last = str(item.get('LastName') or item.get('MemberLastName') or '')
    full = str(item.get('MemberName') or item.get('Name') or '')
    pattern = r'\b\(g\)\b|\bguest\b'
    if re.search(pattern, first, re.I) or re.search(pattern, last, re.I) or re.search(pattern, full, re.I):
        return True
    return False

def extract_guests(events_path='data/events.json', reservations_path='data/reservations.json', checkins_path='data/checkins.json', output_path='data/event-guests.json'):
    guests = []
    sessions_map = {}

    # 1. Process Event Registrations
    if os.path.exists(events_path):
        try:
            with open(events_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
                items = raw.get('Data', raw) if isinstance(raw, dict) else raw
                if not isinstance(items, list):
                    items = []
        except Exception as e:
            print(f"Error reading {events_path}: {e}")
            items = []

        print(f"Loaded {len(items)} raw event registration records.")

        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get('IsPublic') is False or item.get('IsHidden') is True:
                continue

            event_id = str(item.get('EventId') or item.get('eventId') or '').strip()
            title = str(item.get('DivisionName') or item.get('EventName') or item.get('title') or 'Event').strip()
            start_time = str(item.get('StartTime') or item.get('startTime') or '').strip()
            end_time = str(item.get('EndTime') or item.get('endTime') or '').strip()

            host_first = str(item.get('FirstName') or item.get('MemberFirstName') or '').strip()
            host_last = str(item.get('LastName') or item.get('MemberLastName') or '').strip()
            host_name = clean_name(f"{host_first} {host_last}".strip()) or clean_name(str(item.get('MemberName', '')))

            # A. Check top-level item if it's a guest registration
            if is_guest_record(item):
                g_name = clean_name(str(item.get('GuestName') or f"{host_first} {host_last}".strip() or item.get('MemberName', '')))
                g_email = str(item.get('Email') or item.get('MemberEmail') or '').strip().lower()
                g_phone = str(item.get('Phone') or item.get('CellPhone') or '').strip()
                if g_name or g_email:
                    guests.append({
                        'name': g_name or 'Unnamed Guest',
                        'email': g_email,
                        'phone': g_phone,
                        'eventId': event_id,
                        'eventTitle': title,
                        'startTime': start_time,
                        'endTime': end_time,
                        'hostName': host_name if host_name != g_name else 'Direct Guest Registration',
                        'checkedIn': bool(item.get('CheckedIn') or item.get('CheckInStatusName') == 'Checked-in'),
                        'source': 'Event Registration'
                    })

            # B. Check nested guest arrays (PartnersInfo, Guests, EventRegistrationGuests, Partners)
            for container in ['Guests', 'PartnersInfo', 'EventRegistrationGuests', 'Partners']:
                nested = item.get(container)
                if isinstance(nested, list) and len(nested) > 0:
                    for sub in nested:
                        if not isinstance(sub, dict):
                            continue
                        sub_is_guest = is_guest_record(sub) or (container == 'Guests') or (container == 'EventRegistrationGuests')
                        if sub_is_guest:
                            sub_first = str(sub.get('FirstName') or sub.get('MemberFirstName') or '').strip()
                            sub_last = str(sub.get('LastName') or sub.get('MemberLastName') or '').strip()
                            sub_name = clean_name(str(sub.get('GuestName') or f"{sub_first} {sub_last}".strip() or sub.get('MemberName', '')))
                            sub_email = str(sub.get('Email') or sub.get('MemberEmail') or '').strip().lower()
                            sub_phone = str(sub.get('Phone') or sub.get('CellPhone') or '').strip()
                            if sub_name or sub_email:
                                guests.append({
                                    'name': sub_name or 'Unnamed Guest',
                                    'email': sub_email,
                                    'phone': sub_phone,
                                    'eventId': event_id,
                                    'eventTitle': title,
                                    'startTime': start_time,
                                    'endTime': end_time,
                                    'hostName': host_name or 'Registered Member',
                                    'checkedIn': bool(sub.get('CheckedIn') or sub.get('CheckInStatusName') == 'Checked-in'),
                                    'source': 'Event Guest'
                                })

    # 2. Process Court Reservations for Guests
    if os.path.exists(reservations_path):
        try:
            with open(reservations_path, 'r', encoding='utf-8') as f:
                raw_res = json.load(f)
                res_items = raw_res.get('Data', raw_res) if isinstance(raw_res, dict) else raw_res
                if not isinstance(res_items, list):
                    res_items = []
        except Exception as e:
            print(f"Error reading {reservations_path}: {e}")
            res_items = []

        print(f"Loaded {len(res_items)} court reservation records.")

        for res in res_items:
            if not isinstance(res, dict):
                continue
            r_court = str(res.get('Courts') or res.get('CourtName') or 'Court').strip()
            r_start = str(res.get('StartTime') or '').strip()
            r_end = str(res.get('EndTime') or '').strip()
            r_host = clean_name(str(res.get('MemberName') or res.get('ReservedBy') or f"{res.get('MemberFirstName', '')} {res.get('MemberLastName', '')}"))

            # Check Players array for guests
            players = res.get('Players') or []
            if isinstance(players, list):
                for p in players:
                    if not isinstance(p, dict):
                        continue
                    if is_guest_record(p):
                        p_first = str(p.get('FirstName') or p.get('MemberFirstName') or '').strip()
                        p_last = str(p.get('LastName') or p.get('MemberLastName') or '').strip()
                        p_name = clean_name(str(p.get('GuestName') or f"{p_first} {p_last}".strip() or p.get('MemberName', '')))
                        p_email = str(p.get('Email') or '').strip().lower()
                        p_phone = str(p.get('Phone') or '').strip()
                        if p_name or p_email:
                            guests.append({
                                'name': p_name or 'Unnamed Guest',
                                'email': p_email,
                                'phone': p_phone,
                                'eventId': f"res_{res.get('ReservationId', '')}",
                                'eventTitle': f"Reservation ({r_court})",
                                'startTime': r_start,
                                'endTime': r_end,
                                'hostName': r_host or 'Reservation Host',
                                'checkedIn': bool(p.get('CheckedIn')),
                                'source': 'Court Reservation'
                            })

    # Deduplicate guests per session (same name and email in same session)
    unique_guests = []
    seen_keys = set()
    for g in guests:
        dedup_key = (g['name'].lower(), g['email'], g['startTime'])
        if dedup_key not in seen_keys:
            seen_keys.add(dedup_key)
            unique_guests.append(g)

    # Sort guests by startTime then name
    unique_guests.sort(key=lambda x: (x.get('startTime', ''), x.get('name', '')))

    # Build unique session summaries for dropdown filtering
    for g in unique_guests:
        s_key = (g.get('eventId', ''), g.get('startTime', ''))
        if s_key not in sessions_map:
            sessions_map[s_key] = {
                'eventId': g.get('eventId'),
                'title': g.get('eventTitle'),
                'startTime': g.get('startTime'),
                'endTime': g.get('endTime'),
                'guestCount': 0
            }
        sessions_map[s_key]['guestCount'] += 1

    sessions_list = sorted(list(sessions_map.values()), key=lambda x: x.get('startTime', ''))

    output_data = {
        'lastUpdated': datetime.now(timezone.utc).isoformat(),
        'totalGuests': len(unique_guests),
        'sessions': sessions_list,
        'guests': unique_guests
    }

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as out:
        json.dump(output_data, out, indent=2)

    print(f"Extracted {len(unique_guests)} guests across {len(sessions_list)} sessions into {output_path}.")
    return output_data

if __name__ == '__main__':
    extract_guests()
