from __future__ import annotations

import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; AppleMusicMetadataPilot/0.1; "
    "+https://music.apple.com/)"
)
ALLOWED_HOSTS = ("music.apple.com",)


class FetchError(RuntimeError):
    """Raised when a page fetch fails."""


@dataclass(slots=True)
class CurlFetcher:
    user_agent: str = DEFAULT_USER_AGENT
    accept_language: str = "en-CA,en;q=0.9"

    def fetch_text(self, url: str) -> str:
        self._assert_allowed(url)
        try:
            completed = subprocess.run(
                [
                    "curl",
                    "-sSL",
                    "--fail",
                    "-A",
                    self.user_agent,
                    "-H",
                    "Accept: text/html,application/xhtml+xml",
                    "-H",
                    f"Accept-Language: {self.accept_language}",
                    url,
                ],
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as exc:
            raise FetchError("curl is required but was not found on this machine") from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or "curl exited with a non-zero status"
            raise FetchError(f"Could not fetch {url}: {message}")
        return completed.stdout

    def _assert_allowed(self, url: str) -> None:
        host = urlparse(url).netloc.lower()
        if host not in ALLOWED_HOSTS:
            raise ValueError(f"Refusing to fetch disallowed host: {host}")

