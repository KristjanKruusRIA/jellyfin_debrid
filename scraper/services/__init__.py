import sys
import time

from ui.ui_print import ui_print, ui_settings

# import child modules
try:
    from scraper.services import aiostreams

    aiostreams_available = True
except Exception as e:
    ui_print(
        f"[scraper] warning: could not import aiostreams: {e}", debug=ui_settings.debug
    )
    aiostreams_available = False
    aiostreams = None  # type: ignore[assignment]

try:
    from scraper.services import comet

    comet_available = True
except Exception as e:
    ui_print(f"[scraper] warning: could not import comet: {e}", debug=ui_settings.debug)
    comet_available = False
    comet = None  # type: ignore[assignment]

# Build scrapers list and active_default based on available scrapers
scrapers = []
active_default = []

if aiostreams_available:
    scrapers.append(aiostreams)
    active_default.append("aiostreams")

if comet_available:
    assert comet is not None
    if hasattr(comet, "create_instance"):
        comet_selfhosted = comet.create_instance("comet-selfhosted")
        comet_elfhosted = comet.create_instance("comet-elfhosted")
        comet_base = comet.create_instance("comet-base")
        scrapers.extend([comet_selfhosted, comet_elfhosted, comet_base])
        active_default.extend(["comet-selfhosted", "comet-elfhosted", "comet-base"])
    else:
        scrapers.append(comet)
        active_default.append("comet")

# from scraper.services import rarbg
# from scraper.services import x1337
# from scraper.services import jackett
# from scraper.services import prowlarr
# from scraper.services import orionoid
# from scraper.services import nyaa


# define subclass method
def __subclasses__():
    return scrapers


active = active_default
overwrite: list = []


def _supported_services_map():
    cls = sys.modules[__name__]
    return {service.name: service for service in cls.__subclasses__()}


def _supported_sources_text(services_by_name):
    return ", ".join(sorted(services_by_name.keys()))


def _warn_unsupported_source(servicename, supported_sources):
    ui_print(
        "[scraper] warning: ignoring unsupported source "
        + f"'{servicename}'"
        + " in Sources config. Supported sources: "
        + supported_sources
    )


def _error_no_supported_sources(supported_sources):
    ui_print(
        "[scraper] error: no supported sources found in Sources config. "
        "Please update your settings. Supported sources: " + supported_sources
    )


def setup(cls, new=False):
    from settings import settings_list

    global active
    settings = []
    for category, allsettings in settings_list:
        for setting in allsettings:
            if setting.cls == cls:
                settings += [setting]
    if settings == []:
        if cls.name not in active:
            active += [cls.name]
    back = False
    if not new:
        while not back:
            print("0) Back")
            indices = []
            for index, setting in enumerate(settings):
                print(str(index + 1) + ") " + setting.name)
                indices += [str(index + 1)]
            print()
            if settings == []:
                print("Nothing to edit!")
                print()
                time.sleep(3)
                return
            choice = input("Choose an action: ")
            if choice in indices:
                settings[int(choice) - 1].setup()
                if cls.name not in active:
                    active += [cls.name]
                back = True
            elif choice == "0":
                back = True
    else:
        print()
        indices = []
        for setting in settings:
            setting.setup()
            if cls.name not in active:
                active += [cls.name]


def get():
    services_by_name = _supported_services_map()
    supported_sources = _supported_sources_text(services_by_name)
    activeservices = []
    for servicename in active:
        service = services_by_name.get(servicename)
        if service is None:
            _warn_unsupported_source(servicename, supported_sources)
            continue
        activeservices += [service]
    if active and activeservices == []:
        _error_no_supported_sources(supported_sources)
    return activeservices


def sequential():
    global overwrite
    services_by_name = _supported_services_map()
    supported_sources = _supported_sources_text(services_by_name)
    activeservices = []
    for sequence in overwrite:
        activesequence = []
        for servicename in sequence:
            service = services_by_name.get(servicename)
            if service is None:
                _warn_unsupported_source(servicename, supported_sources)
                continue
            activesequence += [service]
        if sequence and activesequence == []:
            _error_no_supported_sources(supported_sources)
        activeservices += [activesequence]
    return activeservices
