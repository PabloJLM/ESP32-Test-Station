import sys
import os
import re
import serial
import serial.tools.list_ports
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QGroupBox, QPushButton, QLabel, QComboBox,
    QLineEdit, QTextEdit, QSlider, QSplitter, QStatusBar, QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QTextCursor

from validacion    import TabValidacion
from tab_buscador  import TabBuscador
from tab_dashboard import TabDashboard


# ══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN GLOBAL
# ══════════════════════════════════════════════════════════════

# Google Sheets
SHEET_ID   = '13WIYurPQvRztU1xpUru8-COzgfdPzqvTP4hEZM6pX2I'
HEADER_ROW = 1
COL_ESTADO    = 'A'
COL_ID        = 'B'
COL_QR        = 'C'
COL_TIMESTAMP = 'D'
COL_NOTAS     = 'E'

SHEET_MAP = {
    "ESP32":       "ESP32",
    "ROBOFUT":     "Robofut",
    "TODOTERRENO": "Todoterreno",
    "STEM_SR":     "STEM SR",
    "STEM_JR":     "STEM JR",
    "DRONES":      "Drones",
    "IOT":         "IOT",
}

QR_PATTERN = re.compile(
    r'^(ESP32|ROBOFUT|TODOTERRENO|STEM_SR|STEM_JR|DRONES|IOT)-BALAM-(\d+)$',
    re.IGNORECASE
)

# Protocolo serial Maestro/Slave
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

# Stylesheet (Catppuccin Mocha)
STYLE = """
QMainWindow, QWidget          { background: #1e1e2e; color: #cdd6f4; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QTabWidget::pane              { border: 1px solid #45475a; border-radius: 6px; background: #1e1e2e; }
QTabBar::tab                  { background: #313244; color: #cdd6f4; padding: 8px 22px;
                                 border-bottom: 2px solid transparent; font-size: 12px; font-weight: 600; min-width: 160px; }
QTabBar::tab:selected         { background: #1e1e2e; color: #89b4fa; border-bottom: 2px solid #89b4fa; }
QTabBar::tab:hover            { background: #45475a; }
QGroupBox                     { border: 1px solid #45475a; border-radius: 6px; margin-top: 10px;
                                 font-weight: bold; color: #89b4fa; padding: 6px; }
QGroupBox::title              { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QPushButton                   { background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                                 border-radius: 5px; padding: 5px 12px; font-size: 12px; }
QPushButton:hover             { background: #45475a; }
QPushButton:pressed           { background: #585b70; }
QPushButton:checked           { background: #a6e3a1; color: #1e1e2e; }
QPushButton:disabled          { background: #252535; color: #585b70; border-color: #313244; }
QPushButton[primary="true"]   { background: #2563eb; color: white; border: none; font-weight: 700; }
QPushButton[primary="true"]:hover     { background: #1d4ed8; }
QPushButton[primary="true"]:disabled  { background: #1e3a6e; color: #7a9fd6; }
QPushButton[success="true"]   { background: #14532d; color: #86efac; border: 1px solid #22c55e; font-weight: 700; }
QPushButton[success="true"]:hover     { background: #166534; }
QPushButton[danger="true"]    { background: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; font-weight: 700; }
QPushButton[danger="true"]:hover      { background: #991b1b; }
QComboBox, QLineEdit, QSpinBox { background: #313244; color: #cdd6f4; border: 1px solid #45475a;
                                  border-radius: 4px; padding: 4px 8px; }
QComboBox:focus, QLineEdit:focus      { border-color: #89b4fa; }
QComboBox::drop-down          { border: none; }
QComboBox QAbstractItemView   { background: #313244; color: #cdd6f4; border: 1px solid #45475a; }
QTextEdit                     { background: #11111b; color: #a6e3a1; border: 1px solid #45475a; border-radius: 4px; }
QSlider::groove:horizontal    { height: 6px; background: #45475a; border-radius: 3px; }
QSlider::handle:horizontal    { background: #89b4fa; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
QSlider::sub-page:horizontal  { background: #89b4fa; border-radius: 3px; }
QStatusBar                    { background: #181825; color: #6c7086; }
QSplitter::handle             { background: #45475a; width: 2px; }
QLabel                        { color: #cdd6f4; }
"""


