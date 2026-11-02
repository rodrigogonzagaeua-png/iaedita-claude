"""04 · Quebra de moldura — o vídeo vira um quadro pendurado numa sala clara (parede creme, sofá verde)
e, nas falas fortes, a pessoa SAI do quadro: a borda de cima desce para trás da cabeça e cabeça e
pescoço ficam na frente da moldura. Usa a pessoa recortada; sem recorte (ou com algo na frente do pescoço),
o quadro continua (inclinado, com "soco" de escala nos momentos fortes), só a cabeça não sai."""
from __future__ import annotations

import ctypes
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .. import desenho as d

try:  # OpenCV deixa cada quadro ~10x mais rápido; sem ele o estilo sai igual, só mais lento
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

INFO = {
    "id": "04-quebra-de-moldura",
    "nome": "Quebra de moldura",
    "precisa_recorte": True,
    "antes": 0.05,
    "depois": 0.6,
    # legenda: 1-2 palavras por vez, tinta escura numa etiqueta creme (a cor da parede), embaixo, dentro do quadro
    "legenda": {"peso": 800, "tamanho": 0.074, "cor": "#222729", "destaque": "#3F6E2A", "caixa": "#F2F0E7F2",
                "max_caracteres": 13, "max_linhas": 1, "posicao": "baixo", "animacao": "pop"},
    "eventos": {
        "moldura": "inicio, fim (2–8 s), som: o vídeo encolhe e vira um quadro inclinado na parede; "
                   "a pessoa fica DENTRO do quadro",
        "quebra": "inicio, fim (0,8–3 s), som: a borda de cima desce para trás da cabeça e a pessoa sai do "
                  "quadro (sozinha ou dentro de uma moldura)",
        "titulo": "inicio, fim, texto (2–5 palavras), marca (1 palavra do texto com faixa verde-limão, opcional): "
                  "título escuro na parede, acima da cabeça; só aparece enquanto há moldura ou quebra",
    },
}

TINTA = "#222729"
LIMA = "#D4ED80"
ENTRA, SAI = 0.55, 0.45          # quadro entrando / saindo (s)
Q_ENTRA, Q_SAI = 0.34, 0.38      # quebra: borda descendo / voltando (s)
JUNTAR = 0.9                     # eventos a menos de 0,9 s viram um bloco só (o quadro não pisca)
BASE = 0.885                     # base do quadro (fração da altura)
LADO_MIN = 0.07                  # margem lateral mínima do quadro
TOPO_LIVRE = 0.20                # topo da cabeça nunca acima disto quando o quadro está na tela
TITULO_Y = 0.125                 # topo do título (fora dos 11% de cima)
POP = 0.035                      # "soco" de escala na quebra
BALANCO = 1.8                    # graus de balanço do quadro
PERIODO = 6.5                    # segundos de um balanço completo
PESCOCO_MIN = 0.62               # parte do pescoço que precisa estar no recorte para a cabeça sair
PONTUACAO = ".,!?;:\"'“”‘’«»()"


def _limpa(p):
    return str(p).strip().strip(PONTUACAO).lower()


# ------------------------------------------------------------------ validação do plano

def validar(plano, duracao):
    p = []
    evs = plano["eventos"]
    quadros = [e for e in evs if e.get("tipo") in ("moldura", "quebra")]
    for e in evs:
        tipo, ini, fim = e.get("tipo"), e.get("inicio", 0), e.get("fim", 0)
        if tipo == "moldura" and fim - ini < 1.5:
            p.append(f"Moldura curta demais em {ini:.2f}s (mínimo 1,5 s; o quadro precisa de tempo para ser visto).")
        if tipo == "quebra" and not (0.6 <= fim - ini <= 6):
            p.append(f"Quebra em {ini:.2f}s com {fim - ini:.1f}s: use entre 0,8 e 3 s (máximo 6 s).")
        if tipo == "titulo":
            txt = str(e.get("texto", "")).strip()
            if not txt:
                p.append(f"Título vazio em {ini:.2f}s.")
            elif len(txt.split()) > 5 or len(txt) > 34:
                p.append(f"Título longo demais em {ini:.2f}s (máx. 5 palavras / 34 letras).")
            marca = _limpa(e.get("marca", ""))
            if marca and marca not in [_limpa(w) for w in txt.split()]:
                p.append(f"A 'marca' do título em {ini:.2f}s precisa ser uma palavra do próprio texto.")
            for q in (x for x in evs if x.get("tipo") == "quebra"):
                if ini < q["fim"] + 0.3 and fim > q["inicio"]:
                    p.append(f"Título em {ini:.2f}s se sobrepõe à quebra de {q['inicio']:.2f}s: em plano fechado ele "
                             f"não aparece. Comece o título uns 0,4 s depois do fim da quebra "
                             f"({q['fim'] + 0.4:.2f}s).")
                    break
            dentro = any(q["inicio"] - 0.05 <= ini and fim <= q["fim"] + SAI for q in quadros)
            if not dentro:
                p.append(f"Título em {ini:.2f}s fora de uma moldura/quebra: ele só aparece com o quadro na tela "
                         f"(coloque o título dentro do tempo de uma moldura ou quebra).")
    qs = sorted((e for e in evs if e.get("tipo") == "quebra"), key=lambda e: e["inicio"])
    for a, b in zip(qs, qs[1:]):
        if b["inicio"] < a["fim"] + 0.8:
            p.append(f"Quebras coladas em {b['inicio']:.2f}s: deixe pelo menos 0,8 s entre uma e outra.")
    if duracao > 10 and quadros:
        tempo = sum(e["fim"] - e["inicio"] for e in quadros if e.get("tipo") == "moldura")
        if tempo > duracao * 0.85:
            p.append("Moldura ocupando quase o vídeo todo: deixe respiros em tela cheia entre os blocos.")
    return p


