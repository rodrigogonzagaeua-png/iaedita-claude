"""Ferramentas de desenho de alta qualidade (Pillow): texto, painéis, vidro, sombra,
perspectiva, curvas de movimento. Todas as medidas em pixels do quadro de saída."""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from . import FONTES

NEON = "#D4FF1F"
BRANCO = "#FFFFFF"
PRETO = "#0B0B0C"

# ---------------------------------------------------------------- cores


def cor(c, alfa: float | None = None) -> tuple[int, int, int, int]:
    """'#RRGGBB', '#RRGGBBAA' ou tupla -> (r,g,b,a). alfa (0-1) sobrescreve."""
    if isinstance(c, str):
        c = c.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        a = int(c[6:8], 16) if len(c) == 8 else 255
    else:
        r, g, b = c[:3]
        a = c[3] if len(c) > 3 else 255
    if alfa is not None:
        a = int(round(255 * max(0.0, min(1.0, alfa))))
    return (int(r), int(g), int(b), int(a))


# ---------------------------------------------------------------- curvas de movimento

def limitar(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def mapear(t, t0, t1):
    """0 antes de t0, 1 depois de t1, linear no meio."""
    if t1 <= t0:
        return 1.0 if t >= t1 else 0.0
    return limitar((t - t0) / (t1 - t0))


def lerp(a, b, k):
    return a + (b - a) * k


def suave(k):  # ease in-out cúbico
    k = limitar(k)
    return 4 * k * k * k if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2


def saida(k):  # ease-out exponencial (entra rápido, assenta suave)
    k = limitar(k)
    return 1.0 if k >= 1 else 1 - 2 ** (-10 * k)


def entrada(k):  # ease-in cúbico
    k = limitar(k)
    return k * k * k


def mola(k, quique: float = 1.6):
    """Ease-out com leve passada do ponto (back-out). quique 0 = sem passada."""
    k = limitar(k)
    c1 = quique
    c3 = c1 + 1
    return 1 + c3 * (k - 1) ** 3 + c1 * (k - 1) ** 2


def envelope(t, inicio, fim, entra=0.35, sai=0.3):
    """0→1 na entrada, 1 no meio, 1→0 na saída. Para opacidade/escala de elementos."""
    if t < inicio or t > fim:
        return 0.0
    a = saida(mapear(t, inicio, inicio + entra)) if entra > 0 else 1.0
    b = 1 - entrada(mapear(t, fim - sai, fim)) if sai > 0 else 1.0
    return min(a, b)


def ruido(t, semente: int = 0, freq: float = 1.0) -> float:
    """Ruído suave determinístico em [-1, 1] (para tremidos e flutuação)."""
    x = t * freq + semente * 17.31
    i = math.floor(x)
    f = x - i

    def h(n):
        n = (n * 374761393 + semente * 668265263) & 0xFFFFFFFF
        n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 32767.5 - 1.0
    u = f * f * (3 - 2 * f)
    return h(i) * (1 - u) + h(i + 1) * u


# ---------------------------------------------------------------- fontes e texto

@lru_cache(maxsize=256)
def fonte(tamanho: int, peso: int = 700, familia: str = "inter") -> ImageFont.FreeTypeFont:
    """Inter (sem serifa, padrão) ou 'serif' (Cormorant Garamond). Peso 100-900."""
    tamanho = max(6, int(tamanho))
    try:
        if familia == "serif":
            f = ImageFont.truetype(str(FONTES / "CormorantGaramond-Variable.ttf"), tamanho)
            f.set_variation_by_axes([max(300, min(700, peso))])
        else:
            f = ImageFont.truetype(str(FONTES / "Inter-Variable.ttf"), tamanho)
            f.set_variation_by_axes([32 if tamanho >= 32 else 14, max(100, min(900, peso))])
        return f
    except Exception:  # noqa: BLE001  fonte do sistema como reserva
        for nome in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
            try:
                return ImageFont.truetype(nome, tamanho)
            except Exception:  # noqa: BLE001
                continue
        return ImageFont.load_default()


def largura_texto(txt: str, f) -> float:
    return f.getlength(txt)


def quebrar(txt: str, f, largura_max: float, max_linhas: int = 99) -> list[str]:
    palavras = txt.split()
    linhas, atual = [], ""
    for p in palavras:
        teste = (atual + " " + p).strip()
        if f.getlength(teste) <= largura_max or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    if len(linhas) > max_linhas:
        linhas = linhas[: max_linhas - 1] + [" ".join(linhas[max_linhas - 1:])]
    return linhas


def ajustar_texto(txt: str, largura: float, altura: float, peso: int = 800, familia: str = "inter",
                  tam_max: int = 200, tam_min: int = 14, max_linhas: int = 3, entrelinha: float = 1.08):
    """Maior fonte que faz o texto caber na caixa. Devolve (fonte, linhas, altura_linha)."""
    tam = int(tam_max)
    while tam >= tam_min:
        f = fonte(tam, peso, familia)
        linhas = quebrar(txt, f, largura, 99)
        al = tam * entrelinha
        if len(linhas) <= max_linhas and al * len(linhas) <= altura and \
                all(f.getlength(l) <= largura for l in linhas):
            return f, linhas, al
        tam = int(tam * 0.92) if tam > 40 else tam - 2
    f = fonte(tam_min, peso, familia)
    return f, quebrar(txt, f, largura, max_linhas), tam_min * entrelinha


def caixa_texto(linhas, f, al) -> tuple[float, float]:
    return (max((f.getlength(l) for l in linhas), default=0), al * len(linhas))


def escrever(img: Image.Image, xy, linhas, f, cor_txt=BRANCO, alinhar: str = "esquerda", al: float | None = None,
             sombra: float = 0.0, contorno: int = 0, cor_contorno=PRETO, ancora_y: str = "topo"):
    """Escreve linhas em img (RGBA). xy = ponto de âncora. alinhar: esquerda|centro|direita.
    sombra: opacidade 0-1 de uma sombra suave atrás do texto."""
    if isinstance(linhas, str):
        linhas = [linhas]
    al = al or f.size * 1.1
    x, y = xy
    total_h = al * len(linhas)
    if ancora_y == "centro":
        y -= total_h / 2
    elif ancora_y == "base":
        y -= total_h
    larg = max((f.getlength(l) for l in linhas), default=0)
    if sombra > 0:
        pad = int(f.size * 0.6)
        cam = Image.new("RGBA", (int(larg + pad * 2), int(total_h + pad * 2)), (0, 0, 0, 0))
        d = ImageDraw.Draw(cam)
        for i, l in enumerate(linhas):
            lx = pad + {"esquerda": 0, "centro": (larg - f.getlength(l)) / 2, "direita": larg - f.getlength(l)}[alinhar]
            d.text((lx, pad + i * al), l, font=f, fill=(0, 0, 0, int(255 * sombra)))
        cam = cam.filter(ImageFilter.GaussianBlur(f.size * 0.18))
        ox = {"esquerda": x, "centro": x - larg / 2, "direita": x - larg}[alinhar]
        img.alpha_composite(cam, (int(ox - pad), int(y - pad + f.size * 0.06)))
    d = ImageDraw.Draw(img)
    c = cor(cor_txt)
    for i, l in enumerate(linhas):
        w = f.getlength(l)
        lx = {"esquerda": x, "centro": x - w / 2, "direita": x - w}[alinhar]
        d.text((lx, y + i * al), l, font=f, fill=c,
               stroke_width=contorno, stroke_fill=cor(cor_contorno) if contorno else None)
    return (x, y, larg, total_h)


# ---------------------------------------------------------------- formas

@lru_cache(maxsize=512)
def mascara_arredondada(w: int, h: int, raio: int, ss: int = 3) -> Image.Image:
    """Máscara L com cantos arredondados e borda suave (super-amostrada)."""
    w, h = max(1, int(w)), max(1, int(h))
    raio = max(0, min(int(raio), w // 2, h // 2))
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), raio * ss, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def painel(w, h, raio=24, fundo=(18, 18, 20, 235), borda=None, larg_borda=2, gradiente=None) -> Image.Image:
    """Cartão/painel RGBA com cantos suaves. gradiente=(cor_topo, cor_base) opcional."""
    w, h = int(w), int(h)
    if gradiente:
        a, b = np.array(cor(gradiente[0]), np.float32), np.array(cor(gradiente[1]), np.float32)
        k = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        arr = (a * (1 - k) + b * k).repeat(w, axis=1).astype(np.uint8)
        base = Image.fromarray(arr, "RGBA")
    else:
        base = Image.new("RGBA", (w, h), cor(fundo))
    m = mascara_arredondada(w, h, raio)
    alfa = ImageChops.multiply(base.getchannel("A"), m)
    base.putalpha(alfa)
    if borda:
        ss = 3
        bm = Image.new("L", (w * ss, h * ss), 0)
        ImageDraw.Draw(bm).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), raio * ss, outline=255,
                                             width=max(1, larg_borda * ss))
        bm = bm.resize((w, h), Image.LANCZOS)
        cb = Image.new("RGBA", (w, h), cor(borda))
        cb.putalpha(ImageChops.multiply(bm, Image.new("L", (w, h), cor(borda)[3])))
        base.alpha_composite(cb)
    return base


