"""05 · Zoom digital — aproximações rápidas de câmera nas palavras fortes, com títulos de impacto
e faixa de destaque. Aceita qualquer vídeo (não precisa recortar a pessoa).

Decisões de enquadramento (tomadas UMA vez por evento e guardadas em g.cache, chave determinística):
- zoom: a câmera aproxima em torno de um ponto FIXO do rosto (entre nariz e boca), como a prévia aprovada
  (que aproxima num ponto fixo, sem recentralizar). O ponto desce o necessário para o queixo ampliado nunca
  chegar na legenda do trecho.
- destaque: o lugar (topo/baixo), o tamanho e as linhas do título são decididos olhando a legenda de TODO o
  intervalo do evento e o rosto JÁ AMPLIADO pelo zoom do intervalo. Nunca muda de lugar no meio da exibição.
"""
from __future__ import annotations

import statistics

from PIL import Image, ImageFilter

from .. import desenho as d

INFO = {
    "id": "05-zoom-digital",
    "nome": "Zoom digital",
    "precisa_recorte": False,
    "antes": 0.25,
    "depois": 0.35,
    # identidade da prévia aprovada: 1-2 palavras por vez, Inter 900 grande, entrada com impulso curto
    "legenda": {"peso": 900, "tamanho": 0.078, "cor": "#F8F7F0", "destaque": "#D4ED80", "caixa": "#222729E8",
                "max_caracteres": 11, "max_linhas": 1, "animacao": "subir"},
    "eventos": {
        "zoom": "inicio, fim, nivel (1=leve 1.15x | 2=médio 1.27x | 3=forte 1.42x), "
                "transicao ('corte' = salto seco, padrão | 'suave' = empurrão), alvo ('rosto' padrão | [x,y] 0-1), som",
        "destaque": "inicio, fim (1,2-2,5 s), texto (2 a 4 palavras), marca (a palavra que ganha a faixa neon), "
                    "posicao ('auto' padrão | 'topo'), som",
        "flash": "inicio, fim (curto, 0,1-0,25 s): clarão branco rápido de impacto, som",
    },
}

NIVEIS = {1: 1.15, 2: 1.27, 3: 1.42}
FATOR_FECHADO = 0.75      # plano fechado (rosto > 38% da largura): zoom um pouco mais contido
RESPIRO = 0.015           # a câmera "respira" 1,5% dentro do zoom seco
ANCORA = 0.62             # ponto fixo do zoom: 62% da altura da caixa do rosto (entre nariz e boca)
OLHOS = 0.27              # o título do topo termina acima desta linha da caixa do rosto (sobrancelha/olhos)
TOPO_SEG, BASE_SEG = 0.115, 0.80
TINTA = "#11140F"
FAIXA = "#D4ED80"
CLARO = "#F8F7F0"


# ------------------------------------------------------------------ validação do plano

def _pal(s):
    return str(s).strip(".,!?;:\"'").lower()


