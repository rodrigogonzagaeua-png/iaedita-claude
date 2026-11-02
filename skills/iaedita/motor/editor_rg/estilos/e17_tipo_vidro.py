"""17 · Tipo vidro — palavras gigantes de vidro (o vídeo de trás aparece refratado dentro das letras,
com borda cromada, reflexo que atravessa, profundidade em camadas e leve giro 3D).
A palavra fica ATRÁS da pessoa (a pessoa recortada passa na frente) quando sobra fundo visível,
ou NA FRENTE, fora do rosto (acima da cabeça ou entre o queixo e a legenda).

Sem recorte (c.pessoa None) o estilo continua igual, só que sempre na frente e fora do rosto.

Geometria: cada palavra é desenhada uma vez "de frente" numa camada plana (cache), e a cada quadro
é girada em 3D (rotação no eixo Y + Z com perspectiva) e colada. A refração amostra o próprio quadro
atrás de cada pixel da letra, deslocado por um campo de lente (chanfro + ondulação) — por isso o
vidro mostra o vídeo de verdade, em movimento."""
from __future__ import annotations

import hashlib
import inspect
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import desenho as d

INFO = {
    "id": "17-tipo-vidro",
    "nome": "Tipo vidro",
    "precisa_recorte": True,
    "antes": 0.15,
    "depois": 0.05,
    # perfil da ficha: Inter 800, caixa verde-escura translúcida, palavra falada em verde-claro.
    # Fica embaixo (dentro da zona segura) para sobrar espaço para a palavra de vidro.
    "legenda": {"peso": 800, "tamanho": 0.062, "cor": "#F4F7F8", "destaque": "#E0F4A4", "caixa": "#23332AD9",
                "max_caracteres": 20, "max_linhas": 1, "posicao": "baixo", "animacao": "subir"},
    "eventos": {
        "vidro": "inicio, fim (1,2-4 s): palavra gigante de vidro. texto (1 palavra forte da fala, até 12 letras; "
                 "no máximo 2 palavras curtas), camada ('auto' padrão | 'atras' = atrás da pessoa, a cabeça passa "
                 "na frente das letras | 'frente' = na frente, fora do rosto), posicao (só na frente: 'auto' padrão | "
                 "'topo' = acima da cabeça | 'baixo' = entre o queixo e a legenda), apoio (opcional: frase curta de "
                 "2-5 palavras em letra branca menor, sem repetir a palavra de vidro; a palavra diminui para a frase "
                 "caber e, se mesmo assim não couber, o terminal mostra um AVISO), som",
        "brilho": "inicio, fim (0,3-0,8 s), DENTRO de um 'vidro' (começa ≥0,35 s depois do início dele e ≥0,25 s "
                  "antes do fim): reflexo forte que atravessa as letras e acende a borda, numa palavra de peso "
                  "dita enquanto a palavra está na tela, som",
    },
}

# ------------------------------------------------------------------ paleta (prévia aprovada / Scene17)
CROMO = ((0.0, (255, 255, 255)), (0.18, (220, 229, 220)), (0.40, (86, 100, 93)),
         (0.57, (255, 255, 255)), (0.78, (105, 124, 114)), (1.0, (239, 246, 236)))
FACE = ((0.0, (255, 255, 255), 0.30), (0.45, (178, 204, 185), 0.05), (0.72, (255, 255, 255), 0.24),
        (1.0, (216, 232, 219), 0.07))
PROF_ESCURA = (71, 85, 75)       # linhas de profundidade sobre fundo claro
PROF_CLARA = (214, 226, 218)     # linhas de profundidade sobre fundo escuro
CREME = (255, 253, 241)
TINTA_VIDRO = np.array([232, 241, 234], np.float32)
FOSCO = 0.0100                   # desfoque do vídeo dentro da letra (W): separa a letra do fundo agitado
TINTA, LUZ = 0.20, 18            # quanto de tinta verde-clara e de luz entra na face da letra
SOMBRA_COR = (14, 22, 18)
APOIO_COR = "#FFFDF2"

# ------------------------------------------------------------------ geometria (frações de W/H)
ROT_Y, AMP_Y = -10.0, 4.0        # graus: lado direito mais perto, balanço lento
ROT_Z, AMP_Z = -1.8, 0.6
FOCO = 1.39                      # perspective(1500px) num quadro de 1080
X0, X1 = 0.06, 0.87              # faixa horizontal da palavra (coluna da direita livre)
TOPO, BASE = 0.118, 0.80         # zona segura vertical
FOLGA_ROSTO = 0.008              # além da folga que o queixo estimado já tem (H)
FOLGA_LEG = 0.014                # distância mínima da legenda (H)
TAM_MAX = 0.40                   # tamanho máximo da fonte (W) — palavras muito curtas
TAM_BOM = 0.125                  # abaixo disso a palavra já não é "gigante"
TAM_MIN = 0.085                  # mínimo absoluto (letra maiúscula ≈ 6% da largura)
OCULTO_MAX = 0.22                # atrás da pessoa: no máximo 22% das letras escondidas
OCULTO_TOPO_MAX = 0.06           # ... e a metade de cima das letras quase toda visível
OCULTO_LETRA_MAX = 0.25          # ... e nenhuma letra com mais de 1/4 escondido (B não pode virar P)
OCULTO_REDONDA_MAX = 0.48        # letras que se leem só pela metade de cima (O, I, T, M, N, H...)
REDONDAS = set("OÓÔÕ0ITÍHMN")
APOIO_TAM = 0.05                 # fonte da frase de apoio (W)
APOIO_TAM_MIN = 0.042            # ... e o menor tamanho aceito quando falta espaço (plano fechado)
PALAVRA_MIN_REL = 0.6            # com apoio, a palavra pode encolher até 60% (sem passar de TAM_BOM)
CONTRASTE_ALTO = 0.18            # desvio da luminância atrás da letra a partir do qual o vidro fica mais fosco
ENTRA, SAI = 0.62, 0.40          # duração da entrada / saída (s)


# ================================================================== utilidades

def _passos(t0, t1, passo=0.2):
    n = max(2, int(math.ceil((t1 - t0) / passo)) + 1)
    return [t0 + (t1 - t0) * k / (n - 1) for k in range(n)]


def _texto(e):
    t = " ".join(str(e.get("texto", "")).split()).upper()
    return t.strip(".,;:!?…\"'“”")


def _normal(s):
    """Minúsculas, sem acento e sem pontuação (para comparar palavras)."""
    import unicodedata
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return " ".join("".join(ch if ch.isalnum() else " " for ch in s).split())


def _camada_pedida(e):
    v = str(e.get("camada", "auto")).strip().lower()
    return {"atrás": "atras", "atras": "atras", "frente": "frente", "na frente": "frente"}.get(v, "auto")


def _semente(*partes):
    return int(hashlib.md5("|".join(str(p) for p in partes).encode("utf-8")).hexdigest()[:8], 16)


def _grad(stops, p):
    """Interpola paradas [(pos, (r,g,b)[, a])] num array p (0-1). Devolve (rgb, a|None)."""
    pos = np.array([s[0] for s in stops], np.float32)
    rgb = np.stack([np.interp(p, pos, [s[1][k] for s in stops]) for k in range(3)], axis=-1)
    a = np.interp(p, pos, [s[2] for s in stops]) if len(stops[0]) > 2 else None
    return rgb.astype(np.float32), (a.astype(np.float32) if a is not None else None)


