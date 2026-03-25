"""
tab_tester.py — Tesla Lab BALAM 2026
Tester serial con GUI animada, modos por modelo y tabla de resultados.

Modelos:
    Robofut      — 4 motores, 1 NeoPixel, 8 digitales (AIN/BIN)
    STEM SR      — 4 motores, 1 servo, 1 NeoPixel, 8 digitales
    Todoterreno  — 4 motores, 1 NeoPixel, 8 digitales
    IoT          — Matriz NeoPixel 4x4
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
    QCheckBox, QScrollArea,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QRectF
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QPen, QBrush, QTextCursor,
)


# ══════════════════════════════════════════════════════════════
#  COLORES
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


# ══════════════════════════════════════════════════════════════
#  PROTOCOLO
# ══════════════════════════════════════════════════════════════
CMD_PWM      = 0x01
CMD_DIGITAL  = 0x02
CMD_SERVO    = 0x03
CMD_NEOPIXEL = 0x04
CMD_PING     = 0xF0
CMD_RESET    = 0xFF

ACK_OK  = 0xAA
ACK_ERR = 0xEE

NEO_COLORS = {
    0x00: (30,  30,  30),
    0x01: (255,  0,   0),
    0x02: (0,  255,   0),
    0x03: (0,    0, 255),
    0xFF: (255, 255, 255),
}
NEO_NAMES = {0x00:"OFF", 0x01:"ROJO", 0x02:"VERDE", 0x03:"AZUL", 0xFF:"BLANCO"}


# ══════════════════════════════════════════════════════════════
#  DEFINICION DE MODELOS
# ══════════════════════════════════════════════════════════════

# Pines digitales por modelo: (nombre_display, pin_id_hex)
DIGITAL_PINS = {
    "Robofut": [
        ("M1 AIN1", 0x11), ("M1 AIN2", 0x12),
        ("M2 BIN1", 0x21), ("M2 BIN2", 0x22),
        ("M3 AIN1", 0x31), ("M3 AIN2", 0x32),
        ("M4 BIN1", 0x41), ("M4 BIN2", 0x42),
    ],
    "STEM SR": [
        ("M1 AIN1", 0x11), ("M1 AIN2", 0x12),
        ("M2 BIN1", 0x21), ("M2 BIN2", 0x22),
        ("M3 AIN1", 0x31), ("M3 AIN2", 0x32),
        ("M4 BIN1", 0x41), ("M4 BIN2", 0x42),
    ],
    "Todoterreno": [
        ("M1 AIN1", 0x11), ("M1 AIN2", 0x12),
        ("M2 BIN1", 0x21), ("M2 BIN2", 0x22),
        ("M3 AIN1", 0x31), ("M3 AIN2", 0x32),
        ("M4 BIN1", 0x41), ("M4 BIN2", 0x42),
    ],
    "IoT": [],
}

# Pruebas fijas por modelo (motores, servo, neo)
# Los digitales se agregan dinamicamente segun seleccion del encargado
PRUEBAS_BASE = {
    "Robofut": [
        ("PWM M1",   CMD_PWM,      0x01, 128, "Motor 1 al 50%"),
        ("PWM M2",   CMD_PWM,      0x02, 128, "Motor 2 al 50%"),
        ("PWM M3",   CMD_PWM,      0x03, 128, "Motor 3 al 50%"),
        ("PWM M4",   CMD_PWM,      0x04, 128, "Motor 4 al 50%"),
        ("NeoPixel", CMD_NEOPIXEL, 0x00, 0x01,"NeoPixel Rojo"),
    ],
    "STEM SR": [
        ("PWM M1",   CMD_PWM,      0x01, 128, "Motor 1 al 50%"),
        ("PWM M2",   CMD_PWM,      0x02, 128, "Motor 2 al 50%"),
        ("PWM M3",   CMD_PWM,      0x03, 128, "Motor 3 al 50%"),
        ("PWM M4",   CMD_PWM,      0x04, 128, "Motor 4 al 50%"),
        ("Servo",    CMD_SERVO,    0x00,  90, "Servo a 90°"),
        ("NeoPixel", CMD_NEOPIXEL, 0x00, 0x02,"NeoPixel Verde"),
    ],
    "Todoterreno": [
        ("PWM M1",   CMD_PWM,      0x01, 128, "Motor 1 al 50%"),
        ("PWM M2",   CMD_PWM,      0x02, 128, "Motor 2 al 50%"),
        ("PWM M3",   CMD_PWM,      0x03, 128, "Motor 3 al 50%"),
        ("PWM M4",   CMD_PWM,      0x04, 128, "Motor 4 al 50%"),
        ("NeoPixel", CMD_NEOPIXEL, 0x00, 0x03,"NeoPixel Azul"),
    ],
    "IoT": [
        ("Neo 0,0",  CMD_NEOPIXEL, 0x00, 0xFF, "Matriz [0,0] Blanco"),
        ("Neo 0,1",  CMD_NEOPIXEL, 0x01, 0xFF, "Matriz [0,1] Blanco"),
        ("Neo 1,0",  CMD_NEOPIXEL, 0x10, 0xFF, "Matriz [1,0] Blanco"),
        ("Neo 1,1",  CMD_NEOPIXEL, 0x11, 0xFF, "Matriz [1,1] Blanco"),
        ("Neo OFF",  CMD_NEOPIXEL, 0x00, 0x00, "Apagar todos"),
    ],
}


# ══════════════════════════════════════════════════════════════
#  HILO SERIAL
# ══════════════════════════════════════════════════════════════
class SerialWorker(QThread):
    result = pyqtSignal(bool, int, int, int)   # ok, ack, cmd, val

    def __init__(self, ser, cmd, pin_id, value, mode="binario", timeout=1.0):
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
        except Exception:
            self.result.emit(False, ACK_ERR, self.cmd, 0)

    def _send_binary(self):
        self.ser.write(bytes([self.cmd, self.pin_id, self.value]))
        self._wait_response()

    def _send_text(self):
        if   self.cmd == CMD_PING:    line = "ping"
        elif self.cmd == CMD_RESET:   line = "reset"
        elif self.cmd == CMD_PWM:     line = f"pwm {self.pin_id} {self.value}"
        elif self.cmd == CMD_SERVO:   line = f"servo {self.value}"
        elif self.cmd == CMD_NEOPIXEL:
            line = f"neo {'ff' if self.value == 0xFF else self.value}"
        elif self.cmd == CMD_DIGITAL:
            dec = (self.pin_id >> 4) * 10 + (self.pin_id & 0x0F)
            line = f"digital {dec} {self.value}"
        else:
            line = f"raw {self.cmd} {self.pin_id} {self.value}"
        self.ser.write((line + "\n").encode())
        self._wait_response()

    def _wait_response(self):
        import time
        t0  = time.time()
        buf = bytearray()
        while time.time() - t0 < self.timeout:
            if self.ser.in_waiting:
                buf.extend(self.ser.read(self.ser.in_waiting))
            if len(buf) >= 3:
                self.result.emit(
                    buf[0] == ACK_OK, buf[0], buf[1], buf[2]
                )
                return
            time.sleep(0.01)
        self.result.emit(False, ACK_ERR, self.cmd, 0)


# ══════════════════════════════════════════════════════════════
#  WIDGETS ANIMADOS
# ══════════════════════════════════════════════════════════════

class MotorWidget(QWidget):
    def __init__(self, label="M1"):
        super().__init__()
        self.label  = label
        self.angle  = 0.0
        self.speed  = 0.0
        self.ok     = None
        self.setFixedSize(80, 100)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_speed(self, duty_0_255: int, ok: bool):
        self.speed = duty_0_255 / 255.0
        self.ok    = ok

    def reset(self):
        self.speed = 0.0
        self.ok    = None
        self.angle = 0.0

    def _tick(self):
        if self.speed > 0:
            self.angle = (self.angle + self.speed * 12) % 360
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy, r = w//2, h//2 - 8, 30
        border = (QColor(C_GREEN) if self.ok is True else
                  QColor(C_RED)   if self.ok is False else
                  QColor(C_OVERLAY))
        p.setPen(QPen(border, 3))
        p.setBrush(QBrush(QColor(C_SURFACE)))
        p.drawEllipse(cx-r, cy-r, 2*r, 2*r)
        if self.speed > 0:
            rad = math.radians(self.angle)
            x2  = cx + (r-5)*math.cos(rad)
            y2  = cy + (r-5)*math.sin(rad)
            p.setPen(QPen(QColor(C_BLUE), 3))
            p.drawLine(cx, cy, int(x2), int(y2))
        p.setPen(QPen(QColor(C_OVERLAY), 1))
        p.drawLine(cx-8, cy, cx+8, cy)
        p.drawLine(cx, cy-8, cx, cy+8)
        p.setPen(QColor(C_TEXT))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(QRectF(0, h-20, w, 20), Qt.AlignCenter, self.label)
        if self.speed > 0:
            p.setPen(QColor(C_SUBTEXT))
            p.setFont(QFont("Consolas", 8))
            p.drawText(QRectF(0, h-34, w, 14), Qt.AlignCenter,
                       f"{int(self.speed*100)}%")


class ServoWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.angle = 90.0
        self.ok    = None
        self.setFixedSize(110, 110)

    def set_angle(self, angle: int, ok: bool):
        self.angle = float(angle)
        self.ok    = ok
        self.update()

    def reset(self):
        self.angle = 90.0
        self.ok    = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy, r = w//2, h-20, 40
        border = (QColor(C_GREEN) if self.ok is True else
                  QColor(C_RED)   if self.ok is False else
                  QColor(C_OVERLAY))
        p.setPen(QPen(QColor(C_OVERLAY), 2))
        p.setBrush(Qt.NoBrush)
        p.drawArc(cx-r, cy-r, 2*r, 2*r, 0, 180*16)
        rad = math.radians(180 - self.angle)
        x2  = cx + r*math.cos(rad)
        y2  = cy - r*math.sin(rad)
        p.setPen(QPen(border, 4))
        p.drawLine(cx, cy, int(x2), int(y2))
        p.setPen(QPen(QColor(C_SURFACE), 2))
        p.setBrush(QBrush(QColor(C_SURFACE)))
        p.drawEllipse(cx-6, cy-6, 12, 12)
        p.setPen(QColor(C_TEXT))
        p.setFont(QFont("Consolas", 9))
        p.drawText(QRectF(0, 0, w, 20), Qt.AlignCenter,
                   f"Servo {int(self.angle)}°")


class NeoPixelWidget(QWidget):
    def __init__(self, label="NEO"):
        super().__init__()
        self.label = label
        self.color = QColor(40, 40, 40)
        self.ok    = None
        self.setFixedSize(70, 90)

    def set_color(self, color_idx: int, ok: bool):
        rgb = NEO_COLORS.get(color_idx, (40, 40, 40))
        self.color = QColor(*rgb)
        self.ok    = ok
        self.update()

    def reset(self):
        self.color = QColor(40, 40, 40)
        self.ok    = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy, r = w//2, h//2-8, 24
        border = (QColor(C_GREEN) if self.ok is True else
                  QColor(C_RED)   if self.ok is False else
                  QColor(C_OVERLAY))
        if self.color != QColor(40, 40, 40):
            glow = QColor(self.color); glow.setAlpha(60)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(cx-r-8, cy-r-8, 2*r+16, 2*r+16)
        p.setPen(QPen(border, 3))
        p.setBrush(QBrush(self.color))
        p.drawEllipse(cx-r, cy-r, 2*r, 2*r)
        p.setPen(QColor(C_TEXT))
        p.setFont(QFont("Segoe UI", 9, QFont.Bold))
        p.drawText(QRectF(0, h-20, w, 20), Qt.AlignCenter, self.label)


class NeoMatrixWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.grid = [[QColor(30, 30, 30)]*4 for _ in range(4)]
        self.setFixedSize(180, 180)

    def set_pixel(self, row: int, col: int, color_idx: int):
        rgb = NEO_COLORS.get(color_idx, (30, 30, 30))
        self.grid[row][col] = QColor(*rgb)
        self.update()

    def reset(self):
        self.grid = [[QColor(30, 30, 30)]*4 for _ in range(4)]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cell = self.width() // 4
        for r in range(4):
            for c in range(4):
                x = c*cell+4; y = r*cell+4; s = cell-8
                p.setPen(QPen(QColor(C_OVERLAY), 1))
                p.setBrush(QBrush(self.grid[r][c]))
                p.drawRoundedRect(x, y, s, s, 4, 4)


class DigitalLedWidget(QWidget):
    """LED individual para un pin AIN/BIN."""

    def __init__(self, label="DIG", pin_id=0x11):
        super().__init__()
        self.label  = label
        self.pin_id = pin_id
        self.state  = False
        self.ok     = None
        self.setFixedSize(64, 80)

    def set_state(self, state: bool, ok: bool):
        self.state = state
        self.ok    = ok
        self.update()

    def reset(self):
        self.state = False
        self.ok    = None
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy, r = w//2, h//2-10, 18
        led_color = (QColor(C_GREEN)   if self.state and self.ok is not False else
                     QColor(C_RED)     if self.ok is False else
                     QColor(C_OVERLAY))
        p.setPen(QPen(QColor(C_OVERLAY), 2))
        p.setBrush(QBrush(led_color))
        p.drawEllipse(cx-r, cy-r, 2*r, 2*r)
        # Pin ID en pequeño
        p.setPen(QColor(C_SUBTEXT))
        p.setFont(QFont("Consolas", 7))
        p.drawText(QRectF(0, cy+r+2, w, 14), Qt.AlignCenter,
                   f"0x{self.pin_id:02X}")
        # Label
        p.setPen(QColor(C_TEXT))
        p.setFont(QFont("Segoe UI", 8, QFont.Bold))
        p.drawText(QRectF(0, h-18, w, 18), Qt.AlignCenter, self.label)


# ══════════════════════════════════════════════════════════════
#  TABLA DE RESULTADOS
# ══════════════════════════════════════════════════════════════
class ResultTable(QTableWidget):
    COLS = ["Prueba", "Descripcion", "CMD", "ACK", "Valor", "Resultado"]

    def __init__(self):
        super().__init__(0, len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setStyleSheet(f"""
            QTableWidget {{
                background:{C_MANTLE}; color:{C_TEXT};
                gridline-color:{C_OVERLAY};
                border:1px solid {C_OVERLAY}; border-radius:4px;
                font-size:11px;
            }}
            QTableWidget::item {{ padding:4px 8px; }}
            QTableWidget::item:selected {{ background:#3b4261; }}
            QHeaderView::section {{
                background:{C_SURFACE}; color:{C_BLUE};
                font-weight:700; font-size:11px;
                padding:6px; border:none;
                border-right:1px solid {C_OVERLAY};
                border-bottom:2px solid {C_BLUE};
            }}
            QTableWidget {{ alternate-background-color:#1a1a2a; }}
        """)
        self.setAlternatingRowColors(True)

    def add_result(self, nombre, desc, cmd_str, ack, val, ok):
        r = self.rowCount()
        self.insertRow(r)
        for c, txt in enumerate([nombre, desc, cmd_str,
                                  f"0x{ack:02X}", str(val),
                                  "PASS" if ok else "FAIL"]):
            item = QTableWidgetItem(txt)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            if c == 5:
                item.setForeground(QColor(C_GREEN if ok else C_RED))
                item.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self.setItem(r, c, item)
        self.setRowHeight(r, 28)
        self.scrollToBottom()

    def clear_results(self):
        self.setRowCount(0)


# ══════════════════════════════════════════════════════════════
#  PESTANA TESTER
# ══════════════════════════════════════════════════════════════
class TabTester(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ser         = None
        self._worker     = None
        self._mode       = "binario"
        self._modelo     = "Robofut"
        self._prueba_idx = 0
        self._running    = False
        self._full_queue = []   # lista de pruebas a ejecutar en prueba completa

        # Widgets animados — se crean en _build_anim_widgets()
        self._motors  = {}
        self._servo_w = None
        self._neo_w   = None
        self._dig_w   = {}   # {pin_id: DigitalLedWidget}
        self._matrix  = None

        self._build_ui()
        self._refresh_ports()
        self._build_anim_widgets()

    # ── UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)
        root.addWidget(self._build_conn_bar())
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([520, 460])
        root.addWidget(splitter, 1)

    def _build_conn_bar(self):
        box = QGroupBox("Conexion")
        box.setStyleSheet(self._gstyle(C_BLUE))
        lay = QHBoxLayout(box)
        lay.setSpacing(10)
        lay.addWidget(self._lbl("Puerto:"))
        self._combo_port = QComboBox()
        self._combo_port.setMinimumWidth(110)
        lay.addWidget(self._combo_port)
        lay.addWidget(self._lbl("Baud:"))
        self._combo_baud = QComboBox()
        self._combo_baud.addItems(["9600", "115200"])
        lay.addWidget(self._combo_baud)
        btn_ref = QPushButton("Actualizar")
        btn_ref.setFixedWidth(90)
        btn_ref.setStyleSheet(self._bstyle())
        btn_ref.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_ref)
        self._btn_conn = QPushButton("Conectar")
        self._btn_conn.setCheckable(True)
        self._btn_conn.setFixedWidth(110)
        self._btn_conn.setStyleSheet(self._bstyle())
        self._btn_conn.clicked.connect(self._toggle_conn)
        lay.addWidget(self._btn_conn)
        self._lbl_conn = QLabel("Desconectado")
        self._lbl_conn.setStyleSheet(f"color:{C_RED}; font-weight:600;")
        lay.addWidget(self._lbl_conn)
        lay.addStretch()
        lay.addWidget(self._lbl("Modelo:"))
        self._combo_model = QComboBox()
        self._combo_model.addItems(list(PRUEBAS_BASE.keys()))
        self._combo_model.setMinimumWidth(120)
        self._combo_model.currentTextChanged.connect(self._on_model_changed)
        lay.addWidget(self._combo_model)
        lay.addWidget(self._lbl("Protocolo:"))
        self._combo_proto = QComboBox()
        self._combo_proto.addItems(["binario", "texto"])
        self._combo_proto.currentTextChanged.connect(
            lambda t: setattr(self, '_mode', t))
        lay.addWidget(self._combo_proto)
        return box

    def _build_left_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(8)

        # Panel de animaciones con scroll
        self._anim_box = QGroupBox("Estado del dispositivo")
        self._anim_box.setStyleSheet(self._gstyle(C_TEAL))
        self._anim_lay = QVBoxLayout(self._anim_box)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border:none; background:transparent; }}"
        )
        scroll.setWidget(self._anim_box)
        lay.addWidget(scroll, 1)

        # Selector de digitales para prueba completa
        self._dig_sel_box = QGroupBox("Digitales a probar (prueba completa)")
        self._dig_sel_box.setStyleSheet(self._gstyle(C_MAUVE))
        self._dig_sel_lay = QGridLayout(self._dig_sel_box)
        self._dig_checks  = {}   # {pin_id: QCheckBox}
        lay.addWidget(self._dig_sel_box)

        # Controles manuales
        ctrl_box = QGroupBox("Control manual")
        ctrl_box.setStyleSheet(self._gstyle(C_PEACH))
        ctrl_lay = QVBoxLayout(ctrl_box)

        # PWM — un slider por motor, se reconstruyen al cambiar modelo
        self._pwm_sliders_box = QGroupBox("PWM Motores")
        self._pwm_sliders_box.setStyleSheet(
            f"QGroupBox {{ border:1px solid {C_OVERLAY}; border-radius:6px; "
            f"margin-top:8px; font-weight:bold; color:{C_PEACH}; padding:6px; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; left:8px; padding:0 4px; }}"
        )
        self._pwm_sliders_lay = QGridLayout(self._pwm_sliders_box)
        self._pwm_sliders_lay.setSpacing(4)
        self._pwm_slider_widgets = {}   # {motor_num: (slider, lbl_val)}
        ctrl_lay.addWidget(self._pwm_sliders_box)

        # Servo
        row_srv = QHBoxLayout()
        row_srv.addWidget(self._lbl("Servo:"))
        self._slider_srv = QSlider(Qt.Horizontal)
        self._slider_srv.setRange(0, 180)
        self._slider_srv.setValue(90)
        self._slider_srv.setStyleSheet(self._slider_style())
        self._lbl_srv_val = QLabel("90°")
        self._lbl_srv_val.setFixedWidth(36)
        self._slider_srv.valueChanged.connect(
            lambda v: self._lbl_srv_val.setText(f"{v}°"))
        btn_srv = QPushButton("Enviar")
        btn_srv.setFixedWidth(70)
        btn_srv.setStyleSheet(self._bstyle())
        btn_srv.clicked.connect(self._manual_servo)
        row_srv.addWidget(self._slider_srv, 1)
        row_srv.addWidget(self._lbl_srv_val)
        row_srv.addWidget(btn_srv)
        ctrl_lay.addLayout(row_srv)

        # NeoPixel
        row_neo = QHBoxLayout()
        row_neo.addWidget(self._lbl("NeoPixel:"))
        self._combo_neo = QComboBox()
        self._combo_neo.addItems(["OFF","ROJO","VERDE","AZUL","BLANCO"])
        btn_neo = QPushButton("Enviar")
        btn_neo.setFixedWidth(70)
        btn_neo.setStyleSheet(self._bstyle())
        btn_neo.clicked.connect(self._manual_neo)
        row_neo.addWidget(self._combo_neo, 1)
        row_neo.addWidget(btn_neo)
        ctrl_lay.addLayout(row_neo)

        # Digital manual con selector de pin
        row_dig = QHBoxLayout()
        row_dig.addWidget(self._lbl("Digital:"))
        self._combo_dig_pin = QComboBox()
        self._combo_dig_pin.setMinimumWidth(90)
        row_dig.addWidget(self._combo_dig_pin, 1)
        btn_on  = QPushButton("ON")
        btn_off = QPushButton("OFF")
        btn_on.setFixedWidth(50)
        btn_off.setFixedWidth(50)
        btn_on.setStyleSheet(
            f"QPushButton {{ background:#14532d; color:{C_GREEN}; "
            f"border:1px solid #22c55e; border-radius:4px; font-weight:700; }}"
        )
        btn_off.setStyleSheet(
            f"QPushButton {{ background:#7f1d1d; color:{C_RED}; "
            f"border:1px solid #ef4444; border-radius:4px; font-weight:700; }}"
        )
        btn_on.clicked.connect(lambda: self._manual_digital(1))
        btn_off.clicked.connect(lambda: self._manual_digital(0))
        row_dig.addWidget(btn_on)
        row_dig.addWidget(btn_off)
        ctrl_lay.addLayout(row_dig)
        lay.addWidget(ctrl_box)

        # Botones prueba
        btn_row = QHBoxLayout()
        self._btn_full = QPushButton("Iniciar prueba completa")
        self._btn_full.setFixedHeight(38)
        self._btn_full.setStyleSheet(
            f"QPushButton {{ background:#2563eb; color:white; border:none; "
            f"border-radius:6px; font-size:13px; font-weight:700; }}"
            f"QPushButton:hover {{ background:#1d4ed8; }}"
            f"QPushButton:disabled {{ background:#1e3a6e; color:#7a9fd6; }}"
        )
        self._btn_full.clicked.connect(self._start_full_test)
        btn_reset = QPushButton("Limpiar")
        btn_reset.setFixedHeight(38)
        btn_reset.setFixedWidth(90)
        btn_reset.setStyleSheet(self._bstyle())
        btn_reset.clicked.connect(self._reset_ui)
        btn_row.addWidget(self._btn_full, 1)
        btn_row.addWidget(btn_reset)
        lay.addLayout(btn_row)
        return w

    def _build_right_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(8)

        res_box = QGroupBox("Resultados")
        res_box.setStyleSheet(self._gstyle(C_BLUE))
        res_lay = QVBoxLayout(res_box)
        self._table = ResultTable()
        res_lay.addWidget(self._table)
        self._lbl_badge = QLabel("")
        self._lbl_badge.setAlignment(Qt.AlignCenter)
        self._lbl_badge.setFixedHeight(36)
        self._lbl_badge.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self._lbl_badge.hide()
        res_lay.addWidget(self._lbl_badge)
        lay.addWidget(res_box, 1)

        log_box = QGroupBox("Log serial")
        log_box.setStyleSheet(self._gstyle(C_BLUE))
        log_lay = QVBoxLayout(log_box)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 9))
        self._log.setFixedHeight(140)
        self._log.setStyleSheet(
            f"QTextEdit {{ background:{C_MANTLE}; color:{C_GREEN}; "
            f"border:none; border-radius:4px; }}"
        )
        hdr = QHBoxLayout()
        btn_cl = QPushButton("Limpiar")
        btn_cl.setFixedWidth(70)
        btn_cl.setStyleSheet(self._bstyle())
        btn_cl.clicked.connect(self._log.clear)
        hdr.addStretch(); hdr.addWidget(btn_cl)
        log_lay.addLayout(hdr)
        log_lay.addWidget(self._log)
        lay.addWidget(log_box)
        return w

    # ── Widgets animados por modelo ──────────────────────────────
    def _build_anim_widgets(self):
        # Limpiar layout anterior
        while self._anim_lay.count():
            item = self._anim_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._motors  = {}
        self._servo_w = None
        self._neo_w   = None
        self._dig_w   = {}
        self._matrix  = None

        if self._modelo == "IoT":
            self._matrix = NeoMatrixWidget()
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(self._matrix)
            row.addStretch()
            self._anim_lay.addLayout(row)
            self._anim_lay.addStretch()
            self._build_pwm_sliders()
            self._build_dig_selector()
            self._update_dig_pin_combo()
            return

        # Motores
        motor_row = QHBoxLayout()
        motor_row.addStretch()
        for i in range(1, 5):
            m = MotorWidget(f"M{i}")
            self._motors[i] = m
            motor_row.addWidget(m)
        motor_row.addStretch()
        self._anim_lay.addLayout(motor_row)

        # Servo (solo STEM SR) + Neo
        mid_row = QHBoxLayout()
        mid_row.addStretch()
        if self._modelo == "STEM SR":
            self._servo_w = ServoWidget()
            mid_row.addWidget(self._servo_w)
        self._neo_w = NeoPixelWidget("NEO")
        mid_row.addWidget(self._neo_w)
        mid_row.addStretch()
        self._anim_lay.addLayout(mid_row)

        # Digitales — 8 LEDs en 2 filas x 4 columnas
        dig_label = QLabel("Pines digitales AIN / BIN")
        dig_label.setStyleSheet(
            f"color:{C_MAUVE}; font-size:10px; font-weight:700; "
            f"margin-top:6px;"
        )
        dig_label.setAlignment(Qt.AlignCenter)
        self._anim_lay.addWidget(dig_label)

        dig_grid_w = QWidget()
        dig_grid = QGridLayout(dig_grid_w)
        dig_grid.setSpacing(4)
        pins = DIGITAL_PINS.get(self._modelo, [])
        for idx, (name, pin_id) in enumerate(pins):
            led = DigitalLedWidget(name, pin_id)
            self._dig_w[pin_id] = led
            dig_grid.addWidget(led, idx // 4, idx % 4)
        row_dg = QHBoxLayout()
        row_dg.addStretch()
        row_dg.addWidget(dig_grid_w)
        row_dg.addStretch()
        self._anim_lay.addLayout(row_dg)
        self._anim_lay.addStretch()

        # Selector de digitales para prueba completa
        self._build_pwm_sliders()
        self._build_dig_selector()
        self._update_dig_pin_combo()

    def _build_pwm_sliders(self):
        # Limpia sliders anteriores
        while self._pwm_sliders_lay.count():
            item = self._pwm_sliders_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._pwm_slider_widgets = {}

        n_motors = 0 if self._modelo == "IoT" else 4
        for i, motor in enumerate(range(1, n_motors + 1)):
            lbl = QLabel(f"M{motor}:")
            lbl.setFixedWidth(26)
            lbl.setStyleSheet(f"color:{C_PEACH}; font-weight:700; font-size:11px;")

            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 255)
            slider.setValue(0)
            slider.setStyleSheet(self._slider_style())
            slider.setMinimumWidth(100)

            lbl_val = QLabel("0")
            lbl_val.setFixedWidth(28)
            lbl_val.setStyleSheet(f"color:{C_TEXT}; font-size:11px;")
            slider.valueChanged.connect(
                lambda v, l=lbl_val: l.setText(str(v)))

            btn = QPushButton("Set")
            btn.setFixedWidth(40)
            btn.setFixedHeight(24)
            btn.setStyleSheet(self._bstyle())
            btn.clicked.connect(lambda _, m=motor: self._manual_pwm(m))

            self._pwm_sliders_lay.addWidget(lbl,     i, 0)
            self._pwm_sliders_lay.addWidget(slider,  i, 1)
            self._pwm_sliders_lay.addWidget(lbl_val, i, 2)
            self._pwm_sliders_lay.addWidget(btn,     i, 3)
            self._pwm_slider_widgets[motor] = (slider, lbl_val)

        # Fila de botones rapidos (0%, 50%, 100%, parar todos)
        if n_motors > 0:
            quick_row = QHBoxLayout()
            for label, val in [("0%", 0), ("50%", 128), ("100%", 255)]:
                btn_q = QPushButton(label)
                btn_q.setFixedHeight(22)
                btn_q.setStyleSheet(self._bstyle())
                btn_q.clicked.connect(
                    lambda _, v=val: self._set_all_pwm_sliders(v))
                quick_row.addWidget(btn_q)
            btn_stop = QPushButton("Parar todos")
            btn_stop.setFixedHeight(22)
            btn_stop.setStyleSheet(
                f"QPushButton {{ background:#7f1d1d; color:{C_RED}; "
                f"border:1px solid #ef4444; border-radius:4px; "
                f"font-size:11px; font-weight:700; }}"
                f"QPushButton:hover {{ background:#991b1b; }}"
            )
            btn_stop.clicked.connect(self._stop_all_motors)
            quick_row.addWidget(btn_stop)
            self._pwm_sliders_lay.addLayout(
                quick_row, n_motors, 0, 1, 4)

    def _set_all_pwm_sliders(self, value: int):
        for slider, _ in self._pwm_slider_widgets.values():
            slider.setValue(value)

    def _stop_all_motors(self):
        for motor, (slider, _) in self._pwm_slider_widgets.items():
            slider.setValue(0)
            self._send_cmd(CMD_PWM, motor, 0,
                           callback=lambda ok, ack, c, v, m=motor:
                           self._animate(CMD_PWM, m, 0, ok, v))

    def _build_dig_selector(self):
        # Limpia el grid de checkboxes
        while self._dig_sel_lay.count():
            item = self._dig_sel_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._dig_checks = {}

        pins = DIGITAL_PINS.get(self._modelo, [])
        if not pins:
            lbl = QLabel("Sin pines digitales en este modelo.")
            lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
            self._dig_sel_lay.addWidget(lbl, 0, 0)
            return

        # Botones seleccionar/deseleccionar todo
        btn_all  = QPushButton("Todos")
        btn_none = QPushButton("Ninguno")
        btn_all.setFixedHeight(24)
        btn_none.setFixedHeight(24)
        btn_all.setStyleSheet(self._bstyle())
        btn_none.setStyleSheet(self._bstyle())
        btn_all.clicked.connect(
            lambda: [cb.setChecked(True) for cb in self._dig_checks.values()])
        btn_none.clicked.connect(
            lambda: [cb.setChecked(False) for cb in self._dig_checks.values()])
        row_btns = QHBoxLayout()
        row_btns.addWidget(btn_all)
        row_btns.addWidget(btn_none)
        row_btns.addStretch()
        self._dig_sel_lay.addLayout(row_btns, 0, 0, 1, 4)

        for idx, (name, pin_id) in enumerate(pins):
            cb = QCheckBox(f"{name}  (0x{pin_id:02X})")
            cb.setChecked(True)
            cb.setStyleSheet(
                f"QCheckBox {{ color:{C_TEXT}; font-size:11px; spacing:6px; }}"
                f"QCheckBox::indicator {{ width:14px; height:14px; "
                f"border:2px solid {C_MAUVE}; border-radius:3px; "
                f"background:{C_SURFACE}; }}"
                f"QCheckBox::indicator:checked {{ background:{C_MAUVE}; }}"
            )
            self._dig_checks[pin_id] = cb
            self._dig_sel_lay.addWidget(cb, (idx // 4) + 1, idx % 4)

    def _update_dig_pin_combo(self):
        # Actualiza el combo de seleccion de pin para control manual
        self._combo_dig_pin.clear()
        for name, pin_id in DIGITAL_PINS.get(self._modelo, []):
            self._combo_dig_pin.addItem(f"{name} (0x{pin_id:02X})", pin_id)

    # ── Conexion ─────────────────────────────────────────────────
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
            self._lbl_conn.setText("Conectado")
            self._lbl_conn.setStyleSheet(f"color:{C_GREEN}; font-weight:600;")
            self._btn_conn.setText("Desconectar")
            self._log_line(f"Conectado a {port} @ {baud}", C_BLUE)
            self.status_msg.emit(f"Conectado: {port}")
        except Exception as e:
            self._btn_conn.setChecked(False)
            self._log_line(f"Error: {e}", C_RED)
            self.status_msg.emit(f"Error: {e}")

    def _disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self._lbl_conn.setText("Desconectado")
        self._lbl_conn.setStyleSheet(f"color:{C_RED}; font-weight:600;")
        self._btn_conn.setText("Conectar")
        self._btn_conn.setChecked(False)
        self._log_line("Desconectado.", C_YELLOW)
        self.status_msg.emit("Desconectado.")

    # ── Modelo ───────────────────────────────────────────────────
    def _on_model_changed(self, modelo: str):
        self._modelo = modelo
        self._build_anim_widgets()
        self._reset_ui()
        self._log_line(f"Modelo: {modelo}", C_TEAL)

    # ── Prueba completa ──────────────────────────────────────────
    def _start_full_test(self):
        if not self.ser or not self.ser.is_open:
            self._log_line("Sin conexion serial.", C_RED)
            return

        # Construir cola: pruebas base + digitales seleccionados
        self._full_queue = list(PRUEBAS_BASE[self._modelo])
        for pin_id, cb in self._dig_checks.items():
            if cb.isChecked():
                name = next(
                    (n for n, pid in DIGITAL_PINS[self._modelo] if pid == pin_id),
                    f"DIG 0x{pin_id:02X}"
                )
                self._full_queue.append(
                    (name, CMD_DIGITAL, pin_id, 1, f"{name} ON")
                )

        if not self._full_queue:
            self._log_line("No hay pruebas seleccionadas.", C_YELLOW)
            return

        self._table.clear_results()
        self._lbl_badge.hide()
        self._reset_anim()
        self._prueba_idx = 0
        self._running    = True
        self._btn_full.setEnabled(False)
        self.status_msg.emit(f"Prueba completa: {self._modelo}...")
        self._run_next()

    def _run_next(self):
        if self._prueba_idx >= len(self._full_queue):
            self._finish_test()
            return
        nombre, cmd, pin_id, value, desc = self._full_queue[self._prueba_idx]
        n = self._prueba_idx + 1
        total = len(self._full_queue)
        self._log_line(f"[{n}/{total}] {nombre}: {desc}", C_SUBTEXT)
        self._send_cmd(
            cmd, pin_id, value,
            callback=lambda ok, ack, c, v: self._on_result(
                ok, ack, c, v, nombre, desc, cmd, pin_id, value
            )
        )

    def _on_result(self, ok, ack, cmd_r, val,
                   nombre, desc, cmd, pin_id, value):
        cmd_str = self._cmd_str(cmd, pin_id, value)
        self._table.add_result(nombre, desc, cmd_str, ack, val, ok)
        self._animate(cmd, pin_id, value, ok, val)
        self._log_line(
            f"  -> ACK=0x{ack:02X} VAL={val} {'PASS' if ok else 'FAIL'}",
            C_GREEN if ok else C_RED
        )
        self._prueba_idx += 1
        QTimer.singleShot(300, self._run_next)

    def _finish_test(self):
        self._running = False
        self._btn_full.setEnabled(True)
        total = self._table.rowCount()
        fails = sum(
            1 for r in range(total)
            if self._table.item(r, 5) and
               self._table.item(r, 5).text() == "FAIL"
        )
        if fails == 0:
            self._lbl_badge.setText(
                f"TODAS LAS PRUEBAS PASARON  ({total}/{total})")
            self._lbl_badge.setStyleSheet(
                f"background:#14532d; color:{C_GREEN}; border-radius:8px;")
        else:
            self._lbl_badge.setText(f"FALLARON {fails} DE {total} PRUEBAS")
            self._lbl_badge.setStyleSheet(
                f"background:#7f1d1d; color:{C_RED}; border-radius:8px;")
        self._lbl_badge.show()
        self.status_msg.emit(
            f"Prueba completa: {total-fails}/{total} PASS")

    # ── Controles manuales ───────────────────────────────────────
    def _manual_pwm(self, motor: int = 1):
        if motor not in self._pwm_slider_widgets:
            return
        slider, _ = self._pwm_slider_widgets[motor]
        v = slider.value()
        self._send_cmd(CMD_PWM, motor, v,
                       callback=lambda ok, ack, c, val, m=motor:
                       self._animate(CMD_PWM, m, v, ok, val))

    def _manual_servo(self):
        v = self._slider_srv.value()
        self._send_cmd(CMD_SERVO, 0x00, v,
                       callback=lambda ok, ack, c, val:
                       self._animate(CMD_SERVO, 0x00, v, ok, val))

    def _manual_neo(self):
        idx_map = [0x00, 0x01, 0x02, 0x03, 0xFF]
        v = idx_map[self._combo_neo.currentIndex()]
        self._send_cmd(CMD_NEOPIXEL, 0x00, v,
                       callback=lambda ok, ack, c, val:
                       self._animate(CMD_NEOPIXEL, 0x00, v, ok, val))

    def _manual_digital(self, state: int):
        pin_id = self._combo_dig_pin.currentData()
        if pin_id is None:
            return
        self._send_cmd(CMD_DIGITAL, pin_id, state,
                       callback=lambda ok, ack, c, val:
                       self._animate(CMD_DIGITAL, pin_id, state, ok, val))

    # ── Envio ────────────────────────────────────────────────────
    def _send_cmd(self, cmd, pin_id, value, callback=None):
        if not self.ser or not self.ser.is_open:
            self._log_line("Sin conexion.", C_RED)
            return
        self._log_line(f"-> {self._cmd_str(cmd, pin_id, value)}", C_BLUE)
        self._worker = SerialWorker(self.ser, cmd, pin_id, value, self._mode)
        if callback:
            self._worker.result.connect(
                lambda ok, ack, c, v: callback(ok, ack, c, v))
        self._worker.result.connect(
            lambda ok, ack, c, v: self._log_line(
                f"<- ACK=0x{ack:02X} VAL={v}",
                C_GREEN if ok else C_RED))
        self._worker.start()

    # ── Animaciones ──────────────────────────────────────────────
    def _animate(self, cmd, pin_id, value, ok, measured):
        if cmd == CMD_PWM:
            if pin_id in self._motors:
                self._motors[pin_id].set_speed(value, ok)
        elif cmd == CMD_SERVO:
            if self._servo_w:
                self._servo_w.set_angle(value, ok)
        elif cmd == CMD_NEOPIXEL:
            if self._neo_w:
                self._neo_w.set_color(value, ok)
            if self._matrix:
                row = (pin_id >> 4) & 0x0F
                col =  pin_id & 0x0F
                self._matrix.set_pixel(row, col, value)
        elif cmd == CMD_DIGITAL:
            if pin_id in self._dig_w:
                self._dig_w[pin_id].set_state(bool(value), ok)

    def _reset_anim(self):
        for m in self._motors.values():  m.reset()
        if self._servo_w: self._servo_w.reset()
        if self._neo_w:   self._neo_w.reset()
        if self._matrix:  self._matrix.reset()
        for led in self._dig_w.values(): led.reset()

    def _reset_ui(self):
        self._reset_anim()
        self._table.clear_results()
        self._lbl_badge.hide()
        self._prueba_idx = 0
        self._running    = False
        self._full_queue = []
        self._btn_full.setEnabled(True)

    # ── Helpers ──────────────────────────────────────────────────
    def _cmd_str(self, cmd, pin_id, value) -> str:
        if cmd == CMD_PWM:
            return f"pwm {pin_id} {value} ({int(value/255*100)}%)"
        if cmd == CMD_SERVO:
            return f"servo {value}°"
        if cmd == CMD_NEOPIXEL:
            return f"neo {NEO_NAMES.get(value, hex(value))}"
        if cmd == CMD_DIGITAL:
            name = next(
                (n for n, pid in DIGITAL_PINS.get(self._modelo, [])
                 if pid == pin_id), f"0x{pin_id:02X}")
            return f"digital {name} = {value}"
        if cmd == CMD_PING:  return "ping"
        return f"0x{cmd:02X} 0x{pin_id:02X} {value}"

    def _log_line(self, msg: str, color: str = C_TEXT):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(
            f'<span style="color:{C_SUBTEXT}">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )
        self._log.moveCursor(QTextCursor.End)

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color:{C_TEXT}; font-weight:600;")
        return l

    def _gstyle(self, accent: str) -> str:
        return (
            f"QGroupBox {{ border:1px solid {C_OVERLAY}; border-radius:8px; "
            f"margin-top:10px; font-weight:bold; color:{accent}; padding:8px; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; "
            f"left:10px; padding:0 6px; }}"
        )

    def _bstyle(self) -> str:
        return (
            f"QPushButton {{ background:{C_SURFACE}; color:{C_TEXT}; "
            f"border:1px solid {C_OVERLAY}; border-radius:4px; "
            f"font-size:11px; padding:4px 8px; }}"
            f"QPushButton:hover {{ background:{C_OVERLAY}; }}"
            f"QPushButton:disabled {{ background:{C_MANTLE}; "
            f"color:{C_OVERLAY}; }}"
        )

    def _slider_style(self) -> str:
        return (
            f"QSlider::groove:horizontal {{ height:4px; "
            f"background:{C_OVERLAY}; border-radius:2px; }}"
            f"QSlider::handle:horizontal {{ background:{C_BLUE}; "
            f"width:14px; height:14px; margin:-5px 0; "
            f"border-radius:7px; }}"
            f"QSlider::sub-page:horizontal {{ background:{C_BLUE}; "
            f"border-radius:2px; }}"
        )

    def cleanup(self):
        self._disconnect()
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
