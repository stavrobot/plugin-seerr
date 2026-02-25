#!/usr/bin/env -S uv run
# /// script
# dependencies = []
# ///

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


REQUEST_STATUS_CODES: dict[int, str] = {
    1: "pending",
    2: "approved",
    3: "declined",
    5: "available",
}


def call_seerr_api(api_url: str, api_key: str, path: str, body: dict) -> dict:
    encoded_body = json.dumps(body).encode()
    request = urllib.request.Request(
        f"{api_url}{path}",
        data=encoded_body,
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        response_body = error.read().decode()
        json.dump({"error": f"HTTP {error.code}: {response_body}"}, sys.stderr)
        sys.exit(1)


def call_seerr_api_get(api_url: str, api_key: str, path: str) -> dict:
    request = urllib.request.Request(
        f"{api_url}{path}",
        headers={"X-Api-Key": api_key},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        response_body = error.read().decode()
        json.dump({"error": f"HTTP {error.code}: {response_body}"}, sys.stderr)
        sys.exit(1)


def fetch_title(api_url: str, api_key: str, media_type: str, tmdb_id: int) -> str | None:
    # A stale or invalid TMDB ID shouldn't abort the request confirmation,
    # so we catch all exceptions here and fall back to null rather than propagating.
    # SystemExit must be caught explicitly because call_seerr_api_get uses sys.exit(1)
    # on HTTP errors, and SystemExit inherits from BaseException, not Exception.
    try:
        detail = call_seerr_api_get(api_url, api_key, f"/api/v1/{media_type}/{tmdb_id}")
        if media_type == "movie":
            return detail["title"]
        return detail["name"]
    except (Exception, SystemExit):
        return None


def main() -> None:
    config = json.loads(Path("../config.json").read_text())
    api_url = config["api_url"].rstrip("/")
    api_key = config["api_key"]

    params = json.load(sys.stdin)
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
        request_body["seasons"] = seasons

    result = call_seerr_api(api_url, api_key, "/api/v1/request", request_body)

    tmdb_id = result["media"]["tmdbId"]
    result_media_type = result["type"]
    title = fetch_title(api_url, api_key, result_media_type, tmdb_id)

    status_code = result["status"]
    output: dict = {
        "id": result["id"],
        "title": title,
        "media_type": result_media_type,
        "status": REQUEST_STATUS_CODES.get(status_code, f"unknown ({status_code})"),
        "is_4k": result["is4k"],
    }

    if result_media_type == "tv":
        output["seasons"] = [season["seasonNumber"] for season in result.get("seasons", [])]

    json.dump(output, sys.stdout)


main()
