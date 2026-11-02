"""Montagem: lê cada quadro do vídeo original, entrega ao estilo, desenha a legenda e grava.

Contrato do módulo de estilo (editor_rg/estilos/eNN_nome.py):
    INFO = {"id", "nome", "precisa_recorte": bool, "legenda": {perfil}, "eventos": {tipo: "campos"},
            "antes": s, "depois": s}   # antes/depois: folga para animações de entrada/saída
    def preparar(g): ...               # opcional: pré-desenha cartões, carrega fontes (g.cache)
    def quadro(c) -> PIL.Image RGBA    # OBRIGATÓRIO: função só do tempo (sem memória entre quadros)
    def validar(plano, duracao) -> [problemas]   # opcional
"""
from __future__ import annotations

import importlib
import json
import math
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from . import desenho as d
from .legenda import Legendas, PerfilLegenda
from .midia import (EscritorDeVideo, LeitorDeQuadros, bitrate_alvo_kbps, ffmpeg_bin, fps_de_saida, linha_concat,
                    nucleos, sondar, tamanho_de_trabalho)
from .plano import ativos, carregar
from .recorte import firmar_borda
from .rosto import Rosto


def modulo_do_estilo(estilo_id: str):
    """'05-zoom-digital' ou '5' -> módulo editor_rg.estilos.e05_zoom_digital"""
    pasta = Path(__file__).resolve().parent / "estilos"
    num = str(estilo_id).split("-")[0].zfill(2)
    for arq in sorted(pasta.glob(f"e{num}_*.py")):
        return importlib.import_module(f"editor_rg.estilos.{arq.stem}")
    raise ValueError(f"Estilo {estilo_id} não encontrado em {pasta}")


@dataclass
class Global:
    W: int
    H: int
    fps: float
    duracao: float
    plano: dict
    palavras: list
    rosto: Rosto
    tem_mascara: bool
    cache: dict = field(default_factory=dict)
    legendas: Legendas | None = None
    video_caminho: str | None = None      # vídeo original
    mascara_caminho: str | None = None    # máscara da pessoa (None se não houver)


@dataclass
class Contexto:
    t: float
    i: int
    W: int
    H: int
    fonte: Image.Image            # quadro original RGBA (pode ser usado como fundo ou textura)
    mascara: Image.Image | None   # L: 255 = pessoa
    eventos: list                 # eventos ativos em t (com folga antes/depois)
    g: Global

    @property
    def fonte_pessoa(self) -> Image.Image | None:
        """Quadro original com a borda da pessoa limpa (sem a cor do fundo antigo). Use-o no lugar de `fonte`
        sempre que COLAR a pessoa sobre outro fundo com a máscara (None se não houver recorte)."""
        if self.mascara is None:
            return None
        if "_fonte_pessoa" not in self.__dict__:
            self.__dict__["_fonte_pessoa"] = d.limpar_borda(self.fonte, self.mascara).convert("RGBA")
        return self.__dict__["_fonte_pessoa"]

    @property
    def pessoa(self) -> Image.Image | None:
        """Camada RGBA só com a pessoa recortada (None se não houver recorte)."""
        if self.mascara is None:
            return None
        if "_pessoa" not in self.__dict__:
            self.__dict__["_pessoa"] = d.recortar_pessoa(self.fonte_pessoa, self.mascara)
        return self.__dict__["_pessoa"]

    @property
    def rosto(self):
        return self.g.rosto.em(self.t)

    def faixa_legenda(self):
        return self.g.legendas.ocupacao(self.t) if self.g.legendas else None

    def palavras_em(self, t0: float, t1: float) -> list[dict]:
        return [p for p in self.g.palavras if p["fim"] > t0 and p["inicio"] < t1]

    def pessoa_por_cima(self, base: Image.Image, quadro_pessoa: Image.Image | None = None):
        """Recoloca a pessoa por cima de tudo que foi desenhado atrás dela (oclusão)."""
        p = self.pessoa if quadro_pessoa is None else quadro_pessoa
        if p is not None:
            base.alpha_composite(p)
        return base


