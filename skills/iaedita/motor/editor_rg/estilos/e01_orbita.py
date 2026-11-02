"""01 · Órbita — cartões de papel giram ao redor da pessoa e passam ATRÁS dela (oclusão com o recorte).

Cada cartão chega à frente da pessoa no instante em que a palavra dele é dita, segura ali para ser lido
e segue girando; o próximo sai de trás da cabeça. A órbita se adapta ao enquadramento:
- com recorte: o arco de trás passa atrás da cabeça e o arco da frente passa abaixo do queixo; enquanto um
  cartão é lido, os outros esperam INTEIROS ao lado da cabeça (anel aberto, cartões de lado um pouco menores)
  ou, sem espaço (plano fechado), somem atrás dela: nunca fica palavra cortada parada na tela;
- sem recorte: vira um carrossel abaixo do queixo, por cima com sombra, que nunca cobre o rosto.
"""
from __future__ import annotations

import math
import re

import numpy as np
from PIL import Image, ImageDraw

from .. import desenho as d

INFO = {
    "id": "01-orbita",
    "nome": "Órbita",
    "precisa_recorte": True,
    "antes": 0.75,     # a órbita entra nos 0,7 s ANTES de 'inicio' (o 1º cartão chega na frente em 'inicio')
    "depois": 0.05,    # a saída acontece DENTRO do evento (some por completo em 'fim')
    "legenda": {"peso": 800, "tamanho": 0.066, "cor": "#F8F7F0", "destaque": "#D4ED80", "caixa": "#222729ED",
                "max_caracteres": 18, "max_linhas": 1, "animacao": "subir", "posicao": "baixo"},
    "eventos": {
        "orbita": "inicio (= quando o 1º cartão está na frente, na palavra dele), fim (quando a órbita já sumiu), "
                  "cartoes: lista de 1 a 3 {texto (1-3 palavras, até 18 letras), rotulo (opcional, 1-2 palavras "
                  "em cima do texto, até 14 letras), em (segundo em que ESTE cartão chega na frente; o 1º usa "
                  "'inicio')}, sentido (1 = cartões vêm da direita, -1 = da esquerda; padrão alterna), som",
        "titulo": "inicio, fim, texto (2 a 5 palavras), som — título de papel grande, fora do rosto "
                  "(nunca junto com uma órbita)",
    },
}

PAPEL = "#FFFDF6"
TINTA = "#222729"
CINZA = "#6E756A"
ACENTO = "#D4ED80"
BORDA = "#FFFFFFB0"

# medidas em fração da largura do vídeo (W)
PAD_X, PAD_Y = 0.050, 0.042
TAM_ROTULO = 0.042
TAM_TEXTO_MAX, TAM_TEXTO_MIN = 0.074, 0.056
TAM_TEXTO_UMA_LINHA = 0.060          # abaixo disso, prefere quebrar em 2 linhas
TAM_TEXTO_DUAS = 0.066               # texto em 2 linhas: um pouco menor (cartão não fica alto demais)
LARG_MIN, LARG_MAX = 0.30, 0.50
BARRA_W, BARRA_H = 0.085, 0.013
RAIO = 0.030
LEGIVEL = 0.035                      # menor texto permitido (3,5% da largura)

INCLINACAO = math.radians(-8)        # inclinação do anel no plano da tela (como na prévia)
DERIVA = math.radians(14)            # giro lento contínuo (rad/s) enquanto um cartão é lido
DERIVA_MAX = 0.14                    # giro máximo durante uma leitura (fração do passo entre cartões)
ENTRADA = 0.7                        # segundos de entrada antes de 'inicio'
A0 = math.pi / 2                     # ângulo da frente


def _escala_prof(z, k_lado=1.0, z_lado=-0.5):
    """Tamanho pela profundidade: frente 1.0, lados 0.82, fundo 0.64.
    k_lado < 1 encolhe os cartões de trás (para caberem inteiros ao lado da cabeça)."""
    s = 0.82 + 0.18 * z
    if z < 0 and k_lado != 1.0:
        s *= 1 + (k_lado - 1) * d.limitar(-z / max(0.15, -z_lado))
    return s


def _passo(n):
    """Ângulo entre cartões. Com 1 ou 2 cartões o anel tem 3 lugares: o 2º cartão espera AO LADO da cabeça
    (não escondido atrás dela) e, depois de lido, o 1º fica do outro lado (comparação lado a lado)."""
    return 2 * math.pi / max(3, n)


def _lado_repouso(n):
    """Pior posição de descanso dos cartões de lado (contando o giro lento): fator horizontal e profundidade."""
    ang = A0 + _passo(n) + 0.5 * DERIVA_MAX * _passo(n)
    return abs(math.cos(ang)), math.sin(ang)


# ---------------------------------------------------------------- validação

_INTERNO = re.compile(r"(\b\d{2}-[a-z]|órbita\s*\d|orbita\s*\d|estilo\s*\d|\{|\}|seu texto|texto aqui|xxx)", re.I)


