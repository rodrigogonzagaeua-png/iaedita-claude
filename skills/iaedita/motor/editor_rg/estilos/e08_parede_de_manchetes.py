"""08 · Parede de manchetes — recortes de papel com as manchetes da fala são pregados, um a um, numa
parede ATRÁS da pessoa: a cabeça e os ombros passam na frente dos papéis (oclusão com o recorte).
Cada manchete entra no instante em que a frase é dita (sobe, cresce e assenta com um leve giro), a
parede inteira balança devagar e, no fim do trecho, os papéis saem juntos e a tela fica limpa.

Composição: a posição de cada manchete é calculada UMA vez em preparar(g), a partir do rosto ao longo
do tempo em que ela fica na tela: o TEXTO nunca fica atrás da cabeça, dos ombros ou da legenda (o papel
pode ficar). Rosto grande (> 32% da largura) ou cabeça alta no quadro: a câmera recua até 20% (o vídeo
encolhe ancorado embaixo, sobre o próprio quadro desfocado e escurecido) só enquanto há paredes.
Parede cheia: o papel novo pode pousar sobre um já lido, que então sai, e um "Aviso (parede de
manchetes)" vai para o stderr. Sem recorte: os papéis ficam por cima, em volta e acima da cabeça
(podem tapar o alto do cabelo e os ombros, com sombra), nunca sobre o rosto.
quadro(c) só depende de c.t e do plano. Legenda própria: bloco editorial claro, serifado, alinhado à
esquerda, com fio vinho em cima e a palavra falada em vinho (como na prévia aprovada)."""
from __future__ import annotations

import math
import sys
from itertools import combinations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .. import desenho as d
from ..legenda import agrupar

try:  # OpenCV deixa o recuo de câmera mais rápido; sem ele o resultado é o mesmo
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

INFO = {
    "id": "08-parede-de-manchetes",
    "nome": "Parede de manchetes",
    "precisa_recorte": True,
    "antes": 0.15,
    "depois": 0.9,
    # perfil da legenda própria (Cormorant 700, bloco claro, palavra falada em vinho)
    "legenda": {"fonte": "serif", "peso": 700, "tamanho": 0.074, "cor": "#222729", "destaque": "#88463E",
                "caixa": "#F8F7F0F5", "max_caracteres": 22, "max_linhas": 1, "animacao": "subir"},
    "legenda_propria": True,
    "eventos": {
        "manchete": "inicio (instante em que a frase da manchete começa a ser dita), fim (quando a parede é "
                    "limpa: use o MESMO fim para todas as manchetes da mesma parede), texto (1 a 5 palavras, "
                    "até 34 letras), chapeu (opcional: 1 a 3 palavras curtas acima da manchete, até 16 letras, ex. "
                    "'NOVIDADE'), escuro (opcional: true = papel verde-escuro com letras verde-limão, para a "
                    "manchete mais forte da parede), marca (opcional: 1 palavra do texto que ganha sublinhado), "
                    "lado ('auto' padrão | 'esquerda' | 'direita' | 'topo'), som (use 'papel')",
    },
}

# ------------------------------------------------------------------ paleta (da prévia aprovada)
PAPEL = "#FFFCF1"
TINTA = "#263229"
ESCURO = "#263329"
LIMA = "#D4ED80"
VINHO = "#88463E"
LEG_CAIXA = "#F8F7F0F5"
LEG_TINTA = "#222729"
SOMBRA = (21, 39, 26)

# ------------------------------------------------------------------ medidas (frações de W/H)
TOPO_TXT = 0.115     # texto nunca acima disto (interface da rede social)
TOPO_PAPEL = 0.10
ESQ_TXT, DIR_TXT = 0.045, 0.875
ESQ_PAPEL, DIR_PAPEL = 0.025, 0.965
LEG_BASE = 0.795     # base da legenda (zona segura de baixo)
CAB = 0.45           # cabelo/boné acima da caixa do rosto (x altura do rosto), como o motor
S_MIN = 0.80         # recuo máximo da câmera em plano fechado
FW_ALVO = 0.30       # largura do rosto (fração de W) que deixa parede livre em volta da cabeça
FW_RECUO = 0.32      # recua se o rosto passar desta largura (plano fechado)...
TOPO_CAB = 0.25      # ...ou se o alto da cabeça estiver acima desta altura (pouca parede livre)
ROTS = (-6.0, 5.0, -3.0, 7.0, -5.0, 4.0, -7.0, 3.0)
LADOS = ("auto", "esquerda", "direita", "topo")
PERIODO = 6.0        # balanço lento da parede (s)

# ------------------------------------------------------------------ tempos das animações (s)
E_ANTES = 0.10       # a entrada começa um pouquinho antes da palavra
E_DUR = 0.55         # sobe + cresce + assenta (curva ease-out exponencial, como na prévia)
S_DUR = 0.42         # saída (desbota e desce)
S_PASSO = 0.07       # saída em cascata: cada papel sai 0,07 s depois do anterior


def _u(W, H):
    """Unidade de medida: largura de um quadro 9:16 com a mesma altura."""
    return min(W, H * 0.5625)


def _chave(e):
    return (round(float(e["inicio"]), 3), round(float(e["fim"]), 3), str(e.get("texto", "")))


def _bool(v):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "sim", "yes", "s")
    return bool(v)


def _lado(e):
    lado = str(e.get("lado", "auto") or "auto").strip().lower()
    lado = {"esq": "esquerda", "dir": "direita", "left": "esquerda", "right": "direita", "cima": "topo",
            "alto": "topo", "top": "topo", "acima": "topo"}.get(lado, lado)
    return lado if lado in LADOS else "auto"


def _limpo(p):
    return p.lower().strip(".,!?:;\"'()…")


# ------------------------------------------------------------------ texto


def _metricas(f):
    cap = -f.getbbox("H", anchor="ls")[1]
    desc = f.getbbox("gjpqy,", anchor="ls")[3]
    return cap, desc


def _melhor_quebra(palavras, f, larg, max_linhas):
    """Divide a manchete em até max_linhas linhas que caibam em larg: linhas equilibradas, sem
    palavra curtinha sozinha no fim e sem 'de'/'a'/'no' pendurado no fim da linha."""
    n = len(palavras)
    if n == 0:
        return None
    esp = f.getlength(" ")
    ws = [f.getlength(p) for p in palavras]
    melhor = None
    for k in range(1, min(max_linhas, n) + 1):
        for cortes in combinations(range(1, n), k - 1):
            cs = (0,) + cortes + (n,)
            lw = [sum(ws[a:b]) + esp * (b - a - 1) for a, b in zip(cs, cs[1:])]
            mx = max(lw)
            if mx > larg:
                continue
            # linha com uma palavrinha sozinha ("de", "na", "26"): tipografia de amador, proibida
            if k > 1 and any(b - a == 1 and len(_limpo(" ".join(palavras[a:b]))) <= 3 for a, b in zip(cs, cs[1:])):
                continue
            nota = mx + (0.3 * (mx - min(lw)) if k > 1 else 0.0) + k * 0.03 * larg + (0.18 * larg if k > 2 else 0.0)
            feia = 0.35 if k > 2 else 0.0
            for b in cs[1:-1]:
                fim_linha = _limpo(palavras[b - 1].split()[-1])
                if len(fim_linha) <= 2 and not fim_linha[:1].isdigit():
                    nota += 0.25 * larg
            if melhor is None or nota < melhor[0]:
                linhas = [" ".join(palavras[a:b]) for a, b in zip(cs, cs[1:])]
                melhor = (nota, linhas, mx, feia)
    return (melhor[1], melhor[2], melhor[3]) if melhor else None


def _colar_curtas(palavras):
    """Palavrinhas (até 3 letras: 'a', 'de', 'da', 'no', 'que', '26') andam junto com a palavra
    seguinte, como num título de jornal: nunca ficam sozinhas no fim da linha."""
    out, cola = [], ""
    for i, p in enumerate(palavras):
        if i < len(palavras) - 1 and len(_limpo(p)) <= 3:
            cola = f"{cola} {p}".strip()
            continue
        out.append(f"{cola} {p}".strip())
        cola = ""
    if cola:
        out.append(cola)
    return out


