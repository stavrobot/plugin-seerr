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
        body = error.read().decode()
        json.dump({"error": f"HTTP {error.code}: {body}"}, sys.stderr)
        sys.exit(1)


MEDIA_STATUS_CODES: dict[int, str] = {
    1: "unknown",
    2: "pending",
    3: "processing",
    4: "partially_available",
    5: "available",
}


def clean_result(result: dict) -> dict:
    media_type = result.get("mediaType", "")
    if media_type == "person":
        return {
            "id": result["id"],
            "media_type": "person",
            "title": result.get("name", ""),
        }

    if media_type == "movie":
        title = result.get("title", "")
        date_key = "release_date"
        date_value = result.get("releaseDate", "")
    elif media_type == "tv":
        title = result.get("name", "")
        date_key = "first_air_date"
        date_value = result.get("firstAirDate", "")
    else:
        return {
            "id": result["id"],
            "media_type": media_type,
            "title": result.get("name", result.get("title", "")),
        }

    cleaned: dict = {
        "id": result["id"],
        "media_type": media_type,
        "title": title,
        "overview": result.get("overview", ""),
        date_key: date_value,
        "vote_average": result.get("voteAverage"),
    }

    media_info = result.get("mediaInfo")
    if media_info is not None:
        status_code = media_info.get("status")
        if status_code is not None:
            cleaned["status"] = MEDIA_STATUS_CODES.get(
                status_code, f"unknown ({status_code})"
            )

    return cleaned


def clean_response(raw: dict) -> dict:
    return {
        "page": raw.get("page"),
        "total_pages": raw.get("totalPages"),
        "total_results": raw.get("totalResults"),
        "results": [clean_result(r) for r in raw.get("results", [])],
    }


KNOWN_PARAMS = {"query", "page"}


def main() -> None:
    config = json.loads(Path("../config.json").read_text())
    api_url = config["api_url"].rstrip("/")
    api_key = config["api_key"]

    params = json.load(sys.stdin)
    unknown = set(params) - KNOWN_PARAMS
    if unknown:
        print(f"Unknown parameters: {', '.join(sorted(unknown))}", file=sys.stderr)
        sys.exit(1)
    query = params["query"]
    page = params.get("page", 1)

    # urlencode defaults to encoding spaces as '+', which the Seerr API rejects.
    # quote_via=urllib.parse.quote produces percent-encoded spaces (%20) instead.
    query_string = urllib.parse.urlencode(
        {"query": query, "page": page}, quote_via=urllib.parse.quote
    )
    path = f"/api/v1/search?{query_string}"

    raw = call_seerr_api(api_url, api_key, path)
    json.dump(clean_response(raw), sys.stdout)


main()
