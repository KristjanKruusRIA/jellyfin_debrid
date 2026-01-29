import copy

import content
import debrid
import releases
import scraper
from ui import ui_settings


# Lazy loader for scraper.services to avoid circular imports
class LazyScraperServices:
    def __getattr__(self, name):
        return getattr(scraper.services, name)


_lazy_scraper_services = LazyScraperServices()


class setting:
    def __init__(
        self,
        name,
        prompt,
        cls,
        key,
        required=False,
        entry="",
        test=None,
        help="",
        hidden=False,
        subclass=False,
        oauth=False,
        moveable=True,
        preflight=False,
        radio=False,
        special=False,
    ):
        self.name = name
        self.prompt = prompt
        self.cls = cls
        self.key = key
        self.required = required
        self.entry = entry
        self.test = test
        self.hidden = hidden
        self.subclass = subclass
        self.oauth = oauth
        self.help = help
        self.moveable = moveable
        self.preflight = preflight
        self.radio = radio
        self.special = special

    def input(self):
        if self.special:
            self.cls.setup(self.cls)
            return
        elif self.moveable:
            if not self.help == "":
                print(self.help)
                print()
            print(
                "Current " + self.name + ': "' + str(getattr(self.cls, self.key)) + '"'
            )
            print()
            print("0) Back")
            print("1) Edit")
            print()
            choice = input("Choose an action: ")
        else:
            choice = "1"
        if choice == "1":
            if not isinstance(getattr(self.cls, self.key), list):
                if self.oauth:
                    device_code, user_code = self.cls.oauth()
                    print(self.prompt + str(user_code))
                    console_input = self.cls.oauth(device_code)
                    setattr(self.cls, self.key, console_input)
                    return True
                else:
                    console_input = input(
                        self.prompt
                        + '- current value "'
                        + str(getattr(self.cls, self.key))
                        + '": '
                    )
                    setattr(self.cls, self.key, console_input)
                    return True
            else:
                lists = getattr(self.cls, self.key)
                if self.radio:
                    print()
                    print("0) Back")
                    if len(lists) > 0:
                        print("1) Change " + self.entry)
                        print("2) Edit " + self.entry)
                    else:
                        print("1) Add " + self.entry)
                    print()
                    choice = input("Choose an action: ")
                elif self.moveable:
                    print()
                    print("0) Back")
                    print("1) Add " + self.entry)
                    if len(lists) > 0:
                        print("2) Edit " + self.entry + "s")
                    print()
                    choice = input("Choose an action: ")
                else:
                    choice = "2"
                if choice == "1":
                    if self.subclass:
                        back = False
                        while not back:
                            print()
                            print("0) Back")
                            services = []
                            indices = []
                            index = 0
                            for service in self.cls.__subclasses__():
                                if (
                                    service.name not in getattr(self.cls, self.key)
                                    and "(NOT FUNCTIONAL)" not in service.name
                                ):
                                    print(str(index + 1) + ") " + service.name)
                                    indices += [str(index + 1)]
                                    services += [service]
                                    index += 1
                            print()
                            choice = input("Choose a " + self.entry + ": ")
                            if choice in indices:
                                service = services[int(choice) - 1]
                                service.setup(service, new=True)
                                back = True
                            elif choice == "0":
                                back = True
                    elif self.oauth:
                        edit = []
                        lists = getattr(self.cls, self.key)
                        for prompt in self.prompt:
                            if "code" in prompt:
                                try:
                                    device_code, user_code = self.cls.oauth()
                                except Exception:
                                    print(
                                        "It seems that this authentification service could not be reached. Please try again at a later time."
                                    )
                                    return
                                print(prompt + str(user_code))
                                edit += [self.cls.oauth(device_code)]
                            else:
                                edit += [input(prompt)]
                        lists += [edit]
                        setattr(self.cls, self.key, lists)
                    else:
                        edit = []
                        for prompt in self.prompt:
                            edit += [input(prompt)]
                        lists += [edit]
                        setattr(self.cls, self.key, lists)
                        return True
                elif choice == "2":
                    if not self.radio:
                        print()
                        print("0) Back")
                        indices = []
                        for index, entry in enumerate(lists):
                            if self.moveable:
                                print(
                                    str(index + 1)
                                    + ") Edit "
                                    + self.entry
                                    + " "
                                    + str(index + 1)
                                    + ": "
                                    + str(entry)
                                )
                            else:
                                print(str(index + 1) + ") " + str(entry))
                            indices += [str(index + 1)]
                        print()
                        index = input("Choose a " + self.entry + ": ")
                    else:
                        index = "1"
                        indices = [
                            "1",
                        ]
                    back3 = False
                    while not back3:
                        if index == "0":
                            back3 = True
                        if index in indices:
                            if self.moveable and not self.radio:
                                print()
                                print(
                                    self.entry.capitalize()
                                    + " "
                                    + index
                                    + ": "
                                    + str(lists[int(index) - 1])
                                )
                                print()
                                print("0) Back")
                                print("1) Edit")
                                print("2) Delete")
                                if len(lists) > 1:
                                    print("3) Move")
                                print()
                                choice = input("Choose an action: ")
                            else:
                                choice = "1"
                            back2 = False
                            while not back2:
                                print()
                                if choice == "0":
                                    back2 = True
                                    back3 = True
                                if choice == "1":
                                    if self.subclass:
                                        for service in self.cls.__subclasses__():
                                            if (
                                                str(lists[int(index) - 1])
                                                == service.name
                                            ):
                                                service.setup(service)
                                                return True
                                    elif self.oauth:
                                        edit = []
                                        for prompt in self.prompt:
                                            if "code" in prompt:
                                                (
                                                    device_code,
                                                    user_code,
                                                ) = self.cls.oauth()
                                                print(prompt + str(user_code))
                                                edit += [self.cls.oauth(device_code)]
                                            else:
                                                edit += [input(prompt)]
                                        lists[int(index) - 1] = edit
                                        setattr(self.cls, self.key, lists)
                                        return True
                                    else:
                                        edit = []
                                        for k, prompt in enumerate(self.prompt):
                                            response = input(
                                                prompt
                                                + '- current value "'
                                                + lists[int(index) - 1][k]
                                                + '": '
                                            )
                                            edit += [response]
                                        lists[int(index) - 1] = edit
                                        setattr(self.cls, self.key, lists)
                                        return True
                                if choice == "2":
                                    del lists[int(index) - 1]
                                    return True
                                if choice == "3":
                                    back = False
                                    while not back:
                                        print("0) Back")
                                        for i in indices:
                                            print(i + ") Position " + i)
                                        print()
                                        choice = input(
                                            "Move " + self.entry + " " + index + " to: "
                                        )
                                        if choice == "0":
                                            back = True
                                        if choice in indices:
                                            temp = copy.deepcopy(lists[int(index) - 1])
                                            del lists[int(index) - 1]
                                            lists.insert(int(choice) - 1, temp)
                                            setattr(self.cls, self.key, lists)
                                            return True

    def setup(self):
        if isinstance(getattr(self.cls, self.key), list):
            print()
            working = False
            while not working:
                if self.subclass:
                    print(self.help)
                    print()
                    services = []
                    indices = []
                    index = 0
                    for service in self.cls.__subclasses__():
                        if (
                            "(NOT FUNCTIONAL)" not in service.name
                            and not service.name == "jellyseerr"
                        ):
                            print(str(index + 1) + ") " + service.name)
                            indices += [str(index + 1)]
                            services += [service]
                            index += 1
                    print()
                    choice = input("Choose a " + self.entry + ": ")
                    if choice in indices:
                        service = services[int(choice) - 1]
                        service.setup(service, new=True)
                        working = True
                else:
                    edit = []
                    print(
                        self.name
                        + " - current value: "
                        + str(getattr(self.cls, self.key))
                    )
                    print()
                    if not self.help == "":
                        print(self.help)
                        print()
                    if self.oauth:
                        edit = []
                        lists = getattr(self.cls, self.key)
                        for prompt in self.prompt:
                            if "code" in prompt:
                                try:
                                    device_code, user_code = self.cls.oauth()
                                except Exception:
                                    print(
                                        "it seems this authentification service could not be reached right now. Please try again later."
                                    )
                                    return
                                print(prompt + str(user_code))
                                edit += [self.cls.oauth(device_code)]
                            else:
                                edit += [input(prompt)]
                        lists += [edit]
                        setattr(self.cls, self.key, lists)
                    else:
                        lists = getattr(self.cls, self.key)
                        for prompt in self.prompt:
                            edit += [input(prompt)]
                        lists = [
                            edit,
                        ]
                        setattr(self.cls, self.key, lists)
                    working = True
        else:
            working = False
            while not working:
                print(
                    self.name + " - current value: " + str(getattr(self.cls, self.key))
                )
                print()
                if self.oauth:
                    device_code, user_code = self.cls.oauth()
                    print(self.prompt + str(user_code))
                    console_input = self.cls.oauth(device_code)
                    setattr(self.cls, self.key, console_input)
                else:
                    console_input = input(self.prompt)
                    setattr(self.cls, self.key, console_input)
                if self.name == "Real Debrid API Key":
                    url = (
                        "https://api.real-debrid.com/rest/1.0/torrents?limit=2&auth_token="
                        + console_input
                    )
                    response = debrid.services.realdebrid.session.get(url)
                    if response.status_code == 200:
                        working = True
                    else:
                        print()
                        print(
                            "Looks like the api key does not work. Please enter a valid api key."
                        )
                        print()
                else:
                    working = True

    def set(self, value):
        # Convert legacy or dict-form 'Versions' setting into internal list format
        if self.key == "versions" and isinstance(value, dict):
            new_versions = []
            for name, props in value.items():
                # Determine language
                lang = "true"
                if (
                    isinstance(props, dict)
                    and "languages" in props
                    and isinstance(props["languages"], list)
                    and len(props["languages"]) > 0
                ):
                    lang = props["languages"][0]
                # Determine profile/name
                profile = (
                    props.get("profile", name) if isinstance(props, dict) else name
                )
                # Default triggers to 'both' which expands to default_triggers
                triggers = "both"
                # Create simple rules based on profile (detect common profiles)
                rules = []
                p_lower = str(profile).lower()
                if "4k" in p_lower or "2160" in p_lower:
                    rules = [["resolution", "requirement", ">=", "2160"]]
                elif "1080" in p_lower or "fullhd" in p_lower:
                    rules = [["resolution", "requirement", "<=", "1080"]]
                # Append as [name, triggers, lang, rules]
                new_versions += [[profile, triggers, lang, rules]]
            setattr(self.cls, self.key, new_versions)
            return
        setattr(self.cls, self.key, value)

    def get(self):
        return getattr(self.cls, self.key)


