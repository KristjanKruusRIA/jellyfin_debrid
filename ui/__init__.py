from base import *

import content
import scraper
import releases
import debrid
from ui import ui_settings
from ui.ui_print import *
from settings import *

#import uvicorn

config_dir = ""
service_mode = False

class option:
    def __init__(self, name, cls, key):
        self.name = name
        self.cls = cls
        self.key = key

    def input(self):
        func = getattr(self.cls, self.key)
        func()

def ignored():
    back = False
    while not back:
        ui_cls('Options/Ignored Media/')
        if len(content.classes.ignore.ignored) == 0:
            library_services = content.classes.library()
            if len(library_services) == 0:
                print('No library collection service configured. Please configure a library service first.')
                time.sleep(3)
                return
            library = library_services[0]()
            if len(library) > 0:
                jellyseerr_requests = content.services.jellyseerr.requests()
                print('checking new content ...')
                for iterator in itertools.zip_longest([jellyseerr_requests]):
                    for element in iterator:
                        if hasattr(element, 'uncollected') and hasattr(element, 'watched'):
                            element.watched()
                            element.uncollected(library)
            print()
        print('0) Back')
        indices = []
        for index, element in enumerate(content.classes.ignore.ignored):
            print(str(index + 1) + ') ' + element.query())
            indices += [str(index + 1)]
        print()
        choice = input('Choose a media item that you want to remove from the ignored list: ')
        if choice in indices:
            print("Media item: " + content.classes.ignore.ignored[int(choice) - 1].query() + ' removed from ignored list.')
            content.classes.ignore.ignored[int(choice) - 1].unwatch()
            time.sleep(3)
        elif choice == '0':
            back = True
    options()

def scrape():
    ui_cls('Options/Scraper/')
    print('Press Enter to return to the main menu.')
    print()
    print("Please choose a version to scrape for: ")
    print()
    obj = releases.release('', '', '', [], 0, [])
    indices = []
    for index, version in enumerate(releases.sort.versions):
        print(str(index + 1) + ') ' + version[0] + (' (disabled)' if '\u0336' in version[0] else ''))
        indices += [str(index + 1)]
    print(str(index + 2) + ') Scrape without defining a version')
    indices += [str(index + 2)]
    print()
    choice = input("Choose a version: ")
    if choice in indices and not choice == str(index + 2):
        obj.version = releases.sort.version(releases.sort.versions[int(choice) - 1][0],
                                            releases.sort.versions[int(choice) - 1][1],
                                            releases.sort.versions[int(choice) - 1][2],
                                            releases.sort.versions[int(choice) - 1][3])
    elif choice == str(index + 2):
        obj.version = None
    else:
        return
    while True:
        ui_cls('Options/Scraper/')
        print('Press Enter to return to the main menu.')
        print()
        query = input("Enter a query: ")
        if query == '':
            return
        print()
        if hasattr(obj,"version"):
            if not obj.version == None:
                for trigger, operator, value in obj.version.triggers:
                    if trigger == "scraper sources":
                        if operator in ["==","include"]:
                            if value in scraper.services.active:
                                scraper.services.overwrite += [value]
                        elif operator == "exclude":
                            if value in scraper.services.active:
                                for s in scraper.services.active:
                                    if not s == value:
                                        scraper.services.overwrite += [s]
                    if trigger == "scraping adjustment":
                        if operator == "add text before title":
                            query = value + query
                        elif operator == "add text after title":
                            query = query + value
        scraped_releases = scraper.scrape(query)
        if len(scraped_releases) > 0:
            obj.Releases = scraped_releases
            debrid.check(obj, force=True)
            scraped_releases = obj.Releases
            if not obj.version == None:
                releases.sort(scraped_releases, obj.version)
            back = False
            while not back:
                ui_cls('Options/Scraper/')
                print("0) Back")
                releases.print_releases(scraped_releases)
                print()
                print("Type 'auto' to automatically download the first cached release.")
                print()
                choice = input("Choose a release to download: ")
                try:
                    if choice == 'auto':
                        release = scraped_releases[0]
                        release.Releases = scraped_releases
                        release.type = ("show" if regex.search(r'(S[0-9]+|SEASON|E[0-9]+|EPISODE|[0-9]+-[0-9])',release.title,regex.I) else "movie")
                        if debrid.download(release, stream=True, query=query, force=True):
                            content.classes.media.collect(release)
                            scraped_releases.remove(scraped_releases[0])
                            time.sleep(3)
                        else:
                            print()
                            print("These releases do not seem to be cached on your debrid services. Add uncached torrent?")
                            print()
                            print("0) Back")
                            print("1) Add uncached torrent")
                            print()
                            choice = input("Choose an action: ")
                            if choice == '1':
                                debrid.download(release, stream=False, query=query, force=True)
                                content.classes.media.collect(release)
                                scraped_releases.remove(scraped_releases[0])
                                time.sleep(3)
                    elif int(choice) <= len(scraped_releases) and not int(choice) <= 0:
                        release = scraped_releases[int(choice) - 1]
                        release.Releases = [release, ]
                        release.type = ("show" if regex.search(r'(S[0-9]+|SEASON|E[0-9]+|EPISODE|[0-9]+-[0-9])',release.title,regex.I) else "movie")
                        if debrid.download(release, stream=True, query=release.title, force=True):
                            content.classes.media.collect(release)
                            scraped_releases.remove(scraped_releases[int(choice) - 1])
                            time.sleep(3)
                        else:
                            print()
                            print(
                                "This release does not seem to be cached on your debrid services. Add uncached torrent?")
                            print()
                            print("0) Back")
                            print("1) Add uncached torrent")
                            print()
                            choice2 = input("Choose an action: ")
                            if choice2 == '1':
                                if debrid.download(release, stream=False, query=query, force=True):
                                    content.classes.media.collect(release)
                                    scraped_releases.remove(scraped_releases[int(choice) - 1])
                                    time.sleep(3)
                                else:
                                    print()
                                    print(
                                        "There was an error adding this uncached torrent to your debrid service. Choose another release?")
                    elif choice == '0':
                        back = True
                except:
                    back = False
        else:
            print("No releases were found!")
            time.sleep(3)

