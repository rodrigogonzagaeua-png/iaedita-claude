"""06 · Maquete de celular — nos momentos certos da fala a câmera se afasta: a pessoa recortada fica grande
numa sala clara (a mesma da prévia aprovada) e um celular escuro, inclinado em 3D, flutua ao lado dela
mostrando a INTERFACE de um app: frase com ícone neon, barra de progresso que vira "pronto" e número que
sobe, tudo DENTRO da tela do celular. Entre uma cena e outra o vídeo volta para a tela cheia (rosto grande).

Dois modos por cena (campo "modo" do evento celular):
- "pessoa" (padrão quando existe recorte): a composição da prévia aprovada.
- "tela" (padrão sem recorte): o vídeo inteiro encolhe e vira a tela do celular; os cartões ficam ao lado,
  sempre abaixo do queixo. É o caminho sem recorte — continua bonito e nunca cobre o rosto."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .. import desenho as d
from ..legenda import Legendas, PerfilLegenda, agrupar

try:  # OpenCV distorce em ~3 ms (o Pillow leva 30-100 ms); sem ele o estilo funciona igual, só mais devagar
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

INFO = {
    "id": "06-maquete-de-celular",
    "nome": "Maquete de celular",
    "precisa_recorte": True,    # modo "pessoa" (o da prévia); sem recorte o estilo usa o modo "tela"
    "antes": 0.05,
    "depois": 0.05,
    # perfil da ficha: Inter 750, palavra falada com fundo neon, caixa escura de largura fixa
    "legenda": {"peso": 750, "tamanho": 0.063, "cor": "#F8F7F0", "destaque": "#D4ED80", "caixa": "#222729ED",
                "max_caracteres": 20, "max_linhas": 1, "animacao": "pop", "posicao": "auto"},
    "legenda_propria": True,   # o estilo desenha a legenda (palavra falada ganha uma caixinha neon)
    "eventos": {
        "celular": "inicio, fim (2,5 a 12 s): a câmera se afasta, a pessoa vai para a sala e o celular inclinado "
                   "entra ao lado (modo 'pessoa'), ou o vídeo vira a tela do celular (modo 'tela'); no fim volta "
                   "para a tela cheia. titulo (opcional, até 22 letras, aparece no alto), "
                   "lado ('direita' padrão | 'esquerda': onde fica o celular), fundo ('sala' padrão | "
                   "'sala-escura' | 'video'), modo (opcional: 'pessoa' | 'tela'; o motor escolhe), som",
        "cartao": "inicio, fim (1,2 a 4 s), dentro de uma cena celular: cartão de interface com ícone neon. "
                  "texto (até 4 palavras), detalhe (opcional, até 4 palavras, linha pequena em cima), "
                  "icone (check | estrela | raio | alvo | grafico | dinheiro | coracao | play | seta_cima), som",
        "progresso": "inicio, fim (2,5 a 5 s), dentro de uma cena celular: blocos e barra que enchem e botão que "
                     "vira '✓ final'. texto (até 4 palavras), final (até 3 palavras, ex.: 'Tudo pronto'), "
                     "conclui (segundo em que a barra enche, entre inicio + 0,8 s e fim - 1 s; padrão: 1 s antes do fim), som",
        "contador": "inicio, fim (1,5 a 4 s), dentro de uma cena celular: número que sobe de 0 até o valor. "
                    "valor (número, ex.: 26 ou 2.5), antes (ex.: 'R$' ou '+'), depois (ex.: 'vídeos', '%', 'mil'), "
                    "texto (opcional, rótulo pequeno em cima), som",
    },
}

# ---------------------------------------------------------------- identidade (cores da prévia aprovada)
TINTA = "#222729"
CREME = "#F8F7F0"
LIMA = "#D4ED80"
UI_FUNDO = "#202A2C"
UI_PAINEL = "#161C1E"
UI_TEXTO = "#F6F9EE"
UI_CINZA = "#AEBDB3"
UI_BLOCO = "#526066"
UI_TRILHO = "#4D5B54"
CORPO = "#151B1C"
ARO = "#576162"
ICONE_TINTA = "#202A22"

TIPOS_UI = ("cartao", "progresso", "contador")
ICONES = ("check", "x", "seta_cima", "seta_baixo", "seta_dir", "play", "estrela", "raio", "alvo", "grafico",
          "dinheiro", "coracao", "ponto")
FUNDOS = ("sala", "sala-escura", "video")
MODOS = ("pessoa", "tela")
LADOS = ("direita", "esquerda")

# ---------------------------------------------------------------- geometria do celular
# Unidade = largura da área do vídeo dentro da tela. A área do vídeo tem a MESMA proporção do quadro,
# então o vídeo entra inteiro na tela, sem corte.
BORDA = 0.05       # espessura da moldura preta
TOPO = 0.13        # barra de status (ilha, ícones)
BASE = 0.17        # barra de baixo (linha de progresso, ícones, indicador)
R_CORPO = 0.17
R_TELA = 0.125
SOMBRA_DX, SOMBRA_DY, SOMBRA_SIGMA = 0.035, 0.07, 0.05   # sombra (20px 38px 65px da prévia, em unidades)
M_ESQ, M_TOPO, M_DIR, M_BASE = 0.11, 0.08, 0.18, 0.22  # margens da imagem pré-desenhada (botões e sombra)
PERSP = 1.574      # distância da perspectiva em larguras do quadro (1700 px num quadro de 1080, como na prévia)
PERIODO = 6.0      # balanço do celular (s), igual ao ciclo da prévia
T_ENTRA = 0.8
T_SAI = 0.55


def _dims(W, H):
    A = H / W
    bw = 1 + 2 * BORDA
    bh = TOPO + A + BASE + 2 * BORDA
    vy0 = -bh / 2 + BORDA + TOPO
    return A, bw, bh, vy0


# ---------------------------------------------------------------- projeção 3D e colagem em perspectiva

def _proj(pts, pose, W):
    """Pontos locais (unidades) -> pixels do quadro. pose = (cx, cy, escala px/unid, rotY°, rotZ°).
    Mesma ordem do CSS da prévia: perspective() rotateY() rotateZ()."""
    cx, cy, s, ry, rz = pose
    p = np.asarray(pts, dtype=np.float64) * s
    a, b = math.radians(rz), math.radians(ry)
    x1 = p[:, 0] * math.cos(a) - p[:, 1] * math.sin(a)
    y1 = p[:, 0] * math.sin(a) + p[:, 1] * math.cos(a)
    x2 = x1 * math.cos(b)
    z2 = -x1 * math.sin(b)
    dd = PERSP * W
    f = dd / (dd - z2)
    return np.stack([cx + x2 * f, cy + y1 * f], axis=1)


def _coef(origem, destino):
    m, v = [], []
    for (x, y), (u, w) in zip(destino, origem):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        m.append([0, 0, 0, x, y, 1, -w * x, -w * y])
        v += [u, w]
    return np.linalg.solve(np.array(m, dtype=np.float64), np.array(v, dtype=np.float64)).tolist()


def _caixa_quad(base, quad):
    W, H = base.size
    x0 = max(0, int(math.floor(quad[:, 0].min())) - 1)
    y0 = max(0, int(math.floor(quad[:, 1].min())) - 1)
    x1 = min(W, int(math.ceil(quad[:, 0].max())) + 1)
    y1 = min(H, int(math.ceil(quad[:, 1].max())) + 1)
    return x0, y0, x1, y1


def _colar_quad(base, img, quad, metodo=Image.BICUBIC):
    """Distorce img (Pillow) para o quadrilátero (sup-esq, sup-dir, inf-dir, inf-esq) e cola. Só para
    coisas desenhadas uma vez (fundo); por quadro use _distorcer, que é rápido."""
    x0, y0, x1, y1 = _caixa_quad(base, quad)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    w, h = img.size
    dst = [(float(px) - x0, float(py) - y0) for px, py in quad]
    try:
        coef = _coef([(0, 0), (w, 0), (w, h), (0, h)], dst)
    except np.linalg.LinAlgError:
        return
    out = img.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, coef, metodo)
    base.alpha_composite(out, (x0, y0))


def _distorcer(base, src_img, quad, src_np=None, src_pm=None):
    """Cola src (RGBA, alfa direto) distorcida no quadrilátero, quadro a quadro.
    Com OpenCV: src_np (array RGBA). Sem OpenCV: src_pm (a mesma imagem em 'RGBa', pré-multiplicada)."""
    x0, y0, x1, y1 = _caixa_quad(base, quad)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    w, h = src_img.size
    dst = quad - np.array([x0, y0], dtype=np.float64)
    if cv2 is not None:
        arr = src_np if src_np is not None else np.asarray(src_img)
        M = cv2.getPerspectiveTransform(np.float32([(0, 0), (w, 0), (w, h), (0, h)]), dst.astype(np.float32))
        out = Image.fromarray(cv2.warpPerspective(arr, M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR,
                                                  borderMode=cv2.BORDER_CONSTANT, borderValue=(21, 27, 28, 0)),
                              "RGBA")
        base.paste(out, (x0, y0), out)
        return
    try:
        coef = _coef([(0, 0), (w, 0), (w, h), (0, h)], [tuple(p) for p in dst])
    except np.linalg.LinAlgError:
        return
    pm = src_pm if src_pm is not None else src_img.convert("RGBa")
    out = pm.transform((x1 - x0, y1 - y0), Image.PERSPECTIVE, coef, Image.BILINEAR).convert("RGBA")
    base.paste(out, (x0, y0), out)


def _painel_c(g, w, h, raio, cor_):
    """Painel arredondado guardado em cache (cartões redesenhados a cada quadro ficam leves)."""
    cor_ = d.cor(cor_)
    chave = ("06pn", int(w), int(h), int(raio), cor_)
    if chave not in g.cache:
        g.cache[chave] = d.painel(int(w), int(h), int(raio), fundo=cor_)
    return g.cache[chave]


def _poligono_suave(base, pts, cor, ss=4):
    """Polígono com borda suave (super-amostrado), desenhado só na área dele."""
    W, H = base.size
    x0 = max(0, int(math.floor(pts[:, 0].min())) - 1)
    y0 = max(0, int(math.floor(pts[:, 1].min())) - 1)
    x1 = min(W, int(math.ceil(pts[:, 0].max())) + 1)
    y1 = min(H, int(math.ceil(pts[:, 1].max())) + 1)
    if x1 - x0 < 1 or y1 - y0 < 1:
        return
    m = Image.new("L", ((x1 - x0) * ss, (y1 - y0) * ss), 0)
    ImageDraw.Draw(m).polygon([((px - x0) * ss, (py - y0) * ss) for px, py in pts], fill=cor[3])
    m = m.resize((x1 - x0, y1 - y0), Image.BILINEAR)
    cam = Image.new("RGBA", (x1 - x0, y1 - y0), cor[:3] + (255,))
    cam.putalpha(m)
    base.alpha_composite(cam, (x0, y0))


def _sombra_quad(base, quad, desloc, raio, cor, alfa):
    """Sombra suave do celular (polígono desfocado em 1/4 da resolução, só na área dela)."""
    if alfa <= 0.01:
        return
    W, H = base.size
    q = quad + np.asarray(desloc)
    marg = raio * 3
    x0 = max(0, int(q[:, 0].min() - marg))
    y0 = max(0, int(q[:, 1].min() - marg))
    x1 = min(W, int(q[:, 0].max() + marg))
    y1 = min(H, int(q[:, 1].max() + marg))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return
    r = 4
    m = Image.new("L", (max(1, (x1 - x0) // r), max(1, (y1 - y0) // r)), 0)
    ImageDraw.Draw(m).polygon([((px - x0) / r, (py - y0) / r) for px, py in q], fill=int(255 * d.limitar(alfa)))
    m = m.filter(ImageFilter.GaussianBlur(max(1.0, raio / r))).resize((x1 - x0, y1 - y0), Image.BILINEAR)
    base.paste(d.cor(cor)[:3] + (255,), (x0, y0, x1, y1), m)


# ---------------------------------------------------------------- fundo: a sala da prévia

PALETAS = {
    "sala": {"parede": "#E4E0D5", "luz": "#FFF7DC", "luz_a": 0.67, "moldura": "#C2BCAE", "janela": "#AD9E86",
             "janela_borda": "#786B55", "vidro": ("#D0DBCA", "#A3BAAF", "#7C9690"), "vidro_borda": "#766C58",
             "piso": "#C3B9A5", "piso_borda": "#A99D88", "sofa": ("#879C8B", "#647C6A"), "assento": "#7E9482",
             "poste": "#685A40", "cupula": "#D8C8A1"},
    "sala-escura": {"parede": "#343B3C", "luz": "#75847C", "luz_a": 0.33, "moldura": "#68716B",
                    "janela": "#262D2D", "janela_borda": "#4A4639", "vidro": ("#4F5F5A", "#3A4A47", "#2C3A38"),
                    "vidro_borda": "#3E3A30", "piso": "#262C2C", "piso_borda": "#3A4242",
                    "sofa": ("#435C50", "#30483E"), "assento": "#3B5145", "poste": "#4A4130", "cupula": "#8C8268"},
}


def _gradiente_v(w, h, c0, c1):
    a, b = np.array(d.cor(c0), np.float32), np.array(d.cor(c1), np.float32)
    k = np.linspace(0, 1, max(1, h), dtype=np.float32)[:, None, None]
    arr = (a * (1 - k) + b * k).repeat(max(1, w), axis=1).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def _ret_arred(w, h, r_topo, r_base, ss=2):
    """Máscara L com raios diferentes em cima e embaixo (o encosto do sofá da prévia)."""
    w, h = max(1, int(w)), max(1, int(h))
    cima = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(cima).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), int(r_topo * ss), fill=255)
    baixo = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(baixo).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), int(r_base * ss), fill=255)
    meio = h * ss // 2
    cima.paste(baixo.crop((0, meio, w * ss, h * ss)), (0, meio))
    return cima.resize((w, h), Image.LANCZOS)


def _janela(P, w, h, U):
    """Janela/porta da prévia (plana); depois vai para a perspectiva."""
    img = Image.new("RGBA", (int(w), int(h)), d.cor(P["janela_borda"]))
    b = int(0.0185 * U)
    ImageDraw.Draw(img).rectangle((b, b, int(w) - b - 1, int(h) - b - 1), fill=d.cor(P["janela"]))
    ins = int(0.026 * U)
    gw, gh = int(w) - 2 * ins, int(h) - 2 * ins
    c0, c1, c2 = (np.array(d.cor(c), np.float32) for c in P["vidro"])
    yy, xx = np.mgrid[0:gh, 0:gw].astype(np.float32)
    k = np.clip((xx / max(1, gw) * 0.64 + yy / max(1, gh) * 0.77) / 1.41, 0, 1)[..., None]
    arr = np.where(k < 0.65, c0 + (c1 - c0) * (k / 0.65), c1 + (c2 - c1) * ((k - 0.65) / 0.35))
    vidro = Image.fromarray(arr.astype(np.uint8), "RGBA")
    bv = int(0.011 * U)
    dv = ImageDraw.Draw(vidro)
    dv.rectangle((0, 0, gw - 1, gh - 1), outline=d.cor(P["vidro_borda"]), width=bv)
    xm = int(0.102 * U) - ins
    dv.rectangle((xm, 0, xm + int(0.009 * U), gh), fill=d.cor(P["vidro_borda"]))
    img.alpha_composite(vidro, (ins, ins))
    return img


def _sala(g, tom):
    chave = ("06sala", tom, g.W, g.H)
    if chave in g.cache:
        return g.cache[chave]
    W, H = g.W, g.H
    S = 2
    w, h = W * S, H * S
    U = W * S                     # medidas da prévia em frações da largura (1080) e altura (1920)
    P = PALETAS["sala-escura" if tom == "sala-escura" else "sala"]
    # parede: luz difusa no alto à esquerda + leve escurecimento para baixo/direita (como a prévia).
    # Gradientes suaves: calculados pequenos e ampliados uma vez (pouca memória).
    lw, lh = W // 4, H // 4
    yy, xx = np.mgrid[0:lh, 0:lw].astype(np.float32)
    nx, ny = (xx / lw - 0.18) / (0.82 * 1.414), (yy / lh - 0.20) / (0.80 * 1.414)
    a_luz = np.clip(1 - np.sqrt(nx * nx + ny * ny) / 0.58, 0, 1)[..., None] * P["luz_a"]
    ang = math.radians(110)
    tt = ((xx / lw - 0.5) * math.sin(ang) * lw - (yy / lh - 0.5) * math.cos(ang) * lh)
    tt = tt / (abs(math.sin(ang)) * lw + abs(math.cos(ang)) * lh) + 0.5
    a_som = np.clip((tt - 0.4) / 0.6, 0, 1)[..., None] * 0.082
    parede = np.array(d.cor(P["parede"])[:3], np.float32)
    parede = parede * (1 - a_luz) + np.array(d.cor(P["luz"])[:3], np.float32) * a_luz
    parede = parede * (1 - a_som)
    base = np.dstack([np.clip(parede, 0, 255), np.full((lh, lw, 1), 255, np.float32)]).astype(np.uint8)
    img = Image.fromarray(base, "RGBA").resize((w, h), Image.BILINEAR)
    del base, parede, a_luz, a_som, yy, xx, nx, ny, tt
    dr = ImageDraw.Draw(img)
    # moldura de parede (duas linhas)
    lt = max(2, int(0.0028 * U))
    x0, y0, x1, y1 = 0.088 * w, 0.0625 * h, 0.69 * w, 0.547 * h
    dr.rectangle((x0, y0, x1, y1), outline=d.cor(P["moldura"]), width=lt)
    ins = 0.0194 * U
    dr.rectangle((x0 + ins, y0 + ins, x1 - ins, y1 - ins), outline=d.cor(P["moldura"]), width=lt)
    # janela à direita, girada em perspectiva (rotateY -16°)
    jw, jh = 0.273 * U, 0.589 * h
    jan = _janela(P, jw, jh, U)
    cxj, cyj = (0.796 + 0.273 / 2) * w, (0.104 + 0.589 / 2) * h
    cantos = np.array([(-jw / 2, -jh / 2), (jw / 2, -jh / 2), (jw / 2, jh / 2), (-jw / 2, jh / 2)])
    b = math.radians(-16)
    dd = 1.0185 * U
    x2 = cantos[:, 0] * math.cos(b)
    z2 = -cantos[:, 0] * math.sin(b)
    f = dd / (dd - z2)
    quad = np.stack([cxj + x2 * f, cyj + cantos[:, 1] * f], axis=1)
    _sombra_quad(img, quad, (-0.037 * U, 0.022 * U), 0.03 * U, "#24282B", 0.13)
    _colar_quad(img, jan, quad)
    # piso
    yp = 0.7135 * h
    dr.rectangle((0, yp, w, h), fill=d.cor(P["piso"]))
    dr.rectangle((0, yp, w, yp + 0.00625 * h), fill=d.cor(P["piso_borda"]))
    # sofá: encosto com sombra + assento
    sx0, sx1, sy0, sy1 = -0.083 * w, 1.083 * w, 0.667 * h, 0.922 * h
    sw_, sh_ = sx1 - sx0, sy1 - sy0
    m_sofa = _ret_arred(sw_, sh_, 0.102 * U, 0.042 * U)
    q = np.array([(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)])
    _sombra_quad(img, q, (0, 0.018 * h), 0.028 * U, "#000000", 0.13)
    sofa = _gradiente_v(int(sw_), int(sh_), P["sofa"][0], P["sofa"][1])
    sofa.putalpha(m_sofa)
    d.colar_em(img, sofa, (sx0, sy0))
    ax0, ax1, ay0, ay1 = 0.0185 * w, 0.981 * w, 0.747 * h, 0.875 * h
    real = d.painel(ax1 - ax0, ay1 - ay0, int(0.0556 * U), fundo=d.cor("#FFFFFF", 0.13))
    img.alpha_composite(real, (int(ax0), int(ay0)))
    ass = d.painel(ax1 - ax0, ay1 - ay0 - 0.002 * h, int(0.0556 * U), fundo=P["assento"])
    img.alpha_composite(ass, (int(ax0), int(ay0 + 0.002 * h)))
    # luminária à esquerda (haste, cúpula e brilho)
    brilho = Image.new("RGBA", (int(0.6 * U), int(0.5 * U)), (0, 0, 0, 0))
    ImageDraw.Draw(brilho).ellipse((0.15 * U, 0.12 * U, 0.45 * U, 0.38 * U), fill=d.cor("#FFF0BF", 0.33))
    brilho = brilho.filter(ImageFilter.GaussianBlur(0.06 * U))
    d.colar(img, brilho, (0.042 * w, 0.354 * h))
    dr = ImageDraw.Draw(img)
    dr.rectangle((0.037 * w, 0.354 * h, 0.0435 * w, 0.573 * h), fill=d.cor(P["poste"]))
    # cúpula = meia elipse em cima + retângulo embaixo (border-radius 50% 50% 0 0 da prévia)
    cx0, cx1, cy0, cy1 = -0.042 * w, 0.125 * w, 0.318 * h, 0.39 * h
    dr.ellipse((cx0, cy0, cx1, cy1), fill=d.cor(P["cupula"]))
    dr.rectangle((cx0, (cy0 + cy1) / 2, cx1, cy1), fill=d.cor(P["cupula"]))
    out = img.resize((W, H), Image.LANCZOS)
    g.cache[chave] = out
    return out


def _fundo(c, tipo, arr_fonte=None):
    if tipo == "video":
        # o próprio vídeo, ampliado, desfocado e escurecido nas bordas (tudo em 1/4 da resolução)
        W, H = c.W, c.H
        if cv2 is not None:
            # 1/8 da resolução: o desfoque é forte, então não perde nada e fica 4x mais leve
            # RGBA inteiro (contíguo: o OpenCV não precisa copiar); o alfa continua 255
            fonte = arr_fonte if arr_fonte is not None else np.asarray(c.fonte)
            arr = cv2.resize(fonte, (math.ceil(W / 8), math.ceil(H / 8)), interpolation=cv2.INTER_AREA)
            arr = cv2.GaussianBlur(arr, (0, 0), max(1.5, W / 8 * 0.045))
            h, w = arr.shape[:2]
            ch = ("06escvid4", (w, h))
            if ch not in c.g.cache:
                yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
                dist = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
                fator = 0.58 * (1 - np.clip((dist - 0.55) / 0.85, 0, 1) ** 1.6 * 0.5)
                f4 = np.repeat(np.round(fator * 256).astype(np.uint16)[..., None], 4, axis=2)
                f4[..., 3] = 256
                c.g.cache[ch] = f4
            arr = np.minimum(arr.astype(np.uint16) * c.g.cache[ch] >> 8, 255).astype(np.uint8)
            arr = cv2.resize(arr, (W, H), interpolation=cv2.INTER_LINEAR)
            return Image.fromarray(arr, "RGBA")
        peq = c.fonte.reduce(4).filter(ImageFilter.GaussianBlur(max(2, W / 4 * 0.045)))
        ch = ("06escvid", peq.size)
        if ch not in c.g.cache:
            h, w = peq.height, peq.width
            yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
            dist = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
            fator = 0.58 * (1 - np.clip((dist - 0.55) / 0.85, 0, 1) ** 1.6 * 0.5)
            c.g.cache[ch] = np.round(fator * 256).astype(np.uint16)[..., None]
        arr = np.array(peq)
        arr[..., :3] = (arr[..., :3].astype(np.uint16) * c.g.cache[ch] >> 8).astype(np.uint8)
        return Image.fromarray(arr, "RGBA").resize((W, H), Image.BILINEAR)
    return _sala(c.g, tipo).copy()


# ---------------------------------------------------------------- o celular pré-desenhado

def _icone_balao(tam, cor):
    S = tam * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse((S * .1, S * .12, S * .9, S * .78), fill=d.cor(cor))
    dr.polygon([(S * .22, S * .62), (S * .14, S * .92), (S * .46, S * .74)], fill=d.cor(cor))
    return im.resize((tam, tam), Image.LANCZOS)


def _icone_aviao(tam, cor):
    S = tam * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon([(S * .1, S * .45), (S * .9, S * .12), (S * .62, S * .9), (S * .48, S * .56)],
                               fill=d.cor(cor))
    return im.resize((tam, tam), Image.LANCZOS)


def _icone_marcador(tam, cor):
    S = tam * 4
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon([(S * .24, S * .1), (S * .76, S * .1), (S * .76, S * .9), (S * .5, S * .68),
                                (S * .24, S * .9)], fill=d.cor(cor))
    return im.resize((tam, tam), Image.LANCZOS)


def _celular(g, n, escuro=False):
    """Celular pré-desenhado: sombra suave, corpo, aro, botões, barra de status e barra de baixo, com a
    área do vídeo vazada. Desenhado uma vez (por fator de redução n) e reaproveitado em todos os quadros.
    A resolução é W/n px por unidade: o quadro reduzido por n cabe EXATO no furo da tela, e celular +
    vídeo são distorcidos juntos numa só operação. A sombra acompanha a inclinação (box-shadow da prévia)."""
    sr = g.W / n
    chave = ("06fone", n, bool(escuro), g.W, g.H)
    if chave in g.cache:
        return g.cache[chave]
    if n == 1:
        return _celular_ampliado(g, escuro, chave)
    A, bw, bh, vy0 = _dims(g.W, g.H)
    S = 2
    k = sr * S
    Wi, Hi = int(round((bw + M_ESQ + M_DIR) * k)), int(round((bh + M_TOPO + M_BASE) * k))
    img = Image.new("RGBA", (Wi, Hi), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)

    def P(x, y):
        return ((x + bw / 2 + M_ESQ) * k, (y + bh / 2 + M_TOPO) * k)

    def ret(x0, y0, x1, y1, raio, **kw):
        (a, b), (c_, e) = P(x0, y0), P(x1, y1)
        dr.rounded_rectangle((a, b, c_, e), radius=max(0, int(raio * k)), **kw)

    # botões laterais (ficam um pouco para fora do corpo)
    lado = "#2A3235"
    ret(-bw / 2 - 0.012, -bh / 2 + 0.36, -bw / 2 + 0.01, -bh / 2 + 0.43, 0.006, fill=lado)
    ret(-bw / 2 - 0.012, -bh / 2 + 0.50, -bw / 2 + 0.01, -bh / 2 + 0.66, 0.006, fill=lado)
    ret(-bw / 2 - 0.012, -bh / 2 + 0.70, -bw / 2 + 0.01, -bh / 2 + 0.86, 0.006, fill=lado)
    ret(bw / 2 - 0.01, -bh / 2 + 0.56, bw / 2 + 0.012, -bh / 2 + 0.80, 0.006, fill=lado)
    # corpo + aro claro na borda (inset 4px da prévia)
    ret(-bw / 2, -bh / 2, bw / 2, bh / 2, R_CORPO, fill=d.cor(CORPO))
    ret(-bw / 2, -bh / 2, bw / 2, bh / 2, R_CORPO, outline=d.cor(ARO), width=max(2, int(0.0095 * k)))
    # tela (fundo escuro da interface)
    sy0, sy1 = -bh / 2 + BORDA, bh / 2 - BORDA
    ret(-0.5, sy0, 0.5, sy1, R_TELA, fill=d.cor(UI_FUNDO))
    # barra de status: ilha, ponto verde da câmera, sinal, wi-fi e bateria (sem texto)
    yc = sy0 + TOPO * 0.52
    ret(-0.165, yc - 0.037, 0.165, yc + 0.037, 0.037, fill=d.cor("#090E10"))
    (a, b), (c_, e) = P(0.198, yc - 0.012), P(0.222, yc + 0.012)
    dr.ellipse((a, b, c_, e), fill=d.cor(LIMA))
    claro = d.cor(UI_TEXTO)
    for i in range(4):
        hh = 0.014 + i * 0.006
        x0 = -0.42 + i * 0.019
        ret(x0, yc + 0.02 - hh, x0 + 0.012, yc + 0.02, 0.003, fill=claro)
    (a, b), (c_, e) = P(0.285, yc - 0.03), P(0.345, yc + 0.03)
    for j, rr in enumerate((1.0, 0.66, 0.33)):
        cx_, cy_ = (a + c_) / 2, e
        R = (c_ - a) / 2 * rr
        dr.pieslice((cx_ - R, cy_ - R, cx_ + R, cy_ + R), 225, 315, fill=claro)
        if j < 2:
            R2 = R - 0.009 * k
            dr.pieslice((cx_ - R2, cy_ - R2, cx_ + R2, cy_ + R2), 225, 315, fill=d.cor(UI_FUNDO))
    ret(0.37, yc - 0.017, 0.435, yc + 0.017, 0.007, outline=claro, width=max(1, int(0.005 * k)))
    ret(0.377, yc - 0.010, 0.418, yc + 0.010, 0.003, fill=claro)
    ret(0.438, yc - 0.006, 0.446, yc + 0.006, 0.002, fill=claro)
    # barra de baixo: trilho da linha de progresso, ícones e indicador de início
    vb = vy0 + A
    ret(-0.44, vb + 0.026, 0.44, vb + 0.038, 0.006, fill=d.cor(UI_TRILHO))
    tam = int(0.07 * k)
    yi = vb + 0.092
    cor_ic = "#C9D3CB"
    icones = [d.icone("coracao", tam, cor_ic), _icone_balao(tam, cor_ic), _icone_aviao(tam, cor_ic),
              _icone_marcador(tam, cor_ic)]
    for i, ic in enumerate(icones):
        px, py = P(-0.36 + i * 0.24, yi)
        img.alpha_composite(ic, (int(px - tam / 2), int(py - tam / 2)))
    ret(-0.1775, sy1 - 0.036, 0.1775, sy1 - 0.024, 0.006, fill=d.cor("#FFFFFF", 0.47))
    fone = img.resize((max(1, Wi // S), max(1, Hi // S)), Image.LANCZOS)
    k1 = k / S

    def P1(x, y):
        return ((x + bw / 2 + M_ESQ) * k1, (y + bh / 2 + M_TOPO) * k1)

    # sombra: silhueta do corpo, deslocada e desfocada (em 1/4 da resolução)
    r = 4
    m = Image.new("L", (max(1, fone.width // r), max(1, fone.height // r)), 0)
    (a, b), (c_, e) = P1(-bw / 2 + SOMBRA_DX, -bh / 2 + SOMBRA_DY), P1(bw / 2 + SOMBRA_DX, bh / 2 + SOMBRA_DY)
    cor_s, alfa_s = (("#000000", 0.5) if escuro else ("#26352C", 0.3))
    ImageDraw.Draw(m).rounded_rectangle((a / r, b / r, c_ / r, e / r), radius=int(R_CORPO * k1 / r),
                                        fill=int(255 * alfa_s))
    m = m.filter(ImageFilter.GaussianBlur(SOMBRA_SIGMA * k1 / r)).resize(fone.size, Image.BILINEAR)
    out = Image.new("RGBA", fone.size, d.cor(cor_s, 1.0))
    out.putalpha(m)
    out.alpha_composite(fone)
    # área do vídeo vazada: exatamente do tamanho do quadro reduzido por n
    (a, b) = P1(-0.5, vy0)
    fx, fy = int(round(a)), int(round(b))
    fw, fh = math.ceil(g.W / n), math.ceil(g.H / n)
    ImageDraw.Draw(out).rectangle((fx, fy, fx + fw - 1, fy + fh - 1), fill=(0, 0, 0, 0))
    # brilho do vidro (faixa clara à esquerda, como a prévia): aplicado por cima do vídeo a cada quadro
    (gx0, gy0), (gx1, gy1) = P1(-0.5 + 0.035, sy0 + 0.06), P1(-0.5 + 0.15, sy1 - 0.14)
    gw, gh = int(gx1 - gx0), int(gy1 - gy0)
    brilho = None
    if gw > 2 and gh > 2:
        alfa = (np.linspace(1, 0, gw, dtype=np.float32) ** 1.4)[None, :] * 0.085
        alfa = alfa * (np.asarray(d.mascara_arredondada(gw, gh, int(0.06 * k1)), dtype=np.float32) / 255)
        brilho = (int(gx0), int(gy0), np.round(alfa * 256).astype(np.uint16)[..., None])
    # pixels transparentes recebem a cor da moldura: a interpolação não cria contorno claro/escuro
    arr = np.array(out)
    vazio = arr[..., 3] == 0
    arr[vazio, 0], arr[vazio, 1], arr[vazio, 2] = 21, 27, 28
    out = Image.fromarray(arr, "RGBA")
    res = {"img": out, "arr": arr, "furo": (fx, fy, fw, fh), "brilho": brilho}
    g.cache[chave] = res
    return res


def _celular_ampliado(g, escuro, chave):
    """Versão em resolução cheia (só aparece no começo/fim da transição, em movimento rápido)."""
    b = _celular(g, 2, escuro)
    im = b["img"].resize((b["img"].width * 2, b["img"].height * 2), Image.BICUBIC)
    fx, fy, _, _ = b["furo"]
    fx, fy, fw, fh = fx * 2, fy * 2, g.W, g.H
    ImageDraw.Draw(im).rectangle((fx, fy, fx + fw - 1, fy + fh - 1), fill=(21, 27, 28, 0))
    brilho = None
    if b["brilho"] is not None:
        x, y, a = b["brilho"]
        brilho = (x * 2, y * 2, np.repeat(np.repeat(a, 2, axis=0), 2, axis=1))
    arr = np.array(im)
    res = {"img": im, "arr": arr, "furo": (fx, fy, fw, fh), "brilho": brilho}
    g.cache[chave] = res
    return res


def _aplicar_brilho(arr, brilho):
    if brilho is None:
        return
    x, y, a = brilho
    h, w = a.shape[:2]
    reg = arr[y:y + h, x:x + w, :3]
    a = a[:reg.shape[0], :reg.shape[1]]
    reg += ((255 - reg.astype(np.uint16)) * a >> 8).astype(np.uint8)


def _colar_celular(img, fone, src, quad):
    """Põe o quadro reduzido (ou a interface do app) no furo da tela, o brilho do vidro por cima e distorce
    tudo de uma vez. Com OpenCV reaproveita um buffer: a cada quadro só o furo e a faixa do brilho são
    reescritos (o resto do celular não muda)."""
    fx, fy, fw, fh = fone["furo"]
    if cv2 is not None:
        arr = fone.get("buf")
        if arr is None:
            arr = fone["buf"] = fone["arr"].copy()
        if fone["brilho"] is not None:   # restaura a faixa do brilho (passa um pouco do furo, na barra de status)
            bx, by, ba = fone["brilho"]
            arr[by:by + ba.shape[0], bx:bx + ba.shape[1]] = fone["arr"][by:by + ba.shape[0], bx:bx + ba.shape[1]]
        fr = src if isinstance(src, np.ndarray) else np.asarray(src)
        arr[fy:fy + min(fh, fr.shape[0]), fx:fx + min(fw, fr.shape[1])] = fr[:fh, :fw]
        _aplicar_brilho(arr, fone["brilho"])
        _distorcer(img, fone["img"], quad, src_np=arr)
        return
    comb = fone["img"].copy()
    if isinstance(src, np.ndarray):
        src = Image.fromarray(np.ascontiguousarray(src[:fh, :fw]), "RGBA")
    comb.paste(src, (fx, fy))
    arr = np.array(comb)
    _aplicar_brilho(arr, fone["brilho"])
    _distorcer(img, comb, quad, src_pm=Image.fromarray(arr, "RGBA").convert("RGBa"))


def _cantos_img(W, H):
    A, bw, bh, vy0 = _dims(W, H)
    x0, y0, x1, y1 = -bw / 2 - M_ESQ, -bh / 2 - M_TOPO, bw / 2 + M_DIR, bh / 2 + M_BASE
    return np.array([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _cantos_corpo(W, H):
    A, bw, bh, vy0 = _dims(W, H)
    return np.array([(-bw / 2, -bh / 2), (bw / 2, -bh / 2), (bw / 2, bh / 2), (-bw / 2, bh / 2)])


# ---------------------------------------------------------------- cenas, poses e composição

def _cenas(g):
    ch = "06cenas"
    if ch not in g.cache:
        g.cache[ch] = sorted([e for e in g.plano["eventos"] if e.get("tipo") == "celular"],
                             key=lambda e: e["inicio"])
    return g.cache[ch]


def _cena_em(g, t):
    for e in _cenas(g):
        if e["inicio"] <= t <= e["fim"]:
            return e
    return None


def _k_cena(e, t):
    """Presença da cena: 0 = tela cheia, 1 = celular assentado (pode passar um pouco de 1 na mola)."""
    ini, fim = e["inicio"], e["fim"]
    if t < ini or t > fim:
        return 0.0, 0.0
    dur = fim - ini
    te, ts = min(T_ENTRA, dur * 0.35), min(T_SAI, dur * 0.3)
    a = d.mapear(t, ini, ini + te)
    ka = d.mola(a, 0.8) if a < 1 else 1.0
    kb = 1 - d.suave(d.mapear(t, fim - ts, fim))
    return ka * kb, kb


def _fase(t):
    f = 2 * math.pi * t / PERIODO
    return math.sin(f), (1 - math.cos(f)) / 2


def _pose_assentada(lay, t, H):
    sw, wv = _fase(t)
    sinal = lay["sinal"]
    return (lay["cx"], lay["cy"] - 0.026 * H * wv, lay["s"], sinal * (-15 + 5 * sw), sinal * (5 + 2 * sw))


def _pose(g, lay, t, k):
    W, H = g.W, g.H
    A, bw, bh, vy0 = _dims(W, H)
    s0 = float(W)
    c0x, c0y = W / 2, H / 2 - (vy0 + A / 2) * s0
    cx1, cy1, s1, ry1, rz1 = _pose_assentada(lay, t, H)
    s = math.exp(d.lerp(math.log(s0), math.log(s1), k))
    return (d.lerp(c0x, cx1, k), d.lerp(c0y, cy1, k), s, ry1 * k, rz1 * k)


def _caixa_proj(g, lay, s, cx, cy):
    """Limites do celular projetado (pior caso do balanço) para uma escala e centro."""
    W, H = g.W, g.H
    cantos = _cantos_corpo(W, H)
    xs, ys = [], []
    for i in range(16):
        fase = 2 * math.pi * i / 16
        sw, wv = math.sin(fase), (1 - math.cos(fase)) / 2
        pose = (cx, cy - 0.026 * H * wv, s, lay["sinal"] * (-15 + 5 * sw), lay["sinal"] * (5 + 2 * sw))
        q = _proj(cantos, pose, W)
        xs += list(q[:, 0])
        ys += list(q[:, 1])
    return min(xs), min(ys), max(xs), max(ys)


def _modo(g, e):
    """'pessoa' (composição da prévia: pessoa recortada na sala + interface dentro do celular) quando há
    recorte; 'tela' (o vídeo vira a tela do celular) quando não há recorte ou o plano pede."""
    pedido = e.get("modo")
    tem = bool(getattr(g, "tem_mascara", False))
    if pedido == "tela" or not tem:
        return "tela"
    return "pessoa"


def _layout(g, e):
    """Onde ficam título, legenda, celular (e a pessoa, no modo 'pessoa') nesta cena (calculado uma vez)."""
    chave = ("06lay", e["inicio"], e["fim"])
    if chave in g.cache:
        return g.cache[chave]
    W, H = g.W, g.H
    fundo = e.get("fundo", "sala") if e.get("fundo", "sala") in FUNDOS else "sala"
    lado = e.get("lado", "direita") if e.get("lado", "direita") in LADOS else "direita"
    titulo = str(e.get("titulo") or "").strip()
    tit = _titulo(g, titulo, fundo) if titulo else None
    y_tit = 0.118 * H
    y_leg = y_tit + (tit.height + 0.026 * H if tit else 0)
    leg = g.cache.get("06leg")
    alt_leg = leg.altura_caixa if leg is not None else 0.0
    y_livre = y_leg + (alt_leg if leg is not None else (0.0 if tit else -0.03 * H))
    lay = {"sinal": 1 if lado == "direita" else -1, "lado": lado, "fundo": fundo, "tit": tit,
           "y_tit": y_tit, "y_leg": y_leg, "y_livre": y_livre, "modo": _modo(g, e)}
    if lay["modo"] == "pessoa":
        _layout_pessoa(g, e, lay)
    else:
        _layout_tela(g, e, lay)
    g.cache[chave] = lay
    return lay


def _encaixar_celular(g, lay, s, topo, baixo, x_borda, larg_max, embaixo=False):
    """Ajusta escala e centro do celular para caber entre topo/baixo, encostado em x_borda (lado do celular).
    embaixo=True: se sobrar altura, o celular desce até 'baixo' (em vez de ficar encostado no topo)."""
    W = g.W
    A, bw, bh, vy0 = _dims(g.W, g.H)
    cx, cy = W * (0.6 if lay["sinal"] > 0 else 0.4), (topo + baixo) / 2
    for _ in range(4):
        x0, y0, x1, y1 = _caixa_proj(g, lay, s, cx, cy)
        s *= min((baixo - topo) / (y1 - y0), larg_max / (x1 - x0))
        x0, y0, x1, y1 = _caixa_proj(g, lay, s, cx, cy)
        cy += (baixo - y1) if embaixo else (topo - y0)
        if lay["sinal"] > 0:
            cx += x_borda - x1
        else:
            cx += x_borda - x0
    return s, cx, cy


def _queixo_proj(g, lay, t0, t1):
    """Pior caso (mais baixo) do queixo projetado dentro da tela do celular, no intervalo (modo 'tela')."""
    W, H = g.W, g.H
    A, bw, bh, vy0 = _dims(W, H)
    queixo = 0.0
    t = max(t0, 0.0)
    while t <= t1 + 1e-6:
        x0, y0, x1, y1 = g.rosto.em(t)
        qy = g.rosto.queixo(t) / H
        pts = np.array([(x0 / W - 0.5, vy0 + qy * A), (x1 / W - 0.5, vy0 + qy * A)])
        q = _proj(pts, _pose_assentada(lay, t, H), W)
        queixo = max(queixo, float(q[:, 1].max()))
        t += 0.2
    return queixo


def _alturas_ui(g, e_cena, escuro):
    """Altura de cada cartão (modo 'tela') desta cena: [(evento, altura)]."""
    out = []
    for ev in g.plano["eventos"]:
        if ev.get("tipo") in TIPOS_UI and e_cena["inicio"] <= ev["inicio"] <= e_cena["fim"]:
            if ev.get("tipo") == "cartao":
                h = _img_cartao(g, ev, escuro)[2]
            elif ev.get("tipo") == "progresso":
                h = _base_progresso(g, ev, escuro)[1]["h"]
            else:
                h = _base_contador(g, ev, escuro)[1]["h"]
            out.append((ev, h))
    return out


def _layout_tela(g, e, lay):
    """Modo 'tela': o vídeo inteiro vira a tela do celular; os cartões ficam do outro lado, abaixo do queixo.
    Se um cartão não couber entre o queixo e 80% da altura, o celular desta cena encolhe até caber."""
    W, H = g.W, g.H
    topo = lay["y_livre"] + 0.02 * H
    baixo = 0.86 * H           # a base do celular (linha de progresso) fora da faixa da descrição do app
    x_borda = 0.872 * W if lay["sinal"] > 0 else 0.128 * W
    A, bw, bh, vy0 = _dims(W, H)
    s, cx, cy = _encaixar_celular(g, lay, (baixo - topo) / bh, topo, baixo, x_borda, 0.64 * W)
    lay.update({"s": s, "cx": cx, "cy": cy})
    uis = _alturas_ui(g, e, lay["fundo"] != "sala")
    for _ in range(8):
        cabe = all(_queixo_proj(g, lay, ev["inicio"], ev["fim"]) + 0.03 * H + h <= 0.80 * H for ev, h in uis)
        if cabe:
            break
        baixo = topo + (baixo - topo) * 0.93
        s, cx, cy = _encaixar_celular(g, lay, lay["s"] * 0.93, topo, baixo, x_borda, 0.64 * W)
        lay.update({"s": s, "cx": cx, "cy": cy})


def _titulo(g, texto, fundo):
    chave = ("06tit", texto, fundo, g.W)
    if chave in g.cache:
        return g.cache[chave]
    W, H = g.W, g.H
    # uma linha sempre que couber com letra grande; senão duas linhas. Largura máxima 0,72 W: o título fica
    # na parte lisa da parede (a janela da sala começa perto de 0,80 W) e longe dos botões da direita.
    larg_max = W * 0.72
    f, linhas, al = d.ajustar_texto(texto, larg_max, H * 0.06, 720, tam_max=int(W * 0.087),
                                    tam_min=int(W * 0.066), max_linhas=1, entrelinha=1.03)
    if len(linhas) > 1 or max(f.getlength(l) for l in linhas) > larg_max:
        f, linhas, al = d.ajustar_texto(texto, larg_max, H * 0.12, 720, tam_max=int(W * 0.08),
                                        tam_min=int(W * 0.058), max_linhas=2, entrelinha=1.03)
    track = -0.035 * f.size
    larg = max(f.getlength(l) + track * (len(l) - 1) for l in linhas)
    pad = int(f.size * 0.5)
    cam = Image.new("RGBA", (int(larg + 2 * pad), int(al * len(linhas) + 2 * pad)), (0, 0, 0, 0))
    cor_t = d.cor(TINTA if fundo == "sala" else CREME)

    def desenhar(alvo, cor_):
        dr = ImageDraw.Draw(alvo)
        for i, l in enumerate(linhas):
            for j, ch in enumerate(l):
                dr.text((pad + f.getlength(l[:j]) + track * j, pad + i * al), ch, font=f, fill=cor_)

    if fundo != "sala":
        sombra = Image.new("RGBA", cam.size, (0, 0, 0, 0))
        desenhar(sombra, (0, 0, 0, 150))
        cam.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(f.size * 0.16)), (0, int(f.size * 0.05)))
    desenhar(cam, cor_t)
    bb = cam.getchannel("A").getbbox() or (0, 0, cam.width, cam.height)
    cam = cam.crop((pad - 2, bb[1], cam.width, bb[3] + 2))
    g.cache[chave] = cam
    return cam


def _quadro_celular(c, e, k, kb):
    g, W, H, t = c.g, c.W, c.H, c.t
    lay = _layout(g, e)
    arr_fonte = np.asarray(c.fonte) if cv2 is not None else None
    img = _fundo(c, lay["fundo"], arr_fonte)
    pose = _pose(g, lay, t, k)
    kk = d.limitar(k)
    escuro = lay["fundo"] != "sala"
    # vídeo dentro do celular: reduz o quadro (nítido e sem serrilhado), encaixa no furo e distorce junto
    r = pose[2] / W
    n = max(1, min(4, int(round(0.9 / max(r, 0.05)))))
    if cv2 is not None:   # redução com OpenCV (área): ~5x mais rápida que o reduce do Pillow, mesma nitidez
        src = arr_fonte
        if n > 1:
            src = cv2.resize(src, (math.ceil(W / n), math.ceil(H / n)), interpolation=cv2.INTER_AREA)
    else:
        src = c.fonte if n == 1 else c.fonte.reduce(n)
    _colar_celular(img, _celular(g, n, escuro), src, _proj(_cantos_img(W, H), pose, W))
    # linha de progresso do próprio vídeo (anda com o tempo real)
    A, bw, bh, vy0 = _dims(W, H)
    vb = vy0 + A
    prog = d.limitar(t / max(0.1, g.duracao))
    if prog > 0.005:
        x1 = -0.44 + 0.88 * prog
        pts = _proj(np.array([(-0.44, vb + 0.026), (x1, vb + 0.026), (x1, vb + 0.038), (-0.44, vb + 0.038)]),
                    pose, W)
        _poligono_suave(img, pts, d.cor(LIMA))
    # título no alto
    tit = lay["tit"]
    if tit is not None:
        a = d.saida(d.mapear(t, e["inicio"] + 0.22, e["inicio"] + 0.7))
        op = a * d.suave(d.limitar((kb - 0.45) / 0.55))   # na saída some antes de o celular crescer
        if op > 0.01:
            d.colar_em(img, tit, (0.074 * W, lay["y_tit"] + (1 - a) * 0.02 * H), opacidade=op)
    # cartões de interface
    for ev in c.eventos:
        if ev.get("tipo") in TIPOS_UI and e["inicio"] <= ev["inicio"] <= e["fim"]:
            _desenhar_ui(c, img, lay, ev, kk)
    return img, lay


# ---------------------------------------------------------------- cartões de interface

def _texto_espacado(dr, xy, txt, f, cor_, track):
    x, y = xy
    for j, ch in enumerate(txt):
        dr.text((x + f.getlength(txt[:j]) + track * j, y), ch, font=f, fill=cor_)


def _larg_espacado(txt, f, track):
    return f.getlength(txt) + track * max(0, len(txt) - 1)


def _base_cartao(g, w, h, escuro):
    W = g.W
    p = d.painel(w, h, raio=int(0.042 * W), fundo=UI_FUNDO, borda=d.cor("#FFFFFF", 0.13 if escuro else 0.09),
                 larg_borda=max(1, round(W * 0.0018)))
    img, off = d.sombra(p, raio=0.026 * W, opacidade=0.42 if escuro else 0.34, desloc=(0.008 * W, 0.022 * W))
    return img, -off[0]


def _img_cartao(g, e, escuro):
    chave = ("06card", e.get("texto"), e.get("detalhe"), e.get("icone"), escuro, g.W)
    if chave in g.cache:
        return g.cache[chave]
    W = g.W
    pad, ic, gap = 0.045 * W, 0.112 * W, 0.034 * W
    det = str(e.get("detalhe") or "").strip().upper()
    txt = str(e.get("texto") or "").strip()
    f_det = d.fonte(int(0.04 * W), 650)
    tr = 0.07 * f_det.size
    fm, linhas, al = d.ajustar_texto(txt, 0.42 * W, 0.2 * W, 800, tam_max=int(0.058 * W), tam_min=int(0.044 * W),
                                     max_linhas=2, entrelinha=1.1)
    tw = max((fm.getlength(l) for l in linhas), default=0)
    dw = _larg_espacado(det, f_det, tr) if det else 0
    dh = f_det.size * 1.35 if det else 0
    th = fm.size * 0.78 + al * (len(linhas) - 1)      # altura visual (da maiúscula até a base)
    bloco = max(tw, dw)
    w = pad + ic + gap + bloco + pad
    h = max(ic, dh + th) + 2 * pad
    img, m = _base_cartao(g, w, h, escuro)
    corpo = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    circ = d.painel(ic, ic, int(ic / 2), fundo=LIMA)
    nome = e.get("icone") if e.get("icone") in ICONES else "check"
    icn = d.icone(nome, int(ic * 0.56), ICONE_TINTA, espessura=0.13)
    circ.alpha_composite(icn, ((circ.width - icn.width) // 2, (circ.height - icn.height) // 2))
    corpo.alpha_composite(circ, (int(pad), int((h - ic) / 2)))
    dr = ImageDraw.Draw(corpo)
    x = pad + ic + gap
    y = (h - (dh + th)) / 2
    if det:
        _texto_espacado(dr, (x, y - f_det.size * 0.2), det, f_det, d.cor(UI_CINZA), tr)
    yb = y + dh + fm.size * 0.78
    for i, l in enumerate(linhas):
        dr.text((x, yb + i * al), l, font=fm, fill=d.cor(UI_TEXTO), anchor="ls")
    img.alpha_composite(corpo, (int(m), int(m)))
    g.cache[chave] = (img, w, h)
    return g.cache[chave]


def _geo_progresso(W):
    # compacto: cabe abaixo do queixo mesmo em plano fechado com título
    w, pad = 0.58 * W, 0.036 * W
    return {"w": w, "pad": pad, "lab": 0.05 * W, "painel_h": 0.07 * W, "barra_h": 0.011 * W, "botao_h": 0.084 * W}


def _base_progresso(g, e, escuro):
    chave = ("06prog", e.get("texto"), escuro, g.W)
    if chave in g.cache:
        return g.cache[chave]
    W = g.W
    G = _geo_progresso(W)
    w, pad = G["w"], G["pad"]
    txt = str(e.get("texto") or "").strip()
    y = pad
    linhas, f = [], None
    if txt:
        f, linhas, al = d.ajustar_texto(txt, w - 2 * pad, 0.08 * W, 800, tam_max=int(0.052 * W),
                                        tam_min=int(0.04 * W), max_linhas=1)
        y_txt = y + f.size * 0.78
        y += f.size * 0.78 + 0.03 * W
    y_painel = y
    y += G["painel_h"] + 0.026 * W
    y_barra = y
    y += G["barra_h"] + 0.032 * W
    y_botao = y
    h = y + G["botao_h"] + pad
    img, m = _base_cartao(g, w, h, escuro)
    corpo = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    dr = ImageDraw.Draw(corpo)
    if linhas:
        dr.text((pad, y_txt), linhas[0], font=f, fill=d.cor(UI_TEXTO), anchor="ls")
    corpo.alpha_composite(d.painel(w - 2 * pad, G["painel_h"], int(0.02 * W), fundo=UI_PAINEL),
                          (int(pad), int(y_painel)))
    corpo.alpha_composite(d.painel(w - 2 * pad, G["barra_h"], int(G["barra_h"] / 2), fundo=UI_TRILHO),
                          (int(pad), int(y_barra)))
    img.alpha_composite(corpo, (int(m), int(m)))
    # blocos da linha do tempo (larguras variadas como na prévia)
    pesos = [54, 74, 94, 54, 74, 94]
    ins, gapb = 0.014 * W, 0.009 * W
    larg_util = w - 2 * pad - 2 * ins - gapb * (len(pesos) - 1)
    xs, x = [], pad + ins
    for p_ in pesos:
        bw_ = larg_util * p_ / sum(pesos)
        xs.append((x, bw_))
        x += bw_ + gapb
    geo = {"m": m, "w": w, "h": h, "pad": pad, "y_painel": y_painel, "y_barra": y_barra, "y_botao": y_botao,
           "blocos": xs, "bloco_y": y_painel + ins, "bloco_h": G["painel_h"] - 2 * ins, "G": G}
    g.cache[chave] = (img, geo)
    return g.cache[chave]


def _misturar(c0, c1, k):
    a, b = d.cor(c0), d.cor(c1)
    return tuple(int(round(a[i] + (b[i] - a[i]) * k)) for i in range(4))


def _conclui(e):
    """Segundo em que a barra enche. O botão "pronto" fica pelo menos ~1 s inteiro na tela (o momento
    principal do cartão); em cartões curtos divide o tempo entre encher e mostrar o "pronto"."""
    ini, fim = e["inicio"], e["fim"]
    dur = fim - ini
    padrao = fim - min(1.2, dur * 0.4)
    try:
        cc = float(e.get("conclui", padrao))
    except (TypeError, ValueError):
        cc = padrao
    if dur >= 1.6:
        return d.limitar(cc, ini + 0.6, fim - 1.0)
    return ini + dur * 0.5


def _img_progresso(c, e, escuro):
    W, t = c.W, c.t
    base, geo = _base_progresso(c.g, e, escuro)
    cc = _conclui(e)
    pronto = ("06progpronto", e["inicio"], escuro, W)
    if t >= cc + 0.32 and pronto in c.g.cache:   # depois do "pronto" o cartão não muda mais
        return c.g.cache[pronto]
    img = base.copy()
    m = geo["m"]
    p = d.suave(d.mapear(t, e["inicio"] + 0.3, cc))
    n = len(geo["blocos"])
    for i, (x, bw_) in enumerate(geo["blocos"]):
        f = round(d.saida(d.limitar(p * n - i)) * 16) / 16
        cor_ = _misturar(UI_BLOCO, LIMA, f)
        img.alpha_composite(_painel_c(c.g, bw_, geo["bloco_h"], 0.008 * W, cor_),
                            (int(m + x), int(m + geo["bloco_y"])))
    G = geo["G"]
    larg = (geo["w"] - 2 * geo["pad"]) * p
    if larg > G["barra_h"]:
        img.alpha_composite(_painel_c(c.g, larg, G["barra_h"], G["barra_h"] / 2, LIMA),
                            (int(m + geo["pad"]), int(m + geo["y_barra"])))
    # botão: "carregando" (três pontos) -> "✓ final" em neon
    bw_ = geo["w"] - 2 * geo["pad"]
    bh_ = G["botao_h"]
    kc = round(d.mapear(t, cc, cc + 0.16) * 8) / 8
    pulo = 1 + 0.06 * math.sin(math.pi * d.mapear(t, cc, cc + 0.3)) if t >= cc else 1.0
    botao = _painel_c(c.g, bw_, bh_, bh_ / 2, _misturar("#F5F7EE", LIMA, kc)).copy()
    db = ImageDraw.Draw(botao)
    if kc < 0.5:
        for j in range(3):
            fase = (t * 2.2 - j * 0.18) % 1.0
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * fase))
            r = bh_ * 0.075
            cx_ = bw_ / 2 + (j - 1) * bh_ * 0.32
            db.ellipse((cx_ - r, bh_ / 2 - r, cx_ + r, bh_ / 2 + r), fill=d.cor(TINTA, a * (1 - 2 * kc)))
    else:
        final = str(e.get("final") or "").strip()
        tam_ic = int(bh_ * 0.5)
        ic = d.icone("check", tam_ic, TINTA, espessura=0.14)
        if final:
            f = d.fonte(int(0.044 * W), 850)
            if f.getlength(final) > bw_ - tam_ic - bh_:
                f, _, _ = d.ajustar_texto(final, bw_ - tam_ic - bh_, bh_, 850, tam_max=int(0.044 * W),
                                          tam_min=int(0.04 * W), max_linhas=1)
            tw = f.getlength(final)
            x0 = (bw_ - (tam_ic + 0.02 * W + tw)) / 2
            botao.alpha_composite(ic, (int(x0), int((bh_ - tam_ic) / 2)))
            db.text((x0 + tam_ic + 0.02 * W, bh_ / 2 + f.size * 0.36), final, font=f, fill=d.cor(TINTA), anchor="ls")
        else:
            botao.alpha_composite(ic, (int((bw_ - tam_ic) / 2), int((bh_ - tam_ic) / 2)))
    if abs(pulo - 1) > 0.002:
        botao = botao.resize((int(bw_ * pulo), int(bh_ * pulo)), Image.BICUBIC)
    img.alpha_composite(botao, (int(m + geo["pad"] + (bw_ - botao.width) / 2),
                                int(m + geo["y_botao"] + (bh_ - botao.height) / 2)))
    if t >= cc + 0.32 and d.mapear(t, e["inicio"] + 0.3, cc) >= 1:
        c.g.cache[pronto] = (img, geo["w"], geo["h"])
    return img, geo["w"], geo["h"]


def _numero(v, casas):
    s = f"{abs(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + s


def _valor(e):
    try:
        v = float(str(e.get("valor", 0)).replace(" ", ""))
    except ValueError:
        v = 0.0
    txt = str(e.get("valor", ""))
    casas = 0
    if "." in txt and not isinstance(e.get("valor"), int):
        casas = min(2, len(txt.split(".")[-1]))
    return v, casas


def _base_contador(g, e, escuro):
    chave = ("06cont", e.get("texto"), e.get("valor"), e.get("antes"), e.get("depois"), escuro, g.W)
    if chave in g.cache:
        return g.cache[chave]
    W = g.W
    pad = 0.05 * W
    rot = str(e.get("texto") or "").strip().upper()
    antes = str(e.get("antes") or "").strip()
    depois = str(e.get("depois") or "").strip()
    v, casas = _valor(e)
    f_rot = d.fonte(int(0.04 * W), 650)
    tr = 0.07 * f_rot.size
    tam_n = int(0.13 * W)
    while True:
        f_n = d.fonte(tam_n, 850)
        f_a = d.fonte(int(tam_n * 0.46), 800)
        larg_final = (f_a.getlength(antes + " ") if antes else 0) + f_n.getlength(_numero(v, casas)) + \
                     (f_a.getlength(" " + depois) if depois else 0)
        if larg_final <= 0.62 * W or tam_n <= int(0.07 * W):
            break
        tam_n = int(tam_n * 0.92)
    rot_w = _larg_espacado(rot, f_rot, tr) if rot else 0
    w = max(0.42 * W, max(rot_w, larg_final) + 2 * pad)
    y = pad
    y_rot = y
    if rot:
        y += f_rot.size * 1.5
    y_base = y + f_n.size * 0.74
    y_barra = y_base + 0.03 * W
    h = y_barra + 0.01 * W + pad * 0.9
    img, m = _base_cartao(g, w, h, escuro)
    corpo = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    dr = ImageDraw.Draw(corpo)
    if rot:
        _texto_espacado(dr, (pad, y_rot - f_rot.size * 0.2), rot, f_rot, d.cor(UI_CINZA), tr)
    corpo.alpha_composite(d.painel(0.09 * W, 0.011 * W, int(0.0055 * W), fundo=LIMA), (int(pad), int(y_barra)))
    img.alpha_composite(corpo, (int(m), int(m)))
    geo = {"m": m, "w": w, "h": h, "pad": pad, "y_base": y_base, "f_n": f_n, "f_a": f_a, "antes": antes,
           "depois": depois, "v": v, "casas": casas}
    g.cache[chave] = (img, geo)
    return g.cache[chave]


def _img_contador(c, e, escuro):
    base, geo = _base_contador(c.g, e, escuro)
    t = c.t
    dur = min(1.1, 0.5 * (e["fim"] - e["inicio"]))
    k = d.saida(d.mapear(t, e["inicio"], e["inicio"] + dur))
    pronto = ("06contpronto", e["inicio"], escuro, c.W)
    if k >= 0.999 and pronto in c.g.cache:
        return c.g.cache[pronto]
    img = base.copy()
    v = geo["v"] * k
    txt_n = _numero(v if geo["casas"] else round(v), geo["casas"])
    dr = ImageDraw.Draw(img)
    x = geo["m"] + geo["pad"]
    y = geo["m"] + geo["y_base"]
    if geo["antes"]:
        dr.text((x, y), geo["antes"] + " ", font=geo["f_a"], fill=d.cor(UI_TEXTO), anchor="ls")
        x += geo["f_a"].getlength(geo["antes"] + " ")
    dr.text((x, y), txt_n, font=geo["f_n"], fill=d.cor(LIMA), anchor="ls")
    x += geo["f_n"].getlength(txt_n)
    if geo["depois"]:
        dr.text((x, y), " " + geo["depois"], font=geo["f_a"], fill=d.cor(UI_TEXTO), anchor="ls")
    if k >= 0.999:
        c.g.cache[pronto] = (img, geo["w"], geo["h"])
    return img, geo["w"], geo["h"]


def _fim_efetivo(g, e):
    """Um cartão por vez: se o próximo entra antes, este sai junto."""
    chave = ("06fimui", e.get("tipo"), e["inicio"])
    if chave not in g.cache:
        fim = e["fim"]
        for o in g.plano["eventos"]:
            if o.get("tipo") in TIPOS_UI and e["inicio"] < o["inicio"] < fim:
                fim = o["inicio"] + 0.12
        g.cache[chave] = fim
    return g.cache[chave]


def _lugar_ui(c, lay, e, w, h):
    """Posição do cartão (modo 'tela'): do lado oposto ao celular, sempre abaixo do queixo (o rosto na tela
    nunca é coberto) e acima de 80% da altura (zona segura). O layout da cena já encolheu o celular para o
    cartão caber; aqui só um ajuste fino (no máximo 3% menor) e, em último caso, a base passa um pouco dos
    80% — nunca sobe por cima do rosto."""
    g, W, H = c.g, c.W, c.H
    chave = ("06lugar", e.get("tipo"), e["inicio"], int(w), int(h))
    if chave in g.cache:
        return g.cache[chave]
    queixo = _queixo_proj(g, lay, e["inicio"], e["fim"])
    topo = max(0.5 * H, queixo + 0.03 * H)
    lim = 0.80 * H
    esc = 1.0
    if topo + h > lim:
        esc = max(0.97, (lim - topo) / h)
    if lay["lado"] == "direita":
        x = 0.065 * W
    else:
        x = 0.872 * W - w * esc
    g.cache[chave] = (x, topo, esc)
    return g.cache[chave]


def _desenhar_ui(c, img, lay, e, kk):
    t, W, H = c.t, c.W, c.H
    fim = _fim_efetivo(c.g, e)
    if t < e["inicio"] or t > fim:
        return
    escuro = lay["fundo"] != "sala"
    tipo = e.get("tipo")
    if tipo == "cartao":
        cam, w, h = _img_cartao(c.g, e, escuro)
    elif tipo == "progresso":
        cam, w, h = _img_progresso(c, e, escuro)
    else:
        cam, w, h = _img_contador(c, e, escuro)
    x, y, esc = _lugar_ui(c, lay, e, w, h)
    a = d.mapear(t, e["inicio"], e["inicio"] + 0.42)
    op = d.saida(d.mapear(t, e["inicio"], e["inicio"] + 0.18))
    sc = esc * (0.86 + 0.14 * d.mola(a, 1.25))
    dx = (1 - d.saida(a)) * 0.07 * W * lay["sinal"]
    b = d.mapear(t, fim - 0.28, fim)
    op *= 1 - d.entrada(b)
    dy = d.entrada(b) * 0.02 * H + 0.0035 * H * math.sin(2 * math.pi * t / 3.4 + e["inicio"])
    sc *= 1 - 0.05 * b
    op *= d.limitar(kk * 1.3)
    centro = (x + w * esc / 2 + dx, y + h * esc / 2 + dy)
    d.colar(img, cam, centro, escala=sc, opacidade=op)


# ---------------------------------------------------------------- modo "pessoa": a composição da prévia aprovada
# A pessoa recortada fica grande na sala (do lado oposto ao celular, abaixo do título e da legenda) e o
# celular flutua ao lado mostrando a interface do app. O celular fica NA FRENTE do corpo (esconde o corte
# lateral do vídeo) e a cabeça é redesenhada por cima dele: o rosto nunca é coberto.

ROSTO_ALVO = 0.30      # largura da caixa do rosto na cena (fração de W); a prévia mostra a pessoa grande
UI_SKEL = "#334043"    # "esqueleto" da interface (linhas sem texto enquanto nenhum cartão está na tela)
UI_CAIXA = "#2F3B3B"   # painel interno (mesmo da prévia)
# A cabeça de verdade (cabelo, boné, orelhas) passa da caixa do rosto do detector: medido em vídeos reais,
# até ~0,2 da largura do rosto para cada lado. Do lado da borda do quadro usamos uma folga maior (a borda
# não perdoa: o que passar dela é cortado); do lado do celular a cabeça ainda é redesenhada por cima dele.
EXTRA_FORA = 0.30
EXTRA_DENTRO = 0.20
MARGEM_LAT = 0.06      # zona segura lateral: a cabeça fica sempre a pelo menos 6% da borda do quadro
SP_MIN = 0.40          # menor escala da pessoa (rosto muito grande no vídeo original)
LARG_FONE = 0.42       # largura mínima do celular (fração de W) para a interface ficar legível
FOLGA_FONE = 0.02      # espaço entre a cabeça e o celular (fração de W)


def _estat_rosto(g, t0, t1):
    W = g.W
    cxs, largs, x0s, x1s, topos, queixos = [], [], [], [], [], []
    t = max(0.0, t0)
    while t <= t1 + 1e-6:
        x0, y0, x1, y1 = g.rosto.em(t)
        cxs.append((x0 + x1) / 2)
        largs.append(x1 - x0)
        x0s.append(x0)
        x1s.append(x1)
        topos.append(g.rosto.topo_cabeca(t))
        queixos.append(g.rosto.queixo(t))
        t += 0.2
    return {"cx": float(np.median(cxs)), "larg": max(0.05 * W, float(np.median(largs))),
            "x0m": float(np.median(x0s)), "x1m": float(np.median(x1s)),
            "x0": float(np.percentile(x0s, 8)), "x1": float(np.percentile(x1s, 92)),
            "x0e": float(np.percentile(x0s, 3)), "x1e": float(np.percentile(x1s, 97)),
            "topo": float(np.percentile(topos, 8)), "queixo": float(np.percentile(queixos, 92))}


def _layout_pessoa(g, e, lay):
    """Escala e posição da pessoa e do celular na cena. Regras, nesta ordem:
    1. a cabeça inteira (com cabelo/boné, no pior caso da cena) fica a pelo menos 6% das bordas laterais;
    2. entre a cabeça e a borda do celular cabe um celular de pelo menos 0,42 W (interface legível);
    3. a base do vídeo chega à base do quadro (o corpo sai por baixo, sem corte reto visível) e o topo da
       cabeça fica abaixo do título e da legenda; o queixo nunca desce além de 80% da altura;
    4. o rosto fica o maior possível (até ~30% da largura).
    Em plano fechado o rosto fica menor que no vídeo original (~24% da largura) e a pessoa fica de pé na
    parte de baixo da sala, como na prévia aprovada."""
    W, H = g.W, g.H
    est = _estat_rosto(g, e["inicio"], e["fim"])
    sinal = lay["sinal"]
    lw = est["larg"]
    y_cab = lay["y_livre"] + 0.075 * H          # o topo da cabeça não sobe além daqui
    larg_min = LARG_FONE * W
    gap = FOLGA_FONE * W
    x_fone = 0.90 * W if sinal > 0 else 0.10 * W   # borda de fora do celular
    # extensão da cabeça no vídeo original (pixels), do lado da borda (fora) e do lado do celular (dentro)
    if sinal > 0:     # celular à direita, pessoa à esquerda
        fora, dentro = est["x0e"] - EXTRA_FORA * lw, est["x1e"] + EXTRA_DENTRO * lw
        util = x_fone - MARGEM_LAT * W
    else:
        fora, dentro = est["x1e"] + EXTRA_FORA * lw, est["x0e"] - EXTRA_DENTRO * lw
        util = (W - MARGEM_LAT * W) - x_fone
    larg_cab = max(1.0, abs(dentro - fora))
    sp_cabe = (util - gap - larg_min) / larg_cab        # cabeça + folga + celular cabem lado a lado
    sp = d.limitar(min(ROSTO_ALVO * W / lw, sp_cabe), SP_MIN, 0.9)
    # horizontal: o ideal é a borda de fora do vídeo ficar fora do quadro (esconde o corte lateral do vídeo);
    # a cabeça nunca passa da margem segura (prioridade) e o celular fica com o espaço dele
    if sinal > 0:
        ox_cab = MARGEM_LAT * W - sp * fora              # mínimo: cabeça a 6% da borda esquerda
        ox_fone = x_fone - larg_min - gap - sp * dentro   # máximo: espaço do celular
        ox = max(ox_cab, min(0.0, ox_fone))
        livre = x_fone - (ox + sp * dentro + gap)
    else:
        ox_cab = (W - MARGEM_LAT * W) - sp * fora         # máximo: cabeça a 6% da borda direita
        ox_fone = x_fone + larg_min + gap - sp * dentro   # mínimo: espaço do celular
        ox = min(ox_cab, max(W - sp * W, ox_fone))
        livre = (ox + sp * dentro - gap) - x_fone
    # vertical: a pessoa "de pé" na sala, com a base do vídeo na base do quadro
    oy = max(y_cab - sp * est["topo"], H - sp * H)
    oy = min(oy, 0.80 * H - sp * est["queixo"])          # o rosto nunca entra na faixa de baixo
    lay.update({"sp": sp, "ox": ox, "oy": oy, "est": est, "fechado": lw > 0.38 * W})
    # a base do celular pode passar um pouco dos 80% (só a barra de ícones); a interface fica acima
    topo_f = lay["y_livre"] + 0.025 * H
    baixo_f = 0.83 * H
    A, bw, bh, vy0 = _dims(W, H)
    # plano fechado: o celular desce (se sobrar altura) e fica na frente do lado de dentro do corpo
    s, cx, cy = _encaixar_celular(g, lay, (baixo_f - topo_f) / bh, topo_f, baixo_f, x_fone,
                                  max(0.36 * W, min(livre, 0.47 * W)), embaixo=lay["fechado"])
    lay.update({"s": s, "cx": cx, "cy": cy})


def _escalar(arr, tw, th):
    if cv2 is not None:
        return cv2.resize(arr, (tw, th), interpolation=cv2.INTER_AREA if tw < arr.shape[1] else cv2.INTER_LINEAR)
    modo = "L" if arr.ndim == 2 else "RGBA"
    return np.asarray(Image.fromarray(arr, modo).resize((tw, th), Image.BILINEAR if tw >= arr.shape[1]
                                                         else Image.BOX))


def _rampa_bordas(alfa, tw, th, vx0, vy0, rw):
    """Some suave com as bordas esquerda/direita/baixo do vídeo escalado (o topo não), mexendo só nas faixas
    perto das bordas. alfa = recorte (vy0.., vx0..) do canal alfa do vídeo escalado (tw x th)."""
    k = max(1, int(rw))
    h, w = alfa.shape
    for borda, eixo in ((0, 1), (tw, 1), (th, 0)):
        ini = vx0 if eixo == 1 else vy0
        n = w if eixo == 1 else h
        pos = ini + np.arange(n)
        dist = pos if borda == 0 else (borda - 1 - pos)
        sel = np.nonzero(dist < k)[0]
        if len(sel) == 0:
            continue
        f = (np.clip(dist[sel] / k, 0, 1) ** 1.5).astype(np.float32)
        if eixo == 1:
            alfa[:, sel] = (alfa[:, sel] * f[None, :]).astype(np.uint8)
        else:
            alfa[sel, :] = (alfa[sel, :] * f[:, None]).astype(np.uint8)


def _rampa_lados_corpo(alfa, tw, vx0, r_ini, rw):
    """Plano fechado: o corpo some devagar perto das laterais do vídeo (rampa larga e suave), só abaixo do
    queixo (r_ini = linha do recorte), entrando aos poucos para não marcar uma linha. A cabeça não é tocada."""
    k = max(2, int(rw))
    h, w = alfa.shape
    r_ini = max(0, int(r_ini))
    if r_ini >= h:
        return
    pos = vx0 + np.arange(w)
    dist = np.minimum(pos, tw - 1 - pos)
    sel = np.nonzero(dist < k)[0]
    if len(sel) == 0:
        return
    x = np.clip(dist[sel] / k, 0, 1)
    f = (x * x * (3 - 2 * x)).astype(np.float32)                        # 0 na borda do vídeo, 1 dentro
    lin = np.clip(np.arange(h - r_ini, dtype=np.float32) / max(1.0, 0.5 * k), 0, 1)[:, None]
    fator = 1 - lin * (1 - f[None, :])                                  # entra aos poucos abaixo do queixo
    alfa[r_ini:, sel] = (alfa[r_ini:, sel] * fator).astype(np.uint8)


def _fechar_pescoco(m, rosto, sc, vx0, vy0):
    """Plano fechado: o recorte às vezes 'descola' a cabeça do corpo (faixa vazia no pescoço, comum quando
    há textos ou telas gravados na frente do peito) ou deixa o peito meio transparente. Nas colunas do rosto,
    do meio do rosto para baixo, todo ponto que tem pessoa acima E abaixo vira pessoa: a cabeça fica
    ligada ao corpo e o peito fica inteiro. Não mexe fora dessas colunas (braços e fundo ficam como estão)."""
    fx0, fy0, fx1, fy1 = rosto
    fw = fx1 - fx0
    c0 = max(0, int((fx0 - 0.1 * fw) * sc) - vx0)
    c1 = min(m.shape[1], int((fx1 + 0.1 * fw) * sc) - vx0)
    r0 = max(0, int((fy0 + fy1) / 2 * sc) - vy0)
    if c1 - c0 < 2 or m.shape[0] - r0 < 2:
        return
    sub = m[r0:, c0:c1]
    desce = np.maximum.accumulate(sub, axis=0)
    sobe = np.maximum.accumulate(sub[::-1], axis=0)[::-1]
    np.maximum(sub, np.minimum(desce, sobe), out=sub)


def _camada_pessoa(fonte_arr, masc, sc, ox, oy, W, H, op_video, bbox=None, rosto=None):
    """Quadro escalado por sc e posto em (ox, oy): devolve (vídeo com opacidade op_video ou None,
    pessoa recortada ou None, (x, y) da pessoa no quadro, (x, y) do vídeo). Só a parte visível é devolvida;
    a pessoa ainda é cortada na caixa do recorte (bbox, em pixels do quadro original) para compor menos.
    rosto (caixa do rosto no quadro original) = plano fechado: liga cabeça e corpo e some mais suave
    nas laterais (o corte reto do vídeo original nunca aparece como uma linha)."""
    tw, th = max(2, int(round(W * sc))), max(2, int(round(H * sc)))
    x, y = int(round(ox)), int(round(oy))
    vx0, vy0 = max(0, -x), max(0, -y)
    vx1, vy1 = min(tw, W - x), min(th, H - y)
    if vx1 - vx0 < 2 or vy1 - vy0 < 2:
        return None, None, (0, 0), (0, 0)
    peq = _escalar(fonte_arr, tw, th)
    video = pessoa = None
    if op_video > 0.004:
        video = np.array(peq[vy0:vy1, vx0:vx1])
        video[..., 3] = int(round(255 * d.limitar(op_video)))
    px, py = x + vx0, y + vy0
    if masc is not None:
        if bbox is not None:   # só a área da pessoa
            vx0, vy0 = max(vx0, int(bbox[0] * sc) - 2), max(vy0, int(bbox[1] * sc) - 2)
            vx1, vy1 = min(vx1, int(math.ceil(bbox[2] * sc)) + 2), min(vy1, int(math.ceil(bbox[3] * sc)) + 2)
        if vx1 - vx0 >= 2 and vy1 - vy0 >= 2:
            m = np.array(_escalar(masc, tw, th)[vy0:vy1, vx0:vx1])
            if rosto is not None:
                _fechar_pescoco(m, rosto, sc, vx0, vy0)
            _rampa_bordas(m, tw, th, vx0, vy0, 0.05 * W * sc)
            if rosto is not None:
                queixo = rosto[3] + (rosto[3] - rosto[1]) * 0.08
                _rampa_lados_corpo(m, tw, vx0, queixo * sc - vy0, 0.16 * W * sc)
            pessoa = np.array(peq[vy0:vy1, vx0:vx1])
            pessoa[..., 3] = m
            px, py = x + vx0, y + vy0
    return video, pessoa, (px, py), (x + max(0, -x), y + max(0, -y))


def _skel(g, n, fw, fh):
    """Base da tela do app (cabeçalho) e o 'esqueleto' sem texto, desenhados uma vez por resolução."""
    chave = ("06skel", n, g.W)
    if chave in g.cache:
        return g.cache[chave]
    u = fw
    base = Image.new("RGBA", (fw, fh), d.cor(UI_FUNDO))
    db = ImageDraw.Draw(base)
    # cabeçalho: ícone do app (círculo neon) + nome em barra (sem texto inventado) + três pontos
    r = int(0.075 * u)
    cx_, cy_ = int(0.085 * u + r), int(0.075 * u + r)
    circ = d.painel(2 * r, 2 * r, r, fundo=LIMA)
    ic = d.icone("estrela", int(r * 1.15), ICONE_TINTA, espessura=0.13)
    circ.alpha_composite(ic, ((circ.width - ic.width) // 2, (circ.height - ic.height) // 2))
    base.alpha_composite(circ, (cx_ - r, cy_ - r))
    bar_h = int(0.045 * u)
    base.alpha_composite(d.painel(int(0.36 * u), bar_h, bar_h // 2, fundo=UI_SKEL),
                         (int(cx_ + r + 0.04 * u), int(cy_ - bar_h / 2)))
    for j in range(3):
        px = int(0.80 * u + j * 0.045 * u)
        rr = max(1, int(0.012 * u))
        db.ellipse((px - rr, cy_ - rr, px + rr, cy_ + rr), fill=d.cor(UI_CINZA, 0.6))
    # esqueleto do conteúdo (quando nenhum cartão está na tela)
    sk = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    x0 = int(0.06 * u)
    y = 0.40 * u
    for wv in (0.80, 0.64, 0.40):
        hh = int(0.085 * u)
        sk.alpha_composite(d.painel(int(wv * u), hh, hh // 2, fundo=UI_SKEL), (x0, int(y)))
        y += 0.13 * u
    y += 0.07 * u
    for wv in (0.72, 0.52):
        hh = int(0.042 * u)
        sk.alpha_composite(d.painel(int(wv * u), hh, hh // 2, fundo="#2B3639"), (x0, int(y)))
        y += 0.08 * u
    y += 0.08 * u
    ph = int(0.30 * u)
    sk.alpha_composite(d.painel(int(0.88 * u), ph, int(0.05 * u), fundo=UI_CAIXA), (x0, int(y)))
    bx, gap = x0 + 0.04 * u, 0.02 * u
    bw_ = (0.88 * u - 0.08 * u - gap * 5) / 6
    for j in range(6):
        sk.alpha_composite(d.painel(int(bw_), int(0.12 * u), int(0.02 * u), fundo=UI_BLOCO),
                           (int(bx + j * (bw_ + gap)), int(y + 0.09 * u)))
    y += ph + 0.08 * u
    bh_ = int(0.17 * u)
    sk.alpha_composite(d.painel(int(0.88 * u), bh_, bh_ // 2, fundo="#3B4749"), (x0, int(y)))
    g.cache[chave] = (base, sk)
    return g.cache[chave]


def _conteudo_cartao(g, e, u):
    chave = ("06tcard", e.get("texto"), e.get("detalhe"), e.get("icone"), u)
    if chave in g.cache:
        return g.cache[chave]
    larg = 0.90 * u
    det = str(e.get("detalhe") or "").strip().upper()
    txt = str(e.get("texto") or "").strip()
    ic = int(0.27 * u)
    f_det = d.fonte(int(0.125 * u), 700)
    tr = 0.04 * f_det.size
    det_l = [det] if det else []
    if det and _larg_espacado(det, f_det, tr) > larg:
        # não cabe em caixa alta: escreve normal (como foi escrito), em até 2 linhas
        det = str(e.get("detalhe") or "").strip()
        tr = 0.0
        f_det, det_l, _ = d.ajustar_texto(det, larg, f_det.size * 2.4, 700, tam_max=f_det.size,
                                          tam_min=int(0.12 * u), max_linhas=2)
    fm, linhas, al = d.ajustar_texto(txt, larg, 0.62 * u, 850, tam_max=int(0.18 * u), tam_min=int(0.12 * u),
                                     max_linhas=3, entrelinha=1.06)
    dh = f_det.size * (1.45 + 1.15 * (len(det_l) - 1)) if det_l else 0
    h = ic + 0.11 * u + dh + fm.size * 0.78 + al * (len(linhas) - 1) + 0.12 * u
    img = Image.new("RGBA", (int(u), int(h + 0.04 * u)), (0, 0, 0, 0))
    circ = d.painel(ic, ic, ic // 2, fundo=LIMA)
    nome = e.get("icone") if e.get("icone") in ICONES else "check"
    icn = d.icone(nome, int(ic * 0.56), ICONE_TINTA, espessura=0.13)
    circ.alpha_composite(icn, ((ic - icn.width) // 2, (ic - icn.height) // 2))
    x0 = 0.05 * u
    img.alpha_composite(circ, (int(x0), 0))
    dr = ImageDraw.Draw(img)
    y = ic + 0.11 * u
    for j, l in enumerate(det_l):
        _texto_espacado(dr, (x0, y - f_det.size * 0.18 + j * f_det.size * 1.15), l, f_det, d.cor(UI_CINZA), tr)
    y += dh
    yb = y + fm.size * 0.78
    for i, l in enumerate(linhas):
        dr.text((x0, yb + i * al), l, font=fm, fill=d.cor(UI_TEXTO), anchor="ls")
    yb += al * (len(linhas) - 1) + 0.09 * u
    dr.rounded_rectangle((x0, yb, x0 + 0.22 * u, yb + 0.028 * u), radius=int(0.014 * u), fill=d.cor(LIMA))
    g.cache[chave] = img
    return img


def _conteudo_contador(c, e, u):
    g, t = c.g, c.t
    chave = ("06tcont", e.get("texto"), e.get("valor"), e.get("antes"), e.get("depois"), u)
    if chave not in g.cache:
        larg = 0.90 * u
        rot = str(e.get("texto") or "").strip().upper()
        antes = str(e.get("antes") or "").strip()
        depois = str(e.get("depois") or "").strip()
        v, casas = _valor(e)
        f_rot = d.fonte(int(0.125 * u), 700)
        tr = 0.04 * f_rot.size
        rot_l = [rot] if rot else []
        if rot and _larg_espacado(rot, f_rot, tr) > larg:
            # não cabe em caixa alta numa linha: escreve como foi escrito, em até 2 linhas
            rot = str(e.get("texto") or "").strip()
            tr = 0.0
            f_rot, rot_l, _ = d.ajustar_texto(rot, larg, f_rot.size * 2.4, 700, tam_max=f_rot.size,
                                              tam_min=int(0.12 * u), max_linhas=2)
        tam = int(0.40 * u)
        while True:
            f_n = d.fonte(tam, 850)
            f_a = d.fonte(max(int(0.12 * u), int(tam * 0.42)), 800)
            lf = (f_a.getlength(antes + " ") if antes else 0) + f_n.getlength(_numero(v, casas))
            if lf <= larg or tam <= int(0.2 * u):
                break
            tam = int(tam * 0.92)
        # a unidade vai do lado do número se couber; senão, na linha de baixo
        unid_baixo = bool(depois) and lf + f_a.getlength(" " + depois) > larg
        y = f_rot.size * (1.5 + 1.15 * (len(rot_l) - 1)) if rot_l else 0
        y_num = y + f_n.size * 0.74
        y_fim = y_num + (f_a.size * 1.25 if unid_baixo else 0) + 0.10 * u
        base = Image.new("RGBA", (int(u), int(y_fim + 0.05 * u)), (0, 0, 0, 0))
        dr = ImageDraw.Draw(base)
        x0 = 0.05 * u
        for j, l in enumerate(rot_l):
            _texto_espacado(dr, (x0, j * f_rot.size * 1.15), l, f_rot, d.cor(UI_CINZA), tr)
        dr.rounded_rectangle((x0, y_fim - 0.028 * u, x0 + 0.22 * u, y_fim), radius=int(0.014 * u),
                             fill=d.cor(LIMA))
        g.cache[chave] = (base, {"x0": x0, "y_num": y_num, "f_n": f_n, "f_a": f_a, "antes": antes,
                                 "depois": depois, "v": v, "casas": casas, "baixo": unid_baixo})
    base, geo = g.cache[chave]
    dur = min(1.1, 0.5 * (e["fim"] - e["inicio"]))
    k = d.saida(d.mapear(t, e["inicio"], e["inicio"] + dur))
    pronto = ("06tcontok", e["inicio"], u)
    if k >= 0.999 and pronto in g.cache:
        return g.cache[pronto]
    img = base.copy()
    dr = ImageDraw.Draw(img)
    v = geo["v"] * k
    txt_n = _numero(v if geo["casas"] else round(v), geo["casas"])
    x, y = geo["x0"], geo["y_num"]
    if geo["antes"]:
        dr.text((x, y), geo["antes"] + " ", font=geo["f_a"], fill=d.cor(UI_TEXTO), anchor="ls")
        x += geo["f_a"].getlength(geo["antes"] + " ")
    dr.text((x, y), txt_n, font=geo["f_n"], fill=d.cor(LIMA), anchor="ls")
    x += geo["f_n"].getlength(txt_n)
    if geo["depois"]:
        if geo["baixo"]:
            dr.text((geo["x0"], y + geo["f_a"].size * 1.2), geo["depois"], font=geo["f_a"],
                    fill=d.cor(UI_TEXTO), anchor="ls")
        else:
            dr.text((x, y), " " + geo["depois"], font=geo["f_a"], fill=d.cor(UI_TEXTO), anchor="ls")
    if k >= 0.999:
        g.cache[pronto] = img
    return img


def _conteudo_progresso(c, e, u):
    g, t = c.g, c.t
    chave = ("06tprog", e.get("texto"), u)
    if chave not in g.cache:
        larg = 0.90 * u
        x0 = 0.05 * u
        txt = str(e.get("texto") or "").strip()
        topo = 0.06 * u      # espaço para acentos em maiúsculas (Ú, É...)
        y = 0.0
        linhas, f, al = [], None, 0
        if txt:
            f, linhas, al = d.ajustar_texto(txt, larg, 0.34 * u, 850, tam_max=int(0.155 * u), tam_min=int(0.125 * u),
                                            max_linhas=2, entrelinha=1.06)
            y = topo + f.size * 0.78 + al * (len(linhas) - 1) + 0.09 * u
        y_painel = y
        ph = 0.30 * u
        y_barra = y_painel + ph + 0.06 * u
        bar_h = 0.03 * u
        y_botao = y_barra + bar_h + 0.08 * u
        bot_h = 0.19 * u
        h = y_botao + bot_h * 1.1 + 0.02 * u
        base = Image.new("RGBA", (int(u), int(h)), (0, 0, 0, 0))
        dr = ImageDraw.Draw(base)
        for i, l in enumerate(linhas):
            dr.text((x0, topo + f.size * 0.78 + i * al), l, font=f, fill=d.cor(UI_TEXTO), anchor="ls")
        base.alpha_composite(d.painel(int(larg), int(ph), int(0.05 * u), fundo=UI_CAIXA), (int(x0), int(y_painel)))
        base.alpha_composite(d.painel(int(larg), int(bar_h), int(bar_h / 2), fundo=UI_TRILHO),
                             (int(x0), int(y_barra)))
        gap = 0.02 * u
        bw_ = (larg - 0.08 * u - gap * 5) / 6
        blocos = [(x0 + 0.04 * u + j * (bw_ + gap), bw_) for j in range(6)]
        g.cache[chave] = (base, {"x0": x0, "larg": larg, "y_bl": y_painel + 0.09 * u, "bl_h": 0.12 * u,
                                 "blocos": blocos, "y_barra": y_barra, "bar_h": bar_h, "y_botao": y_botao,
                                 "bot_h": bot_h})
    base, geo = g.cache[chave]
    cc = _conclui(e)
    pronto = ("06tprogok", e["inicio"], u)
    if t >= cc + 0.32 and pronto in g.cache:
        return g.cache[pronto]
    img = base.copy()
    p = d.suave(d.mapear(t, e["inicio"] + 0.3, cc))
    n = len(geo["blocos"])
    for i, (x, bw_) in enumerate(geo["blocos"]):
        f = round(d.saida(d.limitar(p * n - i)) * 16) / 16
        img.alpha_composite(_painel_c(g, bw_, geo["bl_h"], 0.02 * u, _misturar(UI_BLOCO, LIMA, f)),
                            (int(x), int(geo["y_bl"])))
    larg = geo["larg"] * p
    if larg > geo["bar_h"]:
        img.alpha_composite(_painel_c(g, larg, geo["bar_h"], geo["bar_h"] / 2, LIMA),
                            (int(geo["x0"]), int(geo["y_barra"])))
    bw_, bh_ = geo["larg"], geo["bot_h"]
    kc = round(d.mapear(t, cc, cc + 0.16) * 8) / 8
    pulo = 1 + 0.07 * math.sin(math.pi * d.mapear(t, cc, cc + 0.3)) if t >= cc else 1.0
    botao = _painel_c(g, bw_, bh_, bh_ / 2, _misturar("#F5F7EE", LIMA, kc)).copy()
    db = ImageDraw.Draw(botao)
    if kc < 0.5:
        for j in range(3):
            fase = (t * 2.2 - j * 0.18) % 1.0
            a = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2 * math.pi * fase))
            r = bh_ * 0.08
            cx_ = bw_ / 2 + (j - 1) * bh_ * 0.34
            db.ellipse((cx_ - r, bh_ / 2 - r, cx_ + r, bh_ / 2 + r), fill=d.cor(TINTA, a * (1 - 2 * kc)))
    else:
        final = str(e.get("final") or "").strip()
        tam_ic = int(bh_ * 0.5)
        ic = d.icone("check", tam_ic, TINTA, espessura=0.15)
        if final:
            gx = 0.03 * u
            caber = bw_ - tam_ic - gx - 0.03 * u
            f = d.fonte(int(0.13 * u), 850)
            if f.getlength(final) > caber:
                f, _, _ = d.ajustar_texto(final, caber, bh_, 850, tam_max=int(0.13 * u),
                                          tam_min=int(0.12 * u), max_linhas=1)
            tw = f.getlength(final)
            x0 = (bw_ - (tam_ic + gx + tw)) / 2
            botao.alpha_composite(ic, (int(x0), int((bh_ - tam_ic) / 2)))
            db.text((x0 + tam_ic + gx, bh_ / 2 + f.size * 0.36), final, font=f, fill=d.cor(TINTA), anchor="ls")
        else:
            botao.alpha_composite(ic, (int((bw_ - tam_ic) / 2), int((bh_ - tam_ic) / 2)))
    if abs(pulo - 1) > 0.002:
        botao = botao.resize((int(bw_ * pulo), int(bh_ * pulo)), Image.BICUBIC)
    img.alpha_composite(botao, (int(geo["x0"] + (bw_ - botao.width) / 2),
                                int(geo["y_botao"] + (bh_ - botao.height) / 2)))
    if t >= cc + 0.32 and p >= 1:
        g.cache[pronto] = img
    return img


def _tela_app(c, e_cena, fw, fh, n):
    """A interface do app dentro da tela do celular neste instante (array RGBA do tamanho do furo)."""
    g, t = c.g, c.t
    u = fw
    base, sk = _skel(g, n, fw, fh)
    pres_max = 0.0
    camadas = []
    estatico = True     # nada mexendo na tela: reaproveita a imagem pronta
    chave_est = ("06uiarr", n, g.W, None)
    for ev in c.eventos:
        if ev.get("tipo") not in TIPOS_UI or not (e_cena["inicio"] <= ev["inicio"] <= e_cena["fim"]):
            continue
        fim = _fim_efetivo(g, ev)
        if t < ev["inicio"] or t > fim:
            continue
        a = d.mapear(t, ev["inicio"], ev["inicio"] + 0.38)
        b = d.mapear(t, fim - 0.25, fim)
        op = d.saida(a) * (1 - d.entrada(b))
        if op <= 0.005:
            continue
        tipo = ev.get("tipo")
        parado = a >= 1 and b <= 0
        if tipo == "cartao":
            cam = _conteudo_cartao(g, ev, u)
        elif tipo == "progresso":
            cam = _conteudo_progresso(c, ev, u)
            parado = parado and ("06tprogok", ev["inicio"], u) in g.cache and t >= _conclui(ev) + 0.32
        else:
            cam = _conteudo_contador(c, ev, u)
            parado = parado and ("06tcontok", ev["inicio"], u) in g.cache and                 d.mapear(t, ev["inicio"], ev["inicio"] + min(1.1, 0.5 * (ev["fim"] - ev["inicio"]))) >= 1
        estatico = estatico and parado and chave_est[3] is None
        chave_est = ("06uiarr", n, g.W, ev["inicio"])
        dy = (1 - d.saida(a)) * 0.07 * u - d.entrada(b) * 0.04 * u
        # conteúdo um pouco acima do meio da altura útil da tela (entre o cabeçalho e a barra de baixo)
        y0 = max(0.36 * u, 0.36 * u + (fh - 0.46 * u - cam.height) * 0.35)
        camadas.append((cam, int(y0 + dy), op))
        pres_max = max(pres_max, op)
    if estatico and chave_est in g.cache:
        return g.cache[chave_est]
    img = base.copy()
    op_sk = 1 - d.limitar(pres_max * 1.8)
    if op_sk > 0.01:
        d.colar_em(img, sk, (0, 0), opacidade=op_sk)
    for cam, y, op in camadas:
        d.colar_em(img, cam, (0, y), opacidade=op)
    arr = np.asarray(img)
    if estatico:
        g.cache[chave_est] = arr
    return arr


def _quadro_pessoa(c, e, k, kb):
    g, W, H, t = c.g, c.W, c.H, c.t
    lay = _layout(g, e)
    fonte_arr = np.asarray(c.fonte)
    img = _fundo(c, lay["fundo"], fonte_arr)
    masc = np.asarray(c.mascara) if c.mascara is not None else None
    bbox = c.mascara.getbbox() if c.mascara is not None else None
    # câmera: o quadro inteiro vai da tela cheia para o lugar da pessoa; o fundo do vídeo some e fica a sala
    sc = math.exp(d.lerp(0.0, math.log(lay["sp"]), k))
    ox, oy = d.lerp(0.0, lay["ox"], k), d.lerp(0.0, lay["oy"], k)
    op_video = 1.0 if masc is None else 1 - d.suave(d.limitar(k / 0.6))
    if masc is not None and bbox is None:   # recorte vazio neste quadro: mostra o vídeo
        masc, op_video = None, 1.0
    rosto = g.rosto.em(t) if lay.get("fechado") and masc is not None else None
    video, pessoa, (px, py), pos_v = _camada_pessoa(fonte_arr, masc, sc, ox, oy, W, H, op_video, bbox, rosto)
    if video is not None:
        img.alpha_composite(Image.fromarray(video, "RGBA"), pos_v)
    if pessoa is not None:
        img.alpha_composite(Image.fromarray(pessoa, "RGBA"), (px, py))
    # celular: entra voando do lado dele (com mola) e sai antes de a pessoa voltar para a tela cheia
    ini, fim = e["inicio"], e["fim"]
    dur = fim - ini
    ts = min(T_SAI, dur * 0.3)
    a = d.mapear(t, ini + 0.12, ini + 0.12 + min(0.75, dur * 0.3))
    kf = (d.mola(a, 0.7) if a < 1 else 1.0) * (1 - d.entrada(d.mapear(t, fim - ts - 0.08, fim - ts * 0.3)))
    escuro = lay["fundo"] != "sala"
    if kf > 0.005:
        cx_, cy_, s_, ry, rz = _pose_assentada(lay, t, H)
        sinal = lay["sinal"]
        fora = 1 - kf
        pose = (cx_ + fora * 0.85 * W * sinal, cy_ + fora * 0.06 * H, s_, ry, rz + fora * 16 * sinal)
        r = s_ / W
        n = max(1, min(4, int(round(0.9 / max(r, 0.05)))))
        fone = _celular(g, n, escuro)
        fx, fy, fw, fh = fone["furo"]
        tela = _tela_app(c, e, fw, fh, n)
        quad = _proj(_cantos_img(W, H), pose, W)
        _colar_celular(img, fone, tela, quad)
        A, bw, bh, vy0 = _dims(W, H)
        vb = vy0 + A
        prog = d.limitar(t / max(0.1, g.duracao))
        if prog > 0.005:
            x1 = -0.44 + 0.88 * prog
            pts = _proj(np.array([(-0.44, vb + 0.026), (x1, vb + 0.026), (x1, vb + 0.038), (-0.44, vb + 0.038)]),
                        pose, W)
            _poligono_suave(img, pts, d.cor(LIMA))
        # a cabeça volta por cima do celular (se a pessoa se inclinar, o rosto nunca fica coberto)
        if pessoa is not None:
            q = _proj(_cantos_corpo(W, H), pose, W)
            qx0, qx1 = int(q[:, 0].min()), int(q[:, 0].max()) + 1
            queixo = oy + sc * g.rosto.queixo(t)
            y_corte = int(queixo + 0.035 * H)
            x0r, x1r = max(px, qx0), min(px + pessoa.shape[1], qx1)
            y1r = min(py + pessoa.shape[0], y_corte)
            if x1r - x0r > 1 and y1r - py > 1:
                reg = np.array(pessoa[0:y1r - py, x0r - px:x1r - px])
                hr = reg.shape[0]
                rampa = np.clip((y_corte - (py + np.arange(hr))) / (0.03 * H), 0, 1).astype(np.float32)
                reg[..., 3] = (reg[..., 3].astype(np.float32) * rampa[:, None]).astype(np.uint8)
                img.alpha_composite(Image.fromarray(reg, "RGBA"), (x0r, py))
    # título no alto
    tit = lay["tit"]
    if tit is not None:
        a = d.saida(d.mapear(t, ini + 0.22, ini + 0.7))
        op = a * d.suave(d.limitar((kb - 0.45) / 0.55))
        if op > 0.01:
            d.colar_em(img, tit, (0.074 * W, lay["y_tit"] + (1 - a) * 0.02 * H), opacidade=op)
    return img, lay


# ---------------------------------------------------------------- legenda do estilo (palavra com caixinha neon)

def _paginas(palavras, max_car=20, max_pal=4):
    out = []
    for gr in agrupar(palavras, max_car, 1):
        ps = gr["palavras"]
        partes = [ps[i:i + max_pal] for i in range(0, len(ps), max_pal)]
        for j, pp in enumerate(partes):
            fim = partes[j + 1][0]["inicio"] if j + 1 < len(partes) else gr["fim"]
            out.append({"palavras": pp, "inicio": pp[0]["inicio"], "fim": fim})
    return out


def _painel_leg(leg, w, h, raio):
    chave = (w, h, raio)
    if chave not in leg._hl:
        leg._hl[chave] = d.painel(w, h, raio, fundo=leg.p.destaque)
    return leg._hl[chave]


class _Legenda(Legendas):
    """Caixa escura de largura fixa (como a prévia), até 4 palavras numa linha; a palavra falada ganha
    uma caixinha neon que desliza de palavra em palavra. Fora das cenas fica perto do rosto (abaixo do
    queixo); nas cenas do celular sobe para baixo do título."""

    def __init__(self, palavras, W, H, perfil, rosto):
        super().__init__(palavras, W, H, perfil, rosto)
        self.grupos = _paginas(palavras, int(perfil.max_caracteres or 20))
        self.f = d.fonte(int(W * perfil.tamanho), perfil.peso, perfil.fonte)
        self.caixa_w = 0.80 * W
        self.altura_caixa = max(0.125 * W, self.f.size * 2.0)
        self.x = 0.074 * W
        self._med = {}
        self._hl = {}
        self._caixa = d.painel(self.caixa_w, self.altura_caixa, int(0.034 * W), fundo=perfil.caixa)

    def _medidas(self, gi):
        if gi in self._med:
            return self._med[gi]
        gr = self.grupos[gi]
        txts = [w["texto"].upper() if self.p.maiusculas else w["texto"] for w in gr["palavras"]]
        f = self.f
        util = self.caixa_w - f.size * 1.0
        while True:
            esp = f.getlength(" ")
            ws = [f.getlength(x) for x in txts]
            total = sum(ws) + esp * (len(txts) - 1)
            if total <= util or f.size <= int(self.W * 0.045):
                break
            f = d.fonte(int(f.size * 0.94), self.p.peso, self.p.fonte)
        xs, x = [], (self.caixa_w - total) / 2
        for wv in ws:
            xs.append(x)
            x += wv + esp
        self._med[gi] = (f, txts, xs, ws)
        return self._med[gi]

    def _grupo(self, t):
        for i, gr in enumerate(self.grupos):
            if gr["inicio"] - 0.05 <= t < gr["fim"]:
                return i
        return None

    def desenhar_em(self, img, t, y_cena, k):
        gi = self._grupo(t)
        if gi is None:
            return
        gr = self.grupos[gi]
        f, txts, xs, ws = self._medidas(gi)
        bw, bh = self.caixa_w, self.altura_caixa
        y = self._y(t, bh)
        op_troca = 1.0
        if y_cena is not None:
            # na transição a legenda some no lugar antigo e reaparece no novo (nunca atravessa o rosto)
            kk = d.limitar(k)
            if kk <= 0.35:
                op_troca = 1 - d.suave(kk / 0.35)
            elif kk >= 0.7:
                y, op_troca = y_cena, d.suave((kk - 0.7) / 0.3)
            else:
                return
            if op_troca <= 0.01:
                return
        cam = self._caixa.copy()
        pal = gr["palavras"]
        i = 0
        for j, w in enumerate(pal):
            if t >= w["inicio"] - 0.03:
                i = j
        gl = 1.0
        if i > 0:
            gl = d.saida(d.mapear(t, pal[i]["inicio"] - 0.03, pal[i]["inicio"] + 0.09))
        xb = d.lerp(xs[i - 1], xs[i], gl) if i > 0 else xs[i]
        wb = d.lerp(ws[i - 1], ws[i], gl) if i > 0 else ws[i]
        hx, hh = f.size * 0.12, f.size * 1.22
        base = bh / 2 + f.size * 0.36
        dr = ImageDraw.Draw(cam)
        for j, txt in enumerate(txts):
            dr.text((xs[j], base), txt, font=f, fill=d.cor(self.p.cor), anchor="ls")
        # caixinha neon que desliza; dentro dela o texto fica escuro (só onde ela está)
        hl = _painel_leg(self, int(wb + 2 * hx), int(hh), int(f.size * 0.16))
        px, py = int(xb - hx), int((bh - hh) / 2)
        cam.alpha_composite(hl, (px, py))
        tinta = Image.new("RGBA", hl.size, d.cor(TINTA, 0))
        dt = ImageDraw.Draw(tinta)
        for j, txt in enumerate(txts):
            if xs[j] + ws[j] >= px and xs[j] <= px + hl.width:
                dt.text((xs[j] - px, base - py), txt, font=f, fill=d.cor(TINTA), anchor="ls")
        tinta.putalpha(Image.fromarray(np.minimum(np.asarray(tinta.getchannel("A")),
                                                  np.asarray(hl.getchannel("A"))), "L"))
        cam.alpha_composite(tinta, (px, py))
        a = d.mapear(t, gr["inicio"] - 0.05, gr["inicio"] + 0.2)
        esc = 0.95 + 0.05 * d.mola(a, 1.4)
        op = d.saida(d.mapear(t, gr["inicio"] - 0.05, gr["inicio"] + 0.1)) * op_troca
        dy = (1 - d.saida(a)) * self.H * 0.008
        d.colar(img, cam, (self.x + bw / 2, y + bh / 2 + dy), escala=esc, opacidade=op)


# ---------------------------------------------------------------- contrato

def preparar(g):
    leg = g.plano.get("legenda") or {}
    if leg.get("ativa", True) and g.palavras:
        perfil = dict(INFO["legenda"])
        perfil.update(leg.get("perfil") or {})
        g.cache["06leg"] = _Legenda(g.palavras, g.W, g.H, PerfilLegenda.de(perfil), g.rosto)


def quadro(c):
    t = c.t
    e = _cena_em(c.g, t)
    k, kb = _k_cena(e, t) if e is not None else (0.0, 0.0)
    leg = c.g.cache.get("06leg")
    if e is None or k <= 0.002:
        img = c.fonte.copy()
        if leg is not None:
            leg.desenhar_em(img, t, None, 0.0)
        return img
    if _layout(c.g, e)["modo"] == "pessoa":
        img, lay = _quadro_pessoa(c, e, k, kb)
    else:
        img, lay = _quadro_celular(c, e, k, kb)
    if leg is not None:
        leg.desenhar_em(img, t, lay["y_leg"], d.limitar(k))
    return img


def _palavras(txt):
    return len(str(txt or "").split())


def _larg_rel(txt, peso=850):
    """Largura do texto em 'tamanhos de letra' (largura / tamanho da fonte)."""
    return d.fonte(100, peso).getlength(str(txt)) / 100


def _palavra_larga(txt, limite, peso=850):
    return next((w for w in str(txt or "").split() if _larg_rel(w, peso) > limite), None)


def validar(plano, duracao):
    p = []
    evs = plano["eventos"]
    cenas = sorted([e for e in evs if e.get("tipo") == "celular"], key=lambda e: e["inicio"])
    if not cenas:
        p.append("Este estilo precisa de pelo menos uma cena 'celular' (o vídeo vira a tela do celular).")
    for a, b in zip(cenas, cenas[1:]):
        if b["inicio"] < a["fim"] - 0.01:
            p.append(f"Cenas 'celular' sobrepostas em {b['inicio']:.2f}s: uma cena termina antes da outra começar.")
        elif b["inicio"] - a["fim"] < 1.0:
            p.append(f"Só {b['inicio'] - a['fim']:.1f}s de tela cheia entre as cenas em {a['fim']:.2f}s: deixe pelo "
                     "menos 1 s entre duas cenas 'celular' ou junte as duas numa cena só.")
    for e in cenas:
        dur = e["fim"] - e["inicio"]
        if dur < 2.5:
            p.append(f"Cena 'celular' em {e['inicio']:.2f}s curta demais ({dur:.1f}s): mínimo 2,5 s.")
        if e.get("lado", "direita") not in LADOS:
            p.append(f"Cena em {e['inicio']:.2f}s: 'lado' deve ser 'direita' ou 'esquerda'.")
        if e.get("modo") is not None and e.get("modo") not in MODOS:
            p.append(f"Cena em {e['inicio']:.2f}s: 'modo' deve ser 'pessoa' ou 'tela' (ou não use o campo).")
        if e.get("fundo", "sala") not in FUNDOS:
            p.append(f"Cena em {e['inicio']:.2f}s: 'fundo' deve ser 'sala', 'sala-escura' ou 'video'.")
        tit = str(e.get("titulo") or "")
        if _palavras(tit) > 5 or len(tit) > 34:
            p.append(f"Título longo demais em {e['inicio']:.2f}s (máx. 5 palavras / 34 letras): '{tit}'.")
    uis = sorted([e for e in evs if e.get("tipo") in TIPOS_UI], key=lambda e: e["inicio"])
    for e in uis:
        tipo, ini = e.get("tipo"), e["inicio"]
        dentro = any(c["inicio"] + 0.35 <= ini and e["fim"] <= c["fim"] - 0.2 for c in cenas)
        if not dentro:
            p.append(f"'{tipo}' em {ini:.2f}s precisa ficar dentro de uma cena 'celular' (começar pelo menos 0,4 s "
                     "depois do início da cena e terminar 0,2 s antes do fim dela).")
        if e["fim"] - ini < 1.0:
            p.append(f"'{tipo}' em {ini:.2f}s curto demais: mínimo 1 s na tela para dar tempo de ler.")
        if tipo == "cartao":
            txt = str(e.get("texto") or "")
            if not txt.strip():
                p.append(f"Cartão em {ini:.2f}s sem 'texto'.")
            if _palavras(txt) > 5 or len(txt) > 30:
                p.append(f"Texto do cartão longo demais em {ini:.2f}s (máx. 4-5 palavras / 30 letras): '{txt}'.")
            if len(str(e.get("detalhe") or "")) > 26:
                p.append(f"'detalhe' do cartão em {ini:.2f}s longo demais (máx. 26 letras).")
            larga = _palavra_larga(txt, 7.4) or _palavra_larga(e.get("detalhe"), 7.4, 700)
            if larga:
                p.append(f"Cartão em {ini:.2f}s: a palavra '{larga}' é comprida demais para a tela do celular. "
                         "Troque por uma palavra mais curta.")
            if e.get("icone") and e.get("icone") not in ICONES:
                p.append(f"Ícone '{e.get('icone')}' não existe. Use: {', '.join(ICONES)}.")
        elif tipo == "progresso":
            if len(str(e.get("texto") or "")) > 26:
                p.append(f"'texto' do progresso em {ini:.2f}s longo demais (máx. 26 letras).")
            final = str(e.get("final") or "")
            if len(final) > 14 or _larg_rel(final) > 6.2:
                p.append(f"'final' do progresso em {ini:.2f}s longo demais para o botão: use até 11 letras "
                         "(ex.: 'Tudo pronto', 'Pronto!', 'No ar').")
            larga = _palavra_larga(e.get("texto"), 7.2)
            if larga:
                p.append(f"Progresso em {ini:.2f}s: a palavra '{larga}' é comprida demais para a tela do celular.")
            if e["fim"] - ini < 2.0:
                p.append(f"Progresso em {ini:.2f}s curto demais: mínimo 2 s para a barra encher.")
            if e.get("conclui") is not None:
                try:
                    cc = float(e.get("conclui"))
                except (TypeError, ValueError):
                    cc = None
                    p.append(f"Progresso em {ini:.2f}s: 'conclui' precisa ser um número (segundos).")
                if cc is not None and e["fim"] - cc < 1.0:
                    p.append(f"Progresso em {ini:.2f}s: 'conclui' ({cc:.2f}s) perto demais do fim ({e['fim']:.2f}s). "
                             f"Deixe o botão pronto pelo menos 1 s na tela: use fim de pelo menos {cc + 1.0:.2f}s.")
                if cc is not None and cc - ini < 0.8:
                    p.append(f"Progresso em {ini:.2f}s: 'conclui' ({cc:.2f}s) cedo demais: pelo menos 0,8 s depois "
                             "do início, para a barra encher na frente de quem assiste.")
        elif tipo == "contador":
            try:
                float(str(e.get("valor")).replace(" ", ""))
            except ValueError:
                p.append(f"Contador em {ini:.2f}s: 'valor' precisa ser um número (ex.: 26 ou 2.5), sem pontos de milhar.")
            if len(str(e.get("depois") or "")) > 12 or len(str(e.get("antes") or "")) > 4:
                p.append(f"Contador em {ini:.2f}s: 'antes' até 4 letras e 'depois' até 12 letras.")
            if len(str(e.get("texto") or "")) > 26:
                p.append(f"'texto' do contador em {ini:.2f}s longo demais (máx. 26 letras).")
    for a, b in zip(uis, uis[1:]):
        if b["inicio"] < a["fim"] - 0.3:
            p.append(f"Cartões de interface sobrepostos em {b['inicio']:.2f}s: um por vez (o próximo entra quando "
                     "o anterior sai).")
    return p
