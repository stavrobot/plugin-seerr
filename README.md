# seerr-plugin

A [Stavrobot](https://github.com/stavrobot) plugin for managing media requests via [seerr](https://github.com/seerr-team/seerr).

## Tools

- **search_media** — Search for movies, TV shows, and people.
- **discover_media** — Discover trending, upcoming, and popular movies and TV shows, with filtering by genre, network, studio, language, year, rating, and runtime.
- **get_media_details** — Get details for a movie or TV show, including which seasons exist and which are already available.
- **create_request** — Request a movie or TV show to be added to the library.
- **get_requests** — List media requests and their statuses.
- **cancel_request** — Cancel one of your own pending requests.

## Installation

Ask Stavrobot to install the plugin:

> Install the plugin https://github.com/stavrobot/plugin-seerr.git

Stavrobot will ask you to configure the plugin with your seerr instance URL and your Jellyfin or Emby credentials:

- `api_url` — the base URL of your seerr instance, for example `http://localhost:5055`.
- `jellyfin_username` — your Jellyfin or Emby username.
- `jellyfin_password` — your Jellyfin or Emby password.

The plugin signs in with those credentials and keeps a session cookie for subsequent requests. Only Jellyfin and Emby sign-in are supported. Instances configured for Plex sign-in, or for local email and password sign-in, will not work.

Your Jellyfin or Emby password is stored in `config.json` in plain text on the host running Stavrobot.

The plugin acts as that user, so requests follow that account's quota and approval rules and may stay pending until an administrator approves them.

## License

AGPL-3.0
