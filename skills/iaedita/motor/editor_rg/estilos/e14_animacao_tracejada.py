"""14 · Animação tracejada — desenhos feitos à mão em volta da pessoa, com o tremido da animação
quadro a quadro ("doodle boil"): contorno da silhueta, setas, estrelas, corações, sublinhados,
notas escritas com seta e títulos sublinhados. Paleta da prévia aprovada: tinta #222729,
creme #F5F1DD, rosa #E9A3BC, lima #D4ED80.

Com recorte: o fundo escurece um pouco (a pessoa fica em destaque), a linha creme contorna a
silhueta e os desenhos na altura da cabeça ficam "na parede", ATRÁS da pessoa.
Sem recorte: o contorno vira um círculo feito à mão em volta da cabeça (ou cantoneiras, se o
círculo não couber) e todos os desenhos ficam na frente, sempre fora do rosto.

Tudo é função só do tempo: o tremido troca de desenho 10 vezes por segundo num ciclo de 3
variantes (como na animação tradicional), e cada variante pronta fica em cache."""
from __future__ import annotations

import math
import multiprocessing

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import desenho as d

TINTA = "#222729"
CREME = "#F5F1DD"
ROSA = "#E9A3BC"
LIMA = "#D4ED80"
SOMBRA = "#121516"
CORES = {"creme": CREME, "rosa": ROSA, "lima": LIMA}

FERVURA_HZ = 10    # o traço "ferve" 10x por segundo (a cada 3 quadros em 30 fps)
VARIANTES = 3      # ciclo de 3 desenhos
PASSOS_HZ = 15     # o lápis avança 15 vezes por segundo ("em dois")

FORMAS_VALIDAS = ("coracao", "estrela", "seta", "claquete", "raio", "lampada", "balao", "check", "x",
                  "exclamacao", "interrogacao", "cifrao", "grafico", "brilhos")

INFO = {
    "id": "14-animacao-tracejada",
    "nome": "Animação tracejada",
    "precisa_recorte": True,
    "antes": 0.05,
    "depois": 0.05,
    "legenda": {"peso": 850, "tamanho": 0.062, "cor": "#F8F7F0", "destaque": ROSA, "caixa": "#222729EE",
                "max_caracteres": 17, "max_linhas": 2, "animacao": "pop"},
    "eventos": {
        "contorno": "inicio, fim (1,5-5 s), cor ('creme' padrão | 'rosa' | 'lima'), som — linha feita à mão "
                    "que se desenha em volta da silhueta da pessoa e treme",
        "desenho": "inicio, fim (1,2-3 s), forma (coracao|estrela|seta|claquete|raio|lampada|balao|check|x|"
                   "exclamacao|interrogacao|cifrao|grafico|brilhos), lado ('auto'|'esquerda'|'direita'), "
                   "tamanho (1 pequeno | 2 padrão | 3 grande), cor (opcional), som",
        "nota": "inicio, fim (1,4-2,5 s), texto (1-3 palavras, até 18 letras), lado ('auto'|'esquerda'|'direita'), "
                "cor (cor da seta, opcional), som — palavra escrita com seta desenhada apontando para a pessoa "
                "(só 1 nota ou título na tela por vez, além da legenda)",
        "titulo": "inicio, fim (1,8-3 s), texto (2-5 palavras, até 28 letras), marca (1 palavra do texto, "
                  "opcional), posicao ('auto'|'topo'|'baixo'), som — título grande com sublinhado feito à mão",
        "aura": "inicio, fim (0,8-2 s), cor (opcional, padrão 'lima'), som — riscos de energia em volta da "
                "cabeça (momento de impacto)",
    },
}

LIMITES = {  # duração mínima e máxima (s) de cada tipo
    "contorno": (1.2, 8.0), "desenho": (0.9, 5.0), "nota": (1.0, 4.0), "titulo": (1.2, 4.5), "aura": (0.6, 3.0),
}


# ------------------------------------------------------------------ validação do plano

def _norm(p):
    return str(p).strip(".,!?;:\"'“”‘’()").lower()


def validar(plano, duracao):
    p = []
    evs = plano.get("eventos", [])
    for e in evs:
        tipo = e.get("tipo")
        if tipo not in LIMITES:
            continue
        ini, fim = float(e.get("inicio", 0)), float(e.get("fim", 0))
        dmin, dmax = LIMITES[tipo]
        if fim - ini < dmin - 1e-6:
            p.append(f"{tipo} em {ini:.2f}s dura {fim - ini:.2f}s: precisa de pelo menos {dmin:.1f}s "
                     f"(o traço leva tempo para se desenhar).")
        if fim - ini > dmax + 1e-6:
            p.append(f"{tipo} em {ini:.2f}s dura {fim - ini:.2f}s: no máximo {dmax:.1f}s.")
        cor = e.get("cor")
        if cor is not None and str(cor).lower() not in CORES:
            p.append(f"{tipo} em {ini:.2f}s: cor '{cor}' não existe (use creme, rosa ou lima).")
        if tipo == "desenho":
            forma = str(e.get("forma", "")).lower()
            if forma not in FORMAS_VALIDAS:
                p.append(f"desenho em {ini:.2f}s: forma '{e.get('forma')}' não existe. Formas: {', '.join(FORMAS_VALIDAS)}.")
            if "tamanho" in e and str(e.get("tamanho")) not in ("1", "2", "3", "1.0", "2.0", "3.0"):
                p.append(f"desenho em {ini:.2f}s: tamanho '{e.get('tamanho')}' não existe (use 1, 2 ou 3).")
        lado = str(e.get("lado", "auto")).lower()
        if tipo in ("desenho", "nota") and lado not in ("auto", "esquerda", "direita"):
            p.append(f"{tipo} em {ini:.2f}s: lado '{e.get('lado')}' não existe (use auto, esquerda ou direita).")
        if tipo == "titulo" and str(e.get("posicao", "auto")).lower() not in ("auto", "topo", "baixo"):
            p.append(f"titulo em {ini:.2f}s: posicao '{e.get('posicao')}' não existe (use auto, topo ou baixo).")
        if tipo in ("nota", "titulo"):
            txt = str(e.get("texto", "")).strip()
            n_pal, n_car = len(txt.split()), len(txt)
            if not txt:
                p.append(f"{tipo} em {ini:.2f}s sem texto.")
            elif tipo == "nota" and (n_pal > 3 or n_car > 18):
                p.append(f"nota em {ini:.2f}s longa demais ('{txt}'): até 3 palavras e 18 letras.")
            elif tipo == "titulo" and (n_pal > 5 or n_car > 28):
                p.append(f"titulo em {ini:.2f}s longo demais ('{txt}'): até 5 palavras e 28 letras.")
            if tipo == "titulo" and e.get("marca"):
                if _norm(e["marca"]) not in [_norm(x) for x in txt.split()]:
                    p.append(f"titulo em {ini:.2f}s: a marca '{e['marca']}' não é uma palavra do texto.")
    cont = sorted((e for e in evs if e.get("tipo") == "contorno"), key=lambda e: e["inicio"])
    for a, b in zip(cont, cont[1:]):
        if b["inicio"] < a["fim"] - 0.01:
            p.append(f"Contornos sobrepostos em {b['inicio']:.2f}s: um precisa terminar antes do outro começar.")
    # no máximo 1 texto do estilo (nota ou título) na tela ao mesmo tempo, além da legenda
    txts = sorted((e for e in evs if e.get("tipo") in ("nota", "titulo")), key=lambda e: float(e.get("inicio", 0)))
    for a, b in zip(txts, txts[1:]):
        if float(b["inicio"]) < float(a["fim"]) - 0.01:
            p.append(f"{b.get('tipo')} '{b.get('texto', '')}' em {float(b['inicio']):.2f}s começa antes de "
                     f"'{a.get('texto', '')}' sumir ({float(a['fim']):.2f}s): só 1 nota ou título por vez "
                     "(além da legenda), senão os textos se amontoam. Mude o momento ou troque por um 'desenho'.")
    # no máximo 3 elementos (desenho/nota/título) na tela ao mesmo tempo
    elem = [e for e in evs if e.get("tipo") in ("desenho", "nota", "titulo")]
    for e in elem:
        t = float(e["inicio"]) + 0.01
        juntos = [x for x in elem if x["inicio"] <= t < x["fim"]]
        if len(juntos) > 3:
            p.append(f"Em {t:.2f}s há {len(juntos)} desenhos/notas/títulos juntos: no máximo 3 (fica poluído).")
            break
    return p


# ------------------------------------------------------------------ ruído e geometria dos traços

def _rv(x, semente):
    """Ruído suave vetorizado em [-1, 1] (mesma ideia de desenho.ruido, para muitos pontos)."""
    x = np.asarray(x, np.float64)
    i = np.floor(x).astype(np.int64)
    f = x - i
    s = int(semente) & 0xFFFFF

    def h(n):
        n = (n * 374761393 + s * 668265263) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 0xFFFF) / 32767.5 - 1.0
    u = f * f * (3 - 2 * f)
    return h(i) * (1 - u) + h(i + 1) * u


def _cum(p):
    if len(p) < 2:
        return np.zeros(len(p))
    seg = np.hypot(*(np.diff(p, axis=0).T))
    return np.concatenate([[0.0], np.cumsum(seg)])


