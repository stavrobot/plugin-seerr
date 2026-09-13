#!/usr/bin/env -S uv run
# /// script
# dependencies = []
# ///

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seerr_client import MediaRequestStatus, SeerrClient


def fetch_title(client: SeerrClient, media_type: str, tmdb_id: int) -> str | None:
    # A stale or invalid TMDB ID shouldn't abort the request confirmation,
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


KNOWN_PARAMS = {"media_type", "media_id", "is_4k", "seasons"}


def main() -> None:
    params = json.load(sys.stdin)
    unknown = set(params) - KNOWN_PARAMS
    if unknown:
        print(f"Unknown parameters: {', '.join(sorted(unknown))}", file=sys.stderr)
        sys.exit(1)
    media_type = params["media_type"]
    media_id = params["media_id"]
    is_4k = params.get("is_4k", False)
    seasons_raw = params.get("seasons", "")

    seasons: list[int] = (
        [int(season.strip()) for season in seasons_raw.split(",") if season.strip()]
        if seasons_raw
        else []
    )

    request_body: dict = {
        "mediaType": media_type,
        "mediaId": media_id,
        "is4k": is_4k,
    }

    if media_type == "tv":
        # The Seerr server rejects an empty seasons list with NoSeasonsAvailableError,
        # so when the caller names no seasons we ask for every season; the API accepts
        # the literal string "all" for that case and an explicit list of integers
        # otherwise.
        request_body["seasons"] = seasons if seasons else "all"

    client = SeerrClient.from_config()
    result = client.post("/api/v1/request", request_body)

    if "media" not in result:
        # Seerr answers HTTP 202, a success status, with no "media" key when
        # there is nothing to request, for example when every season is already
        # requested or available: {"message": "No seasons available to request"}.
        # urllib only raises on error statuses, so this failure carried by a
        # success status must be surfaced by hand, in the same shape as an HTTP
        # error, rather than letting the missing "media" key raise a traceback.
        json.dump({"error": result["message"]}, sys.stderr)
        sys.exit(1)

    tmdb_id = result["media"]["tmdbId"]
    result_media_type = result["type"]
    title = fetch_title(client, result_media_type, tmdb_id)

    status_code = result["status"]
    output: dict = {
        "id": result["id"],
        "title": title,
        "media_type": result_media_type,
        "status": MediaRequestStatus.get(status_code, f"unknown ({status_code})"),
        "is_4k": result["is4k"],
    }

    if result_media_type == "tv":
        output["seasons"] = [
            season["seasonNumber"] for season in result.get("seasons", [])
        ]

    json.dump(output, sys.stdout)


main()
