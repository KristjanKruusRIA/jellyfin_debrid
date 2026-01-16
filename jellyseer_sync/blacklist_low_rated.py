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
        min_imdb_score: float = 5.0,
        dry_run: bool = False
    ):
        self.jellyseerr_url = jellyseerr_url.rstrip('/')
        self.jellyseerr_api_key = jellyseerr_api_key
        self.user_id = user_id
        self.min_imdb_score = min_imdb_score
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
        sort_by: str = "vote_average.desc",
        max_pages: int = 50
    ) -> List[Dict]:
        """Fetch movies from Jellyseerr discover endpoint"""
        print(f"Fetching movies from Jellyseerr discover...")
        print(f"Filters: genre={genre}, year>={year_gte}, vote_avg>={vote_avg_gte}, vote_count>={vote_count_gte}")
        
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
        """Get movie ratings including IMDb score"""
        try:
            response = self.session.get(
                f"{self.jellyseerr_url}/api/v1/movie/{tmdb_id}/ratingscombined"
            )
            response.raise_for_status()
            return response.json()
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

    def add_to_blacklist(self, tmdb_id: int, title: str, imdb_score: float) -> bool:
        """Add a movie to Jellyseerr blacklist"""
        if self.dry_run:
            print(f"[DRY RUN] Would blacklist: {title} (TMDB: {tmdb_id}, IMDb: {imdb_score})")
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
        """Process movies and blacklist those with low IMDb scores"""
        print(f"\nProcessing {len(movies)} movies...")
        print(f"IMDb score threshold: < {self.min_imdb_score}")
        print(f"Dry run mode: {self.dry_run}\n")
        
        success_count = 0
        skip_count = 0
        no_score_count = 0
        above_threshold_count = 0
        error_count = 0
        
        for idx, movie in enumerate(movies, 1):
            tmdb_id = movie.get('id')
            title = movie.get('title', 'Unknown')
            
            if not tmdb_id:
                print(f"[{idx}/{len(movies)}] ✗ Skipping '{title}': No TMDB ID")
                skip_count += 1
                continue
            
            # Skip if already blacklisted
            if tmdb_id in existing_blacklist:
                skip_count += 1
                continue
            
            # Get movie ratings to fetch IMDb score
            print(f"[{idx}/{len(movies)}] Checking: {title}...", end=" ")
            ratings = self.get_movie_ratings(tmdb_id)
            
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
            
            # Rate limiting
            time.sleep(0.3)
        
        print("\n" + "="*60)
        print("Processing Summary:")
        print(f"  Total movies processed: {len(movies)}")
        print(f"  Blacklisted (IMDb < {self.min_imdb_score}): {success_count}")
        print(f"  Above threshold: {above_threshold_count}")
        print(f"  No IMDb score available: {no_score_count}")
        print(f"  Already blacklisted: {skip_count}")
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
        default=5.0,
        help='Minimum IMDb score threshold (default: 5.0)'
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
        dry_run=args.dry_run
    )
    
    # Fetch movies from discover
    movies = processor.get_discover_movies(
        genre=args.genre,
        year_gte=args.year_gte,
        year_lte=args.year_lte,
        vote_avg_gte=args.vote_avg_gte,
        vote_count_gte=args.vote_count_gte,
        sort_by=args.sort_by,
        max_pages=args.max_pages
    )
    
    if not movies:
        print("No movies found with the specified filters")
        sys.exit(1)
    
    # Get existing blacklist
    existing_blacklist = processor.get_existing_blacklist()
    
    # Process and blacklist low-rated movies
    processor.process_movies(movies, existing_blacklist)


if __name__ == '__main__':
    main()
