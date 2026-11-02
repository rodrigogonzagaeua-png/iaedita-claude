"""Transcrição com o tempo de cada palavra (base das legendas e do ritmo de todos os estilos).

Ordem: faster-whisper -> openai-whisper -> texto do agente (tempos pela voz). O fluxo por etapas nunca usa o
openai-whisper: sem faster-whisper, vai direto ao texto do agente.
Saída transcricao.json: {"idioma", "metodo", "palavras":[{"texto","inicio","fim"}], "segmentos":[...]}"""
from __future__ import annotations

import json
import os
import re
import shutil
import ssl
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

import numpy as np

from .midia import extrair_audio, sha256_do_arquivo, sondar


# ---------------------------------------------------------------- modelo do faster-whisper (baixado em etapas)

ARQUIVOS_MODELO = ("config.json", "tokenizer.json", "vocabulary.txt", "preprocessor_config.json", "model.bin")
OPCIONAIS_MODELO = {"preprocessor_config.json"}  # só alguns modelos têm
HF_OFICIAL = "https://huggingface.co"
REVISAO_MODELO = {"Systran/faster-whisper-small": "536b0662742c02347bc0e980a01041f333bce120"}  # um ramo pode mudar; outro --modelo segue em main
SHA256_MODELO = {"Systran/faster-whisper-small": "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671"}  # do model.bin
RESERVA_HASH = 8  # segundos para conferir o model.bin na mesma chamada; sem isso, fica para o começo da próxima
AVISO_SEM_MODELO = ("Não consegui baixar o modelo de transcrição (sem internet?). Peça ao cliente o texto da fala e rode "
                    "o MESMO comando com --texto 'fala completa' (as legendas ficam com tempos estimados pela voz).")
AVISO_SEM_PROGRAMA = ("Não consegui instalar o programa de transcrição neste ambiente. NÃO rode pip (prende o chat): "
                      "peça ao cliente o texto da fala e rode o MESMO comando com --texto 'fala completa' "
                      "(as legendas ficam com tempos estimados pela voz).")
AVISO_TODAS_FALHARAM = ("A transcrição automática falhou em todos os trechos neste ambiente. NÃO rode pip nem analisar "
                        "(prende o chat): peça ao cliente o texto da fala e rode o MESMO comando com --texto 'fala "
                        "completa' (as legendas ficam com tempos estimados pela voz).")


def _repo_modelo(modelo: str) -> str:
    try:
        from faster_whisper.utils import _MODELS
        return _MODELS.get(modelo, modelo)
    except Exception:  # noqa: BLE001
        return modelo if "/" in modelo else f"Systran/faster-whisper-{modelo}"


def _pasta_modelo(modelo: str) -> Path:
    """Onde o modelo baixado por etapas fica (mesma pasta do modelo de recorte); sobrevive entre as chamadas."""
    base = Path(os.environ.get("EDITOR_RG_MODELOS") or Path.home() / ".cache" / "editor_rg")
    return base / _repo_modelo(modelo).replace("/", "--")


def modelo_local(modelo: str) -> str | None:
    """Caminho do modelo já baixado, sem usar a internet: a nossa pasta ou o cache do Hugging Face."""
    p = _pasta_modelo(modelo)
    if (p / "_completo").exists():
        return str(p)
    try:
        from faster_whisper.utils import download_model
        c = download_model(modelo, local_files_only=True)
        return c if (Path(c) / "model.bin").exists() else None  # download antigo cortado deixa a pasta sem o model.bin
    except Exception:  # noqa: BLE001
        return None


