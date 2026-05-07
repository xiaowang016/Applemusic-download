from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from urllib.parse import parse_qs, urlparse


HOST = "music.apple.com"
META_TAG_RE = re.compile(r"<meta\b(?P<attrs>[^>]*)>", re.IGNORECASE)
ATTR_RE = re.compile(r'([A-Za-z_:.-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
TITLE_TAG_RE = re.compile(r"<title>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
TRACK_ID_RE = re.compile(r"[?&]i=(?P<song_id>\d+)")
DESCRIPTION_ARTIST_RE = re.compile(
    r"^Listen to .*? by (?P<artist>.+?) on Apple\s*Music",
    re.IGNORECASE,
)
TITLE_ARTIST_RE = re.compile(
    r"(?:Song|Album) by (?P<artist>.+?)\s*[–-]\s*Apple\s*Music",
    re.IGNORECASE,
)
OG_TITLE_ARTIST_RE = re.compile(
    r"^.*? by (?P<artist>.+?) on Apple\s*Music$",
    re.IGNORECASE,
)
OG_TITLE_SONG_RE = re.compile(
    r"^(?P<title>.+?) by .+? on Apple\s*Music$",
    re.IGNORECASE,
)
TITLE_TAG_SONG_RE = re.compile(
    r"^(?P<title>.+?)\s*[–-]\s*(?:Song|Album) by .+?\s*[–-]\s*Apple\s*Music$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class AppleSongMetadata:
    song_id: str
    song_name: str
    artist_name: str
    original_url: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def normalize_url(url: str) -> str:
    cleaned = url.strip().replace("\u2028", "").replace("\u2029", "")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme: {cleaned}")
    if parsed.netloc.lower() != HOST:
        raise ValueError(f"Unsupported Apple Music host: {parsed.netloc}")
    return cleaned


def parse_song_page(body: str, original_url: str) -> AppleSongMetadata:
    normalized_url = normalize_url(original_url)
    direct_song_id = extract_song_id_from_url(normalized_url)
    song_id = infer_song_id(normalized_url, body)
    song_name = extract_song_name(
        body,
        song_id=song_id,
        prefer_track_context=direct_song_id is None,
    )
    artist_name = extract_artist_name(body)
    return AppleSongMetadata(
        song_id=song_id,
        song_name=song_name,
        artist_name=artist_name,
        original_url=normalized_url,
    )


def infer_song_id(url: str, body: str) -> str:
    direct_song_id = extract_song_id_from_url(url)
    if direct_song_id:
        return direct_song_id

    page_song_ids = extract_song_ids_from_body(body)
    if len(page_song_ids) == 1:
        return page_song_ids[0]
    if not page_song_ids:
        raise ValueError(f"Could not determine song_id for {url}")
    raise ValueError(
        "Apple Music page exposed multiple track ids; use a track URL with ?i=..."
    )


def extract_song_id_from_url(url: str) -> str | None:
    query = parse_qs(urlparse(url).query)
    values = query.get("i")
    if not values:
        return None
    candidate = values[0].strip()
    return candidate or None


def extract_song_ids_from_body(body: str) -> list[str]:
    discovered: list[str] = []
    seen: set[str] = set()
    for match in TRACK_ID_RE.finditer(body):
        candidate = match.group("song_id")
        if candidate not in seen:
            seen.add(candidate)
            discovered.append(candidate)
    return discovered


def extract_artist_name(body: str) -> str:
    for meta_name in ("description", "apple:description"):
        content = extract_meta_content(body, meta_name)
        if not content:
            continue
        match = DESCRIPTION_ARTIST_RE.search(content)
        if match:
            return clean_text(match.group("artist"))

    og_title = extract_meta_content(body, "og:title")
    if og_title:
        match = OG_TITLE_ARTIST_RE.search(og_title)
        if match:
            return clean_text(match.group("artist"))

    title = extract_title_text(body)
    if title:
        match = TITLE_ARTIST_RE.search(title)
        if match:
            return clean_text(match.group("artist"))

    raise ValueError("Could not determine artist_name from Apple Music page")


def extract_song_name(
    body: str,
    *,
    song_id: str,
    prefer_track_context: bool,
) -> str:
    if prefer_track_context:
        title = extract_track_title_from_body(body, song_id)
        if title:
            return title

    apple_title = extract_meta_content(body, "apple:title")
    if apple_title:
        return apple_title

    og_title = extract_meta_content(body, "og:title")
    if og_title:
        match = OG_TITLE_SONG_RE.search(og_title)
        if match:
            return clean_text(match.group("title"))
        return og_title

    title = extract_title_text(body)
    if title:
        match = TITLE_TAG_SONG_RE.search(title)
        if match:
            return clean_text(match.group("title"))
        return title

    if not prefer_track_context:
        fallback_title = extract_track_title_from_body(body, song_id)
        if fallback_title:
            return fallback_title

    raise ValueError("Could not determine song_name from Apple Music page")


def extract_track_title_from_body(body: str, song_id: str) -> str | None:
    escaped_song_id = re.escape(song_id)
    patterns = (
        re.compile(
            rf'"title":"(?P<title>[^"]+)".{{0,600}}"storeAdamID":"{escaped_song_id}"',
            re.DOTALL,
        ),
        re.compile(
            rf'"storeAdamID":"{escaped_song_id}".{{0,600}}"title":"(?P<title>[^"]+)"',
            re.DOTALL,
        ),
        re.compile(
            rf'"name":"(?P<title>[^"]+)".{{0,400}}"id":"{escaped_song_id}"',
            re.DOTALL,
        ),
        re.compile(
            rf'"id":"{escaped_song_id}".{{0,400}}"name":"(?P<title>[^"]+)"',
            re.DOTALL,
        ),
    )
    for pattern in patterns:
        match = pattern.search(body)
        if match:
            return clean_text(match.group("title"))
    return None


def extract_meta_content(body: str, target_name: str) -> str | None:
    target_name = target_name.lower()
    for match in META_TAG_RE.finditer(body):
        attrs = _parse_attrs(match.group("attrs"))
        name = (attrs.get("name") or attrs.get("property") or "").lower()
        if name != target_name:
            continue
        content = attrs.get("content")
        if content is None:
            continue
        return clean_text(content)
    return None


def extract_title_text(body: str) -> str | None:
    match = TITLE_TAG_RE.search(body)
    if match is None:
        return None
    return clean_text(match.group("title"))


def clean_text(text: str) -> str:
    cleaned = html.unescape(text)
    cleaned = cleaned.replace("\xa0", " ").replace("\u200e", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _parse_attrs(raw_attrs: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in ATTR_RE.finditer(raw_attrs):
        key = match.group(1).lower()
        value = match.group(2) if match.group(2) is not None else match.group(3)
        attrs[key] = value
    return attrs
