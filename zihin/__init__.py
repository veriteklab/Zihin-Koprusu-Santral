"""
Zihin Köprüsü v7.0 – Ana Paket
"""

__all__ = ["Cekirdek", "goster"]


def __getattr__(ad: str):
    """Ağır ses/GUI bağımlılıklarını sadece gerçekten istendiğinde yükle."""
    if ad == "Cekirdek":
        from .cekirdek import Cekirdek
        return Cekirdek
    if ad == "goster":
        from .arayuz import goster
        return goster
    raise AttributeError(f"module 'zihin' has no attribute {ad!r}")
