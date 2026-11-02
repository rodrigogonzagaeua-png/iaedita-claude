"""19 · Split dinâmico — nos momentos de dado a tela se divide: o vídeo desce e vira um cartão de cantos
arredondados na metade de baixo, e um painel escuro (palco) cresce em cima com o dado da fala: gráfico de
linha e barras, número grande contando, comparação em barras, lista de tópicos ou frase de impacto.
Depois o cartão volta para a tela cheia. Uma linha verde luminosa marca a divisão e a legenda (pílula com
contorno verde) pousa em cima dela enquanto a tela está dividida.

Não precisa recortar a pessoa: o vídeo inteiro vai para o cartão, reenquadrado no rosto. Feito para plano
fechado (rosto grande) e funciona também em plano médio/aberto (o cartão aproxima um pouco a câmera).

Painéis encostados (menos de 1,5 s entre um e outro) dividem a mesma abertura: a tela fica dividida e só o
conteúdo do palco troca, sem o cartão subir e descer à toa."""
from __future__ import annotations

import bisect
import math
import re
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import desenho as d
from ..legenda import agrupar

TIPOS_PAINEL = ("grafico", "numero", "comparacao", "topicos", "frase")

INFO = {
    "id": "19-split-dinamico",
    "nome": "Split dinâmico",
    "precisa_recorte": False,
    "antes": 0.0,      # a abertura começa no 'inicio'
    "depois": 0.7,     # o palco fica até o 'fim'; a volta para a tela cheia (0,62 s) acontece DEPOIS do fim
    # legenda da prévia aprovada: pílula escura com contorno verde, 1 linha, palavra falada em verde-claro;
    # o estilo desenha a legenda (ela pousa na linha da divisão quando a tela está dividida)
    "legenda": {"peso": 750, "tamanho": 0.05, "cor": "#FFFFFF", "destaque": "#D4ED80", "caixa": "#101919EE",
                "borda": "#C9F366", "max_caracteres": 20, "max_linhas": 1, "maiusculas": False},
    "legenda_propria": True,
    "eventos": {
        "grafico": "inicio (a tela começa a dividir, na palavra do dado), fim (o palco fica até aqui; a tela volta "
                   "ao normal nos 0,6 s seguintes; 3-7 s), "
                   "titulo (2-5 palavras, até 28 letras), rotulo (opcional: 1-4 palavras acima do título, até 24 "
                   "letras), forma ('subida' padrão | 'queda'), valores (opcional: 3-8 números reais em ordem), "
                   "marca (opcional: selo no fim da linha, até 12 letras, ex. '+300%'), eixo (opcional: "
                   "[esquerda, direita], até 14 letras cada, ex. ['2019', 'Hoje']), som",
        "numero": "inicio, fim (2,5-6 s), valor (o número como a pessoa disse, ex. '26', '3 milhões', '70%', "
                  "'R$ 10 mil', '2,5x'; até 14 letras), titulo (o que o número significa, 2-5 palavras), "
                  "rotulo (opcional), som",
        "comparacao": "inicio, fim (3-7 s), titulo, rotulo (opcional), itens (2 a 4: [{\"rotulo\": \"Antes\", "
                      "\"valor\": \"2 mil\"}, ...]; rotulo até 12 letras, valor até 10), destaque (opcional: "
                      "número do item que fica verde, 1 = primeiro; padrão = o último), som",
        "topicos": "inicio, fim (3-8 s), titulo, rotulo (opcional), itens (2 a 4 textos de até 24 letras, ou "
                   "{\"texto\": \"...\", \"em\": segundo exato em que a pessoa fala aquele item}), som",
        "frase": "inicio, fim (2,5-5 s), titulo (a frase de impacto, 3-9 palavras, até 48 letras), marca "
                 "(opcional: 1-2 palavras da frase que ficam verdes), rotulo (opcional), som",
    },
}

# ------------------------------------------------------------------ paleta (da prévia aprovada)
ACENTO = "#C2F33D"
FUNDO = np.array([6, 18, 25], np.float32)       # #061219 — palco escuro esverdeado
TITULO = "#F6F8EE"
TEXTO_EIXO = "#D3DBDE"
BORDA_CARTAO = (141, 152, 158, 255)             # #8D989E
CINZA_BARRA = "#8D989E"
CENTRO_PONTO = "#121B22"
TINTA_SELO = "#0E1A0C"

# ------------------------------------------------------------------ geometria (frações da tela)
Y_DIV = 0.47           # topo do cartão (linha da divisão)
Y_BASE = 0.975         # base do cartão
MARGEM_X = 0.039       # margem lateral do cartão
TOPO = 0.118           # nada do palco acima disto (zona segura de cima)
PALCO_FIM = 0.425      # fim do palco (abaixo fica a legenda, na divisão)
PALCO_X0, PALCO_X1 = 0.08, 0.905
ZOOM_MAX = 1.30        # aproximação máxima do vídeo no cartão (plano médio/aberto)
ROSTO_NO_CARTAO = 0.42  # largura do rosto desejada no cartão (fração da largura do cartão)
JUNTAR = 1.5           # painéis com intervalo menor que isto dividem a mesma abertura
T_ABRE, T_FECHA = 0.85, 0.62


def _u(W, H):
    return min(W, H * 9 / 16)


# ------------------------------------------------------------------ curvas


def _bezier(x1, y1, x2, y2):
    """Curva CSS cubic-bezier(x1,y1,x2,y2) como função 0-1 (para casar com a prévia aprovada)."""
    def f(k):
        k = d.limitar(k)
        if k <= 0 or k >= 1:
            return k
        a, b = 0.0, 1.0
        for _ in range(22):
            m = (a + b) / 2
            x = 3 * (1 - m) ** 2 * m * x1 + 3 * (1 - m) * m * m * x2 + m ** 3
            if x < k:
                a = m
            else:
                b = m
        m = (a + b) / 2
        return 3 * (1 - m) ** 2 * m * y1 + 3 * (1 - m) * m * m * y2 + m ** 3
    return f


SUAVE = _bezier(0.2, 0.7, 0.3, 1.0)   # 'smooth' da prévia


def _mola(t):
    """Mola sem passar do ponto (prévia: damping 24, stiffness 150): começa macio, assenta firme.
    t em segundos desde o início da abertura; chega exatamente a 1 em T_ABRE."""
    if t <= 0:
        return 0.0
    if t >= T_ABRE:
        return 1.0
    w = 8.2
    def f(x):
        return 1 - (1 + w * x) * math.exp(-w * x)
    return f(t) / f(T_ABRE)


def _rampa(t, t0, dur, curva=SUAVE):
    return curva(d.mapear(t, t0, t0 + dur))


# ------------------------------------------------------------------ texto


def _txt(txt, f, cor_txt, tracking=0.0):
    """Camada RGBA justa com o texto. tracking em fração do tamanho da fonte (negativo = mais apertado)."""
    asc, desc = f.getmetrics()
    tr = tracking * f.size
    larg = f.getlength(txt) + tr * max(0, len(txt) - 1)
    cam = Image.new("RGBA", (max(2, int(math.ceil(larg)) + 4), asc + desc + 2), (0, 0, 0, 0))
    dr = ImageDraw.Draw(cam)
    c = d.cor(cor_txt)
    if abs(tr) < 0.3:
        dr.text((1, 0), txt, font=f, fill=c)
    else:
        for i, ch in enumerate(txt):
            if ch != " ":
                dr.text((1 + f.getlength(txt[:i]) + i * tr, 0), ch, font=f, fill=c)
    return cam


def _larg(txt, f, tracking=0.0):
    return f.getlength(txt) + tracking * f.size * max(0, len(txt) - 1)


def _caber(txt, f_tam_max, f_tam_min, peso, largura, tracking=0.0):
    """Maior fonte (entre max e min) em que o texto cabe em 1 linha."""
    tam = int(f_tam_max)
    while tam > f_tam_min:
        f = d.fonte(tam, peso)
        if _larg(txt, f, tracking) <= largura:
            return f
        tam = int(tam * 0.94)
    return d.fonte(int(f_tam_min), peso)


