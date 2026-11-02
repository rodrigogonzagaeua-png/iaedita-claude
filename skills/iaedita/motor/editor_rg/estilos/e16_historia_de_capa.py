"""16 · História de capa — o vídeo vira capa de revista: um título enorme em serifa (Cormorant) fica
ATRÁS da pessoa (a cabeça passa na frente das letras), com o nome da revista e o número da edição no
alto, chamadas curtas ao lado do rosto, uma moldura fina e a legenda em bloco editorial escuro.
Cada capa nasce de um trecho da fala: o título se revela de cima para baixo, assenta, segura e se
recolhe; entre capas o vídeo respira limpo (prévia aprovada / Scene16).

Composição (calculada UMA vez em preparar):
- o topo REAL da cabeça vem da máscara da pessoa (amostras a 4 por segundo); sem máscara, uma
  estimativa conservadora a partir do rosto;
- o título fica no alto, logo abaixo do nome da revista; a câmera recua (o vídeo encolhe ancorado
  embaixo e o fundo continua em volta, desfocado e sem a pessoa) só o necessário para a cabeça cobrir a
  parte de baixo da última linha — a primeira linha fica sempre inteira. Cabeça baixa (plano aberto):
  o título desce até encostar nela. A boca nunca desce até a legenda;
- chamadas na coluna livre ao lado do rosto; se o rosto é grande demais (plano fechado), elas viram
  uma linha de chamadas no rodapé, logo abaixo da legenda;
- a cor das letras (tinta escura ou creme) é decidida por capa a partir do brilho nos quadros-chave do
  vídeo: nunca um cinza intermediário, nunca pisca. O título (atrás da pessoa) mede só o fundo; chamadas
  e frase (na frente) medem tudo o que fica atrás delas, pessoa incluída, e ganham uma placa escura
  translúcida quando esse fundo é misturado, é a pessoa ou fica no meio-termo de brilho;
- título de 1 linha: a câmera recua o bastante para o pico da cabeça não cobrir mais que 45% da
  maiúscula (a palavra continua legível quando a pessoa se inclina para a câmera);
- sem recorte: o título fica inteiro ACIMA da cabeça e nada passa sobre olhos ou boca.
quadro(c) só depende de c.t e do plano. Legenda própria: Cormorant 700 em bloco escuro alinhado à
esquerda, fio verde-limão no alto e a palavra falada em verde-limão (ficha 16-historia-de-capa)."""
from __future__ import annotations

import math
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import desenho as d
from ..legenda import agrupar

try:  # OpenCV só deixa o recuo de câmera mais rápido; sem ele o resultado é o mesmo
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

INFO = {
    "id": "16-historia-de-capa",
    "nome": "História de capa",
    "precisa_recorte": True,
    "antes": 0.9,
    "depois": 1.0,
    # ficha 16: Cormorant 700, creme, palavra ativa verde-limão, caixa escura, alinhada à esquerda, fio no alto
    "legenda": {"fonte": "serif", "peso": 700, "tamanho": 0.078, "cor": "#F8F7F0", "destaque": "#D4ED80",
                "caixa": "#222729EF", "max_caracteres": 22, "max_linhas": 1, "animacao": "settle"},
    "legenda_propria": True,
    "eventos": {
        "capa": "inicio (segundo em que a ideia da capa começa a ser dita), fim (quando a capa sai; 3 a 10 s "
                "depois), titulo (1 a 3 palavras, só letras, até 10 letras por palavra: o título enorme em "
                "serifa que fica ATRÁS da pessoa), revista (nome da revista no alto, 1 a 4 palavras, até 26 "
                "letras, ex. 'GUIA DO CRIADOR'), edicao (opcional: número da edição ao lado do nome, até 10 "
                "letras, ex. 'Nº 26'), chamadas (opcional: lista de 0 a 3 chamadas de 1 a 3 palavras, até 18 "
                "letras cada; cada item é um texto ou {\"texto\": \"...\", \"em\": segundo em que ela é dita}), "
                "frase (opcional: frase curta em serifa, até 30 letras), frase_em (opcional: segundo em que "
                "a frase é dita), letras ('auto' padrão | 'claras' | "
                "'escuras'), lado ('auto' padrão | 'esquerda' | 'direita': lado das chamadas), "
                "som (use 'props-page-turn')",
    },
}

# ------------------------------------------------------------------ paleta (prévia aprovada / Scene16)
TINTA = (37, 46, 40)          # #252E28 título em tinta escura
TINTA_REV = (52, 66, 54)      # #344236 nome da revista
TINTA_CH = (40, 56, 46)       # #28382E chamadas
CREME = (255, 253, 242)       # #FFFDF2 moldura, frase, letras claras
CREME_TIT = (248, 245, 234)   # título claro (fundo escuro)
LIMA = (212, 237, 128)        # #D4ED80 fio da legenda, barra e pontos das chamadas
LAV_CLARA = (247, 239, 221)   # #F7EFDD lavagem creme do alto (prévia: #f7efdd44)
LAV_ESCURA = (12, 16, 13)     # lavagem escura do alto (quando as letras são claras)
BASE_ESC = (35, 41, 33)       # #232921 lavagem de baixo (prévia: #23292133)
LEG_CAIXA = "#222729EF"
ACENTOS = set("ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜ")

# ------------------------------------------------------------------ medidas (frações de W, H ou u)
MOL_X, MOL_Y = 0.05, 0.042    # moldura fina (afastamento da borda)
REV_Y = 0.116                 # topo das letras do nome da revista (H) — logo abaixo da zona segura
REV_X0, REV_X1 = 0.085, 0.86  # margens do nome da revista / edição (W)
REV_TAM = 0.036               # letra do nome da revista (u) — mínimo legível
TIT_Y0 = 0.156                # topo do título (H)
TIT_LARG = 0.84               # largura máxima do título (W)
TIT_MAX, TIT_MIN = 0.285, 0.15  # tamanho da letra do título (u)
TIT_ENTRE = 0.83              # entrelinha do título (em) — prévia: lineHeight 0.83
TIT_ESP = -0.042              # espacejamento do título (em) — prévia: letterSpacing -13 em 310
COBRE_1, COBRE_2 = 0.36, 0.42  # quanto da última linha (fração da altura da maiúscula) a cabeça cobre
COBRE_MAX_1 = 0.45            # título de 1 linha: o máximo que a cabeça pode cobrir no pico
COL_X0, COL_X1 = 0.07, 0.86   # colunas das chamadas (W): a direita fica livre (botões da rede)
COL_MIN = 0.17                # coluna mais estreita que aceita chamada (W)
CH_MAX, CH_MIN = 0.046, 0.036  # letra das chamadas (u)
FR_MAX, FR_MIN = 0.060, 0.045  # letra da frase (u)
LEG_X, LEG_X1 = 0.074, 0.86   # legenda e rodapé (W)
LEG_TOPO = 0.65               # topo da legenda (H) — ficha: y1250 de 1920
LEG_BASE = 0.80               # base máxima da legenda e do rodapé (H) — zona segura de baixo
S_MIN = 0.64                  # recuo máximo da câmera
S_FIM = 0.998                 # acima disto a câmera conta como parada no normal (sem recuo)
JUNTA = 1.6                   # capas com intervalo menor que isto formam uma só "página" (câmera parada)
LAV_ALFA_CLARA, LAV_ALFA_ESCURA = 0.26, 0.42
BASE_ALFA = 0.20
LIMIAR_TIT, LIMIAR_TXT = 0.60, 0.62   # brilho do fundo acima disto -> letras em tinta escura
                                       # (meio-termo fica creme + lavagem escura: contraste garantido)
# chamadas e frase ficam NA FRENTE da pessoa: se o que está atrás delas é misturado (desvio-padrão alto),
# é muito a pessoa, ou o brilho fica no meio-termo, elas ganham uma placa escura translúcida
PLACA_DP, PLACA_PESSOA = 0.18, 0.30
CREME_MAX, TINTA_MIN = 0.45, 0.68     # creme só sobre fundo escuro; tinta só sobre fundo claro
PLACA_ALFA = 0.75
AM_W = 108                    # largura da amostra da máscara (px); a do brilho é a metade
AM_FPS = 4.0
TOPO_SEM = 0.48               # sem máscara: topo da cabeça = topo do rosto - 0.48 x altura do rosto

LETRAS = {"auto": "auto", "": "auto", "claras": "claras", "clara": "claras", "branca": "claras",
          "brancas": "claras", "creme": "claras", "escuras": "escuras", "escura": "escuras",
          "preta": "escuras", "pretas": "escuras", "tinta": "escuras"}
LADOS = {"auto": "auto", "": "auto", "esquerda": "esquerda", "esq": "esquerda", "left": "esquerda",
         "direita": "direita", "dir": "direita", "right": "direita"}


def _u(W, H):
    """Unidade de medida: largura de um quadro 9:16 com a mesma altura."""
    return min(W, H * 0.5625)


def _txt(v):
    return " ".join(str(v or "").split())


def _aviso(msg):
    print(f"[16-historia-de-capa] {msg}", file=sys.stderr)


def _chamadas(e):
    out = []
    for item in list(e.get("chamadas") or [])[:3]:
        if isinstance(item, dict):
            tx, em = _txt(item.get("texto")), item.get("em")
        else:
            tx, em = _txt(item), None
        if tx:
            try:
                em = float(em) if em is not None else None
            except (TypeError, ValueError):
                em = None
            out.append({"texto": tx, "em": em})
    return out


def _letras(e):
    return LETRAS.get(str(e.get("letras", "auto") or "auto").strip().lower(), None)


def _lado(e):
    return LADOS.get(str(e.get("lado", "auto") or "auto").strip().lower(), None)


# ================================================================== validação do plano


