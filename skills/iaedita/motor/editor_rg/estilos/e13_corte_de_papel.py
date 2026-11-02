"""13 · Corte de papel — o vídeo vira uma colagem num caderno quadriculado creme: a pessoa aparece
RECORTADA com borda branca de papel (como recortada de revista), levemente torta e balançando, na
frente de folhas coloridas (lilás com hachura de lápis em cima, verde-limão do lado). Nas ideias
fortes, um título serifado aparece na folha lilás e um círculo de lápis é desenhado em volta dele;
etiquetas de papel ("crie.") são coladas no corpo e rabiscos de lápis (x, visto, seta, brilho,
estrela) aparecem ao lado da cabeça. A legenda é uma tira de papel com a fala acumulando palavra a
palavra (Cormorant 700, palavra falada em vinho), como na prévia aprovada.

Composição: calculada UMA vez em preparar(g) a partir do rosto ao longo do vídeo — a pessoa é
reduzida e ancorada embaixo só o necessário para sobrar a faixa do título acima da cabeça e a tira
da legenda abaixo do queixo (plano fechado reduz mais, plano médio quase nada).
Sem recorte: o vídeo inteiro vira uma FOTO colada no caderno (borda branca, fitas adesivas nos
cantos, leve giro), com as mesmas folhas, títulos, etiquetas e rabiscos em volta.
quadro(c) só depende de c.t e do plano (cache só de imagens prontas, com chave determinística)."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import desenho as d

try:  # OpenCV deixa cada quadro bem mais rápido; sem ele o resultado é o mesmo, só mais lento
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

INFO = {
    "id": "13-corte-de-papel",
    "nome": "Corte de papel",
    "precisa_recorte": True,
    "antes": 0.1,
    "depois": 0.55,
    # perfil da legenda própria: tira de papel creme, Cormorant 700, até 3 palavras acumulando
    "legenda": {"fonte": "serif", "peso": 700, "tamanho": 0.087, "cor": "#3C3332", "destaque": "#994F68",
                "caixa": "#FFFAF0", "max_caracteres": 18, "max_linhas": 1, "animacao": "subir"},
    "legenda_propria": True,
    "eventos": {
        "titulo": "inicio (quando a frase da ideia começa), fim (quando ela termina; 1,5–5 s), texto (2 a 5 "
                  "palavras, até 32 letras), traco ('circulo' padrão = elipse de lápis em volta do título | "
                  "'sublinhado' = risco de lápis embaixo da palavra marca | 'nenhum'), marca (opcional: 1 palavra "
                  "do texto, fica cor de vinho), som (use 'lapis' com som_atraso 0.3)",
        "etiqueta": "inicio, fim (1–3 s), texto (1 ou 2 palavras, até 12 letras, ex. 'crie.'), lado ('auto' "
                    "padrão | 'esquerda' | 'direita'), som (use 'papel'): etiqueta branca de papel colada no "
                    "corpo, perto da legenda",
        "rabisco": "inicio, fim (0,8–3 s), forma ('x' | 'visto' | 'seta' | 'brilho' | 'estrela'), lado ('auto' "
                   "padrão | 'esquerda' | 'direita'), som (use 'lapis'): desenho de lápis ao lado da cabeça",
        "cena": "inicio, fim (4 s ou mais; pode ir até o fim do vídeo), paleta ('rosa' | 'azul' | 'areia' | "
                "'lilas'), som (use 'papel'): folhas novas deslizam por cima e trocam as cores da colagem",
    },
}

# ------------------------------------------------------------------ paleta (da prévia aprovada)
FUNDO = (243, 238, 223)          # caderno creme #F3EEDF
GRADE = (115, 136, 153)          # linhas do quadriculado #738899
PAPEL_BORDA = (255, 253, 242)    # borda de papel em volta da pessoa #FFFDF2
TINTA = "#222729"
VINHO = "#9B484F"                # lápis vinho do círculo
RABISCO = "#724C52"              # lápis dos rabiscos
ETIQUETA = "#FFFDF5"
LEG_PAPEL = "#FFFAF0"
LEG_TINTA = "#3C3332"
LEG_ATIVA = "#994F68"
FITA = (236, 226, 196)           # fita adesiva (modo sem recorte)
SOMBRA = (52, 46, 40, 255)       # cor da sombra dos papéis colados
LIMIAR = 70                      # máscara acima disto = pessoa

PALETAS = {
    "lilas": {"a": "#CFC2E6", "hachura": "#756D9E", "b": "#D4ED80", "x": "#724C52"},
    "rosa": {"a": "#F2C9D0", "hachura": "#A9606E", "b": "#C4E2D6", "x": "#6E4A55"},
    "azul": {"a": "#C3D5EC", "hachura": "#5C789F", "b": "#F4DB7C", "x": "#5A4B5E"},
    "areia": {"a": "#E6D2AE", "hachura": "#957446", "b": "#CFC2E6", "x": "#6F4B47"},
}
FORMAS = ("x", "visto", "seta", "brilho", "estrela")

# ------------------------------------------------------------------ medidas (frações de W/H)
TOPO_SEG = 0.115       # zona segura de cima
BASE_SEG = 0.80        # zona segura de baixo
DIR_SEG = 0.86         # nada importante à direita disto (botões das redes)
TY0 = 0.128            # topo do título
CABECA_ALVO = 0.30     # topo da cabeça desejado depois da redução (sobra a faixa do título)
BORDA = 0.0085         # borda branca da pessoa (fração de W, já na tela)
BORDA_FOTO = 0.022     # margem branca da foto (sem recorte)
GIRO0 = 2.0            # graus: a pessoa fica levemente torta (anti-horário), como na prévia
BALANCO = 1.0          # graus de balanço em volta do giro
PERIODO = 6.4          # segundos de um balanço completo
LEG_X = 0.47           # centro da tira de legenda (um pouco à esquerda: botões ficam à direita)
PONTUACAO = ".,!?;:\"'“”‘’«»()"

T_ENTRA, T_SAI = 0.35, 0.30      # título
C_INI, C_DUR = 0.28, 0.85        # círculo de lápis: começa 0,28 s depois do título e leva 0,85 s
C_VOLTA = 0.40                   # círculo "desenha ao contrário" nos 0,4 s finais
CENA_ENTRA, CENA_SAI = 0.55, 0.50


_LUTS = {}


def _lut(op):
    q = int(round(d.limitar(op) * 100))
    if q not in _LUTS:
        _LUTS[q] = [int(v * q / 100) for v in range(256)]
    return _LUTS[q]


def _transf(cam, escala=1.0, graus=0.0):
    """Escala e giro (anti-horário, graus) de uma camada RGBA, com a caixa crescendo para caber."""
    if abs(escala - 1) < 0.002 and abs(graus) < 0.05:
        return cam
    w, h = cam.size
    a = math.radians(graus)
    ca, sa = math.cos(a) * escala, math.sin(a) * escala
    nw = int(math.ceil(abs(ca) * w + abs(sa) * h)) + 2
    nh = int(math.ceil(abs(sa) * w + abs(ca) * h)) + 2
    if cv2 is not None:
        M = np.array([[ca, sa, nw / 2 - (ca * w / 2 + sa * h / 2)],
                      [-sa, ca, nh / 2 - (-sa * w / 2 + ca * h / 2)]], np.float64)
        out = cv2.warpAffine(np.asarray(cam), M, (nw, nh), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        return Image.fromarray(out, "RGBA")
    if abs(escala - 1) >= 0.002:
        cam = cam.resize((max(1, int(w * escala)), max(1, int(h * escala))), Image.BICUBIC)
    if abs(graus) >= 0.05:
        cam = cam.rotate(graus, resample=Image.BICUBIC, expand=True)
    return cam


def _por(base, cam, x, y, opacidade=1.0):
    """Cola cam (RGBA) em base pelo canto (x, y), usando o alfa como máscara (rápido; aceita sair da tela)."""
    W, H = base.size
    x, y = int(round(x)), int(round(y))
    if opacidade <= 0.003 or x >= W or y >= H or x + cam.width <= 0 or y + cam.height <= 0:
        return
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(cam.width, W - x), min(cam.height, H - y)
    if (cx0, cy0, cx1, cy1) != (0, 0, cam.width, cam.height):
        cam = cam.crop((cx0, cy0, cx1, cy1))
    m = cam.getchannel("A")
    if opacidade < 0.997:
        m = m.point(_lut(opacidade))
    base.paste(cam, (x + cx0, y + cy0), m)


def _colar(base, cam, centro, escala=1.0, graus=0.0, opacidade=1.0):
    if opacidade <= 0.003 or escala <= 0.01:
        return
    c2 = _transf(cam, escala, graus)
    _por(base, c2, centro[0] - c2.width / 2, centro[1] - c2.height / 2, opacidade)


def _limpa(p):
    return str(p).strip().strip(PONTUACAO).lower()


def _chave(e):
    return (e.get("tipo"), round(float(e["inicio"]), 3), round(float(e["fim"]), 3), str(e.get("texto", "")),
            str(e.get("forma", "")), str(e.get("lado", "")), str(e.get("paleta", "")), str(e.get("marca", "")),
            str(e.get("traco", "")))


# ------------------------------------------------------------------ validação do plano

def validar(plano, duracao):
    p = []
    evs = plano["eventos"]
    por_tipo = {}
    for e in evs:
        tipo, ini, fim = e.get("tipo"), float(e.get("inicio", 0)), float(e.get("fim", 0))
        por_tipo.setdefault(tipo, []).append(e)
        dur = fim - ini
        if tipo == "titulo":
            txt = str(e.get("texto", "")).strip()
            if not txt:
                p.append(f"Título vazio em {ini:.2f}s.")
            elif len(txt.split()) > 5 or len(txt) > 32:
                p.append(f"Título longo demais em {ini:.2f}s (máx. 5 palavras / 32 letras).")
            if not (1.2 <= dur <= 6.0):
                p.append(f"Título em {ini:.2f}s dura {dur:.1f}s: use de 1,5 a 5 s (o círculo de lápis precisa de tempo).")
            marca = _limpa(e.get("marca", ""))
            if marca and marca not in [_limpa(w) for w in txt.split()]:
                p.append(f"A 'marca' do título em {ini:.2f}s precisa ser uma palavra do próprio texto.")
            tr = e.get("traco", "circulo")
            if tr not in ("circulo", "sublinhado", "nenhum"):
                p.append(f"Título em {ini:.2f}s: 'traco' deve ser 'circulo', 'sublinhado' ou 'nenhum'.")
        elif tipo == "etiqueta":
            txt = str(e.get("texto", "")).strip()
            if not txt:
                p.append(f"Etiqueta vazia em {ini:.2f}s.")
            elif len(txt.split()) > 2 or len(txt) > 12:
                p.append(f"Etiqueta longa demais em {ini:.2f}s (máx. 2 palavras / 12 letras).")
            if not (0.7 <= dur <= 4.0):
                p.append(f"Etiqueta em {ini:.2f}s dura {dur:.1f}s: use de 1 a 3 s.")
        elif tipo == "rabisco":
            if e.get("forma") not in FORMAS:
                p.append(f"Rabisco em {ini:.2f}s: 'forma' deve ser uma de {', '.join(FORMAS)}.")
            if not (0.6 <= dur <= 4.0):
                p.append(f"Rabisco em {ini:.2f}s dura {dur:.1f}s: use de 0,8 a 3 s.")
        elif tipo == "cena":
            if e.get("paleta") not in PALETAS:
                p.append(f"Cena em {ini:.2f}s: 'paleta' deve ser uma de {', '.join(PALETAS)}.")
            if dur < 3.9:
                p.append(f"Cena em {ini:.2f}s dura {dur:.1f}s: a troca de folhas precisa de pelo menos 4 s.")
    for tipo, nome in (("titulo", "Títulos"), ("etiqueta", "Etiquetas"), ("cena", "Cenas")):
        lst = sorted(por_tipo.get(tipo, []), key=lambda e: e["inicio"])
        folga = 0.35 if tipo == "titulo" else 0.3 if tipo == "etiqueta" else CENA_SAI
        for a, b in zip(lst, lst[1:]):
            if b["inicio"] < a["fim"] + folga:
                p.append(f"{nome} sobrepostos em {b['inicio']:.2f}s: um precisa sair (fim + {folga:.2f}s) antes do outro entrar.")
    rab = sorted(por_tipo.get("rabisco", []), key=lambda e: e["inicio"])
    for i, e in enumerate(rab):
        juntos = [o for o in rab[:i] if o["fim"] + 0.25 > e["inicio"]]
        if len(juntos) >= 2:
            p.append(f"Rabiscos demais ao mesmo tempo em {e['inicio']:.2f}s (máx. 2).")
    return p


# ------------------------------------------------------------------ composição (uma vez por vídeo)

def _amostras(g):
    """Caixas do rosto (frações) ao longo do vídeo, a cada 0,2 s."""
    ts = np.arange(0.0, max(0.2, g.duracao) + 0.001, 0.2)
    caixas = []
    for t in ts:
        x0, y0, x1, y1 = g.rosto.em(float(t))
        caixas.append((x0 / g.W, y0 / g.H, x1 / g.W, y1 / g.H))
    return ts, np.array(caixas)


def _composicao(g):
    W, H = g.W, g.H
    rec = bool(g.tem_mascara)
    ts, cx = _amostras(g)
    alt = cx[:, 3] - cx[:, 1]
    topo = cx[:, 1] - alt * 0.45            # topo da cabeça (cabelo/boné)
    queixo = cx[:, 3] + alt * 0.08
    ht = float(np.percentile(topo, 10))
    qx = float(np.percentile(queixo, 90))
    leg_h = _leg_altura(W, H, g)
    if rec:
        Yb = 1.02
        s_max = 0.93
    else:
        Yb = 1.0 + BORDA_FOTO * W / H * 0.6
        s_max = 0.80                         # a foto precisa mostrar o caderno em volta
    s_hi = (Yb - CABECA_ALVO) / max(0.2, 1.0 - ht)       # cabe a faixa do título
    s_lo = (Yb - (BASE_SEG - 0.016 - leg_h)) / max(0.2, 1.0 - qx)   # cabe a legenda abaixo do queixo
    s = min(s_hi, s_max)
    s = max(s, s_lo)
    s = d.limitar(s, 0.68, s_max)
    est = {"rec": rec, "s": s, "Yb": Yb, "ts": ts, "cx": cx, "leg_h": leg_h}
    cab = Yb - (1 - ht) * s                  # topo da cabeça na tela (fração de H)
    est["cab"] = cab
    # folha lilás do título: do alto até um pouco atrás da cabeça
    a_y0 = 0.088
    if rec:   # a cabeça passa na frente da folha
        a_y1 = d.limitar(max(cab + 0.07, a_y0 + 0.22), a_y0 + 0.2, 0.46)
    else:     # sem recorte a folha fica POR CIMA da foto: termina logo acima da cabeça
        a_y1 = d.limitar(cab + 0.012, a_y0 + 0.15, 0.40)
    est["folhaA"] = (0.055, a_y0, 0.93, a_y1)
    # folha verde do lado direito, atrás do ombro
    b_y0 = d.limitar(cab + 0.11, 0.36, 0.56)
    est["folhaB"] = (0.56, b_y0, 1.08, min(0.86, b_y0 + 0.40))
    est["x_peq"] = (0.085, d.limitar(cab + 0.2, 0.42, 0.62))
    return est


def _rosto_tela(est, W, H, caixa_px):
    """Caixa do rosto (pixels do vídeo) -> pixels na tela, depois da redução, da âncora embaixo e do
    giro fixo da pessoa (o balanço de ±1° fica dentro das margens de quem usa esta caixa)."""
    s, Yb = est["s"], est["Yb"]
    x0, y0, x1, y1 = caixa_px
    ax, ay = W / 2, Yb * H
    ca, sa = math.cos(math.radians(GIRO0)), math.sin(math.radians(GIRO0))
    xs, ys = [], []
    for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        dx, dy = (x - W / 2) * s, -(H - y) * s
        xs.append(ax + dx * ca + dy * sa)
        ys.append(ay - dx * sa + dy * ca)
    return (min(xs), min(ys), max(xs), max(ys))


def _janela(est, g, t0, t1):
    """Rosto na tela durante [t0, t1]: menor topo da cabeça, menor linha dos olhos, maior queixo,
    e faixa horizontal ocupada pelo rosto."""
    W, H = g.W, g.H
    ts, cx = est["ts"], est["cx"]
    sel = (ts >= t0 - 0.1) & (ts <= t1 + 0.1)
    if not sel.any():
        sel = np.abs(ts - (t0 + t1) / 2) == np.abs(ts - (t0 + t1) / 2).min()
    caixas = cx[sel]
    tops, olhos, queixos, xs0, xs1 = [], [], [], [], []
    for c0 in caixas:
        x0, y0, x1, y1 = _rosto_tela(est, W, H, (c0[0] * W, c0[1] * H, c0[2] * W, c0[3] * H))
        h = y1 - y0
        tops.append(y0 - h * 0.45)
        olhos.append(y0 + h * 0.22)
        queixos.append(y1 + h * 0.08)
        xs0.append(x0)
        xs1.append(x1)
    return {"topo": min(tops), "olhos": min(olhos), "queixo": max(queixos), "x0": min(xs0), "x1": max(xs1),
            "cx": (float(np.median(xs0)) + float(np.median(xs1))) / 2}


# ------------------------------------------------------------------ texturas e folhas (cache)

def _ruido(w, h, semente, escala=1):
    rng = np.random.default_rng(semente)
    if escala <= 1:
        return rng.standard_normal((h, w)).astype(np.float32)
    pw, ph = max(2, w // escala), max(2, h // escala)
    peq = rng.standard_normal((ph, pw)).astype(np.float32)
    im = Image.fromarray(((peq * 40) + 128).clip(0, 255).astype(np.uint8), "L").resize((w, h), Image.BICUBIC)
    return (np.asarray(im, np.float32) - 128) / 40


def _fundo(g):
    """Caderno creme quadriculado com grão de papel (uma vez por vídeo)."""
    k = ("e13_fundo", g.W, g.H)
    if k in g.cache:
        return g.cache[k]
    W, H = g.W, g.H
    lum = (1 + 0.016 * _ruido(W, H, 7) + 0.006 * _ruido(W, H, 8, max(4, W // 90))
           + 0.010 * _ruido(W, H, 9, max(8, W // 14)))
    arr = (np.array(FUNDO, np.float32)[None, None, :] * lum[:, :, None])
    passo = W / 12
    a = 0.16
    for i in range(1, int(H / passo) + 2):
        y = int(round(i * passo - passo * 0.35))
        if 0 <= y < H:
            arr[y, :, :] = arr[y, :, :] * (1 - a) + np.array(GRADE, np.float32) * a
    for i in range(1, 13):
        x = int(round(i * passo - passo * 0.5))
        if 0 <= x < W:
            arr[:, x, :] = arr[:, x, :] * (1 - a) + np.array(GRADE, np.float32) * a
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").convert("RGBA")
    # x pequeno de lápis no caderno (atrás da pessoa), como na prévia
    # (sem recorte a foto cobre esse canto: o x ficaria cortado, então não entra)
    est = g.cache["_e13"]
    if est["rec"]:
        xx, yy = est["x_peq"]
        tam = int(0.07 * W)
        x_img = _desenho(g, "xpeq", _forma_pts("x"), tam, tam, 0.0062 * W, RABISCO, 1.0)
        img.alpha_composite(x_img, (int(xx * W - tam / 2), int(yy * H - tam / 2)))
    g.cache[k] = img
    return img


def _fundo_com_folhas(g, pal, quais=("b", "a")):
    """Caderno + as folhas da paleta, já coladas (a imagem de base de cada quadro)."""
    k = ("e13_fundo_folhas", pal, g.W, g.H, quais)
    if k in g.cache:
        return g.cache[k]
    img = _fundo(g).copy()
    for qual in quais:
        cam, (cx, cy) = _folha(g, qual, pal)
        d.colar_em(img, cam, (cx - cam.width / 2, cy - cam.height / 2))
    antigas = [ch for ch in g.cache if isinstance(ch, tuple) and ch and ch[0] == "e13_fundo_folhas"]
    if len(antigas) >= 3:   # guarda no máximo 3 paletas prontas (memória)
        del g.cache[antigas[0]]
    g.cache[k] = img
    return img


def _poligono(w, h, fr, ss=2):
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).polygon([(x * w * ss, y * h * ss) for x, y in fr], fill=255)
    return m.reduce(ss) if ss > 1 else m


def _folha(g, qual, pal):
    """Folha de papel colorida (lilás 'a' ou verde 'b'), girada, com grão e sombra. -> (img, centro)."""
    W, H = g.W, g.H
    est = g.cache["_e13"]
    k = ("e13_folha", qual, pal, W, H)
    if k in g.cache:
        return g.cache[k]
    cores = PALETAS.get(pal, PALETAS["lilas"])
    x0, y0, x1, y1 = est["folhaA"] if qual == "a" else est["folhaB"]
    w, h = int((x1 - x0) * W), int((y1 - y0) * H)
    if qual == "a":
        fr = [(0.01, 0.05), (0.97, 0.0), (1.0, 0.94), (0.03, 1.0)]
        giro = 4.5
    else:
        fr = [(0.02, 0.0), (0.98, 0.03), (0.96, 0.98), (0.0, 1.0)]
        giro = -6.0
    if pal in ("rosa", "areia"):   # cenas alternam a inclinação das folhas
        giro = -giro * 0.8
    m = _poligono(w, h, fr)
    base = np.array(d.cor(cores[qual]), np.float32)
    lum = 1 + 0.016 * _ruido(w, h, 21 if qual == "a" else 22) + 0.007 * _ruido(w, h, 23, max(6, W // 60))
    arr = np.empty((h, w, 4), np.uint8)
    arr[:, :, :3] = (base[None, None, :3] * lum[:, :, None]).clip(0, 255).astype(np.uint8)
    arr[:, :, 3] = np.asarray(m)
    folha = Image.fromarray(arr, "RGBA")
    if qual == "a":   # hachura de lápis no alto da folha (como na prévia)
        n = max(8, int(w / (0.037 * W)))
        tracos = []
        for i in range(n):
            xa = (0.03 + i * (0.89 / max(1, n - 1)))
            tracos.append([(xa, 0.15), (xa - 0.027, 0.64)])
        hach = _desenho(g, ("hach", pal, w, h), tracos, w, h, 0.0102 * W, cores["hachura"], 1.0, alfa=0.28)
        folha.alpha_composite(hach)
    elif est["rec"]:  # x grande de lápis na folha verde (sem recorte a foto o esconderia)
        tam = int(0.12 * W)
        xi = _desenho(g, ("xg", pal), _forma_pts("x"), tam, tam, 0.0062 * W, cores["x"], 1.0)
        folha.alpha_composite(xi, (int(w * 0.38), int(h * 0.44)))
    sombra, _ = d.sombra(folha, raio=0.014 * W, opacidade=0.16, desloc=(0, 0.0085 * H))
    img = sombra.rotate(giro, resample=Image.BICUBIC, expand=True)
    centro = ((x0 + x1) / 2 * W, (y0 + y1) / 2 * H + 0.004 * H)
    g.cache[k] = (img, centro)
    return g.cache[k]


def _grao(w, h, semente=5):
    rng = np.random.default_rng(semente)
    v = 0.72 + 0.28 * rng.random((h, w), dtype=np.float32)
    return Image.fromarray((v * 255).astype(np.uint8), "L")


# ------------------------------------------------------------------ traços de lápis

def _comprimento(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def _desenho(g, chave, tracos, w, h, larg, cor, k, alfa=1.0, normalizado=True, cache=True):
    """Traços de lápis (lista de polilinhas) desenhados até a fração k do comprimento total.
    Coordenadas normalizadas 0-1 na caixa w x h. Borda suave (super-amostragem) e grão de grafite."""
    k = d.limitar(k)
    kq = round(k * 60) / 60 if k < 1 else 1.0
    ck = ("e13_tr", chave, w, h, int(larg * 10), cor, round(alfa, 3), kq)
    if cache and kq >= 1 and ck in g.cache:
        return g.cache[ck]
    ss = 2
    pts_px = [[(x * w * ss, y * h * ss) if normalizado else (x * ss, y * ss) for x, y in tr] for tr in tracos]
    total = sum(_comprimento(p) for p in pts_px) or 1.0
    falta = total * kq
    m = Image.new("L", (w * ss, h * ss), 0)
    dr = ImageDraw.Draw(m)
    lw = max(2, int(round(larg * ss)))
    for p in pts_px:
        if falta <= 0:
            break
        L = _comprimento(p)
        if L <= falta:
            parte = p
        else:
            parte, acum = [p[0]], 0.0
            for a, b in zip(p, p[1:]):
                seg = math.dist(a, b)
                if acum + seg >= falta:
                    u = (falta - acum) / max(1e-6, seg)
                    parte.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
                    break
                parte.append(b)
                acum += seg
        falta -= L
        if len(parte) >= 2:
            dr.line(parte, fill=255, width=lw, joint="curve")
            r = lw / 2
            for q in (parte[0], parte[-1]):
                dr.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), fill=255)
    m = m.reduce(ss)
    gk = ("e13_grao", w, h)
    if gk not in g.cache:
        g.cache[gk] = _grao(w, h)
    m = ImageChops.multiply(m, g.cache[gk])
    if alfa < 0.999:
        m = m.point(lambda v: int(v * alfa))
    out = Image.new("RGBA", (w, h), d.cor(cor))
    out.putalpha(m)
    if cache and kq >= 1:
        g.cache[ck] = out
    return out


def _forma_pts(forma):
    """Polilinhas (0-1) de cada rabisco, desenhadas como à mão."""
    if forma == "x":
        return [[(0.12, 0.14), (0.40, 0.42), (0.66, 0.66), (0.88, 0.88)],
                [(0.86, 0.12), (0.58, 0.40), (0.36, 0.62), (0.12, 0.86)]]
    if forma == "visto":
        return [[(0.10, 0.55), (0.24, 0.68), (0.38, 0.84), (0.55, 0.58), (0.72, 0.34), (0.92, 0.10)]]
    if forma == "seta":  # curva que aponta para a direita (espelhada quando fica do lado direito)
        curva = []
        for i in range(17):
            u = i / 16
            curva.append((0.08 + 0.80 * u, 0.80 - 0.62 * math.sin(u * math.pi * 0.55) - 0.10 * u))
        fim = curva[-1]
        return [curva, [(fim[0] - 0.24, fim[1] - 0.06), fim, (fim[0] - 0.10, fim[1] + 0.22)]]
    if forma == "brilho":
        return [[(0.50, 0.42), (0.50, 0.06)], [(0.30, 0.52), (0.08, 0.28)], [(0.70, 0.52), (0.92, 0.28)]]
    if forma == "estrela":
        pts = []
        for i in range(11):
            r = 0.46 if i % 2 == 0 else 0.20
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((0.5 + r * math.cos(a), 0.53 + r * math.sin(a)))
        return [pts]
    return [[(0.1, 0.5), (0.9, 0.5)]]


def _elipse_pts(rx, ry, w, h, semente=0, giro=2.5):
    """Elipse feita à mão (raios rx, ry em pixels numa caixa w x h): começa no alto à esquerda,
    dá ~1,08 volta e passa do ponto inicial, com leve tremido de mão e inclinação (giro, graus)."""
    pts = []
    n = 150
    a0 = math.radians(205)
    ca, sa = math.cos(math.radians(giro)), math.sin(math.radians(giro))
    for i in range(n + 1):
        u = i / n
        a = a0 + 2 * math.pi * 1.08 * u
        wob = 1 + 0.022 * d.ruido(u * 3.0, 13 + semente) + 0.035 * u
        x, y = rx * wob * math.cos(a), ry * wob * math.sin(a)
        xr, yr = x * ca + y * sa, -x * sa + y * ca
        pts.append((0.5 + xr / w, 0.5 + yr / h))
    return [pts]


# ------------------------------------------------------------------ preparar

def preparar(g):
    est = _composicao(g)
    g.cache["_e13"] = est
    W, H = g.W, g.H
    est["leg"] = None
    leg = g.plano.get("legenda") or {}
    if leg.get("ativa", True) and g.palavras:
        perfil = dict(INFO["legenda"])
        perfil.update(leg.get("perfil") or {})
        est["leg"] = _Legenda(g, est, perfil)
    est["lay"] = {}
    for e in g.plano["eventos"]:
        try:
            if e.get("tipo") == "titulo":
                est["lay"][_chave(e)] = _lay_titulo(g, est, e)
            elif e.get("tipo") == "etiqueta":
                est["lay"][_chave(e)] = _lay_etiqueta(g, est, e)
        except Exception:  # noqa: BLE001  um evento ruim nunca derruba o vídeo
            continue
    lados = {}
    for i, e in enumerate(sorted([e for e in g.plano["eventos"] if e.get("tipo") == "rabisco"],
                                 key=lambda e: e["inicio"])):
        try:
            est["lay"][_chave(e)] = _lay_rabisco(g, est, e, i, lados)
        except Exception:  # noqa: BLE001
            continue
    _fundo(g)


def _est(g):
    if "_e13" not in g.cache:
        preparar(g)
    return g.cache["_e13"]


# ------------------------------------------------------------------ título

def _lay_titulo(g, est, e):
    W, H = g.W, g.H
    jan = _janela(est, g, e["inicio"], e["fim"] + T_SAI)
    ty0 = TY0 * H
    ty1 = min(jan["topo"] + 0.012 * H, jan["olhos"] - 0.06 * H)
    ty1 = max(ty1, ty0 + 0.10 * H)
    ty1 = min(ty1, est["folhaA"][3] * H - 0.02 * H)
    texto = str(e.get("texto", "")).strip()
    larg = 0.74 * W
    f, linhas, al = d.ajustar_texto(texto, larg, (ty1 - ty0) * 0.80, 500, "serif", tam_max=int(W * 0.125),
                                    tam_min=int(W * 0.068), max_linhas=2, entrelinha=1.0)
    marca = _limpa(e.get("marca", ""))
    pad = int(f.size * 0.35)
    tw = int(max(f.getlength(l) for l in linhas)) + pad * 2
    th = int(al * len(linhas) + f.size * 0.35) + pad * 2
    cam = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    esp = f.getlength(" ")
    caixas_marca = []
    for li, l in enumerate(linhas):
        x = (tw - f.getlength(l)) / 2
        y = pad + li * al - f.size * 0.06
        for pal in l.split():
            wp = f.getlength(pal)
            cor = VINHO if marca and _limpa(pal) == marca else TINTA
            d.escrever(cam, (x, y), [pal], f, cor)
            if marca and _limpa(pal) == marca:
                caixas_marca.append((x, y + f.size * 0.98, x + wp))
            x += wp + esp
    giro = 4.0
    traco = e.get("traco", "circulo")
    cx = 0.48 * W
    cy = (ty0 + ty1) / 2
    info = {"img": cam, "img_rot": cam.rotate(giro, resample=Image.BICUBIC, expand=True), "giro": giro,
            "centro": (cx, cy), "traco": traco, "f": f.size}
    if traco == "circulo":
        rx = min(tw / 2 + 0.035 * W, 0.43 * W)
        ry = th / 2 + 0.028 * H
        ry = min(ry, jan["olhos"] - 0.025 * H - cy)
        ry = max(ry, th / 2 + 0.004 * H)
        info["elipse"] = (rx, ry)
    elif traco == "sublinhado":
        if caixas_marca:
            x0, y, x1 = caixas_marca[0]
        else:
            ul = linhas[-1]
            x0 = (tw - f.getlength(ul)) / 2
            x1 = x0 + f.getlength(ul)
            y = pad + (len(linhas) - 1) * al + f.size * 0.92
        info["sub"] = (x0 - f.size * 0.08, y, x1 + f.size * 0.12)
    return info


def _desenha_titulo(c, img, e, lay):
    W, H, t = c.W, c.H, c.t
    ini, fim = float(e["inicio"]), float(e["fim"])
    ke = d.suave(d.mapear(t, ini, ini + T_ENTRA))
    ks = d.suave(d.mapear(t, fim, fim + T_SAI))
    op = ke * (1 - ks)
    if op <= 0.004:
        return
    cx, cy = lay["centro"]
    kin = d.saida(d.mapear(t, ini, ini + 0.45))
    dy = (1 - kin) * 0.014 * H - ks * 0.01 * H
    esc = 0.965 + 0.035 * kin
    _colar(img, lay["img_rot"], (cx, cy + dy), escala=esc, opacidade=op)
    # traço de lápis: desenha, segura, e "volta" (desenha ao contrário) no fim
    kd = d.suave(d.mapear(t, ini + C_INI, ini + C_INI + C_DUR))
    kv = d.suave(d.mapear(t, fim - C_VOLTA, fim + 0.02))
    k = kd * (1 - kv)
    if k <= 0.002:
        return
    if lay["traco"] == "circulo" and "elipse" in lay:
        rx, ry = lay["elipse"]
        lw = 0.0078 * W
        ew, eh = int(rx * 2.16 + lw * 3), int(ry * 2.16 + lw * 3 + rx * 0.1)
        el = _desenho(c.g, ("elipse",) + _chave(e), _elipse_pts(rx, ry, ew, eh, int(ini * 10) % 7), ew, eh,
                      lw, VINHO, k)
        _colar(img, el, (cx, cy + 0.004 * H))
    elif lay["traco"] == "sublinhado" and "sub" in lay:
        x0, y, x1 = lay["sub"]
        tw, th = lay["img"].size
        larg = int(x1 - x0)
        alt = int(0.05 * H)
        a = math.radians(lay["giro"])
        pts = [[(0.0, 0.40), (0.25, 0.50), (0.55, 0.45), (0.85, 0.52), (1.0, 0.38)],
               [(0.08, 0.68), (0.45, 0.60), (0.92, 0.70)]]
        # a mesma inclinação do título, aplicada nos pontos (sem girar imagem a cada quadro)
        caixa_h = int(alt + larg * math.sin(a) + 4)
        pts_r = []
        for tr in pts:
            q = []
            for px, py in tr:
                ox, oy = (px - 0.5) * larg, (py - 0.5) * alt
                q.append((0.5 + (ox * math.cos(a) + oy * math.sin(a)) / larg,
                          0.5 + (-ox * math.sin(a) + oy * math.cos(a)) / caixa_h))
            pts_r.append(q)
        sub = _desenho(c.g, ("sub",) + _chave(e), pts_r, larg, caixa_h, 0.0068 * W, VINHO, k)
        ox, oy = (x0 + x1) / 2 - tw / 2, y - th / 2 + alt * 0.05
        rx, ry = ox * math.cos(a) + oy * math.sin(a), -ox * math.sin(a) + oy * math.cos(a)
        _colar(img, sub, (cx + rx, cy + dy + ry), opacidade=op)


# ------------------------------------------------------------------ etiqueta ("crie.")

def _cartao_etiqueta(g, texto):
    W, H = g.W, g.H
    k = ("e13_etq", texto, W, H)
    if k in g.cache:
        return g.cache[k]
    f, linhas, al = d.ajustar_texto(texto, 0.30 * W, 0.08 * H, 900, tam_max=int(0.075 * W),
                                    tam_min=int(0.052 * W), max_linhas=1)
    tw = f.getlength(linhas[0])
    px, py = 0.022 * W, f.size * 0.22
    w, h = int(tw + px * 2), int(f.size * 1.18 + py * 2)
    fr = [(0.0, 0.03), (1.0, 0.0), (0.985, 1.0), (0.01, 0.97)]
    m = _poligono(w, h, fr)
    lum = 1 + 0.015 * _ruido(w, h, 31)
    arr = np.empty((h, w, 4), np.uint8)
    arr[:, :, :3] = (np.array(d.cor(ETIQUETA)[:3], np.float32)[None, None] * lum[:, :, None]).clip(0, 255)
    arr[:, :, 3] = np.asarray(m)
    cam = Image.fromarray(arr, "RGBA")
    d.escrever(cam, (px, py - f.size * 0.08), linhas, f, TINTA)
    sombra, _ = d.sombra(cam, raio=0.013 * W, opacidade=0.20, desloc=(0.007 * W, 0.011 * W))
    g.cache[k] = (sombra, w, h)
    return g.cache[k]


def _lay_etiqueta(g, est, e):
    W, H = g.W, g.H
    cam, w, h = _cartao_etiqueta(g, str(e.get("texto", "")).strip())
    jan = _janela(est, g, e["inicio"], e["fim"] + 0.3)
    leg = est.get("leg")
    leg_top = leg.y_padrao if leg else (BASE_SEG * H - est["leg_h"] * H)
    rosto_x0, rosto_x1 = jan["x0"], jan["x1"]
    rosto_ok = lambda x0, y0, x1, y1: (x1 < rosto_x0 + 0.1 * (rosto_x1 - rosto_x0) or  # noqa: E731
                                       x0 > rosto_x1 - 0.1 * (rosto_x1 - rosto_x0) or
                                       y1 < jan["olhos"] - 0.02 * H or y0 > jan["queixo"] - 0.01 * H)
    lado = e.get("lado", "auto")
    cands = []
    yc = leg_top - h * 0.42                       # em cima da tira da legenda, colada no peito
    for ld in (("direita", "esquerda") if lado != "esquerda" else ("esquerda", "direita")):
        xc = (DIR_SEG * W - w / 2 - 0.01 * W) if ld == "direita" else (0.07 * W + w / 2)
        cands.append((ld, xc, yc))
    if lado == "direita":
        cands = [c for c in cands if c[0] == "direita"] + [c for c in cands if c[0] != "direita"]
    # alternativa: na altura do rosto, ao lado da cabeça (plano muito fechado)
    for ld in ("direita", "esquerda"):
        xc = (min(DIR_SEG * W - w / 2, rosto_x1 + 0.03 * W + w / 2) if ld == "direita"
              else max(0.06 * W + w / 2, rosto_x0 - 0.03 * W - w / 2))
        cands.append((ld, xc, (jan["olhos"] + jan["queixo"]) / 2))
    escolha = cands[0]
    for cnd in cands:
        _, xc, yc2 = cnd
        if rosto_ok(xc - w / 2, yc2 - h / 2, xc + w / 2, yc2 + h / 2) and xc - w / 2 >= 0.04 * W \
                and xc + w / 2 <= DIR_SEG * W + 0.005 * W:
            escolha = cnd
            break
    ld, xc, yc = escolha
    return {"img": cam, "centro": (xc, yc), "giro": -7.0 if ld == "direita" else 6.0}


def _desenha_etiqueta(c, img, e, lay):
    t = c.t
    ini, fim = float(e["inicio"]), float(e["fim"])
    if t < ini - 0.02 or t > fim + 0.3:
        return
    ke = d.mapear(t, ini, ini + 0.24)
    ks = d.suave(d.mapear(t, fim, fim + 0.26))
    op = d.saida(d.mapear(t, ini, ini + 0.12)) * (1 - ks)
    if op <= 0.004:
        return
    esc = (1.22 - 0.22 * d.mola(ke, 1.4)) * (1 - 0.06 * ks)
    giro = lay["giro"] + (1 - d.saida(ke)) * (-9 if lay["giro"] < 0 else 9) + 0.8 * math.sin(t * 1.3)
    xc, yc = lay["centro"]
    _colar(img, lay["img"], (xc, yc - ks * 0.01 * c.H), escala=esc, graus=giro, opacidade=op)


# ------------------------------------------------------------------ rabisco de lápis

def _lay_rabisco(g, est, e, ordem, lados):
    W, H = g.W, g.H
    jan = _janela(est, g, e["inicio"], e["fim"] + 0.3)
    esq = jan["x0"] - 0.035 * W - 0.04 * W
    dirr = DIR_SEG * W - (jan["x1"] + 0.035 * W)
    lado = e.get("lado", "auto")
    if lado not in ("esquerda", "direita"):
        if abs(esq - dirr) < 0.04 * W:
            lado = "esquerda" if ordem % 2 == 0 else "direita"
        else:
            lado = "esquerda" if esq > dirr else "direita"
    espaco = esq if lado == "esquerda" else dirr
    tam = int(d.limitar(espaco * 0.92, 0.10 * W, 0.17 * W))
    if lado == "esquerda":
        xc = max(0.045 * W + tam / 2, jan["x0"] - 0.035 * W - tam / 2)
    else:
        xc = min(DIR_SEG * W - tam / 2, jan["x1"] + 0.035 * W + tam / 2)
    forma = e.get("forma", "x")
    yc = jan["olhos"] + 0.02 * H
    if forma == "brilho":   # tracinhos de destaque perto do alto da cabeça
        yc = max(est["folhaA"][3] * H + tam * 0.2, jan["topo"] + 0.06 * H)
    leg = est.get("leg")
    y_max = (leg.y_padrao - tam * 0.6) if leg else BASE_SEG * H - tam
    y_min = TOPO_SEG * H + tam / 2
    # não encavala no "x" pequeno fixo do caderno (fica à esquerda, na altura do rosto)
    xp, yp = est["x_peq"][0] * W, est["x_peq"][1] * H
    folga = 0.035 * W + tam / 2 + 0.012 * W
    if est["rec"] and abs(xc - xp) < folga and abs(yc - yp) < folga:
        yc = yp + folga if yp + folga <= y_max else yp - folga
    yc = d.limitar(yc, y_min, max(y_min, y_max))
    pts = _forma_pts(forma)
    if forma == "seta" and lado == "direita":
        pts = [[(1 - x, y) for x, y in tr] for tr in pts]
    elif forma == "brilho":
        giro_b = -28 if lado == "esquerda" else 28
        ca, sa = math.cos(math.radians(giro_b)), math.sin(math.radians(giro_b))
        pts = [[(0.5 + (x - 0.5) * ca - (y - 0.55) * sa, 0.55 + (x - 0.5) * sa + (y - 0.55) * ca) for x, y in tr]
               for tr in pts]
    return {"pts": pts, "tam": tam, "centro": (xc, yc), "lado": lado,
            "dur": 0.32 if forma in ("visto", "brilho") else 0.5}


def _desenha_rabisco(c, img, e, lay):
    t = c.t
    ini, fim = float(e["inicio"]), float(e["fim"])
    if t < ini or t > fim + 0.3:
        return
    k = d.suave(d.mapear(t, ini, ini + lay["dur"]))
    op = 1 - d.suave(d.mapear(t, fim, fim + 0.28))
    if op <= 0.004 or k <= 0.002:
        return
    tam = lay["tam"]
    esc = 1 + 0.04 * (1 - op)
    if c.mascara is None or not _est(c.g)["rec"]:
        # sem recorte o rabisco cai em cima da foto: ganha um contorno de papel (adesivo) para ser lido
        halo = _desenho(c.g, ("rabh",) + _chave(e), lay["pts"], tam, tam, 0.0175 * c.W, "#FFFDF2", k)
        _colar(img, halo, lay["centro"], escala=esc, opacidade=op * 0.92)
    cam = _desenho(c.g, ("rab",) + _chave(e), lay["pts"], tam, tam, 0.0066 * c.W, RABISCO, k)
    _colar(img, cam, lay["centro"], escala=esc, opacidade=op)


# ------------------------------------------------------------------ legenda própria (tira de papel)

def _leg_altura(W, H, g):
    leg = (g.plano.get("legenda") or {}).get("perfil") or {}
    tam = float(leg.get("tamanho", INFO["legenda"]["tamanho"]))
    linhas = max(1, min(2, int(leg.get("max_linhas", INFO["legenda"]["max_linhas"]))))
    # A prévia vertical usa W como referência; no horizontal a menor dimensão
    # mantém a mesma proporção, sem transformar a legenda numa faixa sobre o rosto.
    fonte_px = int(round(tam * min(W, H)))
    return math.ceil(fonte_px * (1.08 * linhas + 0.70)) / H


def _paginas(palavras, max_car=18, max_pal=3):
    pags, cur = [], []
    for p in palavras:
        if cur:
            txt = " ".join(x["texto"] for x in cur + [p])
            gap = p["inicio"] - cur[-1]["fim"]
            ult = cur[-1]["texto"][-1:]
            if len(cur) >= max_pal or len(txt) > max_car or gap > 0.45 or ult in ".!?" or \
                    (ult in ",;:" and len(cur) >= 1 and len(" ".join(x["texto"] for x in cur)) >= 6):
                pags.append(cur)
                cur = []
        cur.append(p)
    if cur:
        pags.append(cur)
    out = []
    for i, pg in enumerate(pags):
        ini = pg[0]["inicio"] - 0.06
        prox = pags[i + 1][0]["inicio"] - 0.06 if i + 1 < len(pags) else pg[-1]["fim"] + 0.8
        out.append({"pal": pg, "ini": ini, "fim": min(prox, pg[-1]["fim"] + 0.55), "i": i})
    return out


class _Legenda:
    """Tira de papel creme, Cormorant 700; palavras aparecem quando são ditas e se acumulam
    (até 3 por tira); a palavra falada fica vinho. Fica logo abaixo do queixo, dentro da zona segura."""

    def __init__(self, g, est, perfil):
        W, H = g.W, g.H
        self.W, self.H = W, H
        self.fam = perfil.get("fonte", "serif")
        self.peso = int(perfil.get("peso", 700))
        self.tam = int(round(min(W, H) * float(perfil.get("tamanho", 0.087))))
        self.tam_min = int(round(min(W, H) * 0.06))
        self.max_linhas = max(1, min(2, int(perfil.get("max_linhas", 1))))
        self.cor = perfil.get("cor", LEG_TINTA)
        self.destaque = perfil.get("destaque", LEG_ATIVA)
        self.papel = perfil.get("caixa") or LEG_PAPEL
        self.maius = bool(perfil.get("maiusculas", False))
        mc = int(perfil.get("max_caracteres", 18) or 18)
        self.paginas = _paginas(g.palavras, mc, 3)
        self.larg_max = 0.80 * W
        self.h = est["leg_h"] * H
        # posição padrão: abaixo do queixo (percentil alto), nunca acima de 62% nem abaixo da zona segura
        ts, cx = est["ts"], est["cx"]
        qs = []
        for c0 in cx:
            x0, y0, x1, y1 = _rosto_tela(est, W, H, (c0[0] * W, c0[1] * H, c0[2] * W, c0[3] * H))
            qs.append(y1 + (y1 - y0) * 0.08)
        q90 = float(np.percentile(qs, 90)) if qs else 0.6 * H
        self.y_padrao = d.limitar(max(q90 + 0.018 * H, 0.64 * H), 0.5 * H, BASE_SEG * H - self.h)
        self.est, self.g = est, g
        for pg in self.paginas:
            jan = _janela(est, g, pg["ini"], pg["fim"])
            pg["y"] = d.limitar(max(self.y_padrao, jan["queixo"] + 0.015 * H), 0.5 * H, BASE_SEG * H - self.h)
            pg["giro"] = (0.9, -0.7, 0.5, -1.0, 0.7)[pg["i"] % 5]

    def _layout(self, pg):
        k = ("e13_leg", pg["i"])
        g = self.g
        if k in g.cache:
            return g.cache[k]
        W = self.W
        txts = [(w["texto"].upper() if self.maius else w["texto"]) for w in pg["pal"]]
        frase = " ".join(txts)
        pad = 0.045 * W
        tam = self.tam
        linhas = [list(range(len(txts)))]
        while True:
            f = d.fonte(tam, self.peso, self.fam)
            if f.getlength(frase) <= self.larg_max - pad * 2:
                linhas = [list(range(len(txts)))]
                break
            if self.max_linhas >= 2 and len(txts) >= 2:   # só quando o perfil permite
                melhor = None
                for corte in range(1, len(txts)):
                    a, b = " ".join(txts[:corte]), " ".join(txts[corte:])
                    lw = max(f.getlength(a), f.getlength(b))
                    if lw <= self.larg_max - pad * 2 and (melhor is None or lw < melhor[0]):
                        melhor = (lw, corte)
                if melhor:
                    linhas = [list(range(melhor[1])), list(range(melhor[1], len(txts)))]
                    break
            if tam <= self.tam_min:
                linhas = [list(range(len(txts)))]
                break
            tam = max(self.tam_min, int(tam * 0.93))
        f = d.fonte(tam, self.peso, self.fam)
        al = f.size * 1.08
        esp = f.getlength(" ")
        larg_l = [sum(f.getlength(txts[i]) for i in ln) + esp * (len(ln) - 1) for ln in linhas]
        tw = max(larg_l)
        w = int(d.limitar(tw + pad * 2, 0.40 * W, 0.84 * W))
        h = int(al * len(linhas) + f.size * 0.70)
        pos = {}
        for li, ln in enumerate(linhas):
            x = (w - larg_l[li]) / 2
            y = f.size * 0.30 + li * al - f.size * 0.10
            for i in ln:
                pos[i] = (x, y)
                x += f.getlength(txts[i]) + esp
        fr = [(0.0, 0.02), (0.996, 0.0), (1.0, 0.985), (0.004, 1.0)]
        m = _poligono(w, h, fr)
        lum = 1 + 0.014 * _ruido(w, h, 41 + pg["i"] % 3)
        arr = np.empty((h, w, 4), np.uint8)
        arr[:, :, :3] = (np.array(d.cor(self.papel)[:3], np.float32)[None, None] * lum[:, :, None]).clip(0, 255)
        arr[:, :, 3] = np.asarray(m)
        tira = Image.fromarray(arr, "RGBA")
        sombra, (dx, dy) = d.sombra(tira, raio=0.011 * W, opacidade=0.17, desloc=(0.004 * W, 0.008 * W))
        lay = {"tira": sombra, "off": (-dx, -dy), "w": w, "h": h, "f": f, "txts": txts, "pos": pos}
        g.cache[k] = lay
        return lay

    def ativa(self, t):
        for pg in self.paginas:
            if pg["ini"] <= t < pg["fim"]:
                return pg
        return None

    def _estado(self, pg, t):
        """Estado de cada palavra da tira no instante t: (aparecer, cor-de-falada), quantizados."""
        pals = pg["pal"]
        est = []
        for i, w in enumerate(pals):
            ini = w["inicio"] - 0.04
            if t < ini:
                est.append(None)
                continue
            ka = d.saida(d.mapear(t, ini, ini + 0.14))
            prox = pals[i + 1]["inicio"] - 0.04 if i + 1 < len(pals) else w["fim"] + 0.25
            solta = max(prox, w["fim"])
            if t < solta:
                kd = d.saida(d.mapear(t, ini, ini + 0.12))
            else:
                kd = 1 - d.suave(d.mapear(t, solta, solta + 0.14))
            est.append((round(ka * 6) / 6, round(kd * 6) / 6))
        return tuple(est)

    def _palavra(self, pg, i, kd):
        """Imagem de uma palavra da tira na cor do instante (kd: 0 = tinta, 1 = vinho da palavra falada)."""
        k = ("e13_legw", pg["i"], i, kd)
        g = self.g
        if k in g.cache:
            return g.cache[k]
        lay = self._layout(pg)
        f = lay["f"]
        txt = lay["txts"][i]
        mgm = int(f.size * 0.25)
        cam = Image.new("RGBA", (int(f.getlength(txt)) + 2 * mgm, int(f.size * 1.35) + 2 * mgm), (0, 0, 0, 0))
        cb, cd = d.cor(self.cor), d.cor(self.destaque)
        cor = tuple(int(cb[j] + (cd[j] - cb[j]) * kd) for j in range(3))
        d.escrever(cam, (mgm, mgm), [txt], f, cor)
        g.cache[k] = cam
        return cam

    def desenhar(self, img, t):
        pg = self.ativa(t)
        if pg is None:
            return
        lay = self._layout(pg)
        k = d.saida(d.mapear(t, pg["ini"], pg["ini"] + 0.2))
        ks = d.suave(d.mapear(t, pg["fim"] - 0.12, pg["fim"])) if pg["fim"] - pg["ini"] > 0.3 else 0.0
        prox_pg = self.paginas[pg["i"] + 1] if pg["i"] + 1 < len(self.paginas) else None
        if prox_pg is not None and prox_pg["ini"] - pg["fim"] < 0.05:
            ks = 0.0   # a próxima tira entra no lugar: esta só some no instante da troca
        op = k * (1 - ks)
        if op <= 0.004:
            return
        tira = lay["tira"]
        cx = LEG_X * self.W - (1 - k) * 0.035 * self.W
        cy = pg["y"] + lay["h"] / 2
        xt, yt = cx - tira.width / 2, cy - tira.height / 2
        _por(img, tira, xt, yt, op)
        ox, oy = lay["off"]
        f = lay["f"]
        mgm = int(f.size * 0.25)
        for i, st in enumerate(self._estado(pg, t)):
            if st is None:
                continue
            ka, kd = st
            x, y = lay["pos"][i]
            _por(img, self._palavra(pg, i, kd), xt + ox + x - mgm, yt + oy + y - mgm + (1 - ka) * f.size * 0.22,
                 op * ka)


# ------------------------------------------------------------------ pessoa recortada com borda de papel

def _kernel(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def _matriz(est, W, H, t, s, Yb, x0, y0, pad):
    """Transformação (origem do recorte -> tela): escala s, giro com balanço, âncora embaixo no centro."""
    fase = 2 * math.pi * t / PERIODO
    ang = math.radians(GIRO0 + BALANCO * math.sin(fase))
    dx = 0.006 * W * math.sin(fase)
    dy = -0.006 * H * (1 - math.cos(fase)) / 2
    ca, sa = math.cos(ang) * s, math.sin(ang) * s
    # tela = A·(p - âncora_origem) + âncora_tela ; A = s·[[cos, sin], [-sin, cos]] (giro anti-horário)
    ax, ay = W / 2 - (x0 - pad), H - (y0 - pad)   # âncora da origem nas coordenadas do recorte
    tx = W / 2 + dx - (ca * ax + sa * ay)
    ty = Yb * H + dy - (-sa * ax + ca * ay)
    return np.array([[ca, sa, tx], [-sa, ca, ty]], np.float64)


def _aplicar(src_rgba, M, W, H, fundo_rgb):
    if cv2 is not None:
        return cv2.warpAffine(src_rgba, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                              borderValue=(*fundo_rgb, 0))
    A = np.vstack([M, [0, 0, 1]])
    inv = np.linalg.inv(A)
    im = Image.fromarray(src_rgba, "RGBA")
    out = im.transform((W, H), Image.AFFINE, tuple(inv[:2].reshape(6)), Image.BILINEAR,
                       fillcolor=(*fundo_rgb, 0))
    return np.asarray(out)


_RAMPA = np.clip((np.arange(256) - 128) * 2.0 + 128, 0, 255).astype(np.uint8)


def _fator(W):
    """Redução usada nas contas da silhueta (~270 px de largura)."""
    return max(2, int(round(W / 270)))


def _ilhas_fora(bi):
    """Tira pedaços soltos pequenos (texto do vídeo, sujeira da máscara): fica só o que é corpo."""
    n, lab, st, _ = cv2.connectedComponentsWithStats(bi, connectivity=8)
    if n <= 2:
        return bi
    areas = st[:, 4].copy()
    areas[0] = 0
    manter = areas >= max(areas.max() * 0.04, 16)
    manter[0] = False
    if manter[1:].all():
        return bi
    return np.where(manter[lab], 255, 0).astype(np.uint8)


def _abrir(bi, r):
    """Abertura morfológica (tira tudo que é mais fino que 2r) em uint8 0/255."""
    if r < 1:
        return bi
    if cv2 is not None:
        return cv2.morphologyEx(bi, cv2.MORPH_OPEN, _kernel(r))
    im = Image.fromarray(bi, "L")
    return np.asarray(im.filter(ImageFilter.MinFilter(2 * r + 1)).filter(ImageFilter.MaxFilter(2 * r + 1)))


def _reforco(bi, rosto, r_topo):
    """Conserta dois defeitos comuns da máscara, usando a caixa do rosto (px reduzidos):
    1) acima da testa, pedacinhos estreitos grudados na cabeça (fios, letras gravadas no vídeo) somem;
    2) quando a máscara perde o queixo/pescoço e a cabeça fica solta do corpo, uma ponte da largura do
       pescoço liga o queixo ao corpo (os pixels ali são o pescoço de verdade, vindos do vídeo)."""
    if rosto is None:
        return bi
    h, w = bi.shape
    rx0, ry0, rx1, ry1 = rosto
    rw, rh = rx1 - rx0, ry1 - ry0
    if rw < 4 or rh < 4 or rx1 <= 0 or rx0 >= w or ry1 <= 0 or ry0 >= h:
        return bi
    cx = (rx0 + rx1) / 2
    d0, d1 = int(max(0, cx - 0.15 * rw)), int(min(w, cx + 0.15 * rw + 1))   # faixa estreita: detecta
    a0, a1 = int(max(0, cx - 0.22 * rw)), int(min(w, cx + 0.22 * rw + 1))   # largura do pescoço: preenche
    if d1 - d0 < 2:
        return bi
    cov = (bi[:, d0:d1] > 0).mean(axis=1)
    meio = int(d.limitar(ry0 + 0.5 * rh, 0, h - 1))
    if cov[meio] < 0.6:            # a caixa do rosto não bate com a máscara: não mexe
        return bi
    bi = bi.copy()
    # 1) topo da cabeça
    y_lim = int(ry0 - 0.12 * rh)
    if y_lim > 2 and r_topo >= 1:
        bi[:y_lim] = _abrir(bi, r_topo)[:y_lim]
    # 2) ponte do pescoço: só quando a faixa do meio fica quase vazia entre o queixo e o corpo
    g0, g1 = int(max(0, ry1 - 0.25 * rh)), int(min(h, ry1 + 0.7 * rh))
    buraco = np.flatnonzero(cov[g0:g1] < 0.4)
    if len(buraco):
        ini = g0 + int(buraco[0])
        corpo = np.flatnonzero(cov[ini:g1] >= 0.8)
        if len(corpo):
            fim = ini + int(corpo[0])
            bi[g0:min(h, fim + 2), a0:a1] = 255
    return bi


def _silhueta(peq, r_fecha, r_borda, rosto=None, r_topo=0):
    """Máscara reduzida -> (silhueta lisa, borda de papel) reduzidas (uint8). Tira fiapos e pedaços
    soltos, fecha frestas, tapa buracos pequenos e alisa o contorno (como um corte de tesoura)."""
    h, w = peq.shape
    if cv2 is not None:
        _, bi = cv2.threshold(peq, LIMIAR, 255, cv2.THRESH_BINARY)
        r_abre = max(1, (r_fecha + 1) // 2)
        bi = cv2.morphologyEx(bi, cv2.MORPH_OPEN, _kernel(r_abre))       # fiapos finos somem
        bi = _reforco(bi, rosto, r_topo)                                 # topo limpo + pescoço
        bi = _ilhas_fora(bi)                                             # pedaços soltos somem
        # fecha frestas; mais alto que largo: junta cabeça e corpo quando a máscara perde o pescoço,
        # sem encher o vão entre o braço e o corpo
        alto = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r_fecha + 1, 4 * r_fecha + 1))
        # margem vazia em cima e dos lados (senão o fechamento "gruda" a cabeça na borda de cima e
        # aparece uma coluna do fundo acima dela); embaixo repete a última linha (o corpo continua)
        mg = 2 * r_fecha + 2
        bi_p = np.pad(bi, ((mg, 0), (mg, mg)), mode="constant")
        bi_p = np.pad(bi_p, ((0, mg), (0, 0)), mode="edge")
        bi = np.ascontiguousarray(cv2.morphologyEx(bi_p, cv2.MORPH_CLOSE, alto)[mg:mg + h, mg:mg + w])
        n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.bitwise_not(bi), connectivity=4)
        if n > 2:
            x, y, ww, hh, area = st[:, 0], st[:, 1], st[:, 2], st[:, 3], st[:, 4]
            tapar = (area < 0.05 * w * h) & (x > 0) & (y > 0) & (x + ww < w) & (y + hh < h)
            tapar[0] = False
            if tapar.any():
                bi[tapar[lab]] = 255
        bi = _ilhas_fora(bi)
        sil = cv2.GaussianBlur(bi, (0, 0), 0.9)
        bor = cv2.GaussianBlur(cv2.dilate(bi, _kernel(r_borda)), (0, 0), 0.8)
        return sil, bor
    im = Image.fromarray(peq, "L").point(lambda v: 255 if v > LIMIAR else 0)
    ta = 2 * max(1, (r_fecha + 1) // 2) + 1
    im = im.filter(ImageFilter.MinFilter(ta)).filter(ImageFilter.MaxFilter(ta))
    im = Image.fromarray(_reforco(np.asarray(im), rosto, r_topo), "L")
    tam = 2 * r_fecha + 1
    mg = tam + 1   # mesma margem do caminho OpenCV (sem coluna grudada na borda de cima)
    bi_p = np.pad(np.asarray(im), ((mg, 0), (mg, mg)), mode="constant")
    bi_p = np.pad(bi_p, ((0, mg), (0, 0)), mode="edge")
    im = Image.fromarray(bi_p, "L").filter(ImageFilter.MaxFilter(tam)).filter(ImageFilter.MinFilter(tam))
    im = im.crop((mg, mg, mg + w, mg + h))
    moldura = Image.new("L", (w + 2, h + 2), 0)
    moldura.paste(im, (1, 1))
    ImageDraw.floodfill(moldura, (0, 0), 128)
    bi = np.where(np.asarray(moldura)[1:-1, 1:-1] == 128, 0, 255).astype(np.uint8)
    bim = Image.fromarray(bi, "L")
    sil = np.asarray(bim.filter(ImageFilter.GaussianBlur(0.9)))
    bor = np.asarray(bim.filter(ImageFilter.MaxFilter(2 * r_borda + 1)).filter(ImageFilter.GaussianBlur(0.8)))
    return sil, bor


def _subir(peq, w, h):
    """Volta ao tamanho cheio com borda nítida e suave (rampa)."""
    if cv2 is not None:
        return cv2.LUT(cv2.resize(peq, (w, h), interpolation=cv2.INTER_LINEAR), _RAMPA)
    return _RAMPA[np.asarray(Image.fromarray(peq, "L").resize((w, h), Image.BILINEAR))]


def _reduzir(arr, w, h):
    if cv2 is not None:
        return cv2.resize(arr, (w, h), interpolation=cv2.INTER_AREA)
    return np.asarray(Image.fromarray(arr, "L").resize((w, h), Image.BOX))


def _borrar(arr, raio):
    if cv2 is not None:
        return cv2.GaussianBlur(arr, (0, 0), raio)
    return np.asarray(Image.fromarray(arr, "L").filter(ImageFilter.GaussianBlur(raio)))


def _aplicar_sombra(c, img, som, M, fx, fy, mg, desloc, forca, caixa):
    """Sombra suave: 'som' é o alfa reduzido (com margem mg) da camada. Vai direto (reduzido -> tela)
    só na região 'caixa' da tela, e escurece o fundo ali (rápido)."""
    W, H = c.W, c.H
    bx0, by0, bx1, by1 = caixa
    pad = int(0.03 * W)
    bx0, by0, bx1, by1 = max(0, bx0 - pad), max(0, by0 - pad), min(W, bx1 + pad), min(H, by1 + pad)
    bw, bh = bx1 - bx0, by1 - by0
    if bw < 2 or bh < 2:
        return img
    A = M[:, :2] @ np.diag([fx, fy])
    t = M[:, 2] - A @ np.array([mg, mg], np.float64) + np.array(desloc, np.float64) - np.array([bx0, by0])
    Ms = np.hstack([A, t[:, None]])
    som = (som.astype(np.uint16) * int(forca * 256) >> 8).astype(np.uint8)
    if cv2 is not None:
        a = cv2.warpAffine(som, Ms, (bw, bh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        mask = Image.fromarray(a, "L")
    else:
        inv = np.linalg.inv(np.vstack([Ms, [0, 0, 1]]))
        mask = Image.fromarray(som, "L").transform((bw, bh), Image.AFFINE, tuple(inv[:2].reshape(6)), Image.BILINEAR)
    img.paste(_liso(c.g, SOMBRA).crop((bx0, by0, bx1, by1)), (bx0, by0), mask)
    return img


def _liso(g, cor):
    """Imagem de cor lisa do tamanho do quadro (cache). Colar um recorte dela com máscara é ~3x mais
    rápido no Pillow do que colar a cor direto com máscara."""
    k = ("e13_liso", cor, g.W, g.H)
    if k not in g.cache:
        g.cache[k] = Image.new("RGBA", (g.W, g.H), cor)
    return g.cache[k]


def _caixa_na_tela(M, w, h, W, H):
    cantos = M @ np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], np.float64).T
    bx0, by0 = max(0, int(math.floor(cantos[0].min())) - 1), max(0, int(math.floor(cantos[1].min())) - 1)
    bx1, by1 = min(W, int(math.ceil(cantos[0].max())) + 1), min(H, int(math.ceil(cantos[1].max())) + 1)
    return bx0, by0, bx1, by1


def _colar_transformado(img, camada_np, M, W, H, fundo_rgb):
    """Aplica M na camada e cola só na região que ela ocupa na tela."""
    h, w = camada_np.shape[:2]
    bx0, by0, bx1, by1 = _caixa_na_tela(M, w, h, W, H)
    if bx1 - bx0 < 2 or by1 - by0 < 2:
        return
    M2 = M.copy()
    M2[0, 2] -= bx0
    M2[1, 2] -= by0
    out = Image.fromarray(_aplicar(camada_np, M2, bx1 - bx0, by1 - by0, fundo_rgb), "RGBA")
    img.paste(out, (bx0, by0), out.getchannel("A"))


def _pessoa_recortada(c, est, img):
    """Pessoa recortada com borda branca de papel e sombra, reduzida/girada, colada em img."""
    W, H = c.W, c.H
    m = c.mascara
    if m.size != (W, H):
        m = m.resize((W, H), Image.BILINEAR)
    m = np.asarray(m)
    peq = m[::8, ::8]
    linhas = np.flatnonzero(peq.max(axis=1) > 60)
    cols = np.flatnonzero(peq.max(axis=0) > 60)
    if len(linhas) == 0:
        return img
    s, Yb = est["s"], est["Yb"]
    f = _fator(W)
    rb = max(1, int(round(BORDA * W / s / f)))   # borda de papel (px reduzidos)
    rf = max(1, int(round(0.016 * W / f)))       # fecha frestas da máscara
    pad = (rb + 3) * f
    y0, y1 = max(0, linhas[0] * 8 - 8), min(H, linhas[-1] * 8 + 16)
    x0, x1 = max(0, cols[0] * 8 - 8), min(W, cols[-1] * 8 + 16)
    embaixo = y1 >= H
    h_in, w_in = y1 - y0, x1 - x0
    ch, cw = h_in + 2 * pad, w_in + 2 * pad
    mp = np.zeros((ch, cw), np.uint8)
    mp[pad:pad + h_in, pad:pad + w_in] = m[y0:y1, x0:x1]
    if embaixo:   # o corpo continua abaixo do quadro: estende a última linha (o corte fica fora da tela)
        mp[pad + h_in:, pad:pad + w_in] = m[H - 1, x0:x1][None, :]
    sw, sh = -(-cw // f), -(-ch // f)
    fx, fy = cw / sw, ch / sh
    rx0, ry0, rx1, ry1 = c.rosto           # caixa do rosto -> coordenadas da máscara reduzida
    ox, oy = x0 - pad, y0 - pad
    rosto_red = ((rx0 - ox) / fx, (ry0 - oy) / fy, (rx1 - ox) / fx, (ry1 - oy) / fy)
    r_topo = max(1, int(round(0.012 * W / f)))
    sil, bor = _silhueta(_reduzir(mp, sw, sh), rf, rb, rosto_red, r_topo)
    M = _matriz(est, W, H, c.t, s, Yb, x0, y0, pad)
    caixa = _caixa_na_tela(M, cw, ch, W, H)
    mg = int(math.ceil(0.024 * W / s / f))
    som = _borrar(np.pad(bor, mg), max(0.8, 0.011 * W / s / f))
    img = _aplicar_sombra(c, img, som, M, fx, fy, mg, (0.006 * W, 0.009 * H), 0.30, caixa)
    if cv2 is None:   # caminho só com Pillow (mais lento, mesmo visual)
        sil_g = _subir(sil, cw, ch)
        camada = Image.new("RGBA", (cw, ch), (*PAPEL_BORDA, 255))
        camada.putalpha(Image.fromarray(_subir(bor, cw, ch), "L"))
        reg = c.fonte.crop((x0, y0, x1, y1))
        camada.paste(reg, (pad, pad), Image.fromarray(np.ascontiguousarray(sil_g[pad:pad + h_in, pad:pad + w_in]), "L"))
        if embaixo:
            linha = reg.crop((0, h_in - 1, w_in, h_in)).resize((w_in, pad), Image.NEAREST)
            camada.paste(linha, (pad, pad + h_in),
                         Image.fromarray(np.ascontiguousarray(sil_g[pad + h_in:, pad:pad + w_in]), "L"))
        _colar_transformado(img, np.asarray(camada), M, W, H, PAPEL_BORDA)
        return img
    # OpenCV: cada parte vai direto para a região da tela (sem montar a camada no tamanho original)
    bx0, by0, bx1, by1 = caixa
    bw, bh = bx1 - bx0, by1 - by0
    if bw < 2 or bh < 2:
        return img
    M2 = M.copy()
    M2[0, 2] -= bx0
    M2[1, 2] -= by0
    Mf = M2.copy()                       # vídeo inteiro (coordenadas do quadro) -> região da tela
    Mf[:, 2] += M2[:, :2] @ np.array([pad - x0, pad - y0], np.float64)
    Mk = np.hstack([M2[:, :2] @ np.diag([fx, fy]), M2[:, 2:3]])   # silhuetas reduzidas -> tela
    rgb = cv2.warpAffine(np.asarray(c.fonte), Mf, (bw, bh), flags=cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_REPLICATE)
    sil_o = cv2.LUT(cv2.warpAffine(sil, Mk, (bw, bh), flags=cv2.INTER_LINEAR), _RAMPA)
    bor_o = cv2.LUT(cv2.warpAffine(bor, Mk, (bw, bh), flags=cv2.INTER_LINEAR), _RAMPA)
    # papel branco na borda e a pessoa por cima, dentro da silhueta
    img.paste(_liso(c.g, (*PAPEL_BORDA, 255)).crop((bx0, by0, bx1, by1)), (bx0, by0), Image.fromarray(bor_o, "L"))
    img.paste(Image.fromarray(rgb, "RGBA"), (bx0, by0), Image.fromarray(sil_o, "L"))
    return img


def _foto(c, est, img, pal="lilas", movendo=()):
    """Sem recorte: o quadro inteiro vira uma foto com margem branca, colada torta no caderno,
    com sombra e duas fitas adesivas nos cantos de cima."""
    W, H = c.W, c.H
    s, Yb = est["s"], est["Yb"]
    b = int(round(BORDA_FOTO * W / s))
    cw, ch = W + 2 * b, H + 2 * b
    M = _matriz(est, W, H, c.t, s, Yb, 0, 0, b)
    f = _fator(W)
    sw, sh = -(-cw // f), -(-ch // f)
    mg = int(math.ceil(0.03 * W / s / f))
    k = ("e13_sombra_foto", W, H, round(s, 4))
    if k not in c.g.cache:
        ret = np.zeros((sh + 2 * mg, sw + 2 * mg), np.uint8)
        ret[mg:mg + sh, mg:mg + sw] = 255
        c.g.cache[k] = _borrar(ret, max(0.8, 0.014 * W / s / f))
    caixa = _caixa_na_tela(M, cw, ch, W, H)
    img = _aplicar_sombra(c, img, c.g.cache[k], M, cw / sw, ch / sh, mg, (0.007 * W, 0.010 * H), 0.34, caixa)
    if cv2 is not None:
        bx0, by0, bx1, by1 = caixa
        bw, bh = bx1 - bx0, by1 - by0
        M2 = M.copy()
        M2[0, 2] -= bx0
        M2[1, 2] -= by0
        Mf = M2.copy()
        Mf[:, 2] += M2[:, :2] @ np.array([b, b], np.float64)
        foto = cv2.warpAffine(np.asarray(c.fonte), Mf, (bw, bh), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(*PAPEL_BORDA, 255))
        # contorno da foto: retângulo pequeno levado direto à tela (borda reta e suave, barato)
        kq = ("e13_quadro_foto", W, H, b)
        if kq not in c.g.cache:
            q = np.zeros((sh + 2, sw + 2), np.uint8)
            q[1:-1, 1:-1] = 255
            c.g.cache[kq] = q
        Mq = np.hstack([M2[:, :2] @ np.diag([cw / sw, ch / sh]),
                        (M2[:, 2] - M2[:, :2] @ np.array([cw / sw, ch / sh]))[:, None]])
        alfa = cv2.LUT(cv2.warpAffine(c.g.cache[kq], Mq, (bw, bh), flags=cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_CONSTANT, borderValue=0), _RAMPA)
        fim = Image.fromarray(foto, "RGBA")
        img.paste(fim, (bx0, by0), Image.fromarray(alfa, "L"))
    else:
        camada = Image.new("RGBA", (cw, ch), (*PAPEL_BORDA, 255))
        camada.paste(c.fonte, (b, b))
        _colar_transformado(img, np.asarray(camada), M, W, H, PAPEL_BORDA)
    # folha do título por cima da parte de cima da foto (como um bilhete colado), antes das fitas
    cam, (fx_, fy_) = _folha(c.g, "a", pal)
    _por(img, cam, fx_ - cam.width / 2, fy_ - cam.height / 2)
    for p2, k2, modo2 in movendo:
        _folhas_movendo(c, img, p2, k2, modo2, ("a",))
    fita = _fita(c.g)
    ang = math.degrees(math.atan2(-M[1, 0], M[0, 0]))
    for (px, py), giro in (((b * 0.3, b * 0.3), 32), ((cw - b * 0.3, b * 0.3), -32)):
        x, y = M @ np.array([px, py, 1.0])
        _colar(img, fita, (x, y), graus=giro + ang, opacidade=0.88)
    return img


def _fita(g):
    k = ("e13_fita", g.W)
    if k in g.cache:
        return g.cache[k]
    W = g.W
    w, h = int(0.20 * W), int(0.055 * W)
    rng = np.random.default_rng(77)
    pts = [(0, 0)]
    for i in range(1, 6):
        pts.append((rng.uniform(0.0, 0.05) * w, i * h / 6))
    pts += [(0, h), (w, h)]
    for i in range(5, 0, -1):
        pts.append((w - rng.uniform(0.0, 0.05) * w, i * h / 6))
    pts.append((w, 0))
    m = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(m).polygon([(x * 2, y * 2) for x, y in pts], fill=200)
    m = m.reduce(2)
    cam = Image.new("RGBA", (w, h), (*FITA, 255))
    cam.putalpha(m)
    g.cache[k] = cam
    return cam


# ------------------------------------------------------------------ cenas (troca de folhas)

def _paleta_e_transicao(c):
    """Paleta de base e folhas em movimento (entrando/saindo) no instante t."""
    t = c.t
    base = "lilas"
    movendo = []
    cenas = sorted([e for e in c.g.plano["eventos"] if e.get("tipo") == "cena" and e.get("paleta") in PALETAS],
                   key=lambda e: e["inicio"])
    for e in cenas:
        ini, fim = float(e["inicio"]), float(e["fim"])
        if t < ini:
            break
        if t <= fim:
            k = d.mapear(t, ini, ini + CENA_ENTRA)
            if k >= 1:
                base = e["paleta"]
            else:
                movendo.append((e["paleta"], k, "entra"))
        elif t <= fim + CENA_SAI:
            movendo.append((e["paleta"], d.mapear(t, fim, fim + CENA_SAI), "sai"))
    return base, movendo


def _folhas_movendo(c, img, pal, k, modo, quais=("b", "a")):
    """Folhas de uma cena entrando (deslizam por cima e assentam) ou saindo (voltam para fora)."""
    W, H = c.W, c.H
    for qual in quais:
        cam, (cx, cy) = _folha(c.g, qual, pal)
        dx = dy = giro = 0.0
        if modo == "entra":
            u = d.mola(d.mapear(k, 0.0, 0.85), 0.9) if qual == "a" else d.mola(d.mapear(k, 0.15, 1.0), 0.9)
            if qual == "a":
                dy -= (1 - u) * 0.42 * H
                dx -= (1 - u) * 0.10 * W
            else:
                dx += (1 - u) * 0.62 * W
            giro = (1 - u) * (7 if qual == "a" else -9)
        else:
            u = d.entrada(d.mapear(k, 0.0, 0.85)) if qual == "b" else d.entrada(d.mapear(k, 0.15, 1.0))
            if qual == "a":
                dy -= u * 0.45 * H
                dx += u * 0.08 * W
            else:
                dx += u * 0.65 * W
            giro = u * (-6 if qual == "a" else 8)
        _colar(img, cam, (cx + dx, cy + dy), graus=giro)


# ------------------------------------------------------------------ quadro

def quadro(c):
    est = _est(c.g)
    base, movendo = _paleta_e_transicao(c)
    recorte = c.mascara is not None and est["rec"]
    atras = ("b", "a") if recorte else ("b",)   # sem recorte, a folha do título fica por cima da foto
    img = _fundo_com_folhas(c.g, base, atras).copy()
    for pal, k, modo in movendo:
        _folhas_movendo(c, img, pal, k, modo, atras)
    # pessoa recortada (com máscara) ou foto colada (sem recorte / máscara acabou antes do vídeo)
    if recorte:
        img = _pessoa_recortada(c, est, img)
    else:
        img = _foto(c, est, img, base, movendo)
    lays = est["lay"]
    for e in c.eventos:   # rabiscos primeiro (ficam por baixo de títulos e etiquetas)
        if e.get("tipo") == "rabisco":
            lay = lays.get(_chave(e))   # calculado em preparar(); evento inválido fica de fora
            if lay is not None:
                _desenha_rabisco(c, img, e, lay)
    for e in c.eventos:
        lay = lays.get(_chave(e))
        if lay is None:
            continue
        if e.get("tipo") == "titulo":
            _desenha_titulo(c, img, e, lay)
        elif e.get("tipo") == "etiqueta":
            _desenha_etiqueta(c, img, e, lay)
    if est.get("leg"):
        est["leg"].desenhar(img, c.t)
    return img