def _preparar(video, plano_d, transcricao, rosto_json, mascara):
    info = sondar(video)
    W, H = tamanho_de_trabalho(info)
    fps = fps_de_saida(info)
    plano = carregar(plano_d)
    mod = modulo_do_estilo(plano["estilo"])
    palavras = (transcricao or {}).get("palavras", [])
    if plano.get("correcoes"):
        from .transcrever import corrigir
        palavras = corrigir({"palavras": [dict(p) for p in palavras]}, plano["correcoes"])["palavras"]
    rosto = Rosto(rosto_json, W, H)
    tem_m = bool(mascara and Path(mascara).exists())
    g = Global(W, H, fps, info.duracao, plano, palavras, rosto, tem_m,
               video_caminho=str(video), mascara_caminho=str(mascara) if tem_m else None)
    leg = plano.get("legenda", {})
    if leg.get("ativa", True) and palavras and not getattr(mod, "INFO", {}).get("legenda_propria"):
        perfil = dict(getattr(mod, "INFO", {}).get("legenda", {}))
        perfil.update(leg.get("perfil", {}))
        g.legendas = Legendas(palavras, W, H, PerfilLegenda.de(perfil), rosto)
    if hasattr(mod, "preparar"):
        mod.preparar(g)
    return info, mod, g


def _um_quadro(mod, g, q_np, m_img, i, t):
    return np.asarray(_um_quadro_img(mod, g, q_np, m_img, i, t))[..., :3]


def _um_quadro_img(mod, g, q_np, m_img, i, t) -> Image.Image:
    """O quadro final pronto (RGBA, tamanho W x H): pele, estilo e legenda."""
    info = getattr(mod, "INFO", {})
    if g.plano.get("opcoes", {}).get("suavizar_pele"):
        if "_pele" not in g.cache:
            from . import pele
            g.cache["_pele"] = pele if pele.disponivel() else None
        if g.cache["_pele"] is not None:
            q_np = g.cache["_pele"].suavizar(q_np, g.rosto.em(t))
    fonte = d.para_rgba(q_np)
    if m_img is not None and str(g.plano['estilo']).split('-')[0].zfill(2) in ('04', '08'):
        m_img = firmar_borda(m_img)  # única aplicação, compartilhada pela prévia e montagem
    evs = ativos(g.plano, t, info.get("antes", 0.5), info.get("depois", 0.5))
    c = Contexto(t, i, g.W, g.H, fonte, m_img, evs, g)
    img = mod.quadro(c)
    if img.size != (g.W, g.H):
        img = img.resize((g.W, g.H), Image.BICUBIC)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    if g.legendas:
        g.legendas.desenhar(img, t)
    return img


# ---------------------------------------------------------------- render por etapas (cabe no limite de tempo do chat)

_CTX = {}


def _render_parte_ctx(info, mod, g, video, mascara, inicio_q, qn, saida, teto, preset):
    """Renderiza qn quadros a partir do quadro inicio_q e grava já no formato final (sem segunda codificação)."""
    inicio = inicio_q / g.fps
    leitor = iter(LeitorDeQuadros(video, g.W, g.H, g.fps, inicio=inicio, duracao=(qn + 2) / g.fps))
    lm = None
    if g.tem_mascara:
        lm = iter(LeitorDeQuadros(mascara, g.W, g.H, g.fps, inicio=inicio, duracao=(qn + 2) / g.fps, cinza=True))
    esc = EscritorDeVideo(saida, g.W, g.H, g.fps, None, (qn + 1) / g.fps, preset=preset, crf=20, teto_kbps=teto,
                          entrada="rgba")
    ultimo = None
    try:
        for n in range(qn):
            q = next(leitor, None)
            if q is None:
                if ultimo is None:
                    break
                q = ultimo  # faltou um quadro no fim do trecho: repete o último
            ultimo = q
            m = None
            if lm is not None:
                mm = next(lm, None)
                m = Image.fromarray(mm, "L") if mm is not None else None
            esc.escrever(_um_quadro_img(mod, g, q, m, inicio_q + n, (inicio_q + n) / g.fps).tobytes())
    finally:
        esc.fechar()
    return qn


def _init_trabalhador(video, plano_d, transcricao, rosto_json, mascara):
    try:
        import cv2
        cv2.setNumThreads(1)
    except Exception:  # noqa: BLE001
        pass
    _CTX["args"] = (video, mascara)
    _CTX["prep"] = _preparar(video, plano_d, transcricao, rosto_json, mascara)


def _com_tentativa(prep, video, mascara, inicio_q, qn, saida, teto, preset):
    # Uma tentativa por chamada; o contador persistente é gravado pelo coordenador.
    try:
        return _render_parte_ctx(*prep, video, mascara, inicio_q, qn, saida, teto, preset)
    except (RuntimeError, OSError):
        Path(saida).unlink(missing_ok=True)
        raise


def _trabalhar(tarefa):
    video, mascara = _CTX["args"]
    t = time.time()
    _com_tentativa(_CTX["prep"], video, mascara, *tarefa)
    return time.time() - t


