"""Onde está o rosto ao longo do vídeo (para nunca cobrir olhos/boca e posicionar legendas).

Ordem de tentativa: OpenCV (Haar, vem junto com opencv) -> MediaPipe -> máscara da pessoa -> estimativa.
Saída: lista de amostras {t, caixa:[x0,y0,x1,y1]} em frações 0-1 do quadro, suavizada no tempo."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .midia import LeitorDeQuadros, sondar


YUNET = Path(__file__).resolve().parent.parent / "modelos" / "face_detection_yunet_2023mar.onnx"


def _detector():
    try:  # YuNet (OpenCV >= 4.5.4, modelo de 230 KB que vai junto, licença MIT): o mais confiável
        import cv2
        if not (hasattr(cv2, "FaceDetectorYN") and YUNET.exists()):
            raise RuntimeError
        yn = cv2.FaceDetectorYN.create(str(YUNET), "", (320, 320), 0.6, 0.3, 5000)
        def det(rgb):
            h, w = rgb.shape[:2]
            yn.setInputSize((w, h))
            _, fs = yn.detect(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
            if fs is None or len(fs) == 0:
                return None
            x, y, fw, fh = max(fs, key=lambda r: r[2] * r[3])[:4]
            return [max(0, x) / w, max(0, y) / h, min(w, x + fw) / w, min(h, y + fh) / h]
        return "yunet", det
    except Exception:  # noqa: BLE001
        pass
    try:
        import cv2
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        if casc.empty():
            raise RuntimeError
        def det(rgb):
            g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            g = cv2.equalizeHist(g)
            h, w = g.shape
            fs = casc.detectMultiScale(g, 1.12, 5, minSize=(int(w * 0.12), int(w * 0.12)))
            if len(fs) == 0:
                return None
            x, y, fw, fh = max(fs, key=lambda r: r[2] * r[3])
            return [x / w, y / h, (x + fw) / w, (y + fh) / h]
        return "opencv", det
    except Exception:  # noqa: BLE001
        pass
    try:
        import mediapipe as mp
        fd = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
        def det(rgb):
            r = fd.process(rgb)
            if not r.detections:
                return None
            b = max(r.detections, key=lambda d: d.score[0]).location_data.relative_bounding_box
            return [b.xmin, b.ymin, b.xmin + b.width, b.ymin + b.height]
        return "mediapipe", det
    except Exception:  # noqa: BLE001
        return None, None


def _da_mascara(m: np.ndarray):
    """Estimativa do rosto a partir da máscara da pessoa: a cabeça é o topo da silhueta."""
    h, w = m.shape
    lin = np.where((m > 128).sum(axis=1) > w * 0.02)[0]
    if len(lin) == 0:
        return None
    topo = lin[0]
    faixa = m[topo: min(h, topo + int(h * 0.25))] > 128
    cols = np.where(faixa.any(axis=0))[0]
    if len(cols) == 0:
        return None
    cx = (cols[0] + cols[-1]) / 2
    larg = min(cols[-1] - cols[0], w * 0.6)
    y0 = topo + larg * 0.35
    return [(cx - larg * 0.38) / w, y0 / h, (cx + larg * 0.38) / w, (y0 + larg * 0.95) / h]


def analisar_rosto(video: str, saida: str | None = None, passo_s: float = 0.4, mascara: str | None = None) -> dict:
    info = sondar(video)
    nome, det = _detector()
    lw = 360
    lh = int(round(info.altura * lw / info.largura / 2) * 2)
    fps_amostra = 1.0 / passo_s
    amostras = []
    if det:
        for i, q in enumerate(LeitorDeQuadros(video, lw, lh, fps_amostra)):
            caixa = det(np.ascontiguousarray(q))
            if caixa:
                amostras.append({"t": round(i * passo_s, 3), "caixa": [round(float(v), 4) for v in caixa]})
    metodo = nome
    if not amostras and mascara and Path(mascara).exists():
        metodo = "mascara"
        for i, m in enumerate(LeitorDeQuadros(mascara, lw, lh, fps_amostra, cinza=True)):
            caixa = _da_mascara(m)
            if caixa:
                amostras.append({"t": round(i * passo_s, 3), "caixa": [round(float(v), 4) for v in caixa]})
    if not amostras:
        metodo = "estimativa"
        amostras = [{"t": 0.0, "caixa": [0.3, 0.22, 0.7, 0.52]}]
    # suavização: mediana móvel de 5 amostras (tira saltos de detecção falsa)
    if len(amostras) >= 5:
        arr = np.array([a["caixa"] for a in amostras])
        lisa = np.array([np.median(arr[max(0, i - 2): i + 3], axis=0) for i in range(len(arr))])
        for a, c in zip(amostras, lisa):
            a["caixa"] = [round(float(v), 4) for v in c]
    cob = len(amostras) * passo_s / max(info.duracao, 0.1)
    res = {"metodo": metodo, "passo_s": passo_s, "cobertura": round(min(1.0, cob), 2), "amostras": amostras,
           "tamanho_medio": _tamanho_medio(amostras)}
    if saida:
        Path(saida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def analisar_rosto_por_etapas(video: str, saida: str, tempo_max: float = 40.0, passo_s: float = 0.4) -> dict:
    """Mesma análise, em janelas de 20 s com progresso salvo: cabe no limite de tempo do chat em qualquer duração."""
    import time
    t0 = time.time()
    parcial = Path(saida).with_name("_rosto_parcial.json")
    nome, det = _detector()
    if not det:
        return {"concluido": True, "resultado": analisar_rosto(video, saida, passo_s)}
    info = sondar(video)
    est = json.loads(parcial.read_text(encoding="utf-8")) if parcial.exists() else None
    if not est or est.get("video") != str(video):
        est = {"video": str(video), "proximo": 0.0, "amostras": [], "seg_por_janela": None}
    lw = 360
    lh = int(round(info.altura * lw / info.largura / 2) * 2)
    janela, nesta = 20.0, 0
    while est["proximo"] < info.duracao - 1e-3:
        if nesta > 0 and time.time() - t0 + (est["seg_por_janela"] or 8.0) > tempo_max:
            break
        t1 = time.time()
        ini = est["proximo"]
        dur = min(janela, info.duracao - ini)
        for i, q in enumerate(LeitorDeQuadros(video, lw, lh, 1.0 / passo_s, inicio=ini, duracao=dur)):
            caixa = det(np.ascontiguousarray(q))
            if caixa:
                est["amostras"].append({"t": round(ini + i * passo_s, 3), "caixa": [round(float(v), 4) for v in caixa]})
        est["proximo"] = ini + dur
        est["seg_por_janela"] = time.time() - t1
        nesta += 1
        parcial.write_text(json.dumps(est, ensure_ascii=False), encoding="utf-8")
    if est["proximo"] < info.duracao - 1e-3:
        return {"concluido": False, "progresso": est["proximo"] / info.duracao, "detalhe": "procurando o rosto"}
    amostras = est["amostras"] or [{"t": 0.0, "caixa": [0.3, 0.22, 0.7, 0.52]}]
    if len(amostras) >= 5:
        arr = np.array([a["caixa"] for a in amostras])
        lisa = np.array([np.median(arr[max(0, i - 2): i + 3], axis=0) for i in range(len(arr))])
        for a, c in zip(amostras, lisa):
            a["caixa"] = [round(float(v), 4) for v in c]
    cob = len(est["amostras"]) * passo_s / max(info.duracao, 0.1)
    res = {"metodo": nome if est["amostras"] else "estimativa", "passo_s": passo_s, "cobertura": round(min(1.0, cob), 2),
           "amostras": amostras, "tamanho_medio": _tamanho_medio(amostras)}
    Path(saida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    parcial.unlink(missing_ok=True)
    return {"concluido": True, "resultado": res}


def _tamanho_medio(amostras):
    if not amostras:
        return None
    a = np.array([s["caixa"] for s in amostras])
    larg = float(np.median(a[:, 2] - a[:, 0]))
    return {"largura": round(larg, 3), "plano": "fechado" if larg > 0.38 else "medio" if larg > 0.2 else "aberto"}


class Rosto:
    """Consulta rápida: caixa do rosto (pixels) no instante t, interpolada."""

    def __init__(self, dados: dict | None, W: int, H: int):
        self.W, self.H = W, H
        am = (dados or {}).get("amostras") or [{"t": 0.0, "caixa": [0.3, 0.22, 0.7, 0.52]}]
        self.t = np.array([a["t"] for a in am])
        self.c = np.array([a["caixa"] for a in am])
        self.metodo = (dados or {}).get("metodo", "estimativa")

    def em(self, t: float):
        if len(self.t) == 1:
            c = self.c[0]
        else:
            c = np.array([np.interp(t, self.t, self.c[:, k]) for k in range(4)])
        return (c[0] * self.W, c[1] * self.H, c[2] * self.W, c[3] * self.H)

    def topo_cabeca(self, t: float) -> float:
        x0, y0, x1, y1 = self.em(t)
        return max(0.0, y0 - (y1 - y0) * 0.45)  # cabelo acima da testa

    def queixo(self, t: float) -> float:
        x0, y0, x1, y1 = self.em(t)
        return y1 + (y1 - y0) * 0.08