settings_list = [
    [
        "Content Services",
        [
            setting(
                "Content Services",
                [""],
                content.services,
                "active",
                entry="content service",
                subclass=True,
                moveable=False,
                required=True,
                preflight=True,
                help="Please choose at least one content service that jellyfin_debrid should monitor for new content.",
            ),
            setting(
                "jellyseerr users",
                ["Please choose a user: "],
                content.services.jellyseerr,
                "users",
                entry="user",
                help="Please specify which users requests should be downloaded by jellyfin_debrid.",
                hidden=True,
            ),
            setting(
                "jellyseerr API Key",
                "Please specify your jellyseerr API Key: ",
                content.services.jellyseerr,
                "api_key",
                hidden=True,
            ),
            setting(
                "jellyseerr Base URL",
                "Please specify your jellyseerr base URL: ",
                content.services.jellyseerr,
                "base_url",
                hidden=True,
            ),
        ],
    ],
    [
        "Library Services",
        [
            setting(
                "Library collection service",
                [""],
                content.classes.library,
                "active",
                entry="library collection service",
                subclass=True,
                radio=True,
                required=True,
                preflight=True,
                help="Please choose one library collection service that jellyfin_debrid will use to determine your current media collection.",
            ),
            setting(
                "Library update services",
                [""],
                content.classes.refresh,
                "active",
                entry="libary update service",
                subclass=True,
                radio=False,
                required=True,
                preflight=True,
                help="Please choose at least one libary update service that jellyfin_debrid should update after a complete download",
            ),
            setting(
                "Library ignore services",
                [""],
                content.classes.ignore,
                "active",
                entry="libary ignore service",
                subclass=True,
                radio=False,
                required=True,
                preflight=True,
                help="Please choose at least one libary ignore service that jellyfin_debrid should use to ignore content that could repeatedly not be found.",
            ),
            setting(
                "Jellyfin API Key",
                "Please specify your Jellyfin API Key: ",
                content.services.jellyfin,
                "api_key",
                hidden=True,
            ),
            setting(
                "Jellyfin server address",
                "Please enter your Jellyfin server address: ",
                content.services.jellyfin.library,
                "url",
                hidden=True,
            ),
        ],
    ],
    [
        "Scraper Settings",
        [
            setting(
                "Sources",
                [""],
                _lazy_scraper_services,
                "active",
                entry="source",
                subclass=True,
                preflight=True,
            ),
            setting(
                "Versions", [], releases.sort, "versions", special=True, entry="version"
            ),
            setting(
                "Special character renaming",
                [
                    "Please specify a character or string that should be replaced, or provide a regex using {{regex}}: ",
                    "Please specify with what character or string it should be replaced: ",
                ],
                releases.rename,
                "replaceChars",
                entry="rule",
                help="In this setting you can specify a character or a string that should be replaced by nothing, some other character or a string. You can enter regular expressions using {{regex}}.",
            ),
            # REMOVED: Missing scraper services (only torrentio exists)
            # setting('Rarbg API Key', ...),
            # setting('Jackett Base URL', ...),
            # setting('Jackett API Key', ...),
            # setting('Jackett resolver timeout', ...),
            # setting('Jackett indexer filter', ...),
            # setting('Prowlarr Base URL', ...),
            # setting('Prowlarr API Key', ...),
            # setting('Orionoid API Key', ...),
            # setting('Orionoid Scraper Parameters', ...),
            # setting('Nyaa parameters', ...),
            # setting('Nyaa sleep time', ...),
            # setting('Nyaa proxy', ...),
            setting(
                "Torrentio Scraper Parameters",
                "Please enter a valid torrentio manifest url: ",
                _lazy_scraper_services.torrentio,
                "default_opts",
                entry="parameter",
                help='This settings lets you control the torrentio scraping parameters. Visit "https://torrentio.strem.fun/configure" and configure your settings. Dont choose a debrid service. The "manifest url" will be copied to your clipboard.',
                hidden=True,
            ),
        ],
    ],
    [
        "Debrid Services",
        [
            setting(
                "Debrid Services",
                [""],
                debrid.services,
                "active",
                required=True,
                preflight=True,
                entry="service",
                subclass=True,
                help="Please setup at least one debrid service: ",
            ),
            setting(
                "Tracker specific Debrid Services",
                [
                    "Please specify what tracker to look for by providing a regex match group: ",
                    'Please specify what debrid service should be used for a matching tracker (enter "RD","PM","AD","PUT", or "DL"): ',
                ],
                debrid,
                "tracker",
                entry="rule",
            ),
            setting(
                "Real Debrid API Key",
                "Please enter your Real Debrid API Key: ",
                debrid.services.realdebrid,
                "api_key",
                hidden=True,
            ),
            setting(
                "All Debrid API Key",
                "Please enter your All Debrid API Key: ",
                debrid.services.alldebrid,
                "api_key",
                hidden=True,
            ),
            setting(
                "Premiumize API Key",
                "Please enter your Premiumize API Key: ",
                debrid.services.premiumize,
                "api_key",
                hidden=True,
            ),
            setting(
                "Debrid Link API Key",
                'Please open your favorite browser, log into your debridlink account and open "https://debrid-link.fr/device". Enter this code: ',
                debrid.services.debridlink,
                "api_key",
                hidden=True,
                oauth=True,
            ),
            setting(
                "Put.io API Key",
                'Please open your favorite browser, log into your put.io account and open "http://put.io/link". Enter this code: ',
                debrid.services.putio,
                "api_key",
                hidden=True,
                oauth=True,
            ),
        ],
    ],
    [
        "UI Settings",
        [
            setting(
                "Show Menu on Startup",
                'Please enter "true" or "false": ',
                ui_settings,
                "run_directly",
            ),
            setting(
                "Debug printing",
                'Please enter "true" or "false": ',
                ui_settings,
                "debug",
            ),
            setting(
                "Log to file", 'Please enter "true" or "false": ', ui_settings, "log"
            ),
            setting(
                "version",
                "No snooping around! :D This is for compatability reasons.",
                ui_settings,
                "version",
                hidden=True,
            ),
        ],
    ],
]
