import re
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QComboBox,
    QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSortFilterProxyModel
from PyQt5.QtGui import QColor, QFont, QBrush


# ══════════════════════════════════════════════════════════════
#  COLORES Catppuccin Mocha
# ══════════════════════════════════════════════════════════════
C_BASE    = "#1e1e2e"
C_MANTLE  = "#181825"
C_SURFACE = "#313244"
C_OVERLAY = "#45475a"
C_TEXT    = "#cdd6f4"
C_BLUE    = "#89b4fa"
C_GREEN   = "#a6e3a1"
C_RED     = "#f38ba8"
C_YELLOW  = "#f9e2af"
C_MAUVE   = "#cba6f7"
C_TEAL    = "#94e2d5"


# ══════════════════════════════════════════════════════════════
#  HILO LECTOR DE SHEETS
# ══════════════════════════════════════════════════════════════
class SheetsReader(QThread):
    """Lee una o todas las hojas y emite los resultados."""
    result_ready = pyqtSignal(list)   # lista de dicts
    error        = pyqtSignal(str)

    def __init__(self, sheet_id, sheet_map, categoria="Todas", estado_filter="Todos",
                 query="", header_row=1):
        super().__init__()
        self.sheet_id      = sheet_id
        self.sheet_map     = sheet_map          # {"ESP32": "ESP32", ...}
        self.categoria     = categoria
        self.estado_filter = estado_filter
        self.query         = query.strip().lower()
        self.header_row    = header_row

    def run(self):
        try:
            import gspread
            gc = gspread.oauth(
                credentials_filename='credentials.json',
                authorized_user_filename='token.json'
            )
            book = gc.open_by_key(self.sheet_id)

            # Decide qué hojas leer
            if self.categoria == "Todas":
                targets = list(self.sheet_map.values())
            else:
                targets = [self.sheet_map.get(self.categoria, self.categoria)]

            rows = []
            for sheet_name in targets:
                try:
                    ws = book.worksheet(sheet_name)
                    all_vals = ws.get_all_values()
                    # Filas de datos empiezan en header_row (índice 0-based = header_row)
                    for raw in all_vals[self.header_row:]:
                        # Columnas: A=Estado, B=ID, C=QR, D=Timestamp, E=Notas
                        if len(raw) < 3:
                            continue
                        estado = (raw[0] if len(raw) > 0 else "").strip()
                        id_num = (raw[1] if len(raw) > 1 else "").strip()
                        qr     = (raw[2] if len(raw) > 2 else "").strip()
                        ts     = (raw[3] if len(raw) > 3 else "").strip()
                        notas  = (raw[4] if len(raw) > 4 else "").strip()

                        if not qr and not id_num:
                            continue  # fila vacía

                        # Filtro estado
                        if self.estado_filter != "Todos":
                            if estado.upper() != self.estado_filter.upper():
                                continue

                        # Filtro query (nombre / número)
                        if self.query:
                            searchable = f"{qr} {id_num} {notas}".lower()
                            if self.query not in searchable:
                                continue

                        rows.append({
                            "categoria": sheet_name,
                            "estado":    estado,
                            "id":        id_num,
                            "qr":        qr,
                            "timestamp": ts,
                            "notas":     notas,
                        })
                except Exception:
                    pass  # hoja no accesible, se salta

            self.result_ready.emit(rows)

        except FileNotFoundError:
            self.error.emit("credentials.json / token.json no encontrado")
        except Exception as e:
            self.error.emit(str(e))


# ══════════════════════════════════════════════════════════════
#  TABLA BONITA
# ══════════════════════════════════════════════════════════════
HEADERS = ["Categoría", "Estado", "ID", "Código QR", "Timestamp", "Notas"]

TABLA_STYLE = f"""
QTableWidget {{
    background: {C_MANTLE};
    color: {C_TEXT};
    gridline-color: {C_OVERLAY};
    border: 1px solid {C_OVERLAY};
    border-radius: 6px;
    font-size: 12px;
}}
QTableWidget::item {{
    padding: 6px 10px;
}}
QTableWidget::item:selected {{
    background: #3b4261;
    color: {C_TEXT};
}}
QHeaderView::section {{
    background: {C_SURFACE};
    color: {C_BLUE};
    font-weight: 700;
    font-size: 12px;
    padding: 8px 10px;
    border: none;
    border-right: 1px solid {C_OVERLAY};
    border-bottom: 2px solid {C_BLUE};
}}
QHeaderView::section:last {{
    border-right: none;
}}
QScrollBar:vertical {{
    background: {C_MANTLE};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {C_OVERLAY};
    border-radius: 5px;
    min-height: 20px;
}}
"""


