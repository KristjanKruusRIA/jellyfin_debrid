# Download Manager for jellyfin_debrid
# Handles downloading best quality files from Real-Debrid to local storage

from base import *
from ui.ui_print import *
import os
import shutil
import requests
from pathlib import Path
import re
import time

# Download settings - use environment variable if available, otherwise default to E:\Media
download_path = os.environ.get('DOWNLOAD_PATH', r'E:\Media')
movies_path = os.path.join(download_path, "Movies")
shows_path = os.path.join(download_path, "Shows")

# Use Windows temp directory for downloading
# Files will be moved to the final location after download completes
temp_download_path = os.path.join(download_path, ".downloading")

# Ensure directories exist
os.makedirs(movies_path, exist_ok=True)
os.makedirs(shows_path, exist_ok=True)
os.makedirs(temp_download_path, exist_ok=True)

def sanitize_filename(filename):
    """
    Sanitize filename to remove invalid Windows characters
    """
    # Remove or replace invalid Windows filename characters: < > : " / \ | ? *
    # Also handle special patterns like ../ and ..\
    filename = re.sub(r'[<>:"|?*]', '', filename)
    filename = re.sub(r'[\/\\]+', '.', filename)  # Replace slashes with dots
    filename = re.sub(r'\.\.\.', '.', filename)  # Replace ... with .
    filename = re.sub(r'^\.\.', '', filename)  # Remove leading ..
    filename = filename.strip('. ')  # Remove leading/trailing dots and spaces
    
    # Ensure filename is not empty after sanitization
    if not filename:
        filename = "download"
    
    return filename

