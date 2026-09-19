import requests
import csv
import time
import webbrowser
import configparser

APP_NAME = "simklExporter"
APP_VERSION = "1.0"
USER_AGENT = f"{APP_NAME}/{APP_VERSION}"
BASE_URL = "https://api.simkl.com"

DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


def api_request(method, path, client_id, headers=None, data=None):
    """Call a SIMKL endpoint, always attaching client_id/app-name/app-version
    and a descriptive User-Agent, as required by the current API."""
    url = f"{BASE_URL}{path}"
    params = {
        "client_id": client_id,
        "app-name": APP_NAME,
        "app-version": APP_VERSION,
    }
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)

    response = requests.request(method, url, params=params, headers=req_headers, data=data)

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if not response.ok:
        message = payload.get("error_description") or payload.get("message") or payload.get("error") or payload
        raise RuntimeError(f"SIMKL API request failed ({response.status_code}) for {method} {url}: {message}")

    return payload


def make_csv(data):
    with open('./simklData.csv', 'w', newline='') as myfile:
        wr = csv.writer(myfile)
        wr.writerow(['tmdbID', 'imdbID', 'WatchedDate'])
        for movie in data:
            row = [movie['tmdb'], movie['imdb'], movie['WatchedDate']]
            wr.writerow(row)


def map_data(data):
    ids = data['movie']['ids']
    return {
        'tmdb': ids.get('tmdb', ''),
        'imdb': ids.get('imdb', ''),
        'WatchedDate': data['last_watched_at'].split('T')[0] if data['last_watched_at'] else '',
    }


def get_access_token(client_id):
    """SIMKL AUTH V2 device flow (RFC 8628). /oauth/pin refuses V2 client_ids
    and points here instead."""
    device_request = api_request("POST", "/oauth2/device", client_id)

    device_code = device_request['device_code']
    user_code = device_request['user_code']
    verification_uri = device_request.get('verification_uri') or device_request.get('verification_url')
    verification_uri_complete = device_request.get('verification_uri_complete')
    interval = device_request.get('interval', 5)
    expires_in = device_request.get('expires_in', 900)

    open_url = verification_uri_complete or verification_uri

    if verification_uri_complete:
        print(f"Opening {open_url} — the code is already filled in, just click Approve.")
        print(f"(code: {user_code}, in case the browser doesn't open)")
    else:
        print(f"Opening {verification_uri} — enter this code if it isn't pre-filled: {user_code}")

    print(f"You have {expires_in} seconds before this code expires.")
    webbrowser.open(open_url)

    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        try:
            token_response = api_request(
                "POST",
                "/oauth2/token",
                client_id,
                data={
                    "client_id": client_id,
                    "device_code": device_code,
                    "grant_type": DEVICE_GRANT_TYPE,
                },
            )
        except RuntimeError as e:
            msg = str(e).lower()
            if "authorization_pending" in msg or "pending" in msg:
                continue
            if "slow_down" in msg:
                interval += 5
                continue
            if "expired" in msg:
                raise RuntimeError("The device code expired before you approved it. Run the script again.")
            if "access_denied" in msg:
                raise RuntimeError("Authorization was denied on simkl.com/pin.")
            raise

        if 'access_token' in token_response:
            return token_response['access_token']

    raise RuntimeError("Timed out waiting for approval at " + verification_uri)


config = configparser.ConfigParser()
config.read('conf.ini')
client_id = config["CONFIGS"]["client_id"]

access_token = get_access_token(client_id)

z = api_request(
    "GET",
    "/sync/all-items/movies/completed",
    client_id,
    headers={'Authorization': 'Bearer ' + access_token},
)

data = list(map(map_data, z['movies']))

make_csv(data)
print(f"Wrote {len(data)} movies to simklData.csv")