def _bez(p0, p1, p2, p3, n=26):
    t = np.linspace(0.0, 1.0, n)[:, None]
    p0, p1, p2, p3 = (np.asarray(v, np.float64) for v in (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3


def _reta(a, b, n=10):
    t = np.linspace(0.0, 1.0, n)[:, None]
    return np.asarray(a, np.float64) * (1 - t) + np.asarray(b, np.float64) * t


def _arco(cx, cy, rx, ry, a0, a1, n=44):
    a = np.radians(np.linspace(a0, a1, n))
    return np.stack([cx + rx * np.cos(a), cy + ry * np.sin(a)], 1)


def _juntar(*partes):
    out = [np.asarray(partes[0], np.float64)]
    for p in partes[1:]:
        p = np.asarray(p, np.float64)
        out.append(p[1:] if np.allclose(out[-1][-1], p[0]) else p)
    return np.concatenate(out)


def _poli(vertices, fechar=0.0, n=9):
    """Polilinha pelos vértices; fechar>0 volta ao início e passa um pouco do ponto (traço de mão)."""
    v = [np.asarray(x, np.float64) for x in vertices]
    if fechar:
        v = v + [v[0], v[0] + (v[1] - v[0]) * fechar]
    return _juntar(*[_reta(a, b, n) for a, b in zip(v, v[1:])])


def _mao(p, semente, amp=0.011, freq=2.6):
    """Imperfeição fixa de traço feito à mão (não muda com o tempo)."""
    s = _cum(p) * freq
    return p + amp * np.stack([_rv(s, semente), _rv(s, semente + 11)], 1)


def _ferver(p, chave, amp, escala):
    """Tremido do quadro: desloca o traço com ruído suave ao longo do comprimento."""
    s = _cum(p) / escala + 0.5
    k = int(chave) * 7919
    um = np.full(len(p), 0.5)
    dx = _rv(s, k + 1) + 0.4 * _rv(um, k + 2)
    dy = _rv(s, k + 3) + 0.4 * _rv(um, k + 4)
    return p + amp * np.stack([dx, dy], 1)


def _ponta_seta(fim, anterior, comp, abertura=28):
    """Duas pernas da ponta da seta (uma polilinha: perna, ponta, perna)."""
    v = np.asarray(fim, float) - np.asarray(anterior, float)
    v = v / (np.hypot(*v) or 1)
    out = []
    for ang in (abertura, -abertura):
        a = math.radians(ang)
        r = np.array([v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a)])
        out.append(np.asarray(fim, float) - r * comp)
    return _juntar(_reta(out[0], fim, 6), _reta(fim, out[1], 6))


# ------------------------------------------------------------------ biblioteca de desenhos (coordenadas 0-1)
# Cada forma: aspecto (largura/altura), cor principal, cor de detalhe, se aponta para um lado, e a função
# que devolve (traços [(pontos, 'P'|'D', espessura)], preenchimentos [(índice do traço, 'P'|'D', alfa)]).
# Formas "direcionais" apontam para a DIREITA (para uma pessoa à direita); o motor espelha quando preciso.

def _f_coracao():
    c = _juntar(_bez((.53, .93), (.18, .68), (.0, .38), (.2, .17)), _bez((.2, .17), (.35, .03), (.5, .12), (.5, .3)),
                _bez((.5, .3), (.52, .1), (.72, .02), (.84, .16)), _bez((.84, .16), (1.0, .36), (.85, .66), (.45, .96)))
    return [(_mao(c, 3), "P", 1.0)], [(0, "P", .24)]


def _f_estrela():
    v = []
    for k in range(10):
        r = (.49 if k % 2 == 0 else .2) * (1 + .05 * math.sin(k * 2.3))
        a = math.radians(-90 + k * 36)
        v.append((.5 + r * math.cos(a), .53 + r * math.sin(a)))
    return [(_mao(_poli(v, fechar=.4, n=7), 5, .008), "P", 1.0)], [(0, "P", .2)]


def _f_seta():
    corpo = _bez((.05, .7), (.22, .12), (.62, .02), (.93, .4), 32)
    corpo = _mao(corpo, 7, .01)
    return [(corpo, "P", 1.05), (_ponta_seta(corpo[-1], corpo[-4], .3), "P", 1.05)], []


def _f_claquete():
    corpo = _poli([(0, .333), (1, .333), (1, 1), (0, 1)], fechar=.06)
    barra = _poli([(0, .333), (.886, 0), (.962, .204), (.076, .549)], fechar=.05)
    listras = [_reta(a, b, 6) for a, b in (((.223, .251), (.303, .412)), ((.439, .173), (.523, .337)),
                                          ((.659, .086), (.742, .247)))]
    tracos = [(_mao(corpo, 9, .007), "P", 1.0), (_mao(barra, 10, .007), "P", 1.0)]
    tracos += [(x, "P", .9) for x in listras]
    tracos += [(_reta((.075 + i * .1, .58), (.04 + i * .1, .9), 6), "D", .85) for i in range(9)]
    return tracos, []


def _f_raio():
    c = _poli([(.62, .02), (.12, .57), (.47, .57), (.3, .98), (.9, .4), (.55, .4), (.72, .02)], fechar=.3, n=8)
    return [(_mao(c, 13, .008), "P", 1.0)], [(0, "P", .26)]


def _f_lampada():
    cx, cy, r = .5, .47, .27
    bulbo = _arco(cx, cy, r, r, 128, 412, 46)
    e0, e1 = bulbo[0], bulbo[-1]
    pescoco_e = _reta(e0, (.39, .8), 6)
    pescoco_d = _reta(e1, (.61, .8), 6)
    tracos = [(_mao(_juntar(pescoco_e[::-1], bulbo, pescoco_d), 17, .008), "P", 1.0),
              (_reta((.36, .82), (.64, .82), 6), "P", .9), (_reta((.39, .9), (.61, .9), 6), "P", .9),
              (_reta((.45, .97), (.55, .97), 4), "P", .9),
              (_poli([(.41, .66), (.45, .53), (.5, .63), (.55, .53), (.59, .66)], n=5), "D", .8)]
    for a in (200, 236, 270, 304, 340):
        ar = math.radians(a)
        tracos.append((_reta((cx + .34 * math.cos(ar), cy + .34 * math.sin(ar)),
                             (cx + .45 * math.cos(ar), cy + .45 * math.sin(ar)), 4), "D", .9))
    return tracos, []


def _f_balao():
    arco = _arco(.5, .41, .47, .35, 112, 428, 52)
    ponta = (.78, .99)
    c = _juntar(arco, _reta(arco[-1], ponta, 6), _reta(ponta, arco[0] + np.array([.06, 0]), 6))
    tracos = [(_mao(c, 19, .008), "P", 1.0)]
    for x in (.3, .5, .7):  # três pontinhos de "falando"
        tracos.append((_arco(x, .42, .045 / 1.3, .045, 0, 340, 12), "D", 1.1))
    return tracos, [(0, "P", .14)]


def _f_check():
    circ = _arco(.5, .5, .45, .43, -100, 262, 54) * np.array([1, 1]) + 0
    circ = _mao(circ, 23, .012)
    marca = _poli([(.24, .5), (.43, .71), (.8, .26)], n=10)
    return [(circ, "D", .85), (_mao(marca, 29, .008), "P", 1.25)], []


def _f_x():
    a = _bez((.16, .14), (.4, .42), (.6, .58), (.86, .88))
    b = _bez((.84, .14), (.62, .36), (.4, .62), (.14, .87))
    return [(_mao(a, 31, .01), "P", 1.25), (_mao(b, 37, .01), "P", 1.25)], []


def _f_exclamacao():
    a = .42
    barra = _bez((.56, .04), (.53, .3), (.5, .5), (.48, .68))
    ponto = _arco(.47, .88, .07 / a, .07, 0, 350, 14)
    return [(barra, "P", 1.35), (ponto, "P", 1.2)], []


def _f_interrogacao():
    a = .62
    gancho = _juntar(_bez((.12, .32), (.08, .02), (.92, -.01), (.88, .3)), _bez((.88, .3), (.86, .5), (.5, .46), (.5, .7)))
    ponto = _arco(.5, .9, .055 / a, .055, 0, 350, 14)
    return [(_mao(gancho, 41, .008), "P", 1.2), (ponto, "P", 1.1)], []


def _f_cifrao():
    s = _juntar(_bez((.86, .2), (.62, .04), (.12, .1), (.18, .34)), _bez((.18, .34), (.26, .52), (.84, .46), (.84, .68)),
                _bez((.84, .68), (.84, .92), (.24, .96), (.12, .76)))
    return [(_mao(s, 43, .008), "P", 1.15), (_reta((.53, .0), (.48, 1.0), 8), "P", 1.15)], []


def _f_grafico():
    eixos = _poli([(.05, .04), (.05, .95), (.97, .95)], n=12)
    linha = _poli([(.14, .8), (.36, .56), (.52, .68), (.84, .24)], n=9)
    linha = _mao(linha, 47, .008)
    return [(eixos, "D", .9), (linha, "P", 1.1), (_ponta_seta(linha[-1], linha[-3], .2, 32), "P", 1.1)], []


def _f_brilhos():
    tracos = []
    for k, a in enumerate((192, 230, 268)):
        ar = math.radians(a)
        r0, r1 = .3, (.95 if k != 1 else 1.05)
        p0 = (1 + r0 * math.cos(ar), 1 + r0 * math.sin(ar))
        p1 = (1 + r1 * math.cos(ar), 1 + r1 * math.sin(ar))
        tracos.append((_reta(p0, p1, 7), "P", 1.15))
    return tracos, []


FORMAS = {  # nome: (aspecto, cor principal, cor detalhe, direcional, função)
    "coracao": (1.05, ROSA, ROSA, False, _f_coracao),
    "estrela": (1.0, LIMA, LIMA, False, _f_estrela),
    "seta": (1.25, ROSA, ROSA, True, _f_seta),
    "claquete": (1.04, CREME, ROSA, False, _f_claquete),
    "raio": (.66, LIMA, LIMA, False, _f_raio),
    "lampada": (.85, CREME, LIMA, False, _f_lampada),
    "balao": (1.3, CREME, ROSA, True, _f_balao),
    "check": (1.0, LIMA, CREME, False, _f_check),
    "x": (1.0, ROSA, ROSA, False, _f_x),
    "exclamacao": (.42, ROSA, ROSA, False, _f_exclamacao),
    "interrogacao": (.62, CREME, CREME, False, _f_interrogacao),
    "cifrao": (.62, LIMA, LIMA, False, _f_cifrao),
    "grafico": (1.15, LIMA, CREME, False, _f_grafico),
    "brilhos": (1.0, LIMA, LIMA, True, _f_brilhos),
}


# ------------------------------------------------------------------ desenhar traços (com tremido e "lápis" andando)

def _parte(tracos_px, preench, w, h, pos, larg, amp, sal=0, sombra=True):
    return {"tracos": tracos_px, "preench": preench, "tam": (int(math.ceil(w)), int(math.ceil(h))),
            "pos": (float(pos[0]), float(pos[1])), "larg": float(larg), "amp": float(amp), "sal": int(sal),
            "sombra": sombra}


def _forma_em_px(nome, caixa, cor_principal, espelho, W, margem):
    """Escala a forma para a caixa (x0,y0,x1,y1) da tela. Devolve traços em coordenadas locais da parte."""
    aspecto, cp, cd, _, fn = FORMAS[nome]
    tracos, preench = fn()
    x0, y0, x1, y1 = caixa
    h = y1 - y0
    w = x1 - x0
    out = []
    for pts, papel, mult in tracos:
        p = np.array(pts, np.float64)
        if espelho:
            p[:, 0] = 1.0 - p[:, 0]
        p = p * np.array([w, h]) + margem
        cor = cor_principal if papel == "P" else cd
        if papel == "P" and cor_principal is None:
            cor = cp
        out.append((p, d.cor(cor), mult))
    pre = []
    for idx, papel, alfa in preench:
        cor = (cor_principal or cp) if papel == "P" else cd
        pre.append((idx, d.cor(cor), alfa))
    return out, pre, w + 2 * margem, h + 2 * margem


def _render(parte, semente, prog, W, ss=None):
    """Desenha a parte até 'prog' (0-1 do comprimento total do traço), com o tremido da variante 'semente'."""
    w, h = parte["tam"]
    larg, amp = parte["larg"], parte["amp"]
    if ss is None:
        ss = 3 if max(w, h) < 640 else 2
    esc = W * 0.07
    fer = [_ferver(p, semente * 31 + i + parte["sal"] * 977, amp, esc) for i, (p, _, _) in enumerate(parte["tracos"])]
    cums = [_cum(p) for p in fer]
    total = sum(float(cu[-1]) if len(cu) else 0.0 for cu in cums) or 1.0
    resto = prog * total
    mascaras, ordem = {}, []
    for (_, cor_t, mult), p, cu in zip(parte["tracos"], fer, cums):
        if resto <= 1e-6 or len(p) < 2:
            break
        L = float(cu[-1])
        if resto < L:
            j = int(np.searchsorted(cu, resto))
            j = max(1, min(j, len(p) - 1))
            a = (resto - cu[j - 1]) / max(1e-9, cu[j] - cu[j - 1])
            q = p[j - 1] + (p[j] - p[j - 1]) * a
            p = np.vstack([p[:j], q[None]])
        resto -= L
        if cor_t not in mascaras:
            mascaras[cor_t] = Image.new("L", (w * ss, h * ss), 0)
            ordem.append(cor_t)
        dr = ImageDraw.Draw(mascaras[cor_t])
        lw = max(1, int(round(larg * mult * ss)))
        xy = [(float(x) * ss, float(y) * ss) for x, y in p]
        if len(xy) >= 2:
            dr.line(xy, fill=255, width=lw, joint="curve")
        r = lw / 2.0
        for (x, y) in (xy[0], xy[-1]):
            dr.ellipse((x - r, y - r, x + r, y + r), fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if not mascaras:
        return out
    alfas = {c: m.reduce(ss) for c, m in mascaras.items()}
    if parte.get("sombra", True):
        uni = None
        for a in alfas.values():
            uni = a if uni is None else ImageChops.lighter(uni, a)
        s = uni.filter(ImageFilter.GaussianBlur(max(1.0, larg * 0.9))).point(lambda v: int(v * 0.62))
        cam = Image.new("RGBA", (w, h), d.cor(SOMBRA))
        cam.putalpha(s)
        dy = max(1, int(larg * 0.35))
        out.alpha_composite(cam.crop((0, 0, w, h - dy)), (0, dy))
    # preenchimento translúcido entra no fim do traço
    if parte["preench"] and prog > 0.72:
        k = d.suave(d.mapear(prog, 0.72, 1.0))
        for idx, cor_p, alfa in parte["preench"]:
            if idx >= len(fer):
                continue
            m = Image.new("L", (w * ss, h * ss), 0)
            ImageDraw.Draw(m).polygon([(float(x) * ss, float(y) * ss) for x, y in fer[idx]], fill=255)
            m = m.reduce(ss).point(lambda v, a=alfa * k: int(v * a))
            cam = Image.new("RGBA", (w, h), cor_p[:3] + (255,))
            cam.putalpha(m)
            out.alpha_composite(cam)
    for c in ordem:
        cam = Image.new("RGBA", (w, h), c[:3] + (255,))
        cam.putalpha(alfas[c])
        out.alpha_composite(cam)
    return out


def _semente(t):
    return int(math.floor(t * FERVURA_HZ + 1e-4)) % VARIANTES


def _desenhar_parte(g, img, parte, chave, sem, prog, desloc=(0.0, 0.0), opacidade=1.0, atras=None):
    if prog <= 0.002 or opacidade <= 0.003:
        return
    if prog >= 0.999:
        k = ("e14r", chave, sem)
        cam = g.cache.get(k)
        if cam is None:
            cam = g.cache[k] = _render(parte, sem, 1.0, g.W)
    else:
        k = ("e14p", chave)
        ult = g.cache.get(k)
        if ult and ult[0] == sem and abs(ult[1] - prog) < 1e-6:
            cam = ult[2]
        else:   # em movimento: um pouco menos de super-amostragem; guarda só o último passo
            cam = _render(parte, sem, prog, g.W, ss=2)
            g.cache[k] = (sem, prog, cam)
    xy = (parte["pos"][0] + desloc[0], parte["pos"][1] + desloc[1])
    if atras is not None:
        _colar_atras(img, cam, xy, atras, opacidade)
    else:
        d.colar_em(img, cam, xy, opacidade)


def _colar_atras(img, cam, xy, mascara, opacidade=1.0):
    """Cola a camada ATRÁS da pessoa: some onde a máscara diz que há pessoa (só na região da camada)."""
    x, y = int(round(xy[0])), int(round(xy[1]))
    W, H = img.size
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + cam.width), min(H, y + cam.height)
    if x1 <= x0 or y1 <= y0:
        return
    parte = cam.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    inv = ImageChops.invert(mascara.crop((x0, y0, x1, y1)))
    a = ImageChops.multiply(parte.getchannel("A"), inv)
    if opacidade < 0.997:
        a = a.point(lambda v: int(v * opacidade))
    parte.putalpha(a)
    img.alpha_composite(parte, (x0, y0))


# ------------------------------------------------------------------ geometria da cabeça e busca de lugar livre

def _cabeca(g, t):
    x0, y0, x1, y1 = g.rosto.em(t)
    topo, queixo = g.rosto.topo_cabeca(t), g.rosto.queixo(t)
    fw = x1 - x0
    return {"cx": (x0 + x1) / 2, "cy": (topo + queixo) / 2, "rx": fw * 0.62, "ry": (queixo - topo) / 2,
            "rosto": (x0, y0, x1, y1), "topo": topo, "queixo": queixo, "fw": fw}


def _cabeca_no_intervalo(g, t0, t1):
    ts = np.linspace(t0, t1, max(2, int((t1 - t0) / 0.25) + 2))
    cs = [_cabeca(g, float(t)) for t in ts]
    cx = float(np.mean([c["cx"] for c in cs]))
    cy = float(np.mean([c["cy"] for c in cs]))
    rx = max(c["rx"] + abs(c["cx"] - cx) for c in cs)
    ry = max(c["ry"] + abs(c["cy"] - cy) for c in cs)
    ro = (min(c["rosto"][0] for c in cs), min(c["rosto"][1] for c in cs),
          max(c["rosto"][2] for c in cs), max(c["rosto"][3] for c in cs))
    return {"cx": cx, "cy": cy, "rx": rx, "ry": ry, "rosto": ro, "topo": min(c["topo"] for c in cs),
            "queixo": max(c["queixo"] for c in cs), "fw": float(np.mean([c["fw"] for c in cs]))}


FOLGA_LEGENDA = 0.012         # distância mínima (fração da altura) entre um DESENHO e a faixa da legenda
FOLGA_LEGENDA_TEXTO = 0.04    # nota/título: folga maior, para o texto não parecer "empilhado" na legenda


def _faixas_legenda(g, t0, t1, folga=FOLGA_LEGENDA):
    """Faixas (retângulos de largura infinita) ocupadas pela legenda entre t0 e t1 — mesma conta de
    c.faixa_legenda(), amostrada a cada 1/15 s (a legenda acompanha o queixo e pode subir/descer)."""
    if not g.legendas:
        return []
    out = set()
    for t in np.arange(t0 - 0.05, t1 + 0.07, 1.0 / 15):
        oc = g.legendas.ocupacao(float(t))
        if oc:
            out.add((int(oc[0]), int(math.ceil(oc[1]))))
    m = g.H * folga
    return [(-1e5, y0 - m, 1e5, y1 + m) for y0, y1 in sorted(out)]


def _area(g):
    # direita: até 86% em cima; na metade de baixo até 84% (botões de curtir/comentar: ver _proibidos)
    return (g.W * 0.045, g.H * 0.115, g.W * 0.86, g.H * 0.795)


def _procurar(w, h, pref, area, retangulos, elipses, passo, peso_y=1.0):
    """Centro (cx, cy) mais perto de 'pref' para uma caixa w×h dentro da área, sem tocar nada proibido."""
    ax0, ay0, ax1, ay1 = area
    if w > ax1 - ax0 or h > ay1 - ay0:
        return None
    xs = np.arange(ax0 + w / 2, ax1 - w / 2 + 1e-6, passo)
    ys = np.arange(ay0 + h / 2, ay1 - h / 2 + 1e-6, passo)
    if not len(xs) or not len(ys):
        return None
    CX, CY = np.meshgrid(xs, ys)
    ok = np.ones(CX.shape, bool)
    for (px0, py0, px1, py1) in retangulos:
        ok &= ~((CX - w / 2 < px1) & (CX + w / 2 > px0) & (CY - h / 2 < py1) & (CY + h / 2 > py0))
    for (ecx, ecy, erx, ery) in elipses:
        nx = np.clip(ecx, CX - w / 2, CX + w / 2)
        ny = np.clip(ecy, CY - h / 2, CY + h / 2)
        ok &= ((nx - ecx) / erx) ** 2 + ((ny - ecy) / ery) ** 2 >= 1.0
    if not ok.any():
        return None
    dist = (CX - pref[0]) ** 2 + ((CY - pref[1]) * peso_y) ** 2
    dist[~ok] = np.inf
    i = int(np.argmin(dist))
    return float(CX.flat[i]), float(CY.flat[i]), float(dist.flat[i])


def _tamanho(e):
    try:
        return int(float(e.get("tamanho", 2) or 2))
    except (TypeError, ValueError):
        return 2


def _cor_evento(e, padrao=None):
    c = e.get("cor")
    if c and str(c).lower() in CORES:
        return CORES[str(c).lower()]
    return padrao


def _chave(e):
    return (e.get("tipo"), round(float(e["inicio"]), 3), round(float(e["fim"]), 3), str(e.get("texto", "")),
            str(e.get("forma", "")))


def _avisar(g, msg):
    avisos = g.cache.setdefault("e14_avisos", [])
    avisos.append(msg)
    if multiprocessing.current_process().name == "MainProcess":
        print(f"Aviso (estilo 14): {msg}")


# ------------------------------------------------------------------ planejamento das posições (uma vez, em preparar)

def preparar(g):
    _layout(g)


def _layout(g):
    if "e14_lay" in g.cache:
        return g.cache["e14_lay"]
    W, H = g.W, g.H
    lay = {}
    ocupados = []        # (t0, t1, retângulo)
    textos = []          # (t0, t1, texto, retângulo) das notas/títulos já colocados
    riscos = []          # (t0, t1, retângulo) de cada risco das auras: textos não caem em cima deles
    contornos = []       # (t0, t1, (cx, cy, rx, ry)) do círculo/arco feito à mão (modo sem recorte)
    lado_ant = "esq"
    evs = sorted(g.plano["eventos"], key=lambda e: (e["inicio"], {"titulo": 0, "nota": 1, "desenho": 2}.get(e.get("tipo"), 3)))
    for e in evs:
        tipo = e.get("tipo")
        if tipo in ("nota", "titulo"):
            # no máximo 1 texto do estilo na tela (além da legenda): o que começou antes fica, o outro sai
            choque = next((x for x in textos if x[0] < e["fim"] - 0.01 and e["inicio"] < x[1] - 0.01), None)
            if choque:
                _avisar(g, f"{tipo} '{e.get('texto', '')}' em {e['inicio']:.2f}s ficaria na tela junto com "
                           f"'{choque[2]}' (só 1 nota ou título por vez, além da legenda): ele não aparece. "
                           "Mude o momento ou troque por um 'desenho'.")
                continue
        try:
            if tipo == "contorno":
                L = _lay_contorno(g, e)
                if not g.tem_mascara and L.get("oval"):
                    contornos.append((e["inicio"] - 0.15, e["fim"] + 0.15, L["oval"]))
            elif tipo == "aura":
                L = _lay_aura(g, e, [r for t0, t1, _, r in textos if t0 < e["fim"] and t1 > e["inicio"]])
            elif tipo == "desenho" and str(e.get("forma", "")).lower() == "brilhos":
                L = _lay_brilhos(g, e, ocupados)
            elif tipo == "desenho":
                L = _lay_desenho(g, e, ocupados, lado_ant)
            elif tipo == "nota":
                L = _lay_nota(g, e, ocupados + riscos, lado_ant, contornos)
            elif tipo == "titulo":
                L = _lay_titulo(g, e, ocupados + riscos)
            else:
                continue
        except Exception as exc:  # noqa: BLE001  um evento ruim não derruba o vídeo
            _avisar(g, f"{tipo} em {e['inicio']:.2f}s não pôde ser desenhado ({exc}).")
            continue
        if L is None:
            continue
        lay[_chave(e)] = L
        for cx in ([L["caixa"]] if L.get("caixa") is not None else []) + list(L.get("caixas", [])):
            ocupados.append((e["inicio"] - 0.15, e["fim"] + 0.15, cx))
        if tipo in ("nota", "titulo"):
            textos.append((e["inicio"], e["fim"], str(e.get("texto", "")), L["caixa"]))
        for r in L.get("riscos", []):
            riscos.append((e["inicio"] - 0.15, e["fim"] + 0.15, r))
        if L.get("lado") in ("esq", "dir"):
            lado_ant = L["lado"]
    g.cache["e14_lay"] = lay
    return lay


def _proibidos(g, e, ocupados, cab, folga_cab, folga_leg=FOLGA_LEGENDA):
    W = g.W
    x0, y0, x1, y1 = cab["rosto"]
    m = W * 0.03
    rets = [(x0 - m, y0 - m, x1 + m, y1 + m)]
    rets.append((W * 0.84, g.H * 0.45, 1e5, 1e5))     # botões de curtir/comentar (direita, metade de baixo)
    rets += _faixas_legenda(g, e["inicio"], e["fim"], folga_leg)
    mo = W * 0.02
    for t0, t1, r in ocupados:
        if t0 < e["fim"] and t1 > e["inicio"]:
            rets.append((r[0] - mo, r[1] - mo, r[2] + mo, r[3] + mo))
    elipses = [(cab["cx"], cab["cy"], cab["rx"] + folga_cab, cab["ry"] + folga_cab)]
    return rets, elipses


def _lados(e, lado_ant, cab, W):
    lado = str(e.get("lado", "auto")).lower()
    if lado in ("esquerda", "esq"):
        return ["esq"]
    if lado in ("direita", "dir"):
        return ["dir"]
    # alterna os lados; começa pelo que tem mais espaço livre se a pessoa não estiver no centro
    esp_esq = cab["cx"] - cab["rx"]
    esp_dir = W * 0.85 - (cab["cx"] + cab["rx"])
    if abs(esp_esq - esp_dir) > W * 0.12:
        return ["esq", "dir"] if esp_esq > esp_dir else ["dir", "esq"]
    return ["dir", "esq"] if lado_ant == "esq" else ["esq", "dir"]


def _melhor_lugar(g, w, h, lados, cab, rets, elipses, gap, y_pref, area=None):
    area = area or _area(g)
    passo = g.W * 0.012
    melhores = []
    for k, lado in enumerate(lados):
        if lado == "esq":
            pref = (cab["cx"] - cab["rx"] - gap - w / 2, y_pref)
            ar = (area[0], area[1], min(area[2], cab["cx"] + w * 0.15), area[3])
        else:
            pref = (cab["cx"] + cab["rx"] + gap + w / 2, y_pref)
            ar = (max(area[0], cab["cx"] - w * 0.15), area[1], area[2], area[3])
        r = _procurar(w, h, pref, ar, rets, elipses, passo)
        if r:
            melhores.append((r[2] * (1.0 + 0.35 * k), lado, r[0], r[1]))
    if not melhores:
        return None
    melhores.sort()
    _, lado, cx, cy = melhores[0]
    return lado, cx, cy


def _lay_desenho(g, e, ocupados, lado_ant):
    W = g.W
    forma = str(e.get("forma", "")).lower()
    if forma not in FORMAS:
        return None
    aspecto, _, _, direcional, _ = FORMAS[forma]
    H = g.H
    cab = _cabeca_no_intervalo(g, e["inicio"], e["fim"])
    queixo = cab["queixo"]
    base = {1: .19, 2: .25, 3: .31}.get(_tamanho(e), .25) * W
    lados = _lados(e, lado_ant, cab, W)
    y_pref = cab["rosto"][1] + (cab["rosto"][3] - cab["rosto"][1]) * 0.2

    def medidas(esc):
        h = base * esc
        if aspecto > 1:
            h = h / aspecto ** 0.5
        return h * aspecto, h

    achado = None
    w = h = 0.0
    # 1ª tentativa: "na parede", ao lado da cabeça e ATRÁS da pessoa (só com recorte). A própria pessoa esconde
    # a parte que cair atrás dela, então o desenho pode entrar um pouco atrás do boné/cabelo/bochecha (nunca
    # cobre o rosto: fica atrás). Só o miolo do rosto é proibido. Em plano fechado isso mantém o desenho grande.
    if g.tem_mascara:
        x0, y0, x1, y1 = cab["rosto"]
        fw = x1 - x0
        rets, _ = _proibidos(g, e, ocupados, cab, 0)
        miolo = (x0 + fw * 0.14, y0 - W * 0.02, x1 - fw * 0.14, y1 + W * 0.02)
        inteiro = (x0, y0 - W * 0.02, x1, y1 + W * 0.02)
        # seta/balão apontam para a cabeça: a ponta não pode sumir atrás dela. Ficam na altura das bochechas
        # (onde a cabeça é mais estreita) e só encostam na caixa do rosto. O balão ainda pode entrar um pouco
        # atrás da cabeça (a ponta dele é pequena); a seta não.
        tentativas = [(inteiro, y0 + (y1 - y0) * 0.55, 0.15)] if direcional else []
        if forma != "seta":
            tentativas.append((miolo, y0 + (y1 - y0) * 0.15, 0.17))
        area = _area(g)
        area = (area[0], area[1], area[2], min(area[3], queixo + H * 0.02))
        for proib, y_pref1, minimo in tentativas:
            rets[0] = proib
            for esc in (1.0, .92, .84, .76, .68, .62):
                w, h = medidas(esc)
                if max(w, h) < W * minimo:     # menor que isso some em plano fechado: melhor mudar de lugar
                    break
                achado = _melhor_lugar(g, w, h, lados, cab, rets, [], W * 0.02, y_pref1, area)
                if achado:
                    break
            if achado:
                break
    else:
        # sem recorte o desenho fica na frente: ao lado da cabeça, sem encostar nela
        rets, elipses = _proibidos(g, e, ocupados, cab, W * 0.02)
        for esc in (1.0, .92, .84, .76, .68):
            w, h = medidas(esc)
            if max(w, h) < W * 0.17:
                break
            achado = _melhor_lugar(g, w, h, lados, cab, rets, elipses, W * 0.035, y_pref)
            if achado:
                break
    # 2ª tentativa: abaixo do queixo (no peito/ombro), por cima da pessoa, fora da legenda
    if not achado:
        rets2, _ = _proibidos(g, e, ocupados, cab, 0)
        area2 = (W * 0.06, queixo + H * 0.02, W * 0.84, H * 0.795)
        for esc in (1.0, .9, .8):
            w, h = medidas(esc)
            r = _procurar(w, h, (W * 0.46, queixo + H * 0.06 + h / 2), area2, rets2, [], W * 0.012)
            if r:
                achado = ("esq" if r[0] < W * 0.46 else "dir", r[0], r[1])
                break
    # 3ª tentativa (último recurso): ao lado da cabeça sem encostar nela, menor
    if not achado:
        rets, elipses = _proibidos(g, e, ocupados, cab, W * 0.02)
        for esc in (.84, .76, .68, .6, .54, .48):
            w, h = medidas(esc)
            if max(w, h) < W * 0.11:
                break
            achado = _melhor_lugar(g, w, h, lados, cab, rets, elipses, W * 0.035, y_pref)
            if achado:
                break
    if not achado:
        _avisar(g, f"desenho '{forma}' em {e['inicio']:.2f}s não coube fora do rosto e da legenda: "
                   "ele não aparece. Mude o tempo (longe da legenda) ou use 'brilhos'.")
        return None
    lado, cx, cy = achado
    caixa = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    larg = W * 0.0088 * (0.92 if max(w, h) < W * 0.15 else 1.0) * (1.12 if max(w, h) > W * 0.24 else 1.0)
    amp = W * 0.0032
    margem = larg * 2.6 + amp * 2
    espelho = direcional and lado == "dir"
    tracos, pre, cw, ch = _forma_em_px(forma, (0, 0, w, h), _cor_evento(e), espelho, W, margem)
    parte = _parte(tracos, pre, cw, ch, (caixa[0] - margem, caixa[1] - margem), larg, amp, sal=int(e["inicio"] * 10))
    atras = g.tem_mascara and caixa[3] <= queixo + H * 0.02 + 1
    n_tr = len(tracos)
    dur = e["fim"] - e["inicio"]
    t_in = min(0.5 + 0.03 * max(0, n_tr - 2), 0.85, dur * 0.45)
    return {"tipo": "desenho", "partes": [parte], "caixa": caixa, "atras": atras, "lado": lado,
            "t_in": t_in, "t_out": min(0.32, dur * 0.25), "seguir": False}


def _lay_brilhos(g, e, ocupados):
    W, H = g.W, g.H
    cab = _cabeca_no_intervalo(g, e["inicio"], e["fim"])
    area = _area(g)
    faixas = _faixas_legenda(g, e["inicio"], e["fim"])
    outros = [r for t0, t1, r in ocupados if t0 < e["fim"] and t1 > e["inicio"]]
    x0, y0, x1, y1 = cab["rosto"]
    gap = W * 0.012
    larg, amp = W * 0.0088, W * 0.003
    margem = larg * 2.6 + amp * 2

    def livre(cx):
        if cx[0] < area[0] or cx[2] > area[2] or cx[1] < area[1] or cx[3] > area[3]:
            return False
        if cx[2] > W * 0.84 and cx[3] > H * 0.45:      # botões de curtir/comentar
            return False
        if cx[2] > x0 and cx[0] < x1 and cx[3] > y0 and cx[1] < y1:
            return False
        if any(cx[3] > f[1] and cx[1] < f[3] for f in faixas):
            return False
        m = W * 0.015
        return not any(cx[2] + m > r[0] and cx[0] - m < r[2] and cx[3] + m > r[1] and cx[1] - m < r[3] for r in outros)

    partes, caixas = [], []
    for lado in ("esq", "dir"):
        feito = False
        for s in (W * 0.12, W * 0.1):
            for th in (48, 58, 68, 78, 88, 98, 108):
                a = math.radians(th)
                sx = -1 if lado == "esq" else 1
                px = cab["cx"] + sx * (cab["rx"] + gap) * math.sin(a)
                py = cab["cy"] - (cab["ry"] + gap) * math.cos(a)
                bx0, bx1 = (px - s, px) if lado == "esq" else (px, px + s)
                caixa = (bx0, py - s, bx1, py)
                if not livre(caixa):
                    continue
                tracos, pre, cw, ch = _forma_em_px("brilhos", (0, 0, s, s), _cor_evento(e), lado == "dir", W, margem)
                partes.append(_parte(tracos, pre, cw, ch, (caixa[0] - margem, caixa[1] - margem), larg, amp,
                                     sal=int(e["inicio"] * 10) + (7 if lado == "dir" else 0)))
                caixas.append(caixa)
                feito = True
                break
            if feito:
                break
    if not partes:
        _avisar(g, f"brilhos em {e['inicio']:.2f}s não couberam em volta da cabeça.")
        return None
    dur = e["fim"] - e["inicio"]
    return {"tipo": "desenho", "partes": partes, "caixa": None, "caixas": caixas, "atras": g.tem_mascara, "lado": None,
            "t_in": min(0.3, dur * 0.4), "t_out": min(0.25, dur * 0.25), "seguir": True,
            "ancora": (cab["cx"], cab["cy"])}


def _lay_aura(g, e, evitar=()):
    """evitar: retângulos de notas/títulos na tela ao mesmo tempo (risco nenhum passa por cima de texto)."""
    W, H = g.W, g.H
    cab = _cabeca_no_intervalo(g, e["inicio"], e["fim"])
    faixas = _faixas_legenda(g, e["inicio"], e["fim"])
    x0, y0, x1, y1 = cab["rosto"]
    larg, amp = W * 0.0085, W * 0.003
    mt = W * 0.03
    raios = []
    for k, th in enumerate(range(-104, 105, 16)):
        a = math.radians(th)
        dx, dy = math.sin(a), -math.cos(a)
        # raio da elipse da cabeça nessa direção
        re = 1.0 / math.sqrt((dx / cab["rx"]) ** 2 + (dy / cab["ry"]) ** 2)
        r0 = re + (W * 0.004 if g.tem_mascara else W * 0.03)
        r1 = r0 + W * (0.085 if k % 2 == 0 else 0.06)
        p0 = (cab["cx"] + dx * r0, cab["cy"] + dy * r0)
        p1 = (cab["cx"] + dx * r1, cab["cy"] + dy * r1)
        if not (W * 0.03 <= p1[0] <= W * 0.85 and H * 0.11 <= p1[1] <= H * 0.8):   # zona segura (direita livre)
            continue
        meio_y = (p0[1] + p1[1]) / 2
        if any(f[1] < meio_y < f[3] for f in faixas):
            continue
        if x0 < p1[0] < x1 and y0 < p1[1] < y1:
            continue
        rx0, rx1 = min(p0[0], p1[0]) - mt, max(p0[0], p1[0]) + mt
        ry0, ry1 = min(p0[1], p1[1]) - mt, max(p0[1], p1[1]) + mt
        if any(rx1 > r[0] and rx0 < r[2] and ry1 > r[1] and ry0 < r[3] for r in evitar):
            continue
        raios.append((p0, p1))
    if not raios:
        return None
    pts = np.array([p for r in raios for p in r])
    margem = larg * 2.6 + amp * 2
    bx0, by0 = pts.min(0) - margem
    bx1, by1 = pts.max(0) + margem
    tracos = [(_reta(np.array(p0) - (bx0, by0), np.array(p1) - (bx0, by0), 6), d.cor(_cor_evento(e, LIMA)), 1.1)
              for p0, p1 in raios]
    parte = _parte(tracos, [], bx1 - bx0, by1 - by0, (bx0, by0), larg, amp, sal=int(e["inicio"] * 10) + 3)
    parte["raios"] = True
    dur = e["fim"] - e["inicio"]
    riscos = [(min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])) for a, b in raios]
    return {"tipo": "aura", "partes": [parte], "caixa": None, "atras": g.tem_mascara, "seguir": True,
            "ancora": (cab["cx"], cab["cy"]), "t_in": min(0.22, dur * 0.3), "t_out": min(0.22, dur * 0.3),
            "riscos": riscos}


