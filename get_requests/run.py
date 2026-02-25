#!/usr/bin/env -S uv run
# /// script
# dependencies = []
# ///

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def call_seerr_api(api_url: str, api_key: str, path: str) -> dict:
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
    # A stale or invalid TMDB ID on one request shouldn't abort the entire listing,
    # so we catch all exceptions here and fall back to null rather than propagating.
    # SystemExit must be caught explicitly because call_seerr_api uses sys.exit(1)
    # on HTTP errors, and SystemExit inherits from BaseException, not Exception.
    try:
        detail = call_seerr_api(api_url, api_key, f"/api/v1/{media_type}/{tmdb_id}")
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

    result = call_seerr_api(api_url, api_key, path)

    for request_result in result["results"]:
        tmdb_id = request_result["media"]["tmdbId"]
        request_type = request_result["type"]
        request_result["title"] = fetch_title(api_url, api_key, request_type, tmdb_id)

    json.dump(result, sys.stdout)


main()