def baixar_modelo_por_etapas(modelo: str, tempo_max: float) -> dict:
    """Baixa o modelo aos pedaços sem passar de tempo_max segundos; a chamada seguinte retoma de onde parou.
    Devolve {"concluido": False, "progresso", "detalhe"} | {"concluido": True, "caminho"}
    | {"concluido": True, "erro"}."""
    t0 = time.time()
    pasta = _pasta_modelo(modelo)
    pasta.mkdir(parents=True, exist_ok=True)
    estf = pasta / "_baixando.json"
    est = json.loads(estf.read_text(encoding="utf-8")) if estf.exists() else {}
    est.setdefault("tamanhos", {})
    est.setdefault("ausentes", [])
    base = os.environ.get("HF_ENDPOINT", HF_OFICIAL).rstrip("/")
    repo = _repo_modelo(modelo)
    esperado = SHA256_MODELO.get(repo) if base == HF_OFICIAL else None  # espelho (HF_ENDPOINT) não é conferido
    try:  # os mesmos certificados que o huggingface_hub (httpx) usa: SSL_CERT_FILE, SSL_CERT_DIR ou os do certifi
        if os.environ.get("SSL_CERT_FILE"):
            ctx = ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])
        elif os.environ.get("SSL_CERT_DIR"):
            ctx = ssl.create_default_context(capath=os.environ["SSL_CERT_DIR"])
        else:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        ctx = None

    def feito(nome):
        for p in (pasta / nome, pasta / (nome + ".parte")):
            if p.exists():
                return p.stat().st_size
        return 0

    def promover(nome):
        """Dá o nome final ao arquivo inteiro; o model.bin errado é descartado e devolve o erro."""
        if nome == "model.bin" and esperado and sha256_do_arquivo(pasta / (nome + ".parte")) != esperado:
            (pasta / (nome + ".parte")).unlink(missing_ok=True)
            est["falhas_hash"] = est.get("falhas_hash", 0) + 1  # bytes novos não zeram esta conta
            return "o model.bin baixado não confere com o oficial"
        (pasta / (nome + ".parte")).replace(pasta / nome)
        return None
    antes = sum(feito(n) for n in ARQUIVOS_MODELO)
    erro = None
    for nome in ARQUIVOS_MODELO:
        final, parte = pasta / nome, pasta / (nome + ".parte")
        if final.exists() or nome in est["ausentes"]:
            continue
        ja = parte.stat().st_size if parte.exists() else 0
        if est["tamanhos"].get(nome) and ja >= est["tamanhos"][nome]:
            erro = promover(nome)
            if erro:
                break
            continue
        resta = tempo_max - (time.time() - t0)
        if resta < 8:
            break  # não cabe mais nesta chamada
        pedido = urllib.request.Request(f"{base}/{repo}/resolve/{REVISAO_MODELO.get(repo, 'main')}/{nome}",
                                        headers={"Range": f"bytes={ja}-", "User-Agent": "editor-rg"})
        try:  # espera curta: conexão congelada não pode levar a chamada além do limite
            with urllib.request.urlopen(pedido, timeout=min(5.0, resta - 3), context=ctx) as r:
                if r.status == 206:  # retomada aceita: "bytes ini-fim/total"
                    total = int(r.headers.get("Content-Range", "/0").rsplit("/", 1)[1])
                else:  # o servidor ignorou a retomada: recomeça este arquivo
                    if ja:  # recomeço conta ANTES de baixar de novo; o 3º vira desistência
                        est["recomecos"] = est.get("recomecos", 0) + 1
                        estf.write_text(json.dumps(est), encoding="utf-8")
                        if est["recomecos"] > 2:
                            erro = "o servidor não deixa retomar o download (proxy ou espelho)"
                            break
                    total, ja = int(r.headers.get("Content-Length") or 0), 0
                est["tamanhos"][nome] = total
                with open(parte, "ab" if ja else "wb") as f:
                    while time.time() - t0 < tempo_max - 3:
                        dado = r.read1(1 << 20)
                        if not dado:
                            break
                        f.write(dado)
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and nome in OPCIONAIS_MODELO:
                est["ausentes"].append(nome)
                continue
            if exc.code == 416:  # o pedaço guardado não bate com o arquivo do servidor: recomeça este arquivo
                parte.unlink(missing_ok=True)
            erro = f"HTTP {exc.code} em {nome}"
            break
        except Exception as exc:  # noqa: BLE001  sem internet, conexão caiu, servidor parou de responder
            erro = f"{type(exc).__name__}: {str(exc)[:160]}"
            break
        if est["tamanhos"].get(nome) and parte.stat().st_size >= est["tamanhos"][nome]:
            if nome == "model.bin" and esperado and tempo_max - (time.time() - t0) < RESERVA_HASH:
                break  # não cabe mais nesta chamada: a próxima confere antes de tudo
            erro = promover(nome)
            if erro:
                break
        elif time.time() - t0 < tempo_max - 3:  # a resposta acabou antes do fim, e ainda havia tempo
            erro = f"a conexão terminou antes do fim de {nome}"
            break
        else:
            break  # o tempo acabou no meio deste arquivo
    if all((pasta / n).exists() or n in est["ausentes"] for n in ARQUIVOS_MODELO):
        (pasta / "_completo").write_text("ok", encoding="utf-8")
        estf.unlink(missing_ok=True)
        return {"concluido": True, "caminho": str(pasta)}
    depois = sum(feito(n) for n in ARQUIVOS_MODELO)
    # falha de rede só desiste depois de 3 chamadas seguidas com erro e sem avançar nada (nunca repete sem fim)
    est["falhas"] = 0 if depois > antes else est.get("falhas", 0) + (1 if erro else 0)
    desistiu = bool(erro) and (est["falhas"] >= 3 or est.get("recomecos", 0) > 2 or est.get("falhas_hash", 0) >= 3)
    if desistiu:
        est["falhas"] = est["recomecos"] = est["falhas_hash"] = 0  # o próximo vídeo volta a ter as suas tentativas
    estf.write_text(json.dumps(est), encoding="utf-8")
    if desistiu:
        return {"concluido": True, "erro": erro}
    total = sum(est["tamanhos"].values()) or 1
    det = "baixando o modelo de transcrição (só na 1ª vez)"
    if "model.bin" in est["tamanhos"]:
        det += f": {depois / 1e6:.0f} de {total / 1e6:.0f} MB"
    return {"concluido": False, "progresso": min(depois / total, 0.99),
            "detalhe": det + (f" (rede falhou: {erro}; tentando de novo)" if erro else "")}


