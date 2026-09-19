import requests, configparser

config = configparser.ConfigParser()
config.read('conf.ini')
client_id = config["CONFIGS"]["client_id"]
print(f"client_id read as: {client_id!r}  (length={len(client_id)})")

url = "https://api.simkl.com/oauth/pin?client_id=" + client_id
r = requests.get(url)
print("status:", r.status_code)
print("body:", r.text)
