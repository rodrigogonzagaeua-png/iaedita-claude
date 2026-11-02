"""11 · Revelação para trás — a câmera recua e revela que o vídeo está dentro de uma janela de editor
(barra com três pontinhos, linha do tempo que vai enchendo, cartão com itens que ganham check e um
título em serifa acima da janela). Depois a câmera volta e o vídeo ocupa a tela de novo.
Aceita qualquer vídeo: não precisa recortar a pessoa.

Geometria: o "mundo" é o quadro já recuado (escala 1). A câmera é um zoom puro em torno do ponto fixo P,
escolhido de modo que, na escala 1/S, o retângulo do vídeo dentro da janela cubra a tela inteira — por
isso a entrada e a volta são contínuas com o vídeo original (sem salto)."""
from __future__ import annotations

import math
import re
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

from .. import desenho as d

INFO = {
    "id": "11-revelacao-para-tras",
    "nome": "Revelação para trás",
    "precisa_recorte": False,
    "antes": 0.05,
    "depois": 0.05,
    # perfil da ficha (o estilo desenha a própria legenda: caixa clara, texto escuro, faixa de marca-texto)
    "legenda": {"peso": 650, "tamanho": 0.062, "cor": "#222729", "destaque": "#D4ED80", "caixa": "#F8F7F0",
                "max_caracteres": 20, "max_linhas": 1, "animacao": "settle"},
    "legenda_propria": True,
    "eventos": {
        "revelacao": "inicio, fim (2,5-6 s): a câmera recua e mostra o vídeo dentro de uma janela de editor, "
                     "segura e volta. Campos opcionais: titulo (até 22 letras, em serifa acima da janela), "
                     "contar (true = o número do título conta de 0 até ele), janela (texto da barra da janela, "
                     "até 26 letras), lista (0-3 itens curtos, até 16 letras cada, que ganham check), "
                     "lista_titulo (título do cartão, até 14 letras), marcas (segundos em que cada item ganha "
                     "check — o momento em que a pessoa fala o item), volta ('suave' padrão = câmera volta | "
                     "'corte' = volta seca no fim), som (toca no recuo)",
    },
}

# ------------------------------------------------------------------ paleta (prévia aprovada / Scene11)
PAPEL_CENTRO, PAPEL_BORDA = "#FFFFFF", "#E4E4D6"
JANELA, JANELA_BORDA, BARRA_LINHA = "#FBFAF3", "#D8D8CC", "#DEDED1"
PONTOS = ("#E5B4A5", "#E2D295", "#A8BE9D")
TXT_BARRA = "#5A655C"
FUNDO_VIDEO = "#E4E0D5"
TRILHA, SEG_VAZIO, SEG_CHEIO = "#E9EBE1", "#C8CEC0", "#D4ED80"
LINHA_TRILHO, LINHA = "#D6D9CB", "#4B765D"
CARTAO, TINTA, ITEM, ARO, LIMA = "#FFFEF9", "#222729", "#34483C", "#82917B", "#D4ED80"
LEG_CAIXA = "#F8F7F0"  # opaca: com transparência a borda do vídeo "vaza" por trás da caixa na janela

# ------------------------------------------------------------------ layout do quadro recuado (frações)
S = 0.47                                  # escala do vídeo dentro da janela
JX0, JX1 = 0.115, 0.825                   # janela (W)
JY0 = 0.19                                # topo da janela (H)
BARRA = 0.042                             # altura da barra de título (H)
VX0 = 0.235                               # vídeo (W)
VY0 = JY0 + BARRA + 0.012                 # vídeo (H)
JY1 = 0.835                               # base da janela (H)
TL_Y0, TL_Y1 = 0.782, 0.806               # linha do tempo (H)
LN_Y = 0.8165                             # barra de progresso (H)
ROT_BASE = 0.176                          # linha de base do título em serifa (H)
LEG_CX = 0.47                             # centro horizontal da legenda (W) — deixa a direita livre
LEG_W = 0.76                              # largura da caixa da legenda (W)
LEG_REV_CY = 0.735                        # centro da legenda durante a revelação (H)
MARG = 0.035                              # sobra do mundo além da tela (para o leve recuo contínuo)
DERIVA = 0.03                             # a câmera continua recuando 3% enquanto segura (câmera viva)
R_VID = 0.022                             # raio dos cantos do vídeo (W)
N_SEG = 8


def _P(W, H):
    """Ponto fixo do zoom: na escala 1/S o retângulo do vídeo vira a tela inteira."""
    return (VX0 * W / (1 - S), VY0 * H / (1 - S))


# ------------------------------------------------------------------ curvas e tempos

def _tempos(e, duracao):
    t0, t1 = float(e["inicio"]), float(e["fim"])
    dur = max(0.3, t1 - t0)
    te = d.limitar(0.28 * dur, 0.55, 0.9)
    volta = str(e.get("volta", "suave"))
    if t1 >= duracao - 0.04:
        volta = "corte"  # termina com o vídeo: não há para onde voltar
    tr = d.limitar(0.22 * dur, 0.5, 0.8) if volta != "corte" else 0.0
    te = min(te, dur * 0.45)
    tr = min(tr, dur * 0.4)
    return t0, t1, te, tr


def _ease(k):
    """Movimento de câmera: arranca macio, ganha velocidade e assenta devagar (in-out assimétrico:
    aceleração curta até 38% do tempo + desaceleração longa, sem quebra de velocidade no meio)."""
    k = d.limitar(k)
    c = 0.38  # ponto de velocidade máxima
    if k < c:
        return c * (k / c) ** 2.5
    u = (k - c) / (1 - c)
    return c + (1 - c) * (1 - (1 - u) ** 2.5)  # mesma velocidade dos dois lados do ponto c


