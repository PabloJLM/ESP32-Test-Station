#!/usr/bin/env python3
"""
ESP32 Serial Tester GUI
Compatible con el protocolo Maestro/Slave de ESP32
Requiere: pip install pyserial PyQt5
"""

import sys
import serial
import serial.tools.list_ports
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QGroupBox, QPushButton, QLabel, QComboBox,
    QLineEdit, QTextEdit, QSlider, QSpinBox, QSplitter,
    QFrame, QStatusBar, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QTextCursor, QPalette


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

# ─── Hilo lector serial ───────────────────────────────────────
class SerialReader(QThread):
    data_received = pyqtSignal(str)
    connection_lost = pyqtSignal()

    def __init__(self, ser):
        super().__init__()
        self.ser = ser
        self._running = True

    def run(self):
        while self._running:
            try:
                if self.ser and self.ser.is_open and self.ser.in_waiting:
                    byte = self.ser.read(1)
                    val = byte[0]
                    desc = RESPONSES.get(val, "desconocido")
                    msg = f"← 0x{val:02X}  ({desc})"
                    self.data_received.emit(msg)
                self.msleep(20)
            except Exception as e:
                self.connection_lost.emit()
                break

    def stop(self):
        self._running = False
        self.wait()


# ─── Ventana principal ────────────────────────────────────────
class ESP32Tester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ser = None
        self.reader = None
        self.setWindowTitle("ESP32 Serial Tester — Protocolo Maestro/Slave")
        self.setMinimumSize(900, 680)
        self._build_ui()
        self._apply_style()
        self._refresh_ports()

    # ── UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Barra conexión ─────────────────────────────────────
        conn_box = QGroupBox("Conexión Serial")
        conn_lay = QHBoxLayout(conn_box)

        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(140)
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "57600", "115200", "230400"])
        self.baud_combo.setCurrentText("115200")

        self.btn_refresh = QPushButton("↻ Puertos")
        self.btn_connect = QPushButton("Conectar")
        self.btn_connect.setCheckable(True)
        self.btn_connect.setFixedWidth(110)

        self.lbl_status = QLabel("● Desconectado")
        self.lbl_status.setStyleSheet("color: #e74c3c; font-weight: bold;")

        conn_lay.addWidget(QLabel("Puerto:"))
        conn_lay.addWidget(self.port_combo)
        conn_lay.addWidget(QLabel("Baud:"))
        conn_lay.addWidget(self.baud_combo)
        conn_lay.addWidget(self.btn_refresh)
        conn_lay.addWidget(self.btn_connect)
        conn_lay.addWidget(self.lbl_status)
        conn_lay.addStretch()
        root.addWidget(conn_box)

        # ── Splitter: controles | terminal ─────────────────────
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # Panel izquierdo: controles
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setSpacing(8)

        left_lay.addWidget(self._build_quick_commands())
        left_lay.addWidget(self._build_pwm_panel())
        left_lay.addWidget(self._build_digital_panel())
        left_lay.addWidget(self._build_servo_panel())
        left_lay.addWidget(self._build_neopixel_panel())
        left_lay.addStretch()
        splitter.addWidget(left)

        # Panel derecho: terminal
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setSpacing(6)

        right_lay.addWidget(self._build_terminal())
        right_lay.addWidget(self._build_raw_command())
        splitter.addWidget(right)

        splitter.setSizes([380, 520])

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo.")

        # Señales
        self.btn_refresh.clicked.connect(self._refresh_ports)
        self.btn_connect.clicked.connect(self._toggle_connection)

    def _build_quick_commands(self):
        box = QGroupBox("Comandos Rápidos")
        lay = QHBoxLayout(box)
        for label, fn in [("PING", self._send_ping), ("RESET", self._send_reset), ("STATUS", self._send_status)]:
            btn = QPushButton(label)
            btn.clicked.connect(fn)
            lay.addWidget(btn)
        return box

    def _build_pwm_panel(self):
        box = QGroupBox("PWM — Motores (0-255)")
        grid = QGridLayout(box)
        self._pwm_sliders = {}
        self._pwm_labels  = {}
        for i, motor in enumerate([1, 2, 3, 4]):
            lbl = QLabel(f"M{motor}:")
            slider = QSlider(Qt.Horizontal)
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
            row = i
            grid.addWidget(lbl,     row, 0)
            grid.addWidget(slider,  row, 1)
            grid.addWidget(val_lbl, row, 2)
            grid.addWidget(btn,     row, 3)
        return box

    def _build_digital_panel(self):
        box = QGroupBox("Digital — Dirección Motores")
        grid = QGridLayout(box)
        pins = [
            ("M1 AIN1 (0x11)", 0x11), ("M1 AIN2 (0x12)", 0x12),
            ("M2 AIN1 (0x21)", 0x21), ("M2 AIN2 (0x22)", 0x22),
            ("M3 AIN1 (0x31)", 0x31), ("M3 AIN2 (0x32)", 0x32),
            ("M4 AIN1 (0x41)", 0x41), ("M4 AIN2 (0x42)", 0x42),
        ]
        for i, (name, pid) in enumerate(pins):
            lbl = QLabel(name)
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
        box = QGroupBox("NeoPixel")
        lay = QHBoxLayout(box)
        colors = [
            ("OFF",   "#555555", 0x00),
            ("ROJO",  "#e74c3c", 0x01),
            ("VERDE", "#2ecc71", 0x02),
            ("AZUL",  "#3498db", 0x03),
            ("BLANCO","#ecf0f1", 0xFF),
        ]
        for label, color, val in colors:
            btn = QPushButton(label)
            btn.setStyleSheet(
                f"QPushButton {{ background:{color}; color:{'#111' if val==0xFF else 'white'}; "
                f"font-weight:bold; border-radius:5px; padding:4px 8px; }}"
                f"QPushButton:hover {{ opacity:0.85; }}"
            )
            btn.clicked.connect(lambda _, v=val: self._send_neopixel(v))
            lay.addWidget(btn)
        return box

    def _build_terminal(self):
        box = QGroupBox("Terminal")
        lay = QVBoxLayout(box)

        header = QHBoxLayout()
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setFixedWidth(80)
        self.btn_clear.clicked.connect(self._clear_terminal)
        header.addStretch()
        header.addWidget(self.btn_clear)
        lay.addLayout(header)

        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFont(QFont("Courier New", 10))
        self.terminal.setMinimumHeight(300)
        lay.addWidget(self.terminal)
        return box

    def _build_raw_command(self):
        box = QGroupBox("Comando Raw (texto directo al maestro)")
        lay = QVBoxLayout(box)

        # Ejemplos
        examples = QHBoxLayout()
        for ex in ["ping", "pwm 1 128", "servo 90", "neo 1", "digital 11 1", "reset"]:
            btn = QPushButton(ex)
            btn.setStyleSheet("font-size:10px; padding:2px 6px;")
            btn.clicked.connect(lambda _, t=ex: self.raw_input.setText(t))
            examples.addWidget(btn)
        lay.addLayout(examples)

        send_row = QHBoxLayout()
        self.raw_input = QLineEdit()
        self.raw_input.setPlaceholderText('Ej: "pwm 1 200"  o  "servo 45"  o  "ping"')
        self.raw_input.returnPressed.connect(self._send_raw)
        btn_send = QPushButton("Enviar ↵")
        btn_send.setFixedWidth(90)
        btn_send.clicked.connect(self._send_raw)
        send_row.addWidget(self.raw_input)
        send_row.addWidget(btn_send)
        lay.addLayout(send_row)
        return box

    # ── Estilo ─────────────────────────────────────────────────
    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #1e1e2e; color: #cdd6f4; }
            QGroupBox {
                border: 1px solid #45475a;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                color: #89b4fa;
                padding: 6px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
            QPushButton {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 5px;
                padding: 5px 12px;
                font-size: 12px;
            }
            QPushButton:hover { background: #45475a; }
            QPushButton:pressed { background: #585b70; }
            QPushButton:checked { background: #a6e3a1; color: #1e1e2e; }
            QComboBox, QLineEdit, QSpinBox {
                background: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QComboBox::drop-down { border: none; }
            QTextEdit {
                background: #11111b;
                color: #a6e3a1;
                border: 1px solid #45475a;
                border-radius: 4px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #45475a;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #89b4fa;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::sub-page:horizontal { background: #89b4fa; border-radius: 3px; }
            QStatusBar { background: #181825; color: #6c7086; }
            QSplitter::handle { background: #45475a; width: 2px; }
        """)

    # ── Serial ─────────────────────────────────────────────────
    def _refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(p.device)
        if not ports:
            self.port_combo.addItem("(sin puertos)")

    def _toggle_connection(self, checked):
        if checked:
            self._connect()
        else:
            self._disconnect()

    def _connect(self):
        port = self.port_combo.currentText()
        baud = int(self.baud_combo.currentText())
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self.reader = SerialReader(self.ser)
            self.reader.data_received.connect(self._on_received)
            self.reader.connection_lost.connect(self._on_lost)
            self.reader.start()
            self.lbl_status.setText("● Conectado")
            self.lbl_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.btn_connect.setText("Desconectar")
            self.status_bar.showMessage(f"Conectado a {port} @ {baud}")
            self._log(f"[SISTEMA] Conectado a {port} @ {baud} baud", "#89b4fa")
        except Exception as e:
            self.btn_connect.setChecked(False)
            self._log(f"[ERROR] No se pudo conectar: {e}", "#f38ba8")
            self.status_bar.showMessage(f"Error: {e}")

    def _disconnect(self):
        if self.reader:
            self.reader.stop()
            self.reader = None
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = None
        self.lbl_status.setText("● Desconectado")
        self.lbl_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self.btn_connect.setText("Conectar")
        self.btn_connect.setChecked(False)
        self._log("[SISTEMA] Desconectado", "#f9e2af")
        self.status_bar.showMessage("Desconectado.")

    def _on_received(self, msg):
        self._log(msg, "#a6e3a1")

    def _on_lost(self):
        self._log("[SISTEMA] Conexión perdida", "#f38ba8")
        self._disconnect()

    # ── Envío de bytes ─────────────────────────────────────────
    def _send_bytes(self, cmd, pin_id, value, label):
        if not self.ser or not self.ser.is_open:
            self._log("[ERROR] No conectado", "#f38ba8")
            return
        try:
            buf = bytes([cmd, pin_id, value])
            self.ser.write(buf)
            self._log(f"→ {label}  [{cmd:#04x} {pin_id:#04x} {value:#04x}]", "#89dceb")
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
            self.ser.write((text + "\n").encode())
            self._log(f'→ RAW: "{text}"', "#cba6f7")
            self.raw_input.clear()
        except Exception as e:
            self._log(f"[ERROR] {e}", "#f38ba8")

    # ── Acciones de botones ────────────────────────────────────
    def _send_ping(self):
        self._send_bytes(CMD_PING, 0x00, 0x00, "PING")

    def _send_reset(self):
        self._send_bytes(CMD_RESET, 0x00, 0x00, "RESET")

    def _send_status(self):
        self._log("[INFO] Verificando conexión — envía un PING", "#f9e2af")
        self._send_ping()

    def _send_pwm(self, motor):
        val = self._pwm_sliders[motor].value()
        self._send_bytes(CMD_PWM, motor, val, f"PWM M{motor} = {val}")

    def _send_digital(self, pin_id, value):
        self._send_bytes(CMD_DIGITAL, pin_id, value, f"DIGITAL 0x{pin_id:02X} = {value}")

    def _send_servo(self):
        angle = self.servo_slider.value()
        self._send_bytes(CMD_SERVO, 0x00, angle, f"SERVO = {angle}°")

    def _send_neopixel(self, color):
        names = {0x00: "OFF", 0x01: "ROJO", 0x02: "VERDE", 0x03: "AZUL", 0xFF: "BLANCO"}
        self._send_bytes(CMD_NEOPIXEL, 0x00, color, f"NEOPIXEL = {names.get(color, hex(color))}")

    # ── Terminal ───────────────────────────────────────────────
    def _log(self, msg, color="#cdd6f4"):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.terminal.append(
            f'<span style="color:#585b70">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )
        self.terminal.moveCursor(QTextCursor.End)

    def _clear_terminal(self):
        self.terminal.clear()

    # ── Cierre ─────────────────────────────────────────────────
    def closeEvent(self, event):
        self._disconnect()
        event.accept()


# ─── Main ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ESP32Tester()
    window.show()
    sys.exit(app.exec_())
