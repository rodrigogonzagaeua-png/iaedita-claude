"""12 · Tela verde — nos momentos-chave da fala o CENÁRIO atrás da pessoa troca: um recorte horizontal
com uma linha de luz revela um fundo desenhado (sala violeta, gradientes, cenas gráficas) com um "print" do
assunto desenhado (cartão, número, gráfico, lista ou matéria) no alto, e uma faixa de título escura entra
embaixo. Depois o recorte volta e devolve o fundo original.

Com recorte (máscara da pessoa): a pessoa fica NA FRENTE do cenário novo. Quando falta espaço para o
print (plano fechado), a pessoa "dá um passo para trás": fica menor, com as bordas do quadro suaves e um
chão na frente do corte, abrindo o alto da tela. O rosto nunca fica atrás de nada.
Sem recorte: o vídeo vira uma janela com moldura clara na frente do cenário novo; o print fica atrás, no
alto, e o recorte de luz passa por trás da janela.

Tudo é função do tempo: a linha do tempo (blocos de cenários, enquadramento da pessoa, cartões) é
calculada em preparar() só a partir do plano e do rosto. A legenda do motor recebe o rosto como ele
aparece NA TELA (depois do recuo), para nunca cair sobre o rosto."""
from __future__ import annotations

import math
import re

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import desenho as d

INFO = {
    "id": "12-tela-verde",
    "nome": "Tela verde",
    "precisa_recorte": True,
    "antes": 0.0,
    "depois": 0.0,
    # legenda da prévia aprovada: Inter 850, creme numa caixa tinta, palavra falada em lavanda; 1 linha
    "legenda": {"peso": 850, "tamanho": 0.062, "cor": "#F8F7F0", "destaque": "#A99ADB", "caixa": "#222729ED",
                "max_caracteres": 18, "max_linhas": 1, "animacao": "subir"},
    "eventos": {
        "cenario": "inicio, fim (3,5-8 s; o último 1 s é a volta): troca o fundo atrás da pessoa. fundo "
                   "('violeta' padrão | 'lima' | 'noite' | 'papel' | 'rosa'), print ('cartao' | 'numero' | "
                   "'grafico' | 'lista' | 'artigo' | 'nenhum'), sobretitulo (1-3 palavras, opcional), titulo "
                   "(2-6 palavras; cartao, grafico, artigo), numero + rotulo (print numero), itens (2-3 itens "
                   "curtos) + tempos (opcional, print lista), valor (opcional, print grafico), faixa (2-5 "
                   "palavras: faixa de título embaixo), som, som_atraso, som_volume",
        "faixa": "inicio, fim (1,5-6 s), texto (2-5 palavras): só a faixa de título embaixo, sem trocar o cenário",
    },
}

TINTA = "#222729"
PAPEL = "#F2F0E7"
CARTAO = "#FBFAF1"
LAVANDA = "#A99ADB"
LIMA = "#D4ED80"

FUNDOS = {  # acento = sobretítulo/ícones · chao = cor do chão que cobre o corte da pessoa recuada
    "violeta": {"acento": "#7862B7", "barra": "#7662BF", "chao": "#2A2159", "cartao": CARTAO},
    "lima": {"acento": "#4E6A12", "barra": "#6F8F1F", "chao": "#37461A", "cartao": CARTAO},
    "noite": {"acento": "#6F5CC0", "barra": "#7662BF", "chao": "#0F1214", "cartao": CARTAO},
    "papel": {"acento": "#7862B7", "barra": "#7662BF", "chao": "#3A3550", "cartao": "#FFFFFF"},
    "rosa": {"acento": "#A2466C", "barra": "#C25F86", "chao": "#5A2A42", "cartao": CARTAO},
}
PRINTS = ("cartao", "numero", "grafico", "lista", "artigo", "nenhum")

JUNTAR = 1.5          # cenários a menos de 1,5 s um do outro viram um bloco (o fundo original não pisca)
HT = 0.31             # alto da cabeça (fração de H) depois do recuo, para abrir espaço ao print
CH = 0.585            # queixo nunca abaixo disto num cenário (legenda e faixa cabem embaixo)
S_MIN = 0.56          # a pessoa nunca fica menor que 56% do tamanho original
CARD_X0, CARD_X1, CARD_Y0 = 0.08, 0.92, 0.12
CARD_H_MIN, CARD_H_MAX = 0.15, 0.25
FAIXA_TOPO, FAIXA_LARG = 0.705, 0.80
BASE_SEGURA = 0.80
I = (1.0, 0.0, 0.0)   # enquadramento original (escala, desloc x, desloc y)

# tempos (s) das transições: entrada relativa ao início do cenário, saída relativa ao fim do bloco
TEMPOS = {
    True: {"wipe_in": (0.0, 0.6), "ref_in": (0.55, 1.05), "ref_out": (-0.95, -0.5), "wipe_out": (-0.5, 0.0),
           "card": (0.15, 0.85), "faixa_in": (0.45, 0.85)},
    # sem recorte: a janela encolhe e, quase junto, a cortina passa atrás dela (pouco tempo de fundo borrado)
    False: {"wipe_in": (0.25, 0.85), "ref_in": (0.0, 0.5), "ref_out": (-0.5, 0.0), "wipe_out": (-0.85, -0.3),
            "card": (0.45, 1.1), "faixa_in": (0.55, 0.95)},
}
CARD_RECUO = (0.75, 1.3)    # com recorte e recuo forte: o print entra quando a pessoa já recuou
ATRASO_RECUO = CARD_RECUO[0] - TEMPOS[True]["card"][0]
TROCA = (0.0, 0.6)          # cenário -> cenário dentro do mesmo bloco
FAIXA_SAI = (-1.05, -0.75)  # faixa sai antes do recorte de volta
_PROIBIDO = re.compile(r"[_{}<>|\\#@]|\b\d{2}-[a-z]|\bestilo\s*\d", re.I)


# ------------------------------------------------------------------ plano: leitura e validação

def _txt(e, campo):
    v = e.get(campo)
    return "" if v is None else str(v).strip()


def _tipo_print(e):
    p = _txt(e, "print").lower()
    if p:
        return p
    if _txt(e, "numero"):
        return "numero"
    if e.get("itens"):
        return "lista"
    return "cartao" if _txt(e, "titulo") else "nenhum"


def _itens(e):
    return [str(x).strip() for x in (e.get("itens") or []) if str(x).strip()][:3]


def _blocos_do_plano(cenas):
    blocos = []
    for c in cenas:
        if blocos and c["inicio"] - blocos[-1]["fim"] < JUNTAR:
            blocos[-1]["cenas"].append(c)
            blocos[-1]["fim"] = max(blocos[-1]["fim"], c["fim"])
        else:
            blocos.append({"ini": c["inicio"], "fim": c["fim"], "cenas": [c]})
    return blocos


def _checar_texto(txt, quando, campo, max_pal, max_letras, p):
    if not txt:
        return
    if len(txt.replace("\n", " ").split()) > max_pal or len(txt) > max_letras:
        p.append(f"{campo} em {quando:.2f}s com texto longo demais ('{txt}'): no máximo {max_pal} palavras / "
                 f"{max_letras} letras.")
    if _PROIBIDO.search(txt):
        p.append(f"{campo} em {quando:.2f}s parece texto interno ('{txt}'): escreva só palavras do assunto.")


def validar(plano, duracao):
    p = []
    evs = plano["eventos"]
    cenas = sorted((e for e in evs if e.get("tipo") == "cenario"), key=lambda e: e["inicio"])
    for e in cenas:
        q = e["inicio"]
        fundo = _txt(e, "fundo").lower() or "violeta"
        if fundo not in FUNDOS:
            p.append(f"Cenário em {q:.2f}s: fundo '{fundo}' não existe. Use: {', '.join(FUNDOS)}.")
        tipo = _tipo_print(e)
        if tipo not in PRINTS:
            p.append(f"Cenário em {q:.2f}s: print '{tipo}' não existe. Use: {', '.join(PRINTS)}.")
        if tipo in ("cartao", "grafico", "artigo") and not _txt(e, "titulo"):
            p.append(f"Cenário em {q:.2f}s: o print '{tipo}' precisa de 'titulo'.")
        if tipo == "numero":
            if not _txt(e, "numero"):
                p.append(f"Cenário em {q:.2f}s: o print 'numero' precisa de 'numero' (ex.: \"26\").")
            elif len(_txt(e, "numero")) > 7:
                p.append(f"Cenário em {q:.2f}s: 'numero' longo demais (até 7 caracteres, ex.: \"3 mil\", \"+80%\").")
            if not _txt(e, "rotulo"):
                p.append(f"Cenário em {q:.2f}s: o print 'numero' precisa de 'rotulo' (o que o número conta).")
        if tipo == "lista":
            it = _itens(e)
            if not 2 <= len(e.get("itens") or []) <= 3:
                p.append(f"Cenário em {q:.2f}s: a lista precisa de 2 ou 3 'itens'.")
            for x in it:
                _checar_texto(x, q, "Item da lista", 4, 22, p)
            tempos = e.get("tempos")
            if tempos is not None:
                if len(tempos) != len(e.get("itens") or []):
                    p.append(f"Cenário em {q:.2f}s: 'tempos' precisa ter um tempo para cada item.")
                elif any(not (e["inicio"] - 0.01 <= float(x) <= e["fim"] - 2.0) for x in tempos):
                    p.append(f"Cenário em {q:.2f}s: cada tempo da lista precisa ficar pelo menos 2 s antes do "
                             f"fim do cenário (fim {e['fim']:.2f}s: último tempo até {e['fim'] - 2.0:.2f}s). O "
                             "último item precisa de ~1 s na tela antes da volta: aumente o 'fim' ou tire o item.")
        _checar_texto(_txt(e, "sobretitulo"), q, "Sobretítulo", 3, 24, p)
        _checar_texto(_txt(e, "titulo"), q, "Título", 7, 44, p)
        _checar_texto(_txt(e, "rotulo"), q, "Rótulo", 5, 32, p)
        _checar_texto(_txt(e, "valor"), q, "Valor", 2, 8, p)
        _checar_texto(_txt(e, "faixa"), q, "Faixa", 5, 28, p)
        if e["fim"] - e["inicio"] > 12.5:
            p.append(f"Cenário em {q:.2f}s dura {e['fim'] - e['inicio']:.1f}s: no máximo 12 s (o ideal é 3-8 s).")
    blocos = _blocos_do_plano(cenas)
    for b in blocos:
        cs = b["cenas"]
        for a, c in zip(cs, cs[1:]):
            if c["inicio"] - a["inicio"] < 2.0:
                p.append(f"Cenários muito juntos em {a['inicio']:.2f}s e {c['inicio']:.2f}s: cada cenário precisa "
                         "de pelo menos 2 s na tela antes do próximo.")
            if (_txt(a, "fundo").lower() or "violeta") == (_txt(c, "fundo").lower() or "violeta"):
                p.append(f"Cenários seguidos em {a['inicio']:.2f}s e {c['inicio']:.2f}s com o mesmo fundo: a troca "
                         "não aparece. Use fundos diferentes (ou deixe mais de 1,5 s entre eles).")
        if b["fim"] - cs[-1]["inicio"] < 2.4:
            p.append(f"Cenário em {cs[-1]['inicio']:.2f}s curto demais: deixe pelo menos 2,5 s (entrada, leitura "
                     "e volta).")
        if b["fim"] > duracao + 0.05:
            p.append(f"Cenário em {cs[-1]['inicio']:.2f}s passa do fim do vídeo ({duracao:.2f}s).")
    if duracao > 8 and blocos:
        tela = sum(min(b["fim"], duracao) - b["ini"] for b in blocos)
        if tela > duracao * 0.75:
            p.append(f"Cenários em {100 * tela / duracao:.0f}% do vídeo: deixe o fundo original aparecer em pelo "
                     "menos 25% (respiro entre as trocas).")
    for e in evs:
        if e.get("tipo") != "faixa":
            continue
        q = e["inicio"]
        txt = _txt(e, "texto")
        if not txt:
            p.append(f"Faixa vazia em {q:.2f}s.")
        _checar_texto(txt, q, "Faixa", 5, 28, p)
        if not 1.2 <= e["fim"] - e["inicio"] <= 8:
            p.append(f"Faixa em {q:.2f}s dura {e['fim'] - e['inicio']:.1f}s: use 1,5 a 6 s.")
        if any(b["ini"] - 0.3 < e["fim"] and e["inicio"] < b["fim"] + 0.3 for b in blocos):
            p.append(f"Faixa em {q:.2f}s está junto de um cenário: use o campo 'faixa' do próprio cenário.")
    return p