def _lay_contorno(g, e):
    W, H = g.W, g.H
    cab = _cabeca(g, e["inicio"])
    cor = _cor_evento(e, CREME)
    dur = e["fim"] - e["inicio"]
    L = {"tipo": "contorno", "caixa": None, "cor": d.cor(cor), "centro": (cab["cx"], cab["cy"]),
         "t_in": min(0.75, dur * 0.4), "t_out": min(0.42, dur * 0.25), "partes": [], "seguir": True,
         "ancora": (cab["cx"], cab["cy"])}
    # reserva para quando não houver recorte: círculo feito à mão em volta da cabeça (ou cantoneiras)
    larg, amp = W * 0.0095, W * 0.0032
    margem = larg * 2.6 + amp * 2
    rx, ry = cab["rx"] * 1.16 + W * 0.02, cab["ry"] * 1.08 + W * 0.02
    cx, cy = cab["cx"], cab["cy"]
    if cx - rx > W * 0.03 and cx + rx < W * 0.85 and cy - ry > H * 0.085 and cy + ry < H * 0.85:
        oval = _arco(rx + margem, ry + margem, rx, ry, -100, 286, 90)
        oval = _mao(oval / (2 * rx), 53, .006) * (2 * rx)
        tr = [(oval, d.cor(cor), 1.0)]
        L["partes"] = [_parte(tr, [], 2 * rx + 2 * margem, 2 * ry + 2 * margem, (cx - rx - margem, cy - ry - margem),
                              larg, amp, sal=int(e["inicio"] * 10))]
        L["oval"] = (cx, cy, rx, ry, -180, 180)
    else:
        # plano fechado: a cabeça não cabe num círculo inteiro. Faz um arco aberto feito à mão só por cima
        # da cabeça (de um lado ao outro), encolhido até caber na tela.
        x0, y0, x1, y1 = cab["rosto"]
        rx = min(rx, cx - W * 0.045, W * 0.845 - cx)
        rx = max(rx, (x1 - x0) * 0.62)
        cx = min(max(cx, W * 0.045 + rx), W * 0.845 - rx)
        topo_min = H * 0.10
        ry = min(ry, cy - topo_min)
        ry = max(ry, (cab["queixo"] - cab["topo"]) * 0.5 + W * 0.01)
        cy = max(cy, topo_min + ry)
        a0, a1 = -200, 20
        arco = _arco(rx + margem, ry + margem, rx, ry, a0, a1, 70)
        arco = _mao(arco / (2 * rx), 53, .007) * (2 * rx)
        tr = [(arco, d.cor(cor), 1.12)]
        L["partes"] = [_parte(tr, [], 2 * rx + 2 * margem, 2 * ry + 2 * margem, (cx - rx - margem, cy - ry - margem),
                              larg, amp, sal=int(e["inicio"] * 10))]
        L["oval"] = (cx, cy, rx, ry, a0, a1)
    return L


