"""
MIT-WPU–style weekly grid: columns = weekdays, rows = periods + recess bands.
Labs span two consecutive period rows (never across recess).
"""
from __future__ import annotations

import html

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")

# (slot_number or None for recess, left header text, short label)
TIMETABLE_ROWS: list[tuple[int | None, str]] = [
    (1, "Period 1\n8:30 – 9:30"),
    (2, "Period 2\n9:30 – 10:30"),
    (None, "RECESS"),
    (3, "Period 3\n10:45 – 11:45"),
    (4, "Period 4\n11:45 – 12:45"),
    (None, "RECESS\n(Lunch break)"),
    (5, "Period 5\n1:30 – 2:30"),
    (6, "Period 6\n2:30 – 3:30"),
    (None, "RECESS"),
    (7, "Period 7\n3:45 – 4:45"),
    (8, "Period 8\n4:45 – 5:45"),
]

SLOT_TO_START_ROW: dict[int, int] = {}
for _i, (sn, _lbl) in enumerate(TIMETABLE_ROWS):
    if sn is not None:
        SLOT_TO_START_ROW[sn] = _i


class ProfessionalTimetableWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.banner = QLabel()
        self.banner.setObjectName("tt_banner")
        self.banner.setWordWrap(True)
        self.banner.setMinimumHeight(72)
        layout.addWidget(self.banner)

        self.table = QTableWidget()
        self.table.setObjectName("professional_timetable")
        nrows = len(TIMETABLE_ROWS)
        ncols = len(DAY_NAMES)
        self.table.setRowCount(nrows)
        self.table.setColumnCount(ncols)
        self.table.setHorizontalHeaderLabels(list(DAY_NAMES))
        self.table.setVerticalHeaderLabels([lbl.replace("\n", " · ") for _, lbl in TIMETABLE_ROWS])
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        font = QFont("Inter", 10)
        if not font.exactMatch():
            font = QFont("Segoe UI", 10)
        self.table.setFont(font)
        self.table.horizontalHeader().setFont(QFont(font.family(), 11, QFont.Weight.DemiBold))
        layout.addWidget(self.table)

        self._apply_styles()

    def _apply_styles(self) -> None:
        self.banner.setStyleSheet(
            """
            QLabel#tt_banner {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #0b1f3b, stop:1 #1a3a6e);
                color: #f2f4f8;
                border-radius: 10px;
                padding: 14px 18px;
                font-size: 13px;
            }
            """
        )
        self.table.setStyleSheet(
            """
            QTableWidget#professional_timetable {
                background-color: #f7f9fc;
                gridline-color: #c5d4e8;
                border: 1px solid #a8bdd9;
                border-radius: 8px;
            }
            QTableWidget#professional_timetable::item {
                padding: 8px;
                border-bottom: 1px solid #d8e3f0;
            }
            QHeaderView::section {
                background-color: #0f2a52;
                color: #ffffff;
                padding: 10px 6px;
                font-weight: 600;
                border: none;
                border-right: 1px solid #1c4580;
            }
            QTableCornerButton::section {
                background-color: #0f2a52;
            }
            """
        )

    def set_banner(
        self,
        *,
        title: str,
        division_line: str,
        meta_line: str,
    ) -> None:
        self.banner.setText(
            f"<div style='font-size:16px;font-weight:700;'>{html.escape(title)}</div>"
            f"<div style='margin-top:6px;opacity:0.92;'>{html.escape(division_line)}</div>"
            f"<div style='margin-top:4px;opacity:0.85;font-size:12px;'>{html.escape(meta_line)}</div>"
        )

    def clear_grid(self) -> None:
        self.table.clearSpans()
        for r in range(self.table.rowCount()):
            for c in range(self.table.columnCount()):
                self.table.removeCellWidget(r, c)
                self.table.setItem(r, c, None)

    def populate(
        self,
        lectures: list[dict],
        *,
        room_names: dict[int, str],
        division_filter: str | None,
    ) -> None:
        self.clear_grid()
        recess_color = QColor(230, 235, 242)
        empty_color = QColor(252, 253, 255)
        lab_bg = "#d6e8ff"
        theory_bg = "#fff8e7"

        for row_idx, (slot_num, _hdr) in enumerate(TIMETABLE_ROWS):
            if slot_num is None:
                it = QTableWidgetItem("— RECESS —")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it.setBackground(recess_color)
                it.setForeground(QColor("#4a5568"))
                f = it.font()
                f.setItalic(True)
                f.setPointSize(9)
                it.setFont(f)
                self.table.setItem(row_idx, 0, it)
                self.table.setSpan(row_idx, 0, 1, self.table.columnCount())

        visible = lectures
        if division_filter and division_filter != "All divisions":
            df = str(division_filter).strip()
            visible = [
                L for L in lectures if str(L.get("division", "")).strip() == df
            ]

        span_covered = set()

        for lec in visible:
            day = int(lec["day"])
            if day < 1 or day > len(DAY_NAMES):
                continue
            col = day - 1
            slot = int(lec["slot"])
            dur = int(lec.get("duration") or 1)
            if dur < 1:
                dur = 1
            if dur > 2:
                dur = 2
            if slot not in SLOT_TO_START_ROW:
                continue
            row = SLOT_TO_START_ROW[slot]
            if dur == 2:
                if slot not in (1, 3, 5, 7):
                    dur = 1
                elif row + 1 >= self.table.rowCount():
                    dur = 1
                elif TIMETABLE_ROWS[row + 1][0] is None:
                    dur = 1

            if self.table.cellWidget(row, col) is not None:
                continue

            rid = int(lec.get("room_id") or 0)
            rname = room_names.get(rid, f"Room {rid}" if rid else "")
            subj = lec.get("subject") or ""
            batch = int(lec.get("batch_id") or 0)
            batch_line = f"Batch {batch}" if batch > 0 else ""

            text = f"<b>{html.escape(subj)}</b>"
            if rname:
                text += f"<br/><span style='color:#2c5282;'>{html.escape(rname)}</span>"
            if batch_line:
                text += f"<br/><span style='font-size:9pt;color:#4a5568;'>{html.escape(batch_line)}</span>"

            bg = lab_bg if dur == 2 else theory_bg
            if dur == 2:
                self.table.setSpan(row, col, 2, 1)
                span_covered.add((row + 1, col))
            ph = QTableWidgetItem()
            ph.setBackground(QColor(bg))
            self.table.setItem(row, col, ph)
            lab = QLabel(text)
            lab.setWordWrap(True)
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lab.setStyleSheet(
                f"padding:10px; background-color:{bg}; color:#1a202c; border-radius:6px;"
            )
            self.table.setCellWidget(row, col, lab)

        for row_idx, (slot_num, _hdr) in enumerate(TIMETABLE_ROWS):
            if slot_num is None:
                continue
            for col in range(self.table.columnCount()):
                if (row_idx, col) in span_covered:
                    continue
                if self.table.cellWidget(row_idx, col) is not None:
                    continue
                it = self.table.item(row_idx, col)
                if it is not None and it.text():
                    continue
                empty = QTableWidgetItem("")
                empty.setBackground(empty_color)
                self.table.setItem(row_idx, col, empty)
