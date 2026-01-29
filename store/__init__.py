def load(module, variable):
    import os
    import pickle

    from ui.ui_print import config_dir, ui_print

    cache = []
    try:
        filename = config_dir + "/" + module + "_" + variable + ".pkl"
        if os.path.exists(filename):
            ui_print("[" + module + "] reading cached " + variable + " file ...")
            with open(filename, "rb") as f:
                cache = pickle.load(f)
            ui_print("done")
    except Exception:
        ui_print("[" + module + "] error: couldnt read cached " + variable + " file.")
        cache = []
    return cache


def save(cache, module, variable):
    import pickle

    from ui.ui_print import config_dir, ui_print

    try:
        filename = config_dir + "/" + module + "_" + variable + ".pkl"
        ui_print("[" + module + "] writing cached " + variable + " file ...")
        with open(filename, "wb") as f:
            pickle.dump(cache, f)
        ui_print("done")
    except Exception:
        ui_print("[" + module + "] error: couldnt write cached " + variable + " file.")