# ------------------------------------------------------------------ preparação (uma vez)

def preparar(g):
    g.cache["e04_sala"] = _sala(g.W, g.H)
    _blocos(g)


def _blocos(g):
    if "e04_blocos" in g.cache:
        return g.cache["e04_blocos"]
    evs = sorted((e for e in g.plano["eventos"] if e.get("tipo") in ("moldura", "quebra")), key=lambda e: e["inicio"])
    blocos = []
    for e in evs:
        if blocos and e["inicio"] - blocos[-1]["t1"] < JUNTAR:
            blocos[-1]["t1"] = max(blocos[-1]["t1"], e["fim"])
            blocos[-1]["eventos"].append(e)
        else:
            blocos.append({"t0": e["inicio"], "t1": e["fim"], "eventos": [e]})
    for b in blocos:
        _geometria(g, b)
    # plano fechado: na quebra a pessoa avança e ocupa o alto da tela, onde fica o título.
    # Título que só apareceria um instante (piscada) não aparece; o resto some e volta com suavidade.
    ocultos = set()
    if g.tem_mascara:
        for e in g.plano["eventos"]:
            if e.get("tipo") != "titulo":
                continue
            visivel = e["fim"] - e["inicio"]
            for b in blocos:
                if not (b["corte"] and b["quebra_ok"]):
                    continue
                for q in b["eventos"]:
                    if q.get("tipo") == "quebra":
                        visivel -= max(0.0, min(e["fim"], q["fim"] + Q_SAI) - max(e["inicio"], q["inicio"]))
            if visivel < 0.9:
                ocultos.add((round(e["inicio"], 3), str(e.get("texto", ""))))
    g.cache["e04_tit_ocultos"] = ocultos
    g.cache["e04_blocos"] = blocos
    return blocos


def _geometria(g, b):
    """Escala e alturas do quadro para o bloco inteiro (fixas: o quadro não 'treme' com a pessoa)."""
    W, H = g.W, g.H
    ts = np.arange(b["t0"], b["t1"] + SAI + 1e-6, 0.2)
    cx = np.array([g.rosto.em(float(t)) for t in ts])
    fh = cx[:, 3] - cx[:, 1]
    topo = np.maximum(0.0, cx[:, 1] - fh * 0.45)
    topo_min = float(topo.min())
    alt_tit = 0
    for e in g.plano["eventos"]:
        if e.get("tipo") == "titulo" and e["inicio"] < b["t1"] + SAI and e["fim"] > b["t0"]:
            alt_tit = max(alt_tit, _titulo(g, e).height)
    quebra_ok = bool(np.median(cx[:, 3]) < 0.76 * H)
    # sem a cabeça saindo, a quebra vira um "soco" maior e o quadro inclina mais: reserva esse espaço
    sai_cabeca = g.tem_mascara and quebra_ok
    pop = POP if sai_cabeca else POP * 1.8
    livre = TOPO_LIVRE * H
    if alt_tit:
        livre = max(livre, TITULO_Y * H + alt_tit * 0.92 + (0.022 if sai_cabeca else 0.04) * H)
    s = (BASE * H - livre) / max(1.0, (H - topo_min) * (1 + pop))
    s = float(d.limitar(s, 0.58, 1 - 2 * LADO_MIN))
    topo_m = max(0.0, topo_min - 0.03 * H / s)
    # cabeça cortada no alto do vídeo original (plano fechado): na quebra a pessoa "avança" para a câmera
    # até o corte sair da tela — senão apareceria uma linha reta no alto da cabeça, em cima da parede
    corte = bool((cx[:, 1] - fh * 0.6).min() < 0.015 * H)
    s_q = max(s, 0.91 / (1 + POP)) if corte else s
    b.update(s=s, s_q=s_q, corte=corte, topo_m=topo_m, cy=(topo_m + H) / 2, quebra_ok=quebra_ok)


# ------------------------------------------------------------------ sala (fundo pintado uma vez)

