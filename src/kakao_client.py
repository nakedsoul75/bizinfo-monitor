"""Kakao 'Send to Me' message client. daily-order-report 와 동일 인터페이스."""
from __future__ import annotations

import json
import os
from typing import Any

import requests


class KakaoClient:
    TOKEN_URL = "https://kauth.kakao.com/oauth/token"
    SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

    def __init__(self, rest_api_key: str, refresh_token: str, client_secret: str | None = None) -> None:
        self.rest_api_key = rest_api_key
        self.refresh_token = refresh_token
        self.client_secret = client_secret
        self.access_token: str | None = None
        self.new_refresh_token: str | None = None

    def _refresh_access_token(self) -> None:
        data = {
            "grant_type": "refresh_token",
            "client_id": self.rest_api_key,
            "refresh_token": self.refresh_token,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret
        resp = requests.post(self.TOKEN_URL, data=data, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        self.access_token = body["access_token"]
        if "refresh_token" in body:
            self.new_refresh_token = body["refresh_token"]
            self.refresh_token = body["refresh_token"]

    def send_text(self, text: str, link_url: str = "https://www.bizinfo.go.kr") -> dict[str, Any]:
        if not self.access_token:
            self._refresh_access_token()

        template = {
            "object_type": "text",
            "text": text[:3900],
            "link": {"web_url": link_url, "mobile_web_url": link_url},
            "button_title": "보고서 열기",
        }
        resp = requests.post(
            self.SEND_URL,
            headers={"Authorization": f"Bearer {self.access_token}"},
            data={"template_object": json.dumps(template, ensure_ascii=False)},
            timeout=15,
        )
        if resp.status_code == 401:
            self._refresh_access_token()
            return self.send_text(text, link_url)
        resp.raise_for_status()
        return resp.json()


def from_env() -> KakaoClient:
    return KakaoClient(
        rest_api_key=os.environ["KAKAO_REST_API_KEY"],
        refresh_token=os.environ["KAKAO_REFRESH_TOKEN"],
        client_secret=os.environ.get("KAKAO_CLIENT_SECRET") or None,
    )
