"""18 · Halo de Topo — título e selos SOBEM DE TRÁS DA CABEÇA, com um halo (anel luminoso) em volta do
topo da cabeça e o fundo escurecido. Estilo feito para plano fechado (rosto grande).

Como cria espaço no plano fechado: quando falta lugar acima da cabeça, a câmera "desce" — o quadro inteiro
desliza para baixo com curva suave e abre um céu escuro no topo, onde o título entra. A câmera volta quando
o título sai. A legenda acompanha o rosto deslocado (o estilo cria a própria legenda com o rosto na tela).

Camadas, de trás para a frente: vídeo deslocado + céu → fundo escurecido → brilho atrás da cabeça → halo →
onda do pulso → selo → título → [pessoa recortada por cima] → título "na frente" (só se não couber) →
selo redondo → legenda.
Sem recorte: o título nasce de uma linha logo acima da cabeça (nunca passa pelo rosto), o escurecimento
para no topo da cabeça e o anel é apagado dentro de uma elipse estimada da cabeça.

Tudo é função só do tempo e do plano (o motor renderiza partes em paralelo). As medidas de cada evento
são calculadas uma vez em `_estado` e as camadas de texto ficam em g.cache."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import desenho as d
from ..legenda import Legendas, PerfilLegenda

# ------------------------------------------------------------------ identidade (prévia aprovada / Scene18)
VERDE = "#D4ED80"
CLARO = "#F8FAED"
ESCURO = (12, 22, 25)          # #0C1619 — céu e escurecimento
SELO_FUNDO = "#17271FEB"
SELO_BORDA = "#D4ED8077"
SELO_TXT = "#F1F6E9"
TINTA = "#26362B"              # ícone sobre o círculo verde

# ------------------------------------------------------------------ medidas (frações de W/H)
TOPO_SEG = 0.115               # zona segura de cima (H)
ESQ_SEG, DIR_SEG = 0.06, 0.90  # o título fica entre estas margens (W) — a direita é dos botões da rede
DESLOC_MAX = 0.24              # quanto a câmera pode descer (H)
TOPO_CABECA = 0.38             # topo do cabelo ≈ topo da caixa do rosto − 0,38 × altura do rosto
JUNTAR = 1.6                   # eventos com intervalo menor que isso dividem a mesma descida de câmera
F2, F2_MIN = 0.165, 0.085      # linha verde (destaque): tamanho cheio e mínimo (W)
F1_MIN = 0.058                 # linha branca: mínimo (W)
FS = 0.044                     # texto do selo (W)
TRACK = -0.035                 # espaçamento entre letras do título (em)
PULSO_DUR = 0.75
ESC_FIM = 0.64                 # o fundo escurecido vai do topo até aqui (H)

ICONES = ("seta", "check", "estrela", "raio", "play", "coracao", "dinheiro", "alvo", "grafico", "seta_cima",
          "nenhum")
PLACEHOLDERS = ("seu texto", "sua ideia em destaque", "texto aqui", "lorem", "{", "}", "halo de topo",
                "18-halo", "evento", "placeholder")

INFO = {
    "id": "18-halo-topo",
    "nome": "Halo de Topo",
    "precisa_recorte": True,
    "antes": 0.2,
    "depois": 0.6,
    # pílula escura no peito, uma linha, palavra falada em verde (DemoCaption "halo")
    "legenda": {"peso": 750, "tamanho": 0.054, "cor": "#FFFFFF", "destaque": VERDE, "caixa": "#101919EE",
                "max_caracteres": 18, "max_linhas": 1, "animacao": "pop", "posicao": "auto"},
    # o estilo monta a legenda ele mesmo (com o rosto já deslocado pela câmera) — o texto é a fala normal
    "legenda_propria": True,
    "eventos": {
        "halo": "inicio, fim (2-6 s): o título sobe de trás da cabeça, com o halo e o fundo escurecido. "
                "destaque (OBRIGATÓRIO: linha grande verde, 1-2 palavras, até 14 letras), texto (opcional: linha "
                "branca menor em cima, até 4 palavras / 24 letras), selo (opcional: etiqueta pequena acima do "
                "título, até 24 letras), icone (opcional: selo redondo verde na ponta do halo: "
                "seta|check|estrela|raio|play|coracao|dinheiro|alvo|grafico|seta_cima|nenhum), som",
        "selo": "inicio, fim (1,2-4 s): só uma etiqueta sobe de trás da cabeça, com o halo (sem título grande). "
                "texto (2-4 palavras, até 24 letras), icone (opcional, dentro da etiqueta), som",
        "pulso": "inicio, fim (0,3-0,8 s): uma onda de luz verde sai do contorno da cabeça; se houver halo na "
                 "tela, a palavra verde dá um pulo. som (opcional)",
    },
}


# ================================================================== curvas

def _crit(k):
    """Mola criticamente amortecida (a do Remotion com damping 22 / stiffness 125): sobe rápido, assenta
    sem passar do ponto."""
    k = d.limitar(k)
    x = 6.0 * k
    return min(1.0, (1 - (1 + x) * math.exp(-x)) / 0.98265)


def _bump(u, dur=0.34):
    """0 → 1 → 0 em 'dur' segundos (pulo curto)."""
    if u < 0 or u > dur:
        return 0.0
    return math.sin(math.pi * u / dur)


# ================================================================== validação do plano

def _textos(e):
    dest = str(e.get("destaque") or "").strip()
    txt = str(e.get("texto") or "").strip()
    if e.get("tipo") == "halo" and not dest and txt:   # reserva: última palavra vira o destaque
        partes = txt.split()
        dest, txt = partes[-1], " ".join(partes[:-1])
    return dest, txt


def validar(plano, duracao):
    p = []
    evs = plano.get("eventos", [])
    blocos = sorted((e for e in evs if e.get("tipo") in ("halo", "selo")), key=lambda e: e["inicio"])
    for e in evs:
        tipo = e.get("tipo")
        ini = float(e.get("inicio", 0))
        dur = float(e.get("fim", ini)) - ini
        todos = " ".join(str(e.get(k) or "") for k in ("texto", "destaque", "selo")).lower()
        if any(x in todos for x in PLACEHOLDERS):
            p.append(f"{tipo} em {ini:.2f}s: texto parece placeholder ou rótulo interno — use palavras da fala.")
        if tipo == "halo":
            dest = str(e.get("destaque") or "").strip()
            txt = str(e.get("texto") or "").strip()
            if not dest:
                p.append(f"Halo em {ini:.2f}s sem 'destaque' (a linha verde grande é obrigatória).")
            elif len(dest) > 14 or len(dest.split()) > 2:
                p.append(f"Halo em {ini:.2f}s: 'destaque' longo demais ('{dest}'): máx. 2 palavras / 14 letras.")
            if len(txt) > 24 or len(txt.split()) > 4:
                p.append(f"Halo em {ini:.2f}s: 'texto' longo demais ('{txt}'): máx. 4 palavras / 24 letras.")
            if len(str(e.get("selo") or "")) > 24:
                p.append(f"Halo em {ini:.2f}s: 'selo' longo demais (máx. 24 letras).")
            if dest.rstrip().endswith(".") or txt.rstrip().endswith("."):
                p.append(f"Halo em {ini:.2f}s: título sem ponto final.")
            if dur < 1.8:
                p.append(f"Halo em {ini:.2f}s curto demais ({dur:.1f}s): mínimo 1,8 s para subir e ser lido.")
            if dur > 7.5:
                p.append(f"Halo em {ini:.2f}s longo demais ({dur:.1f}s): máximo ~6 s; divida em dois.")
        elif tipo == "selo":
            txt = str(e.get("texto") or "").strip()
            if not txt:
                p.append(f"Selo em {ini:.2f}s sem 'texto'.")
            elif len(txt) > 24:
                p.append(f"Selo em {ini:.2f}s: texto longo demais ('{txt}'): máx. 24 letras.")
            if dur < 1.2 or dur > 5.5:
                p.append(f"Selo em {ini:.2f}s com {dur:.1f}s: use de 1,2 a 4 s.")
        elif tipo == "pulso":
            if dur > 1.2:
                p.append(f"Pulso em {ini:.2f}s longo demais: é um efeito de 0,3-0,8 s na palavra forte.")
        ic = e.get("icone")
        if ic is not None and str(ic) not in ICONES:
            p.append(f"{tipo} em {ini:.2f}s: ícone '{ic}' não existe. Use: {', '.join(ICONES)}.")
    for a, b in zip(blocos, blocos[1:]):
        if b["inicio"] < a["fim"] - 0.01:
            p.append(f"'{b.get('tipo')}' em {b['inicio']:.2f}s começa antes do '{a.get('tipo')}' anterior acabar "
                     f"({a['fim']:.2f}s): um título/selo de cada vez.")
    if duracao > 10 and blocos:
        ocupado = sum(e["fim"] - e["inicio"] for e in blocos)
        if ocupado > duracao * 0.6:
            p.append(f"Halo/selo na tela em {ocupado / duracao:.0%} do vídeo: deixe respiros (máx. ~55%).")
    pul = [e for e in evs if e.get("tipo") == "pulso"]
    if duracao > 6 and len(pul) > duracao / 3:
        p.append("Pulsos demais: no máximo 1 a cada 4-5 s, só nas palavras mais fortes.")
    return p


# ================================================================== medidas do rosto e do texto

def _medir_rosto(g, t0, t1):
    r = g.rosto
    ts = np.arange(max(0.0, t0), max(t0, min(t1, g.duracao)) + 1e-6, 0.1)
    if len(ts) == 0:
        ts = np.array([max(0.0, t0)])
    cx, lw, y0, topo, boca, queixo = [], [], [], [], [], []
    for t in ts:
        a, b, c_, e = r.em(float(t))
        cx.append((a + c_) / 2)
        lw.append(c_ - a)
        y0.append(b)
        topo.append(b - (e - b) * TOPO_CABECA)   # sem travar em 0: a cabeça pode sair por cima
        boca.append(e - (e - b) * 0.22)
        queixo.append(r.queixo(float(t)))
    return {"cx": float(np.median(cx)), "lw": float(np.median(lw)), "y0": float(np.percentile(y0, 20)),
            "topo": float(np.percentile(topo, 20)), "boca": float(np.percentile(boca, 80)),
            "queixo": float(np.percentile(queixo, 80))}


def _larg(txt, f):
    return f.getlength(txt) + max(0, len(txt) - 1) * TRACK * f.size


def _acima(txt, f):
    """Altura do texto acima da linha de base (com acentos)."""
    return -f.getbbox(txt, anchor="ls")[1] if txt else 0.0


def _abaixo(txt, f):
    return max(0.0, f.getbbox(txt, anchor="ls")[3]) if txt else 0.0


def _cap(f):
    return -f.getbbox("H", anchor="ls")[1]


def _quebrar2(txt, f, larg):
    """Até 2 linhas equilibradas."""
    pal = txt.split()
    if len(pal) < 2:
        return [txt]
    melhor = None
    for i in range(1, len(pal)):
        a, b = " ".join(pal[:i]), " ".join(pal[i:])
        m = max(_larg(a, f), _larg(b, f))
        if melhor is None or m < melhor[0]:
            melhor = (m, [a, b])
    return melhor[1]


def _alt_pilula(fs):
    return 2.0 * fs


def _medidas(g, e, fator):
    """Tamanhos das fontes e altura total da pilha (selo + título) num certo fator de escala."""
    W, H = g.W, g.H
    fs = int(round(FS * W))
    if e.get("tipo") == "selo":
        return {"fs": fs, "altura": _alt_pilula(fs), "minimo": True}
    dest, txt = _textos(e)
    larg = 0.84 * W
    f2 = max(F2_MIN * W, F2 * W * fator)
    w2 = _larg(dest, d.fonte(int(f2), 850)) if dest else 0
    if w2 > larg:
        f2 = max(F2_MIN * W, f2 * larg / w2)
    f2 = int(f2)
    f1 = int(max(F1_MIN * W, f2 / 1.6))
    linhas1 = []
    if txt:
        w1 = _larg(txt, d.fonte(f1, 850))
        if w1 <= larg:
            linhas1 = [txt]
        elif f1 * larg / w1 >= F1_MIN * W:
            f1 = int(f1 * larg / w1)
            linhas1 = [txt]
        else:
            linhas1 = _quebrar2(txt, d.fonte(f1, 850), larg)
            wmax = max(_larg(l, d.fonte(f1, 850)) for l in linhas1)
            if wmax > larg:
                f1 = int(max(0.045 * W, f1 * larg / wmax))
    fo1, fo2 = d.fonte(f1, 850), d.fonte(f2, 850)
    alt = _cap(fo2)
    if linhas1:
        alt += 0.07 * f2 + 0.17 * f1 + (len(linhas1) - 1) * 1.0 * f1 + _acima(linhas1[0], fo1)
    sel = str(e.get("selo") or "").strip()
    if sel:
        alt += 0.014 * H + _alt_pilula(fs)
    return {"f1": f1, "f2": f2, "linhas1": linhas1, "dest": dest, "selo": sel, "fs": fs, "altura": alt,
            "minimo": f2 <= F2_MIN * W + 1}


def _ajustar(g, e, disp):
    fator, m = 1.0, _medidas(g, e, 1.0)
    while m["altura"] > disp and not m["minimo"]:
        fator *= 0.94
        m = _medidas(g, e, fator)
    return m


# ================================================================== estado (pré-cálculo por plano)

def _estado(g):
    est = g.cache.get("h18_estado")
    if est is not None:
        return est
    W, H = g.W, g.H
    recorte = bool(g.tem_mascara)
    evs = sorted((e for e in g.plano["eventos"] if e.get("tipo") in ("halo", "selo")), key=lambda e: e["inicio"])
    pulsos = sorted((e for e in g.plano["eventos"] if e.get("tipo") == "pulso"), key=lambda e: e["inicio"])
    itens = []
    for i, e in enumerate(evs):
        it = {"idx": i, "e": e, "tipo": e["tipo"], **_medir_rosto(g, e["inicio"], e["fim"])}
        it["cheia"] = _medidas(g, e, 1.0)["altura"]
        itens.append(it)
    segs = []
    for it in itens:
        if segs and it["e"]["inicio"] - segs[-1]["b"] < JUNTAR:
            segs[-1]["itens"].append(it)
            segs[-1]["b"] = max(segs[-1]["b"], it["e"]["fim"])
        else:
            segs.append({"a": it["e"]["inicio"], "b": it["e"]["fim"], "itens": [it]})
    tuck = 0.022 * H if recorte else -0.006 * H   # com recorte o pé do título encosta atrás do cabelo
    for k, s in enumerate(segs):
        precisa = max(TOPO_SEG * H + i["cheia"] - _tuck(i, tuck) - i["topo"] for i in s["itens"])
        boca = max(i["boca"] for i in s["itens"])
        limite = min(DESLOC_MAX * H, 0.70 * H - boca)   # a boca nunca desce até a faixa da legenda
        s["S"] = float(max(0.0, min(precisa, limite)))
        s["forte"] = 1.0 if any(i["tipo"] == "halo" for i in s["itens"]) else 0.7
        s["k"] = k
        s["topo"] = min(i["topo"] for i in s["itens"])
        for it in s["itens"]:
            it["S"] = s["S"]
            it["seg"] = k
            _layout(g, it, tuck, recorte)
    est = {"segs": segs, "itens": itens, "pulsos": pulsos, "recorte": recorte}
    g.cache["h18_estado"] = est
    return est


def _tuck(it, tuck):
    return tuck * 0.6 if it["tipo"] == "selo" else tuck


def _layout(g, it, tuck, recorte):
    """Posição final (já com a câmera descida) de selo, título, linha de corte e halo de um evento."""
    W, H = g.W, g.H
    S = it["S"]
    e = it["e"]
    topo = it["topo"] + S                      # topo estimado da cabeça na tela
    base = topo + _tuck(it, tuck)                       # linha de base da linha verde (ou pé do selo)
    m = _ajustar(g, e, base - TOPO_SEG * H)
    frente = False
    if m["altura"] > base - TOPO_SEG * H + 1:
        # não cabe nem no mínimo: o título fica NA FRENTE e pode cobrir a testa (nunca olhos/boca)
        frente = True
        lim = it["y0"] + S - 0.012 * H
        m = _ajustar(g, e, lim - TOPO_SEG * H)
        base = min(lim, TOPO_SEG * H + m["altura"])
    it["m"] = m
    it["frente"] = frente
    it["base"] = base
    if it["tipo"] == "selo":
        it["topo_pilha"] = base - m["altura"]
        pe = base
        it["titulo_topo"] = it["topo_pilha"]
    else:
        fo1, fo2 = d.fonte(m["f1"], 850), d.fonte(m["f2"], 850)
        b2 = base
        bases1 = []
        if m["linhas1"]:
            ult = b2 - _cap(fo2) - 0.07 * m["f2"] - 0.17 * m["f1"]
            n = len(m["linhas1"])
            bases1 = [ult - (n - 1 - j) * 1.0 * m["f1"] for j in range(n)]
            titulo_topo = bases1[0] - _acima(m["linhas1"][0], fo1)
        else:
            titulo_topo = b2 - _acima(m["dest"], fo2)
        it["b2"], it["bases1"] = b2, bases1
        it["titulo_topo"] = titulo_topo
        it["selo_pe"] = titulo_topo - 0.014 * H
        it["topo_pilha"] = it["selo_pe"] - _alt_pilula(m["fs"]) if m["selo"] else titulo_topo
        pe = b2 + _abaixo(m["dest"], fo2)
    # linha de onde o título nasce (tudo abaixo dela fica escondido)
    if recorte:
        corte = max(topo + 0.065 * H, pe + 0.006 * H)
    else:
        corte = max(topo + 0.008 * H, pe + 0.004 * H)
    it["corte"] = corte
    it["dist"] = corte - it["titulo_topo"] + 0.012 * H
    # halo: anel um pouco abaixo do pé do título
    rx = d.limitar(1.12 * it["lw"], 0.30 * W, 0.44 * W)
    ry = rx * (0.36 if not frente else 0.30)
    it["rx"], it["ry"] = rx, ry
    it["rcy"] = max(pe, topo - 0.02 * H) + 0.006 * H + ry


def _ramp_seg(s, t, ent=(-0.12, 0.42), sai=(-0.05, 0.5)):
    return d.suave(d.mapear(t, s["a"] + ent[0], s["a"] + ent[1])) * \
        (1 - d.suave(d.mapear(t, s["b"] + sai[0], s["b"] + sai[1])))


def _desloc(est, t):
    v = 0.0
    for s in est["segs"]:
        if s["S"] > 0 and s["a"] - 0.2 <= t <= s["b"] + 0.6:
            v = max(v, s["S"] * _ramp_seg(s, t))
    return v


def _escuro(est, t):
    for s in est["segs"]:
        if s["a"] - 0.2 <= t <= s["b"] + 0.6:
            return s["forte"] * _ramp_seg(s, t, (-0.1, 0.5), (-0.2, 0.45)), s
    return 0.0, None


def _ocupado(est, t):
    return any(s["a"] - 0.3 <= t <= s["b"] + 0.5 for s in est["segs"])


# ================================================================== legenda com o rosto na tela

class _RostoNaTela:
    """O rosto como aparece na tela (com a câmera descida). Só a legenda usa isto."""

    def __init__(self, g, est):
        self._r, self._est, self._H = g.rosto, est, g.H

    def __getattr__(self, nome):
        return getattr(self._r, nome)

    def em(self, t):
        x0, y0, x1, y1 = self._r.em(t)
        s = _desloc(self._est, t)
        return (x0, y0 + s, x1, y1 + s)

    def topo_cabeca(self, t):
        if _ocupado(self._est, t):
            return -self._H           # acima da cabeça é o lugar do título: a legenda nunca vai para lá
        return self._r.topo_cabeca(t) + _desloc(self._est, t)

    def queixo(self, t):
        return self._r.queixo(t) + _desloc(self._est, t)


def preparar(g):
    est = _estado(g)
    leg = g.plano.get("legenda") or {}
    if leg.get("ativa", True) and g.palavras and g.legendas is None:
        perfil = dict(INFO["legenda"])
        perfil.update(leg.get("perfil") or {})
        g.legendas = Legendas(g.palavras, g.W, g.H, PerfilLegenda.de(perfil), _RostoNaTela(g, est))


# ================================================================== camadas pré-desenhadas

def _linha_texto(txt, f, cor_txt, sombra=0.34, brilho=0.0, W=1080):
    """Uma linha com espaçamento apertado, sombra suave e (opcional) brilho verde.
    Devolve (camada, (x_base, y_base), largura_visivel)."""
    asc, desc = f.getmetrics()
    tr = TRACK * f.size
    pad = int(f.size * 0.42)
    larg = _larg(txt, f)
    w, h = int(larg + 2 * pad + 2), int(asc + desc + 2 * pad)
    alfa = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(alfa)
    for i, ch in enumerate(txt):
        if ch == " ":
            continue
        x = f.getlength(txt[:i + 1]) - f.getlength(ch) + i * tr
        dr.text((pad + x, pad + asc), ch, font=f, fill=255, anchor="ls")
    cam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if sombra > 0:
        s = alfa.filter(ImageFilter.GaussianBlur(max(1.0, 0.014 * W)))
        s = s.point(lambda v: int(v * sombra))
        sc = Image.new("RGBA", (w, h), (8, 22, 17, 255))
        sc.putalpha(s)
        cam.alpha_composite(sc, (0, int(max(1, 0.0046 * W))))
    if brilho > 0:
        b = alfa.filter(ImageFilter.GaussianBlur(max(2.0, f.size * 0.16)))
        b = b.point(lambda v: min(255, int(v * brilho)))
        bc = Image.new("RGBA", (w, h), d.cor(VERDE))
        bc.putalpha(b)
        cam.alpha_composite(bc)
    tc = Image.new("RGBA", (w, h), d.cor(cor_txt))
    tc.putalpha(alfa)
    cam.alpha_composite(tc)
    return cam, (pad, pad + asc), larg


def _seta_diagonal(tam, cor_ic):
    ss = 4
    S = tam * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    c = d.cor(cor_ic)
    e = max(2, int(S * 0.1))
    dr.line([(S * .27, S * .73), (S * .72, S * .28)], fill=c, width=e)
    dr.line([(S * .34, S * .28), (S * .72, S * .28), (S * .72, S * .66)], fill=c, width=e, joint="curve")
    for p in ((S * .27, S * .73), (S * .34, S * .28), (S * .72, S * .66), (S * .72, S * .28)):
        dr.ellipse([p[0] - e / 2, p[1] - e / 2, p[0] + e / 2, p[1] + e / 2], fill=c)
    return im.resize((tam, tam), Image.LANCZOS)


def _icone(nome, tam, cor_ic):
    if nome == "seta":
        return _seta_diagonal(tam, cor_ic)
    return d.icone(nome, tam, cor_ic)


def _circulo_icone(diam, nome, W):
    """Círculo verde com ícone escuro (o 'selo lateral discreto' da prévia)."""
    ss = 3
    pad = int(diam * 0.45)
    w = diam + 2 * pad
    m = Image.new("L", (w * ss, w * ss), 0)
    ImageDraw.Draw(m).ellipse((pad * ss, pad * ss, (pad + diam) * ss, (pad + diam) * ss), fill=255)
    m = m.resize((w, w), Image.LANCZOS)
    cam = Image.new("RGBA", (w, w), (0, 0, 0, 0))
    s = m.filter(ImageFilter.GaussianBlur(max(1.0, diam * 0.12))).point(lambda v: int(v * 0.35))
    sc = Image.new("RGBA", (w, w), (4, 12, 10, 255))
    sc.putalpha(s)
    cam.alpha_composite(sc, (0, int(diam * 0.06)))
    b = m.filter(ImageFilter.GaussianBlur(max(1.0, diam * 0.2))).point(lambda v: int(v * 0.45))
    bc = Image.new("RGBA", (w, w), d.cor(VERDE))
    bc.putalpha(b)
    cam.alpha_composite(bc)
    cc = Image.new("RGBA", (w, w), d.cor(VERDE))
    cc.putalpha(m)
    cam.alpha_composite(cc)
    if nome and nome != "nenhum":
        ic = _icone(nome, int(diam * 0.56), TINTA)
        cam.alpha_composite(ic, (int((w - ic.width) / 2), int((w - ic.height) / 2)))
    return cam


def _pilula(txt, fs, icone, W):
    """Etiqueta escura com borda verde fina (o selo da prévia). Ícone opcional à esquerda."""
    f = d.fonte(fs, 650)
    h = int(_alt_pilula(fs))
    tw = f.getlength(txt)
    tem_ic = bool(icone) and icone != "nenhum"
    dc = int(h * 0.68)
    pad_l = int(h * 0.16) if tem_ic else int(fs * 0.9)
    larg = int(pad_l + (dc + fs * 0.42 if tem_ic else 0) + tw + fs * 0.9)
    pan = d.painel(larg, h, raio=int(h * 0.3), fundo=SELO_FUNDO, borda=SELO_BORDA, larg_borda=max(1, int(W * 0.0016)))
    sm, (dx, dy) = d.sombra(pan, raio=max(2, W * 0.016), opacidade=0.30, desloc=(0, W * 0.009))
    ox, oy = -dx, -dy
    x = pad_l
    if tem_ic:
        cir = _circulo_icone(dc, icone, W)
        pad_c = (cir.width - dc) // 2
        sm.alpha_composite(cir, (int(ox + x - pad_c), int(oy + (h - dc) / 2 - pad_c)))
        x += dc + fs * 0.42
    d.escrever(sm, (ox + x, oy + h / 2 - fs * 0.62), [txt], f, SELO_TXT)
    return sm, (ox, oy), (larg, h)


def _camadas(g, it):
    """Camadas prontas do evento e posição final (canto superior esquerdo) de cada uma."""
    chave = ("h18_cam", it["idx"])
    if chave in g.cache:
        return g.cache[chave]
    W, H = g.W, g.H
    e, m = it["e"], it["m"]
    out = {"linhas": [], "selo": None, "redondo": None}
    if it["tipo"] == "halo":
        fo1, fo2 = d.fonte(m["f1"], 850), d.fonte(m["f2"], 850)
        larguras = [_larg(l, fo1) for l in m["linhas1"]] + [_larg(m["dest"], fo2)]
        tw = max(larguras) if larguras else 0
        cx = d.limitar(it["cx"], ESQ_SEG * W + tw / 2, DIR_SEG * W - tw / 2) if tw < (DIR_SEG - ESQ_SEG) * W \
            else (ESQ_SEG + DIR_SEG) / 2 * W
        for l, b in zip(m["linhas1"], it["bases1"]):
            cam, (bx, by), lv = _linha_texto(l, fo1, CLARO, 0.34, 0.0, W)
            out["linhas"].append({"cam": cam, "x": cx - lv / 2 - bx, "y": b - by, "verde": False})
        cam, (bx, by), lv = _linha_texto(m["dest"], fo2, VERDE, 0.30, 0.42, W)
        out["linhas"].append({"cam": cam, "x": cx - lv / 2 - bx, "y": it["b2"] - by, "verde": True})
        if m["selo"]:
            pil, (ox, oy), (pw, ph) = _pilula(m["selo"], m["fs"], None, W)
            out["selo"] = {"cam": pil, "x": cx - pw / 2 - ox, "y": it["selo_pe"] - ph - oy}
        ic = e.get("icone", "seta")
        if ic and ic != "nenhum":
            out["redondo"] = _circulo_icone(int(0.084 * W), ic, W)
        out["cx"] = cx
        out["caixa"] = (cx - tw / 2, it["titulo_topo"], cx + tw / 2, it["b2"])
        # todas as linhas numa camada só (uma composição por quadro em vez de duas ou três)
        bx0 = min(ln["x"] for ln in out["linhas"])
        by0 = min(ln["y"] for ln in out["linhas"])
        bx1 = max(ln["x"] + ln["cam"].width for ln in out["linhas"])
        by1 = max(ln["y"] + ln["cam"].height for ln in out["linhas"])
        bl = Image.new("RGBA", (int(bx1 - bx0) + 2, int(by1 - by0) + 2), (0, 0, 0, 0))
        for ln in out["linhas"]:
            bl.alpha_composite(ln["cam"], (int(round(ln["x"] - bx0)), int(round(ln["y"] - by0))))
        bl, dx, dy = _apertar(bl)
        out["bloco"] = {"cam": bl, "x": int(round(bx0)) + dx, "y": int(round(by0)) + dy}
    else:
        pil, (ox, oy), (pw, ph) = _pilula(str(e.get("texto") or "").strip(), m["fs"], e.get("icone"), W)
        cx = d.limitar(it["cx"], ESQ_SEG * W + pw / 2, DIR_SEG * W - pw / 2)
        out["selo"] = {"cam": pil, "x": cx - pw / 2 - ox, "y": it["base"] - ph - oy}
        out["cx"] = cx
        out["caixa"] = (cx - pw / 2, it["base"] - ph, cx + pw / 2, it["base"])
    g.cache[chave] = out
    return out


def _camada_anel(g, rx, ry):
    chave = ("h18_anel", int(rx), int(ry))
    if chave in g.cache:
        return g.cache[chave]
    W = g.W
    lw = max(2.0, 0.0036 * W)
    pad = int(0.05 * W)
    w, h = int(2 * rx + 2 * pad), int(2 * ry + 2 * pad)
    ss = 3
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).ellipse((pad * ss, pad * ss, (w - pad) * ss, (h - pad) * ss), outline=255, width=int(lw * ss))
    traco = m.resize((w, h), Image.LANCZOS)
    glow = traco.filter(ImageFilter.GaussianBlur(0.022 * W)).point(lambda v: min(255, int(v * 3.2)))
    dentro = Image.new("L", (w, h), 0)
    ImageDraw.Draw(dentro).ellipse((pad, pad, w - pad, h - pad), fill=26)
    dentro = dentro.filter(ImageFilter.GaussianBlur(0.03 * W))
    alfa = ImageChops.lighter(ImageChops.lighter(traco, glow.point(lambda v: int(v * 0.5))), dentro)
    cam = Image.new("RGBA", (w, h), d.cor(VERDE))
    cam.putalpha(alfa)
    nucleo = Image.new("RGBA", (w, h), (246, 252, 222, 255))
    nucleo.putalpha(traco.point(lambda v: int(v * 0.55)))
    cam.alpha_composite(nucleo)
    g.cache[chave] = cam
    return cam


def _camada_brilho(g, gx, gy):
    chave = ("h18_brilho", int(gx) // 4, int(gy) // 4)
    if chave in g.cache:
        return g.cache[chave]
    w, h = max(4, int(2 * gx)), max(4, int(2 * gy))
    y, x = np.ogrid[0:h, 0:w]
    dd = ((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2
    a = np.clip(1 - dd, 0, 1) ** 2 * 255
    cam = Image.new("RGBA", (w, h), d.cor(VERDE))
    cam.putalpha(Image.fromarray(a.astype(np.uint8), "L"))
    g.cache[chave] = cam
    return cam


def _mapa_escuro(g, recorte, y_fim=0.0):
    """Máscara L de quanto escurecer cada ponto (fundo escurecido de cima para baixo)."""
    W, H = g.W, g.H
    chave = ("h18_esc", recorte, int(y_fim) // 6)
    if chave in g.cache:
        return g.cache[chave]
    yy = np.arange(H, dtype=np.float32) / H
    xx = np.arange(W, dtype=np.float32) / W
    dist = np.sqrt(((xx[None, :] - 0.5) / 0.5) ** 2 + ((yy[:, None] - 0.5) / 0.5) ** 2)
    # o escurecimento termina em ESC_FIM (a parte de baixo da tela fica intacta: legenda e corpo)
    fade = np.clip((ESC_FIM - yy) / 0.14, 0, 1)[:, None]
    if recorte:
        grad = np.interp(yy, [0, 0.32, 0.64, 1.0], [0.88, 0.47, 0.0, 0.0])
        vig = np.clip((dist - 0.55) / 0.85, 0, 1) ** 1.5 * 0.5
        a = (1 - (1 - grad[:, None]) * (1 - 0.16) * (1 - vig)) * fade
    else:   # sem recorte: escurece só o céu acima da cabeça (nunca o rosto)
        ye = max(0.05, y_fim / H)
        grad = np.interp(yy, [0, ye * 0.55, ye, 1.0], [0.86, 0.5, 0.0, 0.0])
        vig = np.clip((dist - 0.75) / 0.7, 0, 1) ** 1.6 * 0.35 * fade
        a = 1 - (1 - grad[:, None]) * (1 - vig)
    m = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8), "L")
    g.cache[chave] = m
    return m


def _cor_solida(g):
    chave = ("h18_solida",)
    if chave not in g.cache:
        g.cache[chave] = Image.new("RGBA", (g.W, g.H), (*ESCURO, 255))
    return g.cache[chave]


# ================================================================== câmera

def _deslocar(img, s, yb):
    """Desce o quadro s pixels e preenche o topo com um céu escuro que continua a borda de cima.
    Devolve só a faixa de cima (0..yb) — o resto da tela é colado direto depois (rápido)."""
    W, H = img.size
    out = Image.new("RGBA", (W, yb), (*ESCURO, 255))
    out.paste(img.crop((0, 0, W, yb - s)), (0, s))
    hb = min(yb, s + int(H * 0.035))
    # borrão da borda de cima (feito pequeno e ampliado): 35% no alto da tela, 100% na emenda
    tira = img.crop((0, 0, W, max(2, int(H * 0.025))))
    pw, ph = max(8, W // 12), max(2, hb // 12)
    peq = np.asarray(tira.resize((pw, ph), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.6))).astype(np.float32)
    col = np.clip(0.35 + 0.65 * (np.arange(ph) + 0.5) * hb / ph / max(1, s), 0, 1)[:, None, None]
    peq = peq * col + np.array((*ESCURO, 255), dtype=np.float32) * (1 - col)
    banda = Image.fromarray(peq.astype(np.uint8), "RGBA").resize((W, hb), Image.BILINEAR)
    m = np.full(hb, 255, dtype=np.uint8)
    if hb > s:
        m[s:] = np.linspace(255, 0, hb - s).astype(np.uint8)
    mm = Image.fromarray(m[:, None], "L").resize((W, hb), Image.NEAREST)
    topo = Image.composite(banda, out.crop((0, 0, W, hb)), mm)
    out.paste(topo, (0, 0))
    return out


def _faixa_mascara(msk, s, yb):
    """Faixa de cima (0..yb) da máscara, já descida s pixels."""
    W = msk.width
    return msk.crop((0, -s, W, yb - s))


# ================================================================== desenho por quadro

def _colar(base, cam, x, y, escala=1.0, opac=1.0, corte=None, pluma=0, rot=0.0):
    """Cola 'cam' com canto em (x, y) (posição sem escala); escala em torno do centro da camada.
    corte: só mostra o que está ACIMA dessa linha (y da tela), com borda suave de 'pluma' px."""
    if opac <= 0.004:
        return
    c = cam
    cx, cy = x + c.width / 2, y + c.height / 2
    if abs(escala - 1) > 0.003:
        c = c.resize((max(1, int(c.width * escala)), max(1, int(c.height * escala))), Image.BILINEAR)
    if abs(rot) > 0.05:
        c = c.rotate(rot, resample=Image.BICUBIC, expand=True)
    px, py = int(round(cx - c.width / 2)), int(round(cy - c.height / 2))
    if corte is not None:
        vis = int(corte - py)
        if vis <= 0:
            return
        fundo = _fundo_visivel(c)
        if vis < fundo + max(0, int(pluma)):   # o corte pega no desenho (senão nada a fazer: rápido)
            if vis < c.height:
                c = c.crop((0, 0, c.width, vis))
            if pluma > 1:
                n = min(int(pluma), c.height)
                c = c.copy() if c is cam else c
                c.putalpha(ImageChops.multiply(c.getchannel("A"), _rampa(c.width, c.height, n)))
    if opac < 0.996:
        c = c.copy() if c is cam else c
        c.putalpha(c.getchannel("A").point(_tabela_opac(opac)))
    _cola(base, c, px, py)


def _cola(base, c, x, y):
    """Cola pelo canto (x, y). Se a camada cabe inteira na base, cola direto (sem cópia)."""
    x, y = int(round(x)), int(round(y))
    if x >= 0 and y >= 0 and x + c.width <= base.width and y + c.height <= base.height:
        base.alpha_composite(c, (x, y))
    else:
        d.colar_em(base, c, (x, y))


def _apertar(cam):
    """Corta a camada no desenho (menos área para compor). Devolve (camada, dx, dy)."""
    bb = cam.getchannel("A").getbbox()
    if not bb:
        return cam, 0, 0
    return cam.crop(bb), bb[0], bb[1]


def _fundo_visivel(c):
    """Última linha com desenho (alfa > 0) da camada — guardada na própria imagem."""
    v = getattr(c, "_h18_fundo", None)
    if v is None:
        bb = c.getchannel("A").getbbox()
        v = bb[3] if bb else 0
        try:
            c._h18_fundo = v
        except AttributeError:
            pass
    return v


_RAMPAS = {}


def _rampa(w, h, n):
    """Máscara L: opaca em cima, some nos últimos n pixels (pura: pode ser memorizada)."""
    k = (w, h, n)
    r = _RAMPAS.get(k)
    if r is None:
        ramp = np.full(h, 255, dtype=np.uint8)
        ramp[h - n:] = np.linspace(255, 0, n).astype(np.uint8)
        r = Image.fromarray(np.repeat(ramp[:, None], w, axis=1), "L")
        if len(_RAMPAS) > 400:
            _RAMPAS.clear()
        _RAMPAS[k] = r
    return r


def _tabela_opac(op):
    return [int(v * op) for v in range(256)]


def _com_opac(g, chave, cam, op):
    """Versão da camada com opacidade 'op' (24 níveis guardados em cache — sem cópia a cada quadro)."""
    q = int(round(d.limitar(op) * 24))
    if q >= 24:
        return cam
    if q <= 0:
        return None
    k = ("h18_op", chave, q)
    r = g.cache.get(k)
    if r is None:
        r = cam.copy()
        r.putalpha(cam.getchannel("A").point(_tabela_opac(q / 24)))
        g.cache[k] = r
    return r


def _cabeca(g, t, S):
    """Elipse estimada da cabeça na tela: (cx, cy, rx, ry)."""
    x0, y0, x1, y1 = g.rosto.em(t)
    topo = y0 - (y1 - y0) * (TOPO_CABECA + 0.05) + S
    baixo = g.rosto.queixo(t) + S + 0.02 * g.H
    return ((x0 + x1) / 2, (topo + baixo) / 2, (x1 - x0) * 0.66, (baixo - topo) / 2)


def _tempos(it, t):
    e = it["e"]
    ini, fim = e["inicio"], e["fim"]
    dur = fim - ini
    sobe = _crit(d.mapear(t, ini + 0.04, ini + 0.66))
    desce = d.suave(d.mapear(t, fim - 0.45, fim))
    atraso = min(0.75, 0.3 * dur)
    selo = _crit(d.mapear(t, ini + atraso, ini + atraso + 0.5)) * (1 - d.suave(d.mapear(t, fim - 0.5, fim - 0.08)))
    red = _crit(d.mapear(t, ini + atraso + 0.08, ini + atraso + 0.6)) * (1 - d.suave(d.mapear(t, fim - 0.5, fim - 0.1)))
    anel = _crit(d.mapear(t, ini, ini + 0.75)) * (1 - d.suave(d.mapear(t, fim - 0.4, fim + 0.05)))
    return sobe * (1 - desce), selo, red, anel


def _pulo(est, t):
    return max((_bump(t - p["inicio"]) for p in est["pulsos"]), default=0.0)


def _camada_halo(g, rx, ry, forca):
    """Anel + brilho atrás da cabeça numa camada só (assentado). Devolve (camada, dx, dy): canto da
    camada relativo ao centro do anel."""
    chave = ("h18_halo", int(rx), int(ry), forca)
    if chave in g.cache:
        return g.cache[chave]
    gl = _camada_brilho(g, rx * 1.25, ry * 2.3)
    an = _camada_anel(g, rx, ry)
    gx0, gy0 = -gl.width / 2, -0.3 * ry - gl.height / 2
    ax0, ay0 = -an.width / 2, -an.height / 2
    x0, y0 = min(gx0, ax0), min(gy0, ay0)
    x1, y1 = max(gx0 + gl.width, ax0 + an.width), max(gy0 + gl.height, ay0 + an.height)
    cam = Image.new("RGBA", (int(x1 - x0) + 2, int(y1 - y0) + 2), (0, 0, 0, 0))
    gla = gl.copy()
    gla.putalpha(gl.getchannel("A").point(_tabela_opac(0.30 * forca)))
    cam.alpha_composite(gla, (int(round(gx0 - x0)), int(round(gy0 - y0))))
    ana = an.copy()
    ana.putalpha(an.getchannel("A").point(_tabela_opac(min(1.0, 0.82 * forca))))
    cam.alpha_composite(ana, (int(round(ax0 - x0)), int(round(ay0 - y0))))
    cam, dx, dy = _apertar(cam)
    out = (cam, x0 + dx, y0 + dy)
    g.cache[chave] = out
    return out


def _buraco_cabeca(g, hrx, hry):
    """Máscara L: 0 dentro da elipse da cabeça (borda suave), 255 fora. Em cache por tamanho."""
    a, b = int(hrx * 1.08) // 3 * 3, int(hry * 1.04) // 3 * 3
    chave = ("h18_buraco", a, b)
    if chave in g.cache:
        return g.cache[chave]
    pad = int(0.03 * g.W)
    mk = Image.new("L", (2 * a + 2 * pad, 2 * b + 2 * pad), 255)
    ImageDraw.Draw(mk).ellipse((pad, pad, pad + 2 * a, pad + 2 * b), fill=0)
    mk = mk.filter(ImageFilter.GaussianBlur(max(1.0, 0.008 * g.W)))
    g.cache[chave] = (mk, a + pad, b + pad)
    return g.cache[chave]


def _sem_cabeca(g, cam, px, py, t, S):
    """Apaga da camada (colada em px, py) o que cairia dentro da cabeça — sem recorte."""
    hx, hy, hrx, hry = _cabeca(g, t, S)
    mk, ox, oy = _buraco_cabeca(g, hrx, hry)
    m = Image.new("L", cam.size, 255)
    m.paste(mk, (int(round(hx - ox - px)), int(round(hy - oy - py))))
    c2 = cam.copy()
    c2.putalpha(ImageChops.multiply(cam.getchannel("A"), m))
    return c2


def _anel_e_brilho(c, base, it, t, S, anel, pulo, sem_recorte):
    if anel <= 0.004:
        return
    g, W, H = c.g, c.W, c.H
    rx, ry = it["rx"], it["ry"]
    rcx, rcy = _centro_anel(g, it, t)
    forca = 1.0 if it["tipo"] == "halo" else 0.62
    esc = 0.8 + 0.2 * anel
    rot = -8 * (1 - anel)
    if abs(esc - 1) <= 0.003 and abs(rot) <= 0.05:
        # assentado: uma camada pronta (anel + brilho); no pulso, um reforço de luz por cima
        cam, dx, dy = _camada_halo(g, rx, ry, forca)
        camo = _com_opac(g, ("hl", int(rx), int(ry), forca), cam, min(1.0, anel * 1.2))
        if camo is None:
            return
        px, py = rcx + dx, rcy + dy
        if sem_recorte:
            camo = _sem_cabeca(g, camo, px, py, t, S)
        _cola(base, camo, px, py)
        if pulo > 0.02:
            extra = _com_opac(g, ("hl", int(rx), int(ry), forca), cam, 0.45 * pulo)
            if extra is not None:
                if sem_recorte:
                    extra = _sem_cabeca(g, extra, px, py, t, S)
                _cola(base, extra, px, py)
        return
    # entrada / saída: brilho e anel separados (o anel gira e cresce)
    gl = _camada_brilho(g, rx * 1.25, ry * 2.3)
    op_g = min(1.0, anel * forca) * 0.30
    glo = _com_opac(g, ("br", gl.width, gl.height), gl, op_g)
    if glo is not None:
        gpx, gpy = rcx - gl.width / 2, rcy - 0.3 * ry - gl.height / 2
        if sem_recorte:
            glo = _sem_cabeca(g, glo, gpx, gpy, t, S)
        _cola(base, glo, gpx, gpy)
    cam = _camada_anel(g, rx, ry)
    op = min(1.0, 0.82 * forca) * min(1.0, anel * 1.2)
    c2 = cam
    if abs(rot) > 0.05:   # giro de entrada: versões prontas a cada 0,5 grau
        rq = round(rot * 2) / 2
        kr = ("h18_anr", int(rx), int(ry), rq)
        if kr not in g.cache:
            g.cache[kr] = cam.rotate(rq, resample=Image.BICUBIC, expand=True)
        c2 = g.cache[kr]
    if abs(esc - 1) > 0.003:
        c2 = c2.resize((max(1, int(c2.width * esc)), max(1, int(c2.height * esc))), Image.BILINEAR)
    px, py = rcx - c2.width / 2, rcy - c2.height / 2
    if sem_recorte:   # apaga o anel dentro da cabeça (passa "por trás" sem recorte)
        c2 = _sem_cabeca(g, c2, px, py, t, S)
    _colar(base, c2, px, py, 1.0, op)


def _centro_anel(g, it, t):
    W = g.W
    x0, _, x1, _ = g.rosto.em(t)
    return d.limitar((x0 + x1) / 2, it["rx"] + 0.035 * W, W - it["rx"] - 0.035 * W), it["rcy"]


def _onda(c, base, p, t, S, vis):
    """Pulso: com halo na tela, o próprio anel solta uma onda; sem halo, a onda sai do contorno da cabeça."""
    k = d.mapear(t, p["inicio"], p["inicio"] + PULSO_DUR)
    if k <= 0 or k >= 1:
        return
    g, W, H = c.g, c.W, c.H
    alvo = next((it for it in vis if it["e"]["inicio"] - 0.05 <= p["inicio"] <= it["e"]["fim"]), None)
    if alvo is not None:
        hx, hy = _centro_anel(g, alvo, t)
        esc = 1.0 + 0.6 * d.saida(k)
        rx, ry = alvo["rx"] * esc, alvo["ry"] * esc
        op = (1 - k) ** 1.4 * 0.85
    else:
        # sem título na tela: um anel achatado (a forma do halo) nasce no topo da cabeça e se abre
        x0_, y0_, x1_, y1_ = g.rosto.em(t)
        lw_ = x1_ - x0_
        topo = y0_ - (y1_ - y0_) * TOPO_CABECA + S
        rx0 = d.limitar(1.0 * lw_, 0.26 * W, 0.40 * W)
        esc = 0.72 + 0.62 * d.saida(k)
        rx, ry = rx0 * esc, rx0 * 0.30 * esc
        hx = d.limitar((x0_ + x1_) / 2, 0.2 * W, 0.8 * W)
        hy = max(TOPO_SEG * H + ry, topo + 0.25 * rx0 * 0.30)
        op = math.sin(math.pi * min(1.0, k * 1.6) / 2) * (1 - k) ** 1.2 * 0.95
    f = 3  # desenha em 1/3 da resolução (rápido) e amplia
    x0, y0 = max(0, int(hx - rx - 0.04 * W)), max(0, int(hy - ry - 0.04 * W))
    x1, y1 = min(W, int(hx + rx + 0.04 * W)), min(H, int(hy + ry + 0.04 * W))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return
    w, h = (x1 - x0) // f + 1, (y1 - y0) // f + 1
    m = Image.new("L", (w, h), 0)
    lw = max(2, int(0.0055 * W / f * (1.25 - 0.5 * k)))
    ImageDraw.Draw(m).ellipse(((hx - rx - x0) / f, (hy - ry - y0) / f, (hx + rx - x0) / f, (hy + ry - y0) / f),
                              outline=255, width=lw)
    gl = m.filter(ImageFilter.GaussianBlur(0.012 * W / f)).point(lambda v: min(255, int(v * 2.4)))
    a = ImageChops.lighter(m, gl).point(_tabela_opac(op)).resize((w * f, h * f), Image.BILINEAR)
    cam = Image.new("RGBA", (w * f, h * f), d.cor(VERDE))
    cam.putalpha(a)
    if c.mascara is None:   # sem recorte: a onda nunca passa pela cabeça/rosto
        cam = _sem_cabeca(g, cam, x0, y0, t, S)
    _cola(base, cam, x0, y0)


def _titulo(c, base, it, t, rev, selo_k, pulo, na_frente):
    g, W, H = c.g, c.W, c.H
    cam = _camadas(g, it)
    if rev <= 0.003 and selo_k <= 0.003:
        return
    flut = 0.0022 * H * d.ruido(t, it["idx"] + 3, 0.35)
    if it["frente"]:
        dy = -(1 - rev) * 0.05 * H + flut
        corte = None
    else:
        dy = (1 - rev) * it["dist"] + flut
        corte = it["corte"]
    pluma = int(0.014 * H)
    if it["tipo"] == "selo":
        s = cam["selo"]
        _colar(base, s["cam"], s["x"], s["y"] + dy, 0.86 + 0.14 * rev, min(1.0, rev * 1.4), corte, pluma)
        return
    # selo de cima: sobe de trás do título (desenhado antes dele)
    if cam["selo"] is not None and selo_k > 0.003:
        s = cam["selo"]
        # nasce de trás da linha de cima do título (não atravessa as letras)
        c_selo = it["titulo_topo"] + dy + 0.004 * H
        if corte is not None:
            c_selo = min(c_selo, corte)
        _colar(base, s["cam"], s["x"], s["y"] + (1 - selo_k) * 0.045 * H + flut, 0.92 + 0.08 * selo_k,
               selo_k * min(1.0, rev * 1.5 + 0.2), c_selo, int(0.008 * H))
    if rev <= 0.003:
        return
    esc = 0.82 + 0.18 * rev
    op = min(1.0, rev * 1.35)
    gx0, gy0, gx1, gy1 = cam["caixa"]
    gx, gy = (gx0 + gx1) / 2, (gy0 + gy1) / 2
    if pulo < 0.01:   # sem pulo: o bloco inteiro de uma vez
        L = cam["bloco"]["cam"]
        lcx, lcy = cam["bloco"]["x"] + L.width / 2, cam["bloco"]["y"] + L.height / 2
        ncx, ncy = gx + (lcx - gx) * esc, gy + (lcy - gy) * esc + dy
        _colar(base, L, ncx - L.width / 2, ncy - L.height / 2, esc, op, corte, pluma)
        return
    for ln in cam["linhas"]:
        L = ln["cam"]
        e2 = esc * (1 + 0.075 * pulo if ln["verde"] else 1.0)
        lcx, lcy = ln["x"] + L.width / 2, ln["y"] + L.height / 2
        ncx, ncy = gx + (lcx - gx) * esc, gy + (lcy - gy) * esc + dy
        _colar(base, L, ncx - L.width / 2, ncy - L.height / 2, e2, op, corte, pluma)


def _lugar_redondo(g, it, cam):
    """Onde o selo redondo fica (escolhido uma vez por evento, sem pular entre quadros):
    ('anel', ângulo) na ponta esquerda do halo, como na prévia, ou ('linha', dx) colado à esquerda da linha
    verde quando o halo encosta na borda (plano fechado)."""
    W = g.W
    rx, ry = it["rx"], it["ry"]
    rcx = d.limitar(it["cx"], rx + 0.035 * W, W - rx - 0.035 * W)
    raio = 0.042 * W
    folga = 0.012 * W
    tx0, ty0, tx1, ty1 = cam["caixa"]
    ty1 += 0.22 * it["m"]["f2"]
    for ang in (152, 162, 142, 172, 132, 182):
        a = math.radians(ang)
        bx, by = rcx + rx * math.cos(a), it["rcy"] - ry * math.sin(a)
        if bx - raio < 0.035 * W:
            continue
        if not (bx + raio + folga > tx0 and bx - raio - folga < tx1 and by + raio + folga > ty0
                and by - raio - folga < ty1):
            return ("anel", ang)
    verde = cam["linhas"][-1]
    pad = int(it["m"]["f2"] * 0.42)   # margem interna da camada de texto (ver _linha_texto)
    x_txt = verde["x"] + pad
    bx = x_txt - 0.02 * W - raio
    if bx - raio >= 0.035 * W:
        return ("linha", bx)
    return None


def _redondo(c, base, it, t, red, S):
    cam = _camadas(c.g, it)
    if cam["redondo"] is None or red <= 0.003:
        return
    g, W, H = c.g, c.W, c.H
    if "lugar" not in cam:
        cam["lugar"] = _lugar_redondo(g, it, cam)
    lugar = cam["lugar"]
    if lugar is None:
        return
    if lugar[0] == "anel":
        rcx, rcy = _centro_anel(g, it, t)
        a = math.radians(lugar[1])
        bx, by = rcx + it["rx"] * math.cos(a), rcy - it["ry"] * math.sin(a)
    else:   # ao lado da linha verde, na altura do meio das letras
        fo2 = d.fonte(it["m"]["f2"], 850)
        bx, by = lugar[1], it["b2"] - _cap(fo2) / 2 + 0.0022 * H * d.ruido(t, it["idx"] + 3, 0.35)
    by += (1 - red) * 0.07 * H
    R = cam["redondo"]
    _colar(base, R, bx - R.width / 2, by - R.height / 2, 0.75 + 0.25 * red, red, rot=-25 * (1 - red))


def _fundo_desenho(g, est, t, vis, puls, kf, S):
    """Até onde (y) este quadro desenha algo — o trabalho é feito só nessa faixa de cima."""
    W, H = g.W, g.H
    yb = ESC_FIM * H if kf > 0.002 else 0.0
    for it in vis:
        yb = max(yb, it["rcy"] + 1.7 * it["ry"] + 0.06 * W)
    if puls:
        x0, y0, x1, y1 = g.rosto.em(t)
        yb = max(yb, y0 - (y1 - y0) * TOPO_CABECA + S + 0.34 * W)
    return int(min(H, max(8, yb)))


def quadro(c):
    g = c.g
    est = _estado(g)
    t = c.t
    W, H = c.W, c.H
    S = _desloc(est, t)
    kf, seg = _escuro(est, t)
    vis = [it for it in est["itens"] if it["e"]["inicio"] - 0.05 <= t <= it["e"]["fim"] + 0.1]
    puls = [p for p in est["pulsos"] if p["inicio"] <= t <= p["inicio"] + PULSO_DUR]
    s = int(round(S))
    if s < 1 and kf <= 0.002 and not vis and not puls:
        return c.fonte
    # tudo acontece na faixa de cima (0..yb); embaixo é o vídeo (descido s pixels) sem mudança
    yb = max(_fundo_desenho(g, est, t, vis, puls, kf, S), min(H, s + int(H * 0.035)))
    fonte = c.fonte
    if s > 0:
        faixa = _deslocar(fonte, s, yb)
        saida = Image.new("RGBA", (W, H))
        if yb < H:
            saida.paste(fonte.crop((0, yb - s, W, H - s)), (0, yb))
    else:
        faixa = fonte.crop((0, 0, W, yb))
        saida = fonte.copy() if yb < H else None
    msk = _faixa_mascara(c.mascara, s, yb) if c.mascara is not None else None
    sem_recorte = msk is None
    # fundo escurecido (com recorte: todo o fundo; sem recorte: só o céu acima da cabeça)
    if kf > 0.002:
        y_fim = (seg["topo"] + seg["S"] + 0.03 * H) if sem_recorte else 0.0
        mapa = _mapa_escuro(g, not sem_recorte, y_fim).crop((0, 0, W, yb))
        if kf < 0.998:
            mapa = mapa.point(_tabela_opac(kf))
        base = faixa.copy()
        base.paste(_cor_solida(g).crop((0, 0, W, yb)), (0, 0), mapa)
    else:
        base = faixa.copy()
    pulo = _pulo(est, t)
    estados = {it["idx"]: _tempos(it, t) for it in vis}
    # atrás da pessoa
    for it in vis:
        _anel_e_brilho(c, base, it, t, S, estados[it["idx"]][3], pulo, sem_recorte)
    for p in puls:
        _onda(c, base, p, t, S, vis)
    for it in vis:
        if not it["frente"]:
            rev, selo_k, _, _ = estados[it["idx"]]
            _titulo(c, base, it, t, rev, selo_k, pulo, False)
    if msk is not None:   # a pessoa volta por cima de tudo (e sem escurecer)
        base.paste(faixa, (0, 0), msk)
    # na frente
    for it in vis:
        if it["frente"]:
            rev, selo_k, _, _ = estados[it["idx"]]
            _titulo(c, base, it, t, rev, selo_k, pulo, True)
    for it in vis:
        if it["tipo"] == "halo":
            _redondo(c, base, it, t, estados[it["idx"]][2], S)
    if saida is None:
        return base
    saida.paste(base, (0, 0))
    return saida
