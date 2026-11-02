"""15 · Vertigem — efeito "dolly zoom": o FUNDO cresce (ou recua), balança de lado e gira de leve enquanto
a PESSOA fica parada, do mesmo tamanho, no mesmo lugar. Título estável em placa clara e legenda fixa (leitura
estável), como na prévia aprovada (Scene15: fundo com scale 0,88 + wave*0,67, translate + rotateY(swing*5°),
figura parada).

Como funciona (com recorte):
1. O fundo vai para uma imagem de trabalho pequena (~300 px de largura, redução inteira: rápida). O lugar
   da pessoa nele é tapado com as cores do fundo em volta (pirâmide "push-pull", suave). Quando o fundo
   cresce, essa área aparece em volta da pessoa como um halo macio da cor da parede — invisível em fundo
   limpo, discreto em fundo bagunçado.
2. O fundo tapado é ampliado (ou recuado), deslizado de lado e girado levemente em perspectiva numa única
   transformação (homografia de 4 cantos; nunca mostra borda vazia ao aproximar; ao recuar, as bordas
   recebem o próprio ambiente desfocado). Ganha profundidade de campo e vinheta proporcionais ao efeito.
3. A pessoa original (resolução cheia) é recolocada por cima, parada. O corpo é "fechado" abaixo do queixo
   (buracos do recorte em mãos/objetos) e a parte de baixo do quadro, do queixo para baixo, fica igual ao
   original: tronco, mãos e objeto na mão nunca duplicam nem deixam mancha quando o fundo cresce.
Sem recorte: versão suave — o fundo cresce em volta de uma silhueta macia estimada pelo rosto (quase nítido
perto da pessoa, bem desfocado nas bordas).
"""
from __future__ import annotations

import math
import re

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import desenho as d

INFO = {
    "id": "15-vertigem",
    "nome": "Vertigem",
    "precisa_recorte": True,
    "antes": 0.05,
    "depois": 0.30,
    # ficha 15-vertigem: Inter 700, creme, destaque verde-claro discreto, caixa escura, leitura estável
    "legenda": {"peso": 700, "tamanho": 0.062, "cor": "#F8F7F0", "destaque": "#D4ED80", "caixa": "#222729F2",
                "max_caracteres": 22, "max_linhas": 1, "animacao": "nenhuma"},
    "eventos": {
        "vertigem": "inicio, fim: o fundo cresce (ou recua) enquanto a pessoa fica parada. "
                    "forma ('ida-e-volta' padrão: vai e volta, 1,5-5 s | 'segurar': vai, segura e volta no fim, "
                    "2-7 s | 'pulso': soco rápido de fundo, 0,6-1,6 s), intensidade (1 leve | 2 médio, padrão | "
                    "3 forte), direcao ('aproximar' padrão: o fundo vem para a frente | 'afastar': o fundo recua), "
                    "pico (segundo exato do auge, só em 'ida-e-volta'; padrão = meio), lado ('auto' | 'esquerda' | "
                    "'direita': para onde o ambiente balança), suave (true = fundo bem desfocado, para fundo "
                    "bagunçado), recorte (false = ignora o recorte e usa a versão suave; use se o recorte "
                    "cortar o corpo ou deixar mãos/objetos de fora), centro ('rosto' padrão | [x, y] frações 0-1), "
                    "som, som_atraso, som_volume",
        "titulo": "inicio, fim (2-6 s), texto (2-5 palavras, sem ponto final): título estável em placa clara, "
                  "fica parado enquanto o fundo se mexe. posicao ('auto' padrão | 'topo' | 'baixo'), som",
    },
}

# ------------------------------------------------------------------ paleta (prévia aprovada / ficha)
PLACA = "#F8F7F0"       # placa do título (creme da ficha)
TINTA = "#222729"       # texto do título (tinta escura da prévia)
LIMA = "#D4ED80"        # traço de destaque (linha verde-limão da prévia)

APROXIMAR = {1: 1.16, 2: 1.28, 3: 1.42}   # escala do fundo no auge
AFASTAR = {1: 0.93, 2: 0.88, 3: 0.84}
FECHADO = 1.3           # plano fechado (rosto > ~38% da largura): o empurrão do fundo cresce 30%
FORMAS = ("ida-e-volta", "segurar", "pulso")
LARG_PEQ = 144          # largura da imagem pequena que tapa o buraco da pessoa
CENTRO_Y = 0.42         # centro do zoom: rosto, um pouco acima do meio (fração da altura do rosto)


# ================================================================== leitura tolerante dos campos

def _nivel(e):
    """intensidade 1/2/3 (aceita 2, "2", 2.0); None se inválida."""
    try:
        n = float(e.get("intensidade", 2))
    except (TypeError, ValueError):
        return None
    return int(n) if n in (1.0, 2.0, 3.0) else None


def _num(v, padrao=None):
    """Número tolerante (1.4, "1.4", "1,4"); padrao se vazio ou inválido."""
    if isinstance(v, bool) or v is None:
        return padrao
    try:
        return float(str(v).replace(",", ".")) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return padrao


