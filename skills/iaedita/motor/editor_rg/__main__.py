"""Comandos do IAEdita (rode com:  python -m editor_rg <comando> ...).

  ambiente                              o que este computador tem (FFmpeg, recorte, transcrição, núcleos)
  analisar VIDEO --pasta P              dados do vídeo + folha de quadros + transcrição + rosto
  palavras --pasta P                    fala com o tempo de cada palavra (para escrever o plano)
  silencios --pasta P --remover sim|nao aplica a escolha "Remover silêncios" do card (repita até CONCLUÍDO)
  editar --pasta P --estilo ID [--pele sim|nao] [--trilha sim|nao]   editor automático (repita até CONCLUÍDO)
  recortar --pasta P                    máscara da pessoa (para estilos com elementos atrás dela)
  previa --pasta P [--tempos 1,4.5]     só alguns quadros do plano, numa folha (confira ANTES de renderizar)
  renderizar --pasta P --saida F.mp4    vídeo final (áudio, legenda, estilo, tamanho controlado) + conferência
  verificar F.mp4 --pasta P             confere duração, tamanho, áudio e gera a folha do resultado

A pasta de trabalho P guarda tudo da análise; uma nova edição (outro estilo) reaproveita a análise
e SEMPRE parte do vídeo original."""
from __future__ import annotations

import argparse
import errno
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import NoReturn


TEMPO_MAX_PADRAO = float(os.environ.get("EDITOR_RG_TEMPO_MAX", "40"))
_BAIXANDO_SEM_CONTAR = 8  # chamadas que só baixam o modelo de recorte sem gastar tentativa; com as 3, cobre uns 46 KB/s


def _comando_atual() -> str:
    return "python3 \"$ERG\" " + " ".join(f'"{x}"' if " " in x else x for x in sys.argv[1:])


def _em_andamento(r: dict, etapa: str):
    """Avisa, sem ambiguidade, que falta trabalho: o agente deve repetir o MESMO comando já."""
    out = {"concluido": False, "etapa": etapa, "progresso": f"{int(100 * r.get('progresso', 0))}%",
           "detalhe": r.get("detalhe")}
    print(json.dumps(out, ensure_ascii=False))
    print(f"⏳ EM ANDAMENTO ({out['progresso']}). Rode EXATAMENTE o mesmo comando de novo, agora: {_comando_atual()}\n"
          "   NÃO encerre sua resposta. NÃO use segundo plano (&, nohup) nem espera (sleep): o progresso está salvo.")


def _concluido(msg: str = ""):
    print("✅ CONCLUÍDO" + (f" — {msg}" if msg else ""))


_REPETIR_NAO = "Não repita o mesmo comando sem mudar nada."
_REGRA_ZERO = "Não tente consertar o motor e não mostre este erro ao cliente."


def _frase_de_acao(exc: BaseException) -> str:
    """O que o AGENTE deve fazer diante deste erro, em português simples (sem jargão)."""
    from .licenca import ErroLicenca
    if isinstance(exc, ErroLicenca):
        return str(exc) + ' Não repita o comando em sequência; preserve a edição.'
    cadeia, e = [], exc
    while e is not None and e not in cadeia:
        cadeia.append(e)
        e = e.__cause__ or e.__context__
    texto = " ".join(f"{x} {getattr(x, 'stderr', '') or ''}" for x in cadeia)
    if str(exc).startswith('Montagem interrompida:'):
        return 'Não deu para montar este estilo após três tentativas. Preserve o trabalho e ofereça outro estilo. ' + _REPETIR_NAO
    if str(exc).startswith('Instalação interrompida:'):
        return ("Não deu para instalar o que o motor precisa, mesmo depois de três tentativas. Diga ao cliente em uma "
                "frase que este computador não conseguiu preparar a edição e pare. " + _REPETIR_NAO + " " + _REGRA_ZERO)
    if any(isinstance(x, OSError) and x.errno == errno.ENOSPC for x in cadeia) or "No space left" in texto:
        return ("O disco deste computador encheu. Apague só arquivos grandes que VOCÊ criou nesta conversa e não usa "
                "mais (vídeos de teste, downloads), nunca o vídeo original nem a pasta de trabalho, e rode o mesmo "
                "comando uma vez. Se voltar, diga ao cliente em uma frase que o computador do chat ficou sem espaço.")
    if any(isinstance(x, MemoryError) for x in cadeia) or "allocate memory" in texto.lower():
        return ("Faltou memória. Rode o mesmo comando com EDITOR_RG_NUCLEOS=1 na frente "
                "(ex.: EDITOR_RG_NUCLEOS=1 python3 \"$ERG\" ...). Se faltar de novo, diga ao cliente em uma frase "
                "que o vídeo é pesado demais para este computador.")
    if "FFmpeg não encontrado" in texto:
        return ("O FFmpeg não está instalado. Rode uma vez: python3 -m pip install -q --disable-pip-version-check --timeout 8 --retries 1 imageio-ffmpeg e depois o mesmo comando. "
                "Se o pip falhar (sem internet), diga ao cliente que este computador não consegue editar vídeo e pare.")
    if isinstance(exc, FileNotFoundError) and exc.filename:
        return (f"Arquivo não encontrado: {exc.filename}. Se for o vídeo ou o plano, confira o caminho (use aspas "
                "se tiver espaço) e rode com o caminho certo; se for um arquivo da pasta de trabalho, preserve "
                "a edição existente e pare. Se precisar recomeçar, use o vídeo original em uma pasta nova, "
                "sem sobrescrever esta pasta. " + _REPETIR_NAO)
    if isinstance(exc, (subprocess.CalledProcessError, StopIteration)) or "Invalid data found" in texto \
            or "moov atom not found" in texto:
        return ("O vídeo parece corrompido ou sem imagem. Em renderizar (é o arquivo que o motor gerou): diga ao "
                "cliente em uma frase que não deu para gerar o vídeo neste estilo e ofereça outro estilo. Nos outros "
                "comandos (é o vídeo do cliente): peça em uma frase que ele envie de novo, de preferência em MP4. "
                + _REPETIR_NAO)
    onde = {(Path(f.filename).name, f.name) for f in traceback.extract_tb(exc.__traceback__)}
    if onde & {("plano.py", "carregar"), ("montar.py", "modulo_do_estilo")} or (
            isinstance(exc, KeyError) and exc.args[:1] in (("estilo",), ("inicio",), ("fim",))
            and onde & {("__main__.py", "cmd_previa"), ("__main__.py", "cmd_renderizar")}):
        return ("O plano.json tem um defeito (veja 'detalhe'). Corrija o plano: JSON válido em UTF-8, todo evento "
                "com inicio e fim em segundos, estilo com o id do card (ex.: 05-zoom-digital). Depois rode o mesmo "
                "comando. " + _REGRA_ZERO)
    if "Falha ao montar o áudio" in texto:
        return ("Falhou a mistura do som, e o motor já tentou sem limpeza de ruído e sem trilha. "
                "Rode renderizar mais uma vez (o progresso está salvo); se falhar de novo, diga ao cliente "
                "em uma frase que não deu para montar o som neste computador. " + _REGRA_ZERO)
    if str(exc).startswith(("Falha ao", "FFmpeg falhou", "FFmpeg parou")):
        return ("O FFmpeg falhou ao cortar, juntar ou gravar o vídeo. Rode o mesmo comando mais uma vez (o progresso "
                "está salvo). Se falhar de novo: em editar, diga ao cliente em uma frase que não deu para montar este estilo e ofereça outro; em recortar, siga o modo sem "
                "recorte do estilo; em renderizar, diga ao cliente em uma frase que não deu para montar este estilo "
                "e ofereça outro. " + _REGRA_ZERO)
    return ("O motor falhou neste passo. Rode o mesmo comando mais uma vez; se vier o mesmo erro, não insista: "
            "diga ao cliente em uma frase que este passo não deu certo neste computador. " + _REGRA_ZERO)


