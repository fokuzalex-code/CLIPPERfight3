import importlib, os, shutil, subprocess, sys, time
from pathlib import Path
from . import config as cfg

START = time.time()


def _first_line(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return (r.stdout or r.stderr).split("\n")[0].strip() or None
    except Exception:
        return None


def _mem():
    """RAM física disponible. En contenedores el límite real está en cgroup, no en /proc/meminfo."""
    d = {}
    try:
        for line in open("/proc/meminfo"):
            k, v = line.split(":")
            d[k] = int(v.split()[0]) * 1024
    except Exception:
        return None
    total, avail = d.get("MemTotal"), d.get("MemAvailable")
    for f in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            lim = open(f).read().strip()
            if lim.isdigit() and int(lim) < (total or 1 << 62):
                used = 0
                for u in ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory/memory.usage_in_bytes"):
                    if os.path.exists(u):
                        used = int(open(u).read().strip())
                        break
                total, avail = int(lim), max(int(lim) - used, 0)
                break
        except Exception:
            continue
    return {"total": total, "available": avail, "swap": d.get("SwapTotal", 0)}


def gb(n):
    return f"{n / 1024 ** 3:.1f} GB"


def run_all(jobs_info=None):
    checks = []

    def add(id_, name, status, detail, fix=""):
        checks.append({"id": id_, "name": name, "status": status, "detail": detail, "fix": fix})

    add("python", "Python", "ok", sys.version.split()[0])
    for b in ("ffmpeg", "ffprobe"):
        v = _first_line([b, "-version"])
        add(b, b.upper(), "ok" if v else "fail", v or "No encontrado",
            "" if v else "Instala FFmpeg (en Docker: apt-get install ffmpeg).")
    mods = [("faster_whisper", "Faster-Whisper", "fail", "pip install faster-whisper"),
            ("cv2", "OpenCV", "fail", "pip install opencv-python-headless"),
            ("numpy", "NumPy", "fail", "pip install 'numpy<2'"),
            ("yt_dlp", "yt-dlp (Kick/Twitch/YouTube)", "fail", "pip install -U yt-dlp"),
            ("mediapipe", "MediaPipe (opcional)", "warn", "Sin él se usa OpenCV Haar para detectar rostros.")]
    for mod, name, bad, fix in mods:
        try:
            m = importlib.import_module(mod)
            add(mod, name, "ok", getattr(m, "__version__", "instalado"))
        except Exception as e:
            add(mod, name, bad, str(e)[:140], fix)
    hub = Path(os.path.expanduser("~/.cache/huggingface/hub"))
    found = sorted(p.name.split("--")[-1] for p in hub.glob("models--*faster-whisper*")) if hub.exists() else []
    add("models", "Modelos Whisper descargados", "ok" if found else "warn",
        ", ".join(found) or "Ninguno todavía",
        "" if found else "Se descargan solos la primera vez que transcribes (necesita internet).")
    gpu = _first_line(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]) if shutil.which("nvidia-smi") else None
    add("gpu", "GPU", "ok" if gpu else "warn", gpu or "No hay GPU NVIDIA; se usa CPU (int8)",
        "" if gpu else "Es normal en Render. Usa el modelo Whisper 'tiny' o 'base'.")
    m = _mem()
    if m:
        st = "ok" if m["available"] >= 1.5 * 1024 ** 3 else "warn"
        add("ram", "RAM física disponible", st, f"{gb(m['available'])} de {gb(m['total'])} (swap/virtual no cuenta)",
            "" if st == "ok" else "Con poca RAM usa Whisper 'tiny' y clips de 1 en 1.")
    d = shutil.disk_usage(cfg.DATA)
    add("disk", "Almacenamiento", "ok" if d.free > 2 * 1024 ** 3 else "warn",
        f"{gb(d.free)} libres de {gb(d.total)}", "" if d.free > 2 * 1024 ** 3 else "Borra caché en Ajustes o amplía el disco.")
    add("cpu", "CPU", "ok", f"{os.cpu_count()} núcleos")
    up = int(time.time() - START)
    add("server", "Servidor", "ok", f"Activo hace {up // 3600} h {up % 3600 // 60} min" + (f" · {jobs_info}" if jobs_info else ""))
    s = {k: sum(c["status"] == k for c in checks) for k in ("ok", "warn", "fail")}
    return {"checks": checks, "summary": s}
