import sys

# import child modules
from debrid.services import realdebrid

# Define empty module placeholders for services that don't exist yet
alldebrid = None  # type: ignore[assignment]
debridlink = None  # type: ignore[assignment]
premiumize = None  # type: ignore[assignment]
putio = None  # type: ignore[assignment]


# define subclass method
def __subclasses__():
    return [realdebrid]  # Only return services that actually exist


active = []


def setup(cls, new=False):
    from settings import settings_list

    global active
    settings = []
    for category, allsettings in settings_list:
        for setting in allsettings:
            if setting.cls == cls:
                settings += [setting]
    back = False
    if not new:
        while not back:
            print()
            print("0) Back")
            indices = []
            for index, setting in enumerate(settings):
                print(str(index + 1) + ") " + setting.name)
                indices += [str(index + 1)]
            print()
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
    cls = cls = sys.modules[__name__]
    activeservices = []
    for servicename in active:
        for service in cls.__subclasses__():
            if service.name == servicename:
                activeservices += [service]
    return activeservices
