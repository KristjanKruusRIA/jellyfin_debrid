#import modules
from base import *
from ui.ui_print import *
import releases
import downloader

# Try to import rd_downloader for existing torrents
try:
    import rd_downloader
    has_rd_downloader = True
except:
    has_rd_downloader = False
    ui_print("[realdebrid] rd_downloader module not available", ui_settings.debug)

# (required) Name of the Debrid service
name = "Real Debrid"
short = "RD"
# (required) Authentification of the Debrid service, can be oauth aswell. Create a setting for the required variables in the ui.settings_list. For an oauth example check the trakt authentification.
api_key = ""
# Define Variables
session = requests.Session()
errors = [
    [202," action already done"],
    [400," bad Request (see error message)"],
    [403," permission denied (infringing torrent or account locked or not premium)"],
    [503," service unavailable (see error message)"],
    [404," wrong parameter (invalid file id(s)) / unknown ressource (invalid id)"],
    ]
def setup(cls, new=False):
    from debrid.services import setup
    setup(cls,new)

# Error Log
def logerror(response, context=None):
    if not response.status_code in [200,201,204]:
        desc = ""
        for error in errors:
            if response.status_code == error[0]:
                desc = error[1]
        extra = (" Context: " + str(context)) if context else ""
        ui_print("[realdebrid] error: (" + str(response.status_code) + desc + ") " + str(response.content) + extra, debug=ui_settings.debug)
    if response.status_code == 401:
        ui_print("[realdebrid] error: (401 unauthorized): realdebrid api key does not seem to work. check your realdebrid settings." + (" Context: " + str(context) if context else ""))
    if response.status_code == 403:
        ui_print("[realdebrid] error: (403 unauthorized): You may have attempted to add an infringing torrent or your realdebrid account is locked or you dont have premium." + (" Context: " + str(context) if context else ""))

