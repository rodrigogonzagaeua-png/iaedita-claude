"""03 · Mundo da interface — a câmera passeia por um aplicativo de edição desenhado (janela, menu,
tela principal, linha do tempo e cartão de nota). A pessoa recortada vive dentro da tela principal,
à frente do título. Sem recorte, a tela principal mostra o vídeo original como num editor de vídeo.

Camadas por quadro: mundo pré-desenhado (recorte + redimensionamento pela câmera) → título atrás →
pessoa (presa à tela principal) → título à frente (com etiqueta) → progresso/menu → nota → legenda
digitada. Tudo é função só do tempo; os desenhos fixos ficam em g.cache["e03"]."""
from __future__ import annotations

import bisect
import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import desenho as d
from ..legenda import agrupar

INFO = {
    "id": "03-mundo-da-interface",
    "nome": "Mundo da interface",
    "precisa_recorte": True,
    "antes": 0.0,
    "depois": 0.0,
    # perfil de referência (este estilo desenha a própria legenda: digitada, com cursor, à esquerda)
    "legenda": {"peso": 650, "tamanho": 0.06, "cor": "#F8F7F0", "destaque": "#D4ED80", "caixa": "#222729ED",
                "max_caracteres": 22, "max_linhas": 2, "posicao": "baixo", "animacao": "subir"},
    "legenda_propria": True,
    "eventos": {
        "camera": "inicio, fim, foco ('geral' = recua e mostra o aplicativo inteiro | 'perto' = aproxima no "
                  "rosto | 'tela' = volta ao enquadramento normal). Fora desses trechos a câmera fica em 'tela'. "
                  "som (opcional, use 'lente')",
        "titulo": "inicio, fim, texto (2 a 5 palavras, sem ponto final): título grande digitado no alto da "
                  "tela principal, atrás da pessoa. Um título por vez.",
        "nota": "inicio, fim (1,8 a 4 s), rotulo (1 a 3 palavras, ex.: 'PASSO 1', 'DICA'), texto (2 a 6 "
                "palavras): cartão inclinado que entra ao lado da pessoa; a câmera recua sozinha para mostrá-lo. "
                "som (opcional)",
    },
}

# ------------------------------------------------------------------ paleta (prévia aprovada)
FUNDO = "#E5E7DC"
JANELA = "#FBFBF4"
LINHA_CAB = "#E1E6D9"
MENU = "#EEF1E8"
MENU_IC = "#6C7764"
TELA = "#CED9C8"
LIMA = "#D4ED80"
TINTA = "#222729"
BORDA = "#DCE2D3"
BARRA = "#20272C"
BLOCO = "#526066"
MINI = "#B8B2D5"
NOTA = "#FFFEF6"
ROTULO = "#5F6B58"
ESQ = "#CDD4C4"
ROSA = "#E9A3BC"
VIOLETA = "#7662BF"
LEG_CAIXA = "#222729ED"
LEG_COR = "#F8F7F0"
LEG_ATIVA = "#D4ED80"

DW = 1080.0          # largura do mundo em unidades de desenho (altura = DW * H / W)

# câmera e zona segura (frações da tela)
Z_TELA = 1.40
F = Z_TELA           # o mundo é pré-desenhado no zoom da 'tela': parado ali, é só recortar (rápido e nítido)
Z_PERTO = 1.70
Z_NOTA = 1.30
CX_TELA = 620.0
TOPO_TELA = 0.115     # a tela principal começa logo abaixo da faixa proibida de cima
QUEIXO_MAX = 0.68     # queixo sempre acima da legenda
CABECA_MIN = 0.10
NOTA_BASE = 0.685
LEG_BASE = 0.795

TIT_DX, TIT_DY = 34.0, 26.0     # título: canto da tela principal (unidades)
TIT_LARG, TIT_ALT = 575.0, 142.0
RESERVA = 196.0                 # espaço acima da cabeça reservado ao título


# ------------------------------------------------------------------ layout

def _layout(DH):
    k = DH / 1920.0
    return {
        "k": k,
        "jan": (70.0, 196 * k, 1010.0, 1484 * k),
        "cab": 86 * k,
        "menu": (94.0, 306 * k, 256.0, 1460 * k),
        "tela": (280.0, 306 * k, 986.0, 1236 * k),
        "linha": (280.0, 1260 * k, 986.0, 1460 * k),
    }


def _por_tipo(plano, tipo):
    return [e for e in plano["eventos"] if e.get("tipo") == tipo]


# ------------------------------------------------------------------ validação

def validar(plano, duracao):
    p = []
    cams, tits, notas = (_por_tipo(plano, t) for t in ("camera", "titulo", "nota"))
    for e in cams:
        if e.get("foco", "tela") not in ("geral", "tela", "perto"):
            p.append(f"Câmera em {e['inicio']:.2f}s: foco '{e.get('foco')}' não existe (use geral, perto ou tela).")
    for lista, nome in ((cams, "Câmeras"), (tits, "Títulos"), (notas, "Notas")):
        for a, b in zip(lista, lista[1:]):
            if b["inicio"] < a["fim"] - 0.01:
                p.append(f"{nome} sobrepostos em {b['inicio']:.2f}s: um precisa terminar antes do outro começar.")
    for e in tits:
        tx = str(e.get("texto", "")).strip()
        if not tx:
            p.append(f"Título sem texto em {e['inicio']:.2f}s.")
        elif len(tx.split()) > 6 or len(tx) > 36:
            p.append(f"Título longo demais em {e['inicio']:.2f}s (máx. 5 palavras / 36 letras).")
        if e["fim"] - e["inicio"] < 1.2:
            p.append(f"Título curto demais em {e['inicio']:.2f}s (mínimo 1,2 s na tela).")
    for e in notas:
        tx = str(e.get("texto", "")).strip()
        if not tx:
            p.append(f"Nota sem texto em {e['inicio']:.2f}s.")
        elif len(tx.split()) > 7 or len(tx) > 44:
            p.append(f"Nota longa demais em {e['inicio']:.2f}s (máx. 6 palavras / 44 letras).")
        if len(str(e.get("rotulo", "")).strip()) > 18:
            p.append(f"Rótulo da nota longo demais em {e['inicio']:.2f}s (máx. 18 letras).")
        if e["fim"] - e["inicio"] < 1.6:
            p.append(f"Nota curta demais em {e['inicio']:.2f}s (mínimo 1,6 s para dar tempo de ler).")
        for c in cams:
            if c["inicio"] < e["fim"] - 0.01 and e["inicio"] < c["fim"] - 0.01:
                p.append(f"Câmera e nota ao mesmo tempo em {max(c['inicio'], e['inicio']):.2f}s: a nota já move "
                         "a câmera sozinha; tire a câmera desse trecho.")
    # movimentos colados (a câmera mal chega e já sai): deixe respirar
    visitas = sorted([(e["inicio"], e["fim"]) for e in cams if e.get("foco", "tela") != "tela"] +
                     [(e["inicio"], e["fim"]) for e in notas])
    for (a0, a1), (b0, b1) in zip(visitas, visitas[1:]):
        if a1 - 0.01 <= b0 < a1 + 0.5 and b0 > 0.6:
            p.append(f"Movimentos de câmera colados em {b0:.2f}s: deixe pelo menos 1 s entre o fim de uma "
                     "câmera/nota e o início da próxima.")
    # 'perto' repetido perde o impacto (e cansa no plano fechado). O validar não recebe o tamanho do
    # rosto, então aqui vale o piso de todos os enquadramentos (8 s); a skill pede 12 s no plano fechado.
    pertos = sorted(e["inicio"] for e in cams if e.get("foco") == "perto")
    for a, b in zip(pertos, pertos[1:]):
        if b - a < 8.0:
            p.append(f"Dois 'perto' muito próximos ({a:.2f}s e {b:.2f}s): deixe pelo menos 8 s entre eles "
                     "(12 s no plano fechado). Guarde o 'perto' para as palavras mais fortes.")
    return p


