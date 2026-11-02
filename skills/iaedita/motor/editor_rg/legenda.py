"""Legendas palavra a palavra, com a palavra falada em destaque, sempre fora do rosto
e dentro da zona segura do Reels/TikTok (longe do topo, da base e da coluna de botões)."""
from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image

from . import desenho as d

# Zona segura em frações da altura/largura (interface do Instagram/TikTok cobre o resto)
ZONA = {"topo": 0.11, "base": 0.80, "direita": 0.88, "esquerda": 0.06}


@dataclass
class PerfilLegenda:
    fonte: str = "inter"            # inter | serif
    peso: int = 800
    tamanho: float = 0.056          # fração da largura
    cor: str = "#FFFFFF"
    destaque: str = d.NEON          # cor da palavra que está sendo falada
    caixa: str | None = "#0E0E10D9"  # fundo atrás da frase (None = sem caixa, só contorno)
    contorno: int = 0
    maiusculas: bool = False
    max_caracteres: int = 24        # por linha
    max_linhas: int = 2
    posicao: str = "auto"           # auto | baixo | topo | meio | acima-da-cabeca | abaixo-do-rosto
    y_fixo: float | None = None     # fração da altura, se o estilo quiser lugar exato
    animacao: str = "pop"           # pop | subir | nenhuma
    extra: dict = field(default_factory=dict)

    @classmethod
    def de(cls, dados: dict | None) -> "PerfilLegenda":
        p = cls()
        for k, v in (dados or {}).items():
            if hasattr(p, k):
                setattr(p, k, v)
        return p


def _limpar(txt: str) -> str:
    """Legenda profissional: tira vírgula, ponto, dois-pontos e ponto e vírgula do fim (mantém ? e !)."""
    t = txt.rstrip(",.;:…")
    return t or txt


def _fim_real(p: dict) -> float:
    """O transcritor às vezes estica palavra curta por cima da pausa ('e' de 23,8 a 25,1 s).
    Para achar pausas, limita a duração aparente a ~0,12 s por letra (mín. 0,25 s, máx. 0,9 s)."""
    letras = len(p["texto"].strip(".,!?;: "))
    return min(p["fim"], p["inicio"] + max(0.25, min(0.9, 0.12 * letras + 0.1)))


def agrupar(palavras: list[dict], max_car: int, max_linhas: int, pausa: float = 0.45) -> list[dict]:
    """Frases curtas: quebra em pausas da fala, pontuação ou quando passa do limite de caracteres."""
    limite = max_car * max_linhas
    grupos, atual = [], []
    for i, p in enumerate(palavras):
        if atual:
            texto = " ".join(x["texto"] for x in atual + [p])
            gap = p["inicio"] - _fim_real(atual[-1])
            fim_frase = atual[-1]["texto"][-1:] in ".!?"
            if len(texto) > limite or gap > pausa or fim_frase or (atual[-1]["texto"][-1:] == "," and len(texto) > limite * 0.55):
                grupos.append(atual)
                atual = []
        atual.append(p)
    if atual:
        grupos.append(atual)
    out = []
    for i, g in enumerate(grupos):
        ini = g[0]["inicio"]
        fim = _fim_real(g[-1])
        prox = grupos[i + 1][0]["inicio"] if i + 1 < len(grupos) else fim + 0.8
        out.append({"palavras": g, "inicio": ini, "fim": min(prox, fim + 0.6)})
    return out