# ------------------------------------------------------------------ textos (nota e título)

def _bloco_texto(linhas, f, al, cor_txt, marca=None, cor_marca=ROSA):
    """Texto creme com contorno e sombra escuros (legível em qualquer fundo). Devolve (camada, info)."""
    pad = int(f.size * 0.7)
    larg = max(f.getlength(l) for l in linhas)
    w, h = int(larg + pad * 2), int(al * len(linhas) + pad * 2)
    cam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    contorno = max(2, int(f.size * 0.075))
    esp = f.getlength(" ")
    pos_marca = None
    for li, l in enumerate(linhas):
        x = pad + (larg - f.getlength(l)) / 2
        y = pad + li * al
        for p in l.split(" "):
            wp = f.getlength(p)
            eh = bool(marca) and _norm(p) == _norm(marca) and pos_marca is None
            d.escrever(cam, (x, y), [p], f, cor_marca if eh else cor_txt, sombra=0.7, contorno=contorno,
                       cor_contorno=SOMBRA)
            if eh:
                pos_marca = (x, y, wp)
            x += wp + esp
    return cam, {"pad": pad, "larg": larg, "pos_marca": pos_marca, "linhas": linhas, "al": al}


def _zona_rosto_texto(g, cab):
    """Parte do rosto que um texto NUNCA cobre: olhos, nariz e boca (com folga). Fica de fora só a faixa de
    cima da caixa do rosto (testa/aba do boné): em plano fechado, sem espaço ao lado da cabeça, a nota ou o
    título podem encostar no boné/cabelo/testa — longe dos olhos e longe da legenda."""
    x0, y0, x1, y1 = cab["rosto"]
    m = g.W * 0.03
    return (x0 - m, y0 + min((y1 - y0) * 0.2, cab["fw"] * 0.25), x1 + m, y1 + m)


