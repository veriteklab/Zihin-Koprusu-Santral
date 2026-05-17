"""
Zihin Köprüsü – Ana Arayüz
Merkez uzuv yönetimi, ses, Telegram ve karakter yapılandırması.
"""
from __future__ import annotations

import json
import os
import math
import shlex
import sys
import threading
import uuid

try:
    import sounddevice as sd
except Exception:
    sd = None
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QRectF
from PyQt6.QtGui import (QFont, QColor, QPalette, QTextCursor,
                          QPainter, QPen, QRadialGradient)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QTextEdit, QLineEdit,
    QTabWidget, QFrame, QScrollArea, QSplitter,
    QComboBox, QGroupBox, QMessageBox, QFileDialog, QSlider,
    QCheckBox, QSpinBox, QDialog, QFormLayout,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QListWidget,
    QListWidgetItem, QDialogButtonBox,
    QProgressBar, QDoubleSpinBox
)

# ── Renkler ──────────────────────────────────────────────────────────────────
R = {
    "arkaplan": "#0d0f14", "panel": "#13161e", "panel2": "#1a1e2a",
    "kenar": "#252b3b", "vurgu": "#00e5ff", "vurgu2": "#7c4dff",
    "yesil": "#00e676", "sari": "#ffd740", "kirmizi": "#ff5252",
    "turuncu": "#ff6d00", "metin": "#e8eaf0", "metin2": "#7a8099",
    "metin3": "#4a5068",
}

STIL = f"""
QMainWindow,QWidget{{background:{R['arkaplan']};color:{R['metin']};
    font-family:'Courier New',monospace;}}
QTabWidget::pane{{border:1px solid {R['kenar']};background:{R['panel']};border-radius:6px;}}
QTabBar::tab{{background:{R['panel2']};color:{R['metin2']};padding:6px 12px;
    border:1px solid {R['kenar']};border-bottom:none;border-top-left-radius:5px;
    border-top-right-radius:5px;font-size:10px;letter-spacing:1px;}}
QTabBar::tab:selected{{background:{R['panel']};color:{R['vurgu']};
    border-bottom:2px solid {R['vurgu']};}}
QTabBar::tab:hover:!selected{{color:{R['metin']};background:{R['kenar']};}}
QPushButton{{background:{R['panel2']};color:{R['metin']};border:1px solid {R['kenar']};
    border-radius:5px;padding:7px 14px;font-family:'Courier New';font-size:11px;}}
QPushButton:hover{{background:{R['kenar']};border-color:{R['vurgu']};color:{R['vurgu']};}}
QPushButton:pressed{{background:{R['vurgu']};color:{R['arkaplan']};}}
QPushButton:disabled{{color:{R['metin3']};}}
QPushButton#aksiyon{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 {R['vurgu2']},stop:1 {R['vurgu']});color:{R['arkaplan']};
    font-weight:bold;border:none;padding:10px 20px;}}
QPushButton#tehlike{{background:{R['panel2']};border:1px solid {R['kirmizi']};
    color:{R['kirmizi']};}}
QPushButton#tehlike:hover{{background:{R['kirmizi']};color:white;}}
QPushButton#basarili{{background:{R['panel2']};border:1px solid {R['yesil']};
    color:{R['yesil']};}}
QPushButton#whatsapp{{background:#25D366;color:white;border:none;border-radius:6px;
    font-weight:bold;padding:10px 20px;}}
QPushButton#whatsapp:hover{{background:#128C7E;}}
QTextEdit,QPlainTextEdit{{background:{R['panel']};color:{R['metin']};
    border:1px solid {R['kenar']};border-radius:5px;padding:6px;
    font-family:'Courier New';font-size:12px;}}
QLineEdit{{background:{R['panel2']};color:{R['metin']};border:1px solid {R['kenar']};
    border-radius:5px;padding:7px 10px;font-family:'Courier New';font-size:12px;}}
QLineEdit:focus{{border-color:{R['vurgu']};}}
QComboBox{{background:{R['panel2']};color:{R['metin']};border:1px solid {R['kenar']};
    border-radius:5px;padding:5px 10px;}}
QComboBox QAbstractItemView{{background:{R['panel2']};color:{R['metin']};
    selection-background-color:{R['vurgu2']};}}
QScrollBar:vertical{{background:{R['panel']};width:7px;border-radius:3px;}}
QScrollBar::handle:vertical{{background:{R['kenar']};border-radius:3px;min-height:24px;}}
QScrollBar::handle:vertical:hover{{background:{R['vurgu']};}}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
QGroupBox{{border:1px solid {R['kenar']};border-radius:7px;margin-top:10px;padding:10px;
    font-size:11px;color:{R['metin2']};letter-spacing:1px;}}
QGroupBox::title{{subcontrol-origin:margin;subcontrol-position:top left;
    padding:0 6px;color:{R['vurgu']};font-size:11px;letter-spacing:2px;}}
QTreeWidget{{background:{R['panel']};color:{R['metin']};border:1px solid {R['kenar']};
    alternate-background-color:{R['panel2']};}}
QTreeWidget::item:selected{{background:{R['vurgu2']};}}
QTreeWidget::item:hover{{background:{R['kenar']};}}
QHeaderView::section{{background:{R['panel2']};color:{R['metin2']};
    border:1px solid {R['kenar']};padding:5px;}}
QCheckBox{{color:{R['metin']};spacing:6px;}}
QCheckBox::indicator{{width:14px;height:14px;border:1px solid {R['kenar']};
    border-radius:3px;background:{R['panel2']};}}
QCheckBox::indicator:checked{{background:{R['vurgu']};border-color:{R['vurgu']};}}
QSlider::groove:horizontal{{height:4px;background:{R['kenar']};border-radius:2px;}}
QSlider::handle:horizontal{{background:{R['vurgu']};width:13px;height:13px;
    border-radius:6px;margin:-4px 0;}}
QSlider::sub-page:horizontal{{background:{R['vurgu']};border-radius:2px;}}
QStatusBar{{background:{R['panel']};color:{R['metin2']};
    border-top:1px solid {R['kenar']};font-size:11px;}}
QDialog{{background:{R['arkaplan']};color:{R['metin']};}}
QListWidget{{background:{R['panel']};color:{R['metin']};border:1px solid {R['kenar']};}}
QListWidget::item:selected{{background:{R['vurgu2']};}}
QDoubleSpinBox,QSpinBox{{background:{R['panel2']};color:{R['metin']};
    border:1px solid {R['kenar']};border-radius:5px;padding:4px;}}
"""

VARSAYILAN_HITAP = {b: "Operatör" for b in
                    ["ABİ", "BİRADER", "BACİ", "ABLA", "UFAKLIK", "DAYI", "KUZEN", "KEYLO"]}

try:
    from .ses_motoru import SES_EFEKTLERI
except Exception:
    SES_EFEKTLERI = {"normal": {"pitch": 1.0, "tempo": 1.0, "label": "Normal"}}

TUM_BILINCLER = ["ABİ", "BİRADER", "BACİ", "ABLA", "UFAKLIK", "DAYI", "KUZEN", "KEYLO"]


# ── Sinyal Köprüsü ────────────────────────────────────────────────────────────
class SinyalKoprusu(QObject):
    log_geldi     = pyqtSignal(str, str, str)
    durum_degisti = pyqtSignal(str)
    olay_geldi    = pyqtSignal(str, str)
    slot_durum    = pyqtSignal(str, str)
    uzuv_durum    = pyqtSignal(str, str)
    tor_mesaj     = pyqtSignal(str)
    plugin_mesaj  = pyqtSignal(str)
    amplitud      = pyqtSignal(float)   # Ses dalgası için 0.0-1.0
    wake_word     = pyqtSignal(str)     # Wake word tetiklendi
    yedek_sonuc   = pyqtSignal(str, bool, str)


# ── Jarvis Çekirdek Ekranı ───────────────────────────────────────────────────
class ASCIIKarakter(QWidget):
    def __init__(self):
        super().__init__()
        self._mod = "bekleme"
        self._aci = 0.0
        self._tarama = 0.0
        self._faz = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)
        self.setMinimumSize(118, 118)
        self._renk = QColor(R["vurgu"])
        self._ikincil = QColor(R["vurgu2"])
        self._renk_guncelle()

    def mod_degistir(self, mod: str):
        self._mod = mod
        self._renk_guncelle()
        self.update()

    def _renk_guncelle(self):
        renkler = {
            "bekleme": (R["metin2"], R["vurgu"]),
            "dinleniyor": (R["yesil"], R["vurgu"]),
            "konusuyor": (R["vurgu"], R["vurgu2"]),
            "dusunuyor": (R["sari"], R["vurgu2"]),
            "hata": (R["kirmizi"], R["turuncu"]),
        }
        ana, ikincil = renkler.get(self._mod, (R["metin2"], R["vurgu"]))
        self._renk = QColor(ana)
        self._ikincil = QColor(ikincil)

    def _tick(self):
        hiz = {"bekleme": 0.6, "dinleniyor": 1.2, "konusuyor": 2.4, "dusunuyor": 0.9, "hata": 3.2}
        carp = hiz.get(self._mod, 1.0)
        self._aci = (self._aci + carp) % 360
        self._tarama = (self._tarama + 2.5 * carp) % 1000
        self._faz += 0.14 * carp
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r1 = min(w, h) * 0.42
        r2 = r1 * 0.72
        r3 = r1 * 0.46

        ana = QColor(self._renk)
        ik = QColor(self._ikincil)
        zayif = QColor(ana)
        zayif.setAlpha(65)
        orta = QColor(ana)
        orta.setAlpha(140)

        # Derinlik veren yumuşak çekirdek ışığı
        glow = QRadialGradient(cx, cy, r1 * 1.1)
        glow_ana = QColor(ik)
        glow_ana.setAlpha(55 if self._mod != "bekleme" else 28)
        glow.setColorAt(0.0, glow_ana)
        glow.setColorAt(0.55, QColor(0, 0, 0, 0))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(cx - r1 * 1.1, cy - r1 * 1.1, r1 * 2.2, r1 * 2.2))

        # Dış halka
        painter.setPen(QPen(zayif, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(cx - r1, cy - r1, r1 * 2, r1 * 2))

        # Dönen segmentler
        segment = QRectF(cx - r1, cy - r1, r1 * 2, r1 * 2)
        painter.setPen(QPen(ana, 3))
        painter.drawArc(segment, int(-self._aci * 16), int(-72 * 16))
        painter.setPen(QPen(ik, 2))
        painter.drawArc(segment.adjusted(8, 8, -8, -8), int((self._aci + 120) * 16), int(48 * 16))

        # İnce radar ışınları ve düğüm noktaları
        for i in range(12):
            aci = math.radians(self._aci * 0.35 + i * 30)
            ic = r3 * 0.95
            dis = r1 * (0.88 if i % 3 else 0.98)
            renk = QColor(ana if i % 2 == 0 else ik)
            renk.setAlpha(52 if i % 3 else 95)
            painter.setPen(QPen(renk, 1))
            painter.drawLine(
                int(cx + math.cos(aci) * ic),
                int(cy + math.sin(aci) * ic),
                int(cx + math.cos(aci) * dis),
                int(cy + math.sin(aci) * dis),
            )
            if i % 3 == 0:
                painter.setPen(Qt.PenStyle.NoPen)
                nokta = QColor(renk)
                nokta.setAlpha(150)
                painter.setBrush(nokta)
                px = cx + math.cos(aci) * dis
                py = cy + math.sin(aci) * dis
                painter.drawEllipse(QRectF(px - 2.5, py - 2.5, 5, 5))

        # Tarama halkası
        tarama_y = cy - r2 + ((self._tarama / 1000.0) * (r2 * 2))
        scan = QColor(ik)
        scan.setAlpha(90)
        painter.setPen(QPen(scan, 1))
        painter.drawLine(int(cx - r2), int(tarama_y), int(cx + r2), int(tarama_y))

        # İç çekirdek
        painter.setPen(QPen(orta, 1))
        painter.drawEllipse(QRectF(cx - r2, cy - r2, r2 * 2, r2 * 2))
        painter.setPen(QPen(zayif, 1))
        painter.drawEllipse(QRectF(cx - r3 * 1.35, cy - r3 * 1.35, r3 * 2.7, r3 * 2.7))
        cekirdek = QColor(ik)
        cekirdek.setAlpha(78)
        painter.setBrush(cekirdek)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(cx - r3, cy - r3, r3 * 2, r3 * 2))

        # Çapraz nişangah
        painter.setPen(QPen(ana, 1))
        painter.drawLine(int(cx - r2 * 0.9), int(cy), int(cx + r2 * 0.9), int(cy))
        painter.drawLine(int(cx), int(cy - r2 * 0.9), int(cx), int(cy + r2 * 0.9))

        # Alt enerji barları
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(5):
            oran = max(0.15, (math.sin(self._faz + i * 0.7) + 1.0) / 2.0)
            if self._mod == "bekleme":
                oran *= 0.45
            elif self._mod == "dusunuyor":
                oran *= 0.75
            elif self._mod == "hata":
                oran *= 1.1
            bw = 9
            bh = 10 + oran * 22
            bx = cx - 28 + i * 14
            by = cy + r1 - 24 - bh
            renk = QColor(ik if i % 2 else ana)
            renk.setAlpha(180)
            painter.setBrush(renk)
            painter.drawRoundedRect(QRectF(bx, by, bw, bh), 2, 2)

        # Merkez metin
        painter.setPen(QPen(QColor(R["metin"]), 1))
        yazi = {
            "bekleme": "HAZIR",
            "dinleniyor": "DİNLE",
            "konusuyor": "SES",
            "dusunuyor": "ANALİZ",
            "hata": "UYARI",
        }.get(self._mod, "ÖZ")
        fnt = QFont("Courier New", 10, QFont.Weight.Bold)
        fnt.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        painter.setFont(fnt)
        painter.drawText(QRectF(cx - 48, cy - 10, 96, 22), Qt.AlignmentFlag.AlignCenter, yazi)





# ── Hologram Pulse Çerçevesi ──────────────────────────────────────────────────
class HologramCerceve(QWidget):
    """
    Sol panelin etrafında dönen mavi hologram pulse efekti.
    Konuşurken hızlanır, dinliyorken yavaş döner, boştayken soluk.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._aci    = 0.0
        self._hiz    = 1.0       # Derece/frame
        self._alfa   = 40        # Şeffaflık 0-255
        self._renk   = QColor(R["vurgu"])
        self._mod    = "bosta"
        self._timer  = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)    # ~33 FPS

    def mod_ayarla(self, mod: str):
        self._mod = mod
        if mod == "dinleniyor":
            self._hiz = 2.5; self._alfa = 120
            self._renk = QColor(R["yesil"])
        elif mod == "konusuyor":
            self._hiz = 4.0; self._alfa = 200
            self._renk = QColor(R["vurgu2"])
        elif mod == "dusunuyor":
            self._hiz = 1.5; self._alfa = 80
            self._renk = QColor(R["sari"])
        else:
            self._hiz = 0.8; self._alfa = 30
            self._renk = QColor(R["vurgu"])

    def _tick(self):
        self._aci = (self._aci + self._hiz) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r_dis = min(w, h) / 2 - 4
        r_ic  = r_dis - 6

        # İnce dış kalkan
        renk = QColor(self._renk)
        renk.setAlpha(self._alfa)
        pen = QPen(renk, 2)
        painter.setPen(pen)
        painter.drawEllipse(
            QRectF(cx - r_dis, cy - r_dis, r_dis * 2, r_dis * 2))

        # Kademeli kalkan halkaları
        for i, oran in enumerate((0.86, 0.72, 0.58)):
            halka = QColor(self._renk)
            halka.setAlpha(max(18, self._alfa // (i + 2)))
            painter.setPen(QPen(halka, 1))
            rr = r_dis * oran
            painter.drawEllipse(QRectF(cx - rr, cy - rr, rr * 2, rr * 2))

        # Dönen kırık segmentler
        for i in range(6):
            seg = QColor(self._renk)
            seg.setAlpha(min(230, self._alfa + 55))
            painter.setPen(QPen(seg, 2 if i % 2 == 0 else 1))
            bas = int((self._aci * (1 if i % 2 == 0 else -0.65) + i * 60) * 16)
            uzunluk = int((20 + (i % 3) * 10) * 16)
            rr = r_dis - 12 - (i % 3) * 9
            painter.drawArc(QRectF(cx - rr, cy - rr, rr * 2, rr * 2), bas, uzunluk)

        # Dönen parlak nokta
        aci_rad = math.radians(self._aci)
        px = cx + r_dis * math.cos(aci_rad)
        py = cy + r_dis * math.sin(aci_rad)
        parlak = QColor(self._renk)
        parlak.setAlpha(220)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(parlak)
        painter.drawEllipse(QRectF(px - 4, py - 4, 8, 8))

        # İç çember — ters yönde
        ic_renk = QColor(self._renk)
        ic_renk.setAlpha(self._alfa // 2)
        painter.setPen(QPen(ic_renk, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(
            QRectF(cx - r_ic, cy - r_ic, r_ic * 2, r_ic * 2))

        aci_rad2 = math.radians(-self._aci * 1.5)
        px2 = cx + r_ic * math.cos(aci_rad2)
        py2 = cy + r_ic * math.sin(aci_rad2)
        ic_parlak = QColor(self._renk)
        ic_parlak.setAlpha(160)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ic_parlak)
        painter.drawEllipse(QRectF(px2 - 3, py2 - 3, 6, 6))

# ── Ses Dalgası Animasyonu ────────────────────────────────────────────────────
class SesDalgasiWidget(QWidget):
    """
    Mikrofon amplitüdüne göre canlı ses dalgası çizer.
    Hologram efekti: parlayan mavi çizgiler, simetrik dalga.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)
        self.setMaximumHeight(60)
        self._amplitudler = [0.0] * 64   # Dalga tamponu
        self._hedef_amp   = 0.0
        self._mevcut_amp  = 0.0
        self._aktif       = False
        self._wake_aktif  = False
        self._renk        = R["vurgu"]   # Normal: cyan
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._guncelle)
        self._timer.start(40)  # 25 FPS

    def amplitud_guncelle(self, deger: float):
        self._hedef_amp = min(1.0, deger)
        self._aktif = deger > 0.02

    def wake_word_tetiklendi(self):
        """Wake word algılandığında kısa flash efekti."""
        self._renk = R["yesil"]
        QTimer.singleShot(500, lambda: setattr(self, '_renk', R["vurgu"]))

    def konusuyor_ayarla(self, konusuyor: bool):
        self._renk = R["vurgu2"] if konusuyor else R["vurgu"]

    def _guncelle(self):
        # Yumuşak geçiş
        self._mevcut_amp += (self._hedef_amp - self._mevcut_amp) * 0.3
        self._hedef_amp  *= 0.85  # Zaman içinde azal
        # Tampona ekle
        self._amplitudler.pop(0)
        self._amplitudler.append(self._mevcut_amp)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cy = h / 2
        n = len(self._amplitudler)

        # Arka plan
        painter.fillRect(self.rect(), QColor(R["arkaplan"]))

        if not any(a > 0.01 for a in self._amplitudler):
            # Sessiz — ince düz çizgi
            pen = QPen(QColor(R["kenar"]), 1)
            painter.setPen(pen)
            painter.drawLine(0, int(cy), w, int(cy))
            return

        # Dalga çiz — simetrik (üst ve alt)
        renk = QColor(self._renk)
        adim = w / n

        for i in range(n - 1):
            amp1 = self._amplitudler[i]
            amp2 = self._amplitudler[i + 1]
            y1_ust = cy - amp1 * (cy - 4)
            y2_ust = cy - amp2 * (cy - 4)
            y1_alt = cy + amp1 * (cy - 4)
            y2_alt = cy + amp2 * (cy - 4)

            x1 = i * adim
            x2 = (i + 1) * adim

            # Parlaklık: amplitüde göre alfa
            alfa = int(80 + amp1 * 175)
            renk.setAlpha(alfa)

            # Kalınlık: yüksek amplitüdde daha kalın
            kalinlik = max(1.0, amp1 * 3.0)
            pen = QPen(renk, kalinlik)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)

            painter.drawLine(
                int(x1), int(y1_ust), int(x2), int(y2_ust))
            painter.drawLine(
                int(x1), int(y1_alt), int(x2), int(y2_alt))

        # Orta çizgi — ince parlak
        renk.setAlpha(60)
        painter.setPen(QPen(renk, 1))
        painter.drawLine(0, int(cy), w, int(cy))

# ── Log Paneli ────────────────────────────────────────────────────────────────
class LogPaneli(QTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setFont(QFont("Courier New", 11))

    def log_ekle(self, seviye, kaynak, mesaj):
        from datetime import datetime
        renkler = {"BİLGİ": R["metin"], "HATA": R["kirmizi"],
                   "KRİTİK": R["turuncu"], "UYARI": R["sari"]}
        rc = renkler.get(seviye, R["metin2"])
        zaman = datetime.now().strftime("%H:%M:%S")
        html = (f'<span style="color:{R["metin3"]}">[{zaman}]</span> '
                f'<span style="color:{rc}">[{seviye}]</span> '
                f'<span style="color:{R["vurgu2"]}">[{kaynak}]</span> '
                f'<span style="color:{rc}">{mesaj}</span><br>')
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.insertHtml(html)
        self.moveCursor(QTextCursor.MoveOperation.End)


# ── Uzuv Diyalog ─────────────────────────────────────────────────────────────
class UzuvDiyalog(QDialog):
    def __init__(self, uzuv=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Uzuv Sihirbazı")
        self.setMinimumWidth(540)
        self.resize(620, 760)
        self.uzuv = uzuv
        self._kur()
        if uzuv:
            self._doldur(uzuv)

    def _kur(self):
        duz = QVBoxLayout(self)
        kaydir = QScrollArea()
        kaydir.setWidgetResizable(True)
        kaydir.setFrameShape(QFrame.Shape.NoFrame)
        govde = QWidget()
        govde_lay = QVBoxLayout(govde)

        ozet_lbl = QLabel(
            "1. Cihazı seçin  2. Bilinçleri atayın  3. Bağlantı yöntemini seçin\n"
            "Geri kalan teknik ayrıntılar setup paketine otomatik gömülür."
        )
        ozet_lbl.setWordWrap(True)
        ozet_lbl.setStyleSheet(f"color:{R['vurgu']};font-size:11px;")
        govde_lay.addWidget(ozet_lbl)

        form = QFormLayout()
        self.ad_e        = QLineEdit()
        self.takma_e     = QLineEdit()
        self.takma_e.setPlaceholderText("Kısa sesli komut ismi (ev, iş, telefon...)")
        self.id_e        = QLineEdit()
        self.tip_e       = QComboBox()
        self.tip_e.addItem("🐧 Bilgisayar / Linux", "linux")
        self.tip_e.addItem("🪟 Bilgisayar / Windows", "windows")
        self.tip_e.addItem("🤖 Telefon / Android", "android")
        self.tip_e.addItem("🍎 Bilgisayar / Mac", "mac")
        self.simge_e     = QLineEdit(); self.simge_e.setPlaceholderText("🖥️")
        self.notlar_e    = QLineEdit()
        self.sessiz_cb   = QCheckBox("Sessiz mod (ses çıkmasın)")
        self.tor_host_e  = QLineEdit(); self.tor_host_e.setText("127.0.0.1")
        self.tor_port_e  = QSpinBox()
        self.tor_port_e.setRange(1, 65535); self.tor_port_e.setValue(9050)

        self.birincil = self._baglanti_formu_olustur("Birincil", varsayilan_port=22)
        self.yedek = self._baglanti_formu_olustur("Yedek", varsayilan_port=9050)
        self.yedek["yedek_cb"].setChecked(True)
        self.yedek["yedek_cb"].setEnabled(False)
        self.yedek["aktif_cb"].setChecked(True)
        self.yedek["yontem"].setCurrentIndex(self.yedek["yontem"].findData("telegram"))

        self.bilinc_lst  = QListWidget()
        self.bilinc_lst.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection)
        for b in TUM_BILINCLER:
            self.bilinc_lst.addItem(b)
        self.bilinc_lst.setMaximumHeight(100)

        self.setup_grp = QGroupBox("SETUP PAKETİ")
        sf = QFormLayout(self.setup_grp)
        self.setup_otomatik_cb = QCheckBox("Uzuv kaydedilince setup paketini hemen üret")
        self.setup_otomatik_cb.setChecked(True)
        self.setup_paket_cb = QComboBox()
        self.setup_derle_cb = QCheckBox("Gerçek APK/EXE derle")
        self.setup_derle_cb.setChecked(True)
        self.setup_klasor_e = QLineEdit()
        self.setup_klasor_e.setText(os.path.expanduser("~/ZihinKoprusu_Setuplari"))
        self.setup_klasor_e.setPlaceholderText("Otomatik: ~/ZihinKoprusu_Setuplari")
        self.setup_klasor_btn = QPushButton("📁 Seç")
        self.setup_bilgi_lbl = QLabel("")
        self.setup_bilgi_lbl.setWordWrap(True)
        self.setup_bilgi_lbl.setStyleSheet(f"color:{R['metin3']};font-size:10px;")
        setup_kl_row = QHBoxLayout()
        setup_kl_row.addWidget(self.setup_klasor_e)
        setup_kl_row.addWidget(self.setup_klasor_btn)
        setup_kl_w = QWidget()
        setup_kl_w.setLayout(setup_kl_row)
        sf.addRow("", self.setup_otomatik_cb)
        sf.addRow("Paket Türü:", self.setup_paket_cb)
        sf.addRow("", self.setup_derle_cb)
        sf.addRow("Kayıt Klasörü:", setup_kl_w)
        sf.addRow("", self.setup_bilgi_lbl)

        self.kimlik_grp = QGroupBox("GELİŞMİŞ KİMLİK AYARLARI")
        kimlik_form = QFormLayout(self.kimlik_grp)
        kimlik_form.addRow("ID:", self.id_e)
        kimlik_form.addRow("Simge:", self.simge_e)
        kimlik_form.addRow("Notlar:", self.notlar_e)

        form.addRow("Uzuv Adı:", self.ad_e)
        form.addRow("Kısa Çağrı Adı:", self.takma_e)
        form.addRow("Cihaz Tipi:", self.tip_e)
        form.addRow("", self.sessiz_cb)

        kurulum_lbl = QLabel(
            "ℹ Normal kullanımda IP, port, onion veya anahtar girmeniz gerekmez.\n"
            "Merkez sadece bağlantı yöntemini seçer, setup paketi uzuvda çalışınca "
            "sunucuya kendini tanıtır ve komut beklemeye başlar."
        )
        kurulum_lbl.setWordWrap(True)
        kurulum_lbl.setStyleSheet(f"color:{R['metin3']};font-size:10px;")
        self.ileri_ag_cb = QCheckBox("İleri ağ ayarlarını göster")
        self.ileri_ag_cb.toggled.connect(self._ileri_ag_gorunurluk_guncelle)
        self.ileri_kimlik_cb = QCheckBox("Gelişmiş kimlik ayarlarını göster")
        self.ileri_kimlik_cb.toggled.connect(self.kimlik_grp.setVisible)

        self.tor_grp = QGroupBox("TOR PROXY")
        tf = QFormLayout(self.tor_grp)
        tf.addRow("Host:", self.tor_host_e)
        tf.addRow("Port:", self.tor_port_e)

        birincil_grp = self.birincil["grup"]
        yedek_grp = self.yedek["grup"]

        bilinc_grp = QGroupBox("ATANMIŞ BİLİNÇLER")
        bf = QVBoxLayout(bilinc_grp)
        bf.addWidget(self.bilinc_lst)

        govde_lay.addLayout(form)
        govde_lay.addWidget(kurulum_lbl)
        govde_lay.addWidget(self.ileri_kimlik_cb)
        govde_lay.addWidget(self.kimlik_grp)
        govde_lay.addWidget(self.ileri_ag_cb)
        govde_lay.addWidget(birincil_grp)
        govde_lay.addWidget(yedek_grp)
        govde_lay.addWidget(self.tor_grp)
        govde_lay.addWidget(bilinc_grp)
        govde_lay.addWidget(self.setup_grp)
        govde_lay.addStretch()

        kaydir.setWidget(govde)
        duz.addWidget(kaydir, 1)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._kabul_et)
        bb.rejected.connect(self.reject)
        duz.addWidget(bb)

        self.ad_e.textChanged.connect(
            lambda t: self.id_e.setText(
                t.lower().replace(" ", "_")[:20])
            if not self.uzuv else None)
        self.takma_e.textChanged.connect(
            lambda t: self.id_e.setText(
                (t or self.ad_e.text()).lower().replace(" ", "_")[:20])
            if not self.uzuv else None)
        self.tip_e.currentIndexChanged.connect(self._setup_tip_guncelle)
        self.setup_klasor_btn.clicked.connect(self._setup_klasor_sec)
        self.setup_otomatik_cb.toggled.connect(self._setup_aktif_guncelle)
        self.kimlik_grp.setVisible(False)
        self._setup_tip_guncelle()
        self._setup_aktif_guncelle(self.setup_otomatik_cb.isChecked())
        self._ileri_ag_gorunurluk_guncelle(False)

    def _kabul_et(self):
        if not self.ad_e.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Uzuv adı boş olamaz.")
            return
        if not any(self.bilinc_lst.item(i).isSelected() for i in range(self.bilinc_lst.count())):
            QMessageBox.warning(self, "Eksik Bilgi", "En az bir bilinç seçmelisiniz.")
            return
        if not self.birincil["aktif_cb"].isChecked():
            QMessageBox.warning(self, "Bağlantı", "Birincil bağlantı aktif olmalı.")
            return
        if not self.yedek["aktif_cb"].isChecked():
            QMessageBox.warning(self, "Bağlantı", "En az bir yedek bağlantı aktif olmalı.")
            return
        if self.setup_otomatik_cb.isChecked() and not self.setup_klasor_e.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Setup üretimi için kayıt klasörü seçmelisiniz.")
            return
        self.accept()

    def _setup_klasor_sec(self):
        klasor = QFileDialog.getExistingDirectory(self, "Setup Kayıt Klasörü Seç")
        if klasor:
            self.setup_klasor_e.setText(klasor)

    def _setup_tip_guncelle(self, *_):
        tip = self.tip_e.currentData()
        self.setup_paket_cb.clear()
        if tip == "windows":
            self.setup_paket_cb.addItem("🪟 Windows EXE", ("windows", "⚙ C++ (kaynak + cmake)"))
            self.setup_paket_cb.addItem("🐍 Windows Python + .bat", ("windows", "🐍 Python + .bat"))
            self.setup_paket_cb.addItem("📜 Windows .bat", ("windows", "📜 Yalnızca .bat (PowerShell)"))
        elif tip == "android":
            self.setup_paket_cb.addItem("📱 Android APK", ("android", "📱 APK — Buildozer (uzun sürer)"))
            self.setup_paket_cb.addItem("📦 Android Termux", ("android", "📦 Termux (sh + py)"))
        else:
            self.setup_paket_cb.addItem("🐍 Python Setup", ("linux", ""))
        self.setup_bilgi_lbl.setText(
            "Bu adım tamamlanınca seçilen gerçek setup paketi üretilir.\n"
            "APK/EXE derleme internet ve işlemci kullanır; başarısız olursa kaynak proje yedek olarak kalır."
        )

    def _setup_aktif_guncelle(self, aktif: bool):
        for widget in (self.setup_paket_cb, self.setup_derle_cb, self.setup_klasor_e, self.setup_klasor_btn):
            widget.setEnabled(aktif)

    def _baglanti_formu_olustur(self, baslik: str, varsayilan_port: int) -> dict:
        grup = QGroupBox(f"{baslik.upper()} BAĞLANTI")
        duz = QVBoxLayout(grup)
        form = QFormLayout()
        yontem = QComboBox()
        yontem.addItem("🏠 Aynı Ağ / Yerel", "yerel")
        yontem.addItem("🔁 Merkeze SSH Ters Tünel", "ters_ssh")
        yontem.addItem("🌐 Doğrudan SSH", "ssh")
        yontem.addItem("🧅 Tor SSH", "tor_ssh")
        yontem.addItem("🧅 Tor HTTP", "tor_http")
        yontem.addItem("🔒 Tor HTTPS", "tor_https")
        yontem.addItem("✈ Telegram Yedeği", "telegram")
        yontem.addItem("🤖 ADB / Android", "adb")
        yontem.setCurrentIndex(yontem.findData("tor_http" if baslik.lower().startswith("birincil") else "telegram"))
        host = QLineEdit()
        host.setPlaceholderText("Boş bırakılabilir")
        port = QSpinBox()
        port.setRange(1, 65535)
        port.setValue(varsayilan_port)
        kullanici = QLineEdit()
        anahtar = QLineEdit()
        anahtar.setPlaceholderText("İsteğe bağlı")
        token = QLineEdit()
        token.setPlaceholderText("İsteğe bağlı")
        aktif_cb = QCheckBox("Aktif")
        aktif_cb.setChecked(True)
        yedek_cb = QCheckBox("Yedek bağlantı")
        sec_btn = QPushButton("📁 Seç")

        anahtar_row = QHBoxLayout()
        anahtar_row.addWidget(anahtar)
        anahtar_row.addWidget(sec_btn)
        anahtar_w = QWidget()
        anahtar_w.setLayout(anahtar_row)

        sec_btn.clicked.connect(lambda: self._anahtar_sec(anahtar))
        form.addRow("Bağlantı Türü:", yontem)
        form.addRow("", aktif_cb)
        form.addRow("", yedek_cb)
        duz.addLayout(form)

        detay_w = QWidget()
        detay_form = QFormLayout(detay_w)
        detay_form.setContentsMargins(0, 0, 0, 0)
        detay_form.addRow("Host / Hedef:", host)
        detay_form.addRow("Port:", port)
        detay_form.addRow("Kullanıcı:", kullanici)
        detay_form.addRow("Anahtar:", anahtar_w)
        detay_form.addRow("Token:", token)
        duz.addWidget(detay_w)
        return {
            "grup": grup,
            "yontem": yontem,
            "host": host,
            "port": port,
            "kullanici": kullanici,
            "anahtar": anahtar,
            "token": token,
            "aktif_cb": aktif_cb,
            "yedek_cb": yedek_cb,
            "detay_w": detay_w,
        }

    def _ileri_ag_gorunurluk_guncelle(self, acik: bool):
        for alan in (self.birincil, self.yedek):
            alan["detay_w"].setVisible(acik)
            alan["aktif_cb"].setVisible(acik)
            alan["yedek_cb"].setVisible(acik)
        self.tor_grp.setVisible(acik)

    def _varsayilan_baglanti_bilgisi(self, yontem: str) -> tuple[str, str, str]:
        yontem = (yontem or "").strip().lower()
        cekirdek = getattr(self.parent(), "cekirdek", None)
        onion_host = ""
        onion_port = ""
        onion_user = ""
        if cekirdek:
            onion_host = getattr(cekirdek.uzuv, "onion_host", "") or ""
            onion_port = str(getattr(cekirdek.uzuv, "onion_port", 22) or 22)
            onion_user = getattr(cekirdek.uzuv, "onion_kullanici", "") or ""
            if not onion_host:
                try:
                    onion_host = cekirdek.tor.onion_adresi_al("ssh") or ""
                except Exception:
                    onion_host = ""
        if yontem in ("tor_ssh", "tor_http", "tor_https"):
            return onion_host, onion_port, onion_user or "zihin"
        if yontem == "telegram":
            return "", "0", ""
        if yontem == "adb":
            return "", "5555", ""
        return "", "", ""

    def _anahtar_sec(self, hedef_e):
        f, _ = QFileDialog.getOpenFileName(
            self, "SSH Anahtar Seç", os.path.expanduser("~/.ssh"), "Tümü (*)")
        if f:
            hedef_e.setText(f)

    def _baglanti_formu_doldur(self, alanlar: dict, baglanti):
        if not baglanti:
            return
        idx = alanlar["yontem"].findData(str(getattr(baglanti, "yontem", "")))
        if idx >= 0:
            alanlar["yontem"].setCurrentIndex(idx)
        alanlar["host"].setText(getattr(baglanti, "host", ""))
        alanlar["port"].setValue(int(getattr(baglanti, "port", 22) or 22))
        alanlar["kullanici"].setText(getattr(baglanti, "kullanici", ""))
        alanlar["anahtar"].setText(getattr(baglanti, "anahtar", ""))
        alanlar["token"].setText(getattr(baglanti, "token", ""))
        alanlar["aktif_cb"].setChecked(bool(getattr(baglanti, "aktif", True)))
        alanlar["yedek_cb"].setChecked(bool(getattr(baglanti, "yedek", False)))

    def _doldur(self, u):
        self.ad_e.setText(u.ad)
        self.takma_e.setText(getattr(u, "takma_isim", ""))
        self.id_e.setText(u.id)
        for cb, val in [(self.tip_e, u.tip)]:
            idx = cb.findData(str(getattr(val, "value", val)))
            if idx >= 0: cb.setCurrentIndex(idx)
        self.simge_e.setText(u.simge)
        self.notlar_e.setText(u.notlar)
        self.tor_host_e.setText(u.tor_proxy_host)
        self.tor_port_e.setValue(u.tor_proxy_port)
        self.sessiz_cb.setChecked(getattr(u, "sessiz_mod", False))
        self.setup_otomatik_cb.setChecked(False)
        birincil = u.birincil_baglanti() if hasattr(u, "birincil_baglanti") else None
        yedekler = u.yedek_baglantilar() if hasattr(u, "yedek_baglantilar") else []
        self._baglanti_formu_doldur(self.birincil, birincil)
        self._baglanti_formu_doldur(self.yedek, yedekler[0] if yedekler else None)
        for i in range(self.bilinc_lst.count()):
            item = self.bilinc_lst.item(i)
            if item.text() in u.atanmis_bilincler:
                item.setSelected(True)

    def uzuv_al(self):
        from .uzuv_yoneticisi import Uzuv, Baglanti
        secili = [self.bilinc_lst.item(i).text()
                  for i in range(self.bilinc_lst.count())
                  if self.bilinc_lst.item(i).isSelected()]
        uid = self.id_e.text().strip() or str(uuid.uuid4())[:8]
        birincil_yontem = self.birincil["yontem"].currentData()
        yedek_yontem = self.yedek["yontem"].currentData()
        bir_host, bir_port, bir_user = self._varsayilan_baglanti_bilgisi(birincil_yontem)
        yed_host, yed_port, yed_user = self._varsayilan_baglanti_bilgisi(yedek_yontem)
        birincil_baglanti = Baglanti(
            id=f"{uid}-birincil",
            yontem=birincil_yontem,
            aktif=self.birincil["aktif_cb"].isChecked(),
            yedek=False,
            host=self.birincil["host"].text().strip() or bir_host,
            port=self.birincil["port"].value() if self.ileri_ag_cb.isChecked() else int(bir_port or self.birincil["port"].value()),
            kullanici=self.birincil["kullanici"].text().strip() or bir_user,
            anahtar=self.birincil["anahtar"].text().strip(),
            token=self.birincil["token"].text().strip(),
            proxy_host=self.tor_host_e.text().strip(),
            proxy_port=self.tor_port_e.value(),
        )
        yedek_baglanti = Baglanti(
            id=f"{uid}-yedek",
            yontem=yedek_yontem,
            aktif=self.yedek["aktif_cb"].isChecked(),
            yedek=True,
            host=self.yedek["host"].text().strip() or yed_host,
            port=self.yedek["port"].value() if self.ileri_ag_cb.isChecked() else int(yed_port or self.yedek["port"].value()),
            kullanici=self.yedek["kullanici"].text().strip() or yed_user,
            anahtar=self.yedek["anahtar"].text().strip(),
            token=self.yedek["token"].text().strip(),
            proxy_host=self.tor_host_e.text().strip(),
            proxy_port=self.tor_port_e.value(),
        )
        baglantilar = [birincil_baglanti]
        if yedek_baglanti.aktif:
            baglantilar.append(yedek_baglanti)
        u = Uzuv(
            id=uid, ad=self.ad_e.text().strip(),
            takma_isim=self.takma_e.text().strip(),
            tip=self.tip_e.currentData(),
            yontem=birincil_baglanti.yontem,
            baglantilar=baglantilar,
            ssh_host=birincil_baglanti.host,
            ssh_port=birincil_baglanti.port,
            ssh_kullanici=birincil_baglanti.kullanici,
            ssh_anahtar=birincil_baglanti.anahtar,
            simge=self.simge_e.text().strip() or "🖥️",
            notlar=self.notlar_e.text().strip(),
            tor_proxy_host=self.tor_host_e.text().strip(),
            tor_proxy_port=self.tor_port_e.value(),
            adb_host=yedek_baglanti.host if yedek_baglanti.yontem == "adb" else "",
            adb_port=yedek_baglanti.port if yedek_baglanti.yontem == "adb" else 5555,
            atanmis_bilincler=secili,
        )
        # sessiz_mod dinamik olarak ekle
        u.sessiz_mod = self.sessiz_cb.isChecked()
        return u

    def setup_ayari_al(self) -> dict | None:
        if not self.setup_otomatik_cb.isChecked():
            return None
        platform_kod, format_metin = self.setup_paket_cb.currentData()
        birincil = self.birincil["yontem"].currentData()
        if birincil == "telegram":
            baglanti_modu = "telegram_agent"
        elif birincil == "tor_https":
            baglanti_modu = "tor_https"
        elif birincil in ("tor_http", "tor_ssh"):
            baglanti_modu = "tor_http"
        else:
            baglanti_modu = "ssh_reverse"
        return {
            "baglanti_modu": baglanti_modu,
            "platform_kod": "android_apk" if platform_kod == "android" and "APK" in format_metin else (
                "android_termux" if platform_kod == "android" else platform_kod
            ),
            "platform_txt": self.setup_paket_cb.currentText(),
            "format_metin": format_metin,
            "derle_paket": self.setup_derle_cb.isChecked(),
            "klasor": self.setup_klasor_e.text().strip(),
        }


