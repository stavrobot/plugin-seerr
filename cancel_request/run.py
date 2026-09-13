#!/usr/bin/env -S uv run
# /// script
# dependencies = []
# ///

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seerr_client import SeerrClient

KNOWN_PARAMS = {"request_id"}


def main() -> None:
    params = json.load(sys.stdin)
    unknown = set(params) - KNOWN_PARAMS
    if unknown:
        print(f"Unknown parameters: {', '.join(sorted(unknown))}", file=sys.stderr)
        sys.exit(1)
    # request_id is interpolated into the request path, so reject anything that is
    # not an integer rather than letting a string rewrite the endpoint.
    request_id = params.get("request_id")
    if not isinstance(request_id, int):
        print("Error: request_id must be an integer.", file=sys.stderr)
        sys.exit(1)

    client = SeerrClient.from_config()
    # A successful delete returns 204 with an empty body, which the client's
    # delete() method already discards, so there is nothing to parse here.
    client.delete(f"/api/v1/request/{request_id}")

    json.dump({"deleted_request_id": request_id}, sys.stdout)


main()
