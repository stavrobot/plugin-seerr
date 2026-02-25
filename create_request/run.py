#!/usr/bin/env -S uv run
# /// script
# dependencies = []
# ///

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


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
    json.dump(result, sys.stdout)


main()