def _gravar_erro(exc: BaseException, pasta: str | None) -> str | None:
    """Registro em _erro.log; autorização inclui só diagnóstico seguro, sem argumentos."""
    texto = ""
    try:
        from .licenca import ErroLicenca
        if isinstance(exc, ErroLicenca):
            texto = (f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} autorizacao\n"
                     + json.dumps({'tipo': 'ErroLicenca', 'diagnostico': exc.diagnostico}, ensure_ascii=False) + '\n')
        else:
            texto = (f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(sys.argv)}\n"
                     + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        texto = texto.encode("utf-8", "replace").decode("utf-8")
    except Exception:  # noqa: BLE001
        texto = texto or f"{type(exc).__name__}\n"
    try:
        if pasta and Path(pasta).is_dir():
            log = Path(pasta) / "_erro.log"
            modo = "a" if not log.exists() or log.stat().st_size < 200_000 else "w"
            with open(log, modo, encoding="utf-8", errors="replace") as f:
                f.write(texto)
            return str(Path(pasta) / "_erro.log")
    except Exception:  # noqa: BLE001
        pass
    try:
        sys.stderr.write(texto)
    except Exception:  # noqa: BLE001
        pass
    return None


def _falhou(exc: Exception, a: argparse.Namespace) -> NoReturn:
    """Erro não tratado: ❌ ERRO e uma linha JSON {erro, detalhe, log} (sempre a última), código 1."""
    from .licenca import ErroLicenca
    if a.cmd in ('preparar-autorizacao', 'ativar-autorizacao') and not isinstance(exc, ErroLicenca):
        # Falhas locais inesperadas também podem carregar argumentos ou caminhos privados.
        exc = ErroLicenca('Não foi possível concluir a autorização neste ambiente. Preserve o projeto para verificar a falha.')
    tecnico = f"{type(exc).__name__}: {exc} {getattr(exc, 'stderr', '') or ''}".strip()
    dados = {"erro": _frase_de_acao(exc), "detalhe": tecnico[-300:],
             "log": _gravar_erro(exc, getattr(a, "pasta", None))}
    if isinstance(exc, ErroLicenca):
        dados['diagnostico'] = exc.diagnostico
    linha = json.dumps(dados, ensure_ascii=False)
    print("❌ ERRO", flush=True)
    print(linha.encode("utf-8", "replace").decode("utf-8"), flush=True)
    sys.exit(1)


def _ler(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _gravar(p: Path, dados):
    p.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_ambiente(a):
    # sem numpy ou Pillow estes módulos não carregam, e o ambiente responde do mesmo jeito: quem instala é o preparar
    try:
        from .recorte import backends_disponiveis
    except Exception:  # noqa: BLE001
        backends_disponiveis = lambda baixar=False: []  # noqa: E731
    try:
        from .midia import nucleos
    except Exception:  # noqa: BLE001
        nucleos = lambda: os.cpu_count() or 1  # noqa: E731
    res = {"python": platform.python_version(), "sistema": platform.platform(), "nucleos": nucleos()}
    try:
        from .midia import ffmpeg_bin
        res["ffmpeg"] = ffmpeg_bin()
    except Exception as exc:  # noqa: BLE001
        res["ffmpeg"] = shutil.which("ffmpeg")  # o erro pode ser só a falta do numpy
        if not res["ffmpeg"]:
            res["ffmpeg_erro"] = str(exc)
    libs = {}
    for m in ("numpy", "PIL", "cryptography", "cv2", "onnxruntime", "faster_whisper", "whisper", "mediapipe", "rembg"):
        try:
            mod = __import__(m)
            libs[m] = getattr(mod, "__version__", "ok")
        except Exception:  # noqa: BLE001
            libs[m] = None
    res["bibliotecas"] = libs
    res["recorte"] = backends_disponiveis(baixar=a.testar_download)
    res["transcricao"] = ["faster_whisper"] if libs.get("faster_whisper") else ["texto do agente + tempos pela voz"]
    res["internet"] = _tem_internet()
    from .licenca import situacao_da_autorizacao
    # "internet" não diz isso: pypi passa e o servidor pode estar bloqueado
    res["autorizacao_alcancavel"], res["autorizacao_motivo"] = situacao_da_autorizacao(res["internet"])
    from . import MOTOR
    res["pele_disponivel"] = bool(libs["cv2"])
    trilhas = MOTOR / "trilhas" / "catalogo.json"
    pasta_t = MOTOR / "trilhas"
    res["trilha_disponivel"] = trilhas.exists() and (any(pasta_t.glob("*.m4a")) or any(pasta_t.glob("*.wav")))
    res["editor_automatico"] = True  # este motor tem editar; o card e o servidor usam o caminho novo
    sugestoes = []
    res["autorizacao_disponivel"] = bool(libs["cryptography"])
    if not libs["cryptography"]:
        sugestoes.append('python3 -m pip install -q --disable-pip-version-check --timeout 8 --retries 1 "cryptography>=46.0.0,<47"   (necessário antes de autorizar a edição)')
    if not res["ffmpeg"]:
        sugestoes.append("python3 -m pip install -q --disable-pip-version-check --timeout 8 --retries 1 imageio-ffmpeg")
    if not libs["faster_whisper"] and res["internet"]:
        sugestoes.append("python3 -m pip install -q --disable-pip-version-check --timeout 8 --retries 1 faster-whisper   (transcrição com tempo por palavra)")
    if not libs["onnxruntime"] and res["internet"]:
        sugestoes.append("python3 -m pip install -q --disable-pip-version-check --timeout 8 --retries 1 onnxruntime   (recorte da pessoa com RVM)")
    if not libs["cv2"] and res["internet"]:
        sugestoes.append("python3 -m pip install -q --disable-pip-version-check --timeout 8 --retries 1 opencv-python-headless   (achar o rosto)")
    res["instalar_se_puder"] = sugestoes
    res["caminho"] = "completo" if (res["recorte"] and not res["recorte"][0].endswith(")")) or res["internet"] else "leve"
    print(json.dumps(res, ensure_ascii=False, indent=1))


def _tem_internet():
    import threading
    import urllib.request
    alcancou = []

    def pedir(url):
        try:
            urllib.request.urlopen(url, timeout=4)
            alcancou.append(url)
        except Exception:  # noqa: BLE001
            pass
    for url in ("https://pypi.org/simple/pip/", "https://github.com"):
        pedido = threading.Thread(target=pedir, args=(url,), daemon=True)
        pedido.start()
        pedido.join(4)  # o timeout do urllib vale por leitura: resposta que goteja prenderia a chamada
        if alcancou:
            return True
    return False


_OBRIGATORIOS = ("numpy", "Pillow")  # sem eles o preparar não termina: o motor importa o numpy e a folha de quadros usa o Pillow


def _faltando() -> list[str]:
    """O que melhora a edição e não está neste computador (nomes do pip)."""
    import importlib
    pacotes = {"numpy": "numpy", "PIL": "Pillow", "cv2": "opencv-python-headless",
               "onnxruntime": "onnxruntime", "faster_whisper": "faster-whisper"}
    faltam = []
    for mod, pkg in pacotes.items():
        try:
            importlib.import_module(mod)
        except Exception:  # noqa: BLE001
            faltam.append(pkg)
    try:
        from .midia import ffmpeg_bin
        ffmpeg_bin()
    except Exception:  # noqa: BLE001
        faltam.append("imageio-ffmpeg")
    return faltam


def _instalar_um(pkg: str, segundos: float, log_arq: Path) -> bool:
    """Tenta instalar UM pacote em no máximo `segundos`. Nunca trava: estourou o tempo, desiste e segue sem ele."""
    import importlib
    import subprocess
    fim = time.time() + segundos
    with open(log_arq, "a", encoding="utf-8") as log:  # arquivo, não pipe: pip morto não prende a chamada
        for extra in ([], ["--user"], ["--break-system-packages"]):
            falta = fim - time.time()
            if falta < 3:
                return False
            try:
                r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check",
                                    "--no-input", "--prefer-binary", "--timeout", "8", "--retries", "1", *extra, pkg],
                                   stdout=log, stderr=subprocess.STDOUT, timeout=falta)
            except subprocess.TimeoutExpired:
                return False  # internet lenta: não cabe nesta chamada
            if r.returncode == 0:
                import site
                if site.ENABLE_USER_SITE:  # a pasta do usuário pode ter nascido agora: sem isso, só a próxima chamada a veria
                    site.addsitedir(site.getusersitepackages())
                importlib.invalidate_caches()
                return True
    return False


def _esquecer_video_anterior(P: Path) -> None:
    for f in ("transcricao.json", "rosto.json", "_transcricao_parcial.json", "_rosto_parcial.json", "analise.json",
              "mascara.mkv", "recorte.json", "folha_recorte.jpg", "opcoes.json", "_aviso_som.json"):
        (P / f).unlink(missing_ok=True)
    shutil.rmtree(P / "_versoes", ignore_errors=True)


