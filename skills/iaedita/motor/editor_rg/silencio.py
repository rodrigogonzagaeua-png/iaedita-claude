"""Remover silêncios (caixinha do card): corta só as pausas sem fala, deixando um respiro natural.

Como decide o que é silêncio (sem achismo):
  1. mede o volume da voz a cada 10 ms;
  2. silêncio = trecho bem abaixo da fala (32 dB abaixo dos trechos mais altos) por pelo menos 0,55 s;
  3. deixa 0,12 s de respiro antes e depois de cada corte, e um fade de 15 ms no áudio (sem estalo).
Palavra que a transcrição de verdade (Whisper) ouviu nunca é cortada, mesmo dita baixo (duração limitada como na
legenda, para não segurar a pausa inteira); trecho que a transcrição não leu também não. Numa gravação muito
barulhenta usa os intervalos entre as palavras.

O vídeo cortado é montado em pedaços curtos (cada chamada cabe no limite de tempo do chat) e
os tempos da transcrição e do rosto são recalculados para o vídeo novo."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import numpy as np

from .midia import ffmpeg_bin, ffprobe_bin, fps_de_saida, linha_concat, sondar

MIN_PAUSA = 0.55     # pausa mínima (s) para cortar
FOLGA = 0.12         # respiro mantido de cada lado do corte (s)
FOLGA_FIM = 0.30     # respiro mantido depois da última fala (s)
PEDACO_MAX = 6.0     # duração máxima de cada pedaço montado por vez (s)
TENTATIVAS = 3       # tentativas por pedaço (e da junção) antes de seguir com o vídeo original
VERSAO = 2           # muda quando a montagem muda: pasta de motor antigo refaz a versão sem silêncio
PEDACO_MIN = 0.50    # combinar: pedaço sem palavra, mais curto que isto, encostado num corte de gaguejo, sai junto (respiro de 0,27-0,30 s sobrava no teste real IMG_8292)


MARGEM_VOZ = 0.10    # folga em volta de cada palavra quando o detector de voz corta pausa com barulho


def _trechos_de_voz(x16k: np.ndarray) -> list[list[float]] | None:
    """Trechos com fala segundo o detector de voz Silero que vem com o faster-whisper (None se não houver).
    Mesma configuração validada no teste real IMG_8292: silêncio mínimo 400 ms, folga 100 ms."""
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps
        r = get_speech_timestamps(x16k, VadOptions(min_silence_duration_ms=400, speech_pad_ms=100))
    except Exception:  # noqa: BLE001  sem o programa ou sem o modelo: segue só com o volume
        return None
    return [[s["start"] / 16000, s["end"] / 16000] for s in r]


def _audio_16k(video: str) -> np.ndarray:
    r = subprocess.run([ffmpeg_bin(), "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                        "-f", "s16le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


def detectar(video: str, palavras: list[dict] | None, min_pausa: float = MIN_PAUSA,
             folga: float = FOLGA, sem_legenda=None, proteger_palavras: bool = False) -> dict:
    """Devolve {"manter": [[ini, fim], ...], "cortes": [[ini, fim], ...], "removido": s, "metodo": ...}
    com tempos já alinhados aos quadros do vídeo (e "aviso" quando não há fala para medir)."""
    info = sondar(video)
    dur = info.duracao
    fps = fps_de_saida(info)
    palavras = palavras or []
    x = _audio_16k(video) if info.tem_audio else np.zeros(0, np.float32)
    hop = 160  # 10 ms
    n = len(x) // hop
    silencio = np.zeros(0, bool)
    metodo = "nenhum"
    if n > 50:
        db = 20 * np.log10(np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
        # um trecho só conta como silêncio se a vizinhança de 50 ms também for silenciosa
        viz = np.lib.stride_tricks.sliding_window_view(np.pad(db, 2, mode="edge"), 5).max(1)
        ref, piso = float(np.percentile(db, 95)), float(np.percentile(db, 10))
        if ref - piso >= 15:
            limiar = max(ref - 32.0, piso + 6.0)
            silencio = viz < limiar
            metodo = f"volume (limiar {limiar:.0f} dB; fala {ref:.0f} dB; fundo {piso:.0f} dB)"
            for a_, b_ in sem_legenda or []:  # trecho que a transcrição não leu é fala: nunca corta
                silencio[int(a_ * 100):int(np.ceil(b_ * 100))] = False
            if proteger_palavras and palavras:  # palavra que a transcrição ouviu nunca é cortada, mesmo baixa
                from .legenda import _fim_real
                for p in palavras:
                    silencio[int(p["inicio"] * 100):int(np.ceil(_fim_real(p) * 100))] = False
                metodo += " + palavras"
                voz = _trechos_de_voz(x)
                if voz is not None:  # barulho sem fala: sai quando o detector de voz E a transcrição concordam
                    livre = np.ones(n, bool)
                    for a_, b_ in voz + [[a, b] for a, b in sem_legenda or []]:
                        livre[int(a_ * 100):int(np.ceil(b_ * 100))] = False
                    for p in palavras:  # a palavra inteira, com folga
                        livre[max(0, int((p["inicio"] - MARGEM_VOZ) * 100)):int(np.ceil((p["fim"] + MARGEM_VOZ) * 100))] = False
                    livre[int(palavras[-1]["inicio"] * 100):int(np.ceil((palavras[-1]["fim"] + FOLGA_FIM) * 100))] = False
                    silencio = silencio | livre
                    metodo += " + detector de voz"
    if metodo == "nenhum" and palavras:  # barulho demais: usa os intervalos entre as palavras
        n = int(dur * 100)
        silencio = np.ones(n, bool)
        for p in palavras:
            silencio[int(p["inicio"] * 100):int(np.ceil(p["fim"] * 100))] = False
        for a, b in sem_legenda or []:  # trecho que a transcrição não leu é fala: nunca corta
            silencio[int(a * 100):int(np.ceil(b * 100))] = False
        metodo = "intervalos entre as palavras"
    if not len(silencio):  # sem fala para medir: nada a cortar (mesmas chaves do retorno normal)
        return {"manter": [[0.0, round(dur, 4)]], "cortes": [], "removido": 0.0, "duracao_original": round(dur, 3),
                "duracao_nova": round(dur, 3), "metodo": "sem áudio para medir", "fps": fps, "versao": VERSAO,
                "aviso": "Não há fala reconhecível para medir as pausas: nada foi cortado. Siga normalmente."}
    # trechos contínuos de silêncio
    bordas = np.flatnonzero(np.diff(np.concatenate([[0], silencio.astype(np.int8), [0]])))
    cortes = []
    for s_i, e_i in zip(bordas[::2], bordas[1::2]):
        s, e = s_i / 100.0, min(dur, e_i / 100.0)
        no_inicio, no_fim = s <= 0.02, e >= dur - 0.05
        if (no_inicio or no_fim) and e - s < 0.3:
            continue
        if not (no_inicio or no_fim) and e - s < min_pausa:
            continue
        a = 0.0 if no_inicio else s + folga
        b = dur if no_fim else e - folga
        if no_fim:
            a = s + FOLGA_FIM
        a, b = round(a * fps) / fps, round(b * fps) / fps
        if b - a >= 0.2:
            cortes.append([a, b])
    # o que sobra é mantido; sobras minúsculas entre dois cortes (estalo, clique) vão junto
    manter, t = [], 0.0
    for a, b in cortes:
        if a - t > 0.08:
            manter.append([t, a])
        t = b
    if dur - t > 0.08:
        manter.append([t, dur])
    if not manter:
        manter = [[0.0, dur]]
    restante = sum(b - a for a, b in manter)
    return {"manter": [[round(a, 4), round(b, 4)] for a, b in manter],
            "cortes": [[round(a, 3), round(b, 3)] for a, b in cortes],
            "removido": round(dur - restante, 2), "duracao_original": round(dur, 3),
            "duracao_nova": round(restante, 3), "metodo": metodo, "fps": fps, "versao": VERSAO}


def mapa_de_tempo(manter: list[list[float]]):
    """Função t_original -> t_no_video_cortado (pontos dentro de um corte vão para o ponto do corte)."""
    inicios = []
    acum = 0.0
    for a, b in manter:
        inicios.append(acum)
        acum += b - a

    def f(t: float) -> float:
        for (a, b), o in zip(manter, inicios):
            if t < a:
                return o
            if t <= b:
                return o + (t - a)
        return acum
    return f


def dentro(manter, t: float) -> bool:
    return any(a <= t <= b for a, b in manter)


def remapear_transcricao(tr: dict, manter, duracao_nova: float, apagar=()) -> dict:
    """apagar = índices das palavras que o corte de gaguejos tirou: saem da lista, do texto e dos segmentos.
    Palavra que só encostou num corte de silêncio nunca sai (pode ser fala com tempo estimado)."""
    f = mapa_de_tempo(manter)
    tr = json.loads(json.dumps(tr))
    apagar = set(apagar)
    if apagar:
        todas = tr.get("palavras", [])
        fica = [p for k, p in enumerate(todas) if k not in apagar]
        for s in tr.get("segmentos", []):
            antes = [p for p in todas if s["inicio"] <= p["inicio"] <= s["fim"]]
            depois = [p for p in fica if s["inicio"] <= p["inicio"] <= s["fim"]]
            if len(depois) < len(antes):
                s["texto"] = " ".join(p["texto"] for p in depois)
        tr["palavras"] = fica
        tr["texto"] = " ".join(p["texto"] for p in fica)
        tr["palavras_cortadas"] = len(todas) - len(fica)
    for lista in ("palavras", "segmentos"):
        for p in tr.get(lista, []):
            ini, fim = f(p["inicio"]), f(p["fim"])
            p["inicio"], p["fim"] = round(ini, 3), round(max(fim, ini + 0.05), 3)
    if tr.get("trechos_sem_legenda"):  # também nos tempos do vídeo novo
        tr["trechos_sem_legenda"] = [[round(f(a), 3), round(f(b), 3)] for a, b in tr["trechos_sem_legenda"]]
    tr["duracao"] = round(duracao_nova, 3)
    tr["silencios_removidos"] = True
    return tr


def combinar(det_s: dict, det_g: dict, palavras=None) -> dict:
    """Silêncios + gaguejos na linha do tempo do ORIGINAL: mantém só o que os dois mantêm. Sobra menor que 1 quadro
    sai junto. Com `palavras`, também sai o pedaço sem nenhuma palavra, mais curto que PEDACO_MIN, encostado num
    trecho do gaguejo: é o respiro de uma palavra cortada (ficaria piscando poucos quadros entre dois cortes)."""
    fps, dur = det_s["fps"], det_s["duracao_original"]
    bordas = [x for t in det_g.get("trechos", []) for x in (t["ini"], t["fim"])]
    meios = [(p["inicio"] + p["fim"]) / 2 for p in palavras or []]
    manter = []
    for a, b in det_s["manter"]:
        for c, d in det_g["manter"]:
            x, y = max(a, c), min(b, d)
            if y - x < 1 / fps:
                continue
            if (palavras is not None and y - x < PEDACO_MIN and not any(x <= m <= y for m in meios)
                    and any(abs(z - x) < 1e-3 or abs(z - y) < 1e-3 for z in bordas)):
                continue
            manter.append([x, y])
    cortes = [[a, b] for a, b in zip([0.0] + [m[1] for m in manter], [m[0] for m in manter] + [dur]) if b - a > 1e-6]
    restante = sum(b - a for a, b in manter)
    res = {"manter": manter, "cortes": [[round(a, 3), round(b, 3)] for a, b in cortes],
           "removido": round(dur - restante, 2), "duracao_original": dur, "duracao_nova": round(restante, 3),
           "metodo": f"{det_s['metodo']} + {det_g['metodo']}", "fps": fps, "trechos": det_g.get("trechos", []),
           "versao": VERSAO}
    avisos = [d["aviso"] for d in (det_s, det_g) if d.get("aviso")]
    if avisos:
        res["aviso"] = " ".join(avisos)
    return res


def remapear_rosto(ro: dict, manter) -> dict:
    f = mapa_de_tempo(manter)
    ro = json.loads(json.dumps(ro))
    am = [dict(s, t=round(f(s["t"]), 3)) for s in ro.get("amostras", []) if dentro(manter, s["t"])]
    ro["amostras"] = am or ro.get("amostras", [])[:1]
    return ro


def _fim_da_imagem(video: str, duracao: float) -> float:
    """Onde a IMAGEM acaba (o som pode durar mais): duração da faixa de vídeo, ou a do arquivo se não der para medir."""
    try:
        r = subprocess.run([ffprobe_bin(), "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=duration:stream_tags=DURATION", "-of", "json", str(video)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        st = json.loads(r.stdout)["streams"][0]
        txt = str(st.get("duration") or st.get("tags", {}).get("DURATION"))
        h, m, seg = (["0", "0"] + txt.split(":"))[-3:]  # no .mkv vem como hh:mm:ss.f
        return min(duracao, int(h) * 3600 + int(m) * 60 + float(seg))
    except Exception:  # noqa: BLE001
        return duracao


def montar_por_etapas(video: str, manter, saida: str, tempo_max: float = 40.0) -> dict:
    """Monta o vídeo sem os silêncios em pedaços de até 6 s (progresso salvo). Chame até concluido=True."""
    t0 = time.time()
    S = Path(saida)
    D = S.parent / "_silencio_partes"
    D.mkdir(parents=True, exist_ok=True)
    estf = D / "estado.json"
    info = sondar(video)
    fps = fps_de_saida(info)
    chave = [str(video), manter, fps, VERSAO]
    est = json.loads(estf.read_text(encoding="utf-8")) if estf.exists() else None
    if not est or est.get("chave") != chave:
        for f in D.glob("*"):
            f.unlink(missing_ok=True)
        pedacos = []
        for i, (a, b) in enumerate(manter):
            n_total = max(1, int(round((b - a) * fps)))
            por = max(1, int(PEDACO_MAX * fps))
            for k in range(0, n_total, por):
                pedacos.append({"ini": a + k / fps, "n": min(por, n_total - k),
                                "fade_in": k == 0 and a > 0.01, "fade_out": k + por >= n_total and b < info.duracao - 0.05,
                                "arq": f"c{len(pedacos):04d}.mkv", "feito": False})
        est = {"chave": chave, "pedacos": pedacos, "seg_por_pedaco": None}
        estf.write_text(json.dumps(est), encoding="utf-8")
    fim_img = _fim_da_imagem(video, info.duracao)
    feitos_nesta = 0
    for p in est["pedacos"]:
        if p["feito"]:
            continue
        previsto = (est["seg_por_pedaco"] or 12.0) * 1.2
        if feitos_nesta > 0 and time.time() - t0 + previsto > tempo_max:
            break
        if p.get("tentativas", 0) >= TENTATIVAS:  # a chamada anterior morreu no meio da 3ª tentativa
            return _desistir(D, f"o pedaço {p['arq']} não terminou em {TENTATIVAS} tentativas")
        p["tentativas"] = p.get("tentativas", 0) + 1
        estf.write_text(json.dumps(est), encoding="utf-8")  # conta ANTES de rodar
        t1 = time.time()
        d = p["n"] / fps
        af = ["aresample=48000"]
        if p["fade_in"]:
            af.append("afade=t=in:d=0.015")
        if p["fade_out"]:
            af.append(f"afade=t=out:st={max(0.0, d - 0.015):.4f}:d=0.015")
        af += ["apad", f"atrim=0:{d:.4f}"]
        # imagem com exatamente n quadros (repete o último se o som for mais longo), som com exatamente d segundos
        vf = f"fps={fps},tpad=stop_mode=clone:stop=-1,setpts=N/({fps}*TB),trim=end_frame={p['n']},format=yuv420p"
        if p["ini"] < fim_img - 1 / fps:
            entrada = ["-ss", f"{p['ini']:.4f}", "-i", str(video), "-map", "0:v:0", "-map", "0:a:0?"]
        else:  # pedaço só de som (depois do último quadro): a imagem repete o último quadro, não some
            entrada = ["-ss", f"{max(0.0, fim_img - 2 / fps):.4f}", "-i", str(video),
                       "-ss", f"{p['ini']:.4f}", "-i", str(video), "-map", "0:v:0", "-map", "1:a:0?"]
        cmd = [ffmpeg_bin(), "-v", "error", "-y", *entrada, "-vf", vf,
               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "15", "-af", ",".join(af),
               "-c:a", "pcm_s16le", str(D / p["arq"])]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            if p["tentativas"] >= TENTATIVAS:
                return _desistir(D, f"o pedaço {p['arq']} falhou {TENTATIVAS} vezes: {r.stderr[-300:]}")
            return {"concluido": False, "progresso": sum(q["feito"] for q in est["pedacos"]) / len(est["pedacos"]),
                    "detalhe": f"um pedaço falhou; tentando de novo ({p['tentativas']} de {TENTATIVAS} tentativas usadas)"}
        p["feito"] = True
        feitos_nesta += 1
        est["seg_por_pedaco"] = time.time() - t1
        estf.write_text(json.dumps(est), encoding="utf-8")
    feitos = sum(p["feito"] for p in est["pedacos"])
    if feitos < len(est["pedacos"]):
        return {"concluido": False, "progresso": feitos / len(est["pedacos"]),
                "detalhe": f"cortando os silêncios ({feitos}/{len(est['pedacos'])} pedaços)"}
    if est.get("juntar", 0) >= TENTATIVAS:
        return _desistir(D, f"a junção não terminou em {TENTATIVAS} tentativas")
    est["juntar"] = est.get("juntar", 0) + 1
    estf.write_text(json.dumps(est), encoding="utf-8")  # conta ANTES de rodar
    lista = D / "lista.txt"
    lista.write_text("".join(linha_concat(D / p["arq"]) for p in est["pedacos"]), encoding="utf-8")
    r = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                        "-c", "copy", str(S)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        if est["juntar"] >= TENTATIVAS:
            return _desistir(D, f"a junção falhou {TENTATIVAS} vezes: {r.stderr[-300:]}")
        return {"concluido": False, "progresso": 0.99,
                "detalhe": f"a junção falhou; tentando de novo ({est['juntar']} de {TENTATIVAS} tentativas usadas)"}
    for f in D.glob("*"):
        f.unlink(missing_ok=True)
    D.rmdir()
    return {"concluido": True, "arquivo": str(S)}


def _desistir(D: Path, motivo: str) -> dict:
    """Depois de 3 tentativas: limpa as partes e avisa quem chamou para seguir com o vídeo original."""
    for f in D.glob("*"):
        f.unlink(missing_ok=True)
    D.rmdir()
    return {"concluido": True, "falhou": motivo}
