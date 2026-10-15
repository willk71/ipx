import os
import re
import json
import urllib.request
import urllib.error
import base64

def discover():
    auth = os.environ.get('AUTH_HEADER', '')
    if not auth:
        user = os.environ.get('CR_USER', '')
        password = os.environ.get('CR_PASS', '')
        if user and password:
            auth = 'Basic ' + base64.b64encode(f"{user}:{password}".encode()).decode()

    if not auth:
        print("No auth credentials found.")
        return

    headers = {
        'Authorization': auth,
        'Accept': 'application/json'
    }

    results = {
        'help_links': [],
        'event_endpoints': [],
        'endpoint_details': {},
        'test_calls': {}
    }

    # 1. Fetch /help
    try:
        req = urllib.request.Request('https://api.courtreserve.com/help', headers={'Authorization': auth, 'Accept': 'text/html'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            links = sorted(list(set(re.findall(r'href="(/Help/Api/[^"]+)"', html, re.I))))
            results['help_links'] = links
            print(f"Discovered {len(links)} Help API links.")
            
            # Find all links mentioning event or reservation
            event_links = [l for l in links if 'event' in l.lower()]
            results['event_endpoints'] = event_links
            print(f"Event-related endpoints: {event_links}")

            # Fetch documentation for each event link
            for el in event_links:
                try:
                    h_req = urllib.request.Request(f"https://api.courtreserve.com{el}", headers={'Authorization': auth, 'Accept': 'text/html'})
                    with urllib.request.urlopen(h_req, timeout=10) as h_resp:
                        h_html = h_resp.read().decode('utf-8', errors='ignore')
                        # Extract table text or parameter text
                        params = re.findall(r'<td>\s*([a-zA-Z0-9_\.]+)\s*</td>', h_html)
                        results['endpoint_details'][el] = params
                except Exception as ex:
                    results['endpoint_details'][el] = str(ex)

    except Exception as e:
        print(f"Failed to fetch /help: {e}")
        results['help_error'] = str(e)

    # 2. Test candidate endpoints for listing all events
    test_urls = [
        'https://api.courtreserve.com/api/v1/eventreport/listactive',
        'https://api.courtreserve.com/api/v1/events',
        'https://api.courtreserve.com/api/v1/event',
        'https://api.courtreserve.com/Events',
    ]
    for el in results.get('event_endpoints', []):
        match = re.search(r'GET-([a-zA-Z0-9-]+)', el)
        if match:
            path = match.group(1).replace('-', '/')
            test_urls.append(f"https://api.courtreserve.com/{path}")

    test_urls = list(dict.fromkeys(test_urls))

    for url in test_urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                sample = resp.read(500).decode('utf-8', errors='ignore')
                results['test_calls'][url] = {'status': status, 'sample': sample[:200]}
                print(f"SUCCESS {url} -> {status}")
        except urllib.error.HTTPError as e:
            results['test_calls'][url] = {'status': e.code, 'error': str(e.read(200))}
            print(f"HTTPError {url} -> {e.code}")
        except Exception as e:
            results['test_calls'][url] = {'error': str(e)}
            print(f"Error {url} -> {e}")

    os.makedirs('data', exist_ok=True)
    with open('data/cr_api_discovery.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("Saved results to data/cr_api_discovery.json")

if __name__ == '__main__':
    discover()