def _esquecer_opcoes_se_outro_video(P: Path, video: str) -> None:
    """analisar com outro vídeo: a escolha do vídeo anterior não pode vencer o plano do novo"""
    try:
        an = _ler(P / "analise.json") or {}
    except ValueError:
        an = {}
    if video not in {an.get("video"), an.get("video_original")}:
        (P / "opcoes.json").unlink(missing_ok=True)
        (P / "_aviso_som.json").unlink(missing_ok=True)


def cmd_preparar(a):
    """Um comando só, em etapas de no máximo ~40 s: instala o que falta, transcreve a fala e acha o rosto.
    Repita o mesmo comando até aparecer CONCLUÍDO."""
    t0 = time.time()
    P = Path(a.pasta)
    P.mkdir(parents=True, exist_ok=True)
    resta = lambda: a.tempo_max - (time.time() - t0)  # noqa: E731
    estf = P / "_preparo.json"
    est = _ler(estf) or {}
    video = str(Path(a.video).resolve())
    if est.get("video") != video or a.refazer:
        _esquecer_video_anterior(P)
        est = {"video": video, "instalado": False, "transcrito": False, "rosto": False}
        _gravar(estf, est)
    if (P / "_versoes" / "ativa.txt").exists():  # o preparar sempre trabalha no ORIGINAL (nunca mistura tempos)
        _ativar_versao(P, "original")
    if not est["instalado"]:
        # um pacote por vez, com tempo-limite e até 3 tentativas (a seguinte aproveita o que o pip já baixou);
        # a tentativa é gravada ANTES: se o ambiente cortar a chamada, ela conta. O que não der fica para trás.
        tent = est.setdefault("tentativas", {})
        nesta = 0  # cada chamada faz pelo menos uma tentativa: com --tempo-max baixo nunca repete sem avançar
        while True:
            ausentes = _faltando()
            sem_saida = [p for p in _OBRIGATORIOS if p in ausentes and tent.get(p, 0) >= 3]
            if sem_saida:  # o resto só gastaria tempo; nada fica marcado: se o pacote aparecer, o mesmo comando segue
                raise RuntimeError(f"Instalação interrompida: {sem_saida[0]} não instalou em 3 tentativas (veja _instalacao.log).")
            faltam = [p for p in ausentes if tent.get(p, 0) < 3]
            if not faltam:
                break
            if nesta and resta() < 15:
                return _em_andamento({"progresso": 0.05, "detalhe": f"instalando ferramentas ({sum(tent.values())} "
                                      "tentativas feitas)"}, "preparar")
            pkg = faltam[0]
            tent[pkg] = tent.get(pkg, 0) + 1
            nesta += 1
            _gravar(estf, est)
            print(f"Instalando {pkg}…", flush=True)
            if _instalar_um(pkg, max(10.0, resta() - 8), P / "_instalacao.log"):
                est.setdefault("instalados", []).append(pkg)
            else:
                print(f"Aviso: não consegui instalar {pkg} a tempo (tentativa {tent[pkg]} de 3)."
                      + (" Sigo sem ele." if tent[pkg] >= 3 and pkg not in _OBRIGATORIOS else ""), flush=True)
            _gravar(estf, est)
        if not est.get("rvm_tentado"):  # já deixa baixado o modelo de recorte (15 MB), se couber no tempo
            if nesta and resta() < 15:  # chamada que já tentou instalar deixa o modelo para a próxima
                return _em_andamento({"progresso": 0.08, "detalhe": "ferramentas instaladas"}, "preparar")
            est["rvm_tentado"] = True
            _gravar(estf, est)
            try:
                from .recorte import baixar_rvm_por_etapas  # adianta o download; o recortar termina
                baixar_rvm_por_etapas(t0 + a.tempo_max - 10)
            except Exception:  # noqa: BLE001
                pass
        est["instalado"] = True
        est.setdefault("instalados", [])
        _gravar(estf, est)
        if resta() < 15:
            return _em_andamento({"progresso": 0.1, "detalhe": "ferramentas instaladas"}, "preparar")
    from .midia import folha_de_contato, sondar  # só agora: estes precisam do numpy que o passo acima pode ter instalado
    from .rosto import analisar_rosto_por_etapas
    from .transcrever import transcrever, transcrever_por_etapas
    # --texto/--segmentos depois de uma transcrição que falhou (aviso "rode com --texto") refaz a transcrição
    if not est["transcrito"] or ((a.texto or a.segmentos) and not (_ler(P / "transcricao.json") or {}).get("ok")):
        if a.texto or a.segmentos:
            transcrever(video, str(P / "transcricao.json"), modelo=a.modelo, idioma=a.idioma, texto_manual=a.texto,
                        segmentos_manuais=_ler(Path(a.segmentos)) if a.segmentos else None)
        else:
            r = transcrever_por_etapas(video, str(P / "transcricao.json"), tempo_max=max(10.0, resta()),
                                       modelo=a.modelo, idioma=a.idioma)
            if not r["concluido"]:
                return _em_andamento({"progresso": 0.1 + 0.6 * r["progresso"], "detalhe": r["detalhe"]}, "preparar")
        est["transcrito"] = True
        _gravar(estf, est)
        shutil.rmtree(P / "_versoes", ignore_errors=True)  # versões feitas com a transcrição antiga
    if not est["rosto"]:
        if resta() < 8:
            return _em_andamento({"progresso": 0.7, "detalhe": "fala transcrita"}, "preparar")
        r = analisar_rosto_por_etapas(video, str(P / "rosto.json"), tempo_max=max(8.0, resta()))
        if not r["concluido"]:
            return _em_andamento({"progresso": 0.7 + 0.25 * r["progresso"], "detalhe": r["detalhe"]}, "preparar")
        est["rosto"] = True
        _gravar(estf, est)
        shutil.rmtree(P / "_versoes", ignore_errors=True)  # versões feitas com rosto antigo
    info = sondar(video)
    tr = _ler(P / "transcricao.json") or {}
    ro = _ler(P / "rosto.json") or {}
    folha = folha_de_contato(video, str(P / "folha_original.jpg"), 5, 2, 260)
    analise = {"video": video, "info": info.para_dict(), "folha": folha, "transcricao_ok": tr.get("ok"),
               "transcricao_metodo": tr.get("metodo"), "palavras": len(tr.get("palavras", [])),
               "rosto": {"metodo": ro.get("metodo"), "cobertura": ro.get("cobertura"), **(ro.get("tamanho_medio") or {})},
               "instalados": est.get("instalados", [])}
    _gravar(P / "analise.json", analise)
    print(json.dumps(analise, ensure_ascii=False, indent=1))
    if tr.get("aviso"):
        print("AVISO:", tr["aviso"])
    if (ro.get("cobertura") or 0) < 0.5:
        print("AVISO: o rosto apareceu em poucos quadros; confira na folha se nada cobre o rosto.")
    print("Olhe a folha de quadros:", folha)
    _concluido("abra o card (abrir_galeria_de_estilos) e chame aguardar_escolha")


def cmd_analisar(a):
    from .midia import folha_de_contato, sondar
    from .rosto import analisar_rosto
    from .transcrever import transcrever
    P = Path(a.pasta)
    P.mkdir(parents=True, exist_ok=True)
    _esquecer_opcoes_se_outro_video(P, str(Path(a.video).resolve()))
    t0 = time.time()
    info = sondar(a.video)
    analise = {"video": str(Path(a.video).resolve()), "info": info.para_dict()}
    folha = folha_de_contato(a.video, str(P / "folha_original.jpg"), 5, 2, 260)
    anterior = _ler(P / "transcricao.json")
    if not anterior or not anterior.get("ok") or a.refazer:  # transcrição que falhou nunca é reaproveitada
        tr = transcrever(a.video, str(P / "transcricao.json"), modelo=a.modelo, idioma=a.idioma,
                         texto_manual=a.texto,
                         segmentos_manuais=_ler(Path(a.segmentos)) if a.segmentos else None)
    else:
        tr = anterior
    ro = analisar_rosto(a.video, str(P / "rosto.json"))
    if ro["cobertura"] < 0.5:
        print("AVISO: o rosto foi encontrado em poucos quadros. Confira na folha se nada cobre o rosto; "
              "se o estilo usa recorte, rode 'recortar' (ele refaz a posição do rosto pela silhueta).")
    analise.update({"folha": folha, "transcricao_ok": tr.get("ok"), "transcricao_metodo": tr.get("metodo"),
                    "palavras": len(tr.get("palavras", [])), "rosto": {"metodo": ro["metodo"],
                    "cobertura": ro["cobertura"], **(ro.get("tamanho_medio") or {})},
                    "segundos": round(time.time() - t0, 1)})
    _gravar(P / "analise.json", analise)
    print(json.dumps(analise, ensure_ascii=False, indent=1))
    if tr.get("aviso"):
        print("AVISO:", tr["aviso"])
    print("Olhe a folha de quadros:", folha)