def download_file(url, filename, is_show=False, expected_size=None):
    """
    Download a file from URL using requests library

    expected_size: optional expected size (bytes). If provided, final file will be validated and discarded on large mismatch.
    """
    try:
        # Sanitize filename to remove invalid characters
        filename = sanitize_filename(filename)
        ui_print(f"[downloader] Starting download: {filename}", debug="true")
        
        # Download to temp directory first
        temp_file = os.path.join(temp_download_path, filename)
        
        # Remove existing temp file if it exists and is old (more than 1 hour old)
        if os.path.exists(temp_file):
            try:
                file_age = time.time() - os.path.getmtime(temp_file)
                if file_age > 3600:  # More than 1 hour old - abandoned download
                    os.remove(temp_file)
                    ui_print(f"[downloader] Removed old temp file", debug="true")
                # Otherwise skip removal - file is likely from current download
            except Exception as e:
                # If we can't remove it, just skip and let the new download overwrite
                pass
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        with session.get(url, stream=True, timeout=30) as response:
            # Add diagnostics: log status, content-length and content-type to help debug small or non-video downloads
            content_length = response.headers.get('content-length', 'None')
            content_type = response.headers.get('content-type', 'None')
            ui_print(f"[downloader] HTTP status: {response.status_code}; Content-Length: {content_length}; Content-Type: {content_type}", debug="true")
            response.raise_for_status()
            total_size = int(content_length) if content_length and content_length.isdigit() else 0
            
            chunk_size = 16 * 1024 * 1024  # 16MB chunks
            downloaded = 0
            last_reported = 0
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size, decode_unicode=False):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Report progress every 500MB
                        if downloaded - last_reported >= 500 * 1024 * 1024:
                            percent = (downloaded / total_size) * 100 if total_size > 0 else 0
                            downloaded_mb = downloaded / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            ui_print(f"[downloader] Progress: {downloaded_mb:.0f}MB / {total_mb:.0f}MB ({percent:.1f}%)", debug="true")
                            last_reported = downloaded

        # If nothing was downloaded, avoid moving an empty file and surface diagnostics
        if downloaded == 0:
            ui_print(f"[downloader] Error: downloaded 0 bytes for URL: {url} (status: {response.status_code}); not moving temp file", debug="true")
            # Try to capture small response for debugging
            try:
                snippet = response.content[:2048]
                ui_print(f"[downloader] Response snippet (first 2KB): {snippet!r}", debug="true")
            except Exception:
                pass
            # Clean up temp file if it exists
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            return None

        # If the downloaded file is suspiciously small, capture diagnostics (headers and snippet)
        if downloaded < 5 * 1024 * 1024:  # less than 5MB
            ui_print(f"[downloader] Warning: small download size ({downloaded} bytes). Content-Type: {content_type}", debug="true")
            try:
                snippet = open(temp_file, 'rb').read(2048)
                ui_print(f"[downloader] Small response snippet (first 2KB): {snippet!r}", debug="true")
            except Exception:
                pass

            # If content-type is not a video type, warn
            if not (isinstance(content_type, str) and content_type.startswith('video')):
                ui_print(f"[downloader] Warning: content-type does not look like a video file, might be an error page", debug="true")

            # If it's a video but too small compared to expected streaming sizes, try a single ranged retry
            if isinstance(content_type, str) and content_type.startswith('video'):
                ui_print("[downloader] Attempting ranged retry (Range: bytes=0-) to fetch a larger file", debug="true")
                try:
                    # Remove previous partial temp file
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    # Use Range header to request full content from start
                    ranged_headers = {'Range': 'bytes=0-'}
                    with session.get(url, stream=True, timeout=60, headers=ranged_headers, allow_redirects=True) as resp2:
                        ui_print(f"[downloader] Range HTTP status: {resp2.status_code}; Content-Length: {resp2.headers.get('content-length', 'None')}; Content-Range: {resp2.headers.get('content-range', 'None')}", debug="true")
                        if resp2.status_code in (200, 206):
                            downloaded2 = 0
                            with open(temp_file, 'wb') as f2:
                                for chunk in resp2.iter_content(chunk_size=chunk_size, decode_unicode=False):
                                    if chunk:
                                        f2.write(chunk)
                                        downloaded2 += len(chunk)
                            ui_print(f"[downloader] Ranged request downloaded {downloaded2} bytes", debug="true")
                            downloaded = downloaded2
                        else:
                            ui_print("[downloader] Ranged request returned non-206/200 status, skipping", debug="true")
                except Exception as e:
                    ui_print(f"[downloader] Ranged retry failed: {e}", debug="true")

        # Size validation against expected_size (if provided)
        try:
            if expected_size and expected_size > 0:
                # expected_size is in bytes
                diff = abs(downloaded - expected_size)
                threshold = max(int(expected_size * 0.05), 10 * 1024 * 1024)  # 5% or 10MB
                if diff > threshold:
                    ui_print(f"[downloader] Error: downloaded size ({downloaded} bytes) differs from expected ({expected_size} bytes) by more than threshold ({threshold} bytes). Discarding file.", debug="true")
                    # Clean up temp file
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except Exception:
                            pass
                    return None
        except Exception as e:
            ui_print(f"[downloader] Error during size validation: {e}", debug="true")

        # Get organized destination path (no element parameter here since this is generic download_file)
        dest_path = organize_path(filename, is_show)
        
        # Move from temp to final location
        ui_print(f"[downloader] Moving file to: {dest_path}", debug="true")
        shutil.move(temp_file, dest_path)
        
        file_size_bytes = os.path.getsize(dest_path)
        file_size_mb = file_size_bytes / (1024 * 1024)
        ui_print(f"[downloader] Download complete: {file_size_mb:.2f}MB ({file_size_bytes} bytes) - {filename}", debug="true")
        return dest_path
        
    except Exception as e:
        ui_print(f"[downloader] Error downloading {filename}: {str(e)}", debug="true")
        # Clean up temp file if it exists
        if 'temp_file' in locals() and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        return None

