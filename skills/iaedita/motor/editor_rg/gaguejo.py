"""Corte automático de gaguejos, muletas isoladas e frases recomeçadas (comando editar). Só os casos certos: o cliente não revisa.

  gaguejo  = a mesma palavra dita duas vezes seguidas, com menos de 0,5 s entre elas ("o o vídeo"):
             sai a 1ª, do começo dela até o começo da que fica.
  muleta   = "ahn", "hum", "éé", "tipo" ou "né" SOZINHA, com pelo menos 0,25 s de silêncio dos dois lados:
             sai do começo dela até 0,10 s antes da palavra seguinte. Colada na fala ("é tipo assim"), fica.
  recomeço = frase curta (< 6 s) largada e dita de novo em até 12 s, com o mesmo começo e indo além
             ("Hoje eu vou te mostrar... Hoje eu vou te mostrar como editar"): sai só a 1ª tentativa;
             a pausa entre as duas fica (quem tira pausa é o corte de silêncios, que mede o volume).
  repetição = frase inteira idêntica, com pelo menos 6 palavras e pausa clara: fica a 1ª ocorrência;
              saem as cópias consecutivas, sem ignorar acentos, negação ou indicações de ênfase.
Nunca corta: palavra seguida de pontuação ("muito, muito"; reticências e hífen contam como hesitação),
palavra que se repete de propósito (ênfase, número, riso), trecho que a transcrição não leu, nem nada
quando os tempos das palavras são estimados.
Ideia de nateherkai/hyperframes-student-kit (MIT): cut-mistakes/scripts/find-cut-candidates.mjs e
docs/EDITING-PLAYBOOK.md:48 (muleta só com silêncio dos dois lados)."""
from __future__ import annotations

import math
import re
import unicodedata

from .silencio import VERSAO

GAP_GAGUEJO = 0.5; PAUSA_TRECHO = 0.85; TRECHO_MAX = 16.0      # Herk :68 e :93
RECOMECO_DUR_MAX = 6.0; RECOMECO_DISTANCIA_MAX = 12.0           # Herk :121 (falso começo)
JACCARD_MIN = 0.45                                              # Herk :125 (confiança "high")
MARGEM_ANTES = 0.03; MARGEM_VIZINHA = 0.08; MARGEM = 0.02
CAUDA_RECOMECO = 0.15; CORTE_MIN = 0.10; TETO_FRACAO, TETO_MIN_S = 0.15, 3.0
PAUSA_MULETA = 0.25; FOLGA_MULETA = 0.10                        # silêncio dos dois lados; respiro antes da seguinte
FRASE_REPETIDA_MIN = 6; FRASE_REPETIDA_PAUSA_MAX = 3.0
TRANSCRICAO_REAL = ("faster-whisper", "openai-whisper")         # transcrever.py:272 e :446
MULETAS = frozenset("ahn hum humm hm hmm ee eee tipo ne".split())  # sem acento: "éé" -> "ee", "né" -> "ne"
PALAVRAS_COMUNS = frozenset("""
a o as os um uma uns umas de do da dos das em no na nos nas num numa por pelo pela pelos pelas para pra pro
com sem sobre ate entre ao aos e ou mas que se sim eu tu ele ela voce voces vc eles elas me te lhe mim ti
meu minha meus minhas teu tua seu sua seus suas nosso nossa isso isto esse essa esses essas este esta estes
estas aquele aquela aquilo la ali aqui ai entao tambem ja ainda so mais muito muita muitos muitas bem como
quando onde porque pois qual quem ser sou foi era sao estar estou estao estava ter tenho tem tinha ir vou vai
vamos fazer faz ta tao ne tipo assim ah eh hum uh olha cara gente coisa tudo todo toda todos todas nada
""".split())
REPETICAO_NORMAL = frozenset("""
a muito muita muitos muitas bem mais menos nunca sempre nao sim tao super ja vai vem corre calma olha pronto
isso exato claro bom boa ta ne oi tchau obrigado obrigada que se ha he hi rs kk kkk haha hahaha bla
zero um uma dois duas tres quatro cinco seis sete oito nove dez cem mil
""".split())


def normalizar(texto: str) -> str:
    """minúsculas e sem pontuação, COM acento: 'É,' -> 'é' (e ≠ é: "e é" é fala normal, não gaguejo)."""
    return re.sub(r"[\W_]", "", unicodedata.normalize("NFC", (texto or "").casefold()))


def sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def _pausa_marcada(texto: str) -> bool:
    t = (texto or "").strip()
    return not t.endswith(("...", "…", "-", "–", "—")) and bool(re.search(r"[^\w\s]$", t))


def _repete(pal, tk, j) -> bool:
    a, b = pal[j], pal[j + 1]
    return (bool(tk[j]) and tk[j] == tk[j + 1] and b["inicio"] - a["fim"] < GAP_GAGUEJO
            and not _pausa_marcada(a["texto"]) and sem_acento(tk[j]) not in REPETICAO_NORMAL
            and not any(c.isdigit() for c in tk[j])
            and min(a["fim"] - a["inicio"], b["fim"] - b["inicio"]) > 0.051)


