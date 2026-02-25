#!/usr/bin/env python3
"""
ESP32 Board Tester — main.py
Carga esp32_tester.ui y conecta toda la lógica serial + widgets visuales.

Instalar dependencias:
    pip install pyserial PyQt5

Correr:
    python main.py
"""

import sys
import math
import serial
import serial.tools.list_ports
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QLabel
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import (
    QFont, QColor, QTextCursor, QPainter, QPen, QBrush,
    QLinearGradient, QRadialGradient,
)
from PyQt5 import uic

# ── Ruta al .ui ───────────────────────────────────────────────
UI_FILE = "esp32_tester.ui"

# ── Protocolo ─────────────────────────────────────────────────
CMD_PWM      = 0x01
CMD_DIGITAL  = 0x02
CMD_SERVO    = 0x03
CMD_NEOPIXEL = 0x04
CMD_PING     = 0xF0
CMD_RESET    = 0xFF

RESPONSES = {
    0xAA: ("PONG / OK",    "#22c55e"),
    0x01: ("PWM OK",       "#3b82f6"),
    0x02: ("Digital OK",   "#8b5cf6"),
    0x03: ("Servo OK",     "#f59e0b"),
    0x04: ("NeoPixel OK",  "#ec4899"),
    0xBB: ("Reset OK",     "#06b6d4"),
    0xEE: ("Error",        "#ef4444"),
}

# ═══════════════════════════════════════════════════════════════
# WIDGETS VISUALES CUSTOM (pintados con QPainter)
# ═══════════════════════════════════════════════════════════════