def _entrada_ret(p, v, r):
    """Fração s (0-1) em que o segmento p → p+v entra no retângulo r, ou None se não entra."""
    s0, s1 = 0.0, 1.0
    for k in (0, 1):
        lo, hi = r[k], r[k + 2]
        if abs(v[k]) < 1e-9:
            if not lo <= p[k] <= hi:
                return None
            continue
        a, b = (lo - p[k]) / v[k], (hi - p[k]) / v[k]
        if a > b:
            a, b = b, a
        s0, s1 = max(s0, a), min(s1, b)
    return s0 if s0 <= s1 else None


def _quebrar_ate(texto, f, largura, max_linhas):
    linhas = d.quebrar(texto, f, largura, 99)
    if len(linhas) > max_linhas or any(f.getlength(l) > largura for l in linhas):
        return None
    return linhas


def _lay_nota(g, e, ocupados, lado_ant, contornos=()):
    W, H = g.W, g.H
    texto = " ".join(str(e.get("texto", "")).split())
    if not texto:
        return None
    cab = _cabeca_no_intervalo(g, e["inicio"], e["fim"])
    folga = W * 0.075                     # espaço para a seta entre a nota e a cabeça
    rets, elipses = _proibidos(g, e, ocupados, cab, folga, FOLGA_LEGENDA_TEXTO)
    # contorno feito à mão ativo (sem recorte): a nota fica fora dele e a seta para na linha, sem cruzar
    ovais = [o for t0, t1, o in contornos if t0 < e["fim"] and t1 > e["inicio"]]
    elipses_sem_oval = list(elipses)
    for (ocx, ocy, orx, ory, _a0, _a1) in ovais:
        elipses.append((ocx, ocy, orx + W * 0.06, ory + W * 0.06))
    # a seta não pode atravessar a legenda: nada do outro lado da legenda em relação à cabeça
    for f in _faixas_legenda(g, e["inicio"], e["fim"]):
        if (f[1] + f[3]) / 2 > cab["cy"]:
            rets.append((-1e5, f[1], 1e5, 1e5))
        else:
            rets.append((-1e5, -1e5, 1e5, f[3]))
    lados = _lados(e, lado_ant, cab, W)
    y_pref = cab["rosto"][1]
    tamanhos = ((0.066, .46), (0.06, .42), (0.055, .36), (0.05, .30), (0.046, .25))
    achado = None
    junto = False
    for fs, mw in tamanhos:
        f = d.fonte(int(W * fs), 800)
        linhas = _quebrar_ate(texto, f, W * mw, 2)
        if not linhas:
            continue
        al = f.size * 1.05
        tw = max(f.getlength(l) for l in linhas)
        w, h = tw + W * 0.03, al * len(linhas) + W * 0.02
        achado = _melhor_lugar(g, w, h, lados, cab, rets, elipses, folga, y_pref)
        if not achado and ovais:      # não coube fora do contorno: aceita ficar dentro dele (a seta para antes)
            achado = _melhor_lugar(g, w, h, lados, cab, rets, elipses_sem_oval, folga, y_pref)
        if achado:
            break
    if not achado:
        # plano fechado: a cabeça ocupa a largura e a legenda está logo abaixo do queixo. A nota pode ficar por
        # cima do boné/cabelo/orelha (no alto, ao lado da testa), mas nunca sobre olhos/nariz/boca e sempre
        # longe da legenda; a seta, curta, aponta para o rosto e para antes dele.
        rets2 = [_zona_rosto_texto(g, cab)] + rets[1:]
        for fs, mw in tamanhos:
            f = d.fonte(int(W * fs), 800)
            linhas = _quebrar_ate(texto, f, W * mw, 2)
            if not linhas:
                continue
            al = f.size * 1.05
            tw = max(f.getlength(l) for l in linhas)
            w, h = tw + W * 0.03, al * len(linhas) + W * 0.02
            achado = _melhor_lugar(g, w, h, lados, cab, rets2, [], W * 0.02, y_pref)
            if achado:
                junto = True
                break
    if not achado:
        _avisar(g, f"nota '{texto}' em {e['inicio']:.2f}s não coube fora do rosto e da legenda: ela não aparece. "
                   "Use texto mais curto (1-2 palavras) ou outro momento.")
        return None
    lado, cx, cy = achado
    caixa = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    cam, info = _bloco_texto(linhas, f, al, CREME)
    # seta: da borda da nota até perto da cabeça, curvada para fora
    ang = math.atan2(cy - cab["cy"], cx - cab["cx"])
    re = 1.0 / math.sqrt((math.cos(ang) / (cab["rx"] + W * 0.025)) ** 2 + (math.sin(ang) / (cab["ry"] + W * 0.025)) ** 2)
    alvo = np.array([cab["cx"] + math.cos(ang) * re, cab["cy"] + math.sin(ang) * re])
    if junto:
        # a nota já está sobre a cabeça: a seta mira o meio do rosto e para na borda da zona proibida
        zx0, zy0, zx1, zy1 = _zona_rosto_texto(g, cab)
        zona = (zx0 - W * 0.04, zy0 - W * 0.04, zx1 + W * 0.04, zy1 + W * 0.04)   # a ponta fica longe das sobrancelhas
        rx0, ry0, rx1, ry1 = cab["rosto"]
        mira = np.array([(rx0 + rx1) / 2, ry0 + (ry1 - ry0) * 0.4])
        s = _entrada_ret(np.array([cx, cy]), mira - (cx, cy), zona)
        alvo = np.array([cx, cy]) + (mira - (cx, cy)) * (s if s is not None else 1.0)
        ovais = []
    for (ocx, ocy, orx, ory, oa0, oa1) in ovais:   # para antes da linha do contorno (nota fora dele)
        if ((cx - ocx) / (orx + W * 0.03)) ** 2 + ((cy - ocy) / (ory + W * 0.03)) ** 2 <= 1.0:
            continue
        a2 = math.atan2(cy - ocy, cx - ocx)
        graus = math.degrees(a2)
        if not any(oa0 <= gr <= oa1 for gr in (graus, graus - 360, graus + 360)):
            continue          # nessa direção o arco é aberto: a seta passa livre até a cabeça
        r2 = 1.0 / math.sqrt((math.cos(a2) / (orx + W * 0.03)) ** 2 + (math.sin(a2) / (ory + W * 0.03)) ** 2)
        p2 = np.array([ocx + math.cos(a2) * r2, ocy + math.sin(a2) * r2])
        if W * 0.09 < np.hypot(*(p2 - (cx, cy))) < np.hypot(*(alvo - (cx, cy))):
            alvo = p2
    centro = np.array([cx, cy])
    v = alvo - centro
    # ponto de saída: borda da caixa na direção do alvo
    tx = (w / 2 + W * 0.012) / abs(v[0]) if abs(v[0]) > 1e-6 else 1e9
    ty = (h / 2 + W * 0.012) / abs(v[1]) if abs(v[1]) > 1e-6 else 1e9
    inicio_s = centro + v * min(tx, ty, 0.6)
    comp = float(np.hypot(*(alvo - inicio_s)))
    larg, amp = W * 0.0085, W * 0.003
    partes = []
    seta_caixa = None
    if comp > W * 0.035:
        normal = np.array([-(alvo - inicio_s)[1], (alvo - inicio_s)[0]]) / comp
        if np.dot(normal, np.array([cab["cx"], cab["cy"]]) - (inicio_s + alvo) / 2) > 0:
            normal = -normal
        ctrl = (inicio_s + alvo) / 2 + normal * comp * 0.28
        curva = _juntar(_reta(inicio_s, ctrl, 1)[:1], _bez(inicio_s, inicio_s + (ctrl - inicio_s) * 0.9,
                                                           alvo + (ctrl - alvo) * 0.9, alvo, 22))
        ponta = _ponta_seta(curva[-1], curva[-4], max(W * 0.032, comp * 0.18), 30)
        pts = np.vstack([curva, ponta])
        margem = larg * 2.6 + amp * 2
        b0 = pts.min(0) - margem
        b1 = pts.max(0) + margem
        cor = d.cor(_cor_evento(e, LIMA))
        partes.append(_parte([(curva - b0, cor, 1.0), (ponta - b0, cor, 1.0)], [], b1[0] - b0[0], b1[1] - b0[1],
                             tuple(b0), larg, amp, sal=int(e["inicio"] * 10) + 5))
        seta_caixa = (b0[0], b0[1], b1[0], b1[1])
    dur = e["fim"] - e["inicio"]
    rot = 3.2 if lado == "esq" else -3.2
    caixa_total = caixa if seta_caixa is None else (min(caixa[0], seta_caixa[0]), min(caixa[1], seta_caixa[1]),
                                                     max(caixa[2], seta_caixa[2]), max(caixa[3], seta_caixa[3]))
    return {"tipo": "nota", "texto": cam, "centro": (cx, cy), "rot": rot, "partes": partes, "caixa": caixa_total,
            "lado": lado, "t_in": min(0.2, dur * 0.2), "t_seta": min(0.34, dur * 0.3), "t_out": min(0.24, dur * 0.2),
            "seguir": False}


