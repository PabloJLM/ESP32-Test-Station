"""
tab_tester.py — Tesla Lab BALAM 2026
Tester general ESP32 con DAQ real y sistema de vistas intercambiables.

Vistas del panel de estado:
  • Motores  — 4 dials PWM + 8 LEDs AIN/BIN puente H
  • Servo    — arco grande con aguja cmd + aguja medida
  • NeoPixel — matriz 4x4 con color real por pixel
  • I2C      — lista de dispositivos encontrados en el bus

El dropdown de vista cambia automáticamente al paso activo
durante la prueba completa.

Protocolo (3 bytes fijos, excepto I2C scan):
  TX → [CMD, PIN_ID, VALUE]
  RX ← [ACK, CMD, VALOR_MEDIDO]
  I2C RX ← [ACK, 0x06, COUNT] + COUNT bytes de direcciones
"""

import math
import serial
import serial.tools.list_ports
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QComboBox,
    QSlider, QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSplitter, QFrame,
    QScrollArea, QStackedWidget, QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QRectF, QPointF
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QTextCursor,
    QLinearGradient, QPainterPath,
)


# ══════════════════════════════════════════════════════════════
#  PALETA Catppuccin Mocha
# ══════════════════════════════════════════════════════════════
C_BASE    = "#1e1e2e"
C_MANTLE  = "#181825"
C_SURFACE = "#313244"
C_OVERLAY = "#45475a"
C_TEXT    = "#cdd6f4"
C_SUBTEXT = "#6c7086"
C_BLUE    = "#89b4fa"
C_GREEN   = "#a6e3a1"
C_RED     = "#f38ba8"
C_YELLOW  = "#f9e2af"
C_MAUVE   = "#cba6f7"
C_TEAL    = "#94e2d5"
C_PEACH   = "#fab387"
C_PINK    = "#f5c2e7"

# Colores NeoPixel reales (R, G, B)
NEO_COLORS = {
    0x00: (30,  30,  30),
    0x01: (220,  40,  40),
    0x02: (40,  200,  60),
    0x03: (40,   80, 220),
    0xFF: (220, 220, 220),
}
NEO_NAMES = {
    0x00: "OFF", 0x01: "ROJO", 0x02: "VERDE",
    0x03: "AZUL", 0xFF: "BLANCO",
}

# ══════════════════════════════════════════════════════════════
#  PROTOCOLO
# ══════════════════════════════════════════════════════════════
CMD_PWM      = 0x01
CMD_DIGITAL  = 0x02
CMD_SERVO    = 0x03
CMD_NEOPIXEL = 0x04
CMD_ADC      = 0x05
CMD_I2C_SCAN = 0x06
CMD_PING     = 0xF0
CMD_RESET    = 0xFF

ACK_OK  = 0xAA
ACK_ERR = 0xEE

# Pines digitales AIN/BIN  {pin_id: (nombre, motor)}
DIGITAL_PINS = {
    0x11: ("M1 AIN1", 1), 0x12: ("M1 AIN2", 1),
    0x21: ("M2 BIN1", 2), 0x22: ("M2 BIN2", 2),
    0x31: ("M3 AIN1", 3), 0x32: ("M3 AIN2", 3),
    0x41: ("M4 BIN1", 4), 0x42: ("M4 BIN2", 4),
}

# Vista que se activa automáticamente según el CMD del paso activo
CMD_TO_VIEW = {
    CMD_PWM:      "Motores",
    CMD_DIGITAL:  "Motores",
    CMD_SERVO:    "Servo",
    CMD_NEOPIXEL: "NeoPixel",
    CMD_I2C_SCAN: "I2C",
    CMD_PING:     None,   # no cambia vista
    CMD_RESET:    None,
}

# ══════════════════════════════════════════════════════════════
#  SECUENCIA PRUEBA COMPLETA
#  (nombre, cmd, pin_id, valor, descripcion)
# ══════════════════════════════════════════════════════════════
PRUEBA_COMPLETA = [
    ("Ping",        CMD_PING,     0x00, 0x00, "Verificar slave activo"),
    ("PWM M1 50%",  CMD_PWM,      0x01,  128, "Motor 1 al 50%"),
    ("PWM M2 50%",  CMD_PWM,      0x02,  128, "Motor 2 al 50%"),
    ("PWM M3 50%",  CMD_PWM,      0x03,  128, "Motor 3 al 50%"),
    ("PWM M4 50%",  CMD_PWM,      0x04,  128, "Motor 4 al 50%"),
    ("M1 AIN1 ON",  CMD_DIGITAL,  0x11,    1, "Puente H M1 AIN1 = HIGH"),
    ("M1 AIN2 ON",  CMD_DIGITAL,  0x12,    1, "Puente H M1 AIN2 = HIGH"),
    ("M2 BIN1 ON",  CMD_DIGITAL,  0x21,    1, "Puente H M2 BIN1 = HIGH"),
    ("M2 BIN2 ON",  CMD_DIGITAL,  0x22,    1, "Puente H M2 BIN2 = HIGH"),
    ("M3 AIN1 ON",  CMD_DIGITAL,  0x31,    1, "Puente H M3 AIN1 = HIGH"),
    ("M3 AIN2 ON",  CMD_DIGITAL,  0x32,    1, "Puente H M3 AIN2 = HIGH"),
    ("M4 BIN1 ON",  CMD_DIGITAL,  0x41,    1, "Puente H M4 BIN1 = HIGH"),
    ("M4 BIN2 ON",  CMD_DIGITAL,  0x42,    1, "Puente H M4 BIN2 = HIGH"),
    ("M1 AIN1 OFF", CMD_DIGITAL,  0x11,    0, "Puente H M1 AIN1 = LOW"),
    ("M1 AIN2 OFF", CMD_DIGITAL,  0x12,    0, "Puente H M1 AIN2 = LOW"),
    ("M2 BIN1 OFF", CMD_DIGITAL,  0x21,    0, "Puente H M2 BIN1 = LOW"),
    ("M2 BIN2 OFF", CMD_DIGITAL,  0x22,    0, "Puente H M2 BIN2 = LOW"),
    ("Servo 0°",    CMD_SERVO,    0x00,    0, "Servo posición 0°"),
    ("Servo 90°",   CMD_SERVO,    0x00,   90, "Servo posición 90°"),
    ("Servo 180°",  CMD_SERVO,    0x00,  180, "Servo posición 180°"),
    ("Neo ROJO",    CMD_NEOPIXEL, 0x00, 0x01, "NeoPixel color rojo"),
    ("Neo VERDE",   CMD_NEOPIXEL, 0x00, 0x02, "NeoPixel color verde"),
    ("Neo AZUL",    CMD_NEOPIXEL, 0x00, 0x03, "NeoPixel color azul"),
    ("Neo OFF",     CMD_NEOPIXEL, 0x00, 0x00, "NeoPixel apagado"),
    ("I2C Scan",    CMD_I2C_SCAN, 0x00, 0x00, "Escanear bus I2C del slave"),
    ("PWM M1 OFF",  CMD_PWM,      0x01,    0, "Motor 1 stop"),
    ("PWM M2 OFF",  CMD_PWM,      0x02,    0, "Motor 2 stop"),
    ("PWM M3 OFF",  CMD_PWM,      0x03,    0, "Motor 3 stop"),
    ("PWM M4 OFF",  CMD_PWM,      0x04,    0, "Motor 4 stop"),
]