class ResultTable(QTableWidget):
    def __init__(self):
        super().__init__(0, len(HEADERS))
        self.setHorizontalHeaderLabels(HEADERS)
        self.setStyleSheet(TABLA_STYLE)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setStyleSheet(self.styleSheet() + """
            QTableWidget { alternate-background-color: #1a1a2a; }
        """)

    def populate(self, rows: list):
        self.setSortingEnabled(False)
        self.setRowCount(0)
        for row_data in rows:
            r = self.rowCount()
            self.insertRow(r)
            values = [
                row_data["categoria"],
                row_data["estado"],
                row_data["id"],
                row_data["qr"],
                row_data["timestamp"],
                row_data["notas"],
            ]
            for c, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)

                # Colorear columna Estado
                if c == 1:
                    if val.upper() == "OK":
                        item.setForeground(QBrush(QColor(C_GREEN)))
                        item.setFont(QFont("Segoe UI", 11, QFont.Bold))
                    elif val.upper() == "FAIL":
                        item.setForeground(QBrush(QColor(C_RED)))
                        item.setFont(QFont("Segoe UI", 11, QFont.Bold))
                    else:
                        item.setForeground(QBrush(QColor(C_YELLOW)))

                # Colorear columna Categoría
                elif c == 0:
                    cat_colors = {
                        "ESP32": C_BLUE, "Robofut": C_MAUVE,
                        "Todoterreno": C_TEAL, "STEM SR": "#fab387",
                        "STEM JR": "#f9e2af", "Drones": "#89dceb",
                        "IOT": "#94e2d5",
                    }
                    item.setForeground(QBrush(QColor(cat_colors.get(val, C_TEXT))))
                    item.setFont(QFont("Segoe UI", 11, QFont.Bold))

                self.setItem(r, c, item)

            self.setRowHeight(r, 34)

        self.setSortingEnabled(True)


