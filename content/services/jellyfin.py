# import modules
import json
import time
from types import SimpleNamespace

import requests

# import parent modules
from content import classes
from ui.ui_print import ui_cls, ui_print, ui_settings

name = "Jellyfin"
session = requests.Session()
api_key = ""


def logerror(response):
    if hasattr(response, "status_code"):
        if response.status_code >= 400:
            # Only log actual errors (4xx, 5xx status codes)
            if (
                hasattr(response, "content")
                and response.content
                and len(response.content) > 0
            ):
                ui_print(
                    "jellyfin error: " + str(response.content), debug=ui_settings.debug
                )
        if response.status_code == 401:
            ui_print(
                "jellyfin error: (401 unauthorized): api token does not seem to work. check your jellyfin settings."
            )


def get(url, timeout=30):
    try:
        headers = {"X-MediaBrowser-Token": api_key}
        response = session.get(url, timeout=timeout, headers=headers)
        logerror(response)
        response = json.loads(
            response.content, object_hook=lambda d: SimpleNamespace(**d)
        )
        return response
    except Exception as e:
        ui_print("jellyfin error: (json exception): " + str(e), debug=ui_settings.debug)
        return None


def post(url, data):
    try:
        headers = {"X-MediaBrowser-Token": api_key}
        response = session.post(url, data=data, headers=headers)
        logerror(response)
        # Some endpoints like /Library/Refresh return empty responses
        if response.content and len(response.content) > 0:
            response = json.loads(
                response.content, object_hook=lambda d: SimpleNamespace(**d)
            )
        else:
            response = None
        return response
    except Exception as e:
        ui_print("jellyfin error: (json exception): " + str(e), debug=ui_settings.debug)
        return None


