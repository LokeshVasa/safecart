import requests

def geocode_address(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "SafeCartApp"
    }

    response = requests.get(url, params=params, headers=headers, timeout=10)
    data = response.json()

    if data:
        return float(data[0]["lat"]), float(data[0]["lon"])

    return None, None