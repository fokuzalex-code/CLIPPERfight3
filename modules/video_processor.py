from pathlib import Path
from . import procs, transcriber

W, H = 1080, 1920


def run(cmd, cwd=None):
    rc, _, err = procs.run(cmd, cwd)
    if rc:
        raise RuntimeError("FFmpeg: " + err[-500:])


def tc(t):
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def make_ass(path, events, o):
    al = {"bottom": (2, 430), "center": (5, 0), "top": (8, 520)}[o["sub_pos"]]
    wal = {"tl": (7, 130), "tr": (9, 130), "bl": (1, 260), "br": (3, 260)}[o["wm_pos"]]
    alpha = int((1 - float(o["wm_opacity"])) * 255)
    base = "&H00" + transcriber.bgr(o["sub_color"])
    act = "&H00" + transcriber.bgr(o["sub_active"])
    f, sz = o["sub_font"], int(o["sub_size"])
    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,"
        "Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,"
        "MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Sub,{f},{sz},{base},{base},&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,7,2,{al[0]},70,70,{al[1]},1\n"
        f"Style: Hook,{f},{int(sz * .9)},&H00000000,&H00000000,{act},&H00000000,1,0,0,0,100,100,0,0,3,16,0,8,90,90,230,1\n"
        f"Style: WM,{f},44,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,{wal[0]},50,50,{wal[1]},1\n"
        f"Style: Stinger,{f},130,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,8,0,5,40,40,0,1\n"
        "\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    lines = []
    dur = o["dur"]
    user = (o.get("wm_user") or "").strip()
    if user and not user.startswith("@"):
        user = "@" + user
    if o.get("hook") and o.get("hook_text"):
        lines.append(f"Dialogue: 3,{tc(0)},{tc(min(2, dur))},Hook,,0,0,0,,{{\\fad(120,250)}}{o['hook_text']}")
    if user:
        lines.append(f"Dialogue: 1,{tc(0)},{tc(dur)},WM,,0,0,0,,{{\\1a&H{alpha:02X}&\\3a&H{alpha:02X}&}}{user}")
        if o.get("stinger"):
            lines.append(f"Dialogue: 4,{tc(0)},{tc(1)},Stinger,,0,0,0,,{{\\fad(100,300)}}{user.upper()}")
    for s, e, t in events:
        lines.append(f"Dialogue: 2,{tc(s)},{tc(min(e, dur))},Sub,,0,0,0,,{t}")
    Path(path).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def _ev(v):
    return int(round(v / 2) * 2)


def _box(face, info, aspect, minfrac, mult):
    iw, ih = info["width"], info["height"]
    ch = max(minfrac, min(1.0, face["h"] * mult)) * ih
    cw = ch * aspect
    if cw > iw:
        cw = iw
        ch = cw / aspect
    x = min(max(face["x"] * iw - cw / 2, 0), iw - cw)
    y = min(max(face["y"] * ih - ch / 2, 0), ih - ch)
    return _ev(x), _ev(y), _ev(cw), _ev(ch)


def _fit(inp, out, w, h, blur):
    if blur:
        bw, bh = w // 4, h // 4
        return (f"[{inp}]split=2[{out}a][{out}b];"
                f"[{out}a]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
                f"boxblur=6:2,scale={w}:{h}[{out}bg];"
                f"[{out}b]scale={w}:{h}:force_original_aspect_ratio=decrease[{out}fg];"
                f"[{out}bg][{out}fg]overlay=(W-w)/2:(H-h)/2[{out}]")
    return (f"[{inp}]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black[{out}]")


def build_graph(layout, faces, info, blur, punch, dur, o):
    g = []
    cam = {"x": .5, "y": .5, "w": .3, "h": .5}
    if layout == "split" and faces:
        x, y, w, h = _box(faces[0], info, 1080 / 960, .25, 3.2)
        g += ["[0:v]split=2[s1][s2]", f"[s1]crop={w}:{h}:{x}:{y},scale=1080:960[top]",
              _fit("s2", "bot", 1080, 960, blur), "[top][bot]vstack[v0]"]
    elif layout == "podcast" and len(faces) >= 2:
        b1 = _box(faces[0], info, 1080 / 960, .35, 2.8)
        b2 = _box(faces[1], info, 1080 / 960, .35, 2.8)
        g += ["[0:v]split=2[s1][s2]",
              "[s1]crop=%d:%d:%d:%d,scale=1080:960[top]" % (b1[2], b1[3], b1[0], b1[1]),
              "[s2]crop=%d:%d:%d:%d,scale=1080:960[bot]" % (b2[2], b2[3], b2[0], b2[1]),
              "[top][bot]vstack[v0]"]
    elif layout in ("cam", "podcast"):
        x, y, w, h = _box(faces[0] if faces else cam, info, 9 / 16, .35, 3.0)
        z = "(1+0.12*gt(mod(t,6),3))"
        g += [f"[0:v]crop={w}:{h}:{x}:{y},scale=1080:1920[c]"]
        if punch:
            g += [f"[c]scale=w='trunc(1080*{z}/2)*2':h='trunc(1920*{z}/2)*2':eval=frame,crop=1080:1920[v0]"]
        else:
            g += ["[c]null[v0]"]
    else:  # original (y split sin rostro detectado)
        g += [_fit("0:v", "v0", 1080, 1920, blur)]
    last = "v0"
    g.append(f"[{last}]fps=30[v1]")
    last = "v1"
    if o.get("stinger"):
        g.append(f"[{last}]drawbox=x=0:y=0:w=iw:h=ih:color=black@0.65:t=fill:enable='lt(t,1)'[v2]")
        last = "v2"
    g.append(f"[{last}]ass={o['ass']}[v3]")
    last = "v3"
    if o.get("progress_bar"):
        g.append(f"color=c=0xFFE600:s=1080x14:r=30:d={dur:.2f}[bar]")
        g.append(f"[{last}][bar]overlay=x='-w+w*t/{dur:.2f}':y=H-h-40:shortest=1[v4]")
        last = "v4"
    g.append(f"[{last}]format=yuv420p[vout]")
    return ";".join(g)


def render(src, out, start, end, layout, faces, info, words, fillers, o):
    """o: sub_*, wm_*, hook_text, hook, stinger, progress_bar, blur, punch, anti_fillers, target_lufs."""
    out = Path(out)
    wd = out.parent
    dur = end - start
    ass = wd / (out.stem + ".ass")
    ev = transcriber.karaoke_events(words, o["sub_active"], o["sub_color"], o["anti_fillers"])
    make_ass(ass, ev, {**o, "dur": dur})
    graph = build_graph(layout, faces, info, o["blur"], o.get("punch", True), dur, {**o, "ass": ass.name})
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}",
           "-i", str(src), "-filter_complex", graph, "-map", "[vout]"]
    if info["has_audio"]:
        af = []
        if o["anti_fillers"]:
            af += [f"volume=0:enable='between(t,{a:.2f},{b:.2f})'" for a, b in fillers[:40]]
        af += [f"loudnorm=I={o['target_lufs']}:TP=-1.5:LRA=11",
               f"afade=t=out:st={max(dur - .25, 0):.2f}:d=0.25"]
        cmd += ["-map", "0:a:0", "-af", ",".join(af), "-c:a", "aac", "-b:a", "160k", "-ar", "44100"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{dur:.2f}", str(out)]
    try:
        run(cmd, cwd=wd)
    finally:
        ass.unlink(missing_ok=True)


def thumbnail(video, thumb):
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", str(video), "-frames:v", "1",
         "-vf", "scale=360:-2", str(thumb)])
