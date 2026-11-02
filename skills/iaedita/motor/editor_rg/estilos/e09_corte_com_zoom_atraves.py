"""09 · Corte com zoom através — nas mudanças de assunto a câmera ATRAVESSA o quadro: zoom forte e rápido
no rosto com desfoque radial, um portal circular verde-limão se abre no centro e revela o "próximo plano"
(outro enquadramento do mesmo vídeo, com o título do novo assunto), que chega de perto e assenta.
Entre as passagens a câmera nunca para: avança devagar (zoom contínuo). Não precisa recortar a pessoa.

Linha do tempo (pré-calculada em preparar, só a partir do plano):
  plano 0 | passagem 0 | plano 1 | passagem 1 | plano 2 ...
Cada plano tem enquadramento próprio ("aberto" = vídeo inteiro, "fechado" = mais perto do rosto, com vinheta)
e os títulos que pertencem a ele (eles entram e saem junto com o plano, como na prévia aprovada)."""
from __future__ import annotations

import functools
import math
import re

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from .. import desenho as d

LIMA = "#D4ED80"
PAPEL = "#F8F7F0"

INFO = {
    "id": "09-corte-com-zoom-atraves",
    "nome": "Corte com zoom através",
    "precisa_recorte": False,
    "antes": 0.0,
    "depois": 0.0,
    "legenda": {"peso": 900, "tamanho": 0.085, "cor": "#F8F7F0", "destaque": "#D4ED80", "caixa": "#222729D9",
                "max_caracteres": 12, "max_linhas": 1, "animacao": "subir"},
    "eventos": {
        "passagem": "inicio, fim (0,6-0,8 s; o MEIO cai no início da 1ª palavra do novo assunto), "
                    "titulo (opcional, 1-4 palavras: o nome do novo assunto), titulo_fim (opcional, segundos), "
                    "enquadramento ('auto' alterna, padrão | 'aberto' | 'fechado'), forca (1 leve | 2 padrão | "
                    "3 forte), som ('whoosh') + som_atraso (= metade da duração), som_volume",
        "titulo": "inicio, fim, texto (1-4 palavras): título no plano atual, sem passagem (gancho do começo)",
        "chegada": "inicio 0, fim 0,6: o vídeo abre chegando pelo portal; só no começo, no máximo 1; som",
    },
}

# zoom da cena que sai (A), da cena que chega (B) e força do clarão, por nível
FORCA = {1: (1.7, 1.6, 0.16), 2: (2.6, 2.4, 0.28), 3: (3.4, 3.0, 0.42)}
ESC_FECHADO = ((0.38, 1.16), (0.20, 1.22), (0.0, 1.32))  # largura do rosto (fração de W) -> aproximação
DESLOC_FECHADO = 0.035  # rosto grande: o plano "fechado" também anda para o lado (alternando), fração de W
FOCO_ZOOM = 0.45   # onde a câmera mergulha e o portal abre (fração da altura do rosto): entre os olhos
_PROIBIDO = re.compile(r"[_{}<>|\\]|\b\d{2}-[a-z]", re.I)


# ------------------------------------------------------------------ validação

def _janelas_titulos(eventos, duracao):
    """Títulos com plano dono, início, fim e se são 'levados' pela próxima passagem.
    Função pura do plano: usada pelo validar e pelo preparar."""
    pas = sorted((e for e in eventos if e.get("tipo") == "passagem"), key=lambda e: e["inicio"])
    itens = []
    for j, e in enumerate(pas):
        txt = str(e.get("titulo") or "").strip()
        if not txt:
            continue
        explicito = e.get("titulo_fim") is not None
        fim = float(e["titulo_fim"]) if explicito else e["fim"] + 3.0
        itens.append({"texto": txt, "plano": j + 1, "ini": float(e["inicio"]), "fim": fim,
                      "entrada": "portal", "explicito": explicito})
    for e in eventos:
        if e.get("tipo") != "titulo":
            continue
        k = sum(1 for p in pas if p["inicio"] <= e["inicio"])
        itens.append({"texto": str(e.get("texto", "")).strip(), "plano": k, "ini": float(e["inicio"]),
                      "fim": float(e["fim"]), "entrada": "camera", "explicito": True})
    for it in itens:
        k = it["plano"]
        prox = pas[k] if k < len(pas) else None
        it["levado"] = False
        if prox is not None:
            encosta = it["fim"] > prox["inicio"] - 0.1
            perto = (not it["explicito"]) and prox["inicio"] - it["fim"] < 2.0
            if encosta or perto:  # fica até a próxima passagem e é levado pelo zoom
                it["fim"], it["levado"] = float(prox["fim"]), True
        if not it["levado"]:
            it["fim"] = min(it["fim"], duracao)
    return sorted(itens, key=lambda i: i["ini"])