def _faster_whisper(audio: str, modelo: str, idioma: str):
    from faster_whisper import WhisperModel
    caminho = modelo_local(modelo)
    if caminho is None:  # baixar aqui, de uma vez, passaria do limite da chamada: quem baixa é transcrever_por_etapas
        raise RuntimeError("modelo de transcrição ainda não baixado")
    m = WhisperModel(caminho, device="cpu", compute_type="int8")
    # Entrega o áudio já decodificado (16 kHz, mono, float32): evita o leitor de áudio (PyAV) do faster-whisper,
    # que quebra em algumas versões instaladas no computador do chat.
    with wave.open(audio, "rb") as f:
        dados = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768.0
    segs, info = m.transcribe(dados, language=None if idioma == "auto" else idioma, word_timestamps=True,
                              vad_filter=True, beam_size=1,
                              initial_prompt=PROMPT_PT if idioma == "pt" else None)
    palavras, segmentos = [], []
    for s in segs:
        segmentos.append({"texto": s.text.strip(), "inicio": round(s.start, 3), "fim": round(s.end, 3)})
        for w in s.words or []:
            if w.word.strip():
                palavras.append({"texto": w.word.strip(), "inicio": round(w.start, 3), "fim": round(w.end, 3)})
    return palavras, segmentos, info.language


