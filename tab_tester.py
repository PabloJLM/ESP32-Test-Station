"""
tab_tester.py — Tesla Lab BALAM 2026
Tester de hardware: NeoPixels · Motores · Servos · I2C
Requiere slave_main.bin en el slave.

CMD_MOTOR    0x01  ID=1/2    VAL=0(stop)/1(fwd)/2(bwd)
CMD_PWM      0x02  ID=1/2    VAL=speed 0-255
CMD_SERVO    0x03  ID=1/2/3  VAL=angle 0-180
CMD_NEO      0x04  ID=0(all) VAL=color
CMD_I2C_SCAN 0x06            → [ACK,CMD,N]+N×addr
CMD_PING     0xF0
CMD_RESET    0xFF
"""
import serial, serial.tools.list_ports
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QComboBox, QSlider,
    QTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSplitter, QFrame,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QRectF
from PyQt5.QtGui import (
    QFont, QColor, QBrush, QPainter, QPen, QTextCursor,
)

C_BASE    = "#1e1e2e"; C_MANTLE  = "#181825"; C_SURFACE = "#313244"
C_OVERLAY = "#45475a"; C_TEXT    = "#cdd6f4"; C_SUB     = "#6c7086"
C_BLUE    = "#89b4fa"; C_GREEN   = "#a6e3a1"; C_RED     = "#f38ba8"
C_YELLOW  = "#f9e2af"; C_MAUVE   = "#cba6f7"; C_TEAL    = "#94e2d5"

CMD_MOTOR    = 0x01; CMD_PWM      = 0x02; CMD_SERVO    = 0x03
CMD_NEO      = 0x04; CMD_DIGITAL  = 0x05; CMD_I2C_SCAN = 0x06
CMD_PING     = 0xF0; CMD_RESET    = 0xFF
ACK_OK, ACK_ERR = 0xAA, 0xEE

NEO_PAL = {
    0x00:(30,30,30), 0x01:(220,40,40),
    0x02:(40,200,60), 0x03:(40,80,220), 0xFF:(220,220,220),
}
NEO_LBL = {0x00:"OFF",0x01:"ROJO",0x02:"VERDE",0x03:"AZUL",0xFF:"BLANCO"}

FULL_TEST = [
    ("Ping",            CMD_PING,     0,    0, 1.5,  300),
    ("Neo ROJO",        CMD_NEO,      0, 0x01, 1.5,  500),
    ("Neo VERDE",       CMD_NEO,      0, 0x02, 1.5,  500),
    ("Neo AZUL",        CMD_NEO,      0, 0x03, 1.5,  500),
    ("Neo BLANCO",      CMD_NEO,      0, 0xFF, 1.5,  500),
    ("Neo OFF",         CMD_NEO,      0, 0x00, 1.5,  300),
    ("M1 Adelante",     CMD_MOTOR,    1,    1, 1.5,  800),
    ("M1 Stop",         CMD_MOTOR,    1,    0, 1.5,  300),
    ("M1 Atras",        CMD_MOTOR,    1,    2, 1.5,  800),
    ("M1 Stop",         CMD_MOTOR,    1,    0, 1.5,  300),
    ("M2 Adelante",     CMD_MOTOR,    2,    1, 1.5,  800),
    ("M2 Stop",         CMD_MOTOR,    2,    0, 1.5,  300),
    ("M2 Atras",        CMD_MOTOR,    2,    2, 1.5,  800),
    ("M2 Stop",         CMD_MOTOR,    2,    0, 1.5,  300),
    ("Servo IO18   0",  CMD_SERVO,    1,    0, 2.0,  700),
    ("Servo IO18  90",  CMD_SERVO,    1,   90, 2.0,  700),
    ("Servo IO18 180",  CMD_SERVO,    1,  180, 2.0,  700),
    ("Servo IO18  90",  CMD_SERVO,    1,   90, 2.0,  400),
    ("IO13 ON",         CMD_DIGITAL,  13,   1, 1.5,  500),
    ("IO13 OFF",        CMD_DIGITAL,  13,   0, 1.5,  300),
    ("IO15 ON",         CMD_DIGITAL,  15,   1, 1.5,  500),
    ("IO15 OFF",        CMD_DIGITAL,  15,   0, 1.5,  300),
    ("I2C Scan",        CMD_I2C_SCAN, 0,    0, 4.5,  300),
]