# ══════════════════════════════════════════════════════════════
#  PESTAÑA BUSCADOR
# ══════════════════════════════════════════════════════════════
class TabBuscador(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self, sheet_id, sheet_map, header_row=1):
        super().__init__()
        self.sheet_id   = sheet_id
        self.sheet_map  = sheet_map
        self.header_row = header_row
        self._worker    = None
        self._build_ui()

    # ── UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        root.addWidget(self._build_filter_bar())
        root.addWidget(self._build_stats_bar())
        root.addWidget(self._build_table(), 1)

    def _build_filter_bar(self):
        box = QGroupBox("Filtros de búsqueda")
        box.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {C_OVERLAY};
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
                color: {C_BLUE};
                padding: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }}
        """)
        lay = QHBoxLayout(box)
        lay.setSpacing(14)

        # Categoría
        lay.addWidget(self._lbl("Categoría:"))
        self.combo_cat = QComboBox()
        self.combo_cat.addItems(["Todas", "ESP32", "Robofut", "Todoterreno",
                                  "STEM SR", "STEM JR", "Drones", "IOT"])
        self.combo_cat.setMinimumWidth(130)
        lay.addWidget(self.combo_cat)

        lay.addWidget(self._lbl("Estado:"))
        self.combo_estado = QComboBox()
        self.combo_estado.addItems(["Todos", "OK", "FAIL"])
        self.combo_estado.setMinimumWidth(90)
        lay.addWidget(self.combo_estado)

        lay.addWidget(self._lbl("Nombre / Nº:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ej: 007  ó  ESP32-BALAM-003")
        self.search_input.setMinimumWidth(200)
        self.search_input.returnPressed.connect(self._buscar)
        lay.addWidget(self.search_input, 1)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.setProperty("primary", True)
        self.btn_buscar.setFixedWidth(120)
        self.btn_buscar.setFixedHeight(32)
        self.btn_buscar.clicked.connect(self._buscar)
        lay.addWidget(self.btn_buscar)

        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.setFixedWidth(100)
        self.btn_limpiar.setFixedHeight(32)
        self.btn_limpiar.clicked.connect(self._limpiar)
        lay.addWidget(self.btn_limpiar)

        return box

    def _build_stats_bar(self):
        w = QWidget()
        w.setStyleSheet(f"background:{C_MANTLE}; border-radius:6px; padding:4px;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(12, 6, 12, 6)

        self.lbl_total = self._stat_lbl("Total", "0", C_BLUE)
        self.lbl_ok    = self._stat_lbl("OK",    "0", C_GREEN)
        self.lbl_fail  = self._stat_lbl("FAIL",  "0", C_RED)
        self.lbl_otros = self._stat_lbl("Otros", "0", C_YELLOW)
        self.lbl_ts    = QLabel("")
        self.lbl_ts.setStyleSheet(f"color:{C_OVERLAY}; font-size:11px;")

        for w2 in [self.lbl_total, self.lbl_ok, self.lbl_fail, self.lbl_otros]:
            lay.addWidget(w2)
            sep = QLabel("|")
            sep.setStyleSheet(f"color:{C_OVERLAY};")
            lay.addWidget(sep)

        lay.addStretch()
        lay.addWidget(self.lbl_ts)
        return w

    def _stat_lbl(self, label: str, value: str, color: str):
        w = QLabel(f'<span style="color:{C_OVERLAY}; font-size:11px;">{label}: </span>'
                   f'<span style="color:{color}; font-size:14px; font-weight:700;">{value}</span>')
        w.setTextFormat(Qt.RichText)
        return w

    def _update_stat(self, lbl_widget, label, value, color):
        lbl_widget.setText(
            f'<span style="color:{C_OVERLAY}; font-size:11px;">{label}: </span>'
            f'<span style="color:{color}; font-size:14px; font-weight:700;">{value}</span>'
        )

    def _build_table(self):
        self.table = ResultTable()
        return self.table

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"color:{C_TEXT}; font-weight:600;")
        return l

    # ── Acciones ────────────────────────────────────────────────
    def _buscar(self):
        cat     = self.combo_cat.currentText()
        estado  = self.combo_estado.currentText()
        query   = self.search_input.text()

        self.btn_buscar.setEnabled(False)
        self.btn_buscar.setText("Buscando…")
        self.status_msg.emit("Consultando Google Sheets…")

        self._worker = SheetsReader(
            sheet_id=self.sheet_id,
            sheet_map=self.sheet_map,
            categoria=cat,
            estado_filter=estado,
            query=query,
            header_row=self.header_row,
        )
        self._worker.result_ready.connect(self._on_results)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _limpiar(self):
        self.combo_cat.setCurrentIndex(0)
        self.combo_estado.setCurrentIndex(0)
        self.search_input.clear()
        self.table.setRowCount(0)
        self._update_stat(self.lbl_total, "Total", "0", C_BLUE)
        self._update_stat(self.lbl_ok,    "OK",    "0", C_GREEN)
        self._update_stat(self.lbl_fail,  "FAIL",  "0", C_RED)
        self._update_stat(self.lbl_otros, "Otros", "0", C_YELLOW)
        self.lbl_ts.setText("")
        self.status_msg.emit("Listo.")

    def _on_results(self, rows: list):
        self.table.populate(rows)

        total = len(rows)
        ok    = sum(1 for r in rows if r["estado"].upper() == "OK")
        fail  = sum(1 for r in rows if r["estado"].upper() == "FAIL")
        otros = total - ok - fail

        self._update_stat(self.lbl_total, "Total", str(total), C_BLUE)
        self._update_stat(self.lbl_ok,    "OK",    str(ok),    C_GREEN)
        self._update_stat(self.lbl_fail,  "FAIL",  str(fail),  C_RED)
        self._update_stat(self.lbl_otros, "Otros", str(otros), C_YELLOW)
        self.lbl_ts.setText(f"Actualizado: {datetime.now().strftime('%H:%M:%S')}")

        self.btn_buscar.setEnabled(True)
        self.btn_buscar.setText("Buscar")
        self.status_msg.emit(f"{total} resultado(s) encontrado(s).")

    def _on_error(self, msg: str):
        self.btn_buscar.setEnabled(True)
        self.btn_buscar.setText("Buscar")
        self.status_msg.emit(f"Error: {msg}")
        # Mostrar error en tabla como fila roja
        self.table.setRowCount(1)
        item = QTableWidgetItem(f"Error al conectar con Sheets: {msg}")
        item.setForeground(QBrush(QColor(C_RED)))
        item.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.table.setItem(0, 0, item)
        self.table.setSpan(0, 0, 1, len(HEADERS))

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
