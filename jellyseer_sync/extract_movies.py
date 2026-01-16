"""
Helper script to extract watched movies from Trakt history JSON files
and prepare them for the blacklist sync script.
"""

import json
import os
from pathlib import Path

def extract_movies_from_history(history_dir: str = "watched") -> list:
    """Extract all unique watched movies from Trakt history files"""
    movies_dict = {}  # Use dict to deduplicate by TMDB ID
    
    history_dir_path = Path(history_dir)
    
    # Find all history JSON files
    history_files = sorted(history_dir_path.glob("history-*.json"))
    
    if not history_files:
        print(f"No history files found in {history_dir}")
        return []
    
    print(f"Found {len(history_files)} history files to process...")
    
    for history_file in history_files:
        print(f"Processing {history_file.name}...")
        
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Filter for movies only
            movie_count = 0
            for item in data:
                if item.get('type') == 'movie' and 'movie' in item:
                    movie_data = item['movie']
                    tmdb_id = movie_data.get('ids', {}).get('tmdb')
                    
                    if tmdb_id:
                        # Store by TMDB ID to deduplicate
                        if tmdb_id not in movies_dict:
                            movies_dict[tmdb_id] = {
                                'movie': movie_data,
                                'watched_at': item.get('watched_at')
                            }
                            movie_count += 1
            
            print(f"  Found {movie_count} new movies")
        
        except Exception as e:
            print(f"  Error processing {history_file.name}: {e}")
    
    # Convert dict back to list
    movies_list = list(movies_dict.values())
    
    print(f"\nTotal unique movies watched: {len(movies_list)}")
    
    return movies_list

def main():
    # Extract movies from history files
    movies = extract_movies_from_history("watched")
    
    if not movies:
        print("No movies found to export")
        return
    
    # Save to a single file for easy use
    output_file = "watched/movies-only.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(movies, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Saved {len(movies)} unique movies to {output_file}")
    print(f"\nNow run:")
    print(f"python trakt_blacklist_sync.py --mode json --json-file {output_file} --jellyseerr-api-key YOUR_API_KEY --user-id 1 --dry-run")

if __name__ == '__main__':
    main()
