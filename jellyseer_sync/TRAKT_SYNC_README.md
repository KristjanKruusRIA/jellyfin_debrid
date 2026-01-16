# Trakt to Jellyseerr Blacklist Sync

This script automatically syncs your watched movies from Trakt to Jellyseerr's blacklist, preventing already-watched content from being requested.

## Prerequisites

1. **Python 3.7+** with `requests` library:
   ```powershell
   pip install requests
   ```

2. **Jellyseerr API Key**: 
   - Log into Jellyseerr
   - Go to Settings → General
   - Copy your API Key

3. **Your Jellyseerr User ID**:
   - Go to Settings → Users
   - Click on your username
   - The user ID is in the URL: `/users/{id}`

4. **Trakt Data** (choose one):
   - **Option A**: Trakt JSON export (easier, recommended)
     - Go to https://trakt.tv/users/settings/data
     - Request your data export
     - Download the `watched.json` file
   
   - **Option B**: Trakt API credentials
     - Create an app at https://trakt.tv/oauth/applications
     - Get Client ID, Client Secret, and Access Token

## Usage

### Using Trakt JSON Export (Recommended)

1. Download your Trakt data export and save `watched.json`

2. **Dry run** (preview without making changes):
   ```powershell
   python trakt_blacklist_sync.py --mode json --json-file "path\to\watched.json" --jellyseerr-api-key "YOUR_API_KEY" --user-id YOUR_USER_ID --dry-run
   ```

3. **Actual sync**:
   ```powershell
   python trakt_blacklist_sync.py --mode json --json-file "path\to\watched.json" --jellyseerr-api-key "YOUR_API_KEY" --user-id YOUR_USER_ID
   ```

### Using Trakt API

```powershell
python trakt_blacklist_sync.py --mode api --trakt-client-id "YOUR_CLIENT_ID" --trakt-access-token "YOUR_ACCESS_TOKEN" --jellyseerr-api-key "YOUR_API_KEY" --user-id YOUR_USER_ID
```

### Full Example

```powershell
# Replace these values with your own
python trakt_blacklist_sync.py `
  --mode json `
  --json-file "C:\Downloads\trakt-watched.json" `
  --jellyseerr-url "http://localhost:5055" `
  --jellyseerr-api-key "abcdef123456" `
  --user-id 1 `
  --dry-run
```

## Options

| Option | Required | Description |
|--------|----------|-------------|
| `--mode` | Yes | Data source: `api` or `json` |
| `--jellyseerr-api-key` | Yes | Your Jellyseerr API key |
| `--user-id` | Yes | Your Jellyseerr user ID |
| `--json-file` | For JSON mode | Path to Trakt JSON export |
| `--trakt-client-id` | For API mode | Trakt API client ID |
| `--trakt-access-token` | For API mode | Trakt API access token |
| `--jellyseerr-url` | No | Jellyseerr URL (default: http://localhost:5055) |
| `--dry-run` | No | Preview changes without applying them |

## What It Does

1. ✓ Fetches your watched movies from Trakt (via API or JSON)
2. ✓ Gets your current Jellyseerr blacklist to avoid duplicates
3. ✓ Matches movies using TMDB IDs
4. ✓ For movies without TMDB IDs, attempts to find them using IMDB IDs
5. ✓ Adds watched movies to Jellyseerr's blacklist
6. ✓ Prevents already-watched movies from showing up in recommendations or being requested

## Output Example

```
Loading watched movies from watched.json...
Found 342 watched movies in JSON file

Starting sync of 342 watched movies...
Jellyseerr URL: http://localhost:5055
Dry run mode: True

Fetching existing blacklist from Jellyseerr...
Found 15 items already blacklisted

[1/342] Processing: The Matrix...
[DRY RUN] Would blacklist: The Matrix (TMDB: 603)
[2/342] ⊘ Skipping 'Inception': Already blacklisted
[3/342] Processing: Interstellar...
[DRY RUN] Would blacklist: Interstellar (TMDB: 157336)
...

============================================================
Sync Summary:
  Total watched movies: 342
  Successfully blacklisted: 310
  Skipped (already blacklisted or no TMDB ID): 28
  Errors: 4
============================================================
```

## Troubleshooting

### "Error: 'requests' library not found"
```powershell
pip install requests
```

### "Error 401: Unauthorized"
- Check that your Jellyseerr API key is correct
- Make sure you have the MANAGE_BLACKLIST permission

### "No TMDB ID found"
- Some older or obscure movies may not have TMDB IDs in Trakt
- These will be automatically skipped
- The script attempts to search by IMDB ID as a fallback

### Movies not being blocked in jellyfin_debrid
After running this script, blacklisted movies won't be automatically requested. However, if you want jellyfin_debrid to also skip them during processing, you may need to update its logic to check Jellyseerr's blacklist before processing requests.

## Scheduling Regular Syncs

To keep your blacklist in sync with Trakt, you can schedule this script to run periodically:

### Windows Task Scheduler
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., daily)
4. Action: Start a program
5. Program: `python`
6. Arguments: `E:\DockerDesktopWSL\jellyfin_debrid\trakt_blacklist_sync.py --mode json --json-file "path\to\watched.json" --jellyseerr-api-key "KEY" --user-id 1`

## Notes

- The script respects existing blacklist entries and won't create duplicates
- Use `--dry-run` first to preview what will be blacklisted
- You can run this script multiple times safely
- Only movies are synced (TV shows are not currently supported)