class library(classes.library):
    name = "Jellyfin Library"
    url = "http://localhost:8096"

    def setup(cls, new=False):
        from settings import settings_list

        if new:
            print()
            settings = []
            for category, allsettings in settings_list:
                for setting in allsettings:
                    settings += [setting]
            if len(api_key) == 0:
                print("Please specify your jellyfin api key:")
                print()
                for setting in settings:
                    if setting.name == "Jellyfin API Key":
                        setting.setup()
                print()
            for setting in settings:
                if setting.name == "Jellyfin server address":
                    setting.setup()
                    print()
            classes.library.active = [library.name]
        else:
            classes.library.setup(library)

    class refresh(classes.refresh):
        name = "Jellyfin Libraries"

        def setup(cls, new=False):
            ui_cls("Options/Settings/Library Services/Library update services")
            from settings import settings_list

            settings = []
            for category, allsettings in settings_list:
                for setting in allsettings:
                    settings += [setting]
            if len(api_key) == 0:
                print(
                    "It looks like you havent setup a jellyfin api key. Please set up a jellyfin api key first."
                )
                print()
                for setting in settings:
                    if setting.name == "Jellyfin API Key":
                        setting.setup()
            working = False
            while not working:
                try:
                    headers = {"X-MediaBrowser-Token": api_key}
                    response = session.get(
                        library.url + "/System/Info", headers=headers
                    )
                    while response.status_code == 401:
                        print("It looks like your jellyfin api key did not work.")
                        print()
                        for setting in settings:
                            if setting.name == "Jellyfin API Key":
                                setting.setup()
                        headers = {"X-MediaBrowser-Token": api_key}
                        response = session.get(
                            library.url + "/System/Info", headers=headers
                        )
                    working = True
                except Exception as e:
                    ui_print(
                        f"[jellyfin] connection error: {str(e)}",
                        ui_settings.debug,
                    )
                    print(
                        "It looks like your jellyfin server could not be reached at '"
                        + library.url
                        + "'"
                    )
                    print()
                    for setting in settings:
                        if setting.name == "Jellyfin server address":
                            setting.setup()
                    print()
            if not new:
                back = False
                jellysettings = []
                for setting in settings:
                    if (
                        setting.name == "Jellyfin API Key"
                        or setting.name == "Jellyfin server address"
                    ):
                        jellysettings += [setting]
                while not back:
                    print("0) Back")
                    indices = []
                    for i, setting in enumerate(jellysettings):
                        print(str(i + 1) + ") " + setting.name)
                        indices += str(i + 1)
                    print()
                    choice2 = input("Choose an action")
                    if choice2 == "0":
                        back = True
                    elif choice2 in indices:
                        jellysettings[int(choice2) - 1].setup()
            else:
                back = False
                while not back:
                    if library.refresh.name not in classes.refresh.active:
                        classes.refresh.active += [library.refresh.name]
                        print()
                        print("Successfully added jellyfin!")
                        print()
                        time.sleep(3)
                    return

        def __new__(cls, element):
            try:
                ui_print("[jellyfin] refreshing all libraries")
                url = library.url + "/Library/Refresh"
                response = post(url, "")
                # /Library/Refresh returns 204 No Content or 200 with empty body on success
                # response will be None when the body is empty, which is expected
                # Only warn if there was an actual error
                if response is None:
                    # This is expected - the endpoint returns empty body
                    pass
                elif hasattr(response, "status_code") and response.status_code >= 400:
                    ui_print(
                        "[jellyfin] warning: library refresh returned error status code",
                        ui_settings.debug,
                    )
            except Exception as e:
                ui_print(
                    f"[jellyfin] error: couldnt refresh libraries: {str(e)}",
                    ui_settings.debug,
                )

    def __new__(self):
        list = []
        ui_print("[jellyfin] getting entire jellyfin library ...")
        url = library.url + "/users"
        users_response = get(url)
        if not users_response:
            ui_print(
                "[jellyfin error]: couldnt reach local jellyfin server at server address: "
                + library.url
            )
            return list

        # Get items from first user only
        try:
            # users_response should be a list, get first user
            user = users_response[0]
        except (TypeError, IndexError, KeyError):
            # If it's not indexable or is empty, use it directly
            user = users_response
        # Request movies and series with minimal fields for better performance
        url = (
            library.url
            + "/users/"
            + user.Id
            + "/Items?Recursive=true&IncludeItemTypes=Movie,Series&Fields=ProviderIds,Path,PremiereDate"
        )
        items_response = get(url, timeout=60)
        ui_print("done")

        if not items_response:
            ui_print(
                "[jellyfin error]: couldnt get items from jellyfin server at "
                + library.url
            )
            return list

        # Jellyfin returns {"Items": [...], "TotalRecordCount": ...}
        if hasattr(items_response, "Items"):
            ui_print(
                f"[jellyfin] found {items_response.TotalRecordCount} items in library"
            )
            for element in items_response.Items:
                try:
                    # Map Jellyfin Type to jellyfin_debrid type field
                    if hasattr(element, "Type"):
                        if element.Type == "Movie":
                            element.type = "movie"
                        elif element.Type == "Series":
                            element.type = "show"

                    # Determine if this is a series and fetch full details
                    if hasattr(element, "Type") and element.Type == "Series":
                        # Fetch seasons for this series
                        seasons_url = (
                            library.url
                            + "/Users/"
                            + user.Id
                            + "/Items?ParentId="
                            + element.Id
                            + "&IncludeItemTypes=Season"
                        )
                        seasons_response = get(seasons_url, timeout=30)
                        if seasons_response and hasattr(seasons_response, "Items"):
                            element.seasons = []
                            total_episode_count = 0
                            for season in seasons_response.Items:
                                # Fetch episodes for this season
                                episodes_url = (
                                    library.url
                                    + "/Users/"
                                    + user.Id
                                    + "/Items?ParentId="
                                    + season.Id
                                )
                                episodes_response = get(episodes_url, timeout=30)
                                season.Episodes = []
                                if episodes_response and hasattr(
                                    episodes_response, "Items"
                                ):
                                    season.Episodes = episodes_response.Items
                                    total_episode_count += len(episodes_response.Items)
                                element.seasons.append(season)
                            # Set leafCount to total episode count for matching
                            element.leafCount = total_episode_count
                        else:
                            # Fallback to empty seasons list if fetch fails
                            element.seasons = []
                            element.leafCount = 0

                    # Convert Jellyfin item to jellyfin_debrid media object
                    media_obj = classes.media(element)
                    list += [media_obj]
                except Exception as e:
                    ui_print(
                        f"[jellyfin] error processing item: {str(e)}",
                        debug=ui_settings.debug,
                    )
        else:
            ui_print(
                "[jellyfin error]: unexpected response format from jellyfin server"
            )

        if len(list) == 0:
            ui_print(
                "[jellyfin error]: Your library seems empty. To prevent unwanted behaviour, no further downloads will be started. If your library really is empty, please add at least one media item manually."
            )
        return list


# Multiprocessing watchlist method
def multi_init(cls, obj, result, index):
    result[index] = cls(obj)