def _desfocar_L(img, sigma):
    return img if sigma < 0.3 else img.filter(ImageFilter.GaussianBlur(sigma))


def _erodir(A, r):
    """Erosão arredondada e suave de uma máscara L (borra e corta alto)."""
    if r < 0.5:
        return A
    b = A.filter(ImageFilter.GaussianBlur(max(0.6, r)))
    return b.point(lambda v: 0 if v < 184 else 255 if v > 244 else int((v - 184) * 255 / 60))


def _dilatar(A, r):
    if r < 0.5:
        return A
    b = A.filter(ImageFilter.GaussianBlur(max(0.6, r)))
    return b.point(lambda v: 0 if v < 11 else 255 if v > 71 else int((v - 11) * 255 / 60))


def _f(img):
    return np.asarray(img, np.float32) / 255.0


def _deslocar(arr, dx, dy):
    """Desloca um array 2D (sem dar a volta)."""
    out = np.zeros_like(arr)
    dx, dy = int(round(dx)), int(round(dy))
    h, w = arr.shape[:2]
    xs0, xs1 = max(0, -dx), min(w, w - dx)
    ys0, ys1 = max(0, -dy), min(h, h - dy)
    if xs1 > xs0 and ys1 > ys0:
        out[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx] = arr[ys0:ys1, xs0:xs1]
    return out


def _sobre(rgb, a, src_rgb, src_a):
    """Operador 'sobre' em float (rgb 0-255, a 0-1). Altera rgb/a no lugar."""
    sa = src_a[..., None]
    na = src_a + a * (1 - src_a)
    rgb_num = src_rgb * sa + rgb * (a * (1 - src_a))[..., None]
    with np.errstate(invalid="ignore", divide="ignore"):
        rgb[:] = np.where(na[..., None] > 1e-5, rgb_num / np.maximum(na[..., None], 1e-5), 0)
    a[:] = na