class Legendas:
    def __init__(self, palavras: list[dict], W: int, H: int, perfil: PerfilLegenda, rosto=None):
        self.W, self.H, self.p, self.rosto = W, H, perfil, rosto
        self.grupos = agrupar(palavras, perfil.max_caracteres, perfil.max_linhas)
        self.f = d.fonte(int(W * perfil.tamanho), perfil.peso, perfil.fonte)
        self._cache = {}

    def _linhas(self, g):
        txts = [_limpar(w["texto"]).upper() if self.p.maiusculas else _limpar(w["texto"]) for w in g["palavras"]]
        larg_max = self.W * 0.80
        linhas, atual = [], []
        for i, t in enumerate(txts):
            teste = " ".join(txts[j] for j in atual + [i])
            if atual and (len(teste) > self.p.max_caracteres or self.f.getlength(teste) > larg_max):
                linhas.append(atual)
                atual = []
            atual.append(i)
        if atual:
            linhas.append(atual)
        return txts, linhas

    def _y(self, t, altura_bloco):
        H, p = self.H, self.p
        if p.y_fixo is not None:
            return p.y_fixo * H - altura_bloco / 2
        topo_seg, base_seg = ZONA["topo"] * H, ZONA["base"] * H
        pos = p.posicao
        if self.rosto is not None:
            x0, y0, x1, y1 = self.rosto.em(t)
            cabeca = self.rosto.topo_cabeca(t)
            queixo = self.rosto.queixo(t)
        else:
            cabeca, queixo = H * 0.18, H * 0.52
        if pos == "auto":
            # 1º: logo abaixo do queixo, se couber antes da base segura; 2º: acima da cabeça; 3º: faixa baixa
            if queixo + H * 0.02 + altura_bloco <= base_seg:
                return max(queixo + H * 0.03, H * 0.62)
            if cabeca - H * 0.02 - altura_bloco >= topo_seg:
                return cabeca - H * 0.025 - altura_bloco
            return base_seg - altura_bloco
        if pos == "acima-da-cabeca":
            return max(topo_seg, cabeca - H * 0.025 - altura_bloco)
        if pos == "abaixo-do-rosto":
            return min(base_seg - altura_bloco, queixo + H * 0.03)
        if pos == "topo":
            return topo_seg + H * 0.04
        if pos == "meio":
            return H * 0.5 - altura_bloco / 2
        return base_seg - altura_bloco  # baixo

    def desenhar(self, img: Image.Image, t: float) -> None:
        g = next((g for g in self.grupos if g["inicio"] - 0.05 <= t < g["fim"]), None)
        if not g:
            return
        txts, linhas = self._linhas(g)
        f, p = self.f, self.p
        al = f.size * 1.18
        pad_x, pad_y = f.size * 0.45, f.size * 0.28
        alt = al * len(linhas) + pad_y * 2
        y = self._y(t, alt)
        # animação de entrada da frase
        k = d.saida(d.mapear(t, g["inicio"] - 0.05, g["inicio"] + 0.16))
        dy = (1 - k) * f.size * 0.5 if p.animacao == "subir" else 0
        esc = 0.92 + 0.08 * d.mola(k, 2.0) if p.animacao == "pop" else 1.0
        camada = Image.new("RGBA", (self.W, int(alt + f.size)), (0, 0, 0, 0))
        larguras = [f.getlength(" ".join(txts[i] for i in ln)) for ln in linhas]
        if p.caixa:
            for li, ln in enumerate(linhas):
                lw = larguras[li]
                caixa = d.painel(lw + pad_x * 2, al + pad_y * (2 if len(linhas) == 1 else 1.1),
                                 raio=int(f.size * 0.32), fundo=p.caixa)
                cx = (self.W - caixa.width) / 2
                cy = li * al + (0 if li == 0 else pad_y * 0.45)
                camada.alpha_composite(caixa, (int(cx), int(cy)))
        draw_y0 = pad_y
        for li, ln in enumerate(linhas):
            x = (self.W - larguras[li]) / 2
            yy = draw_y0 + li * al - f.size * 0.06
            for i in ln:
                w = g["palavras"][i]
                # rampa de ~150 ms: a palavra "acende" quando é dita e volta à cor normal depois
                ini, fim = w["inicio"] - 0.03, max(w["fim"], w["inicio"] + 0.12)
                acende = d.saida(d.mapear(t, ini, ini + 0.15)) * (1 - d.suave(d.mapear(t, fim, fim + 0.12)))
                cb, cd = d.cor(p.cor), d.cor(p.destaque)
                cor_p = tuple(int(cb[k] + (cd[k] - cb[k]) * acende) for k in range(3))
                alfa = 1.0 if p.animacao == "nenhuma" else 0.55 + 0.45 * d.saida(d.mapear(t, ini, ini + 0.15))
                d.escrever(camada, (x, yy), [txts[i]], f, d.cor(cor_p, alfa),
                           contorno=p.contorno, sombra=0.0 if p.caixa else 0.55)
                x += f.getlength(txts[i] + " ")
        if esc != 1.0:
            nw, nh = int(camada.width * esc), int(camada.height * esc)
            camada = camada.resize((nw, nh), Image.BICUBIC)
            img.alpha_composite(camada, (int((self.W - nw) / 2), int(y + dy + (alt - alt * esc) / 2)))
        else:
            img.alpha_composite(camada, (0, int(y + dy)))

    def ocupacao(self, t: float):
        """Faixa vertical (y0, y1) ocupada pela legenda em t — para estilos não colocarem nada em cima."""
        g = next((g for g in self.grupos if g["inicio"] - 0.05 <= t < g["fim"]), None)
        if not g:
            return None
        _, linhas = self._linhas(g)
        alt = self.f.size * 1.18 * len(linhas) + self.f.size * 0.56
        y = self._y(t, alt)
        return (y, y + alt)
