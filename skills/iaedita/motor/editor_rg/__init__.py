"""Motor do IAEdita: edição de vídeo por estilos, só com Python + Pillow + numpy + FFmpeg.

Funciona no computador do chat do Claude, no Claude Desktop e no Claude Code.
Recursos opcionais (recorte da pessoa, transcrição local, detecção de rosto) são usados
quando o ambiente tem; sem eles, o motor segue por um caminho mais simples e avisa.
"""
from pathlib import Path

__version__ = "1.4.0"
RAIZ = Path(__file__).resolve().parent
MOTOR = RAIZ.parent
FONTES = MOTOR / "fontes"
SONS = MOTOR / "sons"
