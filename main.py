import os
import sys
import threading

import ui

config_dir = ""
service_mode = False

if os.path.exists("./settings.json"):
    if os.path.getsize("./settings.json") > 0 and os.path.isfile("./settings.json"):
        config_dir = "."

for i, arg in enumerate(sys.argv):
    if config_dir == "" and arg == "--config-dir":
        config_dir = sys.argv[i + 1]
    if arg == "-service":
        service_mode = True

if config_dir == "":
    config_dir = "."

if __name__ == "__main__":
    if service_mode:
        from log_viewer import start_log_viewer

        log_thread = threading.Thread(target=start_log_viewer, daemon=True)
        log_thread.start()
    ui.run(config_dir, service_mode)
