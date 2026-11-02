"""Suavizar a pele (caixinha do card): alisa só a pele do rosto, mantendo a textura natural.

Precisa do OpenCV (cv2). Sem ele, a opção não aparece no card (o comando 'ambiente' informa).
Funciona assim: acha os tons de pele perto do rosto, aplica um filtro que alisa sem borrar bordas
(bilateral) e devolve uma parte do detalhe fino, para não ficar com cara de boneco."""
from __future__ import annotations

import numpy as np


def disponivel() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def suavizar(rgb: np.ndarray, caixa_rosto, forca: float = 0.6) -> np.ndarray:
    """rgb HxWx3 uint8; caixa_rosto (x0,y0,x1,y1) em pixels. Devolve nova imagem."""
    import cv2
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = caixa_rosto
    fw, fh = x1 - x0, y1 - y0
    if fw < 20 or fh < 20:
        return rgb
    # região de trabalho: rosto + testa + pescoço
    rx0, ry0 = int(max(0, x0 - fw * 0.25)), int(max(0, y0 - fh * 0.45))
    rx1, ry1 = int(min(w, x1 + fw * 0.25)), int(min(h, y1 + fh * 0.55))
    roi = rgb[ry0:ry1, rx0:rx1]
    if roi.size == 0:
        return rgb
    escala = min(1.0, 420 / max(roi.shape[:2]))  # trabalha menor: rápido e o filtro fica mais forte
    peq = cv2.resize(roi, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA) if escala < 1 else roi
    liso = cv2.bilateralFilter(peq, 9, 38, 7)
    liso = cv2.resize(liso, (roi.shape[1], roi.shape[0]), interpolation=cv2.INTER_LINEAR) if escala < 1 else liso
    # máscara de pele (YCrCb), suavizada e limitada a uma elipse do rosto
    ycc = cv2.cvtColor(roi, cv2.COLOR_RGB2YCrCb)
    pele = cv2.inRange(ycc, (40, 135, 85), (250, 175, 135)).astype(np.float32) / 255.0
    elipse = np.zeros(roi.shape[:2], np.float32)
    cx, cy = (x0 + x1) / 2 - rx0, (y0 + y1) / 2 - ry0 + fh * 0.05
    cv2.ellipse(elipse, (int(cx), int(cy)), (int(fw * 0.62), int(fh * 0.85)), 0, 0, 360, 1.0, -1)
    m = cv2.GaussianBlur(pele * elipse, (0, 0), max(2.0, fw * 0.03))
    # devolve parte do detalhe fino (poros), para não plastificar
    detalhe = roi.astype(np.float32) - cv2.GaussianBlur(roi, (0, 0), 1.2).astype(np.float32)
    alvo = liso.astype(np.float32) + detalhe * 0.35
    mix = (m * forca)[..., None]
    out = rgb.copy()
    out[ry0:ry1, rx0:rx1] = np.clip(roi * (1 - mix) + alvo * mix, 0, 255).astype(np.uint8)
    return out