# ------------------------------------------------------------------ linha do tempo (pré-calculada)

def _lerp(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


def _medidas_rosto(g, ini, fim):
    """Alto da cabeça, queixo e centro do rosto (pixels) no trecho — valores robustos (percentis)."""
    ts = np.arange(ini, max(fim, ini + 0.05), 0.2)
    cx = np.array([g.rosto.em(float(t)) for t in ts], np.float64)
    x0, y0, x1, y1 = cx[:, 0], cx[:, 1], cx[:, 2], cx[:, 3]
    h = y1 - y0
    topo = float(np.percentile(np.maximum(0.0, y0 - 0.45 * h), 15))
    queixo = float(np.percentile(y1 + 0.08 * h, 85))
    return topo, queixo, float(np.median((x0 + x1) / 2)), float(np.median(x1 - x0)) / g.W


def _enquadramento(W, H, topo, queixo, cx, com_print, largura=0.0):
    """Escala e posição da pessoa no cenário: abre espaço para o print no alto e mantém o queixo acima
    da legenda. Devolve ((s, ox, oy), modo): x' = ox + x*s, y' = oy + y*s; modo 'sobe' = a base da pessoa
    sai da borda de baixo (o chão cobre o corte). largura = largura do rosto / W."""
    ht, chm = HT * H, CH * H
    if not com_print:
        if largura > 0.38:   # plano fechado sem print: um passo leve para trás, senão o cenário quase não aparece
            s = max(S_MIN, 0.80)
        elif queixo <= chm:
            return I, "base"
        else:
            s = max(S_MIN, (H - chm) / max(1.0, H - queixo))
        oy = H * (1 - s)
    else:
        # 1º: base da pessoa na borda de baixo (o mais natural). s_alto = maior escala que abre o alto;
        # s_baixo = menor escala que ainda deixa o queixo acima da legenda.
        s_alto = 1.0 if topo >= ht else (H - ht) / max(1.0, H - topo)
        s_baixo = (H - chm) / max(1.0, H - queixo)  # encolher com a base fixa EMPURRA o queixo para baixo
        s_alto2 = min(1.0, (H - ht + 0.04 * H) / max(1.0, H - topo))  # aceita um print um pouco mais baixo
        if s_alto >= max(s_baixo, S_MIN):
            s, oy = s_alto, H * (1 - s_alto)
        elif max(s_baixo, S_MIN) <= s_alto2:
            s = max(s_baixo, S_MIN)
            oy = H * (1 - s)
        else:  # 2º: plano bem fechado — a pessoa recua e sobe; o chão cobre o corte de baixo
            s = min(1.0, max(S_MIN, (chm - ht) / max(1.0, queixo - topo)))
            oy = chm - queixo * s
    k = min(1.0, (1.0 - s) / 0.2)
    cx2 = cx + (0.5 * W - cx) * k          # quanto mais recua, mais vai para o centro
    ox = cx2 - cx * s
    modo = "sobe" if oy + H * s < H - 1 else "base"
    return (s, ox, oy), modo


def _dados_cena(g, e, j, tem_m):
    W, H = g.W, g.H
    ini, fim = float(e["inicio"]), float(e["fim"])
    tipo = _tipo_print(e)
    if tipo not in PRINTS:
        tipo = "nenhum"
    topo, queixo, cx, larg = _medidas_rosto(g, ini, fim)
    T, modo = _enquadramento(W, H, topo, queixo, cx, tipo != "nenhum", larg)
    s, ox, oy = T
    janela = (max(ox, 0.04 * W), oy + max(0.0, topo - 0.025 * H) * s, min(ox + W * s, 0.96 * W),
              min(oy + H * s, BASE_SEGURA * H))
    lim = (oy + topo * s + 0.03 * H) if tem_m else (janela[1] + 0.015 * H)
    ch = d.limitar(lim - CARD_Y0 * H, CARD_H_MIN * H, CARD_H_MAX * H)
    fundo = _txt(e, "fundo").lower() or "violeta"
    return {"e": e, "j": j, "ini": ini, "fim": fim, "print": tipo, "fundo": fundo if fundo in FUNDOS else "violeta",
            "T": T, "modo": modo, "janela": janela, "cartao": (int(CARD_X0 * W), int(CARD_Y0 * H),
                                                                 int((CARD_X1 - CARD_X0) * W), int(ch)),
            "faixa": _txt(e, "faixa")}


def preparar(g):
    tem_m = bool(g.tem_mascara)
    cenas_ev = sorted((e for e in g.plano["eventos"] if e.get("tipo") == "cenario"), key=lambda e: e["inicio"])
    cenas = [_dados_cena(g, e, j, tem_m) for j, e in enumerate(cenas_ev)]
    blocos = []
    for c in cenas:
        if blocos and c["ini"] - blocos[-1]["fim"] < JUNTAR:
            blocos[-1]["cenas"].append(c)
            blocos[-1]["fim"] = max(blocos[-1]["fim"], c["fim"])
        else:
            blocos.append({"ini": c["ini"], "fim": c["fim"], "cenas": [c]})
    faixas = [{"texto": _txt(e, "texto"), "ini": float(e["inicio"]), "fim": float(e["fim"])}
              for e in g.plano["eventos"] if e.get("tipo") == "faixa" and _txt(e, "texto")]
    for b in blocos:   # plano fechado: o print só aparece quando a pessoa já recuou (revelação limpa)
        for i, c in enumerate(b["cenas"]):
            c["atraso"] = ATRASO_RECUO if (tem_m and i == 0 and c["T"][0] < 0.9) else 0.0
    tl = {"mascara": tem_m, "blocos": blocos, "faixas": faixas, "tempos": TEMPOS[tem_m], "W": g.W, "H": g.H}
    g.cache["_tv"] = tl
    if g.legendas is not None:   # a legenda passa a enxergar o rosto onde ele está NA TELA
        g.legendas.rosto = _RostoNaTela(g.rosto, tl)


class _RostoNaTela:
    """Mesmo contrato de rosto.Rosto, mas com o rosto já recuado/reposicionado pelo cenário."""

    def __init__(self, base, tl):
        self.base, self.tl = base, tl
        self.W, self.H = base.W, base.H
        self.metodo = getattr(base, "metodo", "")

    def em(self, t):
        x0, y0, x1, y1 = self.base.em(t)
        est = _estado(self.tl, t)
        s, ox, oy = est["T"] if est else I
        return (ox + x0 * s, oy + y0 * s, ox + x1 * s, oy + y1 * s)

    def topo_cabeca(self, t):
        x0, y0, x1, y1 = self.em(t)
        return max(0.0, y0 - (y1 - y0) * 0.45)

    def queixo(self, t):
        x0, y0, x1, y1 = self.em(t)
        return y1 + (y1 - y0) * 0.08


def _estado(tl, t):
    """Tudo o que muda com o tempo num bloco de cenários (função pura do plano)."""
    b = next((b for b in tl["blocos"] if b["ini"] <= t <= b["fim"]), None)
    if b is None:
        return None
    W, H = tl["W"], tl["H"]
    tp = tl["tempos"]
    cs = b["cenas"]
    k = 0
    for j, c in enumerate(cs):
        if c["ini"] <= t:
            k = j
    cur = cs[k]
    T, R = cur["T"], cur["janela"]
    if k > 0:
        p = d.suave(d.mapear(t, cur["ini"] + TROCA[0], cur["ini"] + TROCA[1]))
        T = _lerp(cs[k - 1]["T"], T, p)
        R = _lerp(cs[k - 1]["janela"], R, p)
        camadas = [(k - 1, 1.0), (k, p)] if p < 0.999 else [(k, 1.0)]
    else:
        r = d.suave(d.mapear(t, cur["ini"] + tp["wipe_in"][0], cur["ini"] + tp["wipe_in"][1]))
        camadas = [("orig", 1.0), (0, r)]
    r_out = 1.0 - d.suave(d.mapear(t, b["fim"] + tp["wipe_out"][0], b["fim"] + tp["wipe_out"][1]))
    if r_out < 0.999:
        camadas = [("orig", 1.0), (k, min(r_out, camadas[-1][1]))]
    a = d.suave(d.mapear(t, cs[0]["ini"] + tp["ref_in"][0], cs[0]["ini"] + tp["ref_in"][1]))
    z = d.suave(d.mapear(t, b["fim"] + tp["ref_out"][0], b["fim"] + tp["ref_out"][1]))
    kk = a * (1.0 - z)
    T = _lerp(I, T, kk)
    R = _lerp((0.0, 0.0, float(W), float(H)), R, kk)
    return {"bloco": b, "k": k, "camadas": camadas, "T": T, "R": R, "kk": kk}


# ------------------------------------------------------------------ fundos desenhados (uma vez por fundo)

def _grad_vertical(w, h, paradas):
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)
    pos = np.array([p for p, _ in paradas], np.float32)
    cols = np.array([d.cor(c) for _, c in paradas], np.float32)
    lin = np.stack([np.interp(ys, pos, cols[:, k]) for k in range(4)], axis=1)
    return Image.fromarray(np.repeat(lin[:, None, :], w, axis=1).astype(np.uint8), "RGBA")