# ══════════════════════════════════════════════════════════════
#  HILO LECTOR SERIAL
# ══════════════════════════════════════════════════════════════
class SerialReader(QThread):
    data_received   = pyqtSignal(str)
    connection_lost = pyqtSignal()

    def __init__(self, ser):
        super().__init__()
        self.ser      = ser
        self._running = True
        self._buf     = bytearray()

    def run(self):
        while self._running:
            try:
                if self.ser and self.ser.is_open:
                    waiting = self.ser.in_waiting
                    if waiting:
                        self._buf.extend(self.ser.read(waiting))
                        self._flush_buffer()
                self.msleep(15)
            except Exception:
                self.connection_lost.emit()
                break

    def _flush_buffer(self):
        while self._buf:
            for sep in (b'\r\n', b'\n'):
                idx = self._buf.find(sep)
                if idx != -1:
                    line = self._buf[:idx]
                    self._buf = self._buf[idx + len(sep):]
                    text = line.decode('latin-1', errors='replace').strip()
                    if text:
                        self.data_received.emit(f"← TEXT: {text}")
                    return
            b = self._buf[0]
            if not ((0x20 <= b <= 0x7E) or b in (0x09, 0x0A, 0x0D)):
                self._buf.pop(0)
                self.data_received.emit(f"← BIN: 0x{b:02X}  [{RESPONSES.get(b, 'desconocido')}]")
                return
            break

    def stop(self):
        self._running = False
        self.wait()


