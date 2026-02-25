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

VALID_CATEGORIES = {"trending", "movies", "movies_upcoming", "tv", "tv_upcoming"}


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


def build_path(params: dict) -> str:
    category = params.get("category", "")
    if category not in VALID_CATEGORIES:
        print(
            f"Error: invalid category {category!r}. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    page = params.get("page", 1)

    if category == "trending":
        query_string = urllib.parse.urlencode(
            {"page": page}, quote_via=urllib.parse.quote
        )
        return f"/api/v1/discover/trending?{query_string}"

    if category == "movies_upcoming":
        query_string = urllib.parse.urlencode(
            {"page": page}, quote_via=urllib.parse.quote
        )
        return f"/api/v1/discover/movies/upcoming?{query_string}"

    if category == "tv_upcoming":
        query_string = urllib.parse.urlencode(
            {"page": page}, quote_via=urllib.parse.quote
        )
        return f"/api/v1/discover/tv/upcoming?{query_string}"

    if category == "movies":
        genre = params.get("genre")
        studio = params.get("studio")
        language = params.get("language")
        sort_by = params.get("sort_by")

        if genre is not None:
            query_string = urllib.parse.urlencode(
                {"page": page}, quote_via=urllib.parse.quote
            )
            return f"/api/v1/discover/movies/genre/{genre}?{query_string}"

        if studio is not None:
            query_string = urllib.parse.urlencode(
                {"page": page}, quote_via=urllib.parse.quote
            )
            return f"/api/v1/discover/movies/studio/{studio}?{query_string}"

        if language is not None:
            query_string = urllib.parse.urlencode(
                {"page": page}, quote_via=urllib.parse.quote
            )
            return f"/api/v1/discover/movies/language/{language}?{query_string}"

        query_params: dict = {"page": page}
        if sort_by is not None:
            query_params["sortBy"] = sort_by
        query_string = urllib.parse.urlencode(
            query_params, quote_via=urllib.parse.quote
        )
        return f"/api/v1/discover/movies?{query_string}"

    # All other categories have returned above, so only "tv" remains.
    network = params.get("network")
    genre = params.get("genre")

    if network is not None:
        query_string = urllib.parse.urlencode(
            {"page": page}, quote_via=urllib.parse.quote
        )
        return f"/api/v1/discover/tv/network/{network}?{query_string}"

    query_params = {"page": page}
    if genre is not None:
        query_params["genre"] = genre
    query_string = urllib.parse.urlencode(
        query_params, quote_via=urllib.parse.quote
    )
    return f"/api/v1/discover/tv?{query_string}"


def main() -> None:
    config = json.loads(Path("../config.json").read_text())
    api_url = config["api_url"].rstrip("/")
    api_key = config["api_key"]

    params = json.load(sys.stdin)

    path = build_path(params)
    raw = call_seerr_api(api_url, api_key, path)
    json.dump(clean_response(raw), sys.stdout)


main()