class NeoStrip(QWidget):
    N = 4
    def __init__(self):
        super().__init__()
        self._cols = [QColor(30,30,30)] * self.N
        self.setMinimumHeight(120)
        self.setMinimumWidth(300)

    def fill(self, rgb):
        self._cols = [QColor(*rgb)] * self.N
        self.update()

    def reset(self):
        self._cols = [QColor(30,30,30)] * self.N
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        R = min(40, (W - 80) // (2 * self.N), H // 2 - 16)
        gap = max(16, (W - self.N * 2 * R) // (self.N + 1))
        total = self.N * (2*R) + (self.N-1)*gap
        ox = (W - total) // 2
        oy = H // 2 - R - 8
        dark = QColor(30,30,30)
        for i, c in enumerate(self._cols):
            x = ox + i*(2*R+gap)
            if c != dark:
                g = QColor(c); g.setAlpha(70)
                p.setPen(Qt.NoPen); p.setBrush(g)
                p.drawEllipse(x-10, oy-10, 2*R+20, 2*R+20)
            p.setPen(QPen(QColor(C_OVERLAY), 2))
            p.setBrush(c)
            p.drawEllipse(x, oy, 2*R, 2*R)
            if c != dark:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(255,255,255,70))
                p.drawEllipse(x+R//2, oy+R//4, R//2, R//3)
            p.setPen(QColor(C_SUB))
            p.setFont(QFont("Consolas",10))
            p.drawText(QRectF(x, oy+2*R+6, 2*R, 16), Qt.AlignCenter, str(i+1))


class SerialWorker(QThread):
    done = pyqtSignal(bool, int, int, bytes)

    def __init__(self, ser, cmd, pid=0, val=0, timeout=1.5):
        super().__init__()
        self.ser=ser; self.cmd=cmd; self.pid=pid; self.val=val; self.timeout=timeout

    def run(self):
        import time
        try:
            self.ser.reset_input_buffer()
            self.ser.write(bytes([self.cmd, self.pid, self.val]))
            limit = 5.0 if self.cmd == CMD_I2C_SCAN else self.timeout
            t0 = time.time(); buf = bytearray()
            while time.time()-t0 < limit:
                if self.ser.in_waiting:
                    buf.extend(self.ser.read(self.ser.in_waiting))
                if len(buf) >= 3:
                    if self.cmd == CMD_I2C_SCAN:
                        cnt = buf[2]
                        if len(buf) >= 3+cnt:
                            self.done.emit(buf[0]==ACK_OK, self.cmd,
                                           cnt, bytes(buf[3:3+cnt]))
                            return
                    else:
                        self.done.emit(buf[0]==ACK_OK, self.cmd, buf[2], b'')
                        return
                time.sleep(0.02)
            self.done.emit(False, self.cmd, 0, b'')
        except Exception:
            self.done.emit(False, self.cmd, 0, b'')


class ResultTable(QTableWidget):
    COLS = ["Prueba", "Valor", "Estado"]
    def __init__(self):
        super().__init__(0, len(self.COLS))
        self.setHorizontalHeaderLabels(self.COLS)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().setVisible(False)
        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setStyleSheet(f"""
            QTableWidget{{background:{C_MANTLE};color:{C_TEXT};
                gridline-color:{C_OVERLAY};border:1px solid {C_OVERLAY};
                border-radius:4px;font-size:12px;alternate-background-color:#1a1a2a;}}
            QTableWidget::item{{padding:4px 8px;}}
            QTableWidget::item:selected{{background:#3b4261;}}
            QHeaderView::section{{background:{C_SURFACE};color:{C_BLUE};
                font-weight:700;padding:5px;border:none;
                border-right:1px solid {C_OVERLAY};border-bottom:2px solid {C_BLUE};}}
        """)

    def add(self, nombre, valor, ok):
        r = self.rowCount(); self.insertRow(r)
        for c, (txt, clr) in enumerate(zip(
            [nombre, str(valor), "PASS" if ok else "FAIL"],
            [C_TEXT, C_TEXT, C_GREEN if ok else C_RED]
        )):
            it = QTableWidgetItem(txt)
            it.setTextAlignment(Qt.AlignVCenter|Qt.AlignLeft)
            it.setForeground(QBrush(QColor(clr)))
            if c == 2: it.setFont(QFont("Segoe UI",11,QFont.Bold))
            self.setItem(r,c,it)
        self.setRowHeight(r,26); self.scrollToBottom()

    def clear(self): self.setRowCount(0)


class TabTester(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ser      = None
        self._workers = []
        self._queue   = []
        self._q_idx   = 0
        self._running = False
        self._m_dir   = {1:0, 2:0}
        self._neo_strip  = None
        self._m_status   = {}
        self._m_speed_sl = {}
        self._srv_sl     = {}
        self._dig_status = {}   # {gpio: QLabel}
        self._i2c_lbl    = None
        self._badge      = None
        self._build_ui()
        self._refresh_ports()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8); root.setContentsMargins(10,10,10,10)
        root.addWidget(self._build_conn_bar())
        sp = QSplitter(Qt.Horizontal)
        sp.addWidget(self._build_left())
        sp.addWidget(self._build_right())
        sp.setSizes([390, 570])
        root.addWidget(sp, 1)

    def _build_conn_bar(self):
        box = QGroupBox("Conexion")
        box.setStyleSheet(self._gs(C_BLUE))
        lay = QHBoxLayout(box); lay.setSpacing(8)
        lay.addWidget(self._lbl("Puerto:"))
        self._combo_port = QComboBox(); self._combo_port.setMinimumWidth(110)
        lay.addWidget(self._combo_port)
        lay.addWidget(self._lbl("Baud:"))
        self._combo_baud = QComboBox()
        self._combo_baud.addItems(["9600","115200"])
        lay.addWidget(self._combo_baud)
        btn_ref = QPushButton("~"); btn_ref.setFixedWidth(28)
        btn_ref.setStyleSheet(self._bs()); btn_ref.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_ref)
        self._btn_conn = QPushButton("Conectar")
        self._btn_conn.setCheckable(True); self._btn_conn.setFixedWidth(100)
        self._btn_conn.setStyleSheet(self._bs())
        self._btn_conn.clicked.connect(self._toggle_conn)
        lay.addWidget(self._btn_conn)
        self._lbl_conn = QLabel("  Desconectado")
        self._lbl_conn.setStyleSheet(f"color:{C_RED};font-weight:700;font-size:12px;")
        lay.addWidget(self._lbl_conn)
        lay.addStretch()
        for label, fn, accent in [("Ping",self._do_ping,C_TEAL),("Reset",self._do_reset,C_YELLOW)]:
            b = QPushButton(label); b.setFixedWidth(60)
            b.setStyleSheet(self._bs_accent(accent))
            b.clicked.connect(fn); lay.addWidget(b)
        return box

    def _build_left(self):
        w = QWidget()
        lay = QVBoxLayout(w); lay.setSpacing(8); lay.setContentsMargins(0,0,0,0)
        lay.addWidget(self._build_neo())
        lay.addWidget(self._build_motors())
        lay.addWidget(self._build_servos())
        lay.addWidget(self._build_i2c())
        lay.addWidget(self._build_full_btn())
        lay.addStretch()
        return w

    # ── NeoPixel ────────────────────────────────────────────
    def _build_neo(self):
        box = QGroupBox("NeoPixel  IO23  (4x WS2812B)")
        box.setStyleSheet(self._gs(C_MAUVE))
        lay = QVBoxLayout(box); lay.setSpacing(6)
        self._neo_strip = NeoStrip()
        lay.addWidget(self._neo_strip, 0, Qt.AlignCenter)
        btn_row = QHBoxLayout(); btn_row.setSpacing(5)
        palette = [
            (0x00,"OFF",  (80,80,80)),
            (0x01,"ROJO", (180,40,40)),
            (0x02,"VERDE",(40,150,50)),
            (0x03,"AZUL", (40,80,200)),
            (0xFF,"BLANCO",(180,180,180)),
        ]
        for idx, name, rgb in palette:
            r,g,b = rgb
            btn = QPushButton(name); btn.setFixedHeight(30)
            btn.setStyleSheet(
                f"QPushButton{{background:rgb({r},{g},{b});color:white;"
                f"border:none;border-radius:4px;font-size:11px;font-weight:700;}}"
                f"QPushButton:hover{{border:2px solid white;}}")
            btn.clicked.connect(lambda _,i=idx,c=rgb: self._neo_cmd(i,c))
            btn_row.addWidget(btn)
        lay.addLayout(btn_row)
        return box

    def _neo_cmd(self, color_idx, rgb):
        self._send(CMD_NEO, 0, color_idx,
                   cb=lambda ok,c,v,ex,ci=color_idx,co=rgb: self._on_neo(ok,ci,co))

    def _on_neo(self, ok, idx, rgb):
        if ok and self._neo_strip:
            self._neo_strip.fill(rgb if idx != 0x00 else (30,30,30))
        self._table.add(f"Neo {NEO_LBL.get(idx,'?')}", "OK" if ok else "ERR", ok)
        self._log(f"Neo {NEO_LBL.get(idx,'?')}: {'PASS' if ok else 'FAIL'}",
                  C_GREEN if ok else C_RED)

    # ── Motores ─────────────────────────────────────────────
    def _build_motors(self):
        box = QGroupBox("Motores")
        box.setStyleSheet(self._gs(C_GREEN))
        lay = QVBoxLayout(box); lay.setSpacing(8)
        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(self._motor_card(1))
        row.addWidget(self._motor_card(2))
        lay.addLayout(row)
        btn_stop = QPushButton("PARAR TODO")
        btn_stop.setFixedHeight(36)
        btn_stop.setStyleSheet(
            f"QPushButton{{background:#7f1d1d;color:{C_RED};"
            f"border:1px solid #ef4444;border-radius:6px;"
            f"font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{background:#991b1b;}}")
        btn_stop.clicked.connect(self._stop_all)
        lay.addWidget(btn_stop)
        return box

    def _motor_card(self, m):
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:{C_SURFACE};border:1px solid {C_OVERLAY};"
            f"border-radius:8px;}}")
        lay = QVBoxLayout(card); lay.setSpacing(6); lay.setContentsMargins(8,8,8,8)
        hdr = QHBoxLayout()
        ln = QLabel(f"M{m}")
        ln.setFont(QFont("Segoe UI",13,QFont.Bold))
        ln.setStyleSheet(f"color:{C_GREEN};background:transparent;border:none;")
        self._m_status[m] = QLabel("STOP")
        self._m_status[m].setStyleSheet(
            f"color:{C_SUB};font-size:11px;font-weight:700;"
            f"background:transparent;border:none;")
        hdr.addWidget(ln); hdr.addStretch(); hdr.addWidget(self._m_status[m])
        lay.addLayout(hdr)
        row = QHBoxLayout(); row.setSpacing(4)
        b_bwd = QPushButton("< ATRAS")
        b_stp = QPushButton("STOP")
        b_fwd = QPushButton("ADELANTE >")
        for btn,h in [(b_bwd,36),(b_stp,36),(b_fwd,36)]:
            btn.setFixedHeight(h)
        b_bwd.setStyleSheet(
            f"QPushButton{{background:#4a0d0d;color:{C_RED};"
            f"border:1px solid {C_RED};border-radius:5px;"
            f"font-size:11px;font-weight:700;}}"
            f"QPushButton:hover{{background:#6b1515;}}")
        b_stp.setStyleSheet(
            f"QPushButton{{background:{C_SURFACE};color:{C_TEXT};"
            f"border:1px solid {C_OVERLAY};border-radius:5px;"
            f"font-size:11px;font-weight:700;}}"
            f"QPushButton:hover{{background:{C_OVERLAY};}}")
        b_fwd.setStyleSheet(
            f"QPushButton{{background:#0d3d1a;color:{C_GREEN};"
            f"border:1px solid {C_GREEN};border-radius:5px;"
            f"font-size:11px;font-weight:700;}}"
            f"QPushButton:hover{{background:#155228;}}")
        b_bwd.clicked.connect(lambda _,mo=m: self._motor_cmd(mo,2))
        b_stp.clicked.connect(lambda _,mo=m: self._motor_cmd(mo,0))
        b_fwd.clicked.connect(lambda _,mo=m: self._motor_cmd(mo,1))
        row.addWidget(b_bwd); row.addWidget(b_stp); row.addWidget(b_fwd)
        lay.addLayout(row)
        spd_row = QHBoxLayout(); spd_row.setSpacing(6)
        lv = QLabel("Vel:")
        lv.setStyleSheet(f"color:{C_SUB};font-size:11px;background:transparent;border:none;")
        lv.setFixedWidth(26)
        sl = QSlider(Qt.Horizontal); sl.setRange(0,255); sl.setValue(255)
        sl.setStyleSheet(self._slider_style(C_GREEN))
        lp = QLabel("100%"); lp.setFixedWidth(36)
        lp.setStyleSheet(f"color:{C_TEXT};font-size:11px;background:transparent;border:none;")
        sl.valueChanged.connect(lambda v,l=lp: l.setText(f"{int(v/255*100)}%"))
        sl.sliderReleased.connect(lambda mo=m,s=sl: self._motor_speed(mo,s.value()))
        self._m_speed_sl[m] = sl
        spd_row.addWidget(lv); spd_row.addWidget(sl,1); spd_row.addWidget(lp)
        lay.addLayout(spd_row)
        return card

    def _motor_cmd(self, m, direction):
        D_LBL = {0:"STOP",1:"ADELANTE",2:"ATRAS"}
        D_COL = {0:C_SUB,1:C_GREEN,2:C_RED}
        self._m_dir[m] = direction
        self._m_status[m].setText(D_LBL[direction])
        self._m_status[m].setStyleSheet(
            f"color:{D_COL[direction]};font-size:11px;font-weight:700;"
            f"background:transparent;border:none;")
        self._send(CMD_MOTOR, m, direction,
                   cb=lambda ok,c,v,ex,mo=m,d=direction: self._on_motor(ok,mo,d))

    def _on_motor(self, ok, m, direction):
        D = {0:"Stop",1:"Adelante",2:"Atras"}
        self._table.add(f"M{m} {D[direction]}", "OK" if ok else "ERR", ok)
        self._log(f"M{m} {D[direction]}: {'PASS' if ok else 'FAIL'}",
                  C_GREEN if ok else C_RED)

    def _motor_speed(self, m, spd):
        self._send(CMD_PWM, m, spd,
                   cb=lambda ok,c,v,ex,mo=m,s=spd:
                   self._log(f"M{mo} vel={int(s/255*100)}%: {'OK' if ok else 'ERR'}",
                              C_GREEN if ok else C_RED))

    def _stop_all(self):
        # motores se paran en el paso correspondiente del test
        pass

    # ── Servo IO18 + Digitales IO13/IO15 ─────────────────────
    def _build_servos(self):
        box = QGroupBox("Servo  (IO18)  +  GPIO  (IO13 / IO15)")
        box.setStyleSheet(self._gs(C_TEAL))
        lay = QVBoxLayout(box); lay.setSpacing(8)

        # Servo IO18
        srv_row = QHBoxLayout(); srv_row.setSpacing(8)
        lbl = QLabel("Servo  IO18")
        lbl.setFixedWidth(100)
        lbl.setStyleSheet(f"color:{C_TEAL};font-size:11px;font-weight:700;")
        srv_row.addWidget(lbl)
        sl = QSlider(Qt.Horizontal); sl.setRange(0,180); sl.setValue(90)
        sl.setStyleSheet(self._slider_style(C_TEAL))
        self._srv_sl[1] = sl; srv_row.addWidget(sl,1)
        ld = QLabel("90"); ld.setFixedWidth(28)
        ld.setStyleSheet(f"color:{C_TEXT};font-size:11px;")
        sl.valueChanged.connect(lambda v,l=ld: l.setText(str(v)))
        srv_row.addWidget(ld)
        lbl_deg = QLabel("deg")
        lbl_deg.setStyleSheet(f"color:{C_SUB};font-size:10px;")
        srv_row.addWidget(lbl_deg)
        btn = QPushButton("Set"); btn.setFixedWidth(44); btn.setFixedHeight(28)
        btn.setStyleSheet(self._bs_accent(C_TEAL))
        btn.clicked.connect(lambda _,sld=sl: self._servo_cmd(1,sld.value()))
        srv_row.addWidget(btn)
        lay.addLayout(srv_row)

        # Separador
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C_OVERLAY};max-height:1px;")
        lay.addWidget(sep)

        # Digitales IO13 / IO15
        dig_row = QHBoxLayout(); dig_row.setSpacing(10)
        for gpio in (13, 15):
            card = QFrame()
            card.setStyleSheet(
                f"QFrame{{background:{C_SURFACE};border:1px solid {C_OVERLAY};"
                f"border-radius:6px;}}")
            cl = QHBoxLayout(card); cl.setContentsMargins(10,6,10,6); cl.setSpacing(8)
            lbl_g = QLabel(f"IO{gpio}")
            lbl_g.setStyleSheet(
                f"color:{C_BLUE};font-size:12px;font-weight:700;"
                f"background:transparent;border:none;")
            lbl_g.setFixedWidth(36)
            self._dig_status[gpio] = QLabel("OFF")
            self._dig_status[gpio].setStyleSheet(
                f"color:{C_SUB};font-size:11px;font-weight:700;"
                f"background:transparent;border:none;")
            self._dig_status[gpio].setFixedWidth(30)
            b_on = QPushButton("ON"); b_on.setFixedHeight(30); b_on.setFixedWidth(52)
            b_on.setStyleSheet(
                f"QPushButton{{background:#0d3d1a;color:{C_GREEN};"
                f"border:1px solid {C_GREEN};border-radius:5px;"
                f"font-size:11px;font-weight:700;}}"
                f"QPushButton:hover{{background:#155228;}}")
            b_off = QPushButton("OFF"); b_off.setFixedHeight(30); b_off.setFixedWidth(52)
            b_off.setStyleSheet(
                f"QPushButton{{background:#4a0d0d;color:{C_RED};"
                f"border:1px solid {C_RED};border-radius:5px;"
                f"font-size:11px;font-weight:700;}}"
                f"QPushButton:hover{{background:#6b1515;}}")
            b_on.clicked.connect(lambda _,g=gpio: self._digital_cmd(g,1))
            b_off.clicked.connect(lambda _,g=gpio: self._digital_cmd(g,0))
            cl.addWidget(lbl_g)
            cl.addWidget(self._dig_status[gpio])
            cl.addWidget(b_on); cl.addWidget(b_off)
            dig_row.addWidget(card)
        dig_row.addStretch()
        lay.addLayout(dig_row)
        return box

    def _servo_cmd(self, sid, angle):
        self._send(CMD_SERVO, sid, angle,
                   cb=lambda ok,c,v,ex,a=angle:
                   self._on_servo(ok,a))

    def _on_servo(self, ok, angle):
        self._table.add("Servo IO18", f"{angle}deg", ok)
        self._log(f"Servo IO18 -> {angle}deg: {'PASS' if ok else 'FAIL'}",
                  C_GREEN if ok else C_RED)

    def _digital_cmd(self, gpio, state):
        self._send(CMD_DIGITAL, gpio, state,
                   cb=lambda ok,c,v,ex,g=gpio,s=state:
                   self._on_digital(ok,g,s))

    def _on_digital(self, ok, gpio, state):
        lbl = self._dig_status.get(gpio)
        if lbl and ok:
            lbl.setText("ON" if state else "OFF")
            lbl.setStyleSheet(
                f"color:{C_GREEN if state else C_SUB};font-size:11px;"
                f"font-weight:700;background:transparent;border:none;")
        self._table.add(f"IO{gpio} {'ON' if state else 'OFF'}",
                        "OK" if ok else "ERR", ok)
        self._log(f"IO{gpio} {'ON' if state else 'OFF'}: {'PASS' if ok else 'FAIL'}",
                  C_GREEN if ok else C_RED)

    # ── I2C ─────────────────────────────────────────────────
    KNOWN_I2C = {
        0x3C:"OLED",0x3D:"OLED",0x68:"MPU6050",0x69:"MPU9250",
        0x1E:"HMC5883",0x48:"ADS1115",0x27:"PCF8574(LCD)",
        0x76:"BME280",0x77:"BMP280",0x40:"INA219",
    }

    def _build_i2c(self):
        box = QGroupBox("I2C  (SCL=IO22  SDA=IO21)")
        box.setStyleSheet(self._gs(C_BLUE))
        lay = QHBoxLayout(box); lay.setSpacing(10)
        btn = QPushButton("Escanear I2C")
        btn.setFixedHeight(34); btn.setStyleSheet(self._bs_accent(C_BLUE))
        btn.clicked.connect(self._i2c_scan); lay.addWidget(btn)
        self._i2c_lbl = QLabel("--")
        self._i2c_lbl.setStyleSheet(
            f"color:{C_YELLOW};font-size:11px;font-family:Consolas;")
        self._i2c_lbl.setWordWrap(True)
        lay.addWidget(self._i2c_lbl,1)
        return box

    def _i2c_scan(self):
        self._i2c_lbl.setText("Escaneando...")
        self._send(CMD_I2C_SCAN, 0, 0,
                   cb=lambda ok,c,cnt,ex: self._on_i2c(ok,cnt,ex),
                   timeout=5.0)

    def _on_i2c(self, ok, count, addrs_bytes):
        if not ok:
            self._i2c_lbl.setText("Error de bus")
            self._table.add("I2C Scan","ERROR",False); return
        if count == 0:
            self._i2c_lbl.setText("Bus vacio")
            self._table.add("I2C Scan","0 dispositivos",True)
        else:
            parts = [f"0x{a:02X}({self.KNOWN_I2C.get(a,'?')})" for a in addrs_bytes]
            txt = f"{count}: {', '.join(parts)}"
            self._i2c_lbl.setText(txt)
            self._table.add("I2C Scan",txt,True)
        self._log(f"I2C: {count} dispositivos {'PASS' if ok else 'FAIL'}",
                  C_GREEN if ok else C_RED)

    # ── Prueba completa ──────────────────────────────────────
    def _build_full_btn(self):
        w = QWidget(); lay = QHBoxLayout(w); lay.setContentsMargins(0,0,0,0)
        self._btn_full = QPushButton(
            f"PRUEBA COMPLETA  ({len(FULL_TEST)} pasos)")
        self._btn_full.setFixedHeight(42)
        self._btn_full.setStyleSheet(
            f"QPushButton{{background:#2563eb;color:white;border:none;"
            f"border-radius:8px;font-size:13px;font-weight:700;}}"
            f"QPushButton:hover{{background:#1d4ed8;}}"
            f"QPushButton:disabled{{background:#1e3a6e;color:#7a9fd6;}}")
        self._btn_full.clicked.connect(self._start_full)
        lay.addWidget(self._btn_full)
        btn_cl = QPushButton("Limpiar"); btn_cl.setFixedWidth(80)
        btn_cl.setStyleSheet(self._bs()); btn_cl.clicked.connect(self._reset_ui)
        lay.addWidget(btn_cl)
        return w

    def _start_full(self):
        if not self._check_conn(): return
        self._queue = list(FULL_TEST); self._q_idx = 0; self._running = True
        self._table.clear(); self._badge.hide()
        if self._neo_strip: self._neo_strip.reset()
        # motores se paran en el paso correspondiente del test
        self._btn_full.setEnabled(False)
        self.status_msg.emit("Prueba completa iniciada...")
        self._log(f"=== Prueba completa: {len(FULL_TEST)} pasos ===", C_BLUE)
        self._run_next()

    def _run_next(self):
        if self._q_idx >= len(self._queue):
            self._finish(); return
        nombre, cmd, pid, val, timeout, delay = self._queue[self._q_idx]
        n, total = self._q_idx+1, len(self._queue)
        self.status_msg.emit(f"[{n}/{total}] {nombre}")
        self._log(f"[{n}/{total}] {nombre}", C_SUB)
        w = SerialWorker(self.ser, cmd, pid, val, timeout)
        w.done.connect(lambda ok,c,v,ex,nm=nombre,cm=cmd,i=pid,vl=val,d=delay:
                       self._on_full_result(ok,c,v,ex,nm,cm,i,vl,d))
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w); w.start()

    def _on_full_result(self, ok, cmd, val, extra, nombre, orig_cmd, pid, orig_val, delay):
        if orig_cmd == CMD_NEO:
            rgb = NEO_PAL.get(orig_val,(30,30,30))
            self._neo_strip.fill(rgb if orig_val != 0 else (30,30,30))
        elif orig_cmd == CMD_MOTOR and ok:
            D_LBL={0:"STOP",1:"ADELANTE",2:"ATRAS"}
            D_COL={0:C_SUB,1:C_GREEN,2:C_RED}
            self._m_status[pid].setText(D_LBL.get(orig_val,"STOP"))
            self._m_status[pid].setStyleSheet(
                f"color:{D_COL.get(orig_val,C_SUB)};font-size:11px;"
                f"font-weight:700;background:transparent;border:none;")
        elif orig_cmd == CMD_SERVO and ok and 1 in self._srv_sl:
            self._srv_sl[1].setValue(orig_val)
        elif orig_cmd == CMD_DIGITAL and ok:
            lbl = self._dig_status.get(pid)
            if lbl:
                lbl.setText("ON" if orig_val else "OFF")
                lbl.setStyleSheet(
                    f"color:{C_GREEN if orig_val else C_SUB};font-size:11px;"
                    f"font-weight:700;background:transparent;border:none;")
        elif orig_cmd == CMD_I2C_SCAN:
            self._on_i2c(ok, val, extra)
            self._q_idx += 1
            QTimer.singleShot(delay, self._run_next); return

        if orig_cmd == CMD_MOTOR:
            v_str={0:"Stop",1:"Adelante",2:"Atras"}.get(orig_val,str(orig_val))
        elif orig_cmd == CMD_SERVO:
            v_str = f"{orig_val}deg"
        elif orig_cmd == CMD_NEO:
            v_str = NEO_LBL.get(orig_val,hex(orig_val))
        elif orig_cmd == CMD_DIGITAL:
            v_str = "ON" if orig_val else "OFF"
        else:
            v_str = "OK" if ok else "ERR"

        self._table.add(nombre, v_str, ok)
        self._log(f"  RX: {'PASS' if ok else 'FAIL'}", C_GREEN if ok else C_RED)
        self._q_idx += 1
        QTimer.singleShot(delay, self._run_next)

    def _finish(self):
        self._running = False; self._btn_full.setEnabled(True)
        total = self._table.rowCount()
        fails = sum(1 for r in range(total)
                    if self._table.item(r,2) and
                    self._table.item(r,2).text()=="FAIL")
        if fails == 0:
            self._badge.setText(f"TODAS PASARON  ({total}/{total})")
            self._badge.setStyleSheet(
                f"background:#14532d;color:{C_GREEN};border-radius:8px;padding:2px 12px;")
        else:
            self._badge.setText(f"FALLARON {fails} DE {total}")
            self._badge.setStyleSheet(
                f"background:#7f1d1d;color:{C_RED};border-radius:8px;padding:2px 12px;")
        self._badge.show()
        self.status_msg.emit(f"Prueba completa: {total-fails}/{total} PASS")
        self._log(f"=== Fin: {total-fails}/{total} PASS ===",
                  C_GREEN if fails==0 else C_RED)

    # ── Panel derecho ────────────────────────────────────────
    def _build_right(self):
        w = QWidget(); lay = QVBoxLayout(w)
        lay.setSpacing(8); lay.setContentsMargins(0,0,0,0)
        res_box = QGroupBox("Resultados")
        res_box.setStyleSheet(self._gs(C_BLUE))
        rl = QVBoxLayout(res_box)
        self._table = ResultTable()
        rl.addWidget(self._table,1)
        self._badge = QLabel("")
        self._badge.setAlignment(Qt.AlignCenter); self._badge.setFixedHeight(30)
        self._badge.setFont(QFont("Segoe UI",11,QFont.Bold)); self._badge.hide()
        rl.addWidget(self._badge)
        lay.addWidget(res_box,1)
        log_box = QGroupBox("Log")
        log_box.setStyleSheet(self._gs(C_BLUE))
        ll = QVBoxLayout(log_box)
        hdr = QHBoxLayout(); hdr.addStretch()
        btn_cl = QPushButton("Limpiar"); btn_cl.setFixedWidth(70)
        btn_cl.setStyleSheet(self._bs())
        btn_cl.clicked.connect(lambda: self._log_w.clear()); hdr.addWidget(btn_cl)
        ll.addLayout(hdr)
        self._log_w = QTextEdit(); self._log_w.setReadOnly(True)
        self._log_w.setFont(QFont("Consolas",9)); self._log_w.setFixedHeight(170)
        self._log_w.setStyleSheet(
            f"QTextEdit{{background:{C_MANTLE};color:{C_GREEN};"
            f"border:none;border-radius:4px;}}")
        ll.addWidget(self._log_w)
        lay.addWidget(log_box)
        return w

    # ── Serial ───────────────────────────────────────────────
    def _refresh_ports(self):
        self._combo_port.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self._combo_port.addItems(ports if ports else ["(sin puertos)"])

    def _toggle_conn(self, checked):
        if checked: self._connect()
        else: self._disconnect()

    def _connect(self):
        port = self._combo_port.currentText()
        baud = int(self._combo_baud.currentText())
        try:
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self._lbl_conn.setText("  Conectado")
            self._lbl_conn.setStyleSheet(f"color:{C_GREEN};font-weight:700;font-size:12px;")
            self._btn_conn.setText("Desconectar")
            self._log(f"Conectado: {port} @ {baud}", C_BLUE)
            self.status_msg.emit(f"Tester: {port}")
        except Exception as e:
            self._btn_conn.setChecked(False)
            self._log(f"Error: {e}", C_RED)

    def _disconnect(self):
        if self.ser and self.ser.is_open: self.ser.close()
        self.ser = None
        self._lbl_conn.setText("  Desconectado")
        self._lbl_conn.setStyleSheet(f"color:{C_RED};font-weight:700;font-size:12px;")
        self._btn_conn.setText("Conectar"); self._btn_conn.setChecked(False)

    def _check_conn(self):
        if not self.ser or not self.ser.is_open:
            self._log("Sin conexion serial.", C_RED); return False
        return True

    def _send(self, cmd, pid, val, cb=None, timeout=1.5):
        if not self._check_conn(): return
        w = SerialWorker(self.ser, cmd, pid, val, timeout)
        if cb: w.done.connect(cb)
        w.finished.connect(lambda: self._workers.remove(w) if w in self._workers else None)
        self._workers.append(w); w.start()

    def _do_ping(self):
        self._send(CMD_PING, 0, 0,
                   cb=lambda ok,c,v,ex:
                   self._log("PING -> slave vivo" if ok else "PING -> sin respuesta",
                              C_GREEN if ok else C_RED))

    def _do_reset(self):
        self._send(CMD_RESET, 0, 0,
                   cb=lambda ok,c,v,ex: self._log("RESET enviado.", C_YELLOW))

    def _reset_ui(self):
        self._table.clear(); self._badge.hide()
        if self._neo_strip: self._neo_strip.reset()
        for m in (1,2):
            if m in self._m_status:
                self._m_status[m].setText("STOP")
                self._m_status[m].setStyleSheet(
                    f"color:{C_SUB};font-size:11px;font-weight:700;"
                    f"background:transparent;border:none;")
        for gpio, lbl in self._dig_status.items():
            lbl.setText("OFF")
            lbl.setStyleSheet(
                f"color:{C_SUB};font-size:11px;font-weight:700;"
                f"background:transparent;border:none;")
        if self._i2c_lbl: self._i2c_lbl.setText("--")
        self._btn_full.setEnabled(True)
        self._running = False; self._queue = []; self._q_idx = 0

    def _log(self, msg, color=None):
        color = color or C_TEXT
        ts = datetime.now().strftime("%H:%M:%S")
        safe = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self._log_w.append(
            f'<span style="color:{C_SUB}">[{ts}]</span> '
            f'<span style="color:{color}">{safe}</span>')
        self._log_w.moveCursor(QTextCursor.End)

    # ── Style ────────────────────────────────────────────────
    def _gs(self, accent):
        return (f"QGroupBox{{border:1px solid {C_OVERLAY};border-radius:8px;"
                f"margin-top:10px;font-weight:bold;color:{accent};padding:8px;}}"
                f"QGroupBox::title{{subcontrol-origin:margin;left:10px;padding:0 6px;}}")

    def _bs(self):
        return (f"QPushButton{{background:{C_SURFACE};color:{C_TEXT};"
                f"border:1px solid {C_OVERLAY};border-radius:4px;"
                f"font-size:11px;padding:3px 8px;}}"
                f"QPushButton:hover{{background:{C_OVERLAY};}}"
                f"QPushButton:checked{{background:#2563eb;color:white;border-color:#2563eb;}}"
                f"QPushButton:disabled{{background:{C_MANTLE};color:{C_OVERLAY};}}")

    def _bs_accent(self, accent):
        return (f"QPushButton{{background:{C_SURFACE};color:{accent};"
                f"border:1px solid {accent};border-radius:4px;"
                f"font-size:11px;padding:3px 8px;}}"
                f"QPushButton:hover{{background:{C_OVERLAY};}}")

    def _slider_style(self, accent=C_BLUE):
        return (f"QSlider::groove:horizontal{{height:4px;"
                f"background:{C_OVERLAY};border-radius:2px;}}"
                f"QSlider::handle:horizontal{{background:{accent};"
                f"width:14px;height:14px;margin:-5px 0;border-radius:7px;}}"
                f"QSlider::sub-page:horizontal{{background:{accent};border-radius:2px;}}")

    def _lbl(self, txt):
        l = QLabel(txt); l.setStyleSheet(f"color:{C_TEXT};font-weight:600;")
        return l

    def cleanup(self):
        self._disconnect()
        for w in list(self._workers):
            if w.isRunning(): w.terminate(); w.wait()
        self._workers.clear()