def _lay_titulo(g, e, ocupados):
    W, H = g.W, g.H
    texto = " ".join(str(e.get("texto", "")).split())
    if not texto:
        return None
    marca = str(e.get("marca", "") or "").strip()
    cab = _cabeca_no_intervalo(g, e["inicio"], e["fim"])
    # o título é TEXTO: fica longe da legenda (folga maior que a dos desenhos) para não "empilhar" nela
    rets, elipses = _proibidos(g, e, ocupados, cab, W * 0.025, FOLGA_LEGENDA_TEXTO)
    pos = str(e.get("posicao", "auto")).lower()
    achado = None
    # 1ª passada: fora da cabeça inteira (boné/cabelo incluídos), em tamanho grande.
    # 2ª passada (plano fechado: a cabeça ocupa a largura e a legenda está logo abaixo do queixo): o título
    # pode ficar por cima do boné/cabelo/testa/ombro, mas NUNCA sobre olhos/nariz/boca (_zona_rosto_texto) nem
    # perto da legenda — como na prévia aprovada, o título vai para o alto da tela.
    rets2 = [_zona_rosto_texto(g, cab)] + rets[1:]
    passadas = ((rets, elipses, (0.094, 0.086, 0.078, 0.07, 0.063)),
                (rets2, [], (0.094, 0.086, 0.078, 0.07, 0.063, 0.057, 0.052)))
    for rets_p, elip, tamanhos in passadas:
        for fs in tamanhos:
            f = d.fonte(int(W * fs), 850)
            linhas = _quebrar_ate(texto, f, W * 0.8, 2)
            if not linhas:
                continue
            al = f.size * 1.04
            tw = max(f.getlength(l) for l in linhas)
            w, h = tw + W * 0.03, al * len(linhas) + f.size * 0.42
            acima = (W * 0.46, cab["topo"] - H * 0.02 - h / 2)
            abaixo = (W * 0.46, cab["queixo"] + H * 0.025 + h / 2)
            prefs = {"topo": [acima], "baixo": [abaixo]}.get(pos, [acima, abaixo])
            melhores = []
            for k, pref in enumerate(prefs):
                r = _procurar(w, h, pref, _area(g), rets_p, elip, W * 0.012, peso_y=1.0)
                if r:
                    melhores.append((r[2] * (1 + 0.2 * k), r[0], r[1]))
            if melhores:
                melhores.sort()
                achado = (melhores[0][1], melhores[0][2])
                break
        if achado:
            break
    if not achado:
        _avisar(g, f"título '{texto}' em {e['inicio']:.2f}s não coube fora do rosto e da legenda: ele não aparece. "
                   "Encurte o texto ou mude o momento.")
        return None
    cx, cy = achado
    caixa = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    cam, info = _bloco_texto(linhas, f, al, CREME, marca=marca or None, cor_marca=ROSA)
    # sublinhado feito à mão: duplo, em lima, embaixo da palavra marcada; sem marca, rosa embaixo da última linha
    larg, amp = max(W * 0.0085, f.size * 0.085), W * 0.0028
    pad = info["pad"]
    pm = info["pos_marca"]
    if pm:
        x, y, wp = pm
        yb = y + f.size * 1.02
        a = _bez((x - f.size * .06, yb), (x + wp * .3, yb + f.size * .06), (x + wp * .7, yb - f.size * .02),
                 (x + wp + f.size * .1, yb - f.size * .04), 20)
        b = _bez((x + wp + f.size * .02, yb + f.size * .06), (x + wp * .6, yb + f.size * .16),
                 (x + wp * .3, yb + f.size * .1), (x + f.size * .1, yb + f.size * .2), 18)
        tr = [(a, d.cor(LIMA), 1.0), (b, d.cor(LIMA), 0.9)]
    else:
        ult = info["linhas"][-1]
        lw = f.getlength(ult)
        x = pad + (info["larg"] - lw) / 2
        yb = pad + (len(info["linhas"]) - 1) * al + f.size * 1.04
        a = _bez((x - f.size * .08, yb + f.size * .02), (x + lw * .35, yb + f.size * .1), (x + lw * .65, yb - f.size * .03),
                 (x + lw + f.size * .12, yb + f.size * .01), 26)
        tr = [(a, d.cor(ROSA), 1.0)]
    sub = _parte(tr, [], cam.width, cam.height, (0, 0), larg, amp, sal=int(e["inicio"] * 10) + 9)
    dur = e["fim"] - e["inicio"]
    return {"tipo": "titulo", "texto": cam, "sub": sub, "centro": (cx, cy), "rot": -1.6, "caixa": caixa,
            "t_in": min(0.38, dur * 0.3), "t_sub": min(0.3, dur * 0.25), "t_out": min(0.24, dur * 0.2),
            "seguir": False, "info": info}


# ------------------------------------------------------------------ desenho por quadro

ROT_FERVURA = (0.0, 0.45, -0.35)


def _tinta(g):
    k = ("e14_tinta", g.W, g.H)
    if k not in g.cache:
        g.cache[k] = Image.new("RGBA", (g.W, g.H), d.cor(TINTA))
    return g.cache[k]


def _tom(c):
    """0-1: quanto o fundo escurece além do tom base (contorno e aura pedem palco mais escuro)."""
    k = 0.0
    for e in c.eventos:
        if e.get("tipo") in ("contorno", "aura"):
            k = max(k, d.envelope(c.t, e["inicio"], e["fim"], 0.35, 0.35))
    return k


def _em_dois(t):
    """Tempo em passos de 1/15 s: o traço avança "em dois" (a cada 2 quadros), como animação feita à mão."""
    return math.floor(t * PASSOS_HZ + 1e-4) / PASSOS_HZ


def _progresso(t, e, t_in, t_out):
    """Quanto do traço está na tela: desenha no começo e "apaga" de trás para frente no fim."""
    t = _em_dois(t)
    p_in = d.suave(d.mapear(t, e["inicio"], e["inicio"] + t_in))
    p_out = d.entrada(d.mapear(t, e["fim"] - t_out, e["fim"]))
    return p_in * (1 - p_out)


def _seguir(c, L):
    if not L.get("seguir") or "ancora" not in L:
        return (0.0, 0.0)
    cab = _cabeca(c.g, c.t)
    return (cab["cx"] - L["ancora"][0], cab["cy"] - L["ancora"][1])