# ------------------------------------------------------------------ rosto (suavizado) e posição da pessoa

_DESL = np.array([-0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6])


def _rosto_fr(g, t):
    r = g.rosto
    if len(r.t) == 1:
        return tuple(float(v) for v in r.c[0])
    ts = np.clip(t + _DESL, 0.0, max(0.0, g.duracao))
    return tuple(float(np.interp(ts, r.t, r.c[:, j]).mean()) for j in range(4))


def _rosto_mundo(est, g, t):
    chave = round(t, 3)
    memo = est["memo_rosto"]
    if chave in memo:
        return memo[chave]
    fx0, fy0, fx1, fy1 = _rosto_fr(g, t)
    fh = fy1 - fy0
    px0, py0, frw, frh = est["px0"], est["py0"], est["frw"], est["frh"]
    r = {"x0": px0 + fx0 * frw, "x1": px0 + fx1 * frw, "y0": py0 + fy0 * frh, "y1": py0 + fy1 * frh,
         "cx": px0 + (fx0 + fx1) / 2 * frw, "cy": py0 + (fy0 + fy1) / 2 * frh,
         "topo": py0 + (fy0 - 0.45 * fh) * frh, "queixo": py0 + (fy1 + 0.08 * fh) * frh}
    if len(memo) > 20000:
        memo.clear()
    memo[chave] = r
    return r


def _posicionar_pessoa(est, g):
    """Escala e posição (fixas no vídeo todo) do quadro original dentro da tela principal."""
    L, DH = est["L"], est["DH"]
    tx0, ty0, tx1, ty1 = L["tela"]
    cw, ch = tx1 - tx0, ty1 - ty0
    c = np.asarray(g.rosto.c, dtype=float)
    fx0, fy0, fx1, fy1 = (float(np.median(c[:, j])) for j in range(4))
    fw, fh = max(0.05, fx1 - fx0), max(0.05, fy1 - fy0)
    topo = fy0 - 0.45 * fh
    sp_cobre = max(cw / DW, ch / DH)
    sp_nativo = 1.0 / Z_TELA            # parado na 'tela', o vídeo aparece pixel a pixel (sem reamostrar)
    sp_rosto = 0.30 * cw / (fw * DW)    # plano aberto (rosto pequeno): aproxima um pouco mais
    sp = max(sp_cobre, sp_nativo)
    if sp_rosto > sp * 1.25:
        sp = min(sp_rosto, 0.85)
    frw, frh = DW * sp, DH * sp
    px0 = (tx0 + tx1) / 2 - (fx0 + fx1) / 2 * frw
    px0 = d.limitar(px0, tx1 - frw, tx0)
    py0 = ty0 + RESERVA * L["k"] - max(0.0, topo) * frh
    if topo < 0.04 or not est["recorte"]:
        py0 = min(py0, ty0)             # cabeça encostada no topo do vídeo: o corte fica escondido na borda
    py0 = max(py0, ty1 - frh)          # o corpo sempre chega até a base da tela principal
    if not est["recorte"]:
        py0 = min(py0, ty0)
    sw = est["sw"]                      # alinha à grade de pixels do mundo (recorte exato quando parado)
    px0, py0 = round(px0 * sw) / sw, round(py0 * sw) / sw
    est.update(sp=sp, frw=frw, frh=frh, px0=px0, py0=py0,
               rosto_med=((fx0 + fx1) / 2, (fy0 + fy1) / 2))


# ------------------------------------------------------------------ desenho do mundo (uma vez)

