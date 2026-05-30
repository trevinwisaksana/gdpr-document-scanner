import os
import time
import requests

# 1. Load configuration from environment variables
# On Cloud Run, mount MICROSOFT_CLIENT_SECRET from Secret Manager
TENANT_ID = os.environ.get("MICROSOFT_TENANT_ID")
CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID")
CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET")

# Global variables to cache the token in-memory across warm Cloud Run invocations
_cached_token = None
_token_expires_at = 0

def get_access_token():
    global _cached_token, _token_expires_at

    if _cached_token and time.time() < (_token_expires_at - 300):
        return _cached_token

    print("Cached token expired or missing. Fetching a new one from Microsoft...")

    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default"
    }

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()

    token_data = response.json()

    _cached_token = token_data["access_token"]
    _token_expires_at = time.time() + token_data["expires_in"]

    return _cached_token


def list_user_files(target_user_email):
    token = get_access_token()

    url = f"https://graph.microsoft.com/v1.0/users/{target_user_email}/drive/root/children"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json().get("value", [])


def upload_file_to_onedrive(target_user_email, dest_file_path, file_content):
    token = get_access_token()

    url = f"https://graph.microsoft.com/v1.0/users/{target_user_email}/drive/root:/{dest_file_path}:/content"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain"
    }

    response = requests.put(url, headers=headers, data=file_content)
    response.raise_for_status()

    print(f"Successfully uploaded {dest_file_path}!")
    return response.json()


if __name__ == "__main__":
    TARGET_USER = "employee@yourcompany.com"

    try:
        print(f"Files in {TARGET_USER}'s OneDrive root:")
        files = list_user_files(TARGET_USER)
        for f in files:
            print(f"- {f['name']} ({f['size']} bytes)")

    except requests.exceptions.HTTPError as err:
        print(f"HTTP Error occurred: {err}")
        print(f"Response Body: {err.response.text}")
