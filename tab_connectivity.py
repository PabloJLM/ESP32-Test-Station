"""
tab_connectivity.py — Tesla Lab BALAM 2026
WiFi + BLE en un solo tab.

Protocolo: [CMD, 0x00, 0x00] → [ACK, CMD, VAL]

WiFi:  0x10 Scan | 0x11 AP | 0x12 Connect STA | 0x13 Ping | 0x14 Disc
BLE:   0x20 Scan | 0x21 Advertise | 0x22 Stop
"""

import os, re, sys, subprocess, serial, serial.tools.list_ports
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QComboBox, QTextEdit,
    QProgressBar, QFileDialog, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFrame, QSplitter,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush, QTextCursor

C_BASE    = "#1e1e2e";  C_MANTLE  = "#181825";  C_SURFACE = "#313244"
C_OVERLAY = "#45475a";  C_TEXT    = "#cdd6f4";  C_SUBTEXT = "#6c7086"
C_BLUE    = "#89b4fa";  C_GREEN   = "#a6e3a1";  C_RED     = "#f38ba8"
C_YELLOW  = "#f9e2af";  C_MAUVE   = "#cba6f7";  C_TEAL    = "#94e2d5"

ACK_OK  = 0xAA;  ACK_ERR = 0xEE

WIFI_TESTS = [
    (0x10, "WiFi Scan",    "Redes visibles",           8.0,  "WiFi"),
    (0x11, "Crear AP",     "AP 'TeslaLab-Test'",       6.0,  "WiFi"),
    (0x14, "Apagar AP",    "Detiene AP",                4.0,  "WiFi"),
    (0x12, "Conectar STA", "Red 'galileo'",            12.0, "WiFi"),
    (0x13, "Ping Google",  "Ping 8.8.8.8 (RTT ms)",    8.0,  "WiFi"),
    (0x14, "Desconectar",  "Apaga WiFi",                4.0,  "WiFi"),
]
BLE_TESTS = [
    (0x21, "BLE Advertise", "Visible 'TeslaLab-ESP32'", 5.0, "BLE"),
    (0x20, "BLE Scan",      "Dispositivos cercanos",    8.0,  "BLE"),
    (0x22, "BLE Stop",      "Detiene advertising",       4.0, "BLE"),
]
ALL_TESTS = WIFI_TESTS + BLE_TESTS

_default_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "firmware", "slave_connectivity.bin")


# ── Flash worker ────────────────────────────────────────────
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
               "--baud", str(self.baud), "write_flash", "0x0", self.bin_path]
        self.output.emit(f"$ {' '.join(cmd)}\n")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                line = line.rstrip(); self.output.emit(line)
                m = re.search(r'\((\d+)\s*%\)', line)
                if m: self.progress.emit(int(m.group(1)))
            proc.wait()
            ok = proc.returncode == 0
            if ok: self.progress.emit(100)
            self.finished.emit(ok, "Flash completado." if ok else f"esptool error ({proc.returncode})")
        except FileNotFoundError:
            self.finished.emit(False, "esptool no encontrado — pip install esptool")
        except Exception as e:
            self.finished.emit(False, str(e))


# ── Serial worker ────────────────────────────────────────────
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


