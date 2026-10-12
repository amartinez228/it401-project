import requests
from urllib.parse import urlsplit


class ApiService:
    """Thin wrapper around outbound HTTP calls to external APIs."""

    def __init__(self, base_url, api_key=None, timeout=10):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        origin = urlsplit(self.base_url)
        if origin.scheme != "https" or not origin.hostname or origin.username or origin.password or origin.query or origin.fragment:
            raise ValueError("External APIs require an HTTPS origin without credentials.")

    def _headers(self):
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get(self, path, params=None):
        response = requests.get(
            f"{self.base_url}/{path.lstrip('/')}",
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            raise ValueError("API redirects are not accepted.")
        response.raise_for_status()
        return response.json()

    def post(self, path, payload=None):
        response = requests.post(
            f"{self.base_url}/{path.lstrip('/')}",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            raise ValueError("API redirects are not accepted.")
        response.raise_for_status()
        return response.json()


class RapidApiService(ApiService):
    """HTTP client that adds RapidAPI authentication on the server."""

    def __init__(self, base_url, api_key, host, timeout=10):
        super().__init__(base_url, api_key=api_key, timeout=timeout)
        self.host = host

    def _headers(self):
        return {
            "Accept": "application/json",
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.host,
        }