def _sala(W, H):
    """Sala editorial clara do visual aprovado: parede creme com luz, moldura de gesso, janela à direita,
    abajur à esquerda e sofá verde embaixo. Desenhada em 2x para bordas limpas."""
    ss = 2
    sx, sy = W * ss / 1080, H * ss / 1920
    w2, h2 = W * ss, H * ss
    img = Image.new("RGBA", (w2, h2), d.cor("#E4E0D5"))
    # luz quente no alto à esquerda + leve sombra para a direita
    yy, xx = np.mgrid[0:h2:4, 0:w2:4].astype(np.float32)
    dist = np.sqrt(((xx - 0.18 * w2) / (1.15 * w2)) ** 2 + ((yy - 0.20 * h2) / (1.13 * h2)) ** 2)
    luz = np.clip(1 - dist / 0.58, 0, 1) * 0.62
    k = np.clip(((xx / w2) * 0.94 + (yy / h2) * 0.34 - 0.40) / 0.9, 0, 1) * 0.085
    camada = np.zeros(luz.shape + (4,), np.float32)
    camada[..., 0], camada[..., 1], camada[..., 2] = 255, 247, 220
    camada[..., 3] = luz * 255
    img.alpha_composite(Image.fromarray(camada.astype(np.uint8), "RGBA").resize((w2, h2), Image.BILINEAR))
    esc = np.zeros(luz.shape + (4,), np.uint8)
    esc[..., 3] = (k * 255).astype(np.uint8)
    img.alpha_composite(Image.fromarray(esc, "RGBA").resize((w2, h2), Image.BILINEAR))
    dr = ImageDraw.Draw(img)

    def R(x0, y0, x1, y1):
        return [x0 * sx, y0 * sy, x1 * sx, y1 * sy]

    # moldura de gesso na parede
    lw = max(2, int(3 * sx))
    dr.rectangle(R(95, 120, 745, 1050), outline=d.cor("#C2BCAE"), width=lw)
    dr.rectangle(R(113, 138, 727, 1032), outline=d.cor("#C2BCAE"), width=lw)
    # janela à direita (em perspectiva)
    jan = Image.new("RGBA", (int(295 * sx), int(1130 * sy)), d.cor("#786B55"))
    jd = ImageDraw.Draw(jan)
    jd.rectangle([20 * sx, 20 * sy, jan.width - 20 * sx, jan.height - 20 * sy], fill=d.cor("#AD9E86"))
    vid = d.painel(jan.width - 56 * sx, jan.height - 56 * sy, raio=0, gradiente=("#D0DBCA", "#7C9690"))
    jan.alpha_composite(vid, (int(28 * sx), int(28 * sy)))
    jd.rectangle([28 * sx, 28 * sy, jan.width - 28 * sx, jan.height - 28 * sy], outline=d.cor("#766C58"),
                 width=max(2, int(12 * sx)))
    jd.rectangle([110 * sx, 28 * sy, 120 * sx, jan.height - 28 * sy], fill=d.cor("#766C58"))
    cantos = [(860 * sx, 215 * sy), (1165 * sx, 175 * sy), (1165 * sx, 1370 * sy), (860 * sx, 1318 * sy)]
    jan_p = d.perspectiva(jan, cantos, (w2, h2))
    sombra_j = Image.new("RGBA", (w2, h2), (36, 40, 43, 0))
    sombra_j.putalpha(jan_p.getchannel("A").point(lambda v: int(v * 0.13)).filter(ImageFilter.GaussianBlur(35 * sx)))
    img.alpha_composite(sombra_j, (int(-40 * sx), int(24 * sy)))
    img.alpha_composite(jan_p)
    # piso
    dr = ImageDraw.Draw(img)
    dr.rectangle(R(0, 1370, 1080, 1920), fill=d.cor("#C3B9A5"))
    dr.rectangle(R(0, 1370, 1080, 1382), fill=d.cor("#A99D88"))
    # sofá: encosto com sombra + assento
    enc = d.painel(1260 * sx, 490 * sy, raio=int(110 * sx), gradiente=("#879C8B", "#647C6A"))
    s_img, (dx, dy) = d.sombra(enc, raio=30 * sx, opacidade=0.13, desloc=(0, 35 * sy))
    img.alpha_composite(s_img, (int(-90 * sx + dx), int(1280 * sy + dy)))
    ass = d.painel(1040 * sx, 245 * sy, raio=int(60 * sx), fundo="#7E9482", borda="#FFFFFF22",
                   larg_borda=max(2, int(4 * sx)))
    img.alpha_composite(ass, (int(20 * sx), int(1435 * sy)))
    # abajur
    dr = ImageDraw.Draw(img)
    dr.rectangle(R(40, 680, 47, 1100), fill=d.cor("#685A40"))
    brilho = Image.new("RGBA", (int(520 * sx), int(480 * sy)), (0, 0, 0, 0))
    ImageDraw.Draw(brilho).ellipse([130 * sx, 120 * sy, 390 * sx, 360 * sy], fill=(255, 240, 191, 90))
    brilho = brilho.filter(ImageFilter.GaussianBlur(70 * sx))
    img.alpha_composite(brilho, (int(-215 * sx), int(440 * sy)))
    cup = Image.new("RGBA", (int(180 * sx), int(140 * sy)), (0, 0, 0, 0))
    ImageDraw.Draw(cup).ellipse([0, 0, cup.width - 1, cup.height * 2], fill=d.cor("#D8C8A1"))
    img.alpha_composite(cup, (int(-45 * sx), int(610 * sy)))
    img = img.resize((W, H), Image.LANCZOS)
    return np.ascontiguousarray(np.asarray(img))


# ------------------------------------------------------------------ título

def _titulo(g, e):
    W, H = g.W, g.H
    texto = " ".join(str(e.get("texto", "")).split())
    marca = _limpa(e.get("marca", ""))
    chave = ("e04_tit", texto, marca, W)
    if chave in g.cache:
        return g.cache[chave]
    f, linhas, al = d.ajustar_texto(texto, W * 0.80, H * 0.17, 800, tam_max=int(W * 0.093),
                                    tam_min=int(W * 0.062), max_linhas=2, entrelinha=1.04)
    trilha = -0.022 * f.size          # letras um pouco mais juntas, como no título aprovado

    def larg(txt):
        return sum(f.getlength(ch) + trilha for ch in txt) - trilha if txt else 0

    larg_max = max(larg(l) for l in linhas)
    pad = int(f.size * 0.3)
    cam = Image.new("RGBA", (int(larg_max + pad * 2), int(al * len(linhas) + pad * 1.6)), (0, 0, 0, 0))
    dr = ImageDraw.Draw(cam)
    esp = f.getlength(" ") + trilha
    for li, linha in enumerate(linhas):
        x, y = pad, pad * 0.5 + li * al
        for p in linha.split():
            wp = larg(p)
            if marca and _limpa(p) == marca:
                # faixa verde-limão atrás da palavra marcada (como marca-texto)
                faixa = d.painel(wp + f.size * 0.28, f.size * 0.86, raio=int(f.size * 0.12), fundo=LIMA)
                faixa = faixa.rotate(1.5, resample=Image.BICUBIC, expand=True)
                cam.alpha_composite(faixa, (int(x - f.size * 0.14), int(y + f.size * 0.13)))
                dr = ImageDraw.Draw(cam)
            for ch in p:
                dr.text((x, y), ch, font=f, fill=d.cor(TINTA))
                x += f.getlength(ch) + trilha
            x += esp
    cam.info["pad"], cam.info["pad_y"] = pad, int(pad * 0.5)
    g.cache[chave] = cam
    return cam