def _ajustar(texto, larg, tmax, tmin, peso, fam, max_linhas=3, colar=True):
    palavras = _colar_curtas(texto.split()) if colar else texto.split()
    tam = int(round(tmax))
    while tam >= int(round(tmin)):
        f = d.fonte(tam, peso, fam)
        r = _melhor_quebra(palavras, f, larg, max_linhas)
        if r:
            return f, r[0], r[1], r[2]
        tam -= max(1, int(round(tam * 0.04)))
    return None


def _larg_espacado(txt, f, esp):
    return sum(f.getlength(ch) for ch in txt) + esp * max(0, len(txt) - 1)


def _escrever_espacado(dr, x, y_base, txt, f, cor, esp):
    for ch in txt:
        dr.text((x, y_base), ch, font=f, fill=cor, anchor="ls")
        x += f.getlength(ch) + esp


def _medir(e, u, tw, esc=1.0, colar=True):
    """Medidas de um recorte para uma largura de texto tw (px). None se a manchete não cabe.
    esc < 1: versão compacta (letra menor, ainda legível) para quando a parede está cheia."""
    escuro = _bool(e.get("escuro"))
    texto = " ".join(str(e.get("texto", "")).split())
    chapeu = " ".join(str(e.get("chapeu", "") or "").upper().split())
    if escuro:
        fam, peso, tmax, tmin, ent = "inter", 800, 0.066 * u * esc, max(0.040, 0.048 * esc) * u, 1.06
    else:
        fam, peso, tmax, tmin, ent = "serif", 700, 0.082 * u * esc, max(0.047, 0.056 * esc) * u, 1.0
    r = _ajustar(texto, tw, tmax, tmin, peso, fam, 3, colar)
    if r is None:
        return None
    f, linhas, larg, feia = r
    fk = d.fonte(max(10, int(round(0.038 * u))), 700, "inter")   # chapéu nunca encolhe (>= 3,5% da largura)
    espk = 0.09 * fk.size
    larg_k = _larg_espacado(chapeu, fk, espk) if chapeu else 0.0
    if larg_k > 0.62 * u:
        chapeu, larg_k = "", 0.0
    bloco = max(larg, larg_k, 0.16 * u)
    cap, desc = _metricas(f)
    capk = _metricas(fk)[0] if chapeu else 0
    pad_x, pt, pb = 0.034 * u, 0.030 * u, 0.032 * u
    linha = max(1, int(round(0.0024 * u)))
    k_alt = (capk + 0.013 * u) if chapeu else (0.0075 * u + 0.010 * u)
    y_fio = pt + k_alt
    y_tit = y_fio + linha + 0.020 * u
    al = f.size * ent
    th = cap + al * (len(linhas) - 1) + desc
    y_barras = y_tit + th + 0.018 * u
    barra_h = max(2, int(round(0.0058 * u)))
    ch = y_barras + barra_h + pb
    return {"feia": feia, "escuro": escuro, "texto": texto, "chapeu": chapeu, "fam": fam, "peso": peso, "fs": f.size,
            "tmax": tmax, "linhas": linhas, "larg": larg, "bloco": bloco, "cap": cap, "al": al, "fk": fk.size,
            "espk": espk, "capk": capk, "pad_x": pad_x, "pt": pt, "y_fio": y_fio, "linha": linha, "y_tit": y_tit,
            "th": th, "y_barras": y_barras, "barra_h": barra_h, "cw": bloco + 2 * pad_x, "ch": ch,
            # retângulo do que precisa ficar visível (chapéu + título), no recorte com bloco à esquerda
            "txt": (pad_x - 0.006 * u, pt - 0.004 * u, pad_x + bloco + 0.004 * u, y_tit + th + 0.004 * u)}


# ------------------------------------------------------------------ desenho do recorte


def _papel_cortado(w, h, u, semente):
    """Papel claro com borda de tesoura (cantos levemente irregulares) e fibra sutil."""
    rng = np.random.default_rng(semente)
    j = 0.0045 * u
    ss = 3
    pts = [(rng.uniform(0, j), rng.uniform(0, j)), (w - rng.uniform(0, j), rng.uniform(0, j)),
           (w - rng.uniform(0, j), h - rng.uniform(0, j)), (rng.uniform(0, j), h - rng.uniform(0, j))]
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).polygon([(x * ss, y * ss) for x, y in pts], fill=255)
    m = m.resize((w, h), Image.LANCZOS)
    base = np.array(d.cor(PAPEL)[:3], np.float32)
    grad = np.linspace(2.0, -4.0, h, dtype=np.float32)[:, None, None]
    fibra = rng.normal(0.0, 2.0, (h, w, 1)).astype(np.float32)
    arr = np.clip(base[None, None, :] + grad + fibra, 0, 255).astype(np.uint8)
    pap = Image.fromarray(arr, "RGB").convert("RGBA")
    pap.putalpha(m)
    # filete escuro quase invisível na borda (dá corpo ao recorte sobre fundos claros)
    contorno = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(contorno).polygon(pts, outline=d.cor(TINTA, 0.16))
    pap.alpha_composite(contorno)
    return pap