# Get Function
def get(url, context=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36','authorization': 'Bearer ' + api_key}
    response = None
    try:
        response = session.get(url, headers=headers)
        logerror(response, context)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print("[realdebrid] error: (json exception): " + str(e), debug=ui_settings.debug)
        response = None
    return response

# Post Function
def post(url, data, context=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36','authorization': 'Bearer ' + api_key}
    response = None
    try:
        response = session.post(url, headers=headers, data=data)
        logerror(response, context)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        if hasattr(response,"status_code"):
            if response.status_code >= 300:
                ui_print("[realdebrid] error: (json exception): " + str(e) + (" Context: " + str(context) if context else ""), debug=ui_settings.debug)
        else:
            ui_print("[realdebrid] error: (json exception): " + str(e) + (" Context: " + str(context) if context else ""), debug=ui_settings.debug)
        response = None
    return response

# Delete Function
def delete(url, context=None):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36','authorization': 'Bearer ' + api_key}
    try:
        resp = requests.delete(url, headers=headers)
        if resp.status_code >= 300:
            logerror(resp, context)
        # time.sleep(1)
    except Exception as e:
        ui_print("[realdebrid] error: (delete exception): " + str(e) + (" Context: " + str(context) if context else ""), debug=ui_settings.debug)
        None
    return None

# Object classes
class file:
    def __init__(self, id, name, size, wanted_list, unwanted_list):
        self.id = id
        self.name = name
        self.size = size / 1000000000
        self.match = ''
        wanted = False
        unwanted = False
        for key, wanted_pattern in wanted_list:
            if wanted_pattern.search(self.name):
                wanted = True
                self.match = key
                break

        if not wanted:
            for key, unwanted_pattern in unwanted_list:
                if unwanted_pattern.search(self.name) or self.name.endswith('.exe') or self.name.endswith('.txt'):
                    unwanted = True
                    break

        self.wanted = wanted
        self.unwanted = unwanted

    def __eq__(self, other):
        return self.id == other.id

class version:
    def __init__(self, files):
        self.files = files
        self.needed = 0
        self.wanted = 0
        self.unwanted = 0
        self.size = 0
        for file in self.files:
            self.size += file.size
            if file.wanted:
                self.wanted += 1
            if file.unwanted:
                self.unwanted += 1

# (required) Download Function.
def download(element, stream=True, query='', force=False):
    cached = element.Releases
    if query == '':
        query = element.deviation()
    wanted = [query]
    if not isinstance(element, releases.release):
        wanted = element.files()
    for release in cached[:]:
        # if release matches query
        if regex.match(query, release.title,regex.I) or force:
            if stream:
                release.size = 0
                # Check if files are available, if not we need to add magnet to get file list
                if not release.files or all(not hasattr(v, 'files') or len(v.files) == 0 for v in release.files):
                    ui_print('[realdebrid] no file info available (nodownloadlinks enabled), adding magnet to RD...', ui_settings.debug)
                    # Add magnet to get file information
                    try:
                        context = "release: '" + str(release.title) + "' | item: '" + str(element.query()) + "'"
                        response = post('https://api.real-debrid.com/rest/1.0/torrents/addMagnet',{'magnet': str(release.download[0])}, context=context)
                        torrent_id = str(response.id)
                        ui_print('[realdebrid] magnet added, torrent_id: ' + torrent_id, ui_settings.debug)
                        
                        # Get torrent info to see available files
                        import time
                        time.sleep(2)  # Wait for RD to process
                        response = get('https://api.real-debrid.com/rest/1.0/torrents/info/' + torrent_id, context=context)
                        ui_print('[realdebrid] torrent status: ' + response.status, ui_settings.debug)
                        
                        # Select all files in the torrent
                        if hasattr(response, 'files') and len(response.files) > 0:
                            file_ids = [str(f.id) for f in response.files]
                            ui_print('[realdebrid] selecting all ' + str(len(file_ids)) + ' files...', ui_settings.debug)
                            post('https://api.real-debrid.com/rest/1.0/torrents/selectFiles/' + torrent_id, 
                                 {'files': ','.join(file_ids)}, context=context)
                            
                            # Wait a bit more and get updated info
                            time.sleep(2)
                            response = get('https://api.real-debrid.com/rest/1.0/torrents/info/' + torrent_id, context=context)
                            ui_print('[realdebrid] updated status: ' + response.status, ui_settings.debug)
                            
                            # Get unrestricted links and download
                            if hasattr(response, 'links') and len(response.links) > 0:
                                ui_print('[realdebrid] getting unrestricted links for ' + str(len(response.links)) + ' files...', ui_settings.debug)
                                unrestricted_links = []
                                filenames = []
                                for link in response.links:
                                    try:
                                        unres_response = post('https://api.real-debrid.com/rest/1.0/unrestrict/link',{'link': link}, context=context)
                                        if hasattr(unres_response, 'download'):
                                            unrestricted_links.append(unres_response.download)
                                            # Store actual filename from RD response
                                            if hasattr(unres_response, 'filename'):
                                                filenames.append(unres_response.filename)
                                            else:
                                                filenames.append(release.title)
                                    except:
                                        continue
                                
                                if len(unrestricted_links) > 0:
                                    release.download = unrestricted_links
                                    release.filenames = filenames  # Store actual filenames
                                    ui_print('[realdebrid] downloading from cached RD torrent: ' + release.title)
                                    download_success = downloader.download_from_realdebrid(release, element)
                                    if download_success:
                                        ui_print('[realdebrid] successfully downloaded file to local storage')
                                        # Trigger Jellyfin library refresh after successful download
                                        try:
                                            from content.services import jellyfin
                                            jellyfin.library.refresh(element)
                                        except Exception as e:
                                            ui_print(f'[realdebrid] could not refresh jellyfin libraries: {str(e)}', debug=True)
                                        return True
                            else:
                                ui_print('[realdebrid] no links available yet, status: ' + response.status, ui_settings.debug)
                        
                        # Delete the torrent since we couldn't use it or already processed it
                        delete('https://api.real-debrid.com/rest/1.0/torrents/delete/' + torrent_id, context=context)
                    except Exception as e:
                        ui_print('[realdebrid] error processing torrent: ' + str(e), ui_settings.debug)
                        import traceback
                        ui_print('[realdebrid] traceback: ' + traceback.format_exc(), ui_settings.debug)
                    
                    continue  # Skip to next release instead of trying version.files
                    
                for version in release.files:
                    if hasattr(version, 'files'):
                        if len(version.files) > 0 and version.wanted > len(wanted) / 2 or force:
                            cached_ids = []
                            for file in version.files:
                                cached_ids += [file.id]
                            # post magnet to real debrid
                            try:
                                context = "release: '" + str(release.title) + "' | item: '" + str(element.query()) + "'"
                                response = post('https://api.real-debrid.com/rest/1.0/torrents/addMagnet',{'magnet': str(release.download[0])}, context=context)
                                torrent_id = str(response.id)
                            except:
                                ui_print('[realdebrid] error: could not add magnet for release: ' + release.title, ui_settings.debug)
                                continue
                            response = post('https://api.real-debrid.com/rest/1.0/torrents/selectFiles/' + torrent_id,{'files': str(','.join(cached_ids))}, context=context)
                            response = get('https://api.real-debrid.com/rest/1.0/torrents/info/' + torrent_id, context=context)
                            actual_title = ""
                            if len(response.links) == len(cached_ids):
                                actual_title = response.filename
                                release.download = response.links
                            else:
                                if response.status in ["queued","magnet_convesion","downloading","uploading"]:
                                    if hasattr(element,"version"):
                                        debrid_uncached = True
                                        for i,rule in enumerate(element.version.rules):
                                            if (rule[0] == "cache status") and (rule[1] == 'requirement' or rule[1] == 'preference') and (rule[2] == "cached"):
                                                debrid_uncached = False
                                        if debrid_uncached:
                                            import debrid as db
                                            release.files = version.files
                                            db.downloading += [element.query() + ' [' + element.version.name + ']']
                                            ui_print('[realdebrid] adding uncached release: ' + release.title)
                                            return True
                                else:
                                    ui_print('[realdebrid] error: selecting this cached file combination returned a .rar archive - trying a different file combination.', ui_settings.debug)
                                    delete('https://api.real-debrid.com/rest/1.0/torrents/delete/' + torrent_id, context=context)
                                    continue
                            if len(release.download) > 0:
                                # Get unrestricted download links
                                unrestricted_links = []
                                for link in release.download:
                                    try:
                                        response = post('https://api.real-debrid.com/rest/1.0/unrestrict/link',{'link': link}, context=context)
                                        if hasattr(response, 'download'):
                                            unrestricted_links.append(response.download)
                                    except:
                                        break
                                
                                # Update release with unrestricted links
                                if len(unrestricted_links) > 0:
                                    release.download = unrestricted_links
                                
                                release.files = version.files
                                ui_print('[realdebrid] adding cached release: ' + release.title)
                                if not actual_title == "":
                                    release.title = actual_title
                                
                                # Download the best file locally
                                try:
                                    ui_print('[realdebrid] initiating local download of best quality file...')
                                    download_success = downloader.download_from_realdebrid(release, element)
                                    if download_success:
                                        ui_print('[realdebrid] successfully downloaded file to local storage')
                                    else:
                                        ui_print('[realdebrid] warning: download to local storage failed, but release was added')
                                except Exception as e:
                                    ui_print(f'[realdebrid] error during download: {str(e)}', ui_settings.debug)
                                
                                return True
                ui_print('[realdebrid] error: no streamable version could be selected for release: ' + release.title)
                return False
            else:
                try:
                    context = "release: '" + str(release.title) + "' | item: '" + str(element.query()) + "'"
                    response = post('https://api.real-debrid.com/rest/1.0/torrents/addMagnet',{'magnet': release.download[0]}, context=context)
                    time.sleep(0.1)
                    post('https://api.real-debrid.com/rest/1.0/torrents/selectFiles/' + str(response.id),{'files': 'all'}, context=context)
                    ui_print('[realdebrid] adding uncached release: ' + release.title)
                    return True
                except:
                    continue
        else:
            ui_print('[realdebrid] error: rejecting release: "' + release.title + '" because it doesnt match the allowed deviation', ui_settings.debug)
    return False

# (required) Check Function
def check(element, force=False):
    if force:
        wanted = ['.*']
    else:
        wanted = element.files()
    unwanted = releases.sort.unwanted
    wanted_patterns = list(zip(wanted, [regex.compile(r'(' + key + ')', regex.IGNORECASE) for key in wanted]))
    unwanted_patterns = list(zip(unwanted, [regex.compile(r'(' + key + ')', regex.IGNORECASE) for key in unwanted]))

    hashes = []
    for release in element.Releases[:]:
        if len(release.hash) == 40:
            hashes += [release.hash]
        else:
            ui_print("[realdebrid] error (missing torrent hash): ignoring release '" + release.title + "' ",ui_settings.debug)
            element.Releases.remove(release)
    if len(hashes) > 0:
        response = get('https://api.real-debrid.com/rest/1.0/torrents/instantAvailability/' + '/'.join(hashes), context=element.query())
        ui_print("[realdebrid] checking and sorting all release files ...", ui_settings.debug)
        for release in element.Releases:
            release.files = []
            release_hash = release.hash.lower()
            if hasattr(response, release_hash):
                response_attr = getattr(response, release_hash)
                if hasattr(response_attr, 'rd'):
                    rd_attr = response_attr.rd
                    if len(rd_attr) > 0:
                        for cashed_version in rd_attr:
                            version_files = []
                            for file_ in cashed_version.__dict__:
                                file_attr = getattr(cashed_version, file_)
                                debrid_file = file(file_, file_attr.filename, file_attr.filesize, wanted_patterns, unwanted_patterns)
                                version_files.append(debrid_file)
                            release.files += [version(version_files), ]
                        # select cached version that has the most needed, most wanted, least unwanted files, highest quality and largest size
                        release.files.sort(key=lambda x: len(x.files), reverse=True)
                        release.files.sort(key=lambda x: x.size, reverse=True)  # Sort by size (larger is better)
                        release.files.sort(key=lambda x: x.wanted, reverse=True)
                        release.files.sort(key=lambda x: x.unwanted, reverse=False)
                        release.wanted = release.files[0].wanted
                        release.unwanted = release.files[0].unwanted
                        release.size = release.files[0].size
                        release.cached += ['RD']
                        continue
        
        # Sort releases by quality and size to prioritize best quality
        ui_print("[realdebrid] sorting releases by quality and size...", ui_settings.debug)
        element.Releases.sort(key=lambda x: getattr(x, 'size', 0), reverse=True)  # Larger files first
        ui_print("done",ui_settings.debug)

# Diagnostic: get basic account info (useful to debug 403 permissions)
def account_info():
    try:
        response = get('https://api.real-debrid.com/rest/1.0/user')
        if response is None:
            ui_print('[realdebrid] error: unable to fetch account info', ui_settings.debug)
            return None
        ui_print('[realdebrid] account info: ' + str(response.__dict__), ui_settings.debug)
        return response
    except Exception as e:
        ui_print('[realdebrid] error: fetching account info: ' + str(e), ui_settings.debug)
        return None

# Diagnostic: list torrents (helps verify that RD accepted an uncached torrent and its download status)
def torrents_list(limit=50):
    try:
        response = get('https://api.real-debrid.com/rest/1.0/torrents?limit=' + str(limit), context='torrents_list')
        if response is None:
            ui_print('[realdebrid] error: unable to fetch torrents list', ui_settings.debug)
            return None
        # Response is a list of torrent objects
        try:
            summary = [{'id': t.id, 'status': t.status, 'filename': getattr(t, 'filename', None), 'files': len(getattr(t, 'files', [])) if hasattr(t, 'files') else None} for t in response]
        except Exception:
            summary = str(response)
        ui_print('[realdebrid] torrents: ' + str(summary), ui_settings.debug)
        return response
    except Exception as e:
        ui_print('[realdebrid] error: fetching torrents list: ' + str(e), ui_settings.debug)
        return None
