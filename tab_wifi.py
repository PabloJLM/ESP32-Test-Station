"""
tab_wifi.py — Tesla Lab BALAM 2026
Pruebas WiFi simples:
  1. Scan  — cuantas redes ve
  2. AP    — crear punto de acceso propio
  3. STA   — conectar a red "galileo" (abierta)
  4. Ping  — ping UDP a 8.8.8.8, retorna RTT ms
  5. Disc  — desconectar / apagar AP

Protocolo 3 bytes: [CMD, 0x00, 0x00] → [ACK, CMD, VAL]
"""

import os, re, sys, subprocess, serial, serial.tools.list_ports
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QPushButton, QLabel, QComboBox,
    QTextEdit, QProgressBar, QFileDialog,
    QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush, QTextCursor

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
C_TEAL    = "#94e2d5"

CMD_PING         = 0xF0
CMD_WIFI_SCAN    = 0x10
CMD_WIFI_AP      = 0x11   # crear AP
CMD_WIFI_CONNECT = 0x12   # conectar STA
CMD_WIFI_PING    = 0x13   # ping 8.8.8.8
CMD_WIFI_DISC    = 0x14   # desconectar todo
ACK_OK  = 0xAA
ACK_ERR = 0xEE

PRUEBAS = [
    (CMD_WIFI_SCAN,    "WiFi Scan",    "Redes visibles en el entorno", 8.0),
    (CMD_WIFI_AP,      "Crear AP",     "Levanta AP 'TeslaLab-Test'",   6.0),
    (CMD_WIFI_DISC,    "Apagar AP",    "Detiene el AP",                4.0),
    (CMD_WIFI_CONNECT, "Conectar STA", "Conecta a red 'galileo'",     12.0),
    (CMD_WIFI_PING,    "Ping Google",  "Ping UDP a 8.8.8.8 (RTT ms)", 8.0),
    (CMD_WIFI_DISC,    "Desconectar",  "Desconecta STA",               4.0),
]

_bin_wifi = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "firmware", "slave_wifi_test.bin")


# ── Flash worker ─────────────────────────────────────────
class FlashWorker(QThread):
    output   = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, port, bin_path, baud=115200):
        super().__init__()
        self.port = port; self.bin_path = bin_path; self.baud = baud

    def run(self):
        cmd = [sys.executable, "-m", "esptool",
               "--chip", "esp32", "--port", self.port,
               "--baud", str(self.baud),
               "write_flash", "0x0", self.bin_path]
        self.output.emit(f"$ {' '.join(cmd)}\n")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                line = line.rstrip()
                self.output.emit(line)
                m = re.search(r'\((\d+)\s*%\)', line)
                if m: self.progress.emit(int(m.group(1)))
            proc.wait()
            if proc.returncode == 0:
                self.progress.emit(100)
                self.finished.emit(True, "Flash completado.")
            else:
                self.finished.emit(False, f"esptool error ({proc.returncode})")
        except FileNotFoundError:
            self.finished.emit(False, "esptool no encontrado — pip install esptool")
        except Exception as e:
            self.finished.emit(False, str(e))


# ── Serial worker ─────────────────────────────────────────
class SerialWorker(QThread):
    result = pyqtSignal(bool, int, int, int)

    def __init__(self, ser, cmd, timeout=8.0):
        super().__init__()
        self.ser = ser; self.cmd = cmd; self.timeout = timeout

    def run(self):
        import time
        try:
            self.ser.reset_input_buffer()
            self.ser.write(bytes([self.cmd, 0x00, 0x00]))
            t0 = time.time(); buf = bytearray()
            while time.time() - t0 < self.timeout:
                if self.ser.in_waiting:
                    buf.extend(self.ser.read(self.ser.in_waiting))
                if len(buf) >= 3:
                    self.result.emit(buf[0] == ACK_OK, buf[0], buf[1], buf[2])
                    return
                time.sleep(0.02)
            self.result.emit(False, ACK_ERR, self.cmd, 0)
        except Exception:
            self.result.emit(False, ACK_ERR, self.cmd, 0)


