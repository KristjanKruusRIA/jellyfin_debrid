#import modules
from base import *
#import parent modules
from content import classes
from ui.ui_print import *

name = 'jellyseerr'
base_url = ""
users = ['all']
# Jellyseerr statuses: 1=Pending, 2=Approved, 3=Declined, 4=Processing, 5=Available
# Include status 1 (Pending) to pick up new requests immediately
allowed_movie_status = [['1'], ['2'], ['3']]
allowed_show_status = [['1'], ['2'], ['3'], ['4']]
api_key = ""
session = requests.Session()
last_requests = []

def setup(self):
    global base_url
    global api_key
    global users
    global allowed_status
    global session
    from settings import settings_list
    ui_cls("Options/Settings/Content Services/Content Services/jellyseerr")
    working_key = False
    working_url = False
    try:
        response = session.get(base_url + '/api/v1/request', headers={"X-Api-Key": api_key}, timeout=0.5)
        if response.status_code == 200:
            working_key = True
            working_url = True
        else:
            working_key = False
            working_url = True
    except:
        working_url = False
    while not working_url:
        if base_url == "http://localhost:5055":
            print("Looks like jellyseerr couldn't be reached under the default base url ('" + base_url + "').")
        else:
            print("Looks like jellyseerr couldn't be reached under the current base url ('" + base_url + "').")
        print("Please make sure jellyseerr is running and try again, or provide your jellyseerr base URL below.")
        print("Please provide your jellyseerr base URL in the following format 'http://localhost:5055' or press enter to return to the main menu.")
        print()
        base_url = input("Please provide your jellyseerr base URL: ")
        if base_url == "":
            return
        working_key = False
        working_url = False
        try:
            response = session.get(base_url + '/api/v1/request', headers={"X-Api-Key": api_key}, timeout=0.5)
            if response.status_code == 200:
                working_key = True
                working_url = True
            else:
                working_key = False
                working_url = True
        except:
            working_url = False
    while not working_key:
        if api_key == "":
            print("To setup jellyseerr, please provide your jellyseerr API Key. Press enter to return to the main menu.")
        else:
            print("Looks like your current API Key ('" + api_key + "') doesnt work.")
        print()
        api_key = input("Please enter your jellyseerr API Key: ")
        if api_key == "":
            return
        working_key = False
        working_url = False
        try:
            response = session.get(base_url + '/api/v1/request', headers={"X-Api-Key": api_key}, timeout=0.5)
            if response.status_code == 200:
                working_key = True
                working_url = True
            else:
                working_key = False
                working_url = True
        except:
            working_url = False
    settings = []
    for category, allsettings in settings_list:
        for setting in allsettings:
            if setting.cls == self or setting.name.startswith(self.name):
                settings += [setting]
    response = get(base_url + '/api/v1/user?take=10000')
    users_ = response.results
    new_users = []
    for user in users_:
        if not user.displayName in users:
            new_users += [user.displayName]
    back = False
    ui_cls("Options/Settings/Content Services/Content Services/jellyseerr")
    while not back:
        print("0) Back")
        indices = []
        for index, setting in enumerate(settings):
            print(str(index + 1) + ') ' + setting.name)
            indices += [str(index + 1)]
        print()
        choice = input("Choose an action: ")
        if choice in indices:
            if settings[int(choice) - 1].name == "jellyseerr users":
                print()
                print("You can define which users approved requests should be downloaded by jellyfin_debrid.")
                print()
                print('Currently monitored jellyseerr users: "' + str(users) + '"')
                print()
                print('0) Back')
                print('1) Always monitor all users')
                print('2) Add user')
                if len(users) > 0 and not users == ['all']:
                    print('3) Remove user')
                print()
                choice = input('Choose an action: ')
                print()
                if choice == '1':
                    users = ['all']
                    return True
                elif choice == '2':
                    print(
                        "Choose which users approved requests should be downloaded by jellyfin_debrid. Type 'all' to add all currently listed users.")
                    print()
                    i = 0
                    indices = []
                    add_user = []
                    print('0) Back')
                    for user in users_:
                        if not user.displayName in users:
                            print(str(i + 1) + ') ' + user.displayName)
                            indices += [str(i + 1)]
                            add_user += [user.displayName]
                            i += 1
                    print()
                    choice = input("Choose a user: ")
                    if choice == '0':
                        back = True
                    elif choice == 'all':
                        users += new_users
                        return True
                    elif choice in indices:
                        users += [add_user[int(choice) - 1]]
                        return True
                elif choice == '3':
                    indices = []
                    print("Choose a user to remove.")
                    print()
                    print('0) Back')
                    for index, user in enumerate(users):
                        print(str(index + 1) + ') ' + user)
                        indices += [str(index + 1)]
                    print()
                    choice = input("Choose a user: ")
                    if choice == '0':
                        back = True
                    elif choice in indices:
                        users.remove(users[int(choice) - 1])
                        return True
            else:
                settings[int(choice) - 1].input()
            back = True
        elif choice == '0':
            back = True

