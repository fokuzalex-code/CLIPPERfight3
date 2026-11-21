import json, os, shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("DATA_DIR", BASE / "data"))
UPLOADS, WORK, JOBS_DIR = DATA / "uploads", DATA / "work", DATA / "jobs"
SETTINGS_FILE = DATA / "settings.json"

DEFAULTS = {
    "out_dir": os.environ.get("OUTPUT_DIR", str(BASE / "output_clips")),
    "whisper_model": "base", "language": "auto",
    "sub_font": "Montserrat", "sub_color": "#FFFFFF", "sub_active": "#FFE600",
    "sub_position": "bottom", "sub_size": 84,
    "wm_user": "", "wm_opacity": 0.6, "wm_pos": "br",
    "default_duration": "30-60", "target_lufs": -14, "anti_fillers": True,
    "default_layout": "split", "hashtags": "#kick #gaming #clips",
    "sensitivity": 50, "oled": True, "max_source_minutes": 60,
}


def ensure():
    for d in (DATA, UPLOADS, WORK, JOBS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load():
    ensure()
    s = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        try:
            s.update(json.loads(SETTINGS_FILE.read_text()))
        except Exception:
            pass
    return s


def save(new):
    s = load()
    for k, v in new.items():
        if k in DEFAULTS:
            s[k] = v
    SETTINGS_FILE.write_text(json.dumps(s, indent=2))
    return s


def out_dir():
    p = Path(load()["out_dir"])
    p.mkdir(parents=True, exist_ok=True)
    return p


def clear_cache():
    for d in (WORK, UPLOADS):
        shutil.rmtree(d, ignore_errors=True)
    ensure()