def _sombra_ret(base, caixa, raio, desfoque, cor_s, alfa):
    q = 4
    W, H = base.size
    m = Image.new("L", (W // q + 1, H // q + 1), 0)
    ImageDraw.Draw(m).rounded_rectangle([v / q for v in caixa], radius=max(1, raio / q), fill=int(255 * alfa))
    m = m.filter(ImageFilter.GaussianBlur(max(1, desfoque / q))).resize((W, H), Image.BILINEAR)
    s = Image.new("RGBA", (W, H), d.cor(cor_s))
    s.putalpha(m)
    base.alpha_composite(s)


def _icone_menu(i, tam, cor_ic):
    """Ícones do menu lateral: vídeo, texto, som, cores (sem palavras)."""
    if i == 0:
        return d.icone("play", tam, cor_ic)
    ss = 4
    S = tam * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    c = d.cor(cor_ic)
    if i == 1:
        f = d.fonte(int(S * 0.62), 750)
        dr.text((S * 0.5, S * 0.54), "Aa", font=f, fill=c, anchor="mm")
    elif i == 2:
        for j, hh in enumerate((0.34, 0.7, 0.5, 0.82, 0.42)):
            x = S * (0.1 + j * 0.18)
            dr.rounded_rectangle([x, S * (0.5 - hh / 2), x + S * 0.1, S * (0.5 + hh / 2)], S * 0.05, fill=c)
    else:
        for j, (ox, oy) in enumerate(((0.32, 0.36), (0.68, 0.36), (0.5, 0.68))):
            r = S * 0.2
            dr.ellipse([S * ox - r, S * oy - r, S * ox + r, S * oy + r], fill=c)
    return im.resize((tam, tam), Image.LANCZOS)


def _desenhar_mundo(est):
    sw, L, DH = est["sw"], est["L"], est["DH"]
    k = L["k"]
    Wm, Hm = int(round(DW * sw)), int(round(DH * sw))

    def S(v):
        return v * sw

    mundo = Image.new("RGBA", (Wm, Hm), d.cor(FUNDO))
    # grade fina do "mundo"
    grade = Image.new("L", (Wm, Hm), 0)
    gd = ImageDraw.Draw(grade)
    lw = max(1, int(round(1.3 * sw)))
    v = 0.0
    while v <= DW + 1:
        gd.line([(S(v), 0), (S(v), Hm)], fill=255, width=lw)
        v += 60
    v = 0.0
    while v <= DH + 1:
        gd.line([(0, S(v)), (Wm, S(v))], fill=255, width=lw)
        v += 60
    cam = Image.new("RGBA", (Wm, Hm), (55, 73, 60, 255))
    cam.putalpha(grade.point(lambda a: int(a * 0.085)))
    mundo.alpha_composite(cam)

    jx0, jy0, jx1, jy1 = L["jan"]
    _sombra_ret(mundo, (S(jx0), S(jy0 + 35), S(jx1), S(jy1 + 35)), S(28), S(55), (52, 66, 54, 255), 0.22)
    jan = d.painel(S(jx1 - jx0), S(jy1 - jy0), raio=int(S(28)), fundo=JANELA, borda="#FFFFFF",
                   larg_borda=max(1, int(S(2))))
    mundo.alpha_composite(jan, (int(S(jx0)), int(S(jy0))))
    dr = ImageDraw.Draw(mundo)

    # cabeçalho: botões da janela, logo, nome (esqueleto) e "salvo" (check)
    ycab = jy0 + L["cab"]
    dr.line([(S(jx0 + 3), S(ycab)), (S(jx1 - 3), S(ycab))], fill=LINHA_CAB, width=max(1, int(S(2))))
    yc = jy0 + L["cab"] / 2
    for j, cc in enumerate((ROSA, LIMA, VIOLETA)):
        x = jx0 + 36 + j * 26
        dr.ellipse([S(x - 8), S(yc - 8), S(x + 8), S(yc + 8)], fill=cc)
    logo = d.painel(S(38), S(38), raio=int(S(11)), fundo=TINTA)
    logo.alpha_composite(d.icone("play", int(S(20)), LIMA), (int(S(10)), int(S(9))))
    mundo.alpha_composite(logo, (int(S(jx0 + 128)), int(S(yc - 19))))
    dr.rounded_rectangle([S(jx0 + 182), S(yc - 9), S(jx0 + 360), S(yc + 9)], S(9), fill="#3A4441")
    dr.rounded_rectangle([S(jx0 + 372), S(yc - 9), S(jx0 + 440), S(yc + 9)], S(9), fill=ESQ)
    pil = d.painel(S(150), S(42), raio=int(S(21)), fundo=MENU)
    mundo.alpha_composite(pil, (int(S(jx1 - 184)), int(S(yc - 21))))
    dr.ellipse([S(jx1 - 176), S(yc - 15), S(jx1 - 146), S(yc + 15)], fill=LIMA)
    mundo.alpha_composite(d.icone("check", int(S(22)), TINTA), (int(S(jx1 - 172)), int(S(yc - 11))))
    dr.rounded_rectangle([S(jx1 - 134), S(yc - 7), S(jx1 - 50), S(yc + 7)], S(7), fill=ESQ)

    # menu lateral com ícones
    mx0, my0, mx1, my1 = L["menu"]
    mundo.alpha_composite(d.painel(S(mx1 - mx0), S(my1 - my0), raio=int(S(18)), fundo=MENU),
                          (int(S(mx0)), int(S(my0))))
    mcx = (mx0 + mx1) / 2
    est["menu_pos"] = []
    for i in range(4):
        y = my0 + 74 * k + i * 112 * k
        est["menu_pos"].append((mcx, y))
        ic = _icone_menu(i, int(S(40)), MENU_IC)
        mundo.alpha_composite(ic, (int(S(mcx - 20)), int(S(y - 20))))
    for j, wv in enumerate((96, 64)):
        yb = my1 - (90 - j * 30) * k
        dr.rounded_rectangle([S(mcx - wv / 2), S(yb - 6), S(mcx + wv / 2), S(yb + 6)], S(6), fill="#DDE2D5")

    # tela principal (fundo sálvia + círculo lima atrás da pessoa)
    tx0, ty0, tx1, ty1 = L["tela"]
    cw, ch = S(tx1 - tx0), S(ty1 - ty0)
    tela = d.painel(cw, ch, raio=int(S(18)), fundo=TELA)
    if est["recorte"]:
        fcx, fcy = est["rosto_med"]
        ccx = est["px0"] + fcx * est["frw"] - 0.05 * (tx1 - tx0)
        ccy = est["py0"] + fcy * est["frh"] + 0.42 * (ty1 - ty0)
        r = 0.60 * (tx1 - tx0)
        circ = Image.new("RGBA", (int(cw), int(ch)), (0, 0, 0, 0))
        ImageDraw.Draw(circ).ellipse([S(ccx - tx0 - r), S(ccy - ty0 - r), S(ccx - tx0 + r), S(ccy - ty0 + r)],
                                     fill=d.cor(LIMA, 0.82))
        circ.putalpha(ImageChops.multiply(circ.getchannel("A"),
                                          d.mascara_arredondada(int(cw), int(ch), int(S(18)))))
        tela.alpha_composite(circ)
    mundo.alpha_composite(tela, (int(S(tx0)), int(S(ty0))))

    # linha do tempo ("sequência"): esqueleto do rótulo, barra escura com blocos, miniaturas
    lx0, ly0, lx1, ly1 = L["linha"]
    mundo.alpha_composite(d.painel(S(lx1 - lx0), S(ly1 - ly0), raio=int(S(14)), fundo=(0, 0, 0, 0), borda=BORDA,
                                   larg_borda=max(1, int(S(2)))), (int(S(lx0)), int(S(ly0))))
    dr.rounded_rectangle([S(lx0 + 24), S(ly0 + 22 * k), S(lx0 + 200), S(ly0 + 38 * k)], S(8), fill=ESQ)
    bx0, by0, bx1, by1 = lx0 + 20, ly0 + 52 * k, lx1 - 20, ly0 + 132 * k
    mundo.alpha_composite(d.painel(S(bx1 - bx0), S(by1 - by0), raio=int(S(12)), fundo=BARRA),
                          (int(S(bx0)), int(S(by0))))
    blocos = []
    x = bx0 + 12
    for n in range(6):
        wb = 54 + (n % 3) * 20
        blocos.append((x, by0 + 12 * k, x + wb, by1 - 12 * k))
        x += wb + 6
    for (a0, b0, a1, b1) in blocos:
        dr.rounded_rectangle([S(a0), S(b0), S(a1), S(b1)], S(5), fill=d.cor(BLOCO, 0.92))
    est["blocos"] = blocos
    est["barra"] = (bx0, by0, bx1, by1)
    nmin = 8
    larg_m = (bx1 - bx0 - 7 * (nmin - 1)) / nmin
    for n in range(nmin):
        a0 = bx0 + n * (larg_m + 7)
        dr.rounded_rectangle([S(a0), S(ly0 + 146 * k), S(a0 + larg_m), S(ly0 + 174 * k)], S(4), fill=MINI)

    # camada "cheia" dos blocos (progresso do vídeo)
    fx0, fy0 = blocos[0][0], blocos[0][1]
    fx1, fy1 = blocos[-1][2], blocos[-1][3]
    cheia = Image.new("RGBA", (int(S(fx1 - fx0)) + 2, int(S(fy1 - fy0)) + 2), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cheia)
    for (a0, b0, a1, b1) in blocos:
        cd.rounded_rectangle([S(a0 - fx0), S(b0 - fy0), S(a1 - fx0), S(b1 - fy0)], S(5), fill=LIMA)
    est["cheia"] = (cheia, fx0, fy0, fx1)

    # item ativo do menu (quadrado lima + ícone escuro)
    est["menu_ativo"] = []
    for i in range(4):
        q = d.painel(S(78), S(78), raio=int(S(20)), fundo=LIMA)
        q.alpha_composite(_icone_menu(i, int(S(40)), TINTA), (int(S(19)), int(S(19))))
        est["menu_ativo"].append(q)
    return mundo


# ------------------------------------------------------------------ título (digitado, tracking justo)

def _render_titulo(texto, sw, larg, alt, tam_max=66, tam_min=44, max_linhas=2):
    f, linhas, al = d.ajustar_texto(texto, larg * sw, alt * sw, 850, tam_max=int(tam_max * sw),
                                    tam_min=int(tam_min * sw), max_linhas=max_linhas, entrelinha=1.04)
    trk = 0.032 * f.size
    pos = []
    largs = []
    for l in linhas:
        xs = [f.getlength(l[:j + 1]) - trk * j for j in range(len(l))]
        pos.append(xs)
        largs.append(xs[-1] if xs else 0)
    wi = int(max(largs) + f.size * 0.25)
    hi = int(al * len(linhas) + f.size * 0.3)
    img = Image.new("RGBA", (wi, hi), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    for li, l in enumerate(linhas):
        for j, chh in enumerate(l):
            x = (f.getlength(l[:j]) - trk * j) if j else 0.0
            dr.text((x, li * al), chh, font=f, fill=TINTA)
    return {"img": img, "linhas": linhas, "pos": pos, "al": al, "fs": f.size}


def _preparar_titulos(est, g):
    sw = est["sw"]
    L = est["L"]
    tx0, ty0 = L["tela"][0], L["tela"][1]
    out = []
    for e in est["titulos"]:
        texto = str(e.get("texto", "")).strip()
        r = _render_titulo(texto, sw, TIT_LARG, TIT_ALT)
        x, y = tx0 + TIT_DX, ty0 + TIT_DY
        h = r["img"].height / sw
        # onde fica a cabeça/olhos durante o título (pior caso)
        ts = np.arange(e["inicio"], e["fim"] + 0.01, 0.4)
        topo = min(_rosto_mundo(est, g, float(t))["topo"] for t in ts)
        olhos = min(_rosto_mundo(est, g, float(t))["y0"] for t in ts)
        disp = olhos - y - 18
        if h > disp > 40:  # título invadiria a linha dos olhos: 1 linha, menor
            r = _render_titulo(texto, sw, TIT_LARG, disp, tam_max=58, tam_min=42, max_linhas=1)
            h = r["img"].height / sw
        frente = (not est["recorte"]) or topo < y + h + 8
        n = sum(len(l) for l in r["linhas"])
        r.update(x=x, y=y, h=h, frente=frente, n=n, ini=e["inicio"], fim=e["fim"],
                 dig=min(0.6, 0.12 + 0.032 * n))
        if frente:
            pad = 18 * sw
            et = d.painel(r["img"].width + pad * 2, r["img"].height + pad * 1.4, raio=int(16 * sw),
                          fundo=d.cor(JANELA, 0.94), borda="#FFFFFF", larg_borda=max(1, int(1.5 * sw)))
            sh, (dx, dy) = d.sombra(et, raio=14 * sw, opacidade=0.16, desloc=(0, 8 * sw))
            r["etiqueta"] = (sh, dx - pad, dy - pad * 0.7)
        out.append(r)
    return out


def _titulo_revelado(est, i, m):
    chave = ("e03_tit", i, m)
    cache = est["cache_tit"]
    if chave in cache:
        return cache[chave]
    r = est["tits"][i]
    if m >= r["n"]:
        img = r["img"]
    else:
        img = Image.new("RGBA", r["img"].size, (0, 0, 0, 0))
        resto = m
        for li, xs in enumerate(r["pos"]):
            if resto <= 0:
                break
            q = min(len(xs), resto)
            corte = int(math.ceil(xs[q - 1] + r["fs"] * 0.04))
            y0 = int(li * r["al"])
            y1 = int(min(img.height, (li + 1) * r["al"] + r["fs"] * 0.3))
            img.paste(r["img"].crop((0, y0, corte, y1)), (0, y0))
            resto -= q
    cache[chave] = img
    return img


def _cursor_titulo(r, m):
    """Posição (unidades da imagem do título, px) do cursor depois do caractere m."""
    resto = m
    for li, xs in enumerate(r["pos"]):
        q = min(len(xs), resto)
        if resto <= len(xs):
            x = xs[q - 1] if q > 0 else 0.0
            return x + r["fs"] * 0.06, li * r["al"]
        resto -= len(xs)
    return r["pos"][-1][-1] + r["fs"] * 0.06, (len(r["pos"]) - 1) * r["al"]


def _sobrepor(base, camada, xy, op=1.0):
    """Cola uma peça RGBA em base RGBA (composição) ou RGB (colagem pela própria transparência)."""
    if base.mode == "RGBA":
        d.colar_em(base, camada, xy, op)
        return
    x, y = int(round(xy[0])), int(round(xy[1]))
    W, H = base.size
    if x >= W or y >= H or x + camada.width <= 0 or y + camada.height <= 0 or op <= 0.003:
        return
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(camada.width, W - x), min(camada.height, H - y)
    peca = camada.crop((cx0, cy0, cx1, cy1))
    alfa = peca.getchannel("A")
    if op < 0.997:
        alfa = alfa.point(lambda v: int(v * op))
    base.paste(peca, (x + cx0, y + cy0), alfa)


def _escalado(est, chave, img, esc):
    """Versão redimensionada de uma peça pronta (guardada: com a câmera parada não refaz)."""
    esc = round(esc, 4)
    cache = est["cache_esc"]
    ch = (chave, esc)
    if ch not in cache:
        if len(cache) > 300:
            cache.clear()
        cache[ch] = img if abs(esc - 1) < 1e-4 else img.resize(
            (max(1, int(round(img.width * esc))), max(1, int(round(img.height * esc)))), Image.BICUBIC)
    return cache[ch]


def _lugar_titulo(c, est, cam, r, frente, op):
    """Posição e escala do título na tela. Parado na 'tela' fica onde foi desenhado (preso à tela
    principal). Quando a câmera aproxima ('perto'), o título NÃO some: desliza para dentro da zona
    segura (11% do topo, margens laterais) e encolhe o necessário para caber acima da cabeça, com
    piso de tamanho de letra legível. Só esmaece se nem assim couber acima do rosto."""
    W, H = c.W, c.H
    sw = est["sw"]
    k = cam["k"]
    sx = (r["x"] - cam["vx0"]) * k
    sy = (r["y"] - cam["vy0"]) * k
    esc = k / sw
    # caixa visível (px da imagem do título): o texto, ou a etiqueta de papel quando vai à frente
    if frente and "etiqueta" in r:
        et, dx, dy = r["etiqueta"]
        bx0, by0 = dx + 22 * sw, dy + 22 * sw
        bx1, by1 = dx + et.width - 22 * sw, dy + et.height - 22 * sw
    else:
        bx0, by0, bx1, by1 = 0.0, 0.0, float(r["img"].width), float(r["img"].height)
    X0, Y0 = sx + bx0 * esc, sy + by0 * esc
    bw, bh = (bx1 - bx0) * esc, (by1 - by0) * esc
    s = 1.0
    if bw > 0.81 * W:                                   # largura: cabe entre as margens seguras
        s = 0.81 * W / bw
    # aproximando além da 'tela': cabe acima da cabeça (peso cresce suave com o zoom, sem salto)
    peso = d.suave(d.limitar((cam["z"] - Z_TELA - 0.01) / 0.14))
    ro = _rosto_mundo(est, c.g, c.t)
    olhos = (ro["y0"] - cam["vy0"]) * k                 # topo da caixa do rosto na tela
    topo = (ro["topo"] - cam["vy0"]) * k
    Y0n = max(Y0, 0.115 * H)
    if peso > 0:
        # atrás da pessoa pode encostar no alto do cabelo/boné; à frente (etiqueta) só até a testa
        lim = olhos - 0.012 * H if frente else topo + 0.35 * (olhos - topo)
        if Y0n + bh * s > lim:
            s_v = max(0.0, (lim - Y0n) / max(1.0, bh))
            s = min(s, 1 - peso * (1 - s_v))
    s_min = min(1.0, 0.05 * W / max(1.0, r["fs"] * esc))  # piso: letra com 5% da largura
    s = max(s, s_min)
    X0n = d.limitar(X0, 0.065 * W, 0.875 * W - bw * s)
    # esmaece só se, no piso de tamanho, a base ainda descer sobre o rosto
    if peso > 0:
        sobra = Y0n + bh * s - (olhos - 0.01 * H)
        op *= 1 - peso * d.suave(d.limitar(sobra / (0.02 * H)))
    esc2 = esc * s
    return X0n - bx0 * esc2, Y0n - by0 * esc2, esc2, op


def _desenhar_titulos(c, est, cam, img, frente):
    t = c.t
    W, H = c.W, c.H
    sw = est["sw"]
    for i, r in enumerate(est["tits"]):
        if not (r["ini"] <= t <= r["fim"]) or r["frente"] != frente:
            continue
        p_dig = d.mapear(t, r["ini"], r["ini"] + r["dig"])
        m = r["n"] if p_dig >= 1 else int(r["n"] * p_dig)
        k_in = d.saida(d.mapear(t, r["ini"], r["ini"] + 0.16))
        k_out = d.entrada(d.mapear(t, r["fim"] - 0.26, r["fim"]))
        op = k_in * (1 - k_out)
        sx, sy, esc, op = _lugar_titulo(c, est, cam, r, frente, op)
        sy -= 10 * k_out * cam["k"]
        if op <= 0.01:
            continue
        if frente and "etiqueta" in r:
            et, dx, dy = r["etiqueta"]
            _sobrepor(img, _escalado(est, ("etq", i), et, esc), (sx + dx * esc, sy + dy * esc), op)
        if m > 0:
            rev = _titulo_revelado(est, i, max(m, 0))
            _sobrepor(img, _escalado(est, ("tit", i, min(m, r["n"])), rev, esc), (sx, sy), op)
        # cursor de digitação: aparece digitando e pisca um pouco depois
        if t < r["ini"] + r["dig"] + 0.7 and op > 0.3:
            pisca = p_dig < 1 or ((t - r["ini"] - r["dig"]) * 2.4) % 1 < 0.6
            if pisca:
                cx_, cy_ = _cursor_titulo(r, max(m, 0))
                x0 = sx + cx_ * esc
                y0 = sy + (cy_ + r["fs"] * 0.14) * esc
                ImageDraw.Draw(img).rectangle([x0, y0, x0 + max(2, r["fs"] * 0.075 * esc),
                                               y0 + r["fs"] * 0.9 * esc], fill=d.cor(TINTA, op))


# ------------------------------------------------------------------ nota (cartão inclinado)

def _render_nota(est, e):
    sw = est["sw"]
    rot = str(e.get("rotulo", "")).strip().upper()
    txt = str(e.get("texto", "")).strip()
    pad = 30 * sw
    f, linhas, al = d.ajustar_texto(txt, 470 * sw, 2 * 60 * 1.06 * sw, 850, tam_max=int(60 * sw),
                                    tam_min=int(44 * sw), max_linhas=2, entrelinha=1.06)
    fr = d.fonte(int(38 * sw), 650)
    trk = 0.06 * fr.size
    lr = (fr.getlength(rot) + trk * max(0, len(rot) - 1)) if rot else 0
    lt = max(f.getlength(l) for l in linhas)
    iw = max(lt, lr, 300 * sw)
    h_rot = fr.size * 1.25 + 10 * sw if rot else 0
    w = iw + pad * 2
    h = pad + h_rot + al * len(linhas) + 20 * sw + 10 * sw + pad * 0.95
    card = d.painel(w, h, raio=int(20 * sw), fundo=NOTA, borda="#FFFFFF", larg_borda=max(1, int(2 * sw)))
    dr = ImageDraw.Draw(card)
    y = pad
    if rot:
        x = pad
        for chh in rot:
            dr.text((x, y), chh, font=fr, fill=ROTULO)
            x += fr.getlength(chh) + trk
        y += h_rot
    d.escrever(card, (pad, y - f.size * 0.08), linhas, f, TINTA, al=al)
    y += al * len(linhas) + 20 * sw
    dr.rounded_rectangle([pad, y, pad + iw * 0.82, y + 10 * sw], 5 * sw, fill=LIMA)
    girado = card.rotate(-5, resample=Image.BICUBIC, expand=True)
    sh, _ = d.sombra(girado, raio=22 * sw, opacidade=0.22, desloc=(0, 16 * sw))
    return {"img": sh, "wr": girado.width / sw, "hr": girado.height / sw, "ini": e["inicio"], "fim": e["fim"]}


def _camera_dict(est, z, cx, cy):
    DH = est["DH"]
    z = max(1.0, z)
    vw, vh = DW / z, DH / z
    cx = d.limitar(cx, vw / 2, DW - vw / 2)
    cy = d.limitar(cy, vh / 2, DH - vh / 2)
    return {"z": z, "cx": cx, "cy": cy, "vw": vw, "vh": vh, "vx0": cx - vw / 2, "vy0": cy - vh / 2,
            "k": z * est["W"] / DW}


def _lugar_nota(sx, sy, ws, hs, r, cam, W, H):
    """Posição final da nota na tela: dentro da zona segura, abaixo do queixo e NUNCA acima da linha
    da boca. Se não couber, desce um pouco sobre a margem da legenda ou encolhe até 15%."""
    k = cam["k"]
    queixo = (r["queixo"] - cam["vy0"]) * k
    boca = (r["y0"] + 0.88 * (r["y1"] - r["y0"]) - cam["vy0"]) * k
    sx = d.limitar(sx, 0.06 * W, 0.88 * W - ws)
    sy = min(max(sy, 0.12 * H, queixo + 0.02 * H), NOTA_BASE * H - hs)
    sy = max(sy, boca + 0.012 * H)
    esc = 1.0
    limite = 0.705 * H
    if sy + hs > limite:
        esc = max(0.85, (limite - sy) / hs)
    return sx, sy, esc


def _ancorar_notas(est, g):
    W, H = est["W"], est["H"]
    for i, n in enumerate(est["notas_r"]):
        tm = (n["ini"] + n["fim"]) / 2
        js = [j for j, m in enumerate(est["marcos"]) if m[1] == ("nota", i)]
        z = _z_marco(est, g, js[0]) if js else _z_alvo(("nota", i), tm, est, g)
        cx, cy = _enquadramento(("nota", i), tm, est, g, z)
        cam = _camera_dict(est, z, cx, cy)
        k = cam["k"]
        ws, hs = n["wr"] * k, n["hr"] * k
        r = _rosto_mundo(est, g, tm)
        queixo = (r["queixo"] - cam["vy0"]) * k
        sx, sy, _ = _lugar_nota(0.875 * W - ws, max(queixo + 0.025 * H, 0.42 * H), ws, hs, r, cam, W, H)
        n["ax"] = cam["vx0"] + sx / k
        n["ay"] = cam["vy0"] + sy / k


def _desenhar_notas(c, est, cam, img):
    t = c.t
    W, H = c.W, c.H
    sw = est["sw"]
    for n in est["notas_r"]:
        t_in = n["ini"] + 0.30
        if not (t_in <= t <= n["fim"]):
            continue
        p_in = d.mapear(t, t_in, t_in + 0.5)
        k_in = d.mola(p_in, 1.2)
        p_out = d.mapear(t, n["fim"] - 0.32, n["fim"])
        op = d.saida(d.mapear(t, t_in, t_in + 0.22)) * (1 - d.entrada(p_out))
        if op <= 0.01:
            continue
        k = cam["k"]
        ws, hs = n["wr"] * k, n["hr"] * k
        sx = (n["ax"] - cam["vx0"]) * k
        sy = (n["ay"] - cam["vy0"]) * k
        r = _rosto_mundo(est, c.g, t)
        sx, sy, encolhe = _lugar_nota(sx, sy, ws, hs, r, cam, W, H)
        if encolhe < 1:  # encolhe pelo canto de cima à direita (continua alinhada)
            sx += ws * (1 - encolhe)
            ws, hs = ws * encolhe, hs * encolhe
        sx += (1 - k_in) * 0.10 * W + d.entrada(p_out) * 0.05 * W
        esc = round(k / sw * encolhe, 3) * (0.94 + 0.06 * d.limitar(k_in, 0, 1.2))
        cartao = _escalado(est, ("nota", n["ini"]), n["img"], esc)
        d.colar(img, cartao, (sx + ws / 2, sy + hs / 2), opacidade=op)


# ------------------------------------------------------------------ câmera

def _z_alvo(alvo, t, est, g):
    """Zoom ideal de um foco no instante t (depende do tamanho/posição do rosto)."""
    DH = est["DH"]
    if alvo == "geral":
        return 1.0
    ty0 = est["L"]["tela"][1]
    r = _rosto_mundo(est, g, t)
    if alvo == "perto":
        z = min(Z_PERTO, (QUEIXO_MAX - CABECA_MIN) * DH / max(1.0, r["queixo"] - r["topo"]))
    elif isinstance(alvo, tuple) and alvo[0] == "nota":
        hn = est["notas_r"][alvo[1]]["hr"]
        z = min(Z_NOTA, (NOTA_BASE - TOPO_TELA - 0.03) * DH / max(1.0, r["queixo"] - ty0 + hn))
    else:
        z = min(Z_TELA, (QUEIXO_MAX - TOPO_TELA) * DH / max(1.0, r["queixo"] - ty0))
    return max(1.0, z)


def _z_marco(est, g, j):
    """Zoom fixo durante a visita j inteira (o mais restritivo do trecho). Câmera parada = zoom
    constante: o mundo é redimensionado uma vez e depois só recortado."""
    memo = est["memo_z"]
    if j not in memo:
        M = est["marcos"]
        t0, alvo = M[j]
        t1 = M[j + 1][0] if j + 1 < len(M) else g.duracao
        ts = np.arange(t0, max(t1, t0 + 0.01) + 1e-3, 0.25)
        memo[j] = round(min(_z_alvo(alvo, float(t), est, g) for t in ts), 4)
    return memo[j]


def _enquadramento(alvo, t, est, g, z):
    """Centro (x, y) da câmera em unidades do mundo para um foco com zoom z, no instante t."""
    DH = est["DH"]
    vw, vh = DW / z, DH / z
    if alvo == "geral":
        return (DW / 2, DH / 2)
    tx0, ty0, tx1, ty1 = est["L"]["tela"]
    if alvo == "perto":
        r = _rosto_mundo(est, g, t)
        cy = r["cy"] + 0.10 * vh
        cy = max(cy, r["queixo"] - (QUEIXO_MAX - 0.5) * vh)
        cy = min(cy, r["topo"] + (0.5 - CABECA_MIN) * vh)
        cx = r["cx"]
        if vw <= tx1 - tx0:
            cx = d.limitar(cx, tx0 + vw / 2, tx1 - vw / 2)
        return (cx, cy)
    cy = ty0 - TOPO_TELA * vh + vh / 2
    if isinstance(alvo, tuple) and alvo[0] == "nota":
        return (CX_TELA + 0.05 * vw, cy)
    return (CX_TELA, cy)


def _marcos(est):
    vis = []
    for e in est["cameras"]:
        vis.append((e["inicio"], e["fim"], e.get("foco", "tela"), 0))
    for i, n in enumerate(est["notas_r"]):
        vis.append((n["ini"], n["fim"], ("nota", i), 1))
    limites = sorted({0.0} | {v[0] for v in vis} | {v[1] for v in vis})
    marcos = []
    for b in limites:
        at = [v for v in vis if v[0] <= b + 1e-4 < v[1]]
        alvo = max(at, key=lambda v: (v[3], v[0]))[2] if at else "tela"
        if not marcos or marcos[-1][1] != alvo:
            marcos.append((b, alvo))
    # volta curtíssima para 'tela' entre duas visitas: pula (a câmera vai direto)
    limpo = []
    for j, m in enumerate(marcos):
        if m[1] == "tela" and j + 1 < len(marcos) and j > 0 and marcos[j + 1][0] - m[0] < 0.35:
            continue
        if limpo and limpo[-1][1] == m[1]:
            continue
        limpo.append(m)
    return limpo


def _duracao_mov(a, b):
    return 1.25 if "geral" in (a, b) else 0.95


def _estado(est, g, j, t):
    """((log zoom, cx, cy), progresso do movimento) no instante t, dentro da visita j."""
    t0, alvo = est["marcos"][j]
    z = _z_marco(est, g, j)
    cx, cy = _enquadramento(alvo, t, est, g, z)
    fim = (math.log(z), cx, cy)
    if j == 0:
        return fim, 1.0
    memo = est["memo_cam"]
    if j not in memo:
        memo[j] = _estado(est, g, j - 1, t0)[0]
    ini = memo[j]
    p = d.suave(d.mapear(t, t0, t0 + _duracao_mov(est["marcos"][j - 1][1], alvo)))
    return tuple(a + (b - a) * p for a, b in zip(ini, fim)), p


def _camera(est, g, t):
    j = max(0, bisect.bisect_right(est["marcos_t"], t) - 1)
    (lz, cx, cy), p = _estado(est, g, j, t)
    parado = p >= 1.0
    z = _z_marco(est, g, j) if parado else math.exp(lz)
    # câmera viva: deriva mínima (só deslocamento, para não reamostrar o quadro inteiro)
    cx += 4 * d.ruido(t, 12, 0.10)
    cy += 4 * d.ruido(t, 13, 0.09)
    cam = _camera_dict(est, z, cx, cy)
    cam["parado"] = cam["nativo"] = False
    if parado:  # encaixa na grade de pixels: o mundo e a pessoa andam juntos, sem tremer
        k = cam["k"]
        cam = _camera_dict(est, z, round(cam["vx0"] * k) / k + cam["vw"] / 2,
                           round(cam["vy0"] * k) / k + cam["vh"] / 2)
        cam["parado"] = True
        cam["nativo"] = abs(z - Z_TELA) < 1e-6
    return cam


def _mundo_em(est, k):
    """O mundo inteiro já redimensionado para a escala k (guardado enquanto a câmera fica parada)."""
    chave = round(k, 5)
    cache = est["mundo_z"]
    if chave not in cache:
        if len(cache) >= 3:
            cache.pop(next(iter(cache)))
        m = est["mundo_rgb"]
        f = k / est["sw"]
        cache[chave] = m.resize((max(1, int(round(m.width * f))), max(1, int(round(m.height * f)))),
                                Image.BILINEAR)
    return cache[chave]


# ------------------------------------------------------------------ pessoa dentro da tela principal

_CANTOS = {}


def _canto(r):
    if r not in _CANTOS:
        m = d.mascara_arredondada(2 * r, 2 * r, r)
        _CANTOS[r] = [m.crop((0, 0, r, r)), m.crop((r, 0, 2 * r, r)), m.crop((r, r, 2 * r, 2 * r)),
                      m.crop((0, r, r, 2 * r))]
    return _CANTOS[r]


def _tronco_poligono(est, g, t, q):
    """Silhueta de ombros/peito (resolução 1/q), guardada por décimo de segundo (o rosto já é suavizado)."""
    chave = round(t * 10)
    cache = est["cache_tronco"]
    if chave in cache:
        return cache[chave]
    W, H = est["W"], est["H"]
    fx0, fy0, fx1, fy1 = _rosto_fr(g, chave / 10)
    fw, fh = (fx1 - fx0) * W / q, (fy1 - fy0) * H / q
    cx, yq = (fx0 + fx1) / 2 * W / q, (fy1 + 0.02 * (fy1 - fy0)) * H / q
    pw, ph = W // q + 1, H // q + 1
    ss = 2  # desenha com sobreamostragem: contorno liso, sem degraus
    tr = Image.new("L", (pw * ss, ph * ss), 0)
    pts = [(cx - 0.30 * fw, yq - 0.25 * fh), (cx + 0.30 * fw, yq - 0.25 * fh),
           (cx + 0.42 * fw, yq + 0.06 * fh), (cx + 0.80 * fw, yq + 0.30 * fh),
           (cx + 1.18 * fw, yq + 0.52 * fh), (cx + 1.42 * fw, yq + 0.95 * fh),
           (cx + 1.50 * fw, ph + 2), (cx - 1.50 * fw, ph + 2),
           (cx - 1.42 * fw, yq + 0.95 * fh), (cx - 1.18 * fw, yq + 0.52 * fh),
           (cx - 0.80 * fw, yq + 0.30 * fh), (cx - 0.42 * fw, yq + 0.06 * fh)]
    ImageDraw.Draw(tr).polygon([(x * ss, y * ss) for x, y in pts], fill=255)
    tr = tr.resize((pw, ph), Image.BOX).filter(ImageFilter.GaussianBlur(max(1.0, fw * 0.035)))
    if len(cache) > 600:
        cache.clear()
    cache[chave] = tr
    return tr


def _suavizar_borda(pm, W):
    """Borda da máscara macia (sem cara de recortado com tesoura) e um leve aperto para não lavar o corpo."""
    caixa = pm.getbbox()                 # só a região da pessoa (fora dela é tudo zero)
    if not caixa:
        return pm
    w, h = pm.size
    m = max(4, int(0.012 * W))
    x0, y0 = max(0, caixa[0] - m) // 2 * 2, max(0, caixa[1] - m) // 2 * 2
    x1, y1 = min(w, caixa[2] + m), min(h, caixa[3] + m)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return pm
    # metade da resolução (a máscara já vem de um vídeo menor), desfoque ~0,4% de W, aperto, volta ao tamanho
    peq = pm.crop((x0, y0, x1, y1)).reduce(2)
    peq = peq.filter(ImageFilter.BoxBlur(max(1, int(round(0.002 * W))))).point(_APERTO)
    out = Image.new("L", (w, h), 0)
    out.paste(peq.resize((x1 - x0, y1 - y0), Image.BILINEAR), (x0, y0))
    return out


_APERTO = [min(255, int(v * 1.15)) for v in range(256)]


def _tronco_seguro(est, c, pm, box, tam):
    """Se o recorte perdeu o corpo (só a cabeça "flutuando"), completa ombros e peito com um tronco
    suave desenhado a partir do rosto. Com recorte bom (corpo presente) não muda nada."""
    q = 4
    tr = _tronco_poligono(est, c.g, c.t, q)
    cx0, cy0, cx1, cy1 = (v / q for v in box)
    if cx1 - cx0 < 1 or cy1 - cy0 < 1:
        return pm
    peq = (max(1, tam[0] // 8), max(1, tam[1] // 8))
    a_tr = np.asarray(tr.resize(peq, Image.BILINEAR, box=(cx0, cy0, cx1, cy1)), dtype=np.float32) / 255
    a_pm = np.asarray(pm.resize(peq, Image.BILINEAR), dtype=np.float32) / 255
    soma = float(a_tr.sum())
    if soma < 4:
        return pm
    cob = float((a_tr * a_pm).sum()) / soma
    fator = d.limitar((0.55 - cob) / 0.35)
    if fator <= 0.01:
        return pm
    trg = tr.resize(tam, Image.BILINEAR, box=(cx0, cy0, cx1, cy1))
    if fator < 0.99:
        trg = trg.point(lambda v: int(v * fator))
    return ImageChops.lighter(pm, trg)


def _desenhar_pessoa(c, est, cam, img):
    W, H = c.W, c.H
    k = cam["k"]
    a = est["sp"] * cam["z"]                      # pixels da tela por pixel do vídeo
    offx = (est["px0"] - cam["vx0"]) * k
    offy = (est["py0"] - cam["vy0"]) * k
    tx0, ty0, tx1, ty1 = est["L"]["tela"]
    sx0, sy0 = (tx0 - cam["vx0"]) * k, (ty0 - cam["vy0"]) * k
    sx1, sy1 = (tx1 - cam["vx0"]) * k, (ty1 - cam["vy0"]) * k
    R0 = int(math.ceil(max(sx0, offx, 0) - 1e-6))
    R1 = int(math.ceil(max(sy0, offy, 0) - 1e-6))
    R2 = int(math.floor(min(sx1, offx + W * a, W) + 1e-6))
    R3 = int(math.floor(min(sy1, offy + H * a, H) + 1e-6))
    if R2 - R0 < 2 or R3 - R1 < 2:
        return
    tam = (R2 - R0, R3 - R1)
    usar_mascara = est["recorte"] and c.mascara is not None
    if abs(a - 1) < 1e-4:                         # parado na 'tela': recorte exato, nitidez total
        bx, by = int(round(R0 - offx)), int(round(R1 - offy))
        box = (bx, by, bx + tam[0], by + tam[1])
        rgb = c.fonte.crop(box)                   # já é RGBA: cola direto com a máscara (sem converter)
        pm = c.mascara.crop(box) if usar_mascara else None
    else:
        box = ((R0 - offx) / a, (R1 - offy) / a, (R2 - offx) / a, (R3 - offy) / a)
        e0, e1 = max(0, int(box[0]) - 2), max(0, int(box[1]) - 2)
        e2, e3 = min(W, int(math.ceil(box[2])) + 2), min(H, int(math.ceil(box[3])) + 2)
        parte = c.fonte.crop((e0, e1, e2, e3)).convert("RGB")
        andando = not cam["parado"]
        if a < 0.97:      # reduzindo: média de área com a câmera andando (leve), bilinear parada
            filtro = Image.BOX if andando else Image.BILINEAR
        elif a > 1.03:    # ampliando: bicúbico parado, bilinear andando
            filtro = Image.BILINEAR if andando else Image.BICUBIC
        else:
            filtro = Image.BILINEAR
        rgb = parte.resize(tam, filtro, box=(box[0] - e0, box[1] - e1, box[2] - e0, box[3] - e1))
        fm = Image.BOX if (andando and a < 0.97) else Image.BILINEAR
        pm = c.mascara.resize(tam, fm, box=box) if usar_mascara else None
    if pm is not None:
        pm = _suavizar_borda(_tronco_seguro(est, c, pm, box, tam), W)
    else:
        pm = Image.new("L", tam, 255)
    # cantos arredondados da tela principal
    raio = int(round(18 * k))
    if raio >= 2:
        cantos = _canto(raio)
        for q, (cx_, cy_) in enumerate(((sx0, sy0), (sx1 - raio, sy0), (sx1 - raio, sy1 - raio), (sx0, sy1 - raio))):
            x, y = int(round(cx_ - R0)), int(round(cy_ - R1))
            if x + raio <= 0 or y + raio <= 0 or x >= tam[0] or y >= tam[1]:
                continue
            reg = (max(0, x), max(0, y), min(tam[0], x + raio), min(tam[1], y + raio))
            mq = cantos[q].crop((reg[0] - x, reg[1] - y, reg[2] - x, reg[3] - y))
            pm.paste(ImageChops.multiply(pm.crop(reg), mq), reg[:2])
    img.paste(rgb, (R0, R1), pm)


# ------------------------------------------------------------------ peças dinâmicas do aplicativo

def _desenhar_progresso(c, est, cam, img):
    cheia, fx0, fy0, fx1 = est["cheia"]
    bx0, by0, bx1, by1 = est["barra"]
    k = cam["k"]
    if (by0 - cam["vy0"]) * k > c.H or (by1 - cam["vy0"]) * k < 0:
        return
    sw = est["sw"]
    p = d.limitar(c.t / max(0.1, c.g.duracao))
    xw = fx0 + p * (fx1 - fx0)
    wpx = int((xw - fx0) * sw)
    if wpx > 1:
        parte = cheia.crop((0, 0, wpx, cheia.height))
        esc = k / sw
        parte = parte.resize((max(1, int(parte.width * esc)), max(1, int(parte.height * esc))), Image.BILINEAR)
        d.colar_em(img, parte, ((fx0 - cam["vx0"]) * k, (fy0 - cam["vy0"]) * k))
    # agulha de reprodução
    x = (xw - cam["vx0"]) * k
    lw = max(2, int(3 * k))
    ImageDraw.Draw(img).rounded_rectangle([x - lw / 2, (by0 + 6 - cam["vy0"]) * k, x + lw / 2,
                                           (by1 - 6 - cam["vy0"]) * k], lw / 2, fill=d.cor("#FFFFFF", 0.9))


def _desenhar_menu(c, est, cam, img):
    k = cam["k"]
    mx0 = est["L"]["menu"][0]
    if (est["L"]["menu"][2] - cam["vx0"]) * k < 0 or (mx0 - cam["vx0"]) * k > c.W:
        return
    t = c.t
    inis = est["tit_inis"]
    n = bisect.bisect_right(inis, t)
    idx = n % 4
    pop = 1.0
    if n > 0:
        pop = 0.7 + 0.3 * d.mola(d.mapear(t, inis[n - 1], inis[n - 1] + 0.3), 1.8)
    q = est["menu_ativo"][idx]
    mx, my = est["menu_pos"][idx]
    esc = k / est["sw"] * pop
    d.colar(img, q, ((mx - cam["vx0"]) * k, (my - cam["vy0"]) * k), escala=esc)


# ------------------------------------------------------------------ legenda digitada (palavra por palavra)

def _paginas(g):
    pal = g.palavras or []
    if not pal:
        return []
    pags = []
    for gr in agrupar(pal, 22, 2, 0.45):
        ws = gr["palavras"]
        n = max(1, math.ceil(len(ws) / 4))
        base, extra = divmod(len(ws), n)
        partes, i = [], 0
        for j in range(n):
            q = base + (1 if j < extra else 0)
            partes.append(ws[i:i + q])
            i += q
        for j, pt in enumerate(partes):
            fim = partes[j + 1][0]["inicio"] if j + 1 < len(partes) else gr["fim"]
            pags.append({"palavras": pt, "inicio": pt[0]["inicio"], "fim": fim})
    return pags


def _layout_pagina(est, pg):
    W = est["W"]
    f = est["leg_fonte"]
    larg_max = 0.80 * W - 2 * est["leg_padx"] - 0.02 * W
    txts = [w["texto"] for w in pg["palavras"]]
    linhas, atual = [], []
    for i, tx in enumerate(txts):
        teste = " ".join(txts[j] for j in atual + [i])
        if atual and f.getlength(teste) > larg_max:
            linhas.append(atual)
            atual = []
        atual.append(i)
    if atual:
        linhas.append(atual)
    linhas = linhas[:2] if len(linhas) <= 2 else [linhas[0], sum(linhas[1:], [])]
    al = f.size * 1.16
    larg = max(f.getlength(" ".join(txts[i] for i in ln)) for ln in linhas)
    pg["_lay"] = {"txts": txts, "linhas": linhas, "al": al,
                  "w": int(larg + 2 * est["leg_padx"] + 0.022 * W),
                  "h": int(al * len(linhas) + 2 * est["leg_pady"])}
    return pg["_lay"]


def _img_pagina(est, ip, n, ativo):
    chave = ("e03_leg", ip, n, ativo)
    cache = est["cache_leg"]
    if chave in cache:
        return cache[chave]
    pg = est["paginas"][ip]
    lay = pg.get("_lay") or _layout_pagina(est, pg)
    f = est["leg_fonte"]
    img = d.painel(lay["w"], lay["h"], raio=int(0.012 * est["W"]), fundo=LEG_CAIXA)
    cursor = (est["leg_padx"], est["leg_pady"])
    for li, ln in enumerate(lay["linhas"]):
        x = est["leg_padx"]
        y = est["leg_pady"] + li * lay["al"] - f.size * 0.05
        for i in ln:
            tx = lay["txts"][i]
            if i < n:
                d.escrever(img, (x, y), [tx], f, LEG_ATIVA if i == ativo else LEG_COR)
                cursor = (x + f.getlength(tx) + f.size * 0.12, y)
            x += f.getlength(tx + " ")
    if len(cache) > 400:
        cache.clear()
    cache[chave] = (img, cursor)
    return cache[chave]


def _desenhar_legenda(c, est, img):
    if not est["leg_ativa"] or not est["paginas"]:
        return
    t = c.t
    j = bisect.bisect_right(est["pag_inis"], t + 0.04) - 1
    if j < 0:
        return
    pg = est["paginas"][j]
    if t >= pg["fim"]:
        return
    ws = pg["palavras"]
    n = sum(1 for w in ws if w["inicio"] - 0.03 <= t)
    if n == 0:
        n = 1
    ativo = None
    for i, w in enumerate(ws):
        if w["inicio"] - 0.03 <= t < max(w["fim"], w["inicio"] + 0.12):
            ativo = i
    cam, (cx, cy) = _img_pagina(est, j, n, ativo)
    W, H = c.W, c.H
    k_in = d.saida(d.mapear(t, pg["inicio"] - 0.04, pg["inicio"] + 0.14))
    colada = j > 0 and est["paginas"][j - 1]["fim"] >= pg["inicio"] - 0.06
    op_in = 1.0 if colada else k_in          # páginas seguidas: a caixa fica, só o texto troca
    prox = est["paginas"][j + 1]["inicio"] if j + 1 < len(est["paginas"]) else 1e9
    k_out = d.entrada(d.mapear(t, pg["fim"] - 0.14, pg["fim"])) if prox > pg["fim"] + 0.05 else 0.0
    op = op_in * (1 - k_out)
    x = 0.07 * W
    y = LEG_BASE * H - cam.height + (1 - k_in) * (0.005 if colada else 0.012) * H
    d.colar_em(img, cam, (x, y), op)
    # cursor discreto
    ult = max((w["inicio"] for w in ws if w["inicio"] - 0.03 <= t), default=pg["inicio"])
    if (t - ult) < 0.25 or (t * 2.4) % 1 < 0.6:
        f = est["leg_fonte"]
        x0 = x + cx
        y0 = y + cy + f.size * 0.16
        ImageDraw.Draw(img).rectangle([x0, y0, x0 + max(2, f.size * 0.07), y0 + f.size * 0.92],
                                      fill=d.cor(LEG_ATIVA, op))


# ------------------------------------------------------------------ preparo e quadro

def preparar(g):
    W, H = g.W, g.H
    DH = DW * H / W
    est = {"W": W, "H": H, "DH": DH, "L": _layout(DH), "sw": F * W / DW, "recorte": bool(g.tem_mascara),
           "memo_rosto": {}, "memo_cam": {}, "memo_z": {}, "mundo_z": {}, "cache_tit": {}, "cache_leg": {},
           "cache_esc": {}, "cache_tronco": {}}
    plano = g.plano
    est["cameras"] = _por_tipo(plano, "camera")
    est["titulos"] = _por_tipo(plano, "titulo")
    est["notas"] = _por_tipo(plano, "nota")
    g.cache["e03"] = est
    _posicionar_pessoa(est, g)
    est["mundo"] = _desenhar_mundo(est)            # RGBA: recorte direto quando a câmera está parada
    est["mundo_rgb"] = est["mundo"].convert("RGB")  # RGB: redimensiona 2x mais rápido nos movimentos
    est["tits"] = _preparar_titulos(est, g)
    est["tit_inis"] = [r["ini"] for r in est["tits"]]
    est["notas_r"] = [_render_nota(est, e) for e in est["notas"]]
    est["marcos"] = _marcos(est)
    est["marcos_t"] = [m[0] for m in est["marcos"]]
    _ancorar_notas(est, g)
    est["leg_ativa"] = bool((plano.get("legenda") or {}).get("ativa", True))
    est["paginas"] = _paginas(g)
    est["pag_inis"] = [p["inicio"] for p in est["paginas"]]
    est["leg_fonte"] = d.fonte(int(round(0.06 * W)), 650)
    est["leg_padx"] = 0.032 * W
    est["leg_pady"] = 0.02 * W


def quadro(c):
    g = c.g
    est = g.cache.get("e03")
    if est is None:
        preparar(g)
        est = g.cache["e03"]
    cam = _camera(est, g, c.t)
    sw = est["sw"]
    if cam["parado"]:  # câmera parada: só recorta (o mundo já está na escala certa)
        mz = est["mundo"] if cam["nativo"] else _mundo_em(est, cam["k"])
        esc = sw if cam["nativo"] else cam["k"]
        x0 = min(max(0, int(round(cam["vx0"] * esc))), max(0, mz.width - c.W))
        y0 = min(max(0, int(round(cam["vy0"] * esc))), max(0, mz.height - c.H))
        img = mz.crop((x0, y0, x0 + c.W, y0 + c.H))
    else:
        caixa = (cam["vx0"] * sw, cam["vy0"] * sw, (cam["vx0"] + cam["vw"]) * sw, (cam["vy0"] + cam["vh"]) * sw)
        # em movimento: filtro de área (mais leve) quando reduz; o olho não vê diferença com a câmera andando.
        # (medido: uma pirâmide de escalas pré-reduzidas não acelera — o custo é o tamanho da saída)
        filtro = Image.BOX if cam["k"] < sw / 1.05 else Image.BILINEAR
        img = est["mundo_rgb"].resize((c.W, c.H), filtro, box=caixa)
    if est["recorte"] and c.mascara is not None:
        _desenhar_titulos(c, est, cam, img, frente=False)
        _desenhar_pessoa(c, est, cam, img)
        img = img if img.mode == "RGBA" else img.convert("RGBA")
        _desenhar_titulos(c, est, cam, img, frente=True)
    else:
        _desenhar_pessoa(c, est, cam, img)
        img = img if img.mode == "RGBA" else img.convert("RGBA")
        _desenhar_titulos(c, est, cam, img, frente=False)
        _desenhar_titulos(c, est, cam, img, frente=True)
    _desenhar_progresso(c, est, cam, img)
    _desenhar_menu(c, est, cam, img)
    _desenhar_notas(c, est, cam, img)
    _desenhar_legenda(c, est, img)
    return img
