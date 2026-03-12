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

from cryptography.fernet import Fernet
from django.conf import settings

cipher = Fernet(settings.OTP_ENCRYPTION_KEY)

def encrypt_value(value):
    return cipher.encrypt(value.encode()).decode()

def decrypt_value(value):
    return cipher.decrypt(value.encode()).decode()