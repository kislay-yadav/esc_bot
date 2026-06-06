"""
Plugin Loader
=============
Every .py file in the plugins/ folder is auto-loaded.
Each plugin registers its own handlers via register(app, db_funcs).

To ADD a new command/feature:
  1. Create plugins/my_feature.py
  2. Define async handler functions
  3. Add a register(app, db) function at the bottom
  4. Done — no main.py changes needed

To REMOVE a feature:
  - Delete the plugin file or rename it to my_feature.py.disabled
"""

import os, importlib, logging

log = logging.getLogger("PluginLoader")

def load_all(app, db_funcs: dict):
    """Load every .py plugin from the plugins/ directory."""
    plugin_dir = os.path.join(os.path.dirname(__file__), "plugins")
    loaded = []
    failed = []

    for fname in sorted(os.listdir(plugin_dir)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        module_name = f"plugins.{fname[:-3]}"
        try:
            mod = importlib.import_module(module_name)
            if hasattr(mod, "register"):
                mod.register(app, db_funcs)
                loaded.append(fname)
                log.info("✅ Plugin loaded: %s", fname)
            else:
                log.warning("⚠️ Plugin %s has no register() — skipped", fname)
        except Exception as e:
            failed.append(fname)
            log.error("❌ Plugin %s failed: %s", fname, e)

    log.info("Plugins: %d loaded, %d failed", len(loaded), len(failed))
    if failed:
        log.error("Failed plugins: %s", failed)
    return loaded, failed
