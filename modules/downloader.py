import json, subprocess
from pathlib import Path
from . import procs


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                        "-show_format", str(path)], capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    st = d.get("streams", [])
    v = next((s for s in st if s.get("codec_type") == "video"), None)
    a = next((s for s in st if s.get("codec_type") == "audio"), None)
    if not v:
        raise ValueError("El archivo no contiene video")
    rotated = bool(v.get("tags", {}).get("rotate")) or any(
        "rotation" in sd for sd in v.get("side_data_list", []))
    dur = float(d.get("format", {}).get("duration") or v.get("duration") or 0)
    return {"width": int(v["width"]), "height": int(v["height"]), "vcodec": v["codec_name"],
            "acodec": a["codec_name"] if a else None, "has_audio": a is not None,
            "duration": dur, "rotated": rotated}


def download_kick(url, dest_dir, start_min=0, max_min=60, cb=None):
    """Descarga un VOD/clip de Kick con yt-dlp. Solo baja el tramo [start_min, start_min+max_min]."""
    import yt_dlp
    from yt_dlp.utils import download_range_func
    if not url.startswith("http"):
        raise ValueError("URL inválida")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    def hook(d):
        if cb and d.get("status") == "downloading":
            tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if tot:
                cb(min(1, d.get("downloaded_bytes", 0) / tot))

    opts = {"outtmpl": str(dest_dir / "raw.%(ext)s"),
            "format": "best[height<=1080]/bv*[height<=1080]+ba/b",
            "merge_output_format": "mp4", "quiet": True, "no_warnings": True,
            "noprogress": True, "retries": 5, "fragment_retries": 10,
            "concurrent_fragment_downloads": 4, "progress_hooks": [hook]}
    if max_min > 0:
        opts["download_ranges"] = download_range_func(None, [(start_min * 60, (start_min + max_min) * 60)])
        opts["force_keyframes_at_cuts"] = False
    with yt_dlp.YoutubeDL(opts) as y:
        y.download([url])
    files = [f for f in dest_dir.glob("raw.*") if f.suffix not in (".part", ".ytdl")]
    if not files:
        raise RuntimeError("No se pudo descargar el video (¿URL privada o bloqueada?)")
    return max(files, key=lambda f: f.stat().st_size)


def normalize(src, dst):
    """Deja un MP4 H.264/AAC (<=1080p). Si ya cumple, solo copia el contenedor."""
    src, dst = Path(src), Path(dst)
    i = probe(src)
    ok = (i["vcodec"] == "h264" and i["acodec"] in ("aac", None) and not i["rotated"]
          and i["height"] <= 1080)
    if ok:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-c", "copy",
               "-movflags", "+faststart", str(dst)]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
               "-vf", "scale=-2:'min(1080,ih)'", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
               "-movflags", "+faststart", str(dst)]
    rc, _, err = procs.run(cmd)
    if rc:
        raise RuntimeError("Error normalizando: " + err[-400:])
    return dst