def _openai_whisper(audio: str, modelo: str, idioma: str):
    import whisper
    m = whisper.load_model(modelo)
    r = m.transcribe(audio, language=None if idioma == "auto" else idioma, word_timestamps=True)
    palavras, segmentos = [], []
    for s in r["segments"]:
        segmentos.append({"texto": s["text"].strip(), "inicio": round(s["start"], 3), "fim": round(s["end"], 3)})
        for w in s.get("words", []):
            if w["word"].strip():
                palavras.append({"texto": w["word"].strip(), "inicio": round(w["start"], 3), "fim": round(w["end"], 3)})
    return palavras, segmentos, r.get("language", idioma)


def regioes_de_voz(wav16k: str, limiar_db: float = -38.0, min_silencio: float = 0.25):
    """Trechos com voz pela energia do áudio (sem modelo). Lista de (inicio, fim)."""
    with wave.open(wav16k, "rb") as f:
        sr = f.getframerate()
        x = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768
    jan = int(sr * 0.03)
    n = len(x) // jan
    if n == 0:
        return []
    rms = np.sqrt((x[: n * jan].reshape(n, jan) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    ref = np.percentile(db, 95)
    voz = db > max(limiar_db, ref - 30)
    regs, ini = [], None
    for i, v in enumerate(voz):
        t = i * 0.03
        if v and ini is None:
            ini = t
        elif not v and ini is not None:
            regs.append([ini, t])
            ini = None
    if ini is not None:
        regs.append([ini, n * 0.03])
    juntas = []
    for r in regs:
        if juntas and r[0] - juntas[-1][1] < min_silencio:
            juntas[-1][1] = r[1]
        else:
            juntas.append(r)
    return [(a, b) for a, b in juntas if b - a > 0.12]


def palavras_de_texto(texto: str, regioes, inicio=None, fim=None):
    """Distribui as palavras de um texto pelos trechos com voz, proporcional ao tamanho de cada palavra."""
    ws = texto.split()
    if not ws:
        return []
    if inicio is not None and fim is not None:
        regioes = [(max(a, inicio), min(b, fim)) for a, b in regioes if b > inicio and a < fim] or [(inicio, fim)]
    total_voz = sum(b - a for a, b in regioes) or 1.0
    pesos = np.array([len(re.sub(r"\W", "", w)) + 1.5 for w in ws], np.float64)
    marcos = np.concatenate([[0], np.cumsum(pesos) / pesos.sum() * total_voz])

    def tempo(d):
        acc = 0.0
        for a, b in regioes:
            if d <= acc + (b - a):
                return a + (d - acc)
            acc += b - a
        return regioes[-1][1]
    return [{"texto": w, "inicio": round(tempo(marcos[i]), 3), "fim": round(tempo(marcos[i + 1]) - 0.02, 3)}
            for i, w in enumerate(ws)]


def transcrever(video: str, saida: str, modelo: str = "small", idioma: str = "pt",
                texto_manual: str | None = None, segmentos_manuais: list | None = None, so_reserva: bool = False) -> dict:
    pasta = Path(saida).parent
    wav = str(pasta / "_audio16k.wav")
    info = sondar(video)
    if not info.tem_audio or not extrair_audio(video, wav):
        res = {"ok": False, "metodo": None, "palavras": [], "segmentos": [], "aviso": "O vídeo não tem áudio."}
        Path(saida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return res
    erros = []
    palavras = segmentos = None
    metodo = lang = None
    if not (texto_manual or segmentos_manuais or so_reserva):
        for nome, fn in (("faster-whisper", _faster_whisper), ("openai-whisper", _openai_whisper)):
            try:
                palavras, segmentos, lang = fn(wav, modelo, idioma)
                metodo = f"{nome}:{modelo}"
                break
            except Exception as exc:  # noqa: BLE001
                erros.append(f"{nome}: {str(exc)[:200]}")
    if palavras is None:
        regs = regioes_de_voz(wav)
        if segmentos_manuais:
            palavras = []
            for s in segmentos_manuais:
                palavras += palavras_de_texto(s["texto"], regs, s.get("inicio"), s.get("fim"))
            segmentos = segmentos_manuais
            metodo = "segmentos-do-agente + tempos pela voz"
        elif texto_manual:
            palavras = palavras_de_texto(texto_manual, regs)
            segmentos = [{"texto": texto_manual, "inicio": regs[0][0] if regs else 0, "fim": regs[-1][1] if regs else info.duracao}]
            metodo = "texto-do-agente + tempos pela voz"
        else:
            res = {"ok": False, "metodo": None, "palavras": [], "segmentos": [], "erros": erros,
                   "regioes_de_voz": regs,
                   "aviso": (("A transcrição falhou (veja 'erros'). Se for falta de biblioteca: python3 -m pip install -q --disable-pip-version-check --timeout 8 --retries 1 faster-whisper e "
                              "rode analisar de novo. " if any("No module" not in e for e in erros) else
                              "Sem programa de transcrição neste ambiente: python3 -m pip install -q --disable-pip-version-check --timeout 8 --retries 1 faster-whisper e rode analisar de novo. ") +
                             "Sem internet: peça ao cliente o texto da fala e rode com --texto 'fala completa'.")}
            Path(saida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            return res
        lang = idioma
    res = {"ok": True, "metodo": metodo, "idioma": lang, "duracao": info.duracao,
           "palavras": palavras, "segmentos": segmentos, "erros": erros,
           "texto": " ".join(p["texto"] for p in palavras)}
    Path(saida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def corrigir(transcricao: dict, correcoes: dict[str, str]) -> dict:
    """Troca palavras mal reconhecidas (ex.: {"Instagran": "Instagram"}) mantendo os tempos."""
    if not correcoes:
        return transcricao
    mapa = {k.lower().strip(".,!?;: "): v.strip().rstrip(".,!?;:") for k, v in correcoes.items()}
    for p in transcricao.get("palavras", []):
        nucleo = p["texto"].strip(".,!?;:").lower()
        if nucleo in mapa:
            pont = p["texto"][len(p["texto"].rstrip(".,!?;:")):]
            p["texto"] = mapa[nucleo] + pont
    return transcricao


# ---------------------------------------------------------------- transcrição por etapas (cabe no limite de tempo do chat)

PROMPT_PT = "Transcrição em português do Brasil, com pontuação."


def janelas_de_fala(regs, dur: float, alvo: float = 30.0) -> list[tuple[float, float]]:
    """Divide o áudio em janelas de ~30 s, cortando no meio da maior pausa perto de cada corte."""
    cortes, pos = [0.0], 0.0
    while dur - pos > alvo * 1.3:
        lo, hi = pos + alvo * 0.75, pos + alvo * 1.25
        melhor = None
        for (_, b), (c, _) in zip(regs, regs[1:]):
            meio, pausa = (b + c) / 2, c - b
            if lo <= meio <= hi and (melhor is None or pausa > melhor[1]):
                melhor = (meio, pausa)
        corte = melhor[0] if melhor else pos + alvo
        cortes.append(round(corte, 3))
        pos = corte
    cortes.append(dur)
    return list(zip(cortes, cortes[1:]))


def _sem_faster_whisper(video: str, saida: str, modelo: str, idioma: str, motivo: str) -> dict:
    """Segue sem modelo (transcrever com so_reserva=True: nem passada única nem openai-whisper) e diz ao agente para usar --texto."""
    res = transcrever(video, saida, modelo=modelo, idioma=idioma, so_reserva=True)
    if not res.get("ok") and "erros" in res:  # (sem áudio mantém o aviso próprio)
        res["aviso"] = AVISO_SEM_MODELO
    res.setdefault("erros", []).append(f"faster-whisper: {motivo}")
    Path(saida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (Path(saida).parent / "_transcricao_parcial.json").unlink(missing_ok=True)
    return {"concluido": True, "resultado": res}


def transcrever_por_etapas(video: str, saida: str, tempo_max: float = 40.0, modelo: str = "small",
                           idioma: str = "pt") -> dict:
    """Faz o que couber em tempo_max segundos e guarda o progresso. Devolve {"concluido": bool, ...}.
    Chame de novo até concluido=True. Sem faster-whisper, devolve o aviso para usar --texto (sem passada única)."""
    t0 = time.time()
    pasta = Path(saida).parent
    parcial = pasta / "_transcricao_parcial.json"
    try:
        from faster_whisper import WhisperModel
    except Exception:  # noqa: BLE001
        res = transcrever(video, saida, modelo=modelo, idioma=idioma, so_reserva=True)
        if not res.get("ok") and "erros" in res:  # o preparar já tentou instalar: o aviso não pode mandar rodar pip
            res["aviso"] = AVISO_SEM_PROGRAMA
            Path(saida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"concluido": True, "resultado": res}
    wav = str(pasta / "_audio16k.wav")
    est = json.loads(parcial.read_text(encoding="utf-8")) if parcial.exists() else None
    if not est or est.get("video") != str(video):
        info = sondar(video)
        if not info.tem_audio or not extrair_audio(video, wav):
            res = {"ok": False, "metodo": None, "palavras": [], "segmentos": [], "aviso": "O vídeo não tem áudio."}
            Path(saida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            return {"concluido": True, "resultado": res}
        regs = regioes_de_voz(wav)
        est = {"video": str(video), "duracao": info.duracao, "janelas": janelas_de_fala(regs, info.duracao, alvo=20.0),
               "feitas": 0, "palavras": [], "segmentos": [], "idioma": idioma, "seg_por_janela": None}
    # o modelo (464 MB no "small") vem em etapas que cabem na chamada e retomam de onde pararam; baixado de uma vez
    # dentro do WhisperModel, passava do limite e o ambiente cortava a chamada sem imprimir nada
    caminho = modelo_local(modelo)
    if caminho is None:
        r = baixar_modelo_por_etapas(modelo, tempo_max - (time.time() - t0))
        if r.get("erro"):  # sem internet: segue pelo caminho reserva e diz ao agente o que fazer
            return _sem_faster_whisper(video, saida, modelo, idioma, f"não consegui baixar o modelo ({r['erro']})")
        # chamada que baixou não transcreve: a transcrição começa na próxima, com o tempo inteiro
        parcial.write_text(json.dumps(est, ensure_ascii=False), encoding="utf-8")
        return {"concluido": False, "progresso": 0.0, "detalhe": r.get("detalhe") or "modelo de transcrição baixado"}
    with wave.open(wav, "rb") as f:
        dados = np.frombuffer(f.readframes(f.getnframes()), np.int16).astype(np.float32) / 32768.0
    m = None
    nesta = 0  # cada chamada faz pelo menos uma janela (garante progresso)
    while est["feitas"] < len(est["janelas"]):
        a, b = est["janelas"][est["feitas"]]
        previsto = (est["seg_por_janela"] or 0.6) * (b - a) + 3
        if nesta > 0 and time.time() - t0 + previsto > tempo_max:
            break  # não cabe mais uma janela nesta chamada
        if m is None:
            try:
                m = WhisperModel(caminho, device="cpu", compute_type="int8")
            except Exception as exc:  # noqa: BLE001  modelo estragado: apaga o nosso (baixa de novo no próximo vídeo)
                if Path(caminho) == _pasta_modelo(modelo):
                    shutil.rmtree(caminho, ignore_errors=True)
                return _sem_faster_whisper(video, saida, modelo, idioma, f"o modelo não carregou: {str(exc)[:160]}")
        t1 = time.time()
        # logo depois de uma janela que falhou, o texto de antes dela não é o contexto desta (o modelo pulava a fala)
        falhou_antes = bool(est.get("falhas")) and est["falhas"][-1]["fim"] == a
        ultimo_txt = "" if falhou_antes else " ".join(p["texto"] for p in est["palavras"][-20:])
        n_pal, n_seg = len(est["palavras"]), len(est["segmentos"])
        try:
            segs, info = m.transcribe(dados[int(a * 16000): int(b * 16000)], language=None if idioma == "auto" else idioma,
                                      word_timestamps=True, vad_filter=True, beam_size=1,
                                      # no máximo 1 nova tentativa (a padrão faz até 6 e uma janela chegou a 53 s)
                                      temperature=(0.0, 0.5),
                                      initial_prompt=((PROMPT_PT if idioma == "pt" else "") + " " + ultimo_txt).strip() or None)
            fim_ant = est["palavras"][-1]["fim"] if est["palavras"] else 0.0
            for s in segs:
                est["segmentos"].append({"texto": s.text.strip(), "inicio": round(s.start + a, 3), "fim": round(s.end + a, 3)})
                for w in s.words or []:
                    ini, fim = round(w.start + a, 3), round(w.end + a, 3)
                    if w.word.strip() and ini >= fim_ant - 0.05:
                        est["palavras"].append({"texto": w.word.strip(), "inicio": ini, "fim": max(fim, ini + 0.05)})
                        fim_ant = fim
            est["idioma"] = info.language
        except Exception as exc:  # noqa: BLE001
            # repetir a mesma janela daria o mesmo erro para sempre: ela fica sem legenda, anotada, e seguimos
            del est["palavras"][n_pal:]
            del est["segmentos"][n_seg:]  # nada dela pela metade
            est.setdefault("falhas", []).append({"inicio": a, "fim": b, "erro": f"faster-whisper: {str(exc)[:200]}"})
        est["feitas"] += 1
        nesta += 1
        # usa a janela mais lenta já vista para prever a próxima (nenhuma chamada passa do limite)
        est["seg_por_janela"] = max(est["seg_por_janela"] or 0.0, (time.time() - t1) / max(b - a, 1.0))
        parcial.write_text(json.dumps(est, ensure_ascii=False), encoding="utf-8")
    if est["feitas"] < len(est["janelas"]):
        return {"concluido": False, "progresso": est["feitas"] / len(est["janelas"]),
                "detalhe": f"transcrição {est['feitas']}/{len(est['janelas'])} trechos"}
    falhas = est.get("falhas", [])
    erros = [f["erro"] for f in falhas]
    if falhas and len(falhas) == len(est["janelas"]):  # nenhuma janela deu certo: as janelas já foram as tentativas
        res = transcrever(video, saida, modelo=modelo, idioma=idioma, so_reserva=True)
        if not res.get("ok") and "erros" in res:
            res["aviso"] = AVISO_TODAS_FALHARAM
        res.setdefault("erros", []).extend(erros)
        Path(saida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        parcial.unlink(missing_ok=True)
        return {"concluido": True, "resultado": res}
    res = {"ok": True, "metodo": f"faster-whisper:{modelo}", "idioma": est["idioma"], "duracao": est["duracao"],
           "palavras": est["palavras"], "segmentos": est["segmentos"], "erros": erros,
           "texto": " ".join(p["texto"] for p in est["palavras"])}
    if falhas:  # trechos que falharam ficam sem legenda; o resto do vídeo segue normal
        res["trechos_sem_legenda"] = [[f["inicio"], f["fim"]] for f in falhas]
        res["aviso"] = ("A transcrição falhou em " + ", ".join(f"{f['inicio']:.0f}-{f['fim']:.0f} s" for f in falhas) +
                        ": esse trecho fica sem legenda. Não repita o comando; siga normalmente.")
    elif not res["palavras"]:
        res["aviso"] = "Nenhuma fala reconhecida. Se o vídeo tem fala, confira o áudio."
    Path(saida).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    parcial.unlink(missing_ok=True)
    return {"concluido": True, "resultado": res}
