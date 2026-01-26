"""
Jellyseerr Low-Rated Movie Blacklist Script

This script fetches movies from Jellyseerr's discover endpoint based on your filters
and automatically blacklists any movie with an IMDb critics score below a threshold.

Usage:
    # Blacklist movies with IMDb score < 5.0 (default)
    python blacklist_low_rated.py --jellyseerr-api-key YOUR_API_KEY --user-id 1

    # Custom IMDb score threshold
    python blacklist_low_rated.py --jellyseerr-api-key YOUR_API_KEY --user-id 1 --min-score 6.0

    # Specify custom discover filters
    python blacklist_low_rated.py --jellyseerr-api-key YOUR_API_KEY --user-id 1 --genre 27 --year-gte 2020

    # Dry run
    python blacklist_low_rated.py --jellyseerr-api-key YOUR_API_KEY --user-id 1 --dry-run
"""

import argparse
import sys
import time
from typing import List, Dict, Optional

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install with: pip install requests")
    sys.exit(1)


class LowRatedBlacklist:
    def __init__(
        self,
        jellyseerr_url: str,
        jellyseerr_api_key: str,
        user_id: int,
        min_imdb_score: Optional[float] = None,
        blacklist_no_ratings: bool = False,
        min_runtime: Optional[int] = None,
        blacklist_countries: Optional[List[str]] = None,
        skip_blacklist_check: bool = False,
        dry_run: bool = False
    ):
        self.jellyseerr_url = jellyseerr_url.rstrip('/')
        self.jellyseerr_api_key = jellyseerr_api_key
        self.user_id = user_id
        self.min_imdb_score = min_imdb_score
        self.blacklist_no_ratings = blacklist_no_ratings
        self.min_runtime = min_runtime
        self.blacklist_countries = [c.upper() for c in blacklist_countries] if blacklist_countries else []
        self.skip_blacklist_check = skip_blacklist_check
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            'X-Api-Key': jellyseerr_api_key,
            'Content-Type': 'application/json'
        })

    def get_discover_movies(
        self,
        genre: Optional[int] = None,
        year_gte: Optional[int] = None,
        year_lte: Optional[int] = None,
        vote_avg_gte: Optional[float] = None,
        vote_count_gte: Optional[int] = None,
        vote_count_lte: Optional[int] = None,
        sort_by: str = "vote_average.desc",
        max_pages: int = 50
    ) -> List[Dict]:
        """Fetch movies from Jellyseerr discover endpoint"""
        print(f"Fetching movies from Jellyseerr discover...")
        year_filter = f"year>={year_gte}" if year_gte else ""
        if year_lte:
            year_filter += f"-{year_lte}" if year_filter else f"year<={year_lte}"
        year_filter = year_filter or "all years"
        vote_count_filter = f"vote_count>={vote_count_gte}" if vote_count_gte else ""
        if vote_count_lte:
            vote_count_filter += f"-{vote_count_lte}" if vote_count_filter else f"vote_count<={vote_count_lte}"
        vote_count_filter = vote_count_filter or "any"
        print(f"Filters: genre={genre}, {year_filter}, vote_avg>={vote_avg_gte}, {vote_count_filter}")
        
        all_movies = []
        page = 1
        
        while page <= max_pages:
            try:
                params = {
                    'page': page,
                    'sortBy': sort_by
                }
                
                if genre:
                    params['genre'] = genre
                if year_gte:
                    params['primaryReleaseDateGte'] = f"{year_gte}-1-1"
                if year_lte:
                    params['primaryReleaseDateLte'] = f"{year_lte}-12-31"
                if vote_avg_gte:
                    params['voteAverageGte'] = vote_avg_gte
                if vote_count_gte:
                    params['voteCountGte'] = vote_count_gte
                if vote_count_lte:
                    params['voteCountLte'] = vote_count_lte
                
                response = self.session.get(
                    f"{self.jellyseerr_url}/api/v1/discover/movies",
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                results = data.get('results', [])
                if not results:
                    break
                
                all_movies.extend(results)
                print(f"  Page {page}: Found {len(results)} movies (total: {len(all_movies)})")
                
                # Check if there are more pages
                total_pages = data.get('totalPages', page)
                if page >= total_pages:
                    break
                
                page += 1
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break
        
        print(f"\nTotal movies found: {len(all_movies)}")
        return all_movies

    def get_movie_ratings(self, tmdb_id: int) -> Optional[Dict]:
        """Get movie ratings including IMDb score. Returns 'NOT_FOUND' for 404 errors."""
        try:
            response = self.session.get(
                f"{self.jellyseerr_url}/api/v1/movie/{tmdb_id}/ratingscombined"
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return 'NOT_FOUND'
            print(f"Error fetching ratings for TMDB {tmdb_id}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching ratings for TMDB {tmdb_id}: {e}")
            return None

    def get_imdb_score(self, ratings: Dict) -> Optional[float]:
        """Extract IMDb critics score from ratings"""
        if not ratings:
            return None
        
        imdb_data = ratings.get('imdb', {})
        if isinstance(imdb_data, dict):
            return imdb_data.get('criticsScore')
        
        return None

    def get_movie_details(self, tmdb_id: int) -> Optional[Dict]:
        """Get full movie details including runtime"""
        try:
            response = self.session.get(
                f"{self.jellyseerr_url}/api/v1/movie/{tmdb_id}"
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching movie details for TMDB {tmdb_id}: {e}")
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
            
            print(f"Found {len(blacklisted)} items already blacklisted\n")
            return blacklisted
        except Exception as e:
            print(f"Error fetching blacklist: {e}")
            return set()

    def add_to_blacklist(self, tmdb_id: int, title: str, imdb_score: Optional[float]) -> bool:
        """Add a movie to Jellyseerr blacklist"""
        if self.dry_run:
            score_str = f"IMDb: {imdb_score}" if imdb_score is not None else "No ratings"
            print(f"[DRY RUN] Would blacklist: {title} (TMDB: {tmdb_id}, {score_str})")
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
                print(f"✓ Blacklisted: {title} (TMDB: {tmdb_id}, IMDb: {imdb_score})")
                return True
            elif response.status_code == 412:
                print(f"⊘ Already blacklisted: {title} (TMDB: {tmdb_id}, IMDb: {imdb_score})")
                return True
            else:
                print(f"✗ Failed to blacklist {title}: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"✗ Error blacklisting {title}: {e}")
            return False

    def process_movies(
        self,
        movies: List[Dict],
        existing_blacklist: set
    ):
        """Process movies and blacklist those with low IMDb scores or short runtime"""
        print(f"\nProcessing {len(movies)} movies...")
        if self.min_imdb_score is not None:
            print(f"IMDb score threshold: < {self.min_imdb_score}")
        if self.min_runtime:
            print(f"Runtime threshold: < {self.min_runtime} minutes")
        if self.blacklist_countries:
            print(f"Blacklisted countries: {', '.join(self.blacklist_countries)}")
        print(f"Dry run mode: {self.dry_run}\n")
        
        success_count = 0
        skip_count = 0
        no_score_count = 0
        no_ratings_count = 0
        above_threshold_count = 0
        runtime_blacklist_count = 0
        country_blacklist_count = 0
        error_count = 0
        
        for idx, movie in enumerate(movies, 1):
            tmdb_id = movie.get('id')
            title = movie.get('title', 'Unknown')
            
            if not tmdb_id:
                print(f"[{idx}/{len(movies)}] ✗ Skipping '{title}': No TMDB ID")
                skip_count += 1
                continue
            
            # Get movie details for runtime/country checks if needed
            movie_details = None
            if self.min_runtime or self.blacklist_countries:
                movie_details = self.get_movie_details(tmdb_id)
                if movie_details:
                    # Check runtime
                    if self.min_runtime:
                        runtime = movie_details.get('runtime', 0)
                        if runtime > 0 and runtime < self.min_runtime:
                            print(f"[{idx}/{len(movies)}] {title}: Runtime {runtime}min < {self.min_runtime}min → BLACKLISTING")
                            if self.add_to_blacklist(tmdb_id, title, None):
                                runtime_blacklist_count += 1
                            else:
                                error_count += 1
                            continue
                    
                    # Check production countries
                    if self.blacklist_countries:
                        production_countries = movie_details.get('productionCountries', [])
                        country_codes = [pc.get('iso_3166_1', '').upper() for pc in production_countries]
                        blacklisted_country = next((c for c in country_codes if c in self.blacklist_countries), None)
                        if blacklisted_country:
                            country_name = next((pc.get('name', blacklisted_country) for pc in production_countries if pc.get('iso_3166_1', '').upper() == blacklisted_country), blacklisted_country)
                            print(f"[{idx}/{len(movies)}] {title}: Country '{country_name}' is blacklisted → BLACKLISTING")
                            if self.add_to_blacklist(tmdb_id, title, None):
                                country_blacklist_count += 1
                            else:
                                error_count += 1
                            continue
            
            # Only check IMDb score if threshold is set
            if self.min_imdb_score is not None:
                # Get movie ratings to fetch IMDb score
                print(f"[{idx}/{len(movies)}] Checking: {title}...", end=" ")
                ratings = self.get_movie_ratings(tmdb_id)
                
                # Handle movies without ratings endpoint (404)
                if ratings == 'NOT_FOUND':
                    if self.blacklist_no_ratings:
                        print("No ratings available → BLACKLISTING")
                        if self.add_to_blacklist(tmdb_id, title, None):
                            success_count += 1
                        else:
                            error_count += 1
                    else:
                        print("⊘ No ratings available")
                        no_ratings_count += 1
                    continue
                
                if not ratings:
                    print("✗ Failed to fetch ratings")
                    error_count += 1
                    continue
                
                imdb_score = self.get_imdb_score(ratings)
                
                if imdb_score is None:
                    print(f"⊘ No IMDb score")
                    no_score_count += 1
                    continue
                
                print(f"IMDb: {imdb_score}", end=" ")
                
                if imdb_score < self.min_imdb_score:
                    print("→ BLACKLISTING")
                    if self.add_to_blacklist(tmdb_id, title, imdb_score):
                        success_count += 1
                    else:
                        error_count += 1
                else:
                    print("→ Above threshold, skipping")
                    above_threshold_count += 1
            else:
                # No IMDb filtering requested
                print(f"[{idx}/{len(movies)}] Processed: {title}")
                skip_count += 1
            
            # Rate limiting
            time.sleep(0.3)
        
        print("\n" + "="*60)
        print("Processing Summary:")
        print(f"  Total movies checked: {len(movies)}")
        if self.min_imdb_score is not None:
            print(f"  Blacklisted (IMDb < {self.min_imdb_score}): {success_count}")
        if self.min_runtime:
            print(f"  Blacklisted (runtime < {self.min_runtime}min): {runtime_blacklist_count}")
        if self.blacklist_countries:
            print(f"  Blacklisted (production country): {country_blacklist_count}")
        if self.min_imdb_score is not None:
            print(f"  Above threshold: {above_threshold_count}")
            print(f"  No IMDb score available: {no_score_count}")
            print(f"  No ratings endpoint (404): {no_ratings_count}")
        print(f"  Skipped: {skip_count}")
        print(f"  Errors: {error_count}")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Blacklist low-rated movies from Jellyseerr discover',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Jellyseerr settings
    parser.add_argument(
        '--jellyseerr-url',
        default='http://192.168.1.169:5055',
        help='Jellyseerr URL (default: http://192.168.1.169:5055)'
    )
    parser.add_argument(
        '--jellyseerr-api-key',
        required=True,
        help='Jellyseerr API key'
    )
    parser.add_argument(
        '--user-id',
        type=int,
        required=True,
        help='Jellyseerr user ID'
    )
    
    # IMDb score threshold
    parser.add_argument(
        '--min-score',
        type=float,
        default=None,
        help='Minimum IMDb score threshold (optional, only checks IMDb if specified)'
    )
    
    # Discover filters
    parser.add_argument(
        '--genre',
        type=int,
        help='Genre ID (e.g., 27 for horror)'
    )
    parser.add_argument(
        '--year-gte',
        type=int,
        help='Minimum release year (e.g., 2020)'
    )
    parser.add_argument(
        '--year-lte',
        type=int,
        help='Maximum release year (e.g., 2024)'
    )
    parser.add_argument(
        '--vote-avg-gte',
        type=float,
        help='Minimum TMDB vote average (e.g., 5.0)'
    )
    parser.add_argument(
        '--vote-count-gte',
        type=int,
        help='Minimum TMDB vote count (e.g., 51)'
    )
    parser.add_argument(
        '--vote-count-lte',
        type=int,
        help='Maximum TMDB vote count (e.g., 1000)'
    )
    parser.add_argument(
        '--min-runtime',
        type=int,
        help='Minimum acceptable runtime - blacklist movies with runtime less than this value in minutes (e.g., 80)'
    )
    parser.add_argument(
        '--blacklist-countries',
        nargs='+',
        help='Production country codes to blacklist (e.g., IN for India, CN for China). Separate multiple with spaces.'
    )
    parser.add_argument(
        '--sort-by',
        default='vote_average.desc',
        help='Sort order (default: vote_average.desc)'
    )
    parser.add_argument(
        '--max-pages',
        type=int,
        default=50,
        help='Maximum pages to fetch (default: 50)'
    )
    
    # Options
    parser.add_argument(
        '--blacklist-no-ratings',
        action='store_true',
        help='Blacklist movies that have no ratings endpoint (404)'
    )
    parser.add_argument(
        '--skip-blacklist-check',
        action='store_true',
        help='Skip fetching existing blacklist (faster, relies on API 412 for duplicates)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without actually blacklisting'
    )
    
    args = parser.parse_args()
    
    # Create processor instance
    processor = LowRatedBlacklist(
        jellyseerr_url=args.jellyseerr_url,
        jellyseerr_api_key=args.jellyseerr_api_key,
        user_id=args.user_id,
        min_imdb_score=args.min_score,
        blacklist_no_ratings=args.blacklist_no_ratings,
        min_runtime=args.min_runtime,
        blacklist_countries=args.blacklist_countries,
        skip_blacklist_check=args.skip_blacklist_check,
        dry_run=args.dry_run
    )
    
    # Fetch movies from discover
    movies = processor.get_discover_movies(
        genre=args.genre,
        year_gte=args.year_gte,
        year_lte=args.year_lte,
        vote_avg_gte=args.vote_avg_gte,
        vote_count_gte=args.vote_count_gte,
        vote_count_lte=args.vote_count_lte,
        sort_by=args.sort_by,
        max_pages=args.max_pages
    )
    
    if not movies:
        print("No movies found with the specified filters")
        sys.exit(1)
    
    # Get existing blacklist (skip if requested for performance)
    if args.skip_blacklist_check:
        print("Skipping blacklist check (--skip-blacklist-check enabled)")
        print("API will return 412 for already blacklisted movies\n")
        existing_blacklist = set()
        movies_to_check = movies
    else:
        existing_blacklist = processor.get_existing_blacklist()
        
        # Filter out already blacklisted movies
        movies_to_check = [m for m in movies if m.get('id') not in existing_blacklist]
        print(f"\nAfter filtering blacklisted movies: {len(movies_to_check)} movies to check")
        print(f"Skipped {len(movies) - len(movies_to_check)} already blacklisted movies\n")
        
        if not movies_to_check:
            print("All discovered movies are already blacklisted!")
            sys.exit(0)
    
    # Process and blacklist low-rated movies
    processor.process_movies(movies_to_check, existing_blacklist)


if __name__ == '__main__':
    main()
