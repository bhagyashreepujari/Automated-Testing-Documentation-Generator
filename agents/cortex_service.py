from __future__ import annotations

import time
from typing import Any
from wsgiref import headers

import requests


class CortexAPIService:
    """
    Authenticates with Azure AD via client-credentials grant and calls the
    Lilly Cortex API gateway.

    Parameters
    ----------
    base_url      : e.g. "https://gateway.apim-dev.lilly.com/cortex/model"
    tenant_id     : Azure AD tenant GUID
    client_id     : App registration client ID
    client_secret : App registration client secret
    scope         : OAuth2 scope string (optional — defaults to base_url/.default)
    timeout       : seconds for each HTTP request (default 60)
    """

    _TOKEN_URL_TEMPLATE = (
        "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    )

    def __init__(
        self,
        base_url: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        scope: str | None = None,
        timeout: int = 60,
    ) -> None:
        self._base_url      = base_url.rstrip("/")
        self._tenant_id     = tenant_id
        self._client_id     = client_id
        self._client_secret = client_secret
        self._scope         = scope or f"{base_url.rstrip('/')}/.default"
        self._timeout       = timeout
        self._session       = requests.Session()

        # Cached token state
        self._access_token:  str   = ""
        self._token_expiry:  float = 0.0

    # ── Token management ──────────────────────────────────────────────────────

    def _fetch_token(self) -> str:
        """Request a new access token via client-credentials grant."""
        url = self._TOKEN_URL_TEMPLATE.format(tenant_id=self._tenant_id)
        response = self._session.post(
            url,
            data={
                "grant_type":    "client_credentials",
                "client_id":     self._client_id,
                "client_secret": self._client_secret,
                "scope":         self._scope,
            },
            timeout=self._timeout,
        )
        print("URL:", url)
        print("Headers:", headers)
        print("Status:", response.status_code)
        print("Response:", response.text)
        response.raise_for_status()
        token_data          = response.json()
        self._access_token  = token_data["access_token"]
        # Refresh 60 s before actual expiry to avoid edge-case failures
        expires_in          = int(token_data.get("expires_in", 3600))
        self._token_expiry  = time.monotonic() + expires_in - 60
        return self._access_token

    def _get_token(self) -> str:
        """Return a valid access token, fetching a new one when necessary."""
        if not self._access_token or time.monotonic() >= self._token_expiry:
            self._fetch_token()
        return self._access_token

    # ── Public API ────────────────────────────────────────────────────────────

    def call(
        self,
        endpoint: str,
        method: str = "POST",
        data: dict[str, Any] | None = None,
        files=None,
    ) -> dict[str, Any] | None:
        """
        Call a Cortex agent endpoint.

        Parameters
        ----------
        endpoint     : path relative to base_url, e.g. "ask/planner-agent"
        method       : HTTP verb (default "POST")
        data         : form body dict, e.g. {"q": "your prompt"}
        content_type : request Content-Type header

        Returns the parsed JSON dict, or None on failure.
        """
        url     = f"{self._base_url}/{endpoint.lstrip('/')}"
        token   = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}"
        }

        response = self._session.request(
            method=method.upper(),
            url=url,
            data=data,
            files=files,
            headers=headers,
            timeout=self._timeout,
        )
        print("URL:", url)
        print("Headers:", headers)
        print("Status:", response.status_code)
        print("Response:", response.text)
        response.raise_for_status()

        try:
            result = response.json()
        except ValueError:
            return None

        return result if isinstance(result, dict) else None

    def close(self) -> None:
        """Release the underlying HTTP session."""
        self._session.close()
