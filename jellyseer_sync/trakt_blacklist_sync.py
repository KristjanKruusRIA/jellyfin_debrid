"""
Trakt to Jellyseerr Blacklist Sync Script

This script syncs your Trakt watched movies to Jellyseerr's blacklist to prevent
already-watched content from being requested.

Supports two modes:
1. Trakt API (requires API credentials)
2. Trakt JSON export files (from https://trakt.tv/users/settings/data)

Usage:
    # Using Trakt API
    python trakt_blacklist_sync.py --mode api --trakt-client-id YOUR_CLIENT_ID --trakt-client-secret YOUR_SECRET

    # Using Trakt JSON export
    python trakt_blacklist_sync.py --mode json --json-file path/to/watched.json

    # Dry run (preview without making changes)
    python trakt_blacklist_sync.py --mode json --json-file watched.json --dry-run
"""

import argparse
import json
import sys
from typing import List, Dict, Optional
from datetime import datetime

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install with: pip install requests")
    sys.exit(1)


class TraktBlacklistSync:
    def __init__(
        self,
        jellyseerr_url: str,
        jellyseerr_api_key: str,
        user_id: int,
        dry_run: bool = False
    ):
        self.jellyseerr_url = jellyseerr_url.rstrip('/')
        self.jellyseerr_api_key = jellyseerr_api_key
        self.user_id = user_id
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            'X-Api-Key': jellyseerr_api_key,
            'Content-Type': 'application/json'
        })

    def get_trakt_watched_from_api(
        self,
        client_id: str,
        client_secret: str,
        access_token: Optional[str] = None
    ) -> List[Dict]:
        """Fetch watched movies from Trakt API"""
        print("Fetching watched movies from Trakt API...")
        
        # If no access token provided, we'll need to implement OAuth flow
        if not access_token:
            print("Error: Access token required for Trakt API")
            print("Get your access token from: https://trakt.tv/oauth/applications")
            return []
        
        headers = {
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': client_id,
            'Authorization': f'Bearer {access_token}'
        }
        
        try:
            response = requests.get(
                'https://api.trakt.tv/sync/watched/movies',
                headers=headers
            )
            response.raise_for_status()
            watched = response.json()
            print(f"Found {len(watched)} watched movies on Trakt")
            return watched
        except requests.exceptions.RequestException as e:
            print(f"Error fetching from Trakt API: {e}")
            return []

    def get_trakt_watched_from_json(self, json_file: str) -> List[Dict]:
        """Load watched movies from Trakt JSON export"""
        print(f"Loading watched movies from {json_file}...")
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Trakt export format has different structures
            # Handle both "watched" export and full history export
            movies = []
            
            if isinstance(data, dict):
                # Full export format
                if 'movies' in data:
                    movies = data['movies']
                elif 'watched' in data and 'movies' in data['watched']:
                    movies = data['watched']['movies']
            elif isinstance(data, list):
                # Direct list of watched items
                movies = [item for item in data if item.get('movie')]
            
            print(f"Found {len(movies)} watched movies in JSON file")
            return movies
        except FileNotFoundError:
            print(f"Error: File not found: {json_file}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON file: {e}")
            return []

    def get_tmdb_id_from_trakt_item(self, item: Dict) -> Optional[int]:
        """Extract TMDB ID from Trakt item"""
        # API format
        if 'movie' in item and 'ids' in item['movie']:
            return item['movie']['ids'].get('tmdb')
        
        # Direct format
        if 'ids' in item:
            return item['ids'].get('tmdb')
        
        return None

    def get_movie_title_from_trakt_item(self, item: Dict) -> str:
        """Extract movie title from Trakt item"""
        if 'movie' in item:
            return item['movie'].get('title', 'Unknown')
        return item.get('title', 'Unknown')

    def search_tmdb_by_imdb(self, imdb_id: str) -> Optional[int]:
        """Search TMDB for a movie by IMDB ID using Jellyseerr's API"""
        try:
            # Use Jellyseerr's built-in TMDB search
            response = self.session.get(
                f"{self.jellyseerr_url}/api/v1/search",
                params={'query': imdb_id}
            )
            response.raise_for_status()
            results = response.json()
            
            if results.get('results'):
                for result in results['results']:
                    if result.get('mediaType') == 'movie':
                        return result.get('id')
        except Exception as e:
            print(f"Error searching TMDB for IMDB {imdb_id}: {e}")
        
        return None

    def get_existing_blacklist(self) -> set:
        """Get currently blacklisted TMDB IDs from Jellyseerr"""
        print("Fetching existing blacklist from Jellyseerr...")
        blacklisted = set()
        
        try:
            skip = 0
            take = 100
            
            while True:
                response = self.session.get(
                    f"{self.jellyseerr_url}/api/v1/blacklist",
                    params={'skip': skip, 'take': take}
                )
                response.raise_for_status()
                data = response.json()
                
                for item in data.get('results', []):
                    blacklisted.add(item['tmdbId'])
                
                # Check if we have more pages
                page_info = data.get('pageInfo', {})
                current_page = page_info.get('page', 1)
                total_pages = page_info.get('pages', 1)
                
                if current_page >= total_pages:
                    break
                
                skip += take
            
            print(f"Found {len(blacklisted)} items already blacklisted")
            return blacklisted
        except Exception as e:
            print(f"Error fetching blacklist: {e}")
            return set()

    def add_to_blacklist(self, tmdb_id: int, title: str) -> bool:
        """Add a movie to Jellyseerr blacklist"""
        if self.dry_run:
            print(f"[DRY RUN] Would blacklist: {title} (TMDB: {tmdb_id})")
            return True
        
        try:
            payload = {
                'tmdbId': tmdb_id,
                'mediaType': 'movie',
                'title': title,
                'user': self.user_id
            }
            
            response = self.session.post(
                f"{self.jellyseerr_url}/api/v1/blacklist",
                json=payload
            )
            
            if response.status_code == 201:
                print(f"✓ Blacklisted: {title} (TMDB: {tmdb_id})")
                return True
            elif response.status_code == 412:
                print(f"⊘ Already blacklisted: {title} (TMDB: {tmdb_id})")
                return True
            else:
                print(f"✗ Failed to blacklist {title}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"✗ Error blacklisting {title}: {e}")
            return False

    def sync_watched_movies(self, watched_movies: List[Dict]):
        """Sync watched movies to Jellyseerr blacklist"""
        if not watched_movies:
            print("No watched movies to sync")
            return
        
        print(f"\nStarting sync of {len(watched_movies)} watched movies...")
        print(f"Jellyseerr URL: {self.jellyseerr_url}")
        print(f"Dry run mode: {self.dry_run}\n")
        
        # Get existing blacklist to avoid duplicates
        existing_blacklist = self.get_existing_blacklist()
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for idx, item in enumerate(watched_movies, 1):
            tmdb_id = self.get_tmdb_id_from_trakt_item(item)
            title = self.get_movie_title_from_trakt_item(item)
            
            if not tmdb_id:
                # Try to get TMDB ID from IMDB ID
                if 'movie' in item and 'ids' in item['movie']:
                    imdb_id = item['movie']['ids'].get('imdb')
                elif 'ids' in item:
                    imdb_id = item['ids'].get('imdb')
                else:
                    imdb_id = None
                
                if imdb_id:
                    print(f"[{idx}/{len(watched_movies)}] No TMDB ID for '{title}', searching by IMDB ID...")
                    tmdb_id = self.search_tmdb_by_imdb(imdb_id)
                
                if not tmdb_id:
                    print(f"[{idx}/{len(watched_movies)}] ✗ Skipping '{title}': No TMDB ID found")
                    skip_count += 1
                    continue
            
            # Skip if already blacklisted
            if tmdb_id in existing_blacklist:
                print(f"[{idx}/{len(watched_movies)}] ⊘ Skipping '{title}': Already blacklisted")
                skip_count += 1
                continue
            
            # Add to blacklist
            print(f"[{idx}/{len(watched_movies)}] Processing: {title}...")
            if self.add_to_blacklist(tmdb_id, title):
                success_count += 1
            else:
                error_count += 1
        
        print("\n" + "="*60)
        print("Sync Summary:")
        print(f"  Total watched movies: {len(watched_movies)}")
        print(f"  Successfully blacklisted: {success_count}")
        print(f"  Skipped (already blacklisted or no TMDB ID): {skip_count}")
        print(f"  Errors: {error_count}")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Sync Trakt watched movies to Jellyseerr blacklist',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Jellyseerr settings
    parser.add_argument(
        '--jellyseerr-url',
        default='http://localhost:5055',
        help='Jellyseerr URL (default: http://localhost:5055)'
    )
    parser.add_argument(
        '--jellyseerr-api-key',
        required=True,
        help='Jellyseerr API key (get from Settings > General)'
    )
    parser.add_argument(
        '--user-id',
        type=int,
        required=True,
        help='Jellyseerr user ID to associate blacklisted items with'
    )
    
    # Trakt data source
    parser.add_argument(
        '--mode',
        choices=['api', 'json'],
        required=True,
        help='Data source: "api" for Trakt API or "json" for exported JSON file'
    )
    
    # Trakt API settings
    parser.add_argument(
        '--trakt-client-id',
        help='Trakt API client ID (required for API mode)'
    )
    parser.add_argument(
        '--trakt-client-secret',
        help='Trakt API client secret (required for API mode)'
    )
    parser.add_argument(
        '--trakt-access-token',
        help='Trakt API access token (required for API mode)'
    )
    
    # JSON file settings
    parser.add_argument(
        '--json-file',
        help='Path to Trakt JSON export file (required for JSON mode)'
    )
    
    # Options
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without actually blacklisting anything'
    )
    
    args = parser.parse_args()
    
    # Validate mode-specific arguments
    if args.mode == 'api':
        if not args.trakt_client_id or not args.trakt_access_token:
            parser.error("API mode requires --trakt-client-id and --trakt-access-token")
    elif args.mode == 'json':
        if not args.json_file:
            parser.error("JSON mode requires --json-file")
    
    # Create sync instance
    sync = TraktBlacklistSync(
        jellyseerr_url=args.jellyseerr_url,
        jellyseerr_api_key=args.jellyseerr_api_key,
        user_id=args.user_id,
        dry_run=args.dry_run
    )
    
    # Get watched movies based on mode
    watched_movies = []
    if args.mode == 'api':
        watched_movies = sync.get_trakt_watched_from_api(
            client_id=args.trakt_client_id,
            client_secret=args.trakt_client_secret,
            access_token=args.trakt_access_token
        )
    elif args.mode == 'json':
        watched_movies = sync.get_trakt_watched_from_json(args.json_file)
    
    # Perform sync
    if watched_movies:
        sync.sync_watched_movies(watched_movies)
    else:
        print("No watched movies found to sync")
        sys.exit(1)


if __name__ == '__main__':
    main()
