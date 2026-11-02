"""Áudio final: voz limpa e no volume certo (-14 LUFS, picos abaixo de -1 dB: padrão de Reels/TikTok),
trilha que abaixa sozinha quando a pessoa fala (ducking) e efeitos sonoros nos momentos do plano."""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import MOTOR, SONS
from .midia import ffmpeg_bin, medir_volume, sondar

MODELO_VOZ = MOTOR / "modelos" / "voz_rnnoise.rnnn"
_ARNNDN = None
TRILHA_FATOR = 0.7  # trilha 30% mais baixa que o volume pedido


def _canais(fonte: str) -> int:
    """Quantos canais tem a 1ª faixa de som (2 quando não dá para saber)."""
    from .midia import ffprobe_bin
    probe = ffprobe_bin()
    if not probe:
        return 2
    r = subprocess.run([probe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=channels",
                        "-of", "csv=p=0", fonte], capture_output=True, text=True)
    try:
        return int(r.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return 2


def _tem_arnndn() -> bool:
    """O FFmpeg deste computador tem o filtro de voz com rede neural (RNNoise)?"""
    global _ARNNDN
    if _ARNNDN is None:
        try:
            r = subprocess.run([ffmpeg_bin(), "-hide_banner", "-filters"], capture_output=True, text=True, timeout=20)
            _ARNNDN = " arnndn " in r.stdout and MODELO_VOZ.exists()
        except Exception:  # noqa: BLE001
            _ARNNDN = False
    return _ARNNDN


def filtro_de_ruido() -> tuple[str, str]:
    """(filtro, nome). Medido num vídeo real com chiado forte somado: RNNoise baixa o fundo ~16 dB sem
    abaixar a voz; o FFT (reserva, quando o FFmpeg não tem RNNoise) baixa só ~5 dB."""
    if _tem_arnndn():
        return f"arnndn=m={MODELO_VOZ.name}", "rnnoise"
    return "afftdn=nr=14:nf=-32:tn=1", "fft"


_KIT = None


def _kit():
    """Catálogo da SFX Kit (CC0): 320 sons de edição de vídeo com o ponto de encaixe de cada um."""
    global _KIT
    if _KIT is None:
        import json
        cat = SONS / "kit" / "catalogo.json"
        if cat.exists():
            d = json.loads(cat.read_text(encoding="utf-8"))
            _KIT = {"apelidos": d.get("apelidos", {}), "sons": {x["id"]: x for x in d["sons"]}}
        else:
            _KIT = {"apelidos": {}, "sons": {}}
    return _KIT


def info_som(nome: str):
    """(caminho, sync_em): sync_em = segundos entre o início do arquivo e o ponto que deve bater no momento."""
    k = _kit()
    nid = k["apelidos"].get(nome, nome)
    if nid in k["sons"]:
        x = k["sons"][nid]
        f = SONS / "kit" / x["arquivo"]
        if f.exists():
            return str(f), float(x.get("sync_em") or 0.0)
    c = resolver_som(nome)
    return (c, 0.0) if c else (None, 0.0)


def resolver_som(nome_ou_caminho: str) -> str | None:
    p = Path(nome_ou_caminho)
    if p.exists():
        return str(p)
    from . import MOTOR
    for pasta in (SONS, MOTOR / "trilhas"):
        for ext in ("", ".wav", ".m4a", ".mp3", ".ogg"):
            c = pasta / f"{Path(nome_ou_caminho).stem if ext else nome_ou_caminho}{ext}"
            if c.exists():
                return str(c)
    return None


def escolher_trilha(clima: str | None = None, energia: str | None = None) -> dict | None:
    """Escolhe a trilha do catálogo pelo clima (ex.: 'motivacional', 'tensao') e energia."""
    import json
    from . import MOTOR
    cat = MOTOR / "trilhas" / "catalogo.json"
    if not cat.exists():
        return None
    itens = [t for t in json.loads(cat.read_text(encoding="utf-8")) if resolver_som(t["arquivo"])]
    if not itens:
        return None
    def nota(t):
        n = 0
        if clima and (clima.lower() in [c.lower() for c in t.get("clima", [])] or clima.lower() == t["nome"]):
            n += 2
        if energia and t.get("energia") == energia:
            n += 1
        return n
    return max(itens, key=nota)


def montar_audio(fonte: str, saida_wav: str, duracao: float, reduzir_ruido: bool = False,
                 trilha: str | None = None, volume_trilha: float = 0.16, efeitos: list[dict] | None = None,
                 lufs: float = -14.0, preservar_voz: bool = False) -> dict:
    """efeitos: [{"som": "whoosh" ou caminho, "t": segundos, "volume": 0.0-1.0}]
    preservar_voz: a voz sai como foi gravada (sem filtro, sem normalizar, nos canais originais); o limitador
    só entra quando trilha ou efeitos são misturados, para a soma não estourar."""
    info = sondar(fonte)
    fonte, saida_wav = str(Path(fonte).resolve()), str(Path(saida_wav).resolve())  # o FFmpeg roda na pasta dos modelos
    entradas = ["-i", fonte]
    denoise = None
    grafo = []
    if info.tem_audio and preservar_voz:
        # mono vira 2 canais iguais (a conversão automática baixaria 3 dB); estéreo fica como está
        canais = "pan=stereo|c0=c0|c1=c0" if _canais(fonte) == 1 else "aformat=channel_layouts=stereo"
        voz = f"[0:a]aresample=48000,{canais},apad,atrim=0:{duracao:.3f}[voz]"
    elif info.tem_audio:
        voz = "[0:a]aresample=48000,aformat=channel_layouts=mono,highpass=f=75"
        if reduzir_ruido:
            filtro, denoise = filtro_de_ruido()
            voz += f",{filtro},lowpass=f=15000"
        voz += f",loudnorm=I={lufs}:TP=-1.0:LRA=11,aformat=channel_layouts=stereo,apad,atrim=0:{duracao:.3f}[voz]"
    else:
        voz = f"anullsrc=r=48000:cl=stereo,atrim=0:{duracao:.3f}[voz]"
    grafo.append(voz)
    mix = ["[voz]"]
    idx = 1
    usados = []
    if trilha and resolver_som(trilha):
        entradas += ["-stream_loop", "-1", "-i", str(Path(resolver_som(trilha)).resolve())]
        volume_trilha *= TRILHA_FATOR
        reforco_chave = 1.0
        if preservar_voz and info.tem_audio:
            # a voz não foi levada a -14 LUFS: a trilha desce na mesma medida (fica na proporção de sempre) e o
            # "abaixa quando fala" ouve a voz como no caminho normalizado, senão uma gravação baixa nem o aciona.
            # Referência = lufs - 3 dB: no caminho normalizado a voz vira estéreo depois do loudnorm e perde 3 dB.
            fala = medir_volume(fonte).get("lufs")
            if fala == fala and fala > -70:  # NaN ou silêncio: segue como antes
                ganho = min(1.0, 10 ** ((fala - (lufs - 3.0)) / 20))
                volume_trilha *= ganho
                reforco_chave = min(40.0, 1 / ganho)
        grafo.append("[voz]asplit=2[voz][chave]")
        grafo.append(f"[chave]volume={reforco_chave:.4f}[chave_n]")
        grafo.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{duracao:.3f},"
                     f"volume={volume_trilha:.4f},afade=t=in:d=0.6,afade=t=out:st={max(0, duracao - 1.2):.3f}:d=1.2[mus]")
        grafo.append("[mus][chave_n]sidechaincompress=threshold=0.025:ratio=7:attack=25:release=350[musd]")
        mix.append("[musd]")
        usados.append({"trilha": trilha})
        idx += 1
    for e in efeitos or []:
        arq, sync = info_som(e.get("som", ""))
        if not arq or not (0 <= float(e.get("t", -1)) < duracao):
            continue
        entradas += ["-i", str(Path(arq).resolve())]
        ms = int(max(0.0, float(e["t"]) - sync) * 1000)  # o ponto forte do som bate no momento do plano
        vol = float(e.get("volume", 0.35))
        grafo.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},adelay={ms}|{ms}[s{idx}]")
        mix.append(f"[s{idx}]")
        usados.append({"som": e["som"], "t": e["t"]})
        idx += 1
    if len(mix) > 1:
        grafo.append("".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,alimiter=limit=0.89[out]")
    elif preservar_voz:
        grafo.append("[voz]anull[out]")
    else:
        grafo.append("[voz]alimiter=limit=0.89[out]")
    cmd = [ffmpeg_bin(), "-v", "error", "-y", *entradas, "-filter_complex", ";".join(grafo),
           "-map", "[out]", "-t", f"{duracao:.3f}", "-ar", "48000", "-c:a", "pcm_s16le", str(saida_wav)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(MODELO_VOZ.parent))
    if r.returncode != 0:
        raise RuntimeError(f"Falha ao montar o áudio: {r.stderr[-1200:]}")
    return {"arquivo": saida_wav, "itens": usados, "reduzir_ruido": reduzir_ruido, "filtro_de_ruido": denoise}