def _luz(img, cx, cy, raio, cor_luz, alfa, potencia=1.0):
    """Luz radial suave (calculada pequena e ampliada: rápida e sem degraus)."""
    w, h = img.size
    f = 4
    sw, sh = max(2, w // f), max(2, h // f)
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    dist = np.sqrt((xx * f - cx) ** 2 + (yy * f - cy) ** 2) / max(1.0, raio)
    a = (np.clip(1.0 - dist, 0, 1) ** potencia) * alfa * 255
    cam = Image.new("RGBA", (sw, sh), d.cor(cor_luz, 1.0))
    cam.putalpha(Image.fromarray(a.astype(np.uint8), "L"))
    img.alpha_composite(cam.resize((w, h), Image.BILINEAR))


def _linear(img, angulo, c0, c1):
    """Gradiente linear por cima (ângulo como no CSS: 0 = para cima, 90 = para a direita)."""
    w, h = img.size
    a = math.radians(angulo)
    vx, vy = math.sin(a), -math.cos(a)
    comp = abs(w * vx) + abs(h * vy)
    f = 4
    sw, sh = max(2, w // f), max(2, h // f)
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    p = np.clip(((xx * f - w / 2) * vx + (yy * f - h / 2) * vy) / comp + 0.5, 0, 1)[..., None]
    a0, a1 = np.array(d.cor(c0), np.float32), np.array(d.cor(c1), np.float32)
    arr = (a0 * (1 - p) + a1 * p).astype(np.uint8)
    img.alpha_composite(Image.fromarray(arr, "RGBA").resize((w, h), Image.BILINEAR))


def _camada_2x(w, h):
    return Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))


def _assentar_2x(img, cam, opacidade=1.0):
    cam = cam.resize(img.size, Image.LANCZOS)
    if opacidade < 0.999:
        cam.putalpha(cam.getchannel("A").point(lambda v: int(v * opacidade)))
    img.alpha_composite(cam)


def _aneis(img, cx, cy, r0, passo, n, cor_l, larg, opacidade):
    w, h = img.size
    cam = _camada_2x(w, h)
    dr = ImageDraw.Draw(cam)
    for i in range(n):
        r = (r0 + i * passo) * 2
        dr.ellipse((cx * 2 - r, cy * 2 - r, cx * 2 + r, cy * 2 + r), outline=d.cor(cor_l), width=max(2, int(larg * 2)))
    _assentar_2x(img, cam, opacidade)


def _fundo_violeta(W, H):
    """A sala violeta da prévia aprovada: parede com moldura, janela, abajur, chão e sofá, tingidos de
    violeta, luz clara no alto e anéis finos atrás da cabeça."""
    S = W / 1080.0
    img = Image.new("RGBA", (W, H), d.cor("#8170B5"))
    _luz(img, 0.18 * W, 0.20 * H, 0.58 * math.hypot(0.82 * W, 0.80 * H), "#FFF7DC", 0.6)
    _linear(img, 110, (0, 0, 0, 0), (0, 0, 0, 22))
    cam = _camada_2x(W, H)
    dr = ImageDraw.Draw(cam)
    q = 2.0
    lw = max(2, int(3 * S * q))
    x0, y0, x1, y1 = 95 * S * q, 0.0625 * H * q, 745 * S * q, 0.547 * H * q
    dr.rectangle((x0, y0, x1, y1), outline=d.cor("#C2BCAE"), width=lw)
    ins = 21 * S * q
    dr.rectangle((x0 + ins, y0 + ins, x1 - ins, y1 - ins), outline=d.cor("#C2BCAE"), width=lw)
    # abajur à esquerda
    dr.rectangle((40 * S * q, 0.354 * H * q, 47 * S * q, 0.573 * H * q), fill=d.cor("#685A40"))
    dr.pieslice((-45 * S * q, 0.318 * H * q, 135 * S * q, 0.318 * H * q + 280 * S * q), 180, 360,
                fill=d.cor("#D8C8A1"))
    _assentar_2x(img, cam)
    _luz(img, 45 * S, 0.33 * H, 200 * S, "#FFF0BF", 0.4)
    # janela em perspectiva à direita
    pw, ph = int(295 * S), int(1130 * S)
    jan = Image.new("RGBA", (pw, ph), d.cor("#786B55"))
    b = max(2, int(20 * S))
    jan.paste(d.cor("#AD9E86"), (b, b, pw - b, ph - b))
    vid = _grad_vertical(pw - 2 * int(28 * S), ph - 2 * int(28 * S), [(0, "#D0DBCA"), (0.65, "#A3BAAF"), (1, "#7C9690")])
    dv = ImageDraw.Draw(vid)
    bb = max(2, int(12 * S))
    dv.rectangle((0, 0, vid.width - 1, vid.height - 1), outline=d.cor("#766C58"), width=bb)
    dv.rectangle((int(110 * S), 0, int(120 * S), vid.height), fill=d.cor("#766C58"))
    jan.alpha_composite(vid, (int(28 * S), int(28 * S)))
    jx0, jx1 = 0.80 * W, 1.07 * W
    cantos = [(jx0, 0.112 * H), (jx1, 0.096 * H), (jx1, 0.70 * H), (jx0, 0.682 * H)]
    img.alpha_composite(d.perspectiva(jan, cantos, (W, H)))
    # chão e sofá
    dr = ImageDraw.Draw(img)
    yc = int(H - 550 * S)
    dr.rectangle((0, yc, W, H), fill=d.cor("#C3B9A5"))
    dr.rectangle((0, yc, W, yc + int(12 * S)), fill=d.cor("#A99D88"))
    sofa = d.painel(int(1260 * S), int(490 * S), int(100 * S), gradiente=("#879C8B", "#647C6A"))
    so, (sdx, sdy) = d.sombra(sofa, raio=30 * S, opacidade=0.25, desloc=(0, 30 * S))
    img.alpha_composite(so, (int(-90 * S) + sdx, int(H - 150 * S - 490 * S) + sdy))
    assento = d.painel(int(1040 * S), int(245 * S), int(60 * S), fundo="#7E9482")
    img.alpha_composite(assento, (int(20 * S), int(H - 240 * S - 245 * S)))
    # tinta violeta por cima de tudo (como na prévia) + luz lilás + anéis
    _luz(img, 0.65 * W, 0.34 * H, 0.6 * math.hypot(0.65 * W, 0.66 * H), "#E3D8FF", 0.47)
    _linear(img, 140, (0x48, 0x2E, 0x95, 0x77), (0x76, 0x62, 0xBF, 0x55))
    _aneis(img, 0.5 * W, 0.4167 * H, 180 * S, 72 * S, 12, "#F2E7FF", 2 * S, 0.3)
    return img


def _fundo_lima(W, H):
    img = _grad_vertical(W, H, [(0, "#EDF8BE"), (0.5, "#D4ED80"), (1, "#AECD52")])
    _luz(img, 0.5 * W, 0.30 * H, 0.55 * H, "#FFFFFF", 0.55)
    cam = _camada_2x(W, H)
    dr = ImageDraw.Draw(cam)
    # sol claro atrás da cabeça
    r = 0.40 * W * 2
    cx, cy = 0.5 * W * 2, 0.40 * H * 2
    dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=d.cor("#F7FCDF", 0.55))
    # retícula de pontos nos cantos (cena gráfica)
    passo = 0.036 * W * 2
    for gy in np.arange(0, H * 2 + passo, passo):
        for gx in np.arange(0, W * 2 + passo, passo):
            u, v = gx / (W * 2), gy / (H * 2)
            k = max(0.0, 1 - math.hypot(u, v * 1.4) / 0.55) + max(0.0, 1 - math.hypot(1 - u, (1 - v) * 1.4) / 0.6)
            if k <= 0.02:
                continue
            rr = passo * 0.22 * min(1.0, k)
            dr.ellipse((gx - rr, gy - rr, gx + rr, gy + rr), fill=d.cor("#3E5410", 0.22))
    _assentar_2x(img, cam)
    _aneis(img, 0.5 * W, 0.40 * H, 0.46 * W, 0.075 * W, 6, "#3E5410", W / 1080 * 2, 0.16)
    return img


def _fundo_noite(W, H):
    img = _grad_vertical(W, H, [(0, "#2D3437"), (0.6, "#1A1F21"), (1, "#101315")])
    _luz(img, 0.80 * W, 0.16 * H, 0.52 * H, "#7662BF", 0.6, 1.2)
    _luz(img, 0.50 * W, 0.44 * H, 0.40 * H, "#D4ED80", 0.16, 1.4)
    cam = _camada_2x(W, H)
    dr = ImageDraw.Draw(cam)
    yh = 0.64 * H * 2
    lw = max(2, int(W / 1080 * 2 * 2))
    for i in range(-14, 15):
        dr.line((W + i * 0.03 * W * 2, yh, W + i * 0.20 * W * 2, H * 2), fill=d.cor(LIMA), width=lw)
    for j in range(1, 10):
        y = yh + (H * 2 - yh) * (j / 9) ** 1.8
        dr.line((0, y, W * 2, y), fill=d.cor(LIMA), width=lw)
    # o grid nasce no horizonte (some suave perto dele)
    a = np.asarray(cam.getchannel("A"), np.float32)
    ys = np.arange(cam.height, dtype=np.float32)[:, None]
    a *= np.clip((ys - yh) / (0.16 * H * 2), 0, 1) * 0.30
    cam.putalpha(Image.fromarray(a.astype(np.uint8), "L"))
    dr = ImageDraw.Draw(cam)
    rng = np.random.default_rng(12)
    for _ in range(70):
        x, y = rng.uniform(0, W * 2), rng.uniform(0, 0.55 * H * 2)
        rr = rng.uniform(1.0, 2.6) * W / 1080 * 2
        dr.ellipse((x - rr, y - rr, x + rr, y + rr), fill=d.cor("#FFFFFF", rng.uniform(0.25, 0.6)))
    _assentar_2x(img, cam)
    return img