def cmd_palavras(a):
    P = Path(a.pasta)
    tr = _ler(P / "transcricao.json") or {}
    pal = tr.get("palavras", [])
    if not pal:
        print("Sem palavras transcritas.")
        return
    linha, ini = [], pal[0]["inicio"]
    for i, p in enumerate(pal):
        linha.append(f"{p['texto']}·{p['inicio']:.2f}")
        prox = pal[i + 1] if i + 1 < len(pal) else None
        if len(linha) >= 10 or not prox or prox["inicio"] - p["fim"] > 0.45:
            pausa = f"  [pausa {prox['inicio'] - p['fim']:.1f}s]" if prox and prox["inicio"] - p["fim"] > 0.45 else ""
            print(f"[{ini:6.2f}–{p['fim']:6.2f}] " + " ".join(linha) + pausa)
            linha = []
            if prox:
                ini = prox["inicio"]
    print(f"\nTotal: {len(pal)} palavras · duração {tr.get('duracao', 0):.2f}s · método {tr.get('metodo')}")


# arquivos que mudam junto com o vídeo (original × sem silêncios)
_DADOS = ("analise.json", "transcricao.json", "rosto.json", "folha_original.jpg")
_MASCARA = ("mascara.mkv", "recorte.json", "folha_recorte.jpg")


def _ativar_versao(P: Path, alvo: str) -> None:
    """Põe a versão `alvo` (original × sem_silencio) em P, guardando a ativa em _versoes/ com a máscara dela."""
    import shutil as sh
    V = P / "_versoes"
    ativa_f = V / "ativa.txt"
    ativa = ativa_f.read_text(encoding="utf-8").strip() if ativa_f.exists() else "original"
    if alvo == ativa:
        return
    de = V / ativa
    de.mkdir(exist_ok=True)
    for f in _DADOS:  # guarda o estado da versão ativa (o recorte pode ter atualizado o rosto)
        if (P / f).exists():
            sh.copy2(P / f, de / f)
    for f in _MASCARA:
        (de / f).unlink(missing_ok=True)
        if (P / f).exists():
            sh.move(str(P / f), str(de / f))
    para = V / alvo
    for f in _DADOS:
        if (para / f).exists():
            sh.copy2(para / f, P / f)
    for f in _MASCARA:
        if (para / f).exists():
            sh.move(str(para / f), str(P / f))
    ativa_f.write_text(alvo, encoding="utf-8")


def cmd_silencios(a):
    """Aplica a caixinha "Remover silêncios": --remover sim corta as pausas (em etapas; repita até CONCLUÍDO);
    --remover nao volta ao vídeo original. Guarda as duas versões para trocar de estilo sem refazer nada."""
    import shutil as sh
    from .midia import folha_de_contato, sondar
    from .silencio import VERSAO, detectar, montar_por_etapas, remapear_rosto, remapear_transcricao
    t0 = time.time()
    P = Path(a.pasta)
    if not _ler(P / "analise.json"):
        sys.exit("Rode 'preparar' antes.")
    V = P / "_versoes"
    V.mkdir(exist_ok=True)
    orig = V / "original"
    if not (orig / "analise.json").exists():
        orig.mkdir(exist_ok=True)
        for f in _DADOS:
            if (P / f).exists():
                sh.copy2(P / f, orig / f)
    alvo = "sem_silencio" if a.remover == "sim" else "original"
    info_corte = None
    if alvo == "sem_silencio":
        dst = V / "sem_silencio"
        if (dst / "cortes.json").exists() and (_ler(dst / "cortes.json") or {}).get("versao") != VERSAO:
            _ativar_versao(P, "original")  # versão de motor antigo: sai de P (com a máscara dela) antes de apagar
            sh.rmtree(dst)
        dst.mkdir(exist_ok=True)
        if not (dst / "analise.json").exists():
            an0 = _ler(orig / "analise.json")
            tr0 = _ler(orig / "transcricao.json") or {}
            ro0 = _ler(orig / "rosto.json") or {}
            detf = dst / "cortes.json"
            det = _ler(detf)
            if not det:
                det = detectar(an0["video"], tr0.get("palavras"), sem_legenda=tr0.get("trechos_sem_legenda"),
                               proteger_palavras=str(tr0.get("metodo", "")).startswith(("faster-whisper", "openai-whisper")))
                _gravar(detf, det)
            video_novo = dst / f"video_sem_silencios_v{VERSAO}.mkv"  # versão no nome: muda a chave de recorte e render
            if det["removido"] >= 0.5:
                r = montar_por_etapas(an0["video"], det["manter"], str(video_novo),
                                      tempo_max=max(10.0, a.tempo_max - (time.time() - t0)))
                from .licenca import registrar_progresso
                registrar_progresso(P, an0["video"], video_novo)
                if not r["concluido"] or r.get("falhou"):
                    from .licenca import descartar_derivada_incompleta
                    descartar_derivada_incompleta(P, an0["video"], video_novo)
                if not r["concluido"]:
                    return _em_andamento(r, "silencios")
                if r.get("falhou"):  # 3 tentativas sem sucesso: segue com o vídeo original
                    dur = det["duracao_original"]
                    det = dict(det, manter=[[0.0, dur]], cortes=[], removido=0.0, duracao_nova=dur, falhou=r["falhou"],
                               aviso="Não consegui cortar os silêncios deste vídeo: segue o vídeo original, "
                                     "sem cortes. Siga normalmente.")
                    _gravar(detf, det)
                else:
                    from .licenca import registrar_derivada
                    registrar_derivada(P, an0["video"], video_novo)
            if det["removido"] < 0.5:  # nada que valha cortar: a versão "sem silêncio" é o próprio original
                for f in _DADOS:
                    if (orig / f).exists():
                        sh.copy2(orig / f, dst / f)
            else:
                info = sondar(str(video_novo))
                _gravar(dst / "transcricao.json", remapear_transcricao(tr0, det["manter"], info.duracao))
                _gravar(dst / "rosto.json", remapear_rosto(ro0, det["manter"]))
                an1 = dict(an0, video=str(video_novo.resolve()), video_original=an0["video"], info=info.para_dict(),
                           folha=folha_de_contato(str(video_novo), str(dst / "folha_original.jpg"), 5, 2, 260),
                           silencios={"removido_s": det["removido"], "cortes": len(det["cortes"])})
                _gravar(dst / "analise.json", an1)
        info_corte = _ler(dst / "cortes.json")
    _ativar_versao(P, alvo)
    an = _ler(P / "analise.json")
    if an.get("folha"):  # a folha da versão ativa sempre no lugar de sempre
        an["folha"] = str(P / "folha_original.jpg")
        _gravar(P / "analise.json", an)
    res = {"remover_silencios": a.remover == "sim", "duracao_agora": round(an["info"]["duracao"], 2)}
    if info_corte:
        res.update({"duracao_original": info_corte.get("duracao_original", an["info"]["duracao"]),
                    "segundos_removidos": info_corte["removido"],
                    "cortes": len(info_corte["cortes"]), "como_mediu": info_corte["metodo"]})
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if info_corte and info_corte.get("aviso"):
        print("AVISO:", info_corte["aviso"])
    print("\nPalavras com os tempos que valem AGORA (use só estes no plano):")
    cmd_palavras(a)
    _concluido("use só os tempos acima no plano; siga a direção do estilo")


EDITAR_MIN_PAUSA = 0.40  # ritmo do editor automático (DECISOES2, item 12): pausa que sai
EDITAR_FOLGA = 0.10      # e o respiro que fica de cada lado. O silencios antigo segue com silencio.MIN_PAUSA e FOLGA.