# ══════════════════════════════════════════════════════════════
#  HILO SERIAL
# ══════════════════════════════════════════════════════════════
class SerialWorker(QThread):
    result = pyqtSignal(bool, int, int, int, str)

    def __init__(self, ser, cmd, pin_id, value, mode="binario", timeout=1.5):
        super().__init__()
        self.ser     = ser
        self.cmd     = cmd
        self.pin_id  = pin_id
        self.value   = value
        self.mode    = mode
        self.timeout = timeout

    def run(self):
        try:
            if self.mode == "texto":
                self._send_text()
            else:
                self._send_binary()
        except Exception as e:
            self.result.emit(False, ACK_ERR, self.cmd, 0, f"ERROR: {e}")

    # ── Binario ────────────────────────────────────────────────
    def _send_binary(self):
        self.ser.reset_input_buffer()
        self.ser.write(bytes([self.cmd, self.pin_id, self.value]))
        if self.cmd == CMD_I2C_SCAN:
            self._wait_binary_i2c()
        else:
            self._wait_binary()

    def _wait_binary(self):
        import time
        t0, buf = time.time(), bytearray()
        while time.time() - t0 < self.timeout:
            if self.ser.in_waiting:
                buf.extend(self.ser.read(self.ser.in_waiting))
            if len(buf) >= 3:
                ok  = buf[0] == ACK_OK
                raw = f"ACK=0x{buf[0]:02X} CMD=0x{buf[1]:02X} VAL={buf[2]}"
                self.result.emit(ok, buf[0], buf[1], buf[2], raw)
                return
            time.sleep(0.01)
        self.result.emit(False, ACK_ERR, self.cmd, 0, "TIMEOUT")

    def _wait_binary_i2c(self):
        import time
        t0, buf = time.time(), bytearray()
        tlimit = max(self.timeout, 3.0)
        while time.time() - t0 < tlimit:
            if self.ser.in_waiting:
                buf.extend(self.ser.read(self.ser.in_waiting))
            if len(buf) >= 3:
                ack, count = buf[0], buf[2]
                deadline = time.time() + 1.0
                while len(buf) < 3 + count and time.time() < deadline:
                    if self.ser.in_waiting:
                        buf.extend(self.ser.read(self.ser.in_waiting))
                    time.sleep(0.005)
                addrs = buf[3: 3 + count]
                ok    = ack == ACK_OK
                raw   = (f"COUNT={count} ADDRS=" +
                         (",".join(f"0x{a:02X}" for a in addrs) if count else "none"))
                self.result.emit(ok, ack, CMD_I2C_SCAN, count, raw)
                return
            time.sleep(0.01)
        self.result.emit(False, ACK_ERR, CMD_I2C_SCAN, 0, "TIMEOUT")

    # ── Texto ──────────────────────────────────────────────────
    def _send_text(self):
        mapping = {
            CMD_PING:     "ping",
            CMD_RESET:    "reset",
            CMD_I2C_SCAN: "i2c",
            CMD_ADC:      f"adc {self.pin_id}",
        }
        if self.cmd in mapping:
            line = mapping[self.cmd]
        elif self.cmd == CMD_PWM:
            line = f"pwm {self.pin_id} {self.value}"
        elif self.cmd == CMD_SERVO:
            line = f"servo {self.value}"
        elif self.cmd == CMD_NEOPIXEL:
            v = "ff" if self.value == 0xFF else str(self.value)
            line = f"neo {v}"
        elif self.cmd == CMD_DIGITAL:
            dec = (self.pin_id >> 4) * 10 + (self.pin_id & 0x0F)
            line = f"digital {dec} {self.value}"
        else:
            line = f"raw {self.cmd} {self.pin_id} {self.value}"
        self.ser.reset_input_buffer()
        self.ser.write((line + "\n").encode())
        tlimit = 4.0 if self.cmd == CMD_I2C_SCAN else None
        self._wait_text(tlimit)

    def _wait_text(self, timeout_override=None):
        import time
        limit = timeout_override or self.timeout
        t0, buf = time.time(), b""
        while time.time() - t0 < limit:
            if self.ser.in_waiting:
                buf += self.ser.read(self.ser.in_waiting)
                if b"\n" in buf:
                    raw = buf.split(b"\n")[0].decode(errors="replace").strip()
                    ok  = raw.startswith("[OK]")
                    val = 0
                    parts = raw.split("|")
                    if self.cmd == CMD_I2C_SCAN and len(parts) >= 3:
                        try:
                            val = int(parts[2].strip().split("=")[-1].strip())
                        except Exception:
                            pass
                    elif len(parts) >= 3:
                        try:
                            seg = parts[2].strip()
                            num = "".join(c for c in seg.split("=")[-1]
                                          if c.isdigit() or c == ".")
                            val = int(float(num)) if num else 0
                        except Exception:
                            pass
                    self.result.emit(ok, ACK_OK if ok else ACK_ERR,
                                     self.cmd, val, raw)
                    return
            time.sleep(0.01)
        self.result.emit(False, ACK_ERR, self.cmd, 0, "TIMEOUT")