def parse_filename(filename):
    """Parse filename to extract metadata"""
    # Check if it's a TV show or movie
    is_show = bool(regex.search(r'S[0-9]+E[0-9]+', filename, regex.I))
    
    info = {
        'is_show': is_show,
        'title': '',
        'year': '',
        'season': '',
        'episode': '',
        'quality': '',
        'size': 0
    }
    
    # Extract year
    year_match = regex.search(r'(19|20)\d{2}', filename)
    if year_match:
        info['year'] = year_match.group()
    
    # Extract season and episode for shows
    if is_show:
        se_match = regex.search(r'S(\d+)E(\d+)', filename, regex.I)
        if se_match:
            info['season'] = se_match.group(1).zfill(2)
            info['episode'] = se_match.group(2).zfill(2)
        
        # Extract show title (everything before season/episode)
        title_match = regex.search(r'^(.+?)[\.\s]+S\d+E\d+', filename, regex.I)
        if title_match:
            info['title'] = title_match.group(1).replace('.', ' ').replace('_', ' ').strip()
    else:
        # Extract movie title (everything before year or quality markers)
        title_match = regex.search(r'^(.+?)[\.\s]+(19|20)\d{2}', filename)
        if title_match:
            info['title'] = title_match.group(1).replace('.', ' ').replace('_', ' ').strip()
        else:
            # Fallback: extract before quality markers
            title_match = regex.search(r'^(.+?)[\.\s]+(720p|1080p|2160p|4K)', filename, regex.I)
            if title_match:
                info['title'] = title_match.group(1).replace('.', ' ').replace('_', ' ').strip()
    
    # Extract quality
    quality_match = regex.search(r'(2160p|4K|1080p|720p|480p)', filename, regex.I)
    if quality_match:
        info['quality'] = quality_match.group(1).upper()
        if info['quality'] == '2160P':
            info['quality'] = '4K'
    
    return info

def get_quality_score(quality_str):
    """Convert quality string to numerical score for comparison"""
    quality_map = {
        '4K': 4000,
        '2160P': 4000,
        '1080P': 1080,
        '720P': 720,
        '480P': 480,
        '': 0
    }
    return quality_map.get(quality_str.upper(), 0)

def is_video_file(filename):
    """
    Check if a file is a video file based on extension or video-like patterns.
    Handles both traditional extensions and extensionless HTTP filenames.
    """
    video_extensions = [
        '.mkv', '.mp4', '.avi', '.mov', '.flv', '.wmv', '.webm',
        '.m4v', '.mpg', '.mpeg', '.3gp', '.ogv', '.ts', '.m2ts',
        '.mts', '.m2v', '.m4p', '.mxf', '.asf', '.rm', '.rmvb',
        '.vob', '.f4v', '.divx'
    ]
    filename_lower = filename.lower()
    
    # Check for traditional video extensions
    if any(filename_lower.endswith(ext) for ext in video_extensions):
        return True
    
    # Handle extensionless filenames from HTTP sources (e.g., AIOStreams)
    # Check for quality indicators (1080p, 720p, 4K, 2160p, etc.)
    import regex
    if regex.search(r'(2160p|4K|1080p|720p|480p|BluRay|WEB-?DL|HDTV|WEBRip)', filename, regex.I):
        # Likely a video file based on quality/source markers
        return True
    
    return False

def is_archive_or_unsafe(filename):
    """
    Check if a file is an archive or potentially unsafe
    """
    unsafe_extensions = [
        '.rar', '.zip', '.7z', '.tar', '.gz', '.bz2', '.iso',
        '.exe', '.bat', '.cmd', '.com', '.scr', '.txt', '.doc',
        '.docx', '.pdf', '.nfo', '.sfv', '.md5', '.sub', '.srt',
        '.ass', '.ssa', '.vtt', '.m3u'
    ]
    filename_lower = filename.lower()
    return any(filename_lower.endswith(ext) for ext in unsafe_extensions)

