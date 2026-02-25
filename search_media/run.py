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


def main() -> None:
    config = json.loads(Path("../config.json").read_text())
    api_url = config["api_url"].rstrip("/")
    api_key = config["api_key"]

    params = json.load(sys.stdin)
    query = params["query"]
    page = params.get("page", 1)

    query_string = urllib.parse.urlencode({"query": query, "page": page})
    path = f"/api/v1/search?{query_string}"

    result = call_seerr_api(api_url, api_key, path)
    json.dump(result, sys.stdout)


main()
