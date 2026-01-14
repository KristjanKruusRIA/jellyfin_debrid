# Download Manager for jellyfin_debrid
# Handles downloading best quality files from Real-Debrid to local storage

from base import *
from ui.ui_print import *
import os
import shutil
import requests
from pathlib import Path
import re

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

def download_file(url, filename, is_show=False):
    """
    Download a file from URL using requests library
    """
    try:
        # Sanitize filename to remove invalid characters
        filename = sanitize_filename(filename)
        ui_print(f"[downloader] Starting download: {filename}", debug="true")
        
        # Download to temp directory first
        temp_file = os.path.join(temp_download_path, filename)
        
        # Remove existing temp file if it exists
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
                ui_print(f"[downloader] Removed existing temp file", debug="true")
            except Exception as e:
                ui_print(f"[downloader] Warning: Could not remove existing temp file: {e}", debug="true")
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        with session.get(url, stream=True, timeout=30) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            
            chunk_size = 16 * 1024 * 1024  # 16MB chunks
            downloaded = 0
            last_reported = 0
            
            with open(temp_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size, decode_unicode=False):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if downloaded - last_reported >= 500 * 1024 * 1024:  # Report every 500MB
                            percent = (downloaded / total_size) * 100 if total_size > 0 else 0
                            downloaded_mb = downloaded / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            ui_print(f"[downloader] Progress: {downloaded_mb:.0f}MB / {total_mb:.0f}MB ({percent:.1f}%)", debug="true")
                            last_reported = downloaded
        
        # Get organized destination path
        dest_path = organize_path(filename, is_show)
        
        # Move from temp to final location
        ui_print(f"[downloader] Moving file to: {dest_path}", debug="true")
        shutil.move(temp_file, dest_path)
        
        file_size = os.path.getsize(dest_path) / (1024 * 1024)
        ui_print(f"[downloader] Download complete: {file_size:.0f}MB - {filename}", debug="true")
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

def select_best_file(files_list):
    """
    Select the best file from a list based on quality and size
    Returns the file with highest quality, and if tied, the largest file
    """
    if not files_list:
        return None
    
    # Score each file
    scored_files = []
    for file in files_list:
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

def organize_path(filename, is_show=False):
    """
    Create organized folder structure for the file
    Returns the full destination path
    """
    info = parse_filename(filename)
    
    if info['is_show'] or is_show:
        # TV Show: Shows/Show Name/Season XX/filename
        show_name = info['title'] if info['title'] else "Unknown Show"
        season_folder = f"Season {info['season']}" if info['season'] else "Season 01"
        
        dest_dir = os.path.join(shows_path, show_name, season_folder)
        os.makedirs(dest_dir, exist_ok=True)
        return os.path.join(dest_dir, filename)
    else:
        # Movie: Movies/Movie Name (Year)/filename
        movie_name = info['title'] if info['title'] else "Unknown Movie"
        if info['year']:
            folder_name = f"{movie_name} ({info['year']})"
        else:
            folder_name = movie_name
        
        dest_dir = os.path.join(movies_path, folder_name)
        os.makedirs(dest_dir, exist_ok=True)
        return os.path.join(dest_dir, filename)

def download_from_realdebrid(release, element):
    """
    Download files from a Real-Debrid release
    Automatically selects the best quality file and downloads it
    """
    try:
        if not hasattr(release, 'download') or not release.download:
            ui_print("[downloader] No download links available", debug="true")
            return False
        
        # Determine if this is a show or movie
        is_show = hasattr(element, 'show_id') or 'show' in str(type(element)).lower()
        
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
        
        # Select the best file
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
        
        # Download the file
        result = download_file(download_url, best_file['name'], is_show)
        
        return result is not None
        
    except Exception as e:
        ui_print(f"[downloader] Error in download_from_realdebrid: {str(e)}", debug="true")
        return False
