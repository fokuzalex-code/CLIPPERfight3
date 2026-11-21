import math, re, unicodedata, wave
from collections import Counter
import numpy as np

EMO = ["jaja", "jeje", "no puede", "dios", "mierda", "increíble", "increible", "imposible", "wtf",
       "omg", "no way", "what the", "let's go", "vamos", "ganamos", "clutch", "insane", "crazy",
       "oh my", "joder", "carajo", "coño", "maldito", "no lo creo", "uff", "locura", "ayuda"]
STOP = set("para pero como esto esta este esos esas porque cuando donde entonces ahora tambien también "
           "with that this have just like what your they there from about".split())


def energy_curve(wav_path, hop=0.5):
    out = []
    with wave.open(str(wav_path)) as w:
        n = int(w.getframerate() * hop)
        while True:
            b = w.readframes(n)
            if not b:
                break
            a = np.frombuffer(b, dtype=np.int16).astype(np.float32) / 32768
            out.append(20 * math.log10(float(np.sqrt(np.mean(a * a))) + 1e-6))
    e = np.array(out) if out else np.zeros(1)
    med = np.median(e)
    mad = np.median(np.abs(e - med)) * 1.4826 + 1e-3
    return (e - med) / mad, hop


def score_window(s, e, z, hop, words):
    i0 = min(int(s / hop), len(z) - 1)
    i1 = max(i0 + 1, min(int(e / hop), len(z)))
    zz = np.clip(z[i0:i1], -1, 5)
    energy = float(np.clip(zz.mean() / 2.0, 0, 1))
    peaks = float(np.clip((zz > 2.0).mean() * 6, 0, 1))
    nw = [w for w in words if s <= w["s"] < e]
    speech = float(np.clip(len(nw) / max(e - s, 1) / 3.5, 0, 1))
    txt = " ".join(w["w"].lower() for w in nw)
    emo = min(1.0, sum(txt.count(k) for k in EMO) / 4)
    hook = float(np.clip(z[i0:i0 + 4].max() / 4, 0, 1))  # energía en los primeros 2 s
    return round(100 * (0.30 * energy + 0.20 * peaks + 0.15 * speech + 0.20 * emo + 0.15 * hook))


def find_candidates(wav, tr, dmin, dmax, total, sensitivity=50, count=10):
    """Devuelve candidatos ordenados por score, sin solaparse (>30%)."""
    z, hop = energy_curve(wav)
    words, segs = tr["words"], tr["segments"]
    target = (dmin + dmax) / 2
    cands = []
    for i, sg in enumerate(segs):
        s = max(0, sg["s"] - 0.1)
        ends = [x["e"] for x in segs[i:] if dmin <= x["e"] - s <= dmax]
        if ends:
            e = min(ends, key=lambda v: abs((v - s) - target))
        elif total - s >= dmin:
            e = min(s + target, total)
        else:
            continue
        cands.append({"s": round(s, 2), "e": round(min(e, total), 2)})
    if len(cands) < count:  # audio sin habla: ventanas fijas
        t = 0.0
        while t + dmin <= total:
            cands.append({"s": t, "e": min(t + target, total)})
            t += 10
    for c in cands:
        c["score"] = score_window(c["s"], c["e"], z, hop, words)
    cands.sort(key=lambda c: -c["score"])
    picked = []
    for c in cands:
        ok = True
        for p in picked:
            ov = min(c["e"], p["e"]) - max(c["s"], p["s"])
            if ov > 0.3 * (c["e"] - c["s"]):
                ok = False
                break
        if ok:
            picked.append(c)
    return picked


def describe(tr, s, e, hashtags):
    segs = [x for x in tr["segments"] if x["e"] > s and x["s"] < e]

    def sc(x):
        t = x["t"].lower()
        return sum(t.count(k) for k in EMO) * 2 + ("!" in t) + min(len(t.split()), 12) / 12

    best = max(segs, key=sc) if segs else None
    title = (best["t"] if best else "Clip").strip(" .,-¡!¿?")
    title = title[:1].upper() + title[1:]
    if len(title) > 70:
        title = title[:67].rsplit(" ", 1)[0] + "…"
    first = segs[0]["t"] if segs else title
    hook = " ".join(first.split()[:7]).upper().strip(" .,")
    text = " ".join(x["t"] for x in segs)
    ws = [w for w in re.findall(r"[a-záéíóúñü]{5,}", text.lower()) if w not in STOP]
    tags = list(dict.fromkeys(hashtags.split() + ["#" + w for w, _ in Counter(ws).most_common(3)]))
    return {"title": title, "hook": hook or title.upper(), "tags": " ".join(tags),
            "desc": f"{title}\n\n{' '.join(tags)}"}


def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40] or "clip"