def select_best_file(files_list):
    """
    Select the best file from a list based on quality and size
    Returns the file with highest quality, and if tied, the largest file
    Only considers video files, excludes archives and unsafe files
    """
    if not files_list:
        return None
    
    # Filter to only video files and exclude archives/unsafe files
    filtered_files = []
    for file in files_list:
        filename = file.get('name', '')
        if is_video_file(filename) and not is_archive_or_unsafe(filename):
            filtered_files.append(file)
    
    if not filtered_files:
        # No video files found - try to warn about this
        available_files = [f.get('name', '') for f in files_list[:5]]
        ui_print(f"[downloader] Warning: No video files found in release. Available files: {available_files}", debug="true")
        return None
    
    # Score each file
    scored_files = []
    for file in filtered_files:
        info = parse_filename(file.get('name', ''))
        quality_score = get_quality_score(info['quality'])
        size = file.get('size', 0)
        
        scored_files.append({
            'file': file,
            'quality_score': quality_score,
            'size': size,
            'info': info
        })
    
    # Sort by quality (descending), then by size (descending)
    scored_files.sort(key=lambda x: (x['quality_score'], x['size']), reverse=True)
    
    best = scored_files[0]
    ui_print(f"[downloader] Selected best file: {best['file'].get('name')} "
             f"(Quality: {best['info']['quality']}, Size: {best['size'] / (1024**3):.2f} GB)", 
             debug="true")
    
    return best['file']

def organize_path(filename, is_show=False, element=None):
    """
    Create organized folder structure for the file
    Returns the full destination path
    
    element: optional media element with title/year metadata
    """
    info = parse_filename(filename)
    
    # Try to get metadata from element first, fallback to parsed filename
    if element:
        if hasattr(element, 'type'):
            element_type = element.type
            # Determine if show based on element type
            if element_type in ['show', 'season', 'episode']:
                is_show = True
    
    if info['is_show'] or is_show:
        # TV Show: Shows/Show Name/Season XX/filename
        if element and hasattr(element, 'title'):
            show_name = element.title
        elif element and hasattr(element, 'parentTitle'):
            show_name = element.parentTitle
        elif element and hasattr(element, 'grandparentTitle'):
            show_name = element.grandparentTitle
        else:
            show_name = info['title'] if info['title'] else "Unknown Show"
        
        # Sanitize show name to remove invalid Windows characters (like colons)
        show_name = sanitize_filename(show_name)
        
        # Get season number from element or filename
        season_num = None
        if element and hasattr(element, 'parentIndex'):
            season_num = str(element.parentIndex).zfill(2)
        elif element and hasattr(element, 'index') and hasattr(element, 'type') and element.type == 'season':
            season_num = str(element.index).zfill(2)
        elif info['season']:
            season_num = info['season']
        
        season_folder = f"Season {season_num}" if season_num else "Season 01"
        
        dest_dir = os.path.join(shows_path, show_name, season_folder)
        os.makedirs(dest_dir, exist_ok=True)
        return os.path.join(dest_dir, filename)
    else:
        # Movie: Movies/Movie Name (Year)/filename
        if element and hasattr(element, 'title'):
            movie_name = element.title
        else:
            movie_name = info['title'] if info['title'] else "Unknown Movie"
        
        # Get year from element or filename
        year = None
        if element and hasattr(element, 'year'):
            year = str(element.year)
        elif info['year']:
            year = info['year']
        
        if year:
            folder_name = f"{movie_name} ({year})"
        else:
            folder_name = movie_name
        
        # Sanitize folder name to remove invalid Windows characters (like colons)
        folder_name = sanitize_filename(folder_name)
        
        dest_dir = os.path.join(movies_path, folder_name)
        os.makedirs(dest_dir, exist_ok=True)
        return os.path.join(dest_dir, filename)