def validar(plano, duracao):
    p = []
    evs = plano["eventos"]
    zs = sorted((e for e in evs if e.get("tipo") == "zoom"), key=lambda e: e["inicio"])
    for e in zs:
        if e["fim"] - e["inicio"] > 4.0:
            p.append(f"Zoom de {e['inicio']:.2f}s dura mais de 4 s: termine no fim da frase (0,8-2,5 s).")
    for a, b in zip(zs, zs[1:]):
        folga = b["inicio"] - a["fim"]
        if folga < -0.01:
            p.append(f"Zooms sobrepostos em {b['inicio']:.2f}s: um zoom precisa terminar antes do outro começar.")
        elif folga <= 0.05:
            if int(b.get("nivel", 2)) <= int(a.get("nivel", 2)):
                p.append(f"Zooms colados em {b['inicio']:.2f}s sem subir o nível: escada só sobe (1 → 2 → 3); "
                         "senão junte os dois num zoom só.")
        elif folga < 1.2:
            p.append(f"Zooms muito próximos em {b['inicio']:.2f}s ({folga:.2f} s depois do anterior): deixe pelo "
                     "menos 1,2 s entre eles, ou cole os dois numa escada subindo o nível.")
    ds = sorted((e for e in evs if e.get("tipo") == "destaque"), key=lambda e: e["inicio"])
    for e in ds:
        palavras = str(e.get("texto", "")).split()
        if len(palavras) > 5:
            p.append(f"Destaque longo demais em {e['inicio']:.2f}s (máx. 4 palavras).")
        if e["fim"] - e["inicio"] > 2.6:
            p.append(f"Destaque de {e['inicio']:.2f}s fica tempo demais na tela (máx. 2,5 s).")
        marca = _pal(e.get("marca", ""))
        if marca and marca not in [_pal(w) for w in palavras]:
            p.append(f"Destaque de {e['inicio']:.2f}s: a marca '{e.get('marca')}' não é uma palavra do texto "
                     f"'{e.get('texto')}'. Use uma palavra exata do texto.")
        if e.get("posicao", "auto") not in ("auto", "topo", "baixo"):
            p.append(f"Destaque de {e['inicio']:.2f}s: posicao deve ser 'auto' ou 'topo'.")
    for a, b in zip(ds, ds[1:]):
        if b["inicio"] < a["fim"]:
            p.append(f"Dois destaques ao mesmo tempo em {b['inicio']:.2f}s: um precisa sair antes do outro entrar "
                     "(deixe 0,3 s entre eles).")
    for e in evs:
        if e.get("tipo") == "flash" and e["fim"] - e["inicio"] > 0.3:
            p.append(f"Flash de {e['inicio']:.2f}s longo demais (use 0,1-0,25 s).")
    return p


# ------------------------------------------------------------------ utilidades de tempo

def _amostras(t0, t1, fps=30.0):
    n = max(1, int((t1 - t0) * fps))
    return [t0 + (t1 - t0) * k / n for k in range(n + 1)]


def _faixa_legenda(g, t0, t1):
    """União (y0 mín., y1 máx.) da legenda entre t0 e t1, ou None se não houver legenda no intervalo."""
    if not g.legendas:
        return None
    y0 = y1 = None
    for t in _amostras(t0, t1, min(30.0, g.fps or 30.0)):
        f = g.legendas.ocupacao(t)
        if f:
            y0 = f[0] if y0 is None else min(y0, f[0])
            y1 = f[1] if y1 is None else max(y1, f[1])
    return None if y0 is None else (y0, y1)


def _zooms(g):
    ch = ("z05_lista",)
    if ch not in g.cache:
        g.cache[ch] = sorted((e for e in g.plano["eventos"] if e.get("tipo") == "zoom"), key=lambda e: e["inicio"])
    return g.cache[ch]


# ------------------------------------------------------------------ câmera

def _param_zoom(g, e):
    """Nível efetivo e ponto fixo (frações) de um evento de zoom. Calculado uma vez por evento."""
    ch = ("z05", e["inicio"], e["fim"])
    if ch in g.cache:
        return g.cache[ch]
    W, H = g.W, g.H
    nivel = NIVEIS.get(int(e.get("nivel", 2)), NIVEIS[2])
    ts = _amostras(e["inicio"], e["fim"], 10)
    caixas = [g.rosto.em(t) for t in ts]
    larg = statistics.median((c[2] - c[0]) / W for c in caixas)
    if larg > 0.38:
        nivel = 1 + (nivel - 1) * FATOR_FECHADO
    alvo = e.get("alvo", "rosto")
    if isinstance(alvo, (list, tuple)) and len(alvo) == 2:
        par = {"nivel": nivel, "modo": "alvo", "centro": (float(alvo[0]), float(alvo[1]))}
    else:
        esc_max = 1 + (nivel - 1) * (1 + RESPIRO)
        ax = statistics.median((c[0] + c[2]) / 2 / W for c in caixas)
        ay = statistics.median((c[1] + (c[3] - c[1]) * ANCORA) / H for c in caixas)
        queixo = max(g.rosto.queixo(t) for t in ts) / H
        faixa = _faixa_legenda(g, e["inicio"], e["fim"])
        limite = (faixa[0] / H - 0.02) if faixa else BASE_SEG
        if queixo <= limite:
            # queixo ampliado = ay + (queixo - ay) * esc  <=  limite   ->  ay >= (queixo*esc - limite) / (esc - 1)
            ay = max(ay, (queixo * esc_max - limite) / (esc_max - 1))
        else:  # o queixo já está na altura da legenda sem zoom: segura o queixo parado
            ay = queixo
        par = {"nivel": nivel, "modo": "rosto", "ancora": (min(max(ax, 0.0), 1.0), min(max(ay, 0.0), 1.0))}
    g.cache[ch] = par
    return par