# ── Result table ─────────────────────────────────────────
class ResultTable(QTableWidget):
    COLS = ["Prueba", "Descripcion", "Valor", "Resultado"]

    def __init__(self):
        super().__init__(0, len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setAlternatingRowColors(True)
        self.setStyleSheet(f"""
            QTableWidget {{background:{C_MANTLE};color:{C_TEXT};
                gridline-color:{C_OVERLAY};border:1px solid {C_OVERLAY};
                border-radius:4px;font-size:12px;
                alternate-background-color:#1a1a2a;}}
            QTableWidget::item {{padding:5px 10px;}}
            QTableWidget::item:selected {{background:#3b4261;}}
            QHeaderView::section {{background:{C_SURFACE};color:{C_BLUE};
                font-weight:700;padding:7px;border:none;
                border-right:1px solid {C_OVERLAY};
                border-bottom:2px solid {C_BLUE};}}
        """)

    def add_row(self, nombre, desc, valor_str, ok):
        r = self.rowCount(); self.insertRow(r)
        for c, txt in enumerate([nombre, desc, valor_str, "PASS" if ok else "FAIL"]):
            item = QTableWidgetItem(txt)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            if c == 3:
                item.setForeground(QBrush(QColor(C_GREEN if ok else C_RED)))
                item.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self.setItem(r, c, item)
        self.setRowHeight(r, 32)
        self.scrollToBottom()


# ── Tab WiFi ─────────────────────────────────────────────
class TabWifi(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self, is_admin_fn=None):
        super().__init__()
        self._is_admin     = is_admin_fn or (lambda: False)
        self._bin_path     = _bin_wifi if os.path.exists(_bin_wifi) else ""
        self._flash_worker = None
        self._ser          = None
        self._queue        = []
        self._queue_idx    = 0
        self._workers      = []
        self._build_ui()
        self._refresh_ports()

    def notify_login(self):
        self._refresh_bin_label()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(14, 14, 14, 14)

        # ── Fila superior: firmware + puerto ──────────────
        top = QHBoxLayout(); top.setSpacing(10)

        bin_box = QGroupBox("Firmware WiFi (.bin)")
        bin_box.setStyleSheet(self._gs(C_TEAL))
        bl = QHBoxLayout(bin_box)
        self._lbl_bin = QLabel(self._bin_display())
        self._lbl_bin.setStyleSheet(f"color:{C_YELLOW};font-size:11px;font-family:Consolas;")
        self._lbl_bin.setWordWrap(True)
        bl.addWidget(self._lbl_bin, 1)
        self._btn_bin = QPushButton("Elegir .bin")
        self._btn_bin.setFixedWidth(100)
        self._btn_bin.setStyleSheet(self._bs())
        self._btn_bin.clicked.connect(self._elegir_bin)
        bl.addWidget(self._btn_bin)
        top.addWidget(bin_box, 2)

        port_box = QGroupBox("Puerto + Flash")
        port_box.setStyleSheet(self._gs(C_TEAL))
        pl = QHBoxLayout(port_box)
        self._combo_port = QComboBox(); self._combo_port.setMinimumWidth(100)
        btn_ref = QPushButton("↺"); btn_ref.setFixedWidth(30)
        btn_ref.setStyleSheet(self._bs())
        btn_ref.clicked.connect(self._refresh_ports)
        self._btn_flash = QPushButton("Flashear")
        self._btn_flash.setFixedHeight(32)
        self._btn_flash.setStyleSheet(
            f"QPushButton{{background:#0e7490;color:white;border:none;"
            f"border-radius:5px;font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{background:#0c6580;}}"
            f"QPushButton:disabled{{background:#0a3d4a;color:#4a8a99;}}")
        self._btn_flash.clicked.connect(self._flashear)
        pl.addWidget(self._combo_port); pl.addWidget(btn_ref)
        pl.addSpacing(8); pl.addWidget(self._btn_flash)
        top.addWidget(port_box, 2)

        root.addLayout(top)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100); self._progress.setValue(0)
        self._progress.setFixedHeight(12); self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{C_OVERLAY};border-radius:3px;border:none;}}"
            f"QProgressBar::chunk{{background:{C_TEAL};border-radius:3px;}}")
        root.addWidget(self._progress)

        # ── Conexion serial ───────────────────────────────
        conn_box = QGroupBox("Conexion serial")
        conn_box.setStyleSheet(self._gs(C_BLUE))
        cl = QHBoxLayout(conn_box)
        cl.addWidget(QLabel("Puerto:"))
        self._combo_port2 = QComboBox(); self._combo_port2.setMinimumWidth(100)
        btn_ref2 = QPushButton("↺"); btn_ref2.setFixedWidth(30)
        btn_ref2.setStyleSheet(self._bs())
        btn_ref2.clicked.connect(self._refresh_ports)
        self._btn_conn = QPushButton("Conectar")
        self._btn_conn.setCheckable(True); self._btn_conn.setFixedWidth(100)
        self._btn_conn.setStyleSheet(self._bs())
        self._btn_conn.clicked.connect(self._toggle_conn)
        self._lbl_conn = QLabel("Desconectado")
        self._lbl_conn.setStyleSheet(f"color:{C_RED};font-weight:600;")
        cl.addWidget(self._combo_port2); cl.addWidget(btn_ref2)
        cl.addWidget(self._btn_conn); cl.addWidget(self._lbl_conn)
        cl.addStretch()
        root.addWidget(conn_box)

        # ── Cuerpo: botones | tabla ───────────────────────
        mid = QHBoxLayout(); mid.setSpacing(10)

        test_box = QGroupBox("Pruebas WiFi")
        test_box.setStyleSheet(self._gs(C_TEAL))
        tl = QVBoxLayout(test_box); tl.setSpacing(6)

        for cmd, nombre, desc, timeout in PRUEBAS:
            btn = QPushButton(nombre)
            btn.setFixedHeight(32)
            btn.setToolTip(desc)
            btn.setStyleSheet(self._bs())
            btn.clicked.connect(
                lambda _, c=cmd, n=nombre, d=desc, t=timeout:
                self._prueba_single(c, n, d, t))
            tl.addWidget(btn)

        tl.addSpacing(6)
        self._btn_all = QPushButton("Prueba completa")
        self._btn_all.setFixedHeight(38)
        self._btn_all.setStyleSheet(
            f"QPushButton{{background:#0e7490;color:white;border:none;"
            f"border-radius:6px;font-size:13px;font-weight:700;}}"
            f"QPushButton:hover{{background:#0c6580;}}")
        self._btn_all.clicked.connect(self._prueba_completa)
        tl.addWidget(self._btn_all)
        tl.addStretch()
        mid.addWidget(test_box, 1)

        right = QWidget()
        rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0)
        res_box = QGroupBox("Resultados")
        res_box.setStyleSheet(self._gs(C_BLUE))
        resl = QVBoxLayout(res_box)
        self._table = ResultTable()
        self._badge = QLabel("")
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFixedHeight(32)
        self._badge.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self._badge.hide()
        resl.addWidget(self._table); resl.addWidget(self._badge)
        rl.addWidget(res_box, 1)
        mid.addWidget(right, 2)

        root.addLayout(mid, 1)

        # ── Log ───────────────────────────────────────────
        log_box = QGroupBox("Log")
        log_box.setStyleSheet(self._gs(C_BLUE))
        ll = QVBoxLayout(log_box)
        self._log = QTextEdit(); self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 9)); self._log.setFixedHeight(110)
        self._log.setStyleSheet(
            f"QTextEdit{{background:{C_MANTLE};color:{C_GREEN};"
            f"border:none;border-radius:4px;}}")
        btn_cl = QPushButton("Limpiar"); btn_cl.setFixedWidth(70)
        btn_cl.setStyleSheet(self._bs()); btn_cl.clicked.connect(self._log.clear)
        hrow = QHBoxLayout(); hrow.addStretch(); hrow.addWidget(btn_cl)
        ll.addLayout(hrow); ll.addWidget(self._log)
        root.addWidget(log_box)

        self._refresh_bin_label()

    # ── Ports ─────────────────────────────────────────────
    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        for combo in (self._combo_port, self._combo_port2):
            combo.clear()
            combo.addItems(ports if ports else ["(sin puertos)"])

    # ── Bin ───────────────────────────────────────────────
    def _bin_display(self):
        if not self._bin_path: return "Sin seleccionar"
        return (os.path.basename(self._bin_path) + "  ✓"
                if os.path.exists(self._bin_path)
                else os.path.basename(self._bin_path) + "  (no encontrado)")

    def _refresh_bin_label(self):
        self._btn_bin.setEnabled(self._is_admin())
        exists = bool(self._bin_path) and os.path.exists(self._bin_path)
        color = C_GREEN if exists else (C_YELLOW if not self._bin_path else C_RED)
        self._lbl_bin.setText(self._bin_display())
        self._lbl_bin.setStyleSheet(f"color:{color};font-size:11px;font-family:Consolas;")

    def _elegir_bin(self):
        if not self._is_admin():
            QMessageBox.warning(self, "Sin permiso", "Solo admin puede cambiar firmware.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Firmware WiFi (.bin)", os.path.expanduser("~"), "Firmware (*.bin)")
        if path:
            self._bin_path = path
            self._refresh_bin_label()
            self._log_line(f"Firmware: {path}", C_GREEN)

    # ── Flash ─────────────────────────────────────────────
    def _flashear(self):
        if not self._bin_path or not os.path.exists(self._bin_path):
            QMessageBox.warning(self, "Sin firmware", "Elige un .bin primero.")
            return
        port = self._combo_port.currentText()
        if not port or port == "(sin puertos)":
            QMessageBox.warning(self, "Sin puerto", "Selecciona un puerto COM.")
            return
        if QMessageBox.question(self, "Confirmar",
            f"Flashear {os.path.basename(self._bin_path)} en {port}?",
            QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._btn_flash.setEnabled(False)
        self._progress.setValue(0)
        self._log_line(f"Flasheando en {port}...", C_TEAL)
        self._flash_worker = FlashWorker(port, self._bin_path)
        self._flash_worker.output.connect(lambda l: self._log_line(l))
        self._flash_worker.progress.connect(self._progress.setValue)
        self._flash_worker.finished.connect(self._on_flash_done)
        self._flash_worker.start()

    def _on_flash_done(self, ok, msg):
        self._btn_flash.setEnabled(True)
        self._log_line(msg, C_GREEN if ok else C_RED)
        self.status_msg.emit(f"Flash WiFi: {msg}")
        if ok:
            idx = self._combo_port2.findText(self._combo_port.currentText())
            if idx >= 0: self._combo_port2.setCurrentIndex(idx)

    # ── Serial conn ───────────────────────────────────────
    def _toggle_conn(self, checked):
        if checked: self._conectar()
        else: self._desconectar()

    def _conectar(self):
        port = self._combo_port2.currentText()
        try:
            self._ser = serial.Serial(port, 9600, timeout=0.1)
            self._lbl_conn.setText("Conectado")
            self._lbl_conn.setStyleSheet(f"color:{C_GREEN};font-weight:600;")
            self._btn_conn.setText("Desconectar")
            self._log_line(f"Conectado: {port}", C_TEAL)
            self.status_msg.emit(f"WiFi tester: {port}")
        except Exception as e:
            self._btn_conn.setChecked(False)
            self._log_line(f"Error: {e}", C_RED)

    def _desconectar(self):
        if self._ser and self._ser.is_open: self._ser.close()
        self._ser = None
        self._lbl_conn.setText("Desconectado")
        self._lbl_conn.setStyleSheet(f"color:{C_RED};font-weight:600;")
        self._btn_conn.setText("Conectar")
        self._btn_conn.setChecked(False)

    def _check_conn(self):
        if not self._ser or not self._ser.is_open:
            self._log_line("Sin conexion serial.", C_RED); return False
        return True

    # ── Pruebas ───────────────────────────────────────────
    def _prueba_single(self, cmd, nombre, desc, timeout):
        if not self._check_conn(): return
        self._log_line(f"-> {nombre}", C_TEAL)
        w = SerialWorker(self._ser, cmd, timeout)
        w.result.connect(lambda ok, ack, c, v, n=nombre, d=desc, cm=cmd:
                         self._on_result(ok, v, n, d, cm))
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w); w.start()

    def _on_result(self, ok, val, nombre, desc, cmd):
        valor_str = self._fmt(cmd, val, ok)
        self._table.add_row(nombre, desc, valor_str, ok)
        self._log_line(f"<- {nombre}: {valor_str} — {'PASS' if ok else 'FAIL'}",
                       C_GREEN if ok else C_RED)
        self.status_msg.emit(f"WiFi {nombre}: {'PASS' if ok else 'FAIL'}")

    def _fmt(self, cmd, val, ok):
        if cmd == CMD_WIFI_SCAN:    return f"{val} redes" if ok else "0 redes"
        if cmd == CMD_WIFI_AP:      return "AP activo" if ok else "Fallo"
        if cmd == CMD_WIFI_CONNECT: return "Conectado" if ok else "Fallo"
        if cmd == CMD_WIFI_PING:    return f"{val} ms" if ok else "Sin respuesta"
        if cmd == CMD_WIFI_DISC:    return "OK"
        return str(val)

    def _prueba_completa(self):
        if not self._check_conn(): return
        self._table.setRowCount(0)
        self._badge.hide()
        self._queue = list(PRUEBAS); self._queue_idx = 0
        self._btn_all.setEnabled(False)
        self._run_next()

    def _run_next(self):
        if self._queue_idx >= len(self._queue):
            self._finish(); return
        cmd, nombre, desc, timeout = self._queue[self._queue_idx]
        self._log_line(f"[{self._queue_idx+1}/{len(self._queue)}] {nombre}", C_SUBTEXT)
        w = SerialWorker(self._ser, cmd, timeout)
        w.result.connect(lambda ok, ack, c, v, n=nombre, d=desc, cm=cmd:
                         self._on_seq(ok, v, n, d, cm))
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w); w.start()

    def _on_seq(self, ok, val, nombre, desc, cmd):
        self._on_result(ok, val, nombre, desc, cmd)
        self._queue_idx += 1
        QTimer.singleShot(500, self._run_next)

    def _finish(self):
        self._btn_all.setEnabled(True)
        total = self._table.rowCount()
        fails = sum(1 for r in range(total)
                    if self._table.item(r, 3) and
                    self._table.item(r, 3).text() == "FAIL")
        if fails == 0:
            self._badge.setText(f"TODAS PASARON  ({total}/{total})")
            self._badge.setStyleSheet(f"background:#14532d;color:{C_GREEN};border-radius:8px;")
        else:
            self._badge.setText(f"FALLARON {fails} DE {total}")
            self._badge.setStyleSheet(f"background:#7f1d1d;color:{C_RED};border-radius:8px;")
        self._badge.show()
        self.status_msg.emit(f"WiFi: {total-fails}/{total} PASS")

    # ── Log ───────────────────────────────────────────────
    def _log_line(self, msg, color=C_TEXT):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(
            f'<span style="color:{C_SUBTEXT}">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>')
        self._log.moveCursor(QTextCursor.End)

    # ── Style helpers ─────────────────────────────────────
    def _gs(self, accent):
        return (f"QGroupBox{{border:1px solid {C_OVERLAY};border-radius:8px;"
                f"margin-top:10px;font-weight:bold;color:{accent};padding:8px;}}"
                f"QGroupBox::title{{subcontrol-origin:margin;left:10px;padding:0 6px;}}")

    def _bs(self):
        return (f"QPushButton{{background:{C_SURFACE};color:{C_TEXT};"
                f"border:1px solid {C_OVERLAY};border-radius:4px;"
                f"font-size:11px;padding:4px 8px;}}"
                f"QPushButton:hover{{background:{C_OVERLAY};}}"
                f"QPushButton:disabled{{background:{C_MANTLE};color:{C_OVERLAY};}}")

    def cleanup(self):
        self._desconectar()
        for w in list(self._workers):
            if w.isRunning(): w.terminate(); w.wait()
        self._workers.clear()
        if self._flash_worker and self._flash_worker.isRunning():
            self._flash_worker.terminate(); self._flash_worker.wait()