def _sim(v, padrao):
    """Booleano tolerante: true/false, "true"/"false", "sim"/"não", 1/0."""
    if v is None:
        return padrao
    if isinstance(v, str):
        return v.strip().lower() in ("true", "sim", "1", "yes", "verdadeiro")
    return bool(v)


# ================================================================== validação do plano

def validar(plano, duracao):
    p = []
    validos = [e for e in plano["eventos"] if _num(e.get("inicio")) is not None and _num(e.get("fim")) is not None]
    vs = sorted((e for e in validos if e.get("tipo") == "vertigem"), key=lambda e: e["inicio"])
    for a, b in zip(vs, vs[1:]):
        if b["inicio"] < a["fim"] - 0.01:
            p.append(f"Vertigens sobrepostas em {b['inicio']:.2f}s: uma precisa terminar antes da outra começar.")
        elif b["inicio"] - a["fim"] < 0.8:
            p.append(f"Vertigens coladas em {b['inicio']:.2f}s: deixe pelo menos 0,8 s de fundo parado entre elas.")
    total = 0.0
    for e in vs:
        dur = e["fim"] - e["inicio"]
        total += dur
        forma = e.get("forma", "ida-e-volta")
        if forma not in FORMAS:
            p.append(f"Vertigem em {e['inicio']:.2f}s: forma '{forma}' não existe (use ida-e-volta, segurar ou pulso).")
            continue
        lim = {"ida-e-volta": (1.2, 6.0), "segurar": (1.6, 8.0), "pulso": (0.5, 1.8)}[forma]
        if not lim[0] <= dur <= lim[1]:
            p.append(f"Vertigem '{forma}' em {e['inicio']:.2f}s dura {dur:.1f}s; o certo é {lim[0]}-{lim[1]} s.")
        if _nivel(e) is None:
            p.append(f"Vertigem em {e['inicio']:.2f}s: intensidade precisa ser 1, 2 ou 3.")
        if e.get("direcao", "aproximar") not in ("aproximar", "afastar"):
            p.append(f"Vertigem em {e['inicio']:.2f}s: direcao precisa ser 'aproximar' ou 'afastar'.")
        if e.get("lado", "auto") not in ("auto", "esquerda", "direita"):
            p.append(f"Vertigem em {e['inicio']:.2f}s: lado precisa ser 'auto', 'esquerda' ou 'direita'.")
        pico = e.get("pico")
        if pico is not None:
            pv = _num(pico)
            if pv is None:
                p.append(f"Vertigem em {e['inicio']:.2f}s: 'pico' precisa ser um número (segundos).")
            elif not (e["inicio"] + 0.25 <= pv <= e["fim"] - 0.25):
                p.append(f"Vertigem em {e['inicio']:.2f}s: 'pico' precisa cair dentro do evento (com 0,25 s de folga).")
        centro = e.get("centro", "rosto")
        if centro != "rosto" and not (isinstance(centro, (list, tuple)) and len(centro) == 2
                                      and all(_num(v) is not None and 0 <= _num(v) <= 1 for v in centro)):
            p.append(f"Vertigem em {e['inicio']:.2f}s: 'centro' precisa ser \"rosto\" ou [x, y] com frações de 0 a 1.")
    if duracao > 6 and total > duracao * 0.6:
        p.append("Vertigem demais: o fundo se mexe em mais de 60% do vídeo (cansa e enjoa). Use só nos momentos fortes.")
    ts = sorted((e for e in validos if e.get("tipo") == "titulo"), key=lambda e: e["inicio"])
    for a, b in zip(ts, ts[1:]):
        if b["inicio"] < a["fim"] + 0.2:
            p.append(f"Títulos sobrepostos em {b['inicio']:.2f}s: um título por vez (0,2 s entre eles).")
    for e in ts:
        txt = str(e.get("texto", "")).strip()
        if not txt:
            p.append(f"Título vazio em {e['inicio']:.2f}s.")
        elif len(txt.split()) > 6 or len(txt) > 42:
            p.append(f"Título longo demais em {e['inicio']:.2f}s (máx. 5 palavras / ~40 letras).")
        # só padrões de identificador (a palavra "vertigem" pode ser assunto real da fala: não bloqueia)
        if re.search(r"\b\d{1,2}-[a-z]|_|[{}<>\[\]]|\btipo\s*:|\bestilo\s*\d", txt.lower()):
            p.append(f"Título em {e['inicio']:.2f}s parece texto interno ('{txt}'): escreva só palavras da fala.")
        if e["fim"] - e["inicio"] < 1.2:
            p.append(f"Título em {e['inicio']:.2f}s some rápido demais (mín. 1,2 s para dar tempo de ler).")
    return p


# ================================================================== curvas do efeito