def settings():
    back = False
    while not back:
        list = settings_list
        ui_cls('Options/Settings/')
        print('0) Back')
        indices = []
        for index, category in enumerate(list):
            print(str(index + 1) + ') ' + category[0])
            indices += [str(index + 1)]
        print()
        print('Type "discard" to go back and discard changes.')
        print()
        choice = input('Choose an action: ')
        if choice in indices:
            ui_cls('Options/Settings/' + list[int(choice) - 1][0] + '/')
            settings = []
            for index, setting in enumerate(list[int(choice) - 1][1]):
                if not setting.hidden:
                    settings += [setting]
            if len(settings) > 1:
                print('0) Back')
                for index, setting in enumerate(settings):
                    if not setting.hidden:
                        print(str(index + 1) + ') ' + setting.name)
                print()
                choice2 = input('Choose an action: ')
            else:
                choice2 = '1'
            for index, setting in enumerate(list[int(choice) - 1][1]):
                if choice2 == str(index + 1) and not setting.hidden:
                    ui_cls('Options/Settings/' + list[int(choice) - 1][0] + '/' + setting.name)
                    setting.input()
        elif choice == '0':
            save()
            back = True
        elif choice == 'discard':
            load(doprint=True)
            back = True

def options():
    current_module = sys.modules[__name__]
    list = [
        option('Run', current_module, 'download_script_run'),
        option('Settings', current_module, 'settings'),
        option('Ignored Media', current_module, 'ignored'),
        option('Scraper', current_module, 'scrape'),
    ]
    ui_cls('Options/',update=update_available())
    for index, option_ in enumerate(list):
        print(str(index + 1) + ') ' + option_.name)
    print()
    print('Type exit to quit.')
    print()
    choice = input('Choose an action: ')
    if choice == 'exit':
        exit()
    for index, option_ in enumerate(list):
        if choice == str(index + 1):
            option_.input()
    options()