# ------------------------------------------------------------------ estado no instante t (só função do tempo)

def _estado(c):
    """Bloco ativo, presença do quadro P (0-1), quebra Q (com passada de mola) e Qs (suave, sem passada)."""
    t = c.t
    blocos = c.g.cache["e04_blocos"] if "e04_blocos" in c.g.cache else _blocos(c.g)
    for b in blocos:
        if b["t0"] - 0.02 <= t <= b["t1"] + SAI:
            kin = d.mapear(t, b["t0"], b["t0"] + ENTRA)
            pin = 1 - (1 - kin) ** 3
            pout = 1 - d.suave(d.mapear(t, b["t1"], b["t1"] + SAI))
            P = pin * pout
            Q = Qs = 0.0
            for e in b["eventos"]:
                if e.get("tipo") != "quebra" or t < e["inicio"]:
                    continue
                k = d.mapear(t, e["inicio"], e["inicio"] + Q_ENTRA)
                qout = 1 - d.suave(d.mapear(t, e["fim"], e["fim"] + Q_SAI))
                Q = max(Q, d.mola(k, 1.15) * qout)
                Qs = max(Qs, d.suave(d.mapear(t, e["inicio"], e["inicio"] + Q_ENTRA * 1.35)) * qout)
            return b, P, Q, Qs, kin
    return None, 0.0, 0.0, 0.0, 0.0


def _matriz(c, b, P, Q, Qs, kin, w):
    """Transformação do vídeo original para a tela: encolhe para a base do quadro, inclina e balança.
    w (0-1) = quanto a cabeça sai do quadro nesta quebra (0 = "soco": sem recorte ou pescoço não confiável)."""
    W, H = c.W, c.H
    s_base = d.lerp(b["s"], b["s_q"], Qs * w)
    # sem a cabeça saindo, a quebra vira um "soco" mais forte com o quadro se inclinando
    pop = d.lerp(POP * 1.8, POP, w)
    s = d.lerp(1.0, s_base, P) * (1 + pop * Q)
    cy = d.lerp(H, BASE * H, P)
    tilt_in = -3.2 * (1 - d.mola(kin, 1.5))
    theta = P * (BALANCO * math.sin(2 * math.pi * (c.t - b["t0"]) / PERIODO) + tilt_in)
    theta -= 1.6 * Q * P * (1 - w)
    ax, ay = W / 2, H
    pcx, pcy = W / 2, s * (b["cy"] - ay) + cy                   # centro de giro = centro do quadro
    a = math.radians(theta)
    co, si = math.cos(a), math.sin(a)
    Rm = np.array([[co, -si], [si, co]])
    tr = Rm @ np.array([W / 2 - s * ax - pcx, cy - s * ay - pcy]) + np.array([pcx, pcy])
    return np.hstack([Rm * s, tr[:, None]]), s


def _aplicar(M, pts):
    pts = np.asarray(pts, np.float64)
    return pts @ M[:, :2].T + M[:, 2]