def _camera(g, t):
    """(escala, parâmetros do zoom dominante ou None) no instante t — só do plano e do tempo."""
    esc, par = 1.0, None
    for e in _zooms(g):
        if t < e["inicio"] - 0.01 or t > e["fim"] + 0.01:
            continue
        if e.get("transicao", "corte") == "suave":
            k = d.suave(d.mapear(t, e["inicio"], e["inicio"] + 0.45)) * (1 - d.suave(d.mapear(t, e["fim"] - 0.3, e["fim"])))
        else:
            k = 1.0 if e["inicio"] <= t < e["fim"] else 0.0
            k *= 1 + RESPIRO * d.mapear(t, e["inicio"], e["fim"])
        if k > 0:
            p = _param_zoom(g, e)
            v = 1 + (p["nivel"] - 1) * k
            if v > esc:
                esc, par = v, p
    return esc, par


def _centro_enquadrar(par, esc):
    if par["modo"] == "alvo":
        return par["centro"]
    ax, ay = par["ancora"]
    # mantém o ponto (ax, ay) parado na tela: o rosto cresce em volta dele, sem descer
    return (ax + (0.5 - ax) / esc, ay + (0.5 - ay) / esc)


def _y_na_tela(g, t, y):
    """Onde a altura y (pixels do quadro original) aparece depois do zoom em t (mesma conta do d.enquadrar)."""
    esc, par = _camera(g, t)
    if par is None or esc <= 1.0005:
        return y
    H = g.H
    ch = H / esc
    cy = d.limitar(_centro_enquadrar(par, esc)[1] * H, ch / 2, H - ch / 2)
    return (y - (cy - ch / 2)) * esc


def _desfoque_corte(g, t):
    """2-3 quadros de borrão de movimento no instante do salto (sensação de lente)."""
    for e in _zooms(g):
        if e.get("transicao", "corte") == "corte":
            for borda in (e["inicio"], e["fim"]):
                if 0 <= t - borda < 0.07:
                    return 2.6 * (1 - (t - borda) / 0.07)
    return 0.0


# ------------------------------------------------------------------ título de impacto

