"""Leitura e escrita de vídeo via FFmpeg (canos de quadros crus, sem PNG em disco)."""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def sha256_do_arquivo(arquivo: Path) -> str:
    """Hash do arquivo inteiro, aos pedaços: o modelo de transcrição tem 484 MB."""
    h = hashlib.sha256()
    with open(arquivo, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def nucleos() -> int:
    """Núcleos que este processo pode usar DE VERDADE (contêiner com cota de CPU informa menos que os da máquina)."""
    import os
    import sys
    env = os.environ.get("EDITOR_RG_NUCLEOS")
    if env:
        return max(1, int(env))
    n = os.cpu_count() or 1
    try:
        n = len(os.sched_getaffinity(0))
    except Exception:  # noqa: BLE001
        pass
    for arq in ("/sys/fs/cgroup/cpu.max",):
        try:
            cota, periodo = open(arq).read().split()[:2]
            if cota != "max":
                n = min(n, max(1, int(cota) // int(periodo)))
        except Exception:  # noqa: BLE001
            pass
    try:
        cota = int(open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read())
        periodo = int(open("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read())
        if cota > 0:
            n = min(n, max(1, cota // periodo))
    except Exception:  # noqa: BLE001
        pass
    if sys.platform == "win32":
        try:
            import psutil
            n = min(n, len(psutil.Process().cpu_affinity()))
        except Exception:  # noqa: BLE001
            pass
    return max(1, n)


def ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:  # FFmpeg empacotado no pip (imageio-ffmpeg), útil quando o sistema não tem
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("FFmpeg não encontrado. Tente: python3 -m pip install -q --disable-pip-version-check --timeout 8 --retries 1 imageio-ffmpeg") from exc


def ffprobe_bin() -> str | None:
    exe = shutil.which("ffprobe")
    if exe:
        return exe
    irmao = Path(ffmpeg_bin()).with_name("ffprobe" + Path(ffmpeg_bin()).suffix)
    return str(irmao) if irmao.exists() else None


def linha_concat(arq) -> str:
    """Uma linha da lista do concat. O FFmpeg lê o caminho a partir da pasta da LISTA (não da pasta onde o
    motor roda): vai o caminho completo, e o apóstrofo escapado do jeito do FFmpeg (pasta "D'Avila")."""
    return "file '" + Path(arq).resolve().as_posix().replace("'", "'\\''") + "'\n"


@dataclass
class InfoVideo:
    caminho: str
    largura: int          # já considerando a rotação gravada pelo celular
    altura: int
    fps: float
    duracao: float
    tem_audio: bool
    codec: str
    tamanho_mb: float

    def para_dict(self) -> dict:
        return self.__dict__.copy()


def _fracao(txt: str | None) -> float:
    if not txt or txt in ("0/0", "N/A"):
        return 0.0
    if "/" in txt:
        a, b = txt.split("/")
        return float(a) / float(b) if float(b) else 0.0
    return float(txt)


def sondar(caminho: str | Path) -> InfoVideo:
    """Lê dimensões, fps, duração e rotação. Usa ffprobe; sem ffprobe, decodifica 1 quadro."""
    caminho = str(caminho)
    probe = ffprobe_bin()
    tamanho_mb = Path(caminho).stat().st_size / 1_048_576
    if probe:
        r = subprocess.run(
            [probe, "-v", "error", "-show_streams", "-show_format", "-of", "json", caminho],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
        d = json.loads(r.stdout)
        v = next(s for s in d["streams"] if s.get("codec_type") == "video"
                 and not s.get("disposition", {}).get("attached_pic"))
        w, h = int(v["width"]), int(v["height"])
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(float(sd["rotation"]))
        rot = rot or int(float(v.get("tags", {}).get("rotate", 0) or 0))
        if abs(rot) % 180 == 90:
            w, h = h, w
        fps = _fracao(v.get("avg_frame_rate")) or _fracao(v.get("r_frame_rate")) or 30.0
        dur = float(d["format"].get("duration") or v.get("duration") or 0)
        tem_audio = any(s.get("codec_type") == "audio" for s in d["streams"])
        return InfoVideo(caminho, w, h, round(fps, 3), dur, tem_audio, v.get("codec_name", "?"), round(tamanho_mb, 1))
    # sem ffprobe: pede ao ffmpeg as informações pelo texto de erro
    r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-i", caminho], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    import re
    txt = r.stderr
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", txt)
    f = re.search(r"(\d+(?:\.\d+)?) fps", txt)
    du = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", txt)
    w, h = (int(m.group(1)), int(m.group(2))) if m else (1080, 1920)
    if "rotate" in txt and re.search(r"rotat\w*\D+-?90", txt):
        w, h = h, w
    dur = int(du.group(1)) * 3600 + int(du.group(2)) * 60 + float(du.group(3)) if du else 0.0
    return InfoVideo(caminho, w, h, float(f.group(1)) if f else 30.0, dur, "Audio:" in txt, "?", round(tamanho_mb, 1))


def tamanho_de_trabalho(info: InfoVideo, lado_max: int = 1920) -> tuple[int, int]:
    """Resolução de saída: mantém a do vídeo (nunca reduz abaixo da original),
    só limita o lado maior a 1920 e garante números pares."""
    w, h = info.largura, info.altura
    escala = min(1.0, lado_max / max(w, h))
    w2, h2 = int(round(w * escala / 2) * 2), int(round(h * escala / 2) * 2)
    return w2, h2


def fps_de_saida(info: InfoVideo) -> float:
    if info.fps > 31 or info.fps < 20:
        return 30.0
    for padrao in (24.0, 25.0, 30.0):  # celular grava com fps variável (ex.: 30,05): usa o padrão mais próximo
        if abs(info.fps - padrao) < 0.6:
            return padrao
    return round(info.fps, 3)


class LeitorDeQuadros:
    """Entrega quadros RGB (numpy HxWx3 uint8) já no tamanho e fps de trabalho."""

    def __init__(self, caminho: str, w: int, h: int, fps: float, inicio: float = 0.0,
                 duracao: float | None = None, cinza: bool = False):
        self.w, self.h, self.canais = w, h, (1 if cinza else 3)
        cmd = [ffmpeg_bin(), "-v", "error"]
        if inicio > 0:
            cmd += ["-ss", f"{inicio:.3f}"]
        cmd += ["-i", str(caminho)]
        if duracao is not None:
            cmd += ["-t", f"{duracao:.3f}"]
        cmd += ["-an", "-vf", f"fps={fps},scale={w}:{h}:flags=bicubic,setsar=1",
                "-f", "rawvideo", "-pix_fmt", "gray" if cinza else "rgb24", "-"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
        self.bytes_quadro = w * h * self.canais

    def __iter__(self):
        return self

    def __next__(self) -> np.ndarray:
        if self.proc.stdout.closed:  # já acabou: continua avisando o fim (quem pede de novo repete o último quadro)
            raise StopIteration
        buf = self.proc.stdout.read(self.bytes_quadro)
        if len(buf) < self.bytes_quadro:
            self.fechar()
            raise StopIteration
        a = np.frombuffer(buf, np.uint8)
        return a.reshape(self.h, self.w) if self.canais == 1 else a.reshape(self.h, self.w, 3)

    def fechar(self):
        try:
            self.proc.stdout.close()
        except Exception:  # noqa: BLE001
            pass
        self.proc.wait()


def bitrate_alvo_kbps(duracao: float, mb_max: float, audio_kbps: int = 160) -> int:
    total = mb_max * 8 * 1024 / max(duracao, 1.0)  # kbps
    return int(max(1200, min(10000, total * 0.94 - audio_kbps)))


class EscritorDeVideo:
    """Recebe quadros RGB e grava MP4 H.264 + AAC compatível com WhatsApp/Instagram.
    O teto de bitrate garante o tamanho máximo do arquivo."""

    def __init__(self, saida: str, w: int, h: int, fps: float, audio: str | None,
                 duracao: float, mb_max: float = 25.0, preset: str = "veryfast", crf: int = 20,
                 teto_kbps: int | None = None, entrada: str = "rgb24"):
        teto = teto_kbps or bitrate_alvo_kbps(duracao, mb_max)
        cmd = [ffmpeg_bin(), "-v", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", entrada, "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-"]
        if audio:
            cmd += ["-i", str(audio)]
        cmd += ["-map", "0:v:0"] + (["-map", "1:a:0"] if audio else [])
        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                "-maxrate", f"{teto}k", "-bufsize", f"{teto * 2}k",
                "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
                "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                "-movflags", "+faststart", "-t", f"{duracao:.3f}"]
        if audio:
            cmd += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
        cmd += [str(saida)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**8)
        self.n = 0

    def escrever(self, quadro):
        try:
            if isinstance(quadro, (bytes, bytearray, memoryview)):
                dados = quadro
            else:
                dados = np.ascontiguousarray(quadro, dtype=np.uint8).tobytes()
            self.proc.stdin.write(dados)
        except OSError as exc:  # o FFmpeg fechou antes: mostra o motivo real
            err = self.proc.stderr.read().decode("utf-8", "replace") if self.proc.stderr else ""
            raise RuntimeError(f"FFmpeg parou de aceitar quadros (código {self.proc.poll()}): {err[-800:] or exc}") from exc
        self.n += 1

    def fechar(self):
        self.proc.stdin.close()
        err = self.proc.stderr.read().decode("utf-8", "replace")
        if self.proc.wait() != 0:
            raise RuntimeError(f"FFmpeg falhou ao gravar o vídeo: {err[-1500:]}")


class EscritorDeMascara:
    """Grava a máscara da pessoa (cinza) num arquivo compacto sem perda (FFV1)."""

    def __init__(self, saida: str, w: int, h: int, fps: float):
        cmd = [ffmpeg_bin(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray",
               "-s", f"{w}x{h}", "-r", f"{fps}", "-i", "-", "-c:v", "ffv1", "-pix_fmt", "gray", str(saida)]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def escrever(self, m: np.ndarray):
        self.proc.stdin.write(np.ascontiguousarray(m, dtype=np.uint8).tobytes())

    def fechar(self):
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError(self.proc.stderr.read().decode("utf-8", "replace")[-800:])


def extrair_audio(fonte: str, saida_wav: str) -> bool:
    r = subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(fonte), "-vn", "-ac", "1",
                        "-ar", "16000", "-c:a", "pcm_s16le", str(saida_wav)], capture_output=True)
    return r.returncode == 0 and Path(saida_wav).exists()


def quadro_rgb(video: str, t: float, largura: int) -> "np.ndarray | None":
    """Um único quadro no instante t (busca direta: não decodifica o vídeo inteiro)."""
    info_w = None
    r = subprocess.run([ffmpeg_bin(), "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={largura}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return info_w
    from PIL import Image
    import io
    return np.asarray(Image.open(io.BytesIO(r.stdout)).convert("RGB"))


def folha_de_contato(video: str, saida_jpg: str, colunas: int = 5, linhas: int = 2, largura: int = 300) -> str:
    """Grade de quadros espaçados, para o agente CONFERIR o resultado olhando a imagem.
    Busca cada quadro direto (rápido mesmo em vídeo longo com 1 processador)."""
    from PIL import Image
    info = sondar(video)
    n = colunas * linhas
    tempos = [(i + 0.5) * info.duracao / n for i in range(n)]
    quadros = [q for q in (quadro_rgb(video, t, largura) for t in tempos) if q is not None]
    if not quadros:
        raise RuntimeError("Não consegui ler quadros do vídeo para a folha.")
    h, w = quadros[0].shape[:2]
    folha = Image.new("RGB", (colunas * (w + 6) - 6, linhas * (h + 6) - 6), (0, 0, 0))
    for i, q in enumerate(quadros):
        folha.paste(Image.fromarray(q).resize((w, h)), ((i % colunas) * (w + 6), (i // colunas) * (h + 6)))
    folha.save(saida_jpg, quality=85)
    return str(saida_jpg)


def quadro_em(video: str, t: float, saida_jpg: str, largura: int = 540) -> str:
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video),
                    "-frames:v", "1", "-vf", f"scale={largura}:-2", "-q:v", "3", str(saida_jpg)], check=True)
    return str(saida_jpg)


def medir_volume(arquivo: str) -> dict:
    """Loudness integrada (LUFS) e pico, para conferir o áudio sem precisar ouvir."""
    r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-nostats", "-i", str(arquivo), "-vn", "-af",
                        "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    txt = r.stderr
    try:
        bloco = txt[txt.rindex("{"): txt.rindex("}") + 1]
        d = json.loads(bloco)
        return {"lufs": float(d["input_i"]), "pico_db": float(d["input_tp"])}
    except Exception:  # noqa: BLE001
        return {"lufs": math.nan, "pico_db": math.nan}