def _texto_ok(txt, quando):
    p = []
    if not txt:
        p.append(f"Título vazio em {quando:.2f}s.")
    elif len(txt.split()) > 5 or len(txt) > 32:
        p.append(f"Título longo demais em {quando:.2f}s ('{txt}'): use 1 a 4 palavras, até 32 letras.")
    if txt and _PROIBIDO.search(txt):
        p.append(f"Título em {quando:.2f}s parece texto interno ('{txt}'): escreva só palavras do assunto.")
    return p


def _nivel(e):
    try:
        return int(e.get("forca", 2))
    except (TypeError, ValueError):
        return -1


def validar(plano, duracao):
    p = []
    evs = plano["eventos"]
    pas = sorted((e for e in evs if e.get("tipo") == "passagem"), key=lambda e: e["inicio"])
    for e in pas:
        dur = e["fim"] - e["inicio"]
        if dur < 0.4 or dur > 1.3:
            p.append(f"Passagem em {e['inicio']:.2f}s dura {dur:.2f}s: use 0,5 a 1,0 s (o ideal é 0,7 s).")
        if _nivel(e) not in FORCA:
            p.append(f"Passagem em {e['inicio']:.2f}s: 'forca' precisa ser 1, 2 ou 3.")
        if e.get("som") and abs(float(e.get("som_atraso", 0) or 0) - dur / 2) > 0.15:
            p.append(f"Passagem em {e['inicio']:.2f}s: ponha \"som_atraso\": {dur / 2:.2f} para o pico do som "
                     "bater no meio da travessia (no clarão).")
        if e.get("enquadramento", "auto") not in ("auto", "aberto", "fechado"):
            p.append(f"Passagem em {e['inicio']:.2f}s: 'enquadramento' é 'auto', 'aberto' ou 'fechado'.")
        if e.get("titulo") is not None:
            p += _texto_ok(str(e.get("titulo", "")).strip(), e["inicio"])
        if e.get("titulo_fim") is not None and float(e["titulo_fim"]) <= e["fim"] + 0.8:
            p.append(f"Passagem em {e['inicio']:.2f}s: 'titulo_fim' precisa ser pelo menos 0,8 s depois do 'fim'.")
        if e["fim"] > duracao - 0.6:
            p.append(f"Passagem em {e['inicio']:.2f}s cola no fim do vídeo: termine o vídeo limpo, sem passagem.")
    for a, b in zip(pas, pas[1:]):
        if b["inicio"] - a["fim"] < 2.0:
            p.append(f"Passagens muito juntas em {a['inicio']:.2f}s e {b['inicio']:.2f}s: deixe pelo menos 2 s "
                     "de plano entre uma e outra (o ideal é 4 s ou mais).")
    ches = [e for e in evs if e.get("tipo") == "chegada"]
    if len(ches) > 1:
        p.append("Só pode haver 1 'chegada' (a abertura do vídeo).")
    for e in ches:
        if e["inicio"] > 0.5:
            p.append(f"'chegada' em {e['inicio']:.2f}s: ela só existe no começo (inicio 0).")
        if not 0.3 <= e["fim"] - e["inicio"] <= 1.2:
            p.append("'chegada' precisa durar de 0,5 a 0,8 s.")
        if pas and pas[0]["inicio"] < e["fim"] + 2.0:
            p.append("A primeira passagem está colada na 'chegada': deixe pelo menos 2 s entre elas.")
    for e in evs:
        if e.get("tipo") == "titulo":
            p += _texto_ok(str(e.get("texto", "")).strip(), e["inicio"])
            if e["fim"] - e["inicio"] < 1.15:
                p.append(f"Título em {e['inicio']:.2f}s some rápido demais: deixe pelo menos 1,2 s.")
            for q in pas:
                if q["inicio"] - 0.05 < e["inicio"] < q["fim"]:
                    p.append(f"Título em {e['inicio']:.2f}s começa no meio de uma passagem: use o campo "
                             "'titulo' da passagem.")
    jan = _janelas_titulos(evs, duracao)
    for a, b in zip(jan, jan[1:]):
        if a["plano"] == b["plano"] and b["ini"] < a["fim"] - 0.05:
            p.append(f"Dois títulos ao mesmo tempo em {b['ini']:.2f}s: um título por vez (encurte o primeiro "
                     "com 'fim' ou 'titulo_fim').")
    return p