def _titulo(g, texto, marca, tam, max_linhas):
    """Camada do título (recortada pelo conteúdo) no tamanho de fonte 'tam' (ou menor, se não couber)."""
    W, H = g.W, g.H
    ch = ("dest05", texto, marca, int(tam), max_linhas)
    if ch in g.cache:
        return g.cache[ch]
    f, linhas, al = d.ajustar_texto(texto, W * 0.76, H * 0.2, 900, tam_max=int(tam),
                                    tam_min=int(W * 0.05), max_linhas=max_linhas, entrelinha=1.04)
    s = f.size
    larg = max(f.getlength(l) for l in linhas)
    cam = Image.new("RGBA", (int(larg + s * 1.2), int(al * len(linhas) + s * 0.9)), (0, 0, 0, 0))
    espaco = f.getlength(" ")
    pos = []
    for li, l in enumerate(linhas):
        y = s * 0.3 + li * al
        x = (cam.width - f.getlength(l)) / 2
        for p in l.split():
            pos.append((p, x, y))
            x += f.getlength(p) + espaco
    marcadas = []
    # 1º as faixas neon (todas), depois o texto: a faixa de uma linha nunca cobre letras da outra
    for p, x, y in pos:
        if marca and _pal(p) == marca:
            bb = f.getbbox(p)  # caixa REAL da palavra (inclui acento de maiúscula e cedilha)
            topo = y + bb[1] - 0.07 * s
            alt = max(0.9 * s, (bb[3] - bb[1]) + 0.14 * s)
            larg_f = (bb[2] - bb[0]) + 0.3 * s
            faixa = d.painel(larg_f, alt, raio=int(s * 0.12), fundo=FAIXA)
            faixa = faixa.rotate(-2, resample=Image.BICUBIC, expand=True)
            cx, cy = x + (bb[0] + bb[2]) / 2, topo + alt / 2
            cam.alpha_composite(faixa, (int(cx - faixa.width / 2), int(cy - faixa.height / 2)))
            marcadas.append(p)
    for p, x, y in pos:
        if marca and _pal(p) == marca:
            d.escrever(cam, (x, y), [p], f, TINTA)
        else:
            d.escrever(cam, (x, y), [p], f, CLARO, sombra=0.75)
    # recorta pelo conteúdo (ignora o rastro quase invisível da sombra) para medir a altura real
    a = cam.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if a:
        m = int(s * 0.04)
        cam = cam.crop((max(0, a[0] - m), max(0, a[1] - m), min(cam.width, a[2] + m), min(cam.height, a[3] + m)))
    g.cache[ch] = (cam, s)
    return g.cache[ch]


def _caber(g, texto, marca, alt_disp, pulso, minimo=0.05):
    """Maior título (2 linhas ou 1) cuja altura, já com o pulso, cabe em alt_disp. None se não couber
    com fonte de pelo menos minimo*W."""
    W = g.W
    melhor = None
    for ml in (2, 1):
        tam = int(W * 0.125)
        while tam >= int(W * minimo):
            cam, s = _titulo(g, texto, marca, tam, ml)
            if s < int(W * minimo):
                break
            if cam.height * pulso <= alt_disp and cam.width * pulso <= W * 0.86:
                if melhor is None or s > melhor[1]:
                    melhor = (cam, s)
                break
            tam = int(tam * 0.92)
    return melhor


def _layout(g, e):
    """Lugar, tamanho e camada do título — decididos UMA vez para o evento inteiro."""
    texto = str(e.get("texto", "")).upper().strip()
    marca = _pal(str(e.get("marca", "")).upper())
    pos_pedida = e.get("posicao", "auto")
    ch = ("pos05", e["inicio"], e["fim"], texto, marca, pos_pedida)
    if ch in g.cache:
        return g.cache[ch]
    W, H = g.W, g.H
    ts = _amostras(e["inicio"], e["fim"], 15)
    faixa = _faixa_legenda(g, e["inicio"], e["fim"])
    olhos, cabeca, queixo, pulso = H, H, 0.0, 1.0
    for t in ts:
        x0, y0, x1, y1 = g.rosto.em(t)
        olhos = min(olhos, _y_na_tela(g, t, y0 + (y1 - y0) * OLHOS))
        cabeca = min(cabeca, _y_na_tela(g, t, g.rosto.topo_cabeca(t)))
        queixo = max(queixo, _y_na_tela(g, t, g.rosto.queixo(t)))
        pulso = max(pulso, 1 + 0.3 * (_camera(g, t)[0] - 1))
    pulso *= 1.015  # passada da mola na entrada

    def topo():
        a = TOPO_SEG * H
        if faixa and faixa[1] < H * 0.5:  # legenda em cima da cabeça: o título fica abaixo dela
            a = max(a, faixa[1] + 0.015 * H)
        b = olhos - 0.01 * H
        r = _caber(g, texto, marca, b - a, pulso)
        if r is None:
            return None
        h = r[0].height * pulso
        ideal = min(0.20 * H, max(a + h / 2, cabeca - h * 0.2))
        return ("topo", min(max(ideal, a + h / 2), b - h / 2), r[0])

    def baixo():
        a = queixo + 0.03 * H
        if faixa and faixa[1] > H * 0.5:
            a = max(a, faixa[1] + 0.02 * H)
        a = max(a, 0.6 * H)
        b = BASE_SEG * H
        # embaixo o espaço é curto: só aceita se o título sair grande; senão vai para o topo
        r = _caber(g, texto, marca, b - a, pulso, minimo=0.085)
        if r is None:
            return None
        h = r[0].height * pulso
        return ("baixo", a + h / 2, r[0])

    if pos_pedida == "baixo":
        ordem = (baixo, topo)
    elif pos_pedida == "auto" and faixa and (faixa[0] + faixa[1]) / 2 < H * 0.5:
        ordem = (baixo, topo)  # legenda acima da cabeça: o título vai para baixo
    else:
        ordem = (topo, baixo)
    res = None
    for fn in ordem:
        res = fn()
        if res:
            break
    if res is None:  # último recurso: menor título possível, colado no topo seguro
        cam, _ = _titulo(g, texto, marca, int(W * 0.05), 1)
        res = ("topo", TOPO_SEG * H + cam.height * pulso / 2, cam)
    g.cache[ch] = res
    return res


