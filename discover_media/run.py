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
        # Require a minimum vote count to filter out obscure titles that skew
        # rating-based sorting with a handful of perfect scores.
        query_params: dict = {"page": page, "voteCountGte": 200}
        for plugin_param, overseerr_param in [
            ("genre", "genre"),
            ("studio", "studio"),
            ("language", "language"),
            ("sort_by", "sortBy"),
            ("primary_release_date_gte", "primaryReleaseDateGte"),
            ("primary_release_date_lte", "primaryReleaseDateLte"),
            ("vote_average_gte", "voteAverageGte"),
            ("vote_average_lte", "voteAverageLte"),
            ("runtime_gte", "withRuntimeGte"),
            ("runtime_lte", "withRuntimeLte"),
        ]:
            value = params.get(plugin_param)
            if value is not None:
                query_params[overseerr_param] = value
        query_string = urllib.parse.urlencode(
            query_params, quote_via=urllib.parse.quote
        )
        return f"/api/v1/discover/movies?{query_string}"

    # All other categories have returned above, so only "tv" remains.
    # Require a minimum vote count to filter out obscure titles that skew
    # rating-based sorting with a handful of perfect scores.
    query_params = {"page": page, "voteCountGte": 200}
    for plugin_param, overseerr_param in [
        ("genre", "genre"),
        ("network", "network"),
        ("language", "language"),
        ("sort_by", "sortBy"),
        ("first_air_date_gte", "firstAirDateGte"),
        ("first_air_date_lte", "firstAirDateLte"),
        ("vote_average_gte", "voteAverageGte"),
        ("vote_average_lte", "voteAverageLte"),
        ("runtime_gte", "withRuntimeGte"),
        ("runtime_lte", "withRuntimeLte"),
    ]:
        value = params.get(plugin_param)
        if value is not None:
            query_params[overseerr_param] = value
    query_string = urllib.parse.urlencode(
        query_params, quote_via=urllib.parse.quote
    )
    return f"/api/v1/discover/tv?{query_string}"


KNOWN_PARAMS = {
    "category",
    "genre",
    "network",
    "studio",
    "language",
    "sort_by",
    "page",
    "primary_release_date_gte",
    "primary_release_date_lte",
    "first_air_date_gte",
    "first_air_date_lte",
    "vote_average_gte",
    "vote_average_lte",
    "runtime_gte",
    "runtime_lte",
}


def main() -> None:
    config = json.loads(Path("../config.json").read_text())
    api_url = config["api_url"].rstrip("/")
    api_key = config["api_key"]

    params = json.load(sys.stdin)
    unknown = set(params) - KNOWN_PARAMS
    if unknown:
        print(f"Unknown parameters: {', '.join(sorted(unknown))}", file=sys.stderr)
        sys.exit(1)

    path = build_path(params)
    raw = call_seerr_api(api_url, api_key, path)
    json.dump(clean_response(raw), sys.stdout)


main()