# ── Result table ─────────────────────────────────────────────
class ResultTable(QTableWidget):
    COLS = ["Tipo", "Prueba", "Descripcion", "Valor", "Resultado"]

    def __init__(self):
        super().__init__(0, len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().setVisible(False)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setStyleSheet(f"""
            QTableWidget {{background:{C_MANTLE};color:{C_TEXT};
                gridline-color:{C_OVERLAY};border:1px solid {C_OVERLAY};
                border-radius:4px;font-size:12px;
                alternate-background-color:#1a1a2a;}}
            QTableWidget::item {{padding:4px 8px;}}
            QTableWidget::item:selected {{background:#3b4261;}}
            QHeaderView::section {{background:{C_SURFACE};color:{C_BLUE};
                font-weight:700;padding:6px;border:none;
                border-right:1px solid {C_OVERLAY};
                border-bottom:2px solid {C_BLUE};}}
        """)

    def add_row(self, tipo, nombre, desc, valor_str, ok):
        r = self.rowCount(); self.insertRow(r)
        tipo_color = C_TEAL if tipo == "WiFi" else C_MAUVE
        for c, (txt, color) in enumerate(zip(
            [tipo, nombre, desc, valor_str, "PASS" if ok else "FAIL"],
            [tipo_color, C_TEXT, C_SUBTEXT, C_TEXT, C_GREEN if ok else C_RED]
        )):
            item = QTableWidgetItem(txt)
            item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            item.setForeground(QBrush(QColor(color)))
            if c in (0, 4):
                item.setFont(QFont("Segoe UI", 11, QFont.Bold))
            self.setItem(r, c, item)
        self.setRowHeight(r, 28)
        self.scrollToBottom()

    def clear(self):
        self.setRowCount(0)


# ── Tab Conectividad ─────────────────────────────────────────
class TabConnectivity(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self, is_admin_fn=None):
        super().__init__()
        self._is_admin     = is_admin_fn or (lambda: False)
        self._bin_path     = _default_bin if os.path.exists(_default_bin) else ""
        self._flash_worker = None
        self._ser          = None
        self._queue        = []
        self._queue_idx    = 0
        self._workers      = []
        self._build_ui()
        self._refresh_ports()

    def notify_login(self):
        self._refresh_bin_label()

    # ── UI ───────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # Row 1: firmware + flash
        root.addLayout(self._build_top_bar())

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 100); self._progress.setValue(0)
        self._progress.setFixedHeight(10); self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{C_OVERLAY};border-radius:3px;border:none;}}"
            f"QProgressBar::chunk{{background:{C_BLUE};border-radius:3px;}}")
        root.addWidget(self._progress)

        # Row 2: serial connection
        root.addWidget(self._build_conn_bar())

        # Row 3: tests + results
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_tests_panel())
        splitter.addWidget(self._build_results_panel())
        splitter.setSizes([300, 600])
        root.addWidget(splitter, 1)

        # Row 4: log
        root.addWidget(self._build_log())

    def _build_top_bar(self):
        lay = QHBoxLayout(); lay.setSpacing(10)

        # Firmware
        bin_box = QGroupBox("Firmware Conectividad")
        bin_box.setStyleSheet(self._gs(C_BLUE))
        bl = QHBoxLayout(bin_box); bl.setSpacing(8)
        self._lbl_bin = QLabel("Sin seleccionar")
        self._lbl_bin.setStyleSheet(f"color:{C_YELLOW};font-size:11px;font-family:Consolas;")
        self._lbl_bin.setWordWrap(True)
        bl.addWidget(self._lbl_bin, 1)
        self._btn_bin = QPushButton("Elegir .bin")
        self._btn_bin.setFixedWidth(95)
        self._btn_bin.setStyleSheet(self._bs())
        self._btn_bin.clicked.connect(self._elegir_bin)
        bl.addWidget(self._btn_bin)
        lay.addWidget(bin_box, 3)

        # Puerto + flash
        port_box = QGroupBox("Puerto + Flash")
        port_box.setStyleSheet(self._gs(C_BLUE))
        pl = QHBoxLayout(port_box); pl.setSpacing(6)
        self._combo_port_flash = QComboBox()
        self._combo_port_flash.setMinimumWidth(110)
        btn_ref = QPushButton("↺"); btn_ref.setFixedWidth(28)
        btn_ref.setStyleSheet(self._bs())
        btn_ref.clicked.connect(self._refresh_ports)
        self._btn_flash = QPushButton("Flashear")
        self._btn_flash.setFixedHeight(32)
        self._btn_flash.setStyleSheet(
            f"QPushButton{{background:#2563eb;color:white;border:none;"
            f"border-radius:5px;font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{background:#1d4ed8;}}"
            f"QPushButton:disabled{{background:#1e3a6e;color:#7a9fd6;}}")
        self._btn_flash.clicked.connect(self._flashear)
        pl.addWidget(self._combo_port_flash)
        pl.addWidget(btn_ref)
        pl.addWidget(self._btn_flash)
        lay.addWidget(port_box, 2)
        return lay

    def _build_conn_bar(self):
        box = QGroupBox("Conexión Serial")
        box.setStyleSheet(self._gs(C_TEAL))
        lay = QHBoxLayout(box); lay.setSpacing(8)
        lay.addWidget(QLabel("Puerto:"))
        self._combo_port = QComboBox()
        self._combo_port.setMinimumWidth(110)
        btn_ref = QPushButton("↺"); btn_ref.setFixedWidth(28)
        btn_ref.setStyleSheet(self._bs())
        btn_ref.clicked.connect(self._refresh_ports)
        self._btn_conn = QPushButton("Conectar")
        self._btn_conn.setCheckable(True)
        self._btn_conn.setFixedWidth(100)
        self._btn_conn.setStyleSheet(self._bs())
        self._btn_conn.clicked.connect(self._toggle_conn)
        self._lbl_conn = QLabel("● Desconectado")
        self._lbl_conn.setStyleSheet(f"color:{C_RED};font-weight:700;")
        lay.addWidget(self._combo_port)
        lay.addWidget(btn_ref)
        lay.addWidget(self._btn_conn)
        lay.addWidget(self._lbl_conn)
        lay.addStretch()

        # Prueba completa a la derecha
        self._btn_all = QPushButton("▶  Prueba Completa  (WiFi + BLE)")
        self._btn_all.setFixedHeight(36)
        self._btn_all.setStyleSheet(
            f"QPushButton{{background:#2563eb;color:white;border:none;"
            f"border-radius:6px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#1d4ed8;}}"
            f"QPushButton:disabled{{background:#1e3a6e;color:#7a9fd6;}}")
        self._btn_all.clicked.connect(self._prueba_completa)
        lay.addWidget(self._btn_all)
        return box

    def _build_tests_panel(self):
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(8)

        # WiFi
        wifi_box = QGroupBox("WiFi")
        wifi_box.setStyleSheet(self._gs(C_TEAL))
        wl = QVBoxLayout(wifi_box); wl.setSpacing(4)
        for cmd, nombre, desc, timeout, tipo in WIFI_TESTS:
            btn = QPushButton(nombre)
            btn.setFixedHeight(30)
            btn.setToolTip(desc)
            btn.setStyleSheet(self._bs_teal())
            btn.clicked.connect(
                lambda _, c=cmd, n=nombre, d=desc, t=timeout, tp=tipo:
                self._prueba_single(c, n, d, t, tp))
            wl.addWidget(btn)
        lay.addWidget(wifi_box)

        # BLE
        ble_box = QGroupBox("BLE")
        ble_box.setStyleSheet(self._gs(C_MAUVE))
        bl = QVBoxLayout(ble_box); bl.setSpacing(4)
        for cmd, nombre, desc, timeout, tipo in BLE_TESTS:
            btn = QPushButton(nombre)
            btn.setFixedHeight(30)
            btn.setToolTip(desc)
            btn.setStyleSheet(self._bs_mauve())
            btn.clicked.connect(
                lambda _, c=cmd, n=nombre, d=desc, t=timeout, tp=tipo:
                self._prueba_single(c, n, d, t, tp))
            bl.addWidget(btn)
        lay.addWidget(ble_box)
        lay.addStretch()
        return w

    def _build_results_panel(self):
        box = QGroupBox("Resultados")
        box.setStyleSheet(self._gs(C_BLUE))
        lay = QVBoxLayout(box); lay.setSpacing(6)
        hdr = QHBoxLayout()
        self._lbl_progress = QLabel("")
        self._lbl_progress.setStyleSheet(f"color:{C_SUBTEXT};font-size:11px;")
        hdr.addWidget(self._lbl_progress)
        hdr.addStretch()
        btn_cl = QPushButton("Limpiar")
        btn_cl.setFixedWidth(70)
        btn_cl.setStyleSheet(self._bs())
        btn_cl.clicked.connect(self._limpiar_resultados)
        hdr.addWidget(btn_cl)
        lay.addLayout(hdr)
        self._table = ResultTable()
        lay.addWidget(self._table, 1)
        self._badge = QLabel("")
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFixedHeight(30)
        self._badge.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._badge.hide()
        lay.addWidget(self._badge)
        return box

    def _build_log(self):
        box = QGroupBox("Log")
        box.setStyleSheet(self._gs(C_BLUE))
        lay = QVBoxLayout(box); lay.setSpacing(4)
        hdr = QHBoxLayout()
        hdr.addStretch()
        btn_cl = QPushButton("Limpiar")
        btn_cl.setFixedWidth(70)
        btn_cl.setStyleSheet(self._bs())
        btn_cl.clicked.connect(lambda: self._log.clear())
        hdr.addWidget(btn_cl)
        lay.addLayout(hdr)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 9))
        self._log.setFixedHeight(90)
        self._log.setStyleSheet(
            f"QTextEdit{{background:{C_MANTLE};color:{C_GREEN};"
            f"border:none;border-radius:4px;}}")
        lay.addWidget(self._log)
        return box

    # ── Ports ────────────────────────────────────────────────
    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        items = ports if ports else ["(sin puertos)"]
        for combo in (self._combo_port_flash, self._combo_port):
            combo.clear()
            combo.addItems(items)

    # ── Bin ──────────────────────────────────────────────────
    def _refresh_bin_label(self):
        self._btn_bin.setEnabled(self._is_admin())
        if self._bin_path and os.path.exists(self._bin_path):
            self._lbl_bin.setText(os.path.basename(self._bin_path) + "  ✓")
            self._lbl_bin.setStyleSheet(f"color:{C_GREEN};font-size:11px;font-family:Consolas;")
        else:
            self._lbl_bin.setText("Sin seleccionar" if not self._bin_path
                                   else os.path.basename(self._bin_path) + "  (no encontrado)")
            self._lbl_bin.setStyleSheet(f"color:{C_YELLOW};font-size:11px;font-family:Consolas;")

    def _elegir_bin(self):
        if not self._is_admin():
            QMessageBox.warning(self, "Sin permiso", "Solo admin puede cambiar firmware.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Firmware Conectividad (.bin)", os.path.expanduser("~"), "Firmware (*.bin)")
        if path:
            self._bin_path = path
            self._refresh_bin_label()
            self._log_line(f"Firmware: {path}", C_GREEN)

    # ── Flash ────────────────────────────────────────────────
    def _flashear(self):
        if not self._bin_path or not os.path.exists(self._bin_path):
            QMessageBox.warning(self, "Sin firmware", "Elige un .bin primero."); return
        port = self._combo_port_flash.currentText()
        if not port or port == "(sin puertos)":
            QMessageBox.warning(self, "Sin puerto", "Selecciona un puerto COM."); return
        if QMessageBox.question(self, "Confirmar",
            f"Flashear {os.path.basename(self._bin_path)} en {port}?",
            QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._btn_flash.setEnabled(False)
        self._progress.setValue(0)
        self._log_line(f"Flasheando en {port}...", C_BLUE)
        self._flash_worker = FlashWorker(port, self._bin_path)
        self._flash_worker.output.connect(lambda l: self._log_line(l))
        self._flash_worker.progress.connect(self._progress.setValue)
        self._flash_worker.finished.connect(self._on_flash_done)
        self._flash_worker.start()

    def _on_flash_done(self, ok, msg):
        self._btn_flash.setEnabled(True)
        self._log_line(msg, C_GREEN if ok else C_RED)
        self.status_msg.emit(f"Flash: {msg}")
        if ok:
            idx = self._combo_port.findText(self._combo_port_flash.currentText())
            if idx >= 0: self._combo_port.setCurrentIndex(idx)

    # ── Serial ───────────────────────────────────────────────
    def _toggle_conn(self, checked):
        if checked: self._conectar()
        else: self._desconectar()

    def _conectar(self):
        port = self._combo_port.currentText()
        try:
            self._ser = serial.Serial(port, 9600, timeout=0.1)
            self._lbl_conn.setText("● Conectado")
            self._lbl_conn.setStyleSheet(f"color:{C_GREEN};font-weight:700;")
            self._btn_conn.setText("Desconectar")
            self._log_line(f"Conectado: {port}", C_TEAL)
            self.status_msg.emit(f"Conectividad: {port}")
        except Exception as e:
            self._btn_conn.setChecked(False)
            self._log_line(f"Error: {e}", C_RED)

    def _desconectar(self):
        if self._ser and self._ser.is_open: self._ser.close()
        self._ser = None
        self._lbl_conn.setText("● Desconectado")
        self._lbl_conn.setStyleSheet(f"color:{C_RED};font-weight:700;")
        self._btn_conn.setText("Conectar")
        self._btn_conn.setChecked(False)

    def _check_conn(self):
        if not self._ser or not self._ser.is_open:
            self._log_line("Sin conexión serial.", C_RED); return False
        return True

    # ── Pruebas ──────────────────────────────────────────────
    def _prueba_single(self, cmd, nombre, desc, timeout, tipo):
        if not self._check_conn(): return
        accent = C_TEAL if tipo == "WiFi" else C_MAUVE
        self._log_line(f"→ [{tipo}] {nombre}", accent)
        w = SerialWorker(self._ser, cmd, timeout)
        w.result.connect(lambda ok, ack, c, v, n=nombre, d=desc, cm=cmd, t=tipo:
                         self._on_result(ok, v, n, d, cm, t))
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w); w.start()

    def _on_result(self, ok, val, nombre, desc, cmd, tipo):
        valor_str = self._fmt(cmd, val, ok)
        self._table.add_row(tipo, nombre, desc, valor_str, ok)
        accent = C_TEAL if tipo == "WiFi" else C_MAUVE
        self._log_line(f"← [{tipo}] {nombre}: {valor_str} — {'PASS' if ok else 'FAIL'}",
                       C_GREEN if ok else C_RED)
        self.status_msg.emit(f"[{tipo}] {nombre}: {'PASS' if ok else 'FAIL'}")

    def _fmt(self, cmd, val, ok):
        fmts = {
            0x10: lambda v, o: f"{v} redes"       if o else "0 redes",
            0x11: lambda v, o: "AP activo"          if o else "Fallo",
            0x12: lambda v, o: "Conectado"           if o else "Fallo",
            0x13: lambda v, o: f"{v} ms"            if o else "Sin respuesta",
            0x14: lambda v, o: "OK",
            0x20: lambda v, o: f"{v} dispositivos" if o else "Sin respuesta",
            0x21: lambda v, o: "Advertising ON"     if o else "Fallo",
            0x22: lambda v, o: "Detenido"            if o else "Fallo",
        }
        fn = fmts.get(cmd)
        return fn(val, ok) if fn else str(val)

    def _prueba_completa(self):
        if not self._check_conn(): return
        self._table.clear()
        self._badge.hide()
        self._lbl_progress.setText("")
        self._queue = list(ALL_TESTS)
        self._queue_idx = 0
        self._btn_all.setEnabled(False)
        self._run_next()

    def _run_next(self):
        if self._queue_idx >= len(self._queue):
            self._finish(); return
        cmd, nombre, desc, timeout, tipo = self._queue[self._queue_idx]
        n, total = self._queue_idx + 1, len(self._queue)
        self._lbl_progress.setText(f"Paso {n}/{total} — [{tipo}] {nombre}")
        accent = C_TEAL if tipo == "WiFi" else C_MAUVE
        self._log_line(f"[{n}/{total}] [{tipo}] {nombre}", accent)
        w = SerialWorker(self._ser, cmd, timeout)
        w.result.connect(lambda ok, ack, c, v, n=nombre, d=desc, cm=cmd, t=tipo:
                         self._on_seq(ok, v, n, d, cm, t))
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w); w.start()

    def _on_seq(self, ok, val, nombre, desc, cmd, tipo):
        self._on_result(ok, val, nombre, desc, cmd, tipo)
        self._queue_idx += 1
        delay = 800 if cmd in (0x12,) else 400
        QTimer.singleShot(delay, self._run_next)

    def _finish(self):
        self._btn_all.setEnabled(True)
        self._lbl_progress.setText("")
        total = self._table.rowCount()
        fails = sum(1 for r in range(total)
                    if self._table.item(r, 4) and
                    self._table.item(r, 4).text() == "FAIL")
        if fails == 0:
            self._badge.setText(f"TODAS PASARON  ({total}/{total})")
            self._badge.setStyleSheet(f"background:#14532d;color:{C_GREEN};border-radius:8px;")
        else:
            self._badge.setText(f"FALLARON {fails} DE {total}")
            self._badge.setStyleSheet(f"background:#7f1d1d;color:{C_RED};border-radius:8px;")
        self._badge.show()
        self.status_msg.emit(f"Conectividad: {total - fails}/{total} PASS")

    def _limpiar_resultados(self):
        self._table.clear()
        self._badge.hide()
        self._lbl_progress.setText("")

    # ── Log ──────────────────────────────────────────────────
    def _log_line(self, msg, color=C_TEXT):
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.append(
            f'<span style="color:{C_SUBTEXT}">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>')
        self._log.moveCursor(QTextCursor.End)

    # ── Style helpers ─────────────────────────────────────────
    def _gs(self, accent):
        return (f"QGroupBox{{border:1px solid {C_OVERLAY};border-radius:8px;"
                f"margin-top:10px;font-weight:bold;color:{accent};padding:8px;}}"
                f"QGroupBox::title{{subcontrol-origin:margin;left:10px;padding:0 6px;}}")

    def _bs(self):
        return (f"QPushButton{{background:{C_SURFACE};color:{C_TEXT};"
                f"border:1px solid {C_OVERLAY};border-radius:4px;"
                f"font-size:11px;padding:3px 8px;}}"
                f"QPushButton:hover{{background:{C_OVERLAY};}}"
                f"QPushButton:disabled{{background:{C_MANTLE};color:{C_OVERLAY};}}")

    def _bs_teal(self):
        return (f"QPushButton{{background:{C_SURFACE};color:{C_TEAL};"
                f"border:1px solid {C_TEAL};border-radius:4px;"
                f"font-size:11px;padding:3px 6px;}}"
                f"QPushButton:hover{{background:#0a2a2a;}}")

    def _bs_mauve(self):
        return (f"QPushButton{{background:{C_SURFACE};color:{C_MAUVE};"
                f"border:1px solid {C_MAUVE};border-radius:4px;"
                f"font-size:11px;padding:3px 6px;}}"
                f"QPushButton:hover{{background:#1a0a2a;}}")

    def cleanup(self):
        self._desconectar()
        for w in list(self._workers):
            if w.isRunning(): w.terminate(); w.wait()
        self._workers.clear()
        if self._flash_worker and self._flash_worker.isRunning():
            self._flash_worker.terminate(); self._flash_worker.wait()