# ── Komut Diyalog ─────────────────────────────────────────────────────────────
class KomutDiyalog(QDialog):
    def __init__(self, komut=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Komut Ekle / Düzenle")
        self.setMinimumWidth(560)
        self.komut = komut
        self._kur()
        if komut:
            self._doldur(komut)

    def _kur(self):
        duz = QVBoxLayout(self)
        form = QFormLayout()
        self.ad_e       = QLineEdit()
        self.kategori_e = QLineEdit()
        self.tur_e      = QComboBox()
        self.tur_e.addItems(["kabuk", "konusma", "uzuv"])
        self.os_e       = QComboBox()
        self.os_e.addItems(["hepsi", "linux", "windows", "android"])
        self.tetik_e    = QTextEdit(); self.tetik_e.setMaximumHeight(60)
        self.tetik_e.setPlaceholderText("Her satıra bir tetikleyici")
        self.komut_e    = QLineEdit(); self.komut_e.setPlaceholderText("Linux/Mac")
        self.komut_w_e  = QLineEdit(); self.komut_w_e.setPlaceholderText("Windows")
        self.komut_a_e  = QLineEdit(); self.komut_a_e.setPlaceholderText("Android/Termux")
        self.yanit_e    = QLineEdit()
        self.uzuv_e     = QLineEdit(); self.uzuv_e.setPlaceholderText("Uzuv ID")
        self.aciklama_e = QLineEdit()
        self.aktif_cb   = QCheckBox("Aktif"); self.aktif_cb.setChecked(True)
        self.yetki_lst  = QListWidget()
        self.yetki_lst.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for b in TUM_BILINCLER:
            self.yetki_lst.addItem(b)
        self.yetki_lst.setMaximumHeight(80)
        form.addRow("Ad:", self.ad_e)
        form.addRow("Kategori:", self.kategori_e)
        form.addRow("Tür:", self.tur_e)
        form.addRow("Hedef OS:", self.os_e)
        form.addRow("Tetikleyiciler:", self.tetik_e)
        form.addRow("Komut (Linux):", self.komut_e)
        form.addRow("Komut (Win):", self.komut_w_e)
        form.addRow("Komut (Android):", self.komut_a_e)
        form.addRow("Yanıt metni:", self.yanit_e)
        form.addRow("Uzuv ID:", self.uzuv_e)
        form.addRow("Açıklama:", self.aciklama_e)
        form.addRow("", self.aktif_cb)
        form.addRow("Yetkili Bilinçler:", self.yetki_lst)
        duz.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        duz.addWidget(bb)

    def _doldur(self, k):
        self.ad_e.setText(k.ad)
        self.kategori_e.setText(k.kategori)
        for cb, val in [(self.tur_e, k.tur), (self.os_e, k.hedef_os)]:
            idx = cb.findText(val)
            if idx >= 0: cb.setCurrentIndex(idx)
        self.tetik_e.setPlainText("\n".join(k.tetikleyiciler))
        self.komut_e.setText(k.komut)
        self.komut_w_e.setText(k.komut_windows)
        self.komut_a_e.setText(k.komut_android)
        self.yanit_e.setText(k.yanit)
        self.uzuv_e.setText(k.uzuv_id)
        self.aciklama_e.setText(k.aciklama)
        self.aktif_cb.setChecked(k.aktif)
        for i in range(self.yetki_lst.count()):
            if self.yetki_lst.item(i).text() in k.yetkili_bilincler:
                self.yetki_lst.item(i).setSelected(True)

    def komut_al(self):
        from .komut_veritabani import Komut
        yetki = [self.yetki_lst.item(i).text()
                 for i in range(self.yetki_lst.count())
                 if self.yetki_lst.item(i).isSelected()]
        tetikler = [t.strip() for t in
                    self.tetik_e.toPlainText().split("\n") if t.strip()]
        ad  = self.ad_e.text().strip()
        kat = self.kategori_e.text().strip()
        kid = f"{kat}_{ad}".lower().replace(" ", "_")[:40]
        if self.komut and self.komut.id:
            kid = self.komut.id
        return Komut(
            id=kid, kategori=kat, ad=ad,
            tetikleyiciler=tetikler,
            tur=self.tur_e.currentText(),
            komut=self.komut_e.text().strip(),
            komut_windows=self.komut_w_e.text().strip(),
            komut_android=self.komut_a_e.text().strip(),
            yanit=self.yanit_e.text().strip(),
            uzuv_id=self.uzuv_e.text().strip(),
            hedef_os=self.os_e.currentText(),
            aciklama=self.aciklama_e.text().strip(),
            aktif=self.aktif_cb.isChecked(),
            yetkili_bilincler=yetki,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Ana Arayüz
# ═══════════════════════════════════════════════════════════════════════════════
class AnaArayuz(QMainWindow):
    def __init__(self, cekirdek=None):
        super().__init__()
        self.cekirdek = cekirdek
        self.sinyal   = SinyalKoprusu()
        self._basladi = False
        self._slot_kartlari: dict = {}

        self._hitap_adlari: dict[str, str] = dict(VARSAYILAN_HITAP)
        self._hitap_dosyasi = ""
        if cekirdek:
            self._hitap_dosyasi = os.path.join(
                cekirdek.proje_yolu, "hitap_ayar.json")
            self._hitap_yukle()

        # Bilinç görünen adları (GUI'den değiştirilebilir)
        self._bilinc_goruntu: dict[str, str] = {}
        self._bilinc_goruntu_yukle()

        self.setWindowTitle("Zihin Köprüsü v7.0")
        self.setMinimumSize(1440, 860)
        self.setStyleSheet(STIL)

        merkez = QWidget()
        self.setCentralWidget(merkez)
        ana = QHBoxLayout(merkez)
        ana.setContentsMargins(0, 0, 0, 0); ana.setSpacing(0)

        ana.addWidget(self._sol_panel_olustur())
        self.sekmeler = QTabWidget()
        self.sekmeler.setDocumentMode(True)
        self.sekmeler.addTab(self._ana_sekme(),        "◈  ANA")
        self.sekmeler.addTab(self._makro_sekme(),      "⚡  MAKROLAR")
        self.sekmeler.addTab(self._uzuv_sekme(),       "🖥  UZUVLAR")
        self.sekmeler.addTab(self._komut_sekme(),      "⌨  KOMUTLAR")
        if self._gelistirici_modu_aktif():
            self.sekmeler.addTab(self._eklenti_sekme(), "⬡  EKLENTİLER")
            self.sekmeler.addTab(self._plugin_sekme(),  "📦  PLUGİNLER")
        self.sekmeler.addTab(self._ai_sekme(),         "🤖  AI")
        self.sekmeler.addTab(self._ses_sekme(),        "🔊  SES")
        self.sekmeler.addTab(self._karakter_sekme(),   "👤  KARAKTERLER")
        self.sekmeler.addTab(self._telegram_sekme(),   "✈  TELEGRAM")
        self.sekmeler.addTab(self._tor_sekme(),        "🧅  TOR")
        self.sekmeler.addTab(self._guncelleme_sekme(), "⬇  GÜNCELLEME")
        self.sekmeler.addTab(self._yedek_sekme(),      "💾  YEDEK")
        self.sekmeler.addTab(self._gunluk_sekme(),     "≡  GÜNLÜK")
        self.sekmeler.addTab(self._yardim_sekme(),     "❓  YARDIM")
        self.sekmeler.addTab(self._hakkinda_sekme(),   "ℹ  HAKKINDA")
        ana.addWidget(self.sekmeler, 1)

        self.statusBar().showMessage("Zihin Köprüsü v7.0 — Hazır.")
        self._sinyaller_bagla()
        if cekirdek:
            self._cekirdek_bagla()

    def _gelistirici_modu_aktif(self) -> bool:
        if not self.cekirdek:
            return False
        return bool(self.cekirdek.beyin.get("arayuz", {}).get("gelistirici_modu", False))

    # ── Bilinç Görüntü Adı ───────────────────────────────────────────────────

    def _bilinc_goruntu_yukle(self):
        if not self.cekirdek:
            return
        dosya = os.path.join(self.cekirdek.proje_yolu, "bilinc_goruntu.json")
        if os.path.exists(dosya):
            try:
                with open(dosya) as f:
                    self._bilinc_goruntu = json.load(f)
            except Exception:
                pass

    def _bilinc_goruntu_kaydet(self):
        if not self.cekirdek:
            return
        dosya = os.path.join(self.cekirdek.proje_yolu, "bilinc_goruntu.json")
        with open(dosya, "w") as f:
            json.dump(self._bilinc_goruntu, f, ensure_ascii=False, indent=2)

    def _goruntu_ad(self, bilinc: str) -> str:
        return self._bilinc_goruntu.get(bilinc, bilinc)

    # ── Hitap ────────────────────────────────────────────────────────────────

    def _hitap_yukle(self):
        if self._hitap_dosyasi and os.path.exists(self._hitap_dosyasi):
            try:
                with open(self._hitap_dosyasi) as f:
                    self._hitap_adlari = json.load(f)
            except Exception:
                pass

    def _hitap_kaydet(self):
        if self._hitap_dosyasi:
            with open(self._hitap_dosyasi, "w") as f:
                json.dump(self._hitap_adlari, f, ensure_ascii=False, indent=2)
        if self.cekirdek:
            self.cekirdek._hitap_adlari = self._hitap_adlari

    # ── Sol Panel ────────────────────────────────────────────────────────────

    def _sol_panel_olustur(self):
        p = QWidget(); p.setFixedWidth(248)
        p.setStyleSheet(
            f"background:{R['panel']};border-right:1px solid {R['kenar']};")
        d = QVBoxLayout(p); d.setContentsMargins(14, 18, 14, 18); d.setSpacing(14)

        logo = QLabel("ZİHİN\nKÖPRÜSÜ")
        logo.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            f"color:{R['vurgu']};letter-spacing:4px;"
            f"padding:10px 0;border-bottom:1px solid {R['kenar']};")
        d.addWidget(logo)

        surum = QLabel("v7.1  |  MERKEZ AĞI")
        surum.setAlignment(Qt.AlignmentFlag.AlignCenter)
        surum.setFont(QFont("Courier New", 9))
        surum.setStyleSheet(f"color:{R['metin3']};margin-top:-10px;")
        d.addWidget(surum)

        # Hologram efekti: ASCII karakterin etrafında dönen çerçeve
        hologram_kap = QWidget()
        hologram_kap.setFixedSize(188, 188)
        hologram_layout = QVBoxLayout(hologram_kap)
        hologram_layout.setContentsMargins(18, 18, 18, 18)

        self.hologram = HologramCerceve(hologram_kap)
        self.hologram.setGeometry(0, 0, 188, 188)

        self.ascii_karakter = ASCIIKarakter()
        hologram_layout.addWidget(self.ascii_karakter)
        d.addWidget(hologram_kap, 0, Qt.AlignmentFlag.AlignHCenter)

        self.sol_telemetri_lbl = QLabel("MERKEZ: BEKLEMEDE\nBAĞ: HAZIRLANIYOR\nSES: PASİF")
        self.sol_telemetri_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sol_telemetri_lbl.setFont(QFont("Courier New", 9))
        self.sol_telemetri_lbl.setStyleSheet(
            f"color:{R['metin2']};"
            f"background:{R['panel2']};"
            f"border:1px solid {R['kenar']};"
            f"border-radius:8px;padding:8px;")
        d.addWidget(self.sol_telemetri_lbl)

        # Ses dalgası animasyonu
        self.ses_dalgasi = SesDalgasiWidget()
        d.addWidget(self.ses_dalgasi)

        self.durum_lbl = QLabel("◎  BEKLEMEDE")
        self.durum_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.durum_lbl.setFont(QFont("Courier New", 10))
        self.durum_lbl.setStyleSheet(f"color:{R['metin2']};letter-spacing:2px;")
        d.addWidget(self.durum_lbl)

        grp = QGroupBox("AKTİF BİLİNÇ")
        gd = QVBoxLayout(grp)
        bilinc = self.cekirdek.aktif_bilinc if self.cekirdek else "ABLA"
        self.bilinc_lbl = QLabel(self._goruntu_ad(bilinc))
        self.bilinc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bilinc_lbl.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self.bilinc_lbl.setStyleSheet(f"color:{R['vurgu']};")
        self.hitap_lbl = QLabel("")
        self.hitap_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hitap_lbl.setFont(QFont("Courier New", 9))
        self.hitap_lbl.setStyleSheet(f"color:{R['metin3']};")
        gd.addWidget(self.bilinc_lbl); gd.addWidget(self.hitap_lbl)
        d.addWidget(grp)
        self._sol_hitap_guncelle()

        self.baslat_btn = QPushButton("▶  BAŞLAT")
        self.baslat_btn.setObjectName("aksiyon")
        self.baslat_btn.setFixedHeight(48)
        self.baslat_btn.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        self.baslat_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {R['vurgu2']}, stop:1 {R['vurgu']});
                color: {R['arkaplan']};
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                letter-spacing: 2px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {R['vurgu']}, stop:1 {R['vurgu2']});
            }}
            QPushButton:pressed {{
                background: {R['vurgu2']};
                padding-top: 12px;
            }}
        """)
        self.baslat_btn.clicked.connect(self._baslat_durdur)
        d.addWidget(self.baslat_btn)

        # Wake word toggle
        self.wake_cb = QCheckBox("🎤  Wake Word")
        self.wake_cb.setToolTip(
            "Aktif: Sadece wake word duyulunca dinler\n"
            "Pasif: Sürekli dinler (eski mod)")
        self.wake_cb.setStyleSheet(
            f"QCheckBox{{color:{R['vurgu']};font-size:11px;}}"
            f"QCheckBox::indicator{{width:14px;height:14px;}}")
        self.wake_cb.toggled.connect(self._wake_word_toggled)
        d.addWidget(self.wake_cb)

        self.gelistirici_modu_cb = QCheckBox("⚙  Geliştirici Araçları")
        self.gelistirici_modu_cb.setToolTip(
            "Eklentiler ve Pluginler sekmelerini gösterir. Normal kullanıcı için kapalı kalmalıdır."
        )
        self.gelistirici_modu_cb.setStyleSheet(
            f"QCheckBox{{color:{R['metin3']};font-size:10px;}}"
            f"QCheckBox::indicator{{width:14px;height:14px;}}")
        self.gelistirici_modu_cb.setChecked(self._gelistirici_modu_aktif())
        self.gelistirici_modu_cb.toggled.connect(self._gelistirici_modu_toggled)
        d.addWidget(self.gelistirici_modu_cb)

        self.ses_kes_btn = QPushButton("⏹  SES KES")
        self.ses_kes_btn.setFixedHeight(40)
        self.ses_kes_btn.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        self.ses_kes_btn.setStyleSheet(f"""
            QPushButton {{
                background: {R['panel2']};
                color: {R['kirmizi']};
                border: 2px solid {R['kirmizi']};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background: {R['kirmizi']};
                color: white;
                border-color: {R['kirmizi']};
            }}
            QPushButton:pressed {{
                background: #cc0000;
                padding-top: 10px;
            }}
            QPushButton:disabled {{
                color: {R['metin3']};
                border-color: {R['metin3']};
                background: {R['panel']};
            }}
        """)
        self.ses_kes_btn.clicked.connect(self._ses_kes)
        self.ses_kes_btn.setEnabled(False)
        d.addWidget(self.ses_kes_btn)
        d.addStretch()

        sahip = (self.cekirdek.beyin["sistem"]["sahip"]
                 if self.cekirdek else "Operatör")
        self.aktif_lbl = QLabel(f"◈ {sahip}")
        self.aktif_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.aktif_lbl.setFont(QFont("Courier New", 9))
        self.aktif_lbl.setStyleSheet(
            f"color:{R['metin3']};border-top:1px solid {R['kenar']};padding-top:10px;")
        d.addWidget(self.aktif_lbl)
        return p

    def _sol_hitap_guncelle(self):
        b = (self.bilinc_lbl.text() if hasattr(self, "bilinc_lbl")
             else "ABLA")
        # bilinc_lbl görüntü adı gösteriyor, gerçek bilinç ID'yi bul
        gercek = next((k for k, v in self._bilinc_goruntu.items()
                       if v == b), b)
        hitap = self._hitap_adlari.get(gercek, "Operatör")
        if hasattr(self, "hitap_lbl"):
            self.hitap_lbl.setText(f"hitap: {hitap}")

    # ── Ana Sekme ────────────────────────────────────────────────────────────



    def _makro_sekme(self):
        w = QWidget()
        kaydir = QScrollArea(); kaydir.setWidgetResizable(True)
        kaydir.setStyleSheet("QScrollArea{border:none;}")
        kap = QWidget()
        d = QVBoxLayout(kap); d.setContentsMargins(16,16,16,16); d.setSpacing(12)

        bl = QLabel("⚡  MAKROLAR & RUTINLER")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        d.addWidget(bl)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Sol: Makro Listesi ─────────────────────────────────────────────
        sol = QWidget()
        sol_d = QVBoxLayout(sol); sol_d.setContentsMargins(0,0,6,0)

        self.makro_liste = QTreeWidget()
        self.makro_liste.setHeaderLabels(["Makro", "Tetik", "Son Çalışma"])
        self.makro_liste.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.makro_liste.setColumnWidth(1, 80)
        self.makro_liste.itemSelectionChanged.connect(self._makro_secildi)
        sol_d.addWidget(self.makro_liste)

        btn_row = QHBoxLayout()
        ekle_btn = QPushButton("+ Ekle")
        ekle_btn.clicked.connect(self._makro_ekle_dialog)
        sil_btn  = QPushButton("✕ Sil")
        sil_btn.setObjectName("tehlike")
        sil_btn.clicked.connect(self._makro_sil)
        calistir_btn = QPushButton("▶ Çalıştır")
        calistir_btn.setObjectName("aksiyon")
        calistir_btn.clicked.connect(self._makro_calistir)
        btn_row.addWidget(ekle_btn); btn_row.addWidget(sil_btn)
        btn_row.addWidget(calistir_btn)
        sol_d.addLayout(btn_row)
        splitter.addWidget(sol)

        # ── Sağ: Makro Detayı ─────────────────────────────────────────────
        sag = QWidget()
        sag_d = QVBoxLayout(sag); sag_d.setContentsMargins(6,0,0,0)

        grp_det = QGroupBox("MAKRO DETAYI")
        gdet = QFormLayout(grp_det)
        self.makro_ad_e     = QLineEdit(); self.makro_ad_e.setPlaceholderText("Makro adı")
        self.makro_acik_e   = QLineEdit(); self.makro_acik_e.setPlaceholderText("Açıklama")
        self.makro_tetik_cb = QComboBox()
        self.makro_tetik_cb.addItems([
            "Manuel", "Zamanlı (saat)", "Aralıklı", "Koşullu", "Sesli"])
        self.makro_tetik_cb.currentIndexChanged.connect(
            self._makro_tetik_degisti)
        self.makro_aktif_cb = QCheckBox("Aktif")
        self.makro_aktif_cb.setChecked(True)
        gdet.addRow("Ad:", self.makro_ad_e)
        gdet.addRow("Açıklama:", self.makro_acik_e)
        gdet.addRow("Tetikleyici:", self.makro_tetik_cb)
        gdet.addRow("", self.makro_aktif_cb)
        sag_d.addWidget(grp_det)

        # Zamanlı ayarlar
        self.makro_zaman_w = QWidget()
        zw = QFormLayout(self.makro_zaman_w)
        self.makro_saat_e = QLineEdit(); self.makro_saat_e.setPlaceholderText("07:30")
        self.makro_gun_e  = QLineEdit(); self.makro_gun_e.setPlaceholderText("0,1,2,3,4 (Pzt-Cum)")
        self.makro_kelime_e = QLineEdit(); self.makro_kelime_e.setPlaceholderText("günaydın")
        zw.addRow("Saat:", self.makro_saat_e)
        zw.addRow("Günler:", self.makro_gun_e)
        zw.addRow("Sesli kelime:", self.makro_kelime_e)
        self.makro_zaman_w.setVisible(False)
        sag_d.addWidget(self.makro_zaman_w)

        # Koşullu ayarlar
        self.makro_kosul_w = QWidget()
        kw = QFormLayout(self.makro_kosul_w)
        self.makro_kosul_cb = QComboBox()
        self.makro_kosul_cb.addItems([
            "CPU % aşım", "RAM % aşım", "Pil düşük",
            "İnternet yok", "İnternet var", "Sıcaklık aşım", "Uzuv çevrimdışı"])
        self.makro_esik_e = QDoubleSpinBox()
        self.makro_esik_e.setRange(0, 100); self.makro_esik_e.setValue(80)
        kw.addRow("Koşul:", self.makro_kosul_cb)
        kw.addRow("Eşik:", self.makro_esik_e)
        self.makro_kosul_w.setVisible(False)
        sag_d.addWidget(self.makro_kosul_w)

        # Adımlar
        grp_adim = QGroupBox("ADIMLAR")
        gadim = QVBoxLayout(grp_adim)
        self.makro_adim_lst = QListWidget()
        self.makro_adim_lst.setMinimumHeight(100)
        gadim.addWidget(self.makro_adim_lst)

        adim_ekle_row = QHBoxLayout()
        self.makro_adim_tip = QComboBox()
        self.makro_adim_tip.addItems(["komut", "bekle", "konusma", "isle"])
        self.makro_adim_deger = QLineEdit()
        self.makro_adim_deger.setPlaceholderText("Değer...")
        adim_ekle_btn = QPushButton("+")
        adim_ekle_btn.setFixedWidth(30)
        adim_ekle_btn.clicked.connect(self._makro_adim_ekle)
        adim_sil_btn = QPushButton("−")
        adim_sil_btn.setFixedWidth(30)
        adim_sil_btn.setObjectName("tehlike")
        adim_sil_btn.clicked.connect(self._makro_adim_sil)
        adim_ekle_row.addWidget(self.makro_adim_tip)
        adim_ekle_row.addWidget(self.makro_adim_deger, 1)
        adim_ekle_row.addWidget(adim_ekle_btn)
        adim_ekle_row.addWidget(adim_sil_btn)
        gadim.addLayout(adim_ekle_row)
        sag_d.addWidget(grp_adim)

        kaydet_btn = QPushButton("💾 Kaydet")
        kaydet_btn.setObjectName("aksiyon")
        kaydet_btn.clicked.connect(self._makro_kaydet)
        sag_d.addWidget(kaydet_btn)

        # Durum
        self.makro_durum_lbl = QLabel("")
        self.makro_durum_lbl.setStyleSheet(
            f"color:{R['yesil']};font-size:11px;")
        self.makro_durum_lbl.setWordWrap(True)
        sag_d.addWidget(self.makro_durum_lbl)
        sag_d.addStretch()
        splitter.addWidget(sag)

        # ── Zamanlayıcı Paneli ────────────────────────────────────────────
        grp_zaman = QGroupBox("⏱ HIZLI ZAMANLAYICI")
        gz = QHBoxLayout(grp_zaman)
        self.zaman_sure_e = QSpinBox()
        self.zaman_sure_e.setRange(1, 999); self.zaman_sure_e.setValue(5)
        self.zaman_birim_cb = QComboBox()
        self.zaman_birim_cb.addItems(["dakika", "saat"])
        self.zaman_mesaj_e = QLineEdit()
        self.zaman_mesaj_e.setPlaceholderText("Hatırlatıcı mesajı...")
        zaman_kur_btn = QPushButton("⏰ Kur")
        zaman_kur_btn.clicked.connect(self._zamanlayici_kur)
        gz.addWidget(QLabel("Süre:")); gz.addWidget(self.zaman_sure_e)
        gz.addWidget(self.zaman_birim_cb)
        gz.addWidget(self.zaman_mesaj_e, 1)
        gz.addWidget(zaman_kur_btn)
        d.addWidget(grp_zaman)

        splitter.setSizes([340, 460])
        d.addWidget(splitter, 1)

        kaydir.setWidget(kap)
        ana = QVBoxLayout(w); ana.setContentsMargins(0,0,0,0)
        ana.addWidget(kaydir)

        self._makro_listesi_yenile()
        return w

    def _makro_tetik_degisti(self, idx):
        self.makro_zaman_w.setVisible(idx in (1, 2, 4))
        self.makro_kosul_w.setVisible(idx == 3)

    def _makro_listesi_yenile(self):
        if not self.cekirdek or not hasattr(self.cekirdek, 'makro'):
            return
        self.makro_liste.clear()
        for mid, makro in self.cekirdek.makro.makrolar.items():
            son = makro.son_calisma[:16] if makro.son_calisma else "—"
            item = QTreeWidgetItem([
                ("✓ " if makro.aktif else "○ ") + makro.ad,
                makro.tetik_tipi,
                son,
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, mid)
            if not makro.aktif:
                item.setForeground(0, QColor(R["metin3"]))
            self.makro_liste.addTopLevelItem(item)

    def _makro_secildi(self):
        items = self.makro_liste.selectedItems()
        if not items or not self.cekirdek:
            return
        mid = items[0].data(0, Qt.ItemDataRole.UserRole)
        makro = self.cekirdek.makro.makrolar.get(mid)
        if not makro:
            return
        self.makro_ad_e.setText(makro.ad)
        self.makro_acik_e.setText(makro.aciklama)
        self.makro_aktif_cb.setChecked(makro.aktif)
        self.makro_saat_e.setText(makro.saat)
        self.makro_gun_e.setText(",".join(map(str, makro.gunler)))
        self.makro_kelime_e.setText(makro.sesli_kelime)
        self.makro_esik_e.setValue(makro.kosul_esik)
        self.makro_adim_lst.clear()
        for adim in makro.adimlar:
            self.makro_adim_lst.addItem(f"[{adim.tip}] {adim.deger}")

    def _makro_calistir(self):
        items = self.makro_liste.selectedItems()
        if not items or not self.cekirdek:
            return
        mid = items[0].data(0, Qt.ItemDataRole.UserRole)
        self.makro_durum_lbl.setText("▶ Çalışıyor...")
        def _cb(ok, mesaj):
            renk = R["yesil"] if ok else R["kirmizi"]
            self.makro_durum_lbl.setStyleSheet(
                f"color:{renk};font-size:11px;")
            self.makro_durum_lbl.setText(mesaj)
            self._makro_listesi_yenile()
        self.cekirdek.makro.calistir(mid, _cb)

    def _makro_ekle_dialog(self):
        import uuid
        mid = str(uuid.uuid4())[:8]
        try:
            from .makro_yoneticisi import Makro
        except ImportError:
            from zihin.makro_yoneticisi import Makro
        makro = Makro(id=mid, ad=f"Yeni Makro {mid}")
        self.cekirdek.makro.makro_ekle(makro)
        self._makro_listesi_yenile()

    def _makro_sil(self):
        items = self.makro_liste.selectedItems()
        if not items or not self.cekirdek:
            return
        mid = items[0].data(0, Qt.ItemDataRole.UserRole)
        self.cekirdek.makro.makro_sil(mid)
        self._makro_listesi_yenile()

    def _makro_adim_ekle(self):
        tip   = self.makro_adim_tip.currentText()
        deger = self.makro_adim_deger.text().strip()
        if deger:
            self.makro_adim_lst.addItem(f"[{tip}] {deger}")
            self.makro_adim_deger.clear()

    def _makro_adim_sil(self):
        row = self.makro_adim_lst.currentRow()
        if row >= 0:
            self.makro_adim_lst.takeItem(row)

    def _makro_kaydet(self):
        items = self.makro_liste.selectedItems()
        if not items or not self.cekirdek:
            return
        mid = items[0].data(0, Qt.ItemDataRole.UserRole)
        makro = self.cekirdek.makro.makrolar.get(mid)
        if not makro:
            return
        try:
            from .makro_yoneticisi import TetikTipi
        except ImportError:
            from zihin.makro_yoneticisi import TetikTipi
        makro.ad      = self.makro_ad_e.text().strip() or makro.ad
        makro.aciklama = self.makro_acik_e.text().strip()
        makro.aktif   = self.makro_aktif_cb.isChecked()
        makro.saat    = self.makro_saat_e.text().strip()
        makro.sesli_kelime = self.makro_kelime_e.text().strip()
        try:
            gunler_str = self.makro_gun_e.text().strip()
            makro.gunler = [int(g) for g in gunler_str.split(",")
                            if g.strip().isdigit()] if gunler_str else []
        except Exception:
            makro.gunler = []
        makro.kosul_esik = self.makro_esik_e.value()

        # Tetikleyici
        idx = self.makro_tetik_cb.currentIndex()
        tl = [TetikTipi.MANUEL, TetikTipi.ZAMANLI, TetikTipi.ARALIKLI,
              TetikTipi.KOSULLU, TetikTipi.SESLI]
        makro.tetik_tipi = tl[idx]

        # Adımlar
        try:
            from .makro_yoneticisi import MakroAdim
        except ImportError:
            from zihin.makro_yoneticisi import MakroAdim
        adimlar = []
        for i in range(self.makro_adim_lst.count()):
            metin = self.makro_adim_lst.item(i).text()
            if metin.startswith("[") and "]" in metin:
                tip   = metin[1:metin.index("]")]
                deger = metin[metin.index("]")+2:]
                adimlar.append(MakroAdim(tip=tip, deger=deger))
        makro.adimlar = adimlar

        self.cekirdek.makro.makro_guncelle(makro)
        self._makro_listesi_yenile()
        self.makro_durum_lbl.setText("✓ Kaydedildi.")

    def _zamanlayici_kur(self):
        if not self.cekirdek:
            return
        sure = self.zaman_sure_e.value()
        birim = self.zaman_birim_cb.currentText()
        dk = sure if birim == "dakika" else sure * 60
        mesaj = self.zaman_mesaj_e.text().strip() or f"{sure} {birim} geçti!"
        self.cekirdek.makro.zamanlayici_ekle(
            ad=mesaj, sure_dakika=dk, mesaj=mesaj)
        self.makro_durum_lbl.setText(
            f"⏰ Zamanlayıcı kuruldu: {sure} {birim} sonra — {mesaj}")
        self.zaman_mesaj_e.clear()

    # ═══════════════════════════════════════════════════════════════════════
    # Dashboard & Hologram Efektler
    # ═══════════════════════════════════════════════════════════════════════

    def _dashboard_sekme(self):
        w = QWidget()
        d = QVBoxLayout(w); d.setContentsMargins(0, 0, 0, 0); d.setSpacing(8)

        kap = QFrame()
        kap.setStyleSheet(
            f"QFrame{{background:{R['panel']};border:1px solid {R['kenar']};"
            f"border-radius:10px;}}"
        )
        kd = QVBoxLayout(kap); kd.setContentsMargins(12, 10, 12, 12); kd.setSpacing(8)

        ust = QHBoxLayout()
        bl = QLabel("SİSTEM ÖZETİ")
        bl.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;border:none;")
        self.dash_yenile_btn = QPushButton("Canlı")
        self.dash_yenile_btn.setCheckable(True)
        self.dash_yenile_btn.setChecked(True)
        self.dash_yenile_btn.setFixedWidth(72)
        self.dash_yenile_btn.toggled.connect(self._dash_oto_yenile_toggled)
        ust.addWidget(bl)
        ust.addStretch()
        ust.addWidget(self.dash_yenile_btn)
        kd.addLayout(ust)

        kartlar = QGridLayout()
        kartlar.setSpacing(8)

        self.dash_cpu_bar = QProgressBar()
        self.dash_cpu_bar.setRange(0, 100); self.dash_cpu_bar.setTextVisible(False)
        self.dash_cpu_bar.setStyleSheet(self._bar_stil(R["vurgu"]))
        self.dash_cpu_lbl = QLabel("—")
        kartlar.addWidget(self._ozet_karti("İşlemci", self.dash_cpu_lbl, self.dash_cpu_bar, R["vurgu"]), 0, 0)

        self.dash_ram_bar = QProgressBar()
        self.dash_ram_bar.setRange(0, 100); self.dash_ram_bar.setTextVisible(False)
        self.dash_ram_bar.setStyleSheet(self._bar_stil(R["vurgu2"]))
        self.dash_ram_lbl = QLabel("—")
        kartlar.addWidget(self._ozet_karti("Bellek", self.dash_ram_lbl, self.dash_ram_bar, R["vurgu2"]), 0, 1)

        self.dash_disk_bar = QProgressBar()
        self.dash_disk_bar.setRange(0, 100); self.dash_disk_bar.setTextVisible(False)
        self.dash_disk_bar.setStyleSheet(self._bar_stil(R["yesil"]))
        self.dash_disk_lbl = QLabel("—")
        kartlar.addWidget(self._ozet_karti("Disk", self.dash_disk_lbl, self.dash_disk_bar, R["yesil"]), 0, 2)

        self.dash_sicak_lbl = QLabel("—")
        kartlar.addWidget(self._ozet_karti("Sıcaklık", self.dash_sicak_lbl, None, R["turuncu"]), 1, 0)

        self.dash_pil_lbl = QLabel("—")
        kartlar.addWidget(self._ozet_karti("Güç", self.dash_pil_lbl, None, R["yesil"]), 1, 1)

        self.dash_uzuv_ozet_lbl = QLabel("—")
        kartlar.addWidget(self._ozet_karti("Uzuvlar", self.dash_uzuv_ozet_lbl, None, R["sari"]), 1, 2)

        kd.addLayout(kartlar)

        alt = QHBoxLayout()
        self.dash_ag_lbl = QLabel("Ağ: bekleniyor")
        self.dash_ag_lbl.setStyleSheet(f"color:{R['metin2']};font-size:10px;border:none;")
        self.dash_ek_lbl = QLabel("Çalışma: —")
        self.dash_ek_lbl.setStyleSheet(f"color:{R['metin2']};font-size:10px;border:none;")
        ping_btn = QPushButton("Uzuvları Yokla")
        ping_btn.setFixedWidth(120)
        ping_btn.clicked.connect(self._dash_tum_ping)
        alt.addWidget(self.dash_ag_lbl)
        alt.addStretch()
        alt.addWidget(self.dash_ek_lbl)
        alt.addWidget(ping_btn)
        kd.addLayout(alt)

        d.addWidget(kap)

        # Timer — her 3sn güncelle
        self._dash_timer = QTimer(self)
        self._dash_timer.timeout.connect(self._dash_guncelle)
        self._dash_timer.start(3000)
        self._dash_guncelle()  # İlk anlık veri

        return w

    def _ozet_karti(self, baslik: str, deger_lbl: QLabel, bar: QProgressBar | None, renk: str) -> QFrame:
        kart = QFrame()
        kart.setMinimumHeight(86)
        kart.setStyleSheet(
            f"QFrame{{background:{R['panel2']};border:1px solid {R['kenar']};"
            f"border-radius:9px;}}"
            f"QLabel{{border:none;background:transparent;}}"
        )
        d = QVBoxLayout(kart); d.setContentsMargins(10, 8, 10, 8); d.setSpacing(5)
        bas = QLabel(baslik)
        bas.setStyleSheet(f"color:{R['metin2']};font-size:10px;letter-spacing:1px;")
        deger_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        deger_lbl.setStyleSheet(f"color:{renk};font-size:18px;font-weight:bold;")
        d.addWidget(bas)
        d.addWidget(deger_lbl)
        if bar:
            d.addWidget(bar)
        d.addStretch()
        return kart

    def _bar_stil(self, renk: str) -> str:
        return (
            f"QProgressBar{{background:{R['panel2']};border:1px solid {R['kenar']};"
            f"border-radius:4px;height:14px;text-align:center;"
            f"color:{R['metin']};font-size:10px;}}"
            f"QProgressBar::chunk{{background:{renk};border-radius:3px;}}"
        )

    def _dash_oto_yenile_toggled(self, aktif: bool):
        if not hasattr(self, "_dash_timer"):
            return
        if aktif:
            self._dash_timer.start(3000)
        else:
            self._dash_timer.stop()

    def _dash_guncelle(self):
        """Sistem metriklerini güncelle."""
        m = self._sistem_metrikleri_al()

        cpu = m.get("cpu")
        if cpu is not None:
            renk = R["kirmizi"] if cpu > 80 else (R["sari"] if cpu > 55 else R["vurgu"])
            self.dash_cpu_bar.setValue(int(cpu))
            self.dash_cpu_lbl.setText(f"{cpu:.0f}%")
            self.dash_cpu_lbl.setStyleSheet(f"color:{renk};font-size:18px;font-weight:bold;")

        ram = m.get("ram")
        if ram:
            yuzde = int(ram["percent"])
            renk = R["kirmizi"] if yuzde > 85 else (R["sari"] if yuzde > 65 else R["vurgu2"])
            self.dash_ram_bar.setValue(yuzde)
            self.dash_ram_lbl.setText(f"{yuzde}%")
            self.dash_ram_lbl.setToolTip(
                f"{self._boyut_yaz(ram['used'])} / {self._boyut_yaz(ram['total'])}"
            )
            self.dash_ram_lbl.setStyleSheet(f"color:{renk};font-size:18px;font-weight:bold;")

        disk = m.get("disk")
        if disk:
            yuzde = int(disk["percent"])
            renk = R["kirmizi"] if yuzde > 90 else (R["sari"] if yuzde > 75 else R["yesil"])
            self.dash_disk_bar.setValue(yuzde)
            self.dash_disk_lbl.setText(f"{yuzde}%")
            self.dash_disk_lbl.setToolTip(
                f"{self._boyut_yaz(disk['used'])} / {self._boyut_yaz(disk['total'])}"
            )
            self.dash_disk_lbl.setStyleSheet(f"color:{renk};font-size:18px;font-weight:bold;")

        net = m.get("net")
        if net:
            self.dash_ag_lbl.setText(
                f"Ağ: ↓ {self._hiz_yaz(net['down'])}/s  ↑ {self._hiz_yaz(net['up'])}/s"
            )

        sicak = m.get("sicaklik")
        if sicak is not None:
            renk = R["kirmizi"] if sicak > 80 else (R["sari"] if sicak > 65 else R["turuncu"])
            self.dash_sicak_lbl.setText(f"{sicak:.0f}°C")
            self.dash_sicak_lbl.setStyleSheet(f"color:{renk};font-size:18px;font-weight:bold;")
        else:
            self.dash_sicak_lbl.setText("—")
            self.dash_sicak_lbl.setToolTip("Bu cihaz sıcaklık verisini paylaşmıyor olabilir.")
            self.dash_sicak_lbl.setStyleSheet(f"color:{R['metin3']};font-size:18px;font-weight:bold;")

        pil = m.get("pil")
        if pil is None:
            self.dash_pil_lbl.setText("Adaptör")
            self.dash_pil_lbl.setStyleSheet(f"color:{R['metin2']};font-size:18px;font-weight:bold;")
        else:
            renk = R["kirmizi"] if pil < 15 else (R["sari"] if pil < 30 else R["yesil"])
            self.dash_pil_lbl.setText(f"{pil}%")
            self.dash_pil_lbl.setStyleSheet(f"color:{renk};font-size:18px;font-weight:bold;")

        self.dash_ek_lbl.setText(
            f"Yük {m.get('load', '—')} · Süreç {m.get('processes', '—')} · Çalışma {m.get('uptime', '—')}"
        )

        # Uzuv tablosu
        self._dash_uzuv_guncelle()

    def _sistem_metrikleri_al(self) -> dict:
        import os
        import shutil
        import time

        veri = {}
        try:
            import psutil
        except Exception:
            psutil = None

        if psutil:
            try:
                veri["cpu"] = float(psutil.cpu_percent(interval=None))
            except Exception:
                pass
            try:
                vm = psutil.virtual_memory()
                veri["ram"] = {"percent": vm.percent, "used": vm.used, "total": vm.total}
            except Exception:
                pass
            try:
                du = psutil.disk_usage("/")
                veri["disk"] = {"percent": du.percent, "used": du.used, "total": du.total}
            except Exception:
                pass
            try:
                io = psutil.net_io_counters()
                veri["net"] = self._ag_hizi_hesapla(io.bytes_recv, io.bytes_sent, time.time())
            except Exception:
                pass
            try:
                bat = psutil.sensors_battery()
                if bat is not None:
                    veri["pil"] = int(bat.percent)
            except Exception:
                pass
            try:
                veri["processes"] = len(psutil.pids())
            except Exception:
                pass

        if "cpu" not in veri:
            cpu = self._proc_cpu_yuzde()
            if cpu is not None:
                veri["cpu"] = cpu
        if "ram" not in veri:
            ram = self._proc_ram()
            if ram:
                veri["ram"] = ram
        if "disk" not in veri:
            du = shutil.disk_usage("/")
            veri["disk"] = {
                "percent": (du.used * 100 / du.total) if du.total else 0,
                "used": du.used,
                "total": du.total,
            }
        if "net" not in veri:
            net_raw = self._proc_net()
            if net_raw:
                veri["net"] = self._ag_hizi_hesapla(net_raw[0], net_raw[1], time.time())
        if "pil" not in veri:
            veri["pil"] = self._sysfs_pil()

        sicak = self._sicaklik_oku(psutil)
        if sicak is not None:
            veri["sicaklik"] = sicak

        try:
            yuk = os.getloadavg()
            veri["load"] = f"{yuk[0]:.2f}"
        except Exception:
            pass
        try:
            if psutil:
                uptime_s = max(0, time.time() - psutil.boot_time())
            else:
                with open("/proc/uptime", "r", encoding="utf-8") as f:
                    uptime_s = float(f.read().split()[0])
            veri["uptime"] = self._sure_yaz(uptime_s)
        except Exception:
            pass
        return veri

    def _proc_cpu_yuzde(self):
        try:
            with open("/proc/stat", "r", encoding="utf-8") as f:
                parcalar = [int(x) for x in f.readline().split()[1:8]]
            idle = parcalar[3] + parcalar[4]
            toplam = sum(parcalar)
            onceki = getattr(self, "_dash_cpu_onceki", None)
            self._dash_cpu_onceki = (toplam, idle)
            if not onceki:
                return 0.0
            toplam_fark = toplam - onceki[0]
            idle_fark = idle - onceki[1]
            if toplam_fark <= 0:
                return 0.0
            return max(0.0, min(100.0, (1.0 - idle_fark / toplam_fark) * 100.0))
        except Exception:
            return None

    def _proc_ram(self):
        try:
            mem = {}
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for satir in f:
                    ad, deger = satir.split(":", 1)
                    mem[ad] = int(deger.strip().split()[0]) * 1024
            toplam = mem.get("MemTotal", 0)
            uygun = mem.get("MemAvailable", 0)
            kullanilan = max(0, toplam - uygun)
            return {
                "percent": (kullanilan * 100 / toplam) if toplam else 0,
                "used": kullanilan,
                "total": toplam,
            }
        except Exception:
            return None

    def _proc_net(self):
        try:
            rx = tx = 0
            with open("/proc/net/dev", "r", encoding="utf-8") as f:
                for satir in f.readlines()[2:]:
                    if ":" not in satir:
                        continue
                    ad, veri = satir.split(":", 1)
                    if ad.strip() == "lo":
                        continue
                    p = veri.split()
                    rx += int(p[0])
                    tx += int(p[8])
            return rx, tx
        except Exception:
            return None

    def _ag_hizi_hesapla(self, rx: int, tx: int, simdi: float) -> dict:
        onceki = getattr(self, "_dash_net_onceki", None)
        self._dash_net_onceki = (rx, tx, simdi)
        if not onceki:
            return {"down": 0.0, "up": 0.0}
        dt = max(0.1, simdi - onceki[2])
        return {
            "down": max(0.0, (rx - onceki[0]) / dt),
            "up": max(0.0, (tx - onceki[1]) / dt),
        }

    def _sicaklik_oku(self, psutil_mod=None):
        try:
            if psutil_mod:
                temps = psutil_mod.sensors_temperatures(fahrenheit=False)
                adaylar = []
                for ad, liste in (temps or {}).items():
                    for item in liste:
                        cur = getattr(item, "current", None)
                        if cur is not None and 0 < cur < 130:
                            adaylar.append(float(cur))
                if adaylar:
                    return max(adaylar)
        except Exception:
            pass

        yollar = []
        for kok in ("/sys/class/thermal", "/sys/class/hwmon"):
            try:
                for root, _, files in os.walk(kok):
                    for ad in files:
                        if ad == "temp" or (ad.startswith("temp") and ad.endswith("_input")):
                            yollar.append(os.path.join(root, ad))
            except Exception:
                continue
        degerler = []
        for yol in yollar:
            try:
                with open(yol, "r", encoding="utf-8") as f:
                    ham = f.read().strip()
                if not ham:
                    continue
                val = float(ham)
                if val > 1000:
                    val /= 1000.0
                if 0 < val < 130:
                    degerler.append(val)
            except Exception:
                continue
        return max(degerler) if degerler else None

    def _sysfs_pil(self):
        try:
            bat_kok = "/sys/class/power_supply"
            for ad in os.listdir(bat_kok):
                if not ad.upper().startswith("BAT"):
                    continue
                yol = os.path.join(bat_kok, ad, "capacity")
                if os.path.exists(yol):
                    with open(yol, "r", encoding="utf-8") as f:
                        return int(f.read().strip())
        except Exception:
            pass
        return None

    @staticmethod
    def _boyut_yaz(byte: float) -> str:
        deger = float(byte or 0)
        for birim in ("B", "KB", "MB", "GB", "TB"):
            if deger < 1024 or birim == "TB":
                return f"{deger:.1f} {birim}" if birim != "B" else f"{int(deger)} B"
            deger /= 1024
        return f"{deger:.1f} TB"

    def _hiz_yaz(self, byte_s: float) -> str:
        return self._boyut_yaz(byte_s)

    @staticmethod
    def _sure_yaz(saniye: float) -> str:
        saniye = int(max(0, saniye))
        gun, kalan = divmod(saniye, 86400)
        saat, kalan = divmod(kalan, 3600)
        dakika, _ = divmod(kalan, 60)
        if gun:
            return f"{gun}g {saat}sa"
        if saat:
            return f"{saat}sa {dakika}dk"
        return f"{dakika}dk"

    def _dash_uzuv_guncelle(self):
        if not self.cekirdek:
            if hasattr(self, "dash_uzuv_ozet_lbl"):
                self.dash_uzuv_ozet_lbl.setText("0 bağlı")
            return
        toplam = len(self.cekirdek.uzuv.uzuvlar)
        bagli = 0
        sorunlu = 0
        if hasattr(self, "dash_uzuv_tablo"):
            self.dash_uzuv_tablo.clear()
        for uid, uzuv in self.cekirdek.uzuv.uzuvlar.items():
            _d = str(uzuv.durum).lower()
            if "bagl" in _d and "degil" not in _d:
                bagli += 1
            if "hata" in _d or "cevrimdisi" in _d:
                sorunlu += 1
            if not hasattr(self, "dash_uzuv_tablo"):
                continue
            durum_renk = (R["yesil"] if "bagl" in _d and "degil" not in _d
                         else R["sari"] if "bekliy" in _d or "baglaniyor" in _d
                         else R["kirmizi"] if "hata" in _d or "cevrimdisi" in _d
                         else R["metin3"])
            item = QTreeWidgetItem([
                f"{uzuv.simge} {uzuv.ad}",
                str(uzuv.tip),
                uzuv.baglanti_ozeti() if hasattr(uzuv, "baglanti_ozeti") else str(uzuv.yontem.value if hasattr(uzuv.yontem, "value") else uzuv.yontem),
                uzuv.durum,
                self.cekirdek.uzuv.onion_host or "—",
            ])
            item.setForeground(3, QColor(durum_renk))
            self.dash_uzuv_tablo.addTopLevelItem(item)
        if hasattr(self, "dash_uzuv_ozet_lbl"):
            self.dash_uzuv_ozet_lbl.setText(f"{bagli}/{toplam} bağlı")
            renk = R["yesil"] if toplam and bagli == toplam else (R["sari"] if toplam else R["metin2"])
            if sorunlu:
                renk = R["kirmizi"]
            self.dash_uzuv_ozet_lbl.setStyleSheet(
                f"color:{renk};font-size:18px;font-weight:bold;"
            )

    def _dash_tum_ping(self):
        if not self.cekirdek:
            return
        for uid in self.cekirdek.uzuv.uzuvlar:
            self.cekirdek.uzuv.ping_arkaplanda(uid)
        if hasattr(self, "dash_uzuv_ozet_lbl"):
            self.dash_uzuv_ozet_lbl.setText("Yoklanıyor")
        if hasattr(self, "dash_cikti"):
            self.dash_cikti.append("◎ Tüm uzuvlar ping'leniyor...")
        self.statusBar().showMessage("Tüm uzuvlar yoklanıyor...")

    def _dash_hizli_calistir(self, cmd: str):
        import subprocess, threading
        def _calistir():
            try:
                r = subprocess.run(
                    cmd, shell=True, capture_output=True,
                    text=True, timeout=10)
                cikti = (r.stdout + r.stderr).strip()[:500]
                if hasattr(self, "dash_cikti"):
                    self.dash_cikti.append(f"$ {cmd}\n{cikti}\n")
                else:
                    self.statusBar().showMessage(cikti[:140] or "Komut tamamlandı.")
            except Exception as e:
                if hasattr(self, "dash_cikti"):
                    self.dash_cikti.append(f"Hata: {e}\n")
                else:
                    self.statusBar().showMessage(f"Hata: {e}")
        threading.Thread(target=_calistir, daemon=True).start()

    def _ana_sekme(self):
        w = QWidget()
        d = QVBoxLayout(w); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(10)

        d.addWidget(self._dashboard_sekme())

        grp1 = QGroupBox("KONUŞMA GEÇMİŞİ")
        g1 = QVBoxLayout(grp1)
        self.konusma_ekrani = QTextEdit()
        self.konusma_ekrani.setReadOnly(True)
        self.konusma_ekrani.setMinimumHeight(220)
        g1.addWidget(self.konusma_ekrani)
        d.addWidget(grp1, 1)

        grp2 = QGroupBox("MERKEZ KOMUTA")
        g2 = QHBoxLayout(grp2)
        self.komut_girisi = QLineEdit()
        self.komut_girisi.setPlaceholderText(
            "Komut, soru veya uzuv emri yazın... Örn: reader terminal komutu uptime")
        self.komut_girisi.setFixedHeight(38)
        self.komut_girisi.returnPressed.connect(self._klavye_komutu_gonder)
        gonder = QPushButton("GÖNDER")
        gonder.setFixedHeight(38); gonder.setFixedWidth(100)
        gonder.clicked.connect(self._klavye_komutu_gonder)
        g2.addWidget(self.komut_girisi); g2.addWidget(gonder)
        d.addWidget(grp2)

        grp3 = QGroupBox("HIZLI BİLİNÇ DEVRİ")
        g3 = QHBoxLayout(grp3); g3.setSpacing(5)
        for b in TUM_BILINCLER:
            btn = QPushButton(self._goruntu_ad(b))
            btn.setFixedHeight(30)
            btn.setFont(QFont("Courier New", 9))
            btn.clicked.connect(lambda _, bb=b: self._bilinc_degistir(bb))
            g3.addWidget(btn)
        d.addWidget(grp3)
        return w



    # ── Ekran Yayını Metodları ────────────────────────────────────────────────

    def _ekran_mod_degisti(self, idx: int):
        """VNC seçilince ek ayarları göster."""
        self.ekran_vnc_w.setVisible(idx == 1)

    def _ekran_gereksinim_goster(self):
        if not self.cekirdek:
            return
        gerek = self.cekirdek.ekran.gereksinim_kontrol()
        eksik = [ad for ad, var in gerek.items() if not var]
        if eksik:
            self.ekran_gerek_lbl.setText(
                "Eksik: " + ", ".join(eksik) +
                "\nsudo apt install " + " ".join(eksik))
        else:
            self.ekran_gerek_lbl.setText("✓ Tüm bağımlılıklar mevcut")
            self.ekran_gerek_lbl.setStyleSheet(
                f"color:{R['yesil']};font-size:10px;")

    def _ekran_baslat(self):
        if not self.cekirdek:
            return
        item = self.uzuv_agaci.currentItem()
        if not item:
            QMessageBox.warning(self, "Uyarı", "Önce bir uzuv seçin.")
            return

        uid = item.data(0, Qt.ItemDataRole.UserRole)
        uzuv = self.cekirdek.uzuv.uzuvlar.get(uid)
        if not uzuv:
            return

        try:
            from .ekran_yayinci import EkranYayinAyar, YayinMod
        except ImportError:
            from zihin.ekran_yayinci import EkranYayinAyar, YayinMod
        idx = self.ekran_mod_cb.currentIndex()

        if idx == 0:    # scrcpy
            ayar = EkranYayinAyar(
                uzuv_id=uid, uzuv_ad=uzuv.ad,
                mod=YayinMod.SCRCPY,
                host=uzuv.adb_host,
                port=uzuv.adb_port,
                salt_okunur=self.ekran_salt_cb.isChecked(),
                kayit_yap=self.ekran_kayit_cb.isChecked(),
            )
        elif idx == 1:  # VNC
            ayar = EkranYayinAyar(
                uzuv_id=uid, uzuv_ad=uzuv.ad,
                mod=YayinMod.VNC,
                host=self.ekran_vnc_host_e.text().strip() or uzuv.ssh_host,
                port=self.ekran_vnc_port_e.value(),
                sifre=self.ekran_vnc_sifre_e.text(),
                ssh_host=uzuv.ssh_host,
                ssh_port=uzuv.ssh_port,
                ssh_kullanici=uzuv.ssh_kullanici,
                ssh_anahtar=uzuv.ssh_anahtar,
                kullan_tor=self.ekran_tor_cb.isChecked(),
                salt_okunur=self.ekran_salt_cb.isChecked(),
                kayit_yap=self.ekran_kayit_cb.isChecked(),
            )
        else:           # SSH X11
            ayar = EkranYayinAyar(
                uzuv_id=uid, uzuv_ad=uzuv.ad,
                mod=YayinMod.SSH_X11,
                ssh_host=uzuv.ssh_host,
                ssh_port=uzuv.ssh_port,
                ssh_kullanici=uzuv.ssh_kullanici,
                ssh_anahtar=uzuv.ssh_anahtar,
                kullan_tor=self.ekran_tor_cb.isChecked() if hasattr(
                    self, 'ekran_tor_cb') else False,
            )

        ok = self.cekirdek.ekran.baslat(ayar)
        if ok:
            self.ekran_durum_lbl.setText(
                f"🟢 {uzuv.ad} — {ayar.mod.value} aktif")
            self.ekran_durum_lbl.setStyleSheet(
                f"color:{R['yesil']};font-size:10px;")
        else:
            self.ekran_durum_lbl.setText("🔴 Yayın başlatılamadı")
            self.ekran_durum_lbl.setStyleSheet(
                f"color:{R['kirmizi']};font-size:10px;")

    def _ekran_durdur(self):
        if not self.cekirdek:
            return
        item = self.uzuv_agaci.currentItem()
        if item:
            uid = item.data(0, Qt.ItemDataRole.UserRole)
            self.cekirdek.ekran.durdur(uid)
        else:
            self.cekirdek.ekran.tumu_durdur()
        self.ekran_durum_lbl.setText("● Yayın durduruldu")
        self.ekran_durum_lbl.setStyleSheet(
            f"color:{R['metin3']};font-size:10px;")

    def _web_sekme(self):
        w = QWidget()
        kaydir = QScrollArea(); kaydir.setWidgetResizable(True)
        kaydir.setStyleSheet("QScrollArea{border:none;}")
        kap = QWidget()
        d = QVBoxLayout(kap); d.setContentsMargins(16,16,16,16); d.setSpacing(12)

        # Başlık + fabrika butonu
        _fab_row = QHBoxLayout()
        bl = QLabel("WEB & PC TAM KONTROL")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        _fab_row.addWidget(bl); _fab_row.addStretch()
        _fab_row.addWidget(self._fabrika_btn_olustur("WEB"))
        d.addLayout(_fab_row)

        # ── Mod & Ayarlar ─────────────────────────────────────────────────────
        grp_ayar = QGroupBox("AYARLAR")
        gay = QFormLayout(grp_ayar)

        self.web_mod_cb = QComboBox()
        self.web_mod_cb.addItems(["xdotool (hafif)", "playwright (tam)"])
        self.web_mod_cb.currentIndexChanged.connect(self._web_mod_degisti)

        self.web_tarayici_cb = QComboBox()
        self.web_tarayici_cb.addItems(["chromium", "firefox", "webkit"])

        self.web_gorunur_cb = QCheckBox("Tarayıcı görünür (headless değil)")
        self.web_gorunur_cb.setChecked(True)

        self.web_playwright_btn = QPushButton("▶ Playwright Başlat")
        self.web_playwright_btn.clicked.connect(self._web_playwright_baslat)
        self.web_kapat_btn = QPushButton("⏹ Kapat")
        self.web_kapat_btn.clicked.connect(self._web_playwright_kapat)
        self.web_kapat_btn.setObjectName("tehlike")

        self.web_durum_lbl = QLabel("● Playwright: Pasif")
        self.web_durum_lbl.setStyleSheet(f"color:{R['metin3']};font-size:11px;")

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.web_playwright_btn)
        btn_row.addWidget(self.web_kapat_btn)

        gay.addRow("Mod:", self.web_mod_cb)
        gay.addRow("Tarayıcı:", self.web_tarayici_cb)
        gay.addRow("", self.web_gorunur_cb)
        gay.addRow("", btn_row)
        gay.addRow("Durum:", self.web_durum_lbl)
        d.addWidget(grp_ayar)

        # ── URL Bar ───────────────────────────────────────────────────────────
        grp_url = QGroupBox("GEZİNME")
        gurl = QVBoxLayout(grp_url)

        url_row = QHBoxLayout()
        self.web_url_e = QLineEdit()
        self.web_url_e.setPlaceholderText("https://... veya arama terimi")
        self.web_url_e.returnPressed.connect(self._web_git)
        git_btn = QPushButton("▶ Git"); git_btn.setObjectName("aksiyon")
        git_btn.clicked.connect(self._web_git)
        url_row.addWidget(self.web_url_e, 1)
        url_row.addWidget(git_btn)
        gurl.addLayout(url_row)

        nav_row = QHBoxLayout()
        for lbl, fn in [("◀ Geri", self._web_geri),
                         ("▶ İleri", self._web_ileri),
                         ("⟳ Yenile", self._web_yenile),
                         ("+ Sekme", self._web_yeni_sekme)]:
            b = QPushButton(lbl); b.clicked.connect(fn)
            nav_row.addWidget(b)
        gurl.addLayout(nav_row)

        hizli_row = QHBoxLayout()
        for site, url in [("Google", "https://google.com"),
                           ("YouTube", "https://youtube.com"),
                           ("Wikipedia", "https://tr.wikipedia.org"),
                           ("Haber", "https://www.hurriyet.com.tr")]:
            b = QPushButton(site)
            b.clicked.connect(lambda _, u=url: self._web_git_url(u))
            b.setFixedHeight(28)
            hizli_row.addWidget(b)
        gurl.addLayout(hizli_row)
        d.addWidget(grp_url)

        # ── İşlemler ──────────────────────────────────────────────────────────
        grp_islem = QGroupBox("İŞLEMLER")
        gis = QVBoxLayout(grp_islem)

        # Tıklama
        tikla_row = QHBoxLayout()
        self.web_tikla_e = QLineEdit()
        self.web_tikla_e.setPlaceholderText("Tıklanacak metin veya selector")
        tikla_btn = QPushButton("Tıkla")
        tikla_btn.clicked.connect(self._web_tikla)
        tikla_row.addWidget(QLabel("Tıkla:")); tikla_row.addWidget(self.web_tikla_e, 1)
        tikla_row.addWidget(tikla_btn)
        gis.addLayout(tikla_row)

        # Yazma
        yaz_row = QHBoxLayout()
        self.web_yaz_e = QLineEdit()
        self.web_yaz_e.setPlaceholderText("Yazılacak metin")
        yaz_btn = QPushButton("Yaz")
        yaz_btn.clicked.connect(self._web_yaz)
        yaz_row.addWidget(QLabel("Yaz:")); yaz_row.addWidget(self.web_yaz_e, 1)
        yaz_row.addWidget(yaz_btn)
        gis.addLayout(yaz_row)

        # Kaydırma
        kaydir_row = QHBoxLayout()
        asagi_btn = QPushButton("↓ Aşağı"); asagi_btn.clicked.connect(
            lambda: self._web_kaydir("asagi"))
        yukari_btn = QPushButton("↑ Yukarı"); yukari_btn.clicked.connect(
            lambda: self._web_kaydir("yukari"))
        gonder_btn = QPushButton("⏎ Gönder"); gonder_btn.setObjectName("aksiyon")
        gonder_btn.clicked.connect(self._web_gonder)
        kaydir_row.addWidget(asagi_btn); kaydir_row.addWidget(yukari_btn)
        kaydir_row.addStretch(); kaydir_row.addWidget(gonder_btn)
        gis.addLayout(kaydir_row)
        d.addWidget(grp_islem)

        # ── Haber & Metin ─────────────────────────────────────────────────────
        grp_metin = QGroupBox("HABER OKU / OCR")
        gmt = QVBoxLayout(grp_metin)
        metin_btn_row = QHBoxLayout()
        haber_btn = QPushButton("📰 Haberi Sesli Oku")
        haber_btn.clicked.connect(self._web_haber_oku)
        ocr_btn = QPushButton("🔍 Ekranı OCR ile Oku")
        ocr_btn.clicked.connect(self._web_ocr)
        metin_btn_row.addWidget(haber_btn); metin_btn_row.addWidget(ocr_btn)
        gmt.addLayout(metin_btn_row)

        self.web_metin_ekrani = QTextEdit()
        self.web_metin_ekrani.setReadOnly(True)
        self.web_metin_ekrani.setMinimumHeight(120)
        self.web_metin_ekrani.setFont(QFont("Courier New", 10))
        gmt.addWidget(self.web_metin_ekrani)
        d.addWidget(grp_metin)

        # ── Fare & Klavye ─────────────────────────────────────────────────────
        grp_hid = QGroupBox("FARE & KLAVYE (PC TAM KONTROL)")
        ghid = QFormLayout(grp_hid)

        fare_row = QHBoxLayout()
        self.web_fare_x = QSpinBox(); self.web_fare_x.setRange(0, 9999)
        self.web_fare_y = QSpinBox(); self.web_fare_y.setRange(0, 9999)
        fare_tasi_btn = QPushButton("Taşı")
        fare_tasi_btn.clicked.connect(self._web_fare_tasi)
        fare_tikla_btn = QPushButton("Tıkla")
        fare_tikla_btn.clicked.connect(self._web_fare_tikla)
        fare_row.addWidget(QLabel("X:")); fare_row.addWidget(self.web_fare_x)
        fare_row.addWidget(QLabel("Y:")); fare_row.addWidget(self.web_fare_y)
        fare_row.addWidget(fare_tasi_btn); fare_row.addWidget(fare_tikla_btn)

        self.web_tus_e = QLineEdit()
        self.web_tus_e.setPlaceholderText("ctrl+c, alt+F4, Return, super...")
        tus_btn = QPushButton("Gönder")
        tus_btn.clicked.connect(self._web_tus_gonder)
        tus_row = QHBoxLayout()
        tus_row.addWidget(self.web_tus_e, 1); tus_row.addWidget(tus_btn)

        ghid.addRow("Fare:", fare_row)
        ghid.addRow("Tuş:", tus_row)
        d.addWidget(grp_hid)

        d.addStretch()
        kaydir.setWidget(kap)
        ana = QVBoxLayout(w); ana.setContentsMargins(0,0,0,0)
        ana.addWidget(kaydir)
        return w

    def _web_mod_degisti(self, idx):
        if not self.cekirdek: return
        mod = "playwright" if idx == 1 else "xdotool"
        self.cekirdek.web.mod_ayarla(mod)

    def _web_playwright_baslat(self):
        if not self.cekirdek: return
        self.cekirdek.web.gorunurluk_ayarla(self.web_gorunur_cb.isChecked())
        self.cekirdek.web.tarayici_ayarla(self.web_tarayici_cb.currentText())
        ok = self.cekirdek.web.baslat()
        durum = "✓ Aktif" if ok else "✗ Başlatılamadı"
        renk = R["yesil"] if ok else R["kirmizi"]
        self.web_durum_lbl.setText(f"● Playwright: {durum}")
        self.web_durum_lbl.setStyleSheet(f"color:{renk};font-size:11px;")

    def _web_playwright_kapat(self):
        if self.cekirdek:
            self.cekirdek.web.kapat()
        self.web_durum_lbl.setText("● Playwright: Pasif")
        self.web_durum_lbl.setStyleSheet(f"color:{R['metin3']};font-size:11px;")

    def _web_git(self):
        if not self.cekirdek: return
        url = self.web_url_e.text().strip()
        if url:
            sonuc = self.cekirdek.web.git(url)
            self.web_metin_ekrani.append(sonuc)

    def _web_git_url(self, url):
        if self.cekirdek:
            self.web_url_e.setText(url)
            self.cekirdek.web.git(url)

    def _web_geri(self):
        if self.cekirdek: self.web_metin_ekrani.append(self.cekirdek.web.geri_git())
    def _web_ileri(self):
        if self.cekirdek: self.web_metin_ekrani.append(self.cekirdek.web.ileri_git())
    def _web_yenile(self):
        if self.cekirdek: self.web_metin_ekrani.append(self.cekirdek.web.yenile())
    def _web_yeni_sekme(self):
        if self.cekirdek: self.web_metin_ekrani.append(self.cekirdek.web.yeni_sekme())

    def _web_tikla(self):
        if not self.cekirdek: return
        hedef = self.web_tikla_e.text().strip()
        if hedef:
            self.web_metin_ekrani.append(self.cekirdek.web.tikla(hedef))

    def _web_yaz(self):
        if not self.cekirdek: return
        metin = self.web_yaz_e.text().strip()
        if metin:
            self.web_metin_ekrani.append(self.cekirdek.web.yaz(metin))

    def _web_kaydir(self, yon):
        if self.cekirdek:
            self.cekirdek.web.kaydır(yon)

    def _web_gonder(self):
        if self.cekirdek:
            self.web_metin_ekrani.append(self.cekirdek.web.gonder())

    def _web_haber_oku(self):
        if not self.cekirdek: return
        self.web_metin_ekrani.append("📰 Haber okunuyor...")
        def _oku():
            sonuc = self.cekirdek.web.haber_oku()
            self.web_metin_ekrani.append(sonuc[:500])
        threading.Thread(target=_oku, daemon=True).start()

    def _web_ocr(self):
        if not self.cekirdek: return
        self.web_metin_ekrani.append("🔍 OCR çalışıyor...")
        def _ocr():
            sonuc = self.cekirdek.web.ekran_oku()
            self.web_metin_ekrani.append(sonuc[:500])
        threading.Thread(target=_ocr, daemon=True).start()

    def _web_fare_tasi(self):
        if not self.cekirdek: return
        x, y = self.web_fare_x.value(), self.web_fare_y.value()
        self.cekirdek.web.fare_tasi(x, y)

    def _web_fare_tikla(self):
        if not self.cekirdek: return
        x, y = self.web_fare_x.value(), self.web_fare_y.value()
        self.cekirdek.web.fare_tikla(x, y)

    def _web_tus_gonder(self):
        if not self.cekirdek: return
        tus = self.web_tus_e.text().strip()
        if tus:
            self.web_metin_ekrani.append(self.cekirdek.web.klavye_bas(tus))

    def _fabrika_web(self):
        if not self.cekirdek: return
        self.cekirdek.web.kapat()
        self.web_mod_cb.setCurrentIndex(0)
        self.web_gorunur_cb.setChecked(True)
        self.web_durum_lbl.setText("● Playwright: Pasif")

    # ── Uzuv Sekmesi ─────────────────────────────────────────────────────────

    def _uzuv_sekme(self):
        w = QWidget()
        d = QVBoxLayout(w); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(10)

        ust = QHBoxLayout()
        bl = QLabel("UZUVLAR")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        ust.addWidget(bl); ust.addStretch()
        ekle_btn = QPushButton("+ Uzuv Ekle")
        ekle_btn.clicked.connect(self._uzuv_ekle)
        ust.addWidget(ekle_btn)
        d.addLayout(ust)

        altyapi_bilgi = QLabel(
            "Merkez erişimi otomatik yönetilir. Setup paketleri gerekli adresleri kendisi alır.\n"
            "Sadece istisnai durumlarda gelişmiş merkez ayarlarını açmanız gerekir."
        )
        altyapi_bilgi.setWordWrap(True)
        altyapi_bilgi.setStyleSheet(f"color:{R['metin3']};font-size:10px;")
        d.addWidget(altyapi_bilgi)

        self.merkez_ozet_lbl = QLabel("Merkez erişimi hazırlanıyor...")
        self.merkez_ozet_lbl.setWordWrap(True)
        self.merkez_ozet_lbl.setStyleSheet(f"color:{R['vurgu']};font-size:10px;")
        d.addWidget(self.merkez_ozet_lbl)

        self.merkez_gelismis_cb = QCheckBox("Gelişmiş merkez ayarlarını göster")
        d.addWidget(self.merkez_gelismis_cb)

        # Merkez erişim profilleri
        onion_grp = QGroupBox("MERKEZ ALTYAPISI / GELİŞMİŞ")
        of = QFormLayout(onion_grp)
        self.merkez_local_host_e = QLineEdit()
        self.merkez_local_host_e.setPlaceholderText("192.168.1.50")
        self.merkez_local_port_e = QSpinBox()
        self.merkez_local_port_e.setRange(1, 65535); self.merkez_local_port_e.setValue(22)
        self.merkez_clearnet_host_e = QLineEdit()
        self.merkez_clearnet_host_e.setPlaceholderText("sunucu.ornek.com")
        self.merkez_clearnet_port_e = QSpinBox()
        self.merkez_clearnet_port_e.setRange(1, 65535); self.merkez_clearnet_port_e.setValue(22)
        self.onion_host_e = QLineEdit()
        self.onion_host_e.setPlaceholderText("abc123.onion")
        self.onion_port_e = QSpinBox()
        self.onion_port_e.setRange(1, 65535); self.onion_port_e.setValue(22)
        self.onion_user_e = QLineEdit(); self.onion_user_e.setText("zihin")
        self.merkez_tg_host_e = QLineEdit()
        self.merkez_tg_host_e.setPlaceholderText("chat id / ajan chat")
        self.onion_bildirim_e = QLineEdit()
        self.onion_bildirim_e.setPlaceholderText("https://sunucu.ornek.com/uzuv_bildir (opsiyonel)")
        btn_row = QHBoxLayout()
        onion_kaydet = QPushButton("💾 Kaydet")
        onion_kaydet.clicked.connect(self._onion_kaydet)
        self.onion_oto_btn = QPushButton("🔄 Tor'dan Otomatik Al")
        self.onion_oto_btn.setToolTip(
            "Tor çalışıyorsa hidden service adresini otomatik okur ve doldurur.")
        self.onion_oto_btn.clicked.connect(self._onion_otomatik_al)
        btn_row.addWidget(self.onion_oto_btn)
        btn_row.addWidget(onion_kaydet)

        # Onion durum etiketi
        self.onion_durum_lbl = QLabel("")
        self.onion_durum_lbl.setStyleSheet(f"color:{R['yesil']};font-size:10px;")

        of.addRow("Yerel IP:", self.merkez_local_host_e)
        of.addRow("Yerel Port:", self.merkez_local_port_e)
        of.addRow("Clearnet Host:", self.merkez_clearnet_host_e)
        of.addRow("Clearnet Port:", self.merkez_clearnet_port_e)
        of.addRow("Tor Hidden Service:", self.onion_host_e)
        of.addRow("Tor Port:", self.onion_port_e)
        of.addRow("SSH Kullanıcı:", self.onion_user_e)
        of.addRow("Telegram Hedef:", self.merkez_tg_host_e)
        of.addRow("Kayıt Bildirim URL:", self.onion_bildirim_e)
        of.addRow("", self.onion_durum_lbl)
        of.addRow("", btn_row)
        d.addWidget(onion_grp)
        self.merkez_gelismis_cb.toggled.connect(onion_grp.setVisible)
        onion_grp.setVisible(False)
        if self.cekirdek:
            self._merkez_erisim_gui_yukle()
            # Onion hazır olayını dinle
            self.cekirdek.olay_dinleyici_ekle(self._onion_olay_isle)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        sol = QWidget()
        sol_d = QVBoxLayout(sol); sol_d.setContentsMargins(0, 0, 0, 0)
        self.uzuv_agaci = QTreeWidget()
        self.uzuv_agaci.setHeaderLabels(["Uzuv", "Takma", "Tip", "Durum"])
        self.uzuv_agaci.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.uzuv_agaci.setColumnWidth(1, 75)
        self.uzuv_agaci.setColumnWidth(2, 70)
        self.uzuv_agaci.setColumnWidth(3, 80)
        # Ctrl+tık ile çoklu seçim
        self.uzuv_agaci.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection)
        self.uzuv_agaci.itemSelectionChanged.connect(self._uzuv_secildi)
        sol_d.addWidget(self.uzuv_agaci)
        alt_btns = QHBoxLayout()
        for lbl, fn in [("◎ Ping", self._uzuv_ping),
                        ("✏ Düzenle", self._uzuv_duzenle),
                        ("✕ Sil", self._uzuv_sil)]:
            btn = QPushButton(lbl)
            if "Sil" in lbl: btn.setObjectName("tehlike")
            btn.clicked.connect(fn)
            alt_btns.addWidget(btn)
        sol_d.addLayout(alt_btns)
        splitter.addWidget(sol)

        sag = QWidget()
        sag_d = QVBoxLayout(sag); sag_d.setContentsMargins(8, 0, 0, 0)
        self.uzuv_bilgi = QLabel("Bir uzuv seçin.")
        self.uzuv_bilgi.setWordWrap(True)
        self.uzuv_bilgi.setStyleSheet(f"color:{R['metin2']};padding:8px;")
        sag_d.addWidget(self.uzuv_bilgi)

        grp_t = QGroupBox("UZUV KOMUTA")
        gt = QVBoxLayout(grp_t)
        self.uzuv_cikti = QTextEdit()
        self.uzuv_cikti.setReadOnly(True)
        self.uzuv_cikti.setFont(QFont("Courier New", 11))
        self.uzuv_cikti.setMinimumHeight(150)
        gt.addWidget(self.uzuv_cikti)

        # Hedef seçim satırı
        hedef_row = QHBoxLayout()
        hedef_lbl = QLabel("Hedef:")
        hedef_lbl.setStyleSheet(f"color:{R['metin2']};font-size:11px;")
        self.uzuv_hedef_cb = QComboBox()
        self.uzuv_hedef_cb.addItem("🎯 Seçili Uzuv", "secili")
        self.uzuv_hedef_cb.addItem("✅ Seçtiklerim", "secili_cok")
        self.uzuv_hedef_cb.addItem("📡 Tüm Uzuvlar", "tumu")
        self.uzuv_hedef_cb.setToolTip(
            "Seçili: ağaçta seçili tek uzuv\n"
            "Seçtiklerim: Ctrl+tık ile işaretledikleriniz\n"
            "Tümü: tüm kayıtlı uzuvlar")
        hedef_row.addWidget(hedef_lbl)
        hedef_row.addWidget(self.uzuv_hedef_cb, 1)
        gt.addLayout(hedef_row)

        mod_row = QHBoxLayout()
        mod_lbl = QLabel("Mod:")
        mod_lbl.setStyleSheet(f"color:{R['metin2']};font-size:11px;")
        self.uzuv_cmd_mod_cb = QComboBox()
        self.uzuv_cmd_mod_cb.addItem("🧠 Akıllı Komut", "akilli")
        self.uzuv_cmd_mod_cb.addItem("💻 Terminal", "terminal")
        self.uzuv_cmd_mod_cb.addItem("🪟 CMD", "cmd")
        self.uzuv_cmd_mod_cb.addItem("⚡ PowerShell", "powershell")
        self.uzuv_cmd_mod_cb.addItem("🤖 ADB Shell", "adb")
        self.uzuv_cmd_mod_cb.currentIndexChanged.connect(self._uzuv_komut_mod_degisti)
        mod_row.addWidget(mod_lbl)
        mod_row.addWidget(self.uzuv_cmd_mod_cb, 1)
        gt.addLayout(mod_row)

        cmd_row = QHBoxLayout()
        self.uzuv_cmd_e = QLineEdit()
        self.uzuv_cmd_e.setPlaceholderText("Komut girin... (Enter ile gönder)")
        self.uzuv_cmd_e.returnPressed.connect(self._uzuv_komut_gonder)
        cmd_gonder = QPushButton("▶ Gönder")
        cmd_gonder.setFixedWidth(90)
        cmd_gonder.setObjectName("aksiyon")
        cmd_gonder.clicked.connect(self._uzuv_komut_gonder)
        cmd_temizle = QPushButton("🗑")
        cmd_temizle.setFixedWidth(32)
        cmd_temizle.setToolTip("Çıktıyı temizle")
        cmd_temizle.clicked.connect(self.uzuv_cikti.clear)
        cmd_row.addWidget(self.uzuv_cmd_e)
        cmd_row.addWidget(cmd_gonder)
        cmd_row.addWidget(cmd_temizle)
        gt.addLayout(cmd_row)
        self._uzuv_komut_mod_degisti(0)
        sag_d.addWidget(grp_t)

        # Gelişmiş istemci üreteci
        grp_is = QGroupBox("MEVCUT UZUV İÇİN YENİDEN SETUP ÜRET")
        gis = QFormLayout(grp_is)

        # Merkez bağlantı yöntemi
        self.istemci_baglanti_cb = QComboBox()
        self.istemci_baglanti_cb.addItem("🔁 Merkeze SSH Ters Tünel", "ssh_reverse")
        self.istemci_baglanti_cb.addItem("🧅 Tor HTTP Ajan", "tor_http")
        self.istemci_baglanti_cb.addItem("🔒 Tor HTTPS Ajan", "tor_https")
        self.istemci_baglanti_cb.addItem("✈ Telegram Ajan", "telegram_agent")
        self.istemci_baglanti_cb.currentIndexChanged.connect(
            self._istemci_baglanti_degisti)
        self.istemci_merkez_lbl = QLabel("Seçilen bağlantı tipine göre merkez erişim otomatik gömülecek.")
        self.istemci_merkez_lbl.setWordWrap(True)
        self.istemci_merkez_lbl.setStyleSheet(f"color:{R['metin3']};font-size:10px;")

        self.istemci_tg_w = QWidget()
        tg_form = QFormLayout(self.istemci_tg_w)
        tg_form.setContentsMargins(0, 0, 0, 0)
        self.istemci_tg_api_id_e = QLineEdit()
        self.istemci_tg_api_hash_e = QLineEdit()
        self.istemci_tg_api_hash_e.setEchoMode(QLineEdit.EchoMode.Password)
        self.istemci_tg_session_e = QLineEdit()
        self.istemci_tg_chat_e = QLineEdit()
        self.istemci_tg_api_id_e.setPlaceholderText("Telegram sekmesinden gelir")
        self.istemci_tg_api_hash_e.setPlaceholderText("Telegram sekmesinden gelir")
        self.istemci_tg_session_e.setPlaceholderText("zk_limb")
        self.istemci_tg_chat_e.setPlaceholderText("chat id / kullanici adi")
        tg_form.addRow("API ID:", self.istemci_tg_api_id_e)
        tg_form.addRow("API Hash:", self.istemci_tg_api_hash_e)
        tg_form.addRow("Session:", self.istemci_tg_session_e)
        tg_form.addRow("Chat:", self.istemci_tg_chat_e)
        self.istemci_tg_w.setVisible(False)

        # Platform seçimi
        self.istemci_platform_cb = QComboBox()
        self.istemci_platform_cb.addItem("🐧 Bilgisayar / Linux-Mac", "linux")
        self.istemci_platform_cb.addItem("🪟 Bilgisayar / Windows", "windows")
        self.istemci_platform_cb.addItem("🤖 Telefon / Android (Termux)", "android_termux")
        self.istemci_platform_cb.addItem("📱 Telefon / Android APK", "android_apk")
        self.istemci_platform_cb.currentIndexChanged.connect(
            self._istemci_platform_degisti)

        # Windows format seçimi (sadece Windows seçilince görünür)
        self.istemci_win_fmt_cb = QComboBox()
        self.istemci_win_fmt_cb.addItems([
            "🐍 Python + .bat",
            "📜 Yalnızca .bat (PowerShell)",
            "⚙ C++ (kaynak + cmake)",
        ])
        self.istemci_win_fmt_w = QWidget()
        win_fmt_row = QHBoxLayout(self.istemci_win_fmt_w)
        win_fmt_row.setContentsMargins(0,0,0,0)
        win_fmt_row.addWidget(QLabel("Format:"))
        win_fmt_row.addWidget(self.istemci_win_fmt_cb, 1)
        self.istemci_win_fmt_w.setVisible(False)

        # Android format seçimi
        self.istemci_and_fmt_cb = QComboBox()
        self.istemci_and_fmt_cb.addItems([
            "📦 Termux (sh + py)",
            "📱 APK — Buildozer (uzun sürer)",
        ])
        self.istemci_and_fmt_w = QWidget()
        and_fmt_row = QHBoxLayout(self.istemci_and_fmt_w)
        and_fmt_row.setContentsMargins(0,0,0,0)
        and_fmt_row.addWidget(QLabel("Format:"))
        and_fmt_row.addWidget(self.istemci_and_fmt_cb, 1)
        self.istemci_and_fmt_w.setVisible(False)

        self.istemci_sessiz_cb = QCheckBox("Sessiz mod")
        self.istemci_otobaslat_cb = QCheckBox("Cihaz açılışında otomatik başlat")
        self.istemci_otobaslat_cb.setChecked(True)
        self.istemci_ses_cb = QCheckBox("Mikrofon sesini sunucuya aktar")
        self.istemci_derle_cb = QCheckBox("Gerçek APK/EXE derle")
        self.istemci_derle_cb.setChecked(True)

        # APK/EXE notu
        uret_not = QLabel(
            "ℹ Burada teknik ağ bilgisi girmezsiniz.\n"
            "Sadece bağlantı yöntemi ve hangi tip setup üretileceğini seçersiniz.\n"
            "APK/EXE derleme internet ve işlemci kullanır; başarısız olursa kaynak proje yedek olarak kalır.\n"
            "Yeni uzuvlar için asıl yol: 'Uzuv Ekle' sihirbazı. Bu alan mevcut uzuv için yeniden paket üretir.")
        uret_not.setWordWrap(True)
        uret_not.setStyleSheet(f"color:{R['metin3']};font-size:10px;")
        gis.addRow("", uret_not)

        self.istemci_durum_lbl = QLabel("Hazır")
        self.istemci_durum_lbl.setStyleSheet(f"color:{R['metin3']};font-size:10px;")
        self.istemci_sonuc_e = QTextEdit()
        self.istemci_sonuc_e.setReadOnly(True)
        self.istemci_sonuc_e.setMaximumHeight(120)
        self.istemci_sonuc_e.setPlaceholderText("Üretilen setup dosyaları burada görünecek...")
        self.istemci_uret_btn = QPushButton("⬇ Setup Oluştur")
        self.istemci_uret_btn.setObjectName("aksiyon")
        self.istemci_uret_btn.clicked.connect(self._istemci_uret)

        sihirbaz_lbl = QLabel(
            "1. Bağlantı yöntemini seçin  2. Hedef cihazı seçin  3. Setup paketini üretin"
        )
        sihirbaz_lbl.setWordWrap(True)
        sihirbaz_lbl.setStyleSheet(f"color:{R['vurgu']};font-size:11px;")
        gis.addRow("", sihirbaz_lbl)
        gis.addRow("Bağlantı Yöntemi:", self.istemci_baglanti_cb)
        gis.addRow("Merkez Erişim:", self.istemci_merkez_lbl)
        gis.addRow("", self.istemci_tg_w)
        gis.addRow("Hedef Cihaz:", self.istemci_platform_cb)
        gis.addRow("", self.istemci_win_fmt_w)
        gis.addRow("", self.istemci_and_fmt_w)
        gis.addRow("", self.istemci_derle_cb)
        gis.addRow("", self.istemci_sessiz_cb)
        gis.addRow("", self.istemci_otobaslat_cb)
        gis.addRow("", self.istemci_ses_cb)
        gis.addRow("Durum:", self.istemci_durum_lbl)
        gis.addRow("Çıktılar:", self.istemci_sonuc_e)
        gis.addRow("", self.istemci_uret_btn)
        sag_d.addWidget(grp_is)
        self._istemci_baglanti_degisti(0)
        self._istemci_platform_degisti(0)

        # ── Ekran Yayını ──────────────────────────────────────────────────────
        grp_ekran = QGroupBox("📺 EKRAN YAYINI")
        gek = QVBoxLayout(grp_ekran)

        mod_row = QHBoxLayout()
        self.ekran_mod_cb = QComboBox()
        self.ekran_mod_cb.addItems([
            "📱 scrcpy (Android)",
            "🖥 VNC (Linux/Windows)",
            "🔀 SSH X11 Forwarding",
        ])
        self.ekran_mod_cb.currentIndexChanged.connect(
            self._ekran_mod_degisti)
        mod_row.addWidget(QLabel("Mod:")); mod_row.addWidget(self.ekran_mod_cb, 1)
        gek.addLayout(mod_row)

        # VNC ayarları (sadece VNC seçince görünür)
        self.ekran_vnc_w = QWidget()
        vnc_lay = QFormLayout(self.ekran_vnc_w)
        self.ekran_vnc_host_e = QLineEdit()
        self.ekran_vnc_host_e.setPlaceholderText("192.168.1.x veya onion.onion")
        self.ekran_vnc_port_e = QSpinBox()
        self.ekran_vnc_port_e.setRange(1, 65535)
        self.ekran_vnc_port_e.setValue(5900)
        self.ekran_vnc_sifre_e = QLineEdit()
        self.ekran_vnc_sifre_e.setEchoMode(QLineEdit.EchoMode.Password)
        self.ekran_vnc_sifre_e.setPlaceholderText("VNC şifresi")
        self.ekran_tor_cb = QCheckBox("Tor üzerinden bağlan")
        vnc_lay.addRow("Host:", self.ekran_vnc_host_e)
        vnc_lay.addRow("Port:", self.ekran_vnc_port_e)
        vnc_lay.addRow("Şifre:", self.ekran_vnc_sifre_e)
        vnc_lay.addRow("", self.ekran_tor_cb)
        self.ekran_vnc_w.setVisible(False)
        gek.addWidget(self.ekran_vnc_w)

        # Ortak seçenekler
        opt_row = QHBoxLayout()
        self.ekran_salt_cb = QCheckBox("Salt okunur (sadece izle)")
        self.ekran_kayit_cb = QCheckBox("Kaydet")
        opt_row.addWidget(self.ekran_salt_cb)
        opt_row.addWidget(self.ekran_kayit_cb)
        gek.addLayout(opt_row)

        # Başlat / Durdur butonları
        btn_ekran_row = QHBoxLayout()
        self.ekran_baslat_btn = QPushButton("▶ Yayını Başlat")
        self.ekran_baslat_btn.setObjectName("aksiyon")
        self.ekran_baslat_btn.clicked.connect(self._ekran_baslat)
        self.ekran_durdur_btn = QPushButton("⏹ Durdur")
        self.ekran_durdur_btn.setObjectName("tehlike")
        self.ekran_durdur_btn.clicked.connect(self._ekran_durdur)
        btn_ekran_row.addWidget(self.ekran_baslat_btn)
        btn_ekran_row.addWidget(self.ekran_durdur_btn)
        gek.addLayout(btn_ekran_row)

        self.ekran_durum_lbl = QLabel("● Yayın yok")
        self.ekran_durum_lbl.setStyleSheet(
            f"color:{R['metin3']};font-size:10px;")
        gek.addWidget(self.ekran_durum_lbl)

        # Gereksinim kontrolü
        self.ekran_gerek_lbl = QLabel("")
        self.ekran_gerek_lbl.setStyleSheet(
            f"color:{R['sari']};font-size:10px;")
        self.ekran_gerek_lbl.setWordWrap(True)
        gek.addWidget(self.ekran_gerek_lbl)
        self._ekran_gereksinim_goster()

        sag_d.addWidget(grp_ekran)
        sag_d.addStretch()

        # Sag paneli kaydırılabilir yap — içerik kesilmesin
        sag_kaydir = QScrollArea()
        sag_kaydir.setWidgetResizable(True)
        sag_kaydir.setStyleSheet("QScrollArea{border:none;}")
        sag_kaydir.setWidget(sag)
        splitter.addWidget(sag_kaydir)
        splitter.setSizes([380, 540])
        d.addWidget(splitter, 1)
        self._uzuv_agaci_yenile()
        return w

    # ── Komut Sekmesi ─────────────────────────────────────────────────────────

    def _komut_sekme(self):
        w = QWidget()
        d = QVBoxLayout(w); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(10)
        ust = QHBoxLayout()
        bl = QLabel("KOMUT VERİTABANI")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        ust.addWidget(bl); ust.addStretch()
        for lbl, fn in [("⬆ İçeri", self._komut_iceri),
                        ("⬇ Dışa", self._komut_disari),
                        ("+ Ekle", self._komut_ekle)]:
            btn = QPushButton(lbl); btn.clicked.connect(fn)
            ust.addWidget(btn)
        d.addLayout(ust)
        filtre_row = QHBoxLayout()
        self.komut_filtre_e = QLineEdit()
        self.komut_filtre_e.setPlaceholderText("Ara...")
        self.komut_filtre_e.setFixedHeight(32)
        self.komut_filtre_e.textChanged.connect(self._komut_listele)
        self.komut_os_filtre = QComboBox()
        self.komut_os_filtre.addItems(["Tümü", "linux", "windows", "android", "hepsi"])
        self.komut_os_filtre.currentTextChanged.connect(lambda _: self._komut_listele())
        filtre_row.addWidget(QLabel("Filtre:"))
        filtre_row.addWidget(self.komut_filtre_e)
        filtre_row.addWidget(QLabel("OS:"))
        filtre_row.addWidget(self.komut_os_filtre)
        d.addLayout(filtre_row)
        self.komut_agaci = QTreeWidget()
        self.komut_agaci.setHeaderLabels(["Ad", "Kategori", "OS", "Tür", "Tetik"])
        self.komut_agaci.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Interactive)
        self.komut_agaci.setColumnWidth(0, 200)
        self.komut_agaci.setAlternatingRowColors(True)
        d.addWidget(self.komut_agaci, 1)
        alt = QHBoxLayout()
        self.komut_sayisi_lbl = QLabel("")
        self.komut_sayisi_lbl.setStyleSheet(f"color:{R['metin3']};")
        for lbl, fn in [("⟳ Yenile", self._komut_listele),
                        ("⚙ Çoğalt", self._komut_cogalt),
                        ("✏ Düzenle", self._komut_duzenle),
                        ("✕ Sil", self._komut_sil)]:
            btn = QPushButton(lbl)
            if "Sil" in lbl: btn.setObjectName("tehlike")
            btn.clicked.connect(fn)
            alt.addWidget(btn)
        alt.addStretch(); alt.addWidget(self.komut_sayisi_lbl)
        d.addLayout(alt)
        self._komut_listele()
        return w

    # ── Eklenti Sekmesi ───────────────────────────────────────────────────────

    def _eklenti_sekme(self):
        w = QWidget()
        d = QVBoxLayout(w); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(10)
        ust = QHBoxLayout()
        bl = QLabel("EKLENTİ SLOTLARI")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        ust.addWidget(bl); ust.addStretch()
        d.addLayout(ust)
        kaydir = QScrollArea(); kaydir.setWidgetResizable(True)
        kaydir.setStyleSheet("QScrollArea{border:none;}")
        kap = QWidget(); izgara = QGridLayout(kap)
        izgara.setSpacing(14); izgara.setContentsMargins(6, 6, 6, 6)
        slotlar = (self.cekirdek.eklenti.slotlar if self.cekirdek else
                   {f"slot_{i:02d}": {"ad": f"Slot {i}", "simge": "⚙️",
                                      "klasor": f"/tmp/slot_{i:02d}"}
                    for i in range(1, 11)})
        for sira, (slot_id, ayar) in enumerate(slotlar.items()):
            satir, sutun = divmod(sira, 5)
            kart = self._slot_karti(slot_id, ayar)
            izgara.addWidget(kart, satir, sutun)
            self._slot_kartlari[slot_id] = kart
        izgara.setRowStretch(izgara.rowCount(), 1)
        izgara.setColumnStretch(5, 1)
        kaydir.setWidget(kap); d.addWidget(kaydir, 1)
        alt = QHBoxLayout()
        dur_btn = QPushButton("■ Tümünü Durdur")
        dur_btn.setObjectName("tehlike")
        dur_btn.clicked.connect(self._tum_slotlari_durdur)
        alt.addWidget(dur_btn); alt.addStretch()
        d.addLayout(alt)
        return w

    def _slot_karti(self, slot_id, ayar):
        kart = QFrame(); kart.setFixedSize(195, 155)
        kart.setStyleSheet(
            f"QFrame{{background:{R['panel2']};border:1px solid {R['kenar']};"
            f"border-radius:8px;}}")
        d = QVBoxLayout(kart); d.setContentsMargins(10, 10, 10, 10); d.setSpacing(5)
        ust = QHBoxLayout()
        simge_lbl = QLabel(ayar.get("simge", "⚙️"))
        simge_lbl.setFont(QFont("Segoe UI Emoji", 20))
        simge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        durum_dot = QLabel("●")
        durum_dot.setStyleSheet(f"color:{R['metin3']};")
        durum_dot.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        ust.addWidget(simge_lbl); ust.addStretch(); ust.addWidget(durum_dot)
        d.addLayout(ust)
        ad_lbl = QLabel(ayar.get("ad", slot_id))
        ad_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ad_lbl.setFont(QFont("Courier New", 9)); ad_lbl.setWordWrap(True)
        d.addWidget(ad_lbl)
        bilgi_lbl = QLabel("Boş")
        bilgi_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bilgi_lbl.setFont(QFont("Courier New", 8))
        bilgi_lbl.setStyleSheet(f"color:{R['metin3']};")
        d.addWidget(bilgi_lbl); d.addStretch()
        btn_row = QHBoxLayout(); btn_row.setSpacing(4)
        cal_btn = QPushButton("▶"); cal_btn.setFixedHeight(24)
        cal_btn.setStyleSheet(
            f"QPushButton{{background:{R['panel']};color:{R['yesil']};"
            f"border:1px solid {R['yesil']};border-radius:3px;}}"
            f"QPushButton:hover{{background:{R['yesil']};color:black;}}")
        cal_btn.clicked.connect(lambda _, s=slot_id: self._slot_calistir(s))
        kl_btn = QPushButton("📁"); kl_btn.setFixedSize(24, 24)
        kl_btn.setStyleSheet(
            f"QPushButton{{background:{R['panel']};border:1px solid {R['kenar']};"
            f"border-radius:3px;padding:0;}}")
        kl_btn.clicked.connect(lambda _, s=slot_id: self._slot_klasor_ac(s))
        btn_row.addWidget(cal_btn); btn_row.addWidget(kl_btn)
        d.addLayout(btn_row)
        klasor = ayar.get("klasor", "")
        if os.path.isdir(klasor):
            py_list = [f for f in os.listdir(klasor)
                       if f.endswith(".py") and not f.startswith("_")]
            if py_list:
                bilgi_lbl.setText(py_list[0])
                bilgi_lbl.setStyleSheet(f"color:{R['yesil']};font-size:8px;")
                durum_dot.setStyleSheet(f"color:{R['yesil']};")
        kart._durum_dot = durum_dot; kart._bilgi_lbl = bilgi_lbl
        return kart

    # ── Plugin Sekmesi ────────────────────────────────────────────────────────

    def _plugin_sekme(self):
        w = QWidget()
        d = QVBoxLayout(w); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(10)
        bl = QLabel("PLUGİN MAĞAZASI")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        _fab_row = QHBoxLayout()
        _fab_row.addWidget(bl)
        _fab_row.addStretch()
        _fab_row.addWidget(self._fabrika_btn_olustur('KOMUTLAR'))
        d.addLayout(_fab_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sol: mağaza listesi
        sol = QWidget(); sol_d = QVBoxLayout(sol); sol_d.setContentsMargins(0,0,0,0)
        sol_d.addWidget(QLabel("Uzak Mağaza:"))
        self.plugin_magaza_lst = QListWidget()
        sol_d.addWidget(self.plugin_magaza_lst)
        tara_btn = QPushButton("🔄 Mağazayı Tara")
        tara_btn.clicked.connect(self._plugin_magaza_tara)
        indir_btn = QPushButton("⬇ Seçili Plugini Kur")
        indir_btn.setObjectName("aksiyon")
        indir_btn.clicked.connect(self._plugin_indir)
        sol_d.addWidget(tara_btn); sol_d.addWidget(indir_btn)
        splitter.addWidget(sol)

        # Sağ: kurulu pluginler
        sag = QWidget(); sag_d = QVBoxLayout(sag); sag_d.setContentsMargins(8,0,0,0)
        sag_d.addWidget(QLabel("Kurulu Pluginler:"))
        self.plugin_kurulu_lst = QListWidget()
        sag_d.addWidget(self.plugin_kurulu_lst)
        kaldir_btn = QPushButton("✕ Kaldır")
        kaldir_btn.setObjectName("tehlike")
        kaldir_btn.clicked.connect(self._plugin_kaldir)
        guncelle_btn = QPushButton("⬆ Güncelle")
        guncelle_btn.clicked.connect(self._plugin_guncelle)
        sag_d.addWidget(guncelle_btn); sag_d.addWidget(kaldir_btn)
        splitter.addWidget(sag)
        splitter.setSizes([500, 400])
        d.addWidget(splitter, 1)

        self.plugin_durum_lbl = QLabel("")
        self.plugin_durum_lbl.setStyleSheet(f"color:{R['metin2']};")
        d.addWidget(self.plugin_durum_lbl)
        self._plugin_kurulu_listele()
        return w

    # ── AI Sekmesi ───────────────────────────────────────────────────────────

    def _ai_sekme(self):
        w = QWidget()
        kaydir = QScrollArea(); kaydir.setWidgetResizable(True)
        kaydir.setStyleSheet("QScrollArea{border:none;}")
        kap = QWidget()
        d = QVBoxLayout(kap); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(14)

        grp1 = QGroupBox("AI SAĞLAYICI")
        g1 = QFormLayout(grp1)
        self.ai_saglayici_cb = QComboBox()
        self.ai_saglayici_cb.addItems(
            ["gemini", "openai", "anthropic", "groq", "ollama", "ollama_uzak"])
        self.ai_saglayici_cb.currentTextChanged.connect(self._ai_panel_guncelle)
        self.ai_model_e = QLineEdit()
        self.ai_model_e.setPlaceholderText("Boş = otomatik")
        model_lst_btn = QPushButton("📋 Modelleri Listele")
        model_lst_btn.clicked.connect(self._ai_modelleri_listele)
        g1.addRow("Sağlayıcı:", self.ai_saglayici_cb)
        g1.addRow("Model:", self.ai_model_e)
        g1.addRow("", model_lst_btn)
        d.addWidget(grp1)

        grp2 = QGroupBox("API / BAĞLANTI")
        g2 = QFormLayout(grp2)
        self.ai_anahtar_e = QLineEdit()
        self.ai_anahtar_e.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_anahtar_e.setPlaceholderText("API anahtarı")
        self.ai_url_e = QLineEdit()
        self.ai_url_e.setPlaceholderText("https://api.openai.com")
        self.ai_tor_cb = QCheckBox("Tor proxy kullan")
        self.ai_tor_proxy_e = QLineEdit()
        self.ai_tor_proxy_e.setText("socks5h://127.0.0.1:9050")
        g2.addRow("API Anahtarı:", self.ai_anahtar_e)
        g2.addRow("API URL:", self.ai_url_e)
        g2.addRow("", self.ai_tor_cb)
        g2.addRow("Tor Proxy:", self.ai_tor_proxy_e)
        d.addWidget(grp2)

        grp_yedek = QGroupBox("YEDEK AI PROFİLLERİ")
        gy = QVBoxLayout(grp_yedek)
        bilgi = QLabel(
            "Her satır: sağlayıcı | model | api anahtarı | api url\n"
            "Örnek: openai | gpt-4o-mini | sk-... | https://api.openai.com")
        bilgi.setStyleSheet(f"color:{R['metin3']};font-size:10px;")
        bilgi.setWordWrap(True)
        self.ai_yedekler_e = QTextEdit()
        self.ai_yedekler_e.setPlaceholderText(
            "groq | llama3-8b-8192 | gsk_... |\n"
            "openai | gpt-4o-mini | sk-... | https://api.openai.com\n"
            "ollama | llama3 | | http://localhost:11434")
        self.ai_yedekler_e.setMaximumHeight(105)
        gy.addWidget(bilgi)
        gy.addWidget(self.ai_yedekler_e)
        d.addWidget(grp_yedek)

        self.grp_uzak_ollama = QGroupBox("UZAK OLLAMA (SSH/Tor)")
        g3 = QFormLayout(self.grp_uzak_ollama)
        self.ollama_ssh_host_e = QLineEdit()
        self.ollama_ssh_port_e = QSpinBox()
        self.ollama_ssh_port_e.setRange(1, 65535); self.ollama_ssh_port_e.setValue(22)
        self.ollama_ssh_user_e = QLineEdit()
        self.ollama_ssh_key_e  = QLineEdit()
        self.ollama_port_e     = QSpinBox()
        self.ollama_port_e.setRange(1, 65535); self.ollama_port_e.setValue(11434)
        g3.addRow("SSH Host:", self.ollama_ssh_host_e)
        g3.addRow("SSH Port:", self.ollama_ssh_port_e)
        g3.addRow("Kullanıcı:", self.ollama_ssh_user_e)
        g3.addRow("SSH Anahtar:", self.ollama_ssh_key_e)
        g3.addRow("Ollama Port:", self.ollama_port_e)
        d.addWidget(self.grp_uzak_ollama)

        grp4 = QGroupBox("SİSTEM MESAJI")
        g4 = QVBoxLayout(grp4)
        self.ai_sistem_e = QTextEdit()
        self.ai_sistem_e.setPlainText(
            "Sen Zihin Köprüsü sisteminin asistanısın. "
            "Sahibine hitap adıyla seslenirsin. "
            "Kısa, net Türkçe yanıtlar verirsin.")
        self.ai_sistem_e.setMaximumHeight(90)
        g4.addWidget(self.ai_sistem_e)
        d.addWidget(grp4)

        kaydet_btn = QPushButton("💾 AI Ayarlarını Kaydet & Yeniden Başlat")
        kaydet_btn.setObjectName("aksiyon")
        kaydet_btn.clicked.connect(self._ai_ayar_kaydet)
        d.addWidget(kaydet_btn)

        self.ai_durum_lbl = QLabel("Bilinmiyor")
        self.ai_durum_lbl.setStyleSheet(f"color:{R['metin2']};")
        d.addWidget(self.ai_durum_lbl)
        d.addStretch()
        kaydir.setWidget(kap)
        ana = QVBoxLayout(w); ana.setContentsMargins(0,0,0,0); ana.addWidget(kaydir)
        self._ai_panel_guncelle("gemini")
        if self.cekirdek: self._ai_formu_doldur()
        return w

    # ── Ses Sekmesi ───────────────────────────────────────────────────────────

    def _ses_sekme(self):
        w = QWidget()
        kaydir = QScrollArea(); kaydir.setWidgetResizable(True)
        kaydir.setStyleSheet("QScrollArea{border:none;}")
        kap = QWidget()
        d = QVBoxLayout(kap); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(14)

        grp1 = QGroupBox("MİKROFON / HOPARLÖR")
        g1 = QFormLayout(grp1)
        self.mikrofon_cb = QComboBox()
        self.hoparlor_cb = QComboBox()
        self._ses_cihazlari_yukle()
        g1.addRow("Mikrofon:", self.mikrofon_cb)
        g1.addRow("Çıkış:", self.hoparlor_cb)
        test_btn = QPushButton("🎤 Test")
        test_btn.clicked.connect(self._mikrofon_test)
        g1.addRow("", test_btn)
        d.addWidget(grp1)

        grp3 = QGroupBox("GENEL HIZ")
        g3 = QFormLayout(grp3)
        self.hiz_slider = QSlider(Qt.Orientation.Horizontal)
        self.hiz_slider.setRange(5, 20)
        hiz_degeri = 1.0
        if self.cekirdek:
            hiz_degeri = float(self.cekirdek.beyin.get("ses", {}).get("konusma_hizi", 1.0))
        self.hiz_slider.setValue(max(5, min(20, int(round(hiz_degeri * 10)))))
        self.hiz_lbl = QLabel(f"{self.hiz_slider.value()/10:.1f}x"); self.hiz_lbl.setFixedWidth(40)
        self.hiz_slider.valueChanged.connect(
            lambda v: self.hiz_lbl.setText(f"{v/10:.1f}x"))
        hz_row = QHBoxLayout()
        hz_row.addWidget(self.hiz_slider); hz_row.addWidget(self.hiz_lbl)
        hz_w = QWidget(); hz_w.setLayout(hz_row)
        g3.addRow("Konuşma Hızı:", hz_w)
        d.addWidget(grp3)

        grp4 = QGroupBox("SİSTEM")
        g4 = QFormLayout(grp4)
        self.sahip_e = QLineEdit()
        if self.cekirdek:
            self.sahip_e.setText(self.cekirdek.beyin["sistem"]["sahip"])
        self.tehlikeli_onay_cb = QCheckBox("Tehlikeli komutlarda ikinci onay iste")
        if self.cekirdek:
            self.tehlikeli_onay_cb.setChecked(
                bool(self.cekirdek.beyin.get("guvenlik", {}).get("tehlikeli_komutlarda_onay", True))
            )
        g4.addRow("Ana Hitap:", self.sahip_e)
        g4.addRow("", self.tehlikeli_onay_cb)
        d.addWidget(grp4)

        kaydet_btn = QPushButton("💾 Ses Ayarlarını Kaydet")
        kaydet_btn.clicked.connect(self._ses_ayar_kaydet)
        d.addWidget(kaydet_btn)
        d.addStretch()
        kaydir.setWidget(kap)
        ana = QVBoxLayout(w); ana.setContentsMargins(0,0,0,0); ana.addWidget(kaydir)
        return w

    # ── Karakter Sekmesi ──────────────────────────────────────────────────────

    def _karakter_sekme(self):
        w = QWidget()
        kaydir = QScrollArea(); kaydir.setWidgetResizable(True)
        kaydir.setStyleSheet("QScrollArea{border:none;}")
        kap = QWidget()
        d = QVBoxLayout(kap); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(16)

        bl = QLabel("KARAKTER AYARLARI")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        _fab_row = QHBoxLayout()
        _fab_row.addWidget(bl)
        _fab_row.addStretch()
        d.addLayout(_fab_row)

        acik = QLabel("Bilinç adı, hitap, TTS sesi ve ses efekti her karakter için ayrı ayarlanabilir.")
        acik.setStyleSheet(f"color:{R['metin3']};font-size:11px;")
        acik.setWordWrap(True); d.addWidget(acik)

        self._karakter_satirlari = {}
        for bilinc in TUM_BILINCLER:
            grp = QGroupBox(f"  {bilinc}  —  {self._goruntu_ad(bilinc)}")
            gf = QFormLayout(grp)

            # Görüntü adı (GUI'de gösterilen isim)
            goruntu_e = QLineEdit()
            goruntu_e.setText(self._bilinc_goruntu.get(bilinc, bilinc))
            goruntu_e.setPlaceholderText("Ekranda görünen isim")

            hitap_e = QLineEdit()
            hitap_e.setText(self._hitap_adlari.get(bilinc, "Operatör"))
            hitap_e.setPlaceholderText("Hitap adı (Patron, Komutan, Operatör...)")

            tts_motor_cb = QComboBox()
            tts_motor_cb.addItems(["gtts", "edge-tts", "piper"])
            ses_e = QLineEdit(); ses_e.setPlaceholderText("tr-TR-AhmetNeural / tr")

            efekt_cb = QComboBox()
            for ek, ev in SES_EFEKTLERI.items():
                efekt_cb.addItem(f"{ev['label']} ({ek})", ek)

            pitch_sp = QDoubleSpinBox()
            pitch_sp.setRange(0.3, 3.0); pitch_sp.setSingleStep(0.05)
            pitch_sp.setValue(1.0)
            tempo_sp = QDoubleSpinBox()
            tempo_sp.setRange(0.3, 3.0); tempo_sp.setSingleStep(0.05)
            tempo_sp.setValue(1.0)

            def _efekt_sec(idx, p=pitch_sp, t=tempo_sp, cb=efekt_cb):
                ek = cb.itemData(idx)
                ayar = SES_EFEKTLERI.get(ek, {"pitch": 1.0, "tempo": 1.0})
                p.setValue(ayar["pitch"]); t.setValue(ayar["tempo"])
            efekt_cb.currentIndexChanged.connect(_efekt_sec)

            if self.cekirdek:
                ayar = self.cekirdek.beyin["bilincler"].get(bilinc, {})
                if isinstance(ayar, dict):
                    idx = tts_motor_cb.findText(ayar.get("tts_motor", "gtts"))
                    if idx >= 0: tts_motor_cb.setCurrentIndex(idx)
                    ses_e.setText(ayar.get("ses", ""))
                    efekt = ayar.get("ses_efekti", "normal")
                    efekt_idx = efekt_cb.findData(efekt)
                    if efekt_idx >= 0:
                        efekt_cb.setCurrentIndex(efekt_idx)
                    varsayilan_efekt = SES_EFEKTLERI.get(efekt, SES_EFEKTLERI["normal"])
                    pitch_sp.setValue(float(ayar.get("pitch", varsayilan_efekt["pitch"])))
                    tempo_sp.setValue(float(ayar.get("tempo", varsayilan_efekt["tempo"])))

            gf.addRow("Ekran adı:", goruntu_e)
            gf.addRow("Hitap:", hitap_e)
            gf.addRow("TTS Motor:", tts_motor_cb)
            gf.addRow("Ses:", ses_e)
            gf.addRow("Efekt:", efekt_cb)
            gf.addRow("Pitch:", pitch_sp)
            gf.addRow("Tempo:", tempo_sp)

            kaydet_btn = QPushButton(f"💾 {bilinc} Kaydet")
            kaydet_btn.clicked.connect(
                lambda _, b=bilinc, ge=goruntu_e, he=hitap_e,
                       ec=efekt_cb, ps=pitch_sp, ts=tempo_sp,
                       mc=tts_motor_cb, se=ses_e:
                self._karakter_kaydet(b, ge, he, ec, ps, ts, mc, se))
            gf.addRow("", kaydet_btn)

            self._karakter_satirlari[bilinc] = {
                "goruntu": goruntu_e, "hitap": hitap_e,
                "efekt": efekt_cb, "pitch": pitch_sp, "tempo": tempo_sp,
                "tts_motor": tts_motor_cb, "ses": ses_e,
            }
            d.addWidget(grp)

        d.addStretch()
        kaydir.setWidget(kap)
        ana = QVBoxLayout(w); ana.setContentsMargins(0,0,0,0); ana.addWidget(kaydir)
        return w

    # ── Telegram Sekmesi ─────────────────────────────────────────────────────

    def _telegram_sekme(self):
        w = QWidget()
        kaydir = QScrollArea(); kaydir.setWidgetResizable(True)
        kaydir.setStyleSheet("QScrollArea{border:none;}")
        kap = QWidget()
        d = QVBoxLayout(kap); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(14)

        bl = QLabel("TELEGRAM MERKEZİ")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        _fab_row = QHBoxLayout()
        _fab_row.addWidget(bl)
        _fab_row.addStretch()
        _fab_row.addWidget(self._fabrika_btn_olustur('TELEGRAM'))
        d.addLayout(_fab_row)

        grp1 = QGroupBox("BOT AYARLARI")
        gf1 = QFormLayout(grp1)
        self.tg_token_e = QLineEdit()
        self.tg_token_e.setEchoMode(QLineEdit.EchoMode.Password)
        self.tg_token_e.setPlaceholderText("1234567890:ABCdef...")
        self.tg_bot_user_e = QLineEdit()
        self.tg_bot_user_e.setPlaceholderText("@ornek_bot")
        self.tg_chat_e = QLineEdit()
        self.tg_chat_e.setPlaceholderText("Telegram chat/user ID")
        self.tg_aktif_cb  = QCheckBox("Telegram aktif")
        self.tg_tor_cb    = QCheckBox("Tor proxy üzerinden")
        gf1.addRow("Bot Token:", self.tg_token_e)
        gf1.addRow("Bot Kullanıcı Adı:", self.tg_bot_user_e)
        gf1.addRow("Chat ID:", self.tg_chat_e)
        gf1.addRow("", self.tg_aktif_cb)
        gf1.addRow("", self.tg_tor_cb)
        d.addWidget(grp1)

        grp1b = QGroupBox("AJAN API AYARLARI")
        gf1b = QFormLayout(grp1b)
        self.tg_api_id_e = QLineEdit()
        self.tg_api_id_e.setPlaceholderText("12345678")
        self.tg_api_hash_e = QLineEdit()
        self.tg_api_hash_e.setEchoMode(QLineEdit.EchoMode.Password)
        self.tg_api_hash_e.setPlaceholderText("32 karakter api hash")
        self.tg_session_e = QLineEdit()
        self.tg_session_e.setPlaceholderText("zk_limb")
        self.tg_agent_chat_e = QLineEdit()
        self.tg_agent_chat_e.setPlaceholderText("Bot ile ayni chat / kullanici")
        gf1b.addRow("API ID:", self.tg_api_id_e)
        gf1b.addRow("API Hash:", self.tg_api_hash_e)
        gf1b.addRow("Session Adı:", self.tg_session_e)
        gf1b.addRow("Ajan Chat:", self.tg_agent_chat_e)
        d.addWidget(grp1b)

        grp2 = QGroupBox("ÖZELLİKLER")
        gf2 = QVBoxLayout(grp2)
        self.tg_komut_cb  = QCheckBox("Telegram'dan komut al (yazılı + sesli)")
        self.tg_yanit_cb  = QCheckBox("Yanıtları Telegram'a gönder")
        self.tg_log_cb    = QCheckBox("Kritik logları Telegram'a gönder")
        self.tg_uzuv_cb   = QCheckBox("Uzuv durum değişikliklerini bildir")
        for cb in [self.tg_komut_cb, self.tg_yanit_cb, self.tg_log_cb, self.tg_uzuv_cb]:
            gf2.addWidget(cb)
        d.addWidget(grp2)

        # Çapraz ses/bildirim ayarları
        grp_capraz = QGroupBox("ÇAPRAZ KANAL AYARLARI")
        gc = QVBoxLayout(grp_capraz)
        gc.addWidget(QLabel(
            "Bu ayarlar Telegram ↔ PC arasındaki ses ve bildirim yönünü belirler.",
        ))
        acik_lbl = QLabel()
        acik_lbl.setStyleSheet(f"color:{R['metin3']};font-size:10px;")
        acik_lbl.setWordWrap(True)
        acik_lbl.setText(
            "PC'den konuşunca Telegram'a bildir: sesli komut geldiğinde bot mesaj atar.\n"
            "Telegram'dan yazınca PC konuşsun: bot'a mesaj atılınca PC'den sesli yanıt verilir.\n"
            "Telegram'dan ses atınca PC konuşsun: sesli mesaj gelince PC seslenir.")
        gc.addWidget(acik_lbl)

        self.tg_pc_tg_bildir_cb = QCheckBox(
            "📢 PC'den sesli komut gelince Telegram'a da bildir")
        self.tg_tg_pc_konus_cb  = QCheckBox(
            "🔊 Telegram'dan yazı gelince PC'den de sesli yanıt ver")
        self.tg_ses_pc_konus_cb = QCheckBox(
            "🎤 Telegram'dan ses gelince PC'den de sesli yanıt ver")
        self.tg_tg_pc_konus_cb.setStyleSheet(f"color:{R['vurgu']};")
        self.tg_ses_pc_konus_cb.setStyleSheet(f"color:{R['yesil']};")
        for cb in [self.tg_pc_tg_bildir_cb,
                   self.tg_tg_pc_konus_cb,
                   self.tg_ses_pc_konus_cb]:
            gc.addWidget(cb)
        d.addWidget(grp_capraz)

        grp3 = QGroupBox("FİLTRELER ve ERİŞİM")
        gf3 = QFormLayout(grp3)
        self.tg_filtre_e = QLineEdit()
        self.tg_filtre_e.setPlaceholderText("HATA,KRİTİK")
        self.tg_bilinc_lst = QListWidget()
        self.tg_bilinc_lst.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.tg_bilinc_lst.setMaximumHeight(90)
        for b in TUM_BILINCLER:
            self.tg_bilinc_lst.addItem(b)

        # Erişim modu
        self.tg_herkese_cb = QCheckBox("🌐 Herkese açık (izin verilirse tüm Telegram kullanıcıları komut gönderebilir)")
        self.tg_herkese_cb.setStyleSheet(f"color:{R['sari']};")
        self.tg_izin_e = QLineEdit()
        self.tg_izin_e.setPlaceholderText("123456789, 987654321  (virgülle ayırın)")
        self.tg_izin_e.setToolTip(
            "İzin verilen ek chat ID'leri. Boşsa sadece Ana Chat ID kullanılır.")

        def _herkese_toggle(aktif):
            self.tg_izin_e.setEnabled(not aktif)
        self.tg_herkese_cb.toggled.connect(_herkese_toggle)

        gf3.addRow("Log seviyesi:", self.tg_filtre_e)
        gf3.addRow("İzin verilen bilinçler:", self.tg_bilinc_lst)
        gf3.addRow("", self.tg_herkese_cb)
        gf3.addRow("Ek izinli ID'ler:", self.tg_izin_e)
        d.addWidget(grp3)

        btn_row = QHBoxLayout()
        kaydet_btn = QPushButton("💾 Kaydet")
        kaydet_btn.setObjectName("aksiyon")
        kaydet_btn.clicked.connect(self._telegram_kaydet)
        test_btn = QPushButton("📨 Test Mesajı")
        test_btn.clicked.connect(self._telegram_test)
        btn_row.addWidget(kaydet_btn); btn_row.addWidget(test_btn)
        d.addLayout(btn_row)

        self.tg_durum_lbl = QLabel("◎ Yapılandırılmamış")
        self.tg_durum_lbl.setStyleSheet(f"color:{R['metin2']};")
        d.addWidget(self.tg_durum_lbl)

        grp4 = QGroupBox("TELEGRAM MESAJLARI (Canlı)")
        g4 = QVBoxLayout(grp4)
        self.tg_mesaj_ekrani = QTextEdit()
        self.tg_mesaj_ekrani.setReadOnly(True)
        self.tg_mesaj_ekrani.setMinimumHeight(120)
        g4.addWidget(self.tg_mesaj_ekrani)
        d.addWidget(grp4)

        self._telegram_ayar_yukle()
        d.addStretch()
        kaydir.setWidget(kap)
        ana = QVBoxLayout(w); ana.setContentsMargins(0,0,0,0); ana.addWidget(kaydir)
        return w

    # ── Tor Sekmesi ───────────────────────────────────────────────────────────

    def _tor_sekme(self):
        w = QWidget()
        kaydir = QScrollArea(); kaydir.setWidgetResizable(True)
        kaydir.setStyleSheet("QScrollArea{border:none;}")
        kap = QWidget()
        d = QVBoxLayout(kap); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(14)

        bl = QLabel("TOR YÖNETİMİ")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        _fab_row = QHBoxLayout()
        _fab_row.addWidget(bl)
        _fab_row.addStretch()
        d.addLayout(_fab_row)

        # Durum
        grp_dur = QGroupBox("DURUM")
        gd = QFormLayout(grp_dur)
        self.tor_durum_lbl = QLabel("Bilinmiyor")
        self.tor_durum_lbl.setStyleSheet(f"color:{R['metin2']};")
        self.tor_ssh_lbl = QLabel("—")
        self.tor_ssh_lbl.setStyleSheet(f"color:{R['vurgu']};font-weight:bold;")
        self.tor_web_lbl = QLabel("—")
        self.tor_web_lbl.setStyleSheet(f"color:{R['yesil']};")
        gd.addRow("Durum:", self.tor_durum_lbl)
        gd.addRow("SSH Onion:", self.tor_ssh_lbl)
        gd.addRow("Web Onion:", self.tor_web_lbl)
        d.addWidget(grp_dur)

        # Kontrol butonları
        btn_row = QHBoxLayout()
        for lbl, fn in [("▶ Başlat", self._tor_baslat),
                        ("■ Durdur", self._tor_durdur),
                        ("⟳ Yeniden Başlat", self._tor_yeniden),
                        ("⟳ Durumu Güncelle", self._tor_durum_guncelle)]:
            btn = QPushButton(lbl)
            if "Durdur" in lbl: btn.setObjectName("tehlike")
            btn.clicked.connect(fn)
            btn_row.addWidget(btn)
        d.addLayout(btn_row)

        # torrc editör
        grp_rc = QGroupBox("TORRC YAPILANDIRMA")
        gr = QVBoxLayout(grp_rc)
        self.torrc_edit = QTextEdit()
        self.torrc_edit.setFont(QFont("Courier New", 11))
        self.torrc_edit.setMinimumHeight(200)
        gr.addWidget(self.torrc_edit)
        torrc_btn_row = QHBoxLayout()
        torrc_yukle = QPushButton("📂 Yükle")
        torrc_yukle.clicked.connect(self._torrc_yukle)
        torrc_kaydet = QPushButton("💾 Kaydet")
        torrc_kaydet.clicked.connect(self._torrc_kaydet)
        torrc_btn_row.addWidget(torrc_yukle); torrc_btn_row.addWidget(torrc_kaydet)
        gr.addLayout(torrc_btn_row)
        d.addWidget(grp_rc)

        # Web dizini
        grp_web = QGroupBox("WEB SİTESİ (Onion'da yayınlanan)")
        gw = QFormLayout(grp_web)
        self.web_dizin_lbl = QLabel(
            self.cekirdek.tor.web_dizini if self.cekirdek else "—")
        self.web_dizin_lbl.setStyleSheet(f"color:{R['metin2']};")
        web_ac_btn = QPushButton("📁 Dizini Aç")
        web_ac_btn.clicked.connect(self._web_dizin_ac)
        gw.addRow("Dizin:", self.web_dizin_lbl)
        gw.addRow("", web_ac_btn)
        d.addWidget(grp_web)

        self.tor_log_ekrani = QTextEdit()
        self.tor_log_ekrani.setReadOnly(True)
        self.tor_log_ekrani.setMaximumHeight(120)
        self.tor_log_ekrani.setFont(QFont("Courier New", 10))
        d.addWidget(QLabel("Tor Günlüğü:"))
        d.addWidget(self.tor_log_ekrani)

        self._tor_durum_guncelle()
        d.addStretch()
        kaydir.setWidget(kap)
        ana = QVBoxLayout(w); ana.setContentsMargins(0,0,0,0); ana.addWidget(kaydir)
        return w

    # ── Güncelleme Sekmesi ────────────────────────────────────────────────────

    def _guncelleme_sekme(self):
        w = QWidget()
        d = QVBoxLayout(w); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(14)

        bl = QLabel("GÜNCELLEME MERKEZİ")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        _fab_row = QHBoxLayout()
        _fab_row.addWidget(bl)
        _fab_row.addStretch()
        _fab_row.addWidget(self._fabrika_btn_olustur('KARAKTERLER'))
        d.addLayout(_fab_row)

        # ── Hava Durumu ───────────────────────────────────────────────────────
        grp_hava = QGroupBox("🌤 HAVA DURUMU")
        ghava = QVBoxLayout(grp_hava)
        hava_row = QHBoxLayout()
        self.hava_sehir_e = QLineEdit()
        self.hava_sehir_e.setPlaceholderText("Şehir (boş = İstanbul)")
        self.hava_sehir_e.setText("Istanbul")
        hava_al_btn = QPushButton("🌤 Al")
        hava_al_btn.clicked.connect(self._hava_al)
        hava_3_btn = QPushButton("📅 3 Gün")
        hava_3_btn.clicked.connect(self._hava_3_gun)
        hava_row.addWidget(self.hava_sehir_e, 1)
        hava_row.addWidget(hava_al_btn)
        hava_row.addWidget(hava_3_btn)
        ghava.addLayout(hava_row)
        self.hava_metin = QLabel("Hava durumu için butona basın.")
        self.hava_metin.setWordWrap(True)
        self.hava_metin.setStyleSheet(
            f"color:{R['vurgu']};font-size:11px;padding:4px;")
        ghava.addWidget(self.hava_metin)
        d.addWidget(grp_hava)

        # ── Takvim ────────────────────────────────────────────────────────────
        grp_takvim = QGroupBox("📅 TAKVİM")
        gtakvim = QVBoxLayout(grp_takvim)
        takvim_btn_row = QHBoxLayout()
        bugun_btn = QPushButton("📅 Bugün")
        bugun_btn.clicked.connect(self._takvim_bugun)
        yakin_btn = QPushButton("📆 Bu Hafta")
        yakin_btn.clicked.connect(self._takvim_yakin)
        takvim_btn_row.addWidget(bugun_btn)
        takvim_btn_row.addWidget(yakin_btn)
        takvim_btn_row.addStretch()
        gtakvim.addLayout(takvim_btn_row)
        ekle_row = QHBoxLayout()
        self.takvim_baslik_e = QLineEdit()
        self.takvim_baslik_e.setPlaceholderText("Etkinlik")
        self.takvim_tarih_e = QLineEdit()
        self.takvim_tarih_e.setPlaceholderText("yarın / pazartesi")
        self.takvim_saat_e = QLineEdit()
        self.takvim_saat_e.setPlaceholderText("14:30")
        self.takvim_saat_e.setFixedWidth(60)
        takvim_ekle_btn = QPushButton("+ Ekle")
        takvim_ekle_btn.clicked.connect(self._takvim_ekle)
        ekle_row.addWidget(self.takvim_baslik_e, 2)
        ekle_row.addWidget(self.takvim_tarih_e, 2)
        ekle_row.addWidget(self.takvim_saat_e)
        ekle_row.addWidget(takvim_ekle_btn)
        gtakvim.addLayout(ekle_row)
        self.takvim_metin = QTextEdit()
        self.takvim_metin.setReadOnly(True)
        self.takvim_metin.setMaximumHeight(100)
        self.takvim_metin.setFont(QFont("Courier New", 10))
        gtakvim.addWidget(self.takvim_metin)
        d.addWidget(grp_takvim)

        acik = QLabel(
            "Zihin Köprüsü, Tor onion sunucusu üzerinden uzaktan güncellenebilir.\n"
            "Güncelleme URL'sini girin ve kontrol edin.")
        acik.setStyleSheet(f"color:{R['metin3']};font-size:11px;")
        acik.setWordWrap(True); d.addWidget(acik)

        grp = QGroupBox("GÜNCELLEME KAYNAĞI")
        gf = QFormLayout(grp)
        self.guncelleme_url_e = QLineEdit()
        self.guncelleme_url_e.setPlaceholderText(
            "https://www.exeteknoteam.com/zihin-koprusu  veya  http://abc.onion")
        self.guncelleme_tor_cb = QCheckBox("Tor üzerinden indir")
        gf.addRow("Güncelleme URL:", self.guncelleme_url_e)
        gf.addRow("", self.guncelleme_tor_cb)
        d.addWidget(grp)

        btn_row = QHBoxLayout()
        kontrol_btn = QPushButton("🔍 Güncelleme Kontrol Et")
        kontrol_btn.clicked.connect(self._guncelleme_kontrol)
        uygula_btn = QPushButton("⬇ Güncellemeyi İndir & Uygula")
        uygula_btn.setObjectName("aksiyon")
        uygula_btn.clicked.connect(self._guncelleme_uygula)
        btn_row.addWidget(kontrol_btn); btn_row.addWidget(uygula_btn)
        d.addLayout(btn_row)

        self.guncelleme_bilgi = QTextEdit()
        self.guncelleme_bilgi.setReadOnly(True)
        self.guncelleme_bilgi.setFont(QFont("Courier New", 11))
        self.guncelleme_bilgi.setMinimumHeight(150)
        d.addWidget(self.guncelleme_bilgi)

        # ── Sistem Ayarları ───────────────────────────────────────────────────
        sys_grp = QGroupBox("SİSTEM AYARLARI")
        sys_lay = QVBoxLayout(sys_grp)

        self.autostart_cb = QCheckBox("💻  PC açıldığında Zihin Köprüsü'nü otomatik başlat")
        self.autostart_cb.setChecked(self._autostart_aktif_mi())
        self.autostart_cb.toggled.connect(self._autostart_ayarla)
        sys_lay.addWidget(self.autostart_cb)

        d.addWidget(sys_grp)
        d.addStretch()
        return w

    def _autostart_aktif_mi(self) -> bool:
        yol = os.path.expanduser("~/.config/autostart/zihin-koprusu.desktop")
        return os.path.exists(yol)

    def _autostart_ayarla(self, aktif: bool):
        import os as _os
        autostart_dir = _os.path.expanduser("~/.config/autostart")
        dosya = _os.path.join(autostart_dir, "zihin-koprusu.desktop")
        if aktif:
            _os.makedirs(autostart_dir, exist_ok=True)
            proje = ""
            if self.cekirdek:
                proje = self.cekirdek.proje_yolu
            baslat = _os.path.join(proje, "baslat.sh") if proje else "baslat.sh"
            ikon = _os.path.join(proje, "assets", "icon.png") if proje else "utilities-terminal"
            with open(dosya, "w") as f:
                f.write(f"""[Desktop Entry]