def validar(plano, duracao):
    p = []
    capas = sorted([e for e in plano["eventos"] if e.get("tipo") == "capa"], key=lambda e: e["inicio"])
    for e in capas:
        ini, fim = float(e["inicio"]), float(e["fim"])
        tit = _txt(e.get("titulo"))
        if not tit:
            p.append(f"Capa em {ini:.2f}s sem 'titulo'.")
        else:
            if re.search(r"\d", tit):
                p.append(f"Capa em {ini:.2f}s: o título '{tit}' tem número. A letra do título usa algarismos "
                         "antigos (desalinhados): escreva só com letras e ponha o número em 'edicao' "
                         "(ex. 'Nº 26') ou numa chamada.")
            ws = tit.split()
            if len(ws) > 3 or max(len(w) for w in ws) > 11 or len(tit) > 20:
                p.append(f"Título da capa em {ini:.2f}s longo demais ('{tit}'): 1 a 3 palavras, até 10 letras "
                         "cada (o título é enorme; frase longa não cabe).")
        dur = fim - ini
        if dur < 2.5:
            p.append(f"Capa em {ini:.2f}s dura só {dur:.1f}s: pouco para revelar e ler (mínimo 2,5 s).")
        if dur > 12:
            p.append(f"Capa em {ini:.2f}s dura {dur:.1f}s: longo demais (até 10 s; troque de capa no próximo assunto).")
        rev = _txt(e.get("revista"))
        if len(rev) > 26 or len(rev.split()) > 4:
            p.append(f"Nome da revista em {ini:.2f}s longo demais ('{rev}'): 1 a 4 palavras, até 26 letras.")
        ed = _txt(e.get("edicao"))
        if len(ed) > 10:
            p.append(f"Edição em {ini:.2f}s longa demais ('{ed}'): até 10 letras, ex. 'Nº 26'.")
        raw = e.get("chamadas") or []
        if not isinstance(raw, (list, tuple)):
            p.append(f"Capa em {ini:.2f}s: 'chamadas' precisa ser uma lista.")
            raw = []
        if len(raw) > 3:
            p.append(f"Capa em {ini:.2f}s com {len(raw)} chamadas: no máximo 3 (o resto não cabe ao lado do rosto).")
        for ch in _chamadas(e):
            if len(ch["texto"]) > 20 or len(ch["texto"].split()) > 4:
                p.append(f"Chamada '{ch['texto']}' (capa em {ini:.2f}s) longa demais: 1 a 3 palavras, até 18 letras.")
            if ch["em"] is not None:
                em = ch["em"]
                if em < ini - 0.05:
                    p.append(f"Chamada '{ch['texto']}': entra em {em:.2f}s, antes do início da capa ({ini:.2f}s). "
                             f"Use uma palavra dita depois de {ini:.2f}s ou diminua 'inicio'.")
                elif em > fim - 0.79:
                    p.append(f"Chamada '{ch['texto']}': entra em {em:.2f}s, mas precisa entrar pelo menos 0,8 s "
                             f"antes do fim da capa ({fim:.2f}s). Aumente 'fim' para {em + 0.8:.2f}s ou use uma "
                             "palavra dita antes.")
        fr = _txt(e.get("frase"))
        if len(fr) > 32:
            p.append(f"Frase da capa em {ini:.2f}s longa demais ('{fr}'): até 30 letras.")
        if e.get("frase_em") is not None:
            try:
                fe = float(e["frase_em"])
                if fe < ini - 0.05:
                    p.append(f"Capa em {ini:.2f}s: a frase entra em {fe:.2f}s ('frase_em'), antes do início da "
                             f"capa. Use o segundo em que a frase é dita, depois de {ini:.2f}s.")
                elif fe > fim - 0.79:
                    p.append(f"Capa em {ini:.2f}s: a frase entra em {fe:.2f}s ('frase_em'), mas precisa entrar "
                             f"pelo menos 0,8 s antes do fim da capa ({fim:.2f}s). Aumente 'fim' para "
                             f"{fe + 0.8:.2f}s ou use uma frase dita antes.")
            except (TypeError, ValueError):
                p.append(f"Capa em {ini:.2f}s: 'frase_em' precisa ser um número (segundos).")
            if not fr:
                p.append(f"Capa em {ini:.2f}s: 'frase_em' sem 'frase'.")
        if _letras(e) is None:
            p.append(f"Capa em {ini:.2f}s: letras '{e.get('letras')}' não existe (auto, claras ou escuras).")
        if _lado(e) is None:
            p.append(f"Capa em {ini:.2f}s: lado '{e.get('lado')}' não existe (auto, esquerda ou direita).")
    for a, b in zip(capas, capas[1:]):
        if float(b["inicio"]) < float(a["fim"]) - 0.01:
            p.append(f"Capas sobrepostas em {b['inicio']:.2f}s: uma capa precisa terminar antes da outra começar.")
    if capas and duracao > 10:
        tot = sum(float(e["fim"]) - float(e["inicio"]) for e in capas)
        if tot > 0.88 * duracao:
            p.append("As capas cobrem quase o vídeo inteiro: deixe respiros sem capa (uns 20% do tempo).")
    return p


# ================================================================== amostras do vídeo e da máscara


def _caminhos():
    """Caminhos do vídeo e da máscara. O motor não os entrega ao estilo; são lidos de quem chamou
    preparar (montar._preparar). Se não achar, o estilo usa estimativas (sem quebrar)."""
    f = sys._getframe(1)
    for _ in range(12):
        if f is None:
            break
        loc = f.f_locals
        v = loc.get("video")
        if isinstance(v, str) and "mascara" in loc:
            m = loc.get("mascara")
            return v, (str(m) if m else None)
        f = f.f_back
    return None, None


def _topo_da_mascara(g, m, t, sw2, sh2):
    """Topo da silhueta (px) acima do centro do rosto numa amostra pequena da máscara."""
    x0, y0, x1, y1 = g.rosto.em(t)
    cx, fw = (x0 + x1) / 2, x1 - x0
    a = int(max(0, (cx - 0.3 * fw) / g.W * sw2))
    b = int(min(sw2, math.ceil((cx + 0.3 * fw) / g.W * sw2)))
    lim = int(min(sh2, max(1, y1 / g.H * sh2)))
    if b - a < 2:
        return float("nan")
    linhas = np.where((m[:lim, a:b] > 110).mean(axis=1) > 0.3)[0]
    return float(linhas[0]) / sh2 * g.H if len(linhas) else float("nan")