def logerror(response):
    if not response.status_code == 200:
        ui_print("[jellyseerr] error: " + str(response.content), debug=ui_settings.debug)
    if response.status_code == 401:
        ui_print("[jellyseerr] error: (401 unauthorized): overserr api key does not seem to work.")

def get(url):
    try:
        response = session.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36',
            'Content-type': "application/json", "X-Api-Key": api_key})
        logerror(response)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print("[jellyseerr] error: (exception): " + str(e), debug=ui_settings.debug)
        return None
    return response

def post(url, data):
    try:
        response = session.post(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36',
            'Content-type': "application/json", "X-Api-Key": api_key}, data=data)
        logerror(response)
        response = json.loads(response.content, object_hook=lambda d: SimpleNamespace(**d))
    except Exception as e:
        ui_print("[jellyseerr] error: (exception): " + str(e), debug=ui_settings.debug)
        return None
    return response

def setEID(self):
    EID = []
    if hasattr(self,"media"):    
        if hasattr(self.media,"imdbId"):
            if not self.media.imdbId == None:
                EID += ['imdb://' + str(self.media.imdbId)]
        if hasattr(self.media,"tmdbId"):
            if not self.media.tmdbId == None:
                EID += ['tmdb://' + str(self.media.tmdbId)]
        if hasattr(self.media,"tvdbId"):
            if not self.media.tvdbId == None:
                EID += ['tvdb://' + str(self.media.tvdbId)]
    return EID

class media(classes.media):
    def __init__(self, other):
        super().__init__(other)

class movie(classes.media):
    def __init__(self, other):
        self.__dict__.update(other.__dict__)
        self.EID = setEID(self)
        self.watchlistedAt = datetime.datetime.timestamp(datetime.datetime.strptime(self.updatedAt,'%Y-%m-%dT%H:%M:%S.000Z'))
        
        # Fetch full movie details from Jellyseerr to get title, release date, and IMDB ID
        if hasattr(self, 'media') and hasattr(self.media, 'tmdbId'):
            try:
                movie_details = get(base_url + f'/api/v1/movie/{self.media.tmdbId}')
                if movie_details:
                    if hasattr(movie_details, 'title'):
                        self.title = movie_details.title
                    if hasattr(movie_details, 'releaseDate') and movie_details.releaseDate:
                        # Extract year from releaseDate (format: YYYY-MM-DD)
                        self.year = int(movie_details.releaseDate.split('-')[0])
                        self.originallyAvailableAt = movie_details.releaseDate
                    # Add IMDB ID from externalIds if available
                    if hasattr(movie_details, 'externalIds') and hasattr(movie_details.externalIds, 'imdbId') and movie_details.externalIds.imdbId:
                        imdb_id_str = 'imdb://' + str(movie_details.externalIds.imdbId)
                        if imdb_id_str not in self.EID:
                            self.EID.insert(0, imdb_id_str)  # Add IMDB at beginning since Torrentio needs it
            except Exception as e:
                ui_print(f'[jellyseerr] error fetching movie details: {str(e)}', ui_settings.debug)