def validar(plano, duracao):
    p = []
    orbs = [e for e in plano["eventos"] if e.get("tipo") == "orbita"]
    tits = [e for e in plano["eventos"] if e.get("tipo") == "titulo"]
    for e in orbs:
        ini, fim = e["inicio"], e["fim"]
        cs = e.get("cartoes") or []
        if not 1 <= len(cs) <= 4:
            p.append(f"Órbita em {ini:.2f}s: use de 1 a 3 cartões, no máximo 4 (tem {len(cs)}).")
            continue
        if fim - ini < 1.6:
            p.append(f"Órbita em {ini:.2f}s curta demais ({fim - ini:.1f}s): mínimo 1,6 s.")
        ant = ini
        for k, c in enumerate(cs):
            txt = str(c.get("texto", "")).strip()
            rot = str(c.get("rotulo", "") or "").strip()
            if not txt:
                p.append(f"Órbita em {ini:.2f}s: cartão {k + 1} sem texto.")
            if len(txt) > 22 or len(txt.split()) > 3:
                p.append(f"Cartão '{txt}' longo demais (máx. 3 palavras / 18 letras).")
            if len(rot) > 16:
                p.append(f"Rótulo '{rot}' longo demais (máx. 14 letras).")
            for s in (txt, rot):
                if s and _INTERNO.search(s):
                    p.append(f"Texto interno/placeholder na tela: '{s}'. Escreva só palavras da fala.")
            if k > 0:
                em = c.get("em")
                if em is None:
                    continue
                if em < ant + 0.7:
                    p.append(f"Cartão '{txt}' chega {em - ant:.2f}s depois do anterior: mínimo 0,7 s (ideal 1,2-3 s).")
                if em > fim - 0.8:
                    p.append(f"Cartão '{txt}' chega em {em:.2f}s, perto demais do fim da órbita ({fim:.2f}s): "
                             "deixe pelo menos 0,8 s.")
                ant = em
    orbs = sorted(orbs, key=lambda e: e["inicio"])
    for a, b in zip(orbs, orbs[1:]):
        if b["inicio"] - ENTRADA < a["fim"] + 0.05:
            p.append(f"Órbitas coladas em {b['inicio']:.2f}s: a próxima precisa começar pelo menos 0,75 s "
                     "depois do fim da anterior.")
    for t in tits:
        if len(str(t.get("texto", "")).split()) > 6:
            p.append(f"Título longo demais em {t['inicio']:.2f}s (máx. 5 palavras).")
        if _INTERNO.search(str(t.get("texto", ""))):
            p.append(f"Texto interno/placeholder no título: '{t.get('texto')}'.")
        for o in orbs:
            if t["inicio"] < o["fim"] and o["inicio"] - ENTRADA < t["fim"]:
                p.append(f"Título em {t['inicio']:.2f}s ao mesmo tempo que uma órbita: separe no tempo.")
    return p


# ---------------------------------------------------------------- pré-desenho

