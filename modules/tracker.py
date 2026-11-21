import cv2
import numpy as np

_det = None


def _get():
    global _det
    if _det:
        return _det
    try:
        import mediapipe as mp
        fd = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)

        def f(img):
            r = fd.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            out = []
            for d in (r.detections or []):
                b = d.location_data.relative_bounding_box
                out.append((b.xmin + b.width / 2, b.ymin + b.height / 2, b.width, b.height))
            return out
        _det = f
    except Exception:  # fallback OpenCV Haar
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

        def f(img):
            if casc.empty():  # cascada no encontrada: sin detección de rostros (no rompe el render)
                return []
            h, w = img.shape[:2]
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            r = casc.detectMultiScale(g, 1.15, 5, minSize=(max(24, w // 40),) * 2)
            return [((x + bw / 2) / w, (y + bh / 2) / h, bw / w, bh / h) for x, y, bw, bh in r]
        _det = f
    return _det


def _med(fs):
    a = np.median(np.array(fs), axis=0)
    return {"x": float(a[0]), "y": float(a[1]), "w": float(a[2]), "h": float(a[3])}


def face_plan(video, start, end, n=10):
    """Muestrea n frames del tramo y devuelve 0, 1 o 2 rostros estables (ordenados de izq. a der.)."""
    cap = cv2.VideoCapture(str(video))
    det = _get()
    per = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_MSEC, (start + (end - start) * (i + 0.5) / n) * 1000)
        ok, fr = cap.read()
        if not ok:
            continue
        if fr.shape[1] > 960:
            k = 960 / fr.shape[1]
            fr = cv2.resize(fr, None, fx=k, fy=k)
        per.append(sorted(det(fr), key=lambda f: -f[2] * f[3]))
    cap.release()
    if not per:
        return {"faces": []}
    multi = [p for p in per if len(p) >= 2]
    if len(multi) >= max(2, len(per) // 2):
        pairs = [sorted(p[:2], key=lambda f: f[0]) for p in multi]
        return {"faces": [_med([p[0] for p in pairs]), _med([p[1] for p in pairs])]}
    single = [p[0] for p in per if p]
    if len(single) < max(2, len(per) // 4):
        return {"faces": []}
    return {"faces": [_med(single)]}