def _quadros_chave(video, sw, sh, dur):
    """Brilho (0-1) dos quadros-chave do vídeo numa grade pequena (decodifica só os quadros-chave: rápido)."""
    from ..midia import LeitorDeQuadros, ffmpeg_bin
    base = [ffmpeg_bin(), "-hide_banner", "-nostdin", "-v", "info", "-skip_frame", "nokey", "-i", video,
            "-an", "-vf", f"scale={sw}:{sh}:flags=area,showinfo"]
    ts, arr = [], None
    for modo in (["-fps_mode", "passthrough"], ["-vsync", "0"]):
        try:
            r = subprocess.run(base + modo + ["-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                               capture_output=True, timeout=120)
        except Exception:  # noqa: BLE001
            continue
        if r.returncode == 0 and r.stdout:
            ts = [float(x) for x in re.findall(rb"pts_time:\s*(-?[0-9.]+)", r.stderr)]
            n = min(len(ts), len(r.stdout) // (sw * sh * 3))
            if n:
                arr = np.frombuffer(r.stdout[:n * sw * sh * 3], np.uint8).reshape(n, sh, sw, 3)
                ts = ts[:n]
            break
    if arr is None or len(ts) < max(2, dur / 5):  # poucos quadros-chave: amostra 1 por segundo
        try:
            arr = np.stack(list(LeitorDeQuadros(video, sw, sh, 1.0)))
            ts = [i * 1.0 for i in range(len(arr))]
        except Exception:  # noqa: BLE001
            return None
    if arr is None or not len(arr):
        return None
    lum = (0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]).astype(np.float32) / 255.0
    return np.array(ts, dtype=float), lum


def _chave_cache(video, mascara, W, H):
    partes = [f"e16v2-{W}x{H}-{AM_W}-{AM_FPS}"]
    for arq in (video, mascara):
        st = os.stat(arq)
        partes.append(f"{os.path.abspath(arq)}|{st.st_size}|{int(st.st_mtime)}")
    return "#".join(partes)


def _ler_cache(arq, chave, am):
    try:
        with np.load(arq, allow_pickle=False) as z:
            if str(z["chave"]) != chave:
                return False
            am["topo"] = (z["topo_t"], z["topo_v"])
            am["mk"] = (z["mk_t"], z["mk"])
            if z["kt"].size:
                am["kt"], am["kl"] = z["kt"], z["kl"]
        return True
    except Exception:  # noqa: BLE001
        return False


def _gravar_cache(arq, chave, am):
    """Amostras guardadas ao lado da máscara (pasta de trabalho): as partes do render reaproveitam."""
    if am["topo"] is None or am["mk"] is None:
        return
    try:
        tmp = arq + ".tmp.npz"
        np.savez(tmp, chave=np.array(chave), topo_t=am["topo"][0], topo_v=am["topo"][1], mk_t=am["mk"][0],
                 mk=am["mk"][1], kt=am["kt"] if am["kt"] is not None else np.zeros(0),
                 kl=am["kl"] if am["kl"] is not None else np.zeros((0, 1, 1), np.float32))
        os.replace(tmp, arq)
    except Exception:  # noqa: BLE001
        pass


def _amostrar(g, est):
    video, mascara = _caminhos()
    if g.tem_mascara and not mascara:
        _aviso("não achei o caminho da máscara: usando estimativa pelo rosto (a cabeça e a cor das letras "
               "ficam menos precisas).")
    if not video:
        _aviso("não achei o caminho do vídeo: a cor das letras usa o padrão (creme).")
    W, H = g.W, g.H
    sw2 = AM_W
    sh2 = max(4, int(round(AM_W * H / W / 2)) * 2)
    sw, sh = sw2 // 2, sh2 // 2
    est["am"] = {"sw": sw, "sh": sh, "topo": None, "mk": None, "kt": None, "kl": None}
    am = est["am"]
    arq_cache = chave = None
    if video and mascara and g.tem_mascara:
        try:
            chave = _chave_cache(video, mascara, W, H)
            arq_cache = os.path.join(os.path.dirname(os.path.abspath(mascara)), "_e16_amostras.npz")
            if os.path.exists(arq_cache) and _ler_cache(arq_cache, chave, am):
                return
        except Exception:  # noqa: BLE001
            arq_cache = None
    if mascara and g.tem_mascara:
        try:
            from ..midia import LeitorDeQuadros
            ts, tops, mks = [], [], []
            for i, m in enumerate(LeitorDeQuadros(mascara, sw2, sh2, AM_FPS, cinza=True)):
                t = i / AM_FPS
                ts.append(t)
                tops.append(_topo_da_mascara(g, m, t, sw2, sh2))
                mks.append(m[::2, ::2].copy())
            if ts:
                tops = np.array(tops)
                for i in np.where(np.isnan(tops))[0]:   # sem silhueta: estimativa pelo rosto
                    x0, y0, x1, y1 = g.rosto.em(ts[i])
                    tops[i] = y0 - 0.33 * (y1 - y0)
                lisa = np.array([np.median(tops[max(0, i - 2): i + 3]) for i in range(len(tops))])
                am["topo"] = (np.array(ts), lisa)
                am["mk"] = (np.array(ts), np.stack(mks))
        except Exception as exc:  # noqa: BLE001
            _aviso(f"não consegui ler a máscara para medir a cabeça ({exc}); usei o rosto.")
    if video:
        try:
            r = _quadros_chave(video, sw, sh, g.duracao)
            if r is not None:
                am["kt"], am["kl"] = r
        except Exception as exc:  # noqa: BLE001
            _aviso(f"não consegui medir o brilho do fundo ({exc}); usei letras claras.")
    if arq_cache:
        _gravar_cache(arq_cache, chave, am)


def _topos(est, g, t0, t1):
    """Topo da cabeça (px, sem recuo) amostrado de 0,1 em 0,1 s entre t0 e t1."""
    ts = np.arange(max(0.0, t0), max(max(0.0, t0) + 0.05, min(g.duracao, t1)) + 1e-6, 0.1)
    am = est["am"]
    if am["topo"] is not None:
        return np.interp(ts, am["topo"][0], am["topo"][1])
    out = []
    for t in ts:
        x0, y0, x1, y1 = g.rosto.em(float(t))
        out.append(y0 - (0.33 if est["mascara"] else TOPO_SEM) * (y1 - y0))
    return np.array(out)


def _lum(est, g, rect, t0, t1, s):
    """Brilho médio (0-1) do FUNDO (sem a pessoa) no retângulo de tela rect, com a câmera em s.
    Serve para o título, que fica ATRÁS da pessoa."""
    r = _fundo(est, g, rect, t0, t1, s, atras=True)
    return None if r is None else r["lum"]


def _fundo(est, g, rect, t0, t1, s, atras=True):
    """Brilho no retângulo de tela rect, com a câmera em s, nos quadros-chave entre t0 e t1.
    atras=True: só o fundo (sem a pessoa) — para o que fica atrás dela.
    atras=False: tudo o que fica atrás do texto, pessoa incluída — para o que fica NA FRENTE.
    Devolve {"lum": média, "dp": desvio-padrão, "pessoa": fração do retângulo coberta pela pessoa}."""
    am = est["am"]
    if am["kl"] is None:
        return None
    W, H = g.W, g.H
    kt, kl = am["kt"], am["kl"]
    sel = np.where((kt >= t0 - 0.6) & (kt <= t1 + 0.6))[0]
    if not len(sel):
        sel = np.argsort(np.abs(kt - (t0 + t1) / 2))[:2]
    sw, sh = am["sw"], am["sh"]
    x0, y0, x1, y1 = rect
    X0, X1 = W / 2 + (x0 - W / 2) / s, W / 2 + (x1 - W / 2) / s
    Y0, Y1 = H - (H - y0) / s, H - (H - y1) / s
    a0 = int(d.limitar(X0 / W, 0, 1) * sw)
    a1 = max(a0 + 1, int(math.ceil(d.limitar(X1 / W, 0, 1) * sw)))
    b0 = int(d.limitar(Y0 / H, 0, 1) * sh)
    b1 = max(b0 + 1, int(math.ceil(d.limitar(Y1 / H, 0, 1) * sh)))
    a1, b1 = min(sw, a1), min(sh, b1)
    a0, b0 = min(a0, a1 - 1), min(b0, b1 - 1)
    soma = soma2 = peso = pes = 0.0
    n = 0
    for i in sel:
        reg = kl[i, b0:b1, a0:a1]
        if am["mk"] is not None:
            j = int(np.argmin(np.abs(am["mk"][0] - kt[i])))
            w = 1.0 - am["mk"][1][j, b0:b1, a0:a1].astype(np.float32) / 255.0
        else:
            w = np.ones_like(reg)
            fx0, fy0, fx1, fy1 = g.rosto.em(float(kt[i]))
            fh = fy1 - fy0
            gx0, gx1 = int(fx0 / W * sw) - a0, int(math.ceil(fx1 / W * sw)) - a0
            gy0, gy1 = int(max(0, fy0 - 0.5 * fh) / H * sh) - b0, int(math.ceil((fy1 + 0.3 * fh) / H * sh)) - b0
            w[max(0, gy0):max(0, gy1), max(0, gx0):max(0, gx1)] = 0.0
            if not atras:   # sem máscara: tronco estimado abaixo do queixo (ombros ~1,6 rosto para cada lado)
                fcx, fw_ = (fx0 + fx1) / 2, fx1 - fx0
                tx0, tx1 = int((fcx - 1.6 * fw_) / W * sw) - a0, int(math.ceil((fcx + 1.6 * fw_) / W * sw)) - a0
                ty0 = int((fy1 + 0.3 * fh) / H * sh) - b0
                w[max(0, ty0):, max(0, tx0):max(0, tx1)] = 0.0
        pes +=1.0 - float(w.mean())
        n += 1
        if not atras or w.sum() < 0.05 * w.size:
            w = np.ones_like(reg)
        soma += float((reg * w).sum())
        soma2 += float((reg * reg * w).sum())
        peso += float(w.sum())
    if peso <= 0:
        return None
    lum = soma / peso
    dp = math.sqrt(max(0.0, soma2 / peso - lum * lum))
    return {"lum": lum, "dp": dp, "pessoa": pes / max(1, n)}


def _decidir(forcado, lum, limiar):
    """1 = letras em tinta escura (fundo claro) · 0 = letras creme (fundo escuro)."""
    if forcado == "claras":
        return 0
    if forcado == "escuras":
        return 1
    if lum is None:
        return 0
    return 1 if lum > limiar else 0


# ================================================================== texto


def _metricas_serif(tam, peso=500):
    f = d.fonte(tam, peso, "serif")
    cap = -f.getbbox("H", anchor="ls")[1]
    acc = -f.getbbox("ÓÉÂ", anchor="ls")[1]
    desc = f.getbbox("ÇQJ", anchor="ls")[3]
    return f, cap, acc, desc


def _metricas(f):
    cap = -f.getbbox("H", anchor="ls")[1]
    desc = f.getbbox("gjpqyç,", anchor="ls")[3]
    return cap, desc


def _larg_esp(txt, f, esp):
    return f.getlength(txt) + esp * max(0, len(txt) - 1)


def _escrever_esp(dr, x, yb, txt, f, esp, fill=255):
    for i, ch in enumerate(txt):
        if ch != " ":
            dr.text((x + f.getlength(txt[:i]) + esp * i, yb), ch, font=f, fill=fill, anchor="ls")


def _quebras(titulo):
    """Opções de linhas do título: 1 linha ou 2 linhas (palavrinhas de até 2 letras vão com a seguinte)."""
    ps = titulo.split()
    blocos, cola = [], ""
    for i, p in enumerate(ps):
        if i < len(ps) - 1 and len(p) <= 2:
            cola = f"{cola} {p}".strip()
            continue
        blocos.append(f"{cola} {p}".strip())
        cola = ""
    if cola:
        blocos.append(cola)
    opcoes = [[" ".join(blocos)]]
    for k in range(1, len(blocos)):
        opcoes.append([" ".join(blocos[:k]), " ".join(blocos[k:])])
    return opcoes


def _tam_titulo(linhas, W, u):
    f = d.fonte(200, 500, "serif")
    larg = max(_larg_esp(l, f, TIT_ESP * 200) for l in linhas)
    return min(TIT_MAX * u, TIT_LARG * W * 200 / max(1.0, larg))


def _mascara_titulo(linhas, tam):
    """Máscara L do título (letras maiúsculas, espacejamento apertado) + medidas relativas à máscara."""
    f, cap, acc, desc = _metricas_serif(tam)
    esp = TIT_ESP * tam
    largs = [_larg_esp(l, f, esp) for l in linhas]
    w = int(math.ceil(max(largs) + 0.08 * tam))
    topo = acc if any(ch in ACENTOS for ch in linhas[0]) else cap
    bases = [topo + i * TIT_ENTRE * tam for i in range(len(linhas))]
    h = int(math.ceil(bases[-1] + desc + 0.02 * tam))
    img = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(img)
    for l, lw, yb in zip(linhas, largs, bases):
        _escrever_esp(dr, (w - lw) / 2, yb, l, f, esp)
    return img, {"bases": bases, "cap": cap, "topo_letra": topo - cap, "desc": desc}


def _quebrar(txt, f, larg, max_linhas):
    ps, cola = [], ""
    for p in txt.split():   # "a internet", "de capa": a palavrinha não fica sozinha no fim da linha
        if len(p.strip(".,!?;:")) <= 2 and not cola:
            cola = p
            continue
        ps.append(f"{cola} {p}".strip() if cola else p)
        cola = ""
    if cola:
        if ps:
            ps[-1] = f"{ps[-1]} {cola}"
        else:
            ps.append(cola)
    linhas, atual = [], ""
    for p in ps:
        teste = f"{atual} {p}".strip()
        if f.getlength(teste) <= larg or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    if len(linhas) > max_linhas or any(f.getlength(l) > larg for l in linhas):
        return None
    return linhas


def _bloco_texto(linhas, f, al, alinhar="esquerda", esp=0.0):
    """Máscara L de linhas de texto (anti-serrilhado) e a máscara da sombra (desfocada)."""
    cap, desc = _metricas(f)
    largs = [(_larg_esp(l, f, esp) if esp else f.getlength(l)) for l in linhas]
    pad = int(math.ceil(f.size * 0.5))
    w = int(math.ceil(max(largs))) + 2 * pad
    h = int(math.ceil(cap + al * (len(linhas) - 1) + desc)) + 2 * pad
    m = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(m)
    for i, (l, lw) in enumerate(zip(linhas, largs)):
        x = pad + (0 if alinhar == "esquerda" else (max(largs) - lw) if alinhar == "direita" else (max(largs) - lw) / 2)
        yb = pad + cap + i * al
        if esp:
            _escrever_esp(dr, x, yb, l, f, esp)
        else:
            dr.text((x, yb), l, font=f, fill=255, anchor="ls")
    sombra = m.filter(ImageFilter.GaussianBlur(max(1.0, f.size * 0.16)))
    return {"m": m, "s": sombra, "pad": pad, "w": max(largs), "h": cap + al * (len(linhas) - 1) + desc,
            "cap": cap}


# ================================================================== legenda própria (bloco editorial)


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
    """Bloco escuro alinhado à esquerda, Cormorant 700 creme, fio verde-limão no alto e a palavra falada
    em verde-limão. Fica a 65% da altura; desce só o necessário para nunca cobrir a boca."""

    def __init__(self, g, perfil):
        W, H = g.W, g.H
        u = _u(W, H)
        self.W, self.H, self.u = W, H, u
        self.fam = perfil.get("fonte", "serif")
        self.peso = int(perfil.get("peso", 700))
        self.tam = int(round(u * float(perfil.get("tamanho", 0.078))))
        self.tam_min = int(round(u * 0.060))
        self.cor = d.cor(perfil.get("cor", "#F8F7F0"))
        self.destaque = d.cor(perfil.get("destaque", "#D4ED80"))
        self.fundo = perfil.get("caixa", LEG_CAIXA) or LEG_CAIXA
        self.maius = bool(perfil.get("maiusculas", False))
        self.paginas = _paginas(g.palavras, int(perfil.get("max_caracteres", 22) or 22), 4)
        self.x = LEG_X * W
        self.larg_max = LEG_X1 * W - self.x
        self.px, self.pt, self.pb = 0.036 * u, 0.040 * u, 0.030 * u
        f = d.fonte(self.tam, self.peso, self.fam)
        self.cap, self.desc = _metricas(f)
        self.h = self.pt + self.cap + self.desc + self.pb
        self.fio_w, self.fio_h = 0.14 * u, max(2, int(round(0.0042 * u)))
        self.ys = [self.topo_padrao()] * len(self.paginas)
        self._med, self._caixa = {}, {}

    def topo_padrao(self):
        return LEG_TOPO * self.H

    def y_max(self):
        return LEG_BASE * self.H - self.h

    def fixar(self, g, est):
        """Posição de cada página, decidida UMA vez: 65% da altura; mais baixa (até a zona segura) se a
        boca da pessoa, com a câmera recuada, descer até a legenda."""
        H = self.H
        self.ys = []
        for pg in self.paginas:
            ts = np.arange(pg["inicio"] - 0.05, pg["fim"] + 1e-6, 0.1)
            boca = -1e9
            for t in ts:
                s = _s_no_tempo(est, float(t))
                r = g.rosto.em(float(t))
                b = r[1] + 0.80 * (r[3] - r[1])
                boca = max(boca, H + (b - H) * s)
            y = max(self.topo_padrao(), boca + 0.016 * H)
            self.ys.append(min(y, self.y_max()))

    def topo_em(self, t0, t1):
        """Topo mais alto da legenda entre t0 e t1 (para as chamadas não descerem até ela)."""
        ys = [y for pg, y in zip(self.paginas, self.ys) if pg["fim"] > t0 and pg["inicio"] < t1]
        return min(ys) if ys else None

    def base_em(self, t0, t1):
        """Base mais baixa da legenda entre t0 e t1 (o rodapé de chamadas começa abaixo dela)."""
        ys = [y for pg, y in zip(self.paginas, self.ys) if pg["fim"] > t0 and pg["inicio"] < t1]
        return (max(ys) + self.h) if ys else None

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
            self._med[i] = (txts, xs, f, caixa_w)
        return self._med[i]

    def _caixa_img(self, w):
        if w not in self._caixa:
            cx = d.painel(w, int(round(self.h)), raio=max(1, int(0.003 * self.u)), fundo=self.fundo)
            fio = Image.new("RGBA", (int(self.fio_w), self.fio_h), LIMA + (255,))
            cx.alpha_composite(fio, (int(round(0.024 * self.u)), int(round(0.012 * self.u))))
            self._caixa[w] = d.sombra(cx, raio=0.014 * self.u, opacidade=0.30, desloc=(0, int(0.007 * self.u)))
        return self._caixa[w]

    def desenhar(self, img, t):
        i = self._pagina(t)
        if i is None:
            return
        pg = self.paginas[i]
        txts, xs, f, caixa_w = self._medidas(i)
        ini, fim = pg["inicio"], pg["fim"]
        novo = i == 0 or ini - self.paginas[i - 1]["fim"] > 0.06
        acaba = i == len(self.paginas) - 1 or self.paginas[i + 1]["inicio"] - fim > 0.06
        a = d.saida(d.mapear(t, ini - 0.05, ini + 0.14)) if novo else 1.0
        if acaba:
            a *= 1 - d.entrada(d.mapear(t, fim - 0.14, fim))
        if a <= 0.003:
            return
        k = d.saida(d.mapear(t, ini - 0.05, ini + 0.22))
        y = self.ys[i]
        y_c = y + ((1 - k) * 0.010 * self.u if novo else 0.0)
        cx, (dx, dy) = self._caixa_img(caixa_w)
        d.colar_em(img, cx, (self.x + dx, y_c + dy), opacidade=a)
        j = None
        for jj, w in enumerate(pg["palavras"]):
            if t >= w["inicio"] - 0.03:
                j = jj
        cam = Image.new("RGBA", (caixa_w, int(round(self.h))), (0, 0, 0, 0))
        dr = ImageDraw.Draw(cam)
        base_y = self.pt + self.cap
        for jj, (xx, tx) in enumerate(zip(xs, txts)):
            dr.text((self.px + xx, base_y), tx, font=f, fill=self.destaque if jj == j else self.cor, anchor="ls")
        ddy = (1 - k) * 0.012 * self.u   # assenta (settle)
        d.colar_em(img, cam, (self.x, y_c + ddy), opacidade=a * (0.35 + 0.65 * k))


# ================================================================== câmera (recuo) e páginas


def _s_no_tempo(est, t):
    s = 1.0
    dur = est["dur"]
    for gr in est["grupos"]:
        if gr["s"] >= 0.9995:
            continue
        ki = 1.0 if gr["a"] - 0.75 <= 0.05 else d.suave(d.mapear(t, gr["a"] - 0.75, gr["a"] + 0.05))
        ko = 0.0 if gr["b"] + 0.8 >= dur - 0.05 else d.suave(d.mapear(t, gr["b"], gr["b"] + 0.8))
        s = min(s, 1 - (1 - gr["s"]) * ki * (1 - ko))
    return s


def _amostras_rosto(g, t0, t1):
    ts = np.arange(max(0.0, t0), max(max(0.0, t0) + 0.05, min(g.duracao, t1)) + 1e-6, 0.2)
    return ts, np.array([g.rosto.em(float(t)) for t in ts], dtype=float)


def _medir_capa(g, est, e, leg_h):
    """Tamanho e posição do título, recuo de câmera desejado e limites da câmera para esta capa."""
    W, H = g.W, g.H
    u = _u(W, H)
    mascara = est["mascara"]
    ini, fim = float(e["inicio"]), float(e["fim"])
    titulo = _txt(e.get("titulo")).upper()
    _, cx = _amostras_rosto(g, ini - 0.3, fim + 0.3)
    fh = cx[:, 3] - cx[:, 1]
    tops = _topos(est, g, ini - 0.3, fim + 0.3)
    topo_med = float(np.percentile(tops, 40))      # posição típica da cabeça (alvo da cobertura)
    topo_alto = float(np.percentile(tops, 5))      # cabeça no ponto mais alto (a 1ª linha fica inteira)
    topo_max = float(np.min(tops))                 # pico absoluto (inclinou para a câmera)
    if not mascara:
        topo_med = topo_alto
    boca = float(np.percentile(cx[:, 1] + 0.80 * fh, 95))
    y_leg = LEG_BASE * H - leg_h - 0.016 * H          # a boca precisa ficar acima disto
    s_boca = (H - y_leg) / max(1.0, H - boca)          # recuo máximo que a boca permite
    opcoes = _quebras(titulo)
    tams = [(_tam_titulo(o, W, u), -len(o), o) for o in opcoes]
    tam, _, linhas = max(tams)
    uma = len(linhas) == 1 and mascara
    if uma:        # 1 linha: é a linha que a cabeça cobre — vale o pico absoluto da cabeça
        topo_alto = topo_max
    while True:
        f, cap, acc, desc = _metricas_serif(int(round(tam)))
        b1 = TIT_Y0 * H + (acc if any(ch in ACENTOS for ch in linhas[0]) else cap)
        bases = [b1 + i * TIT_ENTRE * tam for i in range(len(linhas))]
        if mascara:   # a cabeça cobre a parte de baixo da última linha
            alvo = bases[-1] - (COBRE_2 if len(linhas) > 1 else COBRE_1) * cap
            # 1 linha: no pior instante, pelo menos 55% da altura da maiúscula fica visível
            livre = bases[0] + 0.10 * tam if len(linhas) > 1 else bases[0] - COBRE_MAX_1 * cap
        else:         # sem recorte: título inteiro acima da cabeça
            alvo = bases[-1] + 0.08 * tam + 0.014 * H
            livre = alvo
        desloc = 0.0
        if topo_med >= alvo:          # cabeça baixa (plano aberto): o título desce até encostar nela
            s = 1.0
            desloc = min(topo_med - alvo, 0.12 * H, max(0.0, topo_alto - livre))
        else:
            s = (H - alvo) / max(1.0, H - topo_med)
            s_pico = (H - livre) / max(1.0, H - topo_alto)
            if uma:   # a câmera recua o suficiente para o pico da cabeça não passar de 'livre'
                s = min(s, s_pico)
            s = max(s, S_MIN, min(1.0, s_boca))
            if s > 0.975 and (not uma or s_pico >= 0.999):
                s = 1.0
        cabeca = H - (H - topo_alto) * s - desloc      # ponto mais alto da cabeça, em relação ao título
        if cabeca >= livre - 0.004 * H or tam <= TIT_MIN * u + 0.5:
            break
        tam = max(TIT_MIN * u, tam * 0.94)
    mt, med = _mascara_titulo(linhas, int(round(tam)))
    y_mask = TIT_Y0 * H + desloc      # topo da máscara = topo visível da 1ª linha (acento ou maiúscula)
    return {"e": e, "ini": ini, "fim": fim, "titulo": titulo, "linhas": linhas, "tam": int(round(tam)),
            "mt": mt, "mt_x": int(round((W - mt.width) / 2)), "mt_y": y_mask,
            "tit_base": y_mask + med["bases"][-1], "tit_topo": TIT_Y0 * H + desloc,
            "s": s, "s_boca": s_boca, "desloc": desloc, "alvo": alvo, "livre": livre,
            "topo_med": topo_med, "topo_alto": topo_alto,
            "revista": _txt(e.get("revista")).upper(), "edicao": _txt(e.get("edicao")),
            "chamadas": _chamadas(e), "frase": _txt(e.get("frase")),
            "letras": _letras(e) or "auto", "lado": _lado(e) or "auto",
            "r_in": d.limitar(0.24 * (fim - ini), 0.75, 1.2), "r_out": d.limitar(0.14 * (fim - ini), 0.45, 0.65)}


def _grupos(lays, H):
    """Capas próximas (intervalo < JUNTA) formam uma página: câmera, moldura e lavagem seguram entre elas."""
    grupos = []
    for lay in lays:
        if grupos and lay["ini"] - grupos[-1]["b"] < JUNTA:
            gr = grupos[-1]
            gr["b"] = max(gr["b"], lay["fim"])
            gr["capas"].append(lay)
        else:
            grupos.append({"a": lay["ini"], "b": lay["fim"], "capas": [lay]})
    for gr in grupos:
        s = min(l["s"] for l in gr["capas"])
        s = max(s, min(1.0, max(l["s_boca"] for l in gr["capas"])), S_MIN)
        gr["s"] = 1.0 if s > 0.975 else s
        for l in gr["capas"]:
            l["grupo"] = gr
            if gr["s"] < l["s"] - 0.003:
                _assentar(l, gr["s"], H)
    return grupos


def _assentar(l, s, H):
    """A página recuou mais do que esta capa pedia: a cabeça ficou mais baixa, então o título desce
    junto (até 12% da altura) para a cabeça continuar cobrindo a parte de baixo da última linha."""
    topo = H - (H - l["topo_med"]) * s
    alto = H - (H - l["topo_alto"]) * s
    extra = min(topo - (l["alvo"] + l["desloc"]), 0.12 * H - l["desloc"], alto - (l["livre"] + l["desloc"]))
    if extra > 0.5:
        for k in ("mt_y", "tit_base", "tit_topo", "desloc"):
            l[k] += extra


def _cabeca_na_tela(g, est, t0, t1):
    """Extremos do rosto na tela (com a câmera) entre t0 e t1."""
    W = g.W
    ts, cx = _amostras_rosto(g, t0, t1)
    x0s, x1s = [], []
    for t, (x0, y0, x1, y1) in zip(ts, cx):
        s = _s_no_tempo(est, float(t))
        x0s.append(W / 2 + (x0 - W / 2) * s)
        x1s.append(W / 2 + (x1 - W / 2) * s)
    return float(np.percentile(x0s, 3)), float(np.percentile(x1s, 97))


def _encaixar(itens, larg, alt, tmax, tmin, peso, fam, max_linhas, entre, u, espaco=0.5):
    """Maior letra em que todos os itens cabem na coluna (larg x alt). Devolve (fonte, [linhas], altura)."""
    for ml in range(1, max_linhas + 1):
        tam = tmax
        while tam >= tmin - 0.0001:
            f = d.fonte(int(round(tam * u)), peso, fam)
            ls = [_quebrar(it, f, larg, ml) for it in itens]
            if all(l is not None for l in ls):
                cap, desc = _metricas(f)
                al = f.size * entre
                h = sum(cap + desc + al * (len(l) - 1) for l in ls) + f.size * espaco * (len(ls) - 1)
                if h <= alt:
                    return f, ls, h
            tam -= 0.002
    return None


def _rodape(g, lay, est, textos, tes, u):
    """Plano fechado (sem coluna ao lado do rosto): chamadas numa linha de rodapé logo abaixo da legenda,
    separadas por pontos verde-limão (como as chamadas de pé de capa)."""
    W, H = g.W, g.H
    t0, t1 = min(tes) - 0.2, lay["fim"] + 0.3
    base_leg = est["leg"].base_em(t0, t1) if est["leg"] else None
    y0 = (base_leg if base_leg is not None else 0.70 * H) + 0.018 * H
    y1 = LEG_BASE * H
    x0, larg = LEG_X * W, (LEG_X1 - LEG_X) * W
    for n in range(len(textos), 0, -1):
        tam = CH_MAX
        while tam >= CH_MIN - 0.0001:
            f = d.fonte(int(round(tam * u)), 600, "inter")
            cap, desc = _metricas(f)
            gap = f.size * 1.1
            al = f.size * 1.2
            linhas, atual, x = [], [], 0.0
            ok = True
            for tx in textos[:n]:
                w = f.getlength(tx)
                if w > larg:
                    ok = False
                    break
                extra = (gap if atual else 0.0) + w
                if atual and x + extra > larg:
                    linhas.append(atual)
                    atual, x = [], 0.0
                    extra = w
                atual.append((tx, x + (gap if atual else 0.0)))
                x += extra
            if atual:
                linhas.append(atual)
            h = cap + desc + al * (len(linhas) - 1)
            if ok and len(linhas) <= 2 and h <= y1 - y0:
                out, i = [], 0
                for li, ln in enumerate(linhas):
                    for j, (tx, xx) in enumerate(ln):
                        b = _bloco_texto([tx], f, al)
                        ponto = None
                        if j > 0:
                            r = max(2.0, f.size * 0.11)
                            ponto = (x0 + xx - gap / 2, y0 + li * al + cap * 0.55, r)
                        out.append({"b": b, "x": x0 + xx, "y": y0 + li * al, "te": tes[i], "i": i,
                                    "lado": "rodape", "ponto": ponto})
                        i += 1
                return out, n
            tam -= 0.002
    return [], 0


def _colunas(g, lay, est):
    """Posição das chamadas, da barra verde e da frase (pré-desenhadas, em máscaras)."""
    W, H = g.W, g.H
    u = _u(W, H)
    lay["itens"], lay["frase_b"], lay["barra"] = [], None, None
    chs, fr = lay["chamadas"], lay["frase"]
    if not chs and not fr:
        return
    ini, fim = lay["ini"], lay["fim"]
    tes = []
    for i, ch in enumerate(chs):
        te = ch["em"] if ch["em"] is not None else ini + 0.65 + 0.35 * i
        tes.append(d.limitar(te, ini + 0.3, max(ini + 0.3, fim - 1.0)))
    try:
        fr_em = float(lay["e"].get("frase_em")) if lay["e"].get("frase_em") is not None else None
    except (TypeError, ValueError):
        fr_em = None
    te_fr = fr_em if fr_em is not None else ((max(tes) + 0.45) if tes else ini + 0.9)
    te_fr = d.limitar(te_fr, ini + 0.3, max(ini + 0.3, fim - 1.0))
    t0 = min(tes + [te_fr]) - 0.2
    fx0, fx1 = _cabeca_na_tela(g, est, t0, fim)
    marg = 0.03 * W
    cols = {"esquerda": (COL_X0 * W, fx0 - marg), "direita": (fx1 + marg, COL_X1 * W)}
    yc0 = lay["tit_base"] + 0.07 * lay["tam"] + 0.03 * H
    topo_leg = est["leg"].topo_em(t0, fim + 0.3) if est["leg"] else None
    yc1 = (topo_leg if topo_leg is not None else LEG_TOPO * H) - 0.03 * H
    alt = yc1 - yc0
    larg = {k: v[1] - v[0] for k, v in cols.items()}
    lado = lay["lado"]
    if lado == "auto" or larg[lado] < COL_MIN * W:
        lado = "direita" if larg["direita"] >= larg["esquerda"] - 0.01 * W else "esquerda"
    outro = "esquerda" if lado == "direita" else "direita"
    tem_coluna = larg[lado] >= COL_MIN * W and alt >= 0.06 * H
    barra_h = max(2, int(round(0.0068 * u)))
    usado = 0.0
    rodape_usado = False
    x_col = cols[lado][0]
    cw = min(larg[lado], 0.34 * W)
    if chs:
        textos = [c["texto"] for c in chs]
        n, r = len(textos), None
        if tem_coluna:
            while n > 0:
                r = _encaixar(textos[:n], cw, alt - 0.03 * H, CH_MAX, CH_MIN, 600, "inter", 2, 1.12, u)
                if r:
                    break
                n -= 1
        if r and n < len(textos):
            itens_r, n_r = _rodape(g, lay, est, textos, tes, u)
            if n_r > n:
                r = None
        if r:
            f, ls, h = r
            al = f.size * 1.12
            y = yc0
            for i, linhas in enumerate(ls):
                b = _bloco_texto(linhas, f, al)
                lay["itens"].append({"b": b, "x": x_col, "y": y, "te": tes[i], "i": i, "lado": lado, "ponto": None})
                y += b["h"] + f.size * 0.5
            yb = y - f.size * 0.5 + f.size * 0.42
            lay["barra"] = {"x": x_col, "y": yb, "w": min(0.13 * u, cw * 0.7), "h": barra_h,
                            "te": tes[min(len(ls), len(tes)) - 1] + 0.25}
            usado = yb + barra_h - yc0 + 0.03 * H
        else:
            itens, n = _rodape(g, lay, est, textos, tes, u)
            lay["itens"] = itens
            rodape_usado = bool(itens)
        if n < len(textos):
            _aviso(f"capa em {ini:.2f}s: {len(textos) - n} chamada(s) não couberam e foram omitidas "
                   "(encurte os textos ou use menos chamadas).")
    # frase (Cormorant 600) na outra coluna; se não houver, embaixo das chamadas; se não, no rodapé
    if fr:
        destino = None
        if larg[outro] >= COL_MIN * W and alt >= 0.06 * H:
            cwf = min(larg[outro], 0.36 * W)
            r = _encaixar([fr], cwf, alt, FR_MAX, FR_MIN, 600, "serif", 3, 1.02, u)
            if r:
                destino = (cols[outro][0], r, yc1, False)
        if destino is None and tem_coluna and alt - usado > 0.05 * H:
            # embaixo das chamadas na mesma coluna, ou a coluna inteira se as chamadas foram para o rodapé
            r = _encaixar([fr], cw, alt - usado, FR_MAX, FR_MIN, 600, "serif", 3, 1.02, u)
            if r:
                destino = (x_col, r, yc1, False)
        if destino is None and not rodape_usado:
            base_leg = est["leg"].base_em(te_fr - 0.2, fim + 0.3) if est["leg"] else None
            y0 = (base_leg if base_leg is not None else 0.70 * H) + 0.016 * H
            r = _encaixar([fr], (LEG_X1 - LEG_X) * W, LEG_BASE * H - y0, FR_MAX, FR_MIN, 600, "serif", 1, 1.02, u)
            if r:
                destino = (LEG_X * W, r, y0 + r[2], True)
        if destino is None:
            _aviso(f"capa em {ini:.2f}s: a frase não coube ao lado do rosto nem no rodapé e foi omitida.")
        else:
            xf, (f, ls, h), yfim, rod = destino
            b = _bloco_texto(ls[0], f, f.size * 1.02)
            lay["frase_b"] = {"b": b, "x": xf, "y": yfim - b["h"], "te": te_fr,
                              "lado": "rodape" if rod else ("esquerda" if xf < W / 2 else "direita")}


def _topo_revista(g, lay):
    """Nome da revista e edição (máscaras L com espacejamento largo)."""
    W, H = g.W, g.H
    u = _u(W, H)
    lay["rev_b"], lay["ed_b"] = None, None
    tam = int(round(REV_TAM * u))
    larg_tot = (REV_X1 - REV_X0) * W
    if lay["edicao"]:
        fe = d.fonte(tam, 700, "inter")
        lay["ed_b"] = _bloco_texto([lay["edicao"]], fe, tam, esp=0.06 * tam)
        larg_tot -= lay["ed_b"]["w"] + 0.05 * W
    if lay["revista"]:
        tt = tam
        for tt in range(tam, int(round(0.035 * u)) - 1, -1):
            fr = d.fonte(tt, 500, "inter")
            if _larg_esp(lay["revista"], fr, 0.15 * tt) <= larg_tot:
                break
        lay["rev_b"] = _bloco_texto([lay["revista"]], d.fonte(tt, 500, "inter"), tt, esp=0.15 * tt)
    lay["rev_chave"] = (lay["revista"], lay["edicao"])
    cap = _metricas(d.fonte(tam, 500, "inter"))[0]
    lay["fio_y"] = REV_Y * H + cap + 0.0115 * H


def _cores(g, est):
    """Cor das letras por página (título, revista, lavagem) e por item, decidida UMA vez pelo brilho do
    fundo nos quadros-chave. Tudo binário (tinta escura OU creme): nada de cinza intermediário."""
    W, H = g.W, g.H
    for gr in est["grupos"]:
        forc = gr["capas"][0]["letras"]
        rect_top = (0.08 * W, TIT_Y0 * H, 0.92 * W, max(l["tit_base"] for l in gr["capas"]))
        lum = _lum(est, g, rect_top, gr["a"], gr["b"], gr["s"])
        gr["k"] = _decidir(forc, lum, LIMIAR_TIT)
        gr["lum"] = lum
        for lay in gr["capas"]:
            forc = lay["letras"]
            blocos = {}
            for it in lay["itens"]:
                blocos.setdefault(it["lado"], []).append(it)
            if lay["frase_b"]:
                blocos.setdefault("frase", []).append(lay["frase_b"])
            for nome, its in blocos.items():
                serif = nome == "frase"   # frase em serifa fina: pede mais contraste que as chamadas
                cmax, tmin = (CREME_MAX - 0.08, TINTA_MIN + 0.04) if serif else (CREME_MAX, TINTA_MIN)
                rect = (min(i["x"] for i in its), min(i["y"] for i in its),
                        max(i["x"] + i["b"]["w"] for i in its), max(i["y"] + i["b"]["h"] for i in its))
                # estes textos ficam NA FRENTE da pessoa: mede tudo o que fica atrás deles, pessoa incluída
                r = _fundo(est, g, rect, min(i["te"] for i in its), lay["fim"], gr["s"], atras=False)
                lum = r["lum"] if r else None
                k = _decidir(forc, lum, LIMIAR_TXT)
                placa = False
                if r is not None:   # fundo misturado, pessoa atrás ou brilho no meio-termo: placa escura
                    placa = (r["dp"] > PLACA_DP or r["pessoa"] > PLACA_PESSOA
                             or (k == 0 and lum > cmax) or (k == 1 and lum < tmin))
                if placa:
                    k = 0
                for it in its:   # tingidas uma vez (o quadro só recorta, desloca e cola)
                    it["k"], it["placa"] = k, placa
                    it["dbg"] = None if r is None else (round(r["lum"], 2), round(r["dp"], 2), round(r["pessoa"], 2))
                    it["cam"] = _texto_camada(it["b"], TINTA_CH if k else CREME, CREME if k else (0, 0, 0),
                                              0.40 if k else 0.85, placa)


# ================================================================== preparar


def preparar(g):
    mascara = bool(g.tem_mascara)
    est = {"capas": [], "grupos": [], "leg": None, "dur": g.duracao, "mascara": mascara}
    g.cache["_m16"] = est
    _amostrar(g, est)
    leg = g.plano.get("legenda") or {}
    if leg.get("ativa", True) and g.palavras:
        perfil = dict(INFO["legenda"])
        perfil.update(leg.get("perfil") or {})
        est["leg"] = _Legenda(g, perfil)
    leg_h = est["leg"].h if est["leg"] else 0.075 * g.H
    evs = sorted([e for e in g.plano["eventos"] if e.get("tipo") == "capa" and _txt(e.get("titulo"))],
                 key=lambda e: e["inicio"])
    lays = [_medir_capa(g, est, e, leg_h) for e in evs]
    est["grupos"] = _grupos(lays, g.H)
    if est["leg"]:
        est["leg"].fixar(g, est)
    for lay in lays:
        _topo_revista(g, lay)
        _colunas(g, lay, est)
    _cores(g, est)
    for gr in est["grupos"]:
        tb = max(l["tit_base"] for l in gr["capas"])
        if mascara:   # lavagem do alto: um pouco abaixo do título (a pessoa é recolocada por cima)
            gr["lav_fim"] = min(0.62 * g.H, max(0.36 * g.H, tb + 0.10 * g.H))
        else:         # sem recorte: para acima da cabeça (a cor nunca toca o rosto)
            tops = [float(np.percentile(_topos(est, g, l["ini"] - 0.3, l["fim"] + 0.5), 5)) for l in gr["capas"]]
            gr["lav_fim"] = max(0.2 * g.H, g.H - (g.H - min(tops)) * gr["s"] - 0.01 * g.H)
        gr["y_ocl"] = max(gr["lav_fim"], max(l["mt_y"] + l["mt"].height for l in gr["capas"])) + 2
        # nome da revista: trechos seguidos com o mesmo nome ficam parados (sem piscar)
        trechos = []
        for l in gr["capas"]:
            if trechos and trechos[-1]["chave"] == l["rev_chave"]:
                trechos[-1]["b"] = l["fim"]
            else:
                trechos.append({"a": l["ini"], "b": l["fim"], "chave": l["rev_chave"], "lay": l})
        gr["revistas"] = trechos
        k = gr["k"]
        gr["cor_tit"] = TINTA if k else CREME_TIT
        gr["cor_rev"] = TINTA_REV if k else CREME
        gr["cor_lav"] = LAV_CLARA if k else LAV_ESCURA
        gr["alfa_lav"] = LAV_ALFA_CLARA if k else LAV_ALFA_ESCURA
        for l in gr["capas"]:
            if l["rev_b"]:
                l["rev_cam"] = _tingir(l["rev_b"]["m"], gr["cor_rev"], 1.0)
            if l["ed_b"]:
                l["ed_cam"] = _tingir(l["ed_b"]["m"], gr["cor_rev"], 1.0)
    est["capas"] = lays


# ================================================================== recuo da câmera


def _redim(arr, w, h, area=True):
    if cv2 is not None:
        return cv2.resize(arr, (w, h), interpolation=cv2.INTER_AREA if area else cv2.INTER_LINEAR)
    modo = "RGBA" if arr.ndim == 3 and arr.shape[2] == 4 else ("RGB" if arr.ndim == 3 else "L")
    return np.asarray(Image.fromarray(np.ascontiguousarray(arr), modo).resize((w, h), Image.BOX if area else Image.BILINEAR))


def _borrar(a, sigma):
    """Desfoque gaussiano separável em imagens pequenas (numpy puro)."""
    if sigma <= 0.3:
        return a
    r = max(1, int(math.ceil(sigma * 2.5)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2).astype(np.float32)
    k /= k.sum()
    pad = [(r, r), (0, 0)] + [(0, 0)] * (a.ndim - 2)
    b = np.pad(a, pad, mode="edge")
    b = sum(k[i] * b[i:i + a.shape[0]] for i in range(2 * r + 1))
    pad = [(0, 0), (r, r)] + [(0, 0)] * (a.ndim - 2)
    c = np.pad(b, pad, mode="edge")
    return sum(k[i] * c[:, i:i + a.shape[1]] for i in range(2 * r + 1))


def _preencher(img, peso):
    """Tapa os buracos (peso 0) com as cores em volta (convolução normalizada em 3 escalas)."""
    out = img.copy()
    falta = peso < 0.5
    if not falta.any():
        return out
    for sg in (2.0, 5.0, 12.0):
        num = _borrar(img * peso[:, :, None], sg)
        den = _borrar(peso, sg)
        ok = falta & (den > 0.03)
        out[ok] = num[ok] / den[ok][:, None]
        falta = falta & ~ok
        if not falta.any():
            break
    if falta.any():
        out[falta] = (img * peso[:, :, None]).sum((0, 1)) / max(1e-3, peso.sum())
    return out


def _pena(cache, bw, bh, fw):
    k = ("m16pena", bw, bh, fw)
    if k not in cache:
        y = np.clip((np.arange(bh) + 0.5) / fw, 0, 1)
        x = np.arange(bw) + 0.5
        xl = np.clip(np.minimum(x, bw - x) / fw, 0, 1)
        p = np.minimum(y[:, None], xl[None, :])
        cache[k] = (p * p * (3 - 2 * p)).astype(np.float32)
    return cache[k]


def _cabeca_peq(c, nw, nh):
    """Sem recorte: área estimada da cabeça e dos ombros (para o fundo estendido não 'esticar' a pessoa)."""
    W, H = c.W, c.H
    x0, y0, x1, y1 = c.rosto
    fw, fh = x1 - x0, y1 - y0
    m = Image.new("L", (nw, nh), 0)
    sx, sy = nw / W, nh / H
    cxp = (x0 + x1) / 2
    dr = ImageDraw.Draw(m)
    dr.ellipse(((cxp - fw * 0.85) * sx, (y0 - fh * 0.75) * sy, (cxp + fw * 0.85) * sx, (y1 + fh * 0.5) * sy), fill=255)
    dr.rectangle(((cxp - fw * 1.6) * sx, (y1 + fh * 0.3) * sy, (cxp + fw * 1.6) * sx, nh), fill=255)
    return np.asarray(m, np.float32) / 255.0


def _fundo_estendido(c, arr, m, s):
    """Fundo em volta do vídeo encolhido: o quadro pequeno, sem a pessoa (buracos tapados com as cores
    em volta), estendido para cima e para os lados, escurecido nas pontas e desfocado. Devolve RGBA WxH."""
    W, H = c.W, c.H
    sw, sh = max(24, W // 14), max(42, H // 14)
    nw, nh = max(2, int(round(sw * s))), max(2, int(round(sh * s)))
    x0 = (sw - nw) // 2
    passo = max(1, W // (sw * 3))
    peq = _redim(np.ascontiguousarray(arr[::passo, ::passo, :3]), nw, nh).astype(np.float32)
    if m is not None:
        pm = _redim(np.ascontiguousarray(m[::passo, ::passo]), nw, nh).astype(np.float32) / 255.0
    else:
        pm = _cabeca_peq(c, nw, nh)
    peso = np.clip(1.0 - pm * 2.2, 0.0, 1.0)
    peq = _preencher(peq, peso)
    ext = np.pad(peq, ((sh - nh, 0), (x0, sw - nw - x0), (0, 0)), mode="edge")
    k = ("m16esc", sw, sh, nw, nh)
    if k not in c.g.cache:
        ys, xs = np.arange(sh)[:, None], np.arange(sw)[None, :]
        dist = np.maximum(np.maximum(np.clip((x0 - xs) / max(1, x0), 0, 1),
                                     np.clip((xs - (x0 + nw)) / max(1, sw - nw - x0), 0, 1)),
                          np.clip(((sh - nh) - ys) / max(1, sh - nh), 0, 1))
        c.g.cache[k] = (0.96 - 0.14 * dist)[:, :, None].astype(np.float32)
    ext = _borrar(ext * c.g.cache[k], max(0.8, sw * 0.05))
    ext4 = np.empty((sh, sw, 4), np.uint8)
    ext4[:, :, :3] = np.clip(ext, 0, 255)
    ext4[:, :, 3] = 255
    return _redim(ext4, W, H, area=False)


def _recuo(c, arr, m, s, y_need, parado=False):
    """Câmera recuada: vídeo encolhido ancorado embaixo; em volta, o fundo estendido SEM a pessoa,
    desfocado. arr é o quadro RGBA (numpy contíguo). Devolve (quadro RGBA numpy, máscara da pessoa na
    tela nas linhas 0..y_need ou None).
    parado=True (câmera segurando o recuo): o fundo desfocado quase não muda, então é refeito só a cada
    0,2 s (chave pelo instante, determinística) e reaproveitado nos quadros do meio."""
    W, H = c.W, c.H
    bw, bh = int(round(W * s)), int(round(H * s))
    ox, oy = (W - bw) // 2, H - bh
    grande = _redim(arr, bw, bh, area=False)
    fw = max(2, int(round(0.05 * W)))
    if parado:
        chave = (int(c.t * 5.0 + 1e-6), round(s, 4), W, H, m is not None)
        guardado = c.g.cache.get("m16fundo")
        if guardado is not None and guardado[0] == chave:
            fundo = guardado[1]
        else:
            fundo = _fundo_estendido(c, arr, m, s)
            c.g.cache["m16fundo"] = (chave, fundo)   # só o último: memória constante
        # copia do fundo só o que fica visível em volta do vídeo encolhido (o miolo é o vídeo)
        out = np.empty_like(fundo)
        out[:oy + fw] = fundo[:oy + fw]
        out[oy + fw:, :ox + fw] = fundo[oy + fw:, :ox + fw]
        out[oy + fw:, ox + bw - fw:] = fundo[oy + fw:, ox + bw - fw:]
    else:
        out = _fundo_estendido(c, arr, m, s)
        if not out.flags.writeable:
            out = out.copy()
    pena = _pena(c.g.cache, bw, bh, fw)
    out[oy + fw:H, ox + fw:ox + bw - fw] = grande[fw:, fw:bw - fw]
    for (ya, yb, xa, xb) in ((0, fw, 0, bw), (fw, bh, 0, fw), (fw, bh, bw - fw, bw)):
        a = pena[ya:yb, xa:xb][:, :, None]
        dst = out[oy + ya:oy + yb, ox + xa:ox + xb].astype(np.float32)
        src = grande[ya:yb, xa:xb].astype(np.float32)
        out[oy + ya:oy + yb, ox + xa:ox + xb] = (src * a + dst * (1 - a)).astype(np.uint8)
    mt = None
    if m is not None and y_need > 0:
        mt = np.zeros((y_need, W), np.uint8)
        r = y_need - oy
        if r > 0:
            rs = min(H, int(math.ceil(r / s)) + 2)
            mg = _redim(np.ascontiguousarray(m[:rs]), bw, max(1, int(round(rs * s))), area=False)[:r]
            rr = mg.shape[0]
            mt[oy:oy + rr, ox:ox + bw] = (mg.astype(np.float32) * pena[:rr]).astype(np.uint8)
    return out, mt


# ================================================================== desenho


def _tingir(m, cor, alfa):
    """Camada RGBA de uma cor só com a máscara L m (alfa 0-1)."""
    cam = Image.new("RGBA", m.size, cor + (0,))
    if alfa >= 0.997:
        cam.putalpha(m)
    else:
        lut = [int(v * alfa) for v in range(256)]
        cam.putalpha(m.point(lut))
    return cam


def _texto_camada(b, cor, sombra_cor, forca, placa=False):
    """Texto + sombra macia numa camada só (pré-desenhada). placa=True: o texto vai numa placa escura
    translúcida (mesmo idioma visual da legenda), para ler sobre a pessoa ou sobre fundo misturado."""
    if placa:
        w, h = b["m"].size
        f = b["pad"] / 0.5   # tamanho da letra
        px, py = 0.34 * f, 0.20 * f
        pw, ph = int(round(b["w"] + 2 * px)), int(round(b["h"] + 2 * py))
        cam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        pl = d.painel(pw, ph, raio=max(1, int(round(0.10 * f))), fundo=d.cor(LEG_CAIXA, PLACA_ALFA))
        cam.alpha_composite(pl, (int(round(b["pad"] - px)), int(round(b["pad"] - py))))
        cam.alpha_composite(_tingir(b["m"], CREME, 1.0))
        return cam
    cam = _tingir(b["s"], sombra_cor, forca)
    cam.alpha_composite(_tingir(b["m"], cor, 1.0))
    return cam


def _lavagem(base, y0, y1, perfil, cor, alfa, cache, fixo, livre=None):
    """Gradiente vertical de cor: a cor é colada com uma máscara de gradiente. Na intensidade cheia
    (fixo) a máscara fica pronta em cache; nas transições é feita de uma coluna esticada.
    livre (L, opcional): onde a lavagem pode pintar (255 = fundo, 0 = pessoa)."""
    y0, y1 = int(max(0, y0)), int(min(base.height, y1))
    if y1 - y0 < 2 or alfa <= 0.004:
        return
    n = y1 - y0
    k = ("m16lav", y0, y1, perfil.__name__, round(alfa, 3), base.width)
    msk = cache.get(k) if fixo else None
    if msk is None:
        a = np.clip(perfil(np.linspace(0, 1, n)) * alfa * 255, 0, 255).astype(np.uint8)
        msk = Image.fromarray(np.ascontiguousarray(a[:, None]), "L").resize((base.width, n), Image.NEAREST)
        if fixo:
            cache[k] = msk
    if livre is not None:
        msk = ImageChops.multiply(msk, livre.crop((0, y0, base.width, y1)))
    base.paste(cor + (255,), (0, y0, base.width, y1), msk)


def _perfil_topo(k):
    return (1 - k) ** 1.6


def _perfil_base(k):   # aplicada de 62% a 100% da altura (antes disso a lavagem é invisível)
    return ((0.06 + 0.38 * k) / 0.44) ** 1.8


def _moldura(base, W, H, u, prog, alfa):
    if alfa <= 0.004 or prog <= 0.004:
        return
    lw = max(1, int(round(0.0019 * u)))
    x0, x1 = int(round(MOL_X * W)), int(round((1 - MOL_X) * W))
    y0, y1 = int(round(MOL_Y * H)), int(round((1 - MOL_Y) * H))
    cor = CREME + (int(170 * alfa),)
    p = d.saida(prog)
    lx, ly = int((x1 - x0) * p), int((y1 - y0) * p)
    tiras = []
    if lx > 0:
        tiras.append(((x0, y0), (lx, lw)))                    # topo: esquerda → direita
        tiras.append(((x1 - lx, y1 - lw), (lx, lw)))          # base: direita → esquerda
    if ly > 0:
        tiras.append(((x1 - lw, y0), (lw, ly)))               # direita: cima → baixo
        tiras.append(((x0, y1 - ly), (lw, ly)))               # esquerda: baixo → cima
    for (x, y), (w, h) in tiras:
        base.alpha_composite(Image.new("RGBA", (w, h), cor), (x, y))


def _estado_capa(lay, t):
    """Presenças (0-1) dos elementos de uma capa no instante t."""
    ini, fim = lay["ini"], lay["fim"]
    if t < ini - 0.05 or t > fim + 0.05:
        return None
    r_in = d.suave(d.mapear(t, ini, ini + lay["r_in"]))
    r_out = d.suave(d.mapear(t, fim - lay["r_out"], fim))
    sai = d.entrada(d.mapear(t, fim - lay["r_out"] - 0.25, fim - lay["r_out"] + 0.12))
    return {"tit": r_in * (1 - r_out), "sai": sai}


def _entrada_item(t, te):
    return d.saida(d.mapear(t, te, te + 0.42))


def _colar_alfa(base, cam, xy, alfa):
    if alfa >= 0.996:
        d.colar_em(base, cam, xy)
    else:
        d.colar_em(base, cam, xy, opacidade=alfa)


def quadro(c):
    g = c.g
    est = g.cache.get("_m16")
    if est is None:
        preparar(g)
        est = g.cache["_m16"]
    t, W, H = c.t, c.W, c.H
    u = _u(W, H)
    s = _s_no_tempo(est, t)
    gr = next((gg for gg in est["grupos"] if gg["a"] - 0.35 <= t <= gg["b"] + 0.6), None)
    pag = 0.0
    if gr is not None:
        pin = d.saida(d.mapear(t, gr["a"] - 0.3, gr["a"] + 0.45)) if gr["a"] > 0.05 else d.saida(d.mapear(t, 0, 0.4))
        pout = d.suave(d.mapear(t, gr["b"] - 0.15, gr["b"] + 0.5))
        pag = pin * (1 - pout)
    vis = []
    for lay in (gr["capas"] if gr else ()):
        st = _estado_capa(lay, t)
        if st:
            vis.append((lay, st))
    if s >= S_FIM:   # recuo de menos de 0,2%: invisível, não vale redesenhar o quadro
        s = 1.0
    if s >= 1.0 and pag <= 0.003 and not vis:
        if est["leg"] is not None:
            est["leg"].desenhar(c.fonte, t)
        return c.fonte
    ativo = pag > 0.003 or bool(vis)
    y_lav = int(min(H, gr["y_ocl"])) if (ativo and gr is not None) else 0
    oclusao = ativo and est["mascara"] and c.mascara is not None
    if s < 1.0:
        arr = np.ascontiguousarray(np.asarray(c.fonte))
        m = None
        if c.mascara is not None:
            mm = c.mascara if c.mascara.size == (W, H) else c.mascara.resize((W, H), Image.BILINEAR)
            m = np.asarray(mm)
        parado = gr is not None and abs(s - gr["s"]) < 1e-5
        limpo, m_tela = _recuo(c, arr, m, s, y_lav if oclusao else 0, parado)
        base = Image.fromarray(limpo, "RGBA")
        livre = Image.fromarray(255 - m_tela, "L") if (oclusao and m_tela is not None and y_lav > 0) else None
    else:
        base = c.fonte
        livre = None
        if oclusao and y_lav > 0:
            mm = c.mascara if c.mascara.size == (W, H) else c.mascara.resize((W, H), Image.BILINEAR)
            livre = ImageChops.invert(mm.crop((0, 0, W, y_lav)))
    if ativo:
        # 1) lavagem do alto e título ATRÁS da pessoa: as duas só pintam onde não há pessoa (livre)
        fixo = pag >= 0.999
        _lavagem(base, 0, gr["lav_fim"], _perfil_topo, gr["cor_lav"], gr["alfa_lav"] * (1.0 if fixo else pag),
                 g.cache, fixo, livre)
        for lay, st in vis:
            r = st["tit"]
            if r <= 0.003:
                continue
            mt = lay["mt"]
            vh = int(round(mt.height * r))
            if vh < 1:
                continue
            x, y = lay["mt_x"], int(round(lay["mt_y"] - (1 - r) * 0.016 * H))
            ya, yb = max(0, y), min(H, y + vh)
            xa, xb = max(0, x), min(W, x + mt.width)
            if yb > ya and xb > xa:
                tm = mt.crop((xa - x, ya - y, xb - x, yb - y))
                if livre is not None and ya < livre.height:
                    lb = min(yb, livre.height)
                    sub = ImageChops.multiply(tm.crop((0, 0, xb - xa, lb - ya)), livre.crop((xa, ya, xb, lb)))
                    if lb < yb:
                        tm = tm.copy()
                        tm.paste(sub, (0, 0))
                    else:
                        tm = sub
                base.paste(gr["cor_tit"] + (255,), (xa, ya, xb, yb), tm)
        # 2) lavagem de baixo (suave, como na prévia)
        _lavagem(base, 0.62 * H, H, _perfil_base, BASE_ESC, BASE_ALFA * (1.0 if fixo else pag), g.cache, fixo)
        # 3) moldura, nome da revista, chamadas e frase (na frente)
        _moldura(base, W, H, u, d.mapear(t, gr["a"] - 0.25, gr["a"] + 0.55) if gr["a"] > 0.05
                 else d.mapear(t, 0, 0.6), 1 - d.suave(d.mapear(t, gr["b"] - 0.15, gr["b"] + 0.45)))
        for tr in gr["revistas"]:
            ra = d.saida(d.mapear(t, tr["a"] - 0.05, tr["a"] + 0.45)) * (1 - d.entrada(d.mapear(t, tr["b"] - 0.35, tr["b"])))
            if ra <= 0.004:
                continue
            lay = tr["lay"]
            dx = -(1 - d.saida(d.mapear(t, tr["a"] - 0.05, tr["a"] + 0.6))) * 0.02 * u
            y_rev = REV_Y * H
            if lay["rev_b"]:
                b = lay["rev_b"]
                _colar_alfa(base, lay["rev_cam"], (REV_X0 * W - b["pad"] + dx, y_rev - b["pad"]), ra)
            if lay["ed_b"]:
                b = lay["ed_b"]
                _colar_alfa(base, lay["ed_cam"], (REV_X1 * W - b["w"] - b["pad"] - dx, y_rev - b["pad"]), ra)
            if lay["rev_b"] or lay["ed_b"]:
                pf = d.saida(d.mapear(t, tr["a"] + 0.05, tr["a"] + 0.75))
                fw = int((REV_X1 - REV_X0) * W * pf)
                if fw > 0:
                    lw = max(1, int(round(0.0016 * u)))
                    base.alpha_composite(Image.new("RGBA", (fw, lw), gr["cor_rev"] + (int(120 * ra),)),
                                         (int(REV_X0 * W), int(lay["fio_y"])))
        for lay, st in vis:
            sai = st["sai"]
            for it in lay["itens"]:
                ke = _entrada_item(t, it["te"])
                ka = ke * (1 - sai)
                if ka <= 0.004:
                    continue
                b = it["b"]
                if it["lado"] == "rodape":
                    dx, dy = 0.0, (1 - ke) * 0.018 * u + sai * 0.01 * u
                else:
                    sentido = -1 if it["lado"] == "esquerda" else 1
                    dx, dy = sentido * (1 - ke) * 0.035 * u + sentido * sai * 0.02 * u, 0.0
                _colar_alfa(base, it["cam"], (it["x"] + dx - b["pad"], it["y"] + dy - b["pad"]), ka)
                if it.get("ponto"):
                    px, py, pr = it["ponto"]
                    cam = Image.new("RGBA", (int(2 * pr + 3), int(2 * pr + 3)), (0, 0, 0, 0))
                    ImageDraw.Draw(cam).ellipse((1, 1, 1 + 2 * pr, 1 + 2 * pr), fill=LIMA + (int(255 * ka),))
                    d.colar_em(base, cam, (px - pr - 1, py + dy - pr - 1))
            br = lay["barra"]
            if br:
                pb = d.saida(d.mapear(t, br["te"], br["te"] + 0.45)) * (1 - sai)
                bw = int(br["w"] * d.saida(d.mapear(t, br["te"], br["te"] + 0.5)))
                if pb > 0.004 and bw > 0:
                    base.alpha_composite(Image.new("RGBA", (bw, br["h"]), LIMA + (int(255 * pb),)),
                                         (int(br["x"]), int(br["y"])))
            fb = lay["frase_b"]
            if fb:
                ke = d.saida(d.mapear(t, fb["te"], fb["te"] + 0.5))
                ka = ke * (1 - sai)
                if ka > 0.004:
                    b = fb["b"]
                    dy = (1 - ke) * 0.018 * u
                    _colar_alfa(base, fb["cam"], (fb["x"] - b["pad"], fb["y"] + dy - b["pad"]), ka)
    if est["leg"] is not None:
        est["leg"].desenhar(base, t)
    return base
