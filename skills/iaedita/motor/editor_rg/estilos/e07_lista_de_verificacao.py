"""07 · Lista de verificação — um painel escuro com 2 a 6 itens tirados da fala; cada item acende
pouco antes de ser dito e é MARCADO (círculo verde-limão com check desenhado, tique) no instante em
que a pessoa fala. Contador "2 de 5", barra de progresso, rolagem automática quando há mais itens do
que cabem e legenda clara com sublinhado que corre na palavra falada.

Aceita qualquer vídeo (não precisa recortar a pessoa). O painel fica fora do rosto: entre o queixo e
a legenda (ou acima da cabeça, se ali houver mais espaço). Em plano fechado a câmera sobe um pouco
(zoom suave ancorado embaixo) para abrir espaço, e o número de linhas visíveis se adapta."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw

from .. import desenho as d
from ..legenda import agrupar

try:  # OpenCV deixa o movimento de câmera ~3x mais rápido; sem ele o resultado é igual, só mais lento
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

INFO = {
    "id": "07-lista-de-verificacao",
    "nome": "Lista de verificação",
    "precisa_recorte": False,
    "antes": 0.1,
    "depois": 0.1,
    # legenda própria: caixa clara de largura fixa, texto escuro à esquerda, sublinhado verde-oliva
    # que cresce durante a palavra falada (como na prévia aprovada)
    "legenda": {"peso": 750, "tamanho": 0.06, "cor": "#222729", "destaque": "#53622E", "caixa": "#F8F7F0F5",
                "max_caracteres": 20, "max_linhas": 1, "animacao": "subir"},
    "legenda_propria": True,
    "eventos": {
        "lista": "inicio, fim, titulo (2–4 palavras, até 24 letras), itens (lista de 2 a 6 textos curtos, até 24 "
                 "letras cada, na ordem em que são ditos), chamada (opcional: linha pequena acima do título, até 22 "
                 "letras, ex. 'PASSO A PASSO'), revelar ('junto' padrão: todos os itens aparecem apagados e acendem "
                 "| 'um_a_um': cada item entra quando vai ser dito), posicao ('auto' padrão | 'baixo' | 'topo'), "
                 "camera ('auto' padrão: sobe um pouco em plano fechado | 'fixa'), som (use 'interface')",
        "marca": "inicio (instante exato da palavra que nomeia o item), fim (= inicio + 0.3), item (opcional: "
                 "número do item, 1 = primeiro; sem ele marca o próximo da lista), simbolo ('check' padrão | 'x' "
                 "para erro/o que NÃO fazer), som (use 'tique')",
    },
}

# ------------------------------------------------------------------ paleta (da prévia aprovada)
PAINEL = "#242D2DF8"
TEXTO = "#F4F5ED"
KICK = "#BCC7B7"
ARO = "#798479"
ARO_ATIVO = "#D3DBCF"
LIMA = "#D4ED80"
ROSA = "#E9A3BC"
TINTA = "#273225"
PAPEL = "#F8F7F0F5"
INK = "#222729"
OLIVA = "#53622E"

MAX_ITENS = 6
LEAD = 0.6          # a linha acende este tempo antes da marcação
T_MARCA = 0.37      # animação da marcação (11 quadros a 30 fps, como na prévia)
ENTRA, SAI = 0.42, 0.34
APAGADO = 0.36      # opacidade dos itens que ainda não foram ditos (modo 'junto')
LEG_BASE = 0.80     # base da legenda (zona segura de baixo)
TOPO_SEG = 0.115    # nada acima disto (zona segura de cima)
X0 = 0.065          # margem esquerda do painel e da legenda (fração da largura)
LARG = 0.80         # largura do painel e da legenda (fração de u)
LIFTS = (1.0, 1.05, 1.10, 1.15)
VAL_LINHAS = {0: -3000, 1: -1500, 2: 0, 3: 100, 4: 130, 5: 145, 6: 160}


def _u(W, H):
    """Unidade de medida: a largura de um quadro 9:16 com a mesma altura (vídeo vertical = W)."""
    return min(W, H * 0.5625)


def _itens(e):
    out = []
    for x in (e.get("itens") or []):
        if isinstance(x, dict):
            x = x.get("texto", "")
        x = " ".join(str(x).split())
        if x:
            out.append(x)
    return out[:MAX_ITENS]


def _dono(m, listas):
    """A lista a que uma marca pertence (uma só, mesmo com listas encostadas uma na outra)."""
    t = m["inicio"]
    for e in listas:
        if e["inicio"] <= t <= e["fim"]:
            return e
    for e in listas:
        if e["inicio"] - 0.05 <= t <= e["fim"] + 0.05:
            return e
    return None


# ------------------------------------------------------------------ validação do plano

def validar(plano, duracao):
    p = []
    evs = plano["eventos"]
    listas = sorted([e for e in evs if e.get("tipo") == "lista"], key=lambda e: e["inicio"])
    marcas = sorted([e for e in evs if e.get("tipo") == "marca"], key=lambda e: e["inicio"])
    if not listas:
        p.append("Este estilo precisa de pelo menos uma 'lista' (o painel com os itens).")
    for a, b in zip(listas, listas[1:]):
        if b["inicio"] < a["fim"] - 0.01:
            p.append(f"Listas sobrepostas em {b['inicio']:.2f}s: uma lista termina antes da outra começar.")
    for e in listas:
        ini, fim = e["inicio"], e["fim"]
        itens_brutos = e.get("itens") or []
        itens = _itens(e)
        qtd = len(itens_brutos) if isinstance(itens_brutos, list) else 0
        if qtd > MAX_ITENS:
            p.append(f"Lista em {ini:.2f}s com {qtd} itens: o máximo é {MAX_ITENS}. Divida em duas listas seguidas.")
        elif qtd < 2:
            p.append(f"Lista em {ini:.2f}s com {qtd} item(ns) em 'itens': uma lista precisa de 2 a {MAX_ITENS} itens.")
        for it in itens:
            if len(it) > 24 or len(it.split()) > 4:
                p.append(f"Item longo demais na lista de {ini:.2f}s: '{it}' (máx. 4 palavras / 24 letras).")
        tit = " ".join(str(e.get("titulo") or "").split())
        if not tit:
            p.append(f"Lista em {ini:.2f}s sem 'titulo' (2 a 4 palavras que resumem a lista).")
        elif len(tit) > 24 or len(tit.split()) > 5:
            p.append(f"Título longo demais na lista de {ini:.2f}s: '{tit}' (máx. 24 letras).")
        if len(str(e.get("chamada") or "")) > 22:
            p.append(f"'chamada' da lista de {ini:.2f}s longa demais (máx. 22 letras).")
        if e.get("revelar", "junto") not in ("junto", "um_a_um"):
            p.append(f"Lista em {ini:.2f}s: 'revelar' deve ser 'junto' ou 'um_a_um'.")
        if e.get("posicao", "auto") not in ("auto", "baixo", "topo"):
            p.append(f"Lista em {ini:.2f}s: 'posicao' deve ser 'auto', 'baixo' ou 'topo'.")
        if e.get("camera", "auto") not in ("auto", "fixa"):
            p.append(f"Lista em {ini:.2f}s: 'camera' deve ser 'auto' ou 'fixa'.")
        if fim - ini < 1.6:
            p.append(f"Lista em {ini:.2f}s curta demais ({fim - ini:.1f}s): mínimo 1,6 s.")
        dentro = [m for m in marcas if _dono(m, listas) is e]
        if not dentro:
            p.append(f"Lista em {ini:.2f}s sem nenhuma 'marca': cada item precisa ser marcado quando é dito.")
            continue
        if len(dentro) > len(itens):
            p.append(f"Lista em {ini:.2f}s tem {len(dentro)} marcas e só {len(itens)} itens: uma marca por item.")
        if dentro[0]["inicio"] < ini + 0.3 - 1e-6:
            p.append(f"Primeira marca da lista de {ini:.2f}s cedo demais ({dentro[0]['inicio']:.2f}s): comece a "
                     f"lista pelo menos 0,3 s antes (o painel precisa aparecer antes do primeiro check).")
        if fim - dentro[-1]["inicio"] < 0.6 - 1e-6:
            p.append(f"Lista de {ini:.2f}s termina logo depois da última marca ({dentro[-1]['inicio']:.2f}s): "
                     f"deixe pelo menos 0,6 s (ideal 0,8 s ou mais) para o público ver tudo marcado.")
        for a, b in zip(dentro, dentro[1:]):
            if b["inicio"] - a["inicio"] < 0.25 - 1e-6:
                p.append(f"Marcas coladas em {b['inicio']:.2f}s (menos de 0,25 s): use a palavra seguinte ou junte itens.")
        for m in dentro:
            if m.get("item") is not None:
                try:
                    k = int(m.get("item"))
                except (TypeError, ValueError):
                    k = 0
                if not 1 <= k <= max(1, len(itens)):
                    p.append(f"Marca em {m['inicio']:.2f}s: 'item' deve ser um número de 1 a {len(itens)}.")
    for m in marcas:
        if _dono(m, listas) is None:
            p.append(f"Marca em {m['inicio']:.2f}s fora de qualquer lista: toda marca fica dentro de uma 'lista'.")
        if m.get("simbolo", "check") not in ("check", "x"):
            p.append(f"Marca em {m['inicio']:.2f}s: 'simbolo' deve ser 'check' ou 'x'.")
        if not m.get("som"):
            p.append(f"Marca em {m['inicio']:.2f}s sem som: use \"som\": \"tique\" (ou \"nenhum\" de propósito).")
    return p


# ------------------------------------------------------------------ medidas do painel

def _medidas(u, kick, compacto, linhas_tit=1):
    m = {"kick": kick, "compacto": compacto}
    m["pad_x"] = 0.05 * u
    m["pad_top"] = (0.026 if compacto else 0.036) * u
    m["f_kick"] = 0.036 * u
    m["kick_h"] = (0.036 * 1.25 + 0.03) * u if kick else 0.0
    m["f_tit"] = (0.05 if compacto else 0.058) * u
    m["tit_h"] = m["f_tit"] * (1.16 if compacto else 1.2) * linhas_tit
    m["gap_rows"] = (0.008 if compacto else 0.014) * u
    m["passo"] = (0.072 if compacto else 0.088) * u
    m["f_item"] = (0.045 if compacto else 0.05) * u
    m["circ"] = (0.05 if compacto else 0.058) * u
    m["bar_gap"] = (0.016 if compacto else 0.02) * u
    m["bar_h"] = max(3.0, 0.008 * u)
    m["pad_bot"] = (0.026 if compacto else 0.03) * u
    m["f_cnt"] = 0.038 * u
    m["raio"] = 0.032 * u
    m["fixo"] = m["pad_top"] + m["kick_h"] + m["tit_h"] + m["gap_rows"] + m["bar_gap"] + m["bar_h"] + m["pad_bot"]
    return m


def _rosto_janela(g, t0, t1):
    """Topo da cabeça e queixo durante a lista. Usa o percentil 85 (não o pior quadro isolado): um
    balanço de cabeça de um instante encosta no máximo no queixo, nunca na boca."""
    ts = [float(t) for t in np.arange(max(0.0, t0), max(t0, t1) + 1e-6, 0.2)] or [float(t0)]
    caixas = [g.rosto.em(t) for t in ts]
    topo = float(np.percentile([g.rosto.topo_cabeca(t) for t in ts], 15))
    queixo = float(np.percentile([g.rosto.queixo(t) for t in ts], 85))
    cx = sum((b[0] + b[2]) / 2 for b in caixas) / len(caixas) / g.W
    return topo, queixo, cx


def _y_lift(y, s, H):
    """Posição vertical na tela depois do zoom ancorado embaixo (a câmera 'sobe')."""
    return y * s - H * (s - 1)


def _escolher_layout(g, e, n, leg, tit, tem_chamada, janela=None, fixo=None):
    """Escolhe onde e como o painel fica: região (abaixo do queixo / acima da cabeça), subida da câmera,
    legenda visível, linha de chamada, tamanho normal ou compacto e quantas linhas cabem. 'fixo' repete a
    escolha de outra lista (páginas seguidas da mesma lista ficam iguais)."""
    W, H = g.W, g.H
    u = _u(W, H)
    j0, j1 = janela or (e["inicio"], e["fim"])
    topo, queixo, cx = _rosto_janela(g, j0 - 0.2, j1 + 0.2)
    pos = e.get("posicao", "auto")
    regioes = ["baixo", "topo"] if pos == "auto" else [pos]
    lifts = LIFTS if e.get("camera", "auto") == "auto" else (1.0,)
    leg_top = leg.topo_padrao() if leg else LEG_BASE * H
    gap = 0.009 * H
    inner = LARG * u - 2 * 0.05 * u

    def limites(regiao, s, leg_vis):
        if regiao == "baixo":
            return _y_lift(queixo, s, H) + 0.006 * H, (leg_top - gap) if leg_vis else LEG_BASE * H
        return TOPO_SEG * H, _y_lift(topo, s, H) - 0.018 * H

    def medir(kick, compacto):
        m0 = _medidas(u, kick, compacto)
        larg_tit = inner if kick else inner - _largura_contador(m0, n) - 0.03 * u
        _, lin, _ = d.ajustar_texto(tit, larg_tit, m0["f_tit"] * 2.6, 850, tam_max=int(m0["f_tit"]),
                                    tam_min=int(0.042 * u), max_linhas=2, entrelinha=1.05)
        return _medidas(u, kick, compacto, max(1, len(lin)))

    if fixo is not None:
        regiao, s, leg_vis, kick, compacto, k_max = fixo
        kick = kick and tem_chamada
        m = medir(kick, compacto)
        y_ini, y_fim = limites(regiao, s, leg_vis)
        K = max(2, min(n, k_max))
    else:
        melhor = None
        for regiao in regioes:
            for s in (lifts if regiao == "baixo" else (1.0,)):
                for leg_vis in ((True, False) if leg else (False,)):
                    y_ini, y_fim = limites(regiao, s, leg_vis)
                    A = y_fim - y_ini
                    for kick in ((True, False) if tem_chamada else (False,)):
                        for compacto in (False, True):
                            m = medir(kick, compacto)
                            kfit = int(math.floor((A - m["fixo"]) / m["passo"] + 1e-6))
                            K = max(0, min(n, kfit))
                            nota = (VAL_LINHAS.get(K, 160) + (20 if K == n else 0) - 600 * (s - 1)
                                    + (15 if kick else 0) + (10 if not compacto else 0)
                                    - (170 if (leg and not leg_vis) else 0) - (4 if regiao == "topo" else 0))
                            if melhor is None or nota > melhor[0] + 1e-9:
                                melhor = (nota, regiao, s, leg_vis, kick, compacto, K, m, y_ini, y_fim)
        nota, regiao, s, leg_vis, kick, compacto, K, m, y_ini, y_fim = melhor
        if K < 2 and pos != "auto":  # o lugar pedido não comporta a lista: escolhe sozinho
            return _escolher_layout(g, dict(e, posicao="auto"), n, leg, tit, tem_chamada, janela)
        if K < 2:  # último recurso (rosto enorme): painel compacto de 2 linhas colado na base segura
            regiao, leg_vis, kick, compacto = "baixo", False, False, True
            s = lifts[-1]
            m = medir(False, True)
            K = min(n, 2)
            y_fim = LEG_BASE * H
    h = m["fixo"] + K * m["passo"]
    y_card = y_fim - h if regiao == "baixo" else TOPO_SEG * H + 0.006 * H
    return {"regiao": regiao, "s": s, "cx": cx, "leg_vis": leg_vis, "kick": kick, "compacto": compacto,
            "K": K, "m": m, "y": y_card, "h_full": h, "x": X0 * W, "w": LARG * u, "u": u,
            "escolha": (regiao, s, leg_vis, kick, compacto, K)}


def _largura_contador(m, n):
    f = d.fonte(int(m["f_cnt"]), 800)
    return f.getlength(f"{n} de {n}")


# ------------------------------------------------------------------ desenho de peças (pré-desenho)

def _txt_linha(txt, f, cor, alt, larg=None):
    """Texto numa faixa de altura 'alt', com as maiúsculas centradas na vertical."""
    w = int(larg if larg else f.getlength(txt) + 4)
    im = Image.new("RGBA", (max(1, w), int(alt)), (0, 0, 0, 0))
    cap = -f.getbbox("H", anchor="ls")[1]
    ImageDraw.Draw(im).text((1, alt / 2 + cap / 2), txt, font=f, fill=d.cor(cor), anchor="ls")
    return im


def _espacado(txt, f, cor, espaco, alt):
    larg = sum(f.getlength(ch) for ch in txt) + espaco * max(0, len(txt) - 1)
    im = Image.new("RGBA", (int(larg + 4), int(alt)), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    cap = -f.getbbox("H", anchor="ls")[1]
    x = 1.0
    for ch in txt:
        dr.text((x, alt / 2 + cap / 2), ch, font=f, fill=d.cor(cor), anchor="ls")
        x += f.getlength(ch) + espaco
    return im


def _circulo(cache, tam, tipo, q=1.0, cor_aro=ARO):
    """tipo: 'aro' (vazio) | 'check' | 'x'. q = quanto do símbolo já foi desenhado (0-1)."""
    chave = ("07circ", tam, tipo, round(q * 20), cor_aro)
    if chave in cache:
        return cache[chave]
    ss = 4
    S = int(tam * ss)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    if tipo == "aro":
        e = max(2, int(S * 0.075))
        dr.ellipse([e / 2, e / 2, S - 1 - e / 2, S - 1 - e / 2], outline=d.cor(cor_aro), width=e)
    else:
        dr.ellipse([0, 0, S - 1, S - 1], fill=d.cor(LIMA if tipo == "check" else ROSA))
        e = max(2, int(S * 0.115))
        tinta = d.cor(TINTA)
        if tipo == "check":
            pts = [(S * .28, S * .52), (S * .44, S * .67), (S * .73, S * .37)]
            segs = [(pts[0], pts[1]), (pts[1], pts[2])]
        else:
            segs = [((S * .33, S * .33), (S * .67, S * .67)), ((S * .67, S * .33), (S * .33, S * .67))]
        comp = [math.dist(a, b) for a, b in segs]
        resto = q * sum(comp)
        for (a, b), L in zip(segs, comp):
            if resto <= 0:
                break
            k = min(1.0, resto / L)
            fim = (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
            dr.line([a, fim], fill=tinta, width=e)
            for p in (a, fim):  # pontas arredondadas
                dr.ellipse([p[0] - e / 2, p[1] - e / 2, p[0] + e / 2, p[1] + e / 2], fill=tinta)
            resto -= L
    im = im.resize((int(tam), int(tam)), Image.LANCZOS)
    cache[chave] = im
    return im


def _montar_lista(g, e, marcas, listas, leg, janela=None, fixo=None):
    W, H = g.W, g.H
    itens = _itens(e)
    n = len(itens)
    tit = " ".join(str(e.get("titulo") or "").split())
    chamada = " ".join(str(e.get("chamada") or "").split()).upper()
    L = {"e": e, "n": n, "itens": itens, "revelar": e.get("revelar", "junto")}
    if n == 0:
        return None
    # ---- marcações: tempo de cada item e símbolo
    ms = sorted([m for m in marcas if _dono(m, listas) is e], key=lambda m: m["inicio"])
    tc, simb = [None] * n, ["check"] * n
    for m in ms:
        idx = None
        if m.get("item") is not None:
            try:
                idx = int(m.get("item")) - 1
            except (TypeError, ValueError):
                idx = None
        if idx is None or not 0 <= idx < n or tc[idx] is not None:
            idx = next((i for i in range(n) if tc[i] is None), None)
        if idx is None:
            continue
        tc[idx] = float(m["inicio"])
        simb[idx] = "x" if m.get("simbolo") == "x" else "check"
    # ---- quando cada linha acende (pouco antes de ser dita)
    ordem = sorted([i for i in range(n) if tc[i] is not None], key=lambda i: tc[i]) + \
        [i for i in range(n) if tc[i] is None]
    ta = [math.inf] * n
    prev = e["inicio"] + 0.28
    for i in ordem:
        if tc[i] is not None:
            ta[i] = max(prev, tc[i] - LEAD)
            prev = tc[i] + 0.1
        else:
            ta[i] = prev if prev is not None else math.inf
            prev = None
    L.update({"tc": tc, "ta": ta, "simb": simb, "checks": sorted(t for t in tc if t is not None)})
    # ---- layout (lugar, tamanho, câmera)
    lay = _escolher_layout(g, e, n, leg, tit, bool(chamada), janela, fixo)
    L.update(lay)
    m, u, K = lay["m"], lay["u"], lay["K"]
    w = int(lay["w"])
    inner = w - 2 * m["pad_x"]
    # ---- textos pré-desenhados
    f_cnt = d.fonte(int(m["f_cnt"]), 800)
    cnt_h = m["f_cnt"] * 1.5
    L["cnt"] = {k: _txt_linha(f"{k} de {n}", f_cnt, TEXTO, cnt_h) for k in range(n + 1)}
    L["cnt_fim"] = _txt_linha(f"{n} de {n}", f_cnt, LIMA, cnt_h)
    L["cnt_h"] = cnt_h
    larg_cnt = max(im.width for im in L["cnt"].values())
    larg_tit = inner if lay["kick"] else inner - larg_cnt - 0.03 * u
    f_tit, lin_tit, _ = d.ajustar_texto(tit, larg_tit, m["f_tit"] * 2.6, 850, tam_max=int(m["f_tit"]),
                                             tam_min=int(0.042 * u), max_linhas=2, entrelinha=1.05)
    # ---- fundo do painel (cheio = K linhas) com sombra, cabeçalho e trilho da barra
    h_full = int(round(lay["h_full"]))
    M = int(0.06 * u)
    base = Image.new("RGBA", (w + 2 * M, h_full + 2 * M), (0, 0, 0, 0))
    pan = d.painel(w, h_full, int(m["raio"]), fundo=PAINEL)
    som, _ = d.sombra(pan, raio=0.022 * u, opacidade=0.42, desloc=(0, int(0.016 * u)), margem=M)
    base.alpha_composite(som, (0, 0))
    y = M + m["pad_top"]
    x = M + m["pad_x"]
    if lay["kick"]:
        f_k = d.fonte(int(m["f_kick"]), 600)
        kim = _espacado(chamada, f_k, KICK, m["f_kick"] * 0.16, m["f_kick"] * 1.25)
        base.alpha_composite(kim, (int(x), int(y)))
        L["cnt_xy"] = (M + w - m["pad_x"], y + m["f_kick"] * 1.25 / 2)
        ysep = y + m["f_kick"] * 1.25 + 0.014 * u
        ImageDraw.Draw(base).line([(x, ysep), (M + w - m["pad_x"], ysep)], fill=(255, 255, 255, 38),
                                  width=max(1, int(0.0016 * u)))
        y += m["kick_h"]
    tit_h = m["tit_h"]
    alt_lin = tit_h / max(1, len(lin_tit))
    for i, l in enumerate(lin_tit):
        base.alpha_composite(_txt_linha(l, f_tit, "#FFFFFF", alt_lin), (int(x), int(y + i * alt_lin)))
    if not lay["kick"]:
        L["cnt_xy"] = (M + w - m["pad_x"], y + alt_lin / 2)
    y += tit_h + m["gap_rows"]
    L["y_rows"] = y                      # topo da área das linhas (coordenadas do cartão com margem)
    L["M"] = M
    yb = M + h_full - m["pad_bot"] - m["bar_h"]
    L["bar"] = (x, yb, inner, m["bar_h"])
    trilho = d.painel(inner, m["bar_h"], int(m["bar_h"] / 2), fundo=(255, 255, 255, 30))
    base.alpha_composite(trilho, (int(x), int(yb)))
    L["bg"] = base
    # fatia de baixo do cartão (barra + cantos): usada para o painel crescer no modo 'um_a_um'
    L["bot"] = int(math.ceil(m["pad_bot"] + m["bar_h"] + m["bar_gap"]))
    # ---- linhas: rótulos em branco / verde-limão / rosa
    passo = m["passo"]
    circ = int(m["circ"])
    gap_c = 0.03 * u
    larg_lab = inner - circ - gap_c
    rot = []
    for it in itens:
        f_i, lin, _ = d.ajustar_texto(it, larg_lab, passo * 0.8, 750, tam_max=int(m["f_item"]),
                                      tam_min=int(0.04 * u), max_linhas=1)
        txt = lin[0] if lin else it
        rot.append({c: _txt_linha(txt, f_i, c, passo) for c in (TEXTO, LIMA, ROSA)})
    L["rot"] = rot
    L["circ"], L["gap_c"], L["inner"] = circ, gap_c, inner
    L["area_h"] = int(round(K * passo))
    if n > K:  # leve esmaecido nas bordas da janela de rolagem
        a = np.ones(L["area_h"], np.float32)
        fade = max(2, int(passo * 0.22))
        rampa = np.linspace(0, 1, fade, dtype=np.float32)
        a[:fade] = rampa
        a[-fade:] = rampa[::-1]
        L["mascara_rol"] = Image.fromarray((np.repeat(a[:, None], int(inner), 1) * 255).astype(np.uint8), "L")
    else:
        L["mascara_rol"] = None
    # ---- rolagem: início da janela conforme o número de itens já marcados
    foco = K - 2 if K >= 3 else K - 1
    L["janela"] = [max(0, min(n - K, i - foco)) for i in range(n)] + [max(0, n - K)]
    return L


# ------------------------------------------------------------------ legenda própria (sublinhado progressivo)

def _paginas(palavras, max_car, max_pal=4):
    out = []
    for gr in agrupar(palavras, max_car, 1):
        ps = gr["palavras"]
        partes = [ps[i:i + max_pal] for i in range(0, len(ps), max_pal)]
        for j, pp in enumerate(partes):
            fim = partes[j + 1][0]["inicio"] if j + 1 < len(partes) else gr["fim"]
            out.append({"palavras": pp, "inicio": pp[0]["inicio"], "fim": fim})
    return out


class _Legenda:
    """Caixa clara de largura fixa (alinhada ao painel), texto escuro à esquerda, sublinhado verde-oliva
    que cresce durante a palavra falada. Fica na base da zona segura; sobe para cima da cabeça só se o
    rosto descer até ela."""

    def __init__(self, g, perfil):
        W, H = g.W, g.H
        u = _u(W, H)
        self.g, self.W, self.H, self.u = g, W, H, u
        self.p = perfil
        self.peso = int(perfil.get("peso", 750))
        self.tam = int(u * float(perfil.get("tamanho", 0.06)))
        self.maius = bool(perfil.get("maiusculas", False))
        self.cor = perfil.get("cor", INK)
        self.destaque = perfil.get("destaque", OLIVA)
        self.paginas = _paginas(g.palavras, int(perfil.get("max_caracteres", 20) or 20))
        self.x = X0 * W
        self.w = LARG * u
        self.pad_x, self.pad_y = 0.05 * u, 0.024 * u   # texto alinhado com o texto do painel
        f = d.fonte(self.tam, self.peso)
        self.h = f.size * 1.22 + 2 * self.pad_y
        self.inicios = [pg["inicio"] for pg in self.paginas]
        self._med = {}
        caixa = d.painel(self.w, self.h, int(0.012 * u), fundo=perfil.get("caixa", PAPEL))
        self.caixa, self.caixa_desl = d.sombra(caixa, raio=0.014 * u, opacidade=0.28, desloc=(0, int(0.008 * u)))

    def topo_padrao(self):
        return LEG_BASE * self.H - self.h

    def _pagina(self, t):
        for i, pg in enumerate(self.paginas):
            if pg["inicio"] - 0.05 <= t < pg["fim"]:
                return i
        return None

    def _medidas(self, i):
        if i in self._med:
            return self._med[i]
        pg = self.paginas[i]
        txts = [w["texto"].upper() if self.maius else w["texto"] for w in pg["palavras"]]
        util = self.w - 2 * self.pad_x
        tam = self.tam
        while True:
            f = d.fonte(tam, self.peso)
            esp = f.getlength(" ")
            ws = [f.getlength(x) for x in txts]
            if sum(ws) + esp * (len(ws) - 1) <= util or tam <= int(self.u * 0.045):
                break
            tam = int(tam * 0.94)
        xs, x = [], 0.0
        for wv in ws:
            xs.append(x)
            x += wv + esp
        cap = -f.getbbox("H", anchor="ls")[1]
        base_y = self.h / 2 + cap / 2
        cam = Image.new("RGBA", (int(self.w), int(self.h)), (0, 0, 0, 0))
        dr = ImageDraw.Draw(cam)
        for xx, tx in zip(xs, txts):
            dr.text((self.pad_x + xx, base_y), tx, font=f, fill=d.cor(self.cor), anchor="ls")
        self._med[i] = (cam, xs, ws, base_y, f)
        return self._med[i]

    def desenhar(self, img, t, ocultar=0.0, rosto_tela=None):
        i = self._pagina(t)
        if i is None or ocultar >= 0.999:
            return
        pg = self.paginas[i]
        cam_txt, xs, ws, base_y, f = self._medidas(i)
        ini, fim = pg["inicio"], pg["fim"]
        novo = i == 0 or ini - self.paginas[i - 1]["fim"] > 0.06
        acaba = i == len(self.paginas) - 1 or self.paginas[i + 1]["inicio"] - fim > 0.06
        a_caixa = d.saida(d.mapear(t, ini - 0.05, ini + 0.14)) if novo else 1.0
        if acaba:
            a_caixa *= 1 - d.entrada(d.mapear(t, fim - 0.14, fim))
        a_caixa *= 1 - ocultar
        if a_caixa <= 0.003:
            return
        k = d.saida(d.mapear(t, ini - 0.05, ini + 0.16))
        y = LEG_BASE * self.H - self.h
        if rosto_tela is not None:  # rosto desceu até a legenda: ela sobe para cima da cabeça
            topo, queixo = rosto_tela
            if queixo > y - 0.01 * self.H and topo - 0.02 * self.H - self.h >= TOPO_SEG * self.H:
                y = topo - 0.02 * self.H - self.h
        y += (1 - k) * 0.012 * self.u if novo else 0
        d.colar_em(img, self.caixa, (self.x + self.caixa_desl[0], y + self.caixa_desl[1]), opacidade=a_caixa)
        # texto entra num leve "assentar" a cada página
        dy = (1 - k) * 0.012 * self.u
        d.colar_em(img, cam_txt, (self.x, y + dy), opacidade=a_caixa * (0.25 + 0.75 * k))
        # sublinhado progressivo na palavra falada
        j = None
        for jj, w in enumerate(pg["palavras"]):
            if t >= w["inicio"] - 0.03:
                j = jj
        if j is None:
            return
        w = pg["palavras"][j]
        dur = max(0.15, min(0.6, w["fim"] - w["inicio"]))
        kk = d.suave(d.mapear(t, w["inicio"] - 0.03, w["inicio"] + dur))
        if kk <= 0.01:
            return
        esp = max(2, int(round(0.0058 * self.u)))
        x0 = self.x + self.pad_x + xs[j]
        yl = y + dy + base_y + f.size * 0.16
        larg = max(1, int(ws[j] * kk))
        risco = d.painel(larg, esp, int(esp / 2), fundo=self.destaque)
        d.colar_em(img, risco, (x0, yl), opacidade=a_caixa)


# ------------------------------------------------------------------ preparação

def _segmentos_camera(listas, duracao):
    segs = []
    for L in sorted(listas, key=lambda L: L["e"]["inicio"]):
        a, b = L["e"]["inicio"], L["e"]["fim"]
        if L["regiao"] == "topo":
            segs.append({"a": a, "b": b, "s": 1.0, "cx": L["cx"], "quebra": True})
            continue
        if L["s"] <= 1.0005:
            continue
        if segs and not segs[-1].get("quebra") and a - segs[-1]["b"] < 1.2:
            sg = segs[-1]
            sg["b"] = b
            sg["cx"] = (sg["cx"] * sg["peso"] + L["cx"]) / (sg["peso"] + 1)
            sg["peso"] += 1
            sg["s"] = max(sg["s"], L["s"])
        else:
            segs.append({"a": a, "b": b, "s": L["s"], "cx": L["cx"], "peso": 1})
    out = []
    for sg in segs:
        if sg.get("quebra") or sg["s"] <= 1.0005:
            continue
        ra = sg["a"] - 0.45
        if ra < 0.05:
            ra = -1.0  # lista logo no começo: o vídeo já começa enquadrado
        rb = sg["b"] + 0.3
        if rb > duracao - 0.15:
            rb = duracao + 1.0
        out.append({"ra": ra, "rb": rb, "s": sg["s"], "cx": sg["cx"]})
    return out


def _janela_da_corrente(listas, e, folga=0.6):
    """Listas encostadas (troca de página) medem o rosto no trecho inteiro: o painel fica no mesmo lugar
    e com o mesmo tamanho de uma página para a outra."""
    i = next(k for k, x in enumerate(listas) if x is e)
    a = b = i
    while a > 0 and listas[a]["inicio"] - listas[a - 1]["fim"] < folga:
        a -= 1
    while b < len(listas) - 1 and listas[b + 1]["inicio"] - listas[b]["fim"] < folga:
        b += 1
    return listas[a]["inicio"], listas[b]["fim"]


def preparar(g):
    est = {}
    leg = g.plano.get("legenda") or {}
    perfil = dict(INFO["legenda"])
    perfil.update(leg.get("perfil") or {})
    est["leg"] = _Legenda(g, perfil) if leg.get("ativa", True) and g.palavras else None
    evs = g.plano["eventos"]
    marcas = [e for e in evs if e.get("tipo") == "marca"]
    todas = sorted([e for e in evs if e.get("tipo") == "lista"], key=lambda e: e["inicio"])
    listas = []
    escolhas = {}
    for e in todas:
        jan = _janela_da_corrente(todas, e)
        if jan not in escolhas:  # uma escolha para cada sequência de listas encostadas (troca de página)
            grupo = [x for x in todas if jan[0] <= x["inicio"] and x["fim"] <= jan[1]]
            if len(grupo) > 1:
                rep_n = max(len(_itens(x)) for x in grupo)
                rep_tit = max((" ".join(str(x.get("titulo") or "").split()) for x in grupo), key=len)
                rep_ch = all(str(x.get("chamada") or "").strip() for x in grupo)
                escolhas[jan] = _escolher_layout(g, grupo[0], rep_n, est["leg"], rep_tit, rep_ch, jan)["escolha"]
            else:
                escolhas[jan] = None
        L = _montar_lista(g, e, marcas, todas, est["leg"], jan, escolhas[jan])
        if L is not None:
            listas.append(L)
    est["listas"] = listas
    est["cam"] = _segmentos_camera(listas, g.duracao)
    g.cache["07"] = est


def _subir_camera(img, s, cx):
    """Zoom suave ancorado na base do quadro: o rosto sobe e abre espaço embaixo para o painel.
    Mesma conta de _y_lift (base fixa; centro horizontal no rosto, sem mostrar borda vazia)."""
    W, H = img.size
    cw, ch = W / s, H / s
    x0 = min(max(cx * W - cw / 2, 0.0), W - cw)
    y0 = H - ch
    if cv2 is not None:
        m = np.float32([[s, 0, -s * x0], [0, s, -s * y0]])
        out = cv2.warpAffine(np.asarray(img), m, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return Image.fromarray(out, "RGBA")
    return img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, H))


def _camera(est, t):
    for sg in est["cam"]:
        if sg["ra"] <= t <= sg["rb"] + 0.6:
            k = d.suave(d.mapear(t, sg["ra"], sg["ra"] + 0.6)) * (1 - d.suave(d.mapear(t, sg["rb"], sg["rb"] + 0.55)))
            if k > 0:
                return 1 + (sg["s"] - 1) * k, sg["cx"]
    return 1.0, 0.5


# ------------------------------------------------------------------ quadro

def _com_alfa(cache, chave, im, a):
    """Imagem com opacidade 'a'. A versão apagada (itens ainda não ditos) fica em cache."""
    if a >= 0.997:
        return im
    if abs(a - APAGADO) < 1e-4:
        k = ("07apagado",) + chave
        if k not in cache:
            cp = im.copy()
            cp.putalpha(cp.getchannel("A").point(lambda v: int(v * APAGADO)))
            cache[k] = cp
        return cache[k]
    cp = im.copy()
    cp.putalpha(cp.getchannel("A").point(lambda v: int(v * a)))
    return cp


def _prog_marca(L, i, t):
    tc = L["tc"][i]
    return 0.0 if tc is None or t < tc else d.mapear(t, tc, tc + T_MARCA)


def _rolagem(L, t):
    jan = L["janela"]
    s = float(jan[0])
    for c, tc in enumerate(L["checks"]):
        if c + 1 < len(jan):
            s += (jan[c + 1] - jan[c]) * d.suave(d.mapear(t, tc + 0.12, tc + 0.46))
    return s


def _linhas_visiveis(L, t):
    """Modo 'um_a_um': quantas linhas já entraram (suave) — o painel cresce com elas."""
    return sum(d.saida(d.mapear(t, ta, ta + 0.26)) for ta in L["ta"] if ta != math.inf)


def _desenhar_lista(c, img, L):
    t = c.t
    e = L["e"]
    ini, fim = e["inicio"], e["fim"]
    if t < ini or t > fim:
        return
    k_in = d.mapear(t, ini, ini + ENTRA)
    k_out = d.mapear(t, fim - SAI, fim)
    alfa = d.saida(k_in) * (1 - d.entrada(k_out))
    if alfa <= 0.004:
        return
    m, n, K = L["m"], L["n"], L["K"]
    passo = m["passo"]
    M = L["M"]
    um_a_um = L["revelar"] == "um_a_um"
    # ---- altura atual e janela de rolagem
    if um_a_um:
        R = _linhas_visiveis(L, t)
        vis = min(float(K), R)
        rol = max(0.0, R - K)
    else:
        vis = float(K)
        rol = _rolagem(L, t)
    bg = L["bg"]
    h_full = L["h_full"]
    h_now = m["fixo"] + vis * passo
    if abs(h_now - h_full) < 0.5:
        card = bg.copy()
        h_now = h_full
    else:  # painel mais baixo: fatia de cima (cabeçalho) + fatia de baixo (barra e cantos)
        h_px = int(round(h_now))
        corte = M + h_px - L["bot"]
        card = Image.new("RGBA", (bg.width, h_px + 2 * M), (0, 0, 0, 0))
        card.paste(bg.crop((0, 0, bg.width, corte)), (0, 0))
        card.paste(bg.crop((0, bg.height - (L["bot"] + M), bg.width, bg.height)), (0, corte))
    # ---- linhas
    area_h = max(1, int(round(vis * passo)))
    inner = int(L["inner"])
    lay = Image.new("RGBA", (inner, area_h), (0, 0, 0, 0))
    circ, gap_c = L["circ"], L["gap_c"]
    dr = ImageDraw.Draw(lay)
    for j in range(n):
        yj = (j - rol) * passo
        ta = L["ta"][j]
        if um_a_um:
            kr = d.saida(d.mapear(t, ta + 0.07, ta + 0.38)) if ta != math.inf else 0.0  # entra logo depois do espaço abrir
            if kr <= 0.004:
                continue
            a_lin = kr
            yj += (1 - kr) * passo * 0.25
        else:
            aceso = d.suave(d.mapear(t, ta, ta + 0.25)) if ta != math.inf else 0.0
            a_lin = APAGADO + (1 - APAGADO) * aceso
        if yj <= -passo or yj >= area_h:
            continue
        p = _prog_marca(L, j, t)
        tipo = L["simb"][j]
        # brilho rápido na linha no instante da marcação
        if p > 0:
            fl = 1 - d.mapear(t, L["tc"][j], L["tc"][j] + 0.55)
            if fl > 0:
                cor_fl = LIMA if tipo == "check" else ROSA
                faixa = d.painel(inner, int(passo * 0.86), int(passo * 0.2), fundo=d.cor(cor_fl, 0.13 * fl))
                lay.alpha_composite(faixa, (0, int(yj + passo * 0.07)))
        # círculo
        if p <= 0:
            aceso = d.suave(d.mapear(t, ta, ta + 0.25)) if ta != math.inf else 0.0
            ci = _circulo(c.g.cache, circ, "aro", 1.0, ARO_ATIVO if aceso > 0.5 else ARO)
            esc = 1.0
        else:
            q = d.saida(d.mapear(p, 0.12, 0.85))
            ci = _circulo(c.g.cache, circ, tipo, q)
            esc = 1 + math.sin(min(1.0, p) * math.pi) * 0.2
        ci = _com_alfa(c.g.cache, ("circ", id(ci)), ci, a_lin)
        d.colar(lay, ci, (circ / 2, yj + passo / 2), escala=esc)
        # rótulo: branco -> verde-limão (ou rosa no 'x') na marcação
        rot = L["rot"][j]
        pc = d.suave(d.mapear(t, L["tc"][j], L["tc"][j] + 0.2)) if p > 0 else 0.0
        xl = circ + gap_c + (1 - d.saida(p)) * 0.005 * L["u"] if p > 0 else circ + gap_c + 0.005 * L["u"]
        if pc < 0.999:
            d.colar_em(lay, _com_alfa(c.g.cache, ("rot", e["inicio"], j), rot[TEXTO], a_lin * (1 - pc)), (xl, yj))
        if pc > 0.001:
            d.colar_em(lay, rot[LIMA if tipo == "check" else ROSA], (xl, yj), opacidade=a_lin * pc)
        # linha divisória (como a prévia)
        if j < n - 1:
            ys = yj + passo - 1
            if 0 <= ys < area_h:
                dr.line([(0, ys), (inner, ys)], fill=(255, 255, 255, int(20 * a_lin)), width=max(1, int(0.0014 * L["u"])))
    if L["mascara_rol"] is not None and L["mascara_rol"].size == lay.size:
        lay.putalpha(ImageChops.multiply(lay.getchannel("A"), L["mascara_rol"]))
    card.alpha_composite(lay, (int(M + m["pad_x"]), int(L["y_rows"])))
    # ---- barra de progresso (anda a cada marcação)
    bx, by, bw, bh = L["bar"]
    by = card.height - (bg.height - by)
    prog = sum(d.suave(d.mapear(t, tc, tc + 0.45)) for tc in L["checks"]) / max(1, n)
    if prog > 0.002:
        larg = max(int(bh), int(bw * prog))
        card.alpha_composite(d.painel(larg, bh, int(bh / 2), fundo=LIMA), (int(bx), int(by)))
    # ---- contador "2 de 5" (o número rola a cada marcação)
    feitos = sum(1 for tc in L["checks"] if t >= tc)
    tudo = len(L["checks"]) >= n and feitos >= n
    cx_r, cy = L["cnt_xy"]
    cnt_h = L["cnt_h"]
    caixa_cnt = Image.new("RGBA", (max(im.width for im in L["cnt"].values()) + 4, int(cnt_h)), (0, 0, 0, 0))
    ult = L["checks"][feitos - 1] if feitos > 0 else None
    kr = d.saida(d.mapear(t, ult, ult + 0.24)) if ult is not None else 1.0
    novo = L["cnt_fim"] if (tudo and kr >= 1) else L["cnt"][feitos]
    if kr < 1 and feitos > 0:  # o número velho sobe e some, o novo sobe de baixo
        velho = L["cnt"][feitos - 1]
        d.colar_em(caixa_cnt, velho, (caixa_cnt.width - velho.width, -kr * cnt_h * 0.6), opacidade=1 - kr)
        d.colar_em(caixa_cnt, novo, (caixa_cnt.width - novo.width, (1 - kr) * cnt_h * 0.6), opacidade=kr)
    else:
        caixa_cnt.alpha_composite(novo, (caixa_cnt.width - novo.width, 0))
    card.alpha_composite(caixa_cnt, (int(cx_r - caixa_cnt.width), int(cy - cnt_h / 2)))
    # ---- lista completa: borda verde-limão pulsa uma vez
    if tudo:
        t_fim = L["checks"][-1] + T_MARCA * 0.6
        bri = math.sin(math.pi * d.mapear(t, t_fim, t_fim + 0.8))
        if bri > 0.01:
            chave = ("07borda", L["w"], int(round(h_now)))
            if chave not in c.g.cache:
                c.g.cache[chave] = d.painel(L["w"], int(round(h_now)), int(m["raio"]), fundo=(0, 0, 0, 0),
                                            borda=LIMA, larg_borda=max(2, int(0.004 * L["u"])))
            d.colar_em(card, c.g.cache[chave], (M, M), opacidade=0.85 * bri)
    # ---- entra subindo de leve, sai subindo e sumindo
    dy = (1 - d.saida(k_in)) * 0.016 * c.H - d.entrada(k_out) * 0.012 * c.H
    esc = (0.965 + 0.035 * d.saida(k_in)) * (1 - 0.015 * d.entrada(k_out))
    cxp = L["x"] + L["w"] / 2
    cyp = L["y"] + h_now / 2 + dy      # topo fixo: no modo 'um_a_um' o painel cresce para baixo
    d.colar(img, card, (cxp, cyp), escala=esc, opacidade=alfa)


def quadro(c):
    est = c.g.cache.get("07")
    if est is None:
        preparar(c.g)
        est = c.g.cache["07"]
    t = c.t
    s, cx = _camera(est, t)
    if s > 1.0005:
        img = _subir_camera(c.fonte, s, cx)
    else:
        img = c.fonte.copy()
    ocultar = 0.0
    for L in est["listas"]:
        e = L["e"]
        if e["inicio"] <= t <= e["fim"]:
            _desenhar_lista(c, img, L)
            if not L["leg_vis"]:
                k = d.saida(d.mapear(t, e["inicio"] - 0.1, e["inicio"] + 0.2)) * \
                    (1 - d.entrada(d.mapear(t, e["fim"] - 0.25, e["fim"])))
                ocultar = max(ocultar, k)
    if est["leg"] is not None:
        topo = _y_lift(c.g.rosto.topo_cabeca(t), s, c.H)
        queixo = _y_lift(c.g.rosto.queixo(t), s, c.H)
        est["leg"].desenhar(img, t, ocultar, (topo, queixo))
    return img