def _muleta(pal, tk, i) -> bool:
    """Muleta sozinha: tem palavra depois e silêncio de PAUSA_MULETA dos dois lados (o começo do vídeo conta)."""
    if i + 1 >= len(pal) or sem_acento(tk[i]) not in MULETAS or pal[i]["fim"] - pal[i]["inicio"] <= 0.051:
        return False
    antes = pal[i]["inicio"] - (pal[i - 1]["fim"] if i else 0.0)
    return antes >= PAUSA_MULETA and pal[i + 1]["inicio"] - pal[i]["fim"] >= PAUSA_MULETA


def _trechos(pal) -> list[tuple[int, int]]:
    segs, ini = [], 0
    for k in range(1, len(pal)):
        if (pal[k]["inicio"] - pal[k - 1]["fim"] > PAUSA_TRECHO or re.search(r"[.!?…]$", pal[k - 1]["texto"].strip())
                or pal[k]["fim"] - pal[ini]["inicio"] >= TRECHO_MAX):
            segs.append((ini, k - 1))
            ini = k
    if pal:
        segs.append((ini, len(pal) - 1))
    return segs


def _sem_repeticao(tk, i0, i1) -> list[int]:
    """Índices de i0..i1 sem as repetições imediatas ("eu eu vou" conta como "eu vou")."""
    return [k for k in range(i0, i1 + 1) if not (k > i0 and tk[k] and tk[k] == tk[k - 1])]


def _recomeca(pal, tk, A, B) -> bool:
    (a0, a1), (b0, b1) = A, B
    if pal[a1]["fim"] - pal[a0]["inicio"] >= RECOMECO_DUR_MAX:
        return False
    ka = _sem_repeticao(tk, a0, a1)  # a 1ª tentativa costuma ter o tropeço que fez a pessoa recomeçar
    if pal[b0]["inicio"] - pal[a1]["fim"] > RECOMECO_DISTANCIA_MAX or (b1 - b0 + 1) < len(ka) + 2:
        return False
    ca = [sem_acento(tk[k]) for k in ka if tk[k] and sem_acento(tk[k]) not in PALAVRAS_COMUNS]
    cb = [sem_acento(t) for t in tk[b0:b1 + 1] if t and sem_acento(t) not in PALAVRAS_COMUNS]
    if sum(x == y for x, y in zip(ca[:4], cb[:4])) < 2 or not set(ca) <= set(cb):
        return False
    jan = set(cb[:len(ca) + 2])
    return len(set(ca) & jan) / len(set(ca) | jan) >= JACCARD_MIN


def _uniao(trechos) -> float:
    """Segundos cobertos pelos trechos (um trecho dentro de outro conta uma vez só)."""
    total, fim = 0.0, -math.inf
    for t in sorted(trechos, key=lambda t: t["ini"]):
        total += max(0.0, t["fim"] - max(t["ini"], fim))
        fim = max(fim, t["fim"])
    return total


def _frases_repetidas(pal, tk, sem_legenda) -> list[tuple[int, int]]:
    """Só cópias exatas de frases declarativas; a referência pode ser o fim da frase anterior.

    A pontuação delimita a frase, não uma pausa interna. A primeira ocorrência e seu contexto
    acompanham a série inteira para não perder uma negação, um 'repito' ou uma região não transcrita.
    """
    frases, inicio = [], 0
    for k, p in enumerate(pal):
        if re.search(r"[.!?…]$", p["texto"].strip()):
            frases.append((inicio, k))
            inicio = k + 1
    copias, origens = [], {}
    for (a0, a1), (b0, b1) in zip(frases, frases[1:]):
        n = b1 - b0 + 1
        ref = a1 - n + 1
        frase = tk[b0:b1 + 1]
        if n < FRASE_REPETIDA_MIN or ref < a0 or not all(frase) or tk[ref:a1 + 1] != frase:
            continue
        contexto, ref = origens.get(a0, (a0, ref))
        origens[b0] = (contexto, ref)
        if any(not pal[k]["texto"].strip().endswith(".") or pal[k]["texto"].strip().endswith("...")
               for k in (a1, b1)):
            continue
        if not PAUSA_TRECHO <= pal[b0]["inicio"] - pal[a1]["fim"] <= FRASE_REPETIDA_PAUSA_MAX:
            continue
        if max(pal[ref + n - 1]["fim"] - pal[ref]["inicio"], pal[b1]["fim"] - pal[b0]["inicio"]) >= RECOMECO_DUR_MAX:
            continue
        if len(set(frase)) < 4 or any(x == y for x, y in zip(frase, frase[1:])):
            continue
        if not any(sem_acento(t) not in PALAVRAS_COMUNS | REPETICAO_NORMAL for t in frase):
            continue
        if any(sem_acento(t) in {"repito", "repetindo", "repita"} for t in tk[contexto:b1 + 1]):
            continue
        if any(sem_acento(t) in {"nao", "nunca", "jamais", "nem", "sem"} for t in tk[contexto:ref]):
            continue
        if any("?" in p["texto"] or "!" in p["texto"] for p in pal[contexto:b1 + 1]):
            continue
        if any(p["fim"] - p["inicio"] <= 0.051 for p in pal[ref:b1 + 1]):
            continue
        if any(pal[k]["inicio"] < pal[k - 1]["fim"] - 1e-6 for k in range(ref + 1, b1 + 1)):
            continue
        if any(a < pal[b1]["fim"] and b > pal[ref]["inicio"] for a, b in sem_legenda or []):
            continue
        copias.append((b0, b1 + 1))
    return copias