def _el_desenho(c, img, e, L, sem, atras=None):
    prog = _progresso(c.t, e, L["t_in"], L["t_out"])
    desloc = _seguir(c, L)
    for k, parte in enumerate(L["partes"]):
        _desenhar_parte(c.g, img, parte, (_chave(e), k), sem, prog, desloc, atras=atras)


def _el_aura(c, img, e, L, sem, atras=None):
    """Riscos crescem para fora no começo, pulsam com o tremido e recolhem no fim."""
    prog = _progresso(c.t, e, L["t_in"], L["t_out"])
    if prog <= 0.002:
        return
    parte = L["partes"][0]
    desloc = _seguir(c, L)
    k = ("e14aura", _chave(e), sem)
    cam = c.g.cache.get(k) if prog >= 0.999 else None
    if cam is None:
        # cada risco cresce do centro para fora (encurta os traços em vez de desenhar um por vez)
        p2 = dict(parte)
        tr = []
        for pts, cor, mult in parte["tracos"]:
            n = max(2, int(round(len(pts) * max(0.15, prog))))
            tr.append((pts[:n], cor, mult))
        p2["tracos"] = tr
        cam = _render(p2, sem, 1.0, c.g.W, ss=None if prog >= 0.999 else 2)
        if prog >= 0.999:
            c.g.cache[k] = cam
    xy = (parte["pos"][0] + desloc[0], parte["pos"][1] + desloc[1])
    op = min(1.0, prog * 1.6)
    if atras is not None:
        _colar_atras(img, cam, xy, atras, op)
    else:
        d.colar_em(img, cam, xy, op)


def _el_nota(c, img, e, L, sem):
    t = c.t
    ini, fim = e["inicio"], e["fim"]
    k_txt = d.saida(d.mapear(t, ini, ini + L["t_in"])) * (1 - d.entrada(d.mapear(t, fim - L["t_out"], fim)))
    if k_txt > 0.003:
        rot = L["rot"] + ROT_FERVURA[sem]
        chave = ("e14nota", _chave(e), sem)
        cam = c.g.cache.get(chave)
        if cam is None:
            cam = c.g.cache[chave] = L["texto"].rotate(rot, resample=Image.BICUBIC, expand=True)
        entrada = d.mola(d.mapear(t, ini, ini + L["t_in"] * 1.4), 1.3)
        d.colar(img, cam, L["centro"], escala=0.82 + 0.18 * entrada, opacidade=k_txt)
    t_seta0 = ini + L["t_in"] * 0.6
    tq = _em_dois(t)
    prog = d.suave(d.mapear(tq, t_seta0, t_seta0 + L["t_seta"])) * (1 - d.entrada(d.mapear(tq, fim - L["t_out"] * 1.2, fim - L["t_out"] * 0.2)))
    for k, parte in enumerate(L["partes"]):
        _desenhar_parte(c.g, img, parte, (_chave(e), "seta", k), sem, prog)


def _titulo_girado(g, e, L, sem):
    """Texto do título já girado (uma vez por variante do tremido) e o sublinhado nas coordenadas giradas."""
    k = ("e14tit_g", _chave(e), sem)
    if k not in g.cache:
        rot = L["rot"] + ROT_FERVURA[sem]
        base = L["texto"]
        cam = base.rotate(rot, resample=Image.BICUBIC, expand=True)
        a = math.radians(rot)
        ca, sa = math.cos(a), math.sin(a)
        cx0, cy0 = base.width / 2, base.height / 2
        cx1, cy1 = cam.width / 2, cam.height / 2

        def girar(p):   # mesmo giro do rotate() do Pillow (anti-horário, y para baixo)
            dx, dy = p[:, 0] - cx0, p[:, 1] - cy0
            return np.stack([dx * ca + dy * sa + cx1, -dx * sa + dy * ca + cy1], 1)
        sub = dict(L["sub"])
        sub["tracos"] = [(girar(pts), cor, mult) for pts, cor, mult in L["sub"]["tracos"]]
        sub["tam"] = cam.size
        # onde termina o texto na camada girada (para a escrita da esquerda para a direita)
        info = L["info"]
        x_fim = girar(np.array([[info["pad"] + info["larg"], cy0]]))[0, 0]
        x_ini = girar(np.array([[info["pad"] * 0.5, cy0]]))[0, 0]
        g.cache[k] = (cam, sub, x_ini, x_fim)
    return g.cache[k]


def _el_titulo(c, img, e, L, sem):
    t = c.t
    ini, fim = e["inicio"], e["fim"]
    k_out = 1 - d.entrada(d.mapear(t, fim - L["t_out"], fim))
    if k_out <= 0.003:
        return
    escrita = d.saida(d.mapear(t, ini, ini + L["t_in"]))           # texto "escrito" da esquerda para a direita
    tq = _em_dois(t)
    p_sub = d.suave(d.mapear(tq, ini + L["t_in"] * 0.75, ini + L["t_in"] * 0.75 + L["t_sub"]))
    p_sub *= 1 - d.entrada(d.mapear(tq, fim - L["t_out"], fim))
    texto, sub, x_ini, x_fim = _titulo_girado(c.g, e, L, sem)
    completo = escrita >= 0.999 and p_sub >= 0.999
    chave = ("e14tit", _chave(e), sem)
    cam = c.g.cache.get(chave) if completo else None
    if cam is None:
        if escrita < 0.999:
            wx = int(x_ini + (x_fim - x_ini + texto.width * 0.02) * escrita)
            cam = Image.new("RGBA", texto.size, (0, 0, 0, 0))
            if wx > 0:
                cam.paste(texto.crop((0, 0, min(texto.width, wx), texto.height)), (0, 0))
        else:
            cam = texto.copy()
        if p_sub > 0.002:
            ks = ("e14sub", _chave(e), sem)
            s_img = c.g.cache.get(ks) if p_sub >= 0.999 else None
            if s_img is None:
                s_img = _render(sub, sem, p_sub, c.g.W, ss=None if p_sub >= 0.999 else 2)
                if p_sub >= 0.999:
                    c.g.cache[ks] = s_img
            cam.alpha_composite(s_img)
        if completo:
            c.g.cache[chave] = cam
    d.colar(img, cam, L["centro"], opacidade=k_out)


