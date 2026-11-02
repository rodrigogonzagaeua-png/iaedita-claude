"""02 · Parede do sofá — painéis claros em perspectiva pendurados na parede ATRÁS da pessoa, com
títulos que balançam junto com a parede. A pessoa recortada fica na frente (a cabeça esconde parte
do painel, nunca o texto). Em plano fechado a câmera recua um pouco para abrir parede; sem recorte,
os painéis ficam ao lado/acima da cabeça, sem nunca cobrir o rosto.

Geometria: cada painel é desenhado plano (cache) e projetado em 3D (giro lateral + inclinação).
As posições são calculadas UMA vez por evento em preparar(g) a partir do rosto ao longo do evento;
quadro(c) só depende de c.t e do plano."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import desenho as d

INFO = {
    "id": "02-parede-do-sofa",
    "nome": "Parede do sofá",
    "precisa_recorte": True,
    "antes": 0.3,
    "depois": 0.5,
    "legenda": {"peso": 700, "tamanho": 0.056, "cor": "#222729", "destaque": "#4A5630", "caixa": "#F8F7F0F2",
                "max_caracteres": 22, "max_linhas": 1, "animacao": "subir", "posicao": "auto"},
    "eventos": {
        "painel": "inicio, fim (1,5 a 6 s), texto (1 a 4 palavras: o título do painel), "
                  "lado ('auto' padrão | 'esquerda' | 'direita' | 'centro' = título principal no alto da parede), "
                  "marca (opcional: 1 palavra do texto que ganha marca-texto verde), "
                  "etiqueta (opcional: 1 a 2 palavras na barrinha do topo do painel), "
                  "icone (opcional: check, x, estrela, raio, alvo, grafico, dinheiro, coracao, play, seta_cima, "
                  "seta_baixo, seta_dir), som",
    },
}

# paleta da prévia aprovada
PAPEL = "#F8F7F0"
TINTA = "#222729"
ETIQ = "#667064"
PONTO = "#D2D6CD"
FIO = "#DFE1D8"
SALVIA_CENTRO = "#CCD8C8"
SALVIA_LADO = "#D8D9CF"
LIMA = "#D4ED80"
TL_FUNDO = "#20272C"
TL_APAGADO = "#526066"
LINHA = "#E2E4DA"
BORDA = "#3C494224"
PILULA = "#E4E6DD"

LADOS = ("auto", "esquerda", "direita", "centro")
ICONES = {"check", "estrela", "raio", "alvo", "grafico", "dinheiro", "coracao", "play", "seta_cima", "seta_baixo",
          "seta_dir", "x", "ponto"}

TOPO = 0.125        # topo dos painéis (fração de H) — abaixo da zona da interface
PERIODO = 6.0       # balanço da parede (s), como na prévia
ANG_LADO = 24.0     # giro dos painéis laterais (graus)
INCL = 4.0          # inclinação (topo um pouco para trás)
JUNTAR = 2.0        # painéis com menos de 2 s entre si abrem a parede uma vez só (a câmera não "bomba")
S_MIN = 0.76        # recuo máximo da câmera
CORTE = 0.0         # recuo desligado só se o topo estimado da cabeça sair do quadro (rosto cortado)
CAB = 0.34          # topo da cabeça (com cabelo/boné) = topo da caixa do rosto - CAB x altura do rosto
ENTRA, SAI = 0.15, 0.38   # a entrada começa 0,15 s antes do inicio; a saída dura 0,38 s depois do fim


# ------------------------------------------------------------------ utilidades


def _chave(e):
    return (round(float(e["inicio"]), 3), round(float(e["fim"]), 3), str(e.get("texto", "")), str(e.get("lado", "")))


def _lado_pedido(e):
    lado = str(e.get("lado", "auto")).strip().lower()
    lado = {"esq": "esquerda", "dir": "direita", "meio": "centro", "topo": "centro", "alto": "centro",
            "left": "esquerda", "right": "direita", "center": "centro"}.get(lado, lado)
    return lado if lado in LADOS else "auto"


def _sobrepoe(a, b, folga=0.0):
    return a["inicio"] - ENTRA - folga < b["fim"] + SAI and b["inicio"] - ENTRA - folga < a["fim"] + SAI


def _cabeca(g, t0, t1, s=1.0):
    """Medidas da cabeça (com cabelo/boné) no intervalo, já na tela com recuo s."""
    W, H = g.W, g.H
    ts = np.arange(max(0.0, t0), max(max(0.0, t0) + 0.01, min(g.duracao, t1)), 0.2)
    cx = np.array([g.rosto.em(float(t)) for t in ts])
    x0, y0, x1, y1 = cx[:, 0], cx[:, 1], cx[:, 2], cx[:, 3]
    fw, fh = x1 - x0, y1 - y0
    hx0 = W / 2 + (x0 - 0.14 * fw - W / 2) * s
    hx1 = W / 2 + (x1 + 0.14 * fw - W / 2) * s
    topo = H + (y0 - CAB * fh - H) * s
    queixo = H + (y1 + 0.08 * fh - H) * s
    cy = H + ((y0 + y1) / 2 - H) * s
    return {"hx0": float(hx0.min()), "hx1": float(hx1.max()), "topo": float(topo.min()),
            "queixo": float(queixo.max()), "cy": float(np.median(cy)), "fw": float(np.median(fw) / W),
            "topo_orig": float((y0 - CAB * fh).min())}


def _s_no_tempo(grupos, t):
    s = 1.0
    for gr in grupos:
        if gr["s"] >= 0.9995:
            continue
        k = d.suave(d.mapear(t, gr["a"] - 0.75, gr["a"] + 0.1)) * (1 - d.suave(d.mapear(t, gr["b"] + 0.25, gr["b"] + 1.0)))
        s = min(s, 1 - (1 - gr["s"]) * k)
    return s


class _RostoNaTela:
    """Rosto como aparece na tela depois do recuo da câmera (para a legenda não cair no queixo)."""

    def __init__(self, rosto, grupos, W, H):
        self.r, self.grupos, self.W, self.H = rosto, grupos, W, H
        self.metodo = getattr(rosto, "metodo", "")

    def em(self, t):
        x0, y0, x1, y1 = self.r.em(t)
        s = _s_no_tempo(self.grupos, t)
        W, H = self.W, self.H
        return (W / 2 + (x0 - W / 2) * s, H + (y0 - H) * s, W / 2 + (x1 - W / 2) * s, H + (y1 - H) * s)

    def topo_cabeca(self, t):
        x0, y0, x1, y1 = self.em(t)
        return max(0.0, y0 - (y1 - y0) * 0.45)

    def queixo(self, t):
        x0, y0, x1, y1 = self.em(t)
        return y1 + (y1 - y0) * 0.08


# ------------------------------------------------------------------ projeção 3D


def _rot(x, y, teta, fi):
    """Gira o ponto do plano do painel: teta = giro lateral (>0 afasta a borda direita),
    fi = inclinação (>0 afasta a borda de cima)."""
    ct, st = math.cos(math.radians(teta)), math.sin(math.radians(teta))
    cf, sf = math.cos(math.radians(fi)), math.sin(math.radians(fi))
    x1, z1 = x * ct, x * st
    return x1, y * cf, z1 - y * sf


def _cantos(px, py, w, h, teta, fi, foco, m=0.0, piv="centro", flap=0.0):
    """4 cantos na tela [sup-esq, sup-dir, inf-dir, inf-esq] do retângulo w x h (+ margem m).
    piv='topo': gira em torno da borda de cima (painel central 'caindo' na parede)."""
    if piv == "topo":
        pts = [(-w / 2 - m, -m), (w / 2 + m, -m), (w / 2 + m, h + m), (-w / 2 - m, h + m)]
    else:
        pts = [(-w / 2 - m, -h / 2 - m), (w / 2 + m, -h / 2 - m), (w / 2 + m, h / 2 + m), (-w / 2 - m, h / 2 + m)]
    out = []
    for x, y in pts:
        if flap:
            cf, sf = math.cos(math.radians(flap)), math.sin(math.radians(flap))
            y, zf = y * cf, y * sf          # flap > 0: a borda de baixo se afasta
        else:
            zf = 0.0
        x1, y2, z2 = _rot(x, y, teta, fi)
        z2 += zf
        k = foco / max(1.0, foco + z2)
        out.append((px + x1 * k, py + y2 * k))
    return out


def _homografia(src, dst):
    """Coeficientes (a..h) que levam pontos de dst para src (formato do Image.PERSPECTIVE)."""
    m, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        m.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b += [u, v]
    return np.linalg.solve(np.array(m, np.float64), np.array(b, np.float64)).tolist()


def _aplicar(coef, x, y):
    a, b, c, dd, e, f, g, h = coef
    den = g * x + h * y + 1
    return (a * x + b * y + c) / den, (dd * x + e * y + f) / den


# ------------------------------------------------------------------ texto


def _quebrar(texto, f, largura):
    """Quebra em linhas sem deixar palavra curta sozinha ('a', 'de', 'no' vão junto com a seguinte)."""
    blocos, cola = [], ""
    for p in texto.split():
        if cola:
            p = cola + " " + p
            cola = ""
        if len(p.strip(".,!?:;")) <= 2 and not p[:1].isdigit():
            cola = p
            continue
        blocos.append(p)
    if cola:
        if blocos:
            blocos[-1] += " " + cola
        else:
            blocos.append(cola)
    linhas, atual = [], ""
    for b in blocos:
        teste = (atual + " " + b).strip()
        if f.getlength(teste) <= largura or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = b
    if atual:
        linhas.append(atual)
    return linhas


def _caber(texto, w, h, tmax, tmin, max_linhas, peso=800):
    """Maior fonte que cabe em w x h. Devolve (fonte, linhas, entrelinha, cabe?)."""
    tam = int(tmax)
    while tam >= tmin:
        f = d.fonte(tam, peso)
        linhas = _quebrar(texto, f, w)
        al = tam * 1.06
        if len(linhas) <= max_linhas and al * len(linhas) <= h and all(f.getlength(l) <= w for l in linhas):
            return f, linhas, al, True
        tam = int(tam * 0.94) if tam > 30 else tam - 1
    f = d.fonte(int(tmin), peso)
    linhas = _quebrar(texto, f, w)
    if len(linhas) > max_linhas:
        linhas = linhas[: max_linhas - 1] + [" ".join(linhas[max_linhas - 1:])]
    return f, linhas, tmin * 1.06, False


# ------------------------------------------------------------------ preparar (posições, recuo, legenda)


def preparar(g):
    W, H = g.W, g.H
    evs = [e for e in g.plano["eventos"] if e.get("tipo") == "painel"]
    est = {"grupos": [], "lay": {}}
    g.cache["_p02"] = est
    if not evs:
        return
    evs = sorted(evs, key=lambda e: e["inicio"])
    mascara = bool(g.tem_mascara)

    # 1) lados (auto = lado livre com mais parede; alterna quando empata)
    lados, feitos, ultimo = {}, [], None
    for e in evs:
        lado = _lado_pedido(e)
        ocup = {lados[_chave(o)] for o in feitos if _sobrepoe(o, e)}
        if lado == "auto":
            livres = [l for l in ("esquerda", "direita") if l not in ocup]
            if len(livres) == 2:
                cb = _cabeca(g, e["inicio"] - 0.3, e["fim"] + 0.5)
                esp_e, esp_d = cb["hx0"] - 0.04 * W, 0.90 * W - cb["hx1"]
                if abs(esp_e - esp_d) < 0.05 * W and ultimo in ("esquerda", "direita"):
                    lado = "direita" if ultimo == "esquerda" else "esquerda"
                else:
                    lado = "esquerda" if esp_e >= esp_d else "direita"
            elif livres:
                lado = livres[0]
            else:
                lado = "centro" if "centro" not in ocup else "esquerda"
            ultimo = lado
        lados[_chave(e)] = lado
        feitos.append(e)

    # 2) quanto cada painel precisa que a câmera recue (só quando falta parede:
    #    rosto grande, ou título central sem espaço acima da cabeça)
    precisa = {}
    for e in evs:
        cb = _cabeca(g, e["inicio"] - 0.3, e["fim"] + SAI)
        s = 1.0
        if cb["topo_orig"] >= CORTE * H:          # cabeça encostada no topo: recuar mostraria o corte
            if cb["fw"] > 0.34:
                s = 0.34 / cb["fw"]
            if lados[_chave(e)] == "centro":
                s = min(s, (1 - 0.27) / max(0.05, 1 - cb["topo_orig"] / H))
            s = max(S_MIN, s)
        precisa[_chave(e)] = 1.0 if s > 0.985 else s

    # 3) grupos de recuo: painéis que precisam, próximos entre si, recuam uma vez só (sem "bombear")
    grupos = []
    for e in evs:
        s = precisa[_chave(e)]
        if s >= 1.0:
            continue
        if grupos and e["inicio"] - grupos[-1]["b"] < JUNTAR:
            grupos[-1]["b"] = max(grupos[-1]["b"], e["fim"])
            grupos[-1]["s"] = min(grupos[-1]["s"], s)
            grupos[-1]["evs"].append(e)
        else:
            grupos.append({"a": e["inicio"], "b": e["fim"], "s": s, "evs": [e]})
    est["grupos"] = [{"a": gr["a"], "b": gr["b"], "s": gr["s"]} for gr in grupos]
    s_do = {}
    for gr in grupos:
        for e in gr["evs"]:
            s_do[_chave(e)] = gr["s"]

    # 4) posição de cada painel. Quem precisa de recuo é posicionado na tela recuada; os outros na
    #    tela normal e só "acompanham" a câmera (fonte compensada para continuar legível).
    #    Os centrais primeiro: quando há central junto, os laterais ficam pendurados ABAIXO dele.
    base_centro = {}   # chave do central -> borda de baixo do painel, em coordenadas da cena
    for e in sorted(evs, key=lambda e: lados[_chave(e)] != "centro"):
        s = s_do.get(_chave(e), 1.0)
        ts = np.arange(e["inicio"] + 0.5, max(e["inicio"] + 0.6, e["fim"]), 0.1)   # parte em que se lê
        s_min = min([_s_no_tempo(est["grupos"], float(t)) for t in ts] + [1.0])
        comp = 1.0 if s < 1.0 else 1.0 / max(S_MIN, s_min)
        lado = lados[_chave(e)]
        cb = _cabeca(g, e["inicio"] - 0.3, e["fim"] + SAI, s)
        viz = [o for o in evs if o is not e and _sobrepoe(o, e)]
        # "juntos de verdade" = ficam na tela ao mesmo tempo por mais de 0,5 s (não só na troca)
        juntos = [o for o in viz if min(o["fim"], e["fim"]) - max(o["inicio"], e["inicio"]) > 0.5]
        tem_centro = any(lados[_chave(o)] == "centro" for o in juntos)
        tem_lados = any(lados[_chave(o)] != "centro" for o in juntos)
        lay = None
        if lado == "centro":
            lay = _layout_centro(g, e, cb, tem_lados, mascara, comp)
            if lay is None:  # sem espaço acima da cabeça: vira painel lateral no lado livre
                ocup = {lados[_chave(o)] for o in viz}
                livres = [l for l in ("esquerda", "direita") if l not in ocup] or ["esquerda"]
                esp = {"esquerda": cb["hx0"] - 0.04 * W, "direita": 0.90 * W - cb["hx1"]}
                lado = max(livres, key=lambda l: esp[l])
                lados[_chave(e)] = lado
        if lay is None:
            topo_min = None
            centrais = [o for o in juntos if _chave(o) in base_centro]
            if centrais:   # abaixo da faixa do título central (convertida para o recuo deste painel)
                yb = max(base_centro[_chave(o)] for o in centrais)
                topo_min = H + (yb - H) * s + 0.012 * H
            lay = _layout_lado(g, e, lado, cb, bool(centrais), mascara, comp, topo_min)
        elif lay["tipo"] == "centro":
            base_centro[_chave(e)] = H + (lay["py"] + lay["ph"] - H) / s
        lay["lado"] = lado
        # cena = tela desfeita do recuo (o painel fica preso à parede e acompanha a câmera)
        lay["px_c"] = W / 2 + (lay["px"] - W / 2) / s
        lay["py_c"] = H + (lay["py"] - H) / s
        lay["s0"] = s
        est["lay"][_chave(e)] = lay

    # 5) legenda acompanha o rosto já recuado
    if any(gr["s"] < 0.9995 for gr in est["grupos"]) and getattr(g, "legendas", None) is not None:
        g.legendas.rosto = _RostoNaTela(g.rosto, est["grupos"], W, H)


def _layout_lado(g, e, lado, cb, tem_centro, mascara, comp=1.0, topo_min=None):
    W, H = g.W, g.H
    foco = 1.4 * W
    pw = 0.40 * W
    y0 = TOPO * H if topo_min is None else max(TOPO * H, topo_min)
    baixo = min(cb["queixo"] - 0.03 * H, 0.64 * H)
    x0 = 0.04 * W if lado == "esquerda" else 0.96 * W - pw
    ph = max(0.13 * H, min(pw * 1.22, baixo - y0))
    if not mascara:
        # sem recorte o painel não pode encostar na cabeça: ou fica ao lado, ou só acima dela
        if lado == "esquerda":
            livre = cb["hx0"] - 0.015 * W - x0
        else:
            livre = (x0 + pw) - (cb["hx1"] + 0.015 * W)
        acima = cb["topo"] - 0.012 * H - y0
        if livre >= 0.26 * W:
            if lado == "esquerda":
                pw = min(pw, livre)
            else:
                x0, pw = x0 + pw - min(pw, livre), min(pw, livre)
        elif acima >= 0.10 * H:
            ph = acima
        else:
            pw = max(0.20 * W, livre)
            if lado == "direita":
                x0 = 0.96 * W - pw
    teta = ANG_LADO if lado == "esquerda" else -ANG_LADO
    px, py = x0 + pw / 2, y0 + ph / 2
    cantos = _cantos(px, py, pw, ph, teta, INCL, foco)
    inv = _homografia([(0, 0), (pw, 0), (pw, ph), (0, ph)], cantos)
    fe = int(round(0.038 * W * comp)) if e.get("etiqueta") else 0
    barra = max(0.11 * pw, fe * 1.95)
    pad = 0.07 * pw
    tmax, tmin = 0.075 * W * comp, 0.042 * W * comp
    # limite direito do texto: longe dos botões do Reels/TikTok
    u_dir = min(_aplicar(inv, 0.885 * W, y)[0] for y in np.linspace(y0, y0 + ph, 6))
    cand = []
    u_fim_lado = min(pw - pad, u_dir)
    if mascara:
        ys = np.linspace(y0 + barra, y0 + ph, 8)
        if lado == "esquerda":
            u_cab = min(_aplicar(inv, cb["hx0"] - 0.02 * W, y)[0] for y in ys)
            caixa_a = (pad, u_cab - 0.02 * pw)
        else:
            u_cab = max(_aplicar(inv, cb["hx1"] + 0.02 * W, y)[0] for y in ys)
            caixa_a = (u_cab + 0.02 * pw, u_fim_lado)
        cand.append(("lado", caixa_a[0], caixa_a[1] - caixa_a[0], ph * 0.55))
        xs = np.linspace(cantos[0][0], cantos[1][0], 8)
        v_cab = min(_aplicar(inv, x, cb["topo"] - 0.015 * H)[1] for x in xs)
        cand.append(("topo", pad, u_fim_lado - pad, v_cab - barra - 0.5 * pad - 0.02 * ph))
    else:
        cand.append(("livre", pad, u_fim_lado - pad, min(ph * 0.55, ph - barra - 1.2 * pad)))
    texto = str(e.get("texto", ""))
    melhor = None
    # 1ª tentativa: fonte confortável (≥4,2% da largura); 2ª: até 3,6% e 4 linhas
    for t_min, n_lin in ((tmin, 3), (0.036 * W * comp, 4)):
        for modo, u0, wb, hb in cand:
            if wb < 0.12 * W or hb < t_min * 1.06:
                continue
            f, linhas, al, ok = _caber(texto, wb, hb, tmax, t_min, n_lin)
            nota = f.size + (1000 if ok else 0)
            if melhor is None or nota > melhor[0]:
                melhor = (nota, modo, u0, wb, f, linhas, al, ok)
        if melhor is not None and melhor[-1]:
            break
    if melhor is None or not melhor[-1]:
        # aperto extremo (texto longo em parede pequena): primeiro diminui DENTRO da área visível
        # (nunca atrás da cabeça); só sem nenhuma área usa a largura inteira do cartão
        for modo, u0, wb, hb in cand:
            if wb < 0.10 * W or hb < 0.03 * W * comp * 1.06:
                continue
            f, linhas, al, ok = _caber(texto, wb, hb, tmax, 0.03 * W * comp, 4)
            if ok and (melhor is None or not melhor[-1] or f.size > melhor[4].size):
                melhor = (0, modo, u0, wb, f, linhas, al, ok)
    if melhor is None or not melhor[-1]:
        u0, wb = pad, u_fim_lado - pad
        hb = ph - barra - 1.5 * pad
        f, linhas, al, ok = _caber(texto, wb, hb, tmax, 0.03 * W * comp, 4)
        melhor = (0, "largo", u0, wb, f, linhas, al, ok)
    _, modo, u0, wb, f, linhas, al, ok = melhor
    return {"tipo": "lado", "px": px, "py": py, "pw": pw, "ph": ph, "teta": teta, "fi": INCL, "piv": "centro",
            "barra": barra, "fe": fe, "pad": pad, "modo": modo, "u0": u0, "wb": wb, "fonte": f.size,
            "linhas": linhas, "al": al, "cabe": ok, "salvia": SALVIA_LADO}


def _layout_centro(g, e, cb, tem_lados, mascara, comp=1.0):
    W, H = g.W, g.H
    pw = 0.62 * W
    y0 = TOPO * H
    x0 = (W - pw) / 2
    acima = cb["topo"] - 0.015 * H - y0
    if mascara and not tem_lados:
        ph = max(0.16 * H, min(0.30 * H, cb["queixo"] - 0.06 * H - y0))
    else:
        ph = acima
    fe = int(round(0.038 * W * comp)) if e.get("etiqueta") else 0
    barra = max(0.075 * pw, fe * 1.95)
    pad = 0.06 * pw
    tmax, tmin = 0.095 * W * comp, 0.05 * W * comp
    hb = acima - barra - 0.5 * pad
    if not mascara or tem_lados:
        hb = ph - barra - 1.1 * pad
    if hb < tmin * 1.1:
        return None
    f, linhas, al, ok = _caber(str(e.get("texto", "")), pw - 2 * pad, hb, tmax, tmin, 2)
    if not ok and hb < tmin * 2.2 and len(str(e.get("texto", "")).split()) > 2:
        return None
    if tem_lados:
        # com painéis laterais junto, o central vira uma faixa (barra + título) e eles ficam abaixo
        ph = min(ph, barra + 0.55 * pad + al * len(linhas) + 0.9 * pad)
    px, py = x0 + pw / 2, y0  # pivô na borda de cima
    return {"tipo": "centro", "px": px, "py": py, "pw": pw, "ph": ph, "teta": 0.0, "fi": 0.0, "piv": "topo",
            "barra": barra, "fe": fe, "pad": pad, "modo": "topo", "u0": pad, "wb": pw - 2 * pad, "fonte": f.size,
            "linhas": linhas, "al": al, "cabe": ok, "salvia": SALVIA_CENTRO}


# ------------------------------------------------------------------ desenho do painel (plano)


def _painel_plano(c, e, lay, acesos):
    """Painel plano com sombra (margem m em volta). Cacheado por evento e nº de blocos acesos."""
    chave = ("p02", _chave(e), acesos)
    if chave in c.g.cache:
        return c.g.cache[chave]
    W = c.W
    base = c.g.cache.get(("p02b", _chave(e)))
    pw, ph = int(round(lay["pw"])), int(round(lay["ph"]))
    m = int(round(0.09 * pw))
    pad = lay["pad"]
    if base is None:
        base = Image.new("RGBA", (pw + 2 * m, ph + 2 * m), (0, 0, 0, 0))
        corpo = d.painel(pw, ph, raio=int(0.05 * min(pw, ph * 1.3)), fundo=PAPEL, borda=BORDA,
                         larg_borda=max(1, int(round(0.0028 * W))))
        # sombra macia caindo na parede
        sa = Image.new("L", base.size, 0)
        sa.paste(corpo.getchannel("A").point(lambda v: int(v * 0.30)), (m, m + int(0.035 * pw)))
        sa = sa.filter(ImageFilter.GaussianBlur(max(2, 0.03 * pw)))
        sombra = Image.new("RGBA", base.size, (26, 32, 30, 255))
        sombra.putalpha(sa)
        base.alpha_composite(sombra)
        base.alpha_composite(corpo, (m, m))
        dr = ImageDraw.Draw(base)
        barra = lay["barra"]
        # barra de janela: 3 pontinhos + etiqueta (ou pílula cinza)
        r = max(2, 0.017 * pw) if lay["tipo"] == "lado" else max(2, 0.012 * pw)
        xp = m + pad * 0.85
        for i in range(3):
            cx = xp + i * r * 2.7
            dr.ellipse((cx - r, m + barra / 2 - r, cx + r, m + barra / 2 + r), fill=d.cor(PONTO))
        x_et = xp + 2 * r * 2.7 + r * 2.6
        et = str(e.get("etiqueta", "")).strip()
        fe = None
        if et and lay["fe"]:
            # nunca corta a etiqueta com "…": diminui até o mínimo legível; se não couber, some
            lim = pw - (x_et - m) - pad * 0.6
            tam = lay["fe"]
            while tam >= max(8, int(0.035 * W)) and d.fonte(tam, 650).getlength(et) > lim:
                tam -= 1
            if tam >= max(8, int(0.035 * W)):
                fe = d.fonte(tam, 650)
        if fe is not None:
            d.escrever(base, (x_et, m + barra / 2 - fe.size * 0.62), [et], fe, ETIQ)
        else:
            pl = d.painel(pw * 0.30, max(3, barra * 0.22), raio=int(barra * 0.11), fundo=PILULA)
            base.alpha_composite(pl, (int(x_et), int(m + barra / 2 - pl.height / 2)))
        dr.line((m + 1, m + barra, m + pw - 2, m + barra), fill=d.cor(FIO), width=max(1, int(round(0.0028 * W))))
        # texto principal
        f = d.fonte(lay["fonte"], 800)
        al = lay["al"]
        marca = str(e.get("marca", "")).strip().lower().strip(".,!?:;")
        y = m + barra + pad * 0.55
        espaco = f.getlength(" ")
        for li, linha in enumerate(lay["linhas"]):
            x = m + lay["u0"]
            yy = y + li * al
            for p in linha.split():
                wp = f.getlength(p)
                if marca and p.lower().strip(".,!?:;\"'") == marca:
                    fx = d.painel(wp + f.size * 0.26, f.size * 0.92, raio=int(f.size * 0.14), fundo=LIMA)
                    base.alpha_composite(fx, (int(x - f.size * 0.13), int(yy + f.size * 0.13)))
                d.escrever(base, (x, yy), [p], f, TINTA)
                x += wp + espaco
        y_txt = y + al * len(lay["linhas"]) + pad * 0.45
        # área de imagem (sálvia + círculo lima), linha do tempo e traços
        tl_h = max(0.05 * pw, 0.085 * ph)
        traco_h = max(2, 0.016 * ph)
        y_tl = m + ph - pad * 0.8 - traco_h * 3.4 - tl_h
        img_h = y_tl - pad * 0.45 - y_txt
        if img_h > max(0.11 * ph, 0.2 * pw):
            area = d.painel(pw - 2 * pad, img_h, raio=int(0.04 * pw), fundo=lay["salvia"])
            diam = min(0.46 * pw, img_h * 0.86)
            circ = Image.new("RGBA", area.size, (0, 0, 0, 0))
            ImageDraw.Draw(circ).ellipse(
                (area.width * 0.56 - diam / 2, area.height * 0.5 - diam / 2,
                 area.width * 0.56 + diam / 2, area.height * 0.5 + diam / 2), fill=d.cor(LIMA, 0.92))
            ic = str(e.get("icone", "")).strip()
            if ic in ICONES:
                icn = d.icone(ic, max(8, int(diam * 0.46)), TINTA)
                circ.alpha_composite(icn, (int(area.width * 0.56 - icn.width / 2), int(area.height * 0.5 - icn.height / 2)))
            circ.putalpha(ImageChops.multiply(circ.getchannel("A"), area.getchannel("A")))
            area.alpha_composite(circ)
            base.alpha_composite(area, (int(m + pad), int(y_txt)))
        if y_tl > y_txt + 0.02 * ph:
            for k, frac in enumerate((0.72, 0.48)):
                yb = y_tl + tl_h + traco_h * (1.1 + k * 1.5)
                bar = d.painel((pw - 2 * pad) * frac, traco_h, raio=int(traco_h / 2), fundo=LINHA)
                base.alpha_composite(bar, (int(m + pad), int(yb)))
        c.g.cache[("p02b", _chave(e))] = base
        c.g.cache[("p02tl", _chave(e))] = (y_tl, tl_h, y_tl > y_txt + 0.02 * ph)
    y_tl, tl_h, tem_tl = c.g.cache[("p02tl", _chave(e))]
    img = base.copy()
    if tem_tl:
        tl = d.painel(pw - 2 * pad, tl_h, raio=int(tl_h * 0.2), fundo=TL_FUNDO)
        n, gap = 6, tl_h * 0.16
        bw = (tl.width - gap * (n + 1)) / n
        dr = ImageDraw.Draw(tl)
        for i in range(n):
            x = gap + i * (bw + gap)
            dr.rounded_rectangle((x, gap, x + bw, tl_h - gap), radius=max(1, int(tl_h * 0.1)),
                                 fill=d.cor(LIMA if i < acesos else TL_APAGADO, 0.92))
        img.alpha_composite(tl, (int(m + pad), int(y_tl)))
    c.g.cache[chave] = img
    return img


# ------------------------------------------------------------------ recuo de câmera


def _rampa_tiras(W, H, ox, oy, bw, bh, fw):
    """Alfas (L) das 3 tiras de parede estendida: 255 fora do quadro, rampa suave para dentro."""
    lin = (255 * (1 - np.clip((np.arange(oy + fw) - oy) / fw, 0, 1))).astype(np.uint8)
    topo = Image.fromarray(np.repeat(lin[:, None], W, axis=1), "L")
    col_e = (255 * (1 - np.clip((np.arange(ox + fw) - ox) / fw, 0, 1))).astype(np.uint8)
    esq = Image.fromarray(np.repeat(col_e[None, :], H - oy, axis=0), "L")
    xs = np.arange(ox + bw - fw, W)
    col_d = (255 * (1 - np.clip((ox + bw - 1 - xs) / fw, 0, 1))).astype(np.uint8)
    dire = Image.fromarray(np.repeat(col_d[None, :], H - oy, axis=0), "L")
    return topo, esq, dire


def _recuo(c, s):
    """Câmera recuada (s<1): o vídeo encolhe ancorado embaixo, no centro, e a parede continua em
    volta (bordas estendidas, desfocadas e mais escuras para fora, como uma vinheta).
    Devolve (base, grande, (ox, oy), fw) — 'grande' é o quadro encolhido e limpo (para recortar a pessoa).
    Tudo em RGB: redimensionar RGB custa metade do RGBA (o Pillow não precisa pré-multiplicar o alfa)."""
    W, H = c.W, c.H
    f = c.fonte.convert("RGB")
    bw, bh = int(round(W * s)), int(round(H * s))
    ox, oy = (W - bw) // 2, H - bh
    fw = max(2, int(round(0.035 * W)))
    grande = f.resize((bw, bh), Image.BILINEAR)
    base = Image.new("RGB", (W, H))
    base.paste(grande, (ox, oy))
    # parede estendida em baixa resolução (rápido)
    sw, sh = max(8, W // 8), max(8, H // 8)
    peq = f.resize((sw * 2, sh * 2), Image.NEAREST).reduce(2)
    nw, nh = max(1, int(round(sw * s))), max(1, int(round(sh * s)))
    x0 = (sw - nw) // 2
    arr = np.asarray(peq.resize((nw, nh), Image.BILINEAR)).astype(np.float32)
    arr = np.pad(arr, ((sh - nh, 0), (x0, sw - nw - x0), (0, 0)), mode="edge")
    ys, xs = np.arange(sh)[:, None], np.arange(sw)[None, :]
    dist = np.maximum(np.maximum(np.clip((x0 - xs) / max(1, x0), 0, 1),
                                 np.clip((xs - (x0 + nw)) / max(1, sw - nw - x0), 0, 1)),
                      np.clip(((sh - nh) - ys) / max(1, sh - nh), 0, 1))
    arr *= (0.86 - 0.26 * dist)[:, :, None]
    parede = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB").filter(
        ImageFilter.GaussianBlur(max(1.0, sw * 0.03)))
    chave = ("p02tiras", bw, bh)
    tiras = c.g.cache.get(chave) or _rampa_tiras(W, H, ox, oy, bw, bh, fw)
    if any(abs(s - gr["s"]) < 1e-6 for gr in c.g.cache["_p02"]["grupos"]):
        c.g.cache[chave] = tiras   # só guarda os tamanhos parados (na transição muda a cada quadro)
    ax, ay = sw / W, sh / H
    for (x_0, y_0, x_1, y_1), alfa in zip(((0, 0, W, oy + fw), (0, oy, ox + fw, H), (ox + bw - fw, oy, W, H)), tiras):
        if x_1 - x_0 < 1 or y_1 - y_0 < 1:
            continue
        im = parede.resize((x_1 - x_0, y_1 - y_0), Image.BILINEAR, box=(x_0 * ax, y_0 * ay, x_1 * ax, y_1 * ay))
        base.paste(im, (x_0, y_0), alfa)
    return base, grande, (ox, oy), fw


def _pessoa_regiao(c, s, reg, recuo):
    """Camada RGBA só com a pessoa dentro da região reg=(x0,y0,x1,y1) da tela (para recolocá-la
    por cima dos painéis). Usa o quadro LIMPO. Sem máscara neste quadro: elipse na cabeça."""
    W, H = c.W, c.H
    x0, y0, x1, y1 = reg
    w, h = x1 - x0, y1 - y0
    if recuo is not None:
        grande, (ox, oy), fw = recuo
        img = grande.crop((x0 - ox, y0 - oy, x1 - ox, y1 - oy))
    else:
        img = c.fonte.crop(reg)
        ox = oy = 0
    if c.mascara is not None:
        if recuo is not None:
            mw, mh = c.mascara.size
            caixa = (max(0.0, (x0 - ox) / s), max(0.0, (y0 - oy) / s),
                     min(float(mw), (x1 - ox) / s), min(float(mh), (y1 - oy) / s))
            m = c.mascara.resize((w, h), Image.BILINEAR, box=caixa)
        else:
            m = c.mascara.crop(reg)
    else:
        if not c.g.tem_mascara:
            return None
        # o vídeo tem recorte mas faltou este quadro da máscara: protege a cabeça
        rx0, ry0, rx1, ry1 = c.rosto
        fwid, fh = rx1 - rx0, ry1 - ry0
        cx = (rx0 + rx1) / 2
        el = (cx - fwid * 0.8, ry0 - fh * 0.65, cx + fwid * 0.8, ry1 + fh * 0.5)
        el = (W / 2 + (el[0] - W / 2) * s - x0, H + (el[1] - H) * s - y0,
              W / 2 + (el[2] - W / 2) * s - x0, H + (el[3] - H) * s - y0)
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).ellipse(el, fill=255)
        m = m.filter(ImageFilter.GaussianBlur(max(2, 0.01 * W)))
    if recuo is not None:  # a pessoa também se funde na borda do quadro encolhido
        grande, (ox, oy), fw = recuo
    if recuo is not None and (x0 < ox + fw or x1 > ox + grande.width - fw or y0 < oy + fw):
        xs = np.arange(x0, x1)
        col = np.clip(np.minimum(xs - ox + 0.5, ox + grande.width - xs - 0.5) / fw, 0, 1)
        lin = np.clip((np.arange(y0, y1) - oy + 0.5) / fw, 0, 1)
        pena = Image.fromarray((np.minimum(lin[:, None], col[None, :]) * 255).astype(np.uint8), "L")
        m = ImageChops.multiply(m, pena)
    img.putalpha(m)
    return img


# ------------------------------------------------------------------ quadro


def _estado(e, lay, t):
    """Ângulos/opacidade do painel no instante t (entrada em dobradiça e saída).
    parado=True quando já assentou (a imagem projetada pode vir do cache)."""
    ini, fim = float(e["inicio"]), float(e["fim"])
    if t < ini - ENTRA or t > fim + SAI:
        return None
    k_in = d.mapear(t, ini - ENTRA, ini + 0.5)
    k_out = d.mapear(t, fim, fim + SAI)
    op = d.saida(d.mapear(t, ini - ENTRA, ini + 0.12)) * (1 - d.entrada(d.mapear(t, fim + 0.08, fim + SAI)))
    parado = k_in >= 1.0 and k_out <= 0.0
    if lay["tipo"] == "centro":
        flap = 76 * (1 - d.mola(k_in, 1.2)) + 80 * d.entrada(k_out)
        return {"teta": 0.0, "fi": 0.0, "flap": 0.0 if parado else flap, "op": op, "parado": parado}
    sinal = 1 if lay["teta"] > 0 else -1
    teta = lay["teta"] + sinal * 62 * (1 - d.mola(k_in, 1.3)) + sinal * 64 * d.entrada(k_out)
    return {"teta": lay["teta"] if parado else teta, "fi": lay["fi"], "flap": 0.0, "op": op, "parado": parado}


def _projetado(c, e, lay, st, s, dx, dy, acesos):
    """Painel projetado na tela: (imagem RGBA, x, y)."""
    W, H = c.W, c.H
    plano = _painel_plano(c, e, lay, acesos)
    k = s / lay["s0"]
    px = W / 2 + (lay["px_c"] - W / 2) * s + dx
    py = H + (lay["py_c"] - H) * s + dy
    m = (plano.width - int(round(lay["pw"]))) / 2
    cantos = _cantos(px, py, lay["pw"] * k, lay["ph"] * k, st["teta"], st["fi"], 1.4 * W, m=m * k,
                     piv=lay["piv"], flap=st["flap"])
    xs, ys = [p[0] for p in cantos], [p[1] for p in cantos]
    bx0, by0 = int(math.floor(min(xs))), int(math.floor(min(ys)))
    bx1, by1 = int(math.ceil(max(xs))), int(math.ceil(max(ys)))
    if bx1 - bx0 < 2 or by1 - by0 < 2:
        return None
    rel = [(x - bx0, y - by0) for x, y in cantos]
    coef = _homografia([(0, 0), (plano.width, 0), (plano.width, plano.height), (0, plano.height)], rel)
    cam = plano.transform((bx1 - bx0, by1 - by0), Image.PERSPECTIVE, coef, Image.BILINEAR)
    return cam, bx0, by0


def _limpar_cache(c):
    """Esquece imagens de painéis que já saíram (só economia de memória; não muda o resultado)."""
    t = c.t
    velhos = [k for k in c.g.cache if isinstance(k, tuple) and k and k[0] in ("p02", "p02w", "p02b", "p02tl")
              and isinstance(k[1], tuple) and k[1][1] + SAI < t - 1.5]
    for k in velhos:
        del c.g.cache[k]


def quadro(c):
    est = c.g.cache.get("_p02") or {"grupos": [], "lay": {}}
    W, H, t = c.W, c.H, c.t
    if c.i % 15 == 0:
        _limpar_cache(c)
    s = _s_no_tempo(est["grupos"], t)
    s_parado = abs(s - 1.0) < 1e-6 or any(abs(s - gr["s"]) < 1e-6 for gr in est["grupos"])
    vis = []
    for e in c.eventos:
        if e.get("tipo") != "painel":
            continue
        lay = est["lay"].get(_chave(e))
        st = _estado(e, lay, t) if lay else None
        if st and st["op"] > 0.003:
            vis.append((e, lay, st))
    if s >= 0.9995 and not vis:
        return c.fonte
    # a parede balança devagar (como na prévia): os painéis e os títulos andam juntos
    onda = 2 * math.pi * t / PERIODO
    dx, dy = math.sin(onda) * 0.016 * W, -(1 - math.cos(onda)) / 2 * 0.007 * H
    # ordem: quem está saindo fica atrás; depois laterais; o central na frente
    vis.sort(key=lambda v: (0 if t > float(v[0]["fim"]) else 1, v[1]["tipo"] == "centro"))
    colocados = []
    for e, lay, st in vis:
        ini, fim = float(e["inicio"]), float(e["fim"])
        acesos = 1 + min(5, int(6 * d.mapear(t, ini + 0.2, fim - 0.2)))
        if st["parado"] and s_parado:
            chave = ("p02w", _chave(e), acesos, round(s, 5))
            if chave not in c.g.cache:
                c.g.cache[chave] = _projetado(c, e, lay, st, s, 0.0, 0.0, acesos)
            pr = c.g.cache[chave]
            if pr is None:
                continue
            cam, bx, by = pr[0], pr[1] + int(round(dx)), pr[2] + int(round(dy))
        else:
            pr = _projetado(c, e, lay, st, s, dx, dy, acesos)
            if pr is None:
                continue
            cam, bx, by = pr
        if st["op"] < 0.997:
            cam = cam.copy()
            cam.putalpha(cam.getchannel("A").point(lambda v, o=st["op"]: int(v * o)))
        colocados.append((cam, bx, by))
    recuo = None
    if s < 0.9995:
        base, grande, desl, fw = _recuo(c, s)
        recuo = (grande, desl, fw)
    else:
        base = c.fonte
    # regiões onde a pessoa precisa voltar por cima: a caixa de cada painel (juntando as que se tocam)
    caixas = []
    for cam, bx, by in colocados:
        cx = [bx, by, bx + cam.width, by + cam.height]
        for k in range(len(caixas) - 1, -1, -1):
            o = caixas[k]
            if cx[0] < o[2] and o[0] < cx[2] and cx[1] < o[3] and o[1] < cx[3]:
                cx = [min(cx[0], o[0]), min(cx[1], o[1]), max(cx[2], o[2]), max(cx[3], o[3])]
                caixas.pop(k)
        caixas.append(cx)
    pessoas = []
    for x0, y0, x1, y1 in caixas:
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        if recuo is not None:   # a pessoa só existe dentro do quadro encolhido
            (ox, oy), gw, gh = recuo[1], recuo[0].width, recuo[0].height
            x0, y0, x1, y1 = max(x0, ox), max(y0, oy), min(x1, ox + gw), min(y1, oy + gh)
        if x1 > x0 and y1 > y0:
            p = _pessoa_regiao(c, s, (x0, y0, x1, y1), recuo)   # do quadro LIMPO, antes dos painéis
            if p is not None:
                pessoas.append((p, x0, y0))
    for cam, bx, by in colocados:
        _por(base, cam, bx, by)
    for p, x0, y0 in pessoas:
        _por(base, p, x0, y0)
    return base


def _por(base, cam, x, y):
    """Põe a camada RGBA sobre a base (RGBA: alpha_composite; RGB opaca: paste com o alfa como máscara,
    que dá o mesmo resultado), aceitando posição parcialmente fora da tela."""
    if base.mode == "RGBA":
        d.colar_em(base, cam, (x, y))
        return
    W, H = base.size
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(cam.width, W - x), min(cam.height, H - y)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    if (cx0, cy0, cx1, cy1) != (0, 0, cam.width, cam.height):
        cam = cam.crop((cx0, cy0, cx1, cy1))
    base.paste(cam, (x + cx0, y + cy0), cam)


# ------------------------------------------------------------------ validação do plano


def validar(plano, duracao):
    p = []
    pans = sorted([e for e in plano["eventos"] if e.get("tipo") == "painel"], key=lambda e: e["inicio"])
    for e in pans:
        tx = str(e.get("texto", "")).strip()
        ini = float(e["inicio"])
        if not tx:
            p.append(f"Painel em {ini:.2f}s sem 'texto'.")
        elif len(tx.split()) > 5 or len(tx) > 34:
            p.append(f"Painel em {ini:.2f}s com texto longo demais (use 1 a 4 palavras).")
        et = str(e.get("etiqueta", "")).strip()
        if et and (len(et.split()) > 3 or len(et) > 22):
            p.append(f"Etiqueta do painel em {ini:.2f}s longa demais (1 a 2 palavras).")
        if str(e.get("lado", "auto")).strip().lower() not in LADOS + ("meio",):
            p.append(f"Painel em {ini:.2f}s: lado '{e.get('lado')}' não existe (use auto, esquerda, direita ou centro).")
        if e.get("icone") and str(e["icone"]).strip() not in ICONES:
            p.append(f"Painel em {ini:.2f}s: ícone '{e['icone']}' não existe.")
        if e.get("marca") and str(e["marca"]).strip().lower().strip(".,!?") not in \
                [w.lower().strip(".,!?:;") for w in tx.split()]:
            p.append(f"Painel em {ini:.2f}s: a 'marca' precisa ser uma palavra do texto.")
        dur = float(e["fim"]) - ini
        if dur < 1.2:
            p.append(f"Painel em {ini:.2f}s dura {dur:.1f}s: pouco para ler (mínimo 1,2 s).")
        if dur > 10:
            p.append(f"Painel em {ini:.2f}s dura {dur:.1f}s: longo demais (máximo ~8 s).")
    for a in pans:
        juntos = [b for b in pans if b is not a and min(a["fim"], b["fim"]) - max(a["inicio"], b["inicio"]) > 0.5]
        if len(juntos) >= 2:
            p.append(f"Mais de 2 painéis ao mesmo tempo perto de {a['inicio']:.2f}s: no máximo 2 juntos "
                     f"(um na esquerda e um na direita).")
            break
    for a in pans:
        if _lado_pedido(a) != "centro":
            continue
        juntos = [b for b in pans if b is not a and min(a["fim"], b["fim"]) - max(a["inicio"], b["inicio"]) > 0.5]
        if juntos:
            p.append(f"Painel central em {a['inicio']:.2f}s aparece junto com outro painel: o central fica "
                     f"sozinho (termine o outro antes ou comece depois).")
    for e in pans:
        if _lado_pedido(e) == "centro":
            continue
        longas = [w for w in str(e.get("texto", "")).split() if len(w.strip(".,!?:;")) > 12]
        if longas:
            p.append(f"Painel em {float(e['inicio']):.2f}s: a palavra '{longas[0]}' é longa demais para painel "
                     f"lateral (até 12 letras). Use lado 'centro' ou troque por uma palavra mais curta.")
    for i, a in enumerate(pans):
        la = _lado_pedido(a)
        for b in pans[i + 1:]:
            if la != "auto" and _lado_pedido(b) == la and _sobrepoe(a, b, folga=0.05):
                p.append(f"Dois painéis no lado '{la}' ao mesmo tempo ({a['inicio']:.2f}s e {b['inicio']:.2f}s): "
                         f"deixe ~0,6 s entre o fim de um e o início do outro, ou troque o lado.")
    return p