def setup():
    if os.path.exists(config_dir + '/settings.json'):
        if os.path.getsize(config_dir + '/settings.json') > 0 and os.path.isfile(config_dir + '/settings.json'):
            with open(config_dir + '/settings.json', 'r') as f:
                settings = json.loads(f.read())
            if settings['Show Menu on Startup'] == "false" or service_mode == True:
                return False
            load()
            return True
    ui_cls('Initial Setup')
    try:
        input('Press Enter to continue: ')
    except:
        print("Error: It seems this terminal is not interactive! Please make sure to allow user input in this terminal. For docker, add the 'interactive' flag ('-ti').")
        time.sleep(10)
        exit()
    for category, settings in settings_list:
        for setting in settings:
            if setting.required:
                ui_cls('Options/Settings/' + category + '/' + setting.name)
                setting.setup()
    ui_cls('Done!')
    input('Press Enter to continue to the main menu: ')
    save()
    return True

def save(doprint=True):
    save_settings = {}
    for category, settings in settings_list:
        for setting in settings:
            save_settings[setting.name] = setting.get()
    try:
        with open(config_dir + '/settings.json', 'w') as f:
            json.dump(save_settings, f, indent=4)
        if doprint:
            print('Current settings saved!')
            time.sleep(2)
    except:
        print()
        print("Error: It looks like jellyfin_debrid can not write your settings into a config file. Make sure you are running the script with write or administator privilege.")
        print()
        input("Press enter to exit: ")
        exit()

def load(doprint=False, updated=False):
    with open(config_dir + '/settings.json', 'r') as f:
        settings = json.loads(f.read())
    if 'version' not in settings:
        update(settings, ui_settings.version)
        updated = True
    elif not settings['version'][0] == ui_settings.version[0] and not ui_settings.version[2] == []:
        update(settings, ui_settings.version)
        updated = True
    #compatability code for updating from <2.10
    if 'Library Service' in settings:
        settings['Library collection service'] = settings['Library Service']
    #compatability code for updating from <2.20
    if not 'Library ignore services' in settings:
        settings['Library ignore services'] = []
    for category, load_settings in settings_list:
        for setting in load_settings:
            if setting.name in settings and not setting.name == 'version' and not setting.name == 'Content Services':
                setting.set(settings[setting.name])
    if doprint:
        print('Last settings loaded!')
        time.sleep(2)
    save(doprint=updated)

def preflight():
    missing = []
    for category, settings in settings_list:
        for setting in settings:
            if setting.preflight:
                if len(setting.get()) == 0:
                    missing += [setting]
    if len(missing) > 0:
        print()
        print('Looks like your current settings didnt pass preflight checks. Please edit the following setting/s: ')
        for setting in missing:
            print(setting.name + ': Please add at least one ' + setting.entry + '.')
        print()
        input('Press Enter to return to the main menu: ')
        return False
    return True

def run(cdir = "", smode = False):
    global config_dir
    global service_mode
    config_dir = cdir
    service_mode = smode
    set_log_dir(config_dir)
    if setup():
        #uvicorn.run("webui:app", port=8008, reload=True)
        options()
    else:
        load()
        #uvicorn.run("webui:app", port=8008, reload=True)
        download_script_run()
        options()

def update_available():
    try:
        response = requests.get('https://raw.githubusercontent.com/itsToggle/jellyfin_debrid/main/ui/ui_settings.py',timeout=0.25)
        response = response.content.decode()
        if regex.search(r"(?<=')([0-9]+\.[0-9]+)(?=')",response):
            v = regex.search(r"(?<=')([0-9]+\.[0-9]+)(?=')",response).group()
            if float(ui_settings.version[0]) < float(v):
                return " | [v"+v+"] available!"
            return ""
        return ""
    except:
        return ""