class show(classes.media):
    def __init__(self, other):
        self.__dict__.update(other.__dict__)
        self.type = 'show'
        self.EID = setEID(self)
        self.watchlistedAt = datetime.datetime.timestamp(datetime.datetime.strptime(self.updatedAt,'%Y-%m-%dT%H:%M:%S.000Z'))
        self.Seasons = []
        
        # Set default originallyAvailableAt to ensure it always exists
        if not hasattr(self, 'originallyAvailableAt'):
            self.originallyAvailableAt = "1990-01-01"
        
        # Fetch full TV show details from Jellyseerr to get title, first air date, and IMDB ID
        seasons_from_api = []
        if hasattr(self, 'media') and hasattr(self.media, 'tmdbId'):
            try:
                tv_details = get(base_url + f'/api/v1/tv/{self.media.tmdbId}')
                if tv_details:
                    if hasattr(tv_details, 'name'):
                        self.title = tv_details.name
                    if hasattr(tv_details, 'firstAirDate') and tv_details.firstAirDate:
                        # Extract year from firstAirDate (format: YYYY-MM-DD)
                        self.year = int(tv_details.firstAirDate.split('-')[0])
                        self.originallyAvailableAt = tv_details.firstAirDate
                    # Add IMDB ID from externalIds if available
                    if hasattr(tv_details, 'externalIds') and hasattr(tv_details.externalIds, 'imdbId') and tv_details.externalIds.imdbId:
                        imdb_id_str = 'imdb://' + str(tv_details.externalIds.imdbId)
                        if imdb_id_str not in self.EID:
                            self.EID.insert(0, imdb_id_str)  # Add IMDB at beginning since Torrentio needs it
                    # Extract seasons from TV details if available
                    if hasattr(tv_details, 'seasons') and tv_details.seasons:
                        seasons_from_api = list(tv_details.seasons)
            except Exception as e:
                ui_print(f'[jellyseerr] error fetching TV details: {str(e)}', ui_settings.debug)
        
        # Process seasons
        # First check if this request has specific seasons (from request API)
        # If so, use only requested/approved seasons; otherwise use all seasons from TV details
        seasons_to_process = []
        if hasattr(self, 'seasons') and self.seasons:
            # Use seasons from request, but filter to only approved/requested ones
            for req_season in self.seasons:
                # Include season if it has approved status (status >= 2)
                # Status values: 0=pending, 1=requested, 2=approved, 3=completed, etc.
                if hasattr(req_season, 'status') and req_season.status >= 2:
                    seasons_to_process.append(req_season)
        
        # If no approved seasons in request, use all seasons from TV details
        if not seasons_to_process:
            seasons_to_process = seasons_from_api if seasons_from_api else []
        
        for season in seasons_to_process:
            season.type = "season"
            season.index = season.seasonNumber
            season.parentEID = self.EID
            season.parentTitle = self.title
            season.parentYear = self.year
            # Initialize episodes list
            season.Episodes = []
            
            # Create placeholder episodes based on episodeCount if available
            try:
                episode_count = 0
                # Try to get episode count from season object
                if hasattr(season, 'episodeCount'):
                    episode_count = season.episodeCount
                elif hasattr(season, 'episodes') and season.episodes:
                    episode_count = len(season.episodes)
                
                # Create episode objects for each episode in the season
                for ep_num in range(1, episode_count + 1):
                    episode = SimpleNamespace()
                    episode.type = "episode"
                    episode.index = ep_num
                    episode.parentIndex = season.seasonNumber
                    episode.grandparentEID = self.EID
                    episode.grandparentTitle = self.title
                    episode.grandparentYear = self.year
                    
                    # Set air date if available
                    if hasattr(season, 'airDate') and season.airDate:
                        episode.originallyAvailableAt = season.airDate
                    elif hasattr(self, 'originallyAvailableAt'):
                        episode.originallyAvailableAt = self.originallyAvailableAt
                    else:
                        episode.originallyAvailableAt = "1990-01-01"  # Fallback date
                    
                    season.Episodes.append(episode)
                
                if episode_count == 0:
                    ui_print(f'[jellyseerr] warning: season {season.seasonNumber} has no episode count, creating minimal episode', ui_settings.debug)
                    # Create at least one placeholder episode if we don't know the count
                    episode = SimpleNamespace()
                    episode.type = "episode"
                    episode.index = 1
                    episode.parentIndex = season.seasonNumber
                    episode.grandparentEID = self.EID
                    episode.grandparentTitle = self.title
                    episode.grandparentYear = self.year
                    episode.originallyAvailableAt = self.originallyAvailableAt if hasattr(self, 'originallyAvailableAt') else "1990-01-01"
                    season.Episodes.append(episode)
                    
            except Exception as e:
                ui_print(f'[jellyseerr] error creating episodes for season {season.seasonNumber}: {str(e)}', ui_settings.debug)
                # Create at least one episode as fallback
                episode = SimpleNamespace()
                episode.type = "episode"
                episode.index = 1
                episode.parentIndex = season.seasonNumber
                episode.grandparentEID = self.EID
                episode.grandparentTitle = self.title
                episode.grandparentYear = self.year
                episode.originallyAvailableAt = self.originallyAvailableAt if hasattr(self, 'originallyAvailableAt') else "1990-01-01"
                season.Episodes.append(episode)
            
            # Convert episodes to proper media objects first
            for i, episode in enumerate(season.Episodes):
                season.Episodes[i] = classes.media(episode)
            
            # Convert season to proper media object
            season_media = classes.media(season)
            self.Seasons += [season_media]