Type=Application
Name=Zihin Köprüsü
Exec={baslat}
Icon={ikon}
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
""")
            self.sinyal.log_geldi.emit("BİLGİ", "SİSTEM", "Otomatik başlatma etkinleştirildi.")
        else:
            try:
                _os.remove(dosya)
                self.sinyal.log_geldi.emit("BİLGİ", "SİSTEM", "Otomatik başlatma devre dışı.")
            except FileNotFoundError:
                pass

    # ── Yedek Sekmesi ────────────────────────────────────────────────────────

    def _yedek_sekme(self):
        w = QWidget()
        kaydir = QScrollArea(); kaydir.setWidgetResizable(True)
        kaydir.setStyleSheet("QScrollArea{border:none;}")
        kap = QWidget()
        d = QVBoxLayout(kap); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(14)

        bl = QLabel("YEDEK & GERİ YÜKLEME")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        _fab_row = QHBoxLayout()
        _fab_row.addWidget(bl)
        _fab_row.addStretch()
        _fab_row.addWidget(self._fabrika_btn_olustur('TOR'))
        d.addLayout(_fab_row)

        acik = QLabel(
            "Tüm ayarlar, komutlar, uzuvlar ve eklentiler yedeklenir.\n"
            "Modeller, sanal ortam ve loglar yedek dışıdır (büyük dosyalar).")
        acik.setStyleSheet(f"color:{R['metin3']};font-size:11px;")
        acik.setWordWrap(True); d.addWidget(acik)

        # ── Yedek Al ─────────────────────────────────────────────────────────
        grp_al = QGroupBox("YEDEK AL")
        gal = QVBoxLayout(grp_al)

        self.yedek_hassas_cb = QCheckBox(
            "🔑 Token ve API anahtarlarını da dahil et (güvensiz cihazda kullanmayın)")
        self.yedek_hassas_cb.setStyleSheet(f"color:{R['sari']};")
        gal.addWidget(self.yedek_hassas_cb)

        btn_al_row = QHBoxLayout()
        yedek_al_btn = QPushButton("💾 Yedek Al")
        yedek_al_btn.setObjectName("aksiyon")
        yedek_al_btn.setFixedHeight(38)
        yedek_al_btn.clicked.connect(self._yedek_al)
        yedek_klasor_btn = QPushButton("📂 Klasörü Aç")
        yedek_klasor_btn.clicked.connect(self._yedek_klasor_ac)
        btn_al_row.addWidget(yedek_al_btn)
        btn_al_row.addWidget(yedek_klasor_btn)
        gal.addLayout(btn_al_row)

        self.yedek_durum_lbl = QLabel("")
        self.yedek_durum_lbl.setStyleSheet(f"color:{R['yesil']};font-size:11px;")
        self.yedek_durum_lbl.setWordWrap(True)
        gal.addWidget(self.yedek_durum_lbl)
        d.addWidget(grp_al)

        # ── Mevcut Yedekler ──────────────────────────────────────────────────
        grp_lst = QGroupBox("MEVCUT YEDEKLER")
        glst = QVBoxLayout(grp_lst)

        self.yedek_tablo = QTreeWidget()
        self.yedek_tablo.setHeaderLabels(
            ["Dosya Adı", "Tarih", "Boyut", "Sürüm", "Hassas?"])
        self.yedek_tablo.header().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.yedek_tablo.setColumnWidth(1, 145)
        self.yedek_tablo.setColumnWidth(2, 70)
        self.yedek_tablo.setColumnWidth(3, 55)
        self.yedek_tablo.setColumnWidth(4, 60)
        self.yedek_tablo.setMinimumHeight(160)
        self.yedek_tablo.itemSelectionChanged.connect(self._yedek_secildi)
        glst.addWidget(self.yedek_tablo)

        btn_lst_row = QHBoxLayout()
        yenile_btn = QPushButton("🔄 Yenile")
        yenile_btn.clicked.connect(self._yedek_listesi_yenile)
        sil_btn = QPushButton("🗑 Seçiliyi Sil")
        sil_btn.setObjectName("tehlike")
        sil_btn.clicked.connect(self._yedek_sil)
        btn_lst_row.addWidget(yenile_btn)
        btn_lst_row.addWidget(sil_btn)
        btn_lst_row.addStretch()
        glst.addLayout(btn_lst_row)
        d.addWidget(grp_lst)

        # ── İçerik & Geri Yükleme ────────────────────────────────────────────
        grp_gy = QGroupBox("GERİ YÜKLEME")
        ggy = QVBoxLayout(grp_gy)

        gy_acik = QLabel(
            "Geri yüklemeden önce mevcut durum otomatik olarak yedeklenir.\n"
            "Listeden dosya seçerek seçili dosyaları veya tümünü geri yükleyebilirsiniz.")
        gy_acik.setStyleSheet(f"color:{R['metin3']};font-size:11px;")
        gy_acik.setWordWrap(True)
        ggy.addWidget(gy_acik)

        self.yedek_icerik_lst = QListWidget()
        self.yedek_icerik_lst.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection)
        self.yedek_icerik_lst.setMaximumHeight(130)
        self.yedek_icerik_lst.setFont(QFont("Courier New", 10))
        ggy.addWidget(self.yedek_icerik_lst)

        secim_row = QHBoxLayout()
        tumunu_sec_btn = QPushButton("☑ Tümünü Seç")
        tumunu_sec_btn.clicked.connect(self.yedek_icerik_lst.selectAll)
        secimi_kaldir_btn = QPushButton("☐ Seçimi Kaldır")
        secimi_kaldir_btn.clicked.connect(self.yedek_icerik_lst.clearSelection)
        secim_row.addWidget(tumunu_sec_btn)
        secim_row.addWidget(secimi_kaldir_btn)
        secim_row.addStretch()
        ggy.addLayout(secim_row)

        btn_gy_row = QHBoxLayout()
        secili_yukle_btn = QPushButton("⬆ Seçilenleri Geri Yükle")
        secili_yukle_btn.clicked.connect(
            lambda: self._geri_yukle(sadece_secili=True))
        tumu_yukle_btn = QPushButton("⬆ Tümünü Geri Yükle")
        tumu_yukle_btn.setObjectName("aksiyon")
        tumu_yukle_btn.clicked.connect(
            lambda: self._geri_yukle(sadece_secili=False))
        btn_gy_row.addWidget(secili_yukle_btn)
        btn_gy_row.addWidget(tumu_yukle_btn)
        ggy.addLayout(btn_gy_row)

        self.geri_yukle_durum_lbl = QLabel("")
        self.geri_yukle_durum_lbl.setStyleSheet(
            f"color:{R['yesil']};font-size:11px;")
        self.geri_yukle_durum_lbl.setWordWrap(True)
        ggy.addWidget(self.geri_yukle_durum_lbl)
        d.addWidget(grp_gy)

        d.addStretch()
        kaydir.setWidget(kap)
        ana = QVBoxLayout(w); ana.setContentsMargins(0,0,0,0)
        ana.addWidget(kaydir)

        # İlk yükleme
        self._yedek_listesi_yenile()
        return w

    def _yedek_al(self):
        if not self.cekirdek:
            return
        hassas = self.yedek_hassas_cb.isChecked()
        self.yedek_durum_lbl.setText("⏳ Yedek alınıyor...")
        self.yedek_durum_lbl.setStyleSheet(f"color:{R['sari']};font-size:11px;")
        def _cb(basari, mesaj):
            self.sinyal.yedek_sonuc.emit("al", basari, mesaj)
        self.cekirdek.yedek.yedek_al(hassas_dahil=hassas, callback=_cb)

    def _yedek_klasor_ac(self):
        if self.cekirdek:
            import subprocess
            subprocess.Popen(
                ["xdg-open", self.cekirdek.yedek.yedek_dizini])

    def _yedek_listesi_yenile(self):
        self.yedek_tablo.clear()
        if not self.cekirdek:
            return
        for y in self.cekirdek.yedek.yedek_listesi():
            tarih = y["tarih"][:19].replace("T", " ") if y["tarih"] else "?"
            item = QTreeWidgetItem([
                y["dosya"],
                tarih,
                f"{y['boyut_kb']} KB",
                y["surum"],
                "🔑 Evet" if y["hassas"] else "—",
            ])
            item.setData(0, Qt.ItemDataRole.UserRole, y["tam_yol"])
            self.yedek_tablo.addTopLevelItem(item)

    def _yedek_secildi(self):
        """Seçili yedeğin içeriğini listele."""
        items = self.yedek_tablo.selectedItems()
        self.yedek_icerik_lst.clear()
        if not items or not self.cekirdek:
            return
        yol = items[0].data(0, Qt.ItemDataRole.UserRole)
        icerik = self.cekirdek.yedek.yedek_icerigi(yol)
        for dosya in sorted(icerik):
            if dosya == "_meta.json":
                continue
            self.yedek_icerik_lst.addItem(dosya)

    def _yedek_sil(self):
        items = self.yedek_tablo.selectedItems()
        if not items or not self.cekirdek:
            return
        yol = items[0].data(0, Qt.ItemDataRole.UserRole)
        ad = os.path.basename(yol)
        cevap = QMessageBox.question(
            self, "Yedek Sil",
            f"'{ad}' kalıcı olarak silinecek. Emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if cevap == QMessageBox.StandardButton.Yes:
            self.cekirdek.yedek.yedek_sil(yol)
            self._yedek_listesi_yenile()

    def _geri_yukle(self, sadece_secili: bool):
        items = self.yedek_tablo.selectedItems()
        if not items or not self.cekirdek:
            QMessageBox.warning(self, "Uyarı", "Önce bir yedek seçin.")
            return
        yol = items[0].data(0, Qt.ItemDataRole.UserRole)
        ad = os.path.basename(yol)

        secili_dosyalar = None
        if sadece_secili:
            secili_dosyalar = [
                self.yedek_icerik_lst.item(i).text()
                for i in range(self.yedek_icerik_lst.count())
                if self.yedek_icerik_lst.item(i).isSelected()
            ]
            if not secili_dosyalar:
                QMessageBox.warning(
                    self, "Uyarı",
                    "Geri yüklenecek dosya seçilmedi.\n"
                    "İçerik listesinden dosya seçin.")
                return

        cevap = QMessageBox.question(
            self, "Geri Yükle",
            f"'{ad}' yedeği geri yüklenecek.\n"
            "Mevcut ayarlar üzerine yazılacak.\n"
            "Devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return

        self.geri_yukle_durum_lbl.setText("⏳ Geri yükleniyor...")
        self.geri_yukle_durum_lbl.setStyleSheet(f"color:{R['sari']};font-size:11px;")

        def _cb(basari, mesaj):
            self.sinyal.yedek_sonuc.emit("geri", basari, mesaj)

        self.cekirdek.yedek.geri_yukle(
            yol, secili_dosyalar=secili_dosyalar, callback=_cb)

    def _yedek_sonuc_isle(self, islem: str, basari: bool, mesaj: str):
        renk = R["yesil"] if basari else R["kirmizi"]
        onek = "✓" if basari else "✗ Hata:"
        if islem == "al":
            self.yedek_durum_lbl.setText(f"{onek} {mesaj}")
            self.yedek_durum_lbl.setStyleSheet(f"color:{renk};font-size:11px;")
            if basari:
                self._yedek_listesi_yenile()
        elif islem == "geri":
            ek = " — Yeniden başlatın." if basari else ""
            self.geri_yukle_durum_lbl.setText(f"{onek} {mesaj}{ek}")
            self.geri_yukle_durum_lbl.setStyleSheet(f"color:{renk};font-size:11px;")

    # ── Günlük Sekmesi ────────────────────────────────────────────────────────

    def _gunluk_sekme(self):
        w = QWidget()
        d = QVBoxLayout(w); d.setContentsMargins(16, 16, 16, 16); d.setSpacing(8)
        self.log_paneli = LogPaneli()
        d.addWidget(self.log_paneli, 1)
        alt = QHBoxLayout()
        temizle = QPushButton("Temizle"); temizle.clicked.connect(self.log_paneli.clear)
        kaydet  = QPushButton("Kaydet");  kaydet.clicked.connect(self._gunlugu_kaydet)
        alt.addWidget(temizle); alt.addWidget(kaydet); alt.addStretch()
        d.addLayout(alt)
        return w

    # ── Hakkında Sekmesi ─────────────────────────────────────────────────────


    def _yardim_sekme(self):
        w = QWidget()
        kaydir = QScrollArea(); kaydir.setWidgetResizable(True)
        kaydir.setStyleSheet("QScrollArea{border:none;}")
        kap = QWidget()
        d = QVBoxLayout(kap); d.setContentsMargins(20, 20, 20, 20); d.setSpacing(16)

        bl = QLabel("YARDIM & KULLANIM REHBERİ")
        bl.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        bl.setStyleSheet(f"color:{R['vurgu']};letter-spacing:3px;")
        _fab_row = QHBoxLayout()
        _fab_row.addWidget(bl)
        _fab_row.addStretch()
        _fab_row.addWidget(self._fabrika_btn_olustur('UZUVLAR'))
        d.addLayout(_fab_row)

        acik = QLabel(
            "Her sekmenin işlevi, dikkat edilmesi gereken noktalar "
            "ve sık sorulan sorular bu bölümde açıklanmıştır.")
        acik.setStyleSheet(f"color:{R['metin3']};font-size:11px;")
        acik.setWordWrap(True)
        d.addWidget(acik)

        # Arama kutusu
        arama_row = QHBoxLayout()
        arama_lbl = QLabel("🔍")
        self.yardim_arama_e = QLineEdit()
        self.yardim_arama_e.setPlaceholderText("Konu ara... (örn: telegram, tor, uzuv)")
        self.yardim_arama_e.textChanged.connect(self._yardim_ara)
        arama_row.addWidget(arama_lbl)
        arama_row.addWidget(self.yardim_arama_e, 1)
        d.addLayout(arama_row)

        # Yardım içeriği — QTextEdit ile HTML render
        self.yardim_metin = QTextEdit()
        self.yardim_metin.setReadOnly(True)
        self.yardim_metin.setFont(QFont("Courier New", 11))
        self.yardim_metin.setMinimumHeight(500)
        self.yardim_metin.setStyleSheet(
            f"background:{R['panel']};color:{R['metin']};"
            f"border:1px solid {R['kenar']};border-radius:6px;"
            f"padding:12px;line-height:1.6;")
        self.yardim_metin.setHtml(self._yardim_html())
        d.addWidget(self.yardim_metin, 1)

        d.addStretch()
        kaydir.setWidget(kap)
        ana = QVBoxLayout(w); ana.setContentsMargins(0,0,0,0)
        ana.addWidget(kaydir)
        return w

    def _yardim_ara(self, metin: str):
        """Yardım metninde anahtar kelime vurgula."""
        self.yardim_metin.setHtml(self._yardim_html(metin.strip()))

    def _yardim_html(self, ara: str = "") -> str:
        r = R  # Renk sözlüğü kısayolu

        def blok(baslik, icon, icerik):
            html = (f"<div style='margin-bottom:18px;"
                    f"border-left:3px solid {r['vurgu2']};"
                    f"padding-left:12px;'>"
                    f"<h3 style='color:{r['vurgu']};margin:0 0 6px 0;"
                    f"font-size:13px;letter-spacing:2px;'>"
                    f"{icon} {baslik}</h3>"
                    f"<p style='color:{r['metin']};margin:0;"
                    f"font-size:11px;line-height:1.7;'>{icerik}</p>"
                    f"</div>")
            return html

        bolumler = [
            ("◈ ANA EKRAN", "🏠",
             "Sol panel: Aktif bilinç, ASCII karakter animasyonu, "
             "<b>▶ BAŞLAT</b> / <b>⏹ DURDUR</b> ve <b>⏹ SES KES</b> butonları. "
             "<br><b>BAŞLAT</b> sesli dinleme döngüsünü başlatır. "
             "<b>SES KES</b> konuşan sesi anında keser. "
             "<br>Sağ panel: sohbet ekranı, metin komut girişi. "
             "Klavyeden komut girmek için alt kısımdaki kutuyu kullanın."),

            ("🖥 UZUVLAR", "🖥",
             "Uzak cihaz (Linux/Windows/Android) yönetimi. "
             "<br><b>+ Uzuv Ekle</b>: Yeni cihaz tanımla. "
             "Bağlantı yöntemi: <b>Tor+SSH</b> (güvenli), <b>Yerel SSH</b>, <b>ADB</b>. "
             "<br><b>Onion Sunucu</b>: İstemci üretici için varsayılan sunucu adresi. "
             "<b>🔄 Tor'dan Otomatik Al</b> butonu Tor çalışıyorsa adresinizi otomatik doldurur. "
             "<br><b>Hedef seçim</b>: Tek / Ctrl+tık ile seçtiklerim / Tüm uzuvlar. "
             "<br><b>⬇ İstemci Oluştur</b>: Hedef cihaz için kurulum dosyası üretir. "
             "Üretilen betik cihaza kopyalanıp çalıştırılınca sunucuya <i>hazırım</i> bildirimi gönderir."),

            ("⌨ KOMUTLAR", "⌨",
             "Sesli tetikleyici → kabuk komutu eşleştirme veritabanı. "
             "<br>Her komutun <b>OS'a özel</b> karşılığı olabilir (Linux / Windows / Android). "
             "<br><b>Kategori</b> ile gruplandırın, <b>Yetkili bilinçler</b> ile kısıtlayın. "
             "<br>Tur tipi: <b>kabuk</b> (komut çalıştır), <b>konuşma</b> (sabit yanıt), "
             "<b>uzuv</b> (uzak cihazda çalıştır)."),

            ("🤖 AI", "🤖",
             "Desteklenen sağlayıcılar: <b>Gemini, OpenAI, Anthropic, Groq, Ollama</b>. "
             "<br>API anahtarını buraya girin veya ortam değişkenine ekleyin: "
             "<code>export GEMINI_API_KEY=...</code>"
             "<br>Sistem mesajı kişiselleştirilebilir. "
             "<br><b>Dikkat:</b> Anahtarı <code>ai_ayar.json</code> dosyasında saklarsanız "
             "Git'e <b>eklemeyin</b>."),

            ("🔊 SES", "🔊",
             "STT: <b>Vosk</b> (tamamen offline Türkçe). "
             "TTS: <b>gTTS</b>, <b>Edge-TTS</b>, <b>Piper</b>. "
             "<br>Ses efektleri: pitch/tempo kontrolü (sincap, derin, robot vb.). "
             "<br>Mikrofon sorunlarında: <code>sudo apt install portaudio19-dev</code>"),

            ("👤 KARAKTERLER", "👤",
             "Her bilinç (ABİ, ABLA, KUZEN…) için ayrı <b>hitap adı</b>, "
             "<b>TTS motoru</b>, <b>ses efekti</b> ayarlanabilir. "
             "<br>Kaydet butonuna basınca AI sistem mesajı otomatik güncellenir, "
             "sohbet geçmişi sıfırlanır. "
             "<br>Bilinç geçişi için sesli komut: <i>'Abla devral'</i>, <i>'Kuzen emir komuta sende'</i>"),

            ("✈ TELEGRAM", "✈",
             "<b>Kurulum:</b> @BotFather → /newbot → token → chat_id için @userinfobot. "
             "<br>Yazı mesajı → yazı yanıtı. Sesli mesaj → sesli + yazı yanıtı. "
             "<br><b>Erişim modu:</b> Tek ID, izin listesi (virgülle) veya herkese açık. "
             "<br><b>Dikkat:</b> Herkese açık modda herkes komut gönderebilir!"),

            ("🧅 TOR", "🧅",
             "Tor üç senaryoda çalışır:<br>"
             "1. Sistem Tor zaten çalışıyorsa onu kullanır.<br>"
             "2. Kuruluysa kendi torrc'siyle başlatır.<br>"
             "3. Hiç kurulu değilse <code>apt install tor</code> ile kurar. "
             "<br>SSH ve web hidden service otomatik oluşturulur. "
             "<br>Onion adresi hazır olunca Uzuvlar sekmesine otomatik yazılır."),

            ("💾 YEDEK", "💾",
             "Tüm ayar dosyalarını tek <code>.zip</code> olarak yedekler. "
             "<br><b>Hassas dahil et</b>: token ve API anahtarlarını da ekler — "
             "güvensiz cihazda kullanmayın. "
             "<br>Geri yüklemeden önce mevcut durum <b>otomatik yedeklenir</b>. "
             "<br>Seçili dosyaları veya tümünü geri yükleyebilirsiniz."),

            ("⬇ GÜNCELLEME", "⬇",
             "Tor veya HTTPS üzerinden güncel sürümü kontrol eder ve indirir. "
             "<br>Bu sekmedeki <b>Sistem Ayarları</b> bölümünden "
             "PC açılışında otomatik başlatmayı açıp kapatabilirsiniz."),

            ("⚠ DİKKAT EDİLMESİ GEREKENLER", "⚠",
             "<b>telegram_ayar.json</b>, <b>ai_ayar.json</b>, <b>uzuvlar.json</b> "
             "dosyalarını Git'e eklemeyin — token ve SSH bilgileri içerir. "
             "<br>Telegram botunuzu kamuya açık repoya koymayın. "
             "<br>Uzuv SSH anahtarlarını <code>~/.ssh/</code> içinde tutun. "
             "<br>Tor için ayrı SSH anahtarı kullanın. "
             "<br>Ses kes: <i>'dur', 'ses kes', 'susun'</i> gibi sözcükler."),

            ("❓ SIK SORULAN SORULAR", "❓",
             "<b>Ses tanıma çalışmıyor?</b> → Vosk modeli indirildi mi? "
             "<code>modeller/vosk-tr/vosk-model-small-tr-0.3/</code> klasörü var mı? "
             "<br><b>Telegram yanıt gelmiyor?</b> → Token ve chat_id doğru mu? "
             "Bot aktif mi? (telegram_ayar.json → aktif: true) "
             "<br><b>Onion adresi yok?</b> → Tor Yönetimi sekmesinde Başlat'a basın, "
             "~2 dakika bekleyin. "
             "<br><b>GUI açılmıyor?</b> → <code>pip install PyQt6</code> kurulu mu? "
             "<br><b>Ses çıkmıyor?</b> → <code>sudo apt install ffmpeg</code> kurulu mu?"),
        ]

        if self._gelistirici_modu_aktif():
            bolumler.extend([
                ("⬡ EKLENTİLER", "⬡",
                 "Geliştirici aracı: 10 bağımsız slotta Python scripti çalıştırır. "
                 "<br>Normal kullanıcı için kapalı kalmalıdır. "
                 "<br>Slot klasörüne <code>main.py</code> veya herhangi bir <code>.py</code> dosyası atılabilir. "
                 "<br>Hatalar ana uygulamayı çökertmemesi için ayrı süreçte izole edilir."),

                ("📦 PLUGİNLER", "📦",
                 "Geliştirici aracı: hazır <code>.zip</code> eklenti paketlerini slotlara kurmak için tasarlanmıştır. "
                 "<br>Satışa dönük standart kullanımda gerekli değildir; sadece özel modül dağıtımı yapılacaksa açılmalıdır."),
            ])

        # Ara filtresi
        if ara:
            bolumler = [
                (b, ic, iy) for b, ic, iy in bolumler
                if ara.lower() in b.lower() or ara.lower() in iy.lower()
            ]

        if not bolumler:
            sari = r['sari']
            return (f"<p style='color:{sari};'>"
                    f"'{ara}' için sonuç bulunamadı.</p>")

        html_parcalari = []
        for baslik, icon, icerik in bolumler:
            # Arama terimiyle eşleşen kısmı vurgula
            if ara:
                icerik = icerik.replace(
                    ara,
                    f"<mark style='background:{r['vurgu2']};color:white;"
                    f"border-radius:2px;padding:1px 3px;'>{ara}</mark>"
                )
            html_parcalari.append(blok(baslik, icon, icerik))

        return (
            f"<html><body style='background:{r['panel']};"
            f"color:{r['metin']};font-family:Courier New;'>"
            + "".join(html_parcalari)
            + "</body></html>"
        )

    def _hakkinda_sekme(self):
        w = QWidget()
        d = QVBoxLayout(w); d.setContentsMargins(40, 40, 40, 40); d.setSpacing(18)
        d.setAlignment(Qt.AlignmentFlag.AlignTop)

        baslik = QLabel("ZİHİN KÖPRÜSÜ")
        baslik.setFont(QFont("Courier New", 28, QFont.Weight.Bold))
        baslik.setAlignment(Qt.AlignmentFlag.AlignCenter)
        baslik.setStyleSheet(f"color:{R['vurgu']};letter-spacing:6px;")
        d.addWidget(baslik)

        surum = QLabel("v7.0.0  —  Merkez Uzuv & AI Yönetim Sistemi")
        surum.setAlignment(Qt.AlignmentFlag.AlignCenter)
        surum.setFont(QFont("Courier New", 11))
        surum.setStyleSheet(f"color:{R['metin2']};")
        d.addWidget(surum)

        dev_grp = QGroupBox("DAĞITIM BİLGİSİ")
        dev_f = QFormLayout(dev_grp)
        dev_f.addRow("Ürün:", QLabel("Zihin Köprüsü"))
        dev_f.addRow("Rol:", QLabel("Merkez sunucu ve uzuv orkestrasyonu"))
        dev_f.addRow("Gizlilik:", QLabel("Paket içinde kişisel dağıtım bilgisi tutulmaz"))
        d.addWidget(dev_grp)

        iletisim_grp = QGroupBox("KANALLAR")
        if_layout = QFormLayout(iletisim_grp)
        if_layout.addRow("Telegram:", QLabel("Bot tabanlı tam yönetim desteği"))
        if_layout.addRow("Tor:", QLabel("SSH ve web üzerinden yedek erişim"))
        if_layout.addRow("Uzuv:", QLabel("Yerel, SSH, ters SSH, Tor ve Telegram"))
        d.addWidget(iletisim_grp)

        telif = QLabel(
            "Bu paket dağıtıma hazır anonim yapı ile üretilir.\n"
            "Kişisel isim, telefon, kullanıcı adı ve sabit makine yolu içermez.\n"
            "Dağıtım öncesi son kontrol yine önerilir.")
        telif.setAlignment(Qt.AlignmentFlag.AlignCenter)
        telif.setFont(QFont("Courier New", 10))
        telif.setStyleSheet(
            f"color:{R['vurgu']};padding:10px;"
            f"border:1px solid {R['vurgu']};border-radius:6px;"
            f"background:{R['panel2']};")
        d.addWidget(telif)
        d.addStretch()
        return w


    # ═══════════════════════════════════════════════════════════════════════
    # Fabrika Ayarları
    # ═══════════════════════════════════════════════════════════════════════

    def _fabrika_btn_olustur(self, sekme_adi: str) -> "QPushButton":
        """Sekmeye özel fabrika sıfırlama butonu üretir."""
        btn = QPushButton("⟳ Fabrika")
        btn.setFixedSize(80, 26)
        btn.setStyleSheet(
            f"QPushButton{{background:{R['panel2']};color:{R['metin3']};"
            f"border:1px solid {R['kenar']};border-radius:4px;"
            f"font-size:10px;}}"
            f"QPushButton:hover{{color:{R['sari']};border-color:{R['sari']};}}"
        )
        btn.setToolTip(f"{sekme_adi} ayarlarını fabrika değerlerine sıfırla")
        btn.clicked.connect(lambda: self._fabrika_sifirla(sekme_adi))
        return btn

    def _fabrika_sifirla(self, sekme: str):
        """Seçili sekmenin ayarlarını fabrika değerlerine döndürür."""
        cevap = QMessageBox.question(
            self,
            "Fabrika Ayarları",
            f"'{sekme}' ayarları fabrika değerlerine sıfırlanacak.\n"
            "Mevcut ayarlar kalıcı olarak silinecek. Devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if cevap != QMessageBox.StandardButton.Yes:
            return

        if not self.cekirdek:
            return

        try:
            if sekme == "AI":
                self._fabrika_ai()
            elif sekme == "TELEGRAM":
                self._fabrika_telegram()
            elif sekme == "SES":
                self._fabrika_ses()
            elif sekme == "KOMUTLAR":
                self._fabrika_komutlar()
            elif sekme == "KARAKTERLER":
                self._fabrika_karakterler()
            elif sekme == "TOR":
                self._fabrika_tor()
            elif sekme == "UZUVLAR":
                self._fabrika_uzuvlar()
            else:
                return

            QMessageBox.information(
                self, "Tamamlandı",
                f"'{sekme}' fabrika değerlerine sıfırlandı.")
            self.sinyal.log_geldi.emit(
                "BİLGİ", "FABRİKA", f"{sekme} sıfırlandı.")
        except Exception as e:
            QMessageBox.warning(self, "Hata", str(e))

    def _fabrika_ai(self):
        import os as _os, json as _j
        dosya = _os.path.join(self.cekirdek.proje_yolu, "ai_ayar.json")
        varsayilan = {
            "saglayici": "gemini", "model": "",
            "api_anahtari": "", "api_url": "",
            "sistem_mesaji": (
                "Sen Zihin Köprüsü sisteminin asistanısın. "
                "Kısa, net ve yardımsever Türkçe yanıtlar verirsin."),
            "max_gecmis": 20, "kullan_tor": False,
        }
        with open(dosya, "w") as f:
            _j.dump(varsayilan, f, ensure_ascii=False, indent=2)
        # UI alanlarını sıfırla
        if hasattr(self, 'ai_saglayici_cb'):
            self.ai_saglayici_cb.setCurrentText("gemini")
        if hasattr(self, 'ai_model_e'):
            self.ai_model_e.clear()
        if hasattr(self, 'ai_anahtar_e'):
            self.ai_anahtar_e.clear()
        if hasattr(self, 'ai_url_e'):
            self.ai_url_e.clear()

    def _fabrika_telegram(self):
        import os as _os, json as _j
        dosya = _os.path.join(self.cekirdek.proje_yolu, "telegram_ayar.json")
        varsayilan = {
            "token": "BOT_TOKENINIZI_BURAYA_GIRIN",
            "bot_username": "",
            "chat_id": "", "aktif": False, "tor": False,
            "api_id": "", "api_hash": "", "session_name": "zk_limb", "agent_chat": "",
            "komut_al": True, "yanit_gonder": True,
            "log_gonder": False, "uzuv_bildir": True,
            "log_filtre": "HATA,KRİTİK",
            "herkese_acik": False, "izin_listesi": [],
            "izin_bilincler": ["ABİ", "BİRADER", "ABLA"],
        }
        with open(dosya, "w") as f:
            _j.dump(varsayilan, f, ensure_ascii=False, indent=2)
        self._telegram_ayar_yukle()

    def _fabrika_ses(self):
        if self.cekirdek:
            self.cekirdek.ses.bilinc_efekt.clear()
            self.cekirdek.ses.bilinc_efekt_ozel.clear()
        self.sinyal.log_geldi.emit("BİLGİ", "FABRİKA", "Ses efektleri sıfırlandı.")

    def _fabrika_komutlar(self):
        import os as _os
        dosya = _os.path.join(self.cekirdek.proje_yolu, "komutlar.json")
        if _os.path.exists(dosya):
            _os.remove(dosya)
        from .komut_veritabani import KomutVeritabani
        self.cekirdek.komut_db = KomutVeritabani(
            self.cekirdek.log, dosya)
        self._komut_listele() if hasattr(self, '_komut_listele') else None

    def _fabrika_karakterler(self):
        import os as _os, json as _j
        dosya = _os.path.join(self.cekirdek.proje_yolu, "hitap_ayar.json")
        varsayilan = {b: "Operatör" for b in
                      ["ABİ","BİRADER","BACİ","ABLA","UFAKLIK","DAYI","KUZEN","KEYLO"]}
        with open(dosya, "w") as f:
            _j.dump(varsayilan, f, ensure_ascii=False, indent=2)
        goruntu_dosya = _os.path.join(self.cekirdek.proje_yolu, "bilinc_goruntu.json")
        goruntu_varsayilan = {
            "ABİ": "Abi", "BİRADER": "Birader", "BACİ": "Bacı",
            "ABLA": "Abla", "UFAKLIK": "Ufaklık", "DAYI": "Dayı",
            "KUZEN": "Kuzen", "KEYLO": "Keylo",
        }
        with open(goruntu_dosya, "w") as f:
            _j.dump(goruntu_varsayilan, f, ensure_ascii=False, indent=2)
        for bilinc, ayar in self.cekirdek.beyin.get("bilincler", {}).items():
            if isinstance(ayar, dict):
                ayar["ses_efekti"] = "normal"
                ayar["pitch"] = 1.0
                ayar["tempo"] = 1.0
        self.cekirdek.ses.bilinc_efekt.clear()
        self.cekirdek.ses.bilinc_efekt_ozel.clear()
        self.cekirdek.beyin_kaydet()
        self._hitap_yukle()
        self._bilinc_goruntu_yukle()
        self._sol_hitap_guncelle()

    def _fabrika_tor(self):
        import os as _os, shutil as _shutil
        tor = self.cekirdek.tor
        tor.durdur()
        tor_veri = _os.path.join(self.cekirdek.proje_yolu, "tor_veri")
        for ad in ("torrc", "tor.log"):
            yol = _os.path.join(tor_veri, ad)
            if _os.path.exists(yol):
                _os.remove(yol)
        for ad in ("hs_ssh", "hs_web"):
            yol = _os.path.join(tor_veri, ad)
            if _os.path.isdir(yol):
                _shutil.rmtree(yol, ignore_errors=True)
        tor.kur()
        if hasattr(self, "torrc_edit"):
            self.torrc_edit.setPlainText(tor.torrc_oku())
        if hasattr(self, "tor_durum_lbl"):
            self._tor_durum_guncelle()

    def _fabrika_uzuvlar(self):
        import os as _os, json as _j
        dosya = _os.path.join(self.cekirdek.proje_yolu, "uzuvlar.json")
        with open(dosya, "w") as f:
            _j.dump({"__meta__": {
                "onion_host": "", "onion_port": 22,
                "onion_kullanici": "zihin"}
            }, f, ensure_ascii=False, indent=2)
        self.cekirdek.uzuv.uzuvlar.clear()
        self._uzuv_agaci_yenile()

    # ═══════════════════════════════════════════════════════════════════════════
    # Sinyaller & Bağlantılar
    # ═══════════════════════════════════════════════════════════════════════════

    def _sinyaller_bagla(self):
        self.sinyal.log_geldi.connect(self.log_paneli.log_ekle)
        self.sinyal.durum_degisti.connect(self._durum_guncelle)
        self.sinyal.olay_geldi.connect(self._olay_isle)
        self.sinyal.slot_durum.connect(self._slot_durum_guncelle)
        self.sinyal.uzuv_durum.connect(self._uzuv_durum_guncelle)
        self.sinyal.tor_mesaj.connect(self._tor_log_ekle)
        self.sinyal.plugin_mesaj.connect(
            lambda m: self.plugin_durum_lbl.setText(m))
        self.sinyal.amplitud.connect(self._amplitud_guncelle)
        self.sinyal.wake_word.connect(self._wake_word_isle)
        self.sinyal.yedek_sonuc.connect(self._yedek_sonuc_isle)

    def _cekirdek_bagla(self):
        self.cekirdek.log.dinleyici_ekle(
            lambda s, k, m: self.sinyal.log_geldi.emit(s, k, m))
        self.cekirdek.ses.durum_dinleyici_ekle(
            lambda d: self.sinyal.durum_degisti.emit(d))
        self.cekirdek.olay_dinleyici_ekle(
            lambda t, v: self.sinyal.olay_geldi.emit(t, v))
        self.cekirdek.eklenti.durum_dinleyici_ekle(
            lambda s, d: self.sinyal.slot_durum.emit(s, d))
        self.cekirdek.uzuv.durum_dinleyici_ekle(
            lambda u, d: self.sinyal.uzuv_durum.emit(u, d))
        self.cekirdek.tor.durum_dinleyici_ekle(
            lambda m: self.sinyal.tor_mesaj.emit(m))
        self.cekirdek.plugin.durum_dinleyici_ekle(
            lambda m: self.sinyal.plugin_mesaj.emit(m))
        self.cekirdek._hitap_adlari = self._hitap_adlari

        # Ses dalgası — amplitüd sinyali
        self.cekirdek.ses.amplitud_dinleyici_ekle(
            lambda a: self.sinyal.amplitud.emit(a))

        # Wake word olayı
        self.cekirdek.olay_dinleyici_ekle(
            lambda t, v: self.sinyal.wake_word.emit(v)
            if t == "wake_word" else None)

    # ═══════════════════════════════════════════════════════════════════════════
    # Olay İşleyiciler
    # ═══════════════════════════════════════════════════════════════════════════

    def _durum_guncelle(self, durum):
        dm = {"dinleniyor": ("◉  DİNLENİYOR", "dinleniyor"),
              "konusuyor":  ("◈  KONUŞUYOR",  "konusuyor"),
              "bosta":      ("◎  BEKLEMEDE",  "bekleme"),
              "dusunuyor":  ("◌  DÜŞÜNÜYOR",  "dusunuyor")}
        metin, mod = dm.get(durum, ("◎  BEKLEMEDE", "bekleme"))
        self.durum_lbl.setText(metin)
        self.ascii_karakter.mod_degistir(mod)
        # Hologram efektini senkronize et
        if hasattr(self, 'hologram'):
            self.hologram.mod_ayarla(mod)
        # Ses dalgası modu
        if hasattr(self, 'ses_dalgasi'):
            self.ses_dalgasi.konusuyor_ayarla(durum == "konusuyor")
        if hasattr(self, 'sol_telemetri_lbl'):
            satirlar = {
                "dinleniyor": "MERKEZ: DİNLİYOR\nBAĞ: CANLI\nSES: GİRİŞTE",
                "konusuyor": "MERKEZ: YANITLIYOR\nBAĞ: KARARLI\nSES: ÇIKIŞTA",
                "dusunuyor": "MERKEZ: ANALİZDE\nBAĞ: KARARLI\nSES: İŞLENİYOR",
                "bosta": "MERKEZ: BEKLEMEDE\nBAĞ: HAZIR\nSES: PASİF",
            }
            self.sol_telemetri_lbl.setText(satirlar.get(durum, satirlar["bosta"]))

    def _olay_isle(self, tip, veri):
        if tip == "giris":
            self._konusma_ekle("SİZ", veri, R["yesil"])
        elif tip == "yanit":
            b = (self.cekirdek.aktif_bilinc
                 if self.cekirdek else "SİSTEM")
            self._konusma_ekle(self._goruntu_ad(b), veri, R["vurgu"])
        elif tip == "devir":
            self.bilinc_lbl.setText(self._goruntu_ad(veri))
            self._sol_hitap_guncelle()
            self._konusma_ekle(
                "SİSTEM", f"→ {self._goruntu_ad(veri)}", R["vurgu2"])
        elif tip == "basladi":
            self.bilinc_lbl.setText(self._goruntu_ad(veri))
            self._sol_hitap_guncelle()
            self.baslat_btn.setText("⏹  DURDUR")
            self.baslat_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 #cc2200, stop:1 {R['kirmizi']});
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 13px;
                    letter-spacing: 2px;
                }}
                QPushButton:hover {{
                    background: {R['kirmizi']};
                }}
                QPushButton:pressed {{ padding-top: 12px; }}
            """)
            self.ses_kes_btn.setEnabled(True)
            self._basladi = True
        elif tip == "durduruldu":
            self.baslat_btn.setText("▶  BAŞLAT")
            self.baslat_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {R['vurgu2']}, stop:1 {R['vurgu']});
                    color: {R['arkaplan']};
                    font-weight: bold;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 13px;
                    letter-spacing: 2px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {R['vurgu']}, stop:1 {R['vurgu2']});
                }}
                QPushButton:pressed {{ padding-top: 12px; }}
            """)
            self.ses_kes_btn.setEnabled(False)
            self._basladi = False

    def _konusma_ekle(self, gonderen, metin, renk):
        from datetime import datetime
        zaman = datetime.now().strftime("%H:%M")
        html = (f'<div style="margin-bottom:6px;">'
                f'<span style="color:{R["metin3"]};font-size:10px;">[{zaman}]</span> '
                f'<span style="color:{renk};font-weight:bold;">{gonderen}:</span> '
                f'<span style="color:{R["metin"]};">{metin}</span></div>')
        self.konusma_ekrani.moveCursor(QTextCursor.MoveOperation.End)
        self.konusma_ekrani.insertHtml(html)
        self.konusma_ekrani.moveCursor(QTextCursor.MoveOperation.End)

    def _slot_durum_guncelle(self, slot_id, durum):
        kart = self._slot_kartlari.get(slot_id)
        if not kart: return
        renkler = {"calisiyor": R["sari"], "tamamlandi": R["yesil"],
                   "hata": R["kirmizi"], "bos": R["metin3"]}
        kart._durum_dot.setStyleSheet(
            f"color:{renkler.get(durum, R['metin3'])};")

    def _uzuv_durum_guncelle(self, uid, durum):
        self._uzuv_agaci_yenile()

    def _tor_log_ekle(self, mesaj):
        if hasattr(self, "tor_log_ekrani"):
            self.tor_log_ekrani.append(mesaj)

    # ═══════════════════════════════════════════════════════════════════════════
    # Aksiyonlar
    # ═══════════════════════════════════════════════════════════════════════════

    # ── Genel ────────────────────────────────────────────────────────────────

    def _baslat_durdur(self):
        if not self.cekirdek: return
        if not self._basladi:
            self.cekirdek.baslat_arkaplanda()
        else:
            self.cekirdek.durdur()

    def _ses_kes(self):
        if self.cekirdek:
            self.cekirdek.ses.ses_kes()

    def _klavye_komutu_gonder(self):
        metin = self.komut_girisi.text().strip()
        if not metin or not self.cekirdek: return
        self.komut_girisi.clear()
        threading.Thread(
            target=self.cekirdek.isle, args=(metin, "gui"), daemon=True).start()

    def _bilinc_degistir(self, bilinc):
        if not self.cekirdek: return
        self.cekirdek.aktif_bilinc = bilinc
        self.cekirdek.aktif_bilinc_kaydet()
        self.bilinc_lbl.setText(self._goruntu_ad(bilinc))
        self._sol_hitap_guncelle()
        hitap = self._hitap_adlari.get(bilinc, "Operatör")
        self._konusma_ekle(
            "SİSTEM",
            f"Bilinç → {self._goruntu_ad(bilinc)}  (hitap: {hitap})",
            R["vurgu2"])

    # ── Uzuv ─────────────────────────────────────────────────────────────────

    def _uzuv_agaci_yenile(self):
        if not self.cekirdek: return
        self.uzuv_agaci.clear()
        renk_map = {"bağlı": R["yesil"], "çevrimdışı": R["metin3"],
                    "bağlanıyor": R["sari"], "hata": R["kirmizi"]}
        for uid, uzuv in self.cekirdek.uzuv.uzuvlar.items():
            item = QTreeWidgetItem([
                f"{uzuv.simge} {uzuv.ad}",
                getattr(uzuv, "takma_isim", ""),
                uzuv.tip, uzuv.durum])
            item.setData(0, Qt.ItemDataRole.UserRole, uid)
            item.setForeground(3, QColor(renk_map.get(uzuv.durum, R["metin3"])))
            self.uzuv_agaci.addTopLevelItem(item)

    def _uzuv_secildi(self):
        item = self.uzuv_agaci.currentItem()
        if not item or not self.cekirdek: return
        uid = item.data(0, Qt.ItemDataRole.UserRole)
        uzuv = self.cekirdek.uzuv.uzuvlar.get(uid)
        if uzuv:
            takma = f" | Takma: {uzuv.takma_isim}" \
                if getattr(uzuv, "takma_isim", "") else ""
            birincil = uzuv.birincil_baglanti() if hasattr(uzuv, "birincil_baglanti") else None
            yedekler = uzuv.yedek_baglantilar() if hasattr(uzuv, "yedek_baglantilar") else []
            birincil_metin = "—"
            if birincil:
                birincil_metin = f"{birincil.yontem} | {birincil.host or 'yerel'}:{birincil.port}"
            yedek_metin = ", ".join(
                f"{b.yontem} | {b.host or 'yerel'}:{b.port}" for b in yedekler
            ) or "—"
            self.uzuv_bilgi.setText(
                f"<b>{uzuv.simge} {uzuv.ad}</b>{takma}<br>"
                f"ID: {uzuv.id} | Tip: {uzuv.tip}<br>"
                f"Birincil: {birincil_metin}<br>"
                f"Yedekler: {yedek_metin}<br>"
                f"Bilinçler: {', '.join(uzuv.atanmis_bilincler) or '—'}")

    def _uzuv_ekle(self):
        dlg = UzuvDiyalog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and self.cekirdek:
            yeni_uzuv = dlg.uzuv_al()
            self.cekirdek.uzuv.uzuv_ekle(yeni_uzuv)
            self._uzuv_agaci_yenile()
            setup = dlg.setup_ayari_al()
            if setup:
                self._istemci_uret_ortak(yeni_uzuv, setup["klasor"], {
                    "baglanti_modu": setup["baglanti_modu"],
                    "platform_kod": setup["platform_kod"],
                    "platform_txt": setup["platform_txt"],
                    "windows_format": setup["format_metin"] if setup["platform_kod"] == "windows" else "",
                    "android_format": setup["format_metin"] if setup["platform_kod"] in ("android_apk", "android_termux") else "",
                    "derle_paket": setup.get("derle_paket", False),
                })

    def _otomatik_bildirim_url(self) -> str:
        if not self.cekirdek:
            return ""
        try:
            profil = self.cekirdek.merkez_erisim_profili_getir("local_ip")
            host = (profil.get("host") or "").strip()
            port = int(getattr(self.cekirdek.tor, "web_port", 8765) or 8765)
            if host:
                return f"http://{host}:{port}"
        except Exception:
            pass
        return ""

    def _istemci_uret_ortak(self, uzuv, hedef_ana_klasor: str, secimler: dict):
        if not self.cekirdek or not uzuv or not hedef_ana_klasor:
            return
        klasor = os.path.join(hedef_ana_klasor, f"{uzuv.id}_setup")
        os.makedirs(klasor, exist_ok=True)
        from .istemci_uretici import IstemciUretici, IstemciAyar
        uretici = IstemciUretici(self.cekirdek.log)

        baglanti_modu = secimler.get("baglanti_modu", "ssh_reverse")
        baglanti_txt = {
            "ssh_reverse": "🔁 Merkeze SSH Ters Tünel",
            "tor_http": "🧅 Tor HTTP Ajan",
            "tor_https": "🔒 Tor HTTPS Ajan",
            "telegram_agent": "✈ Telegram Ajan",
        }.get(baglanti_modu, baglanti_modu)
        platform_kod = secimler.get("platform_kod", "linux")
        platform_txt = secimler.get("platform_txt", platform_kod)

        merkez_profil = self.cekirdek.merkez_erisim_bilgisi(baglanti_modu)
        secili_host = merkez_profil.get("host", "")
        secili_port = int(merkez_profil.get("port", self.cekirdek.uzuv.onion_port) or self.cekirdek.uzuv.onion_port)
        if baglanti_modu == "ssh_reverse" and not secili_host:
            QMessageBox.warning(
                self, "Eksik Merkez Erişim",
                "Merkez erişimi henüz otomatik hazırlanamadı.\n"
                "Bir iki saniye bekleyip tekrar deneyin. Gerekirse gelişmiş merkez ayarlarını açabilirsiniz."
            )
            return

        if platform_kod == "windows":
            uzuv_tip = "windows"
            win_fmt = secimler.get("windows_format", "")
        elif platform_kod in ("android_apk", "android_termux"):
            uzuv_tip = "android"
            win_fmt = ""
        else:
            uzuv_tip = "linux"
            win_fmt = ""
        and_fmt = secimler.get("android_format", "")
        derle_paket = bool(secimler.get("derle_paket", False))

        tg_api_id = self.istemci_tg_api_id_e.text().strip() if hasattr(self, 'istemci_tg_api_id_e') else ""
        tg_api_hash = self.istemci_tg_api_hash_e.text().strip() if hasattr(self, 'istemci_tg_api_hash_e') else ""
        tg_session = self.istemci_tg_session_e.text().strip() if hasattr(self, 'istemci_tg_session_e') else "zk_limb"
        tg_chat = self.istemci_tg_chat_e.text().strip() if hasattr(self, 'istemci_tg_chat_e') else ""
        if baglanti_modu == "telegram_agent" and (not tg_api_id or not tg_api_hash or not tg_chat):
            QMessageBox.warning(
                self, "Eksik Bilgi",
                "Telegram ajan üretimi için API ID, API Hash ve Chat alanları dolu olmalı."
            )
            return
        bildirim_url = ""
        if hasattr(self, "onion_bildirim_e"):
            bildirim_url = self.onion_bildirim_e.text().strip()
        if not bildirim_url:
            bildirim_url = self._otomatik_bildirim_url()

        ayar = IstemciAyar(
            uzuv_id=uzuv.id,
            uzuv_ad=uzuv.ad,
            uzuv_tip=uzuv_tip,
            baglanti_modu=baglanti_modu,
            onion_host=secili_host,
            onion_port=secili_port,
            ssh_kullanici=self.cekirdek.uzuv.onion_kullanici,
            ssh_anahtar=uzuv.ssh_anahtar,
            sessiz_mod=self.istemci_sessiz_cb.isChecked() if hasattr(self, "istemci_sessiz_cb") else False,
            ses_aktar=self.istemci_ses_cb.isChecked() if hasattr(self, "istemci_ses_cb") else False,
            otomatik_baslat=self.istemci_otobaslat_cb.isChecked() if hasattr(self, "istemci_otobaslat_cb") else True,
            bildirim_url=bildirim_url,
            windows_format=win_fmt,
            android_format=and_fmt,
            derle_paket=derle_paket,
            telegram_api_id=tg_api_id,
            telegram_api_hash=tg_api_hash,
            telegram_session=tg_session,
            telegram_chat=tg_chat,
        )
        hedef_artifakt = uretici._hedef_artifakt_turu(ayar)
        self.istemci_uretim_durum_yaz(
            f"Hazırlanıyor: {uzuv.ad} | {platform_txt} | {baglanti_txt}",
            R["sari"],
            temizle=True,
        )
        self.istemci_uretim_log_yaz(f"Uzuv: {uzuv.ad} ({uzuv.id})")
        self.istemci_uretim_log_yaz(f"Bağlantı: {baglanti_txt}")
        self.istemci_uretim_log_yaz(
            f"Merkez: {(merkez_profil.get('etiket') or merkez_profil.get('ad') or 'Tanımsız')} → "
            f"{secili_host or 'gerekmez'}:{secili_port}"
        )
        self.istemci_uretim_log_yaz(
            f"Kayıt URL: {bildirim_url or 'otomatik belirlenemedi'}"
        )
        self.istemci_uretim_log_yaz(f"Hedef: {platform_txt}")
        self.istemci_uretim_log_yaz(f"Klasör: {klasor}")
        if hasattr(self, "istemci_uret_btn"):
            self.istemci_uret_btn.setEnabled(False)

        def _uret_thread():
            dosyalar = uretici.uret(ayar, klasor)
            if dosyalar:
                from PyQt6.QtWidgets import QMessageBox as _QMB
                baslik = dosyalar[0].split("/")[-1]
                apk_var = [f for f in dosyalar if f.endswith('.apk')]
                exe_var = [f for f in dosyalar if f.endswith('.exe')]
                zip_var = [f for f in dosyalar if f.endswith('.zip')]
                rapor_var = [f for f in dosyalar if f.endswith('URETIM_RAPORU.txt')]
                gercek_paket = apk_var or exe_var
                paket_basarisiz = derle_paket and hedef_artifakt in ("apk", "exe") and not gercek_paket
                mesaj = (
                    f"{'⚠ Durum' if paket_basarisiz else '✓ Hazır'}\n\n"
                    f"Ana çıktı: {baslik}\n"
                    f"Konum: {klasor}\n\n"
                    f"Toplam: {len(dosyalar)} dosya"
                )
                if apk_var:
                    mesaj += "\n\n📱 Gerçek APK hazır."
                elif exe_var:
                    mesaj += "\n\n💻 Gerçek EXE hazır."
                else:
                    mesaj += "\n\n📦 Kaynak/setup dosyaları hazır."
                if zip_var:
                    mesaj += "\n\nTeslim için paket: " + zip_var[0].split("/")[-1]
                if rapor_var:
                    mesaj += "\nDetay rapor: URETIM_RAPORU.txt"
                from PyQt6.QtCore import QTimer as _QT
                def _goster():
                    self.istemci_uretim_durum_yaz("Hazır" if not paket_basarisiz else "Kaynak setup hazır",
                                                  R["yesil"] if not paket_basarisiz else R["sari"])
                    self.istemci_uretim_log_yaz(
                        "Gerçek paket üretilemedi; rapor ve kaynak setup bırakıldı."
                        if paket_basarisiz else "Üretim tamamlandı."
                    )
                    for yol in dosyalar:
                        self.istemci_uretim_log_yaz(os.path.basename(yol))
                    if hasattr(self, "istemci_uret_btn"):
                        self.istemci_uret_btn.setEnabled(True)
                    (_QMB.warning if paket_basarisiz else _QMB.information)(self, "İstemci Hazır", mesaj)
                _QT.singleShot(0, _goster)
            else:
                from PyQt6.QtCore import QTimer as _QT
                def _hata():
                    self.istemci_uretim_durum_yaz("Üretim başarısız", R["kirmizi"])
                    self.istemci_uretim_log_yaz("Hata: çıktı alınamadı.")
                    if hasattr(self, "istemci_uret_btn"):
                        self.istemci_uret_btn.setEnabled(True)
                    from PyQt6.QtWidgets import QMessageBox as _QMB2
                    _QMB2.warning(self, "Hata", "İstemci oluşturulamadı.\nDetay için loglar/crash.log dosyasına bakın.")
                _QT.singleShot(0, _hata)

        threading.Thread(target=_uret_thread, daemon=True).start()

    def _uzuv_duzenle(self):
        item = self.uzuv_agaci.currentItem()
        if not item or not self.cekirdek: return
        uid = item.data(0, Qt.ItemDataRole.UserRole)
        uzuv = self.cekirdek.uzuv.uzuvlar.get(uid)
        if not uzuv: return
        dlg = UzuvDiyalog(uzuv=uzuv, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.cekirdek.uzuv.uzuv_guncelle(dlg.uzuv_al())
            self._uzuv_agaci_yenile()

    def _uzuv_sil(self):
        item = self.uzuv_agaci.currentItem()
        if not item or not self.cekirdek: return
        uid = item.data(0, Qt.ItemDataRole.UserRole)
        if (QMessageBox.question(self, "Sil", f"'{uid}' silinsin mi?") ==
                QMessageBox.StandardButton.Yes):
            self.cekirdek.uzuv.uzuv_sil(uid)
            self._uzuv_agaci_yenile()

    def _uzuv_ping(self):
        item = self.uzuv_agaci.currentItem()
        if not item or not self.cekirdek: return
        uid = item.data(0, Qt.ItemDataRole.UserRole)
        self.statusBar().showMessage(f"Ping: {uid}...")
        def _cb(ok):
            self.statusBar().showMessage(f"Ping {'✓' if ok else '✗'}: {uid}")
            self._uzuv_agaci_yenile()
        self.cekirdek.uzuv.ping_arkaplanda(uid, _cb)

    def _uzuv_komut_mod_degisti(self, idx: int):
        mod = (self.uzuv_cmd_mod_cb.currentData()
               if hasattr(self, "uzuv_cmd_mod_cb") else "akilli")
        ipuclari = {
            "akilli": "Tanımlı komut veya doğal dil yazın... Örn: reader sesi aç",
            "terminal": "Ham terminal komutu yazın... Örn: uptime && hostname",
            "cmd": "Windows CMD komutu yazın... Örn: dir C:\\",
            "powershell": "PowerShell komutu yazın... Örn: Get-Process | Select -First 5",
            "adb": "ADB shell komutu yazın... Örn: pm list packages",
        }
        if hasattr(self, "uzuv_cmd_e"):
            self.uzuv_cmd_e.setPlaceholderText(
                ipuclari.get(mod, "Komut girin... (Enter ile gönder)")
            )

    def _uzuv_komutunu_hazirla(self, uzuv, komut: str) -> tuple[str, str]:
        mod = (self.uzuv_cmd_mod_cb.currentData()
               if hasattr(self, "uzuv_cmd_mod_cb") else "akilli")
        ham = (komut or "").strip()
        if mod == "akilli":
            return mod, ham
        if mod == "cmd":
            return mod, f'cmd /c "{ham.replace(chr(34), "\\\"")}"'
        if mod == "powershell":
            return mod, f'powershell -NoProfile -Command "{ham.replace(chr(34), "`\"")}"'
        if mod == "adb":
            return mod, ham
        if str(getattr(uzuv, "tip", "")).lower() == "windows":
            return mod, f'cmd /c "{ham.replace(chr(34), "\\\"")}"'
        if str(getattr(uzuv, "tip", "")).lower() == "android":
            return mod, f"sh -lc {shlex.quote(ham)}"
        return mod, f"bash -lc {shlex.quote(ham)}"

    def _uzuv_komut_gonder(self):
        if not self.cekirdek:
            return
        komut = self.uzuv_cmd_e.text().strip()
        if not komut:
            return
        self.uzuv_cmd_e.clear()

        hedef_mod = self.uzuv_hedef_cb.currentData()             if hasattr(self, 'uzuv_hedef_cb') else "secili"

        # Hedef uzuv ID listesini belirle
        if hedef_mod == "tumu":
            uid_listesi = list(self.cekirdek.uzuv.uzuvlar.keys())
        elif hedef_mod == "secili_cok":
            uid_listesi = [
                item.data(0, Qt.ItemDataRole.UserRole)
                for item in self.uzuv_agaci.selectedItems()
                if item.data(0, Qt.ItemDataRole.UserRole)
            ]
        else:  # "secili" — tek seçili
            item = self.uzuv_agaci.currentItem()
            if not item:
                self.uzuv_cikti.append("⚠ Lütfen bir uzuv seçin.\n")
                return
            uid_listesi = [item.data(0, Qt.ItemDataRole.UserRole)]

        if not uid_listesi:
            self.uzuv_cikti.append("⚠ Hedef uzuv bulunamadı.\n")
            return

        mod = (self.uzuv_cmd_mod_cb.currentData()
               if hasattr(self, "uzuv_cmd_mod_cb") else "akilli")
        self.uzuv_cikti.append(
            f"📡 Komut → {len(uid_listesi)} uzuv | mod={mod}: $ {komut}\n")

        for uid in uid_listesi:
            uzuv = self.cekirdek.uzuv.uzuvlar.get(uid)
            ad = uzuv.ad if uzuv else uid
            gidecek = komut
            if uzuv:
                _, gidecek = self._uzuv_komutunu_hazirla(uzuv, komut)
            def _cb(cikti, _ad=ad):
                self.uzuv_cikti.append(f"[{_ad}] {cikti}\n")
            self.cekirdek.uzuv.komut_calistir_arkaplanda(uid, gidecek, _cb)

    def _istemci_uret(self):
        item = self.uzuv_agaci.currentItem()
        if not item or not self.cekirdek:
            QMessageBox.warning(self, "Uyarı", "Önce bir uzuv seçin.")
            return
        uid = item.data(0, Qt.ItemDataRole.UserRole)
        uzuv = self.cekirdek.uzuv.uzuvlar.get(uid)
        if not uzuv: return
        hedef_ana_klasor = QFileDialog.getExistingDirectory(self, "Kayıt Klasörü Seç")
        if not hedef_ana_klasor: return
        platform_kod = (self.istemci_platform_cb.currentData()
                        if hasattr(self, 'istemci_platform_cb') else "")
        if platform_kod == "android_apk" and "APK" in (
                self.istemci_and_fmt_cb.currentText()
                if hasattr(self, 'istemci_and_fmt_cb') else "") and (
                self.istemci_derle_cb.isChecked()
                if hasattr(self, 'istemci_derle_cb') else False):
            QMessageBox.information(
                self, "APK Derleniyor",
                "APK derleme başlatıldı.\n\n"
                "İlk seferinde ~15 dakika sürebilir.\n"
                "Buildozer ve Java yoksa önce otomatik kurulur.\n\n"
                "İşlem arka planda devam ediyor, bitince bildirim gelir.")
        self._istemci_uret_ortak(uzuv, hedef_ana_klasor, {
            "baglanti_modu": (self.istemci_baglanti_cb.currentData()
                               if hasattr(self, 'istemci_baglanti_cb') else "ssh_reverse"),
            "platform_kod": platform_kod,
            "platform_txt": (self.istemci_platform_cb.currentText()
                              if hasattr(self, 'istemci_platform_cb') else ""),
            "windows_format": (self.istemci_win_fmt_cb.currentText()
                                if hasattr(self, 'istemci_win_fmt_cb') else ""),
            "android_format": (self.istemci_and_fmt_cb.currentText()
                                if hasattr(self, 'istemci_and_fmt_cb') else ""),
            "derle_paket": (self.istemci_derle_cb.isChecked()
                             if hasattr(self, 'istemci_derle_cb') else False),
        })

    def istemci_uretim_durum_yaz(self, metin: str, renk: str, temizle: bool = False):
        if hasattr(self, "istemci_durum_lbl"):
            self.istemci_durum_lbl.setText(metin)
            self.istemci_durum_lbl.setStyleSheet(f"color:{renk};font-size:10px;")
        if temizle and hasattr(self, "istemci_sonuc_e"):
            self.istemci_sonuc_e.clear()

    def istemci_uretim_log_yaz(self, metin: str):
        if hasattr(self, "istemci_sonuc_e"):
            self.istemci_sonuc_e.append(metin)

    def _istemci_platform_degisti(self, idx: int):
        """Platform değişince ilgili format seçeneklerini göster/gizle."""
        platform = self.istemci_platform_cb.currentData()
        self.istemci_win_fmt_w.setVisible(platform == "windows")
        self.istemci_and_fmt_w.setVisible(platform in ("android_termux", "android_apk"))
        if platform == "android_apk":
            self.istemci_and_fmt_cb.setCurrentIndex(1)
        elif platform == "android_termux":
            self.istemci_and_fmt_cb.setCurrentIndex(0)

    def _istemci_baglanti_degisti(self, idx: int):
        if not hasattr(self, "istemci_baglanti_cb"):
            return
        baglanti = self.istemci_baglanti_cb.currentData()
        telegram_mi = baglanti == "telegram_agent"
        if hasattr(self, "istemci_tg_w"):
            self.istemci_tg_w.setVisible(telegram_mi)
        if hasattr(self, "istemci_ses_cb"):
            self.istemci_ses_cb.setEnabled(not telegram_mi)
        if telegram_mi:
            if hasattr(self, 'tg_api_id_e'):
                self.istemci_tg_api_id_e.setText(self.tg_api_id_e.text().strip())
            if hasattr(self, 'tg_api_hash_e'):
                self.istemci_tg_api_hash_e.setText(self.tg_api_hash_e.text().strip())
            if hasattr(self, 'tg_session_e'):
                self.istemci_tg_session_e.setText(self.tg_session_e.text().strip() or "zk_limb")
            if hasattr(self, 'tg_agent_chat_e'):
                self.istemci_tg_chat_e.setText(self.tg_agent_chat_e.text().strip() or self.tg_chat_e.text().strip())
        if self.cekirdek:
            mod = baglanti or "ssh_reverse"
            profil = self.cekirdek.merkez_erisim_bilgisi(mod)
            etiket = profil.get("etiket") or profil.get("ad") or "Tanımsız"
            host = profil.get("host") or "otomatik / boş"
            port = profil.get("port") or 0
            if hasattr(self, "istemci_merkez_lbl"):
                self.istemci_merkez_lbl.setText(f"{etiket} → {host}:{port}")

    def _merkez_erisim_gui_yukle(self):
        if not self.cekirdek:
            return
        profiller = self.cekirdek.merkez_erisim_profilleri().get("profiller", {})
        local = profiller.get("local_ip", {})
        clear = profiller.get("clearnet", {})
        tor = profiller.get("tor_hidden_service", {})
        tg = profiller.get("telegram", {})
        self.merkez_local_host_e.setText(local.get("host", ""))
        self.merkez_local_port_e.setValue(int(local.get("port", 22) or 22))
        self.merkez_clearnet_host_e.setText(clear.get("host", ""))
        self.merkez_clearnet_port_e.setValue(int(clear.get("port", 22) or 22))
        self.onion_host_e.setText(tor.get("host", self.cekirdek.uzuv.onion_host))
        self.onion_port_e.setValue(int(tor.get("port", self.cekirdek.uzuv.onion_port) or 22))
        self.onion_user_e.setText(self.cekirdek.uzuv.onion_kullanici)
        self.merkez_tg_host_e.setText(tg.get("host", ""))
        self._merkez_erisim_ozet_guncelle()
        if hasattr(self, "istemci_baglanti_cb"):
            self._istemci_baglanti_degisti(0)

    def _merkez_erisim_ozet_guncelle(self):
        if not self.cekirdek or not hasattr(self, "merkez_ozet_lbl"):
            return
        profiller = self.cekirdek.merkez_erisim_profilleri().get("profiller", {})
        local = profiller.get("local_ip", {})
        clear = profiller.get("clearnet", {})
        tor = profiller.get("tor_hidden_service", {})
        tg = profiller.get("telegram", {})
        satirlar = [
            f"Yerel: {local.get('host') or 'otomatik aranıyor'}:{local.get('port') or 22}",
            f"Clearnet: {clear.get('host') or 'kapalı'}:{clear.get('port') or 22}",
            f"Tor: {tor.get('host') or 'hazır olunca otomatik'}:{tor.get('port') or 22}",
            f"Telegram: {tg.get('host') or 'bot chat otomatik'}",
        ]
        self.merkez_ozet_lbl.setText(" | ".join(satirlar))

    def _onion_kaydet(self):
        if not self.cekirdek: return
        self.cekirdek.uzuv.onion_host = self.onion_host_e.text().strip()
        self.cekirdek.uzuv.onion_port = self.onion_port_e.value()
        self.cekirdek.uzuv.onion_kullanici = self.onion_user_e.text().strip()
        self.cekirdek.uzuv.kaydet()
        profiller = self.cekirdek.merkez_erisim_profilleri().get("profiller", {})
        profiller["local_ip"]["host"] = self.merkez_local_host_e.text().strip()
        profiller["local_ip"]["port"] = self.merkez_local_port_e.value()
        profiller["clearnet"]["host"] = self.merkez_clearnet_host_e.text().strip()
        profiller["clearnet"]["port"] = self.merkez_clearnet_port_e.value()
        profiller["tor_hidden_service"]["host"] = self.onion_host_e.text().strip()
        profiller["tor_hidden_service"]["port"] = self.onion_port_e.value()
        profiller["telegram"]["host"] = self.merkez_tg_host_e.text().strip()
        self.cekirdek.merkez_erisim_kaydet(profiller)
        self._merkez_erisim_ozet_guncelle()
        self.sinyal.log_geldi.emit("BİLGİ", "MERKEZ", "Merkez erişim profilleri kaydedildi.")
        self._istemci_baglanti_degisti(self.istemci_baglanti_cb.currentIndex())

    def _onion_otomatik_al(self):
        """Tor'dan mevcut onion adresini okur, alanlara doldurur."""
        if not self.cekirdek:
            return
        # 1. Tor yöneticisinden oku
        ssh_onion = self.cekirdek.tor.onion_adresi_al("ssh")
        if ssh_onion:
            self.onion_host_e.setText(ssh_onion)
            self.onion_durum_lbl.setText(f"✓ {ssh_onion}")
            # Otomatik kaydet
            self._onion_kaydet()
            self.sinyal.log_geldi.emit(
                "BİLGİ", "ONION", f"Otomatik tanımlandı: {ssh_onion}")
        else:
            self.onion_durum_lbl.setText("⚠ Tor çalışmıyor veya henüz hazır değil.")
            self.onion_durum_lbl.setStyleSheet(f"color:{R['sari']};font-size:10px;")

    def _onion_olay_isle(self, tip: str, veri: str):
        """cekirdek'ten gelen onion_hazir olayını GUI'ye yansıt."""
        if tip == "onion_hazir" and veri:
            self.onion_host_e.setText(veri)
            self.onion_durum_lbl.setText(f"✓ Otomatik: {veri}")
            self.onion_durum_lbl.setStyleSheet(
                f"color:{R['yesil']};font-size:10px;")
            self._merkez_erisim_ozet_guncelle()
            self._istemci_baglanti_degisti(self.istemci_baglanti_cb.currentIndex())

    # ── Komut ────────────────────────────────────────────────────────────────

    def _komut_listele(self):
        if not self.cekirdek: return
        self.komut_agaci.clear()
        filtre = self.komut_filtre_e.text().lower()
        os_f = self.komut_os_filtre.currentText()
        sayac = 0
        for kid, k in self.cekirdek.komut_db.komutlar.items():
            if filtre and filtre not in k.ad.lower() \
                    and filtre not in k.kategori.lower():
                continue
            if os_f != "Tümü" and k.hedef_os != os_f:
                continue
            item = QTreeWidgetItem([
                k.ad, k.kategori, k.hedef_os, k.tur,
                k.tetikleyiciler[0] if k.tetikleyiciler else ""])
            item.setData(0, Qt.ItemDataRole.UserRole, kid)
            if not k.aktif:
                for i in range(5):
                    item.setForeground(i, QColor(R["metin3"]))
            self.komut_agaci.addTopLevelItem(item)
            sayac += 1
        self.komut_sayisi_lbl.setText(f"{sayac} komut")

    def _komut_ekle(self):
        dlg = KomutDiyalog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and self.cekirdek:
            self.cekirdek.komut_db.komut_ekle(dlg.komut_al())
            self._komut_listele()

    def _komut_duzenle(self):
        item = self.komut_agaci.currentItem()
        if not item or not self.cekirdek: return
        kid = item.data(0, Qt.ItemDataRole.UserRole)
        komut = self.cekirdek.komut_db.komutlar.get(kid)
        if not komut: return
        dlg = KomutDiyalog(komut=komut, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.cekirdek.komut_db.komut_guncelle(dlg.komut_al())
            self._komut_listele()

    def _komut_sil(self):
        item = self.komut_agaci.currentItem()
        if not item or not self.cekirdek: return
        kid = item.data(0, Qt.ItemDataRole.UserRole)
        if (QMessageBox.question(self, "Sil", f"'{kid}' silinsin mi?") ==
                QMessageBox.StandardButton.Yes):
            self.cekirdek.komut_db.komut_sil(kid)
            self._komut_listele()

    def _komut_cogalt(self):
        item = self.komut_agaci.currentItem()
        if not item or not self.cekirdek: return
        kid = item.data(0, Qt.ItemDataRole.UserRole)
        komut = self.cekirdek.komut_db.komutlar.get(kid)
        if not komut: return
        import copy
        yeni = copy.deepcopy(komut)
        yeni.id = komut.id + "_k" + str(uuid.uuid4())[:4]
        yeni.ad = komut.ad + " (kopya)"
        self.cekirdek.komut_db.komut_ekle(yeni)
        self._komut_listele()

    def _komut_iceri(self):
        f, _ = QFileDialog.getOpenFileName(self, "İçeri Aktar", "", "JSON (*.json)")
        if f and self.cekirdek:
            try:
                with open(f) as fh:
                    data = json.load(fh)
                from .komut_veritabani import Komut
                for kid, dd in data.items():
                    self.cekirdek.komut_db.komut_ekle(Komut.from_dict(dd))
                self._komut_listele()
            except Exception as e:
                QMessageBox.warning(self, "Hata", str(e))

    def _komut_disari(self):
        f, _ = QFileDialog.getSaveFileName(
            self, "Dışa Aktar", "komutlar.json", "JSON (*.json)")
        if f and self.cekirdek:
            with open(f, "w") as fh:
                json.dump({k: v.to_dict()
                           for k, v in self.cekirdek.komut_db.komutlar.items()},
                          fh, ensure_ascii=False, indent=2)

    # ── AI ───────────────────────────────────────────────────────────────────

    def _ai_panel_guncelle(self, saglayici):
        if hasattr(self, "grp_uzak_ollama"):
            self.grp_uzak_ollama.setVisible(saglayici == "ollama_uzak")

    def _ai_formu_doldur(self):
        if not self.cekirdek: return
        ayar = self.cekirdek._ai_ayar
        idx = self.ai_saglayici_cb.findText(ayar.saglayici)
        if idx >= 0: self.ai_saglayici_cb.setCurrentIndex(idx)
        self.ai_model_e.setText(ayar.model)
        self.ai_anahtar_e.setText(ayar.api_anahtari)
        self.ai_url_e.setText(ayar.api_url)
        self.ai_tor_cb.setChecked(ayar.kullan_tor)
        self.ai_tor_proxy_e.setText(ayar.tor_proxy)
        self.ai_sistem_e.setPlainText(ayar.sistem_mesaji)
        self.ollama_ssh_host_e.setText(ayar.uzak_ssh_host)
        self.ollama_ssh_port_e.setValue(ayar.uzak_ssh_port)
        self.ollama_ssh_user_e.setText(ayar.uzak_ssh_kullanici)
        self.ollama_ssh_key_e.setText(ayar.uzak_ssh_anahtar)
        self.ollama_port_e.setValue(ayar.uzak_ollama_port)
        self.ai_yedekler_e.setPlainText(self._ai_yedekler_metne(self.cekirdek._ai_yedek_ayarlar))
        if self.cekirdek.ai:
            self.ai_durum_lbl.setText(
                f"✓ Hazır — {self.cekirdek.ai.ayar.saglayici}"
                if self.cekirdek.ai.hazir else "✗ Hazır değil")

    def _ai_ayar_kaydet(self):
        if not self.cekirdek: return
        from .ai_motoru import AIAyar
        ayar = AIAyar(
            saglayici=self.ai_saglayici_cb.currentText(),
            model=self.ai_model_e.text().strip(),
            api_anahtari=self.ai_anahtar_e.text().strip(),
            api_url=self.ai_url_e.text().strip(),
            kullan_tor=self.ai_tor_cb.isChecked(),
            tor_proxy=self.ai_tor_proxy_e.text().strip(),
            sistem_mesaji=self.ai_sistem_e.toPlainText().strip(),
            uzak_ssh_host=self.ollama_ssh_host_e.text().strip(),
            uzak_ssh_port=self.ollama_ssh_port_e.value(),
            uzak_ssh_kullanici=self.ollama_ssh_user_e.text().strip(),
            uzak_ssh_anahtar=self.ollama_ssh_key_e.text().strip(),
            uzak_ollama_port=self.ollama_port_e.value(),
        )
        yedekler = self._ai_yedekler_coz(self.ai_yedekler_e.toPlainText())
        self.cekirdek.ai_yeniden_baslat(ayar, yedekler)
        durum = ("✓ Hazır" if (self.cekirdek.ai and self.cekirdek.ai.hazir)
                 else "✗ Hazır değil")
        toplam = 1 + len(yedekler)
        aktif = self.cekirdek.ai.ayar.saglayici if self.cekirdek.ai else ayar.saglayici
        self.ai_durum_lbl.setText(f"{durum} — aktif: {aktif} | profil: {toplam}")

    @staticmethod
    def _ai_yedekler_metne(yedekler) -> str:
        satirlar = []
        for y in yedekler or []:
            satirlar.append(" | ".join([
                y.saglayici or "",
                y.model or "",
                y.api_anahtari or "",
                y.api_url or "",
            ]))
        return "\n".join(satirlar)

    def _ai_yedekler_coz(self, metin: str):
        from .ai_motoru import AIAyar
        yedekler = []
        for satir in (metin or "").splitlines():
            satir = satir.strip()
            if not satir or satir.startswith("#"):
                continue
            parcalar = [p.strip() for p in satir.split("|")]
            while len(parcalar) < 4:
                parcalar.append("")
            saglayici, model, anahtar, url = parcalar[:4]
            if not saglayici:
                continue
            yedekler.append(AIAyar(
                saglayici=saglayici,
                model=model,
                api_anahtari=anahtar,
                api_url=url,
                kullan_tor=self.ai_tor_cb.isChecked(),
                tor_proxy=self.ai_tor_proxy_e.text().strip(),
                sistem_mesaji=self.ai_sistem_e.toPlainText().strip(),
                uzak_ollama_port=self.ollama_port_e.value(),
            ))
        return yedekler

    def _ai_modelleri_listele(self):
        if not self.cekirdek or not self.cekirdek.ai:
            QMessageBox.warning(self, "Uyarı", "Önce AI ayarlarını kaydedin.")
            return
        modeller = self.cekirdek.ai.modeller_listele()
        if not modeller:
            QMessageBox.information(self, "Modeller", "Model listesi alınamadı.")
            return
        dlg = QDialog(self); dlg.setWindowTitle("Modeller")
        dv = QVBoxLayout(dlg)
        lst = QListWidget()
        for m in modeller: lst.addItem(m)
        dv.addWidget(lst)
        sec = QPushButton("Seç")
        sec.clicked.connect(lambda: (
            self.ai_model_e.setText(
                lst.currentItem().text() if lst.currentItem() else ""),
            dlg.accept()))
        dv.addWidget(sec); dlg.exec()

    # ── Ses ──────────────────────────────────────────────────────────────────

    def _ses_cihazlari_yukle(self):
        try:
            cihazlar = sd.query_devices()
            kayitli = self.cekirdek.beyin.get("ses", {}) if self.cekirdek else {}
            kayitli_mik = kayitli.get("mikrofon_cihaz")
            kayitli_hop = kayitli.get("hoparlor_cihaz")
            for i, c in enumerate(cihazlar):
                if c["max_input_channels"] > 0:
                    self.mikrofon_cb.addItem(f"{i}: {c['name']}", i)
                if c["max_output_channels"] > 0:
                    self.hoparlor_cb.addItem(f"{i}: {c['name']}", i)
            vd = sd.default.device
            hedef_mik = kayitli_mik if kayitli_mik is not None else vd[0]
            hedef_hop = kayitli_hop if kayitli_hop is not None else vd[1]
            for i in range(self.mikrofon_cb.count()):
                if self.mikrofon_cb.itemData(i) == hedef_mik:
                    self.mikrofon_cb.setCurrentIndex(i)
            for i in range(self.hoparlor_cb.count()):
                if self.hoparlor_cb.itemData(i) == hedef_hop:
                    self.hoparlor_cb.setCurrentIndex(i)
        except Exception:
            self.mikrofon_cb.addItem("Varsayılan")
            self.hoparlor_cb.addItem("Varsayılan")

    def _mikrofon_test(self):
        QMessageBox.information(self, "Mikrofon Testi",
                                "Test için Vosk başlatılmış olmalı.")

    def _ses_ayar_kaydet(self):
        if not self.cekirdek: return
        self.cekirdek.beyin["sistem"]["sahip"] = self.sahip_e.text().strip()
        self.cekirdek.beyin.setdefault("guvenlik", {})
        self.cekirdek.beyin["guvenlik"]["tehlikeli_komutlarda_onay"] = \
            self.tehlikeli_onay_cb.isChecked()
        self.cekirdek.beyin["ses"]["konusma_hizi"] = self.hiz_slider.value() / 10
        self.cekirdek.ses.konusma_hizi = \
            self.cekirdek.beyin["ses"]["konusma_hizi"]
        mik = self.mikrofon_cb.currentData()
        if mik is not None:
            sd.default.device[0] = mik
            self.cekirdek.beyin["ses"]["mikrofon_cihaz"] = mik
        hop = self.hoparlor_cb.currentData()
        if hop is not None:
            sd.default.device[1] = hop
            self.cekirdek.beyin["ses"]["hoparlor_cihaz"] = hop
        self.aktif_lbl.setText(f"◈ {self.sahip_e.text().strip()}")
        self.cekirdek.beyin_kaydet()

    # ── Karakter ─────────────────────────────────────────────────────────────

    def _karakter_kaydet(self, bilinc, goruntu_e, hitap_e,
                          efekt_cb, pitch_sp, tempo_sp, tts_motor_cb, ses_e):
        # Görüntü adı
        goruntu = goruntu_e.text().strip() or bilinc
        self._bilinc_goruntu[bilinc] = goruntu
        self._bilinc_goruntu_kaydet()

        # Hitap — hem dosyaya hem cekirdek'e hem AI sistem mesajına yansıt
        yeni_hitap = hitap_e.text().strip() or "Operatör"
        self._hitap_adlari[bilinc] = yeni_hitap
        self._hitap_kaydet()          # → hitap_ayar.json + cekirdek._hitap_adlari
        self._sol_hitap_guncelle()    # → sol panel güncelle

        if self.cekirdek:
            # beyin.yaml sahip alanını da güncelle (aktif bilinçse)
            if bilinc == self.cekirdek.aktif_bilinc:
                self.cekirdek.beyin["sistem"]["sahip"] = yeni_hitap

            # AI sistem mesajını hitap adıyla güncelle — AI artık doğru adı bilir
            if self.cekirdek.ai and self.cekirdek._ai_ayar:
                aktif_hitap = self.cekirdek.hitap_al()
                self.cekirdek._ai_ayar.sistem_mesaji = (
                    f"Sen Zihin Köprüsü merkez sisteminin asistanısın. "
                    f"Operatörün hitap adı {aktif_hitap!r}. "
                    f"Ona her zaman '{aktif_hitap}' diye hitap et. "
                    f"Kısa, net ve yardımsever Türkçe yanıtlar verirsin."
                )
                # Sohbet geçmişini sıfırla ki yeni kimlikle başlasın
                self.cekirdek.ai.sohbet_sifirla()

            # Ses efekti
            ek = efekt_cb.currentData()
            self.cekirdek.ses.bilinc_efekt[bilinc] = ek
            self.cekirdek.ses.bilinc_efekt_ozel[bilinc] = {
                "pitch": pitch_sp.value(), "tempo": tempo_sp.value()}
            ayar = self.cekirdek.beyin["bilincler"].get(bilinc, {})
            if isinstance(ayar, dict):
                ayar["tts_motor"] = tts_motor_cb.currentText()
                ses_degeri = ses_e.text().strip()
                if ses_degeri:
                    ayar["ses"] = ses_degeri
                else:
                    ayar.pop("ses", None)
                ayar["ses_efekti"] = ek
                ayar["pitch"] = float(pitch_sp.value())
                ayar["tempo"] = float(tempo_sp.value())

            # Devir komutlarını da güncelle: eski görüntü adı yerine yeni adı ekle
            # (beyin.yaml'daki orijinal komutları bozmadan, ek takma ad olarak)
            bilincler = self.cekirdek.beyin.get("bilincler", {})
            bilinc_ayar = bilincler.get(bilinc, {})
            if isinstance(bilinc_ayar, dict):
                mevcut = bilinc_ayar.get("devir_komutlari", [])
                # Görüntü adı küçük harf ile de devir komut olarak ekle
                yeni_komut = f"{goruntu.lower()} devral"
                yeni_komut2 = f"{goruntu.lower()} emir komuta sende"
                for k in [yeni_komut, yeni_komut2]:
                    if k not in mevcut:
                        mevcut.append(k)
                bilinc_ayar["devir_komutlari"] = mevcut
            self.cekirdek.beyin_kaydet()

        self.sinyal.log_geldi.emit(
            "BİLGİ", "KARAKTER",
            f"{bilinc} → görüntü:{goruntu!r} hitap:{yeni_hitap!r} kaydedildi. "
            f"AI sohbeti sıfırlandı.")

    # ── Telegram ─────────────────────────────────────────────────────────────

    def _telegram_ayar_yukle(self):
        if not self.cekirdek: return
        dosya = os.path.join(self.cekirdek.proje_yolu, "telegram_ayar.json")
        if not os.path.exists(dosya): return
        try:
            with open(dosya) as f:
                ayar = json.load(f)
            self.tg_token_e.setText(ayar.get("token", ""))
            self.tg_bot_user_e.setText(ayar.get("bot_username", ""))
            self.tg_chat_e.setText(str(ayar.get("chat_id", "")))
            self.tg_api_id_e.setText(str(ayar.get("api_id", "")))
            self.tg_api_hash_e.setText(ayar.get("api_hash", ""))
            self.tg_session_e.setText(ayar.get("session_name", "zk_limb"))
            self.tg_agent_chat_e.setText(str(ayar.get("agent_chat", ayar.get("chat_id", ""))))
            self.tg_aktif_cb.setChecked(ayar.get("aktif", False))
            self.tg_tor_cb.setChecked(ayar.get("tor", False))
            self.tg_komut_cb.setChecked(ayar.get("komut_al", True))
            self.tg_yanit_cb.setChecked(ayar.get("yanit_gonder", True))
            self.tg_log_cb.setChecked(ayar.get("log_gonder", False))
            self.tg_uzuv_cb.setChecked(ayar.get("uzuv_bildir", False))
            self.tg_filtre_e.setText(ayar.get("log_filtre", ""))
            izin = ayar.get("izin_bilincler", [])
            for i in range(self.tg_bilinc_lst.count()):
                self.tg_bilinc_lst.item(i).setSelected(
                    self.tg_bilinc_lst.item(i).text() in izin)
            # Erişim modu
            herkese = ayar.get("herkese_acik", False)
            self.tg_herkese_cb.setChecked(herkese)
            self.tg_izin_e.setEnabled(not herkese)
            izin_listesi = ayar.get("izin_listesi", [])
            self.tg_izin_e.setText(", ".join(str(x) for x in izin_listesi))
            # Çapraz kanal ayarları
            if hasattr(self, 'tg_pc_tg_bildir_cb'):
                self.tg_pc_tg_bildir_cb.setChecked(
                    ayar.get("pc_tg_bildir", True))
            if hasattr(self, 'tg_tg_pc_konus_cb'):
                self.tg_tg_pc_konus_cb.setChecked(
                    ayar.get("tg_pc_konus", False))
            if hasattr(self, 'tg_ses_pc_konus_cb'):
                self.tg_ses_pc_konus_cb.setChecked(
                    ayar.get("ses_pc_konus", False))
        except Exception:
            pass

    def _telegram_kaydet(self):
        if not self.cekirdek: return
        izin = [self.tg_bilinc_lst.item(i).text()
                for i in range(self.tg_bilinc_lst.count())
                if self.tg_bilinc_lst.item(i).isSelected()]
        # İzin listesi: virgülle ayrılmış ID'leri parse et
        izin_listesi_raw = self.tg_izin_e.text().strip()
        izin_listesi = [x.strip() for x in izin_listesi_raw.split(",")
                        if x.strip()] if izin_listesi_raw else []

        ayar = {
            "token": self.tg_token_e.text().strip(),
            "bot_username": self.tg_bot_user_e.text().strip(),
            "chat_id": self.tg_chat_e.text().strip(),
            "api_id": self.tg_api_id_e.text().strip(),
            "api_hash": self.tg_api_hash_e.text().strip(),
            "session_name": self.tg_session_e.text().strip(),
            "agent_chat": self.tg_agent_chat_e.text().strip(),
            "aktif": self.tg_aktif_cb.isChecked(),
            "tor": self.tg_tor_cb.isChecked(),
            "komut_al": self.tg_komut_cb.isChecked(),
            "yanit_gonder": self.tg_yanit_cb.isChecked(),
            "log_gonder": self.tg_log_cb.isChecked(),
            "uzuv_bildir": self.tg_uzuv_cb.isChecked(),
            "log_filtre": self.tg_filtre_e.text().strip(),
            "izin_bilincler": izin,
            "herkese_acik": self.tg_herkese_cb.isChecked(),
            "izin_listesi": izin_listesi,
            "pc_tg_bildir": (self.tg_pc_tg_bildir_cb.isChecked()
                             if hasattr(self, 'tg_pc_tg_bildir_cb') else True),
            "tg_pc_konus":  (self.tg_tg_pc_konus_cb.isChecked()
                             if hasattr(self, 'tg_tg_pc_konus_cb') else False),
            "ses_pc_konus": (self.tg_ses_pc_konus_cb.isChecked()
                             if hasattr(self, 'tg_ses_pc_konus_cb') else False),
        }
        self.cekirdek.telegram_yeniden_baslat(ayar)
        durum = "✓ Aktif" if ayar['aktif'] else "○ Pasif"
        self.tg_durum_lbl.setText(f"◈ {durum} | Chat: {ayar['chat_id'] or '—'}")

    def _telegram_test(self):
        token = self.tg_token_e.text().strip()
        chat_id = self.tg_chat_e.text().strip()
        if not token or not chat_id:
            QMessageBox.warning(self, "Uyarı", "Token ve Chat ID girilmeli.")
            return
        def _gonder():
            try:
                import requests
                proxies = ({"https": "socks5h://127.0.0.1:9050"}
                           if self.tg_tor_cb.isChecked() else None)
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                r = requests.post(
                    url, json={"chat_id": chat_id,
                               "text": "🤖 Zihin Köprüsü bağlantı testi başarılı!"},
                    proxies=proxies, timeout=15)
                if r.status_code == 200:
                    self.sinyal.log_geldi.emit(
                        "BİLGİ", "TELEGRAM", "Test mesajı gönderildi ✓")
                    QTimer.singleShot(0, lambda: self.tg_durum_lbl.setText("✓ Bağlantı başarılı"))
                else:
                    self.sinyal.log_geldi.emit(
                        "HATA", "TELEGRAM", f"HTTP {r.status_code}")
                    QTimer.singleShot(0, lambda: self.tg_durum_lbl.setText(f"✗ HTTP {r.status_code}"))
            except Exception as e:
                self.sinyal.log_geldi.emit("HATA", "TELEGRAM", str(e))
                QTimer.singleShot(0, lambda e=e: self.tg_durum_lbl.setText(f"✗ {e}"))
        threading.Thread(target=_gonder, daemon=True).start()

    # ── Tor ──────────────────────────────────────────────────────────────────

    def _tor_baslat(self):
        if not self.cekirdek: return
        self.tor_durum_lbl.setText("▶ Başlatılıyor...")
        def _calistir():
            ok = self.cekirdek.tor.baslat()
            QTimer.singleShot(0, lambda: self.tor_durum_lbl.setText("▶ Başlatılıyor..." if ok else "✗ Hata"))
            QTimer.singleShot(3000, self._tor_durum_guncelle)
        threading.Thread(target=_calistir, daemon=True).start()

    def _tor_durdur(self):
        if not self.cekirdek: return
        self.cekirdek.tor.durdur()
        self.tor_durum_lbl.setText("■ Durduruldu")

    def _tor_yeniden(self):
        if not self.cekirdek: return
        self.tor_durum_lbl.setText("⟳ Yeniden başlatılıyor...")
        def _calistir():
            self.cekirdek.tor.yeniden_baslat()
            QTimer.singleShot(4000, self._tor_durum_guncelle)
        threading.Thread(target=_calistir, daemon=True).start()

    def _tor_durum_guncelle(self):
        if not self.cekirdek: return
        durum = self.cekirdek.tor.durum_al()
        renk = R["yesil"] if durum["calisiyor"] else R["metin3"]
        self.tor_durum_lbl.setText(
            f"<span style='color:{renk}'>{'🟢 Çalışıyor' if durum['calisiyor'] else '🔴 Durdurulmuş'}</span>")
        self.tor_ssh_lbl.setText(durum["ssh_onion"] or "—")
        self.tor_web_lbl.setText(durum["web_onion"] or "—")

    def _torrc_yukle(self):
        if not self.cekirdek: return
        icerik = self.cekirdek.tor.torrc_oku()
        self.torrc_edit.setPlainText(icerik)

    def _torrc_kaydet(self):
        if not self.cekirdek: return
        icerik = self.torrc_edit.toPlainText()
        ok = self.cekirdek.tor.torrc_kaydet(icerik)
        self.statusBar().showMessage(
            "torrc kaydedildi." if ok else "torrc kaydetme hatası!")

    def _web_dizin_ac(self):
        if not self.cekirdek: return
        import subprocess
        subprocess.Popen(["xdg-open", self.cekirdek.tor.web_dizini])

    # ── Plugin ───────────────────────────────────────────────────────────────

    def _plugin_magaza_tara(self):
        if not self.cekirdek: return
        self.plugin_durum_lbl.setText("Mağaza taranıyor...")
        def _cb(liste):
            self.plugin_magaza_lst.clear()
            for p in liste:
                item = QListWidgetItem(f"⬡ {p.get('ad','')} v{p.get('versiyon','')}")
                item.setData(Qt.ItemDataRole.UserRole, p)
                self.plugin_magaza_lst.addItem(item)
            self.plugin_durum_lbl.setText(f"{len(liste)} plugin bulundu.")
        self.cekirdek.plugin.magaza_listesi_al(callback=_cb)

    def _plugin_indir(self):
        item = self.plugin_magaza_lst.currentItem()
        if not item or not self.cekirdek: return
        p_dict = item.data(Qt.ItemDataRole.UserRole)
        from .plugin_yoneticisi import Plugin
        p = Plugin(**{k: v for k, v in p_dict.items()
                      if k in Plugin.__dataclass_fields__})
        # İlk boş slotu bul
        slot_kl = None
        for sid, s in self.cekirdek.eklenti.slotlar.items():
            py_list = [f for f in os.listdir(s["klasor"])
                       if f.endswith(".py")] if os.path.isdir(s["klasor"]) else []
            if not py_list:
                slot_kl = s["klasor"]; break
        if not slot_kl:
            QMessageBox.warning(self, "Uyarı", "Boş slot yok.")
            return
        self.plugin_durum_lbl.setText(f"İndiriliyor: {p.ad}...")
        def _cb(ok):
            msg = f"✓ {p.ad} kuruldu." if ok else f"✗ {p.ad} kurulamadı."
            self.plugin_durum_lbl.setText(msg)
            if ok: self._plugin_kurulu_listele()
        self.cekirdek.plugin.plugin_indir(p, slot_kl, _cb)

    def _plugin_kurulu_listele(self):
        if not self.cekirdek: return
        self.plugin_kurulu_lst.clear()
        for p in self.cekirdek.plugin.yerel_pluginler():
            item = QListWidgetItem(f"{'✓' if p.aktif else '○'} {p.ad} v{p.versiyon}")
            item.setData(Qt.ItemDataRole.UserRole, p.id)
            self.plugin_kurulu_lst.addItem(item)

    def _plugin_kaldir(self):
        item = self.plugin_kurulu_lst.currentItem()
        if not item or not self.cekirdek: return
        pid = item.data(Qt.ItemDataRole.UserRole)
        if (QMessageBox.question(self, "Kaldır", f"'{pid}' kaldırılsın mı?") ==
                QMessageBox.StandardButton.Yes):
            self.cekirdek.plugin.plugin_kaldir(pid)
            self._plugin_kurulu_listele()

    def _plugin_guncelle(self):
        item = self.plugin_kurulu_lst.currentItem()
        if not item or not self.cekirdek: return
        pid = item.data(Qt.ItemDataRole.UserRole)
        self.plugin_durum_lbl.setText(f"Güncelleniyor: {pid}...")
        self.cekirdek.plugin.plugin_guncelle(
            pid, lambda ok: self.plugin_durum_lbl.setText(
                f"{'✓' if ok else '✗'} Güncelleme tamamlandı."))

    # ── Güncelleme ───────────────────────────────────────────────────────────


    def _hava_al(self):
        if not self.cekirdek: return
        sehir = self.hava_sehir_e.text().strip() or "Istanbul"
        self.hava_metin.setText("⏳ Alınıyor...")
        def _cb(sonuc):
            self.hava_metin.setText(sonuc)
        self.cekirdek.hava_takvim.hava.hava_al(sehir, callback=_cb)

    def _hava_3_gun(self):
        if not self.cekirdek: return
        sehir = self.hava_sehir_e.text().strip() or "Istanbul"
        def _cek():
            sonuc = self.cekirdek.hava_takvim.hava.uc_gun_tahmin(sehir)
            self.hava_metin.setText(sonuc)
        threading.Thread(target=_cek, daemon=True).start()

    def _takvim_bugun(self):
        if not self.cekirdek: return
        ozet = self.cekirdek.hava_takvim.takvim.ozet_metin()
        self.takvim_metin.setPlainText(ozet)

    def _takvim_yakin(self):
        if not self.cekirdek: return
        ozet = self.cekirdek.hava_takvim.takvim.ozet_metin()
        self.takvim_metin.setPlainText(ozet)

    def _takvim_ekle(self):
        if not self.cekirdek: return
        baslik = self.takvim_baslik_e.text().strip()
        tarih  = self.takvim_tarih_e.text().strip()
        saat   = self.takvim_saat_e.text().strip()
        if not baslik or not tarih:
            return
        e = self.cekirdek.hava_takvim.takvim.etkinlik_ekle(
            baslik, tarih, saat)
        self.takvim_baslik_e.clear()
        self.takvim_tarih_e.clear()
        self.takvim_saat_e.clear()
        self.takvim_metin.append(
            f"✓ Eklendi: {e['baslik']} — {e['tarih']}")

    def _guncelleme_kontrol(self):
        if not self.cekirdek: return
        url = self.guncelleme_url_e.text().strip()
        if not url:
            QMessageBox.warning(self, "Uyarı", "Güncelleme URL'si girilmeli.")
            return
        self.guncelleme_bilgi.setText("Kontrol ediliyor...")
        def _cek():
            sonuc = self.cekirdek.guncelleme_kontrol(url)
            if sonuc:
                metin = "\n".join(f"{k}: {v}" for k, v in sonuc.items())
            else:
                metin = "Güncelleme bilgisi alınamadı veya mevcut sürüm güncel."
            self.guncelleme_bilgi.setText(metin)
        threading.Thread(target=_cek, daemon=True).start()

    def _guncelleme_uygula(self):
        if not self.cekirdek: return
        url = self.guncelleme_url_e.text().strip()
        if not url: return
        r = QMessageBox.question(
            self, "Güncelleme",
            "Güncelleme indirilip uygulanacak. Devam edilsin mi?")
        if r != QMessageBox.StandardButton.Yes: return
        self.guncelleme_bilgi.setText("İndiriliyor...")
        def _indir():
            ok = self.cekirdek.guncelleme_uygula(url)
            self.guncelleme_bilgi.setText(
                "✓ Güncelleme uygulandı. Lütfen yeniden başlatın."
                if ok else "✗ Güncelleme başarısız.")
        threading.Thread(target=_indir, daemon=True).start()

    # ── Eklenti ──────────────────────────────────────────────────────────────

    def _tum_slotlari_durdur(self):
        if self.cekirdek:
            for sid in self.cekirdek.eklenti.slotlar:
                self.cekirdek.eklenti.slot_durdur(sid)

    def _slot_calistir(self, slot_id):
        if self.cekirdek:
            self.cekirdek.eklenti.slot_calistir(slot_id)

    def _slot_klasor_ac(self, slot_id):
        if self.cekirdek:
            self.cekirdek.eklenti.klasor_ac(slot_id)


    def _amplitud_guncelle(self, deger: float):
        """Ses dalgası animasyonu için amplitüd değerini ilet."""
        if hasattr(self, 'ses_dalgasi'):
            self.ses_dalgasi.amplitud_guncelle(deger)

    def _wake_word_isle(self, kelime: str):
        """Wake word algılandığında görsel geri bildirim."""
        if hasattr(self, 'ses_dalgasi'):
            self.ses_dalgasi.wake_word_tetiklendi()
        # Bilinç kartı flash efekti
        if hasattr(self, 'bilinc_lbl'):
            renk_orig = self.bilinc_lbl.styleSheet()
            self.bilinc_lbl.setStyleSheet(
                f"color:{R['yesil']};font-size:18px;font-weight:bold;")
            QTimer.singleShot(400, lambda:
                self.bilinc_lbl.setStyleSheet(renk_orig))
        self.statusBar().showMessage(
            f"⚡ Wake word: '{kelime}' — Dinliyorum...", 2000)

    def _wake_word_toggled(self, aktif: bool):
        """Wake word checkbox toggled."""
        if not self.cekirdek:
            return
        self.cekirdek.wake_word_modu_ayarla(aktif)
        self.cekirdek.beyin.setdefault("ses", {})
        self.cekirdek.beyin["ses"]["wake_word_aktif"] = bool(aktif)
        self.cekirdek.beyin_kaydet()
        durum = "aktif" if aktif else "pasif"
        self.statusBar().showMessage(
            f"Wake word modu: {durum}", 2000)
        self.sinyal.log_geldi.emit(
            "BİLGİ", "WAKE", f"Wake word modu: {durum}")

    def _gelistirici_modu_toggled(self, aktif: bool):
        if not self.cekirdek:
            return
        self.cekirdek.beyin.setdefault("arayuz", {})
        onceki = bool(self.cekirdek.beyin["arayuz"].get("gelistirici_modu", False))
        self.cekirdek.beyin["arayuz"]["gelistirici_modu"] = bool(aktif)
        self.cekirdek.beyin_kaydet()
        durum = "açık" if aktif else "kapalı"
        self.statusBar().showMessage(
            f"Geliştirici araçları: {durum}. Sekmeler yeniden başlatınca güncellenir.",
            3000)
        if onceki != bool(aktif):
            self.sinyal.log_geldi.emit(
                "BİLGİ", "ARAYÜZ", f"Geliştirici araçları: {durum}")

    def closeEvent(self, event):
        if self.cekirdek:
            try:
                self.cekirdek.aktif_bilinc_kaydet()
                self.cekirdek.durdur()
            except Exception:
                pass
        super().closeEvent(event)

    # ── Günlük ───────────────────────────────────────────────────────────────

    def _gunlugu_kaydet(self):
        f, _ = QFileDialog.getSaveFileName(
            self, "Günlüğü Kaydet", "", "Metin (*.txt);;Tümü (*)")
        if f:
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(self.log_paneli.toPlainText())


# ── Başlatıcı ────────────────────────────────────────────────────────────────
import sys as _sys
import traceback as _tb

def _global_exception_handler(exc_type, exc_val, exc_tb):
    """Yakalanmamış exception'ları log dosyasına yaz."""
    if issubclass(exc_type, KeyboardInterrupt):
        _sys.__excepthook__(exc_type, exc_val, exc_tb)
        return
    hata = "".join(_tb.format_exception(exc_type, exc_val, exc_tb))
    try:
        import os as _os
        from datetime import datetime as _dt
        log_dosya = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            "loglar", "crash.log")
        _os.makedirs(_os.path.dirname(log_dosya), exist_ok=True)
        with open(log_dosya, "a") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"{_dt.now()} CRASH:\n{hata}")
        print(f"[CRASH] Hata log: {log_dosya}\n{hata}")
    except Exception:
        print(f"[CRASH] {hata}")

_sys.excepthook = _global_exception_handler


def goster(cekirdek=None):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(R["arkaplan"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(R["metin"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(R["panel"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(R["panel2"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(R["metin"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(R["panel2"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(R["metin"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(R["vurgu"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(R["arkaplan"]))
    app.setPalette(palette)
    pencere = AnaArayuz(cekirdek)
    pencere.show()
    return app, pencere


if __name__ == "__main__":
    app, pencere = goster()
    sys.exit(app.exec())