def detectar(palavras: list[dict], duracao: float, fps: float, sem_legenda=None, *, metodo: str | None = None) -> dict:
    pal = palavras or []
    trechos, aviso = [], None
    if not str(metodo or "").startswith(TRANSCRICAO_REAL):
        if pal:
            aviso = ("A transcrição deste vídeo não tem o tempo exato de cada palavra: não cortei gaguejos, "
                     "para não cortar fala boa. Siga normalmente.")
    else:
        tk = [normalizar(p["texto"]) for p in pal]

        def aceitar(i0, i_fica, tipo, ate=math.inf):
            p0 = pal[i0]
            antes = max(0.0, p0["inicio"] - MARGEM_ANTES, pal[i0 - 1]["fim"] + MARGEM_VIZINHA if i0 else 0.0)
            s = math.ceil(antes * fps - 1e-6) / fps
            limite = pal[i_fica]["inicio"] - MARGEM if i_fica < len(pal) else duracao
            e = math.floor(min(limite, ate) * fps + 1e-6) / fps
            if (s < (p0["inicio"] + p0["fim"]) / 2 and e - s >= CORTE_MIN
                    and not any(a < e and b > s for a, b in sem_legenda or [])):
                trechos.append({"ini": round(s, 4), "fim": round(e, 4), "tipo": tipo,
                                "texto": " ".join(p["texto"] for p in pal[i0:i_fica]),
                                "indices": list(range(i0, i_fica))})
        i = 0
        while i < len(pal) - 1:
            j = i
            while j + 1 < len(pal) and _repete(pal, tk, j):
                j += 1
            if j > i:
                aceitar(i, j, "gaguejo")
            i = j + 1
        usados = {k for t in trechos for k in t["indices"]}
        for i in range(len(pal)):
            if i not in usados and _muleta(pal, tk, i):
                aceitar(i, i + 1, "muleta", ate=pal[i + 1]["inicio"] - FOLGA_MULETA)
        segs = _trechos(pal)
        for A, B in zip(segs, segs[1:]):
            if _recomeca(pal, tk, A, B):
                aceitar(A[0], B[0], "recomeco", ate=pal[A[1]]["fim"] + CAUDA_RECOMECO)
        if _uniao(trechos) > max(TETO_MIN_S, TETO_FRACAO * duracao):
            trechos = [t for t in trechos if t["tipo"] != "recomeco"]
            aviso = ("Muitas frases recomeçadas para cortar sozinho com segurança: cortei só as palavras repetidas "
                     "e as muletas.")
        # Igualdade de todos os tokens é uma regra separada: o teto dos recomeços continua igual.
        for i0, i_fica in _frases_repetidas(pal, tk, sem_legenda):
            aceitar(i0, i_fica, "repeticao", ate=pal[i_fica - 1]["fim"] + CAUDA_RECOMECO)
        # um gaguejo ou muleta dentro de uma tentativa que já sai não vira um corte à parte
        trechos = [t for t in trechos if not any(set(t["indices"]) < set(o["indices"]) for o in trechos)]
    trechos.sort(key=lambda t: t["ini"])
    manter, t = [], 0.0
    for c in trechos:
        if c["ini"] - t >= 1 / fps:
            manter.append([t, c["ini"]])
        t = max(t, c["fim"])
    if duracao - t >= 1 / fps:
        manter.append([t, duracao])
    manter = manter or [[0.0, duracao]]
    cortes = [[a, b] for a, b in zip([0.0] + [m[1] for m in manter], [m[0] for m in manter] + [duracao]) if b - a > 1e-6]
    restante = sum(b - a for a, b in manter)
    res = {"manter": [[round(a, 4), round(b, 4)] for a, b in manter],
           "cortes": [[round(a, 3), round(b, 3)] for a, b in cortes],
           "removido": round(duracao - restante, 2), "duracao_original": round(duracao, 3),
           "duracao_nova": round(restante, 3), "fps": fps, "trechos": trechos, "versao": VERSAO,
           "metodo": f"repetições pela transcrição ({metodo})" if str(metodo or "").startswith(TRANSCRICAO_REAL)
           else "sem corte de gaguejos (tempos estimados)"}
    if aviso:
        res["aviso"] = aviso
    return res