def _camera(e, t, duracao):
    """(k, A): k = 0 vídeo cheio … 1 recuado; A = escala da câmera sobre o mundo."""
    t0, t1, te, tr = _tempos(e, duracao)
    if t < t0 or t >= t1:
        return 0.0, 1.0 / S
    if t < t0 + te:
        k = _ease((t - t0) / te)
    elif tr > 0 and t >= t1 - tr:
        k = 1 - _ease((t - (t1 - tr)) / tr)
    else:
        k = 1.0
    a_seg = 1 - DERIVA * d.suave(d.mapear(t, t0 + te * 0.6, t1 - tr)) if t1 - tr > t0 + te else 1.0
    log_a = d.lerp(math.log(1 / S), math.log(a_seg), k)
    return k, math.exp(log_a)


def _ui_ab(e, t, duracao, atraso=0.5, entra=0.38, sai_ate=None):
    """(entrada, saída) 0-1 dos elementos da interface: entram quando a câmera já recuou, saem quando ela
    volta. Com sai_ate, a saída começa 0,15 s ANTES da volta e acaba em t1 - tr*sai_ate (sai antes de a
    câmera ampliar muito: nada de texto grande e apagado sobre o papel)."""
    t0, t1, te, tr = _tempos(e, duracao)
    a = d.saida(d.mapear(t, t0 + te * atraso, t0 + te * atraso + entra))
    if tr > 0:
        if sai_ate is None:
            b = 1 - d.suave(d.mapear(t, t1 - tr, t1 - tr * 0.45))
        else:
            b = 1 - d.suave(d.mapear(t, t1 - tr - 0.15, t1 - tr * sai_ate))
    else:
        b = 1.0 if t < t1 else 0.0
    return a, b


def _ui(e, t, duracao, atraso=0.5, entra=0.38, sai_ate=None):
    """Presença (0-1) dos elementos da interface."""
    return min(_ui_ab(e, t, duracao, atraso, entra, sai_ate))


def _janela_dos_checks(e, duracao):
    """Intervalo em que um check pode acontecer: cartão já na tela … antes de a câmera voltar."""
    t0, t1, te, tr = _tempos(e, duracao)
    ini_ok = t0 + te * 0.7 + 0.35
    return ini_ok, max(ini_ok + 0.1, t1 - tr - 0.25)


def _revelacoes(plano):
    return [e for e in plano["eventos"] if e.get("tipo") == "revelacao"]


def _chave(e):
    return (round(float(e["inicio"]), 3), round(float(e["fim"]), 3))


# ------------------------------------------------------------------ validação específica

def validar(plano, duracao):
    p = []
    rs = sorted(_revelacoes(plano), key=lambda e: e["inicio"])
    for a, b in zip(rs, rs[1:]):
        if b["inicio"] < a["fim"] - 0.01:
            p.append(f"Revelações sobrepostas em {b['inicio']:.2f}s: uma precisa terminar antes da outra começar.")
        elif b["inicio"] - a["fim"] < 1.2:
            p.append(f"Revelações coladas em {b['inicio']:.2f}s: deixe pelo menos 1,2 s de vídeo cheio entre elas.")
    for e in rs:
        dur = e["fim"] - e["inicio"]
        if dur < 2.0 and e["fim"] < duracao - 0.05:
            p.append(f"Revelação curta demais em {e['inicio']:.2f}s ({dur:.1f}s): use de 2,5 a 6 s.")
        no_fim = e["fim"] >= duracao - 0.05
        if dur > (9.0 if no_fim else 7.0):
            p.append(f"Revelação longa demais em {e['inicio']:.2f}s ({dur:.1f}s): no máximo ~6 s (8 s no fim do vídeo).")
        if str(e.get("volta", "suave")) not in ("suave", "corte"):
            p.append(f"'volta' em {e['inicio']:.2f}s precisa ser \"suave\" ou \"corte\".")
        tit = str(e.get("titulo", "") or "")
        if len(tit) > 22:
            p.append(f"Título longo demais em {e['inicio']:.2f}s (\"{tit}\"): até 22 letras.")
        jan = str(e.get("janela", "") or "")
        if len(jan) > 26:
            p.append(f"Texto da janela longo demais em {e['inicio']:.2f}s: até 26 letras.")
        lista = e.get("lista") or []
        if not isinstance(lista, list):
            p.append(f"'lista' em {e['inicio']:.2f}s precisa ser uma lista de textos.")
            lista = []
        if len(lista) > 3:
            p.append(f"Lista com {len(lista)} itens em {e['inicio']:.2f}s: no máximo 3.")
        for it in lista:
            if len(str(it)) > 16:
                p.append(f"Item longo demais em {e['inicio']:.2f}s (\"{it}\"): até 16 letras.")
        marcas = e.get("marcas")
        if marcas is not None:
            if not isinstance(marcas, list) or len(marcas) != len(lista):
                p.append(f"'marcas' em {e['inicio']:.2f}s precisa ter um tempo para cada item da lista.")
            else:
                ini_ok, fim_ok = _janela_dos_checks(e, duracao)
                for m in marcas:
                    m = float(m)
                    if m < ini_ok - 0.02:
                        p.append(f"Marca {m:.2f}s cedo demais: o cartão só está na tela a partir de {ini_ok:.2f}s. "
                                 f"Comece a revelação mais cedo (~1 s antes do 1º item) ou tire o item.")
                    elif m > fim_ok + 0.02:
                        p.append(f"Marca {m:.2f}s tarde demais: o último check precisa ser até {fim_ok:.2f}s "
                                 f"(depois a câmera volta). Aumente o 'fim' da revelação.")
        for txt in [tit, jan, str(e.get("lista_titulo", "") or "")] + [str(x) for x in lista]:
            low = txt.lower()
            if (re.search(r"\b\d{2}-[a-z]", low) or "revelacao" in low
                    or re.search(r"\.(mp4|mov|m4v|avi|json|png|jpe?g|txt|wav|mp3)\b|_|\bv\d+\b", low)):
                p.append(f"Texto interno na tela em {e['inicio']:.2f}s (\"{txt}\"): use só palavras da fala.")
    return p