# ------------------------------------------------------------------ linha do tempo (pré-cálculo)

def _caixa(W, H, s, centro):
    """Recorte de câmera igual ao d.enquadrar (centro limitado para nunca mostrar borda vazia)."""
    s = max(1.0, s)
    cw, ch = W / s, H / s
    cx = d.limitar(centro[0] * W, cw / 2, W - cw / 2)
    cy = d.limitar(centro[1] * H, ch / 2, H - ch / 2)
    return (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)


def _curva_deriva(u):
    """Avanço contínuo: começa parado (depois da chegada do plano) e segue em velocidade constante."""
    a = 0.22
    if u <= 0:
        return 0.0
    if u < a:
        return u * u / (2 * a) / (1 - a / 2)
    return (u - a / 2) / (1 - a / 2)


def _esc(P, t):
    u = (t - P["t0"]) / max(0.3, P["t1"] - P["t0"])
    return P["base"] * (1 + P["deriva"] * _curva_deriva(u))


def _rosto_tela(g, P, t):
    x0, y0, x1, y1 = g.rosto.em(t)
    s = _esc(P, t)
    bx, by, _, _ = _caixa(g.W, g.H, s, P["centro"])
    return ((x0 - bx) * s, (y0 - by) * s, (x1 - bx) * s, (y1 - by) * s)


def _centro_rosto(g, P, t):
    """Ponto onde a câmera mergulha e onde o portal se abre: centro do rosto, entre os olhos (não na ponta
    do nariz: o pico do zoom não vira close das narinas)."""
    x0, y0, x1, y1 = _rosto_tela(g, P, t)
    return ((x0 + x1) / 2, y0 + (y1 - y0) * FOCO_ZOOM)


def _raio_rosto(g, P, t):
    """Menor raio do anel (centrado em _centro_rosto) que contorna o rosto inteiro, da testa ao queixo,
    com folga: o anel nunca passa por cima dos olhos nem da boca."""
    x0, y0, x1, y1 = _rosto_tela(g, P, t)
    return 1.12 * math.hypot(0.5 * (x1 - x0), (1.0 - FOCO_ZOOM + 0.13) * (y1 - y0))


def _amostras(t0, t1, passo=0.25):
    n = max(2, int((t1 - t0) / passo) + 1)
    return np.linspace(t0, t1, n)


def _linha(g):
    if "z09" in g.cache:
        return g.cache["z09"]
    W, H, dur = g.W, g.H, g.duracao
    evs = g.plano["eventos"]
    pas = sorted((e for e in evs if e.get("tipo") == "passagem"), key=lambda e: e["inicio"])
    che = next((e for e in evs if e.get("tipo") == "chegada"), None)
    larg = float(np.median(g.rosto.c[:, 2] - g.rosto.c[:, 0]))
    fechado_tela = larg > 0.38
    esc_f = next(v for lim, v in ESC_FECHADO if larg >= lim)
    planos = []
    ant = None
    n_fech = 0
    for k in range(len(pas) + 1):
        t0 = pas[k - 1]["fim"] if k > 0 else (che["fim"] if che else 0.0)
        t1 = pas[k]["inicio"] if k < len(pas) else dur
        vis0 = pas[k - 1]["inicio"] if k > 0 else 0.0
        vis1 = pas[k]["fim"] if k < len(pas) else dur
        enq = pas[k - 1].get("enquadramento", "auto") if k > 0 else "aberto"
        if enq not in ("aberto", "fechado"):
            enq = "aberto" if ant == "fechado" else "fechado" if ant == "aberto" else "aberto"
        ant = enq
        base = 1.0 if enq == "aberto" else esc_f
        deriva = d.limitar(0.006 * (t1 - t0), 0.012, 0.055)
        caixas = np.array([g.rosto.em(t) for t in _amostras(vis0, vis1, 0.2)])
        fx = float(np.mean((caixas[:, 0] + caixas[:, 2]) / 2))
        fcy = float(np.mean(caixas[:, 1] + (caixas[:, 3] - caixas[:, 1]) * 0.45))
        s_max = base * (1 + deriva)
        cx = fx / W
        if enq == "fechado" and fechado_tela:  # rosto grande: o close também muda de ângulo (lado alternado)
            cx += DESLOC_FECHADO * (1 if n_fech % 2 == 0 else -1) * (1 if fx < W / 2 else -1)
            n_fech += 1
        centro = (cx, (fcy + 0.10 * H / s_max) / H)  # rosto um pouco acima do meio, com respiro na cabeça
        planos.append({"t0": t0, "t1": t1, "base": base, "deriva": deriva, "centro": centro,
                       "enq": enq, "titulos": []})
    tl = {"pas": pas, "che": che, "planos": planos, "fechado_tela": fechado_tela}
    for it in _janelas_titulos(evs, dur):
        if not it["texto"] or it["plano"] >= len(planos):
            continue
        _colocar_titulo(g, planos[it["plano"]], it)
        planos[it["plano"]]["titulos"].append(it)
    g.cache["z09"] = tl
    return tl