def _texto_espacado(txt, f, cor_txt, espaco):
    larg = sum(f.getlength(ch) for ch in txt) + espaco * max(0, len(txt) - 1)
    img = Image.new("RGBA", (int(larg) + 4, int(f.size * 1.35)), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    x = 0.0
    for ch in txt:
        dr.text((x, f.size * 1.0), ch, font=f, fill=d.cor(cor_txt), anchor="ls")
        x += f.getlength(ch) + espaco
    return img


def _cartao(g, texto, rotulo):
    """Cartão de papel pronto (sombra + papel + texto), rótulo e barra separados (animados por quadro)."""
    chave = ("orb_cartao", texto, rotulo, g.W)
    if chave in g.cache:
        return g.cache[chave]
    W = g.W
    px, py = PAD_X * W, PAD_Y * W
    larg_max_txt = LARG_MAX * W - 2 * px
    f = None
    tam = int(TAM_TEXTO_MAX * W)
    while tam >= int(TAM_TEXTO_UMA_LINHA * W):      # 1º: uma linha só (cartão mais limpo e mais baixo)
        fx = d.fonte(tam, 800)
        if fx.getlength(texto) <= larg_max_txt:
            f, linhas, al = fx, [texto], tam * 1.04
            break
        tam -= max(1, int(W * 0.002))
    if f is None:                                     # 2º: duas linhas
        f, linhas, al = d.ajustar_texto(texto, larg_max_txt, TAM_TEXTO_MAX * W * 1.05 * 2 + 2, peso=800,
                                        tam_max=int(TAM_TEXTO_DUAS * W), tam_min=int(TAM_TEXTO_MIN * W),
                                        max_linhas=2, entrelinha=1.04)
        if any(f.getlength(l) > larg_max_txt for l in linhas):   # texto longo demais: nunca corta
            f, linhas, al = d.ajustar_texto(texto, larg_max_txt, TAM_TEXTO_MIN * W * 3.3, peso=800,
                                            tam_max=int(TAM_TEXTO_MIN * W), tam_min=int(0.045 * W),
                                            max_linhas=3, entrelinha=1.04)
    larg_txt = max(f.getlength(l) for l in linhas)
    rot_img = None
    if rotulo:
        fr = d.fonte(int(TAM_ROTULO * W), 700)
        rot_img = _texto_espacado(rotulo.upper(), fr, CINZA, fr.size * 0.10)
        if rot_img.width > larg_max_txt:  # rótulo comprido: comprime um pouco (validar já avisa)
            k = larg_max_txt / rot_img.width
            rot_img = rot_img.resize((int(rot_img.width * k), int(rot_img.height * k)), Image.LANCZOS)
    w = max(larg_txt, rot_img.width if rot_img else 0) + 2 * px
    w = int(min(LARG_MAX * W, max(LARG_MIN * W, w)))
    cap = 0.73  # altura das maiúsculas da Inter (fração do tamanho)
    y = py
    pos_rot = None
    if rot_img is not None:
        tr = int(TAM_ROTULO * W)
        pos_rot = (px, y - tr * (1 - cap))      # topo das maiúsculas do rótulo na margem de cima
        y += tr * cap + 0.026 * W
    bases = []
    for i in range(len(linhas)):
        bases.append(y + f.size * cap + i * al)
    y_barra = bases[-1] + f.size * 0.22 + 0.020 * W
    h = int(y_barra + BARRA_H * W + py)
    papel = d.painel(w, h, raio=int(RAIO * W), fundo=PAPEL, borda=BORDA, larg_borda=max(1, int(W * 0.002)))
    dr = ImageDraw.Draw(papel)
    for i, l in enumerate(linhas):
        dr.text((px, bases[i]), l, font=f, fill=d.cor(TINTA), anchor="ls")
    corpo, (dx, dy) = d.sombra(papel, raio=W * 0.02, opacidade=0.40, desloc=(0, W * 0.014))
    m = -dx
    cart = {"id": (texto, rotulo), "tam": f.size / W, "w": w, "h": h, "m": m, "base": corpo, "rotulo": rot_img,
            "pos_rotulo": (m + pos_rot[0], m + pos_rot[1]) if pos_rot else None,
            "pos_barra": (m + px, m + y_barra), "barra_w": BARRA_W * W, "barra_h": BARRA_H * W}
    # versões prontas mais usadas (evita compor a cada quadro)
    cart["so_barra"] = _compor(cart, 0.0, 1.0)
    cart["completo"] = _compor(cart, 1.0, 1.0)
    g.cache[chave] = cart
    return cart


def _compor(cart, k_rot, k_barra):
    img = cart["base"].copy()
    if cart["rotulo"] is not None and k_rot > 0.01:
        d.colar_em(img, cart["rotulo"], cart["pos_rotulo"], k_rot)
    if k_barra > 0.01:
        bw = max(2, int(cart["barra_w"] * k_barra))
        barra = d.painel(bw, max(2, int(cart["barra_h"])), raio=int(cart["barra_h"] / 2), fundo=ACENTO)
        img.alpha_composite(barra, (int(cart["pos_barra"][0]), int(cart["pos_barra"][1])))
    return img


def _imagem_cartao(cart, k_rot, k_barra):
    if cart["rotulo"] is None:
        k_rot = 0.0
    if k_barra >= 0.99:
        if k_rot >= 0.99:
            return cart["completo"]
        if k_rot <= 0.01:
            return cart["so_barra"]
    elif k_barra <= 0.01 and k_rot <= 0.01:
        return cart["base"]
    return _compor(cart, k_rot, k_barra)


def _titulo_img(g, texto):
    chave = ("orb_titulo", texto, g.W)
    if chave in g.cache:
        return g.cache[chave]
    W = g.W
    px, py = 0.055 * W, 0.040 * W
    f, linhas, al = d.ajustar_texto(texto, 0.72 * W, 0.2 * g.H, peso=800, tam_max=int(0.088 * W),
                                    tam_min=int(0.062 * W), max_linhas=2, entrelinha=1.04)
    larg = max(f.getlength(l) for l in linhas)
    cap = 0.73
    bases = [py + f.size * cap + i * al for i in range(len(linhas))]
    y_barra = bases[-1] + f.size * 0.22 + 0.022 * W
    w = int(larg + 2 * px)
    h = int(y_barra + 0.016 * W + py)
    papel = d.painel(w, h, raio=int(0.034 * W), fundo=PAPEL, borda=BORDA, larg_borda=max(1, int(W * 0.002)))
    dr = ImageDraw.Draw(papel)
    for i, l in enumerate(linhas):
        dr.text((px, bases[i]), l, font=f, fill=d.cor(TINTA), anchor="ls")
    barra = d.painel(int(0.12 * W), int(0.016 * W), raio=int(0.008 * W), fundo=ACENTO)
    papel.alpha_composite(barra, (int(px), int(y_barra)))
    img, _ = d.sombra(papel, raio=W * 0.022, opacidade=0.42, desloc=(0, W * 0.016))
    g.cache[chave] = (img, w, h)
    return g.cache[chave]


def preparar(g):
    """Pré-desenha cartões e títulos; decide a posição da legenda pelo enquadramento."""
    H = g.H
    for e in g.plano["eventos"]:
        if e.get("tipo") == "orbita":
            for c in (e.get("cartoes") or [])[:4]:
                _cartao(g, str(c.get("texto", "")).strip() or " ", str(c.get("rotulo", "") or "").strip())
        elif e.get("tipo") == "titulo":
            _titulo_img(g, str(e.get("texto", "")).strip() or " ")
    # ordem das órbitas (para alternar o sentido do giro)
    inis = sorted(e["inicio"] for e in g.plano["eventos"] if e.get("tipo") == "orbita")
    g.cache["orb_ordem"] = {round(t, 3): i for i, t in enumerate(inis)}
    # legenda: acima da cabeça quando há espaço (como na prévia aprovada); senão embaixo, abaixo da órbita
    topo_leg = 0.80 * H
    if g.legendas is not None:
        p = g.legendas.p
        alt = g.legendas.f.size * 1.18 * max(1, p.max_linhas) + g.legendas.f.size * 0.56
        pedida = ((g.plano.get("legenda") or {}).get("perfil") or {}).get("posicao")
        if not pedida and p.y_fixo is None:
            ts = np.linspace(0, max(0.0, g.duracao - 0.05), 40)
            cabecas = np.array([g.rosto.topo_cabeca(float(t)) for t in ts])
            cabeca_alta = float(np.percentile(cabecas, 15))
            p.posicao = "acima-da-cabeca" if cabeca_alta - 0.03 * H - alt >= 0.115 * H else "baixo"
        if p.posicao == "baixo" and p.y_fixo is None:
            topo_leg = 0.80 * H - alt
    g.cache["orb_topo_legenda"] = topo_leg


# ---------------------------------------------------------------- geometria e tempo

def _rosto_suave(c):
    dur = c.g.duracao
    cx = np.array([c.g.rosto.em(min(dur, max(0.0, c.t + dt))) for dt in (-0.6, -0.3, 0.0, 0.3, 0.6)])
    return cx.mean(axis=0)


def _cartoes_do_evento(c, e):
    cs = (e.get("cartoes") or [])[:4]
    return [_cartao(c.g, str(x.get("texto", "")).strip() or " ", str(x.get("rotulo", "") or "").strip()) for x in cs]


def _geometria(c, carts, recorte, lados=None, caixa=None):
    """Órbita no instante: centro, raios, encaixe de cada cartão e a zona do rosto (protegida).
    lados = tamanhos (fração) dos cartões de lado decididos para a órbita toda (ver _modo_lados),
    ou None para o anel simples (plano fechado demais: os de lado ficam escondidos atrás da cabeça)."""
    W, H = c.W, c.H
    x0, y0, x1, y1 = caixa if caixa is not None else _rosto_suave(c)
    fw, fh = x1 - x0, y1 - y0
    queixo = y1 + 0.08 * fh
    lim_baixo = c.g.cache.get("orb_topo_legenda", 0.80 * H) - 0.015 * H
    topo_frente = queixo + 0.016 * H
    esp = lim_baixo - topo_frente                       # espaço para o cartão da frente
    fits = [d.limitar(esp / k["h"], 0.70, 1.0) for k in carts]
    href = min(k["h"] * f for k, f in zip(carts, fits))  # cartões mais altos crescem para baixo
    if recorte:
        y_frente = min(topo_frente + href / 2, lim_baixo - href / 2)
        # arco de trás atrás da cabeça: no meio do rosto (plano médio, como na prévia); em plano fechado
        # desce para a altura da boca/queixo, onde a cabeça é mais estreita
        fechado = d.limitar((fw / W - 0.30) / 0.12)
        y_tras = y0 + (0.45 + 0.27 * fechado) * fh
        y_tras = min(y_tras, y_frente - 0.06 * H)
    else:
        hmax = max(k["h"] * f for k, f in zip(carts, fits))
        y_frente = lim_baixo - hmax + href / 2    # carrossel abaixo do queixo
        y_tras = max(queixo + 0.02 * H + href * _escala_prof(-1) / 2, y_frente - 0.16 * H)
        y_tras = min(y_tras, y_frente - 0.012 * H)
    cy = (y_frente + y_tras) / 2
    ry = max(0.006 * H, (y_frente - y_tras) / 2)
    cxf, zs = _lado_repouso(len(carts))
    # com recorte, o centro compensa a inclinação do anel: os cartões de lado ficam simétricos ao rosto
    ajuste = ry * zs * math.sin(INCLINACAO) if (recorte and len(carts) >= 2) else 0.0
    cx = d.limitar((x0 + x1) / 2 + ajuste, 0.36 * W, 0.54 * W)
    w_lado = max(k["w"] * f for k, f in zip(carts, fits)) * _escala_prof(0) * 1.02
    rx = min(0.40 * W, cx - 0.035 * W - w_lado / 2, 0.905 * W - cx - w_lado / 2)
    rx = max(rx, 0.10 * W)
    geo = {"cx": cx, "cy": cy, "rx": rx, "ry": ry, "fits": fits, "href": href,
           "k_lados": [1.0] * len(carts), "z_lado": zs,
           # zona protegida do rosto (testa até o queixo): nada passa NA FRENTE dela
           "zona": (x0 - 0.07 * fw, y0 - 0.40 * fh, x1 + 0.07 * fw, y1 + 0.005 * H)}
    if recorte and len(carts) >= 2:
        # cartões de lado INTEIROS ao lado da cabeça (como na prévia): o anel abre o bastante para o cartão
        # em descanso ficar fora do rosto (com folga) e dentro da tela
        ca, sa = math.cos(INCLINACAO), math.sin(INCLINACAO)
        cxl = cx - ry * zs * sa                         # centro horizontal dos cartões de lado
        mx, ml = 0.05 * fw, 0.030 * W                   # folga do rosto e da borda
        sl = _escala_prof(zs)
        r_min0 = max(x1 + mx - cxl, cxl - x0 + mx)      # distância mínima até a borda do rosto
        r_cap = (min(cx, W - cx) - 0.015 * W) * cxf * ca  # o anel não sai da tela
        r_borda = min(W - ml - cxl, cxl - ml)
        geo["_lados"] = (min((r_borda - r_min0) / 2, r_cap - r_min0),
                         [k["w"] * f * 1.02 * sl / 2 for k, f in zip(carts, fits)],
                         [LEGIVEL / max(1e-6, sl * k.get("tam", TAM_TEXTO_MAX) * f)
                          for k, f in zip(carts, fits)])
        if lados:
            hw = max(m * k for m, k in zip(geo["_lados"][1], lados))
            r = min(r_min0 + hw + 0.015 * W, max(r_min0 + hw, min(r_borda - hw, r_cap)))
            geo["rx"] = r / (cxf * ca)
            geo["k_lados"] = list(lados)
    return geo


def _modo_lados(c, e, carts, T, ent):
    """Decide UMA vez por órbita se os cartões de lado cabem inteiros ao lado da cabeça (e com que tamanho).
    Fixo na órbita toda: o anel não muda de modo nem de tamanho no meio (sem pulos)."""
    chave = ("orb_lados", float(e["inicio"]), tuple(k["id"] for k in carts), c.W)
    if chave in c.g.cache:
        return c.g.cache[chave]
    dur = c.g.duracao
    folgas, metades, mins = [], None, None
    for t in np.linspace(T[0] - ent, float(e["fim"]), 14):
        caixa = c.g.rosto.em(min(dur, max(0.0, float(t))))
        geo = _geometria(c, carts, True, None, caixa)
        hw_max, metades_t, mins_t = geo["_lados"]
        folgas.append(hw_max)
        if metades is None:
            metades, mins = metades_t, mins_t
        else:
            metades = [max(a, b) for a, b in zip(metades, metades_t)]
            mins = [max(a, b) for a, b in zip(mins, mins_t)]
    hw = float(np.percentile(folgas, 10))          # quase o pior momento (ignora um tremido do detector)
    ks = [min(1.0, hw / max(1.0, m)) for m in metades]
    ok = all(k >= max(0.55, km) for k, km in zip(ks, mins))
    c.g.cache[chave] = ks if ok else None
    return c.g.cache[chave]


def _tempos(e, n):
    ini, fim = float(e["inicio"]), float(e["fim"])
    cs = e.get("cartoes") or []
    span = max(0.9 * (n - 1), fim - 1.2 - ini)
    T = [ini]
    for k in range(1, n):
        em = cs[k].get("em") if k < len(cs) else None
        tk = float(em) if em is not None else ini + k * span / max(1, n - 1)
        T.append(max(tk, T[-1] + 0.6))
    ent = min(ENTRADA, ini)
    saida = min(0.6, max(0.3, (fim - T[-1]) * 0.5))
    return T, ent, saida


def _tr(gap):
    """Duração da troca entre dois cartões (o giro rápido que traz o próximo para a frente)."""
    return min(0.8, 0.6 * gap)


def _pousar(v):
    """Curva da troca: arranca devagar e pousa na palavra (90% do caminho só ~0,1 s antes dela)."""
    return d.suave(d.limitar(v) ** 1.6)


def _derivas(T, fim, n, saida):
    """Giro lento de cada leitura (rad) e a duração dele. O cartão chega um pouco antes do centro e passa
    devagar por ele: fica centrado em média e os de lado ficam sempre perto do lugar de descanso."""
    passo = _passo(n)
    out = []
    for k in range(n):
        dur = (T[k + 1] - _tr(T[k + 1] - T[k]) - T[k]) if k < n - 1 else (fim - saida - T[-1])
        dur = max(0.0, dur)
        out.append((min(DERIVA_MAX * passo, DERIVA * dur), dur))
    return out


def _fase(t, T, fim, n, saida):
    """Ângulo da órbita: cada cartão k chega na frente (pi/2, com o giro lento) em T[k]."""
    passo = _passo(n)
    der = _derivas(T, fim, n, saida)
    S = [A0 + k * passo - 0.5 * der[k][0] for k in range(n)]
    if t < T[0]:
        ent = min(ENTRADA, T[0])
        u = d.mapear(t, T[0] - ent, T[0]) if ent > 0 else 1.0
        return S[0] - 0.9 * math.pi * (1 - _pousar(u))
    for k in range(n):
        dk, dur = der[k]
        taxa = dk / dur if dur > 1e-6 else 0.0
        if k < n - 1 and t < T[k + 1]:
            t_tr = T[k + 1] - _tr(T[k + 1] - T[k])
            p = S[k] + taxa * (t - T[k])                     # leitura: giro lento
            if t <= t_tr:
                return p
            return d.lerp(p, S[k + 1], _pousar(d.mapear(t, t_tr, T[k + 1])))
    p = S[-1] + taxa * (t - T[-1])
    w = d.mapear(t, fim - saida, fim)
    return p + 0.55 * math.pi * d.entrada(w)


def _movimento(t, T, fim, n, saida):
    """1 enquanto a órbita gira (entrada e trocas); 0 enquanto um cartão é lido e na saída
    (na saída, quem está escondido atrás da pessoa continua escondido)."""
    m = 1 - d.suave(d.mapear(t, T[0] - 0.25, T[0] + 0.05))
    for k in range(1, n):
        t_tr = T[k] - _tr(T[k] - T[k - 1])
        a = d.suave(d.mapear(t, t_tr, t_tr + 0.4 * (T[k] - t_tr)))
        b = 1 - d.suave(d.mapear(t, T[k] - 0.25, T[k] + 0.05))
        m = max(m, min(a, b))
    return m


def _oculto(c, caixa):
    """Fração da caixa do cartão coberta pela pessoa (máscara), medida em pixels reais."""
    m = c.mascara
    if m is None:
        return 0.0
    x0, y0, x1, y1 = (int(max(0, caixa[0])), int(max(0, caixa[1])),
                      int(min(c.W, caixa[2])), int(min(c.H, caixa[3])))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return 0.0
    a = np.asarray(m.crop((x0, y0, x1, y1)).reduce(4))
    if a.size == 0:
        return 0.0
    return float((a > 127).mean())


def _sentido(c, e):
    s = e.get("sentido")
    if s in (1, -1, "1", "-1"):
        return int(s)
    i = c.g.cache.get("orb_ordem", {}).get(round(float(e["inicio"]), 3), 0)
    return 1 if i % 2 == 0 else -1


def _dentro(x, lo, hi, macio):
    """Prende x entre lo e hi com uma curva macia (o cartão desacelera perto da borda, sem tranco)."""
    if hi <= lo:
        return (lo + hi) / 2
    macio = min(macio, (hi - lo) / 2)
    if x > hi - macio:
        return hi - macio + macio * math.tanh((x - (hi - macio)) / macio)
    if x < lo + macio:
        return lo + macio - macio * math.tanh(((lo + macio) - x) / macio)
    return x


def _folga(caixa, zona):
    """Distância (px) entre a caixa e a zona do rosto; negativa = encostando/por cima."""
    bx0, by0, bx1, by1 = caixa
    zx0, zy0, zx1, zy1 = zona
    return max(zy0 - by1, by0 - zy1, zx0 - bx1, bx0 - zx1)


# ---------------------------------------------------------------- anel

def _anel(c, geo, esc, a_anel, recorte):
    """Anel da órbita em máscaras de cinza super-amostradas (rápido).
    Devolve [("anel", (x, y), halo_L, linha_L), lado] para 'tras' e/ou 'frente'."""
    W, H = c.W, c.H
    rx, ry = geo["rx"] * esc, geo["ry"] * esc
    cx, cy = geo["cx"], geo["cy"]
    n = 128
    th = np.linspace(0, 2 * math.pi, n + 1)
    ca, sa = math.cos(INCLINACAO), math.sin(INCLINACAO)
    xs = cx + rx * np.cos(th) * ca - ry * np.sin(th) * sa
    ys = cy + rx * np.cos(th) * sa + ry * np.sin(th) * ca
    z = np.sin(th)
    zx0, zy0, zx1, zy1 = geo["zona"]
    fora = np.maximum.reduce([zx0 - xs, xs - zx1, zy0 - ys, ys - zy1])   # >0 = fora da zona do rosto
    k_rosto = np.clip(fora / (0.02 * H), 0, 1)
    lw_h, lw_c = max(2, int(W * 0.010)), max(1, int(W * 0.0042))
    pad = lw_h + 4
    S = 2
    segs = {"tras": [], "frente": []}
    for i in range(n):
        zm = (z[i] + z[i + 1]) / 2
        kr = min(k_rosto[i], k_rosto[i + 1])
        if recorte:
            # na frente só fora do rosto; o que encosta no rosto vai para trás (a cabeça cobre)
            lado = "frente" if zm > 0 and kr > 0.5 else "tras"
            a = a_anel * (0.75 if lado == "tras" else 1.0)
        else:
            lado = "frente"
            a = a_anel * kr * (0.55 if zm <= 0 else 1.0)
        if a > 0.01:
            segs[lado].append(((xs[i], ys[i]), (xs[i + 1], ys[i + 1]), a))
    out = []
    for lado in ("tras", "frente"):
        if not segs[lado]:
            continue
        px_ = [q for p0, p1, _a in segs[lado] for q in (p0[0], p1[0])]
        py_ = [q for p0, p1, _a in segs[lado] for q in (p0[1], p1[1])]
        bx0, by0 = int(min(px_) - pad), int(min(py_) - pad)       # caixa só desta metade do anel
        bx1, by1 = int(max(px_) + pad), int(max(py_) + pad)
        tam = ((bx1 - bx0) * S, (by1 - by0) * S)
        halo, linha = Image.new("L", tam, 0), Image.new("L", tam, 0)
        dh, dl = ImageDraw.Draw(halo), ImageDraw.Draw(linha)
        for p0, p1, a in segs[lado]:
            p0 = ((p0[0] - bx0) * S, (p0[1] - by0) * S)
            p1 = ((p1[0] - bx0) * S, (p1[1] - by0) * S)
            dh.line([p0, p1], fill=int(52 * a), width=lw_h * S)      # halo escuro (lê em fundo claro)
            dl.line([p0, p1], fill=int(210 * a), width=lw_c * S)     # linha clara
        out.append((("anel", (bx0, by0), halo.reduce(S), linha.reduce(S)), lado))
    return out


# ---------------------------------------------------------------- quadro

def _orbita(c, e, ops, recorte):
    W, H, t = c.W, c.H, c.t
    carts = _cartoes_do_evento(c, e)
    n = len(carts)
    if n == 0:
        return
    fim = float(e["fim"])
    T, ent, saida = _tempos(e, n)
    if t < T[0] - ent - 0.001 or t > fim:
        return
    lados = _modo_lados(c, e, carts, T, ent) if recorte and n >= 2 else None
    geo = _geometria(c, carts, recorte, lados)
    phi = _fase(t, T, fim, n, saida)
    passo = _passo(n)
    descanso = 1 - _movimento(t, T, fim, n, saida) if recorte else 0.0
    sent = _sentido(c, e)
    w_sai = d.mapear(t, fim - saida, fim)
    some = 1 - d.suave(w_sai)
    # anel
    u_ent = d.saida(d.mapear(t, T[0] - ent, T[0] - ent + 0.5)) if ent > 0.05 else 1.0
    a_anel = u_ent * some
    if not recorte:  # carrossel achatado (plano fechado): o anel vira um risco, então some
        a_anel *= d.limitar((geo["ry"] - 0.02 * H) / (0.03 * H))
    if a_anel > 0.01:
        for op, lado in _anel(c, geo, 0.82 + 0.18 * u_ent, a_anel, recorte):
            ops.append((lado, -2.0, op))
    ca, sa = math.cos(INCLINACAO), math.sin(INCLINACAO)
    for k, cart in enumerate(carts):
        if k == 0:
            pres = d.saida(d.mapear(t, T[0] - ent, T[0] - ent + 0.3)) if ent > 0.05 else 1.0
        else:
            ini_k = max(T[k - 1] + 0.1, T[k] - 1.7)
            pres = d.saida(d.mapear(t, ini_k, ini_k + 0.45))
        pres *= some
        if pres <= 0.004:
            continue
        th = phi - k * passo
        if sent < 0:
            th = math.pi - th
        ct, st = math.cos(th), math.sin(th)
        x = geo["cx"] + geo["rx"] * ct * ca - geo["ry"] * st * sa
        y = geo["cy"] + geo["rx"] * ct * sa + geo["ry"] * st * ca + d.ruido(t, 11 + k, 0.35) * 0.004 * H
        z = st
        sz = _escala_prof(z, geo["k_lados"][k], geo["z_lado"])
        y += (cart["h"] * geo["fits"][k] - geo["href"]) * sz / 2   # alinha pelo topo (cartão de 2 linhas desce)
        s = sz * geo["fits"][k] * (0.86 + 0.14 * pres) * (1 - 0.2 * w_sai)
        s = round(s * 200) / 200                                       # passos de 0,5% (reaproveita o cache)
        k_rot = d.limitar((TAM_ROTULO * s - LEGIVEL) / 0.0015)         # rótulo só quando legível
        k_barra = d.saida(d.mapear(t, T[k] - 0.05, T[k] + 0.4))        # barra cresce ao chegar na frente
        rot = -6.0 * ct
        rot = 0.0 if (z > 0.8 and abs(rot) < 1.5) else round(rot * 4) / 4   # passos de 0,25 grau
        hw, hh = cart["w"] * s / 2, cart["h"] * s / 2
        x = _dentro(x, 0.03 * W + hw, W - 0.03 * W - hw, 0.05 * W)   # nunca cortado pela borda
        if descanso > 0.01 and z < -0.05:
            # cartão parado atrás da pessoa: se ela cobre parte dele, ele some enquanto descansa
            # (nunca fica uma palavra pela metade na tela); a passagem por trás continua normal
            occ = _oculto(c, (x - hw, y - hh, x + hw, y + hh))
            pres *= 1 - descanso * d.suave(d.mapear(occ, 0.03, 0.15))
            if pres <= 0.004:
                continue
        folga = _folga((x - hw, y - hh, x + hw, y + hh), geo["zona"])
        # 1 = livre do rosto; cai para 0 só quando o cartão realmente encosta (troca rápida, sem cartão translúcido)
        k_rosto = d.suave(d.limitar((folga + 0.008 * H) / (0.012 * H)))
        dados = ("pronto", _transformado(c, cart, k_rot, k_barra, s, rot), (x, y), 1.0, 0.0)
        if recorte:
            f = d.suave(d.mapear(z, -0.02, 0.10)) * k_rosto
            if 0.001 < f < 0.999:   # cruzando para a frente: desenha atrás e na frente (transforma 1 vez só)
                ops.append(("tras", z, dados + (pres,)))
                ops.append(("frente", z, dados + (pres * f,)))
            elif f <= 0.001:
                ops.append(("tras", z, dados + (pres,)))
            else:
                ops.append(("frente", z, dados + (pres,)))
        else:
            # sem recorte nada passa atrás: os de trás quase somem (sem bagunça) e nada encosta no rosto
            a = pres * k_rosto * d.suave(d.mapear(z, -0.45, -0.02))
            if a > 0.004:
                ops.append(("frente", z, dados + (a,)))


def _caixa_op(op, W, H):
    if op[0] == "anel":
        _, (x, y), halo, _l = op
        return (x, y, x + halo.width, y + halo.height)
    _, img, (x, y), s, rot, _a = op
    w, h = img.width * s, img.height * s
    r = math.radians(abs(rot))
    w2 = w * math.cos(r) + h * math.sin(r)
    h2 = w * math.sin(r) + h * math.cos(r)
    return (x - w2 / 2 - 2, y - h2 / 2 - 2, x + w2 / 2 + 2, y + h2 / 2 + 2)


_TABELAS = {}


def _opacidade(img, a):
    """Multiplica o alfa (tabela pronta: rápido)."""
    q = int(round(a * 64))
    if q >= 64:
        return img
    tab = _TABELAS.get(q)
    if tab is None:
        tab = _TABELAS[q] = [int(v * q / 64) for v in range(256)]
    img.putalpha(img.getchannel("A").point(tab))   # 'img' já é uma cópia (nunca a imagem do cache)
    return img


def _transformar(cam, s, rot):
    """Escala + giro numa passada só. Quase reto: só redimensiona (nítido); girado: afim bilinear."""
    w, h = cam.size
    if abs(rot) < 0.35:
        if abs(s - 1) <= 0.003:
            return cam
        return cam.resize((max(1, int(round(w * s))), max(1, int(round(h * s)))),
                          Image.BICUBIC if s > 0.8 else Image.BILINEAR)
    r = math.radians(rot)
    cr, sr = math.cos(r), math.sin(r)
    w2 = int(abs(w * s * cr) + abs(h * s * sr)) + 2
    h2 = int(abs(w * s * sr) + abs(h * s * cr)) + 2
    a, b = cr / s, -sr / s
    dd, e = sr / s, cr / s
    ox, oy = w2 / 2, h2 / 2
    cc = w / 2 - a * ox - b * oy
    f = h / 2 - dd * ox - e * oy
    return cam.transform((w2, h2), Image.AFFINE, (a, b, cc, dd, e, f), resample=Image.BILINEAR)


_CACHE_TF_MAX = 48 * 1024 * 1024     # bytes de cartões já transformados guardados por processo


def _transformado(c, cart, k_rot, k_barra, s, rot):
    """Cartão já escalado e girado. Com rótulo/barra no estado final (o caso comum), guarda o resultado:
    escala e giro andam em passos pequenos, então quadros vizinhos reaproveitam a mesma imagem."""
    kr = 1 if k_rot >= 0.99 or cart["rotulo"] is None else (0 if k_rot <= 0.01 else None)
    kb = 1 if k_barra >= 0.99 else (0 if k_barra <= 0.01 else None)
    if kr is None or kb is None:
        return _transformar(_imagem_cartao(cart, k_rot, k_barra), s, rot)
    cache = c.g.cache.get("orb_tf")
    if cache is None:
        from collections import OrderedDict
        cache = c.g.cache["orb_tf"] = OrderedDict()
        c.g.cache["orb_tf_bytes"] = 0
    chave = (cart["id"], kr, kb, s, rot)
    im = cache.get(chave)
    if im is not None:
        cache.move_to_end(chave)
        return im
    im = _transformar(_imagem_cartao(cart, kr, kb), s, rot)
    cache[chave] = im
    c.g.cache["orb_tf_bytes"] += im.width * im.height * 4
    while c.g.cache["orb_tf_bytes"] > _CACHE_TF_MAX and len(cache) > 1:
        _k, velho = cache.popitem(last=False)
        c.g.cache["orb_tf_bytes"] -= velho.width * velho.height * 4
    return im


def _executar(img, op):
    if op[0] == "anel":
        _, (x, y), halo, linha = op
        caixa = (x, y, x + halo.width, y + halo.height)
        cx0, cy0 = max(0, x), max(0, y)
        cx1, cy1 = min(img.width, caixa[2]), min(img.height, caixa[3])
        if cx1 <= cx0 or cy1 <= cy0:
            return
        corte = (cx0 - x, cy0 - y, cx1 - x, cy1 - y)
        img.paste((16, 18, 20, 255), (cx0, cy0, cx1, cy1), halo.crop(corte))
        img.paste((255, 253, 246, 255), (cx0, cy0, cx1, cy1), linha.crop(corte))
        return
    _, cam, (x, y), s, rot, a = op
    if a <= 0.004 or s <= 0.01:
        return
    c2 = cam if op[0] == "pronto" else _transformar(cam, s, rot)
    if a < 0.995:
        c2 = _opacidade(c2 if c2 is not cam else cam.copy(), a)
    d.colar_em(img, c2, (x - c2.width / 2, y - c2.height / 2))


def _titulo(c, e, img, recorte):
    W, H, t = c.W, c.H, c.t
    k = e.env(t, 0.35, 0.3)
    if k <= 0:
        return
    cam, w, h = _titulo_img(c.g, str(e.get("texto", "")).strip() or " ")
    chave = ("orb_tit_pos", float(e["inicio"]), str(e.get("texto", "")))
    if chave not in c.g.cache:  # decide o lugar UMA vez por título (sem pulos)
        meio = (e["inicio"] + e["fim"]) / 2
        x0, y0, x1, y1 = c.g.rosto.em(meio)
        cabeca = c.g.rosto.topo_cabeca(meio)
        queixo = c.g.rosto.queixo(meio)
        lim_baixo = c.g.cache.get("orb_topo_legenda", 0.80 * H) - 0.015 * H
        if cabeca - 0.02 * H - h >= 0.115 * H:
            lugar, esc = "acima", 1.0
        elif lim_baixo - (queixo + 0.025 * H) >= h * 0.8:
            lugar, esc = "peito", min(1.0, (lim_baixo - queixo - 0.025 * H) / h)
        else:
            lugar, esc = "testa", d.limitar((y0 + 0.12 * (y1 - y0) - 0.12 * H) / h, 0.7, 1.0)
        c.g.cache[chave] = (lugar, esc)
    lugar, esc = c.g.cache[chave]
    x0, y0, x1, y1 = _rosto_suave(c)
    if lugar == "peito":   # entre o queixo e a legenda; se a pessoa descer, o título encolhe (nunca invade)
        topo = y1 + 0.08 * (y1 - y0) + 0.016 * H
        lim_baixo = c.g.cache.get("orb_topo_legenda", 0.80 * H) - 0.015 * H
        esc = d.limitar((lim_baixo - topo) / h, 0.7, esc)
        yc = min(topo + h * esc / 2, lim_baixo - h * esc / 2)
    else:
        yc = 0.12 * H + h * esc / 2
    entra = d.mola(d.mapear(t, e["inicio"], e["inicio"] + 0.42), 1.8)
    sai = d.mapear(t, e["fim"] - 0.3, e["fim"])
    yc += (1 - entra) * -0.025 * H - d.entrada(sai) * 0.02 * H
    rot = (1 - entra) * 4.0
    d.colar(img, cam, (0.47 * W, yc), escala=esc * (0.92 + 0.08 * entra), rotacao=rot, opacidade=k)


def quadro(c):
    orbs = [e for e in c.eventos if e.get("tipo") == "orbita"]
    tits = [e for e in c.eventos if e.get("tipo") == "titulo"]
    if not orbs and not tits:
        return c.fonte
    recorte = c.mascara is not None
    ops = []
    for e in orbs:
        _orbita(c, e, ops, recorte)
    img = c.fonte
    tras = sorted((o for o in ops if o[0] == "tras"), key=lambda o: o[1])
    frente = sorted((o for o in ops if o[0] == "frente"), key=lambda o: o[1])
    pessoa = None
    if recorte and tras:
        caixas = [_caixa_op(o[2], c.W, c.H) for o in tras]
        bx0 = max(0, int(min(b[0] for b in caixas)))
        by0 = max(0, int(min(b[1] for b in caixas)))
        bx1 = min(c.W, int(max(b[2] for b in caixas)) + 1)
        by1 = min(c.H, int(max(b[3] for b in caixas)) + 1)
        if bx1 - bx0 > 1 and by1 - by0 > 1:
            caixa = (bx0, by0, bx1, by1)
            pessoa = c.fonte.crop(caixa)              # guarda a pessoa ANTES de desenhar atrás dela
            pessoa.putalpha(c.mascara.crop(caixa))
    for o in tras:
        _executar(img, o[2])
    if pessoa is not None:
        img.alpha_composite(pessoa, (caixa[0], caixa[1]))
    for o in frente:
        _executar(img, o[2])
    for e in tits:
        _titulo(c, e, img, recorte)
    return img