# ------------------------------------------------------------------ peças desenhadas uma vez

def _fundo_papel(w, h, cx, cy, rx, ry):
    y, x = np.ogrid[0:h, 0:w]
    dd = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    k = np.clip(dd, 0, 1) ** 1.25
    a, b = np.array(d.cor(PAPEL_CENTRO)[:3], np.float32), np.array(d.cor(PAPEL_BORDA)[:3], np.float32)
    arr = a[None, None, :] * (1 - k[..., None]) + b[None, None, :] * k[..., None]
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def _mundo(g, janela_txt):
    """Fundo de papel + janela (sombra, barra, pontinhos, texto, trilho da linha do tempo) — RGB com sobra."""
    chave = ("e11mundo", janela_txt)
    if chave in g.cache:
        return g.cache[chave]
    W, H = g.W, g.H
    mx, my = int(round(W * MARG)), int(round(H * MARG))
    img = _fundo_papel(W + 2 * mx, H + 2 * my, mx + 0.5 * W, my + 0.45 * H, 0.8 * W, 0.62 * H).convert("RGBA")
    jx0, jx1, jy0, jy1 = JX0 * W, JX1 * W, JY0 * H, JY1 * H
    jw, jh = int(round(jx1 - jx0)), int(round(jy1 - jy0))
    raio = int(0.033 * W)
    pan = d.painel(jw, jh, raio, fundo=JANELA, borda=JANELA_BORDA, larg_borda=max(1, int(W * 0.0019)))
    dr = ImageDraw.Draw(pan)
    bh = BARRA * H
    dr.rectangle((int(W * 0.002), int(bh), jw - int(W * 0.002), int(bh + max(1, W * 0.0018))), fill=d.cor(BARRA_LINHA))
    dd = max(4, int(0.017 * W))
    for i, cc in enumerate(PONTOS):
        ponto = d.painel(dd, dd, dd // 2, fundo=cc)
        pan.alpha_composite(ponto, (int(0.034 * W + i * 0.027 * W), int(bh / 2 - dd / 2)))
    if janela_txt:
        f = d.fonte(int(0.038 * W), 600)
        larg_max = jw - 0.034 * W - 3 * 0.027 * W - 0.05 * W
        txt = janela_txt
        while f.getlength(txt) > larg_max and len(txt) > 4:
            txt = txt[:-2].rstrip() + "…"
        d.escrever(pan, (0.034 * W + 3 * 0.027 * W + 0.022 * W, bh / 2), [txt], f, TXT_BARRA, ancora_y="centro",
                   al=f.size * 1.0)
    # área do vídeo (por baixo; aparece só nos cantos arredondados)
    vx, vy = VX0 * W - jx0, VY0 * H - jy0
    pan.alpha_composite(d.painel(int(S * W), int(S * H), int(R_VID * W), fundo=FUNDO_VIDEO), (int(vx), int(vy)))
    # trilho da linha do tempo e da barra de progresso
    tx0, tx1 = (JX0 + 0.04) * W - jx0, (JX1 - 0.04) * W - jx0
    trilho = d.painel(int(tx1 - tx0), int((TL_Y1 - TL_Y0) * H + 0.012 * W), int(0.009 * W), fundo=TRILHA)
    pan.alpha_composite(trilho, (int(tx0), int(TL_Y0 * H - jy0 - 0.006 * W)))
    lh = max(2, int(0.0026 * H))
    dr.rectangle((int(tx0), int(LN_Y * H - jy0), int(tx1), int(LN_Y * H - jy0) + lh - 1), fill=d.cor(LINHA_TRILHO))
    som, (dx, dy) = d.sombra(pan, raio=0.024 * W, opacidade=0.16, desloc=(0, 0.013 * W))
    papel = img.crop((mx, my, mx + W, my + H)).convert("RGB")   # só o papel, na posição da escala 1
    ox, oy = int(mx + jx0 + dx), int(my + jy0 + dy)
    img.alpha_composite(som, (ox, oy))
    out = img.convert("RGB")
    # retângulo (no mundo) que contém janela + sombra: fora dele só há papel liso
    g.cache[chave] = (out, mx, my, papel, (ox, oy, ox + som.width, oy + som.height))
    return g.cache[chave]


def _faixas(base, mundo, mx, my, A, P, regiao, buraco):
    """Pinta em base a parte 'regiao' (tela) vista pela câmera, menos o 'buraco' (onde o vídeo vai)."""
    W, H = base.size
    rx0, ry0, rx1, ry1 = regiao
    hx0, hy0, hx1, hy1 = buraco
    hx0, hy0 = max(rx0, hx0), max(ry0, hy0)
    hx1, hy1 = min(rx1, hx1), min(ry1, hy1)
    if hx1 <= hx0 or hy1 <= hy0:
        hx0 = hx1 = rx0
        hy0 = hy1 = ry0
    for (a0, b0, a1, b1) in ((rx0, ry0, rx1, hy0), (rx0, hy1, rx1, ry1), (rx0, hy0, hx0, hy1), (hx1, hy0, rx1, hy1)):
        if a1 - a0 < 1 or b1 - b0 < 1:
            continue
        caixa = (P[0] + (a0 - P[0]) / A + mx, P[1] + (b0 - P[1]) / A + my,
                 P[0] + (a1 - P[0]) / A + mx, P[1] + (b1 - P[1]) / A + my)
        caixa = (max(0.0, caixa[0]), max(0.0, caixa[1]), min(float(mundo.width), caixa[2]),
                 min(float(mundo.height), caixa[3]))
        if caixa[2] - caixa[0] < 0.5 or caixa[3] - caixa[1] < 0.5:
            continue
        base.paste(mundo.resize((a1 - a0, b1 - b0), Image.BILINEAR, box=caixa), (a0, b0))


def _segmentos(g, n):
    """Linha do tempo com n de 8 blocos acesos (camada RGBA no tamanho do mundo)."""
    chave = ("e11seg", n)
    if chave in g.cache:
        return g.cache[chave]
    W, H = g.W, g.H
    tx0, tx1 = (JX0 + 0.04) * W, (JX1 - 0.04) * W
    vao = 0.009 * W
    sw = (tx1 - tx0 - vao * (N_SEG - 1)) / N_SEG
    sh = (TL_Y1 - TL_Y0) * H
    cam = Image.new("RGBA", (int(tx1 - tx0) + 2, int(sh) + 2), (0, 0, 0, 0))
    for i in range(N_SEG):
        bloco = d.painel(int(sw), int(sh), int(0.006 * W), fundo=SEG_CHEIO if i < n else SEG_VAZIO)
        cam.alpha_composite(bloco, (int(i * (sw + vao)), 0))
    g.cache[chave] = (cam, tx0, TL_Y0 * H)
    return g.cache[chave]


@lru_cache(maxsize=64)
def _canto(r, cor_hex):
    """Quadradinho r×r na cor da janela com um quarto de círculo vazado (arredonda o canto do vídeo)."""
    r = max(1, int(r))
    ss = 4
    m = Image.new("L", (r * ss, r * ss), 255)
    ImageDraw.Draw(m).pieslice((0, 0, 2 * r * ss - 1, 2 * r * ss - 1), 180, 270, fill=0)
    m = m.resize((r, r), Image.LANCZOS)
    c = Image.new("RGBA", (r, r), d.cor(cor_hex))
    c.putalpha(m)
    return {"se": c, "sd": c.transpose(Image.FLIP_LEFT_RIGHT), "id": c.transpose(Image.FLIP_TOP_BOTTOM),
            "ie": c.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM)}