def preparar(g):
    _linha(g)


# ------------------------------------------------------------------ títulos

def _caber(txt, W, larg, alt):
    """Maior título que cabe: prefere 1 linha (até 0,072 W); se não der, 2 linhas (até 0,062 W)."""
    tmax = int(W * 0.098)
    for linhas_max, tmin in ((1, int(W * 0.072)), (2, int(W * 0.062))):
        if alt < tmin * 1.04 * linhas_max:
            continue
        f, linhas, al = d.ajustar_texto(txt, larg, alt, 800, tam_max=tmax, tam_min=tmin,
                                        max_linhas=linhas_max, entrelinha=1.04)
        if len(linhas) <= linhas_max and al * len(linhas) <= alt + 1 and all(f.getlength(l) <= larg + 1 for l in linhas):
            return f, linhas, al
    return None


def _camada_titulo(g, txt, f, linhas, al):
    chave = ("t09", txt, f.size, len(linhas))
    if chave in g.cache:
        return g.cache[chave]
    W = g.W
    barra_h, folga = max(3, int(W * 0.011)), int(W * 0.022)
    larg = max(f.getlength(l) for l in linhas)
    pad = int(f.size * 0.9)
    cam = Image.new("RGBA", (int(larg + pad * 2), int(al * len(linhas) + barra_h + folga + pad * 2)), (0, 0, 0, 0))
    cam.alpha_composite(d.painel(int(W * 0.11), barra_h, raio=barra_h // 2, fundo=LIMA), (pad, pad))
    d.escrever(cam, (pad, pad + barra_h + folga - f.size * 0.12), linhas, f, PAPEL, al=al)
    a = cam.getchannel("A")
    nuvem = a.filter(ImageFilter.GaussianBlur(f.size * 0.45)).point(lambda v: int(min(255, v * 0.95)))
    curta = a.filter(ImageFilter.GaussianBlur(max(1, f.size * 0.06))).point(lambda v: int(v * 0.55))
    sombra = Image.new("RGBA", cam.size, (8, 10, 12, 255))
    sombra.putalpha(ImageChops.lighter(nuvem.point(lambda v: int(v * 0.5)), curta))
    sombra.alpha_composite(cam)
    g.cache[chave] = (sombra, pad)
    return g.cache[chave]


def _colocar_titulo(g, P, it):
    """Escolhe tamanho e lugar do título: no alto à esquerda (como na prévia) se couber acima dos olhos;
    senão no maior espaço livre entre rosto, legenda e a base segura. Nunca sobre olhos/boca."""
    W, H = g.W, g.H
    ts = _amostras(it["ini"], max(it["ini"] + 0.1, it["fim"]))
    bloqueios = []
    zt, zb = H, 0.0
    for t in ts:
        x0, y0, x1, y1 = _rosto_tela(g, P, t)
        fh = y1 - y0
        zt, zb = min(zt, y0 + fh * 0.12), max(zb, y1 + fh * 0.10)
    bloqueios.append((zt, zb))
    if g.legendas:
        cap = [g.legendas.ocupacao(t) for t in ts]
        cap = [c for c in cap if c]
        if cap:
            bloqueios.append((min(c[0] for c in cap), max(c[1] for c in cap)))
    x, larg = W * 0.074, W * 0.80
    extra = max(3, int(W * 0.011)) + int(W * 0.022)
    topo, base = H * 0.12, H * 0.80
    livres, y = [], topo
    for b0, b1 in sorted(bloqueios):
        if b0 - H * 0.015 > y:
            livres.append((y, b0 - H * 0.015))
        y = max(y, b1 + H * 0.015)
    if base > y:
        livres.append((y, base))
    escolha = None
    for (a0, a1) in livres:  # 1º: o alto da tela (identidade do estilo)
        if abs(a0 - topo) < 1:
            r = _caber(it["texto"], W, larg, a1 - a0 - extra)
            if r:
                escolha = (r, a0)
            break
    if escolha is None:
        melhor = None
        for (a0, a1) in livres:
            r = _caber(it["texto"], W, larg, a1 - a0 - extra)
            if r and (melhor is None or r[0].size > melhor[0][0].size):
                alt = r[2] * len(r[1]) + extra
                melhor = (r, a0 + (a1 - a0 - alt) * 0.3)
        escolha = melhor
    if escolha is None:  # sem espaço livre: tamanho mínimo, no alto
        f = d.fonte(int(W * 0.062), 800)
        escolha = ((f, d.quebrar(it["texto"], f, larg, 2), f.size * 1.04), topo)
    (f, linhas, al), y = escolha
    cam, pad = _camada_titulo(g, it["texto"], f, linhas, al)
    it.update({"camada": cam, "xy": (x - pad, y - pad)})


# ------------------------------------------------------------------ títulos na tela

def _estado_titulo(it, t, H):
    """Escala, opacidade e deslocamento do título em t (entrada e saída com curvas)."""
    esc, op, dy = 1.0, 1.0, 0.0
    if it["entrada"] == "camera":  # chega da câmera: grande e transparente -> assenta
        k = d.saida(d.mapear(t, it["ini"], it["ini"] + 0.45))
        esc *= 1 + 0.45 * (1 - k)
        op *= d.suave(d.mapear(t, it["ini"], it["ini"] + 0.22))
    if not it["levado"]:  # sai sozinho (sobe um pouco e some); se for levado, sai com o zoom da passagem
        q = d.entrada(d.mapear(t, it["fim"] - 0.32, it["fim"]))
        op *= 1 - q
        esc *= 1 - 0.04 * q
        dy = -H * 0.008 * q
    return esc, op, dy


def _colar_rgb(base, cam, centro, escala, op):
    """Cola a camada RGBA num quadro RGB (centro, escala, opacidade), redimensionando só a parte visível."""
    if op <= 0.01 or escala <= 0.01:
        return
    w, h = cam.size
    if abs(escala - 1) < 0.002:
        xi, yi = int(round(centro[0] - w / 2)), int(round(centro[1] - h / 2))
        cx0, cy0 = max(0, -xi), max(0, -yi)
        cx1, cy1 = min(w, base.width - xi), min(h, base.height - yi)
        if cx1 - cx0 < 2 or cy1 - cy0 < 2:
            return
        peca, pos = cam.crop((cx0, cy0, cx1, cy1)), (xi + cx0, yi + cy0)
    else:
        nw, nh = w * escala, h * escala
        x0, y0 = centro[0] - nw / 2, centro[1] - nh / 2
        vx0, vy0 = max(0, int(math.floor(x0))), max(0, int(math.floor(y0)))
        vx1, vy1 = min(base.width, int(math.ceil(x0 + nw))), min(base.height, int(math.ceil(y0 + nh)))
        if vx1 - vx0 < 2 or vy1 - vy0 < 2:
            return
        caixa = (max(0.0, (vx0 - x0) / escala), max(0.0, (vy0 - y0) / escala),
                 min(float(w), (vx1 - x0) / escala), min(float(h), (vy1 - y0) / escala))
        peca, pos = cam.resize((vx1 - vx0, vy1 - vy0), Image.BICUBIC, box=caixa), (vx0, vy0)
    a = peca.getchannel("A")
    if op < 0.997:
        a = a.point(lambda v: int(v * op))
    base.paste(peca.convert("RGB"), pos, a)


def _titulos(img, P, t, r, z, foco, H):
    """Títulos do plano P (com o zoom extra z em torno de foco, na resolução r)."""
    for it in P["titulos"]:
        if not (it["ini"] <= t <= it["fim"]):
            continue
        esc, op, dy = _estado_titulo(it, t, H)
        cam = it["camada"]
        x, y = it["xy"]
        cx, cy = x + cam.width / 2, y + cam.height / 2 + dy
        if z > 1.0005:
            cx, cy = foco[0] + (cx - foco[0]) * z, foco[1] + (cy - foco[1]) * z
        _colar_rgb(img, cam, (cx * r, cy * r), esc * z * r, op)


# ------------------------------------------------------------------ planos e câmera

class _Fonte:
    """Quadro original em RGB (e em meia resolução, sob demanda): redimensionar RGB custa metade do RGBA."""

    def __init__(self, c):
        self.rgb = c.fonte.convert("RGB")
        self._meia = self._quarto = None

    def meia(self):
        if self._meia is None:
            self._meia = self.rgb.reduce(2)
        return self._meia

    def quarto(self):
        if self._quarto is None:
            self._quarto = self.meia().reduce(2)
        return self._quarto


@functools.lru_cache(maxsize=4)
def _vinheta_rgb(w, h):
    """Vinheta do plano 'fechado' como multiplicação (mesmo visual de d.vinheta(img, 0.30), mais rápida)."""
    y, x = np.ogrid[0:h, 0:w]
    dd = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2)
    a = np.clip((dd - 0.55) / 0.85, 0, 1) ** 1.6 * 0.30
    v = ((1 - a) * 255 + 0.5).astype(np.uint8)
    return Image.fromarray(np.repeat(v[:, :, None], 3, axis=2), "RGB")


@functools.lru_cache(maxsize=1)
def _tabela_fechado():
    """Plano 'fechado' com outra cor: contraste +6% e tom levemente frio (238, 246, 255)."""
    tab = []
    for tinta in (238, 246, 255):
        for v in range(256):
            u = 128 + (v - 128) * 1.06
            tab.append(int(d.limitar(round(u * tinta / 255), 0, 255)))
    return tab


@functools.lru_cache(maxsize=8)
def _solido(w, h, cor):
    return Image.new("RGB", (w, h), d.cor(cor)[:3])


def _caixa_zoom(W, H, z, cx, cy):
    """Zoom de câmera com o ponto (cx, cy) parado na tela."""
    z = max(1.0, z)
    return (cx - cx / z, cy - cy / z, cx + (W - cx) / z, cy + (H - cy) / z)


def _render(fonte, g, P, t, r=1.0, z=1.0, foco=None):
    """Plano P em t: enquadramento + avanço contínuo + vinheta + títulos, com zoom extra z em torno de foco
    (pixels de tela), na resolução r (1 = cheia, 0.5 = metade). Um único redimensionamento. Devolve RGB."""
    W, H = g.W, g.H
    bx0, by0, bx1, by1 = _caixa(W, H, _esc(P, t), P["centro"])
    k = (bx1 - bx0) / W
    if z > 1.0005:
        v = _caixa_zoom(W, H, z, foco[0], foco[1])
    else:
        z, v = 1.0, (0.0, 0.0, float(W), float(H))
    caixa = (bx0 + v[0] * k, by0 + v[1] * k, bx0 + v[2] * k, by0 + v[3] * k)
    ow, oh = int(round(W * r)), int(round(H * r))
    amp = ow / max(1.0, caixa[2] - caixa[0])  # pixels de saída por pixel do original
    if r < 1 and amp <= 0.375:  # recorte grande em saída pequena: parte do quadro já reduzido (rápido)
        src, caixa, filtro = fonte.quarto(), tuple(q / 4 for q in caixa), Image.BILINEAR
    elif r < 1 and amp <= 0.75:
        src, caixa, filtro = fonte.meia(), tuple(q / 2 for q in caixa), Image.BILINEAR
    else:
        src, filtro = fonte.rgb, (Image.BICUBIC if r >= 1 else Image.BILINEAR)
    if src.size == (ow, oh) and max(abs(caixa[0]), abs(caixa[1]), abs(caixa[2] - ow), abs(caixa[3] - oh)) < 0.02:
        img = src.copy()
    else:
        img = src.resize((ow, oh), filtro, box=caixa)
    if P["enq"] == "fechado":
        img = ImageChops.multiply(img.point(_tabela_fechado()), _vinheta_rgb(ow, oh))
    _titulos(img, P, t, r, z, foco, H)
    return img


def _passes(espalha, w, h):
    """Quantas dobras de desfoque radial (cada dobra dobra as cópias: 2, 4, 8, 16)."""
    alcance = espalha * math.hypot(w, h) * 0.5  # deslocamento do borrão perto dos cantos (px)
    if alcance < 1.5:
        return 0
    return int(d.limitar(math.ceil(math.log2(alcance / 4.0)), 1, 4))


def _borrar(img, foco, espalha, n, desfoque):
    """Desfoque radial (zoom) em torno de foco: média de 2^n cópias em escalas vizinhas + desfoque leve."""
    w, h = img.size
    for k in range(n):
        f = math.exp(espalha / 2 ** (k + 1))
        img = Image.blend(img, img.resize((w, h), Image.BILINEAR, box=_caixa_zoom(w, h, f, foco[0], foco[1])), 0.5)
    if desfoque >= 0.5:
        img = img.filter(ImageFilter.GaussianBlur(desfoque))
    return img


@functools.lru_cache(maxsize=2)
def _campo(gw, gh):
    """Distâncias (em 1/4 de pixel) até o centro de uma grade 2x maior: um recorte dela dá as distâncias
    até qualquer centro, sem calcular raiz quadrada a cada quadro."""
    y = np.arange(2 * gh, dtype=np.float32)[:, None] + 0.5 - gh
    x = np.arange(2 * gw, dtype=np.float32)[None, :] + 0.5 - gw
    return np.round(np.sqrt(x * x + y * y) * 4).astype(np.uint16)


def _vista(gw, gh, cx, cy):
    campo = _campo(gw, gh)
    ox = int(d.limitar(round(gw - cx), 0, gw))
    oy = int(d.limitar(round(gh - cy), 0, gh))
    return campo[oy:oy + gh, ox:ox + gw], int(campo[0, 0]) + 2


def _cena(fonte, g, t, camadas, centro, raio, op_anel, clarao, op_portal=1.0):
    """Monta um quadro de travessia. camadas = [(plano, zoom, foco, espalha, desfoque_px)]; com duas, a 2ª
    aparece dentro do portal (círculo de 'raio' em 'centro', com anel verde-limão). Devolve RGB cheio."""
    W, H = g.W, g.H
    diag = math.hypot(W, H)
    # cada camada na menor resolução que o borrão NO ROSTO esconde (o rosto fica perto do centro do zoom,
    # onde o desfoque radial é pequeno): 1/4 dos pixels a cada degrau
    res = []
    for (_, _, _, es, dz) in camadas:
        borrao = max(dz, es * diag * 0.08)
        res.append(1.0 if borrao < 1.5 else 0.5 if borrao < 8.0 else 0.25)
    r = 1.0 if min(res) >= 1 else 0.5  # resolução da montagem (portal e anel nunca abaixo da metade)
    ow, oh = int(round(W * r)), int(round(H * r))
    imgs = []
    for (P, z, foco, es, dz), ri in zip(camadas, res):
        wi, hi = int(round(W * ri)), int(round(H * ri))
        n = _passes(es, wi, hi) if ri < 1 else 0
        pre = math.exp(-es * (1 - 2 ** -n) / 2) if n else 1.0  # centra as cópias no zoom pedido
        im = _render(fonte, g, P, t, ri, max(1.0, z * pre), foco)
        if ri < 1:
            passo = es * math.hypot(wi, hi) * 0.5 / 2 ** n if n else 0.0
            im = _borrar(im, (foco[0] * ri, foco[1] * ri), es, n, max(dz * ri, passo * 0.35))
        if im.size != (ow, oh):
            im = im.resize((ow, oh), Image.BILINEAR)
        imgs.append(im)
    out = imgs[0]
    gw, gh = int(round(W * 0.5)), int(round(H * 0.5))
    vista, nq = _vista(gw, gh, centro[0] * 0.5, centro[1] * 0.5)
    q = np.arange(nq, dtype=np.float32) / 4.0
    rr = raio * 0.5

    def mascara(lut):
        m = Image.fromarray(np.take(lut, vista), "L")
        return m if r < 1 else m.resize((W, H), Image.BILINEAR)

    if len(imgs) == 2 and op_portal > 0.01:
        lut = (np.clip(rr - q + 0.5, 0, 1) * (255 * min(1.0, op_portal))).astype(np.uint8)
        out = Image.composite(imgs[1], out, mascara(lut))
    if op_anel > 0.02 and rr > 0.5:
        delta = np.abs(q - rr)
        nucleo = np.clip(W * 0.026 / 4 - delta + 0.5, 0, 1)
        halo = np.exp(-(delta / (W * 0.055 / 2)) ** 2) * 0.5
        lut = (np.maximum(nucleo, halo) * (255 * min(1.0, op_anel))).astype(np.uint8)
        if lut.max() > 2:
            out = Image.composite(_solido(out.width, out.height, LIMA), out, mascara(lut))
    if clarao > 0.01:
        out = Image.blend(out, _solido(out.width, out.height, "#FFFEF6"), min(1.0, clarao))
    if r < 1:
        out = out.resize((W, H), Image.BILINEAR)
    return out


def _espalha(lnz, t, fps):
    """Quanto o zoom (em escala log) anda durante meio quadro: o tamanho do rastro do movimento."""
    dt = 0.5 / max(1.0, fps)
    return min(0.30, abs(lnz(t + dt) - lnz(t - dt)))


def _forca(e, tl):
    za, zb, fl = FORCA.get(_nivel(e), FORCA[2])
    if tl["fechado_tela"]:  # rosto enorme: atravessa com um pouco menos de zoom
        za, zb = 1 + (za - 1) * 0.8, 1 + (zb - 1) * 0.85
    return za, zb, fl


def _canto(W, H, x, y):
    return max(math.hypot(px - x, py - y) for px in (0, W) for py in (0, H))


def _passagem(c, fonte, tl, j, t):
    g, W, H = c.g, c.W, c.H
    e = tl["pas"][j]
    A, B = tl["planos"][j], tl["planos"][j + 1]
    a, b = e["inicio"], e["fim"]
    za, zb, fl = _forca(e, tl)

    def prog(tt):
        return d.suave(d.mapear(tt, a, b))

    def lnza(tt):  # a cena que sai mergulha no rosto (pico no meio)
        return math.log(1 + math.sin(prog(tt) * math.pi) * (za - 1))

    def lnzb(tt):  # a cena que chega vem de muito perto e assenta
        return math.log(1 + (1 - prog(tt)) * (zb - 1))

    p = prog(t)
    onda = math.sin(p * math.pi)
    ca, cb = _centro_rosto(g, A, t), _centro_rosto(g, B, t)  # focos do mergulho (parados na tela)
    zA, zB = math.exp(lnza(t)), math.exp(lnzb(t))
    ccx, ccy = d.lerp(ca[0], cb[0], p), d.lerp(ca[1], cb[1], p)
    canto = _canto(W, H, ccx, ccy)
    # o anel nasce JÁ contornando o rosto inteiro (como ele se vê na tela, com o zoom) e se abre para fora:
    # nunca um alvo pequeno sobre nariz/boca
    contorno = d.lerp(_raio_rosto(g, A, t) * zA, _raio_rosto(g, B, t) * zB, p)
    raio = max(p * canto * 1.18, contorno)
    op_anel = min(1.0, onda * 2.4)
    op_portal = d.suave(d.mapear(p, 0.12, 0.5))  # o outro plano aparece dentro do anel aos poucos
    camadas = []
    if raio < canto + 2 or op_portal < 0.99:
        camadas.append((A, zA, ca, _espalha(lnza, t, g.fps), onda * W * 0.0046))
    if raio > 1 and op_portal > 0.01:
        camadas.append((B, zB, cb, _espalha(lnzb, t, g.fps), onda * W * 0.0028))
    pico = a + (b - a) * 0.5
    clarao = fl * math.exp(-((t - pico) / (0.035 if t < pico else 0.075)) ** 2)
    return _cena(fonte, g, t, camadas, (ccx, ccy), raio, op_anel, clarao, op_portal)


def _chegada(c, fonte, tl, t):
    g, W, H = c.g, c.W, c.H
    e = tl["che"]
    P = tl["planos"][0]
    a, b = e["inicio"], e["fim"]
    zc = 2.2 if not tl["fechado_tela"] else 1.9

    def chega(tt):  # sai do portal em velocidade e freia forte (ease-out de 5º grau): nítido antes da metade
        return 1 - (1 - d.mapear(tt, a, b)) ** 5

    def lnz(tt):
        return math.log(1 + (1 - chega(tt)) * (zc - 1))

    lin = d.mapear(t, a, b)
    p = chega(t)
    foco = _centro_rosto(g, P, t)
    z = math.exp(lnz(t))
    raio = max(d.lerp(0.25, 1.2, d.saida(lin)) * _canto(W, H, foco[0], foco[1]), _raio_rosto(g, P, t) * z)
    clarao = 0.30 * (1 - d.saida(d.mapear(t, a, a + (b - a) * 0.6)))
    op_anel = (1 - p) * 0.95
    camada = (P, z, foco, _espalha(lnz, t, g.fps), (1 - p) ** 2 * W * 0.004)
    return _cena(fonte, g, t, [camada], foco, raio, op_anel, clarao)


# ------------------------------------------------------------------ quadro

def quadro(c):
    tl = _linha(c.g)
    fonte = _Fonte(c)
    t = c.t
    che = tl["che"]
    if che is not None and che["inicio"] <= t < che["fim"]:
        return _chegada(c, fonte, tl, t).convert("RGBA")
    k = 0
    for j, e in enumerate(tl["pas"]):
        if e["inicio"] <= t < e["fim"]:
            return _passagem(c, fonte, tl, j, t).convert("RGBA")
        if e["fim"] <= t:
            k = j + 1
    return _render(fonte, c.g, tl["planos"][k], t).convert("RGBA")