def _fundo_papel(W, H):
    img = Image.new("RGBA", (W, H), d.cor(PAPEL))
    _luz(img, 0.10 * W, 0.12 * H, 0.42 * W, LIMA, 0.45, 1.3)
    _luz(img, 0.95 * W, 0.70 * H, 0.55 * W, LAVANDA, 0.40, 1.3)
    _luz(img, 0.32 * W, 0.24 * H, 0.60 * H, "#FFFFFF", 0.55)
    cam = _camada_2x(W, H)
    dr = ImageDraw.Draw(cam)
    passo = 0.06 * W * 2
    lw = max(2, int(W / 1080 * 2 * 2))
    for x in np.arange(passo / 2, W * 2, passo):
        dr.line((x, 0, x, H * 2), fill=d.cor("#CFC8B6"), width=lw)
    for y in np.arange(passo / 2, H * 2, passo):
        dr.line((0, y, W * 2, y), fill=d.cor("#CFC8B6"), width=lw)
    _assentar_2x(img, cam, 0.55)
    return img


def _fundo_rosa(W, H):
    img = _grad_vertical(W, H, [(0, "#F8DAE5"), (0.55, "#E9A3BC"), (1, "#D78AA7")])
    _luz(img, 0.62 * W, 0.30 * H, 0.52 * H, "#FFFFFF", 0.5)
    _luz(img, 0.95 * W, 0.08 * H, 0.45 * W, LAVANDA, 0.45, 1.2)
    _aneis(img, 0.02 * W, 0.98 * H, 0.30 * W, 0.10 * W, 10, "#FFFFFF", W / 1080 * 2.4, 0.28)
    _aneis(img, 0.5 * W, 0.40 * H, 0.42 * W, 0.08 * W, 4, "#FFFFFF", W / 1080 * 2, 0.18)
    return img


_DESENHO_FUNDO = {"violeta": _fundo_violeta, "lima": _fundo_lima, "noite": _fundo_noite,
                  "papel": _fundo_papel, "rosa": _fundo_rosa}


def _fundo_img(g, nome):
    chave = ("_tv_fundo", nome, g.W, g.H)
    if chave not in g.cache:
        g.cache[chave] = _DESENHO_FUNDO.get(nome, _fundo_violeta)(g.W, g.H)
    return g.cache[chave]


# ------------------------------------------------------------------ prints (cartões desenhados)

def _topo_tinta(f, txt):
    return f.getbbox(txt or "H")[1]


def _altura_tinta(f, linhas, al):
    linhas = [l for l in linhas if l]
    if not linhas:
        return 0
    return (len(linhas) - 1) * al + f.getbbox(linhas[-1])[3] - f.getbbox(linhas[0])[1]


def _escrever_tinta(cam, x, y, linhas, f, cor_txt, al, alinhar="esquerda", larg=0):
    """Escreve com o TOPO DA TINTA da 1ª linha em y (fontes serifadas têm muito respiro em cima)."""
    linhas = [l for l in linhas if l]
    if not linhas:
        return
    dr = ImageDraw.Draw(cam)
    top = _topo_tinta(f, linhas[0])
    for i, l in enumerate(linhas):
        lx = x if alinhar == "esquerda" else x + (larg - f.getlength(l)) / 2
        dr.text((lx, y - top + i * al), l, font=f, fill=d.cor(cor_txt))


def _ajustar_linhas(txt, larg, alt, peso, familia, tam_max, tam_min, max_linhas, entrelinha=1.0):
    partes = [p.strip() for p in str(txt).split("\n") if p.strip()]
    if len(partes) > 1:  # quebra de linha escolhida pelo agente
        tam = int(tam_max)
        while tam >= tam_min:
            f = d.fonte(tam, peso, familia)
            al = tam * entrelinha
            if all(f.getlength(l) <= larg for l in partes) and al * (len(partes) - 1) + tam * 0.8 <= alt:
                return f, partes, al
            tam = int(tam * 0.94) if tam > 40 else tam - 2
    return d.ajustar_texto(" ".join(partes), larg, alt, peso, familia, int(tam_max), int(tam_min),
                           max_linhas, entrelinha)


def _sobre(cam, x, y, txt, tam, cor_txt, larg_max):
    """Sobretítulo em maiúsculas com letras espaçadas (como 'UMA NOVA CENA' da prévia). y = topo da tinta."""
    txt = txt.upper()
    f = d.fonte(tam, 650)
    esp = tam * 0.13
    total = sum(f.getlength(ch) for ch in txt) + esp * max(0, len(txt) - 1)
    if total > larg_max:
        esp = max(0.0, esp - (total - larg_max) / max(1, len(txt) - 1))
    dr = ImageDraw.Draw(cam)
    bb = f.getbbox("H")
    cx = x
    for ch in txt:
        dr.text((cx, y - bb[1]), ch, font=f, fill=d.cor(cor_txt))
        cx += f.getlength(ch) + esp
    return bb[3] - bb[1]


def _altura_sobre(tam):
    bb = d.fonte(tam, 650).getbbox("H")
    return bb[3] - bb[1]


def _painel_cartao(cw, ch, W, fundo):
    raio = int(0.028 * W)
    if fundo == "papel":
        return d.painel(cw, ch, raio, fundo="#FFFFFF", borda="#E2DCCB", larg_borda=max(1, int(W / 540)))
    return d.painel(cw, ch, raio, fundo=FUNDOS[fundo]["cartao"])