def _rgba(rgb, a):
    out = np.dstack([np.clip(rgb, 0, 255), np.clip(a * 255, 0, 255)]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


# ================================================================== letra plana (cache)

def _medidas(txt, tam):
    """Posições de cada letra (com espaçamento extra) e largura total, na fonte Inter 800."""
    f = d.fonte(int(tam), 800)
    trk = (0.055 if len(txt.replace(" ", "")) <= 4 else 0.03) * tam
    xs = [f.getlength(txt[:i]) + i * trk for i in range(len(txt))]
    larg = f.getlength(txt) + (len(txt) - 1) * trk
    return f, xs, larg


def _glifo(txt, tam):
    """Máscara L das letras recortada com folgas para sombra/profundidade.
    Devolve (A, caixa_do_glifo (x0,y0,x1,y1) dentro da camada, u, faixas x (x0,x1) de cada letra na camada)."""
    u = tam / 300.0
    f, xs, larg = _medidas(txt, tam)
    pad = int(tam * 0.5)
    cv = Image.new("L", (int(larg + 2 * pad), int(tam * 1.6 + 2 * pad)), 0)
    dr = ImageDraw.Draw(cv)
    for ch, x in zip(txt, xs):
        dr.text((pad + x, pad), ch, font=f, fill=255)
    bb = cv.getbbox() or (0, 0, cv.width, cv.height)
    # folgas: esquerda/topo para o realce; direita/baixo para profundidade e sombra
    pl, pt, pr, pb = int(16 * u) + 4, int(16 * u) + 4, int(44 * u) + 6, int(52 * u) + 6
    pr += (bb[2] - bb[0] + pl + pr) % 2      # largura e altura pares (textura em meia resolução)
    pb += (bb[3] - bb[1] + pt + pb) % 2
    A = cv.crop((bb[0] - pl, bb[1] - pt, bb[2] + pr, bb[3] + pb))
    caixa = (pl, pt, pl + bb[2] - bb[0], pt + bb[3] - bb[1])
    desl = bb[0] - pl
    letras = []
    for ch, x in zip(txt, xs):
        if ch.strip():
            cb = f.getbbox(ch)
            letras.append((pad + x + cb[0] - desl, pad + x + cb[2] - desl,
                           OCULTO_REDONDA_MAX if ch in REDONDAS else OCULTO_LETRA_MAX))
    return A, caixa, u, letras


def _caixa_conteudo(caixa, u):
    """Caixa visível (letra + aro + profundidade, sem a sombra suave)."""
    x0, y0, x1, y1 = caixa
    return (x0 - 7 * u, y0 - 8 * u, x1 + 26 * u, y1 + 20 * u)


# ================================================================== 3D

def _cantos(pts, ax, ay, cx, cy, th, ph, esc, foco):
    ct, st = math.cos(math.radians(th)), math.sin(math.radians(th))
    cp, sp = math.cos(math.radians(ph)), math.sin(math.radians(ph))
    out = []
    for (uu, vv) in pts:
        x, y = (uu - ax) * esc, (vv - ay) * esc
        z = x * st
        s = foco / max(1.0, foco + z)
        X, Y = x * ct * s, y * s
        out.append((cx + X * cp - Y * sp, cy + X * sp + Y * cp))
    return out


def _extensao(caixa_c, ax, ay, W):
    """Extensão (esq, topo, dir, base) relativa à âncora, no pior caso do balanço."""
    x0, y0, x1, y1 = caixa_c
    pts = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    xs, ys = [], []
    for th in (ROT_Y - AMP_Y, ROT_Y + AMP_Y):
        for ph in (ROT_Z - AMP_Z, ROT_Z + AMP_Z):
            for p in _cantos(pts, ax, ay, 0, 0, th, ph, 1.03, FOCO * W):
                xs.append(p[0])
                ys.append(p[1])
    return min(xs), min(ys), max(xs), max(ys)


# ================================================================== máscara: varredura leve (preparar)

def _avisar(g, msg):
    """Guarda um aviso para o agente e mostra no terminal (stderr, uma vez, só no processo principal:
    o JSON do 'previa' continua limpo no stdout)."""
    avisos = g.cache.setdefault("e17avisos", [])
    if msg in avisos:
        return
    avisos.append(msg)
    if msg in _AVISOS_MOSTRADOS:
        return
    _AVISOS_MOSTRADOS.add(msg)
    try:
        import multiprocessing
        if multiprocessing.current_process().name == "MainProcess":
            print(f"AVISO (17-tipo-vidro): {msg}", file=sys.stderr, flush=True)
    except Exception:  # noqa: BLE001
        pass


_AVISOS_MOSTRADOS: set = set()   # só para não repetir a mesma linha no terminal (não afeta o desenho)


_EXT_VIDEO = (".mkv", ".mp4", ".mov", ".webm")


def _arquivo_mascara():
    """Caminho do arquivo de máscara que o motor está usando (o Global não o guarda — ver bugs_no_motor).
    Procura na pilha de chamadas: primeiro uma variável 'mascara'; depois qualquer caminho de vídeo
    cujo nome comece por 'mascara' (sobrevive a um parâmetro renomeado)."""
    fr = inspect.currentframe()
    achados = []
    try:
        while fr is not None:
            for nome, m in fr.f_locals.items():
                if isinstance(m, (str, Path)) and str(m).lower().endswith(_EXT_VIDEO):
                    if nome == "mascara" or Path(str(m)).name.lower().startswith("mascara"):
                        achados.append((0 if nome == "mascara" else 1, str(m)))
            fr = fr.f_back
    finally:
        del fr
    for _, m in sorted(achados, key=lambda x: x[0]):
        if Path(m).exists():
            return m
    return None


def _varrer_mascara(g):
    """Silhueta da pessoa em baixa resolução, 5 vezes por segundo (só para decidir onde a palavra cabe)."""
    if not g.tem_mascara:
        return None
    arq = g.cache.get("e17varr_fonte") or _arquivo_mascara()
    g.cache["e17varr_fonte"] = arq
    if not arq:
        _avisar(g, "há máscara da pessoa, mas o estilo não achou o arquivo dela: todas as palavras ficarão "
                   "NA FRENTE (fora do rosto), sem passar atrás da cabeça. O vídeo continua correto.")
        return None
    try:
        from ..midia import LeitorDeQuadros
        mw = 90
        mh = int(round(mw * g.H / g.W))
        quadros = [q > 110 for q in LeitorDeQuadros(arq, mw, mh, 5.0, cinza=True)]
    except Exception as erro:  # noqa: BLE001
        _avisar(g, f"não deu para ler a máscara da pessoa ({erro}): as palavras ficarão NA FRENTE, fora do rosto.")
        return None
    if not quadros:
        _avisar(g, "a máscara da pessoa está vazia: as palavras ficarão NA FRENTE, fora do rosto.")
        return None
    return {"fps": 5.0, "q": quadros, "mw": mw, "mh": mh}


def _pegada(varr, t0, t1):
    """União da silhueta no intervalo (onde a pessoa esteve em algum momento)."""
    if varr is None:
        return None
    i0 = max(0, int(math.floor(t0 * varr["fps"])))
    i1 = min(len(varr["q"]) - 1, int(math.ceil(t1 * varr["fps"])))
    if i1 < i0:
        return None
    u = np.zeros_like(varr["q"][0])
    for q in varr["q"][i0:i1 + 1]:
        u |= q
    # um pixel a mais em volta (cabelo, mãos rápidas)
    u2 = u.copy()
    u2[1:, :] |= u[:-1, :]
    u2[:-1, :] |= u[1:, :]
    u2[:, 1:] |= u[:, :-1]
    u2[:, :-1] |= u[:, 1:]
    return u2


# ================================================================== onde a palavra cabe (preparar)

def _cena(g, e, varr):
    """Medidas da cena durante o evento: rosto, queixo, topo da cabeça, legenda, silhueta."""
    W, H = g.W, g.H
    t0, t1 = max(0.0, e["inicio"] - 0.15), min(g.duracao, e["fim"] + 0.05)
    ts = _passos(t0, t1)
    caixas = [g.rosto.em(t) for t in ts]
    fx0, fy0 = min(c[0] for c in caixas), min(c[1] for c in caixas)
    fx1, fy1 = max(c[2] for c in caixas), max(c[3] for c in caixas)
    queixo = max(g.rosto.queixo(t) for t in ts)
    cabeca = min(g.rosto.topo_cabeca(t) for t in ts)
    peg = _pegada(varr, t0, t1)
    if peg is not None:  # topo real da cabeça pela silhueta (o modelo do rosto é conservador)
        mh, mw = peg.shape
        c0, c1 = int(fx0 / W * mw), max(int(fx0 / W * mw) + 1, int(math.ceil(fx1 / W * mw)))
        cob = peg[:, c0:c1].mean(axis=1)
        linhas = np.nonzero(cob > 0.3)[0]
        if len(linhas):
            cabeca = min(fy0, max(cabeca, linhas[0] / mh * H - 0.004 * H))
    leg = None
    if g.legendas is not None:
        faixas = [g.legendas.ocupacao(t) for t in ts]
        faixas = [f for f in faixas if f]
        if faixas:
            leg = (min(f[0] for f in faixas), max(f[1] for f in faixas))
    return {"rosto": (fx0, fy0, fx1, fy1), "queixo": queixo, "cabeca": cabeca, "leg": leg, "peg": peg}


def _faixas(g, cena):
    """Faixas verticais livres para a palavra NA FRENTE: acima/sobre o cabelo e entre queixo e legenda."""
    H = g.H
    base = BASE * H
    if cena["leg"] and cena["leg"][1] > 0.45 * H:
        base = min(base, cena["leg"][0] - FOLGA_LEG * H)
    topo_ini = TOPO * H
    if cena["leg"] and cena["leg"][1] <= 0.45 * H:  # legenda pedida no alto
        topo_ini = max(topo_ini, cena["leg"][1] + FOLGA_LEG * H)
    fy0 = cena["rosto"][1]
    return {"topo": (topo_ini, fy0 - 0.012 * H),
            "baixo": (cena["queixo"] + FOLGA_ROSTO * H, base)}


def _tam_que_cabe(txt, W, faixa_h, ref, x_esp=(X0, X1)):
    """Maior fonte que cabe na largura útil e na altura da faixa (medida por proporção)."""
    ex = ref["ext"]
    largura = (x_esp[1] - x_esp[0]) * W
    k_w = largura / max(1.0, ex[2] - ex[0])
    k_h = faixa_h / max(1.0, ex[3] - ex[1]) if faixa_h > 0 else 0.0
    return min(ref["tam"] * min(k_w, k_h), TAM_MAX * W)


def _referencia(txt, W):
    tam = 0.2 * W
    A, caixa, u, letras = _glifo(txt, tam)
    ax, ay = (caixa[0] + caixa[2]) / 2, (caixa[1] + caixa[3]) / 2
    ext = _extensao(_caixa_conteudo(caixa, u), ax, ay, W)
    return {"tam": tam, "A": A, "caixa": caixa, "ax": ax, "ay": ay, "ext": ext, "letras": letras}


def _oculto(ref, k, cx, cy, peg, W, H):
    """Fração das letras escondida pela pessoa numa posição candidata: (total, metade de cima, pior letra)."""
    mh, mw = peg.shape
    A = ref["A"]
    gw = max(2, int(round(A.width * k * mw / W)))
    gh = max(2, int(round(A.height * k * mh / H)))
    a = np.asarray(A.resize((gw, gh), Image.BILINEAR), np.float32) / 255.0
    ox = int(round((cx - ref["ax"] * k) / W * mw))
    oy = int(round((cy - ref["ay"] * k) / H * mh))
    grade = np.zeros((mh, mw), np.float32)
    x0, y0 = max(0, ox), max(0, oy)
    x1, y1 = min(mw, ox + gw), min(mh, oy + gh)
    if x1 <= x0 or y1 <= y0:
        return 1.0, 1.0, 1.0
    grade[y0:y1, x0:x1] = a[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    tot = grade.sum()
    if tot <= 0:
        return 1.0, 1.0, 1.0
    esc = (grade * peg).sum() / tot
    # metade de cima do glifo
    cy0 = int(round((cy - (ref["ay"] - ref["caixa"][1]) * k) / H * mh))
    cy1 = int(round((cy - (ref["ay"] - (ref["caixa"][1] + ref["caixa"][3]) / 2) * k) / H * mh))
    cima = grade[max(0, cy0):max(0, cy1)]
    pc = peg[max(0, cy0):max(0, cy1)]
    t_cima = cima.sum()
    esc_cima = (cima * pc).sum() / t_cima if t_cima > 0 else 1.0
    # cada letra: esconder a metade de baixo de um B vira "P" — nenhuma letra pode sumir demais
    pior = 0.0
    for lx0, lx1, lim in ref["letras"]:
        c0 = max(0, int(math.floor(ox + lx0 * k * mw / W)))
        c1 = min(mw, int(math.ceil(ox + lx1 * k * mw / W)))
        if c1 <= c0:
            return float(esc), float(esc_cima), 1.0
        gl = grade[:, c0:c1]
        tl = gl.sum()
        if tl > 0:
            pior = max(pior, float((gl * peg[:, c0:c1]).sum() / tl) / lim)
    return float(esc), float(esc_cima), pior


def _centro_x(ref, k, W):
    ex = ref["ext"]
    return (X0 + X1) / 2 * W - (ex[0] + ex[2]) / 2 * k


def _centro_y_na_faixa(ref, k, faixa):
    ex = ref["ext"]
    return (faixa[0] + faixa[1]) / 2 - (ex[1] + ex[3]) / 2 * k


def _apoio_img(g, txt, tam=APOIO_TAM):
    chave = ("e17apoio", txt, round(tam, 4))
    if chave not in g.cache:
        W = g.W
        f, linhas, al = d.ajustar_texto(txt, W * (X1 - X0), W * tam * 1.3, 700,
                                        tam_max=int(W * tam), tam_min=int(W * APOIO_TAM_MIN), max_linhas=1)
        larg = f.getlength(linhas[0])
        cam = Image.new("RGBA", (int(larg + f.size * 1.4), int(f.size * 2.0)), (0, 0, 0, 0))
        # sombra suave mais forte + contorno fino escuro: a frase continua legível sobre fundo agitado
        # (malha, estante, texto gravado no vídeo), sem virar caixa
        d.escrever(cam, (cam.width / 2, f.size * 0.35), linhas[:1], f, APOIO_COR, alinhar="centro", sombra=0.95,
                   contorno=max(1, round(f.size * 0.05)), cor_contorno="#141C17")
        g.cache[chave] = cam
    return g.cache[chave]


def _layout(g, e, varr):
    """Decide camada, tamanho e lugar da palavra (estável durante todo o evento)."""
    W, H = g.W, g.H
    txt = _texto(e) or " "
    ref = _referencia(txt, W)
    cena = _cena(g, e, varr)
    fx = _faixas(g, cena)
    pedida = _camada_pedida(e)
    pos = str(e.get("posicao", "auto")).strip().lower()
    cand = {}

    # NA FRENTE: acima/sobre o cabelo ou entre o queixo e a legenda
    for nome, (a, b) in fx.items():
        tam = _tam_que_cabe(txt, W, b - a, ref)
        if tam > 0:
            k = tam / ref["tam"]
            cand[nome] = {"camada": "frente", "zona": nome, "tam": tam,
                          "cx": _centro_x(ref, k, W), "cy": _centro_y_na_faixa(ref, k, (a, b)), "faixa": (a, b)}

    # ATRÁS da pessoa: a palavra pode passar atrás da cabeça, se ficar legível
    peg = cena["peg"]
    if peg is not None and pedida != "frente":
        base = BASE * H
        if cena["leg"] and cena["leg"][1] > 0.45 * H:
            base = min(base, cena["leg"][0] - FOLGA_LEG * H)
        tam = _tam_que_cabe(txt, W, 1e9, ref)
        achou = None
        while tam >= TAM_MIN * W and achou is None:
            k = tam / ref["tam"]
            ex = ref["ext"]
            cx = _centro_x(ref, k, W)
            y_topo = TOPO * H
            while y_topo + (ex[3] - ex[1]) * k <= base and y_topo < 0.46 * H:
                cy = y_topo - ex[1] * k
                # medido um pouco mais embaixo: cobre o balanço e o giro da palavra
                esc, esc_cima, pior = _oculto(ref, k, cx, cy + 0.006 * H, peg, W, H)
                if esc <= OCULTO_MAX and esc_cima <= OCULTO_TOPO_MAX and pior <= 1.0:
                    achou = {"camada": "atras", "zona": "atras", "tam": tam, "cx": cx, "cy": cy,
                             "oculto": round(esc, 3)}
                    break
                y_topo += 0.02 * H
            tam *= 0.93
        if achou:
            cand["atras"] = achou

    def melhor_frente():
        t = cand.get("topo")
        b = cand.get("baixo")
        if pos == "topo" and t and t["tam"] >= TAM_MIN * W:
            return t
        if pos == "baixo" and b and b["tam"] >= TAM_MIN * W:
            return b
        if t and b:
            # acima da cabeça é o visual da prévia; sobre o cabelo vale menos que embaixo
            sobre_cabelo = t["faixa"][1] > cena["cabeca"] + 0.01 * H
            nota_t = t["tam"] * (0.85 if sobre_cabelo else 1.08)
            return t if nota_t >= b["tam"] else b
        return t or b

    fr = melhor_frente()
    at = cand.get("atras")
    if pedida == "atras" and at:
        esc = at
    elif pedida == "frente" or not at:
        esc = fr
    else:  # auto: atrás é a assinatura do estilo quando a palavra continua grande
        esc = at if (fr is None or at["tam"] >= 0.8 * fr["tam"] or fr["tam"] < TAM_BOM * W) else fr
    if esc is None or esc["tam"] < TAM_MIN * W:
        # último recurso: a maior das faixas, com o tamanho mínimo legível
        opcoes = [c for c in (cand.get("baixo"), cand.get("topo"), at) if c]
        esc = dict(max(opcoes, key=lambda c: c["tam"])) if opcoes else \
            {"camada": "frente", "zona": "baixo", "tam": TAM_MIN * W, "cx": W * 0.47,
             "cy": fx["baixo"][0] + 0.06 * H, "faixa": fx["baixo"]}
        if esc["tam"] < TAM_MIN * W:
            k0 = esc["tam"] / ref["tam"]
            esc["tam"] = TAM_MIN * W
            k = esc["tam"] / ref["tam"]
            esc["cx"] = _centro_x(ref, k, W)
            if esc.get("faixa"):
                esc["cy"] = _centro_y_na_faixa(ref, k, esc["faixa"])
            else:
                esc["cy"] = esc["cy"] - ref["ext"][1] * (k - k0)
    esc = dict(esc)
    esc["texto"] = txt
    if esc["camada"] == "atras" and fr is not None:
        # reserva NA FRENTE (fora do rosto) para quadros em que a máscara faltar
        r = dict(fr, texto=txt)
        if r["tam"] < TAM_MIN * W:
            r["tam"] = TAM_MIN * W
            kk = r["tam"] / ref["tam"]
            r["cx"], r["cy"] = _centro_x(ref, kk, W), _centro_y_na_faixa(ref, kk, r["faixa"])
        esc["reserva"] = r

    # frase de apoio (branca, plana): embaixo da palavra quando ela está embaixo; senão logo acima da legenda
    apoio = " ".join(str(e.get("apoio", "") or "").split())
    esc["apoio"] = None
    if apoio:
        ex = ref["ext"]
        xm = W * (X0 + X1) / 2
        if esc["zona"] == "baixo":
            a, b = fx["baixo"]
            t0 = esc["tam"]
            # quanto a palavra pode encolher para a frase caber: até 60% (mantém o 80% das palavras
            # já pequenas); na chamada final ('frente' pedida) até o mínimo legível — a frase é a informação
            limites = [max(TAM_MIN * W, min(TAM_BOM * W, 0.8 * t0), PALAVRA_MIN_REL * t0)]
            if pedida == "frente":
                limites.append(TAM_MIN * W)
            for lim in limites:
                for at in (APOIO_TAM, APOIO_TAM_MIN):
                    ha = _apoio_img(g, apoio, at).height * 0.78
                    k = t0 / ref["tam"]
                    if (ex[3] - ex[1]) * k + 0.01 * H + ha <= b - a:
                        novo = t0
                    else:
                        novo = _tam_que_cabe(txt, W, (b - a) - 0.01 * H - ha, ref)
                        if novo < lim - 0.5:
                            continue
                    esc["tam"] = novo
                    k = novo / ref["tam"]
                    esc["cx"] = _centro_x(ref, k, W)
                    bloco = (ex[3] - ex[1]) * k + 0.01 * H + ha
                    y_top = (a + b) / 2 - bloco / 2
                    esc["cy"] = y_top - ex[1] * k
                    esc["apoio"] = (apoio, xm, y_top + (ex[3] - ex[1]) * k + 0.01 * H, at)
                    break
                if esc["apoio"]:
                    break
        else:
            k = esc["tam"] / ref["tam"]
            a, b = fx["baixo"]
            fundo_palavra = esc["cy"] + ex[3] * k
            for at in (APOIO_TAM, APOIO_TAM_MIN):
                ha = _apoio_img(g, apoio, at).height * 0.78
                if b - a >= ha + 0.01 * H and fundo_palavra + 0.01 * H <= b - ha:
                    esc["apoio"] = (apoio, xm, b - ha, at)
                else:
                    fundo = esc["cy"] + ex[3] * k + 0.01 * H
                    if esc["camada"] == "frente" and fundo + ha <= cena["rosto"][1] - 0.01 * H:
                        esc["apoio"] = (apoio, xm, fundo, at)
                if esc["apoio"]:
                    break
        if not esc["apoio"]:
            dica = "" if pedida == "frente" else ", use \"camada\": \"frente\" nesta palavra"
            _avisar(g, f"'vidro' em {e['inicio']:.2f}s ('{txt}'): o apoio '{apoio}' NÃO coube (pouco espaço "
                       f"entre o queixo e a legenda) e não vai aparecer. Encurte para até 3 palavras curtas "
                       f"(até 20 letras){dica} ou tire o apoio.")
    return esc


# ================================================================== camadas da palavra (cache por evento)

def _construir(g, lay):
    """Pré-desenha a palavra de vidro em pé, de frente: camadas de baixo (sombra, profundidade),
    de cima (brilho da face, chanfro, aro cromado, filete creme) e o campo da lente."""
    W = g.W
    txt, tam = lay["texto"], lay["tam"]
    A_img, caixa, u, _ = _glifo(txt, tam)
    A = _f(A_img)
    h, w = A.shape
    gx0, gy0, gx1, gy1 = caixa
    bw, bh = max(1.0, gx1 - gx0), max(1.0, gy1 - gy0)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    xn, yn = (xx - gx0) / bw, (yy - gy0) / bh

    # ---------- de baixo: sombra + corpo e linhas de profundidade
    somb = _f(_desfocar_L(Image.fromarray(
        (_deslocar(A, 8 * u, 16 * u) * 255).astype(np.uint8), "L"), 14 * u)) * 0.30
    anel3 = np.clip(_f(_dilatar(A_img, 1.5 * u)) - _f(_erodir(A_img, 1.5 * u)), 0, 1)
    linhas = np.zeros_like(A)
    corpo = np.zeros_like(A)
    for dd in (6, 10, 14, 18, 22):
        linhas = np.maximum(linhas, _deslocar(anel3, dd * u, 0.7 * dd * u) * (0.30 + 0.012 * (22 - dd)))
    for dd in np.linspace(2, 22, 11):
        corpo = np.maximum(corpo, _deslocar(A, dd * u, 0.7 * dd * u))
    corpo = np.clip(corpo - A, 0, 1) * 0.16
    prof_a = np.clip(np.maximum(linhas, corpo) * (1 - A), 0, 1)

    def _baixo(tom):
        rgb = np.zeros((h, w, 3), np.float32)
        a = np.zeros((h, w), np.float32)
        _sobre(rgb, a, np.broadcast_to(np.array(SOMBRA_COR, np.float32), (h, w, 3)), somb)
        _sobre(rgb, a, np.broadcast_to(np.array(tom, np.float32), (h, w, 3)), prof_a)
        return _rgba(rgb, a)

    baixo_escuro, baixo_claro = _baixo(PROF_ESCURA), _baixo(PROF_CLARA)
    # sombra extra (fundo agitado): leva a sombra de 0,30 para ~0,42
    somb_mais = _rgba(np.broadcast_to(np.array(SOMBRA_COR, np.float32), (h, w, 3)).copy(), somb / 0.30 * 0.17)

    # ---------- de cima: brilho da face (gradiente diagonal), chanfro, aro cromado, filete creme
    rgb = np.zeros((h, w, 3), np.float32)
    a = np.zeros((h, w), np.float32)
    face_rgb, face_a = _grad(FACE, np.clip((xn + yn) / 2, 0, 1))
    _sobre(rgb, a, face_rgb, face_a * A)
    B = _f(_desfocar_L(A_img, 7 * u))
    gy, gx = np.gradient(B)
    mag = np.sqrt(gx * gx + gy * gy)
    mmax = float(mag.max()) or 1.0
    m = (mag / mmax) ** 0.8
    with np.errstate(invalid="ignore", divide="ignore"):
        nx, ny = np.where(mag > 1e-6, -gx / mag, 0), np.where(mag > 1e-6, -gy / mag, 0)
    luz = nx * -0.55 + ny * -0.83
    realce = np.clip(luz, 0, 1) ** 1.3 * m * A * 0.62
    sombra_ch = np.clip(-luz, 0, 1) * m * A * 0.30
    _sobre(rgb, a, np.broadcast_to(np.array((255, 255, 255), np.float32), (h, w, 3)), realce)
    _sobre(rgb, a, np.broadcast_to(np.array((28, 38, 33), np.float32), (h, w, 3)), sombra_ch)
    aro = np.clip(_f(_dilatar(A_img, 4.5 * u)) - _f(_erodir(A_img, 4.5 * u)), 0, 1)
    aro_rgb, _ = _grad(CROMO, np.clip((xn * 0.7 + yn) / 1.7, 0, 1))
    _sobre(rgb, a, aro_rgb, aro * 0.96)
    anel1 = np.clip(_f(_dilatar(A_img, 1.0 * u)) - _f(_erodir(A_img, 1.0 * u)), 0, 1)
    filete = _deslocar(anel1, -4 * u, -5 * u) * 0.9
    _sobre(rgb, a, np.broadcast_to(np.array(CREME, np.float32), (h, w, 3)), filete)
    cima = _rgba(rgb, a)
    aro_img = Image.fromarray((np.clip(aro * 0.75 + anel1 * 0.25, 0, 1) * 255).astype(np.uint8), "L")

    # ---------- lente: deslocamento por chanfro + ondulação lenta (como o feTurbulence da prévia)
    B2 = _f(_desfocar_L(A_img, 10 * u))
    g2y, g2x = np.gradient(B2)
    m2 = float(np.sqrt(g2x * g2x + g2y * g2y).max()) or 1.0
    rng = np.random.default_rng(_semente(txt, round(tam)))
    cel = max(8.0, 70 * u)
    rx = rng.uniform(-1, 1, (max(2, int(h / cel) + 2), max(2, int(w / cel) + 2))).astype(np.float32)
    ry = rng.uniform(-1, 1, rx.shape).astype(np.float32)
    nxf = np.asarray(Image.fromarray(rx, "F").resize((w, h), Image.BICUBIC), np.float32)
    nyf = np.asarray(Image.fromarray(ry, "F").resize((w, h), Image.BICUBIC), np.float32)
    dx = -g2x / m2 * 24 * u + nxf * 13 * u
    dy = -g2y / m2 * 24 * u + nyf * 13 * u
    face_alpha = Image.fromarray((np.clip(A, 0, 1) * 0.95 * 255).astype(np.uint8), "L")
    # textura refratada e reflexo em MEIA resolução (o vidro é fosco: não perde nada e fica 4x mais rápido).
    # A área amostrada é um pouco maior que a letra, para a borda não puxar preto ao ampliar.
    h2, w2 = h // 2, w // 2
    A2 = np.asarray(A_img.resize((w2, h2), Image.BILINEAR).filter(ImageFilter.MaxFilter(5)), np.float32) / 255.0
    vv2, uu2 = np.nonzero(A2 > 0.01)
    fy, fx = np.minimum(vv2 * 2, h - 1), np.minimum(uu2 * 2, w - 1)
    yy2, xx2 = np.mgrid[0:h2, 0:w2].astype(np.float32)
    s2 = xx2 * 2 - 0.571 * yy2 * 2           # coordenada diagonal do reflexo (em px da camada cheia)
    s_min = float(s2.min())
    s_idx = np.round(s2 - s_min).astype(np.int32)
    return {
        "w": w, "h": h, "w2": w2, "h2": h2, "u": u, "caixa": caixa,
        "ax": (gx0 + gx1) / 2, "ay": (gy0 + gy1) / 2,
        "baixo_escuro": baixo_escuro, "baixo_claro": baixo_claro, "somb_mais": somb_mais,
        "cima": cima, "aro": aro_img,
        "face_alpha": face_alpha,
        "uu2": uu2, "vv2": vv2,
        "uf2": (uu2 * 2.0 + 0.5).astype(np.float32), "vf2": (vv2 * 2.0 + 0.5).astype(np.float32),
        "dx2": dx[fy, fx].astype(np.float32), "dy2": dy[fy, fx].astype(np.float32),
        "s_idx": s_idx, "s_min": s_min, "s_n": int(s_idx.max()) + 1,
        "s0": float(gx0 - 0.571 * gy1), "s1": float(gx1 - 0.571 * gy0),
    }


def _camadas(g, idx, lay):
    chave = ("e17cam", idx)
    if chave not in g.cache:
        g.cache[chave] = _construir(g, lay)
        # guarda poucas palavras prontas por processo (memória)
        prontas = [k for k in g.cache if isinstance(k, tuple) and k and k[0] == "e17cam"]
        if len(prontas) > 4:
            for k in prontas[:-4]:
                if k != chave:
                    g.cache.pop(k, None)
    return g.cache[chave]


# ================================================================== preparar / validar

def preparar(g):
    vid = [(i, e) for i, e in enumerate(g.plano["eventos"]) if e.get("tipo") == "vidro"]
    varr = _varrer_mascara(g) if vid else None
    g.cache["e17varr"] = varr is not None
    g.cache["e17lay"] = {i: _layout(g, e, varr) for i, e in vid}


def validar(plano, duracao):
    p = []
    evs = plano.get("eventos", [])
    vid = sorted([e for e in evs if e.get("tipo") == "vidro"], key=lambda e: e["inicio"])
    internos = {"TEXTO", "PALAVRA", "TITULO", "TÍTULO", "VIDRO 17", "TIPO VIDRO", "17-TIPO-VIDRO", "EXEMPLO"}
    for e in vid:
        t = " ".join(str(e.get("texto", "")).split()).strip(".,;:!?…\"'“”")
        if not t:
            p.append(f"'vidro' em {e['inicio']:.2f}s sem texto.")
            continue
        if t.upper() in internos:
            p.append(f"'vidro' em {e['inicio']:.2f}s com texto interno/de exemplo ('{t}'): use uma palavra da fala.")
        if len(t.split()) > 2:
            p.append(f"'vidro' em {e['inicio']:.2f}s com {len(t.split())} palavras: use 1 (no máximo 2 curtas).")
        if len(t) > 12:
            p.append(f"'vidro' em {e['inicio']:.2f}s longo demais ('{t}', {len(t)} letras; máx. 12): "
                     "escolha a palavra mais forte.")
        dur = e["fim"] - e["inicio"]
        if dur < 1.15:
            p.append(f"'vidro' em {e['inicio']:.2f}s curto demais ({dur:.1f}s; mínimo 1,2 s para ler).")
        if dur > 5.0:
            p.append(f"'vidro' em {e['inicio']:.2f}s longo demais ({dur:.1f}s; máximo 4 s).")
        if str(e.get("camada", "auto")).lower() not in ("auto", "atras", "atrás", "frente", "na frente"):
            p.append(f"'vidro' em {e['inicio']:.2f}s: camada deve ser 'auto', 'atras' ou 'frente'.")
        if str(e.get("posicao", "auto")).lower() not in ("auto", "topo", "baixo"):
            p.append(f"'vidro' em {e['inicio']:.2f}s: posicao deve ser 'auto', 'topo' ou 'baixo'.")
        ap = " ".join(str(e.get("apoio", "") or "").split())
        if ap.lower().strip(".!") in ("forma e luz", "sua história merece movimento", "seu texto aqui"):
            p.append(f"'vidro' em {e['inicio']:.2f}s: apoio copiado da prévia do card ('{ap}'): use a fala.")
        if ap and (len(ap.split()) > 5 or len(ap) > 34):
            p.append(f"'vidro' em {e['inicio']:.2f}s: apoio longo demais (máx. 5 palavras / 34 letras).")
        if ap:
            pal_ap = set(_normal(ap).split())
            rep = [w for w in _normal(t).split() if (len(w) >= 3 or w.isdigit()) and w in pal_ap]
            if rep:
                p.append(f"'vidro' em {e['inicio']:.2f}s: o apoio repete a palavra de vidro ('{t}'); "
                         "use só o resto da frase (ex.: texto \"26\" + apoio \"vídeos nos próximos dias\").")
    for a, b in zip(vid, vid[1:]):
        if b["inicio"] < a["fim"] - 0.05:
            p.append(f"Palavras de vidro sobrepostas em {b['inicio']:.2f}s: uma palavra por vez "
                     "(a próxima começa quando a anterior termina).")
    if duracao > 6 and len(vid) > max(2, duracao / 2.6):
        p.append(f"Palavras de vidro demais ({len(vid)} em {duracao:.0f}s): no máximo 1 a cada 3-4 s.")
    for e in evs:
        if e.get("tipo") != "brilho":
            continue
        dono = [v for v in vid if v["inicio"] + 0.35 <= e["inicio"] and e["inicio"] <= v["fim"] - 0.25]
        if not dono:
            p.append(f"'brilho' em {e['inicio']:.2f}s fora de uma palavra de vidro (precisa começar "
                     "≥0,35 s depois do início e ≥0,25 s antes do fim de um 'vidro').")
        if e["fim"] - e["inicio"] > 1.2:
            p.append(f"'brilho' em {e['inicio']:.2f}s longo demais (0,3-0,8 s).")
    try:
        from ..audio import info_som
        for e in evs:
            if e.get("som") and info_som(str(e["som"]))[0] is None:
                p.append(f"Som '{e['som']}' (em {e['inicio']:.2f}s) não existe na biblioteca: use um apelido "
                         "(vidro, whoosh-curto...) ou um id de motor/sons/kit/catalogo.json.")
    except Exception:  # noqa: BLE001
        pass
    return p


# ================================================================== quadro

def _estado(t, e, brilhos):
    """Movimento da palavra no instante t (só função do tempo)."""
    ini, fim = e["inicio"], e["fim"]
    t_in = ini - 0.12
    kin = d.saida(d.mapear(t, t_in, t_in + ENTRA))
    op_in = d.suave(d.mapear(t, t_in, t_in + 0.30))
    kout = d.entrada(d.mapear(t, fim - SAI, fim + 0.02))
    vivo = t - ini
    th = ROT_Y + AMP_Y * math.sin(2 * math.pi * vivo / 5.2 + 0.6) + 34.0 * (1 - kin) - 10.0 * kout
    ph = ROT_Z + AMP_Z * math.sin(2 * math.pi * vivo / 6.6 + 1.9) + 3.0 * (1 - kin)
    esc = (0.90 + 0.10 * kin) * (1 - 0.035 * kout)
    dy = 0.025 * (1 - kin) - 0.015 * kout + 0.0035 * math.sin(2 * math.pi * vivo / 3.7)
    op = op_in * (1 - kout)
    desf = 0.016 * (1 - d.suave(d.mapear(t, t_in, t_in + ENTRA * 0.8))) + 0.012 * kout
    # reflexo: passada forte na entrada, vai-e-volta lento no meio (prévia), passadas dos 'brilho'
    var = []
    p_in = d.mapear(t, t_in + 0.12, t_in + 0.95)
    if 0 < p_in < 1:
        var.append((d.suave(p_in), 0.55))
    if t > t_in + 0.95:
        fase = (t - (t_in + 0.95)) / 4.4
        var.append(((1 - math.cos(2 * math.pi * fase)) / 2, 0.2 * d.suave(d.mapear(t, t_in + 0.95, t_in + 1.4))))
    pulso = 0.0
    for b in brilhos:
        pb = d.mapear(t, b["inicio"], b["inicio"] + max(0.3, min(0.8, b["fim"] - b["inicio"])))
        if 0 < pb < 1:
            var.append((d.suave(pb), 0.75))
        pulso = max(pulso, math.sin(math.pi * d.mapear(t, b["inicio"], b["inicio"] + 0.35)))
    esc *= 1 + 0.022 * pulso
    return {"th": th, "ph": ph, "esc": esc, "dy": dy, "op": op, "desf": desf, "var": var, "pulso": pulso}


def _fundo_limpo(reg, m_reg):
    """Atrás da pessoa o vidro refrata a parede, não a pessoa: preenche a silhueta com o fundo vizinho."""
    w, h = reg.size
    pw, ph = max(2, w // 6), max(2, h // 6)
    livre = Image.eval(m_reg, lambda v: 255 - v)
    num = Image.composite(reg, Image.new("RGB", reg.size, 0), livre).resize((pw, ph), Image.BILINEAR)
    den = livre.resize((pw, ph), Image.BILINEAR)
    num = num.filter(ImageFilter.GaussianBlur(3))
    den = den.filter(ImageFilter.GaussianBlur(3))
    n = np.asarray(num, np.float32)
    dd = np.asarray(den, np.float32)[..., None] / 255.0
    cheio = np.clip(n / np.maximum(dd, 0.02), 0, 255).astype(np.uint8)
    cheio = Image.fromarray(cheio, "RGB").resize((w, h), Image.BILINEAR)
    return Image.composite(cheio, reg, m_reg)


def _desfocar_camada(cam, raio):
    """Desfoque da entrada/saída (reduz antes de desfocar: rápido)."""
    if raio < 0.6:
        return cam
    pm = cam.convert("RGBa")
    if raio > 3:
        w, h = pm.size
        peq = pm.resize((max(2, w // 2), max(2, h // 2)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(raio / 2))
        pm = peq.resize((w, h), Image.BILINEAR)
    else:
        pm = pm.filter(ImageFilter.GaussianBlur(raio))
    return pm.convert("RGBA")


def _desenhar_palavra(c, img, idx, e, brilhos):
    W, H = c.W, c.H
    lay = c.g.cache["e17lay"][idx]
    chave = idx
    if lay["camada"] == "atras" and c.mascara is None and lay.get("reserva"):
        # sem máscara neste quadro (ex.: máscara mais curta que o vídeo): nunca na frente da cabeça
        lay, chave = lay["reserva"], (idx, "reserva")
    est = _estado(c.t, e, brilhos)
    if est["op"] <= 0.004:
        return
    L = _camadas(c.g, chave, lay)
    w, h = L["w"], L["h"]
    cx, cy = lay["cx"], lay["cy"] + est["dy"] * H
    foco = FOCO * W
    flat = ((0, 0), (w, 0), (w, h), (0, h))
    tela = _cantos(flat, L["ax"], L["ay"], cx, cy, est["th"], est["ph"], est["esc"], foco)
    xs, ys = [p[0] for p in tela], [p[1] for p in tela]
    bx0, by0 = int(math.floor(min(xs))), int(math.floor(min(ys)))
    bx1, by1 = int(math.ceil(max(xs))), int(math.ceil(max(ys)))
    if bx1 <= 0 or by1 <= 0 or bx0 >= W or by0 >= H:
        return
    atras = lay["camada"] == "atras" and c.mascara is not None

    # ---------- refração: amostra o quadro atrás de cada ponto da letra (em meia resolução)
    margem = int(0.05 * W)
    rx0, ry0 = max(0, bx0 - margem), max(0, by0 - margem)
    rx1, ry1 = min(W, bx1 + margem), min(H, by1 + margem)
    caixa_r = (rx0, ry0, rx1, ry1)
    # a pessoa original desta região é guardada ANTES de desenhar (o quadro é desenhado no lugar)
    caixa_p = (max(0, bx0), max(0, by0), min(W, bx1), min(H, by1))
    pessoa_reg = c.fonte.crop(caixa_p) if atras else None
    reg = c.fonte.crop(caixa_r).reduce(2).convert("RGB")
    rw, rh = reg.size
    if atras:
        reg = _fundo_limpo(reg, c.mascara.crop(caixa_r).reduce(2))
    # fundo cheio de detalhe (texto gravado, estante): o vidro fica mais fosco, mais tingido e com mais
    # sombra, senão a forma das letras se perde. Transição contínua (sem piscar entre quadros).
    cz = np.asarray(reg.convert("L").reduce(2), np.float32) / 255.0
    kc = d.limitar((float(cz.std()) - (CONTRASTE_ALTO - 0.04)) / 0.08)
    # vidro fosco: desfoque leve (separa a letra do fundo cheio de detalhe)
    reg = reg.filter(ImageFilter.GaussianBlur(max(0.8, FOSCO * (1 + 1.6 * kc) * W / 2)))
    tinta = TINTA + 0.18 * kc
    arr = np.asarray(reg, np.uint8)
    sx, sy = (rx1 - rx0) / rw, (ry1 - ry0) / rh
    lum = float(arr[::4, ::4].mean()) / 255.0
    a_, b_, c_, d_, e_, f_, g_, h_ = d._coef_perspectiva(tela, flat)  # plano -> tela
    uf, vf = L["uf2"], L["vf2"]
    den = g_ * uf + h_ * vf + 1.0
    X = (a_ * uf + b_ * vf + c_) / den
    Y = (d_ * uf + e_ * vf + f_) / den
    # lente: aumenta 5% em torno do centro e desloca pelo campo do chanfro (+ dispersão de cor)
    lente = 1 / 1.05
    X = (cx + (X - cx) * lente - rx0) / sx
    Y = (cy + (Y - cy) * lente - ry0) / sy
    k = est["esc"]
    hh, ww = arr.shape[:2]
    cores = []
    for canal, fator in ((0, 1.12), (1, 1.0), (2, 0.88)):
        ix = np.clip((X + L["dx2"] * (k * fator / sx)).astype(np.int32), 0, ww - 1)
        iy = np.clip((Y + L["dy2"] * (k * fator / sy)).astype(np.int32), 0, hh - 1)
        cores.append(arr[iy, ix, canal].astype(np.float32))
    amostra = np.stack(cores, axis=-1)
    cinza = amostra @ np.array([0.3, 0.59, 0.11], np.float32)
    amostra = cinza[:, None] + (amostra - cinza[:, None]) * 0.65          # dessatura (como a prévia)
    amostra = amostra * (1 - tinta) + TINTA_VIDRO * tinta + LUZ          # tinta verde-clara e luz
    face2 = np.zeros((L["h2"], L["w2"], 4), np.uint8)
    face2[..., 3] = 255
    face2[L["vv2"], L["uu2"], :3] = np.clip(amostra, 0, 255).astype(np.uint8)
    face_img = Image.fromarray(face2, "RGBA").resize((w, h), Image.BILINEAR)
    face_img.putalpha(L["face_alpha"])

    # ---------- empilha: de baixo (tom conforme o fundo) + face refratada + de cima + reflexo
    # fundo claro -> linhas de profundidade escuras; fundo escuro -> claras (8 tons prontos por palavra)
    kt = round(d.limitar((lum - 0.32) / 0.25) * 8) / 8
    ks = round(kc * 4) / 4                                   # sombra extra em 5 degraus (fundo agitado)
    tons = L.setdefault("tons", {})
    if (kt, ks) not in tons:
        tom = Image.blend(L["baixo_claro"], L["baixo_escuro"], kt) if 0 < kt < 1 else \
            (L["baixo_escuro"] if kt >= 1 else L["baixo_claro"])
        if ks > 0:
            mais = L["somb_mais"].copy()
            mais.putalpha(mais.getchannel("A").point(lambda v, f=ks: int(v * f)))
            tom = Image.alpha_composite(mais, tom)
        tons[(kt, ks)] = tom
    baixo = tons[(kt, ks)]
    cam = Image.alpha_composite(baixo, face_img)
    cam.alpha_composite(L["cima"])
    if est["var"]:
        # o reflexo só depende da diagonal: calcula numa linha (tabela) e espalha pela letra
        s = np.arange(L["s_n"], dtype=np.float32) + L["s_min"]
        tab = np.zeros(L["s_n"], np.float32)
        larg = 26 * L["u"]
        for pos, forca in est["var"]:
            centro = L["s0"] - 90 * L["u"] + (L["s1"] - L["s0"] + 180 * L["u"]) * pos
            tab = np.maximum(tab, forca * np.exp(-((s - centro) / larg) ** 2))
            tab = np.maximum(tab, forca * 0.8 * np.exp(-((s - centro - 52 * L["u"]) / (7 * L["u"])) ** 2))
        if tab.max() > 0.01:
            tab8 = (np.clip(tab, 0, 1) * 255).astype(np.uint8)
            m2 = Image.fromarray(tab8[L["s_idx"]], "L").resize((w, h), Image.BILINEAR)
            cam.paste((255, 255, 255, 255), (0, 0), ImageChops.multiply(m2, L["face_alpha"]))
    if est["pulso"] > 0.02:  # o aro acende no brilho
        cam.paste((255, 255, 255, 255), (0, 0), L["aro"].point(lambda v, p=est["pulso"]: int(v * 0.55 * p)))
    cam = _desfocar_camada(cam, est["desf"] * W)

    # ---------- gira em 3D e cola
    destino = [(x - bx0, y - by0) for x, y in tela]
    coef_w = d._coef_perspectiva(flat, destino)
    tw, th_ = bx1 - bx0, by1 - by0
    girada = cam.convert("RGBa").transform((tw, th_), Image.PERSPECTIVE, coef_w, Image.BILINEAR).convert("RGBA")
    d.colar_em(img, girada, (bx0, by0), opacidade=est["op"])

    # ---------- atrás: a pessoa volta por cima, só na região da palavra
    if atras and caixa_p[2] > caixa_p[0] and caixa_p[3] > caixa_p[1]:
        img.paste(pessoa_reg, caixa_p[:2], c.mascara.crop(caixa_p))


def _desenhar_apoio(c, img, idx, e):
    lay = c.g.cache["e17lay"][idx]
    if not lay.get("apoio"):
        return
    if lay["camada"] == "atras" and c.mascara is None and lay.get("reserva"):
        return  # quadro sem máscara: a palavra foi para a frente (reserva) e ocuparia o lugar da frase
    txt, x, y, at = lay["apoio"]
    ini, fim = e["inicio"], e["fim"]
    k = d.saida(d.mapear(c.t, ini + 0.18, ini + 0.6))
    op = d.suave(d.mapear(c.t, ini + 0.18, ini + 0.45)) * (1 - d.entrada(d.mapear(c.t, fim - 0.32, fim)))
    if op <= 0.01:
        return
    cam = _apoio_img(c.g, txt, at)
    yy = y + (1 - k) * 0.012 * c.H
    d.colar_em(img, cam, (x - cam.width / 2, yy - cam.height * 0.12), opacidade=op)


def quadro(c):
    # c.fonte é um quadro novo a cada chamada: desenha direto nele (sem cópia de tela cheia).
    # Tudo o que precisa do quadro original (refração, pessoa) é recortado antes de desenhar.
    img = c.fonte
    lays = c.g.cache.get("e17lay") or {}
    if not lays:
        return img
    evs = c.g.plano["eventos"]
    brilhos = [b for b in c.eventos if b.get("tipo") == "brilho"]
    for idx, e in enumerate(evs):
        if e.get("tipo") != "vidro" or idx not in lays:
            continue
        if not (e["inicio"] - INFO["antes"] <= c.t <= e["fim"] + INFO["depois"]):
            continue
        meus = [b for b in brilhos if e["inicio"] <= b["inicio"] <= e["fim"]]
        _desenhar_palavra(c, img, idx, e, meus)
        _desenhar_apoio(c, img, idx, e)
    return img