def sombra(camada: Image.Image, raio: float = 24, opacidade: float = 0.45, desloc=(0, 12), margem: int | None = None):
    """Devolve (imagem_com_sombra, (dx, dy)) — cole em (x+dx, y+dy) no lugar de (x, y)."""
    margem = int(margem if margem is not None else raio * 2 + max(abs(desloc[0]), abs(desloc[1])))
    w, h = camada.size
    out = Image.new("RGBA", (w + margem * 2, h + margem * 2), (0, 0, 0, 0))
    a = camada.getchannel("A").point(lambda v: int(v * opacidade))
    s = Image.new("RGBA", camada.size, (0, 0, 0, 255))
    s.putalpha(a)
    out.alpha_composite(s, (margem + int(desloc[0]), margem + int(desloc[1])))
    out = out.filter(ImageFilter.GaussianBlur(raio))
    out.alpha_composite(camada, (margem, margem))
    return out, (-margem, -margem)


def vidro(base: Image.Image, caixa, raio=28, desfoque=22, tinta=(255, 255, 255, 38), borda=(255, 255, 255, 90),
          brilho: float = 1.06) -> None:
    """Efeito vidro fosco: desfoca o que está atrás da caixa, aplica tinta e borda clara. Altera base (RGBA)."""
    x0, y0, x1, y1 = [int(v) for v in caixa]
    W, H = base.size
    x0c, y0c, x1c, y1c = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x1c - x0c < 2 or y1c - y0c < 2:
        return
    reg = base.crop((x0c, y0c, x1c, y1c)).convert("RGB")
    pequeno = reg.resize((max(1, reg.width // 4), max(1, reg.height // 4)), Image.BILINEAR)
    pequeno = pequeno.filter(ImageFilter.GaussianBlur(max(1, desfoque / 4)))
    reg = pequeno.resize(reg.size, Image.BILINEAR)
    if brilho != 1:
        reg = Image.eval(reg, lambda v: min(255, int(v * brilho)))
    reg = reg.convert("RGBA")
    reg.alpha_composite(Image.new("RGBA", reg.size, cor(tinta)))
    pan = painel(x1 - x0, y1 - y0, raio, fundo=(0, 0, 0, 0), borda=borda, larg_borda=2)
    m = mascara_arredondada(x1 - x0, y1 - y0, raio).crop((x0c - x0, y0c - y0, x1c - x0, y1c - y0))
    reg.putalpha(m)
    base.alpha_composite(reg, (x0c, y0c))
    base.alpha_composite(pan.crop((x0c - x0, y0c - y0, x1c - x0, y1c - y0)), (x0c, y0c))


def colar(base: Image.Image, camada: Image.Image, centro, escala: float = 1.0, rotacao: float = 0.0,
          opacidade: float = 1.0):
    """Cola camada RGBA em base centrada em 'centro', com escala, rotação (graus) e opacidade."""
    if opacidade <= 0.003 or escala <= 0.01:
        return
    c = camada
    if abs(escala - 1) > 0.002:
        c = c.resize((max(1, int(c.width * escala)), max(1, int(c.height * escala))), Image.BICUBIC)
    if abs(rotacao) > 0.05:
        c = c.rotate(rotacao, resample=Image.BICUBIC, expand=True)
    if opacidade < 0.997:
        a = c.getchannel("A").point(lambda v: int(v * opacidade))
        c = c.copy()
        c.putalpha(a)
    x, y = int(round(centro[0] - c.width / 2)), int(round(centro[1] - c.height / 2))
    _colar_recortado(base, c, x, y)


def _colar_recortado(base, c, x, y):
    W, H = base.size
    if x >= W or y >= H or x + c.width <= 0 or y + c.height <= 0:
        return
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(c.width, W - x), min(c.height, H - y)
    base.alpha_composite(c.crop((cx0, cy0, cx1, cy1)), (x + cx0, y + cy0))


def colar_em(base, camada, xy, opacidade: float = 1.0):
    """Cola pelo canto superior esquerdo (aceita posições fora da tela)."""
    if opacidade < 0.997:
        camada = camada.copy()
        camada.putalpha(camada.getchannel("A").point(lambda v: int(v * opacidade)))
    _colar_recortado(base, camada, int(round(xy[0])), int(round(xy[1])))


def _coef_perspectiva(origem, destino):
    m = []
    for (x, y), (u, v) in zip(destino, origem):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        m.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    a = np.array(m, dtype=np.float64)
    b = np.array(origem, dtype=np.float64).reshape(8)
    return np.linalg.solve(a, b).tolist()


def perspectiva(camada: Image.Image, cantos_destino, tamanho_saida) -> Image.Image:
    """Distorce camada para os 4 cantos destino [(x,y) sup-esq, sup-dir, inf-dir, inf-esq]
    num quadro do tamanho_saida. Use para cartões 2.5D, telas inclinadas e paredes."""
    w, h = camada.size
    orig = [(0, 0), (w, 0), (w, h), (0, h)]
    coef = _coef_perspectiva(orig, cantos_destino)
    return camada.transform(tamanho_saida, Image.PERSPECTIVE, coef, Image.BICUBIC)


def projetar(x, y, z, foco: float, centro):
    """Projeção 3D simples: ponto (x,y,z) relativo ao centro -> (px, py, escala)."""
    s = foco / max(1.0, foco + z)
    return centro[0] + x * s, centro[1] + y * s, s


# ---------------------------------------------------------------- quadro e pessoa

def para_rgba(quadro) -> Image.Image:
    if isinstance(quadro, np.ndarray):
        return Image.fromarray(quadro, "RGB").convert("RGBA")
    return quadro.convert("RGBA") if quadro.mode != "RGBA" else quadro


def enquadrar(img: Image.Image, escala: float = 1.0, centro=(0.5, 0.5), rotacao: float = 0.0,
              desloc=(0.0, 0.0)) -> Image.Image:
    """Zoom de câmera no quadro: escala>1 aproxima em torno de 'centro' (frações 0-1).
    desloc em pixels move o enquadramento. Nunca mostra borda vazia (limita o centro)."""
    if escala <= 1.0005 and abs(rotacao) < 0.01 and desloc == (0.0, 0.0):
        return img
    W, H = img.size
    escala = max(1.0, escala)
    cw, ch = W / escala, H / escala
    cx = limitar(centro[0] * W - desloc[0] / escala, cw / 2, W - cw / 2)
    cy = limitar(centro[1] * H - desloc[1] / escala, ch / 2, H - ch / 2)
    if abs(rotacao) >= 0.01:
        img = img.rotate(rotacao, resample=Image.BICUBIC, center=(cx, cy))
        # gira um pouco mais para esconder cantos
        extra = 1 + abs(math.sin(math.radians(rotacao))) * 0.9
        cw, ch = cw / extra, ch / extra
    caixa = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return img.resize((W, H), Image.BICUBIC, box=caixa)


def recortar_pessoa(quadro: Image.Image, mascara: Image.Image | None) -> Image.Image | None:
    """Camada RGBA só com a pessoa (para colar POR CIMA de elementos que passam atrás dela)."""
    if mascara is None:
        return None
    p = quadro.convert("RGBA").copy()
    if mascara.size != p.size:
        mascara = mascara.resize(p.size, Image.BILINEAR)
    p.putalpha(mascara)
    return p


def _soma_caixa(x: np.ndarray, raio: int) -> np.ndarray:
    """Soma de cada janela (2*raio+1)² ao redor do pixel (borda: só o que existe dentro da imagem)."""
    try:
        import cv2
        k = (2 * raio + 1, 2 * raio + 1)
        return cv2.boxFilter(x, -1, k, normalize=False, borderType=cv2.BORDER_CONSTANT)
    except ImportError:
        pad = [(raio + 1, raio)] * 2 + [(0, 0)] * (x.ndim - 2)
        c = np.pad(x, pad).cumsum(0).cumsum(1)
        n = 2 * raio + 1
        return c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]


def limpar_borda(quadro: Image.Image, mascara: Image.Image, raio: int | None = None) -> Image.Image:
    """Tira a cor do fundo antigo da borda da pessoa: na faixa meio transparente (0,05 < alfa < 0,95) cada pixel
    vira a média das cores da pessoa vizinha (alfa > 0,97). Fora da faixa o quadro sai idêntico. Sem isso, colada
    sobre outro fundo, a pessoa leva junto uma auréola com a cor do chão ou da parede de onde foi gravada."""
    rgb = quadro.convert("RGB")
    if mascara.size != rgb.size:
        mascara = mascara.resize(rgb.size, Image.BILINEAR)
    m = np.asarray(mascara.convert("L"))
    faixa = (m > 12) & (m <= 242)  # 0,05 < alfa < 0,95 (em 0-255, sem converter o quadro inteiro)
    ys, xs = np.nonzero(faixa)
    if not len(ys):
        return rgb
    W, H = rgb.size
    raio = raio or max(3, W // 120)
    mg = 8 * raio  # só a região em volta da faixa: o resto do quadro não muda
    y0, y1, x0, x1 = max(0, ys.min() - mg), min(H, ys.max() + mg + 1), max(0, xs.min() - mg), min(W, xs.max() + mg + 1)
    out = np.asarray(rgb).copy()
    q = out[y0:y1, x0:x1].astype(np.float32)
    peso = (m[y0:y1, x0:x1] >= 248).astype(np.float32)  # alfa > 0,97: pessoa "cheia"
    f = faixa[y0:y1, x0:x1]
    # a cor da pessoa vizinha muda devagar: calcula em resolução reduzida (k vezes) e amplia (bem mais rápido)
    k = max(1, raio // 3)
    hk, wk = (y1 - y0) // k, (x1 - x0) // k
    if k > 1 and hk > 2 and wk > 2:
        qp = q[:hk * k, :wk * k] * peso[:hk * k, :wk * k, None]
        try:
            import cv2
            pk = cv2.resize(peso[:hk * k, :wk * k], (wk, hk), interpolation=cv2.INTER_AREA)
            qk = cv2.resize(qp, (wk, hk), interpolation=cv2.INTER_AREA)
        except ImportError:
            pk = peso[:hk * k, :wk * k].reshape(hk, k, wk, k).mean((1, 3))
            qk = qp.reshape(hk, k, wk, k, 3).mean((1, 3))
        qk = qk / np.maximum(pk, 1e-6)[..., None]
    else:
        k, hk, wk, pk, qk = 1, y1 - y0, x1 - x0, peso, q
    cor_k = np.zeros((hk, wk, 3), np.float32)
    falta_k = np.ones((hk, wk), bool)
    r = max(1, raio // k)
    while falta_k.any() and r <= 8 * max(1, raio // k):  # faixa mais larga que o raio: aumenta até achar a pessoa
        den = _soma_caixa(pk, r)
        num = _soma_caixa(qk * pk[..., None], r)
        ok = falta_k & (den > 0.5 / (k * k))
        cor_k[ok] = num[ok] / den[ok][:, None]
        falta_k &= ~ok
        r *= 2
    if k > 1:  # de volta ao tamanho da região (a sobra da divisão repete a última linha/coluna)
        iy = np.minimum(np.arange(y1 - y0) // k, hk - 1)
        ix = np.minimum(np.arange(x1 - x0) // k, wk - 1)
        cor, falta = cor_k[iy][:, ix], falta_k[iy][:, ix]
    else:
        cor, falta = cor_k, falta_k
    troca = f & ~falta
    bloco = out[y0:y1, x0:x1]
    bloco[troca] = np.clip(cor[troca] + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(out, "RGB")


def escurecer(img: Image.Image, quanto: float = 0.35, cor_base=(0, 0, 0)):
    if quanto <= 0:
        return img
    img.alpha_composite(Image.new("RGBA", img.size, (*cor_base[:3], int(255 * limitar(quanto)))))
    return img


def desfocar(img: Image.Image, raio: float) -> Image.Image:
    if raio <= 0.3:
        return img
    peq = img.resize((max(1, img.width // 3), max(1, img.height // 3)), Image.BILINEAR)
    peq = peq.filter(ImageFilter.GaussianBlur(raio / 3))
    return peq.resize(img.size, Image.BILINEAR)


@lru_cache(maxsize=8)
def _vinheta(w, h, forca_pct: int):
    y, x = np.ogrid[0:h, 0:w]
    d = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2)
    a = np.clip((d - 0.55) / 0.85, 0, 1) ** 1.6 * (forca_pct / 100) * 255
    m = Image.fromarray(a.astype(np.uint8), "L")
    v = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    v.putalpha(m)
    return v


def vinheta(img: Image.Image, forca: float = 0.45):
    img.alpha_composite(_vinheta(img.width, img.height, int(forca * 100)))
    return img


def brilho_neon(camada: Image.Image, cor_brilho=NEON, raio: float = 14, forca: float = 0.8) -> Image.Image:
    """Halo luminoso ao redor de uma camada (texto/ícone)."""
    pad = int(raio * 2.5)
    out = Image.new("RGBA", (camada.width + pad * 2, camada.height + pad * 2), (0, 0, 0, 0))
    g = Image.new("RGBA", camada.size, cor(cor_brilho))
    g.putalpha(camada.getchannel("A").point(lambda v: int(v * forca)))
    out.alpha_composite(g, (pad, pad))
    out = out.filter(ImageFilter.GaussianBlur(raio))
    out.alpha_composite(camada, (pad, pad))
    return out


# ---------------------------------------------------------------- ícones vetoriais simples

def icone(nome: str, tam: int, cor_ic=BRANCO, espessura: float = 0.11) -> Image.Image:
    """Ícones desenhados (sem arquivos): check, x, seta_cima, seta_baixo, seta_dir, play, estrela,
    raio, alvo, grafico, dinheiro, coracao, ponto. Super-amostrado para bordas limpas."""
    ss = 4
    S = tam * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = cor(cor_ic)
    e = max(1, int(S * espessura))
    if nome == "check":
        d.line([(S * .2, S * .52), (S * .42, S * .74), (S * .82, S * .28)], fill=c, width=e, joint="curve")
    elif nome == "x":
        d.line([(S * .25, S * .25), (S * .75, S * .75)], fill=c, width=e)
        d.line([(S * .75, S * .25), (S * .25, S * .75)], fill=c, width=e)
    elif nome in ("seta_cima", "seta_baixo", "seta_dir"):
        pts = [(S * .5, S * .15), (S * .85, S * .55), (S * .62, S * .55), (S * .62, S * .85),
               (S * .38, S * .85), (S * .38, S * .55), (S * .15, S * .55)]
        d.polygon(pts, fill=c)
        im = im.rotate({"seta_cima": 0, "seta_baixo": 180, "seta_dir": -90}[nome], resample=Image.BICUBIC)
    elif nome == "play":
        d.polygon([(S * .3, S * .2), (S * .82, S * .5), (S * .3, S * .8)], fill=c)
    elif nome == "estrela":
        pts = []
        for i in range(10):
            r = S * (.45 if i % 2 == 0 else .19)
            a = math.pi / 2 + i * math.pi / 5
            pts.append((S / 2 + r * math.cos(a), S / 2 - r * math.sin(a)))
        d.polygon(pts, fill=c)
    elif nome == "raio":
        d.polygon([(S * .58, S * .08), (S * .22, S * .56), (S * .48, S * .56), (S * .4, S * .92),
                   (S * .78, S * .42), (S * .52, S * .42)], fill=c)
    elif nome == "alvo":
        for k, w in ((.42, e), (.27, e), (.1, 0)):
            if w:
                d.ellipse([S * (.5 - k), S * (.5 - k), S * (.5 + k), S * (.5 + k)], outline=c, width=w)
            else:
                d.ellipse([S * (.5 - k), S * (.5 - k), S * (.5 + k), S * (.5 + k)], fill=c)
    elif nome == "grafico":
        for i, hh in enumerate((.3, .5, .72)):
            x0 = S * (.15 + i * .25)
            d.rounded_rectangle([x0, S * (.85 - hh), x0 + S * .17, S * .85], S * .03, fill=c)
    elif nome == "dinheiro":
        d.ellipse([S * .1, S * .1, S * .9, S * .9], outline=c, width=e)
        f = fonte(int(S * .55), 800)
        d.text((S * .5, S * .52), "$", font=f, fill=c, anchor="mm")
    elif nome == "coracao":
        d.ellipse([S * .1, S * .2, S * .52, S * .6], fill=c)
        d.ellipse([S * .48, S * .2, S * .9, S * .6], fill=c)
        d.polygon([(S * .12, S * .47), (S * .88, S * .47), (S * .5, S * .88)], fill=c)
    else:  # ponto
        d.ellipse([S * .3, S * .3, S * .7, S * .7], fill=c)
    return im.resize((tam, tam), Image.LANCZOS)