def _layout_cartao(cena, W, H):
    """Desenha a parte fixa do print e devolve {img, off, dinamico}. off = canto do painel dentro de img."""
    x, y, cw, ch = cena["cartao"]
    e, fundo, tipo = cena["e"], cena["fundo"], cena["print"]
    ac = FUNDOS[fundo]["acento"]
    pan = _painel_cartao(cw, ch, W, fundo)
    pad = int(min(0.05 * W, 0.17 * ch))
    sob = _txt(e, "sobretitulo")
    fs_e = max(10, int(0.036 * W))
    alt_e = _altura_sobre(fs_e) if sob else 0
    gap = int(0.024 * W)
    din = {}
    if tipo == "cartao":
        area_h = ch - 2 * pad - (alt_e + gap if sob else 0)
        f, linhas, al = _ajustar_linhas(_txt(e, "titulo"), cw - 2 * pad, area_h, 600, "serif",
                                        0.105 * W, 0.06 * W, 2, 0.98)
        bloco = (alt_e + gap if sob else 0) + _altura_tinta(f, linhas, al)
        yy = (ch - bloco) / 2
        if sob:
            _sobre(pan, pad, yy, sob, fs_e, ac, cw - 2 * pad)
            yy += alt_e + gap
        _escrever_tinta(pan, pad, yy, linhas, f, TINTA, al)
    elif tipo == "numero":
        num, rot = _txt(e, "numero"), _txt(e, "rotulo")
        y0 = pad + (alt_e + gap if sob else 0)
        area_h = ch - pad - y0
        ref = d.fonte(200, 700, "serif")
        bb = ref.getbbox("0123456789%")
        razao = (bb[3] - bb[1]) / 200
        tam = int(area_h * 0.92 / razao)
        fn = d.fonte(tam, 700, "serif")
        larg_max = (cw - 2 * pad) * 0.52
        if fn.getlength(num) > larg_max:
            tam = int(tam * larg_max / fn.getlength(num))
            fn = d.fonte(tam, 700, "serif")
        wn = fn.getlength(num)
        bbn = fn.getbbox(num)
        yn = y0 + (area_h - (bbn[3] - bbn[1])) / 2
        xl = pad + wn + 0.045 * W
        fr, lr, alr = d.ajustar_texto(rot, cw - pad - xl, area_h, 750, "inter", int(0.056 * W),
                                      int(0.038 * W), 3, 1.1)
        yl = y0 + (area_h - _altura_tinta(fr, lr, alr)) / 2
        _escrever_tinta(pan, xl, yl, lr, fr, TINTA, alr)
        barra = d.painel(int(0.1 * W), max(3, int(0.009 * W)), max(1, int(0.0045 * W)), fundo=FUNDOS[fundo]["barra"])
        pan.alpha_composite(barra, (int(xl), int(min(ch - pad * 0.6, yl + _altura_tinta(fr, lr, alr) + 0.022 * W))))
        if sob:
            _sobre(pan, pad, pad, sob, fs_e, ac, cw - 2 * pad)
        m = re.fullmatch(r"(\D*)(\d{1,6})(\D*)", num)
        din = {"tipo": "numero", "texto": num, "fonte": fn, "x": pad, "y": yn - bbn[1],  # origem: linha de base fixa
               "conta": (m.group(1), int(m.group(2)), m.group(3)) if m else None}
    elif tipo == "grafico":
        wc = (cw - 2 * pad) * 0.54
        area_h = ch - 2 * pad - (alt_e + gap if sob else 0)
        f, linhas, al = _ajustar_linhas(_txt(e, "titulo"), wc, area_h, 600, "serif", 0.09 * W, 0.056 * W, 3, 0.98)
        bloco = (alt_e + gap if sob else 0) + _altura_tinta(f, linhas, al)
        yy = (ch - bloco) / 2
        if sob:
            _sobre(pan, pad, yy, sob, fs_e, ac, wc)
            yy += alt_e + gap
        _escrever_tinta(pan, pad, yy, linhas, f, TINTA, al)
        xa0, xa1 = pad + wc + 0.05 * W, cw - pad
        ya0, ya1 = pad * 0.9, ch - pad
        valor = _txt(e, "valor")
        fv = d.fonte(int(0.044 * W), 800)
        dr = ImageDraw.Draw(pan)
        dr.line((xa0, ya1, xa1, ya1), fill=d.cor(TINTA, 0.2), width=max(2, int(W / 540)))
        din = {"tipo": "grafico", "area": (xa0, ya0, xa1, ya1), "valor": valor, "fv": fv,
               "cor": FUNDOS[fundo]["barra"]}
    elif tipo == "lista":
        itens = _itens(e)
        y0 = pad + (alt_e + gap if sob else 0)
        area_h = ch - pad - y0
        n = max(1, len(itens))
        fs = int(min(0.054 * W, area_h / (n * 1.32)))
        fs = max(int(0.036 * W), fs)
        while fs > int(0.036 * W):
            fi = d.fonte(fs, 700)
            if all(fs * 1.25 + 0.025 * W + fi.getlength(x) <= cw - 2 * pad for x in itens):
                break
            fs -= 1
        fi = d.fonte(fs, 700)
        passo = area_h / n
        tiras = []
        for item in itens:
            badge = int(fs * 1.18)
            tira = Image.new("RGBA", (int(cw - 2 * pad), int(max(badge, fs * 1.3)) + 2), (0, 0, 0, 0))
            circ = d.painel(badge, badge, badge // 2, fundo=FUNDOS[fundo]["barra"])
            ic = d.icone("check", int(badge * 0.72), "#FFFFFF", 0.13)
            circ.alpha_composite(ic, ((badge - ic.width) // 2, (badge - ic.height) // 2))
            tira.alpha_composite(circ, (0, (tira.height - badge) // 2))
            bb = fi.getbbox("Hx")  # mesma linha de base para todos os itens (acentos não desalinham)
            ImageDraw.Draw(tira).text((badge + 0.025 * W, tira.height / 2 - (bb[1] + bb[3]) / 2), item, font=fi,
                                      fill=d.cor(TINTA))
            tiras.append(tira)
        if sob:
            _sobre(pan, pad, pad, sob, fs_e, ac, cw - 2 * pad)
        din = {"tipo": "lista", "tiras": tiras, "x": pad, "y0": y0, "passo": passo, "tempos": _tempos_lista(cena)}
    elif tipo == "artigo":
        hs = int(max(0.16 * ch, 0.045 * W))
        topo = Image.new("RGBA", (cw, hs), d.cor("#ECE8DC"))
        dt = ImageDraw.Draw(topo)
        rr = hs * 0.15
        for i, cc in enumerate(("#E9A3BC", "#D4ED80", "#A99ADB")):
            cx0 = pad * 0.7 + rr + i * rr * 3.0
            dt.ellipse((cx0 - rr, hs / 2 - rr, cx0 + rr, hs / 2 + rr), fill=d.cor(cc))
        px0 = pad * 0.7 + rr * 9.5
        pill = d.painel(int(cw - px0 - pad * 0.7), int(hs * 0.52), int(hs * 0.26), fundo="#F9F7F1")
        topo.alpha_composite(pill, (int(px0), int(hs * 0.24)))
        topo.putalpha(ImageChops.multiply(topo.getchannel("A"), pan.getchannel("A").crop((0, 0, cw, hs))))
        pan.alpha_composite(topo)
        wc = (cw - 2 * pad) * 0.64
        y0 = hs + pad * 0.6
        area_h = ch - pad * 0.8 - y0
        fs_s = max(10, int(0.035 * W))
        alt_s = _altura_sobre(fs_s) if sob else 0
        f, linhas, al = _ajustar_linhas(_txt(e, "titulo"), wc, area_h - (alt_s + gap * 0.8 if sob else 0), 600,
                                        "serif", 0.085 * W, 0.056 * W, 2, 0.98)
        yy = y0
        if sob:
            _sobre(pan, pad, yy, sob, fs_s, ac, wc)
            yy += alt_s + gap * 0.8
        _escrever_tinta(pan, pad, yy, linhas, f, TINTA, al)
        yy += _altura_tinta(f, linhas, al) + gap
        dr = ImageDraw.Draw(pan)
        hl = max(3, int(0.011 * W))
        for frac in (1.0, 0.72):
            if yy + hl > ch - pad * 0.6:
                break
            dr.rounded_rectangle((pad, yy, pad + wc * frac, yy + hl), hl // 2, fill=d.cor("#E3DFD3"))
            yy += hl + 0.018 * W
        ix0 = int(pad + wc + 0.04 * W)
        iw, ih = int(cw - pad - ix0), int(area_h)
        if iw > 20 and ih > 20:
            foto = d.painel(iw, ih, int(0.02 * W), gradiente=(LAVANDA, FUNDOS[fundo]["barra"]))
            df = ImageDraw.Draw(foto)
            sr = min(iw, ih) * 0.16
            df.ellipse((iw * 0.68 - sr, ih * 0.3 - sr, iw * 0.68 + sr, ih * 0.3 + sr), fill=d.cor("#FFFFFF", 0.85))
            mont = Image.new("RGBA", (iw, ih), (0, 0, 0, 0))
            ImageDraw.Draw(mont).polygon([(0, ih), (iw * 0.38, ih * 0.5), (iw * 0.62, ih * 0.78), (iw * 0.8, ih * 0.6),
                                          (iw, ih * 0.82), (iw, ih)], fill=d.cor("#FFFFFF", 0.55))
            mont.putalpha(ImageChops.multiply(mont.getchannel("A"), foto.getchannel("A")))
            foto.alpha_composite(mont)
            pan.alpha_composite(foto, (ix0, int(y0)))
    som, (dx, dy) = d.sombra(pan, raio=0.035 * W, opacidade=0.18 if fundo != "noite" else 0.4,
                             desloc=(0, 0.018 * W))
    return {"img": som, "off": (-dx, -dy), "din": din, "pos": (x, y)}


def _cartao_no_tempo(c, cena):
    chave = ("_tv_cartao", cena["j"], c.g.W, c.g.H, cena["cartao"])
    if chave not in c.g.cache:
        c.g.cache[chave] = _layout_cartao(cena, c.W, c.H)
    lay = c.g.cache[chave]
    din = lay["din"]
    if not din:
        return lay
    t = c.t
    at = cena.get("atraso", 0.0)
    img = lay["img"].copy()
    ox, oy = lay["off"]
    W = c.W
    if din["tipo"] == "numero":
        txt = din["texto"]
        if din["conta"]:
            pre, n, suf = din["conta"]
            k = d.saida(d.mapear(t, cena["ini"] + 0.55 + at, cena["ini"] + 1.45 + at))
            txt = f"{pre}{int(round(n * k))}{suf}"
        ImageDraw.Draw(img).text((ox + din["x"], oy + din["y"]), txt, font=din["fonte"], fill=d.cor(TINTA))
    elif din["tipo"] == "grafico":
        xa0, ya0, xa1, ya1 = din["area"]
        n = 4
        alturas = (0.30, 0.47, 0.66, 1.0)
        gapb = (xa1 - xa0) * 0.07
        bw = ((xa1 - xa0) - gapb * (n - 1)) / n
        dr = ImageDraw.Draw(img)
        topos = []
        for i in range(n):
            k = d.mola(d.mapear(t, cena["ini"] + 0.75 + at + i * 0.13, cena["ini"] + 1.3 + at + i * 0.13), 0.6)
            hb = (ya1 - ya0) * alturas[i] * k
            x0 = ox + xa0 + i * (bw + gapb)
            if hb > 2:
                cor_b = din["cor"] if i == n - 1 else LAVANDA
                dr.rounded_rectangle((x0, oy + ya1 - hb, x0 + bw, oy + ya1), int(min(bw * 0.18, hb / 2)), fill=d.cor(cor_b))
            topos.append((x0 + bw / 2, oy + ya1 - hb))
        kl = d.suave(d.mapear(t, cena["ini"] + 1.35 + at, cena["ini"] + 1.85 + at))
        if kl > 0.01:
            larg = max(2, int(W * 0.006))
            pts = [(px, py - 0.03 * W) for px, py in topos]
            seg = kl * (len(pts) - 1)
            vis = [pts[0]]
            for i in range(1, len(pts)):
                if seg >= i:
                    vis.append(pts[i])
                else:
                    f = seg - (i - 1)
                    if f > 0:
                        vis.append((pts[i - 1][0] + (pts[i][0] - pts[i - 1][0]) * f,
                                    pts[i - 1][1] + (pts[i][1] - pts[i - 1][1]) * f))
                    break
            if len(vis) > 1:
                dr.line(vis, fill=d.cor(TINTA), width=larg, joint="curve")
                ex, ey = vis[-1]
                rr = larg * 1.6
                dr.ellipse((ex - rr, ey - rr, ex + rr, ey + rr), fill=d.cor(TINTA))
        if din["valor"]:
            kv = d.saida(d.mapear(t, cena["ini"] + 1.6 + at, cena["ini"] + 1.95 + at))
            if kv > 0.01:
                fv = din["fv"]
                camv = Image.new("RGBA", (int(fv.getlength(din["valor"]) + 4), int(fv.size * 1.3)), (0, 0, 0, 0))
                ImageDraw.Draw(camv).text((2, 0), din["valor"], font=fv, fill=d.cor(din["cor"]))
                # no canto de cima à esquerda do gráfico: ali as barras são baixas e a seta ainda não subiu
                d.colar_em(img, camv, (ox + xa0, oy + ya0 + (1 - kv) * fv.size * 0.4), kv)
    elif din["tipo"] == "lista":
        for i, (tira, ti) in enumerate(zip(din["tiras"], din["tempos"])):
            k = d.saida(d.mapear(t, ti, ti + 0.35))
            if k <= 0.01:
                continue
            yy = din["y0"] + i * din["passo"] + (din["passo"] - tira.height) / 2
            d.colar_em(img, tira, (ox + din["x"] - (1 - k) * 0.03 * W, oy + yy), k)
    return {"img": img, "off": lay["off"], "pos": lay["pos"]}


def _tempo_cartao(tl, cena):
    """Quando o print se assenta (s desde o início do cenário). Cenário encadeado: junto com a cortina."""
    b = next((b for b in tl["blocos"] if cena in b["cenas"]), None)
    if b is not None and b["cenas"][0] is not cena:
        return (0.15, 0.85)
    if cena.get("atraso", 0.0) > 0:
        return CARD_RECUO
    return tl["tempos"]["card"]


def _desenhar_print(c, img, cena, x_corte):
    """Print no alto do cenário, ATRÁS da pessoa; recortado junto com o fundo pela cortina de luz."""
    if cena["print"] == "nenhum" or x_corte <= 0:
        return
    lay = _cartao_no_tempo(c, cena)
    tp = c.g.cache["_tv"]["tempos"]
    a0, a1 = _tempo_cartao(c.g.cache["_tv"], cena)
    p = d.mapear(c.t, cena["ini"] + a0, cena["ini"] + a1)
    cam = lay["img"]
    tl = c.g.cache["_tv"]
    sai = 0.0
    if tl["mascara"]:  # com recorte: o print sobe e some ANTES de a pessoa voltar ao tamanho original
        b = next((b for b in tl["blocos"] if b["cenas"][-1] is cena), None)
        if b is not None:
            q0 = b["fim"] + tp["ref_out"][0]
            if cena["print"] == "lista":   # o último item fica ~1 s inteiro na tela antes de o cartão sair
                q0 = min(max(q0, max(_tempos_lista(cena), default=0.0) + 1.12), b["fim"] + tp["wipe_out"][0] - 0.22)
            sai = d.suave(d.mapear(c.t, q0 - 0.12, q0 + 0.22))
    x, y = lay["pos"]
    cx = x + lay["img"].width / 2 - lay["off"][0]
    cy = y + lay["img"].height / 2 - lay["off"][1] - (1 - d.saida(p)) * 0.035 * c.H - sai * 0.03 * c.H
    px, py = int(round(cx - cam.width / 2)), int(round(cy - cam.height / 2))
    alfa = d.saida(d.mapear(p, 0, 0.5)) * (1 - sai)
    if alfa <= 0.003:
        return
    if x_corte < c.W:
        w = x_corte - px
        if w <= 0:
            return
        cam = cam.crop((0, 0, min(cam.width, w), cam.height))
    d.colar_em(img, cam, (px, py), alfa)


# ------------------------------------------------------------------ peças da composição

def _fundo_quadro(c, cena, x_corte):
    big = _fundo_img(c.g, cena["fundo"])
    if x_corte >= c.W:
        return big.copy()
    return big.crop((0, 0, max(1, x_corte), c.H))


def _faixa_luz(g):
    """Linha de luz verde-clara com brilho, na borda da cortina (pré-desenhada)."""
    chave = ("_tv_luz", g.W, g.H)
    if chave not in g.cache:
        W, H = g.W, g.H
        gw = max(12, int(0.12 * W)) | 1
        xs = np.arange(gw, dtype=np.float32) - gw // 2
        nucleo = np.clip(0.0035 * W + 0.5 - np.abs(xs), 0, 1)
        brilho = np.exp(-(xs ** 2) / (2 * (0.02 * W) ** 2)) * 0.6
        a = np.maximum(nucleo, brilho)
        cor_n, cor_b = np.array(d.cor("#E9FFC4")[:3], np.float32), np.array(d.cor("#EFFFD1")[:3], np.float32)
        rgb = cor_b[None, :] * (1 - nucleo[:, None]) + cor_n[None, :] * nucleo[:, None]
        linha = np.concatenate([rgb, (a * 255)[:, None]], axis=1).astype(np.uint8)
        g.cache[chave] = Image.fromarray(np.repeat(linha[None, :, :], H, axis=0), "RGBA")
    return g.cache[chave]


def _pena(g, com_base):
    """Máscara (L) que suaviza as bordas do quadro original quando a pessoa recua (sem 'corte reto')."""
    chave = ("_tv_pena", g.W, g.H, com_base)
    if chave not in g.cache:
        W, H = g.W, g.H

        def rampa(n):
            r = np.linspace(0, 1, max(2, n), dtype=np.float32)
            return r * r * (3 - 2 * r)
        fx = np.ones(W, np.float32)
        n = int(0.07 * W)
        fx[:n] = rampa(n)
        fx[-n:] = rampa(n)[::-1]
        fy = np.ones(H, np.float32)
        nt = int(0.02 * H)
        fy[:nt] = rampa(nt)
        if com_base:
            nb = int(0.06 * H)
            fy[-nb:] = rampa(nb)[::-1]
        g.cache[chave] = Image.fromarray((fy[:, None] * fx[None, :] * 255).astype(np.uint8), "L")
    return g.cache[chave]


def _pena_escala(g, com_base, s):
    """A máscara de bordas suaves já no tamanho da pessoa recuada (fica em cache enquanto a escala não muda)."""
    w, h = max(1, int(round(g.W * s))), max(1, int(round(g.H * s)))
    chave = ("_tv_pena_s", com_base, w, h)
    if chave not in g.cache:
        for k in [k for k in g.cache if isinstance(k, tuple) and k[0] == "_tv_pena_s"]:
            del g.cache[k]   # guarda só a escala atual (as de transição não se repetem)
        g.cache[chave] = _pena(g, com_base).resize((w, h), Image.BILINEAR)
    return g.cache[chave]


def _colar_com_mascara(img, src, xy, mascara):
    """Cola src (RGB/RGBA opaco) em img usando uma máscara L — uma passada só (mais rápido que
    putalpha + alpha_composite). Aceita posições fora da tela."""
    x, y = int(round(xy[0])), int(round(xy[1]))
    W, H = img.size
    x0, y0 = max(0, -x), max(0, -y)
    x1, y1 = min(src.width, W - x), min(src.height, H - y)
    if x1 <= x0 or y1 <= y0:
        return
    if (x0, y0, x1, y1) != (0, 0, src.width, src.height):
        src, mascara = src.crop((x0, y0, x1, y1)), mascara.crop((x0, y0, x1, y1))
    img.paste(src, (x + x0, y + y0), mascara)


def _caixa_mascara(m):
    """Retângulo da pessoa na máscara (medido numa cópia 8x menor: rápido; margem de 8 px)."""
    peq = m.reduce(8)
    b = peq.getbbox()
    if not b:
        return None
    return (max(0, b[0] * 8 - 8), max(0, b[1] * 8 - 8), min(m.width, b[2] * 8 + 8), min(m.height, b[3] * 8 + 8))


def _fechar_pescoco(m, rosto, k, alto):
    """Fecha o 'buraco' que o recorte às vezes deixa entre o queixo e a roupa (ex.: um objeto no peito):
    sem isso a cabeça parece flutuar sobre o cenário. Só na faixa logo abaixo do queixo e no miolo do rosto;
    cada coluna é preenchida apenas entre pessoa em cima e pessoa embaixo (o fundo real em volta fica).
    m: máscara (pode já estar recortada/reduzida); rosto: caixa do rosto nas coordenadas de m; k: escala de m;
    alto: altura do quadro na escala de m."""
    W, H = m.size
    x0, y0, x1, y1 = rosto
    fw, fh = x1 - x0, y1 - y0
    if fw < 20 * k or fh <= 0:
        return m
    f = 4 if k > 0.75 else 2
    ya, yb = int(max(0, y1 - 0.12 * fh)) // f, int(min(H, y1 + 0.12 * alto)) // f
    xa, xb = int(max(0, (x0 + x1) / 2 - 0.34 * fw)) // f, int(min(W, (x0 + x1) / 2 + 0.34 * fw)) // f
    if yb - ya < 3 or xb - xa < 3:
        return m
    peq = np.asarray(m.reduce(f, box=(xa * f, ya * f, xb * f, yb * f))) > 110
    cima = np.maximum.accumulate(peq, axis=0)
    baixo = np.maximum.accumulate(peq[::-1], axis=0)[::-1]
    buraco = cima & baixo & ~peq
    if not buraco.any():
        return m
    # bordas laterais suaves (o preenchimento some aos poucos nas pontas da faixa)
    nx = buraco.shape[1]
    rampa = np.clip(np.minimum(np.arange(nx), np.arange(nx)[::-1]) / max(1.0, nx * 0.12), 0, 1)
    enche = Image.fromarray(((buraco | peq) * rampa[None, :] * 255).astype(np.uint8), "L")
    caixa = (xa * f, ya * f, xb * f, yb * f)
    enche = enche.resize((caixa[2] - caixa[0], caixa[3] - caixa[1]), Image.BILINEAR)
    m = m.copy()
    m.paste(ImageChops.lighter(m.crop(caixa), enche), caixa[:2])
    return m


def _encher_corpo(m, rosto, k):
    """Buracos e partes meio transparentes DENTRO do corpo (da metade do rosto para baixo; ex.: um celular
    na mão) ficam sólidos: senão o cenário novo aparece em manchas por dentro da roupa. Só onde há pessoa
    nos 4 lados (esquerda, direita, cima e baixo) — o fundo real entre braço e corpo, aberto para a borda,
    fica. Mesmos argumentos de _fechar_pescoco."""
    W, H = m.size
    x0, y0, x1, y1 = rosto
    f = 4 if k > 0.75 else 2
    ya = int(min(H - 4 * f, max(0, (y0 + y1) / 2))) // f   # a cabeça conta como "pessoa em cima"
    if H // f - ya < 4 or W // f < 4:
        return m
    val = np.asarray(m.reduce(f, box=(0, ya * f, W - W % f, H - H % f)))
    peq = val > 110
    if not peq.any():
        return m
    esq = np.maximum.accumulate(peq, axis=1)
    dir_ = np.maximum.accumulate(peq[:, ::-1], axis=1)[:, ::-1]
    cima = np.maximum.accumulate(peq, axis=0)
    baixo = np.maximum.accumulate(peq[::-1], axis=0)[::-1]
    dentro = esq & dir_ & cima & baixo
    solido = Image.fromarray((dentro * 255).astype(np.uint8), "L").filter(ImageFilter.MinFilter(3))
    falta = (np.asarray(solido) > 128) & (val < 200)   # onde o corpo ainda não está sólido
    if not falta.any():
        return m   # máscara boa (o caso comum): nada a fazer, sem cópia
    ys, xs = np.nonzero(falta)
    a0, a1 = max(0, xs.min() - 2), min(solido.width, xs.max() + 3)
    b0, b1 = max(0, ys.min() - 2), min(solido.height, ys.max() + 3)
    caixa = (a0 * f, (ya + b0) * f, a1 * f, (ya + b1) * f)
    solido = solido.resize((caixa[2] - caixa[0], caixa[3] - caixa[1]), Image.BILINEAR, box=(a0, b0, a1, b1))
    m = m.copy()
    m.paste(ImageChops.lighter(m.crop(caixa), solido), caixa[:2])
    return m


def _consertar_mascara(c, m, origem, k):
    """Conserta a máscara já recortada (origem = canto da caixa no quadro) e reduzida pela escala k."""
    x0, y0, x1, y1 = c.g.rosto.em(c.t)
    rosto = ((x0 - origem[0]) * k, (y0 - origem[1]) * k, (x1 - origem[0]) * k, (y1 - origem[1]) * k)
    return _encher_corpo(_fechar_pescoco(m, rosto, k, c.H * k), rosto, k)


def _pessoa(c, img, T, x_vis):
    """Pessoa recortada por cima do cenário, no tamanho/posição do enquadramento T.
    x_vis: até onde (a partir da esquerda) o cenário novo aparece."""
    s, ox, oy = T
    H = c.H
    m = c.mascara
    caixa = _caixa_mascara(m)
    if not caixa:
        return
    if s > 0.999 and abs(ox) < 0.5 and abs(oy) < 0.5:
        # mesmo enquadramento: só onde o cenário aparece (no resto o quadro original já tem a pessoa)
        x1 = min(caixa[2], int(x_vis))
        if x1 <= caixa[0]:
            return
        mc = _consertar_mascara(c, m.crop(caixa), caixa, 1.0)   # conserta com a pessoa inteira, depois corta
        caixa2 = (caixa[0], caixa[1], x1, caixa[3])
        img.paste(c.fonte.crop(caixa2), (caixa[0], caixa[1]), mc.crop((0, 0, x1 - caixa[0], caixa[3] - caixa[1])))
        return
    kf = d.limitar((1 - s) / 0.05)
    base = oy + H * s < H - 1
    cw, chh = caixa[2] - caixa[0], caixa[3] - caixa[1]
    nw, nh = max(1, int(round(cw * s))), max(1, int(round(chh * s)))
    # reduz ANTES de mexer na máscara (RGB + L separados: bem mais rápido que RGBA pré-multiplicado).
    # O quadro vira RGB inteiro (barato) e é reduzido direto da caixa; recuo forte: reduce(2) antes.
    fr = c.fonte.convert("RGB")
    if s < 0.6:
        bx = (caixa[0] - caixa[0] % 2, caixa[1] - caixa[1] % 2, caixa[2] - caixa[2] % 2, caixa[3] - caixa[3] % 2)
        pc = fr.reduce(2, box=bx).resize((nw, nh), Image.BILINEAR)
    else:
        pc = fr.resize((nw, nh), Image.BILINEAR, box=caixa, reducing_gap=2.0)
    mc = _consertar_mascara(c, m.resize((nw, nh), Image.BILINEAR, box=caixa, reducing_gap=2.0), caixa, nw / cw)
    if kf > 0.01:
        fc = _pena_escala(c.g, base, s).crop((int(round(caixa[0] * s)), int(round(caixa[1] * s)),
                                             int(round(caixa[0] * s)) + nw, int(round(caixa[1] * s)) + nh))
        if kf < 0.99:
            fc = Image.blend(Image.new("L", fc.size, 255), fc, kf)
        mc = ImageChops.multiply(mc, fc)
    _colar_com_mascara(img, pc, (ox + caixa[0] * s, oy + caixa[1] * s), mc)


def _degrade_chao(g):
    """Alfa (L) do 'chão': 0 em cima -> 255 depois de 7,5% da altura (curva suave)."""
    chave = ("_tv_chao_a", g.W, g.H)
    if chave not in g.cache:
        h, gh = g.H, int(0.075 * g.H)
        a = np.ones(h, np.float32)
        r = np.linspace(0, 1, gh, dtype=np.float32)
        a[:gh] = r * r * (3 - 2 * r)
        g.cache[chave] = Image.fromarray(np.repeat((a * 255).astype(np.uint8)[:, None], g.W, axis=1), "L")
    return g.cache[chave]


def _chao(c, img, cena, T, x_corte):
    """Quando a pessoa recua e sobe, a parte de baixo dela se dissolve no próprio cenário (sem corte reto)."""
    s, ox, oy = T
    W, H = c.W, c.H
    base = oy + H * s
    if base >= H - 1:
        return
    a = d.limitar((H - base) / (0.02 * H))
    y0 = int(round(base - 0.09 * H))
    if y0 >= H:
        return
    x1 = max(1, min(W, int(x_corte)))
    cam = _fundo_img(c.g, cena["fundo"]).crop((0, max(0, y0), x1, H))
    alfa = _degrade_chao(c.g).crop((0, max(0, -y0), x1, max(0, -y0) + cam.height))
    if a < 0.999:
        alfa = alfa.point(lambda v: int(v * a))
    img.paste(cam, (0, max(0, y0)), alfa)


def _mascara_arred(w, h, r, _cantos={}):
    """Máscara de cantos arredondados rápida (cantos prontos em cache; serve para tamanhos que mudam)."""
    m = Image.new("L", (w, h), 255)
    r = int(min(r, w // 2, h // 2))
    if r < 2:
        return m
    if r not in _cantos:
        ss = 4
        im = Image.new("L", (r * ss * 2, r * ss * 2), 0)
        ImageDraw.Draw(im).ellipse((0, 0, r * ss * 2 - 1, r * ss * 2 - 1), fill=255)
        _cantos[r] = im.resize((r * 2, r * 2), Image.LANCZOS).crop((0, 0, r, r))
    cn = _cantos[r]
    m.paste(cn, (0, 0))
    m.paste(cn.transpose(Image.FLIP_LEFT_RIGHT), (w - r, 0))
    m.paste(cn.transpose(Image.FLIP_TOP_BOTTOM), (0, h - r))
    m.paste(cn.transpose(Image.ROTATE_180), (w - r, h - r))
    return m


def _anel(w, h, miolo):
    """Retângulos (x0, y0, x1, y1) que cobrem w x h, menos o miolo — o miolo vai ficar coberto pelo vídeo,
    então não precisa ser pintado (metade do trabalho a menos em cada quadro da transição)."""
    ix0, iy0, ix1, iy1 = [int(v) for v in miolo]
    ix0, iy0, ix1, iy1 = max(0, ix0), max(0, iy0), min(w, ix1), min(h, iy1)
    if ix1 <= ix0 or iy1 <= iy0:
        return [(0, 0, w, h)]
    rs = [(0, 0, w, iy0), (0, iy1, w, h), (0, iy0, ix0, iy1), (ix1, iy0, w, iy1)]
    return [r for r in rs if r[2] > r[0] and r[3] > r[1]]


def _janela_moldura(c, img, R, kk):
    """Sem recorte: sombra suave + moldura cor de papel da janela (parte que não muda com o vídeo)."""
    W = c.W
    x0, y0, x1, y1 = [int(round(v)) for v in R]
    w, h = x1 - x0, y1 - y0
    if w < 8 or h < 8 or kk <= 0.02:
        return
    raio = int(0.035 * W * kk)
    b = int(round(0.007 * W * kk))
    rm = raio + b                      # raio da moldura
    f, mg = 6, 8
    sw, sh = max(2, (w + 2 * b) // f), max(2, (h + 2 * b) // f)
    sm = Image.new("L", (sw + 2 * mg, sh + 2 * mg), 0)
    ImageDraw.Draw(sm).rounded_rectangle((mg, mg, mg + sw, mg + sh), max(1, raio // f), fill=int(255 * 0.35 * kk))
    sm = sm.filter(ImageFilter.GaussianBlur(4))
    dy = int(round(0.014 * c.H * kk))
    px, py = x0 - b - mg * f, y0 - b - mg * f + dy
    # miolo da sombra que a moldura cobre por inteiro (em coordenadas da sombra ampliada)
    miolo = (mg * f + rm + 2, mg * f - dy + rm + 2, mg * f + w + 2 * b - rm - 2, mg * f - dy + h + 2 * b - rm - 2)
    for (a0, b0, a1, b1) in _anel(sm.width * f, sm.height * f, miolo):
        m = sm.resize((a1 - a0, b1 - b0), Image.BILINEAR, box=(a0 / f, b0 / f, a1 / f, b1 / f))
        _colar_com_mascara(img, Image.new("RGB", m.size, (12, 10, 24)), (px + a0, py + b0), m)
    if b >= 1:
        mm = _mascara_arred(w + 2 * b, h + 2 * b, rm)
        for (a0, b0, a1, b1) in _anel(mm.width, mm.height, (rm + 1, rm + 1, mm.width - rm - 1, mm.height - rm - 1)):
            img.paste(d.cor(CARTAO), (x0 - b + a0, y0 - b + b0, x0 - b + a1, y0 - b + b1), mm.crop((a0, b0, a1, b1)))


def _janela(c, img, T, R, kk, com_moldura=True):
    """Sem recorte: o vídeo vira uma janela com moldura clara na frente do cenário."""
    s, ox, oy = T
    W = c.W
    x0, y0, x1, y1 = [int(round(v)) for v in R]
    w, h = x1 - x0, y1 - y0
    if w < 8 or h < 8:
        return
    if com_moldura:
        _janela_moldura(c, img, R, kk)
    caixa = (d.limitar((x0 - ox) / s, 0, c.W), d.limitar((y0 - oy) / s, 0, c.H),
             d.limitar((x1 - ox) / s, 0, c.W), d.limitar((y1 - oy) / s, 0, c.H))
    bx0, by0 = int(caixa[0]), int(caixa[1])
    bx1, by1 = min(c.W, int(math.ceil(caixa[2]))), min(c.H, int(math.ceil(caixa[3])))
    if abs(s - 1) < 1e-4 and (bx1 - bx0, by1 - by0) == (w, h):
        conteudo = c.fonte.crop((bx0, by0, bx1, by1))
    else:  # reduz direto do quadro em RGB (sem recortar antes: mais rápido)
        conteudo = c.fonte.convert("RGB").resize((w, h), Image.BILINEAR, box=caixa)
    raio = int(0.035 * W * kk)
    if raio >= 2:
        chave = ("_tv_mjan", w, h, raio)
        m = c.g.cache.get(chave)
        if m is None:
            m = _mascara_arred(w, h, raio)
            if kk >= 0.999:
                c.g.cache[chave] = m
        img.paste(conteudo, (x0, y0), m)
    else:
        img.paste(conteudo, (x0, y0))


# ------------------------------------------------------------------ faixa de título

def _caixa_faixa(g):
    chave = ("_tv_faixa_caixa", g.W, g.H)
    if chave not in g.cache:
        W = g.W
        bw = int(FAIXA_LARG * W)
        fs_max = int(0.070 * W)
        bh = int(fs_max * 1.62)
        cx = d.painel(bw, bh, int(0.013 * W), fundo=d.cor(TINTA, 0.97))
        som, (dx, dy) = d.sombra(cx, raio=0.02 * W, opacidade=0.3, desloc=(0, 0.008 * W))
        g.cache[chave] = {"img": som, "off": (-dx, -dy), "bw": bw, "bh": bh, "fs": fs_max}
    return g.cache[chave]


def _texto_faixa(g, txt):
    chave = ("_tv_faixa_txt", txt, g.W, g.H)
    if chave not in g.cache:
        cx = _caixa_faixa(g)
        W = g.W
        larg = cx["bw"] - 2 * int(0.045 * W)
        f, linhas, _ = d.ajustar_texto(txt, larg, cx["bh"], 800, "inter", cx["fs"], int(0.044 * W), 1)
        linha = " ".join(linhas)
        cam = Image.new("RGBA", (cx["bw"], cx["bh"]), (0, 0, 0, 0))
        bb = f.getbbox("Hx")  # centro pela altura das maiúsculas: textos diferentes ficam na mesma linha
        ImageDraw.Draw(cam).text(((cx["bw"] - f.getlength(linha)) / 2, cx["bh"] / 2 - (bb[1] + bb[3]) / 2), linha,
                                 font=f, fill=d.cor(PAPEL))
        g.cache[chave] = cam
    return g.cache[chave]


def _faixa_y(c, bh, em_cena):
    """Topo da faixa: logo abaixo do lugar da legenda (nunca em cima dela), dentro da zona segura."""
    H = c.H
    topo = FAIXA_TOPO * H
    leg = c.g.legendas
    if leg is not None:
        try:
            alt = leg.f.size * 1.18 + leg.f.size * 0.56
            topo = max(topo, leg._y(c.t, alt) + alt + 0.014 * H)
        except Exception:  # noqa: BLE001  (sem legenda/motor diferente: posição padrão)
            pass
    if topo + bh > BASE_SEGURA * H:
        return BASE_SEGURA * H - bh if em_cena else 0.125 * H
    return topo


def _estado_faixa_bloco(tl, est, t):
    b, k = est["bloco"], est["k"]
    cs = b["cenas"]
    tp = tl["tempos"]
    cur = cs[k]
    tx = cur["faixa"]
    sai = 1.0 - d.entrada(d.mapear(t, b["fim"] + FAIXA_SAI[0], b["fim"] + FAIXA_SAI[1]))
    if k == 0:
        if not tx:
            return None
        ent = d.saida(d.mapear(t, cur["ini"] + tp["faixa_in"][0], cur["ini"] + tp["faixa_in"][1]))
        a = ent * sai
        return {"alfa": a, "dy": (1 - a) * 0.03, "textos": [(tx, 1.0, 0.0)]}
    ant = cs[k - 1]["faixa"]
    p = d.suave(d.mapear(t, cur["ini"] + 0.15, cur["ini"] + 0.55))
    if ant and tx:
        if ant == tx:
            return {"alfa": sai, "dy": (1 - sai) * 0.03, "textos": [(tx, 1.0, 0.0)]}
        return {"alfa": sai, "dy": (1 - sai) * 0.03, "textos": [(ant, 1 - p, -0.7 * p), (tx, p, 0.7 * (1 - p))]}
    if ant:
        return {"alfa": 1 - p, "dy": p * 0.03, "textos": [(ant, 1.0, 0.0)]}
    if tx:
        a = p * sai
        return {"alfa": a, "dy": (1 - a) * 0.03, "textos": [(tx, 1.0, 0.0)]}
    return None


def _estado_faixa_avulsa(tl, t):
    for f in tl["faixas"]:
        if f["ini"] <= t <= f["fim"]:
            a = d.envelope(t, f["ini"], f["fim"], 0.4, 0.3)
            return {"alfa": a, "dy": (1 - a) * 0.03, "textos": [(f["texto"], 1.0, 0.0)]}
    return None


def _desenhar_faixa(c, img, st, em_cena):
    if not st or st["alfa"] <= 0.003:
        return
    cx = _caixa_faixa(c.g)
    bw, bh = cx["bw"], cx["bh"]
    y = _faixa_y(c, bh, em_cena) + st["dy"] * c.H
    x = (c.W - bw) / 2
    cam = cx["img"].copy()
    dentro = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    for txt, a, ddy in st["textos"]:
        if a > 0.003 and txt:
            d.colar_em(dentro, _texto_faixa(c.g, txt), (0, ddy * bh), a)
    cam.alpha_composite(dentro, cx["off"])
    d.colar_em(img, cam, (x - cx["off"][0], y - cx["off"][1]), st["alfa"])


# ------------------------------------------------------------------ quadro

def _camadas_visiveis(camadas):
    """Só a partir da última camada que cobre a tela inteira (o resto está escondido)."""
    ini = 0
    for i, (_, r) in enumerate(camadas):
        if r >= 0.999:
            ini = i
    return camadas[ini:]


def _compor_cenario(c, est, fundo_orig):
    """Fundo original (ou borrado) + cenários com a cortina de luz. Devolve (img, linha)."""
    W = c.W
    cs = est["bloco"]["cenas"]
    img, linha = None, None
    for camada, r in _camadas_visiveis(est["camadas"]):
        if camada == "orig":
            img = fundo_orig()
            continue
        if r <= 0.0005:
            continue
        x_corte = W if r >= 0.999 else int(round(r * W))
        cena = cs[camada]
        fq = _fundo_quadro(c, cena, x_corte)
        if img is None:
            if x_corte >= W:
                img = fq
            else:
                img = fundo_orig()
                img.paste(fq, (0, 0))
        else:
            img.paste(fq, (0, 0))
        _desenhar_print(c, img, cena, x_corte)
        if r < 0.999:
            linha = (x_corte, math.sin(math.pi * r))
    if img is None:
        img = fundo_orig()
    return img, linha


def _tempos_lista(cena):
    """Quando cada item da lista entra (s absolutos): o tempo do plano, nunca antes de o cartão aparecer."""
    at = cena.get("atraso", 0.0)
    n = len(_itens(cena["e"]))
    tempos = cena["e"].get("tempos")
    if not tempos or len(tempos) != n:
        tempos = [cena["ini"] + 0.85 + at + 0.4 * i for i in range(n)]
    return [max(float(q), cena["ini"] + 0.5 + 0.75 * at) for q in tempos]


def _fim_animacao(cena):
    """Segundos (desde o início do cenário) até o print terminar de se montar."""
    tipo = cena["print"]
    at = cena.get("atraso", 0.0)
    if tipo == "numero":
        return 1.5 + at
    if tipo == "grafico":
        return 2.0 + at
    if tipo == "lista":
        return max([0.0] + [q - cena["ini"] + 0.4 for q in _tempos_lista(cena)])
    return 0.0


def _assentado(tl, est, t):
    """Cenário parado (sem cortina, sem recuo mudando, print montado): o fundo pode vir pronto do cache."""
    cs, k = est["bloco"]["cenas"], est["k"]
    cena = cs[k]
    vis = _camadas_visiveis(est["camadas"])
    if len(vis) != 1 or vis[0][0] != k or est["kk"] < 0.999:
        return False
    tp = tl["tempos"]
    t0 = cena["ini"] + max(_tempo_cartao(tl, cena)[1], TROCA[1] if k > 0 else tp["wipe_in"][1],
                           _fim_animacao(cena)) + 0.02
    if t < t0:
        return False
    if k == len(cs) - 1 and t > est["bloco"]["fim"] + tp["ref_out"][0] - 0.14:
        return False
    return True


def _base_assentada(c, tl, est):
    cena = est["bloco"]["cenas"][est["k"]]
    chave = ("_tv_estavel", cena["j"], tl["mascara"], c.W, c.H)
    if chave not in c.g.cache:
        for k in [k for k in c.g.cache if isinstance(k, tuple) and k[0] == "_tv_estavel"]:
            del c.g.cache[k]
        img = _fundo_img(c.g, cena["fundo"]).copy()
        _desenhar_print(c, img, cena, c.W)
        if not tl["mascara"]:
            _janela_moldura(c, img, est["R"], 1.0)
        c.g.cache[chave] = img
    return c.g.cache[chave].copy()


def _borrado(c):
    """Sem recorte: o fundo original desfocado e um pouco mais escuro, em volta da janela. Barato: amostrado
    pequeno (o desfoque forte esconde a amostragem) e ampliado em dois passos."""
    W, H = c.W, c.H
    peq = c.fonte.resize((max(4, W // 4), max(4, H // 4)), Image.NEAREST).reduce(2)
    peq = peq.filter(ImageFilter.GaussianBlur(max(1.0, 0.04 * W / 8)))
    peq = peq.point(lambda v: int(v * 0.78))
    peq.putalpha(255)
    return peq.resize((max(4, W // 4), max(4, H // 4)), Image.BILINEAR).resize((W, H), Image.NEAREST)


def quadro(c):
    tl = c.g.cache.get("_tv")
    if tl is None:
        preparar(c.g)
        tl = c.g.cache["_tv"]
    est = _estado(tl, c.t)
    if est is None:
        st = _estado_faixa_avulsa(tl, c.t)
        if not st:
            return c.fonte
        img = c.fonte.copy()
        _desenhar_faixa(c, img, st, False)
        return img
    W, H = c.W, c.H
    cs = est["bloco"]["cenas"]
    T = est["T"]
    luz = _faixa_luz(c.g)
    parado = _assentado(tl, est, c.t)
    if tl["mascara"] and c.mascara is not None:
        if parado:
            img, linha = _base_assentada(c, tl, est), None
        else:
            img, linha = _compor_cenario(c, est, lambda: c.fonte.copy())
        if linha:
            d.colar_em(img, luz, (linha[0] - luz.width // 2, 0), linha[1])
        x_vis = max(((W if r >= 0.999 else r * W) for camada, r in est["camadas"] if camada != "orig"), default=0)
        _pessoa(c, img, T, x_vis + luz.width / 2)
        for camada, r in _camadas_visiveis(est["camadas"]):
            if camada != "orig" and r > 0.0005:
                _chao(c, img, cs[camada], T, W if r >= 0.999 else int(round(r * W)))
    else:
        if est["kk"] <= 0.001:   # a janela ainda é a tela inteira: nada do cenário aparece
            img = c.fonte.copy()
        elif parado:             # cenário + print + moldura prontos; só o vídeo entra na janela
            img = _base_assentada(c, tl, est)
            _janela(c, img, T, est["R"], 1.0, com_moldura=False)
        else:
            img, linha = _compor_cenario(c, est, lambda: _borrado(c))
            if linha:
                d.colar_em(img, luz, (linha[0] - luz.width // 2, 0), linha[1])
            _janela(c, img, T, est["R"], est["kk"])
    _desenhar_faixa(c, img, _estado_faixa_bloco(tl, est, c.t), True)
    return img