# ══════════════════════════════════════════════════════════════
#  VISTA 1 — MOTORES  (4 dials PWM + 8 LEDs AIN/BIN)
# ══════════════════════════════════════════════════════════════
class MotorDial(QWidget):
    """Dial circular animado para un motor."""
    def __init__(self, label="M1"):
        super().__init__()
        self.label  = label
        self.angle  = 0.0
        self.speed  = 0.0
        self.duty   = 0
        self.meas   = None
        self.status = None
        self.has_lb = False   # tiene loopback físico
        self.setFixedSize(100, 118)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def update_state(self, duty: int, meas, ok: bool, has_lb: bool = False):
        self.duty   = duty
        self.speed  = duty / 255.0
        self.meas   = meas
        self.status = ok
        self.has_lb = has_lb

    def reset(self):
        self.speed = self.duty = 0
        self.meas  = None
        self.status = None

    def _tick(self):
        if self.speed > 0:
            self.angle = (self.angle + self.speed * 14) % 360
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy, R = W // 2, (H - 28) // 2 + 4, 36

        # Fondo del dial
        border = (QColor(C_GREEN) if self.status is True else
                  QColor(C_RED)   if self.status is False else
                  QColor(C_OVERLAY))
        p.setPen(QPen(QColor(C_SURFACE), 0))
        p.setBrush(QBrush(QColor(C_SURFACE)))
        p.drawEllipse(cx - R, cy - R, 2*R, 2*R)

        # Arco de progreso (fondo gris)
        pen_bg = QPen(QColor(C_OVERLAY), 5)
        pen_bg.setCapStyle(Qt.RoundCap)
        p.setPen(pen_bg)
        p.drawArc(cx - R + 6, cy - R + 6, 2*(R-6), 2*(R-6),
                  225*16, -270*16)

        # Arco de progreso (valor)
        if self.speed > 0:
            pen_fg = QPen(QColor(C_BLUE), 5)
            pen_fg.setCapStyle(Qt.RoundCap)
            p.setPen(pen_fg)
            p.drawArc(cx - R + 6, cy - R + 6, 2*(R-6), 2*(R-6),
                      225*16, -int(self.speed * 270 * 16))

        # Aguja
        if self.speed > 0:
            rad = math.radians(self.angle)
            x2  = cx + (R - 12) * math.cos(rad)
            y2  = cy + (R - 12) * math.sin(rad)
            p.setPen(QPen(QColor(C_PEACH), 2))
            p.drawLine(cx, cy, int(x2), int(y2))

        # Borde de estado
        p.setPen(QPen(border, 2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(cx - R, cy - R, 2*R, 2*R)

        # Texto central
        p.setPen(QColor(C_TEXT))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(QRectF(cx - R, cy - 10, 2*R, 20),
                   Qt.AlignCenter, f"{int(self.speed*100)}%")

        # Label motor
        p.setPen(QColor(C_TEXT))
        p.setFont(QFont("Segoe UI", 10, QFont.Bold))
        p.drawText(QRectF(0, H - 28, W, 16), Qt.AlignCenter, self.label)

        # Valor medido
        p.setFont(QFont("Consolas", 8))
        if self.meas is not None:
            color = QColor(C_GREEN) if self.status else QColor(C_RED)
            p.setPen(color)
            p.drawText(QRectF(0, H - 14, W, 14),
                       Qt.AlignCenter, f"meas {self.meas:.1f}%")
        elif self.speed > 0:
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(QRectF(0, H - 14, W, 14),
                       Qt.AlignCenter, "meas N/A")


class DigLed(QWidget):
    """LED compacto para un pin AIN/BIN."""
    def __init__(self, label="AIN1", pin_id=0x11):
        super().__init__()
        self.label  = label
        self.pin_id = pin_id
        self.state  = False
        self.status = None
        self.setFixedSize(68, 70)

    def update_state(self, state: bool, ok: bool):
        self.state  = state
        self.status = ok
        self.update()

    def reset(self):
        self.state  = False
        self.status = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy, R = W // 2, H // 2 - 8, 20

        # LED color
        if self.status is False:
            fill = QColor(C_RED)
        elif self.state:
            fill = QColor(C_GREEN)
        else:
            fill = QColor(C_OVERLAY)

        # Glow suave si encendido
        if self.state and self.status is not False:
            glow = QColor(C_GREEN)
            glow.setAlpha(40)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(cx - R - 6, cy - R - 6,
                          2*R + 12, 2*R + 12)

        border = QColor(C_GREEN if (self.state and self.status is not False)
                        else C_RED if self.status is False
                        else C_OVERLAY)
        p.setPen(QPen(border, 1.5))
        p.setBrush(QBrush(fill))
        p.drawEllipse(cx - R, cy - R, 2*R, 2*R)

        # Pin id
        p.setPen(QColor(C_SUBTEXT))
        p.setFont(QFont("Consolas", 7))
        p.drawText(QRectF(0, cy + R + 2, W, 12),
                   Qt.AlignCenter, f"0x{self.pin_id:02X}")

        # Label
        p.setPen(QColor(C_TEXT))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(QRectF(0, H - 14, W, 14), Qt.AlignCenter, self.label)


class ViewMotores(QWidget):
    """Vista: 4 dials PWM grandes + 8 LEDs AIN/BIN."""
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        # — Dials PWM —
        lbl_pwm = QLabel("PWM — Motores")
        lbl_pwm.setStyleSheet(
            f"color:{C_MAUVE}; font-size:10px; font-weight:700;"
            f" letter-spacing:1px;")
        lay.addWidget(lbl_pwm)

        dial_row = QHBoxLayout()
        dial_row.setSpacing(6)
        self.dials = {}
        has_lb = {1: True, 2: True, 3: False, 4: False}
        for i in range(1, 5):
            d = MotorDial(f"M{i}")
            self.dials[i] = d
            dial_row.addWidget(d)
        lay.addLayout(dial_row)

        # — Separador —
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C_OVERLAY}; max-height:1px;")
        lay.addWidget(sep)

        # — LEDs AIN/BIN —
        lbl_dig = QLabel("Puente H — AIN / BIN")
        lbl_dig.setStyleSheet(
            f"color:{C_TEAL}; font-size:10px; font-weight:700;"
            f" letter-spacing:1px;")
        lay.addWidget(lbl_dig)

        dig_grid_w = QWidget()
        dig_grid   = QGridLayout(dig_grid_w)
        dig_grid.setSpacing(4)
        dig_grid.setContentsMargins(0, 0, 0, 0)
        self.leds = {}
        for idx, (pid, (name, _)) in enumerate(DIGITAL_PINS.items()):
            led = DigLed(name, pid)
            self.leds[pid] = led
            dig_grid.addWidget(led, idx // 4, idx % 4)
        lay.addWidget(dig_grid_w)
        lay.addStretch()

    def update_pwm(self, motor: int, duty: int, meas, ok: bool):
        if motor in self.dials:
            has_lb = motor in (1, 2)
            self.dials[motor].update_state(duty, meas, ok, has_lb)

    def update_dig(self, pin_id: int, state: bool, ok: bool):
        if pin_id in self.leds:
            self.leds[pin_id].update_state(state, ok)

    def reset(self):
        for d in self.dials.values():
            d.reset()
        for l in self.leds.values():
            l.reset()


# ══════════════════════════════════════════════════════════════
#  VISTA 2 — SERVO
# ══════════════════════════════════════════════════════════════
class ViewServo(QWidget):
    """Vista: arco grande de servo con cmd (azul) y medido (amarillo)."""
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        lbl = QLabel("Servo")
        lbl.setStyleSheet(
            f"color:{C_MAUVE}; font-size:10px; font-weight:700;"
            f" letter-spacing:1px;")
        lay.addWidget(lbl)

        self._arc = _ServoArcWidget()
        lay.addWidget(self._arc, 1)

        # Info cards
        info_row = QHBoxLayout()
        self._card_cmd  = self._make_card("Enviado", "—°", C_BLUE)
        self._card_meas = self._make_card("Medido",  "—°", C_YELLOW)
        self._card_diff = self._make_card("Diff",    "—°", C_SUBTEXT)
        info_row.addWidget(self._card_cmd)
        info_row.addWidget(self._card_meas)
        info_row.addWidget(self._card_diff)
        lay.addLayout(info_row)

    def _make_card(self, title, value, color):
        w = QFrame()
        w.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid {C_OVERLAY};"
            f" border-radius:6px; }}")
        l = QVBoxLayout(w)
        l.setContentsMargins(8, 6, 8, 6)
        l.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet(f"color:{C_SUBTEXT}; font-size:10px;"
                        f" border:none; background:transparent;")
        t.setAlignment(Qt.AlignCenter)
        v = QLabel(value)
        v.setObjectName("val")
        v.setStyleSheet(f"color:{color}; font-size:16px; font-weight:700;"
                        f" border:none; background:transparent;")
        v.setAlignment(Qt.AlignCenter)
        l.addWidget(t)
        l.addWidget(v)
        return w

    def update_state(self, cmd_angle: int, meas_angle, ok: bool):
        self._arc.update_state(cmd_angle, meas_angle, ok)
        self._card_cmd.findChild(QLabel, "val").setText(f"{cmd_angle}°")
        if meas_angle is not None:
            diff = abs(cmd_angle - meas_angle)
            self._card_meas.findChild(QLabel, "val").setText(f"{meas_angle}°")
            color = C_GREEN if ok else C_RED
            self._card_diff.findChild(QLabel, "val").setStyleSheet(
                f"color:{color}; font-size:16px; font-weight:700;"
                f" border:none; background:transparent;")
            self._card_diff.findChild(QLabel, "val").setText(f"{diff}°")
        else:
            self._card_meas.findChild(QLabel, "val").setText("N/A")
            self._card_diff.findChild(QLabel, "val").setText("—")

    def reset(self):
        self._arc.reset()
        for card, txt in [(self._card_cmd, "—°"),
                          (self._card_meas, "—°"),
                          (self._card_diff, "—°")]:
            card.findChild(QLabel, "val").setText(txt)


class _ServoArcWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.cmd_angle  = 90
        self.meas_angle = None
        self.status     = None
        self.setMinimumHeight(160)

    def update_state(self, cmd: int, meas, ok: bool):
        self.cmd_angle  = cmd
        self.meas_angle = meas
        self.status     = ok
        self.update()

    def reset(self):
        self.cmd_angle  = 90
        self.meas_angle = None
        self.status     = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        cx = W // 2
        cy = H - 24
        R  = min(W // 2 - 20, H - 40)

        # Marcas de ángulo (0, 45, 90, 135, 180)
        p.setFont(QFont("Consolas", 8))
        for deg in [0, 45, 90, 135, 180]:
            rad = math.radians(180 - deg)
            xm  = cx + (R + 14) * math.cos(rad)
            ym  = cy - (R + 14) * math.sin(rad)
            p.setPen(QColor(C_SUBTEXT))
            p.drawText(QRectF(xm - 14, ym - 8, 28, 16),
                       Qt.AlignCenter, f"{deg}°")
            # Tick
            xi = cx + (R - 4) * math.cos(rad)
            yi = cy - (R - 4) * math.sin(rad)
            xo = cx + (R + 4) * math.cos(rad)
            yo = cy - (R + 4) * math.sin(rad)
            p.setPen(QPen(QColor(C_OVERLAY), 1))
            p.drawLine(int(xi), int(yi), int(xo), int(yo))

        # Arco de fondo
        pen_bg = QPen(QColor(C_OVERLAY), 6)
        pen_bg.setCapStyle(Qt.RoundCap)
        p.setPen(pen_bg)
        p.drawArc(cx - R, cy - R, 2*R, 2*R, 0, 180 * 16)

        # Arco de progreso (azul hasta el ángulo)
        cmd_norm = self.cmd_angle / 180.0
        pen_fg   = QPen(QColor(C_BLUE), 6)
        pen_fg.setCapStyle(Qt.RoundCap)
        p.setPen(pen_fg)
        p.drawArc(cx - R, cy - R, 2*R, 2*R, 0, int(cmd_norm * 180 * 16))

        # Aguja CMD (azul)
        status_color = (QColor(C_GREEN) if self.status is True else
                        QColor(C_RED)   if self.status is False else
                        QColor(C_BLUE))
        rad_cmd = math.radians(180 - self.cmd_angle)
        x2 = cx + R * math.cos(rad_cmd)
        y2 = cy - R * math.sin(rad_cmd)
        p.setPen(QPen(status_color, 3))
        p.drawLine(cx, cy, int(x2), int(y2))

        # Aguja MEAS (amarillo punteado)
        if self.meas_angle is not None:
            rad_m = math.radians(180 - self.meas_angle)
            xm = cx + (R - 10) * math.cos(rad_m)
            ym = cy - (R - 10) * math.sin(rad_m)
            pen_m = QPen(QColor(C_YELLOW), 2, Qt.DashLine)
            p.setPen(pen_m)
            p.drawLine(cx, cy, int(xm), int(ym))

        # Centro
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(C_SURFACE)))
        p.drawEllipse(cx - 7, cy - 7, 14, 14)
        p.setBrush(QBrush(status_color))
        p.drawEllipse(cx - 4, cy - 4, 8, 8)