# ------------------------------------------------------------------ quadro

def preparar(g):
    """Decide de uma vez a câmera de cada zoom e o lugar/tamanho de cada título (fora do laço de quadros)."""
    for e in _zooms(g):
        _param_zoom(g, e)
    for e in g.plano["eventos"]:
        if e.get("tipo") == "destaque":
            _layout(g, e)


def quadro(c):
    g = c.g
    esc, par = _camera(g, c.t)
    img = c.fonte
    blur = _desfoque_corte(g, c.t)
    zoom = par is not None and esc > 1.0005
    if blur > 0.2:
        # quadro do salto: recorta, reduz, borra e amplia numa passada só (sem o redimensionamento em alta)
        caixa = (0, 0, c.W, c.H)
        if zoom:
            cw, ch = c.W / esc, c.H / esc
            cx, cy = _centro_enquadrar(par, esc)
            cx = d.limitar(cx * c.W, cw / 2, c.W - cw / 2)
            cy = d.limitar(cy * c.H, ch / 2, c.H - ch / 2)
            caixa = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        peq = img.resize((max(1, c.W // 3), max(1, c.H // 3)), Image.BILINEAR, box=caixa)
        img = peq.filter(ImageFilter.GaussianBlur(blur / 3)).resize((c.W, c.H), Image.BILINEAR)
    elif zoom:
        img = d.enquadrar(img, esc, _centro_enquadrar(par, esc))
    img = img.copy() if img is c.fonte else img
    for e in c.eventos:
        tipo = e.get("tipo")
        if tipo == "destaque":
            k = e.env(c.t, 0.18, 0.2)
            if k <= 0:
                continue
            _, y, cam = _layout(g, e)
            entrada = d.mola(d.mapear(c.t, e["inicio"], e["inicio"] + 0.24), 1.2)  # passa do ponto ≤ 2%
            pulso = 1 + 0.3 * (esc - 1)  # o título "pulsa" junto com a câmera, como na prévia
            d.colar(img, cam, (c.W / 2, y), escala=(0.75 + 0.25 * entrada) * pulso, opacidade=k)
        elif tipo == "flash":
            if e["inicio"] <= c.t <= e["fim"]:
                k = 1 - d.mapear(c.t, e["inicio"], e["fim"])
                if k > 0:
                    ch = ("branco05", c.W, c.H)
                    if ch not in g.cache:
                        g.cache[ch] = Image.new("RGBA", (c.W, c.H), (255, 255, 255, 255))
                    img = Image.blend(img, g.cache[ch], 0.59 * k)
    return img