def _juntas(manter, fps: float) -> list[float]:
    """Instantes (s, no vídeo EDITADO) das emendas entre pedaços mantidos, no quadro exato em que a montagem
    emendou: cada pedaço vira max(1, round((b - a) * fps)) quadros, como em silencio.montar_por_etapas."""
    juntas, quadros = [], 0
    for a, b in manter[:-1]:
        quadros += max(1, int(round((b - a) * fps)))
        juntas.append(round(quadros / fps, 3))
    return juntas


def _detectar_editado(V: Path) -> dict:
    """O que cortar do vídeo ORIGINAL: silêncios, gaguejos, muletas e recomeços, juntos."""
    from . import gaguejo, silencio
    an0 = _ler(V / "original" / "analise.json")
    tr0 = _ler(V / "original" / "transcricao.json") or {}
    det_s = silencio.detectar(an0["video"], tr0.get("palavras"), min_pausa=EDITAR_MIN_PAUSA, folga=EDITAR_FOLGA,
                              sem_legenda=tr0.get("trechos_sem_legenda"),
                              proteger_palavras=str(tr0.get("metodo", "")).startswith(("faster-whisper", "openai-whisper")))
    det_g = gaguejo.detectar(tr0.get("palavras") or [], det_s["duracao_original"], det_s["fps"],
                             tr0.get("trechos_sem_legenda"), metodo=tr0.get("metodo"))
    if det_s["removido"] < 0.5:  # silêncio que soma menos de 0,5 s não vale um corte
        dur = det_s["duracao_original"]
        det_s = dict(det_s, manter=[[0.0, dur]], cortes=[], removido=0.0, duracao_nova=dur)
    return silencio.combinar(det_s, det_g, tr0.get("palavras") or [])


def _sem_cortes(detf: Path, det: dict, motivo: str) -> dict:
    """Desistiu de cortar (3 tentativas): a versão editada vira o próprio original, com aviso."""
    dur = det["duracao_original"]
    det = dict(det, manter=[[0.0, dur]], cortes=[], removido=0.0, duracao_nova=dur, trechos=[], falhou=motivo,
               aviso="Não consegui cortar os silêncios e gaguejos deste vídeo: segue o vídeo original, sem cortes. "
                     "Siga normalmente.")
    _gravar(detf, det)
    return det


def _montar_editado(V: Path, ate: float) -> dict | None:
    """Monta V/editado a partir do ORIGINAL (nunca corte sobre corte). None = pronta; senão o progresso."""
    import shutil as sh
    from .midia import folha_de_contato, sondar
    from .silencio import TENTATIVAS, VERSAO, montar_por_etapas, remapear_rosto, remapear_transcricao
    dst, orig = V / "editado", V / "original"
    dst.mkdir(exist_ok=True)
    detf = dst / "cortes.json"
    det = _ler(detf)
    if not det:
        det = _detectar_editado(V)
        _gravar(detf, det)
    an0 = _ler(orig / "analise.json")
    video_novo = dst / f"video_editado_v{VERSAO}.mkv"
    if det["cortes"] and not (det.get("montado") and video_novo.exists()):
        r = montar_por_etapas(an0["video"], det["manter"], str(video_novo), tempo_max=max(10.0, ate - time.time()))
        from .licenca import registrar_progresso
        registrar_progresso(V.parent, an0["video"], video_novo)
        if not r["concluido"] or r.get("falhou"):
            from .licenca import descartar_derivada_incompleta
            descartar_derivada_incompleta(V.parent, an0["video"], video_novo)
        if not r["concluido"]:
            return r
        if r.get("falhou"):  # 3 tentativas sem sucesso: segue com o vídeo original, sem cortes
            det = _sem_cortes(detf, det, r["falhou"])
        else:
            from .licenca import registrar_derivada
            registrar_derivada(V.parent, an0["video"], video_novo)
            det = dict(det, montado=True)  # a próxima chamada não monta de novo
            _gravar(detf, det)
            if time.time() > ate - 6:  # a junção não olha o relógio: o resto fica para a próxima chamada
                return {"progresso": 0.9, "detalhe": "vídeo cortado; falta conferir"}
    if det["cortes"]:
        n = det.get("pos_tentativas", 0)
        if n >= TENTATIVAS:  # a chamada anterior morreu no meio da 3ª conferência
            det = _sem_cortes(detf, det, f"a conferência do vídeo cortado não terminou em {TENTATIVAS} tentativas")
        else:
            det = dict(det, pos_tentativas=n + 1)
            _gravar(detf, det)  # conta ANTES: chamada cortada no meio também conta
            try:
                info = sondar(str(video_novo))
                apagar = [k for t in det.get("trechos", []) for k in t["indices"]]
                _gravar(dst / "transcricao.json", remapear_transcricao(_ler(orig / "transcricao.json") or {},
                                                                       det["manter"], info.duracao, apagar))
                _gravar(dst / "rosto.json", remapear_rosto(_ler(orig / "rosto.json") or {}, det["manter"]))
                _gravar_atomico(dst / "analise.json", dict(
                    an0, video=str(video_novo.resolve()), video_original=an0["video"], info=info.para_dict(),
                    juntas=_juntas(det["manter"], det["fps"]),
                    folha=folha_de_contato(str(video_novo), str(dst / "folha_original.jpg"), 5, 2, 260),
                    silencios={"removido_s": det["removido"], "cortes": len(det["cortes"]),
                               "gaguejos": len(det.get("trechos", []))}))
                return None
            except Exception as exc:  # noqa: BLE001
                _gravar_erro(exc, str(V.parent))
                if n + 1 < TENTATIVAS:
                    return {"progresso": 0.9, "detalhe": "a conferência do vídeo cortado falhou; tentando de novo "
                                                         f"({n + 1} de {TENTATIVAS} tentativas usadas)"}
                det = _sem_cortes(detf, det, f"a conferência do vídeo cortado falhou {TENTATIVAS} vezes: {exc}"[-300:])
    for f in _DADOS:  # nada cortado (ou desistiu): é o próprio original, sem emendas
        if (orig / f).exists():
            sh.copy2(orig / f, dst / f)
    _gravar_atomico(dst / "analise.json", dict(_ler(dst / "analise.json"), juntas=[]))
    return None


def _momentos(palavras: list[dict], duracao: float) -> list[dict] | None:
    """Momentos fortes do Plano B (editor_rg/momentos.py), só se o módulo existir; senão None."""
    import importlib
    import importlib.util
    if importlib.util.find_spec("editor_rg.momentos") is None:
        return None
    return importlib.import_module("editor_rg.momentos").detectar(palavras, duracao)


def _gravar_atomico(p: Path, dados) -> None:
    tmp = p.with_suffix(".tmp")
    _gravar(tmp, dados)
    tmp.replace(p)


