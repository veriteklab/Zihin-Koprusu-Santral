"""
Zihin Koprusu Santral paketi.

PC tarafinda cagrı olaylarini alir, depolar, Telegram'a bildirir ve
STT/TTS islemlerini yurutur.
"""

from .ayar import SantralAyar
from .sunucu import SantralSunucu

__all__ = ["SantralAyar", "SantralSunucu"]
