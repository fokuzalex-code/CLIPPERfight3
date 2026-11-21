import json, os, re
from pathlib import Path
from . import procs

_MODELS = {}
FILLERS = {"eh", "ehh", "ehhh", "em", "emm", "mm", "mmm", "hmm", "um", "umm", "uh", "uhh", "erm", "ah", "aah"}


def is_filler(w):
    return re.sub(r"[^\wáéíóúñü]", "", w.lower()) in FILLERS


def extract_wav(src, wav):
    rc, _, err = procs.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1",
                            "-ar", "16000", "-c:a", "pcm_s16le", str(wav)])
    if rc:
        raise RuntimeError("No se pudo extraer audio: " + err[-300:])


def get_model(size):
    if size not in _MODELS:
        from faster_whisper import WhisperModel
        _MODELS.clear()
        _MODELS[size] = WhisperModel(size, device="cpu", compute_type="int8",
                                     cpu_threads=os.cpu_count() or 2)
    return _MODELS[size]


def transcribe(src, wd, size="base", language="auto", cb=None):
    wd = Path(wd)
    tj, wav = wd / "transcript.json", wd / "audio.wav"
    if tj.exists():
        return json.loads(tj.read_text())
    if not wav.exists():
        extract_wav(src, wav)
    segs, info = get_model(size).transcribe(
        str(wav), language=None if language == "auto" else language,
        word_timestamps=True, vad_filter=True, beam_size=1)
    out, words = [], []
    for s in segs:
        out.append({"s": round(s.start, 2), "e": round(s.end, 2), "t": s.text.strip()})
        for w in (s.words or []):
            if w.word.strip():
                words.append({"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)})
        if cb and info.duration:
            cb(min(1, s.end / info.duration))
    data = {"segments": out, "words": words, "language": info.language, "duration": info.duration}
    tj.write_text(json.dumps(data))
    return data


def bgr(hexcolor):
    h = hexcolor.lstrip("#")
    return h[4:6] + h[2:4] + h[0:2]


def _esc(t):
    return t.replace("\\", "").replace("{", "(").replace("}", ")")


def karaoke_events(words, active_hex, base_hex, anti=True, per=3):
    """Subtítulos palabra por palabra estilo Hormozi. `words` ya vienen relativos al clip."""
    a, b = "&H%s&" % bgr(active_hex), "&H%s&" % bgr(base_hex)
    ws = [w for w in words if not (anti and is_filler(w["w"]))]
    ev, i = [], 0
    while i < len(ws):
        grp = [ws[i]]
        i += 1
        while i < len(ws) and len(grp) < per and ws[i]["s"] - grp[-1]["e"] < 0.5:
            grp.append(ws[i])
            i += 1
        for k, w in enumerate(grp):
            end = grp[k + 1]["s"] if k + 1 < len(grp) else w["e"] + 0.2
            end = max(end, w["s"] + 0.08)
            parts = []
            for j, x in enumerate(grp):
                t = _esc(x["w"]).upper()
                if j == k:
                    parts.append("{\\c%s\\fscx112\\fscy112}%s{\\c%s\\fscx100\\fscy100}" % (a, t, b))
                else:
                    parts.append(t)
            ev.append((w["s"], end, " ".join(parts)))
    return ev
