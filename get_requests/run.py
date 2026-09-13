#!/usr/bin/env -S uv run
# /// script
# dependencies = []
# ///

import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seerr_client import MediaRequestStatus, SeerrClient


def fetch_title(client: SeerrClient, media_type: str, tmdb_id: int) -> str | None:
    # A stale or invalid TMDB ID on one request shouldn't abort the entire listing,
    # so we catch all exceptions here and fall back to null rather than propagating.
    # SystemExit must be caught explicitly because the shared client calls sys.exit(1)
    # on HTTP errors, and SystemExit inherits from BaseException, not Exception.
    try:
        detail = client.get(f"/api/v1/{media_type}/{tmdb_id}")
        if media_type == "movie":
            return detail["title"]
        return detail["name"]
    except (Exception, SystemExit):
        return None


def get_display_name(requested_by: dict) -> str | None:
    # displayName is the preferred field; fall back to jellyfinUsername then email
    # if the account was created without a display name set.
    return (
        requested_by.get("displayName")
        or requested_by.get("jellyfinUsername")
        or requested_by.get("email")
    )


def clean_result(raw: dict, title: str | None) -> dict:
    media_type = raw["type"]
    status_code = raw["status"]

    cleaned: dict = {
        "id": raw["id"],
        "title": title,
        "media_type": media_type,
        "status": MediaRequestStatus.get(status_code, f"unknown ({status_code})"),
        "requested_by": get_display_name(raw["requestedBy"]),
        "created_at": raw["createdAt"],
        "is_4k": raw["is4k"],
    }

    if media_type == "tv":
        cleaned["seasons"] = [season["seasonNumber"] for season in raw.get("seasons", [])]

    return cleaned


KNOWN_PARAMS = {"filter", "media_type", "take", "skip"}


def main() -> None:
    params = json.load(sys.stdin)
    unknown = set(params) - KNOWN_PARAMS
    if unknown:
        print(f"Unknown parameters: {', '.join(sorted(unknown))}", file=sys.stderr)
        sys.exit(1)
    filter_status = params.get("filter", "all")
    media_type = params.get("media_type")
    take = params.get("take", 20)
    skip = params.get("skip", 0)

    query_params: dict[str, str] = {
        "take": str(take),
        "skip": str(skip),
    }

    if filter_status and filter_status != "all":
        query_params["filter"] = filter_status

    if media_type:
        query_params["mediaType"] = media_type

    query_string = urllib.parse.urlencode(query_params)
    path = f"/api/v1/request?{query_string}"

    client = SeerrClient.from_config()
    raw = client.get(path)

    # Build a title cache keyed by (media_type, tmdb_id) so the same media is only
    # fetched once. Multiple requests can reference the same show (e.g. separate
    # season requests).
    title_cache: dict[tuple[str, int], str | None] = {}
    for result in raw["results"]:
        key = (result["type"], result["media"]["tmdbId"])
        if key not in title_cache:
            title_cache[key] = fetch_title(client, key[0], key[1])

    page_info_raw = raw["pageInfo"]
    output = {
        "page_info": {
            "page": page_info_raw["page"],
            "pages": page_info_raw["pages"],
            # The API names this field "results" but it holds the total count.
            "total": page_info_raw["results"],
        },
        "results": [
            clean_result(r, title_cache[(r["type"], r["media"]["tmdbId"])])
            for r in raw["results"]
        ],
    }

    json.dump(output, sys.stdout)


main()