# ------------------------------------------------------------------ rosto no quadro recuado

def _rosto_recuado(g, t0, t1):
    """União do rosto (com cabelo e queixo) durante o evento, já nas coordenadas do quadro recuado."""
    chave = ("e11rosto", round(t0, 3), round(t1, 3))
    if chave not in g.cache:
        g.cache[chave] = _rosto_recuado_calc(g, t0, t1)
    return g.cache[chave]


def _rosto_recuado_calc(g, t0, t1):
    ts = np.arange(t0, t1 + 1e-6, 0.2) if t1 > t0 else np.array([t0])
    caixas = np.array([g.rosto.em(float(t)) for t in ts])
    topo = min(g.rosto.topo_cabeca(float(t)) for t in ts)
    queixo = max(g.rosto.queixo(float(t)) for t in ts)
    W, H = g.W, g.H

    def X(x):
        return VX0 * W + S * x

    def Y(y):
        return VY0 * H + S * y
    return (X(caixas[:, 0].min()), Y(topo), X(caixas[:, 2].max()), Y(queixo))


def _leg_topo(g, e):
    """True quando, nesta revelação, a legenda vai para o TOPO da tela (y = 0,115 H) em vez da base do
    vídeo na janela: o queixo recuado desce até a faixa da legenda, ou a legenda normal já está acima da
    cabeça (assim ela desliza uma distância curta e nunca atravessa o rosto). Nesse caso o título some."""
    leg = _leg(g)
    if leg is None:
        return False
    chave = ("e11legtopo", _chave(e))
    if chave not in g.cache:
        H = g.H
        t0, t1 = float(e["inicio"]), float(e["fim"])
        rosto = _rosto_recuado(g, t0, t1)
        y_rev = LEG_REV_CY * H - leg.bh / 2
        g.cache[chave] = bool(rosto[3] + 0.012 * H > y_rev or leg.y_normal(t0) < 0.5 * H)
    return g.cache[chave]


# ------------------------------------------------------------------ cartão com lista