# ══════════════════════════════════════════════════════════════
#  VISTA 3 — NEOPIXEL MATRIZ 4×4
# ══════════════════════════════════════════════════════════════
class ViewNeoPixel(QWidget):
    """Vista: matriz 4×4 de LEDs con color real."""
    ROWS = 4
    COLS = 4

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        lbl = QLabel("NeoPixel — Matriz 4×4")
        lbl.setStyleSheet(
            f"color:{C_MAUVE}; font-size:10px; font-weight:700;"
            f" letter-spacing:1px;")
        lay.addWidget(lbl)

        self._matrix = _NeoMatrixWidget(self.ROWS, self.COLS)
        lay.addWidget(self._matrix, 1)

        # Leyenda de colores
        leg = QHBoxLayout()
        for idx, name in [(0x01, "ROJO"), (0x02, "VERDE"),
                          (0x03, "AZUL"), (0xFF, "BLANCO"), (0x00, "OFF")]:
            r, g, b = NEO_COLORS[idx]
            dot = QLabel("●")
            dot.setStyleSheet(
                f"color: rgb({r},{g},{b}); font-size:16px;")
            lbl2 = QLabel(name)
            lbl2.setStyleSheet(
                f"color:{C_SUBTEXT}; font-size:10px;")
            leg.addWidget(dot)
            leg.addWidget(lbl2)
            if idx != 0x00:
                leg.addSpacing(6)
        leg.addStretch()
        lay.addLayout(leg)

        # Status badge
        self._status_lbl = QLabel("")
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet(
            f"color:{C_SUBTEXT}; font-size:11px;")
        lay.addWidget(self._status_lbl)

    def update_pixel(self, row: int, col: int, color_idx: int, ok: bool):
        self._matrix.set_pixel(row, col, color_idx)
        name = NEO_NAMES.get(color_idx, hex(color_idx))
        self._status_lbl.setText(f"[{row},{col}] = {name}")
        self._status_lbl.setStyleSheet(
            f"color:{C_GREEN if ok else C_RED}; font-size:11px;")

    def update_single(self, color_idx: int, ok: bool):
        """Para slave con 1 solo LED — ilumina toda la matriz igual."""
        for r in range(self.ROWS):
            for c in range(self.COLS):
                self._matrix.set_pixel(r, c, color_idx)
        name = NEO_NAMES.get(color_idx, hex(color_idx))
        self._status_lbl.setText(f"Todos = {name}")
        self._status_lbl.setStyleSheet(
            f"color:{C_GREEN if ok else C_RED}; font-size:11px;")

    def reset(self):
        for r in range(self.ROWS):
            for c in range(self.COLS):
                self._matrix.set_pixel(r, c, 0x00)
        self._status_lbl.setText("")


class _NeoMatrixWidget(QWidget):
    def __init__(self, rows=4, cols=4):
        super().__init__()
        self.rows = rows
        self.cols = cols
        self.grid = [[QColor(30, 30, 30)] * cols for _ in range(rows)]
        self.setMinimumSize(160, 160)

    def set_pixel(self, row: int, col: int, color_idx: int):
        if 0 <= row < self.rows and 0 <= col < self.cols:
            r, g, b = NEO_COLORS.get(color_idx, (30, 30, 30))
            self.grid[row][col] = QColor(r, g, b)
            self.update()

    def reset(self):
        self.grid = [[QColor(30, 30, 30)] * self.cols
                     for _ in range(self.rows)]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H   = self.width(), self.height()
        cell_w = (W - 16) // self.cols
        cell_h = (H - 16) // self.rows
        cell   = min(cell_w, cell_h)
        ox = (W - cell * self.cols) // 2
        oy = (H - cell * self.rows) // 2

        for r in range(self.rows):
            for c in range(self.cols):
                color = self.grid[r][c]
                x = ox + c * cell + 4
                y = oy + r * cell + 4
                s = cell - 8

                # Glow si encendido
                if color != QColor(30, 30, 30):
                    glow = QColor(color)
                    glow.setAlpha(55)
                    p.setPen(Qt.NoPen)
                    p.setBrush(QBrush(glow))
                    p.drawRoundedRect(x - 4, y - 4, s + 8, s + 8, 8, 8)

                # LED
                p.setPen(QPen(QColor(C_OVERLAY), 1))
                p.setBrush(QBrush(color))
                p.drawRoundedRect(x, y, s, s, 6, 6)

                # Brillo especular
                if color != QColor(30, 30, 30):
                    p.setPen(Qt.NoPen)
                    p.setBrush(QBrush(QColor(255, 255, 255, 40)))
                    p.drawEllipse(x + s//4, y + s//6,
                                  s//3, s//4)


# ══════════════════════════════════════════════════════════════
#  VISTA 4 — I2C SCAN
# ══════════════════════════════════════════════════════════════
class ViewI2C(QWidget):
    """Vista: lista de dispositivos encontrados en el bus I2C."""
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        lbl = QLabel("I2C — Bus scan")
        lbl.setStyleSheet(
            f"color:{C_MAUVE}; font-size:10px; font-weight:700;"
            f" letter-spacing:1px;")
        lay.addWidget(lbl)

        # Badge de estado
        self._badge = QLabel("Sin datos")
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFixedHeight(36)
        self._badge.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self._badge.setStyleSheet(
            f"color:{C_SUBTEXT}; background:{C_SURFACE};"
            f" border-radius:6px;")
        lay.addWidget(self._badge)

        # Grid de tarjetas de dispositivos
        self._cards_w = QWidget()
        self._cards_l = QGridLayout(self._cards_w)
        self._cards_l.setSpacing(8)
        self._cards_l.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._cards_w, 1)

        # Tabla de dispositivos conocidos comunes
        known_lbl = QLabel("Referencia de direcciones comunes")
        known_lbl.setStyleSheet(
            f"color:{C_SUBTEXT}; font-size:10px;")
        lay.addWidget(known_lbl)

        ref = QLabel(
            "0x3C/0x3D = OLED SSD1306   "
            "0x68/0x69 = MPU6050/MPU9250   "
            "0x1E = HMC5883   "
            "0x48 = ADS1115   "
            "0x27 = PCF8574 (LCD)"
        )
        ref.setStyleSheet(
            f"color:{C_OVERLAY}; font-size:9px; font-family:Consolas;")
        ref.setWordWrap(True)
        lay.addWidget(ref)

    def update_scan(self, count: int, addrs: list, ok: bool):
        # Limpiar cards anteriores
        while self._cards_l.count():
            item = self._cards_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not ok:
            self._badge.setText("Error de bus I2C")
            self._badge.setStyleSheet(
                f"color:{C_RED}; background:#4a1515; border-radius:6px;")
            return

        if count == 0:
            self._badge.setText("Bus vacío — sin dispositivos")
            self._badge.setStyleSheet(
                f"color:{C_YELLOW}; background:#3a3000; border-radius:6px;")
            # Tarjeta de bus vacío
            empty = QLabel("No se encontraron\ndispositivos I2C")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
            self._cards_l.addWidget(empty, 0, 0)
        else:
            self._badge.setText(f"{count} dispositivo{'s' if count != 1 else ''} encontrado{'s' if count != 1 else ''}")
            self._badge.setStyleSheet(
                f"color:{C_GREEN}; background:#1a3a1a; border-radius:6px;")
            for i, addr in enumerate(addrs):
                card = self._make_device_card(addr)
                self._cards_l.addWidget(card, i // 3, i % 3)

    def _make_device_card(self, addr: int) -> QWidget:
        # Nombres conocidos
        KNOWN = {
            0x3C: "OLED", 0x3D: "OLED",
            0x68: "MPU6050", 0x69: "MPU6050",
            0x1E: "HMC5883", 0x48: "ADS1115",
            0x27: "PCF8574", 0x76: "BME280",
            0x77: "BME280/BMP280", 0x40: "INA219",
        }
        name = KNOWN.get(addr, "Dispositivo")
        w = QFrame()
        w.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid {C_BLUE};"
            f" border-radius:8px; }}")
        l = QVBoxLayout(w)
        l.setContentsMargins(10, 8, 10, 8)
        l.setSpacing(2)
        addr_lbl = QLabel(f"0x{addr:02X}")
        addr_lbl.setStyleSheet(
            f"color:{C_BLUE}; font-size:18px; font-weight:700;"
            f" border:none; background:transparent;")
        addr_lbl.setAlignment(Qt.AlignCenter)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            f"color:{C_SUBTEXT}; font-size:10px;"
            f" border:none; background:transparent;")
        name_lbl.setAlignment(Qt.AlignCenter)
        l.addWidget(addr_lbl)
        l.addWidget(name_lbl)
        return w

    def reset(self):
        while self._cards_l.count():
            item = self._cards_l.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._badge.setText("Sin datos")
        self._badge.setStyleSheet(
            f"color:{C_SUBTEXT}; background:{C_SURFACE}; border-radius:6px;")