def _curva(e, t):
    """(k, balanco): k = quanto do efeito está aplicado (0-1); balanco = lado do ambiente (-1..1)."""
    ini, fim = e["inicio"], e["fim"]
    dur = max(0.05, fim - ini)
    forma = e.get("forma", "ida-e-volta")
    if forma == "segurar":
        sobe = min(1.0, dur * 0.35)
        desce = min(0.8, dur * 0.3)
        k = d.suave(d.mapear(t, ini, ini + sobe)) * (1 - d.suave(d.mapear(t, fim - desce, fim)))
        k *= 1 + 0.07 * d.mapear(t, ini + sobe, fim - desce)       # deriva lenta enquanto segura (vivo)
        bal = math.sin(math.pi * d.mapear(t, ini, fim)) * 0.6
    elif forma == "pulso":
        sobe = min(0.32, dur * 0.4)
        k = d.saida(d.mapear(t, ini, ini + sobe)) * (1 - d.suave(d.mapear(t, ini + sobe + 0.06, fim)))
        bal = 0.0
    else:  # ida-e-volta (prévia: wave = (1 - cos)/2, swing = sin)
        pico = _num(e.get("pico"), ini + dur / 2)
        pico = min(max(pico, ini + 0.2), fim - 0.2)
        if t <= pico:
            u = d.mapear(t, ini, pico)
            k = 0.5 - 0.5 * math.cos(math.pi * u)
            bal = math.sin(math.pi * u)
        else:
            u = d.mapear(t, pico, fim)
            k = 0.5 + 0.5 * math.cos(math.pi * u)
            bal = -math.sin(math.pi * u)
        bal *= 0.8
    return max(0.0, k), bal


def _lado(c, e):
    lado = e.get("lado", "auto")
    if lado == "esquerda":
        return -1.0
    if lado == "direita":
        return 1.0
    vs = [x for x in c.g.plano["eventos"] if x.get("tipo") == "vertigem"]
    i = next((n for n, x in enumerate(vs) if x["inicio"] == e["inicio"] and x["fim"] == e["fim"]), 0)
    return 1.0 if i % 2 == 0 else -1.0     # alterna o lado a cada vertigem (variedade sem sorteio)


def _estado(c):
    """Parâmetros do efeito no instante t (ou None se o fundo está parado)."""
    for e in c.eventos:
        if e.get("tipo") != "vertigem" or not (e["inicio"] <= c.t <= e["fim"]):
            continue
        k, bal = _curva(e, c.t)
        if k < 0.004:
            return None
        niv = _nivel(e) or 2
        afastar = e.get("direcao", "aproximar") == "afastar"
        fechado = _quao_fechado(c, e)
        if afastar:
            esc = 1 + (AFASTAR[niv] - 1) * k
        else:
            # plano fechado: sobra pouco fundo à vista, o empurrão precisa ser maior para aparecer
            alvo = 1 + (APROXIMAR[niv] - 1) * (1 + (FECHADO - 1) * fechado)
            esc = 1 + (alvo - 1) * k
        com_recorte = c.mascara is not None and _sim(e.get("recorte"), True)
        if not com_recorte:   # versão suave (sem recorte): movimento um pouco mais contido; em plano fechado
            esc = 1 + (esc - 1) * (0.75 + 0.2 * fechado)   # quase inteiro, senão o efeito some
        return {"e": e, "k": k, "bal": bal * _lado(c, e), "esc": esc, "afastar": afastar,
                "suave": _sim(e.get("suave"), False), "fechado": fechado, "recorte": com_recorte}
    return None


def _quao_fechado(c, e):
    """0 = plano médio/aberto · 1 = plano fechado. Medido UMA vez por evento (mediana da largura do rosto
    no trecho) e com transição macia entre 32% e 42% da largura: o efeito nunca muda de força no meio."""
    ch = ("vt_fechado", e["inicio"], e["fim"])
    if ch not in c.g.cache:
        larg = []
        for t in np.linspace(e["inicio"], e["fim"], 7):
            x0, _, x1, _ = c.g.rosto.em(float(t))
            larg.append((x1 - x0) / c.W)
        c.g.cache[ch] = d.suave(d.mapear(float(np.median(larg)), 0.32, 0.42))
    return c.g.cache[ch]


def _centro(c, e):
    al = e.get("centro", "rosto")
    if isinstance(al, (list, tuple)) and len(al) == 2 and _num(al[0]) is not None and _num(al[1]) is not None:
        return d.limitar(_num(al[0])) * c.W, d.limitar(_num(al[1])) * c.H
    x0, y0, x1, y1 = c.rosto
    return (x0 + x1) / 2, y0 + (y1 - y0) * CENTRO_Y


# ================================================================== tapar o lugar da pessoa no fundo

def _preencher(rgb, buraco):
    """Push-pull (pirâmide de convolução normalizada): o buraco recebe as cores do fundo em volta, suaves.
    rgb: HxWx3 uint8 · buraco: HxW bool. Só numpy + PIL (sem OpenCV)."""
    val = (~buraco).astype(np.float32)
    if val.sum() < 10:
        return rgb
    P = rgb.astype(np.float32) * val[..., None]
    Wt = val
    niveis = []
    while min(Wt.shape) >= 8:
        niveis.append((P, Wt))
        h, w = Wt.shape
        h2, w2 = h // 2, w // 2
        sP = P[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2, 3).sum((1, 3))
        sW = Wt[:h2 * 2, :w2 * 2].reshape(h2, 2, w2, 2).sum((1, 3))
        Wt = np.minimum(sW, 1.0)
        P = sP / np.maximum(sW, 1e-6)[..., None] * Wt[..., None]
    cor_ = np.where(Wt[..., None] > 1e-4, P / np.maximum(Wt, 1e-6)[..., None],
                    rgb[~buraco].reshape(-1, 3).mean(axis=0)[None, None, :])
    for P_l, W_l in reversed(niveis):
        h, w = W_l.shape
        up = np.asarray(Image.fromarray(np.clip(cor_, 0, 255).astype(np.uint8), "RGB").resize((w, h), Image.BILINEAR),
                        np.float32)
        cor_ = P_l + up * (1 - W_l)[..., None]
    return np.clip(cor_, 0, 255).astype(np.uint8)