def _cartao(g, e):
    """Cartão 'lista' pré-desenhado + onde ele fica (sem tocar no rosto). None se não couber."""
    chave = ("e11cart", _chave(e))
    if chave in g.cache:
        return g.cache[chave]
    W, H = g.W, g.H
    itens = [str(x).strip() for x in (e.get("lista") or [])][:3]
    itens = [x for x in itens if x]
    if not itens:
        g.cache[chave] = None
        return None
    cab = str(e.get("lista_titulo", "") or "").strip()
    rosto = _rosto_recuado(g, float(e["inicio"]), float(e["fim"]))
    if _leg_topo(g, e):
        # legenda no topo e sem título: o cartão fica abaixo dela e acima da zona segura da base
        y_min = 0.115 * H + _Legenda.altura_caixa(W) + 0.015 * H
        y_max = 0.79 * H
    else:
        tem_titulo = bool(str(e.get("titulo", "") or "").strip())
        y_min = (ROT_BASE + 0.012) * H if tem_titulo else 0.12 * H
        y_max = (LEG_REV_CY * H - _Legenda.altura_caixa(W) / 2) - 0.012 * H
    x0 = 0.045 * W
    escolha = None
    for usar_cab, f_item in ((bool(cab), 0.041), (False, 0.041), (False, 0.037)):
        fi = d.fonte(int(f_item * W), 600)
        fc = d.fonte(int(0.044 * W), 800)
        pad = 0.032 * W
        diam = 0.044 * W
        linha = f_item * W * 1.72
        larg_txt = max(fi.getlength(x) for x in itens)
        if usar_cab:
            larg_txt = max(larg_txt, fc.getlength(cab) - diam - 0.022 * W)
        cw = d.limitar(pad * 2 + diam + 0.022 * W + larg_txt, 0.30 * W, 0.47 * W)
        ch = pad * 2 + (fc.size * 1.5 if usar_cab else 0) + len(itens) * linha - (linha - diam)
        # faixas livres: acima do cabelo e abaixo do queixo (ou qualquer altura se o cartão não chega ao rosto)
        margem = 0.016 * H
        if x0 + cw < rosto[0] - 0.02 * W:
            faixas = [(y_min, y_max)]
        else:
            faixas = [(rosto[3] + margem, y_max), (y_min, rosto[1] - margem)]
        for (a, b) in faixas:
            if b - a >= ch:
                y = a + (b - a - ch) * (0.3 if len(faixas) > 1 else 0.55)
                escolha = (usar_cab, fi, fc, pad, diam, linha, cw, ch, y)
                break
        if escolha:
            break
    if not escolha:
        g.cache[chave] = None
        return None
    usar_cab, fi, fc, pad, diam, linha, cw, ch, y = escolha
    base = d.painel(int(cw), int(ch), int(0.023 * W), fundo=CARTAO, borda="#E6E4D8", larg_borda=max(1, int(W * 0.0012)))
    yy = pad
    if usar_cab:
        d.escrever(base, (pad, yy - fc.size * 0.05), [cab], fc, TINTA)
        yy += fc.size * 1.5
    aro = d.painel(int(diam), int(diam), int(diam / 2), fundo=(0, 0, 0, 0), borda=ARO,
                   larg_borda=max(2, int(W * 0.0036)))
    centros = []
    for i, it in enumerate(itens):
        cy = yy + i * linha + diam / 2
        base.alpha_composite(aro, (int(pad), int(cy - diam / 2)))
        f = fi
        while f.getlength(it) > cw - pad * 2 - diam - 0.022 * W and f.size > int(0.036 * W):
            f = d.fonte(int(f.size * 0.95), 600)
        d.escrever(base, (pad + diam + 0.022 * W, cy), [it], f, ITEM, ancora_y="centro", al=f.size * 1.0)
        centros.append((pad + diam / 2, cy))
    som, (dx, dy) = d.sombra(base, raio=0.02 * W, opacidade=0.17, desloc=(0, 0.011 * W))
    # selo do check (círculo lima com check escuro)
    selo = d.painel(int(diam), int(diam), int(diam / 2), fundo=LIMA)
    ic = d.icone("check", int(diam * 0.78), TINTA, espessura=0.13)
    selo.alpha_composite(ic, (int((diam - ic.width) / 2), int((diam - ic.height) / 2 + diam * 0.02)))
    # quando cada item ganha check
    ini_ok, fim_ok = _janela_dos_checks(e, g.duracao)
    marcas = e.get("marcas")
    if isinstance(marcas, list) and len(marcas) == len(itens):
        ts = [d.limitar(float(m), ini_ok, fim_ok) for m in marcas]
    else:
        n = len(itens)
        ts = [ini_ok + (i + 0.5) * (fim_ok - ini_ok) / n for i in range(n)]
    g.cache[chave] = {"img": som, "dx": dx, "dy": dy, "x": x0, "y": y, "centros": centros, "selo": selo,
                      "marcas": ts, "w": cw, "h": ch}
    return g.cache[chave]


# ------------------------------------------------------------------ título em serifa (com contagem)

_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def _numero(txt):
    m = _NUM.search(txt)
    if not m:
        return None
    s = m.group(0)
    milhar = bool(re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s))
    if milhar:
        v, casas = float(s.replace(".", "")), 0
    elif "," in s:
        v, casas = float(s.replace(".", "").replace(",", ".")), len(s.split(",")[-1])
    else:
        v, casas = float(s), 0
    return m.start(), m.end(), v, casas, milhar


def _formatar(v, casas, milhar):
    if casas:
        return f"{v:.{casas}f}".replace(".", ",")
    n = int(round(v))
    return f"{n:,}".replace(",", ".") if milhar else str(n)


def _fonte_titulo(g, titulo):
    chave = ("e11ftit", titulo)
    if chave not in g.cache:
        W, H = g.W, g.H
        f, _, _ = d.ajustar_texto(titulo, (JX1 - JX0) * W, 0.075 * H, peso=600, familia="serif",
                                  tam_max=int(0.13 * W), tam_min=int(0.062 * W), max_linhas=1, entrelinha=1.0)
        g.cache[chave] = f
    return g.cache[chave]


