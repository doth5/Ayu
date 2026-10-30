"""Shared API client for Streamlit pages."""
import requests
from config.settings import settings

BASE = settings.API_BASE_URL


def get(path: str, **params) -> dict | list:
    r = requests.get(f"{BASE}{path}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def post(path: str, json: dict = None, data: dict = None, files: dict = None, params: dict = None) -> dict:
    r = requests.post(f"{BASE}{path}", json=json, data=data, files=files, params=params, timeout=30)
    r.raise_for_status()
    # Some endpoints return 204 No Content
    if r.status_code == 204 or not r.content:
        return {}
    return r.json()


def patch(path: str, json: dict) -> dict:
    r = requests.patch(f"{BASE}{path}", json=json, timeout=10)
    r.raise_for_status()
    return r.json()


def delete(path: str) -> None:
    r = requests.delete(f"{BASE}{path}", timeout=10)
    r.raise_for_status()