def _tapar(peq, mascara_peq):
    """Fundo de trabalho (RGB pequeno) com o lugar da pessoa tapado pelas cores do fundo em volta.
    O preenchimento é calculado numa miniatura (largura LARG_PEQ) e só ele é ampliado."""
    ow, oh = peq.size
    pw = min(ow, LARG_PEQ)
    ph = max(2, int(round(oh * pw / ow)))
    mini = peq.resize((pw, ph), Image.BILINEAR)
    m = mascara_peq.resize((pw, ph), Image.BILINEAR).filter(ImageFilter.MaxFilter(5))  # engorda: tira a franja
    buraco = np.asarray(m) > 40
    if not buraco.any():
        return peq
    tapa = Image.fromarray(_preencher(np.asarray(mini), buraco), "RGB")
    alfa = Image.fromarray((buraco * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.8))
    return Image.composite(tapa.resize((ow, oh), Image.BILINEAR), peq, alfa.resize((ow, oh), Image.BILINEAR))


# ================================================================== silhueta suave (modo sem recorte)

def _silhueta_estimada(c):
    """Máscara L macia de cabeça + ombros a partir do rosto (para quando não há recorte).
    Guardada por posição do rosto arredondada a 0,5% do quadro: mesma posição = mesma máscara (determinístico)."""
    W, H = c.W, c.H
    q = 200.0
    b = c.rosto
    chave = (round(b[0] / W * q), round(b[1] / H * q), round(b[2] / W * q), round(b[3] / H * q))
    guarda = c.g.cache.setdefault("vt_silhuetas", {})
    if chave not in guarda:
        if len(guarda) >= 24:
            guarda.pop(next(iter(guarda)))
        rosto = (chave[0] * W / q, chave[1] * H / q, chave[2] * W / q, chave[3] * H / q)
        guarda[chave] = _desenhar_silhueta(W, H, rosto)
    return guarda[chave]


def _desenhar_silhueta(W, H, rosto):
    x0, y0, x1, y1 = rosto
    sw, sh = max(2, W // 6), max(2, H // 6)
    k = sw / W
    fw, fh = (x1 - x0) * k, (y1 - y0) * k
    cx, cy = (x0 + x1) / 2 * k, (y0 + y1) / 2 * k
    m = Image.new("L", (sw, sh), 0)
    dr = ImageDraw.Draw(m)

    def forma(fn, x0_, y0_, x1_, y1_):
        y1_ = min(y1_, sh + fh * 3)   # pode passar da borda (o PIL recorta); só não pode inverter
        if x1_ > x0_ and y1_ > y0_:
            fn([x0_, y0_, x1_, y1_], fill=255)

    forma(dr.ellipse, cx - fw * 0.80, cy - fh * 1.02, cx + fw * 0.80, cy + fh * 0.72)     # cabeça + cabelo
    topo_corpo = cy + fh * 0.75
    forma(dr.ellipse, cx - fw * 1.8, topo_corpo, cx + fw * 1.8, topo_corpo + fh * 2.6)     # ombros
    forma(dr.rectangle, cx - fw * 1.65, topo_corpo + fh * 1.1, cx + fw * 1.65, max(sh, topo_corpo + fh * 1.2))  # tronco
    forma(dr.rectangle, cx - fw * 0.40, cy, cx + fw * 0.40, topo_corpo + fh * 0.4)          # pescoço
    # parte de baixo do quadro inteira (mãos e braços de quem fala ficam ali): não balança nem duplica
    forma(dr.rectangle, 0, topo_corpo + fh * 1.5, sw, max(sh, topo_corpo + fh * 1.6))
    m = m.filter(ImageFilter.GaussianBlur(max(1.0, fw * 0.24)))
    return m.resize((W, H), Image.BILINEAR)


# ================================================================== movimento do fundo

def _vinheta(g, w, h):
    ch = ("vt_vinheta", w, h)
    if ch not in g.cache:
        y, x = np.ogrid[0:h, 0:w]
        dd = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h * 0.45) / (h / 2)) ** 2)
        a = np.clip((dd - 0.35) / 0.95, 0, 1) ** 1.5 * 255
        g.cache[ch] = Image.fromarray(a.astype(np.uint8), "L")
    return g.cache[ch]


def _esfumado(g, w, h):
    """Máscara L com bordas macias (para o fundo recuado se fundir na extensão desfocada)."""
    ch = ("vt_esfumado", w, h)
    if ch not in g.cache:
        m = Image.new("L", (w, h), 0)
        b = max(2, int(w * 0.05))
        ImageDraw.Draw(m).rectangle([b, b, w - 1 - b, h - 1 - b], fill=255)
        g.cache[ch] = m.filter(ImageFilter.GaussianBlur(b * 0.6))
    return g.cache[ch]


