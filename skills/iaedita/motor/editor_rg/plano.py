"""O PLANO DE EDIÇÃO: o que acontece em cada segundo do vídeo, escrito pelo agente seguindo a skill do estilo.

{
  "estilo": "05-zoom-digital",
  "opcoes": {"trilha": false, "suavizar_pele": false},
  "correcoes": {"Instagran": "Instagram"},
  "legenda": {"ativa": true, "perfil": {}},
  "eventos": [{"tipo": "...", "inicio": 3.2, "fim": 5.0, "texto": "...", "som": "whoosh"}],
  "efeitos_sonoros": [{"som": "pop", "t": 7.1, "volume": 0.3}],
  "trilha": {"arquivo": "caminho.mp3", "volume": 0.14}
}
Tempos SEMPRE em segundos do vídeo original. Nada de repetir ciclos fixos: cada evento nasce de algo dito."""
from __future__ import annotations

import json
from pathlib import Path

from . import desenho as d


class Evento(dict):
    """Um acontecimento do plano. Acesso por atributo e ajudantes de animação."""

    __getattr__ = dict.get

    def p(self, t: float) -> float:
        """Progresso 0→1 entre inicio e fim."""
        return d.mapear(t, self["inicio"], self["fim"])

    def env(self, t: float, entra: float = 0.35, sai: float = 0.3) -> float:
        """Envelope de presença: sobe na entrada, 1 no meio, desce na saída."""
        return d.envelope(t, self["inicio"], self["fim"], entra, sai)

    def desde(self, t: float) -> float:
        return t - self["inicio"]

    def ate(self, t: float) -> float:
        return self["fim"] - t


def carregar(caminho_ou_dict) -> dict:
    if isinstance(caminho_ou_dict, dict):
        plano = caminho_ou_dict
    else:
        plano = json.loads(Path(caminho_ou_dict).read_text(encoding="utf-8"))
    plano.setdefault("opcoes", {})
    plano.setdefault("legenda", {"ativa": True})
    plano.setdefault("eventos", [])
    plano["eventos"] = sorted((Evento(e) for e in plano["eventos"]), key=lambda e: e["inicio"])
    return plano


def validar(plano: dict, duracao: float, modulo=None) -> list[str]:
    """Problemas que impedem uma boa edição. Lista vazia = ok."""
    erros = []
    if not plano.get("estilo"):
        erros.append("Falta 'estilo' no plano.")
    for i, e in enumerate(plano["eventos"]):
        if "inicio" not in e or "fim" not in e:
            erros.append(f"Evento {i} sem inicio/fim.")
            continue
        if e["fim"] <= e["inicio"]:
            erros.append(f"Evento {i} ({e.get('tipo')}) termina antes de começar.")
        if e["inicio"] < 0 or e["fim"] > duracao + 0.05:
            erros.append(f"Evento {i} ({e.get('tipo')}) fora da duração do vídeo ({duracao:.2f}s).")
    if modulo is not None:
        tipos = (getattr(modulo, "INFO", {}) or {}).get("eventos", {})
        if tipos:
            for i, e in enumerate(plano["eventos"]):
                if e.get("tipo") not in tipos:
                    erros.append(f"Evento {i}: tipo '{e.get('tipo')}' não existe neste estilo. Tipos: {', '.join(tipos)}.")
        if hasattr(modulo, "validar"):
            erros += list(modulo.validar(plano, duracao) or [])
    import json as _json
    if "�" in _json.dumps(plano["eventos"], ensure_ascii=False):
        erros.append("Há texto com acento quebrado (�) no plano: salve o plano.json em UTF-8 e reescreva as palavras acentuadas.")
    if duracao > 8 and plano["eventos"]:
        fim_ultimo = max(e["fim"] for e in plano["eventos"])
        ini_primeiro = min(e["inicio"] for e in plano["eventos"])
        if fim_ultimo < duracao * 0.5:
            erros.append("Os eventos acabam antes da metade do vídeo: distribua ao longo de TODA a fala.")
        if ini_primeiro > min(4.0, duracao * 0.3):
            erros.append("O primeiro evento demora a aparecer: os 3 primeiros segundos seguram o público.")
    return erros


def ativos(plano: dict, t: float, antes: float = 0.0, depois: float = 0.0) -> list[Evento]:
    return [e for e in plano["eventos"] if e["inicio"] - antes <= t <= e["fim"] + depois]