def cmd_editar(a):
    """Editor automático: corta silêncios, gaguejos, muletas e frases recomeçadas (sempre a partir do ORIGINAL)
    e guarda as opções do cliente em opcoes.json (sem limpeza de ruído). Em etapas: repita até CONCLUÍDO."""
    import shutil as sh
    from .montar import modulo_do_estilo
    from .silencio import TENTATIVAS, VERSAO
    t0 = time.time()
    P = Path(a.pasta)
    if not _ler(P / "analise.json"):
        sys.exit("Rode 'preparar' antes.")
    try:
        mod = modulo_do_estilo(a.estilo)
    except ValueError:
        sys.exit(f"Estilo {a.estilo} não encontrado: use o estilo_id que veio na escolha.")
    V = P / "_versoes"
    atual = _ler(P / "analise.json")
    guardada = _ler(V / "original" / "analise.json")
    origem = Path(atual.get("video_original") or atual["video"]).resolve()
    if origem.is_relative_to(V.resolve()):
        sys.exit("Use o vídeo original no preparar; a entrada está dentro das versões de trabalho.")
    ativa_f = V / "ativa.txt"
    ativa = ativa_f.read_text(encoding="utf-8").strip() if ativa_f.exists() else "original"
    registrada = _ler(V / ativa / "analise.json") or {}
    origem_mudou = guardada and origem != Path(guardada.get("video_original") or guardada["video"]).resolve()
    versao_trocada = registrada.get("video") and Path(atual["video"]).resolve() != Path(registrada["video"]).resolve()
    transcricao_nova = ativa == "original" and guardada and _ler(P / "transcricao.json") != _ler(V / "original" / "transcricao.json")
    if origem_mudou or versao_trocada or transcricao_nova:
        # analisar --refazer pode trocar a origem sem passar pelo preparar.
        # Preserve os dados novos em P, descartando somente derivados da origem antiga.
        for pasta in (V, P / "_recorte_partes", P / "_render_partes"):
            if pasta.exists():
                sh.rmtree(pasta)
        for nome in (*_MASCARA, "opcoes.json", "_aviso_som.json"):
            (P / nome).unlink(missing_ok=True)
    V.mkdir(exist_ok=True)
    orig = V / "original"
    if not (orig / "analise.json").exists():
        orig.mkdir(exist_ok=True)
        for f in _DADOS:
            if (P / f).exists():
                sh.copy2(P / f, orig / f)
    dst = V / "editado"
    if (dst / "cortes.json").exists() and (_ler(dst / "cortes.json") or {}).get("versao") != VERSAO:
        _ativar_versao(P, "original")  # versão feita por um motor antigo: sai de P antes de ser apagada
        sh.rmtree(dst)
    fez = False
    if not (dst / "analise.json").exists():
        r = _montar_editado(V, t0 + a.tempo_max - 6)
        if r:
            return _em_andamento(r, "editar")
        fez = True
    _ativar_versao(P, "editado")
    an = _ler(P / "analise.json")
    if an.get("folha"):  # a folha da versão ativa sempre no lugar de sempre
        an["folha"] = str(P / "folha_original.jpg")
        _gravar(P / "analise.json", an)
    if not _recorte_pronto(P, an):  # também limpa restos de uma chamada encerrada à força
        (P / "mascara.mkv").unlink(missing_ok=True)
        (P / "folha_recorte.jpg").unlink(missing_ok=True)
    aviso_recorte = None
    if mod.INFO.get("precisa_recorte") and not _recorte_pronto(P, an):
        tf = dst / "_tentativas_recorte.json"
        conta = _ler(tf) or {}
        n, livres = conta.get("n", 0), conta.get("livres", 0)
        if n >= TENTATIVAS:
            aviso_recorte = "sem recorte: use o modo sem recorte do estilo"
        elif fez:  # esta chamada já montou o vídeo: o recorte começa na próxima, com o tempo inteiro
            return _em_andamento({"progresso": 0.5, "detalhe": "vídeo pronto; falta recortar a pessoa"}, "editar")
        else:
            _gravar(tf, {"n": n + 1, "livres": livres})  # conta ANTES: chamada cortada no meio também conta
            bytes_antes = _bytes_do_modelo_de_recorte()
            try:
                r = _recortar_uma_etapa(P, max(10.0, a.tempo_max - (time.time() - t0)))
                erro = None if not r["concluido"] or r["resultado"].get("ok") else "; ".join(r["resultado"].get("erros", []))
            except Exception as exc:  # noqa: BLE001
                r, erro = None, str(exc)
            if erro is None:
                if r["concluido"] or r.get("progresso", 0) > 0:  # recortou de verdade: a conta recomeça
                    tf.unlink()
                elif livres < _BAIXANDO_SEM_CONTAR and _bytes_do_modelo_de_recorte() > bytes_antes:
                    _gravar(tf, {"n": n, "livres": livres + 1})  # só baixou (o progresso fica em 0): a tentativa volta
                if not r["concluido"]:
                    return _em_andamento(r, "editar")
            else:
                _gravar(tf, {"n": n + 1, "livres": livres, "erro": erro[-300:]})
                if n + 1 < TENTATIVAS:
                    return _em_andamento({"progresso": 0.0, "detalhe": f"o recorte falhou; tentando de novo "
                                          f"({n + 1} de {TENTATIVAS} tentativas usadas)"}, "editar")
                aviso_recorte = "sem recorte: use o modo sem recorte do estilo"
    op = {"suavizar_pele": a.pele == "sim", "trilha": a.trilha == "sim", "reduzir_ruido": False}  # contrato 3
    _gravar_atomico(P / "opcoes.json", op)
    det = _ler(dst / "cortes.json") or {}
    res = {"estilo": a.estilo, "duracao_original": det.get("duracao_original", an["info"]["duracao"]),
           "duracao_agora": round(an["info"]["duracao"], 2), "segundos_removidos": det.get("removido", 0.0),
           "cortes": len(det.get("cortes", [])), "gaguejos_cortados": len(det.get("trechos", [])),
           "como_mediu": det.get("metodo"), "juntas": len(an.get("juntas", [])), **op,
           "recorte": _recorte_pronto(P, an) if mod.INFO.get("precisa_recorte") else "não precisa"}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if det.get("aviso"):
        print("AVISO:", det["aviso"])
    if aviso_recorte:
        print("AVISO:", aviso_recorte)
    for t in det.get("trechos", []):
        print(f'Cortado ({t["tipo"]}): "{t["texto"]}" — já saiu da lista abaixo; não o coloque no plano.')
    print("\nPalavras com os tempos que valem AGORA (use só estes no plano):")
    cmd_palavras(a)
    tr = _ler(P / "transcricao.json") or {}
    try:
        mom = _momentos(tr.get("palavras", []), an["info"]["duracao"])
    except Exception:  # noqa: BLE001  defeito nos momentos (Plano B) não derruba a edição
        mom = None
        print("AVISO: não deu para achar os momentos fortes; escreva o plano pelas palavras acima.")
    if mom is not None:
        print("\nMomentos fortes (tempos que valem AGORA):", json.dumps(mom, ensure_ascii=False))
    _concluido("use só os tempos acima no plano; depois prévia e renderizar")


def _bytes_do_modelo_de_recorte() -> int:
    """Quanto do modelo de recorte já está no disco, inteiro ou pela metade; sem medida, 0 (vale a conta normal)."""
    from .recorte import NOME_RVM, _pastas_modelo
    try:
        return sum(f.stat().st_size for p in _pastas_modelo() for f in (p / NOME_RVM, p / (NOME_RVM + ".baixando"))
                   if f.is_file())
    except (OSError, RuntimeError):
        return 0


def _recorte_pronto(P: Path, an: dict) -> bool:
    """Arquivo final e relatório de sucesso da versão ativa; relatório antigo acompanha a versão."""
    try:
        res = _ler(P / "recorte.json")
        return (isinstance(res, dict) and res.get("ok") is True
                and (P / "mascara.mkv").is_file() and (P / "mascara.mkv").stat().st_size > 0
                and (not res.get("video") or Path(res["video"]).resolve() == Path(an["video"]).resolve()))
    except (OSError, ValueError, TypeError):
        return False


def _recortar_uma_etapa(P: Path, tempo_max: float, preferir: str | None = None, reforco: bool = False) -> dict:
    """Uma etapa do recorte da pessoa no vídeo ativo de P; quando conclui com sucesso, faz a folha do recorte
    e, sem detector de rosto, o rosto pela silhueta."""
    from .recorte import amostra_visual, gerar_mascara_por_etapas
    from .rosto import analisar_rosto
    an = _ler(P / "analise.json")
    (P / "recorte.json").unlink(missing_ok=True)  # sucesso antigo não valida um arquivo refeito pela metade
    pronto = False
    try:
        r = gerar_mascara_por_etapas(an["video"], str(P), tempo_max=tempo_max, preferir=preferir,
                                     reforco=reforco, rosto_dados=_ler(P / "rosto.json"))
        res = r.get("resultado") or {}
        if r["concluido"] and res.get("ok"):
            res["conferir"] = amostra_visual(an["video"], str(P / "mascara.mkv"), str(P / "folha_recorte.jpg"))
            ro = _ler(P / "rosto.json")
            if ro and ro.get("metodo") == "estimativa":  # sem detector de rosto: usa a silhueta
                ro = analisar_rosto(an["video"], str(P / "rosto.json"), mascara=str(P / "mascara.mkv"))
                an["rosto"] = {"metodo": ro["metodo"], "cobertura": ro["cobertura"], **(ro.get("tamanho_medio") or {})}
                _gravar(P / "analise.json", an)
            _gravar_atomico(P / "recorte.json", dict(res, video=an["video"]))
            pronto = _recorte_pronto(P, an)
            if not pronto:
                raise RuntimeError("O recorte informou sucesso, mas não deixou a máscara completa.")
        return r
    finally:
        if not pronto:
            (P / "mascara.mkv").unlink(missing_ok=True)
            (P / "folha_recorte.jpg").unlink(missing_ok=True)