# borda da máscara mais firme: o véu quase transparente em volta da pessoa carrega a cor do fundo ORIGINAL,
# que fica "desenhada" em volta dela quando o fundo se mexe. Corta o véu fraco e mantém o meio-tom do cabelo.
_BORDA = [0 if v < 36 else min(255, int((v - 36) * 255 / 199)) for v in range(256)]
_IGUAL = list(range(256))


def _coef(origem, destino):
    """Coeficientes do Image.transform(PERSPECTIVE): ponto da saída (destino) -> ponto da origem."""
    A, b = [], []
    for (x, y), (u, v) in zip(destino, origem):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.append(v)
    return [float(v) for v in np.linalg.solve(np.array(A, np.float64), np.array(b, np.float64))]


def _aplicar(coef, x, y):
    a, b, c_, d_, e, f, g, h = coef
    den = g * x + h * y + 1.0
    return (a * x + b * y + c_) / den, (d_ * x + e * y + f) / den


def _ida(px, py, cx, cy, esc, tx, ty, ang, dist):
    """Onde um ponto do fundo original vai parar na tela: escala em volta do rosto, desliza de lado e
    gira levemente no eixo vertical, com perspectiva (prévia Scene15: scale + translate + rotateY)."""
    ox, oy = cx + tx, cy + ty
    dx, dy = esc * (px - cx), esc * (py - cy)
    f = dist / (dist + dx * math.sin(ang))
    return ox + dx * math.cos(ang) * f, oy + dy * f


def _mapa(W, H, cx, cy, esc, tx, ty, ang, cobrir):
    """Os 4 pontos do fundo original que vão para os 4 cantos da tela (pixels do quadro cheio).
    cobrir=True: ajusta (aproxima um pouco mais / desliza de volta) para nunca mostrar borda vazia."""
    dist = W * 1.25                                 # "perspective(1300px)" da prévia, em fração da largura
    orig = [(0.0, 0.0), (float(W), 0.0), (float(W), float(H)), (0.0, float(H))]
    dest = [_ida(x, y, cx, cy, esc, tx, ty, ang, dist) for x, y in orig]
    coef = _coef(orig, dest)
    cantos = [_aplicar(coef, x, y) for x, y in orig]    # canto da tela -> ponto do fundo original
    if not cobrir:
        return cantos
    us, vs = [p[0] for p in cantos], [p[1] for p in cantos]
    mu, mv = (min(us) + max(us)) / 2, (min(vs) + max(vs)) / 2
    s = min(1.0, W / max(1e-6, max(us) - min(us)), H / max(1e-6, max(vs) - min(vs)))
    cantos = [(mu + (u - mu) * s, mv + (v - mv) * s) for u, v in cantos]
    us, vs = [p[0] for p in cantos], [p[1] for p in cantos]
    du = max(0.0, -min(us)) - max(0.0, max(us) - W)
    dv = max(0.0, -min(vs)) - max(0.0, max(vs) - H)
    return [(u + du, v + dv) for u, v in cantos]


def _reducao(W):
    """Fator inteiro de redução da imagem de trabalho do fundo (~300 px de largura; o fundo é desfocado)."""
    return max(1, int(round(W / 300.0)))


def _casco(m, y0):
    """Máscara (uint8 HxW) com o corpo "fechado" abaixo da linha y0 (queixo): em cada linha, tudo entre o
    pixel de pessoa mais à esquerda e o mais à direita vira pessoa. Tapa os buracos que o recorte deixa em
    mãos, braços e objetos na mão (celular, produto) — senão eles ficam no fundo e crescem junto (duplicam).
    Devolve só o preenchimento (uint8, 255 dentro do corpo fechado, 0 acima de y0)."""
    y0 = int(max(0, min(m.shape[0], y0)))
    out = np.zeros_like(m)
    sub = m[y0:] > 128
    if sub.any():
        esq = np.maximum.accumulate(sub, axis=1)
        dir_ = np.maximum.accumulate(sub[:, ::-1], axis=1)[:, ::-1]
        out[y0:] = (esq & dir_).astype(np.uint8) * 255
    return out


def _protecao(c, ow, oh):
    """Máscara (float 0-1, tamanho de trabalho) da parte de BAIXO do quadro que fica igual ao original:
    do queixo para baixo (degradê curto até a linha dos ombros), numa faixa larga em volta do corpo.
    Em vídeo vertical de pessoa falando a vertigem aparece de verdade em volta da cabeça; embaixo só há
    tronco, mãos e objetos (celular, produto), que o recorte erra e que duplicariam ao mexer o fundo."""
    W, H = c.W, c.H
    x0, y0, x1, y1 = c.rosto
    fw = max(1.0, x1 - x0)
    sx, sy = ow / W, oh / H
    # começa logo abaixo da boca (a caixa do rosto termina no queixo): objeto erguido na altura do queixo
    # (celular mostrado para a câmera) também fica protegido
    ch = ("vt_prot", ow, oh, round((y1 - (y1 - y0) * 0.15) * sy), round((x0 + x1) / 2 * sx), round(fw * sx))
    if ch in c.g.cache:
        return c.g.cache[ch]
    a = ch[3]
    b = a + H * 0.06 * sy
    ys = np.clip((np.arange(oh, dtype=np.float32) - a) / max(1.0, b - a), 0, 1)
    vert = ys * ys * (3 - 2 * ys)
    # faixa horizontal em volta do corpo (ombros ~1,8 rosto para cada lado + folga para mãos/objetos);
    # em plano fechado ela já cobre a largura toda
    xs = np.abs(np.arange(ow, dtype=np.float32) - ch[4]) / max(1, ch[5])
    hz = np.clip((2.5 - xs) / 0.5, 0, 1)
    hz = hz * hz * (3 - 2 * hz)
    res = (hz[None, :] * vert[:, None] * 255).astype(np.uint8)
    guarda = c.g.cache.setdefault("vt_prot_n", [])
    guarda.append(ch)
    if len(guarda) > 64:
        c.g.cache.pop(guarda.pop(0), None)
    c.g.cache[ch] = res
    return res


