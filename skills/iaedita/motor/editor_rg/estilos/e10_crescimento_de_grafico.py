"""10 · Crescimento de gráfico — quando a pessoa fala de números ou de crescimento, a câmera recua, o fundo
vira uma parede de papel creme e um gráfico (linha ou barras) cresce ATRÁS dela: grade fina, linha
verde-limão com brilho e núcleo branco (ou barras), pontos que acendem, um traço tracejado que acompanha o
desenho e um selo verde-limão no ponto mais alto, que entra no instante em que o número é dito. Na saída,
uma faixa de luz atravessa a tela e a câmera volta ao enquadramento original.

Além do gráfico, o evento `numero` mostra um cartão de papel com o número contando de 0 até o valor e um
ícone de barras subindo (selo de número), para números citados de passagem.

Com recorte: o vídeo recua como um cartão, a sala do fundo se desfaz em papel e a pessoa fica na frente do
gráfico (a cabeça passa na frente da grade). Sem recorte: o vídeo inteiro recua como um cartão sobre a
parede de papel e o gráfico cresce acima da cabeça, sem nunca cobrir o rosto.
"""
from __future__ import annotations

import math
import re

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import desenho as d

try:  # OpenCV deixa o recuo da câmera bem mais rápido; sem ele o resultado é igual, só mais lento
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

INFO = {
    "id": "10-crescimento-de-grafico",
    "nome": "Crescimento de gráfico",
    "precisa_recorte": True,
    "antes": 0.0,     # tudo acontece dentro de [inicio, fim]
    "depois": 0.0,
    # legenda da prévia aprovada: Inter 800, creme, caixa grafite, palavra falada em verde-limão, sempre embaixo
    "legenda": {"peso": 800, "tamanho": 0.060, "cor": "#F8F7F0", "destaque": "#D4ED80", "caixa": "#222729ED",
                "max_caracteres": 18, "max_linhas": 1, "animacao": "subir", "posicao": "baixo"},
    "eventos": {
        "grafico": "inicio (a câmera começa a recuar; 1,6 a 2,5 s antes de selo_em), fim (tudo já voltou ao normal), "
                   "forma ('linha' padrão | 'barras'), valores (2 a 7 números em ordem de tempo; o ÚLTIMO é o maior), "
                   "selo (texto do selo, até 12 letras, ex. '+300%', '26 VÍDEOS'), selo_em (segundo exato em que a "
                   "pessoa diz o número/palavra do selo: o desenho termina e o selo entra aí), titulo (opcional, 1-4 "
                   "palavras, até 22 letras), rotulos (opcional: [começo, fim] ou um por valor, até 9 letras cada), som",
        "numero": "inicio, fim (1,5-4 s), valor (número, ex. 26 ou 3.5), prefixo (opcional: '+', 'R$'), sufixo "
                  "(opcional: '%', ' mil', 'x'), rotulo (1-3 palavras, até 18 letras), contar (true padrão: conta de "
                  "0 até o valor), posicao ('auto' padrão | 'baixo' | 'topo'), som",
    },
}

# ------------------------------------------------------------------ paleta (da prévia aprovada)
PAREDE_TOPO = (243, 241, 232)      # parede de papel creme
PAREDE_BASE = (230, 227, 214)
PAPEL_TINTA = (246, 244, 236)      # cor para onde a sala do fundo se desfaz (com recorte)
BORDA_CARTAO = (205, 203, 190)
TINTA = "#222729"
LIMA = "#D4ED80"
EIXO = "#596B5B"
GRADE = (110, 123, 113)
NUCLEO = "#FDFEF8"
CENTRO_PONTO = "#2A3C2B"
FAIXA_LUZ = (232, 236, 215)
CARTAO_NUM = "#F8F7F0"

# ------------------------------------------------------------------ medidas (frações de u = largura 9:16)
TOPO_SEG = 0.118          # nada acima disto (zona segura de cima)
LEGIVEL = 0.035           # menor texto permitido
ALVO_REC = 0.30           # com recorte: topo da cabeça vai para 30% da altura
ALVO_SEM = 0.36           # sem recorte: a cabeça fica abaixo do gráfico
S_MIN_REC, S_MIN_SEM = 0.62, 0.56
TINTA_FUNDO = 1.0         # com recorte, a sala some por completo no papel (fica só a pessoa)
RAIO_CARTAO = 0.034
T_ENTRA, T_SAI = 0.55, 0.50
SELO_TAM = 0.047
SELO_ALT = 0.090
ROT_TAM = 0.037
VALORES_PADRAO_LINHA = [130, 190, 165, 380, 340, 590, 710]   # a curva da prévia aprovada
VALORES_PADRAO_BARRAS = [2, 3, 4.5, 6.5, 9]


def _u(W, H):
    return min(W, H * 0.5625)


def _limpo(x) -> str:
    return " ".join(str(x or "").split())


# ------------------------------------------------------------------ validação do plano

_INTERNO = re.compile(r"(\b\d{2}-[a-z]|estilo\s*\d|\{|\}|seu texto|texto aqui|xxx|lorem|placeholder|evento\s*\d)", re.I)


def _numeros(v):
    if not isinstance(v, (list, tuple)):
        return None
    out = []
    for x in v:
        try:
            f = float(x)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(f):
            return None
        out.append(f)
    return out