def download_from_realdebrid(release, element):
    """
    Download files from a Real-Debrid release
    For shows: downloads all episode files from the same quality tier
    For movies: downloads the best quality file
    """
    try:
        if not hasattr(release, 'download') or not release.download:
            ui_print("[downloader] No download links available", debug="true")
            return False
        
        # Determine if this is a show or movie based on element type
        is_show = getattr(element, 'type', '') == 'show' or getattr(element, 'type', '') == 'season' or getattr(element, 'type', '') == 'episode'
        ui_print(f"[downloader] Processing element type: {getattr(element, 'type', 'unknown')} (is_show: {is_show})", debug="true")
        
        # Get all files from the release
        files_to_download = []
        
        if hasattr(release, 'files') and release.files:
            # If we have file objects with metadata
            for version in release.files:
                if hasattr(version, 'files'):
                    for file in version.files:
                        if file.wanted and not file.unwanted:
                            files_to_download.append({
                                'name': file.name,
                                'size': file.size * 1000000000,  # Convert GB back to bytes
                                'id': file.id,
                                'url': None  # Will be populated from download links
                            })
        
        if not files_to_download and release.download:
            # Fallback: use actual filenames from RD or release title
            filenames = getattr(release, 'filenames', [])
            for i, link in enumerate(release.download):
                # Use actual filename from RD if available, otherwise fall back to release title
                filename = filenames[i] if i < len(filenames) else release.title
                files_to_download.append({
                    'name': filename,
                    'size': getattr(release, 'size', 0) * 1000000000,
                    'id': i,
                    'url': link
                })
        
        if is_show:
            # For TV shows: download ALL episode files from the highest quality tier
            # First, find the highest quality among video files
            filtered_files = []
            for file in files_to_download:
                filename = file.get('name', '')
                if is_video_file(filename) and not is_archive_or_unsafe(filename):
                    filtered_files.append(file)
            
            if not filtered_files:
                ui_print("[downloader] No suitable video files found to download", debug="true")
                return False
            
            # Score all files and find the highest quality
            max_quality_score = -1
            for file in filtered_files:
                info = parse_filename(file.get('name', ''))
                quality_score = get_quality_score(info['quality'])
                max_quality_score = max(max_quality_score, quality_score)
            
            # Download all files with the highest quality score
            files_to_download_final = []
            for file in filtered_files:
                info = parse_filename(file.get('name', ''))
                quality_score = get_quality_score(info['quality'])
                if quality_score == max_quality_score:
                    files_to_download_final.append(file)
                    ui_print(f"[downloader] Queuing file: {file.get('name')} "
                             f"(Quality: {info['quality']}, Size: {file.get('size', 0) / (1024**3):.2f} GB)", 
                             debug="true")
            
            # Download all selected files
            all_success = True
            for file in files_to_download_final:
                # Get download URL
                if file.get('url'):
                    download_url = file['url']
                elif len(release.download) > 0:
                    # Use the first download link if URL not specified
                    download_url = release.download[0]
                else:
                    ui_print("[downloader] No download URL available", debug="true")
                    all_success = False
                    continue
                
                # Download the file - we use custom path organization in download_from_realdebrid
                # So we'll organize the path here before calling download_file
                dest_path = organize_path(file['name'], is_show, element)
                # Extract just the filename from dest_path for download_file
                result = download_file(download_url, file['name'], is_show, expected_size=file.get('size'))
                if result is None:
                    all_success = False
            
            return all_success
        else:
            # For movies: select and download only the best file
            best_file = select_best_file(files_to_download)
            
            if not best_file:
                ui_print("[downloader] No suitable file found to download", debug="true")
                return False
            
            # Get download URL
            if best_file['url']:
                download_url = best_file['url']
            elif len(release.download) > 0:
                # Use the first download link if URL not specified
                download_url = release.download[0]
            else:
                ui_print("[downloader] No download URL available", debug="true")
                return False
            
            # Pre-calculate the organized path so the file goes to the right folder
            dest_path = organize_path(best_file['name'], is_show, element)
            
            # Download the file
            result = download_file(download_url, best_file['name'], is_show, expected_size=best_file.get('size'))
            
            return result is not None
        
    except Exception as e:
        ui_print(f"[downloader] Error in download_from_realdebrid: {str(e)}", debug="true")
        return False
