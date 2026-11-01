import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

def fetch_remote_kv_value(account_id, namespace_id, api_token, key_name):
    """
    Fetch the currently stored value in Cloudflare KV via direct API.
    Falls back to the edge worker API if direct API fails.
    """
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{key_name}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {api_token}",
            "User-Agent": "IPX-KV-Uploader"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        print(f"Warning: KV direct GET for {key_name} returned HTTP {e.code}")
    except Exception as e:
        print(f"Warning: KV direct GET for {key_name} failed: {e}")

    # Fallback to worker edge endpoint
    fallback_map = {
        "schedule_latest": "https://ipx-sync-pinger.willkang71.workers.dev/api/schedule",
        "event_choices_latest": "https://ipx-sync-pinger.willkang71.workers.dev/api/event-choices"
    }
    fallback_url = fallback_map.get(key_name)
    if fallback_url:
        try:
            req_fb = urllib.request.Request(fallback_url, headers={"User-Agent": "IPX-KV-Uploader"})
            with urllib.request.urlopen(req_fb, timeout=10) as resp_fb:
                return resp_fb.read().decode("utf-8")
        except Exception as e_fb:
            print(f"Warning: Worker fallback GET for {key_name} failed: {e_fb}")

    return None

def parse_iso_age_minutes(iso_str):
    if not iso_str:
        return None
    try:
        clean = str(iso_str).strip()
        if clean.endswith("Z"):
            clean = clean[:-1]
        if not ("+" in clean or clean.endswith("-00:00")):
            clean += "+00:00"
        dt = datetime.fromisoformat(clean)
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() / 60.0
    except Exception as ex:
        print(f"Warning: could not parse timestamp '{iso_str}': {ex}")
        return None

def is_content_identical(local_obj, remote_obj):
    """
    Compare two JSON objects ignoring the top-level 'lastUpdated' timestamp.
    """
    if type(local_obj) != type(remote_obj):
        return False
    if isinstance(local_obj, dict):
        local_clean = {k: v for k, v in local_obj.items() if k != "lastUpdated"}
        remote_clean = {k: v for k, v in remote_obj.items() if k != "lastUpdated"}
        return local_clean == remote_clean
    return local_obj == remote_obj

def upload_key(account_id, namespace_id, api_token, key_name, file_path, heartbeat_minutes=20, force=False):
    if not os.path.exists(file_path):
        print(f"Skipping {key_name}: file {file_path} not found.")
        return False

    with open(file_path, "r", encoding="utf-8") as f:
        local_raw = f.read()

    try:
        local_obj = json.loads(local_raw)
    except Exception as e:
        print(f"Error reading JSON from {file_path}: {e}")
        return False

    if not force:
        # Check remote KV to see if content is unchanged
        remote_raw = fetch_remote_kv_value(account_id, namespace_id, api_token, key_name)
        if remote_raw:
            try:
                remote_obj = json.loads(remote_raw)
                if is_content_identical(local_obj, remote_obj):
                    age_m = parse_iso_age_minutes(remote_obj.get("lastUpdated"))
                    if age_m is not None and age_m < heartbeat_minutes:
                        print(f"KV Skip: {key_name} content is unchanged (synced {age_m:.1f}m ago < {heartbeat_minutes}m threshold). Preserving KV write quota.")
                        return True
                    else:
                        age_str = f"{age_m:.1f}m ago" if age_m is not None else "unknown age"
                        print(f"KV Heartbeat: {key_name} content unchanged, but last sync was {age_str} (>= {heartbeat_minutes}m). Refreshing timestamp.")
                else:
                    print(f"KV Change: Detected live update in {key_name}. Uploading to KV immediately.")
            except Exception as e:
                print(f"Warning: Failed to parse remote KV value as JSON: {e}. Proceeding with upload.")
        else:
            print(f"KV Initial: No existing remote value found for {key_name}. Uploading.")
    else:
        print(f"KV Force: Force upload requested for {key_name}.")

    # Execute KV PUT
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{key_name}"
    file_bytes = local_raw.encode("utf-8")

    req = urllib.request.Request(
        url,
        data=file_bytes,
        method="PUT",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "User-Agent": "IPX-KV-Uploader"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp_body = resp.read().decode("utf-8")
            data = json.loads(resp_body)
            if data.get("success"):
                print(f"Successfully uploaded {key_name} ({len(file_bytes)} bytes) to Cloudflare KV.")
                return True
            else:
                print(f"Failed to upload {key_name}: {data.get('errors')}")
                return False
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8", errors="replace")
        print(f"HTTP Error {e.code} uploading {key_name}: {err_content}")
        return False
    except Exception as e:
        print(f"Error uploading {key_name}: {e}")
        return False

def main():
    account_id = os.environ.get("CF_ACCOUNT_ID", "").strip()
    namespace_id = os.environ.get("CF_KV_NAMESPACE_ID", "").strip()
    api_token = os.environ.get("CF_API_TOKEN", "").strip()
    force_upload = os.environ.get("FORCE_CHOICES", "").strip().lower() in ("true", "1", "yes")

    if not (account_id and namespace_id and api_token):
        print("Cloudflare KV credentials (CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID, CF_API_TOKEN) not set. Skipping KV upload.")
        return

    print("Checking and uploading latest schedule data to Cloudflare KV...")
    upload_key(account_id, namespace_id, api_token, "schedule_latest", "data/schedule.json", heartbeat_minutes=20, force=force_upload)

    # Only upload event_choices to KV if freshly generated on this run
    if os.path.exists("data/.choices_fresh") and os.path.exists("data/event-choices.json"):
        upload_key(account_id, namespace_id, api_token, "event_choices_latest", "data/event-choices.json", heartbeat_minutes=30, force=force_upload)

if __name__ == "__main__":
    main()