def validar(plano, duracao):
    p = []
    evs = plano["eventos"]
    nossos = sorted([e for e in evs if e.get("tipo") in ("grafico", "numero")], key=lambda e: e["inicio"])
    if not any(e.get("tipo") == "grafico" for e in evs):
        p.append("Este estilo precisa de pelo menos um 'grafico' (o gráfico que cresce atrás da pessoa).")
    for a, b in zip(nossos, nossos[1:]):
        if b["inicio"] < a["fim"] + 0.3 - 1e-6:
            p.append(f"'{b.get('tipo')}' em {b['inicio']:.2f}s começa colado/sobreposto ao '{a.get('tipo')}' de "
                     f"{a['inicio']:.2f}s: deixe pelo menos 0,3 s entre o fim de um e o início do outro.")
    for e in evs:
        tipo, ini, fim = e.get("tipo"), e.get("inicio", 0), e.get("fim", 0)
        textos = []
        if tipo == "grafico":
            dur = fim - ini
            if dur < 2.6 - 1e-6:
                p.append(f"Gráfico em {ini:.2f}s curto demais ({dur:.1f}s): mínimo 2,6 s (ideal 3,5 a 6 s).")
            if dur > 9.0 + 1e-6:
                p.append(f"Gráfico em {ini:.2f}s longo demais ({dur:.1f}s): máximo 9 s.")
            forma = str(e.get("forma", "linha")).lower()
            if forma not in ("linha", "barras"):
                p.append(f"Gráfico em {ini:.2f}s: 'forma' deve ser 'linha' ou 'barras'.")
            if e.get("valores") is not None:
                vs = _numeros(e.get("valores"))
                if vs is None:
                    p.append(f"Gráfico em {ini:.2f}s: 'valores' deve ser uma lista de números.")
                elif not 2 <= len(vs) <= 7:
                    p.append(f"Gráfico em {ini:.2f}s: use de 2 a 7 valores (tem {len(vs)}).")
                elif min(vs) < 0:
                    p.append(f"Gráfico em {ini:.2f}s: valores negativos não são aceitos.")
                elif vs[-1] < max(vs) - 1e-9:
                    p.append(f"Gráfico em {ini:.2f}s: o último valor precisa ser o maior (é um gráfico de crescimento).")
            selo = _limpo(e.get("selo"))
            textos.append(selo)
            if len(selo) > 12:
                p.append(f"Selo do gráfico de {ini:.2f}s longo demais: '{selo}' (máx. 12 letras, ex. '+300%').")
            if e.get("selo_em") is not None:
                try:
                    se = float(e.get("selo_em"))
                except (TypeError, ValueError):
                    se = None
                if se is None:
                    p.append(f"Gráfico em {ini:.2f}s: 'selo_em' deve ser um número (segundos).")
                else:
                    if se < ini + 1.4 - 1e-6:
                        p.append(f"Gráfico em {ini:.2f}s: 'selo_em' ({se:.2f}s) cedo demais. Comece o gráfico pelo "
                                 f"menos 1,4 s antes do selo (inicio no máximo {se - 1.4:.2f}).")
                    if se > fim - 1.0 + 1e-6:
                        p.append(f"Gráfico em {ini:.2f}s: depois do selo ({se:.2f}s) deixe pelo menos 1 s até o "
                                 f"'fim' (fim pelo menos {se + 1.0:.2f}) para o público ler.")
            tit = _limpo(e.get("titulo"))
            textos.append(tit)
            if len(tit) > 22 or len(tit.split()) > 4:
                p.append(f"Título do gráfico de {ini:.2f}s longo demais: '{tit}' (máx. 4 palavras / 22 letras).")
            rots = e.get("rotulos")
            if rots is not None:
                if not isinstance(rots, (list, tuple)):
                    p.append(f"Gráfico em {ini:.2f}s: 'rotulos' deve ser uma lista de textos.")
                else:
                    n = len(_numeros(e.get("valores")) or (VALORES_PADRAO_BARRAS if forma == "barras"
                                                           else VALORES_PADRAO_LINHA))
                    if len(rots) not in (2, n):
                        p.append(f"Gráfico em {ini:.2f}s: 'rotulos' precisa ter 2 textos (começo e fim) ou {n} "
                                 f"(um por valor).")
                    for r in rots:
                        r = _limpo(r)
                        textos.append(r)
                        if len(r) > 9:
                            p.append(f"Rótulo '{r}' do gráfico de {ini:.2f}s longo demais (máx. 9 letras).")
        elif tipo == "numero":
            dur = fim - ini
            if dur < 1.4 - 1e-6:
                p.append(f"Número em {ini:.2f}s curto demais ({dur:.1f}s): mínimo 1,4 s.")
            if dur > 4.5 + 1e-6:
                p.append(f"Número em {ini:.2f}s longo demais ({dur:.1f}s): máximo 4,5 s.")
            try:
                v = float(e.get("valor"))
                if not math.isfinite(v) or v < 0 or v >= 1e7:
                    raise ValueError
            except (TypeError, ValueError):
                p.append(f"Número em {ini:.2f}s: 'valor' deve ser um número de 0 a 9.999.999 (ex. 26 ou 3.5).")
            rot = _limpo(e.get("rotulo"))
            textos.append(rot)
            if not rot:
                p.append(f"Número em {ini:.2f}s sem 'rotulo' (1 a 3 palavras que dizem o que é o número).")
            elif len(rot) > 18 or len(rot.split()) > 3:
                p.append(f"Rótulo do número em {ini:.2f}s longo demais: '{rot}' (máx. 3 palavras / 18 letras).")
            if len(str(e.get("prefixo") or "")) > 3:
                p.append(f"Número em {ini:.2f}s: 'prefixo' até 3 letras (ex. '+', 'R$').")
            if len(str(e.get("sufixo") or "")) > 5:
                p.append(f"Número em {ini:.2f}s: 'sufixo' até 5 letras (ex. '%', ' mil', 'x').")
            if e.get("posicao", "auto") not in ("auto", "baixo", "topo"):
                p.append(f"Número em {ini:.2f}s: 'posicao' deve ser 'auto', 'baixo' ou 'topo'.")
        for txt in textos:
            if txt and _INTERNO.search(txt):
                p.append(f"Texto interno/placeholder na tela em {ini:.2f}s: '{txt}'. Use palavras da fala.")
    return p


# ------------------------------------------------------------------ utilidades de imagem (OpenCV ou Pillow)

def _redim(arr, tam):
    """Redimensiona um array (L ou RGBA). Bilinear: no recuo (0,6x a 1x) fica igual ao 'area' e é 5x mais rápido."""
    w, h = tam
    if arr.shape[1] == w and arr.shape[0] == h:
        return arr
    if cv2 is not None:
        return cv2.resize(arr, (w, h), interpolation=cv2.INTER_LINEAR)
    modo = "L" if arr.ndim == 2 else {3: "RGB", 4: "RGBA"}[arr.shape[2]]
    return np.asarray(Image.fromarray(np.ascontiguousarray(arr), modo).resize((w, h), Image.BILINEAR))


def _borrar_peq(m, sigma):
    if cv2 is not None:
        return cv2.GaussianBlur(m, (0, 0), max(0.5, sigma))
    im = Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(sigma))
    return np.asarray(im).astype(np.float32) / 255.0


_CANTOS = {}


def _canto(r):
    """Alfa (r x r, 0-1) do canto superior esquerdo de um retângulo arredondado, com borda suave."""
    if r not in _CANTOS:
        yy, xx = np.mgrid[0:r, 0:r].astype(np.float32) + 0.5
        dist = np.sqrt((r - xx) ** 2 + (r - yy) ** 2)
        _CANTOS[r] = np.clip(r - dist + 0.5, 0, 1)
    return _CANTOS[r]


def _blocos_cantos(w, h, r, baixo):
    """(fatia_y, fatia_x, alfa) dos cantos arredondados de um retângulo w x h."""
    r = int(min(r, w // 2, h // 2))
    if r < 2:
        return []
    a = _canto(r)
    out = [(slice(0, r), slice(0, r), a), (slice(0, r), slice(w - r, w), a[:, ::-1])]
    if baixo:
        out += [(slice(h - r, h), slice(0, r), a[::-1, :]), (slice(h - r, h), slice(w - r, w), a[::-1, ::-1])]
    return out


def _mascara_cartao(w, h, r, baixo):
    """Máscara L (255 dentro) do cartão com cantos arredondados."""
    m = np.full((h, w), 255, np.uint8)
    for sy, sx, a in _blocos_cantos(w, h, r, baixo):
        m[sy, sx] = (a * 255).astype(np.uint8)
    return Image.fromarray(m, "L")


def _arredondar_mascara(ms, r, baixo):
    """Corta a máscara da pessoa nos cantos arredondados do cartão (ms é alterada)."""
    h, w = ms.shape
    for sy, sx, a in _blocos_cantos(w, h, r, baixo):
        ms[sy, sx] = (ms[sy, sx] * a).astype(np.uint8)
    return ms


def _parede(g):
    """Parede de papel creme (RGBA), com leve degradê e vinheta. Desenhada uma vez."""
    chave = ("e10", "parede")
    if chave not in g.cache:
        W, H = g.W, g.H
        y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        topo, base = np.array(PAREDE_TOPO, np.float32), np.array(PAREDE_BASE, np.float32)
        col = topo * (1 - y) + base * y
        arr = np.repeat(col, W, axis=1)
        yy, xx = np.ogrid[0:H, 0:W]
        dd = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H * 0.42) / (H * 0.8)) ** 2)
        arr *= (1 - 0.09 * np.clip(dd - 0.35, 0, 1) ** 1.3)[..., None].astype(np.float32)
        out = np.empty((H, W, 4), np.uint8)
        out[..., :3] = np.clip(arr, 0, 255).astype(np.uint8)
        out[..., 3] = 255
        g.cache[chave] = out
    return g.cache[chave]


