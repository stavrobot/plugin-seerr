#!/usr/bin/env -S uv run
# /// script
# dependencies = []
# ///

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seerr_client import MediaStatus, SeerrClient

VALID_MEDIA_TYPES = {"movie", "tv"}


def map_status(status_code: int | None) -> str:
    """Map an availability status code to its name, treating absence as unknown."""
    if status_code is None:
        return "unknown"
    return MediaStatus.get(status_code, f"unknown ({status_code})")


def clean_seasons(raw: dict) -> list[dict]:
    """Merge the TMDB season list with the instance's per-season availability."""
    # mediaInfo.seasons is a different shape from the top-level seasons array and is
    # keyed by seasonNumber, so it is looked up rather than zipped positionally: the
    # two arrays can disagree about which seasons exist.
    media_info = raw.get("mediaInfo") or {}
    status_by_season_number = {
        season["seasonNumber"]: season.get("status")
        for season in media_info.get("seasons", [])
    }

    seasons = []
    for season in raw.get("seasons", []):
        season_number = season.get("seasonNumber")
        # Season 0 holds specials, which are not requested as regular seasons.
        if season_number == 0:
            continue
        seasons.append(
            {
                "season_number": season_number,
                "name": season.get("name", ""),
                "episode_count": season.get("episodeCount"),
                "air_date": season.get("airDate", ""),
                "status": map_status(status_by_season_number.get(season_number)),
            }
        )
    return seasons


def clean_response(raw: dict, media_type: str) -> dict:
    """Reduce a TMDB media detail response to the fields the assistant needs."""
    if media_type == "movie":
        cleaned: dict = {
            "id": raw.get("id"),
            "title": raw.get("title", ""),
            "overview": raw.get("overview", ""),
            "release_date": raw.get("releaseDate", ""),
            "vote_average": raw.get("voteAverage"),
            "genres": [genre["name"] for genre in raw.get("genres", [])],
            "runtime": raw.get("runtime"),
        }
    else:
        cleaned = {
            "id": raw.get("id"),
            "title": raw.get("name", ""),
            "overview": raw.get("overview", ""),
            "first_air_date": raw.get("firstAirDate", ""),
            "vote_average": raw.get("voteAverage"),
            "genres": [genre["name"] for genre in raw.get("genres", [])],
            "seasons": clean_seasons(raw),
        }
        # TMDB returns episodeRunTime as a list, unlike the scalar movie runtime, so
        # it is reshaped to a single integer under a distinct key: keeping it as
        # "runtime" would make that key's type depend on media_type and force callers
        # to branch, while an empty list is omitted rather than emitted as null.
        episode_runtime = raw.get("episodeRunTime") or []
        if episode_runtime:
            cleaned["episode_runtime"] = episode_runtime[0]

    # An absent mediaInfo means the instance has never seen this title, so its
    # availability is unknown rather than a specific status.
    media_info = raw.get("mediaInfo") or {}
    cleaned["status"] = map_status(media_info.get("status"))
    return cleaned


KNOWN_PARAMS = {"media_type", "media_id"}


def main() -> None:
    params = json.load(sys.stdin)
    unknown = set(params) - KNOWN_PARAMS
    if unknown:
        print(f"Unknown parameters: {', '.join(sorted(unknown))}", file=sys.stderr)
        sys.exit(1)

    media_type = params.get("media_type")
    if media_type not in VALID_MEDIA_TYPES:
        print(
            f"Error: invalid media_type {media_type!r}. "
            f"Must be one of: {', '.join(sorted(VALID_MEDIA_TYPES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    # media_id is interpolated into the request path, so reject anything that is
    # not an integer rather than letting a string rewrite the endpoint.
    media_id = params.get("media_id")
    if not isinstance(media_id, int):
        print("Error: media_id must be an integer.", file=sys.stderr)
        sys.exit(1)

    client = SeerrClient.from_config()
    raw = client.get(f"/api/v1/{media_type}/{media_id}")
    json.dump(clean_response(raw, media_type), sys.stdout)


main()