def _vertigem(c, st):
    W, H = c.W, c.H
    e, k = st["e"], st["k"]
    cx, cy = _centro(c, e)
    tem_recorte = st["recorte"]          # False sem máscara ou com "recorte": false (recorte ruim)
    suave = st["suave"] or not tem_recorte
    # o fundo trabalha numa imagem pequena (~300 px de largura): ele vai ser desfocado de qualquer jeito
    # (profundidade de campo); a pessoa volta por cima em resolução cheia. Converte para RGB ANTES de
    # reduzir (o PIL reduz RGBA bem mais devagar: pré-multiplica o alfa)
    fr = _reducao(W)
    peq = c.fonte.convert("RGB")
    peq = peq.reduce(fr) if fr > 1 else peq
    ow, oh = peq.size
    sx, sy = ow / W, oh / H
    # sem recorte, a silhueta estimada faz o papel da máscara (tapa a pessoa do fundo: nada de "fantasma")
    bruta = c.mascara if tem_recorte else _silhueta_estimada(c)
    m_peq = bruta.reduce(fr) if fr > 1 else bruta
    extra = None      # com recorte: corpo fechado + parte de baixo protegida (tamanho de trabalho, L)
    if tem_recorte:
        if m_peq.size != (ow, oh):
            m_peq = m_peq.resize((ow, oh), Image.BILINEAR)
        m_np = np.asarray(m_peq)
        casco = _casco(m_np, c.g.rosto.queixo(c.t) * sy)
        ex = np.maximum(casco, _protecao(c, ow, oh))
        extra = Image.fromarray(ex, "L")
        m_peq = Image.fromarray(np.maximum(m_np, ex), "L")
    base = _tapar(peq, m_peq)
    # movimento do ambiente: escala + balanço lateral + leve subida + giro em perspectiva (prévia Scene15)
    bal = st["bal"]
    tx = bal * W * 0.032
    ty = -k * H * 0.02 * (1 if not st["afastar"] else -1)
    ang = math.radians(5.0) * bal * d.suave(min(1.0, k / 0.3))
    cantos = _mapa(W, H, cx, cy, st["esc"], tx, ty, ang, cobrir=not st["afastar"])
    if abs(ang) < 2e-3 and not st["afastar"]:
        # sem giro: o mapa é um retângulo alinhado; um redimensionamento com recorte é mais rápido
        (u0, v0), (u2, v2) = cantos[0], cantos[2]
        fundo = base.resize((ow, oh), Image.BILINEAR, box=(u0 * sx, v0 * sy, u2 * sx, v2 * sy))
    else:
        tela = [(0.0, 0.0), (float(ow), 0.0), (float(ow), float(oh)), (0.0, float(oh))]
        coef = _coef([(u * sx, v * sy) for u, v in cantos], tela)
        fundo = base.transform((ow, oh), Image.PERSPECTIVE, coef, Image.BILINEAR)
    if st["afastar"]:
        # o ambiente recua e precisa de mais fundo do que o vídeo tem. As bordas que faltam recebem o
        # próprio ambiente bem desfocado e escurecido (extensão macia, sem espelho nem emenda); o fundo
        # recuado fica por cima com as bordas esfumadas.
        mg = 0.08
        ext = base.resize((ow, oh), Image.BILINEAR, box=(ow * mg, oh * mg, ow * (1 - mg), oh * (1 - mg)))
        ext = ext.filter(ImageFilter.BoxBlur(max(2.0, ow * 0.035))).point(lambda v: int(v * 0.72))
        valido = _esfumado(c.g, ow, oh).transform((ow, oh), Image.PERSPECTIVE, coef, Image.BILINEAR)
        fundo = Image.composite(fundo, ext, valido)
    # profundidade: o desfoque e a vinheta crescem com o efeito
    raio = W * (0.009 if suave else 0.0045) * k
    if st["afastar"]:
        raio = max(raio, W * 0.006 * k)
    if not suave:   # plano fechado: o pouco fundo visível precisa "ler" a profundidade
        raio *= 1 + 0.5 * st["fechado"]
    r_ = raio * sx - 0.35
    nitido = fundo
    if r_ > 0.2:
        fundo = fundo.filter(ImageFilter.BoxBlur(r_ * 0.9))
    if suave:
        # versão suave: perto da pessoa o ambiente fica mais nítido (dá para VER ele crescer); nas bordas,
        # bem desfocado (esconde bagunça e emendas)
        r2 = W * 0.017 * k * sx - 0.35
        if r2 > 0.2:
            fundo = Image.composite(nitido.filter(ImageFilter.BoxBlur(r2 * 0.9)), fundo, _vinheta(c.g, ow, oh))
    forca = (0.36 if suave else 0.28) * k + (0.16 * k if st["afastar"] else 0.0)
    forca *= 1 + 0.25 * st["fechado"]
    if forca > 0.04:
        q = round(forca / 0.02) * 0.02
        ch = ("vt_vin_q", ow, oh, q)
        if ch not in c.g.cache:
            c.g.cache[ch] = _vinheta(c.g, ow, oh).point(lambda v, q=q: int(v * q))
        fundo = Image.composite(Image.new("RGB", (ow, oh), (8, 9, 10)), fundo, c.g.cache[ch])
    # a pessoa volta por cima, parada, em resolução cheia. Na entrada e na saída do efeito o quadro
    # original também volta aos poucos (mesma máscara, sem custo extra): nada de salto de nitidez
    mix = d.suave(min(1.0, k / 0.25))
    borda = _BORDA if tem_recorte else _IGUAL
    if mix < 0.999:
        borda = [255 - int((255 - v) * mix) for v in borda]
    # só a parte de cima do quadro precisa ser montada: da linha em que a máscara final cobre a largura
    # toda para baixo, o quadro é o original (parte de baixo protegida / silhueta). Economiza metade do
    # trabalho em resolução cheia no plano fechado.
    cheia = np.asarray(extra if extra is not None else m_peq).min(axis=1) >= 250
    livres = np.nonzero(~cheia)[0]
    ult = int(livres[-1]) + 1 if livres.size else 0
    yl = min(H, int(math.ceil((ult + 1) / sy)))
    if yl <= 0:
        return c.fonte.copy()
    # monta direto numa cópia do original: o fundo entra onde a máscara (invertida) deixa
    m_ = bruta.crop((0, 0, W, yl)) if yl < H else bruta
    inv = m_.point([255 - v for v in borda])
    if extra is not None:
        inv_e = Image.fromarray(255 - np.asarray(extra), "L").resize((W, yl), Image.BILINEAR, box=(0, 0, ow, yl * sy))
        inv = ImageChops.darker(inv, inv_e)
    topo = fundo.resize((W, yl), Image.BILINEAR, box=(0, 0, ow, yl * sy)) if (ow, oh) != (W, H) else fundo.crop((0, 0, W, yl))
    out = c.fonte.copy()
    out.paste(topo.convert("RGBA"), (0, 0), inv)
    return out