def _idx_fervura(g, w2, h2, sem):
    """Índices de deslocamento (tremido) para a linha da silhueta: 3 campos de ruído suave fixos."""
    k = ("e14_idx", w2, h2, sem)
    if k not in g.cache:
        rng = np.random.default_rng(1400 + sem)
        amp = max(1.0, w2 * 0.0045)
        gw, gh = max(3, w2 // 36), max(3, h2 // 36)
        campos = []
        for _ in range(2):
            grade = rng.uniform(-1, 1, (gh, gw)).astype(np.float32)
            im = Image.fromarray(((grade + 1) * 127.5).astype(np.uint8), "L").resize((w2, h2), Image.BICUBIC)
            campos.append((np.asarray(im, np.float32) / 127.5 - 1.0) * amp)
        yy, xx = np.mgrid[0:h2, 0:w2]
        xs = np.clip(np.rint(xx + campos[0]).astype(np.int32), 0, w2 - 1)
        ys = np.clip(np.rint(yy + campos[1]).astype(np.int32), 0, h2 - 1)
        g.cache[k] = (ys * w2 + xs).ravel()
    return g.cache[k]


def _angulos(g, w2, h2, centro, chave):
    """Ângulo de cada ponto em volta da cabeça (L 0-255): 0 no alto, 255 embaixo (o lápis dá a volta)."""
    k = ("e14_ang", chave, w2, h2)
    if k not in g.cache:
        cx, cy = centro[0] / 2, centro[1] / 2
        yy, xx = np.mgrid[0:h2, 0:w2].astype(np.float32)
        ang = np.abs(np.arctan2(xx - cx, cy - yy)) / math.pi
        g.cache[k] = Image.fromarray(np.clip(ang * 255.0, 0, 255).astype(np.uint8), "L")
    return g.cache[k]


def _moldura_suave(g, w2, h2):
    """L: 0 nas bordas da tela, 255 no meio (a linha da silhueta não encosta na borda nem faz pontinhos lá).
    Embaixo a linha some antes: rampa entre 80% e 86% da altura (não desce até a base nem até os botões)."""
    k = ("e14_borda_tela", w2, h2)
    if k not in g.cache:
        r = max(3.0, w2 * 0.03)
        x = np.clip(np.minimum(np.arange(w2), np.arange(w2)[::-1]) / r, 0, 1)
        y = np.clip(np.minimum(np.arange(h2), np.arange(h2)[::-1]) / r, 0, 1)
        yy = np.arange(h2) / max(1, h2 - 1)
        y = y * np.clip((0.86 - yy) / 0.06, 0, 1)
        g.cache[k] = Image.fromarray((np.outer(y, x) * 255).astype(np.uint8), "L")
    return g.cache[k]


def _corte_baixo(g, w2, h2, y_ini, y_fim):
    """L: 255 acima de y_ini, rampa suave até 0 em y_fim (linhas da imagem reduzida)."""
    k = ("e14_corte_baixo", w2, h2, y_ini, y_fim)
    if k not in g.cache:
        col = np.clip((y_fim - np.arange(h2, dtype=np.float32)) / max(1, y_fim - y_ini), 0, 1)
        g.cache[k] = Image.fromarray(np.repeat((col * 255).astype(np.uint8)[:, None], w2, 1), "L")
    return g.cache[k]


def _lut_linha(g, w2):
    """Tabela que transforma a máscara desfocada numa linha fina logo FORA da silhueta (bordas suaves)."""
    k = ("e14_lut", w2)
    if k not in g.cache:
        sig = max(1.5, 0.0085 * w2)
        incl = 255 * 0.242 / sig                 # quanto o valor muda por pixel na altura da linha
        nucleo = 1.45 * incl                      # metade da parte cheia (~0,0078 da largura no total)
        suave = 0.8 * incl
        vc = min(110.0, max(48.0, nucleo + suave + 8))
        v = np.arange(256, dtype=np.float32)
        lut = np.clip((nucleo + suave - np.abs(v - vc)) / suave, 0, 1) * 255
        g.cache[k] = (sig, [int(x) for x in lut])
    return g.cache[k]


def _envelope(m2, pescoco=None):
    """Só a borda de FORA da silhueta: em cada linha da imagem, enche do primeiro ao último ponto da pessoa.
    Assim a linha não contorna o que a pessoa segura na frente do corpo (celular, produto, microfone)
    nem buracos entre braço e corpo. 'pescoco' = (x0, x1, y0) em pixels da imagem reduzida: logo abaixo do
    queixo, nessa faixa, enche até embaixo (a linha não corre pela borda de cima de um celular no peito)."""
    a = np.asarray(m2) > 127
    if pescoco is not None:
        x0, x1, y0 = (int(v) for v in pescoco)
        x0, x1, y0 = max(0, x0), min(a.shape[1], x1), max(0, y0)
        if x1 > x0 and y0 < a.shape[0]:
            a = a.copy()
            faixa = a[y0:, x0:x1]
            a[y0:, x0:x1] = np.maximum.accumulate(faixa[::-1], axis=0)[::-1]
    w2 = a.shape[1]
    tem = a.any(1)
    esq = a.argmax(1)
    dir_ = w2 - 1 - a[:, ::-1].argmax(1)
    xs = np.arange(w2)
    env = tem[:, None] & (xs >= esq[:, None]) & (xs <= dir_[:, None])
    return Image.fromarray(env.astype(np.uint8) * 255, "L")


def _linha_silhueta(c, e, L, sem):
    """Máscara L (tela inteira) da linha feita à mão em volta da silhueta, ou None se não houver agora."""
    t = c.t
    p_in = d.suave(d.mapear(t, e["inicio"], e["inicio"] + L["t_in"]))
    p_out = d.suave(d.mapear(t, e["fim"] - L["t_out"], e["fim"]))
    lim = min(p_in, 1 - p_out)
    if lim <= 0.002:
        return None
    W, H = c.W, c.H
    rx0, _, rx1, ry1 = c.g.rosto.em(t)
    fw, fcx = rx1 - rx0, (rx0 + rx1) / 2
    m2 = _envelope(c.mascara.reduce(2), ((fcx - fw * 0.3) / 2, (fcx + fw * 0.3) / 2,
                                         (c.g.rosto.queixo(t) - H * 0.01) / 2))
    w2, h2 = m2.size
    sig, lut = _lut_linha(c.g, w2)
    # a linha contorna cabeça e ombros e some um pouco abaixo do queixo: o resto do corpo quase sempre
    # tem objetos na frente (celular, produto, microfone) ou o recorte fica irregular lá embaixo
    # em plano fechado (rosto largo) os ombros e o que a pessoa segura já estão na altura do queixo:
    # a linha contorna só a cabeça e some no pescoço
    k_fech = min(1.0, max(0.0, (fw / W - 0.36) / 0.1))
    y_px = d.lerp(c.g.rosto.queixo(t) + H * 0.07, ry1 - H * 0.035, k_fech)
    y_ini = int(round(y_px / 8)) * 4      # passos de 4 linhas (poucas imagens no cache)
    y_fim = y_ini + max(4, int(H * d.lerp(0.065, 0.045, k_fech) / 2))
    # tremido: desloca a máscara com um dos 3 campos de ruído ANTES de desfocar (a linha ondula suave)
    arr = np.asarray(m2).ravel().take(_idx_fervura(c.g, w2, h2, sem)).reshape(h2, w2)
    linha = Image.fromarray(arr, "L").filter(ImageFilter.GaussianBlur(sig)).point(lut)
    linha = ImageChops.multiply(linha, _moldura_suave(c.g, w2, h2))   # some perto das bordas da tela
    if y_ini < h2:
        linha = ImageChops.multiply(linha, _corte_baixo(c.g, w2, h2, y_ini, y_fim))
    if lim < 0.999:   # o "lápis" sai do alto da cabeça e desce pelos dois lados (e volta ao apagar)
        ang = _angulos(c.g, w2, h2, L["centro"], _chave(e))
        corte = lim * 1.05 * 255
        rampa = ang.point(lambda v: int(255 * min(1.0, max(0.0, (corte - v) / 9.0))))
        linha = ImageChops.multiply(linha, rampa)
    caixa = linha.getbbox()
    if not caixa:
        return None
    x0, y0, x1, y1 = max(0, caixa[0] - 1), max(0, caixa[1] - 1), min(w2, caixa[2] + 1), min(h2, caixa[3] + 1)
    reg = linha.crop((x0, y0, x1, y1)).resize(((x1 - x0) * 2, (y1 - y0) * 2), Image.BILINEAR)
    tela = Image.new("L", (W, H), 0)
    tela.paste(reg, (x0 * 2, y0 * 2))
    return tela


def _palco_sem_recorte(c, k_tom):
    """Vinheta em tinta + escurecimento extra no contorno/aura, numa composição só."""
    g = c.g
    kv = ("e14_vinheta", c.W, c.H)
    if kv not in g.cache:
        y, x = np.ogrid[0:c.H, 0:c.W]
        dd = np.sqrt(((x - c.W / 2) / (c.W / 2)) ** 2 + ((y - c.H / 2) / (c.H / 2)) ** 2)
        a = np.clip((dd - 0.55) / 0.85, 0, 1) ** 1.6 * 0.42 * 255
        g.cache[kv] = Image.fromarray(a.astype(np.uint8), "L")
    q = round(k_tom * 20) / 20         # 21 níveis bastam (a mudança é lenta)
    kc = ("e14_palco_sem", c.W, c.H, q)
    camada = g.cache.get(kc)
    if camada is None:
        extra = 0.16 * q
        alfa = g.cache[kv].point([int(v + (255 - v) * extra) for v in range(256)])
        camada = Image.new("RGBA", (c.W, c.H), d.cor(TINTA))
        camada.putalpha(alfa)
        if q in (0.0, 1.0):          # só os dois estados que duram guardados (memória)
            g.cache[kc] = camada
    return Image.alpha_composite(c.fonte, camada)


def _palco_com_recorte(c, a, linha, cor_linha):
    """Uma passada só: tinta com alfa a·(1 − pessoa) (fundo mais escuro) + a linha da silhueta por cima.
    Onde a linha é suave, a cor mistura tinta e creme: vira uma sombrinha que ajuda a ler em fundo claro."""
    g = c.g
    alfa = c.mascara.point([int(a * (255 - v)) for v in range(256)])
    tr, tg, tb, _ = d.cor(TINTA)
    k = ("e14_canais", c.W, c.H)
    if k not in g.cache:
        g.cache[k] = tuple(Image.new("L", (c.W, c.H), v) for v in (tr, tg, tb))
    if linha is None:
        camada = Image.merge("RGBA", (*g.cache[k], alfa))
    else:
        alfa = ImageChops.lighter(alfa, linha)
        kp = ("e14_paleta", tuple(cor_linha[:3]))
        if kp not in g.cache:
            pal = []
            for v in range(256):
                pal += [int(ci + (cl - ci) * v / 255) for ci, cl in zip((tr, tg, tb), cor_linha[:3])]
            g.cache[kp] = pal
        camada = linha.copy()
        camada.putpalette(g.cache[kp])        # L vira P: cada valor da linha vira uma cor (tinta → creme)
        camada = camada.convert("RGB")
        camada.putalpha(alfa)
    return Image.alpha_composite(c.fonte, camada)


def _el_contorno_sem_recorte(c, img, e, L, sem):
    prog = _progresso(c.t, e, L["t_in"], L["t_out"])
    desloc = _seguir(c, L)
    for k, parte in enumerate(L["partes"]):
        _desenhar_parte(c.g, img, parte, (_chave(e), "c", k), sem, prog, desloc)


def _borda_legenda(c, img, sem):
    """Moldura tracejada rosa em volta da caixa da legenda (a 'decoração doodle' do perfil do estilo)."""
    Lg = c.g.legendas
    if Lg is None:
        return
    try:
        t = c.t
        grp = next((g for g in Lg.grupos if g["inicio"] - 0.05 <= t < g["fim"]), None)
        if not grp:
            return
        k = d.saida(d.mapear(t, grp["inicio"] + 0.08, grp["inicio"] + 0.26))
        if k <= 0.01:
            return
        txts, linhas = Lg._linhas(grp)
        f = Lg.f
        al, pad_x, pad_y = f.size * 1.18, f.size * 0.45, f.size * 0.28
        alt = al * len(linhas) + pad_y * 2
        y = Lg._y(t, alt)
        larg = max(f.getlength(" ".join(txts[i] for i in ln)) for ln in linhas)
        bw = larg + pad_x * 2
        bh = al + pad_y * 2 if len(linhas) == 1 else len(linhas) * al + pad_y * 1.55
    except Exception:  # noqa: BLE001  se a legenda mudar por dentro, só não desenha a moldura
        return
    W = c.W
    gap = W * 0.011
    rw, rh = bw + gap * 2, bh + gap * 2
    chave = ("e14_borda", int(rw), int(rh), sem)
    cam = c.g.cache.get(chave)
    if cam is None:
        larg_l, amp = max(1.6, W * 0.0034), W * 0.0012
        margem = larg_l * 3 + amp * 3
        raio = min(rh / 2, f.size * 0.32 + gap)
        per = _perimetro_arredondado(rw, rh, raio) + margem
        cum = _cum(per)
        traco, vazio = W * 0.022, W * 0.013
        tr = []
        s = 0.0
        total = cum[-1]
        while s < total - 1:
            s1 = min(total, s + traco)
            sel = (cum >= s) & (cum <= s1)
            seg = per[sel]
            if len(seg) >= 2:
                tr.append((seg, d.cor(ROSA), 1.0))
            s = s1 + vazio
        parte = _parte(tr, [], rw + 2 * margem, rh + 2 * margem, (0, 0), larg_l, amp, sal=17, sombra=False)
        cam = _render(parte, sem, 1.0, W)
        cam = (cam, margem)
        c.g.cache[chave] = cam
    cam, margem = cam
    d.colar_em(img, cam, (W / 2 - bw / 2 - gap - margem, y - gap - margem), k)


def _perimetro_arredondado(w, h, r, passo=4.0):
    """Pontos ao longo do contorno de um retângulo de cantos arredondados (sentido horário)."""
    r = max(1.0, min(r, w / 2, h / 2))
    partes = [
        _reta((r, 0), (w - r, 0), max(2, int((w - 2 * r) / passo))),
        _arco(w - r, r, r, r, -90, 0, 12),
        _reta((w, r), (w, h - r), max(2, int((h - 2 * r) / passo))),
        _arco(w - r, h - r, r, r, 0, 90, 12),
        _reta((w - r, h), (r, h), max(2, int((w - 2 * r) / passo))),
        _arco(r, h - r, r, r, 90, 180, 12),
        _reta((0, h - r), (0, r), max(2, int((h - 2 * r) / passo))),
        _arco(r, r, r, r, 180, 270, 12),
    ]
    return _juntar(*partes)


def quadro(c):
    g = c.g
    lay = _layout(g)
    t = c.t
    sem = _semente(t)
    tem_m = c.mascara is not None
    k_tom = _tom(c)
    atuais = []
    for e in c.eventos:
        L = lay.get(_chave(e))
        if L is not None and e["inicio"] <= t <= e["fim"]:
            atuais.append((e, L))
    # 1) palco: fundo levemente escurecido em tinta (a pessoa fica em destaque) e, com recorte,
    #    a linha da silhueta — tudo numa passada só
    if tem_m:
        linha, cor_linha = None, None
        for e, L in atuais:
            if L["tipo"] == "contorno":
                linha = _linha_silhueta(c, e, L, sem)
                cor_linha = L["cor"]
                break
        img = _palco_com_recorte(c, 0.16 + 0.22 * k_tom, linha, cor_linha)
        for e, L in atuais:          # desenhos "na parede", atrás da pessoa
            if L.get("atras"):
                (_el_aura if L["tipo"] == "aura" else _el_desenho)(c, img, e, L, sem, atras=c.mascara)
    else:
        img = _palco_sem_recorte(c, k_tom)
        for e, L in atuais:
            if L["tipo"] == "contorno":
                _el_contorno_sem_recorte(c, img, e, L, sem)
    # 2) na frente: desenhos, notas e títulos (nunca sobre o rosto: as posições já fogem dele)
    for e, L in atuais:
        if L.get("atras") and tem_m:
            continue
        if L["tipo"] == "aura":
            _el_aura(c, img, e, L, sem)
        elif L["tipo"] == "desenho":
            _el_desenho(c, img, e, L, sem)
    for e, L in atuais:
        if L["tipo"] == "nota":
            _el_nota(c, img, e, L, sem)
    for e, L in atuais:
        if L["tipo"] == "titulo":
            _el_titulo(c, img, e, L, sem)
    _borda_legenda(c, img, sem)
    return img