# ══════════════════════════════════════════════════════════════
#  PESTAÑA TESTER SERIAL
# ══════════════════════════════════════════════════════════════
class TabTester(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ser    = None
        self.reader = None
        self._build_ui()
        self._refresh_ports()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)
        root.addWidget(self._build_conn_bar())
        root.addWidget(self._build_splitter(), 1)

    def _build_conn_bar(self):
        box = QGroupBox("Conexión Serial")
        lay = QHBoxLayout(box)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(140)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "57600", "115200", "230400"])
        self.baud_combo.setCurrentText("9600")
        self.btn_refresh = QPushButton("Puertos")
        self.btn_connect = QPushButton("Conectar")
        self.btn_connect.setCheckable(True)
        self.btn_connect.setFixedWidth(110)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["MAESTRO (texto)", "SLAVE (binario)"])
        self.mode_combo.setToolTip(
            "MAESTRO: envía texto (ping, pwm 1 128…) al ESP32 Maestro via USB\n"
            "SLAVE: envía bytes binarios [CMD, PIN, VAL] directo al ESP32 Slave"
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.lbl_status = QLabel("Desconectado")
        self.lbl_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
        lay.addWidget(QLabel("Puerto:"))
        lay.addWidget(self.port_combo)
        lay.addWidget(QLabel("Baud:"))
        lay.addWidget(self.baud_combo)
        lay.addWidget(self.btn_refresh)
        lay.addWidget(QLabel("Modo:"))
        lay.addWidget(self.mode_combo)
        lay.addWidget(self.btn_connect)
        lay.addWidget(self.lbl_status)
        lay.addStretch()
        self.btn_refresh.clicked.connect(self._refresh_ports)
        self.btn_connect.clicked.connect(self._toggle_connection)
        return box

    def _build_splitter(self):
        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        ll   = QVBoxLayout(left)
        ll.setSpacing(8)
        ll.addWidget(self._build_quick_commands())
        ll.addWidget(self._build_pwm_panel())
        ll.addWidget(self._build_digital_panel())
        ll.addWidget(self._build_servo_panel())
        ll.addWidget(self._build_neopixel_panel())
        ll.addStretch()
        splitter.addWidget(left)
        right = QWidget()
        rl    = QVBoxLayout(right)
        rl.setSpacing(6)
        rl.addWidget(self._build_terminal())
        rl.addWidget(self._build_raw_command())
        splitter.addWidget(right)
        splitter.setSizes([380, 520])
        return splitter

    def _build_quick_commands(self):
        box = QGroupBox("Comandos Rápidos")
        lay = QHBoxLayout(box)
        for label, fn in [("PING", self._send_ping), ("RESET", self._send_reset), ("STATUS", self._send_status)]:
            btn = QPushButton(label)
            btn.clicked.connect(fn)
            lay.addWidget(btn)
        return box

    def _build_pwm_panel(self):
        box  = QGroupBox("PWM — Motores (0-255)")
        grid = QGridLayout(box)
        self._pwm_sliders = {}
        self._pwm_labels  = {}
        for i, motor in enumerate([1, 2, 3, 4]):
            slider  = QSlider(Qt.Horizontal)
            slider.setRange(0, 255)
            slider.setValue(0)
            val_lbl = QLabel("0")
            val_lbl.setFixedWidth(30)
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            btn = QPushButton("Set")
            btn.setFixedWidth(45)
            btn.clicked.connect(lambda _, m=motor: self._send_pwm(m))
            slider.valueChanged.connect(lambda v, l=val_lbl: l.setText(str(v)))
            self._pwm_sliders[motor] = slider
            self._pwm_labels[motor]  = val_lbl
            grid.addWidget(QLabel(f"M{motor}:"), i, 0)
            grid.addWidget(slider,  i, 1)
            grid.addWidget(val_lbl, i, 2)
            grid.addWidget(btn,     i, 3)
        return box

    def _build_digital_panel(self):
        box  = QGroupBox("Digital — Dirección Motores")
        grid = QGridLayout(box)
        pins = [
            ("M1 AIN1 (0x11)", 0x11), ("M1 AIN2 (0x12)", 0x12),
            ("M2 AIN1 (0x21)", 0x21), ("M2 AIN2 (0x22)", 0x22),
            ("M3 AIN1 (0x31)", 0x31), ("M3 AIN2 (0x32)", 0x32),
            ("M4 AIN1 (0x41)", 0x41), ("M4 AIN2 (0x42)", 0x42),
        ]
        for i, (name, pid) in enumerate(pins):
            lbl   = QLabel(name)
            lbl.setFixedWidth(135)
            b_on  = QPushButton("ON")
            b_off = QPushButton("OFF")
            b_on.setFixedWidth(45)
            b_off.setFixedWidth(45)
            b_on.clicked.connect(lambda _, p=pid: self._send_digital(p, 1))
            b_off.clicked.connect(lambda _, p=pid: self._send_digital(p, 0))
            row, col = divmod(i, 2)
            base = col * 3
            grid.addWidget(lbl,   row, base)
            grid.addWidget(b_on,  row, base + 1)
            grid.addWidget(b_off, row, base + 2)
        return box

    def _build_servo_panel(self):
        box = QGroupBox("Servo (0-180°)")
        lay = QHBoxLayout(box)
        self.servo_slider = QSlider(Qt.Horizontal)
        self.servo_slider.setRange(0, 180)
        self.servo_slider.setValue(90)
        self.servo_val = QLabel("90°")
        self.servo_val.setFixedWidth(38)
        self.servo_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        btn = QPushButton("Set Servo")
        self.servo_slider.valueChanged.connect(lambda v: self.servo_val.setText(f"{v}°"))
        btn.clicked.connect(self._send_servo)
        lay.addWidget(QLabel("Ángulo:"))
        lay.addWidget(self.servo_slider)
        lay.addWidget(self.servo_val)
        lay.addWidget(btn)
        return box

    def _build_neopixel_panel(self):
        box  = QGroupBox("NeoPixel")
        lay  = QHBoxLayout(box)
        opts = [
            ("OFF",    "#555555", 0x00), ("ROJO",   "#e74c3c", 0x01),
            ("VERDE",  "#2ecc71", 0x02), ("AZUL",   "#3498db", 0x03),
            ("BLANCO", "#ecf0f1", 0xFF),
        ]
        for label, color, val in opts:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton {{ background:{color}; color:{'#111' if val==0xFF else 'white'}; "
                f"font-weight:bold; border-radius:5px; padding:4px 8px; }}"
            )
            btn.clicked.connect(lambda _, v=val: self._send_neopixel(v))
            lay.addWidget(btn)
        return box

    def _build_terminal(self):
        box = QGroupBox("Terminal")
        lay = QVBoxLayout(box)
        hdr = QHBoxLayout()
        btn_cl = QPushButton("Limpiar")
        btn_cl.setFixedWidth(80)
        btn_cl.clicked.connect(self._clear_terminal)
        hdr.addStretch()
        hdr.addWidget(btn_cl)
        lay.addLayout(hdr)
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFont(QFont("Courier New", 10))
        self.terminal.setMinimumHeight(300)
        lay.addWidget(self.terminal)
        return box

    def _build_raw_command(self):
        box = QGroupBox("Comando Raw")
        lay = QVBoxLayout(box)
        examples = QHBoxLayout()
        for ex in ["ping", "pwm 1 128", "servo 90", "neo 1", "digital 11 1", "reset"]:
            btn = QPushButton(ex)
            btn.setStyleSheet("font-size:10px; padding:2px 6px;")
            btn.clicked.connect(lambda _, t=ex: self.raw_input.setText(t))
            examples.addWidget(btn)
        lay.addLayout(examples)
        row = QHBoxLayout()
        self.raw_input = QLineEdit()
        self.raw_input.setPlaceholderText('"pwm 1 200"  o  "servo 45"  o  "ping"')
        self.raw_input.returnPressed.connect(self._send_raw)
        btn_send = QPushButton("Enviar ↵")
        btn_send.setFixedWidth(90)
        btn_send.clicked.connect(self._send_raw)
        row.addWidget(self.raw_input)
        row.addWidget(btn_send)
        lay.addLayout(row)
        return box

    # ── Serial ──────────────────────────────────────────────────
    def _refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(p.device)
        if not ports:
            self.port_combo.addItem("(sin puertos)")

    def _toggle_connection(self, checked):
        self._connect() if checked else self._disconnect()

    def _connect(self):
        port = self.port_combo.currentText()
        baud = int(self.baud_combo.currentText())
        try:
            self.ser    = serial.Serial(port, baud, timeout=0.1)
            self.reader = SerialReader(self.ser)
            self.reader.data_received.connect(lambda m: self._log(m, "#a6e3a1"))
            self.reader.connection_lost.connect(self._on_lost)
            self.reader.start()
            self.lbl_status.setText("● Conectado")
            self.lbl_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.btn_connect.setText("Desconectar")
            self.status_msg.emit(f"Conectado a {port} @ {baud}")
            self._log(f"[SISTEMA] Conectado a {port} @ {baud} baud", "#89b4fa")
        except Exception as e:
            self.btn_connect.setChecked(False)
            self._log(f"[ERROR] {e}", "#f38ba8")
            self.status_msg.emit(f"Error: {e}")

    def _disconnect(self):
        if self.reader:
            self.reader.stop()
            self.reader = None
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.lbl_status.setText("Desconectado")
        self.lbl_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self.btn_connect.setText("Conectar")
        self.btn_connect.setChecked(False)
        self._log("[SISTEMA] Desconectado", "#f9e2af")
        self.status_msg.emit("Desconectado.")

    def _on_lost(self):
        self._log("[SISTEMA] Conexión perdida", "#f38ba8")
        self._disconnect()

    def _is_master_mode(self):
        return self.mode_combo.currentIndex() == 0

    def _on_mode_changed(self, idx):
        self._log(f"[MODO] {'MAESTRO (texto)' if idx==0 else 'SLAVE (binario)'}", "#f9e2af")
        self.raw_input.setPlaceholderText(
            '"ping"  "pwm 1 200"  "servo 45"  "neo 1"  "reset"' if idx == 0
            else 'Bytes hex: F0 00 00  ó  01 02 80'
        )

    def _bytes_to_text(self, cmd, pin_id, value):
        if cmd == CMD_PING:    return "ping"
        if cmd == CMD_RESET:   return "reset"
        if cmd == CMD_PWM:     return f"pwm {pin_id} {value}"
        if cmd == CMD_SERVO:   return f"servo {value}"
        if cmd == CMD_DIGITAL:
            return f"digital {(pin_id >> 4) * 10 + (pin_id & 0x0F)} {value}"
        if cmd == CMD_NEOPIXEL:
            return f"neo {'ff' if value == 0xFF else value}"
        return f"raw {cmd} {pin_id} {value}"

    def _send_bytes(self, cmd, pin_id, value, label):
        if not self.ser or not self.ser.is_open:
            self._log("[ERROR] No conectado", "#f38ba8")
            return
        try:
            if self._is_master_mode():
                text_cmd = self._bytes_to_text(cmd, pin_id, value)
                self.ser.write((text_cmd + "\n").encode())
                self._log(f'→ TEXT: "{text_cmd}"  [{cmd:#04x} {pin_id:#04x} {value:#04x}]', "#89dceb")
            else:
                self.ser.write(bytes([cmd, pin_id, value]))
                self._log(f"→ BIN: {label}  [{cmd:#04x} {pin_id:#04x} {value:#04x}]", "#89dceb")
        except Exception as e:
            self._log(f"[ERROR] {e}", "#f38ba8")

    def _send_raw(self):
        text = self.raw_input.text().strip()
        if not text:
            return
        if not self.ser or not self.ser.is_open:
            self._log("[ERROR] No conectado", "#f38ba8")
            return
        try:
            if self._is_master_mode():
                self.ser.write((text + "\n").encode())
                self._log(f'→ TEXT: "{text}"', "#cba6f7")
            else:
                buf = bytes(int(p, 16) for p in text.split())
                self.ser.write(buf)
                self._log(f'→ BIN: {" ".join(f"0x{b:02X}" for b in buf)}', "#cba6f7")
            self.raw_input.clear()
        except Exception as e:
            self._log(f"[ERROR] {e}", "#f38ba8")

    def _send_ping(self):    self._send_bytes(CMD_PING,    0x00, 0x00, "PING")
    def _send_reset(self):   self._send_bytes(CMD_RESET,   0x00, 0x00, "RESET")
    def _send_status(self):
        self._log("[INFO] Verificando conexión — envía un PING", "#f9e2af")
        self._send_ping()
    def _send_pwm(self, motor):
        self._send_bytes(CMD_PWM, motor, self._pwm_sliders[motor].value(), f"PWM M{motor}")
    def _send_digital(self, pin_id, value):
        self._send_bytes(CMD_DIGITAL, pin_id, value, f"DIGITAL 0x{pin_id:02X}={value}")
    def _send_servo(self):
        self._send_bytes(CMD_SERVO, 0x00, self.servo_slider.value(), "SERVO")
    def _send_neopixel(self, color):
        names = {0x00: "OFF", 0x01: "ROJO", 0x02: "VERDE", 0x03: "AZUL", 0xFF: "BLANCO"}
        self._send_bytes(CMD_NEOPIXEL, 0x00, color, f"NEOPIXEL={names.get(color, hex(color))}")

    def _log(self, msg, color="#cdd6f4"):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.terminal.append(
            f'<span style="color:#585b70">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )
        self.terminal.moveCursor(QTextCursor.End)

    def _clear_terminal(self):
        self.terminal.clear()

    def cleanup(self):
        self._disconnect()


# ══════════════════════════════════════════════════════════════
#  VENTANA PRINCIPAL
# ══════════════════════════════════════════════════════════════
class ESP32Tester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tesla Lab — ESP32 Tester")
        self.setMinimumSize(1050, 720)
        self.logo_path = self._find_logo()
        self._build_ui()
        self.setStyleSheet(STYLE)

    def _find_logo(self):
        base = os.path.dirname(os.path.abspath(__file__))
        for candidate in [
            os.path.join(base, "imgs", "LOGO TESLA-13.png"),
            os.path.join(base, "LOGO_TESLA-13.png"),
        ]:
            if os.path.exists(candidate):
                return candidate
        return None

    def _build_ui(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo.")

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_banner())
        root.addWidget(self._build_tabs(), 1)

    def _build_banner(self):
        banner = QWidget()
        banner.setStyleSheet("background:#181825; border-bottom:1px solid #45475a;")
        banner.setFixedHeight(52)
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(14, 6, 14, 6)
        if self.logo_path:
            lbl = QLabel()
            lbl.setPixmap(QPixmap(self.logo_path).scaledToHeight(36, Qt.SmoothTransformation))
        else:
            lbl = QLabel("TESLA LAB")
            lbl.setFont(QFont("Segoe UI", 16, QFont.Bold))
            lbl.setStyleSheet("color:#fab387;")
        lay.addWidget(lbl)
        lay.addStretch()
        return banner

    def _build_tabs(self):
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        self.tab_tester     = TabTester()
        self.tab_validacion = TabValidacion(
            logo_path=self.logo_path,
            sheet_id=SHEET_ID,
            sheet_map=SHEET_MAP,
            qr_pattern=QR_PATTERN,
            col_config=(COL_ESTADO, COL_ID, COL_QR, COL_TIMESTAMP, COL_NOTAS),
            header_row=HEADER_ROW,
        )
        self.tab_buscador = TabBuscador(
            sheet_id=SHEET_ID,
            sheet_map=SHEET_MAP,
            header_row=HEADER_ROW,
        )
        self.tab_dashboard = TabDashboard(
            sheet_id=SHEET_ID,
            sheet_map=SHEET_MAP,
            header_row=HEADER_ROW,
        )

        tabs.addTab(self.tab_tester,     "Tester Serial")
        tabs.addTab(self.tab_validacion, "Validacion QR")
        tabs.addTab(self.tab_buscador,   "Buscador")
        tabs.addTab(self.tab_dashboard,  "Dashboard")

        self.tab_tester.status_msg.connect(self.status_bar.showMessage)
        self.tab_validacion.status_msg.connect(self.status_bar.showMessage)
        self.tab_buscador.status_msg.connect(self.status_bar.showMessage)
        self.tab_dashboard.status_msg.connect(self.status_bar.showMessage)
        return tabs

    def closeEvent(self, event):
        self.tab_tester.cleanup()
        self.tab_validacion.cleanup()
        self.tab_buscador.cleanup()
        self.tab_dashboard.cleanup()
        event.accept()


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ESP32Tester()
    window.show()
    sys.exit(app.exec_())