# ================================================================== título estável

def _render_titulo(W, texto, alt_max=None, forcar=False):
    pad_x, pad_y = W * 0.034, W * 0.02
    traco_h, folga = max(3, int(W * 0.0075)), int(W * 0.006)
    larg_max = W * 0.80 - pad_x * 2
    tam_max = int(W * 0.082)
    if alt_max is not None:  # cabe no espaço acima da cabeça
        tam_max = min(tam_max, int((alt_max - pad_y * 2 - traco_h - folga) / 1.02))
    if tam_max < int(W * 0.05):
        return None
    f, linhas, al = d.ajustar_texto(texto, larg_max, (alt_max or W * 0.3) - pad_y * 2 - traco_h - folga, 800,
                                    tam_max=tam_max, tam_min=int(W * 0.05), max_linhas=2, entrelinha=1.02)
    larg = max(f.getlength(l) for l in linhas)
    if larg > larg_max + 1 and not forcar:
        return None
    pw, ph = int(larg + pad_x * 2), int(al * len(linhas) + pad_y * 2)
    if alt_max is not None and ph + traco_h + folga > alt_max + 1:
        return None
    placa = d.painel(pw, ph, raio=max(2, int(W * 0.005)), fundo=d.cor(PLACA, 0.97))
    letras = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))   # texto em camada própria: entra com borda macia
    d.escrever(letras, (pad_x, pad_y - f.size * 0.07), linhas, f, TINTA, al=al)
    traco = d.painel(pw, traco_h, raio=0, fundo=LIMA)
    cam = Image.new("RGBA", (pw, ph + traco_h + folga), (0, 0, 0, 0))
    cam.alpha_composite(placa, (0, 0))
    cam.alpha_composite(traco, (0, ph + folga))
    # sombra separada (só a sombra), para acompanhar a abertura da placa
    mg = int(W * 0.03)
    som = Image.new("RGBA", (cam.width + mg * 2, cam.height + mg * 2), (0, 0, 0, 0))
    preto = Image.new("RGBA", cam.size, (0, 0, 0, 255))
    preto.putalpha(cam.getchannel("A").point(lambda v: int(v * 0.30)))
    som.alpha_composite(preto, (mg, mg + int(W * 0.006)))
    som = som.filter(ImageFilter.GaussianBlur(W * 0.011))
    return cam, som, mg, ph, letras