def cmd_recortar(a):
    """Recorte da pessoa em etapas de no máximo ~40 s. Repita até CONCLUÍDO."""
    P = Path(a.pasta)
    if not _ler(P / "analise.json"):
        sys.exit("Rode 'preparar' antes.")
    r = _recortar_uma_etapa(P, a.tempo_max, a.metodo, a.reforco)
    if not r["concluido"]:
        return _em_andamento(r, "recortar")
    res = r["resultado"]
    print(json.dumps(res, ensure_ascii=False, indent=1))
    _concluido("olhe folha_recorte.jpg" if res.get("ok") else "sem recorte: use o modo sem recorte do estilo")


def _carregar_trabalho(P: Path, plano_arq: str | None):
    an = _ler(P / "analise.json")
    if not an:
        sys.exit("Rode 'analisar' antes.")
    plano = Path(plano_arq) if plano_arq else P / "plano.json"
    if not plano.exists():
        sys.exit(f"Plano não encontrado: {plano}")
    from .plano import carregar
    pl = carregar(plano)
    arq_op = P / "opcoes.json"
    if arq_op.exists():  # escolha gravada pelo motor vence o plano; o ruído nunca liga neste caminho
        try:
            op = _ler(arq_op)
        except ValueError:
            op = None
        vindas = {k: bool(op[k]) for k in ("suavizar_pele", "trilha") if k in op} if isinstance(op, dict) else {}
        pl["opcoes"] = {**pl.get("opcoes", {}), **vindas, "reduzir_ruido": False}
    pl.pop("juntas", None)  # as emendas são do motor, nunca do plano
    if "juntas" in an:  # prévia e render usam as emendas da versão editada
        pl["juntas"] = list(an["juntas"])
    m = P / "mascara.mkv"
    return an, pl, _ler(P / "transcricao.json"), _ler(P / "rosto.json"), (str(m) if m.exists() else None)


def cmd_previa(a):
    from .montar import modulo_do_estilo, quadros_de_previa
    from .plano import validar
    P = Path(a.pasta)
    an, pl, tr, ro, m = _carregar_trabalho(P, a.plano)
    mod = modulo_do_estilo(pl["estilo"])
    problemas = validar(pl, an["info"]["duracao"], mod)
    avisos = []
    if mod.INFO.get("precisa_recorte") and not m:
        avisos.append("Sem máscara da pessoa: o estilo usa o modo sem recorte. Se o 'editar' não avisou 'sem recorte', rode 'recortar' se o ambiente permitir.")
    if a.tempos:
        tempos = [float(x) for x in a.tempos.split(",")]
    else:  # começo do vídeo, entrada e meio de eventos espalhados, e o fim (até 10, em ordem)
        evs = pl["eventos"]
        dur = an["info"]["duracao"]
        cand = [0.5, max(0.5, dur - 1.0)]
        for e in evs:
            cand += [e["inicio"] + min(0.25, (e["fim"] - e["inicio"]) / 3), (e["inicio"] + e["fim"]) / 2]
        cand = sorted({round(min(max(t, 0.1), dur - 0.1), 2) for t in cand})
        if len(cand) > 10:
            passo = (len(cand) - 1) / 9
            cand = [cand[round(i * passo)] for i in range(10)]
        tempos = cand or [dur / 2]
    saida = str(P / "folha_previa.jpg")
    quadros_de_previa(an["video"], pl, tempos, saida, tr, ro, m)
    print(json.dumps({"previa": saida, "tempos": tempos, "problemas_no_plano": problemas, "avisos": avisos},
                     ensure_ascii=False, indent=1))


def _supervisionar_render(a):
    from .supervisao import executar
    P = Path(a.pasta)
    contador = P / '_render_interrupcoes.json'
    estado = _ler(contador) or {}
    chave = str(Path(a.plano or (P / 'plano.json')).resolve())
    plano = Path(chave).read_text(encoding='utf-8') if Path(chave).exists() else ''
    if estado.get('plano') != plano:
        estado = {'plano': plano, 'tentativas': 0}
    if estado['tentativas'] >= 3:
        raise RuntimeError('Montagem interrompida: três chamadas excederam o prazo. Ofereça outro estilo.')
    def progresso():
        est = _ler(P / '_render_partes' / 'estado.json') or {}
        return (sum(bool(p.get('feito')) for p in est.get('partes', [])), bool(est.get('audio')), bool(est.get('final')))
    antes = progresso()
    env = {**os.environ, '_EDITOR_RG_RENDER_FILHO': '1', 'PYTHONIOENCODING': 'utf-8'}
    r = executar([sys.executable, '-B', str(Path(__file__).resolve().parent.parent / 'erg.py'),
                  *a._argv], 38.0, env=env)
    if r['expirou']:
        estado['tentativas'] = 0 if progresso() > antes else estado['tentativas'] + 1
        _gravar(contador, estado)
        _gravar_erro(TimeoutError('Montagem excedeu 38 s; árvore de processos encerrada. ' + r['saida'][-1000:]), str(P))
        if estado['tentativas'] >= 3:
            raise RuntimeError('Montagem interrompida: três chamadas excederam o prazo. Ofereça outro estilo.')
        return _em_andamento({'detalhe': 'a montagem excedeu o prazo; retomando as partes pendentes'}, 'renderizar')
    contador.unlink(missing_ok=True)
    print(r['saida'], end='')
    if r['codigo']:
        sys.exit(r['codigo'])


def _mixar_som(P: Path, an: dict, pl: dict, dur: float, wav: str) -> None:
    from . import audio
    aviso = P / "_aviso_som.json"
    aviso.unlink(missing_ok=True)
    op = pl.get("opcoes", {})
    efeitos = list(pl.get("efeitos_sonoros", []))
    for e in pl["eventos"]:
        if e.get("som"):
            efeitos.append({"som": e["som"], "t": e["inicio"] + float(e.get("som_atraso", 0)),
                            "volume": e.get("som_volume", 0.32)})
    tri = dict(pl.get("trilha") or {})
    trilha = None
    if op.get("trilha"):
        trilha = tri.get("arquivo")
        if not trilha:
            esc = audio.escolher_trilha(tri.get("clima"), tri.get("energia"))
            if esc:
                trilha = esc["arquivo"]
                tri.setdefault("volume", min(0.5, esc.get("volume_sugerido", 0.3)))
    rr = bool(op.get("reduzir_ruido"))
    tem_trilha = bool(trilha) and audio.resolver_som(trilha) is not None
    preservar = (P / "opcoes.json").exists()  # editor automático: a voz sai no volume em que foi gravada
    try:
        audio.montar_audio(an["video"], wav, dur, reduzir_ruido=rr, trilha=trilha,
                           volume_trilha=tri.get("volume", 0.3), efeitos=efeitos, preservar_voz=preservar)
    except RuntimeError as exc:
        if not str(exc).startswith("Falha ao montar o áudio") or not (rr or tem_trilha):
            raise
        audio.montar_audio(an["video"], wav, dur, reduzir_ruido=False, trilha=None,
                           volume_trilha=tri.get("volume", 0.3), efeitos=efeitos, preservar_voz=preservar)
        sem = " e ".join(texto for presente, texto in (
            (rr, "sem a limpeza de ruído"), (tem_trilha, "sem a trilha")) if presente)
        _gravar(aviso, {"aviso": f"O som saiu {sem}: a mistura com esses ajustes falhou neste computador. "
                       "Avise o cliente em uma frase."})


