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
    json.dump(result, sys.stdout)


main()