def _fundo_cartao(g, sw, sh, x0, y0, r, k):
    """Parede + sombra suave do cartão + filete de borda, como array RGBA novo (nunca o do cache)."""
    W, H = g.W, g.H
    u = _u(W, H)
    if k <= 0.01:
        return _parede(g).copy()
    if True:
        f = 8
        pw, ph = max(2, W // f), max(2, H // f)
        m = np.zeros((ph, pw), np.float32)
        dy = 0.016 * u
        ya, yb = int((y0 + dy) / f), int(min(H + 4 * u, y0 + sh + dy) / f)
        xa, xb = int(x0 / f), int((x0 + sw) / f)
        m[max(0, ya):max(0, yb), max(0, xa):max(0, xb)] = 1.0
        m = _borrar_peq(m, 0.032 * u / f)
        fator = (255 * (1 - 0.30 * k * np.clip(m, 0, 1))).astype(np.uint8)
        fator = _redim(fator, (W, H))
        if cv2 is not None:   # parede x sombra (o alfa fica 255)
            base = cv2.multiply(_parede(g), cv2.cvtColor(fator, cv2.COLOR_GRAY2RGBA), scale=1 / 255)
        else:
            base = _parede(g).copy()
            base[..., :3] = (base[..., :3].astype(np.uint16) * fator[..., None] // 255).astype(np.uint8)
        # filete fino em volta do cartão (fica para fora: o cartão cobre o lado de dentro)
        esp = max(1, int(round(0.0024 * u)))
        cor = (*[int(v) for v in BORDA_CARTAO], 255)
        if cv2 is not None:
            x1, y1 = x0 + sw - 1, y0 + sh - 1
            rr = max(0, r)
            for (a, b) in (((x0 + rr, y0 - 1), (x1 - rr, y0 - 1)), ((x0 - 1, y0 + rr), (x0 - 1, min(H, y1 - rr))),
                           ((x1 + 1, y0 + rr), (x1 + 1, min(H, y1 - rr)))):
                cv2.line(base, a, b, cor, esp, cv2.LINE_AA)
            if y1 < H - 1:
                cv2.line(base, (x0 + rr, y1 + 1), (x1 - rr, y1 + 1), cor, esp, cv2.LINE_AA)
            if rr > 1:
                cv2.ellipse(base, (x0 + rr, y0 + rr), (rr + 1, rr + 1), 0, 180, 270, cor, esp, cv2.LINE_AA)
                cv2.ellipse(base, (x1 - rr, y0 + rr), (rr + 1, rr + 1), 0, 270, 360, cor, esp, cv2.LINE_AA)
                if y1 < H - 1:
                    cv2.ellipse(base, (x0 + rr, y1 - rr), (rr + 1, rr + 1), 0, 90, 180, cor, esp, cv2.LINE_AA)
                    cv2.ellipse(base, (x1 - rr, y1 - rr), (rr + 1, rr + 1), 0, 0, 90, cor, esp, cv2.LINE_AA)
        else:
            im = Image.fromarray(base, "RGBA")
            ImageDraw.Draw(im).rounded_rectangle((x0 - 1, y0 - 1, x0 + sw, y0 + sh), radius=r + 1, outline=cor,
                                                 width=esp)
            base = np.array(im)
    return base


def _fundo_parado(g, geo, sw, sh, x0, y0, r, baixo, rec):
    """Fundo do cartão parado (PIL, em cache): parede + sombra + filete e, com recorte, o cartão já pintado
    de papel (a pessoa é colada por cima com a máscara). Sem recorte, o vídeo é colado por cima."""
    chave = ("e10", "parado", geo["id"], sw, sh, x0, y0, r, rec)
    if chave not in g.cache:
        base = _fundo_cartao(g, sw, sh, x0, y0, r, 1.0 if geo["s"] < 1 else 0.0)
        if rec:
            papel = np.empty((sh, sw, 4), np.uint8)
            papel[:] = (*PAPEL_TINTA, 255)
            reg = base[y0:y0 + sh, x0:x0 + sw]
            fundos = [reg[sy, sx].astype(np.float32) for sy, sx, _ in _blocos_cantos(sw, sh, r, baixo)]
            reg[:] = papel
            for (sy, sx, a), bg in zip(_blocos_cantos(sw, sh, r, baixo), fundos):
                reg[sy, sx] = (papel[sy, sx] * a[..., None] + bg * (1 - a[..., None])).astype(np.uint8)
        g.cache[chave] = Image.fromarray(base, "RGBA")
    return g.cache[chave]


def _colar_atras(img, camada, x, y, ms=None, mx=0, my=0, propria=False):
    """Cola a camada em img na posição (x, y); se houver máscara da pessoa (ms, posicionada em mx, my),
    a camada fica ATRÁS dela (o alfa é cortado onde há pessoa). propria=True: a camada pode ser alterada."""
    x, y = int(round(x)), int(round(y))
    W, H = img.size
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(camada.width, W - x), min(camada.height, H - y)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    if (cx0, cy0, cx1, cy1) != (0, 0, camada.width, camada.height):
        camada = camada.crop((cx0, cy0, cx1, cy1))
        x, y = x + cx0, y + cy0
        propria = True
    if ms is not None:
        mh, mw = ms.shape
        ix0, iy0 = max(x, mx), max(y, my)
        ix1, iy1 = min(x + camada.width, mx + mw), min(y + camada.height, my + mh)
        if ix1 > ix0 and iy1 > iy0:
            pm = Image.fromarray(255 - ms[iy0 - my:iy1 - my, ix0 - mx:ix1 - mx], "L")
            a = camada.getchannel("A")
            caixa = (ix0 - x, iy0 - y, ix1 - x, iy1 - y)
            a.paste(ImageChops.multiply(a.crop(caixa), pm), caixa)
            if not propria:
                camada = camada.copy()
            camada.putalpha(a)
    img.alpha_composite(camada, (x, y))


def _opacidade(camada, k):
    if k >= 0.997:
        return camada
    c2 = camada.copy()
    c2.putalpha(c2.getchannel("A").point(lambda v: int(v * k)))
    return c2


def _por(base, camada, centro, escala=1.0):
    """Cola camada centrada (com escala) dentro de base, sem sair dela."""
    if abs(escala - 1) > 0.002:
        camada = camada.resize((max(1, int(camada.width * escala)), max(1, int(camada.height * escala))),
                               Image.BICUBIC)
    x, y = int(round(centro[0] - camada.width / 2)), int(round(centro[1] - camada.height / 2))
    _colar_atras(base, camada, x, y)


# ------------------------------------------------------------------ onde está a pessoa

def _topo_legenda(g):
    """Topo da faixa da legenda (posição 'baixo' do perfil), em pixels."""
    if g.legendas is None:
        return 0.80 * g.H
    f = g.legendas.f
    linhas = max(1, int(getattr(g.legendas.p, "max_linhas", 1)))
    return 0.80 * g.H - (f.size * 1.18 * linhas + f.size * 0.56)


def _zona_cabeca(g, t0, t1):
    """Faixa horizontal ocupada pela cabeça (com cabelo/boné), em frações da largura do vídeo original."""
    ts = np.arange(max(0.0, t0), max(t0, t1) + 1e-6, 0.2)
    if len(ts) == 0:
        ts = np.array([max(0.0, t0)])
    cx = np.array([g.rosto.em(float(t)) for t in ts]) / np.array([g.W, g.H, g.W, g.H])
    x0, x1 = float(np.percentile(cx[:, 0], 20)), float(np.percentile(cx[:, 2], 80))
    fw = float(np.median(cx[:, 2] - cx[:, 0]))
    return x0 - 0.08 * fw, x1 + 0.08 * fw


def _rosto_janela(g, t0, t1):
    """Topo da cabeça (percentil 12 = a cabeça mais alta) e queixo (percentil 88) durante o evento, em frações."""
    ts = np.arange(max(0.0, t0), max(t0, t1) + 1e-6, 0.2)
    if len(ts) == 0:
        ts = np.array([max(0.0, t0)])
    topos = np.array([g.rosto.topo_cabeca(float(t)) for t in ts]) / g.H
    queixos = np.array([g.rosto.queixo(float(t)) for t in ts]) / g.H
    return float(np.percentile(topos, 12)), float(np.percentile(queixos, 88))


# ------------------------------------------------------------------ geometria do gráfico (uma vez por evento)

def _valores(e, forma):
    vs = _numeros(e.get("valores"))
    if not vs or len(vs) < 2:
        vs = list(VALORES_PADRAO_BARRAS if forma == "barras" else VALORES_PADRAO_LINHA)
    return [max(0.0, v) for v in vs[:7]]


def _rotulos(e, n):
    rots = e.get("rotulos")
    if not isinstance(rots, (list, tuple)) or len(rots) not in (2, n):
        return []
    return [_limpo(r).upper()[:9] for r in rots]


def _geo(g, e):
    chave = ("e10", "geo", round(float(e["inicio"]), 3), round(float(e["fim"]), 3))
    if chave in g.cache:
        return g.cache[chave]
    W, H = g.W, g.H
    u = _u(W, H)
    rec = bool(g.tem_mascara)
    forma = "barras" if str(e.get("forma", "linha")).lower().startswith("barra") else "linha"
    ini, fim = float(e["inicio"]), float(e["fim"])
    topo, queixo = _rosto_janela(g, ini, fim)
    lim_queixo = _topo_legenda(g) / H - 0.02
    alvo = ALVO_REC if rec else ALVO_SEM
    # recuo da câmera: a cabeça desce até 'alvo' e o queixo nunca encosta na legenda
    s_base = (1 - alvo) / max(0.05, 1 - topo)
    s_queixo = (lim_queixo - alvo) / max(0.05, queixo - topo)
    s = max(S_MIN_REC if rec else S_MIN_SEM, min(1.0, s_base, s_queixo))
    if s >= 0.995:
        s, yc = 1.0, 0.0
    else:
        yc = alvo - s * topo
        if 1 - (yc + s) < 0.045:   # sobra pouca parede embaixo: o cartão encosta na base da tela
            yc = 1 - s
        yc = max(0.0, min(1 - s, yc))
    topo_tela = (yc + s * topo) * H

    pad = 0.034 * u
    vals = _valores(e, forma)
    n = len(vals)
    rots = _rotulos(e, n)
    f_rot = d.fonte(int(round(ROT_TAM * u)), 600)
    h_rot = f_rot.size * 1.55 if rots else 0.0
    G0 = TOPO_SEG * H
    if rec:   # a base do gráfico fica ATRÁS da cabeça
        base = topo_tela + (0.085 if forma == "linha" else 0.055) * H
        base = min(base, 0.52 * H)
    else:     # sem recorte: tudo acima da cabeça
        base = topo_tela - 0.022 * H - h_rot - pad * 0.35
    base = max(base, G0 + 0.165 * H)
    # o painel é opaco e cobre a largura do cartão do vídeo: o topo do cartão (que fica atrás dele) nunca
    # aparece como um segundo retângulo dentro ou ao lado do painel
    xc0, xc1 = (W - W * s) / 2, (W + W * s) / 2
    px0 = max(0.04 * W, min(0.065 * W, xc0 - 0.012 * u))
    px1 = min(0.92 * W, max(0.875 * W, xc1 + 0.012 * u))
    py0 = G0
    py1 = base + (h_rot + pad * 0.35 if rots else pad * 0.55)

    selo = _limpo(e.get("selo")).upper()
    selo_img = _selo_img(g, selo) if selo else None
    bw = selo_img[0].width - 2 * selo_img[2] if selo else 0
    bh = int(round(SELO_ALT * u))
    raio_pt = 0.0125 * u
    y_t = py0 + pad * 0.8 + (bh + 0.022 * u if selo else pad * 0.6)
    qx0, qx1 = px0 + pad * 1.5, px1 - pad * 2.3

    # selo: perto do ponto final (linha: acima e à esquerda do ponto; barras: acima da última barra)
    if forma == "barras":
        larg_b = min(0.11 * u, (qx1 - qx0) / max(1, n) * 0.62)
        xs = [qx0 + larg_b / 2 + i * ((qx1 - qx0 - larg_b) / max(1, n - 1)) for i in range(n)]
        sx1 = min(px1 - pad * 0.7, xs[-1] + bw / 2)
    else:
        larg_b = 0.0
        xs = [qx0 + i * (qx1 - qx0) / max(1, n - 1) for i in range(n)]
        sx1 = min(px1 - pad * 0.7, xs[-1] + 0.35 * bh)
    sx0 = sx1 - bw

    # título no canto de cima, à esquerda do selo
    titulo = _limpo(e.get("titulo"))
    tit = None
    tit_x0, tit_y0 = px0 + pad, py0 + pad * 0.75
    tit_base = py0
    if titulo:
        disp = (sx0 - 0.03 * u - tit_x0) if selo else (px1 - pad - tit_x0) * 0.62
        disp = max(disp, 0.28 * u)
        f_t, linhas_t, al_t = d.ajustar_texto(titulo, disp, 0.16 * u, 700, tam_max=int(0.072 * u),
                                              tam_min=int(0.046 * u), max_linhas=2, entrelinha=1.04)
        tit = (f_t, linhas_t, al_t)
        larg_t = max(f_t.getlength(l) for l in linhas_t)
        tit_base = tit_y0 + al_t * len(linhas_t)
        tit_x1 = tit_x0 + larg_t
    else:
        tit_x1 = tit_x0

    # posição dos valores
    vmax, vmin = max(vals), min(vals)
    ys = []
    for x, v in zip(xs, vals):
        if forma == "barras":
            k = max(0.08, v / vmax) if vmax > 0 else 0.08
        else:
            k = 0.10 + 0.90 * ((v - vmin) / (vmax - vmin) if vmax > vmin else 1.0)
        y = base - k * (base - y_t)
        if tit and x - (larg_b / 2) < tit_x1 + 0.03 * u:   # nada encosta no título
            y = max(y, tit_base + 0.035 * u)
        ys.append(min(y, base - 0.02 * u))

    if selo:
        sy1 = ys[-1] - (0.016 * u if forma == "barras" else raio_pt + 0.012 * u)
        sy0 = sy1 - bh
    else:
        sy0 = sy1 = 0
    # tempos: o desenho termina no selo
    d0 = ini + T_ENTRA
    try:
        se = float(e.get("selo_em")) if e.get("selo_em") is not None else None
    except (TypeError, ValueError):
        se = None
    if se is None:
        se = d0 + min(3.0, max(1.3, 0.5 * (fim - ini)))
    d1 = min(max(se, d0 + 0.8), fim - T_SAI - 0.45)
    # rótulos do eixo: embaixo da linha de base; com recorte, nunca atrás da cabeça (sem caber, sai)
    rot_pos = []
    if rots:
        zona = None
        if rec:
            hz0, hz1 = _zona_cabeca(g, ini, fim)
            zona = ((0.5 + (hz0 - 0.5) * s) * W, (0.5 + (hz1 - 0.5) * s) * W)
        lim0, lim1 = px0 + pad * 0.9, px1 - pad * 0.9
        yy = base + f_rot.size * 0.38
        if len(rots) == 2 and n != 2:
            alvos = [(xs[0] - larg_b / 2, "esquerda", rots[0]), (xs[-1] + larg_b / 2, "direita", rots[1])]
        else:
            alvos = [(x, "centro", r) for x, r in zip(xs, rots)]
        for x, al, r in alvos:
            # tenta: no lugar natural → encostado na ponta do painel → sem espaçamento entre letras
            for esp, ponta in ((f_rot.size * 0.12, False), (f_rot.size * 0.12, True), (0.0, True)):
                larg = sum(f_rot.getlength(ch) for ch in r) + esp * max(0, len(r) - 1)
                xx = {"esquerda": x, "centro": x - larg / 2, "direita": x - larg}[al]
                if ponta and al == "esquerda":
                    xx = lim0
                elif ponta and al == "direita":
                    xx = lim1 - larg
                xx = max(lim0, min(lim1 - larg, xx))
                if zona is None or xx + larg < zona[0] - 0.012 * u or xx > zona[1] + 0.012 * u:
                    rot_pos.append((xx, yy, r, esp))
                    break
    m = int(0.065 * u)
    geo = {"rot_pos": rot_pos, "u": u, "rec": rec, "forma": forma, "s": s, "yc": yc, "topo_tela": topo_tela, "base": base,
           "px0": px0, "px1": px1, "py0": py0, "py1": py1, "pad": pad, "xs": xs, "ys": ys, "vals": vals,
           "rots": rots, "f_rot": f_rot, "larg_b": larg_b, "selo": selo, "sx0": sx0, "sy0": sy0, "sx1": sx1, "sy1": sy1,
           "tit": tit, "tit_xy": (tit_x0, tit_y0), "y_t": y_t, "d0": d0, "d1": d1, "ts": d1,
           "bx": int(px0) - m, "by": int(py0) - m, "bw": int(px1 - px0) + 2 * m, "bh": int(py1 - py0) + 2 * m,
           "m": m, "raio_pt": raio_pt, "id": chave[2:]}
    g.cache[chave] = geo
    return geo


# ------------------------------------------------------------------ peças desenhadas (cache)

def _seta(tam, cor):
    """Seta diagonal (↗) desenhada, com pontas redondas."""
    ss = 4
    S = tam * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    e = max(2, int(S * 0.15))
    c = d.cor(cor)
    a, b = (S * 0.2, S * 0.8), (S * 0.8, S * 0.2)
    dr.line([a, b], fill=c, width=e)
    dr.line([(S * 0.36, S * 0.2), b, (S * 0.8, S * 0.64)], fill=c, width=e, joint="curve")
    for p in (a, (S * 0.36, S * 0.2), (S * 0.8, S * 0.64), b):
        dr.ellipse([p[0] - e / 2, p[1] - e / 2, p[0] + e / 2, p[1] + e / 2], fill=c)
    return im.resize((tam, tam), Image.LANCZOS)


def _selo_img(g, texto, largura_de=None):
    """Pílula verde-limão com texto escuro e seta ↗. Devolve (imagem com sombra, (dx, dy), margem)."""
    u = _u(g.W, g.H)
    chave = ("e10", "selo", texto, largura_de)
    if chave not in g.cache:
        f = d.fonte(int(round(SELO_TAM * u)), 800)
        h = int(round(SELO_ALT * u))
        seta = int(round(h * 0.40))
        pad = h * 0.40
        tw = f.getlength(largura_de or texto)
        w = int(pad + tw + h * 0.16 + seta + pad * 0.85)
        pill = d.painel(w, h, raio=h // 2, fundo=LIMA)
        x_seta = int(w - pad * 0.85 - seta)
        ImageDraw.Draw(pill).text((x_seta - h * 0.16, h / 2 + f.size * 0.02), texto, font=f, fill=d.cor(TINTA),
                                  anchor="rm")
        pill.alpha_composite(_seta(seta, TINTA), (x_seta, int((h - seta) / 2)))
        img, (dx, dy) = d.sombra(pill, raio=0.016 * u, opacidade=0.20, desloc=(0, 0.010 * u))
        g.cache[chave] = (img, (dx, dy), -dx)
    return g.cache[chave]


_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _selo_contando(texto, k):
    """Texto do selo com o número contando (0 → valor) para k de 0 a 1. Só conta números simples."""
    mt = _NUM.search(texto)
    if not mt or k >= 1:
        return texto
    bruto = mt.group(0)
    if "." in bruto and len(bruto.split(".")[1]) == 3:   # 1.000 = mil
        v, casas = float(bruto.replace(".", "")), 0
        fmt = lambda x: f"{x:,.0f}".replace(",", ".")
    elif "," in bruto or "." in bruto:
        sep = "," if "," in bruto else "."
        casas = len(bruto.split(sep)[1])
        v = float(bruto.replace(",", "."))
        fmt = lambda x: f"{x:.{casas}f}".replace(".", sep)
    else:
        v = float(bruto)
        fmt = lambda x: f"{x:.0f}"
    return texto[:mt.start()] + fmt(v * k) + texto[mt.end():]


def _camada_painel(g, geo):
    """Painel de papel com grade fina, linha de base, título e rótulos do eixo (desenhado uma vez)."""
    chave = ("e10", "painel", geo["id"])
    if chave in g.cache:
        return g.cache[chave]
    u, bx, by = geo["u"], geo["bx"], geo["by"]
    cam = Image.new("RGBA", (geo["bw"], geo["bh"]), (0, 0, 0, 0))
    x0, y0 = geo["px0"] - bx, geo["py0"] - by
    x1, y1 = geo["px1"] - bx, geo["py1"] - by
    alfa = 1.0   # papel opaco: o topo do cartão do vídeo, que fica atrás do painel, não aparece
    pan = d.painel(x1 - x0, y1 - y0, raio=int(0.012 * u), fundo=(251, 250, 244, int(255 * alfa)),
                   borda=(196, 198, 184, 210), larg_borda=max(1, int(round(0.0022 * u))))
    sombra, (sdx, sdy) = d.sombra(pan, raio=0.02 * u, opacidade=0.10, desloc=(0, 0.008 * u))
    cam.alpha_composite(sombra, (int(x0 + sdx), int(y0 + sdy)))
    # grade
    gl = Image.new("RGBA", cam.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(gl)
    ins = geo["pad"] * 0.55
    gx0, gx1 = x0 + ins, x1 - ins
    gy0, gy1 = y0 + ins, geo["base"] - by
    cor_g = (*GRADE, 74)
    lw = max(1, int(round(0.0019 * u)))
    for i in range(6):
        y = gy0 + (gy1 - gy0) * i / 5
        dr.line([(gx0, y), (gx1, y)], fill=cor_g, width=lw)
    xs_v = [x - bx for x in geo["xs"]] if geo["forma"] == "linha" else \
        [gx0 + (gx1 - gx0) * i / 6 for i in range(7)]
    for x in xs_v:
        dr.line([(x, gy0), (x, gy1)], fill=cor_g, width=lw)
    dr.line([(gx0, gy1), (gx1, gy1)], fill=(89, 107, 91, 150), width=max(2, int(round(0.0032 * u))))
    cam.alpha_composite(gl)
    # título
    if geo["tit"]:
        f_t, linhas_t, al_t = geo["tit"]
        tx, ty = geo["tit_xy"]
        d.escrever(cam, (tx - bx, ty - by), linhas_t, f_t, TINTA, al=al_t)
    # rótulos do eixo (posições já calculadas; com recorte, nenhum fica atrás da cabeça)
    f = geo["f_rot"]
    drt = ImageDraw.Draw(cam)
    for xx, yy, r, esp in geo["rot_pos"]:
        xx -= bx
        for ch in r:
            drt.text((xx, yy - by), ch, font=f, fill=d.cor(EIXO))
            xx += f.getlength(ch) + esp
    g.cache[chave] = cam
    return cam


def _camada_linha(g, geo):
    """Área em degradê + brilho verde-limão + núcleo branco da linha inteira (revelada da esquerda p/ direita)."""
    chave = ("e10", "linha", geo["id"])
    if chave in g.cache:
        return g.cache[chave]
    u, bx, by = geo["u"], geo["bx"], geo["by"]
    w, h = geo["bw"], geo["bh"]
    pts = [(x - bx, y - by) for x, y in zip(geo["xs"], geo["ys"])]
    base_y = geo["base"] - by
    cam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    # área sob a linha (degradê de cima para baixo)
    ss = 2
    am = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(am).polygon([(x * ss, y * ss) for x, y in pts] +
                               [(pts[-1][0] * ss, base_y * ss), (pts[0][0] * ss, base_y * ss)], fill=255)
    am = am.resize((w, h), Image.LANCZOS)
    topo = min(y for _, y in pts)
    grad = np.clip((base_y - np.arange(h, dtype=np.float32)) / max(1.0, base_y - topo), 0, 1) * 0.42
    alfa = (np.asarray(am, np.float32) / 255.0) * grad[:, None]
    area = Image.new("RGBA", (w, h), d.cor(LIMA))
    area.putalpha(Image.fromarray((alfa * 255).astype(np.uint8), "L"))
    cam.alpha_composite(area)
    # brilho
    gl = Image.new("L", (w, h), 0)
    larg_g = max(4, int(round(0.042 * u)))
    dg = ImageDraw.Draw(gl)
    dg.line(pts, fill=255, width=larg_g, joint="curve")
    for x, y in (pts[0], pts[-1]):
        dg.ellipse([x - larg_g / 2, y - larg_g / 2, x + larg_g / 2, y + larg_g / 2], fill=255)
    gl = gl.filter(ImageFilter.GaussianBlur(0.0185 * u))
    brilho = Image.new("RGBA", (w, h), d.cor(LIMA))
    brilho.putalpha(gl.point(lambda v: int(v * 0.95)))
    cam.alpha_composite(brilho)
    # núcleo branco (super-amostrado)
    ss = 3
    nc = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    dn = ImageDraw.Draw(nc)
    larg_n = max(3, int(round(0.0078 * u * ss)))
    p3 = [(x * ss, y * ss) for x, y in pts]
    dn.line(p3, fill=d.cor(NUCLEO), width=larg_n, joint="curve")
    for x, y in (p3[0], p3[-1]):
        dn.ellipse([x - larg_n / 2, y - larg_n / 2, x + larg_n / 2, y + larg_n / 2], fill=d.cor(NUCLEO))
    cam.alpha_composite(nc.resize((w, h), Image.LANCZOS))
    g.cache[chave] = cam
    return cam


def _ponto(g):
    u = _u(g.W, g.H)
    chave = ("e10", "ponto")
    if chave not in g.cache:
        r = 0.0125 * u
        ss = 4
        S = int(math.ceil(r * 2 + 4)) * ss
        im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        c = S / 2
        dr.ellipse([c - r * ss, c - r * ss, c + r * ss, c + r * ss], fill=d.cor(LIMA))
        rc = 0.0048 * u * ss
        dr.ellipse([c - rc, c - rc, c + rc, c + rc], fill=d.cor(CENTRO_PONTO))
        g.cache[chave] = im.resize((S // ss, S // ss), Image.LANCZOS)
    return g.cache[chave]


def _ponta(g):
    """Brilho na ponta da linha enquanto ela é desenhada."""
    u = _u(g.W, g.H)
    chave = ("e10", "ponta")
    if chave not in g.cache:
        R = int(0.05 * u)
        im = Image.new("RGBA", (R * 2, R * 2), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.ellipse([R * 0.45, R * 0.45, R * 1.55, R * 1.55], fill=d.cor(LIMA, 0.9))
        im = im.filter(ImageFilter.GaussianBlur(R * 0.28))
        r = 0.0085 * u
        ImageDraw.Draw(im).ellipse([R - r, R - r, R + r, R + r], fill=d.cor(NUCLEO))
        g.cache[chave] = im
    return g.cache[chave]


def _tracejado(g, altura):
    u = _u(g.W, g.H)
    altura = int(altura)
    chave = ("e10", "trac", altura)
    if chave not in g.cache:
        lw = max(2, int(round(0.0028 * u)))
        im = Image.new("RGBA", (lw, altura), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        tr, vz = 0.0075 * u, 0.011 * u
        y = 0.0
        while y < altura:
            dr.rectangle([0, y, lw - 1, min(altura - 1, y + tr)], fill=d.cor(LIMA))
            y += tr + vz
        g.cache[chave] = im
    return g.cache[chave]


def _barra(g, geo, i):
    """Uma barra (com brilho) na altura final; no quadro ela sobe de trás da linha de base."""
    chave = ("e10", "barra", geo["id"], i)
    if chave in g.cache:
        return g.cache[chave]
    u = geo["u"]
    w = int(round(geo["larg_b"]))
    h = int(round(geo["base"] - geo["ys"][i]))
    m = int(0.05 * u)
    ultima = i == len(geo["xs"]) - 1
    cam = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
    gl = Image.new("L", cam.size, 0)
    ImageDraw.Draw(gl).rounded_rectangle([m, m, m + w, m + h + m], radius=int(0.016 * u), fill=255)
    gl = gl.filter(ImageFilter.GaussianBlur(0.02 * u))
    br = Image.new("RGBA", cam.size, d.cor(LIMA))
    br.putalpha(gl.point(lambda v: int(v * (0.85 if ultima else 0.5))))
    cam.alpha_composite(br)
    corpo = d.painel(w, h + int(0.02 * u), raio=int(0.016 * u),
                     gradiente=(d.cor(LIMA, 1.0), d.cor(LIMA, 0.70 if ultima else 0.55)))
    cam.alpha_composite(corpo, (m, m))
    # brilho fino no topo da barra
    hl = Image.new("RGBA", cam.size, (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle([m + w * 0.18, m + 0.006 * u, m + w * 0.82, m + 0.006 * u +
                                          max(2, 0.005 * u)], radius=int(0.003 * u) + 1, fill=d.cor(NUCLEO, 0.85))
    cam.alpha_composite(hl)
    g.cache[chave] = (cam, m, h)
    return g.cache[chave]


def _faixa_luz(g):
    """Faixa de luz inclinada que atravessa a tela na saída (esconde a volta, como na prévia)."""
    chave = ("e10", "faixa")
    if chave not in g.cache:
        W, H = g.W, g.H
        fw, fh = int(W * 1.7), int(H * 0.13)
        y = np.linspace(-1, 1, fh, dtype=np.float32)
        a = (np.clip(1 - np.abs(y), 0, 1) ** 1.6 * 0.55 * 255).astype(np.uint8)
        im = Image.new("RGBA", (fw, fh), (*FAIXA_LUZ, 255))
        im.putalpha(Image.fromarray(np.repeat(a[:, None], fw, axis=1), "L"))
        g.cache[chave] = im.rotate(13, resample=Image.BICUBIC, expand=True)
    return g.cache[chave]


# ------------------------------------------------------------------ o quadro com gráfico

def _quadro_grafico(c, e):
    g = c.g
    W, H = c.W, c.H
    t = c.t
    ini, fim = float(e["inicio"]), float(e["fim"])
    kk = d.suave(d.mapear(t, ini, ini + T_ENTRA)) * (1 - d.suave(d.mapear(t, fim - T_SAI, fim)))
    if kk <= 0.002:
        return None
    geo = _geo(g, e)
    u = geo["u"]
    rec = geo["rec"] and c.mascara is not None
    s = d.lerp(1.0, geo["s"], kk)
    yc = d.lerp(0.0, geo["yc"], kk)
    sw, sh = max(2, int(round(W * s))), max(2, int(round(H * s)))
    x0, y0 = int(round((W - sw) / 2)), int(round(yc * H))
    y0 = max(0, min(H - sh, y0))
    raio = int(round(RAIO_CARTAO * u * min(1.0, (1 - s) / max(1e-3, 1 - geo["s"])))) if geo["s"] < 1 else 0
    flutua = y0 + sh < H - 1
    parado = kk >= 0.999
    # o vídeo recua (cartão)
    fs4 = None
    if (sw, sh) == (W, H):
        fs_img = c.fonte
    else:
        fs4 = _redim(np.asarray(c.fonte), (sw, sh))
        fs_img = Image.fromarray(fs4, "RGBA")
    ms = None
    if rec:
        ms = np.asarray(c.mascara)
        if ms.shape != (H, W):
            ms = _redim(ms, (W, H))
        ms = np.array(_redim(ms, (sw, sh)))
        _arredondar_mascara(ms, raio, flutua)
    tinta = TINTA_FUNDO * kk if rec else 0.0
    if parado and (rec and tinta >= 0.999 or not rec):
        img = _fundo_parado(g, geo, sw, sh, x0, y0, raio, flutua, rec).copy()
        if not rec:
            chave_m = ("e10", "mcartao", sw, sh, raio, flutua)
            if chave_m not in g.cache:
                g.cache[chave_m] = _mascara_cartao(sw, sh, raio, flutua) if raio >= 2 else None
            img.paste(fs_img, (x0, y0), g.cache[chave_m])
    else:   # em movimento: fundo calculado no quadro; a sala se desfaz no papel aos poucos
        img = Image.fromarray(_fundo_cartao(g, sw, sh, x0, y0, raio, kk if geo["s"] < 1 else 0.0), "RGBA")
        card = fs_img
        if tinta > 0.003:
            if cv2 is not None and fs4 is not None:
                papel = np.empty_like(fs4)
                papel[:] = (*PAPEL_TINTA, 255)
                card = Image.fromarray(cv2.addWeighted(fs4, 1 - min(1.0, tinta), papel, min(1.0, tinta), 0), "RGBA")
            else:
                card = Image.blend(fs_img, Image.new("RGBA", (sw, sh), (*PAPEL_TINTA, 255)), min(1.0, tinta))
        img.paste(card, (x0, y0), _mascara_cartao(sw, sh, raio, flutua) if raio >= 2 else None)
    # o gráfico, numa camada só, ATRÁS da pessoa (se houver recorte)
    k_in = d.saida(d.mapear(t, ini + (0.25 if rec else 0.45), ini + (0.70 if rec else 0.85)))
    # saída: o gráfico some no começo da volta da câmera, antes de o topo do cartão do vídeo subir para a
    # área do painel (senão o cartão aparece através do papel); sem recorte some ainda antes, porque a
    # cabeça sobe para onde ele estava
    if rec:
        k_out = 1 - d.suave(d.mapear(t, fim - T_SAI - 0.32, fim - T_SAI + 0.06))
    else:
        k_out = 1 - d.suave(d.mapear(t, fim - T_SAI - 0.32, fim - T_SAI + 0.04))
    kc = min(k_in, k_out)
    dy = (1 - k_in) * 0.022 * H
    if 0.003 < kc < 0.999:   # painel entrando/saindo: o cartão atrás dele não aparece como um fantasma
        _limpar_atras_do_painel(img, g, geo, min(1.0, 4.0 * kc), dy)
    if rec:   # a pessoa inteira por cima do papel
        img.paste(fs_img, (x0, y0), Image.fromarray(ms, "L"))

    if kc > 0.003:
        cam = _opacidade(_desenhar_grafico(c, e, geo), kc)
        _colar_atras(img, cam, geo["bx"], geo["by"] + dy, ms, x0, y0, propria=True)

    # faixa de luz na saída (com recorte passa atrás da pessoa, nunca sobre o rosto)
    kf = d.mapear(t, fim - T_SAI - 0.38, fim - 0.08)
    if 0 < kf < 1:
        fx = _faixa_luz(g)
        yy = d.lerp(H * 1.08, -H * 0.12, d.suave(kf))
        fx = _opacidade(fx, math.sin(math.pi * kf) * (0.9 if rec else 0.45))
        _colar_atras(img, fx, W / 2 - fx.width / 2, yy - fx.height / 2, ms, x0, y0, propria=True)
    return img


def _limpar_atras_do_painel(img, g, geo, f, dy):
    """Na região do painel, troca (na proporção f) o que está atrás dele pela parede limpa. Assim, enquanto o
    painel entra ou sai com transparência, a borda/sombra do cartão do vídeo não aparece através do papel."""
    W, H = img.size
    x0, x1 = max(0, int(geo["px0"])), min(W, int(math.ceil(geo["px1"])))
    y0, y1 = max(0, int(geo["py0"] + dy)), min(H, int(math.ceil(geo["py1"] + dy)))
    if x1 <= x0 or y1 <= y0 or f <= 0.003:
        return
    caixa = (x0, y0, x1, y1)
    reg = np.asarray(img.crop(caixa))
    par = _parede(g)[y0:y1, x0:x1]
    if cv2 is not None:
        out = cv2.addWeighted(reg, 1 - f, par, f, 0)
    else:
        out = (reg.astype(np.float32) * (1 - f) + par.astype(np.float32) * f).astype(np.uint8)
    img.paste(Image.fromarray(out, "RGBA"), caixa)


def _desenhar_grafico(c, e, geo):
    """Desenha o gráfico no instante c.t numa camada do tamanho do painel (coordenadas locais)."""
    g = c.g
    t = c.t
    u, bx, by = geo["u"], geo["bx"], geo["by"]
    p = d.suave(d.mapear(t, geo["d0"], geo["d1"]))
    xs, ys = geo["xs"], geo["ys"]
    chave_pronto = ("e10", "pronto", geo["id"])
    if p >= 1 and chave_pronto in g.cache:
        cam = g.cache[chave_pronto].copy()
    else:
        cam = _camada_painel(g, geo).copy()
        _desenhar_dados(g, t, geo, cam, p)
        if p >= 1:
            g.cache[chave_pronto] = cam.copy()
    _desenhar_selo(g, t, geo, cam)
    return cam


def _desenhar_dados(g, t, geo, cam, p):
    """Linha (com pontos, tracejado e ponta) ou barras, no progresso p do desenho."""
    u, bx, by = geo["u"], geo["bx"], geo["by"]
    xs, ys = geo["xs"], geo["ys"]
    if geo["forma"] == "linha":
        if p > 0:
            lin = _camada_linha(g, geo)
            xp = xs[0] + p * (xs[-1] - xs[0])
            corte = int(round(xp - bx + (0.006 * u if p < 1 else geo["m"])))
            corte = max(1, min(lin.width, corte))
            cam.alpha_composite(lin, (0, 0), (0, 0, corte, lin.height))
            # pontos que acendem quando a linha chega neles
            pt = _ponto(g)
            for i, (x, y) in enumerate(zip(xs, ys)):
                pi = (x - xs[0]) / max(1e-6, xs[-1] - xs[0])
                if p >= pi - 0.03:   # o ponto "estala" quando a linha chega nele (o último, no fim)
                    kp = 1.0 if p >= 1 else d.mapear(p, pi - 0.03, pi + 0.02)
                    if i == 0:
                        kp = d.mapear(t, geo["d0"], geo["d0"] + 0.15)
                    _por(cam, pt, (x - bx, y - by), escala=0.4 + 0.6 * d.mola(kp, 1.8))
            # traço tracejado que acompanha o desenho
            tr = _tracejado(g, geo["base"] - geo["y_t"] + 0.03 * u)
            _colar_atras(cam, _opacidade(tr, 0.8 * p), xp - bx - tr.width / 2, geo["y_t"] - 0.03 * u - by)
            # brilho na ponta
            if p < 1:
                yp = float(np.interp(xp, xs, ys))
                _por(cam, _opacidade(_ponta(g), 1 - d.mapear(p, 0.92, 1.0)), (xp - bx, yp - by))
    else:
        n = len(xs)
        for i in range(n):
            a = 0.62 * i / max(1, n - 1)
            kb = d.saida(d.mapear(p, a, a + 0.38))
            if kb <= 0.001:
                continue
            spr, m, h = _barra(g, geo, i)
            hv = h * kb
            corte = int(round(m + hv))
            if corte <= 1:
                continue
            xb, yb = int(round(xs[i] - bx - spr.width / 2)), int(round(geo["base"] - by - hv - m))
            cam.alpha_composite(spr, (xb, max(0, yb)), (0, max(0, -yb), spr.width, corte))


def _desenhar_selo(g, t, geo, cam):
    """Selo no ponto mais alto, no instante em que o número é dito (entra com mola e 'respira')."""
    bx, by = geo["bx"], geo["by"]
    if geo["selo"]:
        ks = d.mapear(t, geo["ts"] - 0.06, geo["ts"] + 0.34)
        if ks > 0:
            conta = 1 - (1 - d.mapear(t, geo["ts"] - 0.06, geo["ts"] + 0.45)) ** 2.6
            txt = _selo_contando(geo["selo"], conta)
            spr, _, _ = _selo_img(g, txt, geo["selo"] if txt != geo["selo"] else None)
            respira = 1 + 0.022 * math.sin(2 * math.pi * max(0.0, t - geo["ts"] - 0.4) / 1.7)
            esc = (0.55 + 0.45 * d.mola(ks, 1.5)) * respira
            cx = (geo["sx0"] + geo["sx1"]) / 2 - bx
            cy = (geo["sy0"] + geo["sy1"]) / 2 - by
            # a sombra tem a mesma margem dos 4 lados: a pílula fica no centro da imagem
            _por(cam, _opacidade(spr, d.saida(min(1.0, ks * 1.6))), (cx, cy), escala=esc)


# ------------------------------------------------------------------ cartão de número (selo de número)

def _fmt(v, casas):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _num_partes(e):
    try:
        v = float(e.get("valor") or 0)
    except (TypeError, ValueError):
        v = 0.0
    bruto = str(e.get("valor"))
    casas = 0
    if "." in bruto and not bruto.endswith(".0"):
        casas = min(2, len(bruto.split(".")[1]))
    return v, casas, str(e.get("prefixo") or ""), str(e.get("sufixo") or "")


def _cartao_numero(g, e):
    """Cartão de papel: ícone verde-limão com barras + número grande + rótulo. Parte fixa em cache."""
    chave = ("e10", "num", round(float(e["inicio"]), 3))
    if chave in g.cache:
        return g.cache[chave]
    u = _u(g.W, g.H)
    v, casas, pre, suf = _num_partes(e)
    final = pre + _fmt(v, casas) + suf
    rot = _limpo(e.get("rotulo")).upper()
    pad = 0.04 * u
    tile = int(round(0.165 * u))
    disp = 0.80 * u - tile - pad * 3
    f_n, _, _ = d.ajustar_texto(final, disp, 0.14 * u, 800, tam_max=int(0.13 * u), tam_min=int(0.075 * u),
                                max_linhas=1, entrelinha=1.0)
    f_r = d.fonte(int(round(0.042 * u)), 700)
    esp = f_r.size * 0.10
    larg_r = sum(f_r.getlength(ch) for ch in rot) + esp * max(0, len(rot) - 1)
    while larg_r > disp and f_r.size > int(LEGIVEL * u) + 1:
        f_r = d.fonte(f_r.size - 2, 700)
        esp = f_r.size * 0.10
        larg_r = sum(f_r.getlength(ch) for ch in rot) + esp * max(0, len(rot) - 1)
    larg_n = f_n.getlength(final)
    texto_w = max(larg_n, larg_r)
    cw = int(pad + tile + pad * 0.8 + texto_w + pad * 1.1)
    asc, desc = f_n.getmetrics()
    h_num = int(f_n.size * 0.80)
    ch = int(max(tile + pad * 1.6, pad * 0.8 + h_num + f_r.size * 1.55 + pad * 0.9))
    cart = d.painel(cw, ch, raio=int(0.034 * u), fundo=CARTAO_NUM, borda="#FFFFFFB4", larg_borda=2)
    ty = int((ch - tile) / 2)
    cart.alpha_composite(d.painel(tile, tile, raio=int(0.03 * u), fundo=LIMA), (int(pad), ty))
    x_txt = pad + tile + pad * 0.8
    y_num_base = (ch - (h_num + f_r.size * 1.55)) / 2 + h_num
    # rótulo
    dr = ImageDraw.Draw(cart)
    xx = x_txt + f_n.size * 0.04
    for chh in rot:
        dr.text((xx, y_num_base + f_r.size * 0.42), chh, font=f_r, fill=d.cor(EIXO))
        xx += f_r.getlength(chh) + esp
    sombra, (sdx, sdy) = d.sombra(cart, raio=0.03 * u, opacidade=0.24, desloc=(0, 0.014 * u))
    info = {"img": sombra, "off": (-sdx, -sdy), "f_n": f_n, "x_txt": x_txt, "y_base": y_num_base,
            "tile": (int(pad), ty, tile), "w": cw, "h": ch, "v": v, "casas": casas, "pre": pre, "suf": suf}
    g.cache[chave] = info
    return info


def _pos_numero(g, e, info):
    chave = ("e10", "numpos", round(float(e["inicio"]), 3))
    if chave in g.cache:
        return g.cache[chave]
    W, H = g.W, g.H
    topo, queixo = _rosto_janela(g, float(e["inicio"]), float(e["fim"]))
    leg = _topo_legenda(g) / H
    h = info["h"] / H
    cima_ini, cima_fim = TOPO_SEG + 0.005, topo - 0.02
    baixo_ini, baixo_fim = queixo + 0.025, leg - 0.022
    esp_cima, esp_baixo = cima_fim - cima_ini, baixo_fim - baixo_ini
    pos = e.get("posicao", "auto")
    if pos not in ("baixo", "topo"):
        pos = "baixo" if esp_baixo >= h or esp_baixo >= esp_cima else "topo"
    ini_r, fim_r = (baixo_ini, baixo_fim) if pos == "baixo" else (cima_ini, cima_fim)
    esp = fim_r - ini_r
    esc = 1.0 if esp >= h else max(0.82, esp / h)
    hh = h * esc
    # cabe: centraliza no espaço livre; não cabe: encosta no lado longe do rosto (nunca sobe no rosto)
    if esp >= hh:
        cy = (ini_r + fim_r) / 2
    else:
        cy = ini_r + hh / 2 if pos == "baixo" else ini_r + hh / 2
    cx = 0.47 * W
    meia = info["w"] * esc / 2
    cx = max(0.06 * W + meia, min(0.88 * W - meia, cx))
    res = (cx, cy * H, esc)
    g.cache[chave] = res
    return res


def _desenhar_numero(c, img, e):
    t = c.t
    ini, fim = float(e["inicio"]), float(e["fim"])
    k_in = d.mapear(t, ini, ini + 0.36)
    k_out = d.suave(d.mapear(t, fim - 0.28, fim))
    op = d.saida(k_in) * (1 - k_out)
    if op <= 0.003:
        return
    g = c.g
    u = _u(c.W, c.H)
    info = _cartao_numero(g, e)
    cx, cy, esc = _pos_numero(g, e, info)
    cam = info["img"].copy()
    ox, oy = info["off"]
    # número contando
    contar = e.get("contar", True) is not False
    kc = 1 - (1 - d.mapear(t, ini + 0.10, ini + 0.72)) ** 2.6 if contar else 1.0
    v = info["v"] * kc
    txt = info["pre"] + _fmt(v if kc < 1 else info["v"], info["casas"]) + info["suf"]
    ImageDraw.Draw(cam).text((ox + info["x_txt"], oy + info["y_base"]), txt, font=info["f_n"],
                             fill=d.cor(TINTA), anchor="ls")
    # ícone: três barras escuras subindo dentro do quadrado verde-limão + seta
    tx, ty, tl = info["tile"]
    larg = tl * 0.17
    alturas = (0.34, 0.56, 0.80)
    for i, a in enumerate(alturas):
        kb = d.saida(d.mapear(t, ini + 0.12 + i * 0.12, ini + 0.50 + i * 0.12))
        hb = max(1, int(tl * 0.70 * a * kb))
        if hb > 2:
            barra = d.painel(int(larg), hb, raio=max(1, int(larg * 0.28)), fundo=TINTA)
            bx_ = ox + tx + tl * 0.19 + i * (larg + tl * 0.075)
            by_ = oy + ty + tl * 0.84 - hb
            cam.alpha_composite(barra, (int(bx_), int(by_)))
    ks = d.mapear(t, ini + 0.55, ini + 0.85)
    if ks > 0:
        st = _seta(int(tl * 0.30), TINTA)
        st = st.resize((max(1, int(st.width * (0.5 + 0.5 * d.mola(ks, 1.6)))),) * 2, Image.BICUBIC)
        cam.alpha_composite(st, (int(ox + tx + tl * 0.86 - st.width), int(oy + ty + tl * 0.10)))
    sobe = (1 - d.saida(k_in)) * 0.028 * c.H + k_out * 0.012 * c.H
    escala = esc * (0.93 + 0.07 * d.mola(k_in, 1.2))
    # a sombra tem a mesma margem dos 4 lados: o cartão fica no centro da imagem
    d.colar(img, cam, (cx, cy + sobe), escala=escala, opacidade=op)


# ------------------------------------------------------------------ quadro

def quadro(c):
    evs = [e for e in c.eventos if e.get("tipo") in ("grafico", "numero")]
    if not evs:
        return c.fonte
    img = None
    gr = next((e for e in evs if e.get("tipo") == "grafico"), None)
    if gr is not None:
        img = _quadro_grafico(c, gr)
    if img is None:
        img = c.fonte.copy()
    for e in evs:
        if e.get("tipo") == "numero":
            _desenhar_numero(c, img, e)
    return img