class requests(classes.watchlist):

    def __init__(self):
        global last_requests
        # last_requests tracks API-level request objects we've already seen
        # It should persist between update() calls but reset on service restart
        last_requests = []
        self.data = []
        if len(users) > 0 and len(api_key) > 0:
            ui_print('[jellyseerr] getting all jellyseerr requests ...')
            try:
                response = get(base_url + '/api/v1/request?take=10000')
                ui_print(f'[jellyseerr] received {len(response.results) if response and hasattr(response, "results") else 0} requests from API', ui_settings.debug)
                if response and hasattr(response, 'results'):
                    seen = set()
                    added = 0
                    skipped = 0
                    checked = 0
                # Build list of requests to process
                requests_to_process = []
                for element in response.results:
                    # Build a dedupe key (media id + requesting user) to avoid duplicate processing
                    try:
                        media_id = getattr(element.media, 'id', None)
                        user = element.requestedBy.displayName if hasattr(element, 'requestedBy') and hasattr(element.requestedBy, 'displayName') else None
                        dedupe_key = (str(media_id), str(user))
                    except Exception:
                        dedupe_key = None

                    # Skip if duplicate media+user in same API response
                    if dedupe_key and dedupe_key in seen:
                        skipped += 1
                        ui_print(f'[jellyseerr] skipping duplicate request for media={media_id} user={user}', ui_settings.debug)
                        continue

                    checked += 1
                    
                    # Check filters - on init, process ALL matching requests regardless of last_requests
                    user_matches = (element.requestedBy.displayName in users or users == ['all'])
                    status_matches = ([str(element.media.status)] in allowed_movie_status if element.type == 'movie' else [str(element.media.status)] in allowed_show_status)
                    
                    if user_matches and status_matches:
                        ui_print(f'[jellyseerr] adding request to queue: type={element.type}, status={getattr(element.media, "status", "?")}, user={getattr(element.requestedBy, "displayName", "?")}', ui_settings.debug)
                        requests_to_process.append(element)
                        added += 1
                        seen.add(dedupe_key if dedupe_key else element.id)

                # Summary log to avoid spamming the logs on each scan
                ui_print(f'[jellyseerr] checked {checked} unique requests, added {added}, skipped {skipped} duplicates', ui_settings.debug)
                
                # Update last_requests with all current API results to track what we've seen
                for element in response.results:
                    if not any(x.id == element.id and x.updatedAt == element.updatedAt for x in last_requests):
                        last_requests.append(element)
                        
            except Exception as e:
                ui_print('[jellyseerr] error: ' + str(e), ui_settings.debug)
                ui_print('[jellyseerr] error: jellyseerr couldnt be reached. turn on debug printing for more info.')
                requests_to_process = []
            ui_print(f'done - found {len(requests_to_process)} requests to process')
            if requests_to_process == []:
                ui_print('[jellyseerr] no requests to process, skipping', ui_settings.debug)
                return
            # Just process the jellyseerr requests directly
            ui_print('[jellyseerr] processing jellyseerr requests ...')
            add = []
            # default autoremove behavior for this watchlist
            self.autoremove = 'both'
            for element_ in requests_to_process:
                element = copy.deepcopy(element_)
                if element.type == "movie":
                    element = movie(element)
                elif element.type == "tv":
                    element = show(element)
                element.request_id = element_.media.id
                # attach watchlist reference so the item can remove itself later
                element.watchlist = self
                add += [element]
            for element in add:
                if not element in self.data:
                    self.data.append(element)
            ui_print('done')

    def update(self):
        global last_requests
        if len(users) > 0 and len(api_key) > 0:
            refresh = False
            try:
                response = get(base_url + '/api/v1/request?take=10000')
                for element_ in response.results:
                    if not any(x.id == element_.id and x.updatedAt == element_.updatedAt for x in last_requests) and (element_.requestedBy.displayName in users or users == ['all']) and ([str(element_.media.status)] in allowed_movie_status if element_.type == 'movie' else [str(element_.media.status)] in allowed_show_status):
                        # Convert to media object first to check if already in self.data
                        element = copy.deepcopy(element_)
                        if element.type == "movie":
                            element = movie(element)
                        elif element.type == "tv":
                            element = show(element)
                        element.request_id = element_.media.id
                        
                        # Only process if not already in watchlist
                        if not element in self.data:
                            ui_print('[jellyseerr] found new jellyseerr request by user "' + element_.requestedBy.displayName + '".')
                            refresh = True
                            last_requests.append(element_)
                            ui_print('[jellyseerr] processing new jellyseerr request ...')
                            self.data.append(element)
                            ui_print('done')
                        else:
                            # Already in watchlist, just update last_requests to avoid re-checking
                            if not any(x.id == element_.id and x.updatedAt == element_.updatedAt for x in last_requests):
                                last_requests.append(element_)
                            # Handle season updates for shows
                            existing = next(x for x in self.data if x == element)
                            if element.type == "show":
                                for season in element.Seasons:
                                    if not any(season.index == x.index for x in existing.Seasons):
                                        existing.Seasons.append(season)
                                        refresh = True
                # Clean up last_requests for items no longer in API results
                for element in last_requests[:]:
                    if not element.id in (x.id for x in response.results):
                        last_requests.remove(element)
                
                # Remove items from watchlist if their status is no longer in allowed list (e.g., status changed to 5 Available)
                for existing_item in self.data[:]:
                    # Find the corresponding API result
                    api_result = next((x for x in response.results if hasattr(existing_item, 'request_id') and x.media.id == existing_item.request_id), None)
                    if api_result:
                        # Check if status is still allowed
                        status_allowed = ([str(api_result.media.status)] in allowed_movie_status if api_result.type == 'movie' else [str(api_result.media.status)] in allowed_show_status)
                        if not status_allowed:
                            ui_print(f'[jellyseerr] removing request from queue (status changed to {api_result.media.status}): {existing_item.title if hasattr(existing_item, "title") else "unknown"}')
                            self.data.remove(existing_item)
                            refresh = True
                
                if refresh:
                    return True
            except:
                return False
        return False

