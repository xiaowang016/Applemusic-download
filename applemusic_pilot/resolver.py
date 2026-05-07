from __future__ import annotations

from applemusic_pilot.fetch import CurlFetcher
from applemusic_pilot.parse import AppleSongMetadata, normalize_url, parse_song_page


class AppleMusicResolver:
    def __init__(self, *, fetcher: CurlFetcher | None = None) -> None:
        self.fetcher = fetcher or CurlFetcher()

    def resolve(self, url: str) -> AppleSongMetadata:
        normalized_url = normalize_url(url)
        body = self.fetcher.fetch_text(normalized_url)
        return parse_song_page(body, normalized_url)

    def resolve_many(self, urls: list[str]) -> list[AppleSongMetadata]:
        return [self.resolve(url) for url in urls]

