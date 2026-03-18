from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from .config import settings
from .models import FriendEntry, PendingMessageEntry, TokenResponse


class APIClient:
    def __init__(self):
        self.base_url = settings.api_base_url
        self.client = httpx.Client(base_url=self.base_url, timeout=15.0)
        self.token: Optional[str] = None
        self.load_token()

    def load_token(self) -> None:
        try:
            self.token = settings.token_file.read_text().strip()
        except FileNotFoundError:
            self.token = None

    def save_token(self, token: str) -> None:
        self.token = token
        settings.token_file.write_text(token)

    def auth_headers(self) -> Dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def register(self, nick: str, password: str) -> dict:
        response = self.client.post(
            "/auth/register",
            headers=self.auth_headers(),
            json={"nick": nick, "password": password},
        )
        response.raise_for_status()
        return response.json()

    def login(self, nick: str, password: str) -> TokenResponse:
        response = self.client.post(
            "/auth/login",
            json={"nick": nick, "password": password},
        )
        response.raise_for_status()
        return TokenResponse(**response.json())

    def get_friends(self) -> List[FriendEntry]:
        response = self.client.get("/friends/", headers=self.auth_headers())
        response.raise_for_status()
        return [FriendEntry(**item) for item in response.json()]

    def search_profiles(self, query: str) -> List[FriendEntry]:
        response = self.client.get(
            "/friends/search",
            headers=self.auth_headers(),
            params={"q": query, "limit": 25},
        )
        response.raise_for_status()
        return [FriendEntry(**item) for item in response.json()]

    def send_friend_request(self, target_nick: str) -> None:
        response = self.client.post(
            "/friends/requests",
            headers=self.auth_headers(),
            json={"target_nick": target_nick},
        )
        response.raise_for_status()

    def send_message(
        self,
        payload: str,
        recipients: List[str],
        metadata: Optional[Dict[str, str]] = None,
        media_ids: Optional[List[str]] = None,
        group_id: Optional[int] = None,
    ) -> None:
        response = self.client.post(
            "/messages/send",
            headers=self.auth_headers(),
            json={
                "payload": payload,
                "recipients": recipients,
                "metadata": metadata or {},
                "media_ids": media_ids or [],
                "group_id": group_id,
            },
        )
        response.raise_for_status()

    def get_pending(self) -> List[PendingMessageEntry]:
        response = self.client.get("/messages/pending", headers=self.auth_headers())
        response.raise_for_status()
        return [PendingMessageEntry(**item) for item in response.json()]

    def presence_ping(self) -> None:
        response = self.client.post("/friends/presence/ping", headers=self.auth_headers())
        response.raise_for_status()

    def upload_media(self, file_path: Path) -> str:
        with file_path.open("rb") as handle:
            response = self.client.post(
                "/media/upload",
                headers=self.auth_headers(),
                files={"file": (file_path.name, handle, "application/octet-stream")},
            )
        response.raise_for_status()
        return response.json()["media_id"]

    def download_media(self, media_id: str) -> bytes:
        response = self.client.get(
            f"/media/{media_id}/download",
            headers=self.auth_headers(),
        )
        response.raise_for_status()
        return response.content

    def get_settings(self) -> Dict[str, str]:
        response = self.client.get("/settings/", headers=self.auth_headers())
        response.raise_for_status()
        return response.json()

    def update_public_key(self, public_key: str) -> Dict[str, str]:
        payload = {"public_key": public_key}
        response = self.client.put("/settings/", headers=self.auth_headers(), json=payload)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self.client.close()