class library():
    name = 'jellyseerr Requests'

    class refresh(classes.refresh):
        name = 'jellyseerr Requests'

        def setup(cls, new=False):
            ui_cls("Options/Settings/Library Services/Library update services")
            from settings import settings_list
            settings = []
            for category, allsettings in settings_list:
                for setting in allsettings:
                    settings += [setting]
            if len(api_key) == 0:
                print("It looks like you havent setup an jellyseerr api key. Please set up an jellyseerr api key first.")
                print()
                for setting in settings:
                    if setting.name == "jellyseerr API Key":
                        setting.setup()
            if not new:
                if not library.refresh.name in classes.refresh.active:
                    classes.refresh.active += [library.refresh.name]
                    print()
                    print("Successfully added Overserr!")
                    print()
                    time.sleep(3)
                else:
                    print()
                    print("Nothing to edit!")
                    print()
                    time.sleep(3)
                return
            else:
                if not library.refresh.name in classes.refresh.active:
                    classes.refresh.active += [library.refresh.name]
                    print()
                    print("Successfully added Overserr!")
                    print()
                    time.sleep(3)
                return

        def __new__(cls, element):
            try:
                if not hasattr(element,"request_id"):
                    return
                ui_print('[overserr] marking request as available')
                url = base_url + "/api/v1/media/" + str(element.request_id) + "/available"
                response = post(url,'{"is4k":false}')
            except:
                print("[overserr] error: couldnt mark requests as available")