def cmd_renderizar(a):
    """Monta o vídeo final em etapas de no máximo ~40 s (progresso salvo). Repita até CONCLUÍDO."""
    t0 = time.time()
    if os.environ.pop('_EDITOR_RG_RENDER_FILHO', None) != '1':
        return _supervisionar_render(a)
    if sys.stdin.buffer.read(1) != b'1':
        raise RuntimeError('Supervisor da montagem indisponível.')
    from .montar import limpar_partes, modulo_do_estilo, renderizar_por_etapas
    from .plano import validar
    P = Path(a.pasta)
    an, pl, tr, ro, m = _carregar_trabalho(P, a.plano)
    dur = an["info"]["duracao"]
    mod = modulo_do_estilo(pl["estilo"])
    problemas = validar(pl, dur, mod)
    if problemas and not a.forcar:
        print(json.dumps({"ok": False, "problemas_no_plano": problemas,
                          "dica": "Corrija o plano (ou use --forcar se tiver certeza)."}, ensure_ascii=False, indent=1))
        sys.exit(2)
    saida = a.saida or str(P / "video_editado.mp4")
    r = renderizar_por_etapas(an["video"], pl, str(P), saida, tr, ro, m,
                              lambda wav: _mixar_som(P, an, pl, dur, wav),
                              mb_max=a.mb_max, tempo_max=a.tempo_max)
    if not r["concluido"]:
        return _em_andamento(r, "renderizar")
    # conferência que não cabe no resto desta chamada fica para a próxima, que não monta nada (nunca adia 2 vezes)
    # medido: ~0,06 s por segundo de vídeo (1 núcleo, com -vn); 0,12 é o dobro de propósito
    if r.get("trabalhou") and a.tempo_max - (time.time() - t0) < 3 + 0.12 * dur:
        return _em_andamento({"progresso": 0.99, "detalhe": "conferindo o vídeo final"}, "renderizar")
    v = _verificar(saida, an, P)
    aviso = _ler(P / "_aviso_som.json")
    if aviso:
        v["aviso_som"] = aviso["aviso"]
    v.update({"render": r["resultado"]})
    _gravar(P / "resultado.json", v)
    limpar_partes(str(P))
    print(json.dumps(v, ensure_ascii=False, indent=1))
    _concluido("olhe folha_resultado.jpg; depois envie o arquivo MP4 no chat e chame mostrar_resultado" if v["ok"]
               else "há problemas: veja 'problemas', corrija o plano e renderize de novo")


def _verificar(saida, an, P: Path) -> dict:
    from .midia import folha_de_contato, medir_volume, sondar
    i = sondar(saida)
    o = an["info"]
    problemas = []
    if abs(i.duracao - o["duracao"]) > 0.25:
        problemas.append(f"Duração diferente do original ({i.duracao:.2f}s × {o['duracao']:.2f}s).")
    if min(i.largura, i.altura) < min(o["largura"], o["altura"]) * 0.98 and max(o["largura"], o["altura"]) <= 1920:
        problemas.append("Resolução menor que a do original.")
    if not i.tem_audio and o["tem_audio"]:
        problemas.append("O vídeo final ficou sem áudio.")
    # sem fala: não há voz para medir
    vol = medir_volume(saida) if i.tem_audio and o["tem_audio"] and an.get("palavras") else {}
    preservado = (P / "opcoes.json").exists()  # editor automático: o volume é o da gravação, de propósito
    if vol and vol.get("lufs") == vol.get("lufs") and not preservado and not (-17.5 <= vol["lufs"] <= -11.5):
        problemas.append(f"Volume fora do padrão ({vol['lufs']:.1f} LUFS; o ideal é perto de -14).")
    folha = folha_de_contato(saida, str(P / "folha_resultado.jpg"), 5, 2, 260)
    return {"ok": not problemas, "arquivo": saida, "tamanho_mb": i.tamanho_mb, "duracao": round(i.duracao, 2),
            "resolucao": [i.largura, i.altura], "volume": vol, "problemas": problemas,
            "olhe_antes_de_entregar": folha}


def cmd_verificar(a):
    P = Path(a.pasta)
    an = _ler(P / "analise.json")
    print(json.dumps(_verificar(a.video, an, P), ensure_ascii=False, indent=1))


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="editor_rg", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("ambiente")
    s.add_argument("--testar-download", action="store_true")
    s.set_defaults(f=cmd_ambiente)
    s = sp.add_parser("preparar-autorizacao", help="prepara somente os dados públicos da autorização")
    s.add_argument("video")
    s.add_argument("--pasta", required=True)
    s.set_defaults(f=cmd_preparar_autorizacao)
    s = sp.add_parser("ativar-autorizacao", help="comprova a posse da chave local e ativa o projeto")
    s.add_argument("--pasta", required=True)
    s.add_argument("--autorizacao-id", required=True)
    s.add_argument("--desafio", required=True)
    s.add_argument("--expira-em", required=True)
    s.set_defaults(f=cmd_ativar_autorizacao)
    s = sp.add_parser("preparar")
    s.add_argument("video")
    s.add_argument("--tempo-max", type=float, default=TEMPO_MAX_PADRAO)
    s.add_argument("--pasta", required=True)
    s.add_argument("--modelo", default="small")
    s.add_argument("--idioma", default="pt")
    s.add_argument("--texto")
    s.add_argument("--segmentos")
    s.add_argument("--refazer", action="store_true")
    s.set_defaults(f=cmd_preparar)
    s = sp.add_parser("analisar")
    s.add_argument("video")
    s.add_argument("--pasta", required=True)
    s.add_argument("--modelo", default="small")
    s.add_argument("--idioma", default="pt")
    s.add_argument("--texto", help="fala completa (quando não há programa de transcrição)")
    s.add_argument("--segmentos", help="JSON [{inicio,fim,texto}] escrito pelo agente")
    s.add_argument("--refazer", action="store_true")
    s.set_defaults(f=cmd_analisar)
    s = sp.add_parser("palavras")
    s.add_argument("--pasta", required=True)
    s.set_defaults(f=cmd_palavras)
    s = sp.add_parser("silencios")
    s.add_argument("--pasta", required=True)
    s.add_argument("--remover", choices=["sim", "nao", "não"], required=True)
    s.add_argument("--tempo-max", type=float, default=TEMPO_MAX_PADRAO)
    s.set_defaults(f=cmd_silencios)

    s = sp.add_parser("editar")
    s.add_argument("--pasta", required=True)
    s.add_argument("--estilo", required=True)
    s.add_argument("--pele", choices=["sim", "nao", "não"], default="nao")
    s.add_argument("--trilha", choices=["sim", "nao", "não"], default="nao")
    s.add_argument("--tempo-max", type=float, default=TEMPO_MAX_PADRAO)
    s.set_defaults(f=cmd_editar)
    s = sp.add_parser("recortar")
    s.add_argument("--pasta", required=True)
    s.add_argument("--metodo", choices=["rvm", "mediapipe", "rembg"])
    s.add_argument("--reforco", action="store_true", help="reforça o corpo com um 2º modelo (mais lento; 176 MB)")
    s.add_argument("--sem-reforco", action="store_true", help=argparse.SUPPRESS)
    s.add_argument("--tempo-max", type=float, default=TEMPO_MAX_PADRAO)
    s.set_defaults(f=cmd_recortar)
    s = sp.add_parser("previa")
    s.add_argument("--pasta", required=True)
    s.add_argument("--plano")
    s.add_argument("--tempos")
    s.set_defaults(f=cmd_previa)
    s = sp.add_parser("renderizar")
    s.add_argument("--pasta", required=True)
    s.add_argument("--plano")
    s.add_argument("--saida")
    s.add_argument("--mb-max", type=float)
    s.add_argument("--partes", type=int, help=argparse.SUPPRESS)
    s.add_argument("--forcar", action="store_true")
    s.add_argument("--tempo-max", type=float, default=TEMPO_MAX_PADRAO)
    s.set_defaults(f=cmd_renderizar)
    s = sp.add_parser("verificar")
    s.add_argument("video")
    s.add_argument("--pasta", required=True)
    s.set_defaults(f=cmd_verificar)
    a = ap.parse_args(argv)
    a._argv = list(sys.argv[1:] if argv is None else argv)
    protegido = a.cmd in {"preparar", "analisar", "palavras", "silencios", "editar", "recortar", "previa", "renderizar"}
    try:
        if protegido:
            from .licenca import ErroLicenca, exigir_autorizacao
            try:
                exigir_autorizacao(a.pasta, getattr(a, "video", None))
            except ErroLicenca:
                raise
            except Exception:
                # Só a fronteira de autorização é sanitizada; a edição conserva seu diagnóstico.
                raise ErroLicenca('Não foi possível concluir a autorização neste ambiente. Preserve o projeto para verificar a falha.') from None
        a.f(a)
    except Exception as exc:  # noqa: BLE001  SystemExit e KeyboardInterrupt não são Exception: passam direto
        _falhou(exc, a)
    finally:
        if protegido:
            from .licenca import encerrar_operacao
            encerrar_operacao()


def cmd_preparar_autorizacao(a):
    from .licenca import preparar_autorizacao
    print(json.dumps(preparar_autorizacao(a.video, a.pasta), ensure_ascii=False))


def cmd_ativar_autorizacao(a):
    from .licenca import ativar_autorizacao
    print(json.dumps(ativar_autorizacao(a.pasta, a.autorizacao_id, a.desafio, a.expira_em), ensure_ascii=False))


if __name__ == "__main__":
    main()
