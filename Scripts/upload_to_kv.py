import os
import sys
import json
import urllib.request
import urllib.error

def upload_key(account_id, namespace_id, api_token, key_name, file_path):
    if not os.path.exists(file_path):
        print(f"Skipping {key_name}: file {file_path} not found.")
        return False

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/storage/kv/namespaces/{namespace_id}/values/{key_name}"

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

    if not (account_id and namespace_id and api_token):
        print("Cloudflare KV credentials (CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID, CF_API_TOKEN) not set. Skipping KV upload.")
        return

    print("Uploading latest schedule data to Cloudflare KV...")
    upload_key(account_id, namespace_id, api_token, "schedule_latest", "data/schedule.json")
    # Only upload event_choices to KV if freshly generated on this run
    if os.path.exists("data/.choices_fresh") and os.path.exists("data/event-choices.json"):
        upload_key(account_id, namespace_id, api_token, "event_choices_latest", "data/event-choices.json")

if __name__ == "__main__":
    main()