def _rotulo(g, titulo, texto):
    chave = ("e11rot", titulo, texto)
    if chave in g.cache:
        return g.cache[chave]
    f = _fonte_titulo(g, titulo)
    x0, y0, x1, y1 = f.getbbox(texto, anchor="ls")
    pad = int(f.size * 0.15)
    cam = Image.new("RGBA", (int(x1 - min(0, x0)) + pad * 2, int(y1 - y0) + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(cam).text((pad - min(0, x0), pad - y0), texto, font=f, fill=d.cor(TINTA), anchor="ls")
    # (camada, linha de base dentro dela, onde a primeira letra começa dentro dela)
    g.cache[chave] = (cam, pad - y0, pad - min(0, x0) + x0)
    return g.cache[chave]


def _texto_titulo(g, e, t):
    titulo = str(e.get("titulo", "") or "").strip()
    if not titulo or not e.get("contar"):
        return titulo
    num = _numero(titulo)
    if not num:
        return titulo
    a, b, v, casas, milhar = num
    t0, t1, te, tr = _tempos(e, g.duracao)
    ini = t0 + te * 0.5
    dur = min(1.3, max(0.5, (t1 - tr - ini) * 0.45))
    k = d.saida(d.mapear(t, ini, ini + dur))
    return titulo[:a] + _formatar(v * k, casas, milhar) + titulo[b:]


# ------------------------------------------------------------------ legenda própria (faixa de marca-texto)

def _paginas(palavras, max_pal=4, max_car=20, pausa=0.45):
    pags, atual = [], []
    for p in palavras:
        if atual:
            txt = " ".join(x["texto"] for x in atual + [p])
            gap = p["inicio"] - atual[-1]["fim"]
            ult = atual[-1]["texto"]
            if (len(atual) >= max_pal or len(txt) > max_car or gap > pausa or ult[-1:] in ".!?"
                    or (ult[-1:] in ",;:" and len(" ".join(x["texto"] for x in atual)) >= 8)):
                pags.append(atual)
                atual = []
        atual.append(p)
    if atual:
        pags.append(atual)
    out = []
    for i, pg in enumerate(pags):
        prox = pags[i + 1][0]["inicio"] if i + 1 < len(pags) else pg[-1]["fim"] + 0.8
        out.append({"palavras": pg, "inicio": pg[0]["inicio"], "fim": min(prox, pg[-1]["fim"] + 0.6)})
    return out


class _Legenda:
    """Caixa clara de largura fixa, texto escuro alinhado à esquerda; a palavra falada ganha uma faixa
    verde-limão de marca-texto por trás (como na prévia). Fora da revelação fica abaixo do queixo
    (ou acima da cabeça); na revelação fica na base do vídeo dentro da janela."""

    @staticmethod
    def altura_caixa(W):
        return int(W * 0.062 * 1.3 + 2 * 0.03 * W)

    def __init__(self, g):
        self.g, self.W, self.H = g, g.W, g.H
        self.pags = _paginas(g.palavras or [])
        self.fs = int(self.W * 0.062)
        self.bw, self.bh = int(LEG_W * self.W), self.altura_caixa(self.W)
        self.pad = 0.04 * self.W
        cx = d.painel(self.bw, self.bh, int(0.014 * self.W), fundo=LEG_CAIXA)
        self.caixa, (self.cdx, self.cdy) = d.sombra(cx, raio=0.012 * self.W, opacidade=0.10, desloc=(0, 0.005 * self.W))
        self._med = {}

    def pagina(self, t):
        for i, pg in enumerate(self.pags):
            if pg["inicio"] - 0.05 <= t < pg["fim"]:
                return i
        return None

    def _medidas(self, i):
        if i in self._med:
            return self._med[i]
        pg = self.pags[i]
        txts = [w["texto"] for w in pg["palavras"]]
        f = d.fonte(self.fs, 650)
        util = self.bw - 2 * self.pad
        while True:
            esp = f.getlength(" ")
            ws = [f.getlength(x) for x in txts]
            total = sum(ws) + esp * (len(txts) - 1)
            if total <= util or f.size <= int(self.W * 0.048):
                break
            f = d.fonte(int(f.size * 0.94), 650)
        xs, x = [], self.pad
        for wv in ws:
            xs.append(x)
            x += wv + esp
        cap = -f.getbbox("H", anchor="ls")[1]
        base = self.bh / 2 + cap / 2
        cam = Image.new("RGBA", (self.bw, self.bh), (0, 0, 0, 0))
        dr = ImageDraw.Draw(cam)
        for j, tx in enumerate(txts):
            dr.text((xs[j], base), tx, font=f, fill=d.cor(TINTA), anchor="ls")
        self._med[i] = (f, xs, ws, base, cam)
        return self._med[i]

    def y_normal(self, t):
        """Topo da caixa fora da revelação: abaixo do queixo; se não couber, acima da cabeça."""
        H, alt = self.H, self.bh
        cab, qx = self.g.rosto.topo_cabeca(t), self.g.rosto.queixo(t)
        if qx + 0.02 * H + alt <= 0.80 * H:
            return max(qx + 0.03 * H, 0.62 * H)
        if cab - 0.02 * H - alt >= 0.11 * H:
            return cab - 0.025 * H - alt
        return 0.80 * H - alt

    def desenhar(self, img, t, cx, y_topo, opac=1.0):
        i = self.pagina(t)
        if i is None or opac <= 0.01:
            return
        pg = self.pags[i]
        f, xs, ws, base, txt = self._medidas(i)
        # entrada "settle": sobe 0,8% e assenta; a caixa só pisca quando a fala recomeça depois de uma pausa
        k_in = d.saida(d.mapear(t, pg["inicio"] - 0.05, pg["inicio"] + 0.16))
        anterior = self.pags[i - 1] if i > 0 else None
        continua = anterior is not None and pg["inicio"] - anterior["fim"] < 0.12
        prox = self.pags[i + 1] if i + 1 < len(self.pags) else None
        segue = prox is not None and prox["inicio"] - pg["fim"] < 0.12
        k_out = 1.0 if segue else 1 - d.suave(d.mapear(t, pg["fim"] - 0.12, pg["fim"]))
        op_caixa = opac * min(1.0 if continua else k_in, k_out)
        cam = self.caixa.copy()
        ox, oy = -self.cdx, -self.cdy
        # faixa de marca-texto atrás da palavra falada
        for j, w in enumerate(pg["palavras"]):
            ini, fim = w["inicio"] - 0.03, max(w["fim"], w["inicio"] + 0.14)
            cresce = d.saida(d.mapear(t, ini, ini + 0.14))
            some = 1 - d.suave(d.mapear(t, fim, fim + 0.1))
            k = min(cresce, some) if t >= ini else 0.0
            if k <= 0.01:
                continue
            hx = f.size * 0.07
            fw = (ws[j] + 2 * hx) * (cresce if t < ini + 0.14 else 1.0)
            fh = f.size * 0.56
            if fw < 2:
                continue
            faixa = d.painel(int(fw), int(fh), int(f.size * 0.1), fundo=d.cor(LIMA, some))
            cam.alpha_composite(faixa, (int(ox + xs[j] - hx), int(oy + base - f.size * 0.42)))
        dy_txt = (1 - k_in) * 0.006 * self.H
        tl = txt
        if k_in < 0.999:
            tl = txt.copy()
            tl.putalpha(tl.getchannel("A").point(lambda v: int(v * (0.35 + 0.65 * k_in))))
        cam.alpha_composite(tl, (int(ox), int(oy + dy_txt)))
        if op_caixa < 0.997:
            cam.putalpha(cam.getchannel("A").point(lambda v: int(v * op_caixa)))
        x = int(round(cx * self.W - self.bw / 2 + self.cdx))
        y = int(round(y_topo + self.cdy + (1 - k_in) * 0.004 * self.H * (0 if continua else 1)))
        if img.mode == "RGBA":
            d.colar_em(img, cam, (x, y))
        else:
            _colar_rgb(img, cam, x, y)


# ------------------------------------------------------------------ composição

def _colar_rgb(base, cam, x, y):
    W, H = base.size
    if x >= W or y >= H or x + cam.width <= 0 or y + cam.height <= 0:
        return
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(cam.width, W - x), min(cam.height, H - y)
    peca = cam.crop((cx0, cy0, cx1, cy1))
    base.paste(peca, (x + cx0, y + cy0), peca)


def _pintar(base, cam, wx, wy, A, P, opac=1.0):
    """Cola a camada RGBA que está em (wx, wy) no mundo, vista pela câmera (escala A em torno de P)."""
    if opac <= 0.003:
        return
    W, H = base.size
    sx, sy = P[0] + A * (wx - P[0]), P[1] + A * (wy - P[1])
    sw, sh = cam.width * A, cam.height * A
    x0, y0 = max(0.0, sx), max(0.0, sy)
    x1, y1 = min(float(W), sx + sw), min(float(H), sy + sh)
    if x1 - x0 < 1 or y1 - y0 < 1:
        return
    ix0, iy0 = int(math.floor(x0)), int(math.floor(y0))
    ix1, iy1 = int(math.ceil(x1)), int(math.ceil(y1))
    if abs(A - 1) < 1e-4:
        peca = cam.crop((ix0 - int(round(sx)), iy0 - int(round(sy)), ix1 - int(round(sx)), iy1 - int(round(sy))))
    else:
        caixa = (max(0.0, (ix0 - sx) / A), max(0.0, (iy0 - sy) / A),
                 min(float(cam.width), (ix1 - sx) / A), min(float(cam.height), (iy1 - sy) / A))
        if caixa[2] - caixa[0] < 0.5 or caixa[3] - caixa[1] < 0.5:
            return
        peca = cam.resize((ix1 - ix0, iy1 - iy0), Image.BILINEAR, box=caixa)
    if opac < 0.997:
        peca = peca.copy() if peca is cam else peca
        peca.putalpha(peca.getchannel("A").point(lambda v: int(v * opac)))
    base.paste(peca, (ix0, iy0), peca)


def _ativa(c):
    """A revelação que está acontecendo agora (com k > 0)."""
    for e in c.eventos:
        if e.get("tipo") == "revelacao" and e["inicio"] <= c.t < e["fim"]:
            return e
    return None


def _leg(g):
    if "e11leg" not in g.cache:
        g.cache["e11leg"] = _Legenda(g) if g.plano.get("legenda", {}).get("ativa", True) and g.palavras else None
    return g.cache["e11leg"]


def preparar(g):
    _leg(g)
    for e in _revelacoes(g.plano):
        _mundo(g, str(e.get("janela", "") or "").strip())
        _cartao(g, e)
        tit = str(e.get("titulo", "") or "").strip()
        if tit:
            _rotulo(g, tit, tit)
    for n in range(N_SEG + 1):
        _segmentos(g, n)


def quadro(c):
    g, W, H, t = c.g, c.W, c.H, c.t
    leg = _leg(g)
    e = _ativa(c)
    k, A = _camera(e, t, g.duracao) if e is not None else (0.0, 1 / S)
    if e is None or k <= 1e-4:
        img = c.fonte.copy()
        if leg:
            leg.desenhar(img, t, LEG_CX, leg.y_normal(t))
        return img

    P = _P(W, H)
    janela_txt = str(e.get("janela", "") or "").strip()
    mundo, mx, my, papel, jrect = _mundo(g, janela_txt)
    f = A * S
    sx0, sy0 = P[0] + A * (VX0 * W - P[0]), P[1] + A * (VY0 * H - P[1])
    sx1, sy1 = sx0 + f * W, sy0 + f * H
    ix0, iy0 = int(math.floor(max(0.0, sx0))), int(math.floor(max(0.0, sy0)))
    ix1, iy1 = int(math.ceil(min(float(W), sx1))), int(math.ceil(min(float(H), sy1)))
    buraco = (ix0 + 1, iy0 + 1, ix1 - 1, iy1 - 1)

    # 1) mundo (papel + janela) visto pela câmera — só o que o vídeo não cobre
    if abs(A - 1) < 1e-4:
        base = mundo.crop((mx, my, mx + W, my + H))
    elif A < 1.0:
        # segurando (leve recuo contínuo ≤ 3%): o papel liso fica parado; só a janela é reamostrada
        base = papel.copy()
        jx0 = int(math.floor(max(0.0, P[0] + A * (jrect[0] - mx - P[0]))))
        jy0 = int(math.floor(max(0.0, P[1] + A * (jrect[1] - my - P[1]))))
        jx1 = int(math.ceil(min(float(W), P[0] + A * (jrect[2] - mx - P[0]))))
        jy1 = int(math.ceil(min(float(H), P[1] + A * (jrect[3] - my - P[1]))))
        _faixas(base, mundo, mx, my, A, P, (jx0, jy0, jx1, jy1), buraco)
    else:
        base = Image.new("RGB", (W, H), d.cor(JANELA)[:3])
        _faixas(base, mundo, mx, my, A, P, (0, 0, W, H), buraco)

    # 2) o vídeo dentro da janela
    if ix1 - ix0 >= 2 and iy1 - iy0 >= 2:
        cx = (max(0.0, (ix0 - sx0) / f), max(0.0, (iy0 - sy0) / f),
              min(float(W), (ix1 - sx0) / f), min(float(H), (iy1 - sy0) / f))
        if (ix1 - ix0, iy1 - iy0) == (W, H) and abs(f - 1) < 1e-4:
            vid = c.fonte.convert("RGB")
        else:
            # Converte para RGB antes de reamostrar (resize em RGBA é ~2,5x mais lento no Pillow, que
            # pré-multiplica o alfa). Quando só um pedaço do vídeo aparece (início do recuo / fim da volta),
            # recorta esse pedaço antes de converter, para não converter o quadro inteiro.
            bx0, by0 = max(0, int(math.floor(cx[0])) - 1), max(0, int(math.floor(cx[1])) - 1)
            bx1, by1 = min(W, int(math.ceil(cx[2])) + 1), min(H, int(math.ceil(cx[3])) + 1)
            if (bx1 - bx0) * (by1 - by0) < 0.7 * W * H:
                src = c.fonte.crop((bx0, by0, bx1, by1)).convert("RGB")
                cx = (cx[0] - bx0, cx[1] - by0, cx[2] - bx0, cx[3] - by0)
            else:
                src = c.fonte.convert("RGB")
            # reducing_gap: redução inteira rápida (média de blocos) antes do ajuste fino (~40% mais rápido)
            vid = src.resize((ix1 - ix0, iy1 - iy0), Image.BILINEAR, box=cx, reducing_gap=1.05)
        base.paste(vid, (ix0, iy0))
        # cantos arredondados (aparecem aos poucos para a entrada ser contínua)
        r = int(round(R_VID * W * A * d.suave(d.mapear(k, 0.0, 0.45))))
        if r >= 2:
            cs = _canto(r, JANELA)
            for nome, (px, py) in (("se", (sx0, sy0)), ("sd", (sx1 - r, sy0)),
                                   ("id", (sx0, sy1 - r)), ("ie", (sx1 - r, sy1 - r))):
                _colar_rgb(base, cs[nome], int(round(px)), int(round(py)))

    # 3) linha do tempo que vai enchendo + barra de progresso
    t0, t1, te, tr = _tempos(e, g.duracao)
    prog = d.mapear(t, t0 + te * 0.5, max(t0 + te * 0.5 + 0.1, t1 - tr - 0.1))
    n = min(N_SEG, int(prog * N_SEG + 1e-6))
    seg, swx, swy = _segmentos(g, n)
    _pintar(base, seg, swx, swy, A, P)
    if prog > 0:
        lx0, lx1 = (JX0 + 0.04) * W, (JX0 + 0.04) * W + ((JX1 - JX0) - 0.08) * W * prog
        ly0, ly1 = LN_Y * H, LN_Y * H + max(2, 0.0026 * H)
        X0, X1 = P[0] + A * (lx0 - P[0]), P[0] + A * (lx1 - P[0])
        Y0, Y1 = P[1] + A * (ly0 - P[1]), P[1] + A * (ly1 - P[1])
        if X1 > 0 and X0 < W and Y1 > 0 and Y0 < H:
            ImageDraw.Draw(base).rectangle((int(X0), int(Y0), int(X1), max(int(Y0) + 1, int(Y1) - 1)), fill=d.cor(LINHA)[:3])

    # 4) título em serifa acima da janela (sobe e aparece)
    leg_y_rev = LEG_REV_CY * H - (leg.bh / 2 if leg else 0)
    leg_no_topo = _leg_topo(g, e)
    titulo = str(e.get("titulo", "") or "").strip()
    if titulo and not leg_no_topo:
        u = _ui(e, t, g.duracao, atraso=0.5, entra=0.42, sai_ate=0.78)
        if u > 0.003:
            txt = _texto_titulo(g, e, t)
            cam, base_y, x_letra = _rotulo(g, titulo, txt)
            dy = (1 - u) * 0.022 * H
            # a primeira letra alinha com a borda esquerda da janela
            _pintar(base, cam, JX0 * W + 0.004 * W - x_letra, ROT_BASE * H - base_y + dy, A, P, opac=u)

    # 5) cartão com a lista (entra deslizando da esquerda; checks nos tempos da fala)
    cart = _cartao(g, e)
    if cart:
        # sai ANTES de a câmera ampliar (sem restos de texto grandes e apagados sobre o papel)
        ua, ub = _ui_ab(e, t, g.duracao, atraso=0.68, entra=0.45, sai_ate=0.78)
        u = min(ua, ub)
        if u > 0.003:
            cam = cart["img"]
            if any(t >= tm for tm in cart["marcas"]):
                cam = cam.copy()
                for (cxp, cyp), tm in zip(cart["centros"], cart["marcas"]):
                    if t >= tm:
                        kk = d.mola(d.mapear(t, tm, tm + 0.22), 1.8)
                        d.colar(cam, cart["selo"], (cxp - cart["dx"], cyp - cart["dy"]), escala=0.55 + 0.45 * kk)
            dx = -(1 - d.mola(u, 0.9)) * 0.09 * W
            _pintar(base, cam, cart["x"] + cart["dx"] + dx, cart["y"] + cart["dy"], A, P,
                    opac=min(1.0, ua * 1.4, ub))

    # 6) legenda: SEMPRE opaca; desliza do lugar normal (abaixo do queixo) para a base do vídeo dentro da
    #    janela junto com a câmera, e volta do mesmo jeito (nada de cross-fade com texto "fantasma")
    if leg:
        y_rev = leg_y_rev if not leg_no_topo else 0.115 * H
        y = d.lerp(leg.y_normal(t), y_rev, d.suave(d.mapear(k, 0.15, 0.85)))
        leg.desenhar(base, t, LEG_CX, y, opac=1.0)
    return base.convert("RGBA")