def update(settings, version):
    ui_cls('/Update ' + version[0] + '/')
    print('There has been an update to jellyfin_debrid, which is not compatible with your current settings:')
    print()
    print(version[1])
    print()
    print('This update will overwrite the following setting/s: ' + str(version[2]))
    print('A backup file (old.json) with your old settings will be created.')
    print()
    input('Press Enter to update your settings:')
    with open(config_dir + "/old.json", "w+") as f:
        json.dump(settings, f, indent=4)
    for category, load_settings in settings_list:
        for setting in load_settings:
            for setting_name in version[2]:
                if setting.name == setting_name:
                    settings[setting.name] = setting.get()
                elif setting.name == 'version':
                    settings[setting.name] = setting.get()

def unique(lst):
    unique_objects = []
    for obj in lst:
        is_unique = True
        for unique_obj in unique_objects:
            if unique_obj == obj:
                is_unique = False
                break
        if is_unique:
            unique_objects.append(obj)
    return unique_objects

def threaded(stop):
    ui_cls()
    if service_mode == True:
        print("Running in service mode, user input not supported.")
    else:
        print("Type 'exit' to return to the main menu.")
    timeout = 5
    regular_check = 1800
    timeout_counter = 0
    library_services = content.classes.library()
    if len(library_services) == 0:
        ui_print('No library collection service configured. Exiting.', ui_settings.debug)
        return
    library = library_services[0]()
    # get all jellyseerr request
    jellyseerr_requests = content.services.jellyseerr.requests()
    # use only jellyseerr requests
    watchlists = jellyseerr_requests
    try:
        watchlists.data.sort(key=lambda s: s.watchlistedAt,reverse=True)
    except:
        ui_print("couldnt sort monitored media by newest, using default order.", ui_settings.debug)
    if len(library) > 0:
        # Do not start new scans while downloads are active
        import debrid as _debrid
        
        # Clean up downloading list - remove items already in library
        if _debrid.downloading:
            items_to_remove = []
            for download_id in _debrid.downloading:
                # Extract base query from download_id (format: "query [version]")
                base_query = download_id.split(' [')[0] if ' [' in download_id else download_id
                # Check if any library item matches this query
                for lib_item in library:
                    if hasattr(lib_item, 'query') and lib_item.query().lower() == base_query.lower():
                        items_to_remove.append(download_id)
                        ui_print(f'[ui] removing from downloading list (already in library): {download_id}')
                        break
            for item in items_to_remove:
                _debrid.downloading.remove(item)
        
        ui_print(f'[ui] debug: initial scan check - debrid.downloading length: {len(_debrid.downloading)}, ignore_queue length: {len(content.classes.media.ignore_queue)}', ui_settings.debug)
        if _debrid.downloading:
            ui_print(f'[ui] debug: debrid.downloading contents: {_debrid.downloading}', ui_settings.debug)
        if content.classes.media.ignore_queue:
            ui_print(f'[ui] debug: ignore_queue contents: {[str(x) for x in content.classes.media.ignore_queue]}', ui_settings.debug)
        if _debrid.downloading or content.classes.media.ignore_queue:
            ui_print('[ui] downloads in progress, skipping scan', ui_settings.debug)
        else:
            ui_print('checking new content ...')
            t0 = time.time()
            for element in unique(watchlists):
                if hasattr(element, 'download'):
                    try:
                        element_name = element.title if hasattr(element, 'title') else str(type(element))
                        element_type = element.type if hasattr(element, 'type') else 'unknown'
                        ui_print(f'[ui] downloading: {element_name} (type={element_type})', ui_settings.debug)
                        # Prevent duplicate downloads for the same element
                        if element in content.classes.media.ignore_queue:
                            ui_print(f'[ui] skipping download (already in progress): {element_name}', ui_settings.debug)
                        else:
                            # Skip if item is in cooldown
                            try:
                                cooldown_min = int(os.getenv('DOWNLOAD_COOLDOWN_MINUTES', '30'))
                            except Exception:
                                cooldown_min = 30
                            if element.is_in_cooldown():
                                rem = element.cooldown_remaining()
                                ui_print(f"[ui] skipping download (in cooldown {rem}s): {element_name}", ui_settings.debug)
                            else:
                                content.classes.media.ignore_queue += [element]
                                ui_print(f'[ui] debug: added to ignore_queue: {element_name}, queue length: {len(content.classes.media.ignore_queue)}', ui_settings.debug)
                                try:
                                    element.download(library=library)
                                finally:
                                    match = next((x for x in content.classes.media.ignore_queue if element == x), None)
                                    if match:
                                        content.classes.media.ignore_queue.remove(match)
                                        ui_print(f'[ui] debug: removed from ignore_queue: {element_name}, queue length: {len(content.classes.media.ignore_queue)}', ui_settings.debug)
                                    else:
                                        ui_print(f'[ui] warning: element not found in ignore_queue for removal: {element_name}, queue: {[str(x) for x in content.classes.media.ignore_queue]}')
                                    try:
                                        element.set_cooldown(cooldown_min)
                                    except Exception:
                                        pass
                        ui_print(f'[ui] finished downloading: {element_name}', ui_settings.debug)
                    except Exception as e:
                        import traceback
                        element_name = element.title if hasattr(element, 'title') else str(type(element))
                        element_type = element.type if hasattr(element, 'type') else 'unknown'
                        has_seasons = hasattr(element, 'Seasons') if element_type == 'show' else 'N/A'
                        tb = traceback.format_exc()
                        ui_print(f'[ui] error downloading {element_name} (type={element_type}, has_Seasons={has_seasons}): {str(e)}', ui_settings.debug)
                        ui_print(f'[ui] traceback: {tb}', ui_settings.debug)
        ui_print('done')
    while not stop():
        try:
            # Quick check for new jellyseerr requests every loop (every 5 seconds)
            # This ensures new requests are picked up immediately
            if jellyseerr_requests.update():
                ui_print('[jellyseerr] new request detected, processing immediately ...')
                library = content.classes.library()[0]()
                if len(library) > 0:
                    new_watchlists = jellyseerr_requests
                    try:
                        new_watchlists.data.sort(key=lambda s: s.watchlistedAt, reverse=True)
                    except:
                        ui_print("couldnt sort monitored media by newest, using default order.", ui_settings.debug)
                    
                    for element in unique(new_watchlists):
                        if hasattr(element, 'download'):
                            element_name = element.title if hasattr(element, 'title') else str(type(element))
                            if element in content.classes.media.ignore_queue:
                                ui_print(f'[ui] skipping download (already in progress): {element_name}', ui_settings.debug)
                                continue
                            content.classes.media.ignore_queue += [element]
                            try:
                                ui_print(f'checking new content ...')
                                element.download(library=library)
                            except Exception as e:
                                import traceback
                                element_type = element.type if hasattr(element, 'type') else 'unknown'
                                has_seasons = hasattr(element, 'Seasons') if element_type == 'show' else 'N/A'
                                tb = traceback.format_exc()
                                ui_print(f'[ui] error downloading {element_name} (type={element_type}, has_Seasons={has_seasons}): {str(e)}', ui_settings.debug)
                                ui_print(f'[ui] traceback: {tb}', ui_settings.debug)
                            finally:
                                match = next((x for x in content.classes.media.ignore_queue if element == x), None)
                                if match:
                                    content.classes.media.ignore_queue.remove(match)
                    ui_print('done')
            
            # Scheduled check - runs every regular_check seconds
            if timeout_counter >= regular_check:
                jellyseerr_requests = content.services.jellyseerr.requests()
                watchlists = jellyseerr_requests
                try:
                    watchlists.data.sort(key=lambda s: s.watchlistedAt,reverse=True)
                except:
                    ui_print("couldnt sort monitored media by newest, using default order.", ui_settings.debug)
                library = content.classes.library()[0]()
                timeout_counter = 0
                if len(library) == 0:
                    continue
                # Do not start scheduled scans while downloads are active
                import debrid as _debrid
                
                # Clean up downloading list - remove items already in library
                if _debrid.downloading:
                    items_to_remove = []
                    for download_id in _debrid.downloading:
                        # Extract base query from download_id (format: "query [version]")
                        base_query = download_id.split(' [')[0] if ' [' in download_id else download_id
                        # Check if any library item matches this query
                        for lib_item in library:
                            try:
                                if hasattr(lib_item, 'query') and lib_item.query().lower() == base_query.lower():
                                    items_to_remove.append(download_id)
                                    ui_print(f'[ui] removing from downloading list (already in library): {download_id}')
                                    break
                            except AttributeError:
                                # Skip items that don't have required attributes for query()
                                continue
                    for item in items_to_remove:
                        _debrid.downloading.remove(item)
                
                ui_print(f'[ui] debug: scheduled scan check - debrid.downloading length: {len(_debrid.downloading)}, ignore_queue length: {len(content.classes.media.ignore_queue)}', ui_settings.debug)
                if _debrid.downloading:
                    ui_print(f'[ui] debug: debrid.downloading contents: {_debrid.downloading}', ui_settings.debug)
                if content.classes.media.ignore_queue:
                    ui_print(f'[ui] debug: ignore_queue contents: {[str(x) for x in content.classes.media.ignore_queue]}', ui_settings.debug)
                if _debrid.downloading or content.classes.media.ignore_queue:
                    ui_print('[ui] downloads in progress, skipping scheduled scan', ui_settings.debug)
                    t0 = time.time()
                else:
                    ui_print('checking new content ...')
                    t0 = time.time()
                for element in unique(watchlists):
                    if hasattr(element, 'download'):
                        element_name = element.title if hasattr(element, 'title') else str(type(element))
                        if element in content.classes.media.ignore_queue:
                            ui_print(f'[ui] skipping download (already in progress): {element_name}', ui_settings.debug)
                            continue
                        content.classes.media.ignore_queue += [element]
                        try:
                            element.download(library=library)
                        finally:
                            match = next((x for x in content.classes.media.ignore_queue if element == x), None)
                            if match:
                                content.classes.media.ignore_queue.remove(match)
                        t1 = time.time()
                        #if more than 5 seconds have passed, check for newly watchlisted content
                        if t1-t0 >= 5:
                            if jellyseerr_requests.update():
                                library = content.classes.library()[0]()
                                if len(library) == 0:
                                    continue
                                new_watchlists = jellyseerr_requests
                                try:
                                    new_watchlists.data.sort(key=lambda s: s.watchlistedAt,reverse=True)
                                except:
                                    ui_print("couldnt sort monitored media by newest, using default order.", ui_settings.debug)
                                new_watchlists = unique(new_watchlists)
                                for element in new_watchlists[:]:
                                    if element in watchlists:
                                        new_watchlists.remove(element)
                                ui_print('checking new content ...')
                                for element in new_watchlists:
                                    if hasattr(element, 'download'):
                                        element_name = element.title if hasattr(element, 'title') else str(type(element))
                                        if element in content.classes.media.ignore_queue:
                                            ui_print(f'[ui] skipping download (already in progress): {element_name}', ui_settings.debug)
                                            continue
                                        content.classes.media.ignore_queue += [element]
                                        try:
                                            element.download(library=library)
                                        finally:
                                            match = next((x for x in content.classes.media.ignore_queue if element == x), None)
                                            if match:
                                                content.classes.media.ignore_queue.remove(match)
                                ui_print('done')
                            t0 = time.time()
                ui_print('done')
            else:
                timeout_counter += timeout
        
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            ui_print(f'[ui] error in main loop: {str(e)}', ui_settings.debug)
            ui_print(f'[ui] traceback: {tb}', ui_settings.debug)
            ui_print('[ui] main loop will continue despite error')
        
        time.sleep(timeout)

def download_script_run():
    if preflight():
        global stop
        stop = False
        t = Thread(target=threaded, args=(lambda: stop,))
        t.start()
        if service_mode == True:
            print("Running in service mode, user input not supported.")
        else:
            while not stop:
                text = input("")
                if text == 'exit':
                    stop = True
                else:
                    print("Type 'exit' to return to the main menu.")
        print("Waiting for the download automation to stop ... ")
        while t.is_alive():
            time.sleep(1)