_NUM = re.compile(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _ler_numero(txt):
    """'R$ 10 mil' -> ('R$ ', 10.0, 0, ' mil', False). None se não houver número."""
    txt = str(txt)
    m = _NUM.search(txt)
    if not m:
        return None
    s = m.group(0)
    milhar = "." in s
    inteiro, _, frac = s.partition(",")
    v = float(inteiro.replace(".", "") + ("." + frac if frac else ""))
    return txt[:m.start()], v, len(frac), txt[m.end():], milhar


def _formatar(v, casas, milhar):
    s = f"{v:,.{casas}f}" if milhar else f"{v:.{casas}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


# ------------------------------------------------------------------ máscaras rápidas de cantos arredondados


@lru_cache(maxsize=256)
def _cantos(r):
    ss = 4
    R = r * ss
    q = Image.new("L", (R, R), 0)
    ImageDraw.Draw(q).ellipse((0, 0, 2 * R - 1, 2 * R - 1), fill=255)
    q = q.resize((r, r), Image.LANCZOS)
    return (q, q.transpose(Image.FLIP_LEFT_RIGHT), q.transpose(Image.FLIP_TOP_BOTTOM), q.transpose(Image.ROTATE_180))


def _mascara(w, h, r):
    m = Image.new("L", (max(1, w), max(1, h)), 255)
    r = int(min(r, w // 2, h // 2))
    if r >= 1:
        a, b, c_, e = _cantos(r)
        m.paste(a, (0, 0))
        m.paste(b, (w - r, 0))
        m.paste(c_, (0, h - r))
        m.paste(e, (w - r, h - r))
    return m


def _anel(w, h, r, b):
    """Máscara L de uma borda de espessura b por dentro do retângulo arredondado."""
    fora = _mascara(w, h, r)
    if b < 0.6 or w <= 2 * b + 2 or h <= 2 * b + 2:
        return None
    bi = int(round(b))
    dentro = Image.new("L", (w, h), 0)
    dentro.paste(_mascara(w - 2 * bi, h - 2 * bi, max(0, r - bi)), (bi, bi))
    return ImageChops.subtract(fora, dentro)


# ------------------------------------------------------------------ estado (pré-calculado uma vez por processo)


def preparar(g):
    est = _estado(g)
    # pré-desenha os palcos uma vez (tira o pico de 200-400 ms do primeiro quadro de cada painel)
    prep = {"grafico": _prep_grafico, "numero": _prep_numero, "comparacao": _prep_comparacao,
            "topicos": _prep_topicos, "frase": _prep_frase}
    for b in est["blocos"]:
        for e in b["paineis"]:
            try:
                prep[e["tipo"]](g, e)
            except Exception:
                pass      # se falhar aqui, o quadro tenta de novo (e mostra o erro de verdade)


def _estado(g):
    est = g.cache.get("e19")
    if est is not None:
        return est
    paineis = [e for e in g.plano["eventos"] if e.get("tipo") in TIPOS_PAINEL]
    paineis.sort(key=lambda e: e["inicio"])
    blocos = []
    for e in paineis:
        if blocos and e["inicio"] - blocos[-1]["fim"] < JUNTAR:
            blocos[-1]["paineis"].append(e)
            blocos[-1]["fim"] = max(blocos[-1]["fim"], e["fim"])
        else:
            blocos.append({"s": e["inicio"], "fim": e["fim"], "paineis": [e]})
    dur_video = float(getattr(g, "duracao", 0) or 0)
    for bi, b in enumerate(blocos):
        b["id"] = bi
        # 'fim' do plano = o palco fica na tela até aqui; o cartão volta para a tela cheia DEPOIS (T_FECHA)
        b["fim"] = max(b["fim"], b["s"] + T_ABRE + 0.4)
        b["e"] = b["fim"] + T_FECHA
        if dur_video > 0 and b["e"] > dur_video:     # sem tempo para voltar: fecha junto com o fim do vídeo
            b["e"] = max(b["s"] + T_ABRE + 0.3, dur_video)
    leg = g.plano.get("legenda", {}) or {}
    perfil = dict(INFO["legenda"])
    perfil.update(leg.get("perfil") or {})
    est = {"blocos": blocos, "inis": [b["s"] for b in blocos],
           "leg": _Legenda(g, perfil) if leg.get("ativa", True) and g.palavras else None}
    g.cache["e19"] = est
    return est


def _bloco_em(est, t):
    i = bisect.bisect_right(est["inis"], t) - 1
    if i < 0:
        return None
    b = est["blocos"][i]
    return b if t <= b["e"] else None


def _k_split(b, t):
    abre = _mola(t - b["s"])
    fecha = 1 - SUAVE(d.mapear(t, b["e"] - T_FECHA, b["e"]))
    return max(0.0, min(abre, fecha))


# ------------------------------------------------------------------ enquadramento do cartão


def _enquadre(g, b):
    """Centro (px da fonte) e escala do vídeo dentro do cartão, fixos durante o bloco (câmera estável)."""
    if "crop" in b:
        return b["crop"]
    W, H = g.W, g.H
    ts = np.arange(b["s"], b["e"] + 1e-6, 0.25)
    caixas = np.array([g.rosto.em(float(t)) for t in ts])
    fx0, fy0, fx1, fy1 = np.median(caixas, axis=0)
    cw, ch = W * (1 - 2 * MARGEM_X), H * (Y_BASE - Y_DIV)
    crop_w = d.limitar((fx1 - fx0) / ROSTO_NO_CARTAO, W / ZOOM_MAX, W)
    crop_h = crop_w * ch / cw
    if crop_h > H:
        crop_h = H
        crop_w = crop_h * cw / ch
    s1 = cw / crop_w
    ccx = (fx0 + fx1) / 2
    ccy = (fy0 + fy1) / 2 + 0.14 * crop_h       # rosto acima do meio do cartão (boca longe dos 20% de baixo)
    b["crop"] = (float(ccx), float(ccy), float(s1))
    return b["crop"]


def _geometria(g, b, k):
    W, H, u = g.W, g.H, _u(g.W, g.H)
    cx0, cy0, cx1, cy1 = MARGEM_X * W, Y_DIV * H, W - MARGEM_X * W, Y_BASE * H
    x0, y0 = d.lerp(0, cx0, k), d.lerp(0, cy0, k)
    x1, y1 = d.lerp(W, cx1, k), d.lerp(H, cy1, k)
    ix, iy = int(round(x0)), int(round(y0))
    iw, ih = int(round(x1)) - ix, int(round(y1)) - iy
    ccx, ccy, s1 = _enquadre(g, b)
    s = math.exp(d.lerp(0.0, math.log(s1), k))
    s = max(s, iw / W, ih / H)
    cx, cy = d.lerp(W / 2, ccx, k), d.lerp(H / 2, ccy, k)
    bw, bh = iw / s, ih / s
    cx = d.limitar(cx, bw / 2, W - bw / 2)
    cy = d.limitar(cy, bh / 2, H - bh / 2)
    caixa = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
    return {"ix": ix, "iy": iy, "iw": iw, "ih": ih, "caixa": caixa,
            "raio": int(round(0.044 * u * k)), "borda": 0.0037 * u * k}


# ------------------------------------------------------------------ fundo do palco (barato: em 1/8 da resolução)


@lru_cache(maxsize=4)
def _brilhos(sw, sh):
    y, x = np.mgrid[0:sh, 0:sw].astype(np.float32)
    x /= sw
    y /= sh
    ac = np.array(d.cor(ACENTO)[:3], np.float32)
    g1 = np.clip(1 - np.sqrt(((x - 0.9) / 0.5) ** 2 + ((y - 0.09) / 0.46) ** 2), 0, 1) * 0.13
    g2 = np.clip(1 - np.sqrt((x / 0.42) ** 2 + ((y - 0.45) / 0.3) ** 2), 0, 1) * 0.08
    return (g1 + g2)[..., None] * ac[None, None, :]


def _fundo(c, k, geo):
    W, H = c.W, c.H
    fator = 8
    sw, sh = max(8, W // fator), max(8, H // fator)
    # amostra rápida (vizinho mais próximo) + desfoque largo: o fundo fica 81% escuro, ninguém vê a diferença
    peq = c.fonte.resize((sw, sh), Image.NEAREST).convert("RGB").filter(ImageFilter.GaussianBlur(2.6))
    arr = np.asarray(peq, np.float32) * 0.19 + FUNDO * 0.81
    arr += _brilhos(sw, sh) * k
    # sombra do cartão (0 24px 75px #00000078), no fundo pequeno
    som = Image.new("L", (sw, sh), 0)
    dy = 0.0125 * H * k / fator
    ImageDraw.Draw(som).rounded_rectangle(
        (geo["ix"] / fator, geo["iy"] / fator + dy, (geo["ix"] + geo["iw"]) / fator, (geo["iy"] + geo["ih"]) / fator + dy),
        radius=max(0, geo["raio"] / fator), fill=255)
    som = som.filter(ImageFilter.GaussianBlur(max(0.5, 0.034 * H / fator)))
    arr *= 1 - (np.asarray(som, np.float32)[..., None] / 255.0) * 0.47 * k
    a4 = np.empty((sh, sw, 4), np.uint8)
    a4[..., :3] = np.clip(arr, 0, 255)
    a4[..., 3] = 255
    peq = Image.fromarray(a4, "RGBA")
    if k < 0.999:
        return peq.resize((W, H), Image.BILINEAR)
    # tela já dividida: o cartão cobre quase toda a metade de baixo — amplia só as faixas que aparecem
    img = Image.new("RGBA", (W, H), (int(FUNDO[0]), int(FUNDO[1]), int(FUNDO[2]), 255))
    fx, fy = W / sw, H / sh
    r = geo["raio"] + 2
    x0c, y0c, x1c, y1c = geo["ix"], geo["iy"], geo["ix"] + geo["iw"], geo["iy"] + geo["ih"]
    for (x0, y0, x1, y1) in ((0, 0, W, y0c + r), (0, y0c + r, x0c + r, H), (x1c - r, y0c + r, W, H),
                             (x0c + r, y1c - r, x1c - r, H)):
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        if x1 - x0 < 1 or y1 - y0 < 1:
            continue
        faixa = peq.resize((x1 - x0, y1 - y0), Image.BILINEAR, box=(x0 / fx, y0 / fy, x1 / fx, y1 / fy))
        img.paste(faixa, (x0, y0))
    return img


def _linha_divisao(g):
    chave = ("e19", "linha")
    if chave not in g.cache:
        W, H, u = g.W, g.H, _u(g.W, g.H)
        alt = int(0.06 * u) | 1
        x = np.linspace(-1, 1, W, dtype=np.float32)
        perfil = np.clip(1 - np.abs(x), 0, 1) ** 0.9
        ac = d.cor(ACENTO)
        espessura = max(2, int(round(0.0028 * u)))
        a = np.zeros((alt, W), np.float32)
        y0 = alt // 2 - espessura // 2
        a[y0:y0 + espessura] = perfil * 255
        nucleo = Image.fromarray(a.astype(np.uint8), "L")
        brilho = nucleo.filter(ImageFilter.GaussianBlur(0.012 * u)).point(lambda v: min(255, int(v * 2.6 * 0.6)))
        cam = Image.new("RGBA", (W, alt), ac[:3] + (0,))
        cam.putalpha(ImageChops.lighter(brilho, nucleo))
        g.cache[chave] = cam
    return g.cache[chave]


# ------------------------------------------------------------------ cartão com o vídeo


def _cartao(c, img, geo, k):
    iw, ih = geo["iw"], geo["ih"]
    if iw < 4 or ih < 4:
        return
    # recorta só a área usada, em RGB (bem mais rápido que reamostrar o RGBA inteiro); bilinear basta aqui
    bx0, by0, bx1, by1 = geo["caixa"]
    qx0, qy0 = max(0, int(math.floor(bx0)) - 1), max(0, int(math.floor(by0)) - 1)
    qx1, qy1 = min(c.W, int(math.ceil(bx1)) + 1), min(c.H, int(math.ceil(by1)) + 1)
    vid = c.fonte.crop((qx0, qy0, qx1, qy1)).convert("RGB").resize(
        (iw, ih), Image.BILINEAR, box=(bx0 - qx0, by0 - qy0, bx1 - qx0, by1 - qy0))
    chave = ("e19", "masc", iw, ih, geo["raio"], round(geo["borda"], 1))
    cache = c.g.cache
    if chave not in cache:
        u = _u(c.W, c.H)
        m = _mascara(iw, ih, geo["raio"])
        anel = _anel(iw, ih, geo["raio"], geo["borda"])
        # brilho interno claro (inset 0 0 0 14px #c8d0d319)
        faixa = None
        b = geo["borda"]
        t_int = 0.013 * u * k
        if anel is not None and t_int > 1:
            a1 = _anel(iw, ih, geo["raio"], b + t_int)
            faixa = ImageChops.subtract(a1, anel).point(lambda v: v * 25 // 255) if a1 is not None else None
        res = (m, anel, faixa)
        if k < 0.999:      # tamanhos de transição não se repetem: não guarda
            dados = res
        else:
            cache[chave] = res
            dados = res
    else:
        dados = cache[chave]
    m, anel, faixa = dados
    # só as faixas com cantos arredondados usam máscara; o miolo é colado direto (mais rápido)
    r = min(ih // 2, geo["raio"] + 1)
    if r >= 1 and ih > 2 * r:
        img.paste(vid.crop((0, r, iw, ih - r)), (geo["ix"], geo["iy"] + r))
        for (y0, y1) in ((0, r), (ih - r, ih)):
            img.paste(vid.crop((0, y0, iw, y1)), (geo["ix"], geo["iy"] + y0), m.crop((0, y0, iw, y1)))
    else:
        img.paste(vid, (geo["ix"], geo["iy"]), m)
    caixa = (geo["ix"], geo["iy"], geo["ix"] + iw, geo["iy"] + ih)
    if faixa is not None:
        img.paste((200, 208, 211, 255), caixa, faixa)
    if anel is not None:
        img.paste(BORDA_CARTAO, caixa, anel)


# ------------------------------------------------------------------ palco: cabeçalho comum


def _palco(g):
    W, H = g.W, g.H
    x0, x1 = int(PALCO_X0 * W), int(PALCO_X1 * W)
    y0, y1 = int(TOPO * H), int(PALCO_FIM * H)
    return x0, y0, x1 - x0, y1 - y0


def _cabecalho(g, e, alt_max_titulo, tam_max=0.088, tam_min=0.062, linhas_max=2):
    """Rótulo (verde, caixa alta, espaçado) + título (branco, apertado). Devolve (camada, altura)."""
    u = _u(g.W, g.H)
    _, _, SW, _ = _palco(g)
    partes = []
    y = 0
    rot = str(e.get("rotulo") or "").strip().upper()
    if rot:
        fr = _caber(rot, 0.037 * u, 0.036 * u, 600, SW, 0.08)
        cam = _txt(rot, fr, ACENTO, 0.08)
        partes.append((cam, 0))
        y = cam.height + int(0.012 * g.H)
    tit = str(e.get("titulo") or "").strip()
    if tit:
        f, linhas, al = d.ajustar_texto(tit, SW * 1.02, alt_max_titulo, 760, tam_max=int(tam_max * u),
                                        tam_min=int(tam_min * u), max_linhas=linhas_max, entrelinha=1.04)
        for li, l in enumerate(linhas):
            cam = _txt(l, f, TITULO, -0.035)
            partes.append((cam, int(y + li * al)))
        y += int(al * len(linhas))
    alt = max(2, y + 4)
    camada = Image.new("RGBA", (SW, alt), (0, 0, 0, 0))
    for cam, yy in partes:
        camada.alpha_composite(cam, (0, yy))
    return camada, alt


# ------------------------------------------------------------------ painel: gráfico


VAL_LINHA = [0.114, 0.247, 0.196, 0.519, 0.411, 0.690, 0.614, 0.956]   # curva da prévia aprovada
VAL_BARRAS = [0.152, 0.234, 0.316, 0.411, 0.506, 0.601, 0.696, 0.791]


def _prep_grafico(g, e):
    chave = ("e19", "graf", id(e))
    if chave in g.cache:
        return g.cache[chave]
    W, H, u = g.W, g.H, _u(g.W, g.H)
    _, _, SW, SH = _palco(g)
    cab, cab_h = _cabecalho(g, e, SH * 0.34)
    eixo = e.get("eixo") or []
    if isinstance(eixo, str):
        eixo = [eixo]
    f_eixo = d.fonte(int(0.037 * u), 500)
    alt_rot = int(f_eixo.size * 1.35) if eixo else 0
    gy0 = cab_h + int(0.024 * H)
    gy1 = SH - alt_rot - int(0.006 * H)
    ch = max(int(0.08 * H), gy1 - gy0)
    cw = SW
    valores = e.get("valores")
    marca = str(e.get("marca") or "").strip()
    if isinstance(valores, (list, tuple)) and len(valores) >= 2:
        v = np.array([float(x) for x in valores], np.float32)
        lo, hi = float(v.min()), float(v.max())
        norm = (v - lo) / (hi - lo) if hi > lo else np.full_like(v, 0.5)
        linha = 0.1 + 0.86 * norm
        barras = 0.08 + 0.7 * norm
    else:
        linha, barras = np.array(VAL_LINHA), np.array(VAL_BARRAS)
        if str(e.get("forma", "subida")).lower().startswith("q"):
            linha, barras = linha[::-1], barras[::-1]
    if marca:   # espaço para o selo acima do último ponto
        linha = 0.06 + linha * 0.74
    n = len(linha)
    ss = 3
    pad = int(0.03 * u)                      # folga para brilho e pontos
    ax = int(0.004 * u) + 1                  # x do eixo vertical
    area_x0, area_x1 = ax + int(0.02 * cw), cw - int(0.02 * cw)
    passo = (area_x1 - area_x0) / n
    xs = [area_x0 + passo * (i + 0.5) for i in range(n)]
    base_y = ch - 2
    ys = [base_y - (ch - 6) * float(v) for v in linha]
    # estático: grade tracejada, verticais suaves e eixo em L
    est = Image.new("RGBA", (cw + 2 * pad, ch + 2 * pad), (0, 0, 0, 0))
    dr = ImageDraw.Draw(est)
    grade = d.cor("#DCE4E6", 0.10)
    traco, vazio = max(2, int(0.003 * u)), max(6, int(0.012 * u))
    for k_ in range(1, 5):
        yy = pad + base_y - (ch - 6) * k_ / 4.2
        xx = pad + ax
        while xx < pad + cw:
            dr.line([(xx, yy), (min(xx + traco, pad + cw), yy)], fill=grade, width=max(1, int(0.0016 * u)))
            xx += traco + vazio
    for xx in xs:
        dr.line([(pad + xx, pad + 4), (pad + xx, pad + base_y)], fill=d.cor("#DCE4E6", 0.06), width=1)
    eixo_cor = d.cor("#B5BFC3", 0.32)
    le = max(2, int(0.0019 * u))
    dr.line([(pad + ax, pad + 2), (pad + ax, pad + base_y), (pad + cw, pad + base_y)], fill=eixo_cor, width=le)
    # área sob a linha (gradiente verde 15% -> 0)
    ac = d.cor(ACENTO)
    S = (est.width * ss, est.height * ss)
    msk = Image.new("L", S, 0)
    pts = [((pad + x) * ss, (pad + y) * ss) for x, y in zip(xs, ys)]
    ImageDraw.Draw(msk).polygon(pts + [(pts[-1][0], (pad + base_y) * ss), (pts[0][0], (pad + base_y) * ss)], fill=255)
    msk = msk.resize(est.size, Image.LANCZOS)
    grad = np.linspace(0.17, 0.0, est.height, dtype=np.float32)[:, None]
    alfa = (np.asarray(msk, np.float32) * grad).astype(np.uint8)
    area = Image.new("RGBA", est.size, ac[:3] + (0,))
    area.putalpha(Image.fromarray(alfa, "L"))
    # linha: brilho largo desfocado + traço com cantos redondos (super-amostrado)
    lin = Image.new("RGBA", S, (0, 0, 0, 0))
    ImageDraw.Draw(lin).line(pts, fill=ac, width=int(0.0105 * u * ss), joint="curve")
    lin = lin.resize(est.size, Image.LANCZOS)
    brilho = lin.filter(ImageFilter.GaussianBlur(0.005 * u))
    brilho.putalpha(brilho.getchannel("A").point(lambda v: int(v * 0.6)))
    nuc = Image.new("RGBA", S, (0, 0, 0, 0))
    dn = ImageDraw.Draw(nuc)
    lw = max(2, int(0.0042 * u * ss))
    dn.line(pts, fill=ac, width=lw, joint="curve")
    for p in pts[:1] + pts[-1:]:
        dn.ellipse((p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2), fill=ac)
    nuc = nuc.resize(est.size, Image.LANCZOS)
    camada_linha = Image.new("RGBA", est.size, (0, 0, 0, 0))
    camada_linha.alpha_composite(brilho)
    camada_linha.alpha_composite(nuc)
    # barras (gradiente verde 95% -> 20%, opacidade 42%)
    bw = max(4, int(passo * 0.52))
    barra_img = []
    for i, v in enumerate(barras):
        bh = max(4, int((ch - 6) * float(v)))
        gr = np.linspace(0.95, 0.2, bh, dtype=np.float32)[:, None].repeat(bw, axis=1) * 0.42 * 255
        b = Image.new("RGBA", (bw, bh), ac[:3] + (0,))
        b.putalpha(Image.fromarray(gr.astype(np.uint8), "L"))
        mr = _mascara(bw, bh, max(1, int(0.005 * u)))
        b.putalpha(ImageChops.multiply(b.getchannel("A"), mr))
        barra_img.append(b)
    # pontos: halo verde 10% + centro escuro com anel verde
    rp = int(0.0145 * u)
    ponto = Image.new("RGBA", (rp * 2 * ss, rp * 2 * ss), (0, 0, 0, 0))
    dp = ImageDraw.Draw(ponto)
    dp.ellipse((0, 0, rp * 2 * ss - 1, rp * 2 * ss - 1), fill=ac[:3] + (30,))
    ri = 0.0058 * u * ss
    cc = rp * ss
    dp.ellipse((cc - ri, cc - ri, cc + ri, cc + ri), fill=d.cor(CENTRO_PONTO), outline=ac,
               width=max(2, int(0.0029 * u * ss)))
    ponto = ponto.resize((rp * 2, rp * 2), Image.LANCZOS)
    ponta = d.brilho_neon(d.icone("ponto", int(0.03 * u), "#F4FFD6"), ACENTO, 0.012 * u, 1.0)
    # rótulos do eixo
    rotulos = None
    if eixo:
        rotulos = Image.new("RGBA", (SW, alt_rot + 4), (0, 0, 0, 0))
        e0 = _txt(str(eixo[0]), f_eixo, TEXTO_EIXO, 0.01)
        rotulos.alpha_composite(e0, (int(ax), 0))
        if len(eixo) > 1:
            e1 = _txt(str(eixo[-1]), f_eixo, TEXTO_EIXO, 0.01)
            rotulos.alpha_composite(e1, (max(0, SW - e1.width), 0))
    selo = None
    if marca:
        fs = d.fonte(int(0.042 * u), 800)
        tx = _txt(marca, fs, TINTA_SELO, -0.01)
        sw_, sh_ = tx.width + int(0.034 * u), int(fs.size * 1.55)
        selo = d.painel(sw_, sh_, raio=sh_ // 2, fundo=ACENTO)
        selo.alpha_composite(tx, ((sw_ - tx.width) // 2, int((sh_ - tx.height) / 2 + fs.size * 0.02)))
        selo = d.brilho_neon(selo, ACENTO, 0.012 * u, 0.45)
    # comprimento acumulado do traço (o desenho anda com velocidade constante)
    seg = [math.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) for i in range(n - 1)]
    acum = np.concatenate([[0], np.cumsum(seg)])
    estatico = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    estatico.alpha_composite(cab, (0, 0))
    gx, gy = -pad, gy0 - pad
    _colar(estatico, est, gx, gy)
    if rotulos is not None:
        estatico.alpha_composite(rotulos, (0, min(SH - rotulos.height, gy0 + ch + int(0.006 * H))))
    r = {"estatico": estatico, "area": area, "linha": camada_linha, "barras": barra_img, "bw": bw,
         "ponto": ponto, "ponta": ponta, "selo": selo, "xs": xs, "ys": ys, "acum": acum, "pad": pad,
         "gx": gx, "gy": gy, "base_y": base_y}
    g.cache[chave] = r
    return r


def _colar(base, cam, x, y, opac=1.0):
    d.colar_em(base, cam, (x, y), opac)


def _desenhar_grafico(c, e, cam, ta, dur):
    r = _prep_grafico(c.g, e)
    cam.alpha_composite(r["estatico"])
    pad, gx, gy = r["pad"], r["gx"], r["gy"]
    G = d.limitar(dur * 0.42, 1.0, 1.85)
    # barras crescem em escada
    n = len(r["barras"])
    for i, b in enumerate(r["barras"]):
        k = SUAVE(d.mapear(ta, i * G * 0.075, i * G * 0.075 + G * 0.42))
        if k <= 0.01:
            continue
        hh = max(1, int(b.height * k))
        bb = b.resize((b.width, hh), Image.BILINEAR) if hh != b.height else b
        x = gx + pad + r["xs"][i] - r["bw"] / 2
        y = gy + pad + r["base_y"] - hh
        _colar(cam, bb, x, y)
    # linha desenhada da esquerda para a direita (velocidade constante no traço)
    p = d.suave(d.mapear(ta, 0, G)) if ta > 0 else 0.0
    if p <= 0:
        return
    acum, xs, ys = r["acum"], r["xs"], r["ys"]
    alvo = p * acum[-1]
    j = int(min(len(xs) - 2, np.searchsorted(acum, alvo, side="right") - 1))
    f = (alvo - acum[j]) / max(1e-6, acum[j + 1] - acum[j])
    xt = xs[j] + (xs[j + 1] - xs[j]) * f
    yt = ys[j] + (ys[j + 1] - ys[j]) * f
    corte = int(pad + xt + (r["pad"] if p >= 0.999 else 1))
    area = r["area"].crop((0, 0, max(1, corte), r["area"].height))
    _colar(cam, area, gx, gy, p)
    lin = r["linha"].crop((0, 0, max(1, corte), r["linha"].height))
    _colar(cam, lin, gx, gy)
    for i, (x, y) in enumerate(zip(xs, ys)):
        if acum[i] <= alvo + 0.5:
            tp = (acum[i] / max(1e-6, acum[-1])) * G
            k = d.saida(d.mapear(ta, tp, tp + 0.22))
            pt = r["ponto"]
            esc = 0.6 + 0.4 * d.mola(k, 1.4)
            d.colar(cam, pt, (gx + pad + x, gy + pad + y), escala=esc, opacidade=k)
    if p < 0.999:
        d.colar(cam, r["ponta"], (gx + pad + xt, gy + pad + yt), opacidade=0.95)
    if r["selo"] is not None:
        k = d.mapear(ta, G * 0.96, G * 0.96 + 0.32)
        if k > 0:
            s = r["selo"]
            x_ult, y_ult = gx + pad + xs[-1], gy + pad + ys[-1]
            cx = min(cam.width - s.width / 2 + 0.012 * c.W, max(s.width / 2, x_ult))
            cy = y_ult - s.height / 2 - 0.006 * c.H
            cy = max(cy, s.height / 2 - 0.02 * c.H)
            d.colar(cam, s, (cx, cy), escala=0.7 + 0.3 * d.mola(k, 1.7), opacidade=d.saida(k))


# ------------------------------------------------------------------ painel: número grande


def _prep_numero(g, e):
    chave = ("e19", "num", id(e))
    if chave in g.cache:
        return g.cache[chave]
    W, H, u = g.W, g.H, _u(g.W, g.H)
    _, _, SW, SH = _palco(g)
    rot_e = {"rotulo": e.get("rotulo")}
    cab, cab_h = _cabecalho(g, rot_e, 1)
    valor = str(e.get("valor", "")).strip()
    lido = _ler_numero(valor)
    if lido:
        pre, v, casas, suf, milhar = lido
    else:
        pre, v, casas, suf, milhar = "", None, 0, valor, False
    final = _formatar(v, casas, milhar) if v is not None else ""
    # tamanhos: número grande; prefixo/sufixo menores (símbolo curto 60%, palavra 42%)
    def tam_suf(s):
        s = s.strip()
        return 0.6 if len(s) <= 2 else 0.42
    titulo = str(e.get("titulo") or "").strip()
    reserva_tit = 0.30 * SH if titulo else 0
    F = int(0.27 * u)
    while F > 0.09 * u:
        fN = d.fonte(F, 820)
        fP = d.fonte(int(F * tam_suf(pre)), 760)
        fS = d.fonte(int(F * tam_suf(suf)), 760)
        larg = _larg(pre, fP, -0.02) + _larg(final, fN, -0.045) + _larg(suf, fS, -0.02)
        if not final:
            larg = _larg(suf, d.fonte(F, 820), -0.04)
        if larg <= SW * 0.98 and F * 0.86 <= SH - cab_h - reserva_tit - 0.035 * H:
            break
        F = int(F * 0.93)
    fN = d.fonte(F, 820)
    fP = d.fonte(int(F * tam_suf(pre)), 760)
    fS = d.fonte(int(F * tam_suf(suf)), 760) if final else fN
    asc_n = fN.getmetrics()[0]
    caixa_d = fN.getbbox("0123456789")
    topo_tinta = caixa_d[1]
    alt_tinta = caixa_d[3] - caixa_d[1]
    y_num = cab_h + int(0.004 * H) - topo_tinta     # topo da tinta logo abaixo do rótulo
    cam_tit, tit_h = None, 0
    if titulo:
        ft, linhas, al = d.ajustar_texto(titulo, SW, reserva_tit, 700, tam_max=int(0.066 * u),
                                         tam_min=int(0.045 * u), max_linhas=2, entrelinha=1.08)
        tit_h = int(al * len(linhas))
        cam_tit = Image.new("RGBA", (SW, tit_h + int(ft.size * 0.4)), (0, 0, 0, 0))
        for li, l in enumerate(linhas):
            cam_tit.alpha_composite(_txt(l, ft, TITULO, -0.02), (0, int(li * al)))
    y_tit = y_num + topo_tinta + alt_tinta + int(0.018 * H)
    # trilho do medidor no pé do palco
    trilho_y = min(SH - int(0.012 * H), y_tit + tit_h + int(0.03 * H))
    estatico = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    estatico.alpha_composite(cab, (0, 0))
    eh = max(3, int(0.0075 * u))
    trilho = d.painel(SW, eh, raio=eh // 2, fundo=d.cor("#DCE4E6", 0.13))
    estatico.alpha_composite(trilho, (0, trilho_y))
    pct = None
    if v is not None and "%" in suf and 0 < v <= 100:
        pct = v / 100.0
    # camada final do número (com brilho) — usada quando a contagem termina
    def compor(txt_num):
        partes = []
        if pre:
            partes.append(_txt(pre, fP, TITULO, -0.02))
        if txt_num:
            partes.append(_txt(txt_num, fN, ACENTO, -0.045))
        if suf.strip() or not txt_num:
            partes.append(_txt(suf.strip() if txt_num else suf, fS, TITULO, -0.02))
        return partes
    r = {"estatico": estatico, "pre": pre, "v": v, "casas": casas, "suf": suf, "milhar": milhar,
         "fN": fN, "fP": fP, "fS": fS, "asc_n": asc_n, "y_num": y_num, "cam_tit": cam_tit, "y_tit": y_tit,
         "trilho_y": trilho_y, "eh": eh, "pct": pct, "compor": compor, "final": final}
    g.cache[chave] = r
    return r


def _linha_numero(r, txt_num, cache, chave):
    """Monta prefixo + número + sufixo alinhados pela linha de base. Devolve a camada."""
    if chave in cache:
        return cache[chave]
    fN, fP, fS = r["fN"], r["fP"], r["fS"]
    partes = []
    if r["pre"]:
        partes.append((r["pre"], fP, TITULO, -0.02))
    if txt_num:
        partes.append((txt_num, fN, ACENTO, -0.045))
    suf = r["suf"]
    if suf.strip():
        partes.append((suf if not txt_num else suf, fS if txt_num else fN, TITULO, -0.02))
    asc_max = max(f.getmetrics()[0] for _, f, _, _ in partes)
    larg = sum(_larg(t, f, tr) for t, f, _, tr in partes) + 8
    alt = asc_max + max(f.getmetrics()[1] for _, f, _, _ in partes) + 4
    cam = Image.new("RGBA", (int(larg) + 4, int(alt)), (0, 0, 0, 0))
    x = 0.0
    for t, f, cor_t, tr in partes:
        tx = _txt(t, f, cor_t, tr)
        cam.alpha_composite(tx, (int(x), int(asc_max - f.getmetrics()[0])))
        x += _larg(t, f, tr)
    res = (cam, asc_max)
    if len(cache) < 400:
        cache[chave] = res
    return res


def _desenhar_numero(c, e, cam, ta, dur):
    r = _prep_numero(c.g, e)
    u = _u(c.W, c.H)
    cam.alpha_composite(r["estatico"])
    C = d.limitar(dur * 0.38, 0.8, 1.5)
    k = _bezier(0.16, 0.8, 0.3, 1.0)(d.mapear(ta, 0, C)) if ta > 0 else 0.0
    cache = c.g.cache.setdefault(("e19", "numtxt", id(e)), {})
    if r["v"] is not None:
        if k >= 0.999:
            txt = r["final"]
        else:
            vv = r["v"] * k
            txt = _formatar(round(vv, r["casas"]) if r["casas"] else math.floor(vv + 1e-9), r["casas"], r["milhar"])
    else:
        txt = ""
    linha, asc_max = _linha_numero(r, txt, cache, txt)
    y = r["y_num"] + r["asc_n"] - asc_max
    # o número "pousa": leve pulso de escala e brilho quando a contagem termina
    pouso = d.mapear(ta, C, C + 0.35)
    if r["v"] is None:
        aparece = d.saida(d.mapear(ta, 0, 0.4))
        d.colar(cam, linha, (linha.width / 2, y + linha.height / 2), escala=0.85 + 0.15 * d.mola(aparece, 1.5),
                opacidade=aparece)
    else:
        if k >= 0.999:
            chave = ("e19", "numfinal", id(e))
            if chave not in c.g.cache:
                c.g.cache[chave] = d.brilho_neon(linha, ACENTO, 0.02 * u, 0.32)
            gl = c.g.cache[chave]
            pad = (gl.width - linha.width) / 2
            esc = 1 + 0.045 * math.sin(math.pi * min(1.0, pouso)) if pouso < 1 else 1.0
            d.colar(cam, gl, (linha.width / 2 - 0 + 0, y + linha.height / 2), escala=esc)
            _ = pad
        else:
            _colar(cam, linha, 0, y, min(1.0, 0.35 + ta * 3))
    if r["cam_tit"] is not None:
        kt = d.saida(d.mapear(ta, 0.1, 0.5))
        _colar(cam, r["cam_tit"], 0, r["y_tit"] + (1 - kt) * 0.012 * c.H, kt)
    # medidor: enche junto com a contagem (até o % quando o valor é porcentagem)
    alvo = r["pct"] if r["pct"] is not None else 1.0
    larg = int(cam.width * alvo * (k if r["v"] is not None else d.saida(d.mapear(ta, 0, 0.9))))
    if larg > r["eh"]:
        chave = ("e19", "medidor", larg, r["eh"])
        barra = c.g.cache.get(chave)
        if barra is None:
            barra = d.brilho_neon(d.painel(larg, r["eh"], raio=r["eh"] // 2, fundo=ACENTO), ACENTO, 0.008 * u, 0.6)
            if len(c.g.cache) < 3000:
                c.g.cache[chave] = barra
        pad = (barra.height - r["eh"]) // 2
        _colar(cam, barra, -pad, r["trilho_y"] - pad)


# ------------------------------------------------------------------ painel: comparação em barras


def _prep_comparacao(g, e):
    chave = ("e19", "comp", id(e))
    if chave in g.cache:
        return g.cache[chave]
    W, H, u = g.W, g.H, _u(g.W, g.H)
    _, _, SW, SH = _palco(g)
    cab, cab_h = _cabecalho(g, e, SH * 0.34)
    itens = [it if isinstance(it, dict) else {"rotulo": str(it), "valor": ""} for it in (e.get("itens") or [])][:4]
    if len(itens) < 2:
        itens = (itens + [{"rotulo": "", "valor": ""}] * 2)[:2]
    n = len(itens)
    dest = int(e.get("destaque") or n) - 1
    dest = min(max(dest, 0), n - 1)
    f_val = d.fonte(int(0.056 * u), 800)
    f_rot = d.fonte(int(0.037 * u), 560)
    alt_rot = int(f_rot.size * 1.35)
    alt_val = int(f_val.size * 1.3)
    ay0 = cab_h + int(0.02 * H)
    base = SH - alt_rot - int(0.008 * H)
    hmax = max(int(0.05 * H), base - ay0 - alt_val)
    nums = []
    for it in itens:
        if it.get("altura") is not None:
            nums.append(("a", float(it["altura"])))
        else:
            lido = _ler_numero(it.get("valor", ""))
            nums.append(("v", lido[1] * _mult(lido[3]) if lido else None))
    if all(t == "v" and x is not None for t, x in nums):
        mx = max(x for _, x in nums) or 1.0
        alts = [max(0.1, x / mx) for _, x in nums]
    elif all(t == "a" for t, _ in nums):
        alts = [d.limitar(x, 0.08, 1.0) for _, x in nums]
    else:
        alts = [0.4 + 0.6 * i / max(1, n - 1) for i in range(n)]
    passo = SW / n
    bw = int(min(passo * 0.5, SW * 0.2))
    estatico = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    estatico.alpha_composite(cab, (0, 0))
    dr = ImageDraw.Draw(estatico)
    grade = d.cor("#DCE4E6", 0.10)
    traco, vazio = max(2, int(0.003 * u)), max(6, int(0.012 * u))
    for k_ in range(1, 4):
        yy = base - hmax * k_ / 3.2
        xx = 0
        while xx < SW:
            dr.line([(xx, yy), (min(xx + traco, SW), yy)], fill=grade, width=max(1, int(0.0016 * u)))
            xx += traco + vazio
    dr.line([(0, base), (SW, base)], fill=d.cor("#B5BFC3", 0.32), width=max(2, int(0.0019 * u)))
    barras, vals = [], []
    for i, it in enumerate(itens):
        cx = passo * (i + 0.5)
        rot = _txt(str(it.get("rotulo", "")), _caber(str(it.get("rotulo", "")), f_rot.size, 0.036 * u, 560,
                                                     passo * 0.96, 0.01), TEXTO_EIXO, 0.01)
        estatico.alpha_composite(rot, (int(cx - rot.width / 2), base + int(0.008 * H)))
        bh = max(6, int(hmax * alts[i]))
        verde = i == dest
        cor_b = ACENTO if verde else CINZA_BARRA
        a0, a1 = (0.95, 0.35) if verde else (0.55, 0.18)
        gr = np.linspace(a0, a1, bh, dtype=np.float32)[:, None].repeat(bw, axis=1) * 255
        b = Image.new("RGBA", (bw, bh), d.cor(cor_b)[:3] + (0,))
        b.putalpha(ImageChops.multiply(Image.fromarray(gr.astype(np.uint8), "L"),
                                       _mascara(bw, bh, max(2, int(0.008 * u)))))
        if verde:
            b = d.brilho_neon(b, ACENTO, 0.01 * u, 0.35)
        barras.append((b, cx, bh))
        vals.append(str(it.get("valor", "")))
    r = {"estatico": estatico, "barras": barras, "vals": vals, "base": base, "f_val": f_val, "dest": dest,
         "passo": passo}
    g.cache[chave] = r
    return r


def _mult(suf):
    s = str(suf).lower()
    if "bilh" in s:
        return 1e9
    if "milh" in s or "mi" == s.strip():
        return 1e6
    if "mil" in s or s.strip() == "k":
        return 1e3
    return 1.0


def _desenhar_comparacao(c, e, cam, ta, dur):
    r = _prep_comparacao(c.g, e)
    cam.alpha_composite(r["estatico"])
    passo = d.limitar(dur * 0.06, 0.14, 0.26)
    cresce = d.limitar(dur * 0.16, 0.5, 0.8)
    for i, (b, cx, bh) in enumerate(r["barras"]):
        t0 = i * passo
        k = SUAVE(d.mapear(ta, t0, t0 + cresce))
        if k <= 0.01:
            continue
        pad = (b.width - (b.width if i != r["dest"] else b.width)) // 2
        if i == r["dest"]:   # imagem com brilho tem folga em volta
            folga = (b.height - bh) // 2
            hh = max(1, int((b.height - 2 * folga) * k)) + 2 * folga
            bb = b.resize((b.width, hh), Image.BILINEAR)
            _colar(cam, bb, cx - b.width / 2, r["base"] - hh + folga)
            topo = r["base"] - (hh - 2 * folga)
        else:
            hh = max(1, int(bh * k))
            bb = b.resize((b.width, hh), Image.BILINEAR)
            _colar(cam, bb, cx - b.width / 2, r["base"] - hh)
            topo = r["base"] - hh
        _ = pad
        kv = d.saida(d.mapear(ta, t0 + cresce * 0.55, t0 + cresce * 0.55 + 0.3))
        if kv > 0 and r["vals"][i]:
            chave = ("e19", "compval", id(e), i)
            tx = c.g.cache.get(chave)
            if tx is None:
                f = _caber(r["vals"][i], r["f_val"].size, 0.04 * _u(c.W, c.H), 800, r["passo"] * 0.98, -0.03)
                tx = _txt(r["vals"][i], f, ACENTO if i == r["dest"] else TITULO, -0.03)
                c.g.cache[chave] = tx
            _colar(cam, tx, cx - tx.width / 2, topo - tx.height - 0.006 * c.H + (1 - kv) * 0.01 * c.H, kv)


# ------------------------------------------------------------------ painel: tópicos


def _itens_topicos(e):
    out = []
    for it in (e.get("itens") or [])[:4]:
        if isinstance(it, dict):
            out.append((str(it.get("texto", "")).strip(), it.get("em")))
        else:
            out.append((str(it).strip(), None))
    return out


def _prep_topicos(g, e):
    chave = ("e19", "top", id(e))
    if chave in g.cache:
        return g.cache[chave]
    W, H, u = g.W, g.H, _u(g.W, g.H)
    _, _, SW, SH = _palco(g)
    cab, cab_h = _cabecalho(g, e, SH * 0.3)
    itens = _itens_topicos(e)
    n = max(1, len(itens))
    y0 = cab_h + int(0.018 * H)
    rh = min(int(0.068 * H), (SH - y0) // n)
    diam = int(min(rh * 0.74, 0.078 * u))
    larg_txt = SW - diam - int(0.03 * u)
    f = None
    for txt, _ in itens:
        fi = _caber(txt, 0.056 * u, 0.04 * u, 650, larg_txt, -0.02)
        f = fi if f is None or fi.size < f.size else f
    f = f or d.fonte(int(0.05 * u), 650)
    estatico = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    estatico.alpha_composite(cab, (0, 0))
    dr = ImageDraw.Draw(estatico)
    grade = d.cor("#DCE4E6", 0.12)
    traco, vazio = max(2, int(0.003 * u)), max(6, int(0.012 * u))
    for i in range(1, n):
        yy = y0 + rh * i
        xx = 0
        while xx < SW:
            dr.line([(xx, yy), (min(xx + traco, SW), yy)], fill=grade, width=max(1, int(0.0016 * u)))
            xx += traco + vazio
    ss = 4
    linhas = []
    ac = d.cor(ACENTO)
    fnum = d.fonte(int(diam * 0.5), 800)
    for i, (txt, em) in enumerate(itens):
        circ = Image.new("RGBA", (diam * ss, diam * ss), (0, 0, 0, 0))
        dc = ImageDraw.Draw(circ)
        dc.ellipse((0, 0, diam * ss - 1, diam * ss - 1), fill=d.cor(CENTRO_PONTO), outline=ac,
                   width=max(2, int(0.0042 * u * ss)))
        circ = circ.resize((diam, diam), Image.LANCZOS)
        dn = ImageDraw.Draw(circ)
        dn.text((diam / 2, diam / 2 + diam * 0.02), str(i + 1), font=fnum, fill=ac, anchor="mm")
        circ = d.brilho_neon(circ, ACENTO, 0.008 * u, 0.25)
        tx = _txt(txt, f, TITULO, -0.02)
        yc = y0 + rh * (i + 0.5)
        linhas.append({"circ": circ, "tx": tx, "yc": yc, "em": em})
    r = {"estatico": estatico, "linhas": linhas, "diam": diam, "gap": int(0.03 * u)}
    g.cache[chave] = r
    return r


def _desenhar_topicos(c, e, cam, ta, dur, t_abs, t_anim):
    r = _prep_topicos(c.g, e)
    cam.alpha_composite(r["estatico"])
    n = max(1, len(r["linhas"]))
    passo = d.limitar((dur - 0.6) / n, 0.25, 0.6)
    for i, ln in enumerate(r["linhas"]):
        t0 = (float(ln["em"]) - t_anim) if ln["em"] is not None else i * passo
        t0 = max(0.0, t0)
        k = d.mapear(ta, t0, t0 + 0.38)
        if k <= 0:
            continue
        ks = d.saida(k)
        circ = ln["circ"]
        d.colar(cam, circ, (r["diam"] / 2, ln["yc"]), escala=0.5 + 0.5 * d.mola(k, 1.6), opacidade=ks)
        dx = (1 - ks) * 0.04 * c.W
        _colar(cam, ln["tx"], r["diam"] + r["gap"] - (circ.width - r["diam"]) * 0 + dx,
               ln["yc"] - ln["tx"].height / 2 - 0.002 * c.H, ks)


# ------------------------------------------------------------------ painel: frase de impacto


def _prep_frase(g, e):
    chave = ("e19", "frase", id(e))
    if chave in g.cache:
        return g.cache[chave]
    W, H, u = g.W, g.H, _u(g.W, g.H)
    _, _, SW, SH = _palco(g)
    rot_e = {"rotulo": e.get("rotulo")}
    cab, cab_h = _cabecalho(g, rot_e, 1)
    tit = str(e.get("titulo") or "").strip()
    marca = [m.strip(".,!?;:").lower() for m in str(e.get("marca") or "").split()]
    y0 = cab_h + (int(0.008 * H) if cab_h > 4 else 0)
    f, linhas, al = d.ajustar_texto(tit, SW * 1.02, SH - y0 - int(0.05 * H), 780, tam_max=int(0.1 * u),
                                    tam_min=int(0.06 * u), max_linhas=3, entrelinha=1.04)
    estatico = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
    estatico.alpha_composite(cab, (0, 0))
    tr = -0.035
    texto = Image.new("RGBA", (SW, int(al * len(linhas) + f.size)), (0, 0, 0, 0))
    larg_ult = 0
    for li, l in enumerate(linhas):
        x = 0.0
        for p in l.split():
            cor_p = ACENTO if p.strip(".,!?;:").lower() in marca else TITULO
            tx = _txt(p, f, cor_p, tr)
            texto.alpha_composite(tx, (int(x), int(li * al)))
            x += _larg(p + " ", f, tr)
        larg_ult = _larg(l, f, tr)
    y_sub = y0 + int(al * len(linhas)) + int(0.014 * H)
    eh = max(3, int(0.0062 * u))
    sub = d.brilho_neon(d.painel(max(eh * 2, int(larg_ult)), eh, raio=eh // 2, fundo=ACENTO), ACENTO, 0.01 * u, 0.7)
    r = {"estatico": estatico, "texto": texto, "y0": y0, "y_sub": y_sub, "sub": sub, "eh": eh}
    g.cache[chave] = r
    return r


def _desenhar_frase(c, e, cam, ta, dur):
    r = _prep_frase(c.g, e)
    cam.alpha_composite(r["estatico"])
    kt = d.saida(d.mapear(ta, -0.2, 0.3))
    _colar(cam, r["texto"], 0, r["y0"] + (1 - kt) * 0.015 * c.H, kt)
    k = SUAVE(d.mapear(ta, 0.15, 0.15 + d.limitar(dur * 0.2, 0.45, 0.8)))
    if k > 0.01:
        s = r["sub"]
        pad = (s.height - r["eh"]) // 2
        w = max(1, int(pad * 2 + (s.width - 2 * pad) * k))
        _colar(cam, s.crop((0, 0, w, s.height)), -pad, r["y_sub"] - pad)


# ------------------------------------------------------------------ palco: montagem por quadro


def _janelas(b, i):
    """Tempos do painel i do bloco: entrada do conteúdo, início da animação, saída."""
    ps = b["paineis"]
    p = ps[i]
    primeiro, ultimo = i == 0, i == len(ps) - 1
    t_in = b["s"] + 0.22 if primeiro else p["inicio"]
    t_anim = b["s"] + 0.5 if primeiro else p["inicio"] + 0.22
    if ultimo:
        # o palco fica até o 'fim' do plano e se apaga ali, logo ANTES do cartão subir (o cartão começa a voltar
        # em b["e"] - T_FECHA, que é o 'fim'; senão o cartão passaria por cima do texto ainda visível)
        t_out, d_out = max(t_anim + 0.5, b["e"] - T_FECHA - 0.22), 0.24
    else:
        # a saída termina ANTES de o próximo painel começar a entrar (sem dois cabeçalhos sobrepostos)
        t_out, d_out = max(t_anim + 0.5, ps[i + 1]["inicio"] - 0.28), 0.2
    return t_in, t_anim, t_out, d_out


def _estavel(e, ta, dur, t_anim):
    """Tempo (desde t_anim) a partir do qual o desenho do painel não muda mais."""
    tp = e["tipo"]
    if tp == "grafico":
        return d.limitar(dur * 0.42, 1.0, 1.85) + 0.4
    if tp == "numero":
        return max(d.limitar(dur * 0.38, 0.8, 1.5) + 0.4, 1.0)
    if tp == "comparacao":
        n = max(2, min(4, len(e.get("itens") or [])))
        return (n - 1) * d.limitar(dur * 0.06, 0.14, 0.26) + d.limitar(dur * 0.16, 0.5, 0.8) + 0.4
    if tp == "topicos":
        its = _itens_topicos(e)
        n = max(1, len(its))
        passo = d.limitar((dur - 0.6) / n, 0.25, 0.6)
        fim = 0.0
        for i, (_, em) in enumerate(its):
            t0 = max(0.0, (float(em) - t_anim) if em is not None else i * passo)
            fim = max(fim, t0 + 0.4)
        return fim
    if tp == "frase":
        return 0.15 + d.limitar(dur * 0.2, 0.45, 0.8) + 0.05
    return 1e9


DESENHO = {"grafico": _desenhar_grafico, "numero": _desenhar_numero, "comparacao": _desenhar_comparacao,
           "frase": _desenhar_frase}


def _paineis(c, img, b, k):
    t = c.t
    X0, Y0, SW, SH = _palco(c.g)
    for i, e in enumerate(b["paineis"]):
        t_in, t_anim, t_out, d_out = _janelas(b, i)
        if t < t_in - 0.01 or t > t_out + d_out:
            continue
        a_in = SUAVE(d.mapear(t, t_in, t_in + 0.36))
        a_out = 1 - d.suave(d.mapear(t, t_out, t_out + d_out))
        a = min(a_in, a_out)
        if a <= 0.004:
            continue
        ta = t - t_anim
        dur = t_out - t_anim
        # depois que todas as animações internas terminam, o palco é sempre igual: desenha uma vez e reaproveita
        fixo = ta >= _estavel(e, ta, dur, t_anim)
        chave = ("e19", "palco_fixo", id(e), round(dur, 3))
        cam = c.g.cache.get(chave) if fixo else None
        if cam is None:
            cam = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
            if e["tipo"] == "topicos":
                _desenhar_topicos(c, e, cam, ta, dur, t, t_anim)
            else:
                DESENHO[e["tipo"]](c, e, cam, ta, dur)
            if fixo:
                c.g.cache[chave] = cam
        dy = (1 - k) * 0.03 * c.H + (1 - a_in) * 0.018 * c.H - (1 - a_out) * (0.0 if i == len(b["paineis"]) - 1 else 0.014 * c.H)
        _colar(img, cam, X0, Y0 + dy, a)


# ------------------------------------------------------------------ legenda própria (pílula com contorno verde)


class _Legenda:
    def __init__(self, g, perfil):
        W, H = g.W, g.H
        u = _u(W, H)
        self.W, self.H, self.u = W, H, u
        self.f = d.fonte(int(round(u * float(perfil.get("tamanho", 0.05)))), int(perfil.get("peso", 750)))
        self.cor = perfil.get("cor", "#FFFFFF")
        self.dest = perfil.get("destaque", "#D4ED80")
        self.caixa = perfil.get("caixa") or "#101919EE"
        self.borda = perfil.get("borda", "#C9F366")
        self.maius = bool(perfil.get("maiusculas", False))
        self.grupos = agrupar(g.palavras, int(perfil.get("max_caracteres", 20) or 20), 1)
        self.inis = [gr["inicio"] - 0.05 for gr in self.grupos]
        asc, desc = self.f.getmetrics()
        self.asc, self.desc = asc, desc
        self.pad_x = self.f.size * 0.56
        self.pad_y = self.f.size * 0.30
        self.alt = int(asc + desc + 2 * self.pad_y)
        self.margem = int(0.028 * u)
        self.cache = {}

    def _textos(self, gi):
        ws = [w["texto"].strip() for w in self.grupos[gi]["palavras"]]
        return [w.upper() for w in ws] if self.maius else ws

    def _base(self, gi, ai):
        chave = (gi, ai)
        if chave in self.cache:
            return self.cache[chave]
        ws = self._textos(gi)
        f = self.f
        esp = f.getlength(" ")
        larg_txt = sum(f.getlength(w) for w in ws) + esp * (len(ws) - 1)
        escala = min(1.0, self.W * 0.8 / (larg_txt + 2 * self.pad_x))
        pw, ph = int(larg_txt + 2 * self.pad_x), self.alt
        m = self.margem
        if ("pilula", gi) not in self.cache:
            cam = Image.new("RGBA", (pw + 2 * m, ph + 2 * m), (0, 0, 0, 0))
            lb = max(2, int(round(0.0021 * self.u)))
            # brilho verde suave em volta (0 0 26px #caf16744)
            halo = d.painel(pw, ph, raio=int(ph * 0.3), fundo=d.cor(self.borda, 0.5))
            hl = Image.new("RGBA", cam.size, (0, 0, 0, 0))
            hl.alpha_composite(halo, (m, m))
            hl = hl.filter(ImageFilter.GaussianBlur(0.012 * self.u))
            hl.putalpha(hl.getchannel("A").point(lambda v: int(v * 0.55)))
            cam.alpha_composite(hl)
            cam.alpha_composite(d.painel(pw, ph, raio=int(ph * 0.3), fundo=self.caixa, borda=self.borda, larg_borda=lb),
                                (m, m))
            self.cache[("pilula", gi)] = cam
        cam = self.cache[("pilula", gi)].copy()
        dr = ImageDraw.Draw(cam)
        x = m + self.pad_x
        y = m + self.pad_y - f.size * 0.02
        xs = []
        for i, w in enumerate(ws):
            xs.append(x)
            if i != ai:
                dr.text((x, y), w, font=f, fill=d.cor(self.cor))
            x += f.getlength(w) + esp
        res = (cam, xs, y, escala)
        self.cache[chave] = res
        return res

    def _palavra(self, gi, ai):
        chave = ("w", gi, ai)
        if chave not in self.cache:
            w = self._textos(gi)[ai]
            asc, desc = self.f.getmetrics()
            cam = Image.new("RGBA", (int(self.f.getlength(w)) + 4, asc + desc + 2), (0, 0, 0, 0))
            ImageDraw.Draw(cam).text((0, 0), w, font=self.f, fill=d.cor(self.dest))
            self.cache[chave] = cam
        return self.cache[chave]

    def grupo_em(self, t):
        i = bisect.bisect_right(self.inis, t) - 1
        if i < 0 or t >= self.grupos[i]["fim"]:
            return None
        return i

    def desenhar(self, img, t, y_topo, opac=1.0):
        gi = self.grupo_em(t)
        if gi is None:
            return
        gr = self.grupos[gi]
        ai = -1
        for j, w in enumerate(gr["palavras"]):
            if w["inicio"] - 0.03 <= t < max(w["fim"], w["inicio"] + 0.12):
                ai = j
        cam, xs, y, escala = self._base(gi, ai)
        if ai >= 0:
            pal = self._palavra(gi, ai)
            sobe = d.saida(d.mapear(t, gr["palavras"][ai]["inicio"] - 0.03, gr["palavras"][ai]["inicio"] + 0.14))
            cam = cam.copy()
            cam.alpha_composite(pal, (int(xs[ai]), int(y + (1 - sobe) * 0.006 * self.u)))
        k = d.saida(d.mapear(t, self.inis[gi], self.inis[gi] + 0.2))
        esc = (0.93 + 0.07 * d.mola(k, 1.4)) * escala
        d.colar(img, cam, (self.W / 2, y_topo + self.alt / 2), escala=esc, opacidade=min(1.0, 0.2 + k) * opac)

    def y_cheia(self, c):
        """Lugar da legenda com a tela cheia: abaixo do queixo; se não couber, acima da cabeça; senão, embaixo."""
        H = self.H
        base_seg = 0.80 * H
        queixo = c.g.rosto.queixo(c.t)
        cabeca = c.g.rosto.topo_cabeca(c.t)
        hb = self.alt
        if queixo + 0.02 * H + hb <= base_seg:
            return min(max(queixo + 0.03 * H, 0.62 * H), base_seg - hb)
        if cabeca - 0.02 * H - hb >= 0.11 * H:
            return cabeca - 0.025 * H - hb
        return base_seg - hb

    def y_split(self):
        return Y_DIV * self.H - self.alt * 0.55


# ------------------------------------------------------------------ quadro


def quadro(c):
    est = _estado(c.g)
    b = _bloco_em(est, c.t)
    k = _k_split(b, c.t) if b else 0.0
    leg = est["leg"]
    if k <= 0.0008:
        img = c.fonte.copy()
        if leg:
            leg.desenhar(img, c.t, leg.y_cheia(c))
        return img
    geo = _geometria(c.g, b, k)
    img = _fundo(c, k, geo)
    _paineis(c, img, b, k)
    _cartao(c, img, geo, k)
    op_linha = d.mapear(k, 0.65, 1.0) * 0.7
    if op_linha > 0.01:
        ln = _linha_divisao(c.g)
        _colar(img, ln, 0, geo["iy"] - ln.height // 2, op_linha)
    if leg:
        # a legenda nunca atravessa o rosto: com a tela cheia ela fica abaixo do queixo; quando o cartão desce,
        # ela some ali e reaparece presa à borda de cima do cartão (acompanha o movimento, como na prévia)
        a_cheia = 1 - d.suave(d.mapear(k, 0.0, 0.3))
        if a_cheia > 0.01:
            leg.desenhar(img, c.t, leg.y_cheia(c), a_cheia)
        y_borda = geo["iy"] - leg.alt * 0.55
        a_borda = d.suave(d.mapear(k, 0.42, 0.72)) * d.limitar((y_borda - 0.105 * c.H) / (0.02 * c.H))
        if a_borda > 0.01:
            leg.desenhar(img, c.t, y_borda, a_borda)
    return img


# ------------------------------------------------------------------ validação


def validar(plano, duracao):
    p = []
    ps = sorted([e for e in plano["eventos"] if e.get("tipo") in TIPOS_PAINEL], key=lambda e: e["inicio"])
    for a, b in zip(ps, ps[1:]):
        if b["inicio"] < a["fim"] - 0.01:
            p.append(f"Painéis sobrepostos em {b['inicio']:.2f}s: um painel precisa terminar antes do outro começar.")
        elif JUNTAR <= b["inicio"] - a["fim"] < 3.0:
            p.append(f"Painéis em {a['inicio']:.2f}s e {b['inicio']:.2f}s: a tela fecha e reabre em menos de 3 s. "
                     f"Encoste (menos de {JUNTAR:.1f} s entre eles) ou afaste (3 s ou mais).")
    for e in ps:
        t, ini, dur = e["tipo"], e["inicio"], e["fim"] - e["inicio"]
        if dur < 2.2:
            p.append(f"Painel '{t}' em {ini:.2f}s curto demais ({dur:.1f}s): use pelo menos 2,5 s.")
        if dur > 10:
            p.append(f"Painel '{t}' em {ini:.2f}s longo demais ({dur:.1f}s): máximo 8-10 s.")
        tit = str(e.get("titulo") or "")
        lim = 48 if t == "frase" else 28
        if t != "numero" and not tit.strip():
            p.append(f"Painel '{t}' em {ini:.2f}s sem 'titulo'.")
        if len(tit) > lim:
            p.append(f"Título longo demais em {ini:.2f}s ({len(tit)} letras; máx. {lim}).")
        if len(str(e.get("rotulo") or "")) > 24:
            p.append(f"Rótulo longo demais em {ini:.2f}s (máx. 24 letras).")
        if t == "numero":
            v = str(e.get("valor") or "")
            if not v.strip():
                p.append(f"Painel 'numero' em {ini:.2f}s sem 'valor'.")
            if len(v) > 14:
                p.append(f"Valor longo demais em {ini:.2f}s (máx. 14 letras).")
        if t in ("comparacao", "topicos"):
            its = e.get("itens") or []
            if not 2 <= len(its) <= 4:
                p.append(f"Painel '{t}' em {ini:.2f}s precisa de 2 a 4 itens (tem {len(its)}).")
            if t == "topicos":
                for txt, em in _itens_topicos(e):
                    if len(txt) > 24:
                        p.append(f"Tópico longo demais em {ini:.2f}s: '{txt[:30]}…' (máx. 24 letras).")
                    if em is not None and not (ini <= float(em) < e["fim"]):
                        p.append(f"Tópico '{txt}' com 'em' fora do painel ({ini:.2f}-{e['fim']:.2f}s).")
                    elif em is not None and float(em) > e["fim"] - 0.8:
                        p.append(f"Tópico '{txt}' entra só {e['fim'] - float(em):.1f}s antes do fim do painel e "
                                 f"quase não aparece. Aumente 'fim' para pelo menos {float(em) + 0.8:.2f}.")
            else:
                for it in its:
                    if isinstance(it, dict) and len(str(it.get("rotulo", ""))) > 12:
                        p.append(f"Rótulo de item longo demais em {ini:.2f}s (máx. 12 letras).")
        if t == "grafico":
            vs = e.get("valores")
            if vs is not None and (not isinstance(vs, (list, tuple)) or not 3 <= len(vs) <= 8):
                p.append(f"Gráfico em {ini:.2f}s: 'valores' precisa ter 3 a 8 números.")
            if len(str(e.get("marca") or "")) > 12:
                p.append(f"Selo do gráfico longo demais em {ini:.2f}s (máx. 12 letras).")
    if ps and duracao > 0 and max(e["fim"] for e in ps) > duracao - 0.65:
        p.append(f"O último painel termina em {max(e['fim'] for e in ps):.2f}s e o vídeo acaba em {duracao:.2f}s: "
                 "a volta para a tela cheia leva 0,6 s depois do 'fim'. Termine o painel pelo menos 0,7 s antes "
                 "do fim do vídeo.")
    if duracao > 8 and ps:
        dividido = sum(e["fim"] - e["inicio"] for e in ps)
        if dividido > duracao * 0.52:
            p.append(f"A tela fica dividida {dividido:.0f}s de {duracao:.0f}s: a divisão é para os momentos de dado "
                     "(máx. ~50% do vídeo). Deixe a pessoa em tela cheia no resto.")
    return p