# ══════════════════════════════════════════════════════════════
#  TABLA DE RESULTADOS
# ══════════════════════════════════════════════════════════════
class ResultTable(QTableWidget):
    COLS = ["Prueba", "Descripción", "Esperado", "Slave", "Medido", "Resultado"]

    def __init__(self):
        super().__init__(0, len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().setVisible(False)
        hh = self.horizontalHeader()
        hh.setStretchLastSection(True)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.setStyleSheet(f"""
            QTableWidget {{
                background:{C_MANTLE}; color:{C_TEXT};
                gridline-color:{C_OVERLAY};
                border:1px solid {C_OVERLAY}; border-radius:4px;
                font-size:11px;
            }}
            QTableWidget::item {{ padding:3px 8px; }}
            QTableWidget::item:selected {{ background:#3b4261; }}
            QTableWidget {{ alternate-background-color:#1a1a2a; }}
            QHeaderView::section {{
                background:{C_SURFACE}; color:{C_BLUE};
                font-weight:700; font-size:11px;
                padding:5px; border:none;
                border-right:1px solid {C_OVERLAY};
                border-bottom:2px solid {C_BLUE};
            }}
        """)
        self.setAlternatingRowColors(True)

    def add_result(self, nombre, desc, esperado, slave, medido, ok):
        r = self.rowCount()
        self.insertRow(r)
        values = [nombre, desc, str(esperado), str(slave),
                  str(medido) if medido is not None else "N/A",
                  "PASS" if ok else "FAIL"]
        for c, txt in enumerate(values):
            item = QTableWidgetItem(txt)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            if c == 5:
                item.setForeground(QColor(C_GREEN if ok else C_RED))
                item.setFont(QFont("Segoe UI", 11, QFont.Bold))
            elif c in (2, 3, 4):
                item.setFont(QFont("Consolas", 10))
            self.setItem(r, c, item)
        self.setRowHeight(r, 26)
        self.scrollToBottom()

    def clear_results(self):
        self.setRowCount(0)


# ══════════════════════════════════════════════════════════════
#  PESTAÑA TESTER
# ══════════════════════════════════════════════════════════════
class TabTester(QWidget):
    status_msg = pyqtSignal(str)

    # Índice de vista en el QStackedWidget
    VIEW_MOTORES = 0
    VIEW_SERVO   = 1
    VIEW_NEO     = 2
    VIEW_I2C     = 3

    VIEW_NAMES = ["Motores", "Servo", "NeoPixel", "I2C"]

    def __init__(self):
        super().__init__()
        self.ser         = None
        self._worker     = None
        self._mode       = "binario"
        self._prueba_idx = 0
        self._running    = False
        self._queue      = []

        self._build_ui()
        self._refresh_ports()

    # ──────────────────────────────────────────────────────────
    #  UI PRINCIPAL
    # ──────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)
        root.addWidget(self._build_conn_bar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_right())
        splitter.setSizes([520, 460])
        root.addWidget(splitter, 1)

    # ── Barra de conexión ──────────────────────────────────────
    def _build_conn_bar(self):
        box = QGroupBox("Conexión")
        box.setStyleSheet(self._gs(C_BLUE))
        lay = QHBoxLayout(box)
        lay.setSpacing(8)

        lay.addWidget(self._lbl("Puerto:"))
        self._combo_port = QComboBox()
        self._combo_port.setMinimumWidth(100)
        lay.addWidget(self._combo_port)

        lay.addWidget(self._lbl("Baud:"))
        self._combo_baud = QComboBox()
        self._combo_baud.addItems(["9600", "115200"])
        lay.addWidget(self._combo_baud)

        b_ref = self._btn("↻", C_BLUE, 32)
        b_ref.clicked.connect(self._refresh_ports)
        lay.addWidget(b_ref)

        self._btn_conn = QPushButton("Conectar")
        self._btn_conn.setCheckable(True)
        self._btn_conn.setFixedWidth(100)
        self._btn_conn.setStyleSheet(self._bstyle())
        self._btn_conn.clicked.connect(self._toggle_conn)
        lay.addWidget(self._btn_conn)

        self._lbl_conn = QLabel("● Desconectado")
        self._lbl_conn.setStyleSheet(
            f"color:{C_RED}; font-weight:700; font-size:12px;")
        lay.addWidget(self._lbl_conn)

        lay.addStretch()

        lay.addWidget(self._lbl("Protocolo:"))
        self._combo_proto = QComboBox()
        self._combo_proto.addItems(["binario", "texto"])
        self._combo_proto.currentTextChanged.connect(
            lambda t: setattr(self, "_mode", t))
        lay.addWidget(self._combo_proto)

        for label, fn, color in [
            ("Ping",     self._do_ping,  C_TEAL),
            ("Reset",    self._do_reset, C_YELLOW),
            ("I2C Scan", self._do_i2c,   C_MAUVE),
        ]:
            b = self._btn(label, color, 72)
            b.clicked.connect(fn)
            lay.addWidget(b)

        return box

    # ── Panel izquierdo ────────────────────────────────────────
    def _build_left(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(6)
        lay.setContentsMargins(0, 0, 0, 0)

        # — Selector de vista —
        view_bar = QHBoxLayout()
        view_bar.setSpacing(6)
        lbl_v = self._lbl("Vista:")
        lbl_v.setFixedWidth(38)
        view_bar.addWidget(lbl_v)
        self._view_combo = QComboBox()
        self._view_combo.addItems(self.VIEW_NAMES)
        self._view_combo.setFixedHeight(28)
        self._view_combo.currentIndexChanged.connect(self._on_view_changed)
        view_bar.addWidget(self._view_combo, 1)

        # Indicador de paso activo
        self._paso_lbl = QLabel("")
        self._paso_lbl.setStyleSheet(
            f"color:{C_SUBTEXT}; font-size:10px;")
        self._paso_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        view_bar.addWidget(self._paso_lbl)
        lay.addLayout(view_bar)

        # — Stack de vistas —
        self._stack = QStackedWidget()
        self._v_motores = ViewMotores()
        self._v_servo   = ViewServo()
        self._v_neo     = ViewNeoPixel()
        self._v_i2c     = ViewI2C()
        self._stack.addWidget(self._v_motores)   # 0
        self._stack.addWidget(self._v_servo)     # 1
        self._stack.addWidget(self._v_neo)       # 2
        self._stack.addWidget(self._v_i2c)       # 3

        # Frame contenedor para la vista
        view_frame = QFrame()
        view_frame.setStyleSheet(
            f"QFrame {{ background:{C_MANTLE}; border:1px solid {C_OVERLAY};"
            f" border-radius:8px; }}")
        vfl = QVBoxLayout(view_frame)
        vfl.setContentsMargins(0, 0, 0, 0)
        vfl.addWidget(self._stack)
        lay.addWidget(view_frame, 1)

        # — Panel de control manual (compacto, siempre visible) —
        ctrl_box = QGroupBox("Control manual")
        ctrl_box.setStyleSheet(self._gs(C_PEACH))
        ctrl_lay = QVBoxLayout(ctrl_box)
        ctrl_lay.setSpacing(5)
        ctrl_lay.setContentsMargins(8, 8, 8, 8)

        # PWM — botones rápidos + slider seleccionable
        pwm_row = QHBoxLayout()
        pwm_row.addWidget(self._lbl("PWM:"))
        self._combo_motor = QComboBox()
        for i in range(1, 5):
            self._combo_motor.addItem(f"M{i}", i)
        self._combo_motor.setFixedWidth(52)
        pwm_row.addWidget(self._combo_motor)
        self._sl_pwm = QSlider(Qt.Horizontal)
        self._sl_pwm.setRange(0, 255)
        self._sl_pwm.setValue(128)
        self._sl_pwm.setStyleSheet(self._slider_style())
        self._lbl_pwm = QLabel("128")
        self._lbl_pwm.setFixedWidth(30)
        self._sl_pwm.valueChanged.connect(
            lambda v: self._lbl_pwm.setText(str(v)))
        b_pwm = self._btn("Set", C_BLUE, 40)
        b_pwm.clicked.connect(self._manual_pwm)
        pwm_row.addWidget(self._sl_pwm, 1)
        pwm_row.addWidget(self._lbl_pwm)
        pwm_row.addWidget(b_pwm)
        ctrl_lay.addLayout(pwm_row)

        # Botones rápidos PWM
        quick_row = QHBoxLayout()
        quick_row.addWidget(self._lbl("   "))
        for label, val in [("0%", 0), ("25%", 64), ("50%", 128), ("100%", 255)]:
            b = QPushButton(label)
            b.setFixedHeight(22)
            b.setStyleSheet(self._bstyle())
            b.clicked.connect(lambda _, v=val: self._sl_pwm.setValue(v))
            quick_row.addWidget(b)
        b_stop = QPushButton("Stop todo")
        b_stop.setFixedHeight(22)
        b_stop.setStyleSheet(
            f"QPushButton {{ background:#7f1d1d; color:{C_RED};"
            f" border:1px solid #ef4444; border-radius:4px;"
            f" font-size:11px; font-weight:700; }}"
            f"QPushButton:hover {{ background:#991b1b; }}")
        b_stop.clicked.connect(self._stop_all_motors)
        quick_row.addWidget(b_stop)
        ctrl_lay.addLayout(quick_row)

        # Servo
        srv_row = QHBoxLayout()
        srv_row.addWidget(self._lbl("Servo:"))
        self._sl_srv = QSlider(Qt.Horizontal)
        self._sl_srv.setRange(0, 180)
        self._sl_srv.setValue(90)
        self._sl_srv.setStyleSheet(self._slider_style())
        self._lbl_srv = QLabel("90°")
        self._lbl_srv.setFixedWidth(34)
        self._sl_srv.valueChanged.connect(
            lambda v: self._lbl_srv.setText(f"{v}°"))
        b_srv = self._btn("Set", C_BLUE, 40)
        b_srv.clicked.connect(self._manual_servo)
        srv_row.addWidget(self._sl_srv, 1)
        srv_row.addWidget(self._lbl_srv)
        srv_row.addWidget(b_srv)
        ctrl_lay.addLayout(srv_row)

        # Neo + Digital en misma fila
        bot_row = QHBoxLayout()
        bot_row.addWidget(self._lbl("Neo:"))
        self._combo_neo = QComboBox()
        self._combo_neo.addItems(["OFF", "ROJO", "VERDE", "AZUL", "BLANCO"])
        self._combo_neo.setFixedWidth(80)
        b_neo = self._btn("Set", C_BLUE, 40)
        b_neo.clicked.connect(self._manual_neo)
        bot_row.addWidget(self._combo_neo)
        bot_row.addWidget(b_neo)
        bot_row.addSpacing(8)
        bot_row.addWidget(self._lbl("Pin:"))
        self._combo_dig = QComboBox()
        for pid, (name, _) in DIGITAL_PINS.items():
            self._combo_dig.addItem(f"{name}", pid)
        self._combo_dig.setFixedWidth(80)
        b_hi = self._btn_colored("HIGH", C_GREEN, "#14532d", "#22c55e", 46)
        b_lo = self._btn_colored("LOW",  C_RED,   "#7f1d1d", "#ef4444", 46)
        b_hi.clicked.connect(lambda: self._manual_dig(1))
        b_lo.clicked.connect(lambda: self._manual_dig(0))
        bot_row.addWidget(self._combo_dig)
        bot_row.addWidget(b_hi)
        bot_row.addWidget(b_lo)
        ctrl_lay.addLayout(bot_row)

        lay.addWidget(ctrl_box)

        # — Botón prueba completa —
        btn_row = QHBoxLayout()
        self._btn_full = QPushButton(
            f"▶  Iniciar prueba completa  ({len(PRUEBA_COMPLETA)} pasos)")
        self._btn_full.setFixedHeight(40)
        self._btn_full.setStyleSheet(
            f"QPushButton {{ background:#2563eb; color:white; border:none;"
            f" border-radius:7px; font-size:13px; font-weight:700; }}"
            f"QPushButton:hover {{ background:#1d4ed8; }}"
            f"QPushButton:disabled {{ background:#1e3a6e; color:#7a9fd6; }}")
        self._btn_full.clicked.connect(self._start_full_test)

        b_clear = self._btn("Limpiar", C_OVERLAY, 72)
        b_clear.clicked.connect(self._reset_ui)
        btn_row.addWidget(self._btn_full, 1)
        btn_row.addWidget(b_clear)
        lay.addLayout(btn_row)

        return w

    # ── Panel derecho ──────────────────────────────────────────
    def _build_right(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(6)
        lay.setContentsMargins(0, 0, 0, 0)

        # Resultados
        res_box = QGroupBox("Resultados")
        res_box.setStyleSheet(self._gs(C_BLUE))
        res_lay = QVBoxLayout(res_box)

        # Header: progreso + badge
        hdr = QHBoxLayout()
        self._prog_lbl = QLabel("")
        self._prog_lbl.setStyleSheet(
            f"color:{C_SUBTEXT}; font-size:11px; font-weight:600;")
        hdr.addWidget(self._prog_lbl)
        hdr.addStretch()
        self._badge = QLabel("")
        self._badge.setFixedHeight(30)
        self._badge.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.hide()
        hdr.addWidget(self._badge)
        res_lay.addLayout(hdr)

        self._table = ResultTable()
        res_lay.addWidget(self._table, 1)
        lay.addWidget(res_box, 1)

        # Log serial
        log_box = QGroupBox("Log serial")
        log_box.setStyleSheet(self._gs(C_BLUE))
        log_lay = QVBoxLayout(log_box)
        hdr2 = QHBoxLayout()
        hdr2.addStretch()
        b_cl = self._btn("Limpiar", C_OVERLAY, 64)
        b_cl.clicked.connect(self._log.clear if hasattr(self, "_log")
                              else lambda: None)
        hdr2.addWidget(b_cl)
        log_lay.addLayout(hdr2)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 9))
        self._log.setFixedHeight(140)
        self._log.setStyleSheet(
            f"QTextEdit {{ background:{C_MANTLE}; color:{C_GREEN};"
            f" border:none; border-radius:4px; }}")
        b_cl.clicked.connect(self._log.clear)
        log_lay.addWidget(self._log)
        lay.addWidget(log_box)
        return w

    # ──────────────────────────────────────────────────────────
    #  SELECTOR DE VISTA
    # ──────────────────────────────────────────────────────────
    def _on_view_changed(self, idx: int):
        self._stack.setCurrentIndex(idx)

    def _set_view(self, name: str):
        """Cambia la vista por nombre (llamado automáticamente durante prueba)."""
        if name in self.VIEW_NAMES:
            idx = self.VIEW_NAMES.index(name)
            self._view_combo.setCurrentIndex(idx)
            self._stack.setCurrentIndex(idx)

    # ──────────────────────────────────────────────────────────
    #  CONEXIÓN
    # ──────────────────────────────────────────────────────────
    def _refresh_ports(self):
        self._combo_port.clear()
        for p in serial.tools.list_ports.comports():
            self._combo_port.addItem(p.device)
        if self._combo_port.count() == 0:
            self._combo_port.addItem("(sin puertos)")

    def _toggle_conn(self, checked):
        self._connect() if checked else self._disconnect()

    def _connect(self):
        port = self._combo_port.currentText()
        baud = int(self._combo_baud.currentText())
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self._lbl_conn.setText("● Conectado")
            self._lbl_conn.setStyleSheet(
                f"color:{C_GREEN}; font-weight:700; font-size:12px;")
            self._btn_conn.setText("Desconectar")
            self._log_line(f"Conectado: {port} @ {baud} baud", C_BLUE)
            self.status_msg.emit(f"Conectado: {port}")
        except Exception as ex:
            self._btn_conn.setChecked(False)
            self._log_line(f"Error: {ex}", C_RED)
            self.status_msg.emit(f"Error de conexión: {ex}")

    def _disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self._lbl_conn.setText("● Desconectado")
        self._lbl_conn.setStyleSheet(
            f"color:{C_RED}; font-weight:700; font-size:12px;")
        self._btn_conn.setText("Conectar")
        self._btn_conn.setChecked(False)
        self._log_line("Desconectado.", C_YELLOW)
        self.status_msg.emit("Desconectado.")

    # ──────────────────────────────────────────────────────────
    #  PRUEBA COMPLETA
    # ──────────────────────────────────────────────────────────
    def _start_full_test(self):
        if not self.ser or not self.ser.is_open:
            self._log_line("⚠ Sin conexión serial.", C_RED)
            return
        self._queue      = list(PRUEBA_COMPLETA)
        self._prueba_idx = 0
        self._running    = True
        self._table.clear_results()
        self._badge.hide()
        self._reset_anim()
        self._btn_full.setEnabled(False)
        self.status_msg.emit("Prueba completa iniciada...")
        self._log_line(
            f"═══ Prueba completa: {len(self._queue)} pasos ═══", C_BLUE)
        self._run_next()

    def _run_next(self):
        if self._prueba_idx >= len(self._queue):
            self._finish_test()
            return
        n, total = self._prueba_idx + 1, len(self._queue)
        nombre, cmd, pid, val, desc = self._queue[self._prueba_idx]

        # Actualizar indicador de paso
        self._paso_lbl.setText(f"Paso {n}/{total}")
        self._prog_lbl.setText(f"Paso {n} de {total} — {nombre}")

        # Cambiar vista automáticamente
        view_name = CMD_TO_VIEW.get(cmd)
        if view_name:
            self._set_view(view_name)

        self._log_line(f"[{n}/{total}] {nombre}: {desc}", C_SUBTEXT)

        timeout = 2.0 if cmd == CMD_SERVO else 1.5

        self._worker = SerialWorker(
            self.ser, cmd, pid, val, self._mode, timeout)
        self._worker.result.connect(
            lambda ok, ack, c, v, raw,
            nm=nombre, ds=desc, cm=cmd, p=pid, vl=val:
            self._on_result(ok, ack, c, v, raw, nm, ds, cm, p, vl)
        )
        self._worker.start()

    def _on_result(self, ok, ack, cmd_r, val, raw,
                   nombre, desc, cmd, pid, value):
        esperado = self._fmt_esperado(cmd, pid, value)
        medido   = self._parse_meas(raw, cmd, val)
        slave    = self._fmt_slave(cmd, val)

        self._table.add_result(nombre, desc, esperado, slave, medido, ok)
        self._update_views(cmd, pid, value, ok, val, medido, raw)

        color = C_GREEN if ok else C_RED
        self._log_line(
            f"  ← {raw}  →  {'PASS ✔' if ok else 'FAIL ✖'}", color)
        self._prueba_idx += 1

        delay = 600 if cmd == CMD_SERVO else 350
        QTimer.singleShot(delay, self._run_next)

    def _finish_test(self):
        self._running = False
        self._btn_full.setEnabled(True)
        self._prog_lbl.setText("")
        self._paso_lbl.setText("")
        total = self._table.rowCount()
        fails = sum(1 for r in range(total)
                    if self._table.item(r, 5) and
                    self._table.item(r, 5).text() == "FAIL")
        if fails == 0:
            self._badge.setText(f"✔  TODAS PASARON  ({total}/{total})")
            self._badge.setStyleSheet(
                f"background:#14532d; color:{C_GREEN};"
                f" border-radius:8px; padding:2px 12px;")
        else:
            self._badge.setText(f"✖  FALLARON {fails} DE {total}")
            self._badge.setStyleSheet(
                f"background:#7f1d1d; color:{C_RED};"
                f" border-radius:8px; padding:2px 12px;")
        self._badge.show()
        self.status_msg.emit(
            f"Prueba completa: {total-fails}/{total} PASS")
        self._log_line(
            f"═══ Fin: {total-fails}/{total} PASS ═══",
            C_GREEN if fails == 0 else C_RED)

    # ──────────────────────────────────────────────────────────
    #  ACTUALIZACIÓN DE VISTAS
    # ──────────────────────────────────────────────────────────
    def _update_views(self, cmd, pid, value, ok, slave_val, meas, raw=""):
        if cmd == CMD_PWM:
            meas_pct = meas if isinstance(meas, (int, float)) else None
            self._v_motores.update_pwm(pid, value, meas_pct, ok)

        elif cmd == CMD_DIGITAL:
            readback_ok = ok and (slave_val == value)
            self._v_motores.update_dig(pid, bool(value), readback_ok)

        elif cmd == CMD_SERVO:
            meas_ang = meas if isinstance(meas, (int, float)) else None
            self._v_servo.update_state(value, meas_ang, ok)

        elif cmd == CMD_NEOPIXEL:
            # El slave actual tiene 1 LED — modo "all same"
            # Si se expande a matriz, usar update_pixel(row, col, value, ok)
            self._v_neo.update_single(value, ok)

        elif cmd == CMD_I2C_SCAN:
            # Parsear direcciones del raw string
            addrs = []
            if "ADDRS=" in raw:
                addr_str = raw.split("ADDRS=")[-1].split("|")[0].strip()
                if addr_str and addr_str != "none":
                    for a in addr_str.split(","):
                        try:
                            addrs.append(int(a.strip(), 16))
                        except Exception:
                            pass
            self._v_i2c.update_scan(slave_val, addrs, ok)

    def _reset_anim(self):
        self._v_motores.reset()
        self._v_servo.reset()
        self._v_neo.reset()
        self._v_i2c.reset()

    # ──────────────────────────────────────────────────────────
    #  CONTROLES MANUALES
    # ──────────────────────────────────────────────────────────
    def _manual_pwm(self):
        motor = self._combo_motor.currentData()
        v     = self._sl_pwm.value()
        self._send(CMD_PWM, motor, v,
                   cb=lambda ok, ack, c, val, raw, m=motor, duty=v:
                   self._update_views(CMD_PWM, m, duty, ok, val, None))

    def _stop_all_motors(self):
        for m in range(1, 5):
            self._send(CMD_PWM, m, 0,
                       cb=lambda ok, ack, c, v, raw, mo=m:
                       self._update_views(CMD_PWM, mo, 0, ok, v, None))

    def _manual_servo(self):
        v = self._sl_srv.value()
        self._send(CMD_SERVO, 0x00, v,
                   cb=lambda ok, ack, c, val, raw, angle=v:
                   self._update_views(CMD_SERVO, 0x00, angle, ok, val, None))

    def _manual_neo(self):
        idx_map = [0x00, 0x01, 0x02, 0x03, 0xFF]
        v = idx_map[self._combo_neo.currentIndex()]
        self._send(CMD_NEOPIXEL, 0x00, v,
                   cb=lambda ok, ack, c, val, raw, col=v:
                   self._update_views(CMD_NEOPIXEL, 0x00, col, ok, val, None))

    def _manual_dig(self, state: int):
        pid = self._combo_dig.currentData()
        if pid is None:
            return
        self._send(CMD_DIGITAL, pid, state,
                   cb=lambda ok, ack, c, val, raw, p=pid, s=state:
                   self._update_views(CMD_DIGITAL, p, s, ok, val, None))

    def _do_ping(self):
        self._send(CMD_PING, 0x00, 0x00,
                   cb=lambda ok, ack, c, v, raw:
                   self._log_line(
                       "PING → slave vivo ✔" if ok else "PING → sin respuesta ✖",
                       C_GREEN if ok else C_RED))

    def _do_reset(self):
        self._send(CMD_RESET, 0x00, 0x00,
                   cb=lambda ok, ack, c, v, raw:
                   self._log_line(
                       "RESET enviado." if ok else "RESET sin ACK.", C_YELLOW))

    def _do_i2c(self):
        self._set_view("I2C")
        self._send(CMD_I2C_SCAN, 0x00, 0x00,
                   cb=lambda ok, ack, c, v, raw:
                   self._update_views(CMD_I2C_SCAN, 0x00, 0x00, ok, v, None, raw))

    # ──────────────────────────────────────────────────────────
    #  ENVÍO
    # ──────────────────────────────────────────────────────────
    def _send(self, cmd, pid, value, cb=None):
        if not self.ser or not self.ser.is_open:
            self._log_line("⚠ Sin conexión.", C_RED)
            return
        self._log_line(f"→ {self._cmd_str(cmd, pid, value)}", C_BLUE)
        self._worker = SerialWorker(self.ser, cmd, pid, value, self._mode)
        if cb:
            self._worker.result.connect(cb)
        self._worker.result.connect(
            lambda ok, ack, c, v, raw:
            self._log_line(f"← {raw}", C_GREEN if ok else C_RED))
        self._worker.start()

    # ──────────────────────────────────────────────────────────
    #  HELPERS DE FORMATO
    # ──────────────────────────────────────────────────────────
    def _fmt_esperado(self, cmd, pid, value) -> str:
        if cmd == CMD_PWM:
            return f"{int(value/255*100)}% ({value}/255)"
        if cmd == CMD_DIGITAL:
            name = DIGITAL_PINS.get(pid, (f"0x{pid:02X}", None))[0]
            return f"{name} = {'HIGH' if value else 'LOW'}"
        if cmd == CMD_SERVO:
            return f"{value}°"
        if cmd == CMD_NEOPIXEL:
            return NEO_NAMES.get(value, hex(value))
        if cmd == CMD_PING:
            return "ACK 0xAA"
        if cmd == CMD_I2C_SCAN:
            return "Scan I2C"
        return str(value)

    def _fmt_slave(self, cmd, slave_val) -> str:
        if cmd == CMD_PWM:
            return f"{int(slave_val/255*100)}%"
        if cmd == CMD_DIGITAL:
            return "HIGH" if slave_val else "LOW"
        if cmd == CMD_SERVO:
            return f"{slave_val}°"
        if cmd == CMD_NEOPIXEL:
            return f"0x{slave_val:02X}"
        if cmd == CMD_PING:
            return "0xAA" if slave_val == 0 else hex(slave_val)
        if cmd == CMD_I2C_SCAN:
            return f"{slave_val} disp."
        return str(slave_val)

    def _parse_meas(self, raw: str, cmd: int, slave_val: int):
        if cmd == CMD_I2C_SCAN:
            if "ADDRS=" in raw:
                return raw.split("ADDRS=")[-1].split("|")[0].strip()
            return None
        if self._mode == "binario":
            return None
        if "MEAS=" not in raw:
            return None
        try:
            seg = raw.split("MEAS=")[-1].split("|")[0].strip()
            num = "".join(c for c in seg if c.isdigit() or c == ".")
            return round(float(num), 1) if num else None
        except Exception:
            return None

    def _cmd_str(self, cmd, pid, value) -> str:
        if cmd == CMD_PWM:
            return f"pwm M{pid} duty={value} ({int(value/255*100)}%)"
        if cmd == CMD_SERVO:
            return f"servo {value}°"
        if cmd == CMD_NEOPIXEL:
            return f"neo {NEO_NAMES.get(value, hex(value))}"
        if cmd == CMD_DIGITAL:
            name = DIGITAL_PINS.get(pid, (f"0x{pid:02X}", None))[0]
            return f"digital {name} = {'HIGH' if value else 'LOW'}"
        if cmd == CMD_PING:    return "ping"
        if cmd == CMD_RESET:   return "reset"
        if cmd == CMD_I2C_SCAN: return "i2c scan"
        return f"0x{cmd:02X} 0x{pid:02X} {value}"

    # ──────────────────────────────────────────────────────────
    #  UI RESET
    # ──────────────────────────────────────────────────────────
    def _reset_ui(self):
        self._reset_anim()
        self._table.clear_results()
        self._badge.hide()
        self._prog_lbl.setText("")
        self._paso_lbl.setText("")
        self._prueba_idx = 0
        self._running    = False
        self._queue      = []
        self._btn_full.setEnabled(True)

    # ──────────────────────────────────────────────────────────
    #  HELPERS DE ESTILO
    # ──────────────────────────────────────────────────────────
    def _lbl(self, txt: str) -> QLabel:
        l = QLabel(txt)
        l.setStyleSheet(f"color:{C_TEXT}; font-weight:600;")
        return l

    def _btn(self, txt, accent, w=80) -> QPushButton:
        b = QPushButton(txt)
        b.setFixedWidth(w)
        b.setStyleSheet(
            f"QPushButton {{ background:{C_SURFACE}; color:{accent};"
            f" border:1px solid {accent}; border-radius:4px;"
            f" font-size:11px; padding:3px 6px; }}"
            f"QPushButton:hover {{ background:{C_OVERLAY}; }}")
        return b

    def _btn_colored(self, txt, fg, bg, border, w=60) -> QPushButton:
        b = QPushButton(txt)
        b.setFixedWidth(w)
        b.setFixedHeight(26)
        b.setStyleSheet(
            f"QPushButton {{ background:{bg}; color:{fg};"
            f" border:1px solid {border}; border-radius:4px;"
            f" font-weight:700; font-size:11px; }}"
            f"QPushButton:hover {{ background:{C_OVERLAY}; }}")
        return b

    def _gs(self, accent: str) -> str:
        return (
            f"QGroupBox {{ border:1px solid {C_OVERLAY}; border-radius:8px;"
            f" margin-top:10px; font-weight:bold; color:{accent}; padding:8px; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin;"
            f" left:10px; padding:0 6px; }}")

    def _bstyle(self) -> str:
        return (
            f"QPushButton {{ background:{C_SURFACE}; color:{C_TEXT};"
            f" border:1px solid {C_OVERLAY}; border-radius:4px;"
            f" font-size:11px; padding:4px 8px; }}"
            f"QPushButton:hover {{ background:{C_OVERLAY}; }}"
            f"QPushButton:checked {{ background:#2563eb; color:white;"
            f" border-color:#2563eb; }}"
            f"QPushButton:disabled {{ background:{C_MANTLE}; color:{C_OVERLAY}; }}")

    def _slider_style(self) -> str:
        return (
            f"QSlider::groove:horizontal {{ height:4px;"
            f" background:{C_OVERLAY}; border-radius:2px; }}"
            f"QSlider::handle:horizontal {{ background:{C_BLUE};"
            f" width:14px; height:14px; margin:-5px 0; border-radius:7px; }}"
            f"QSlider::sub-page:horizontal {{ background:{C_BLUE};"
            f" border-radius:2px; }}")

    def _log_line(self, msg: str, color: str = C_TEXT):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(
            f'<span style="color:{C_SUBTEXT}">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>')
        self._log.moveCursor(QTextCursor.End)

    # ──────────────────────────────────────────────────────────
    #  CLEANUP
    # ──────────────────────────────────────────────────────────
    def cleanup(self):
        self._disconnect()
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