class LedWidget(QLabel):
    """LED circular con glow. Uso: led.set_on(True/False)"""
    def __init__(self, label="", color_on="#22c55e", size=15, parent=None):
        super().__init__(parent)
        self._on = False
        self._color_on  = QColor(color_on)
        self._color_off = QColor("#d1d5db")
        self._label = label
        self._size  = size
        self.setFixedHeight(size + 6)
        # Ancho estimado: círculo + texto
        self.setMinimumWidth(size + 8 + len(label) * 7)

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
            glow = QRadialGradient(s // 2 + 2, s // 2 + 3, s)
            gc = QColor(c); gc.setAlpha(55)
            glow.setColorAt(0, gc); glow.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(glow)); p.setPen(Qt.NoPen)
            p.drawEllipse(0, 0, s + 4, s + 4)

        grad = QRadialGradient(s // 2 - 1, s // 2 - 1, s // 2)
        dark = QColor(max(0,c.red()-80), max(0,c.green()-80), max(0,c.blue()-80))
        grad.setColorAt(0, c); grad.setColorAt(1, dark)
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor("#9ca3af"), 1))
        p.drawEllipse(2, 2, s, s)

        p.setBrush(QBrush(QColor(255, 255, 255, 75))); p.setPen(Qt.NoPen)
        p.drawEllipse(s // 2 - 2, 4, s // 3, s // 5)

        if self._label:
            p.setPen(QColor("#374151"))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(s + 8, 0, self.width(), s + 6,
                       Qt.AlignVCenter | Qt.AlignLeft, self._label)
        p.end()


class MotorBar(QLabel):
    """Barra de progreso estilo industrial para PWM 0-255."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self.setFixedHeight(36)
        self.setMinimumWidth(120)

    def set_value(self, v):
        self._value = max(0, min(255, v))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        pct = self._value / 255.0
        ty, th = 18, 12

        p.setBrush(QColor("#f1f5f9")); p.setPen(QPen(QColor("#e2e8f0"), 1))
        p.drawRoundedRect(0, ty, w, th, 6, 6)

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
            p.drawRoundedRect(0, ty, bw, th, 6, 6)

        p.setPen(QColor("#64748b"))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(0, 0, w, ty - 1, Qt.AlignRight | Qt.AlignBottom,
                   f"{self._value}  ({int(pct*100)}%)")
        p.end()


class ServoWidget(QLabel):
    """Indicador visual de servo con aguja animada."""
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
        cx, cy, r = w // 2, h - 12, 72

        p.setPen(QPen(QColor("#e2e8f0"), 9, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx-r, cy-r, r*2, r*2, 0*16, 180*16)

        p.setPen(QPen(QColor("#3b82f6"), 9, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(cx-r, cy-r, r*2, r*2, 0*16, int(self._angle)*16)

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
        p.drawText(cx-r-8, cy-4, "0°")
        p.drawText(cx-10,  cy-r-16, "90°")
        p.drawText(cx+r-12, cy-4, "180°")

        p.setPen(QColor("#1e293b")); p.setFont(QFont("Segoe UI", 12, QFont.Bold))
        p.drawText(0, cy-34, w, 20, Qt.AlignHCenter, f"{self._angle}°")
        p.end()


class NeoPixelWidget(QLabel):
    """Círculo que simula el NeoPixel con glow."""
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
                er = r + 10 + i*5
                p.drawEllipse(cx-er, cy-er, er*2, er*2)

        grad = QRadialGradient(cx-4, cy-4, r)
        dark = QColor(max(0,self._color.red()-90),
                      max(0,self._color.green()-90),
                      max(0,self._color.blue()-90))
        grad.setColorAt(0, self._color); grad.setColorAt(1, dark)
        p.setBrush(QBrush(grad)); p.setPen(QPen(QColor("#9ca3af"), 1))
        p.drawEllipse(cx-r, cy-r, r*2, r*2)

        p.setBrush(QBrush(QColor(255,255,255,90))); p.setPen(Qt.NoPen)
        p.drawEllipse(cx-r//2, cy-r+5, r-4, r//3)
        p.end()


# ═══════════════════════════════════════════════════════════════
# SERIAL READER THREAD
# ═══════════════════════════════════════════════════════════════

class SerialReader(QThread):
    text_line       = pyqtSignal(str)  # línea de texto completa
    proto_byte      = pyqtSignal(int)  # byte de protocolo (no-ASCII)
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
                        self.text_line.emit(line)
                    return
            b = self._buf[0]
            if not (0x20 <= b <= 0x7E) and b not in (0x09, 0x0A, 0x0D):
                self._buf.pop(0)
                self.proto_byte.emit(b)
                return
            break

    def stop(self):
        self._running = False
        self.wait()


# ═══════════════════════════════════════════════════════════════
# VENTANA PRINCIPAL
# ═══════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ── Cargar UI ────────────────────────────────────────
        uic.loadUi(UI_FILE, self)

        self.ser    = None
        self.reader = None

        # ── Insertar widgets custom en los contenedores del .ui ──
        self._inject_custom_widgets()

        # ── Conectar señales del .ui ─────────────────────────
        self._connect_signals()

        # ── Poblar puertos al inicio ─────────────────────────
        self._refresh_ports()

        # ── Valor inicial del baud ────────────────────────────
        self.baudCombo.setCurrentText("9600")

    # ──────────────────────────────────────────────────────────
    # INYECCIÓN DE WIDGETS CUSTOM EN CONTENEDORES DEL .UI
    # ──────────────────────────────────────────────────────────
    def _inject_custom_widgets(self):
        """
        Los widgets pintados con QPainter no se pueden declarar en el .ui,
        se crean aquí y se insertan en los QWidget-placeholder definidos en el .ui.
        """

        # ── NeoPixel ──────────────────────────────────────────
        self.neoWidget = NeoPixelWidget()
        lay = QVBoxLayout(self.neoWidgetContainer)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.neoWidget)

        # ── Servo ─────────────────────────────────────────────
        self.servoWidget = ServoWidget()
        lay2 = QVBoxLayout(self.servoWidgetContainer)
        lay2.setContentsMargins(0, 0, 0, 0)
        lay2.addWidget(self.servoWidget)

        # ── LEDs de respuesta ─────────────────────────────────
        resp_lay = QVBoxLayout(self.respLedsContainer)
        resp_lay.setContentsMargins(0, 0, 0, 0)
        resp_lay.setSpacing(5)
        self._resp_leds = {}
        for code, (name, color) in RESPONSES.items():
            led = LedWidget(name, color, 14)
            t   = QTimer(self)
            t.setSingleShot(True)
            t.timeout.connect(lambda l=led: l.set_on(False))
            led._timer = t
            self._resp_leds[code] = led
            resp_lay.addWidget(led)

        # ── Barras PWM feedback ───────────────────────────────
        pwm_lay = QVBoxLayout(self.pwmFbContainer)
        pwm_lay.setContentsMargins(0, 0, 0, 0)
        pwm_lay.setSpacing(2)
        self._fb_bars = {}
        for m in [1, 2, 3, 4]:
            row = QHBoxLayout()
            lbl = QLabel(f"M{m}")
            lbl.setFixedWidth(18)
            lbl.setStyleSheet("font-size:11px;font-weight:700;color:#475569;")
            bar = MotorBar()
            self._fb_bars[m] = bar
            row.addWidget(lbl)
            row.addWidget(bar)
            pwm_lay.addLayout(row)

    # ──────────────────────────────────────────────────────────
    # CONEXIÓN DE SEÑALES (widgets del .ui → métodos Python)
    # ──────────────────────────────────────────────────────────
    def _connect_signals(self):
        # Header
        self.btnRefresh.clicked.connect(self._refresh_ports)
        self.btnConnect.clicked.connect(self._toggle_connection)

        # Sliders motores → actualizar label de valor
        for m in [1, 2, 3, 4]:
            sl  = getattr(self, f"sliderM{m}")
            lbl = getattr(self, f"valM{m}")
            sl.valueChanged.connect(lambda v, l=lbl: l.setText(str(v)))

        # Botones enviar motor
        self.btnSendM1.clicked.connect(lambda: self._send_pwm(1))
        self.btnSendM2.clicked.connect(lambda: self._send_pwm(2))
        self.btnSendM3.clicked.connect(lambda: self._send_pwm(3))
        self.btnSendM4.clicked.connect(lambda: self._send_pwm(4))

        # Servo slider → label + widget visual
        self.sliderServo.valueChanged.connect(
            lambda v: (self.valServo.setText(f"{v}°"),
                       self.servoWidget.set_angle(v))
        )
        self.btnSendServo.clicked.connect(self._send_servo)

        # NeoPixel
        self.btnNeoOff.clicked.connect(   lambda: self._send_neopixel(0x00))
        self.btnNeoRojo.clicked.connect(  lambda: self._send_neopixel(0x01))
        self.btnNeoVerde.clicked.connect( lambda: self._send_neopixel(0x02))
        self.btnNeoAzul.clicked.connect(  lambda: self._send_neopixel(0x03))
        self.btnNeoBlanco.clicked.connect(lambda: self._send_neopixel(0xFF))

        # Ping / Reset
        self.btnPing.clicked.connect( self._send_ping)
        self.btnReset.clicked.connect(self._send_reset)

        # Digital pins
        _digital_map = {
            0x11: ("btnOn11","btnOff11"), 0x12: ("btnOn12","btnOff12"),
            0x21: ("btnOn21","btnOff21"), 0x22: ("btnOn22","btnOff22"),
            0x31: ("btnOn31","btnOff31"), 0x32: ("btnOn32","btnOff32"),
            0x41: ("btnOn41","btnOff41"), 0x42: ("btnOn42","btnOff42"),
        }
        for pid, (on_name, off_name) in _digital_map.items():
            getattr(self, on_name ).clicked.connect(lambda _, p=pid: self._send_digital(p, 1))
            getattr(self, off_name).clicked.connect(lambda _, p=pid: self._send_digital(p, 0))

        # Raw command
        self.rawInput.returnPressed.connect(self._send_raw)
        self.btnSendRaw.clicked.connect(self._send_raw)

        # Log
        self.btnClearLog.clicked.connect(self.terminal.clear)

    # ──────────────────────────────────────────────────────────
    # SERIAL — Conexión
    # ──────────────────────────────────────────────────────────
    def _refresh_ports(self):
        self.portCombo.clear()
        for p in serial.tools.list_ports.comports():
            self.portCombo.addItem(p.device)
        if self.portCombo.count() == 0:
            self.portCombo.addItem("(sin puertos)")

    def _toggle_connection(self, checked):
        self._connect() if checked else self._disconnect()

    def _connect(self):
        port = self.portCombo.currentText()
        baud = int(self.baudCombo.currentText())
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self.reader = SerialReader(self.ser)
            self.reader.text_line.connect(self._on_text)
            self.reader.proto_byte.connect(self._on_byte)
            self.reader.connection_lost.connect(self._on_lost)
            self.reader.start()

            # Actualizar UI
            self.ledConnLabel.setText("●")
            self.ledConnLabel.setStyleSheet("color: #22c55e; font-size: 16px;")
            self.connText.setText(port)
            self.btnConnect.setText("Desconectar")
            self.statusBar.showMessage(f"Conectado  ·  {port}  ·  {baud} baud")
            self._log(f"Conectado a {port} @ {baud}", "#22d3ee")
        except Exception as e:
            self.btnConnect.setChecked(False)
            self._log(f"Error al conectar: {e}", "#f87171")
            self.statusBar.showMessage(f"Error: {e}")

    def _disconnect(self):
        if self.reader:
            self.reader.stop()
            self.reader = None
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.ledConnLabel.setText("●")
        self.ledConnLabel.setStyleSheet("color: #d1d5db; font-size: 16px;")
        self.connText.setText("Desconectado")
        self.btnConnect.setText("Conectar")
        self.btnConnect.setChecked(False)
        self.statusBar.showMessage("Desconectado.")
        self._log("Desconectado.", "#f87171")

    # ──────────────────────────────────────────────────────────
    # RECEPCIÓN
    # ──────────────────────────────────────────────────────────
    def _on_text(self, line):
        """Filtra el menú de ayuda y muestra solo respuestas útiles."""
        skip_prefixes = [
            "===", "Comandos", "  ping", "  pwm", "  servo",
            "  neo", "  digital", "  reset", "UART a", "Estado:"
        ]
        if any(line.startswith(s) for s in skip_prefixes):
            return
        self._log(f"← {line}", "#86efac")

    def _on_byte(self, b):
        """Byte del protocolo Slave → enciende LED de respuesta."""
        name, color = RESPONSES.get(b, (f"0x{b:02X}", "#94a3b8"))
        self._log(f"← {name}", "#fde68a")
        if b in self._resp_leds:
            led = self._resp_leds[b]
            led.set_on(True)
            led._timer.start(1400)

    def _on_lost(self):
        self._log("Conexión perdida.", "#f87171")
        self._disconnect()

    # ──────────────────────────────────────────────────────────
    # ENVÍO
    # ──────────────────────────────────────────────────────────
    def _is_master(self):
        return self.modeCombo.currentIndex() == 0

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
            self._log("No conectado", "#f87171")
            return
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
        val = getattr(self, f"sliderM{motor}").value()
        self._fb_bars[motor].set_value(val)
        self._send(CMD_PWM, motor, val, f"PWM M{motor}={val}")

    def _send_digital(self, pin_id, value):
        self._send(CMD_DIGITAL, pin_id, value, f"DIGITAL {pin_id:#04x}={value}")

    def _send_servo(self):
        angle = self.sliderServo.value()
        self.servoWidget.set_angle(angle)
        self._send(CMD_SERVO, 0, angle, f"SERVO={angle}°")

    def _send_neopixel(self, color):
        neo_map = {
            0x00: (QColor("#d1d5db"), "OFF"),
            0x01: (QColor("#ef4444"), "Rojo"),
            0x02: (QColor("#22c55e"), "Verde"),
            0x03: (QColor("#3b82f6"), "Azul"),
            0xFF: (QColor("#f8fafc"), "Blanco"),
        }
        c, name = neo_map.get(color, (QColor("#888"), "?"))
        self.neoWidget.set_color(c)
        self.neoLabel.setText(f"NeoPixel  —  {name}")
        self._send(CMD_NEOPIXEL, 0, color, f"NEO={name}")

    def _send_raw(self):
        text = self.rawInput.text().strip()
        if not text or not self.ser or not self.ser.is_open:
            return
        try:
            if self._is_master():
                self.ser.write((text + "\n").encode())
                self._log(f"→ {text}", "#c084fc")
            else:
                buf = bytes(int(p, 16) for p in text.split())
                self.ser.write(buf)
                self._log(f"→ BIN {' '.join(f'{b:02X}' for b in buf)}", "#c084fc")
            self.rawInput.clear()
        except Exception as e:
            self._log(f"Error: {e}", "#f87171")

    # ──────────────────────────────────────────────────────────
    # LOG
    # ──────────────────────────────────────────────────────────
    def _log(self, msg, color="#94a3b8"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.terminal.append(
            f'<span style="color:#475569">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )
        self.terminal.moveCursor(QTextCursor.End)

    def closeEvent(self, event):
        self._disconnect()
        event.accept()


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
