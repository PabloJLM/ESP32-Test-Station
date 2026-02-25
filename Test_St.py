#!/usr/bin/env python3
"""
ESP32 Visual Tester
Requiere: pip install pyserial PyQt5
"""

import sys
import math
import serial
import serial.tools.list_ports
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QGroupBox, QPushButton, QLabel, QComboBox,
    QLineEdit, QTextEdit, QSlider, QFrame, QStatusBar,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import (
    QFont, QColor, QTextCursor, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient,
)

# ─── Protocolo ────────────────────────────────────────────────
CMD_PWM      = 0x01
CMD_DIGITAL  = 0x02
CMD_SERVO    = 0x03
CMD_NEOPIXEL = 0x04
CMD_PING     = 0xF0
CMD_RESET    = 0xFF

RESPONSES = {
    0xAA: "PONG / OK",
    0x01: "PWM OK",
    0x02: "DIGITAL OK",
    0x03: "SERVO OK",
    0x04: "NEOPIXEL OK",
    0xBB: "RESET OK",
    0xEE: "ERROR",
}

# ═══════════════════════════════════════════════════════════════
# WIDGETS VISUALES CUSTOM
# ═══════════════════════════════════════════════════════════════

class LedWidget(QWidget):
    def __init__(self, label="", color_on="#2ecc71", size=18, parent=None):
        super().__init__(parent)
        self._on = False
        self._color_on  = QColor(color_on)
        self._color_off = QColor("#d1d5db")
        self._label = label
        self._size  = size
        total_w = size + 4 + (QFont("Segoe UI", 9).pointSize() * len(label) // 1 + 10 if label else 0)
        self.setFixedSize(max(size + 4, size + 6 + len(label) * 7), size + 6)

    def set_on(self, state: bool):
        self._on = state
        self.update()

    def is_on(self):
        return self._on

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self._size
        c = self._color_on if self._on else self._color_off

        if self._on:
            glow = QRadialGradient(s // 2 + 2, s // 2 + 2, s)
            gc = QColor(c); gc.setAlpha(50)
            glow.setColorAt(0, gc); glow.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(glow)); p.setPen(Qt.NoPen)
            p.drawEllipse(0, 0, s + 4, s + 4)

        grad = QRadialGradient(s // 2 - 1, s // 2 - 1, s // 2)
        grad.setColorAt(0, c)
        grad.setColorAt(1, QColor(max(0, c.red()-80), max(0, c.green()-80), max(0, c.blue()-80)))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor("#9ca3af"), 1))
        p.drawEllipse(2, 2, s, s)

        p.setBrush(QBrush(QColor(255, 255, 255, 80))); p.setPen(Qt.NoPen)
        p.drawEllipse(s // 2 - 2, 4, s // 3, s // 5)

        if self._label:
            p.setPen(QColor("#374151"))
            f = QFont("Segoe UI", 9)
            p.setFont(f)
            p.drawText(s + 8, 0, 200, s + 6, Qt.AlignVCenter | Qt.AlignLeft, self._label)
        p.end()


class MotorBar(QWidget):
    def __init__(self, motor_id, parent=None):
        super().__init__(parent)
        self._value = 0
        self.setMinimumSize(120, 36)
        self.setMaximumHeight(36)

    def set_value(self, v):
        self._value = max(0, min(255, v))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pct = self._value / 255.0
        track_y, track_h = 18, 12

        p.setBrush(QColor("#f1f5f9")); p.setPen(QPen(QColor("#e2e8f0"), 1))
        p.drawRoundedRect(0, track_y, w, track_h, 6, 6)

        if pct > 0:
            bw = max(12, int(w * pct))
            g = QLinearGradient(0, 0, bw, 0)
            if pct < 0.4:
                g.setColorAt(0, QColor("#34d399")); g.setColorAt(1, QColor("#10b981"))
            elif pct < 0.75:
                g.setColorAt(0, QColor("#fbbf24")); g.setColorAt(1, QColor("#f59e0b"))
            else:
                g.setColorAt(0, QColor("#f87171")); g.setColorAt(1, QColor("#ef4444"))
            p.setBrush(QBrush(g)); p.setPen(Qt.NoPen)
            p.drawRoundedRect(0, track_y, bw, track_h, 6, 6)

        p.setPen(QColor("#64748b"))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(0, 0, w, track_y - 1, Qt.AlignRight | Qt.AlignBottom,
                   f"{self._value}  ({int(pct*100)}%)")
        p.end()


class ServoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 90
        self.setFixedSize(170, 110)

    def set_angle(self, angle):
        self._angle = max(0, min(180, angle))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h - 12
        r = 72

        p.setPen(QPen(QColor("#e2e8f0"), 9, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx - r, cy - r, r*2, r*2, 0*16, 180*16)

        p.setPen(QPen(QColor("#3b82f6"), 9, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx - r, cy - r, r*2, r*2, 0*16, int(self._angle)*16)

        rad = math.radians(180 - self._angle)
        nl = 58
        nx = cx + nl * math.cos(rad)
        ny = cy - nl * math.sin(rad)
        p.setPen(QPen(QColor("#1e293b"), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(cx, cy, int(nx), int(ny))

        p.setBrush(QColor("#1e293b")); p.setPen(Qt.NoPen)
        p.drawEllipse(cx-6, cy-6, 12, 12)
        p.setBrush(QColor("#93c5fd")); p.drawEllipse(cx-3, cy-3, 6, 6)

        p.setPen(QColor("#94a3b8")); p.setFont(QFont("Segoe UI", 8))
        p.drawText(cx - r - 8, cy - 4, "0°")
        p.drawText(cx - 10, cy - r - 16, "90°")
        p.drawText(cx + r - 12, cy - 4, "180°")

        p.setPen(QColor("#1e293b")); p.setFont(QFont("Segoe UI", 12, QFont.Bold))
        p.drawText(0, cy - 34, w, 20, Qt.AlignHCenter, f"{self._angle}°")
        p.end()


class NeoPixelWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#d1d5db")
        self.setFixedSize(90, 90)

    def set_color(self, color: QColor):
        self._color = color
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy, r = w//2, h//2, 30

        is_lit = self._color.value() > 40
        if is_lit:
            for i in range(4):
                gc = QColor(self._color); gc.setAlpha(max(0, 45 - i*12))
                p.setBrush(QBrush(gc)); p.setPen(Qt.NoPen)
                er = r + 10 + i * 5
                p.drawEllipse(cx - er, cy - er, er*2, er*2)

        grad = QRadialGradient(cx-4, cy-4, r)
        bright = QColor(self._color)
        dark = QColor(max(0, bright.red()-90), max(0, bright.green()-90), max(0, bright.blue()-90))
        grad.setColorAt(0, bright); grad.setColorAt(1, dark)
        p.setBrush(QBrush(grad)); p.setPen(QPen(QColor("#9ca3af"), 1))
        p.drawEllipse(cx-r, cy-r, r*2, r*2)

        p.setBrush(QColor(255,255,255,90)); p.setPen(Qt.NoPen)
        p.drawEllipse(cx-r//2, cy-r+5, r-4, r//3)
        p.end()


# ═══════════════════════════════════════════════════════════════
# SERIAL READER THREAD
# ═══════════════════════════════════════════════════════════════

class SerialReader(QThread):
    data_received   = pyqtSignal(str)
    byte_received   = pyqtSignal(int)
    connection_lost = pyqtSignal()

    def __init__(self, ser):
        super().__init__()
        self.ser = ser
        self._running = True
        self._buf = bytearray()

    def run(self):
        while self._running:
            try:
                if self.ser and self.ser.is_open:
                    n = self.ser.in_waiting
                    if n:
                        self._buf.extend(self.ser.read(n))
                        self._flush()
                self.msleep(15)
            except Exception:
                self.connection_lost.emit()
                break

    def _flush(self):
        while self._buf:
            for sep in (b'\r\n', b'\n'):
                idx = self._buf.find(sep)
                if idx != -1:
                    line = self._buf[:idx].decode('latin-1', errors='replace').strip()
                    self._buf = self._buf[idx+len(sep):]
                    if line:
                        self.data_received.emit(line)
                    return
            b = self._buf[0]
            if not (0x20 <= b <= 0x7E) and b not in (0x09, 0x0A, 0x0D):
                self._buf.pop(0)
                self.byte_received.emit(b)
                return
            break

    def stop(self):
        self._running = False
        self.wait()


# ═══════════════════════════════════════════════════════════════
# VENTANA PRINCIPAL
# ═══════════════════════════════════════════════════════════════

class ESP32Tester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ser = None
        self.reader = None
        self.setWindowTitle("ESP32 Board Tester")
        self.setMinimumSize(1080, 740)
        self._build_ui()
        self._apply_style()
        self._refresh_ports()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._build_header())

        body = QWidget(); body.setObjectName("body")
        b_lay = QHBoxLayout(body)
        b_lay.setContentsMargins(16, 16, 16, 16)
        b_lay.setSpacing(14)

        # Columna izquierda: controles
        left = QWidget(); left.setMaximumWidth(380)
        ll = QVBoxLayout(left); ll.setSpacing(10); ll.setContentsMargins(0,0,0,0)
        ll.addWidget(self._panel_motors())
        ll.addWidget(self._panel_servo())
        ll.addWidget(self._panel_neo_send())
        ll.addWidget(self._panel_commands())
        ll.addStretch()
        b_lay.addWidget(left)

        # Columna derecha: feedback + log
        right = QWidget()
        rl = QVBoxLayout(right); rl.setSpacing(10); rl.setContentsMargins(0,0,0,0)
        rl.addWidget(self._panel_feedback())
        rl.addWidget(self._panel_log(), 1)
        b_lay.addWidget(right, 1)

        root.addWidget(body, 1)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Selecciona un puerto y presiona Conectar.")

    # ── Header ────────────────────────────────────────────────
    def _build_header(self):
        h = QWidget(); h.setObjectName("header"); h.setFixedHeight(60)
        lay = QHBoxLayout(h); lay.setContentsMargins(20, 0, 20, 0); lay.setSpacing(10)

        title = QLabel("ESP32  Board Tester"); title.setObjectName("appTitle")
        lay.addWidget(title); lay.addSpacing(20)

        for lbl_text, widget_attr, items, default in [
            ("Puerto", "port_combo", [], None),
            ("Baud",   "baud_combo", ["9600","57600","115200","230400"], "9600"),
            ("Modo",   "mode_combo", ["Maestro (texto)","Slave (binario)"], None),
        ]:
            lay.addWidget(self._hlbl(lbl_text))
            cb = QComboBox()
            if items: cb.addItems(items)
            if default: cb.setCurrentText(default)
            setattr(self, widget_attr, cb)
            lay.addWidget(cb)

        btn_ref = QPushButton("↻"); btn_ref.setObjectName("btnIcon")
        btn_ref.setFixedSize(34, 34); btn_ref.setToolTip("Refrescar puertos")
        btn_ref.clicked.connect(self._refresh_ports); lay.addWidget(btn_ref)
        lay.addStretch()

        self.led_conn = LedWidget("", "#22c55e", 14)
        lay.addWidget(self.led_conn)
        self.lbl_conn = QLabel("Desconectado"); self.lbl_conn.setObjectName("connText")
        lay.addWidget(self.lbl_conn)
        lay.addSpacing(4)

        self.btn_connect = QPushButton("Conectar")
        self.btn_connect.setObjectName("btnConnect")
        self.btn_connect.setCheckable(True)
        self.btn_connect.setFixedWidth(115)
        self.btn_connect.clicked.connect(self._toggle_connection)
        lay.addWidget(self.btn_connect)
        return h

    def _hlbl(self, t):
        l = QLabel(t); l.setObjectName("hlbl"); return l

    # ── Panel Motores ─────────────────────────────────────────
    def _panel_motors(self):
        box = self._card("Motores — PWM")
        g = QGridLayout(); g.setSpacing(6)
        self._pwm_sliders = {}; self._fb_bars = {}

        for i, m in enumerate([1,2,3,4]):
            ml = QLabel(f"M{m}"); ml.setObjectName("motorLbl"); ml.setFixedWidth(20)
            sl = QSlider(Qt.Horizontal); sl.setRange(0,255); sl.setValue(0)
            bar = MotorBar(m); bar.setFixedWidth(95)
            btn = QPushButton("→"); btn.setObjectName("btnSend"); btn.setFixedSize(28,28)
            btn.setToolTip(f"Enviar PWM Motor {m}")
            sl.valueChanged.connect(lambda v, b=bar: b.set_value(v))
            btn.clicked.connect(lambda _, mo=m: self._send_pwm(mo))
            self._pwm_sliders[m] = sl; self._fb_bars[m] = bar
            g.addWidget(ml,  i, 0); g.addWidget(sl,  i, 1)
            g.addWidget(bar, i, 2); g.addWidget(btn, i, 3)

        box.layout().addLayout(g)
        return box

    # ── Panel Servo ───────────────────────────────────────────
    def _panel_servo(self):
        box = self._card("Servo")
        row = QHBoxLayout(); row.setSpacing(8)
        self.servo_slider = QSlider(Qt.Horizontal)
        self.servo_slider.setRange(0,180); self.servo_slider.setValue(90)
        self.servo_val_lbl = QLabel("90°"); self.servo_val_lbl.setObjectName("bigVal")
        self.servo_val_lbl.setFixedWidth(38); self.servo_val_lbl.setAlignment(Qt.AlignCenter)
        btn = QPushButton("Enviar"); btn.setObjectName("btnAction2"); btn.setFixedWidth(70)
        btn.clicked.connect(self._send_servo)
        self.servo_slider.valueChanged.connect(lambda v: self.servo_val_lbl.setText(f"{v}°"))
        row.addWidget(self.servo_slider); row.addWidget(self.servo_val_lbl); row.addWidget(btn)
        box.layout().addLayout(row)
        return box

    # ── Panel NeoPixel envío ──────────────────────────────────
    def _panel_neo_send(self):
        box = self._card("NeoPixel")
        row = QHBoxLayout(); row.setSpacing(6)
        colors = [
            ("OFF",    "#9ca3af", "#555",    0x00),
            ("Rojo",   "#ef4444", "white",   0x01),
            ("Verde",  "#22c55e", "white",   0x02),
            ("Azul",   "#3b82f6", "white",   0x03),
            ("Blanco", "#f1f5f9", "#1e293b", 0xFF),
        ]
        for label, bg, fg, val in colors:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton{{background:{bg};color:{fg};border:none;border-radius:7px;"
                f"padding:7px 4px;font-weight:600;font-size:11px;}}"
                f"QPushButton:hover{{opacity:0.8;}}"
            )
            btn.clicked.connect(lambda _, v=val: self._send_neopixel(v))
            row.addWidget(btn)
        box.layout().addLayout(row)
        return box

    # ── Panel Comandos ────────────────────────────────────────
    def _panel_commands(self):
        box = self._card("Comandos")
        lay = box.layout()

        r1 = QHBoxLayout(); r1.setSpacing(8)
        for lbl, fn, obj in [("Ping", self._send_ping, "btnAction"),
                               ("Reset", self._send_reset, "btnDanger")]:
            b = QPushButton(lbl); b.setObjectName(obj); b.clicked.connect(fn)
            r1.addWidget(b)
        lay.addLayout(r1)

        sep = QLabel("Dirección motores (Digital)"); sep.setObjectName("sectionLbl")
        lay.addWidget(sep)

        dg = QGridLayout(); dg.setSpacing(5)
        pins = [("M1 AIN1",0x11),("M1 AIN2",0x12),("M2 AIN1",0x21),("M2 AIN2",0x22),
                ("M3 AIN1",0x31),("M3 AIN2",0x32),("M4 AIN1",0x41),("M4 AIN2",0x42)]
        self._dig_leds = {}
        for i, (name, pid) in enumerate(pins):
            led = LedWidget(name, "#6366f1", 13)
            b1 = QPushButton("1"); b1.setObjectName("btnTiny"); b1.setFixedSize(26,22)
            b0 = QPushButton("0"); b0.setObjectName("btnTiny"); b0.setFixedSize(26,22)
            b1.clicked.connect(lambda _, p=pid, l=led: (self._send_digital(p,1), l.set_on(True)))
            b0.clicked.connect(lambda _, p=pid, l=led: (self._send_digital(p,0), l.set_on(False)))
            self._dig_leds[pid] = led
            r, c = divmod(i, 2); base = c * 3
            dg.addWidget(led, r, base); dg.addWidget(b1, r, base+1); dg.addWidget(b0, r, base+2)
        lay.addLayout(dg)

        sep2 = QLabel("Comando libre"); sep2.setObjectName("sectionLbl")
        lay.addWidget(sep2)

        raw_row = QHBoxLayout()
        self.raw_input = QLineEdit()
        self.raw_input.setPlaceholderText("ping / pwm 1 200 / servo 90 / neo 2")
        self.raw_input.returnPressed.connect(self._send_raw)
        bsend = QPushButton("↵"); bsend.setObjectName("btnSend"); bsend.setFixedSize(32,32)
        bsend.clicked.connect(self._send_raw)
        raw_row.addWidget(self.raw_input); raw_row.addWidget(bsend)
        lay.addLayout(raw_row)
        return box

    # ── Panel Feedback ────────────────────────────────────────
    def _panel_feedback(self):
        box = self._card("Retroalimentación — estado del Slave")
        row = QHBoxLayout(); row.setSpacing(16)

        # NeoPixel visual
        nc = QVBoxLayout(); nc.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.neo_widget = NeoPixelWidget()
        self.neo_label  = QLabel("NeoPixel  —  OFF")
        self.neo_label.setAlignment(Qt.AlignHCenter)
        self.neo_label.setObjectName("fbTitle")
        nc.addWidget(self.neo_widget, 0, Qt.AlignHCenter)
        nc.addWidget(self.neo_label)
        row.addLayout(nc)

        # Servo visual
        sc = QVBoxLayout(); sc.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.servo_indicator = ServoWidget()
        srv_lbl = QLabel("Servo"); srv_lbl.setAlignment(Qt.AlignHCenter)
        srv_lbl.setObjectName("fbTitle")
        sc.addWidget(self.servo_indicator, 0, Qt.AlignHCenter)
        sc.addWidget(srv_lbl)
        row.addLayout(sc)

        # LEDs de respuesta
        resp_c = QVBoxLayout(); resp_c.setAlignment(Qt.AlignTop); resp_c.setSpacing(6)
        resp_title = QLabel("Respuestas"); resp_title.setObjectName("fbTitle")
        resp_c.addWidget(resp_title)

        self._resp_leds = {}
        resp_map = {
            0xAA: ("PONG",        "#22c55e"),
            0x01: ("PWM OK",      "#3b82f6"),
            0x02: ("Digital OK",  "#8b5cf6"),
            0x03: ("Servo OK",    "#f59e0b"),
            0x04: ("NeoPixel OK", "#ec4899"),
            0xBB: ("Reset OK",    "#06b6d4"),
            0xEE: ("Error",       "#ef4444"),
        }
        for code, (name, color) in resp_map.items():
            led = LedWidget(name, color, 15)
            self._resp_leds[code] = led
            t = QTimer(self); t.setSingleShot(True)
            t.timeout.connect(lambda l=led: l.set_on(False))
            led._timer = t
            resp_c.addWidget(led)
        row.addLayout(resp_c)

        # PWM feedback bars
        pwm_c = QVBoxLayout(); pwm_c.setAlignment(Qt.AlignTop); pwm_c.setSpacing(4)
        pwm_title = QLabel("PWM enviado"); pwm_title.setObjectName("fbTitle")
        pwm_c.addWidget(pwm_title)
        self._fb_bars2 = {}
        for m in [1,2,3,4]:
            lm = QLabel(f"M{m}"); lm.setObjectName("motorLbl"); lm.setFixedWidth(18)
            bar = MotorBar(m); bar.setFixedWidth(140)
            hr = QHBoxLayout(); hr.addWidget(lm); hr.addWidget(bar)
            pwm_c.addLayout(hr)
            self._fb_bars2[m] = bar
        row.addLayout(pwm_c)

        box.layout().addLayout(row)
        return box

    # ── Panel Log ─────────────────────────────────────────────
    def _panel_log(self):
        box = self._card("Log serial")
        lay = box.layout()
        hr = QHBoxLayout()
        sub = QLabel("Mensajes del dispositivo"); sub.setObjectName("sectionLbl")
        bc = QPushButton("Limpiar"); bc.setObjectName("btnAction2"); bc.setFixedWidth(68)
        bc.clicked.connect(lambda: self.terminal.clear())
        hr.addWidget(sub); hr.addStretch(); hr.addWidget(bc)
        lay.addLayout(hr)
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFont(QFont("Courier New", 9))
        self.terminal.setObjectName("terminal")
        lay.addWidget(self.terminal)
        return box

    # ── Card helper ───────────────────────────────────────────
    def _card(self, title=""):
        w = QGroupBox(title); w.setObjectName("card")
        lay = QVBoxLayout(w); lay.setSpacing(8); lay.setContentsMargins(12,14,12,12)
        return w

    # ── Estilo ────────────────────────────────────────────────
    def _apply_style(self):
        self.setStyleSheet("""
        * { font-family: 'Segoe UI', Arial, sans-serif; }
        QMainWindow, QWidget { background: #f1f5f9; color: #1e293b; }

        #header { background: white; border-bottom: 1px solid #e2e8f0; }
        #body   { background: #f1f5f9; }

        #appTitle { font-size: 17px; font-weight: 700; color: #0f172a; letter-spacing: 0.3px; }
        #hlbl     { font-size: 11px; color: #64748b; font-weight: 500; }
        #connText { font-size: 11px; color: #64748b; }

        #btnConnect {
            background: #2563eb; color: white; border: none;
            border-radius: 8px; padding: 8px 0; font-weight: 600; font-size: 13px;
        }
        #btnConnect:hover   { background: #1d4ed8; }
        #btnConnect:checked { background: #dc2626; }
        #btnConnect:checked:hover { background: #b91c1c; }

        #btnIcon {
            background: #f8fafc; color: #475569;
            border: 1px solid #e2e8f0; border-radius: 8px;
            font-size: 16px; font-weight: bold;
        }
        #btnIcon:hover { background: #f1f5f9; }

        QGroupBox#card {
            background: white; border: 1px solid #e2e8f0;
            border-radius: 12px; margin-top: 16px;
            font-size: 11px; font-weight: 600; color: #64748b;
        }
        QGroupBox#card::title {
            subcontrol-origin: margin; left: 14px; padding: 0 6px; background: white;
        }

        QPushButton {
            background: #f8fafc; color: #334155;
            border: 1px solid #e2e8f0; border-radius: 7px;
            padding: 6px 14px; font-size: 12px;
        }
        QPushButton:hover   { background: #f1f5f9; border-color: #cbd5e1; }
        QPushButton:pressed { background: #e2e8f0; }

        #btnAction  { background: #2563eb; color:white; border:none; border-radius:7px; padding:7px 18px; font-weight:600; }
        #btnAction:hover { background: #1d4ed8; }
        #btnDanger  { background: #dc2626; color:white; border:none; border-radius:7px; padding:7px 18px; font-weight:600; }
        #btnDanger:hover { background: #b91c1c; }
        #btnAction2 { background: #f1f5f9; color:#475569; border:1px solid #e2e8f0; border-radius:6px; padding:5px 10px; font-size:11px; }
        #btnSend    { background: #2563eb; color:white; border:none; border-radius:7px; font-weight:700; font-size:13px; }
        #btnSend:hover { background: #1d4ed8; }
        #btnTiny    { background: #f8fafc; border:1px solid #e2e8f0; border-radius:5px; font-size:10px; padding:1px 2px; color:#334155; }

        #motorLbl   { font-size: 11px; font-weight: 700; color: #475569; }
        #bigVal     { font-size: 14px; font-weight: 700; color: #0f172a; }
        #sectionLbl { font-size: 10px; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin-top: 4px; }
        #fbTitle    { font-size: 11px; font-weight: 600; color: #64748b; }

        QComboBox {
            background: #f8fafc; color: #1e293b;
            border: 1px solid #e2e8f0; border-radius: 7px;
            padding: 5px 10px; font-size: 12px; min-width: 110px;
        }
        QComboBox:hover { border-color: #2563eb; }
        QComboBox::drop-down { border: none; width: 18px; }

        QLineEdit {
            background: #f8fafc; color: #1e293b;
            border: 1px solid #e2e8f0; border-radius: 7px;
            padding: 6px 10px; font-size: 12px;
        }
        QLineEdit:focus { border-color: #2563eb; background: white; }

        QSlider::groove:horizontal {
            height: 5px; background: #e2e8f0; border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #2563eb; width: 15px; height: 15px;
            margin: -5px 0; border-radius: 8px; border: 2px solid white;
        }
        QSlider::sub-page:horizontal { background: #93c5fd; border-radius: 3px; }

        QTextEdit#terminal {
            background: #0f172a; color: #94a3b8;
            border: 1px solid #1e293b; border-radius: 8px;
            font-family: 'Courier New', monospace; font-size: 10px;
            padding: 4px;
        }
        QStatusBar {
            background: white; color: #94a3b8;
            border-top: 1px solid #e2e8f0; font-size: 11px;
        }
        """)

    # ── Serial ────────────────────────────────────────────────
    def _refresh_ports(self):
        self.port_combo.clear()
        for p in serial.tools.list_ports.comports():
            self.port_combo.addItem(p.device)
        if self.port_combo.count() == 0:
            self.port_combo.addItem("(sin puertos)")

    def _toggle_connection(self, checked):
        self._connect() if checked else self._disconnect()

    def _connect(self):
        port = self.port_combo.currentText()
        baud = int(self.baud_combo.currentText())
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self.reader = SerialReader(self.ser)
            self.reader.data_received.connect(self._on_text)
            self.reader.byte_received.connect(self._on_byte)
            self.reader.connection_lost.connect(self._on_lost)
            self.reader.start()
            self.led_conn.set_on(True)
            self.lbl_conn.setText(port)
            self.btn_connect.setText("Desconectar")
            self.status_bar.showMessage(f"Conectado  ·  {port}  ·  {baud} baud")
            self._log(f"Conectado a {port} @ {baud}", "#22d3ee")
        except Exception as e:
            self.btn_connect.setChecked(False)
            self._log(f"Error al conectar: {e}", "#f87171")
            self.status_bar.showMessage(f"Error: {e}")

    def _disconnect(self):
        if self.reader: self.reader.stop(); self.reader = None
        if self.ser and self.ser.is_open: self.ser.close()
        self.ser = None
        self.led_conn.set_on(False)
        self.lbl_conn.setText("Desconectado")
        self.btn_connect.setText("Conectar")
        self.btn_connect.setChecked(False)
        self.status_bar.showMessage("Desconectado.")
        self._log("Desconectado.", "#f87171")

    def _on_text(self, line):
        skip = ["===","Comandos","  ping","  pwm","  servo","  neo","  digital",
                "  reset","UART a","Estado:"]
        if any(line.startswith(s) for s in skip): return
        # Mostrar respuestas de texto del maestro (→ PWM M1 = 128, etc.)
        self._log(f"← {line}", "#86efac")

    def _on_byte(self, b):
        desc = RESPONSES.get(b, f"0x{b:02X}")
        self._log(f"← {desc}", "#fde68a")
        if b in self._resp_leds:
            led = self._resp_leds[b]
            led.set_on(True)
            led._timer.start(1400)

    def _on_lost(self):
        self._log("Conexión perdida.", "#f87171")
        self._disconnect()

    # ── Envío ─────────────────────────────────────────────────
    def _is_master(self):
        return self.mode_combo.currentIndex() == 0

    def _bytes_to_text(self, cmd, pin_id, value):
        if cmd == CMD_PING:    return "ping"
        if cmd == CMD_RESET:   return "reset"
        if cmd == CMD_PWM:     return f"pwm {pin_id} {value}"
        if cmd == CMD_SERVO:   return f"servo {value}"
        if cmd == CMD_DIGITAL:
            dp = (pin_id >> 4) * 10 + (pin_id & 0x0F)
            return f"digital {dp} {value}"
        if cmd == CMD_NEOPIXEL:
            return f"neo {'ff' if value == 0xFF else value}"
        return f"{cmd} {pin_id} {value}"

    def _send(self, cmd, pin_id, value, desc):
        if not self.ser or not self.ser.is_open:
            self._log("No conectado", "#f87171"); return
        try:
            if self._is_master():
                txt = self._bytes_to_text(cmd, pin_id, value)
                self.ser.write((txt + "\n").encode())
                self._log(f"→ {txt}", "#60a5fa")
            else:
                self.ser.write(bytes([cmd, pin_id, value]))
                self._log(f"→ {desc}", "#60a5fa")
        except Exception as e:
            self._log(f"Error: {e}", "#f87171")

    def _send_ping(self):
        self._send(CMD_PING, 0, 0, "PING")

    def _send_reset(self):
        self._send(CMD_RESET, 0, 0, "RESET")

    def _send_pwm(self, motor):
        val = self._pwm_sliders[motor].value()
        self._fb_bars[motor].set_value(val)
        self._fb_bars2[motor].set_value(val)
        self._send(CMD_PWM, motor, val, f"PWM M{motor}={val}")

    def _send_digital(self, pin_id, value):
        self._send(CMD_DIGITAL, pin_id, value, f"DIGITAL {pin_id:#04x}={value}")

    def _send_servo(self):
        angle = self.servo_slider.value()
        self.servo_indicator.set_angle(angle)
        self._send(CMD_SERVO, 0, angle, f"SERVO={angle}°")

    def _send_neopixel(self, color):
        colors_map = {
            0x00: (QColor("#d1d5db"), "OFF"),
            0x01: (QColor("#ef4444"), "Rojo"),
            0x02: (QColor("#22c55e"), "Verde"),
            0x03: (QColor("#3b82f6"), "Azul"),
            0xFF: (QColor("#f8fafc"), "Blanco"),
        }
        c, name = colors_map.get(color, (QColor("#888"), "?"))
        self.neo_widget.set_color(c)
        self.neo_label.setText(f"NeoPixel  —  {name}")
        self._send(CMD_NEOPIXEL, 0, color, f"NEO={name}")

    def _send_raw(self):
        text = self.raw_input.text().strip()
        if not text or not self.ser or not self.ser.is_open: return
        try:
            if self._is_master():
                self.ser.write((text + "\n").encode())
                self._log(f"→ {text}", "#c084fc")
            else:
                buf = bytes(int(p, 16) for p in text.split())
                self.ser.write(buf)
                self._log(f"→ BIN {' '.join(f'{b:02X}' for b in buf)}", "#c084fc")
            self.raw_input.clear()
        except Exception as e:
            self._log(f"Error: {e}", "#f87171")

    # ── Log ───────────────────────────────────────────────────
    def _log(self, msg, color="#94a3b8"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.terminal.append(
            f'<span style="color:#475569">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )
        self.terminal.moveCursor(QTextCursor.End)

    def closeEvent(self, event):
        self._disconnect(); event.accept()


# ─── Main ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = ESP32Tester()
    w.show()
    sys.exit(app.exec_())