def _titulo(c, e):
    """Layout estável do título (uma vez por evento): no alto (identidade da prévia) se couber acima da
    cabeça; senão embaixo, fora do rosto e da legenda. Devolve (placa+traço, sombra, margem, alt_placa,
    letras, y)."""
    W, H = c.W, c.H
    texto = " ".join(str(e.get("texto", "")).split())
    pos = e.get("posicao", "auto")
    ch = ("vt_titulo", texto, pos, e["inicio"], e["fim"], W, H)
    if ch in c.g.cache:
        return c.g.cache[ch]
    topo_seg, base_seg = 0.115 * H, 0.795 * H
    ts = [float(t) for t in np.linspace(e["inicio"], e["fim"], 9)]
    rosto_y0 = min(c.g.rosto.em(t)[1] for t in ts)
    cabeca = min(c.g.rosto.topo_cabeca(t) for t in ts)
    queixo = max(c.g.rosto.queixo(t) for t in ts)
    limite_topo = cabeca + (rosto_y0 - cabeca) * 0.3      # pode tocar o cabelo; nunca testa, olhos, boca
    res = None
    if pos in ("auto", "topo"):
        r = _render_titulo(W, texto, alt_max=limite_topo - topo_seg)
        if r is not None:
            res = (*r, topo_seg)
    if res is None:
        r = _render_titulo(W, texto) or _render_titulo(W, texto, forcar=True)
        alt = r[0].height
        faixas = []
        if c.g.legendas:
            for t in np.linspace(e["inicio"] - 0.2, e["fim"] + 0.2, 15):
                o = c.g.legendas.ocupacao(float(t))
                if o:
                    faixas.append(o)
        leg = (min(f[0] for f in faixas) - H * 0.012, max(f[1] for f in faixas) + H * 0.012) if faixas else None
        proibido = (limite_topo, queixo)

        def bate(y, fx):
            return fx is not None and y < fx[1] and y + alt > fx[0]

        cands = []
        if leg:
            cands += [leg[1], leg[0] - alt]
        cands += [base_seg - alt, queixo + H * 0.015]
        validos = [y for y in cands if topo_seg - 0.5 <= y <= base_seg - alt + 0.5] or [base_seg - alt]
        y = min(validos, key=lambda v: (bate(v, proibido) * 10 + bate(v, leg) * 3, validos.index(v)))
        res = (*r, y)
        if bate(y, proibido):
            # rosto enorme: último recurso é o cabelo, até a linha da testa; se nem assim couber, o título
            # não aparece (nunca cobre olhos e boca)
            r2 = _render_titulo(W, texto, alt_max=rosto_y0 - H * 0.012 - topo_seg)
            res = (*r2, topo_seg) if r2 is not None else None
    c.g.cache[ch] = res
    return res


def _desenhar_titulo(c, img, e):
    t = c.t
    if t < e["inicio"] - 0.01 or t > e["fim"] + INFO["depois"]:
        return
    lay = _titulo(c, e)
    if lay is None:
        return
    cam, som, mg, ph, letras, y = lay
    W, H = c.W, c.H
    x = W * 0.074
    # entrada: a placa abre da esquerda para a direita e as letras saem JUNTO com ela (frente macia logo
    # atrás da borda da placa: nunca há placa vazia nem letra "cortada" no meio); o traço verde corre por último
    ab = d.saida(d.mapear(t, e["inicio"], e["inicio"] + 0.30))
    fr = d.saida(d.mapear(t, e["inicio"], e["inicio"] + 0.40))
    tr = d.saida(d.mapear(t, e["inicio"] + 0.16, e["inicio"] + 0.60))
    sai = d.entrada(d.mapear(t, e["fim"], e["fim"] + 0.26))
    if ab <= 0.003 or sai >= 0.999:
        return
    opac = 1 - sai
    sobe = -H * 0.012 * sai
    pw = cam.width
    larg = max(1, int(pw * ab))
    s = som.crop((0, 0, min(som.width, larg + mg * 2), som.height))
    d.colar_em(img, s, (x - mg, y - mg + sobe), opacidade=opac * min(1.0, ab * 1.3))
    d.colar_em(img, cam.crop((0, 0, larg, ph)), (x, y + sobe), opacidade=opac)
    if fr > 0.003:
        lt = letras
        if fr < 0.999:
            pena = pw * 0.22
            frente = fr * (pw + pena)
            linha = np.clip((frente - np.arange(pw, dtype=np.float32)) / pena, 0, 1) * 255
            grad = Image.fromarray(linha.astype(np.uint8)[None, :], "L").resize((pw, ph), Image.NEAREST)
            lt = letras.copy()
            lt.putalpha(ImageChops.multiply(letras.getchannel("A"), grad))
            lt = lt.crop((0, 0, larg, ph))       # nunca passa da placa que já abriu
        d.colar_em(img, lt, (x, y + sobe), opacidade=opac)
    if tr > 0.003:
        d.colar_em(img, cam.crop((0, ph, max(1, int(pw * tr)), cam.height)), (x, y + ph + sobe),
                   opacidade=opac)


# ================================================================== quadro

def quadro(c):
    st = _estado(c)
    img = _vertigem(c, st) if st else c.fonte.copy()
    for e in c.eventos:
        if e.get("tipo") == "titulo":
            _desenhar_titulo(c, img, e)
    return img
