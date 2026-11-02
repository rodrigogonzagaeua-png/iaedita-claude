"""Recorte da pessoa (máscara alfa) ao longo do vídeo, para elementos passarem ATRÁS dela.

Ordem de tentativa (a primeira que funcionar):
 1. RVM (Robust Video Matting) em ONNX: melhor qualidade e estável no tempo. O modelo (15 MB)
    é baixado do GitHub do projeto na primeira vez, se o ambiente tiver internet.
 2. MediaPipe Selfie Segmentation (se instalado): rápido, bordas mais simples.
 3. rembg (se instalado): por quadro, mais lento.
Sem nenhum: devolve None e o estilo usa o modo sem oclusão (e o agente avisa o cliente).

A máscara é gravada em meia resolução (FFV1, sem perda) e reaproveitada entre edições."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

from .midia import (EscritorDeMascara, LeitorDeQuadros, ffmpeg_bin, fps_de_saida, linha_concat, nucleos, sha256_do_arquivo,
                    sondar, tamanho_de_trabalho)

URL_RVM = "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx"
NOME_RVM = "rvm_mobilenetv3_fp32.onnx"
SHA256_RVM = {URL_RVM: "88d4531297118f595bf2fd60f6f566aec2e559393802d1f436c380f0cbbd2828"}  # só o endereço oficial é conferido


def _pastas_modelo():
    out = []
    if os.environ.get("EDITOR_RG_MODELOS"):
        out.append(Path(os.environ["EDITOR_RG_MODELOS"]))
    out += [Path(__file__).resolve().parent.parent / "modelos", Path.home() / ".cache" / "editor_rg",
            Path("/tmp/editor_rg_modelos")]
    return out


def baixar_rvm_por_etapas(prazo: float) -> dict:
    """Baixa o modelo RVM aos poucos: retoma de onde parou (Range), para no prazo (hora em time.time()) e só
    desiste depois de 3 recomeços do zero ou 3 chamadas seguidas sem nenhum byte novo. Nunca deixa modelo pela
    metade com o nome final. Devolve {"modelo": Path | None, "progresso", "desistiu", "detalhe"}."""
    pasta = None
    for p in _pastas_modelo()[1:]:  # a primeira pasta gravável (a do EDITOR_RG_MODELOS só é lida, como antes)
        try:
            p.mkdir(parents=True, exist_ok=True)
            if os.access(p, os.W_OK):
                pasta = p
                break
        except OSError:
            continue
    if pasta is None:
        return {"modelo": None, "progresso": 0.0, "desistiu": True, "detalhe": "nenhuma pasta gravável para o modelo"}
    destino = pasta / NOME_RVM
    if destino.exists() and destino.stat().st_size > 10_000_000:
        return {"modelo": destino, "progresso": 1.0, "desistiu": False, "detalhe": "modelo de recorte pronto"}
    tmp, estf = pasta / (NOME_RVM + ".baixando"), pasta / (NOME_RVM + ".baixando.json")
    try:
        est = json.loads(estf.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001  sem estado (ou estado estragado): começa do zero
        est = {}
    est = {"bytes": 0, "total": 0, "sem_progresso": 0, "recomecos": 0, **est}

    def resposta(modelo=None, desistiu=False, erro=None):
        feito = tmp.stat().st_size if tmp.exists() else 0
        pct = 100.0 if modelo else (100.0 * feito / est["total"] if est["total"] else 0.0)
        if desistiu:  # zera as tentativas: o próximo vídeo tenta de novo (como o modelo de transcrição)
            tmp.unlink(missing_ok=True)
            estf.unlink(missing_ok=True)
        detalhe = ("modelo de recorte pronto" if modelo else
                   f"não deu para baixar o modelo de recorte: {erro}" if desistiu else
                   f"baixando o modelo de recorte ({pct:.0f}%, só na 1ª vez)")
        return {"modelo": modelo, "progresso": round(pct / 100, 4), "desistiu": desistiu, "detalhe": detalhe}

    ja = tmp.stat().st_size if tmp.exists() else 0
    est["bytes"] = ja
    estf.write_text(json.dumps(est), encoding="utf-8")  # grava ANTES da leitura arriscada
    erro, acabou, integridade = None, False, False
    pedido = urllib.request.Request(URL_RVM, headers={"Range": f"bytes={ja}-", "User-Agent": "editor-rg"})
    try:  # espera curta: conexão congelada não pode levar a chamada além do prazo
        with urllib.request.urlopen(pedido, timeout=max(1.0, min(8.0, prazo - time.time()))) as r:
            if r.status == 206:  # retomada aceita: "bytes ini-fim/total"
                import re
                intervalo = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', r.headers.get('Content-Range', ''))
                if not intervalo or int(intervalo[1]) != ja or int(intervalo[2]) + 1 != int(intervalo[3]):
                    integridade = True
                    raise ValueError('intervalo do download inconsistente')
                total = int(intervalo[3])
                if est['total'] and est['total'] != total:
                    integridade = True
                    raise ValueError('tamanho do modelo mudou durante a retomada')
                est["total"] = total
            else:  # o servidor ignorou a retomada: recomeça do zero
                if ja:  # recomeço conta ANTES de baixar de novo; o 3º vira desistência
                    est["recomecos"] += 1
                    estf.write_text(json.dumps(est), encoding="utf-8")
                    if est["recomecos"] > 2:
                        return resposta(desistiu=True,
                                        erro="o servidor não deixa retomar o download (proxy ou espelho)")
                ja, est["total"] = 0, int(r.headers.get("Content-Length") or 0)
            if est['total'] <= 10_000_000:
                integridade = True
                raise ValueError('servidor não informou um tamanho válido para o modelo')
            with open(tmp, "ab" if ja else "wb") as f:
                while time.time() < prazo:
                    bloco = r.read1(1 << 16)  # read1: devolve o que chegou (read esperaria o bloco inteiro)
                    if not bloco:
                        acabou = True
                        break
                    f.write(bloco)
    except urllib.error.HTTPError as exc:
        if exc.code == 416:  # o pedaço guardado não bate com o arquivo do servidor: recomeça
            tmp.unlink(missing_ok=True)
        erro = f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001  sem internet, conexão caiu, servidor parou de responder
        erro = f"{type(exc).__name__}: {str(exc)[:160]}"
    feito = tmp.stat().st_size if tmp.exists() else 0
    if not integridade and est['total'] and feito == est['total']:
        esperado = SHA256_RVM.get(URL_RVM)
        if esperado and sha256_do_arquivo(tmp) != esperado:  # conta como as outras falhas de integridade, logo abaixo
            integridade, erro = True, "o arquivo baixado não confere com o modelo oficial"
        elif feito > 10_000_000:
            tmp.replace(destino)
            estf.unlink(missing_ok=True)
            return resposta(modelo=destino)
        else:
            tmp.unlink(missing_ok=True)  # "terminou" pequeno demais: não é o modelo
            erro, feito = "o arquivo baixado não é o modelo", 0
    if integridade or feito > est['total'] or (acabou and feito != est['total']):
        est['falhas_integridade'] = est.get('falhas_integridade', 0) + 1
        tmp.unlink(missing_ok=True)
        feito = est['bytes'] = est['total'] = 0
        if est['falhas_integridade'] >= 3:
            return resposta(desistiu=True, erro=erro or 'download incompleto ou tamanho inconsistente')
    est["sem_progresso"] = 0 if feito > est["bytes"] else est["sem_progresso"] + 1
    est["bytes"] = feito
    estf.write_text(json.dumps(est), encoding="utf-8")
    if est["sem_progresso"] >= 3:
        return resposta(desistiu=True, erro=erro or "o download não avançou em 3 tentativas")
    return resposta()


def achar_rvm(baixar: bool = True, prazo: float | None = None) -> Path | None:
    for p in _pastas_modelo():
        if (p / NOME_RVM).exists() and (p / NOME_RVM).stat().st_size > 10_000_000:
            return p / NOME_RVM
    if not baixar:
        return None
    return baixar_rvm_por_etapas(prazo or time.time() + 30)["modelo"]


def backends_disponiveis(baixar: bool = False) -> list[str]:
    b = []
    try:
        import onnxruntime  # noqa: F401
        if achar_rvm(baixar=baixar):
            b.append("rvm")
        else:
            b.append("rvm (falta baixar o modelo)")
    except Exception:  # noqa: BLE001
        pass
    try:
        import mediapipe as mp  # noqa: F401
        if hasattr(mp, "solutions"):
            b.append("mediapipe")
    except Exception:  # noqa: BLE001
        pass
    try:
        import rembg  # noqa: F401
        b.append("rembg")
    except Exception:  # noqa: BLE001
        pass
    return b


class _RVM:
    def __init__(self, modelo: Path, w: int, h: int, base: int = 512):
        import onnxruntime as ort
        op = ort.SessionOptions()
        op.intra_op_num_threads = max(1, min(8, nucleos()))
        op.inter_op_num_threads = 1
        try:
            self.s = ort.InferenceSession(str(modelo), sess_options=op, providers=["CPUExecutionProvider"])
        except Exception as exc:
            # Somente erros de formato comprovados; memória/dependências não invalidam o arquivo.
            if type(exc).__module__.startswith('onnxruntime') and type(exc).__name__ in ('InvalidProtobuf', 'InvalidGraph'):
                modelo.unlink(missing_ok=True)
            raise
        self.r = [np.zeros((1, 1, 1, 1), np.float32)] * 4
        self.ratio = np.array([min(1.0, base / max(w, h))], np.float32)

    def salvar(self, arq: Path):
        np.savez(arq, *self.r)

    def carregar(self, arq: Path):
        if arq.exists():
            d = np.load(arq)
            self.r = [d[f"arr_{i}"] for i in range(4)]

    def __call__(self, rgb: np.ndarray) -> np.ndarray:
        src = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
        feed = {"src": src, "downsample_ratio": self.ratio}
        feed.update({f"r{i + 1}i": v for i, v in enumerate(self.r)})
        fgr, pha, *rs = self.s.run(None, feed)
        self.r = rs
        return (np.clip(pha[0, 0], 0, 1) * 255).astype(np.uint8)


class _MediaPipe:
    def __init__(self):
        import mediapipe as mp
        self.m = mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=0)
        self.ant = None

    def __call__(self, rgb):
        r = self.m.process(rgb).segmentation_mask
        m = np.clip((r - 0.25) / 0.5, 0, 1)
        if self.ant is not None:  # estabiliza tremulação entre quadros
            m = 0.6 * m + 0.4 * self.ant
        self.ant = m
        return (m * 255).astype(np.uint8)


class _Rembg:
    def __init__(self):
        from rembg import new_session, remove
        self.remove = remove
        self.sess = new_session("u2net_human_seg")
        self.ant = None

    def __call__(self, rgb):
        m = np.asarray(self.remove(Image.fromarray(rgb), session=self.sess, only_mask=True), np.float32) / 255
        if self.ant is not None:
            m = 0.6 * m + 0.4 * self.ant
        self.ant = m
        return (m * 255).astype(np.uint8)


URL_U2H = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx"
NOME_U2H = "u2net_human_seg.onnx"


def achar_u2h(baixar: bool = True) -> Path | None:
    for p in _pastas_modelo() + [Path.home() / ".u2net"]:
        if (p / NOME_U2H).exists() and (p / NOME_U2H).stat().st_size > 100_000_000:
            return p / NOME_U2H
    if not baixar:
        return None
    for p in _pastas_modelo()[1:]:
        try:
            p.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(URL_U2H, p / NOME_U2H)
            if (p / NOME_U2H).stat().st_size > 100_000_000:
                return p / NOME_U2H
        except Exception:  # noqa: BLE001
            continue
    return None


class _ReforcoCorpo:
    """Máscaras do corpo inteiro (U2Net humano) a cada 0,5 s, interpoladas no tempo."""

    def __init__(self, video: str, w: int, h: int, baixar: bool = True, passo: float = 0.5):
        import onnxruntime as ort
        mod = achar_u2h(baixar)
        if not mod:
            raise RuntimeError("modelo U2Net humano indisponível")
        op = ort.SessionOptions()
        op.intra_op_num_threads = max(1, min(8, os.cpu_count() or 2))
        s = ort.InferenceSession(str(mod), sess_options=op, providers=["CPUExecutionProvider"])
        nome_in = s.get_inputs()[0].name
        media = np.array([0.485, 0.456, 0.406], np.float32)
        desvio = np.array([0.229, 0.224, 0.225], np.float32)
        self.passo = passo
        self.chaves = []
        for q in LeitorDeQuadros(video, 320, 320, 1.0 / passo):
            x = (q.astype(np.float32) / 255.0 - media) / desvio
            out = s.run(None, {nome_in: x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0, 0]
            out = (out - out.min()) / max(1e-6, out.max() - out.min())
            m = Image.fromarray((out * 255).astype(np.uint8), "L").resize((w, h), Image.BILINEAR)
            self.chaves.append(np.asarray(m, np.float32) / 255.0)
        self.h = h
        self.linhas = np.arange(h, dtype=np.float32)[:, None]

    def combinar(self, m_rvm: np.ndarray, t: float, queixo_y: float) -> np.ndarray:
        if not self.chaves:
            return m_rvm
        k = t / self.passo
        i0 = min(int(k), len(self.chaves) - 1)
        i1 = min(i0 + 1, len(self.chaves) - 1)
        f = k - int(k)
        prior = self.chaves[i0] * (1 - f) + self.chaves[i1] * f
        prior = np.clip((prior - 0.18) / 0.32, 0, 1)  # endurece a borda do corpo
        # só abaixo do queixo (cabelo e rosto ficam com o RVM, que é mais fino), transição suave
        peso = np.clip((self.linhas - (queixo_y - self.h * 0.03)) / (self.h * 0.05), 0, 1)
        rvm = m_rvm.astype(np.float32) / 255.0
        return (np.maximum(rvm, prior * peso) * 255).astype(np.uint8)


def gerar_mascara(video: str, saida: str, preferir: str | None = None, baixar: bool = True,
                  largura_trabalho: int = 540, relatorio: str | None = None, rosto_dados: dict | None = None,
                  reforcar_corpo: bool = True) -> dict:
    """Gera a máscara da pessoa para o vídeo inteiro. Devolve relatório com tempo e método."""
    info = sondar(video)
    W, H = tamanho_de_trabalho(info)
    fps = fps_de_saida(info)
    lw = min(largura_trabalho, W)
    lh = int(round(H * lw / W / 2) * 2)
    t0 = time.time()
    motor = None
    metodo = None
    erros = []
    ordem = [preferir] if preferir else []
    ordem += [m for m in ("rvm", "mediapipe", "rembg") if m not in ordem]
    for m in ordem:
        try:
            if m == "rvm":
                mod = achar_rvm(baixar=baixar)
                if not mod:
                    raise RuntimeError("modelo RVM indisponível (sem internet para baixar?)")
                motor = _RVM(mod, lw, lh)
            elif m == "mediapipe":
                motor = _MediaPipe()
            elif m == "rembg":
                motor = _Rembg()
            metodo = m
            break
        except Exception as exc:  # noqa: BLE001
            erros.append(f"{m}: {exc}")
    if motor is None:
        res = {"ok": False, "metodo": None, "erros": erros,
               "aviso": "Nenhum método de recorte disponível. Use o modo sem oclusão do estilo e avise o cliente."}
        if relatorio:
            Path(relatorio).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return res
    # Reforço do corpo: o RVM às vezes perde o tronco em plano fechado (roupa parecida com a parede).
    # O U2Net humano (Apache-2.0) acha o corpo inteiro; roda só 2x por segundo e entra abaixo do queixo.
    corpo = None
    if metodo == "rvm" and reforcar_corpo:
        try:
            corpo = _ReforcoCorpo(video, lw, lh, baixar=baixar)
        except Exception as exc:  # noqa: BLE001
            erros.append(f"reforço do corpo: {exc}")
    rosto = None
    if rosto_dados:
        from .rosto import Rosto
        rosto = Rosto(rosto_dados, lw, lh)
    esc = EscritorDeMascara(saida, lw, lh, fps)
    n = 0
    cobertura = []
    for q in LeitorDeQuadros(video, lw, lh, fps):
        m = motor(np.ascontiguousarray(q))
        if corpo is not None:
            t = n / fps
            queixo = rosto.queixo(t) if rosto else lh * 0.45
            m = corpo.combinar(m, t, queixo)
        esc.escrever(m)
        if n % 15 == 0:
            cobertura.append(float((m > 128).mean()))
        n += 1
    esc.fechar()
    dt = time.time() - t0
    if corpo is not None:
        metodo += "+corpo-u2net"
    res = {"ok": True, "metodo": metodo, "arquivo": str(saida), "quadros": n, "tamanho": [lw, lh],
           "segundos": round(dt, 1), "ms_por_quadro": round(dt * 1000 / max(n, 1), 1),
           "area_media_pessoa": round(float(np.mean(cobertura)) if cobertura else 0, 3), "erros": erros}
    if res["area_media_pessoa"] < 0.03:
        res["aviso"] = "A máscara quase não encontrou pessoa. Confira a folha de quadros antes de usar oclusão."
    if relatorio:
        Path(relatorio).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


class _CorpoU2Net:
    """Reforço do corpo (opcional): U2Net humano a cada 0,5 s, guardando o último resultado."""

    def __init__(self, w: int, h: int, baixar: bool = True):
        import onnxruntime as ort
        mod = achar_u2h(baixar)
        if not mod:
            raise RuntimeError("modelo U2Net humano indisponível")
        op = ort.SessionOptions()
        op.intra_op_num_threads = max(1, min(8, nucleos()))
        self.s = ort.InferenceSession(str(mod), sess_options=op, providers=["CPUExecutionProvider"])
        self.nome_in = self.s.get_inputs()[0].name
        self.w, self.h = w, h
        self.linhas = np.arange(h, dtype=np.float32)[:, None]
        self.prior = None

    def atualizar(self, rgb: np.ndarray):
        media = np.array([0.485, 0.456, 0.406], np.float32)
        desvio = np.array([0.229, 0.224, 0.225], np.float32)
        x = np.asarray(Image.fromarray(rgb).resize((320, 320), Image.BILINEAR), np.float32) / 255.0
        x = (x - media) / desvio
        out = self.s.run(None, {self.nome_in: x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0, 0]
        out = (out - out.min()) / max(1e-6, out.max() - out.min())
        m = np.asarray(Image.fromarray((out * 255).astype(np.uint8), "L").resize((self.w, self.h), Image.BILINEAR),
                       np.float32) / 255.0
        self.prior = np.clip((m - 0.18) / 0.32, 0, 1)

    def combinar(self, m_rvm: np.ndarray, queixo_y: float) -> np.ndarray:
        if self.prior is None:
            return m_rvm
        peso = np.clip((self.linhas - (queixo_y - self.h * 0.03)) / (self.h * 0.05), 0, 1)
        rvm = m_rvm.astype(np.float32) / 255.0
        return (np.maximum(rvm, self.prior * peso) * 255).astype(np.uint8)


def gerar_mascara_por_etapas(video: str, pasta: str, tempo_max: float = 40.0, preferir: str | None = None,
                             baixar: bool = True, largura_trabalho: int = 540, base_rvm: int = 384,
                             reforco: bool = False, rosto_dados: dict | None = None) -> dict:
    """Recorte da pessoa em fatias que cabem em tempo_max segundos, com progresso salvo
    (inclusive a memória do RVM entre quadros). Chame de novo até concluido=True.
    base_rvm=384: medido em 1 processador, 154 ms por quadro contra 247 ms com 512, com o mesmo recorte."""
    import time
    t0 = time.time()
    P = Path(pasta)
    D = P / "_recorte_partes"
    D.mkdir(parents=True, exist_ok=True)
    estf = D / "estado.json"
    info = sondar(video)
    W, H = tamanho_de_trabalho(info)
    fps = fps_de_saida(info)
    lw = min(largura_trabalho, W)
    lh = int(round(H * lw / W / 2) * 2)
    total = int(round(info.duracao * fps))
    chave = [str(video), lw, lh, base_rvm, bool(reforco), preferir]
    est = json.loads(estf.read_text(encoding="utf-8")) if estf.exists() else None
    if not est or est.get("chave") != chave:
        for f in D.glob("*"):
            f.unlink(missing_ok=True)
        est = {"chave": chave, "proximo": 0, "segmentos": [], "metodo": None, "seg_por_quadro": None,
               "cobertura": [], "erros": [], "segundos": 0.0}
    motor, metodo, erros = None, est.get("metodo"), list(est.get("erros", []))
    ordem = [metodo] if metodo else ([preferir] if preferir else [])
    ordem += [m for m in ("rvm", "mediapipe", "rembg") if m not in ordem]
    for m in ordem:
        try:
            if m == "rvm":
                r = baixar_rvm_por_etapas(t0 + tempo_max - 10) if baixar and not achar_rvm(baixar=False) else None
                if r and not r["modelo"] and not r["desistiu"]:  # ainda baixando: volta na próxima chamada
                    return {"concluido": False, "progresso": 0.0, "detalhe": r["detalhe"]}
                mod = (r and r["modelo"]) or achar_rvm(baixar=False)
                if not mod:
                    raise RuntimeError("modelo RVM indisponível (sem internet para baixar?)")
                if r and r["modelo"] and time.time() - t0 > tempo_max - 12:  # baixou agora: recorta na próxima
                    return {"concluido": False, "progresso": 0.0, "detalhe": "modelo de recorte pronto"}
                motor = _RVM(mod, lw, lh, base=base_rvm)
                if est["proximo"] > 0:
                    motor.carregar(D / "rvm_estado.npz")
            elif m == "mediapipe":
                motor = _MediaPipe()
            elif m == "rembg":
                motor = _Rembg()
            metodo = m
            break
        except Exception as exc:  # noqa: BLE001
            erros.append(f"{m}: {exc}")
    if motor is None:
        res = {"ok": False, "metodo": None, "erros": erros,
               "aviso": "Nenhum método de recorte disponível. Use o modo sem recorte do estilo e avise o cliente."}
        (P / "recorte.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"concluido": True, "resultado": res}
    corpo = None
    if reforco and metodo == "rvm":
        try:
            corpo = _CorpoU2Net(lw, lh, baixar=baixar)
        except Exception as exc:  # noqa: BLE001
            erros.append(f"reforço do corpo: {exc}")
    rosto = None
    if rosto_dados:
        from .rosto import Rosto
        rosto = Rosto(rosto_dados, lw, lh)
    n0 = est["proximo"]
    if n0 < total:
        spq = est["seg_por_quadro"] or 0.35
        cabe = int(max(15, (tempo_max - (time.time() - t0) - 3) / spq))
        n_fim = min(total, n0 + cabe)
        seg = f"s{len(est['segmentos']):04d}.mkv"
        esc = EscritorDeMascara(str(D / seg), lw, lh, fps)
        leitor = LeitorDeQuadros(video, lw, lh, fps, inicio=n0 / fps, duracao=(n_fim - n0 + 2) / fps)
        it = iter(leitor)
        ult_f = D / "ultimo_quadro.npy"  # o som pode durar mais que a imagem: o trecho seguinte repete este quadro
        ultimo, feitos, t1 = (np.load(ult_f) if n0 > 0 and ult_f.exists() else None), 0, time.time()
        passo_corpo = max(1, int(round(fps * 0.5)))
        try:
            for n in range(n0, n_fim):
                q = next(it, None)
                if q is None:
                    if ultimo is None:
                        break
                    q = ultimo
                ultimo = q
                q = np.ascontiguousarray(q)
                m = motor(q)
                if corpo is not None:
                    if (n - n0) % passo_corpo == 0:
                        corpo.atualizar(q)
                    m = corpo.combinar(m, rosto.queixo(n / fps) if rosto else lh * 0.45)
                esc.escrever(m)
                if (n % 30) == 0:
                    est["cobertura"].append(float((m > 128).mean()))
                feitos += 1
                if time.time() - t0 > tempo_max - 2:
                    break
        finally:
            esc.fechar()
            try:
                leitor.fechar()
            except Exception:  # noqa: BLE001
                pass
        est["segmentos"].append(seg)
        est["proximo"] = n0 + feitos
        est["seg_por_quadro"] = (time.time() - t1) / max(feitos, 1)
        est["segundos"] += time.time() - t0
        est["metodo"], est["erros"] = metodo, erros
        if isinstance(motor, _RVM):
            motor.salvar(D / "rvm_estado.npz")
        if ultimo is not None:  # grava inteiro e só então troca: chamada cortada não deixa o arquivo pela metade
            np.save(D / "ultimo_quadro.tmp.npy", ultimo)
            (D / "ultimo_quadro.tmp.npy").replace(ult_f)
        estf.write_text(json.dumps(est), encoding="utf-8")
    if est["proximo"] < total:
        return {"concluido": False, "progresso": est["proximo"] / total,
                "detalhe": f"recortando a pessoa ({est['proximo']}/{total} quadros)"}
    lista = D / "lista.txt"
    lista.write_text("".join(linha_concat(D / sg) for sg in est["segmentos"]), encoding="utf-8")
    saida = P / "mascara.mkv"
    import subprocess
    r = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lista),
                        "-c", "copy", str(saida)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"Falha ao juntar a máscara: {r.stderr[-800:]}")
    area = round(float(np.mean(est["cobertura"])) if est["cobertura"] else 0.0, 3)
    met = est["metodo"] + ("+corpo-u2net" if reforco and est["metodo"] == "rvm" else "")
    res = {"ok": True, "metodo": met, "arquivo": str(saida), "quadros": total, "tamanho": [lw, lh],
           "segundos": round(est["segundos"], 1), "ms_por_quadro": round(est["seg_por_quadro"] * 1000, 1),
           "area_media_pessoa": area, "erros": est["erros"]}
    if area < 0.03:
        res["aviso"] = "A máscara quase não encontrou pessoa. Confira a folha antes de usar o recorte."
    (P / "recorte.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for f in D.glob("*"):
        f.unlink(missing_ok=True)
    D.rmdir()
    return {"concluido": True, "resultado": res}


def amostra_visual(video: str, mascara: str, saida_jpg: str, n: int = 6) -> str:
    """Folha com a pessoa recortada sobre fundo xadrez magenta: mostra erros de recorte
    (pedaços de fundo grudados, cabelo comido) para o agente conferir. Busca cada quadro direto."""
    from .midia import quadro_rgb
    info = sondar(video)
    W = 270
    H = int(round(info.altura * W / info.largura / 2) * 2)
    xad = np.indices((H, W)).sum(axis=0) // 18 % 2
    fundo = np.where(xad[..., None] == 0, [255, 0, 200], [120, 0, 90]).astype(np.uint8)
    folha = Image.new("RGB", (W * n + 6 * (n - 1), H), (0, 0, 0))
    for i in range(n):
        t = (i + 0.5) * info.duracao / n
        q = quadro_rgb(video, t, W)
        mm = quadro_rgb(mascara, t, W)
        if q is None or mm is None:
            continue
        q = np.asarray(Image.fromarray(q).resize((W, H)))
        a = (np.asarray(Image.fromarray(mm).convert("L").resize((W, H)), np.float32) / 255)[..., None]
        comp = (q * a + fundo * (1 - a)).astype(np.uint8)
        folha.paste(Image.fromarray(comp), (i * (W + 6), 0))
    folha.save(saida_jpg, quality=85)
    return saida_jpg


# borda firme: 0-25% de alfa vira 0 (auréola), 75-100% vira cheio, e o meio fica 2x mais íngreme
_FIRME = [0 if v <= 64 else 255 if v >= 191 else int(round((v - 64) * 255 / 127)) for v in range(256)]


def firmar_borda(mascara: Image.Image) -> Image.Image:
    """Estreita a faixa meio transparente da borda (a máscara é feita em 540 px e esticada para o vídeo, o que
    deixa a borda larga e a pessoa "borrada" sobre o fundo novo). O contorno (alfa 50%) fica no mesmo lugar."""
    return mascara.point(_FIRME)


class LeitorDeMascara:
    """Lê a máscara em sincronia com os quadros do render, já no tamanho de saída."""

    def __init__(self, mascara: str | None, W: int, H: int, fps: float):
        self.it = iter(LeitorDeQuadros(mascara, W, H, fps, cinza=True)) if mascara and Path(mascara).exists() else None

    def proxima(self) -> Image.Image | None:
        if not self.it:
            return None
        try:
            return firmar_borda(Image.fromarray(next(self.it), "L"))
        except StopIteration:
            self.it = None
            return None