def _ret_arredondado(x0, y0, x1, y1, r, n=10):
    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = []
    for (cx, cy, a0) in ((x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _linha_da_quebra(c, m_np):
    """Altura (no vídeo original) da borda de cima durante a quebra (logo abaixo do queixo) e a confiança
    (0-1) de que a cabeça pode sair. Se o pescoço não está inteiro no recorte (microfone, celular, cartão
    ou falha do recorte na frente dele), a cabeça sairia "decepada": a confiança cai e a quebra vira "soco"."""
    W, H = c.W, c.H
    x0, y0, x1, y1 = c.rosto
    fw, fh = x1 - x0, y1 - y0
    cobertura = 1.0
    if m_np is not None:
        cx = (x0 + x1) / 2
        xa, xb = int(max(0, cx - fw * 0.16)), int(min(W, cx + fw * 0.16))
        ya, yb = int(min(H - 2, y1 + fh * 0.03)), int(min(H - 1, y1 + fh * 0.13))
        if xb > xa and yb > ya:
            cobertura = float(m_np[ya:yb, xa:xb].mean()) / 255.0
    k = d.suave(d.mapear(cobertura, PESCOCO_MIN, 0.92))
    confia = d.suave(d.mapear(cobertura, PESCOCO_MIN, PESCOCO_MIN + 0.12))
    return min(d.lerp(y1 - 0.03 * fh, y1 + 0.10 * fh, k), 0.82 * H), confia


# ------------------------------------------------------------------ ferramentas (OpenCV ou reserva Pillow/numpy)

class _ArrowSchema(ctypes.Structure):
    pass


_ArrowSchema._fields_ = [("format", ctypes.c_char_p), ("name", ctypes.c_char_p), ("metadata", ctypes.c_char_p),
                         ("flags", ctypes.c_int64), ("n_children", ctypes.c_int64),
                         ("children", ctypes.POINTER(ctypes.POINTER(_ArrowSchema))),
                         ("dictionary", ctypes.c_void_p), ("release", ctypes.c_void_p), ("private", ctypes.c_void_p)]


class _ArrowArray(ctypes.Structure):
    pass


_ArrowArray._fields_ = [("length", ctypes.c_int64), ("null_count", ctypes.c_int64), ("offset", ctypes.c_int64),
                        ("n_buffers", ctypes.c_int64), ("n_children", ctypes.c_int64),
                        ("buffers", ctypes.POINTER(ctypes.c_void_p)),
                        ("children", ctypes.POINTER(ctypes.POINTER(_ArrowArray))),
                        ("dictionary", ctypes.c_void_p), ("release", ctypes.c_void_p), ("private", ctypes.c_void_p)]

try:
    _capsula = ctypes.pythonapi.PyCapsule_GetPointer
    _capsula.restype = ctypes.c_void_p
    _capsula.argtypes = [ctypes.py_object, ctypes.c_char_p]
except Exception:  # noqa: BLE001
    _capsula = None


def _np(img):
    """Imagem PIL -> numpy SEM cópia (exportação Arrow do Pillow 11.2+), só para leitura.
    Devolve (array, segurar): mantenha 'segurar' vivo enquanto usar o array. Se não der, faz a cópia normal."""
    try:
        # só RGBA criada pelo próprio Pillow (imagem "emprestada" de um array, readonly, derruba o Pillow)
        if _capsula is None or img.mode != "RGBA" or img.readonly or not hasattr(img, "__arrow_c_array__"):
            raise ValueError
        bandas = 4
        w, h = img.size
        sch, arr = img.__arrow_c_array__()
        s = _ArrowSchema.from_address(_capsula(sch, b"arrow_schema"))
        a = _ArrowArray.from_address(_capsula(arr, b"arrow_array"))
        if s.format == b"+w:4" and a.n_children == 1 and a.length == w * h:
            ch = a.children[0].contents
            if ch.n_buffers != 2 or ch.length != w * h * 4 or ch.offset or a.offset:
                raise ValueError
            ptr = ch.buffers[1]
        else:
            raise ValueError
        if not ptr:
            raise ValueError
        buf = (ctypes.c_uint8 * (w * h * bandas)).from_address(ptr)
        v = np.frombuffer(buf, np.uint8).reshape((h, w, bandas))
        v.flags.writeable = False
        for (x, y) in ((0, 0), (w - 1, h - 1), (w // 2, h // 3), (w // 3, h - 2)):   # conferência barata
            if tuple(int(k) for k in v[y, x]) != tuple(img.getpixel((x, y))):
                raise ValueError
        return v, (sch, arr, buf, img)
    except Exception:  # noqa: BLE001
        return np.asarray(img), None


def _poligono(tam, pts):
    w, h = tam
    if cv2 is not None:
        z = np.zeros((h, w), np.uint8)
        cv2.fillPoly(z, [np.round(np.asarray(pts) * 16).astype(np.int32)], 255, cv2.LINE_AA, 4)
        return z
    m = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(m).polygon([(x * 2, y * 2) for x, y in pts], fill=255)
    return np.asarray(m.resize((w, h), Image.BILINEAR))


def _contorno(tam, pts, esp):
    w, h = tam
    if cv2 is not None:
        z = np.zeros((h, w), np.uint8)
        cv2.polylines(z, [np.round(np.asarray(pts) * 16).astype(np.int32)], True, 255,
                      max(1, int(round(esp))), cv2.LINE_AA, 4)
        return z
    m = Image.new("L", (w * 2, h * 2), 0)
    p2 = [(x * 2, y * 2) for x, y in pts]
    ImageDraw.Draw(m).line(p2 + [p2[0]], fill=255, width=max(2, int(round(esp * 2))), joint="curve")
    return np.asarray(m.resize((w, h), Image.BILINEAR))


def _deformar(arr, M, tam, repetir=True):
    """Leva o quadro original para a tela. repetir=False: fora do vídeo é 0 (use na máscara da pessoa,
    senão o ombro encostado na borda se "estica" para fora do vídeo e vira uma barra sobre a parede)."""
    if cv2 is not None:
        return cv2.warpAffine(arr, M, tam, flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE if repetir else cv2.BORDER_CONSTANT, borderValue=0)
    inv = np.linalg.inv(np.vstack([M, [0, 0, 1]]))[:2]
    modo = "L" if arr.ndim == 2 else "RGBA"
    im = Image.fromarray(np.ascontiguousarray(arr), modo).transform(tam, Image.AFFINE, tuple(inv.reshape(-1)),
                                                                    Image.BILINEAR)
    return np.asarray(im)


def _mult(a, b):
    """a * b / 255 (uint8, mesmo número de canais)."""
    if cv2 is not None:
        return cv2.multiply(a, b, scale=1 / 255)
    return ((a.astype(np.uint16) * b + 127) // 255).astype(np.uint8)


def _escalar(a, k):
    """a * k (uint8, k entre 0 e 1)."""
    if cv2 is not None:
        return cv2.convertScaleAbs(a, alpha=float(k))
    return (a.astype(np.float32) * float(k)).astype(np.uint8)


def _inv(a):
    return cv2.bitwise_not(a) if cv2 is not None else 255 - a


def _max(a, b):
    return cv2.max(a, b) if cv2 is not None else np.maximum(a, b)


def _quatro(a, ultimo=None):
    """1 canal -> 4 canais (o 4º pode ser outro)."""
    u = a if ultimo is None else ultimo
    if cv2 is not None:
        return cv2.merge([a, a, a, u])
    return np.dstack([a, a, a, u])


def _somar(a, b):
    if cv2 is not None:
        return cv2.add(a, b)
    return np.minimum(a.astype(np.uint16) + b, 255).astype(np.uint8)


def _sombra_de(alfa, desloc_y, raio):
    h, w = alfa.shape
    f = 8
    pw, ph = max(2, w // f), max(2, h // f)
    if cv2 is not None:
        p = cv2.resize(alfa, (pw, ph), interpolation=cv2.INTER_AREA)
        p = cv2.GaussianBlur(p, (0, 0), max(0.6, raio / f))
        p = cv2.warpAffine(p, np.float32([[1, 0, 0], [0, 1, desloc_y / f]]), (pw, ph))
        return cv2.resize(p, (w, h), interpolation=cv2.INTER_LINEAR)
    im = Image.fromarray(alfa, "L").resize((pw, ph), Image.BILINEAR).filter(ImageFilter.GaussianBlur(raio / f))
    im = im.transform((pw, ph), Image.AFFINE, (1, 0, 0, 0, 1, -desloc_y / f), Image.BILINEAR)
    return np.asarray(im.resize((w, h), Image.BILINEAR))


def _pescoco(pessoa, pts, desfoque):
    """Soma à máscara um retângulo suave entre o queixo e a borda (só na caixinha dele: barato)."""
    h, w = pessoa.shape
    x0, y0 = int(max(0, pts[:, 0].min() - desfoque * 3)), int(max(0, pts[:, 1].min() - desfoque * 3))
    x1, y1 = int(min(w, pts[:, 0].max() + desfoque * 3)), int(min(h, pts[:, 1].max() + desfoque * 3))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return pessoa
    pm = _poligono((x1 - x0, y1 - y0), pts - (x0, y0))
    if cv2 is not None:
        pm = cv2.GaussianBlur(pm, (0, 0), desfoque)
    if not pessoa.flags.writeable:
        pessoa = pessoa.copy()
    pessoa[y0:y1, x0:x1] = _max(np.ascontiguousarray(pessoa[y0:y1, x0:x1]), pm)
    return pessoa


def _afinar(fora, W):
    """Aperta 1-2 px a borda do recorte que sai do quadro (a máscara vem em resolução menor e, ampliada,
    deixa um halo cinza em volta da bochecha e da orelha sobre a parede creme)."""
    if cv2 is None:
        return fora
    k = 3 if W < 1000 else 5
    fora = cv2.erode(fora, np.ones((k, k), np.uint8))
    return cv2.GaussianBlur(fora, (0, 0), 0.8)


def _so_cabeca(fora, cabeca, y_linha):
    """Tira manchas soltas do recorte acima do quadro: fica só o que encosta na cabeça ou na borda de cima."""
    if cv2 is None:
        return fora
    f = 4
    peq = (fora[::f, ::f] > 90).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(peq, connectivity=8)
    if n <= 2:
        return fora
    ax0, ay0, ax1, ay1 = [v / f for v in cabeca]
    manter = np.zeros(n, bool)
    for i in range(1, n):
        x, y, w, h, area = st[i]
        toca_cabeca = x < ax1 and x + w > ax0 and y < ay1 and y + h > ay0
        toca_linha = y + h >= y_linha / f - 3
        manter[i] = (toca_cabeca or toca_linha) and area >= 6
    if manter[1:].all():
        return fora
    m = (manter[lab] * 255).astype(np.uint8)
    m = cv2.dilate(m, np.ones((3, 3), np.uint8))
    m = cv2.resize(m, (fora.shape[1], fora.shape[0]), interpolation=cv2.INTER_LINEAR)
    return _mult(fora, m)


def _faixas(pts, n, pad, tam):
    """Retângulos (sem sobreposição) que cobrem só as bordas do quadro: cima, baixo, esquerda, direita."""
    w, h = tam
    k = n + 1
    tl, tr, br, bl = pts[:k], pts[k:2 * k], pts[2 * k:3 * k], pts[3 * k:]
    top = np.vstack([tl, tr])
    bot = np.vstack([br, bl])
    ya0, ya1 = int(max(0, top[:, 1].min() - pad)), int(min(h, top[:, 1].max() + pad))
    yb0, yb1 = int(max(0, bot[:, 1].min() - pad)), int(min(h, bot[:, 1].max() + pad))
    if yb0 <= ya1:
        return [(0, ya0, w, max(ya1, yb1))]
    esq = np.vstack([tl, bl])
    dir_ = np.vstack([tr, br])
    out = [(0, ya0, w, ya1),
           (int(max(0, esq[:, 0].min() - pad)), ya1, int(min(w, esq[:, 0].max() + pad)), yb0),
           (int(max(0, dir_[:, 0].min() - pad)), ya1, int(min(w, dir_[:, 0].max() + pad)), yb0),
           (0, yb0, w, yb1)]
    return [r for r in out if r[2] > r[0] and r[3] > r[1]]


def _miolo(pts, n, pad, tam):
    """Retângulo reto bem dentro do quadro (longe das bordas, do friso e da pessoa saindo): ali o resultado
    é o próprio vídeo. É o complemento exato das faixas de _faixas."""
    w, h = tam
    k = n + 1
    tl, tr, br, bl = pts[:k], pts[k:2 * k], pts[2 * k:3 * k], pts[3 * k:]
    y0 = int(math.ceil(np.vstack([tl, tr])[:, 1].max() + pad)) + 1
    y1 = int(math.floor(np.vstack([br, bl])[:, 1].min() - pad)) - 1
    x0 = int(math.ceil(np.vstack([tl, bl])[:, 0].max() + pad)) + 1
    x1 = int(math.floor(np.vstack([tr, br])[:, 0].min() - pad)) - 1
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    return x0, y0, x1, y1


def _em_volta(miolo, tam):
    """Retângulos que cobrem a região toda MENOS o miolo (cima, baixo, esquerda, direita)."""
    w, h = tam
    if miolo is None:
        return [(0, 0, w, h)]
    x0, y0, x1, y1 = miolo
    out = [(0, 0, w, y0), (0, y1, w, h), (0, y0, x0, y1), (x1, y0, w, y1)]
    return [r for r in out if r[2] > r[0] and r[3] > r[1]]


# ------------------------------------------------------------------ quadro

N_ARCO = 10


def quadro(c):
    b, P, Q, Qs, kin = _estado(c)
    if b is None or P <= 0.002:
        return _com_titulo(c, c.fonte, None, 0.0)
    W, H = c.W, c.H
    com_recorte = c.mascara is not None
    quebra = com_recorte and b["quebra_ok"]
    m_np = segura_m = None
    if com_recorte:
        masc = c.mascara if c.mascara.size == (W, H) else c.mascara.resize((W, H), Image.BILINEAR)
        m_np = np.asarray(masc if masc.mode == "L" else masc.convert("L"))
    # ---------------- onde fica a borda de cima do quadro (no vídeo original)
    x0f, y0f, x1f, y1f = c.rosto
    fh, fw = y1f - y0f, x1f - x0f
    linha, w = y1f, (1.0 if quebra else 0.0)
    if quebra and Q > 0.002:
        linha, w = _linha_da_quebra(c, m_np)
    M, s = _matriz(c, b, P, Q, Qs, kin, w)
    fonte_np, segura_f = _np(c.fonte if c.fonte.mode == "RGBA" else c.fonte.convert("RGBA"))
    q = min(Q, 1.0) * w
    topo = P * d.lerp(b["topo_m"], linha, Q * w)   # com a passada da mola
    raio = 0.034 * W * P / s
    borda = max(2.0, 0.0042 * W)
    pts = _aplicar(M, _ret_arredondado(0, topo, W, H, raio, N_ARCO))
    # região de trabalho (só onde há quadro, cabeça ou sombra)
    cab = _aplicar(M, [(x0f - fw * 0.6, y0f - fh * 0.9), (x1f + fw * 0.6, y0f - fh * 0.9)])
    xs = np.concatenate([pts[:, 0], cab[:, 0]])
    ys = np.concatenate([pts[:, 1], cab[:, 1]])
    pad = int(0.06 * W)
    rx0, ry0 = max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad)
    rx1, ry1 = min(W, int(xs.max()) + pad), min(H, int(ys.max()) + pad + int(0.03 * H))
    tam = (rx1 - rx0, ry1 - ry0)
    Mr = M.copy()
    Mr[:, 2] -= (rx0, ry0)
    off = np.array([rx0, ry0], np.float64)
    pts_r = pts - off
    conteudo = _deformar(fonte_np, Mr, tam)
    cartao = _poligono(tam, pts_r)
    alfa = cartao
    pessoa = _deformar(m_np, Mr, tam, repetir=False) if com_recorte else None
    if pessoa is not None and q > 0.002:
        # pescoço de segurança: costura queixo e borda mesmo se o recorte falhar ali
        cxf = (x0f + x1f) / 2
        pesc = _aplicar(Mr, [(cxf - fw * 0.2, y1f - fh * 0.15), (cxf + fw * 0.2, y1f - fh * 0.15),
                             (cxf + fw * 0.2, linha + 4), (cxf - fw * 0.2, linha + 4)])
        pessoa = _pescoco(pessoa, pesc, max(1.0, fw * s * 0.04))
        # só a parte da pessoa ACIMA da borda de cima sai do quadro
        # (só dentro da largura do vídeo original: nada "sai" pelas laterais)
        acima = _aplicar(Mr, [(0, topo + 2.5 / s), (W, topo + 2.5 / s), (W, -3 * H), (0, -3 * H)])
        fora = _mult(pessoa, _poligono(tam, acima))
        cb = _aplicar(Mr, [(x0f - fw * 0.1, y0f - fh * 0.6), (x1f + fw * 0.1, y1f)])
        y_lin = float(_aplicar(Mr, [((x0f + x1f) / 2, topo)])[0][1])
        fora = _so_cabeca(fora, (cb[0][0], cb[0][1], cb[1][0], cb[1][1]), y_lin)
        fora = _afinar(fora, W)
        if w < 0.999:
            fora = _escalar(fora, w)
        alfa = _max(cartao, fora)
        # a cabeça que sai do quadro fica sobre a sala: fora do quadro usa a borda sem a cor do fundo antigo
        conteudo_p = _deformar(np.asarray(c.fonte_pessoa), Mr, tam)
    else:
        conteudo_p = None
    del segura_f, segura_m           # daqui em diante só as cópias deformadas são usadas
    # ---------------- composição: o miolo do quadro é só o vídeo (cópia direta); a mistura com a sala,
    # a sombra e a pessoa saindo só são calculadas nas faixas em volta do miolo
    sombra = _escalar(_sombra_de(alfa, 0.024 * H * P, 0.045 * W), 0.36 * P)
    sala = c.g.cache["e04_sala"][ry0:ry1, rx0:rx1]
    final = c.g.cache["e04_sala"].copy()
    out = final[ry0:ry1, rx0:rx1]
    pad_b = 0.024 * W + borda * 2 + 3           # largura das faixas: borda + friso + folga
    miolo = _miolo(pts_r, N_ARCO, pad_b, tam)
    for (px0, py0, px1, py1) in _em_volta(miolo, tam):
        a = alfa[py0:py1, px0:px1]
        ia = _inv(a)
        peso = _mult(ia, _inv(sombra[py0:py1, px0:px1]))
        cont = conteudo[py0:py1, px0:px1]
        if conteudo_p is not None:  # dentro do quadro o vídeo original; fora dele, a pessoa com a borda limpa
            ct = cartao[py0:py1, px0:px1]
            cont = _somar(_mult(cont, _quatro(ct)), _mult(conteudo_p[py0:py1, px0:px1], _quatro(_inv(ct))))
        out[py0:py1, px0:px1] = _somar(_mult(cont, _quatro(a)),
                                       _mult(sala[py0:py1, px0:px1], _quatro(peso, ia)))
    if miolo is not None:
        mx0, my0, mx1, my1 = miolo
        out[my0:my1, mx0:mx1] = conteudo[my0:my1, mx0:mx1]
    # ---------------- borda clara do quadro (some atrás da pessoa na borda de cima) + friso interno
    anel = _contorno(tam, pts_r, borda)
    if pessoa is not None and q > 0.002:
        faixa = _aplicar(Mr, [(raio, topo - 3 * borda / s), (W - raio, topo - 3 * borda / s),
                              (W - raio, topo + 3 * borda / s), (raio, topo + 3 * borda / s)])
        tira = _mult(pessoa, _poligono(tam, faixa))
        anel = _mult(anel, _inv(tira if w >= 0.999 else _escalar(tira, w)))
    elif pessoa is None:
        # sem recorte: a borda de cima fica aberta no meio (assinatura do estilo) e abre mais na quebra
        ab = 0.18 + 0.07 * min(Q, 1.0)
        faixa = _aplicar(Mr, [(W * ab, topo - 4 * borda / s), (W * (1 - ab), topo - 4 * borda / s),
                              (W * (1 - ab), topo + 4 * borda / s), (W * ab, topo + 4 * borda / s)])
        anel = _mult(anel, _inv(_poligono(tam, faixa)))
    a_anel = _escalar(anel, 0.66 * P)
    ins = 0.024 * W / s
    if pessoa is not None:
        # friso fino por dentro do quadro, que passa ATRÁS da pessoa (dá profundidade)
        friso = _contorno(tam, _aplicar(Mr, _ret_arredondado(ins, topo + ins, W - ins, H - ins,
                                                             max(0.0, raio - ins), N_ARCO)), max(1.0, 0.0018 * W))
        a_anel = _max(a_anel, _escalar(_mult(friso, _inv(pessoa)), 0.3 * P))
    # clareia só nas faixas das bordas (o miolo do quadro não muda: economiza tempo)
    for (fx0, fy0, fx1, fy1) in _faixas(pts_r, N_ARCO, pad_b, tam):
        o = out[fy0:fy1, fx0:fx1]
        a4 = _quatro(np.ascontiguousarray(a_anel[fy0:fy1, fx0:fx1]))
        out[fy0:fy1, fx0:fx1] = _somar(o, _mult(_inv(o), a4))
    img = Image.fromarray(final, "RGBA")
    topo_cab = float(_aplicar(M, [((x0f + x1f) / 2, max(0.0, y0f - fh * 0.5))])[0][1])
    # o título fica acima da cabeça E acima da borda de cima do quadro (nunca encosta nele)
    topo_quadro = float(pts[:, 1].min()) - 0.004 * H
    return _com_titulo(c, img, min(topo_cab, topo_quadro), P)


def _com_titulo(c, img, topo_cab, P):
    tits = [e for e in c.eventos if e.get("tipo") == "titulo"]
    if not tits or P <= 0.01:
        return img
    W, H = c.W, c.H
    ocultos = c.g.cache.get("e04_tit_ocultos", set())
    for e in tits:
        if (round(e["inicio"], 3), str(e.get("texto", ""))) in ocultos:
            continue
        k = d.envelope(c.t, e["inicio"], e["fim"], 0.4, 0.25) * P
        if k <= 0.01:
            continue
        cam = _titulo(c.g, e)
        alt = cam.height * 0.92
        sobe = d.saida(d.mapear(c.t, e["inicio"], e["inicio"] + 0.45))
        y = TITULO_Y * H
        if topo_cab is not None:
            y = max(0.105 * H, min(y, topo_cab - 0.015 * H - alt))
            # sem espaço acima da cabeça (ex.: pessoa avançando na quebra em plano fechado): o título some
            sobra = topo_cab - 0.008 * H - (y + alt)
            k *= d.limitar(1 + sobra / (0.03 * H))
            if k <= 0.01:
                continue
        y += (1 - sobe) * 0.022 * H
        if img is c.fonte:
            img = img.copy()
        d.colar_em(img, cam, (0.075 * W - cam.info.get("pad", 0), y - cam.info.get("pad_y", 0)), opacidade=k)
    return img
