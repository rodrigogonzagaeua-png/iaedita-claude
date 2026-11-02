"""20 · HUD Glass — painéis de VIDRO FOSCO (desfocam o cenário atrás) com ícone verde-claro e título,
flutuando ACIMA DA CABEÇA, ligados à pessoa por linhas finas de HUD. Feito para plano fechado.
Não precisa recortar a pessoa.

Como cria espaço no plano fechado: quando a cabeça está alta demais para os painéis caberem acima dela,
a câmera "desce" com curva suave (o vídeo inteiro desliza para baixo) e o espaço aberto no topo vira uma
continuação desfocada e escurecida do próprio cenário. Os painéis ficam nesse espaço; a câmera volta quando
o último painel do grupo sai. O deslocamento é limitado para a boca nunca descer até a legenda.

Camadas (de trás para a frente): vídeo deslocado + extensão desfocada → mira (cantos em volta do rosto) →
linhas de chamada → painéis de vidro (sombra, vidro, conteúdo, reflexo) → (legenda do motor).
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from .. import desenho as d

ACENTO = "#D4ED80"
TEXTO = "#FFFFFF"

INFO = {
    "id": "20-hud-glass",
    "nome": "HUD Glass",
    "precisa_recorte": False,
    "antes": 0.7,
    "depois": 0.9,
    "legenda": {"peso": 760, "tamanho": 0.05, "cor": "#FFFFFF", "destaque": ACENTO, "caixa": "#0E1D23C8",
                "max_caracteres": 16, "max_linhas": 1, "y_fixo": 0.745, "animacao": "subir"},
    "eventos": {
        "painel": "inicio, fim (2-6 s), texto (título curto, 2 a 4 palavras), detalhe (opcional, de preferência "
                  "só no painel da esquerda: até ~18 letras em verde, ex. um número ou complemento), icone ('olho' | 'mira' | 'check' | 'raio' | 'grafico' | "
                  "'dinheiro' | 'coracao' | 'estrela' | 'alvo' | 'play' | 'seta_cima'), "
                  "lado ('auto' padrão | 'esquerda' = painel largo | 'direita' = painel alto), som",
        "chamada": "inicio, fim (1-3 s), texto (1 a 3 palavras ou um número): etiqueta de vidro em pílula "
                   "acima da cabeça, com linha até a pessoa. Não usar ao mesmo tempo que um painel. som",
        "mira": "inicio, fim (0.8-2.5 s): cantos de HUD travam em volta do rosto (foco). som",
    },
}

ICONES_MOTOR = {"check", "x", "seta_cima", "seta_baixo", "seta_dir", "play", "estrela", "raio", "alvo",
                "grafico", "dinheiro", "coracao", "ponto"}


# ------------------------------------------------------------------ geometria (frações de W/H)

def _geo(W, H):
    U = W
    return {
        "U": U,
        "largo_x": 0.065 * W, "largo_w": 0.50 * U, "largo_y": 0.125 * H,
        "alto_x": 0.585 * W, "alto_w": 0.285 * U, "alto_y": 0.112 * H,
        "raio": 0.031 * U,
        "chamada_y": 0.125 * H, "chamada_h": 0.098 * U,
        "folga_testa": 0.012 * H,
        "dy_max": 0.20 * H,
        "dy_min": 0.025 * H,  # descida menor que isso não vale a faixa desfocada no topo
    }


# Tamanhos mínimos de texto (fração da largura). O painel pode ser reduzido até 0,8x no plano bem
# fechado; 0,044 x 0,8 = 3,5% da largura, que é o piso da regra de legibilidade.
TAM_MIN = 0.044
ESC_MIN = 0.8
# largura útil do texto em cada painel (fração da largura): largo = 0,50 - 2x0,042; alto = 0,285 - 2x0,036
UTIL = {"esquerda": 0.416, "direita": 0.213}
DETALHE_MAX_LETRAS = 22


def _ajustar(txt, larg, alt, peso, tam_max, tam_min, max_linhas, entrelinha=1.08):
    """Como d.ajustar_texto, mas NUNCA devolve linha mais larga que 'larg' (nada sai cortado pela borda).
    Se não couber no máximo de linhas, quebra em mais linhas (o painel cresce); se uma palavra sozinha
    for mais larga que o painel, diminui a letra só o necessário (último recurso — validar() avisa)."""
    f, linhas, al = d.ajustar_texto(txt, larg, alt, peso, tam_max=tam_max, tam_min=tam_min,
                                    max_linhas=max_linhas, entrelinha=entrelinha)
    if all(f.getlength(l) <= larg for l in linhas):
        return f, linhas, al
    tam = int(tam_min)
    while True:
        f = d.fonte(tam, peso)
        linhas = d.quebrar(txt, f, larg, 99)
        if all(f.getlength(l) <= larg for l in linhas) or tam <= 10:
            return f, linhas, tam * entrelinha
        tam -= 1


# ------------------------------------------------------------------ plano: lados e grupos

def _lados(eventos):
    """Decide o lado de cada painel 'auto': o primeiro vai à esquerda (largo); quem entra com outro
    já na tela vai ao lado livre. Determinístico (só depende do plano)."""
    pain = sorted([e for e in eventos if e.get("tipo") == "painel"], key=lambda e: e["inicio"])
    res = []
    for i, e in enumerate(pain):
        lado = str(e.get("lado", "auto")).lower()
        if lado not in ("esquerda", "direita"):
            ocupados = {res[j][1] for j in range(i) if res[j][0]["fim"] + 0.35 > e["inicio"]}
            lado = "esquerda" if "esquerda" not in ocupados else "direita"
        res.append((e, lado))
    return res


def validar(plano, duracao):
    p = []
    evs = plano.get("eventos", [])
    pares = _lados(evs)
    for i, (a, la) in enumerate(pares):
        n = len(str(a.get("texto", "")).split())
        if n == 0:
            p.append(f"Painel em {a['inicio']:.2f}s sem texto.")
        if n > 5:
            p.append(f"Painel em {a['inicio']:.2f}s com texto longo demais ({n} palavras; máx. 4).")
        dur = a["fim"] - a["inicio"]
        if dur < 1.4:
            p.append(f"Painel em {a['inicio']:.2f}s dura só {dur:.1f}s (mínimo 1,5 s para dar tempo de ler).")
        if dur > 7.5:
            p.append(f"Painel em {a['inicio']:.2f}s dura {dur:.1f}s (máximo ~6 s).")
        ic = str(a.get("icone", "")).lower()
        if ic and ic not in ICONES_MOTOR | {"olho", "mira"}:
            p.append(f"Painel em {a['inicio']:.2f}s: ícone '{ic}' não existe.")
        # medidas em 1080 de largura (tudo é proporcional)
        util = UTIL[la] * 1080
        ft = d.fonte(int((0.045 if la == "esquerda" else TAM_MIN) * 1080), 700)
        longa = [w for w in str(a.get("texto", "")).split() if ft.getlength(w) > util]
        if longa:
            p.append(f"Painel da {la.upper()} em {a['inicio']:.2f}s: a palavra '{longa[0]}' é longa demais para "
                     f"esse painel. " + ("Use palavras de até 8 letras no painel da direita, ou deixe esse texto "
                                         "para um painel que fique sozinho (vai para a esquerda)."
                                         if la == "direita" else "Use uma palavra mais curta."))
        det = " ".join(str(a.get("detalhe", "")).split())
        if det:
            fd = d.fonte(int(TAM_MIN * 1080), 700)
            lin = d.quebrar(det, fd, util, 99)
            if la == "direita" and (len(lin) > 1 or fd.getlength(det) > util):
                p.append(f"Detalhe do painel da DIREITA em {a['inicio']:.2f}s longo demais ('{det}'): o painel "
                         "da direita é estreito — tire o detalhe ou use só um número curto (até 8 letras).")
            elif la == "esquerda" and (len(det) > DETALHE_MAX_LETRAS or len(lin) > 2
                                       or any(fd.getlength(l) > util for l in lin)):
                p.append(f"Detalhe do painel em {a['inicio']:.2f}s longo demais ('{det}'): use até ~18 letras "
                         "(2 a 4 palavras curtas).")
        for b, lb in pares[i + 1:]:
            if b["inicio"] < a["fim"] - 0.01 and la == lb:
                p.append(f"Dois painéis do mesmo lado ({la}) ao mesmo tempo em {b['inicio']:.2f}s.")
    for e in evs:
        if e.get("tipo") == "chamada":
            txt = str(e.get("texto", ""))
            if not txt.strip() or len(txt.split()) > 3 or len(txt) > 22:
                p.append(f"Chamada em {e['inicio']:.2f}s: use 1 a 3 palavras curtas (até 22 letras).")
            for a, _ in pares:
                if a["inicio"] < e["fim"] + 0.2 and e["inicio"] < a["fim"] + 0.2:
                    p.append(f"Chamada em {e['inicio']:.2f}s ao mesmo tempo que um painel: use um ou outro.")
                    break
    for t in sorted({round(e["inicio"], 2) for e in evs if e.get("tipo") == "painel"}):
        n = sum(1 for a, _ in pares if a["inicio"] <= t + 0.01 < a["fim"])
        if n > 2:
            p.append(f"Mais de 2 painéis ao mesmo tempo em {t:.2f}s.")
    # mira logo depois de painel/chamada: a câmera ainda está voltando e o rosto desliza sob os cantos
    ocup = [e for e in evs if e.get("tipo") in ("painel", "chamada")]
    for m in (e for e in evs if e.get("tipo") == "mira"):
        for e in ocup:
            if e["inicio"] < m["inicio"] and 0 <= m["inicio"] - e["fim"] < 1.0:
                p.append(f"Mira em {m['inicio']:.2f}s começa logo depois de um painel/chamada (fim em "
                         f"{e['fim']:.2f}s): deixe pelo menos 1 s entre o fim do painel e a mira.")
                break
    return p


# ------------------------------------------------------------------ pré-desenho

def _cantos_icone(tam, cor_ic):
    """Os 4 cantinhos de HUD em volta do ícone do painel largo (como o 'olho' da prévia)."""
    ss = 4
    S = int(tam * ss)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    c = d.cor(cor_ic)
    e2 = max(2, int(max(2, int(S * 0.034)) * 0.8))
    ca = tuple(c[:3]) + (int(c[3] * 0.75),)
    L, m = S * 0.16, S * 0.04
    for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        x = m if sx == 0 else S - m
        y = m if sy == 0 else S - m
        dx = L if sx == 0 else -L
        dy = L if sy == 0 else -L
        dr.line([(x, y + dy), (x, y), (x + dx, y)], fill=ca, width=e2)
    return im.resize((int(tam), int(tam)), Image.LANCZOS)


def _ss_icone(nome, tam, cor_ic, moldura=False):
    """Ícones próprios do HUD (olho com cantos, mira); os demais vêm do motor.
    moldura=True (painel largo): qualquer ícone fica dentro dos 4 cantinhos de HUD."""
    if moldura and nome != "olho":
        base = _cantos_icone(tam, cor_ic)
        dentro = int(tam * 0.66)
        ic = _ss_icone(nome, dentro, cor_ic)
        base.alpha_composite(ic, ((int(tam) - ic.width) // 2, (int(tam) - ic.height) // 2))
        return base
    ss = 4
    S = int(tam * ss)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    c = d.cor(cor_ic)
    e = max(2, int(S * 0.034))
    if nome == "olho":
        cx, cy = S / 2, S / 2
        w2, h2 = S * 0.42, S * 0.24
        pts_c = [(cx - w2 + 2 * w2 * u / 40, cy - h2 * math.sin(math.pi * u / 40)) for u in range(41)]
        pts_b = [(cx - w2 + 2 * w2 * u / 40, cy + h2 * math.sin(math.pi * u / 40)) for u in range(41)]
        dr.line(pts_c, fill=c, width=e, joint="curve")
        dr.line(pts_b, fill=c, width=e, joint="curve")
        r = S * 0.135
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=e)
        r = S * 0.045
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
        ca = tuple(c[:3]) + (int(c[3] * 0.75),)
        L, m = S * 0.16, S * 0.04
        e2 = max(2, int(e * 0.8))
        for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            x = m if sx == 0 else S - m
            y = m if sy == 0 else S - m
            dx = L if sx == 0 else -L
            dy = L if sy == 0 else -L
            dr.line([(x, y + dy), (x, y), (x + dx, y)], fill=ca, width=e2)
    elif nome == "mira":
        cx = cy = S / 2
        r = S * 0.24
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=e)
        for a0, a1 in (((cx, S * 0.04), (cx, cy - r * 1.0)), ((cx, S * 0.96), (cx, cy + r)),
                       ((S * 0.04, cy), (cx - r, cy)), ((S * 0.96, cy), (cx + r, cy))):
            dr.line([a0, a1], fill=c, width=e)
        r = S * 0.07
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    else:
        return d.icone(nome if nome in ICONES_MOTOR else "ponto", int(tam), cor_ic, espessura=0.09)
    return im.resize((int(tam), int(tam)), Image.LANCZOS)


def _gradiente_tinta(w, h, paradas, angulo):
    """Gradiente linear branco com alfa variável (como o CSS da prévia)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    a = math.radians(angulo)
    proj = x * math.sin(a) - y * math.cos(a)
    proj = (proj - proj.min()) / max(1e-6, proj.max() - proj.min())
    xs = [p for p, _ in paradas]
    al = np.interp(proj, xs, [v for _, v in paradas])
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 0] = 236
    arr[..., 1] = 248
    arr[..., 2] = 252
    arr[..., 3] = (al * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def _sombra_painel(w, h, raio, U):
    """Só a sombra (sem o painel), pré-desfocada em resolução baixa."""
    m = int(0.075 * U)
    f = 4
    W2, H2 = (w + 2 * m) // f, (h + 2 * m) // f
    s = Image.new("L", (W2, H2), 0)
    ImageDraw.Draw(s).rounded_rectangle((m // f, (m + int(0.02 * U)) // f, (m + w) // f, (m + h + int(0.02 * U)) // f),
                                        radius=max(1, raio // f), fill=int(255 * 0.34))
    s = s.filter(ImageFilter.GaussianBlur(0.045 * U / f)).resize((w + 2 * m, h + 2 * m), Image.BILINEAR)
    out = Image.new("RGBA", s.size, (3, 16, 21, 255))
    out.putalpha(s)
    return out, m


def _conteudo(g, e, lado):
    """Camada do conteúdo do painel (borda, ícone, título, cantos) + medidas. Em cache."""
    W, H = g.W, g.H
    G = _geo(W, H)
    U = G["U"]
    texto = " ".join(str(e.get("texto", "")).split())
    detalhe = " ".join(str(e.get("detalhe", "")).split())
    icone = str(e.get("icone", "olho" if lado == "esquerda" else "mira")).lower()
    chave = ("hud_painel", lado, texto, detalhe, icone, W, H)
    if chave in g.cache:
        return g.cache[chave]
    raio = int(G["raio"])
    sw = max(2, int(round(U * 0.0019)))
    if lado == "esquerda":
        pw = int(G["largo_w"])
        pad = 0.042 * U
        iz = int(0.088 * U)
        f, linhas, al = _ajustar(texto, pw - 2 * pad, 0.15 * U, 700, tam_max=int(0.064 * U),
                                 tam_min=int(0.045 * U), max_linhas=2, entrelinha=1.04)
        ytit = pad + iz + 0.022 * U
    else:
        pw = int(G["alto_w"])
        pad = 0.036 * U
        iz = int(0.05 * U)
        f, linhas, al = _ajustar(texto, pw - 2 * pad, 0.2 * U, 690, tam_max=int(0.056 * U),
                                 tam_min=int(TAM_MIN * U), max_linhas=3, entrelinha=1.06)
        ytit = pad * 1.5 + iz + 0.055 * U
    if detalhe:  # ajustado à largura do painel (até 2 linhas): nunca sai cortado pela borda do vidro
        fd, lin_d, ald = _ajustar(detalhe, pw - 2 * pad, 0.11 * U, 700, tam_max=int(0.046 * U),
                                  tam_min=int(TAM_MIN * U), max_linhas=2, entrelinha=1.12)
    else:
        fd, lin_d, ald = None, [], 0
    alt_d = ald * len(lin_d)
    alt_tit = al * len(linhas)
    ph = int(ytit + alt_tit + (0.012 * U + alt_d if detalhe else 0) + pad * 0.95)
    ph = max(ph, int((0.27 if lado == "esquerda" else 0.36) * U))
    if lado == "direita":  # título "assenta" embaixo no painel alto, como na prévia
        pass
    cam = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    dr = ImageDraw.Draw(cam)
    # borda externa + borda interna (inset), como o vidro da prévia
    cam.alpha_composite(d.painel(pw, ph, raio, fundo=(0, 0, 0, 0), borda=(255, 255, 255, 118), larg_borda=sw))
    # brilho fino no topo (inset highlight)
    hl = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    ImageDraw.Draw(hl).line([(raio, sw + 1), (pw - raio, sw + 1)], fill=(255, 255, 255, 120), width=max(1, sw - 1))
    cam.alpha_composite(hl)
    if lado == "esquerda":
        ins = int(0.015 * U)
        cam.alpha_composite(d.painel(pw - 2 * ins, ph - 2 * ins, max(4, raio - ins), fundo=(0, 0, 0, 0),
                                     borda=(255, 255, 255, 40), larg_borda=max(1, sw // 2)), (ins, ins))
        ic = _ss_icone(icone, iz, ACENTO, moldura=True)
        cam.alpha_composite(ic, (int(pad * 0.85), int(pad * 0.85)))
        ybase = ph - pad * 0.95 - (0.012 * U + alt_d if detalhe else 0) - alt_tit
        d.escrever(cam, (pad, ybase), linhas, f, TEXTO, al=al, sombra=0.42)
        if detalhe:
            d.escrever(cam, (pad, ybase + alt_tit + 0.012 * U), lin_d, fd, ACENTO, al=ald, sombra=0.35)
    else:
        L, m = 0.03 * U, 0.024 * U
        cb = (255, 255, 255, 92)
        for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            x = m if sx == 0 else pw - m
            y = m if sy == 0 else ph - m
            dx = L if sx == 0 else -L
            dyy = L if sy == 0 else -L
            dr.line([(x, y + dyy), (x, y), (x + dx, y)], fill=cb, width=max(1, sw - 1))
        ic = _ss_icone(icone, iz, ACENTO)
        cam.alpha_composite(ic, (int(pad + 0.004 * U), int(pad * 1.5)))
        d.escrever(cam, (pad, ytit), linhas, f, TEXTO, al=al, sombra=0.42)
        if detalhe:
            d.escrever(cam, (pad, ytit + alt_tit + 0.012 * U), lin_d, fd, ACENTO, al=ald, sombra=0.35)
    tinta = _gradiente_tinta(pw, ph, [(0, 0.22), (0.45, 0.07), (1, 0.14)] if lado == "esquerda"
                             else [(0, 0.20), (0.5, 0.055), (1, 0.15)], 125 if lado == "esquerda" else 150)
    som, ms = _sombra_painel(pw, ph, raio, U)
    # reflexo: coordenada diagonal pré-calculada
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    ang = math.radians(24 if lado == "esquerda" else 20)
    diag = xx - yy * math.tan(ang)
    r = {"cam": cam, "w": pw, "h": ph, "raio": raio, "tinta": tinta, "sombra": som, "ms": ms,
         "diag": diag, "tan": math.tan(ang), "mask": d.mascara_arredondada(pw, ph, raio)}
    g.cache[chave] = r
    return r


def _reduzido(g, r, esc):
    """Versão menor (plano muito fechado) de um painel pronto, feita UMA vez e guardada no cache."""
    if esc >= 0.999:
        return r
    chave = ("hud_red", id(r), round(esc, 3))
    if chave not in g.cache:
        w, h = max(8, int(r["w"] * esc)), max(8, int(r["h"] * esc))
        raio = max(4, int(r["raio"] * esc))
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        som = r["sombra"].resize((int(r["sombra"].width * esc), int(r["sombra"].height * esc)), Image.BILINEAR)
        g.cache[chave] = {"cam": r["cam"].resize((w, h), Image.LANCZOS), "w": w, "h": h, "raio": raio,
                          "tinta": r["tinta"].resize((w, h), Image.BILINEAR), "sombra": som,
                          "ms": int(r["ms"] * esc), "diag": xx - yy * r["tan"], "tan": r["tan"],
                          "mask": d.mascara_arredondada(w, h, raio)}
    return g.cache[chave]


def _pilula(g, e):
    W, H = g.W, g.H
    G = _geo(W, H)
    U = G["U"]
    texto = " ".join(str(e.get("texto", "")).split())
    chave = ("hud_pilula", texto, W, H)
    if chave in g.cache:
        return g.cache[chave]
    ph = int(G["chamada_h"])
    f, linhas, _ = _ajustar(texto, 0.66 * U, ph * 0.7, 720, tam_max=int(0.054 * U),
                            tam_min=int(TAM_MIN * U), max_linhas=1)
    if len(linhas) > 1:  # pílula é de 1 linha: com texto longo demais (validar avisa) diminui até caber
        tam = int(TAM_MIN * U)
        while tam > 10 and f.getlength(texto) > 0.78 * U:
            tam -= 1
            f = d.fonte(tam, 720)
        linhas = [texto]
    txt = linhas[0] if linhas else texto
    pad = 0.045 * U
    pz = 0.022 * U
    pw = int(pad + pz + 0.024 * U + f.getlength(txt) + pad)
    raio = ph // 2
    sw = max(2, int(round(U * 0.0019)))
    cam = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    cam.alpha_composite(d.painel(pw, ph, raio, fundo=(0, 0, 0, 0), borda=(255, 255, 255, 118), larg_borda=sw))
    pt = d.brilho_neon(_ss_icone("ponto", int(pz * 2.2), ACENTO), ACENTO, raio=pz * 0.5, forca=0.7)
    cam.alpha_composite(pt, (int(pad - pz * 0.6 - (pt.width - pz * 2.2) / 2), int(ph / 2 - pt.height / 2)))
    d.escrever(cam, (pad + pz + 0.024 * U, ph / 2 - f.size * 0.04), [txt], f, TEXTO, sombra=0.42,
               ancora_y="centro")
    tinta = _gradiente_tinta(pw, ph, [(0, 0.2), (0.5, 0.07), (1, 0.14)], 125)
    som, ms = _sombra_painel(pw, ph, raio, U)
    yy, xx = np.mgrid[0:ph, 0:pw].astype(np.float32)
    r = {"cam": cam, "w": pw, "h": ph, "raio": raio, "tinta": tinta, "sombra": som, "ms": ms,
         "diag": xx - yy * math.tan(math.radians(24)), "tan": math.tan(math.radians(24)), "mask": d.mascara_arredondada(pw, ph, raio)}
    g.cache[chave] = r
    return r


def _canto(U, cor_c):
    """Um canto em L (super-amostrado) para a mira; os outros são espelhos."""
    L = int(0.07 * U)
    e = max(2, int(0.0065 * U))
    ss = 4
    im = Image.new("RGBA", (L * ss, L * ss), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    c = d.cor(cor_c)
    E = e * ss
    dr.rounded_rectangle((0, 0, L * ss, E), radius=E // 2, fill=c)
    dr.rounded_rectangle((0, 0, E, L * ss), radius=E // 2, fill=c)
    return im.resize((L, L), Image.LANCZOS)


def preparar(g):
    W, H = g.W, g.H
    G = _geo(W, H)
    evs = g.plano.get("eventos", [])
    for e, lado in _lados(evs):
        e["_lado"] = lado
        _conteudo(g, e, lado)
    for e in evs:
        if e.get("tipo") == "chamada":
            _pilula(g, e)
    # grupos de espaço (painéis/chamadas próximos dividem a mesma "descida" de câmera)
    ocup = sorted([e for e in evs if e.get("tipo") in ("painel", "chamada")], key=lambda e: e["inicio"])
    grupos = []
    for e in ocup:
        if grupos and e["inicio"] - grupos[-1]["fim"] < 1.6:
            grupos[-1]["fim"] = max(grupos[-1]["fim"], e["fim"])
            grupos[-1]["evs"].append(e)
        else:
            grupos.append({"ini": e["inicio"], "fim": e["fim"], "evs": [e]})
    for gr in grupos:
        topo, base = H, 0.0
        for e in gr["evs"]:
            if e.get("tipo") == "painel":
                r = _conteudo(g, e, e["_lado"])
                y = G["largo_y"] if e["_lado"] == "esquerda" else G["alto_y"]
            else:
                r = _pilula(g, e)
                y = G["chamada_y"]
            topo, base = min(topo, y), max(base, y + r["h"])
        ts = np.arange(gr["ini"] - 0.5, gr["fim"] + 0.8, 0.2)
        testa = min(g.rosto.em(float(t))[1] for t in ts)
        boca = max((lambda b: b[1] + 0.72 * (b[3] - b[1]))(g.rosto.em(float(t))) for t in ts)
        need = max(0.0, base + G["folga_testa"] - testa)
        lim = max(0.0, min(G["dy_max"], 0.665 * H - boca))
        dy = min(need, lim)
        esc = 1.0
        if need < G["dy_min"]:
            # falta só um pouquinho (o painel encosta no cabelo/boné, não no rosto): não vale descer a câmera
            # e borrar o topo do vídeo por causa de poucos pixels
            dy = 0.0
        elif need > dy + 1:
            esc = d.limitar((testa + dy - G["folga_testa"] - topo) / max(1.0, base - topo), ESC_MIN, 1.0)
        gr["dy"], gr["esc"] = dy, esc
        for e in gr["evs"]:
            e["_esc"] = esc
    g.cache["hud_grupos"] = grupos
    g.cache["hud_canto"] = _canto(G["U"], "#FFFFFF")
    g.cache["hud_canto_ac"] = _canto(G["U"], ACENTO)


# ------------------------------------------------------------------ por quadro

def _desloc(g, t):
    dy = 0.0
    for gr in g.cache.get("hud_grupos", []):
        if gr["dy"] <= 0.5 or not (gr["ini"] - 0.7 <= t <= gr["fim"] + 0.9):
            continue
        k_in = d.suave(d.mapear(t, gr["ini"] - 0.55, gr["ini"] + 0.1))
        k_out = 1 - d.suave(d.mapear(t, gr["fim"] + 0.1, gr["fim"] + 0.75))
        dy = max(dy, gr["dy"] * min(k_in, k_out))
    return dy


def _base(c, dy):
    """Vídeo deslocado para baixo + extensão desfocada do cenário no topo (com emenda suave).
    Tudo que é desfoque é feito em resolução baixa (rápido)."""
    src = c.fonte
    W, H = c.W, c.H
    dyi = int(round(dy))
    if dyi < 1:
        return src.copy()
    fade = max(8, int(0.06 * H))
    out = src.crop((0, -dyi, W, H - dyi))  # topo vazio (transparente) de altura dyi
    f = 8
    w8 = max(2, W // f)
    h_top, h_fade = max(1, -(-dyi // f)), max(1, fade // f)
    # espelho do topo do quadro (continua o cenário) + o começo do quadro sob a emenda
    rgb_topo = src.crop((0, 0, W, max(dyi, fade))).convert("RGB")  # RGB: o resize de RGBA converte o quadro todo
    topo = rgb_topo.resize((w8, h_top), Image.BILINEAR, box=(0, 0, W, dyi)).transpose(Image.FLIP_TOP_BOTTOM)
    emenda = rgb_topo.resize((w8, h_fade), Image.BILINEAR, box=(0, 0, W, fade))
    faixa = Image.new("RGB", (w8, h_top + h_fade))
    faixa.paste(topo, (0, 0))
    faixa.paste(emenda, (0, h_top))
    faixa = faixa.filter(ImageFilter.GaussianBlur(0.035 * W / f)).convert("RGBA")
    # escurece com tom azul-petróleo (mais forte no topo) para os painéis terem contraste
    hh = h_top + h_fade
    a = np.linspace(0.62, 0.30, hh, dtype=np.float32)
    ton = np.zeros((hh, w8, 4), np.uint8)
    ton[..., 0], ton[..., 1], ton[..., 2] = 12, 26, 32
    ton[..., 3] = (a[:, None] * 255).astype(np.uint8)
    faixa.alpha_composite(Image.fromarray(ton, "RGBA"))
    al = np.ones(hh, np.float32)
    al[h_top:] = [1 - d.suave(k) for k in np.linspace(0, 1, h_fade + 2)[1:-1]]
    faixa.putalpha(Image.fromarray(np.repeat((al * 255).astype(np.uint8)[:, None], w8, axis=1), "L"))
    faixa = faixa.resize((W, h_top * f + h_fade * f), Image.BILINEAR)
    # garante topo 100% coberto (o bilinear não pode deixar fresta transparente)
    cheio = faixa.getchannel("A")
    cheio.paste(255, (0, 0, W, dyi + 1))
    faixa.putalpha(cheio)
    out.alpha_composite(faixa, (0, 0))
    return out


def _kf(t, pontos):
    """Interpolação por quadros-chave [(tempo, valor), ...] com curva que assenta (ease-out)."""
    if t <= pontos[0][0]:
        return pontos[0][1]
    for (t0, v0), (t1, v1) in zip(pontos, pontos[1:]):
        if t <= t1:
            return d.lerp(v0, v1, d.saida(d.mapear(t, t0, t1)))
    return pontos[-1][1]


def _vidro(img, r, x, y, esc, k, t_ref, U):
    """Desenha um painel de vidro completo com opacidade k; (x, y) = canto superior esquerdo JÁ escalado."""
    W, H = img.size
    pw, ph = r["w"], r["h"]
    if abs(esc - 1) > 0.002:
        sw, sh = max(4, int(pw * esc)), max(4, int(ph * esc))
    else:
        sw, sh = pw, ph
    xi, yi = int(round(x)), int(round(y))
    # sombra
    som = r["sombra"]  # a sombra é difusa: não precisa acompanhar a micro-escala da entrada
    d.colar_em(img, som, (xi + (sw - pw) / 2 - r["ms"], yi + (sh - ph) / 2 - r["ms"]), opacidade=k)
    # vidro: desfoca o que está atrás (em resolução baixa, com margem para não escurecer as bordas)
    mg = int(0.03 * U)
    bx0, by0 = max(0, xi - mg), max(0, yi - mg)
    bx1, by1 = min(W, xi + sw + mg), min(H, yi + sh + mg)
    if bx1 - bx0 < 8 or by1 - by0 < 8:
        return
    f = 5
    pw2, ph2 = max(2, (bx1 - bx0) // f), max(2, (by1 - by0) // f)
    peq = img.crop((bx0, by0, bx1, by1)).convert("RGB").resize((pw2, ph2), Image.BILINEAR)
    peq = peq.filter(ImageFilter.GaussianBlur(0.022 * U / f))
    peq = ImageEnhance.Color(peq).enhance(1.25)
    lum = float(np.asarray(peq.convert("L"), np.float32).mean()) / 255
    # fumê adaptativo: fundo claro → vidro mais escuro, para o texto branco sempre ler bem
    fumo = 0.14 + 0.46 * d.limitar((lum - 0.28) / 0.45)
    peq = Image.blend(peq, Image.new("RGB", peq.size, (10, 24, 30)), fumo)
    fx, fy = (bx1 - bx0) / pw2, (by1 - by0) / ph2
    ox, oy = (xi - bx0) / fx, (yi - by0) / fy
    vid = peq.resize((sw, sh), Image.BILINEAR, box=(ox, oy, ox + sw / fx, oy + sh / fy)).convert("RGBA")
    tinta = r["tinta"] if (sw, sh) == (pw, ph) else r["tinta"].resize((sw, sh), Image.BILINEAR)
    vid.alpha_composite(tinta)
    mask = r["mask"] if (sw, sh) == (pw, ph) else r["mask"].resize((sw, sh), Image.BILINEAR)
    if k < 0.997:
        mask = mask.point(lambda v: int(v * k))
    vid.putalpha(mask)
    d.colar_em(img, vid, (xi, yi))
    # conteúdo (borda, ícone, título)
    cam = r["cam"] if (sw, sh) == (pw, ph) else r["cam"].resize((sw, sh), Image.BICUBIC)
    d.colar_em(img, cam, (xi, yi), opacidade=k)
    # reflexo que atravessa o vidro uma vez depois da entrada
    if t_ref is not None and 0 < t_ref < 1 and (sw, sh) == (pw, ph):
        larg = 0.17 * U
        ini, fim = -0.45 * pw - larg, pw + larg
        cpos = d.lerp(ini, fim, d.suave(t_ref))
        a = np.exp(-((r["diag"] - cpos) / (larg * 0.38)) ** 2) * 0.26 * k
        ref = np.zeros((ph, pw, 4), np.uint8)
        ref[..., :3] = 255
        ref[..., 3] = (a * (np.asarray(r["mask"], np.float32) / 255) * 255).astype(np.uint8)
        d.colar_em(img, Image.fromarray(ref, "RGBA"), (xi, yi))


def _linha(img, pts, prog, cor_l, alfa, U, ponto=True):
    """Linha de chamada (polilinha) que se desenha conforme prog 0→1, com ponto verde na ponta."""
    if prog <= 0 or alfa <= 0.01:
        return
    segs = list(zip(pts, pts[1:]))
    comp = [math.dist(a, b) for a, b in segs]
    tot = sum(comp) * prog
    vis = [pts[0]]
    for (a, b), l in zip(segs, comp):
        if tot <= 0:
            break
        q = min(1.0, tot / max(1e-6, l))
        vis.append((a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q))
        tot -= l
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    m = int(0.02 * U)
    x0, y0 = int(min(xs)) - m, int(min(ys)) - m
    w, h = int(max(xs)) - x0 + m, int(max(ys)) - y0 + m
    ss = 3
    cam = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    dr = ImageDraw.Draw(cam)
    lw = max(2, int(0.0021 * U * ss))
    dr.line([((p[0] - x0) * ss, (p[1] - y0) * ss) for p in vis], fill=d.cor(cor_l, alfa), width=lw, joint="curve")
    if ponto and prog >= 0.98:
        r = 0.0055 * U * ss
        px, py = (pts[-1][0] - x0) * ss, (pts[-1][1] - y0) * ss
        dr.ellipse([px - r, py - r, px + r, py + r], fill=d.cor(ACENTO, min(1.0, alfa * 1.4)))
    d.colar_em(img, cam.resize((w, h), Image.LANCZOS), (x0, y0))


def _mira(img, c, e, dy):
    k = e.env(c.t, 0.25, 0.3)
    if k <= 0:
        return
    W, H, U = c.W, c.H, c.W
    x0, y0, x1, y1 = c.rosto
    fw, fh = x1 - x0, y1 - y0
    bx0, bx1 = max(0.05 * W, x0 - 0.1 * fw), min(0.86 * W, x1 + 0.1 * fw)
    by0, by1 = max(0.12 * H, y0 + dy - 0.16 * fh), min(0.70 * H, y1 + dy + 0.06 * fh)
    trava = d.saida(d.mapear(c.t, e["inicio"], e["inicio"] + 0.38))
    abre = 1 + 0.16 * (1 - trava)
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    hw, hh = (bx1 - bx0) / 2 * abre, (by1 - by0) / 2 * abre
    # verde no instante em que trava, depois branco
    verde = 1 - d.suave(d.mapear(c.t, e["inicio"] + 0.38, e["inicio"] + 0.9))
    for nome, alfa in (("hud_canto", k * 0.9 * (1 - verde)), ("hud_canto_ac", k * verde)):
        if alfa <= 0.01:
            continue
        cn = c.g.cache[nome]
        L = cn.width
        for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            im = cn
            if sx:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
            if sy:
                im = im.transpose(Image.FLIP_TOP_BOTTOM)
            px = cx - hw if sx == 0 else cx + hw - L
            py = cy - hh if sy == 0 else cy + hh - L
            d.colar_em(img, im, (px, py), opacidade=alfa)


def quadro(c):
    g = c.g
    W, H = c.W, c.H
    G = _geo(W, H)
    U = G["U"]
    t = c.t
    dy = _desloc(g, t)
    img = _base(c, dy)
    for e in c.eventos:
        if e.get("tipo") == "mira":
            _mira(img, c, e, dy)
    # linhas de chamada primeiro (ficam atrás dos vidros)
    itens = []
    for e in c.eventos:
        tipo = e.get("tipo")
        if tipo not in ("painel", "chamada"):
            continue
        rel = t - e["inicio"]
        k = d.suave(d.mapear(rel, 0, 0.4)) * (1 - d.suave(d.mapear(t, e["fim"] - 0.55, e["fim"])))
        if k <= 0.003:
            continue
        sobe = _kf(rel, [(0, 0.033), (0.6, -0.0036), (0.93, 0.001), (1.33, 0.0)]) * H
        sobe += -0.012 * H * d.suave(d.mapear(t, e["fim"] - 0.6, e["fim"]))
        esc = _kf(rel, [(0, 0.96), (0.7, 1.012), (1.17, 1.0)]) - 0.01 * d.mapear(t, e["fim"] - 0.55, e["fim"])
        base_esc = float(e.get("_esc", 1.0))
        if tipo == "painel":
            lado = e.get("_lado") or "esquerda"
            r = _conteudo(g, e, lado)
            x = G["largo_x"] if lado == "esquerda" else G["alto_x"]
            y = G["largo_y"] if lado == "esquerda" else G["alto_y"]
        else:
            r = _pilula(g, e)
            fx0, _, fx1, _ = c.rosto
            cxr = d.limitar((fx0 + fx1) / 2, 0.06 * W + r["w"] / 2, 0.86 * W - r["w"] / 2)
            x, y = cxr - r["w"] / 2, G["chamada_y"]
        # retângulo final: a entrada escala em torno do centro; a redução de plano fechado (base_esc)
        # mantém o topo e a borda externa no lugar
        cx0 = x + r["w"] / 2
        if base_esc < 0.999 and tipo == "painel":
            cx0 += (-1 if x < W / 2 else 1) * r["w"] * (1 - base_esc) / 2
        cy0 = y + r["h"] * base_esc / 2
        r = _reduzido(g, r, base_esc)
        e_tot = esc
        x, y = cx0 - r["w"] * e_tot / 2, cy0 - r["h"] * e_tot / 2 + sobe
        itens.append((e, tipo, r, x, y, e_tot, k, rel))
    for e, tipo, r, x, y, esc, k, rel in itens:
        pw, ph = r["w"] * esc, r["h"] * esc
        alfa = 0.68 * k
        prog = d.saida(d.mapear(rel, 0.55 if tipo == "painel" else 0.3, 1.25 if tipo == "painel" else 0.85))
        if tipo == "painel":
            esq = (e.get("_lado") or "esquerda") == "esquerda"
            sx = x + (0.05 * U if esq else pw - 0.05 * U)
            yb = y + ph + 0.002 * H
            v = 0.04 * H
            dx = 0.075 * U if esq else -0.075 * U
            _linha(img, [(sx, yb), (sx, yb + v), (sx + dx, yb + v + 0.024 * H)], prog, "#FFFFFF", alfa, U)
        else:
            cx = x + pw / 2
            yb = y + ph + 0.002 * H
            alvo = g.rosto.topo_cabeca(t) + dy + 0.01 * H
            fim_y = d.limitar(alvo, yb + 0.02 * H, yb + 0.22 * H)  # vai até o alto da cabeça
            _linha(img, [(cx, yb), (cx, fim_y)], prog, "#FFFFFF", alfa, U)
    for e, tipo, r, x, y, esc, k, rel in itens:
        t_ref = d.mapear(rel, 0.75, 2.1) if tipo == "painel" else d.mapear(rel, 0.4, 1.4)
        _vidro(img, r, x, y, esc, k, t_ref, U)
    return img