def _salvar_estado(arq, estado):
    tmp = arq.with_suffix('.tmp')
    tmp.write_text(json.dumps(estado), encoding='utf-8')
    tmp.replace(arq)


def _contar_tentativa(estado, chave, nome):
    if estado.get(chave, 0) >= 3:
        raise RuntimeError(f'Montagem interrompida: {nome} não terminou em 3 tentativas. Ofereça outro estilo.')
    estado[chave] = estado.get(chave, 0) + 1


def renderizar_por_etapas(video: str, plano_d: dict, pasta: str, saida: str, transcricao=None, rosto_json=None,
                          mascara: str | None = None, preparar_audio=None, mb_max: float | None = None,
                          tempo_max: float = 40.0, preset: str = "veryfast", log=print) -> dict:
    """Monta o vídeo em trechos de 2 s com progresso salvo. Devolve {"concluido": bool, ...}.
    preparar_audio(caminho_wav) monta o áudio final (uma vez, depois dos trechos)."""
    import hashlib
    t0 = time.time()
    P = Path(pasta)
    D = P / "_render_partes"
    D.mkdir(parents=True, exist_ok=True)
    estf = D / "estado.json"
    info = sondar(video)
    W, H = tamanho_de_trabalho(info)
    fps = fps_de_saida(info)
    dur = info.duracao
    if mb_max is None:
        mb_max = 25.0 if dur <= 75 else 45.0
    teto = bitrate_alvo_kbps(dur, mb_max)
    m_sig = "-"
    if mascara and Path(mascara).exists():
        m_sig = f"{Path(mascara).stat().st_size}:{Path(mascara).stat().st_mtime}"
    n_pal = len((transcricao or {}).get("palavras", []))
    assinatura = hashlib.sha1(json.dumps([plano_d, str(video), m_sig, preset, mb_max, n_pal],
                                         sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    est = json.loads(estf.read_text(encoding="utf-8")) if estf.exists() else None
    if not est or est.get("assinatura") != assinatura:
        for f in D.glob("*"):
            f.unlink(missing_ok=True)
        total_q = int(round(dur * fps))
        por = max(1, int(round(fps * 2)))
        est = {"assinatura": assinatura, "total": total_q,
               "partes": [{"qi": qi, "qn": min(por, total_q - qi), "arq": f"p{k:04d}.mkv", "feito": False}
                          for k, qi in enumerate(range(0, total_q, por))],
               "audio": False, "final": False, "seg_por_parte": None}
        estf.write_text(json.dumps(est), encoding="utf-8")
    trabalhou = not est["final"]  # esta chamada vai montar trecho, áudio ou a junção final
    pend = [p for p in est["partes"] if not p["feito"]]
    if pend:
        nuc = max(1, min(4, nucleos()))
        if any(p.get('tentativas', 0) for p in pend):
            nuc = 1  # parte interrompida tenta novamente sem concorrência
        feitas_nesta = 0
        if nuc == 1:
            prep = _preparar(video, plano_d, transcricao, rosto_json, mascara)
            for p in pend:
                previsto = (est["seg_por_parte"] or 20.0) * 1.15
                if feitas_nesta > 0 and time.time() - t0 + previsto > tempo_max:
                    break
                t1 = time.time()
                _contar_tentativa(p, 'tentativas', p['arq'])
                _salvar_estado(estf, est)
                _com_tentativa(prep, video, mascara, p["qi"], p["qn"], str(D / p["arq"]), teto, preset)
                p["feito"] = True
                feitas_nesta += 1
                est["seg_por_parte"] = time.time() - t1
                _salvar_estado(estf, est)
        else:
            import multiprocessing as mpc
            ctx = mpc.get_context("spawn")
            with ctx.Pool(nuc, initializer=_init_trabalhador,
                          initargs=(video, plano_d, transcricao, rosto_json, mascara)) as pool:
                while pend:
                    previsto = (est["seg_por_parte"] or 25.0) * 1.2
                    if feitas_nesta > 0 and time.time() - t0 + previsto > tempo_max:
                        break
                    lote, pend = pend[:nuc], pend[nuc:]
                    for p in lote:
                        _contar_tentativa(p, 'tentativas', p['arq'])
                    _salvar_estado(estf, est)
                    tarefas = [(p, pool.apply_async(_trabalhar, ((p['qi'], p['qn'], str(D / p['arq']), teto, preset),)))
                               for p in lote]
                    tempos = []
                    while tarefas:
                        for p, tarefa in tarefas[:]:
                            if tarefa.ready():
                                tempos.append(tarefa.get())
                                p['feito'] = True
                                _salvar_estado(estf, est)
                                tarefas.remove((p, tarefa))
                        if tarefas:
                            time.sleep(.02)  # o supervisor externo limita inclusive processos/FFmpeg travados
                    feitas_nesta += len(lote)
                    est["seg_por_parte"] = max(tempos)
                    _salvar_estado(estf, est)
        feitos = sum(p["feito"] for p in est["partes"])
        if feitos < len(est["partes"]) or time.time() - t0 > tempo_max - 20:
            return {"concluido": False, "progresso": feitos / len(est["partes"]) * 0.95,
                    "detalhe": f"montando o vídeo ({feitos}/{len(est['partes'])} trechos)"}
    if not est["audio"]:
        _contar_tentativa(est, 'tentativas_audio', 'áudio')
        _salvar_estado(estf, est)
        if preparar_audio:
            preparar_audio(str(D / "audio.wav"))
        est["audio"] = True
        _salvar_estado(estf, est)
    if not est["final"]:
        _contar_tentativa(est, 'tentativas_final', 'junção final')
        _salvar_estado(estf, est)
        lista = D / "lista.txt"
        lista.write_text("".join(linha_concat(D / p["arq"]) for p in est["partes"]), encoding="utf-8")
        cmd = [ffmpeg_bin(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista)]
        if (D / "audio.wav").exists():
            cmd += ["-i", str(D / "audio.wav"), "-map", "0:v:0", "-map", "1:a:0",
                    "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
        cmd += ["-c:v", "copy", "-movflags", "+faststart", "-t", f"{dur:.3f}", str(saida)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            raise RuntimeError(f"Falha ao juntar o vídeo final: {r.stderr[-1500:]}")
        est["final"] = True
        _salvar_estado(estf, est)
    return {"concluido": True, "trabalhou": trabalhou,
            "resultado": {"saida": saida, "quadros": est["total"], "partes": len(est["partes"]),
                          "resolucao": [W, H], "fps": fps}}


def limpar_partes(pasta: str):
    D = Path(pasta) / "_render_partes"
    if D.exists():
        for f in D.glob("*"):
            f.unlink(missing_ok=True)
        D.rmdir()


def _render_parte_uma(args):
    try:  # cada parte já roda num núcleo: evita o OpenCV disputar todos os núcleos
        import cv2
        cv2.setNumThreads(1)
    except Exception:  # noqa: BLE001
        pass
    (video, plano_d, transcricao, rosto_json, mascara, inicio, dur, saida, q_ini) = args
    info, mod, g = _preparar(video, plano_d, transcricao, rosto_json, mascara)
    total = int(round(dur * g.fps))  # nº exato de quadros desta parte (o leitor pode entregar 1 a mais/menos)
    leitor = iter(LeitorDeQuadros(video, g.W, g.H, g.fps, inicio=inicio, duracao=dur + 2 / g.fps))
    lm = None
    if g.tem_mascara:
        lm = iter(LeitorDeQuadros(mascara, g.W, g.H, g.fps, inicio=inicio, duracao=dur + 2 / g.fps, cinza=True))
    esc = EscritorDeVideo(saida, g.W, g.H, g.fps, None, dur + 1 / g.fps, mb_max=800, preset="ultrafast", crf=14)
    ultimo = None
    for n in range(total):
        q = next(leitor, None)
        if q is None:
            if ultimo is None:
                break
            q = ultimo  # faltou um quadro no fim da parte: repete o último
        ultimo = q
        m = None
        if lm is not None:
            mm = next(lm, None)
            m = Image.fromarray(mm, "L") if mm is not None else None
        esc.escrever(_um_quadro(mod, g, q, m, q_ini + n, inicio + n / g.fps))
    esc.fechar()
    return total


def _render_parte(args):
    """Renderiza uma parte; se o FFmpeg falhar (máquina ocupada), tenta mais uma vez."""
    try:
        return _render_parte_uma(args)
    except (RuntimeError, OSError):
        Path(args[7]).unlink(missing_ok=True)
        return _render_parte_uma(args)


def renderizar(video: str, plano_d, saida: str, transcricao: dict | None = None, rosto_json: dict | None = None,
               mascara: str | None = None, audio_wav: str | None = None, mb_max: float | None = None,
               partes: int | None = None, log=print) -> dict:
    """Renderiza o vídeo final inteiro. partes>1 divide o trabalho entre núcleos do processador."""
    t0 = time.time()
    info, mod, g = _preparar(video, plano_d, transcricao, rosto_json, mascara)
    dur = info.duracao
    if mb_max is None:
        mb_max = 25.0 if dur <= 75 else 45.0
    nucleos = os.cpu_count() or 2
    partes = partes or max(1, min(4, nucleos - 1, math.ceil(dur / 8)))
    tmp = Path(tempfile.mkdtemp(prefix="editor_rg_"))
    total_q = int(round(dur * g.fps))
    por = math.ceil(total_q / partes)
    tarefas = []
    for k in range(partes):
        qi = k * por
        if qi >= total_q:
            break
        qn = min(por, total_q - qi)
        tarefas.append((video, plano_d, transcricao, rosto_json, mascara, qi / g.fps, qn / g.fps,
                        str(tmp / f"parte{k:02d}.mkv"), qi))
    log(f"Montando {total_q} quadros {g.W}x{g.H} em {len(tarefas)} parte(s)…")
    if len(tarefas) == 1:
        feitos = [_render_parte(tarefas[0])]
    else:
        import multiprocessing as mpc
        ctx = mpc.get_context("spawn")
        with ctx.Pool(len(tarefas)) as pool:
            feitos = pool.map(_render_parte, tarefas)
    lista = tmp / "lista.txt"
    lista.write_text("".join(linha_concat(t[7]) for t in tarefas), encoding="utf-8")
    # junta as partes, coloca o áudio e comprime no tamanho final
    from .midia import bitrate_alvo_kbps
    teto = bitrate_alvo_kbps(dur, mb_max)
    cmd = [ffmpeg_bin(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista)]
    if audio_wav:
        cmd += ["-i", str(audio_wav), "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
    cmd += ["-c:v", "libx264", "-preset", "faster", "-crf", "20", "-maxrate", f"{teto}k", "-bufsize", f"{teto * 2}k",
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-movflags", "+faststart", "-t", f"{dur:.3f}", str(saida)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"Falha ao finalizar o vídeo: {r.stderr[-1500:]}")
    for f in tmp.glob("*"):
        f.unlink(missing_ok=True)
    tmp.rmdir()
    return {"saida": saida, "quadros": sum(feitos), "segundos_render": round(time.time() - t0, 1),
            "partes": len(tarefas), "resolucao": [g.W, g.H], "fps": g.fps}


def quadros_de_previa(video: str, plano_d, tempos: list[float], saida_jpg: str, transcricao=None, rosto_json=None,
                      mascara=None, largura_miniatura: int = 360) -> str:
    """Renderiza só alguns instantes e monta uma folha — conferência rápida ANTES do render completo."""
    info, mod, g = _preparar(video, plano_d, transcricao, rosto_json, mascara)
    imgs = []
    for k, t in enumerate(tempos):
        t = max(0.0, min(info.duracao - 1 / g.fps, t))
        q = next(iter(LeitorDeQuadros(video, g.W, g.H, g.fps, inicio=t, duracao=1.5 / g.fps)), None)
        if q is None:
            continue
        m = None
        if g.tem_mascara:
            mm = next(iter(LeitorDeQuadros(mascara, g.W, g.H, g.fps, inicio=t, duracao=1.5 / g.fps, cinza=True)), None)
            m = Image.fromarray(mm, "L") if mm is not None else None
        out = Image.fromarray(_um_quadro(mod, g, q, m, int(t * g.fps), t))
        mini = out.resize((largura_miniatura, int(largura_miniatura * g.H / g.W)), Image.LANCZOS)
        imgs.append((t, mini))
    if not imgs:
        raise RuntimeError("Nenhum quadro de prévia gerado.")
    cols = min(5, len(imgs))
    linhas = math.ceil(len(imgs) / cols)
    mw, mh = imgs[0][1].size
    folha = Image.new("RGB", (cols * (mw + 8) - 8, linhas * (mh + 34) - 8), (16, 16, 18))
    for k, (t, im) in enumerate(imgs):
        x, y = (k % cols) * (mw + 8), (k // cols) * (mh + 34)
        folha.paste(im, (x, y + 26))
        img_rot = Image.new("RGBA", (mw, 26), (0, 0, 0, 0))
        d.escrever(img_rot, (6, 3), [f"{t:.2f}s"], d.fonte(18, 700), "#D4FF1F")
        folha.paste(img_rot, (x, y), img_rot)
    folha.save(saida_jpg, quality=88)
    return saida_jpg
