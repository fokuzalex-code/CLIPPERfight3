"""Ejecuta procesos externos de forma que se puedan cancelar desde otro hilo."""
import subprocess, threading

_cur, _lock = set(), threading.Lock()


def run(cmd, cwd=None):
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    with _lock:
        _cur.add(p)
    try:
        out, err = p.communicate()
    finally:
        with _lock:
            _cur.discard(p)
    return p.returncode, out, err


def kill_all():
    with _lock:
        for p in list(_cur):
            try:
                p.kill()
            except Exception:
                pass
