"""Atalho do IAEdita: funciona de qualquer pasta, em qualquer sistema.
    python3 /caminho/do/motor/erg.py <comando> ...   (mesmos comandos de python -m editor_rg)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from editor_rg.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
