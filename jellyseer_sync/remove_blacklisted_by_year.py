"""
Jellyseerr Blacklist Removal Script

Remove blacklisted movies from a specific year range.

Usage:
    # Remove all movies from 2026
    python remove_blacklisted_by_year.py --jellyseerr-api-key YOUR_API_KEY --year 2026

    # Remove movies from multiple years
    python remove_blacklisted_by_year.py --jellyseerr-api-key YOUR_API_KEY --year-gte 2026 --year-lte 2027

    # Dry run to preview what would be removed
    python remove_blacklisted_by_year.py --jellyseerr-api-key YOUR_API_KEY --year 2026 --dry-run
"""

import argparse
import sys
import time
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install with: pip install requests")
    sys.exit(1)


class BlacklistRemover:
    def __init__(
        self, jellyseerr_url: str, jellyseerr_api_key: str, dry_run: bool = False
    ):
        self.jellyseerr_url = jellyseerr_url.rstrip("/")
        self.jellyseerr_api_key = jellyseerr_api_key
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update(
            {"X-Api-Key": jellyseerr_api_key, "Content-Type": "application/json"}
        )

    def get_blacklist(self) -> List[Dict]:
        """Get all blacklisted items from Jellyseerr"""
        print("Fetching blacklist from Jellyseerr...")
        blacklisted = []

        try:
            skip = 0
            take = 100

            while True:
                response = self.session.get(
                    f"{self.jellyseerr_url}/api/v1/blacklist",
                    params={"skip": skip, "take": take},
                )
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                blacklisted.extend(results)

                # Check if we have more pages
                page_info = data.get("pageInfo", {})
                current_page = page_info.get("page", 1)
                total_pages = page_info.get("pages", 1)

                if current_page >= total_pages:
                    break

                skip += take

            print(f"Found {len(blacklisted)} items in blacklist\n")
            return blacklisted
        except Exception as e:
            print(f"Error fetching blacklist: {e}")
            return []

    def get_movie_details(self, tmdb_id: int) -> Optional[Dict]:
        """Get movie details from Jellyseerr"""
        try:
            response = self.session.get(f"{self.jellyseerr_url}/api/v1/movie/{tmdb_id}")

            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            print(f"Error fetching movie {tmdb_id}: {e}")
            return None

    def remove_from_blacklist(
        self, tmdb_id: int, title: str, year: Optional[str]
    ) -> bool:
        """Remove a movie from Jellyseerr blacklist using TMDB ID"""
        year_str = f"({year})" if year else ""

        if self.dry_run:
            print(f"[DRY RUN] Would remove: {title} {year_str} (TMDB ID: {tmdb_id})")
            return True

        try:
            response = self.session.delete(
                f"{self.jellyseerr_url}/api/v1/blacklist/{tmdb_id}"
            )

            if response.status_code in [200, 204]:
                print(f"✓ Removed: {title} {year_str} (TMDB ID: {tmdb_id})")
                return True
            else:
                print(
                    f"✗ Failed to remove {title} {year_str}: {response.status_code} - {response.text}"
                )
                return False
        except Exception as e:
            print(f"✗ Error removing {title} {year_str}: {e}")
            return False

    def process_removals(
        self,
        year: Optional[int] = None,
        year_gte: Optional[int] = None,
        year_lte: Optional[int] = None,
    ):
        """Process and remove blacklisted movies matching year criteria"""
        blacklist = self.get_blacklist()

        if not blacklist:
            print("No items in blacklist")
            return

        # Filter by media type (movies only)
        movie_blacklist = [
            item for item in blacklist if item.get("mediaType") == "movie"
        ]
        print(f"Found {len(movie_blacklist)} movies in blacklist\n")

        if year is not None:
            year_gte = year
            year_lte = year

        removed_count = 0
        skipped_count = 0
        error_count = 0
        checked_count = 0

        print(
            f"Processing removals for year range: {year_gte or 'any'} - {year_lte or 'any'}"
        )
        print(f"Dry run mode: {self.dry_run}\n")

        for idx, item in enumerate(movie_blacklist, 1):
            item.get("id")  # This is the blacklist database ID
            tmdb_id = item.get("tmdbId")  # This is the TMDB movie ID
            title = item.get("title", "Unknown")

            # Progress indicator every 100 items
            if idx % 100 == 0:
                print(
                    f"Progress: {idx}/{len(movie_blacklist)} items checked, {removed_count} removed, {skipped_count} skipped..."
                )

            # Get movie details to check release year
            movie_details = self.get_movie_details(tmdb_id)

            if not movie_details:
                skipped_count += 1
                continue

            # Extract year from releaseDate
            release_date = movie_details.get("releaseDate", "")
            if release_date:
                movie_year = int(release_date.split("-")[0])
            else:
                skipped_count += 1
                continue

            checked_count += 1

            # Check if movie matches year criteria
            should_remove = True
            if year_gte is not None and movie_year < year_gte:
                should_remove = False
            if year_lte is not None and movie_year > year_lte:
                should_remove = False

            if should_remove:
                if self.remove_from_blacklist(tmdb_id, title, str(movie_year)):
                    removed_count += 1
                else:
                    error_count += 1

                # Small delay to avoid rate limiting
                if not self.dry_run:
                    time.sleep(0.1)
            else:
                skipped_count += 1

        print(f"\nFinished processing all {len(movie_blacklist)} items.")

        print("\n" + "=" * 60)
        print("REMOVAL SUMMARY")
        print("=" * 60)
        print(f"  Removed: {removed_count}")
        print(f"  Skipped (wrong year): {skipped_count}")
        print(f"  Errors: {error_count}")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Remove blacklisted movies by year from Jellyseerr",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Jellyseerr settings
    parser.add_argument(
        "--jellyseerr-url",
        default="http://192.168.1.169:5055",
        help="Jellyseerr URL (default: http://192.168.1.169:5055)",
    )
    parser.add_argument(
        "--jellyseerr-api-key", required=True, help="Jellyseerr API key"
    )

    # Year filters
    parser.add_argument("--year", type=int, help="Specific year to remove (e.g., 2026)")
    parser.add_argument(
        "--year-gte", type=int, help="Minimum release year to remove (e.g., 2026)"
    )
    parser.add_argument(
        "--year-lte", type=int, help="Maximum release year to remove (e.g., 2027)"
    )

    # Options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without actually removing",
    )

    args = parser.parse_args()

    # Validate year arguments
    if not args.year and not args.year_gte and not args.year_lte:
        parser.error(
            "At least one of --year, --year-gte, or --year-lte must be provided"
        )

    # Create processor instance
    processor = BlacklistRemover(
        jellyseerr_url=args.jellyseerr_url,
        jellyseerr_api_key=args.jellyseerr_api_key,
        dry_run=args.dry_run,
    )

    # Process removals
    processor.process_removals(
        year=args.year, year_gte=args.year_gte, year_lte=args.year_lte
    )


if __name__ == "__main__":
    main()