def _render_cartao(med, ext, lado_bloco, u, semente, marca):
    escuro = med["escuro"]
    cw, ch = med["cw"] + ext, med["ch"]
    w, h = int(math.ceil(cw)), int(math.ceil(ch))
    M = 3
    cam = Image.new("RGBA", (w + 2 * M, h + 2 * M), (0, 0, 0, 0))
    if escuro:
        cam.alpha_composite(d.painel(w, h, raio=int(0.013 * u), fundo=ESCURO), (M, M))
    else:
        cam.alpha_composite(_papel_cortado(w, h, u, semente), (M, M))
    # Os traços vão numa camada TRANSPARENTE separada, juntada com alpha_composite: desenhar com cor
    # semitransparente direto no papel RGBA substituiria o pixel (e o alfa), abrindo furos no papel.
    ov = Image.new("RGBA", cam.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(ov)
    pad_x = med["pad_x"]
    x_b = M + (pad_x if lado_bloco == "esq" else ext + pad_x)
    bloco = med["bloco"]
    cor_txt = d.cor(LIMA) if escuro else d.cor(TINTA)
    cor_k = d.cor(LIMA, 0.85) if escuro else d.cor(VINHO)
    cor_fio = d.cor("#FFFFFF", 0.25) if escuro else d.cor(TINTA, 0.27)
    cor_barra = d.cor("#FFFFFF", 0.20) if escuro else d.cor(TINTA, 0.15)
    # extensão que vai para trás da cabeça: colunas de texto de jornal (só traços, sem letras)
    if ext > 0 and not escuro:
        rng = np.random.default_rng(semente + 101)
        if lado_bloco == "esq":
            xa, xb = M + med["cw"] - pad_x * 0.2, M + w - pad_x
        else:
            xa, xb = M + pad_x, M + ext + pad_x * 0.2
        passo = 0.020 * u
        esp = max(1, int(round(0.0034 * u)))
        y = M + med["y_fio"] + 0.004 * u
        n = 0
        while y + esp < M + med["y_barras"] + med["barra_h"]:
            frac = 1.0 if (n % 5) != 4 else rng.uniform(0.35, 0.7)
            dr.rectangle((xa, y, xa + (xb - xa) * frac, y + esp - 1), fill=d.cor(TINTA, 0.10))
            y += passo
            n += 1
    # chapéu (ou etiqueta vinho) + fio
    fk = d.fonte(med["fk"], 700, "inter")
    if med["chapeu"]:
        _escrever_espacado(dr, x_b, M + med["pt"] + med["capk"], med["chapeu"], fk, cor_k, med["espk"])
    else:
        dr.rectangle((x_b, M + med["pt"], x_b + 0.06 * u, M + med["pt"] + 0.0075 * u), fill=cor_k)
    yf = M + med["y_fio"]
    dr.rectangle((x_b, yf, x_b + bloco, yf + med["linha"] - 1), fill=cor_fio)
    # barras (o "corpo" da notícia, como na prévia: 55% + 30%)
    yb = M + med["y_barras"]
    hb = med["barra_h"]
    dr.rectangle((x_b, yb, x_b + bloco * 0.55, yb + hb - 1), fill=cor_barra)
    x2 = x_b + bloco * 0.55 + 0.006 * u
    dr.rectangle((x2, yb, x2 + bloco * 0.30, yb + hb - 1), fill=cor_barra)
    # título (camada própria, por cima do sublinhado)
    tx = Image.new("RGBA", cam.size, (0, 0, 0, 0))
    dt = ImageDraw.Draw(tx)
    f = d.fonte(med["fs"], med["peso"], med["fam"])
    base0 = M + med["y_tit"] + med["cap"]
    alvo = _limpo(str(marca or "")) if marca else ""
    esp_txt = f.getlength(" ")
    for i, l in enumerate(med["linhas"]):
        yb = base0 + i * med["al"]
        if alvo:
            x = x_b
            for p in l.split():
                wp = f.getlength(p)
                if _limpo(p) == alvo:   # sublinhado de caneta, um pouco torto
                    g = max(2.0, f.size * 0.075)
                    y_s = yb + f.size * 0.12
                    cor_s = d.cor("#FFFFFF", 0.85) if escuro else d.cor(VINHO, 0.95)
                    dr.polygon([(x - f.size * 0.04, y_s + g * 0.5), (x + wp + f.size * 0.06, y_s - g * 0.4),
                                (x + wp + f.size * 0.06, y_s + g * 0.6), (x - f.size * 0.04, y_s + g * 1.5)],
                               fill=cor_s)
                x += wp + esp_txt
        dt.text((x_b, yb), l, font=f, fill=cor_txt, anchor="ls")
    cam.alpha_composite(ov)
    cam.alpha_composite(tx)
    return cam


def _girar_com_sombra(cam, rot, u, escuro):
    g = cam.rotate(rot, resample=Image.BICUBIC, expand=True)
    desf = 0.017 * u
    dx, dy = 0.006 * u, 0.014 * u
    m = int(desf * 2.6 + max(dx, dy)) + 2
    out = Image.new("RGBA", (g.width + 2 * m, g.height + 2 * m), (0, 0, 0, 0))
    a = g.getchannel("A").point(lambda v: int(v * (0.40 if escuro else 0.34)))
    sh = Image.new("RGBA", g.size, SOMBRA + (255,))
    sh.putalpha(a)
    out.alpha_composite(sh, (m + int(round(dx)), m + int(round(dy))))
    out = out.filter(ImageFilter.GaussianBlur(desf))
    out.alpha_composite(g, (m, m))
    return out


def _cartao(g, lay):
    k = ("m08c", lay["chave"])
    if k not in g.cache:
        u = _u(g.W, g.H)
        cam = _render_cartao(lay["m"], lay["ext"], lay["lb"], u, 17 + lay["ordem"] * 7, lay["e"].get("marca"))
        g.cache[k] = _girar_com_sombra(cam, lay["rot"], u, lay["m"]["escuro"])
    return g.cache[k]


# ------------------------------------------------------------------ geometria da pessoa


def _zonas(g, t0, t1, s):
    """Cabeça (com cabelo/boné) e linha dos ombros na tela recuada s, durante [t0, t1]."""
    W, H = g.W, g.H
    t0 = max(0.0, t0)
    t1 = min(g.duracao, max(t1, t0 + 0.05))
    ts = np.arange(t0, t1 + 1e-6, 0.2)
    cx_ = np.array([g.rosto.em(float(t)) for t in ts], dtype=float)
    x0 = W / 2 + (cx_[:, 0] - W / 2) * s
    x1 = W / 2 + (cx_[:, 2] - W / 2) * s
    y0 = H + (cx_[:, 1] - H) * s
    y1 = H + (cx_[:, 3] - H) * s
    fw, fh = x1 - x0, y1 - y0
    # percentil 8/92 em vez de mín./máx.: um balanço rápido de cabeça só raspa o papel (a pessoa passa
    # na frente dele, que é a ideia do estilo); a parede não fica toda empurrada por um instante
    z = {"hx0": float(np.percentile(x0 - 0.16 * fw, 8)), "hx1": float(np.percentile(x1 + 0.16 * fw, 92)),
         "ht": float(np.percentile(y0 - CAB * fh, 8)), "hb": float((y1 + 0.10 * fh).max()),
         "cx": float(np.median((x0 + x1) / 2)), "fw": float(np.median(fw)), "fh": float(np.median(fh)),
         "ft": float(np.percentile(y0 - 0.08 * fh, 8))}   # testa (alto do rosto, sem o cabelo)
    # ombros: logo abaixo do queixo (pessoa perto da câmera ou inclinada tem ombros altos)
    z["corpo_y"] = z["hb"]
    z["corpo_x0"] = z["cx"] - 2.4 * z["fw"]
    z["corpo_x1"] = z["cx"] + 2.4 * z["fw"]
    return z


def _cruza(A, B):
    """A: (x0,y0,x1,y1) com arrays; B: escalares. Verdadeiro onde os retângulos se encostam."""
    return (A[0] < B[2]) & (B[0] < A[2]) & (A[1] < B[3]) & (B[1] < A[3])


def _toca_cabeca(A, z, mx, my, p=3.0):
    """A (retângulos, arrays) encosta na cabeça? A cabeça (com o movimento no intervalo) é uma forma
    arredondada (bola L3) dentro da caixa da zona: os cantos de cima ficam livres para os papéis."""
    cx, cy = (z["hx0"] + z["hx1"]) / 2, (z["ht"] + z["hb"]) / 2
    a, b = (z["hx1"] - z["hx0"]) / 2 + mx, (z["hb"] - z["ht"]) / 2 + my
    px = np.minimum(np.maximum(cx, A[0]), A[2])
    py = np.minimum(np.maximum(cy, A[1]), A[3])
    return (np.abs((px - cx) / a) ** p + np.abs((py - cy) / b) ** p) < 1.0


def _area_comum(A, B):
    w = np.clip(np.minimum(A[2], B[2]) - np.maximum(A[0], B[0]), 0, None)
    h = np.clip(np.minimum(A[3], B[3]) - np.maximum(A[1], B[1]), 0, None)
    return w * h


# ------------------------------------------------------------------ posição de cada manchete


def _posicionar(g, e, ordem, z, prev, s0, mascara, cap_top, obst=(), parede=1):
    W, H = g.W, g.H
    u = _u(W, H)
    xs = np.linspace(0.0, W, 81)
    ys = np.linspace(TOPO_PAPEL * H, 0.76 * H, 100)
    X, Y = np.meshgrid(xs, ys)
    X, Y = X.ravel(), Y.ravel()
    rot = ROTS[ordem % len(ROTS)]
    th = math.radians(rot)
    cs, sn = math.cos(th), math.sin(th)
    co, si = abs(cs), abs(sn)
    lado = _lado(e)
    ja, jb = float(e["inicio"]) - E_ANTES, float(e["fim"]) + 0.85
    # papéis que ainda estão inteiros na parede quando este entra (os que já estão saindo não contam)
    conc = [p for p in prev if p["fim"] > ja + 0.1 and p["ja"] < float(e["fim"])]
    # papéis da parede anterior que ainda estão desbotando quando este entra: evitar pousar em cima
    saindo = [p for p in prev if p not in conc and p["fim"] + S_PASSO * 4 + S_DUR > ja]
    legs = [r for (a, b, r) in obst if min(b, jb) > max(a, ja)]   # legenda que subiu para cima da cabeça
    CORPO = (z["corpo_x0"], z["corpo_y"], z["corpo_x1"], 2.0 * H)
    z_rosto = dict(z, ht=z["ft"])
    def _configs(esc, colar=True):
        medidas = []
        for tw_f in (0.20, 0.25, 0.30, 0.36, 0.43, 0.52, 0.62):
            m = _medir(e, u, tw_f * u, esc, colar)
            if m and not any(abs(m["cw"] - o["cw"]) < 1 and abs(m["ch"] - o["ch"]) < 1 for o in medidas):
                medidas.append(m)
        if not medidas:  # palavra longa demais: usa a menor fonte numa caixa larga
            m = _medir(e, u, 0.78 * u, esc, colar)
            if m:
                medidas.append(m)
        cf = []
        for r_ in (rot, 2.0 if rot >= 0 else -2.0):   # giro menor: cabe numa faixa mais baixa
            for m in medidas:
                cf.append((m, 0.0, "esq", r_))
                if mascara and not m["escuro"]:
                    cf.append((m, 0.12 * u, "esq", r_))
                    cf.append((m, 0.12 * u, "dir", r_))
        return medidas, cf

    por_esc = {(1.0, True): _configs(1.0)}
    medidas = por_esc[(1.0, True)][0]
    melhor = None
    # ordem de tentativa: tamanho normal sem cobrir títulos; versão compacta sem cobrir (e, se ainda não
    # couber, quebrando a linha antes da palavrinha); cobrindo um papel já lido (que então sai);
    # por último, cobrindo qualquer papel
    # (colar=False ainda proíbe palavrinha sozinha numa linha: só permite quebrar "Quebra de / moldura")
    tent = [(1.0, True, 0), (0.8, True, 0), (0.7, True, 0), (0.7, False, 0), (1.0, True, 1),
            (0.8, True, 1), (0.7, True, 1), (0.7, False, 1), (1.0, True, 2), (0.7, False, 2)]
    if parede >= 3:   # parede cheia: todos os papéis já nascem compactos (sobra lugar para os próximos)
        tent = [x for x in tent if x[0] < 1.0] + [x for x in tent if x[0] >= 1.0]
    for esc, colar, nivel in tent:
        if (esc, colar) not in por_esc:
            por_esc[(esc, colar)] = _configs(esc, colar)
        for (m, ext, lb, rc) in por_esc[(esc, colar)][1]:
            th = math.radians(rc)
            cs, sn = math.cos(th), math.sin(th)
            co, si = abs(cs), abs(sn)
            cw, ch = m["cw"] + ext, m["ch"]
            rx0, ry0, rx1, ry1 = m["txt"]
            if lb == "dir":
                rx0, rx1 = rx0 + ext, rx1 + ext
            ox, oy = (rx0 + rx1) / 2 - cw / 2, (ry0 + ry1) / 2 - ch / 2
            ta, tb = (rx1 - rx0) / 2, (ry1 - ry0) / 2
            ex, ey = cw / 2 * co + ch / 2 * si, cw / 2 * si + ch / 2 * co
            tcx, tcy = X + ox * cs + oy * sn, Y - ox * sn + oy * cs   # giro anti-horário do Pillow
            tex, tey = ta * co + tb * si, ta * si + tb * co
            P = (X - ex, Y - ey, X + ex, Y + ey)
            T = (tcx - tex, tcy - tey, tcx + tex, tcy + tey)
            ok = (P[0] >= ESQ_PAPEL * W) & (P[2] <= DIR_PAPEL * W) & (P[1] >= TOPO_PAPEL * H) & \
                 (P[3] <= cap_top - 0.006 * H)
            ok &= (T[0] >= ESQ_TXT * W) & (T[2] <= DIR_TXT * W) & (T[1] >= TOPO_TXT * H) & \
                  (T[3] <= cap_top - 0.016 * H)
            for r in legs:
                ok &= ~_cruza(T, r)
            if mascara:   # o texto nunca fica atrás da cabeça nem dos ombros
                ok &= ~_toca_cabeca(T, z, 0.02 * W, 0.012 * H)
                ok &= ~_cruza(T, CORPO)
            else:         # sem recorte o papel fica POR CIMA: pode tapar o alto do cabelo, nunca o rosto
                ok &= ~_toca_cabeca(P, z_rosto, 0.012 * W, 0.01 * H)
            if ext > 0:   # a sobra de papel vai para trás da cabeça, não para a borda
                ok &= (X <= z["cx"]) if lb == "esq" else (X >= z["cx"])
                ok &= (P[3] > z["ht"]) & (P[1] < z["hb"])
                # o meio da sobra precisa cair DENTRO da cabeça (senão ela aparece vazia)
                exc = (cw / 2 - ext / 2) * (1 if lb == "esq" else -1)
                qx, qy = X + exc * cs, Y - exc * sn
                ccx, ccy = (z["hx0"] + z["hx1"]) / 2, (z["ht"] + z["hb"]) / 2
                ra, rb = (z["hx1"] - z["hx0"]) / 2, (z["hb"] - z["ht"]) / 2
                ok &= (np.abs((qx - ccx) / ra) ** 3 + np.abs((qy - ccy) / rb) ** 3) < 0.85
            if lado == "esquerda":
                ok &= T[2] <= z["cx"]
            elif lado == "direita":
                ok &= T[0] >= z["cx"]
            elif lado == "topo":
                ok &= T[3] <= z["ht"]
            nota = -3.0 * (m["fs"] / m["tmax"]) + 0.9 * m["feia"] + (0.15 if rc != rot else 0.0)
            nota = nota + 0.9 * (T[1] - TOPO_TXT * H) / H
            gap = np.maximum(0.0, np.maximum(z["hx0"] - P[2], P[0] - z["hx1"])) / W
            # o centro (acima da cabeça) fica para depois: os primeiros papéis vão para os cantos
            nota = nota + 0.45 * np.clip(1 - np.abs(X - z["cx"]) / (0.28 * W), 0, 1)
            nota = nota + 1.6 * gap
            if mascara:
                vert = (P[1] < z["hb"]) & (P[3] > z["ht"])
                ov = np.clip(np.minimum(P[2], z["hx1"]) - np.maximum(P[0], z["hx0"]), 0, None) / W
                nota = nota - 0.9 * np.minimum(ov, 0.10) / 0.10 * vert
            if conc:
                ult = conc[-1]
                nota = nota + 0.6 * (np.sign(X - z["cx"]) == ult["lado"])
                dmin = np.min([np.hypot(X - p["X"], Y - p["Y"]) for p in conc], axis=0) / W
                nota = nota + 1.0 * np.clip(0.28 - dmin, 0, None) / 0.28
                area = (P[2] - P[0]) * (P[3] - P[1])
                for p in conc:
                    ia = _area_comum(P, p["P"]) / np.minimum(area, p["area"])
                    nota = nota + 2.0 * np.clip(ia - 0.15, 0, None) - 0.2 * ((ia > 0.02) & (ia <= 0.15))
                    # nível 0: nunca cobre título. Nível 1: pode pousar sobre um papel já lido (>= 1,5 s),
                    # que então sai da parede. Nível 2: sobre qualquer um (último recurso).
                    cobre = _cruza(P, p["T"])
                    # chapéu/escuro abrem ou fecham a parede: só saem depois de 3 s na tela
                    forte = bool(p["m"]["chapeu"]) or p["m"]["escuro"]
                    lido = float(e["inicio"]) - p["inicio"] >= (3.0 if forte else 1.5)
                    if nivel == 0 or (nivel == 1 and not lido):
                        ok &= ~cobre
                    else:
                        nota = nota + (1.0 if lido else (6.0 if forte else 3.0)) * cobre
            if saindo:
                area_ = (P[2] - P[0]) * (P[3] - P[1])
                for p in saindo:
                    nota = nota + 1.5 * np.clip(_area_comum(P, p["P"]) / np.minimum(area_, p["area"]), 0, 1)
            nota = np.where(ok, nota, np.inf)
            i = int(np.argmin(nota))
            if np.isfinite(nota[i]) and (melhor is None or nota[i] < melhor[0]):
                melhor = (float(nota[i]), m, ext, lb, float(X[i]), float(Y[i]),
                          tuple(float(v[i]) for v in P), tuple(float(v[i]) for v in T), rc)
        if melhor is not None:
            break
    if melhor is None:   # sem espaço livre: topo, no centro, com a menor manchete
        pequenas = por_esc.get((0.7, True), ([], []))[0] or medidas
        m = min(pequenas, key=lambda mm: mm["ch"]) if pequenas else _medir(e, u, 0.78 * u, 0.7)
        if m is None:
            return None
        co, si = abs(math.cos(math.radians(rot))), abs(math.sin(math.radians(rot)))
        ex = m["cw"] / 2 * co + m["ch"] / 2 * si
        ey = m["cw"] / 2 * si + m["ch"] / 2 * co
        Xc, Yc = W * 0.47, TOPO_PAPEL * H + ey
        melhor = (0.0, m, 0.0, "esq", Xc, Yc, (Xc - ex, Yc - ey, Xc + ex, Yc + ey),
                  (Xc - ex, Yc - ey, Xc + ex, Yc + ey), rot)
        print(f"Aviso (parede de manchetes): sem espaço livre para '{e.get('texto')}' em {e['inicio']:.2f}s; "
              f"use menos manchetes ao mesmo tempo ou textos mais curtos.", file=sys.stderr)
    _, m, ext, lb, Xb, Yb, P, T, rot = melhor
    cobertos = [p for p in conc if bool(_cruza(tuple(np.array([v]) for v in P), p["T"])[0])]
    return {"cobertos": cobertos, "e": e, "chave": _chave(e), "ordem": ordem, "m": m, "ext": ext, "lb": lb, "X": Xb, "Y": Yb,
            "rot": rot, "P": P, "T": T, "area": (P[2] - P[0]) * (P[3] - P[1]), "ja": ja, "jb": jb,
            "inicio": float(e["inicio"]), "fim": float(e["fim"]), "lado": float(np.sign(Xb - z["cx"])),
            "s0": s0, "giro_in": 4.0 if rot >= 0 else -4.0, "u": u, "k_saida": 0}


# ------------------------------------------------------------------ câmera (recuo em plano fechado)


def _cameras(g, evs):
    W, H = g.W, g.H
    grupos = []
    for e in sorted(evs, key=lambda e: e["inicio"]):
        a, b = float(e["inicio"]) - 0.75, float(e["fim"]) + 1.35
        if grupos and a < grupos[-1]["jb"] + 0.4:
            grupos[-1]["jb"] = max(grupos[-1]["jb"], b)
            grupos[-1]["evs"].append(e)
        else:
            grupos.append({"ja": a, "jb": b, "evs": [e]})
    out = []
    for gr in grupos:
        a = min(float(e["inicio"]) for e in gr["evs"])
        b = max(float(e["fim"]) for e in gr["evs"])
        ts = np.arange(max(0.0, a - 0.75), max(max(0.0, a - 0.75) + 0.05, min(g.duracao, b + 1.35)) + 1e-6, 0.2)
        cx = np.array([g.rosto.em(float(t)) for t in ts], dtype=float)
        fw = (cx[:, 2] - cx[:, 0]) / W
        fh = cx[:, 3] - cx[:, 1]
        fw80 = float(np.percentile(fw, 80))
        s_fw = 1.0 if fw80 < FW_RECUO else FW_ALVO / max(fw80, 1e-3)
        # cabeça alta no quadro (pouca parede acima dela): recua só o bastante para o alto da cabeça
        # descer até TOPO_CAB da altura
        ht = float(np.percentile(cx[:, 1] - CAB * fh, 8))
        s_topo = (1.0 - TOPO_CAB) * H / max(1.0, H - ht)
        s = max(S_MIN, min(1.0, s_fw, s_topo))
        if s > 0.965:
            s = 1.0
        if float(((cx[:, 1] - 0.30 * fh) / H).min()) < -0.01:
            s = 1.0   # cabeça cortada pelo topo do vídeo: recuar mostraria o corte
        out.append({"a": a, "b": b, "s": s, "evs": gr["evs"]})
    return out


def _s_no_tempo(est, t):
    s = 1.0
    dur = est["dur"]
    for gr in est["cams"]:
        if gr["s"] >= 0.9995:
            continue
        ki = 1.0 if gr["a"] - 0.75 <= 0.05 else d.suave(d.mapear(t, gr["a"] - 0.75, gr["a"] - E_ANTES))
        ko = 0.0 if gr["b"] + 1.35 >= dur - 0.05 else d.suave(d.mapear(t, gr["b"] + 0.75, gr["b"] + 1.35))
        s = min(s, 1 - (1 - gr["s"]) * ki * (1 - ko))
    return s


def _redim(arr, w, h):
    if cv2 is not None:
        inter = cv2.INTER_AREA if w < arr.shape[1] * 0.6 else cv2.INTER_LINEAR
        return cv2.resize(arr, (w, h), interpolation=inter)
    modo = "RGBA" if arr.ndim == 3 and arr.shape[2] == 4 else ("RGB" if arr.ndim == 3 else "L")
    return np.asarray(Image.fromarray(arr, modo).resize((w, h), Image.BILINEAR))


def _pena(cache, bw, bh, fw):
    k = ("m08pena", bw, bh, fw)
    if k not in cache:
        y = np.clip((np.arange(bh) + 0.5) / fw, 0, 1)
        x = np.arange(bw) + 0.5
        xl = np.clip(np.minimum(x, bw - x) / fw, 0, 1)
        cache[k] = np.minimum(y[:, None], xl[None, :]).astype(np.float32)
    return cache[k]


def _recuo(c, s):
    """Câmera recuada: o vídeo encolhe (ancorado embaixo) sobre um fundo feito do PRÓPRIO quadro em tela
    cheia, bem desfocado e escurecido (como um editor faz), com pena suave nas bordas do vídeo.
    Devolve (base PIL, info do recuo)."""
    W, H = c.W, c.H
    arr = np.asarray(c.fonte)
    bw, bh = int(round(W * s)), int(round(H * s))
    ox, oy = (W - bw) // 2, H - bh
    grande = _redim(arr, bw, bh)
    # fundo: o quadro inteiro reduzido a W/10, desfocado (sigma ~3 px nessa escala), escurecido e ampliado
    sw, sh = max(16, W // 10), max(16, H // 10)
    peq = _redim(grande, sw, sh)[:, :, :3].astype(np.float32)
    sig = max(1.5, 3.0 * sw / 72.0)
    if cv2 is not None:
        peq = cv2.GaussianBlur(peq, (0, 0), sig, borderType=cv2.BORDER_REFLECT)
    else:
        peq = np.asarray(Image.fromarray(np.clip(peq, 0, 255).astype(np.uint8), "RGB").filter(
            ImageFilter.GaussianBlur(sig)), np.float32)
    peq4 = np.empty((sh, sw, 4), np.uint8)
    peq4[:, :, :3] = np.clip(peq * 0.72, 0, 255)
    peq4[:, :, 3] = 255
    if cv2 is not None:   # bicúbica: ampliar 10x um fundo já desfocado fica liso, sem degraus
        base = Image.fromarray(cv2.resize(peq4, (W, H), interpolation=cv2.INTER_CUBIC), "RGBA")
    else:
        base = Image.fromarray(peq4, "RGBA").resize((W, H), Image.BICUBIC)
    fw = max(2, int(round(0.06 * W)))
    pena = _pena(c.g.cache, bw, bh, fw)
    k = ("m08pena8", bw, bh, fw)
    if k not in c.g.cache:
        c.g.cache[k] = np.round(pena * 255).astype(np.uint8)
    # (grande é um array novo: o alfa dele vira a pena, sem cópia; _pessoa_regiao só usa o RGB)
    g4 = grande if grande.shape[2] == 4 else np.dstack([grande, np.full(grande.shape[:2], 255, np.uint8)])
    g4[:, :, 3] = c.g.cache[k]   # pena suave no alto e nas laterais do vídeo encolhido
    base.alpha_composite(Image.fromarray(g4, "RGBA"), (ox, oy))
    return base, (grande, ox, oy, pena, s)


def _transformar(img, rot, esc):
    """Gira (graus, anti-horário) e escala o recorte já pronto numa só operação."""
    w, h = img.size
    th = math.radians(rot)
    co, si = abs(math.cos(th)) * esc, abs(math.sin(th)) * esc
    nw, nh = max(1, int(math.ceil(w * co + h * si))), max(1, int(math.ceil(w * si + h * co)))
    if cv2 is not None:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), rot, esc)
        M[0, 2] += nw / 2 - w / 2
        M[1, 2] += nh / 2 - h / 2
        pre = np.asarray(img.convert("RGBa"))     # alfa pré-multiplicado: sem franja escura na borda
        out = cv2.warpAffine(pre, M, (nw, nh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(0, 0, 0, 0))
        return Image.fromarray(out, "RGBa").convert("RGBA")
    if abs(rot) > 0.05:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    return img.resize((max(1, int(round(img.width * esc))), max(1, int(round(img.height * esc)))), Image.BICUBIC)


def _pessoa_regiao(c, reg, rec):
    """Camada só com a pessoa dentro de reg=(x0,y0,x1,y1) da tela, tirada do quadro LIMPO."""
    x0, y0, x1, y1 = reg
    W, H = c.W, c.H
    if rec is None:
        if x1 <= x0 or y1 <= y0:
            return None
        img = (c.fonte if c.mascara is None else c.fonte_pessoa).crop(reg)  # borda sem a cor do fundo antigo
        if c.mascara is not None:
            img.putalpha(c.mascara.crop(reg))
        else:
            img.putalpha(_elipse_cabeca(c, reg, 1.0))
        return img, (x0, y0)
    grande, ox, oy, pena, s = rec
    bh, bw = grande.shape[:2]
    x0, y0, x1, y1 = max(x0, ox), max(y0, oy), min(x1, ox + bw), min(y1, H)
    if x1 <= x0 or y1 <= y0:
        return None
    rgb = grande[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    if c.mascara is not None:  # a pessoa vai por cima das folhas: cores da borda sem o fundo antigo
        limpo = c.__dict__.get("_e08_limpo")
        if limpo is None or limpo.shape[:2] != (bh, bw):
            limpo = c.__dict__["_e08_limpo"] = _redim(np.asarray(c.fonte_pessoa), bw, bh)
        rgb = limpo[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    if c.mascara is not None:   # só o pedaço da máscara que interessa, encolhido igual ao vídeo
        m = _mascara_regiao(np.asarray(c.mascara), bw, bh, x0 - ox, y0 - oy, x1 - x0, y1 - y0)
    else:
        m = np.asarray(_elipse_cabeca(c, (x0, y0, x1, y1), s), np.float32)
    a = (m * pena[y0 - oy:y1 - oy, x0 - ox:x1 - ox]).astype(np.uint8)
    cam = np.empty((y1 - y0, x1 - x0, 4), np.uint8)
    cam[:, :, :3] = rgb[:, :, :3]
    cam[:, :, 3] = a
    return Image.fromarray(cam, "RGBA"), (x0, y0)


def _mascara_regiao(mask, bw, bh, gx, gy, w, h):
    """Mesmo resultado de redimensionar a máscara inteira para (bw, bh) e recortar (gx, gy, w, h),
    mas calculando só o recorte (bem mais rápido)."""
    H0, W0 = mask.shape[:2]
    sx, sy = bw / W0, bh / H0
    if cv2 is None:
        return _redim(mask, bw, bh)[gy:gy + h, gx:gx + w].astype(np.float32)
    Mi = np.array([[1 / sx, 0, (gx + 0.5) / sx - 0.5], [0, 1 / sy, (gy + 0.5) / sy - 0.5]], np.float64)
    return cv2.warpAffine(mask, Mi, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                          borderMode=cv2.BORDER_REPLICATE).astype(np.float32)


def _elipse_cabeca(c, reg, s):
    """Quadro sem máscara num vídeo com recorte: protege ao menos a cabeça."""
    W, H = c.W, c.H
    x0, y0, x1, y1 = reg
    rx0, ry0, rx1, ry1 = c.rosto
    fw, fh = rx1 - rx0, ry1 - ry0
    cx = (rx0 + rx1) / 2
    el = (cx - fw * 0.8, ry0 - fh * 0.7, cx + fw * 0.8, ry1 + fh * 0.6)
    el = (W / 2 + (el[0] - W / 2) * s - x0, H + (el[1] - H) * s - y0,
          W / 2 + (el[2] - W / 2) * s - x0, H + (el[3] - H) * s - y0)
    m = Image.new("L", (x1 - x0, y1 - y0), 0)
    ImageDraw.Draw(m).ellipse(el, fill=255)
    return m.filter(ImageFilter.GaussianBlur(max(2, 0.01 * W)))


# ------------------------------------------------------------------ legenda própria (bloco editorial)


def _paginas(palavras, max_car, max_pal=5):
    out = []
    for gr in agrupar(palavras, max_car, 1):
        ps = gr["palavras"]
        partes = [ps[i:i + max_pal] for i in range(0, len(ps), max_pal)]
        for j, pp in enumerate(partes):
            fim = partes[j + 1][0]["inicio"] if j + 1 < len(partes) else gr["fim"]
            out.append({"palavras": pp, "inicio": pp[0]["inicio"], "fim": fim})
    return out


class _Legenda:
    """Bloco claro alinhado à esquerda, Cormorant 700, fio vinho no alto, palavra falada em vinho.
    Fica na base da zona segura; sobe para cima da cabeça só se o rosto descer até ela."""

    def __init__(self, g, perfil):
        W, H = g.W, g.H
        u = _u(W, H)
        self.W, self.H, self.u = W, H, u
        self.fam = perfil.get("fonte", "serif")
        self.peso = int(perfil.get("peso", 700))
        self.tam = int(round(u * float(perfil.get("tamanho", 0.074))))
        self.tam_min = int(round(u * 0.056))
        self.cor = perfil.get("cor", LEG_TINTA)
        self.destaque = perfil.get("destaque", VINHO)
        self.fundo = perfil.get("caixa", LEG_CAIXA) or LEG_CAIXA
        self.maius = bool(perfil.get("maiusculas", False))
        self.paginas = _paginas(g.palavras, int(perfil.get("max_caracteres", 22) or 22), 5)
        self.x = 0.074 * W
        self.larg_max = min(0.80 * W, DIR_TXT * W - self.x)
        self.px, self.pt, self.pb = 0.036 * u, 0.040 * u, 0.030 * u
        f = d.fonte(self.tam, self.peso, self.fam)
        self.cap, desc = _metricas(f)
        self.h = self.pt + self.cap + desc + self.pb
        self.fio_w, self.fio_h = 0.085 * u, max(2, int(round(0.0045 * u)))
        self._med = {}
        self._caixa = {}

    def topo_padrao(self):
        return LEG_BASE * self.H - self.h

    def fixar(self, g, est):
        """Posição de cada página, decidida UMA vez: na base da zona segura (pode tapar o queixo, nunca
        a boca); acima da cabeça só se a BOCA descer até a legenda durante a página. Devolve os retângulos das páginas que subiram
        (as manchetes desviam deles)."""
        H = self.H
        self.ys, obst = [], []
        y0 = self.topo_padrao()
        for i, pg in enumerate(self.paginas):
            ts = np.arange(pg["inicio"] - 0.05, pg["fim"] + 1e-6, 0.1)
            topo, queixo = 1e9, -1e9
            for t in ts:
                sc = _s_no_tempo(est, float(t))
                topo = min(topo, H + (g.rosto.topo_cabeca(float(t)) - H) * sc)
                r = g.rosto.em(float(t))
                boca = r[1] + 0.80 * (r[3] - r[1])
                queixo = max(queixo, H + (boca - H) * sc)
            y = y0
            if queixo > y0 - 0.012 * H and topo - 0.025 * H - self.h >= TOPO_TXT * H:
                y = topo - 0.025 * H - self.h
                cw = self._medidas(i)[4]
                obst.append((pg["inicio"] - 0.1, pg["fim"] + 0.2,
                             (self.x - 0.01 * self.W, y - 0.01 * H, self.x + cw + 0.01 * self.W, y + self.h + 0.012 * H)))
            self.ys.append(y)
        return obst

    def _pagina(self, t):
        for i, pg in enumerate(self.paginas):
            if pg["inicio"] - 0.05 <= t < pg["fim"]:
                return i
        return None

    def _medidas(self, i):
        if i not in self._med:
            txts = [w["texto"].upper() if self.maius else w["texto"] for w in self.paginas[i]["palavras"]]
            tam = self.tam
            while True:
                f = d.fonte(tam, self.peso, self.fam)
                esp = f.getlength(" ")
                ws = [f.getlength(x) for x in txts]
                total = sum(ws) + esp * (len(ws) - 1)
                if total <= self.larg_max - 2 * self.px or tam <= self.tam_min:
                    break
                tam = max(self.tam_min, int(tam * 0.95))
            xs, x = [], 0.0
            for wv in ws:
                xs.append(x)
                x += wv + esp
            caixa_w = int(round(max(total + 2 * self.px, 0.30 * self.u)))
            self._med[i] = (txts, xs, ws, f, caixa_w)
        return self._med[i]

    def _caixa_img(self, w):
        if w not in self._caixa:
            cx = d.painel(w, int(round(self.h)), raio=max(1, int(0.004 * self.u)), fundo=self.fundo)
            self._caixa[w] = d.sombra(cx, raio=0.013 * self.u, opacidade=0.26, desloc=(0, int(0.007 * self.u)))
        return self._caixa[w]

    def desenhar(self, img, t):
        i = self._pagina(t)
        if i is None:
            return
        pg = self.paginas[i]
        txts, xs, ws, f, caixa_w = self._medidas(i)
        ini, fim = pg["inicio"], pg["fim"]
        novo = i == 0 or ini - self.paginas[i - 1]["fim"] > 0.06
        acaba = i == len(self.paginas) - 1 or self.paginas[i + 1]["inicio"] - fim > 0.06
        a = d.saida(d.mapear(t, ini - 0.05, ini + 0.14)) if novo else 1.0
        if acaba:
            a *= 1 - d.entrada(d.mapear(t, fim - 0.14, fim))
        if a <= 0.003:
            return
        k = d.saida(d.mapear(t, ini - 0.05, ini + 0.20))
        y = self.ys[i] if getattr(self, "ys", None) else self.topo_padrao()
        y_c = y + ((1 - k) * 0.010 * self.u if novo else 0.0)
        cx, (dx, dy) = self._caixa_img(caixa_w)
        d.colar_em(img, cx, (self.x + dx, y_c + dy), opacidade=a)
        # fio vinho no alto do bloco (marca editorial da prévia)
        fio = Image.new("RGBA", (int(self.fio_w), self.fio_h), d.cor(VINHO))
        d.colar_em(img, fio, (self.x + self.px, y_c + 0.016 * self.u), opacidade=a)
        # texto assenta a cada página; a palavra que está sendo dita fica em vinho
        j = None
        for jj, w in enumerate(pg["palavras"]):
            if t >= w["inicio"] - 0.03:
                j = jj
        cam = Image.new("RGBA", (caixa_w, int(round(self.h))), (0, 0, 0, 0))
        dr = ImageDraw.Draw(cam)
        base_y = self.pt + self.cap
        for jj, (xx, tx) in enumerate(zip(xs, txts)):
            dr.text((self.px + xx, base_y), tx, font=f, fill=d.cor(self.destaque if jj == j else self.cor),
                    anchor="ls")
        ddy = (1 - k) * 0.014 * self.u
        d.colar_em(img, cam, (self.x, y_c + ddy), opacidade=a * (0.3 + 0.7 * k))


# ------------------------------------------------------------------ recheio: jornal atrás da cabeça


def _recheios(g, colocados, cams):
    """Com recorte: 2 folhas de jornal SEM letras (só colunas) atrás da cabeça, por baixo das manchetes.
    A cabeça passa na frente delas: é o que faz a parede continuar atrás da pessoa."""
    W, H = g.W, g.H
    u = _u(W, H)
    # o jornal de fundo entra com o 1º papel e sai logo depois do último (mesma curva de saída)
    janelas = sorted((l["inicio"] - E_ANTES, l["fim"] + S_PASSO * l["k_saida"] + 0.5, l) for l in colocados)
    segs = []
    for a, b, l in janelas:
        if segs and a < segs[-1]["b"] + 0.5:
            segs[-1]["b"] = max(segs[-1]["b"], b)
            segs[-1]["n"] += 1
        else:
            segs.append({"a": a, "b": b, "s0": l["s0"], "n": 1})
    out = []
    for k, sg in enumerate(segs):
        if sg["n"] < 2:
            continue
        z = _zonas(g, sg["a"], sg["b"], sg["s0"])
        for j, (dxf, dyf, wf, hf, rot) in enumerate(((-0.15, 0.05, 0.46, 0.15, -4.0), (0.16, 0.10, 0.42, 0.14, 5.0))):
            w, h = wf * u, hf * H
            x = min(max(z["cx"] + dxf * W, ESQ_PAPEL * W + w / 2 + 0.02 * W), DIR_PAPEL * W - w / 2 - 0.02 * W)
            y = max(z["ht"] + dyf * H, TOPO_PAPEL * H + h / 2 + 0.02 * H)
            out.append({"a": sg["a"] + 0.12 * j, "b": sg["b"] - 0.1 * j, "X": x, "Y": y, "w": w, "h": h, "rot": rot,
                        "s0": sg["s0"], "chave": ("m08r", k, j), "semente": 900 + 31 * k + j})
    return out


def _recheio_img(g, r):
    if r["chave"] not in g.cache:
        u = _u(g.W, g.H)
        w, h = int(r["w"]), int(r["h"])
        pap = _papel_cortado(w, h, u, r["semente"])
        ov = Image.new("RGBA", pap.size, (0, 0, 0, 0))   # traços numa camada à parte (sem furar o papel)
        dr = ImageDraw.Draw(ov)
        rng = np.random.default_rng(r["semente"])
        pad = 0.03 * u
        # "manchete" em blocos cinza + 3 colunas de texto em traços (nada legível)
        yb = pad
        for frac in (0.82, 0.55):
            dr.rectangle((pad, yb, pad + (w - 2 * pad) * frac, yb + 0.026 * u), fill=d.cor(TINTA, 0.12))
            yb += 0.038 * u
        yb += 0.008 * u
        dr.rectangle((pad, yb, w - pad, yb + max(1, int(0.0024 * u))), fill=d.cor(TINTA, 0.22))
        yb += 0.018 * u
        ncol = 3
        cw = (w - 2 * pad - (ncol - 1) * 0.02 * u) / ncol
        for c in range(ncol):
            x0 = pad + c * (cw + 0.02 * u)
            y = yb
            n = 0
            while y + 0.004 * u < h - pad:
                frac = 1.0 if (n % 6) != 5 else rng.uniform(0.3, 0.7)
                dr.rectangle((x0, y, x0 + cw * frac, y + max(1, int(0.0034 * u)) - 1), fill=d.cor(TINTA, 0.11))
                y += 0.019 * u
                n += 1
        pap.alpha_composite(ov)
        g.cache[r["chave"]] = _girar_com_sombra(pap, r["rot"], u, False)
    return g.cache[r["chave"]]


# ------------------------------------------------------------------ preparar


def preparar(g):
    W, H = g.W, g.H
    mascara = bool(g.tem_mascara)
    est = {"lay": {}, "cams": [], "leg": None, "dur": g.duracao, "recheio": []}
    g.cache["_m08"] = est
    leg = g.plano.get("legenda") or {}
    if leg.get("ativa", True) and g.palavras:
        perfil = dict(INFO["legenda"])
        perfil.update(leg.get("perfil") or {})
        est["leg"] = _Legenda(g, perfil)
    cap_top = est["leg"].topo_padrao() if est["leg"] else LEG_BASE * H - 0.07 * H
    evs = sorted([e for e in g.plano["eventos"] if e.get("tipo") == "manchete" and str(e.get("texto", "")).strip()],
                 key=lambda e: e["inicio"])
    est["cams"] = _cameras(g, evs) if evs else []
    obst = est["leg"].fixar(g, est) if est["leg"] else []
    if not evs:
        return
    s_de = {}
    for gr in est["cams"]:
        for e in gr["evs"]:
            s_de[_chave(e)] = gr["s"]
    colocados = []
    for ordem, e in enumerate(evs):
        s0 = s_de.get(_chave(e), 1.0)
        z = _zonas(g, float(e["inicio"]) - E_ANTES, float(e["fim"]) + 0.85, s0)
        parede = sum(1 for o in evs if abs(float(o["fim"]) - float(e["fim"])) < 0.35)
        lay = _posicionar(g, e, ordem, z, colocados, s0, mascara, cap_top, obst, parede)
        if lay is None:
            continue
        for p in lay.pop("cobertos"):   # o papel novo pousa por cima: o antigo sai da parede
            if p["fim"] > lay["inicio"] + 0.05:
                print(f"Aviso (parede de manchetes): '{p['e']['texto']}' sai em {lay['inicio']:.2f}s, antes do fim "
                      f"{float(p['e']['fim']):.2f}s, para dar lugar a '{lay['e']['texto']}'. Tire uma manchete dessa "
                      f"parede ou encurte os textos.", file=sys.stderr)
            p["fim"] = min(p["fim"], lay["inicio"] + 0.05)
            p["jb"] = p["fim"] + 0.85
        colocados.append(lay)
        est["lay"][lay["chave"]] = lay
    # saída em cascata: papéis que saem juntos (fim parecido) saem um depois do outro
    por_fim = sorted(colocados, key=lambda l: (l["fim"], l["inicio"]))
    grupo, ref = [], None
    for lay in por_fim:
        if ref is None or lay["fim"] - ref > 0.35:
            grupo, ref = [], lay["fim"]
        lay["k_saida"] = min(6, len(grupo))
        grupo.append(lay)
    if mascara:
        est["recheio"] = _recheios(g, colocados, est["cams"])


# ------------------------------------------------------------------ quadro


def _estado(lay, t):
    te = lay["inicio"] - E_ANTES
    ts = lay["fim"] + S_PASSO * lay["k_saida"]
    if t < te or t > ts + S_DUR:
        return None
    ki = d.mapear(t, te, te + E_DUR)
    ko = d.mapear(t, ts, ts + S_DUR)
    op = d.saida(d.mapear(t, te, te + 0.30)) * (1 - d.suave(ko))
    if op <= 0.004:
        return None
    sk = d.saida(ki)
    return {"op": op, "esc": (0.82 + 0.18 * sk) * (1 - 0.04 * d.suave(ko)),
            "dy": lay["u"] * (0.055 * (1 - sk) + 0.03 * d.entrada(ko)),
            "drot": lay["giro_in"] * (1 - sk)}


def quadro(c):
    g = c.g
    est = g.cache.get("_m08")
    if est is None:
        preparar(g)
        est = g.cache["_m08"]
    t, W, H = c.t, c.W, c.H
    u = _u(W, H)
    s = _s_no_tempo(est, t)
    vis = []
    for e in c.eventos:
        if e.get("tipo") != "manchete":
            continue
        lay = est["lay"].get(_chave(e))
        st = _estado(lay, t) if lay else None
        if st:
            vis.append((lay, st))
    vis.sort(key=lambda v: v[0]["ordem"])
    rec = None
    if s < 0.9995:
        base, rec = _recuo(c, s)
    else:
        base = c.fonte
    rech = []
    for r in est.get("recheio", ()):
        if r["a"] <= t <= r["b"]:
            op = d.saida(d.mapear(t, r["a"], r["a"] + 0.35)) * (1 - d.suave(d.mapear(t, r["b"] - 0.4, r["b"])))
            if op > 0.004:
                rech.append((r, op))
    if vis or rech:
        dx = math.sin(2 * math.pi * t / PERIODO) * 0.006 * u   # a parede inteira balança de leve
        colocados = []
        for r, op in rech:
            img = _recheio_img(g, r)
            k = s / r["s0"]
            if abs(k - 1) > 0.003:
                img = _transformar(img, 0.0, k)
            X = W / 2 + (r["X"] - W / 2) * k + dx
            Y = H + (r["Y"] - H) * k
            colocados.append((img, int(round(X - img.width / 2)), int(round(Y - img.height / 2)), op))
        for lay, st in vis:
            img = _cartao(g, lay)
            k = s / lay["s0"]
            esc = st["esc"] * k
            if abs(st["drot"]) > 0.05 or abs(esc - 1) > 0.003:
                img = _transformar(img, st["drot"], esc)
            X = W / 2 + (lay["X"] - W / 2) * k + dx
            Y = H + (lay["Y"] - H) * k + st["dy"] * k
            colocados.append((img, int(round(X - img.width / 2)), int(round(Y - img.height / 2)), st["op"]))
        pessoa = None
        if g.tem_mascara:
            reg = (max(0, min(x for _, x, _, _ in colocados)), max(0, min(y for _, _, y, _ in colocados)),
                   min(W, max(x + im.width for im, x, _, _ in colocados)),
                   min(H, max(y + im.height for im, _, y, _ in colocados)))
            pessoa = _pessoa_regiao(c, reg, rec)   # do quadro limpo, ANTES de colar os papéis
        for img, x, y, op in colocados:
            d.colar_em(base, img, (x, y), opacidade=op)
        if pessoa is not None:
            base.alpha_composite(pessoa[0], dest=pessoa[1])
    if est["leg"] is not None:
        est["leg"].desenhar(base, t)
    return base


# ------------------------------------------------------------------ validação do plano


def validar(plano, duracao):
    p = []
    ms = sorted([e for e in plano["eventos"] if e.get("tipo") == "manchete"], key=lambda e: e["inicio"])
    for e in ms:
        ini = float(e["inicio"])
        tx = " ".join(str(e.get("texto", "")).split())
        if not tx:
            p.append(f"Manchete em {ini:.2f}s sem 'texto'.")
            continue
        if len(tx.split()) > 5 or len(tx) > 34:
            p.append(f"Manchete em {ini:.2f}s longa demais ('{tx}'): use 1 a 5 palavras, até 34 letras.")
        ch = " ".join(str(e.get("chapeu", "") or "").split())
        if ch and (len(ch.split()) > 3 or len(ch) > 16):
            p.append(f"Chapéu da manchete em {ini:.2f}s longo demais (1 a 3 palavras curtas, até 16 letras).")
        lado = str(e.get("lado", "auto") or "auto").strip().lower()
        if _lado(e) == "auto" and lado not in ("auto", ""):
            p.append(f"Manchete em {ini:.2f}s: lado '{e.get('lado')}' não existe (auto, esquerda, direita ou topo).")
        if e.get("marca") and _limpo(str(e["marca"])) not in [_limpo(w) for w in tx.split()]:
            p.append(f"Manchete em {ini:.2f}s: a 'marca' precisa ser uma palavra do texto.")
        dur = float(e["fim"]) - ini
        if dur < 1.5:
            p.append(f"Manchete em {ini:.2f}s fica só {dur:.1f}s na tela: pouco para ler (mínimo 1,5 s).")
        if dur > 15:
            p.append(f"Manchete em {ini:.2f}s fica {dur:.1f}s na tela: longo demais (limpe a parede antes de 12 s).")
    for e in ms:
        t = float(e["inicio"])
        juntas = [o for o in ms if float(o["inicio"]) <= t <= float(o["fim"]) + 0.5]
        if len(juntas) > 6:
            p.append(f"Mais de 6 manchetes na parede ao mesmo tempo perto de {t:.2f}s: limpe a parede antes.")
            break
        escuras = [o for o in juntas if _bool(o.get("escuro"))]
        if len(escuras) > 2:
            p.append(f"Mais de 2 manchetes escuras juntas perto de {t:.2f}s: o papel escuro é só para a mais forte.")
            break
    for a, b in zip(ms, ms[1:]):
        if 0 <= float(b["inicio"]) - float(a["inicio"]) < 0.2:
            p.append(f"Manchetes em {a['inicio']:.2f}s e {b['inicio']:.2f}s entram coladas: deixe ao menos 0,25 s.")
    return p
