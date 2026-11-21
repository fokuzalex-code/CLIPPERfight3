import uuid, zipfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import database as db
from modules import config as cfg, diagnostics, procs as pl

app = FastAPI(title="Clipper.fight")
BASE = Path(__file__).parent
(BASE / "static").mkdir(exist_ok=True)
(BASE / "templates").mkdir(exist_ok=True)


@app.on_event("startup")
def startup():
    cfg.ensure()
    load_fn = getattr(pl, "load_jobs", None)
    if callable(load_fn):
        load_fn()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def index():
    f = BASE / "templates" / "index.html"
    if not f.exists():
        return HTMLResponse("<h3>Falta templates/index.html en el repositorio</h3>", 500)
    return f.read_text(encoding="utf-8")


@app.get("/api/settings")
def get_settings():
    return cfg.load()


@app.post("/api/settings")
def set_settings(d: dict):
    return cfg.save(d)


@app.post("/api/cleanup")
def cleanup():
    busy_fn = getattr(pl, "busy", None)
    if callable(busy_fn) and busy_fn():
        raise HTTPException(409, "Hay trabajos en proceso")
    cfg.clear_cache()
    return {"ok": True}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".mp4", ".mkv", ".mov", ".webm"):
        raise HTTPException(400, "Formato no soportado (usa MP4 o MKV)")
    fid = uuid.uuid4().hex[:10]
    d = cfg.UPLOADS / fid
    d.mkdir(parents=True, exist_ok=True)
    with open(d / ("upload" + ext), "wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)
    return {"file_id": fid, "name": file.filename}


class JobReq(BaseModel):
    url: Optional[str] = None
    file_id: Optional[str] = None
    start_min: int = 0
    duration: str = "30-60"
    count: int = 10
    layout: str = "split"
    blur: bool = True
    wm_user: str = ""
    wm_opacity: float = 0.6
    wm_pos: str = "br"
    hook: bool = True
    fillers: bool = True
    stinger: bool = False
    progress_bar: bool = True


@app.post("/api/jobs")
def create_job(r: JobReq):
    if not r.url and not r.file_id:
        raise HTTPException(400, "Pega una URL de Kick o sube un archivo")
    if r.file_id and not (cfg.UPLOADS / Path(r.file_id).name).exists():
        raise HTTPException(400, "Archivo no encontrado, súbelo de nuevo")
    dur = getattr(pl, "DUR", ("15-30", "30-60", "60-90"))
    if r.duration not in dur or r.layout not in ("split", "cam", "podcast", "original"):
        raise HTTPException(400, "Parámetros inválidos")
    new_job_fn = getattr(pl, "new_job", None)
    if not callable(new_job_fn):
        raise HTTPException(503, "El módulo de procesamiento aún no tiene configurada la cola de trabajos")
    d = r.dict()
    d["count"] = max(1, min(30, d["count"]))
    d["file_id"] = Path(d["file_id"]).name if d["file_id"] else None
    return {"id": new_job_fn(d)["id"]}


def _jobs_dict():
    return getattr(pl, "JOBS", {})


def _job(jid):
    j = _jobs_dict().get(jid)
    if not j:
        raise HTTPException(404, "Trabajo no encontrado")
    return j


def _clip(j, cid):
    c = next((c for c in j["clips"] if c["id"] == cid), None)
    if not c:
        raise HTTPException(404, "Clip no encontrado")
    return c


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    j = _job(jid)
    public_fn = getattr(pl, "public", None)
    return public_fn(j) if callable(public_fn) else j


@app.post("/api/jobs/{jid}/clips/{cid}/reroll")
def reroll(jid: str, cid: str):
    _job(jid), _clip(_job(jid), cid)
    reroll_fn = getattr(pl, "reroll", None)
    if not callable(reroll_fn):
        raise HTTPException(503, "Función reroll no disponible")
    try:
        reroll_fn(jid, cid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/jobs/{jid}/clips/{cid}/trash")
def trash(jid: str, cid: str):
    _clip(_job(jid), cid)
    trash_fn = getattr(pl, "trash", None)
    if not callable(trash_fn):
        raise HTTPException(503, "Función trash no disponible")
    trash_fn(jid, cid)
    return {"ok": True}


@app.post("/api/jobs/{jid}/clips/{cid}/edit")
def edit(jid: str, cid: str, d: dict):
    _clip(_job(jid), cid)
    edit_fn = getattr(pl, "edit", None)
    if not callable(edit_fn):
        raise HTTPException(503, "Función edit no disponible")
    try:
        edit_fn(jid, cid, d)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.get("/media/{jid}/{name}")
def media(jid: str, name: str):
    p = Path(_job(jid)["dir"]) / Path(name).name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)  # Starlette soporta Range (necesario para <video> en iOS)


@app.get("/api/jobs/{jid}/clips/{cid}/download")
def download(jid: str, cid: str):
    j = _job(jid)
    c = _clip(j, cid)
    p = Path(j["dir"]) / (c["file"] or "x")
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="video/mp4", filename=c["name"])


@app.get("/api/jobs/{jid}/zip")
def make_zip(jid: str):
    j = _job(jid)
    zp = Path(j["dir"]) / f"Clipper.fight_{jid}.zip"
    meta = []
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
        for c in j["clips"]:
            p = Path(j["dir"]) / (c["file"] or "x")
            if c["trashed"] or not p.exists():
                continue
            z.write(p, f"Clipper.fight/{c['layout']}/{c['name']}")
            meta.append(f"{c['name']}\n  Título: {c['title']}\n  Score: {c['score']}\n  {c['tags']}\n")
        z.writestr("Clipper.fight/metadata.txt", "\n".join(meta) or "Sin clips")
    return FileResponse(zp, media_type="application/zip", filename=zp.name)


@app.get("/api/diagnostics")
def get_diagnostics():
    n = sum(1 for j in _jobs_dict().values() if j["status"] not in ("done", "error", "cancelled"))
    return diagnostics.run_all(f"{n} trabajo(s) activo(s)")


@app.get("/api/library")
def library(q: str = "", layout: str = ""):
    out = []
    for c in db.library(q.strip(), layout):
        out.append({**c, "duration": round(c["end_s"] - c["start_s"], 1)})
    return out


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str):
    _job(jid)
    cancel_fn = getattr(pl, "cancel", None)
    if not callable(cancel_fn):
        raise HTTPException(503, "Función cancel no disponible")
    try:
        cancel_fn(jid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
