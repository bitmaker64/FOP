"""Shared Qt styles for Faculty Assistant (applied in addition to per-page Designer styles)."""

from PyQt6.QtWidgets import QApplication

APP_STYLESHEET = """
/* --- Dashboard (welcome) --- */
QMainWindow#AppWelcomePage {
    border-image: url(resources/bg1.jpg) 0 0 0 0 stretch stretch;
}

QLabel#dashboard_subtitle {
    color: rgba(241, 245, 249, 0.92);
    font-family: "Inter", "Inter Variable", "Segoe UI", sans-serif;
    font-size: 17px;
    font-weight: 500;
    letter-spacing: 0.03em;
    padding: 8px 24px 20px 24px;
    background: transparent;
}

QFrame#dashCard {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(255, 255, 255, 0.98),
        stop:1 rgba(241, 245, 249, 0.94)
    );
    border: 1px solid rgba(255, 255, 255, 0.9);
    border-radius: 28px;
    min-width: 260px;
    min-height: 300px;
}
QFrame#dashCard:hover {
    border: 1px solid rgba(37, 99, 235, 0.35);
}
QFrame#dashCard QLabel {
    color: #0f172a;
    font-family: "Inter", "Inter Variable", "Segoe UI", sans-serif;
    font-weight: 700;
}
QMainWindow#AppTimetablePage,
QMainWindow#AppStudentPage,
QMainWindow#AppAttendancePage {
    background-color: #e2e8f0;
}

/* Admin toolbar on dashboard */
QFrame#AdminToolbar {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 12px;
    padding: 8px 12px;
}
QFrame#AdminToolbar QLabel {
    color: #e2e8f0;
    font-size: 12px;
    font-weight: 600;
}

/* Primary actions */
QPushButton[btnTier="primary"] {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton[btnTier="primary"]:hover {
    background-color: #1d4ed8;
}
QPushButton[btnTier="primary"]:pressed {
    background-color: #1e3a8a;
}

/* Secondary / outline */
QPushButton[btnTier="secondary"] {
    background-color: rgba(255, 255, 255, 0.12);
    color: #f1f5f9;
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton[btnTier="secondary"]:hover {
    background-color: rgba(255, 255, 255, 0.2);
}

/* Timetable / inner pages: dark toolbar buttons from Designer get overridden */
QMainWindow#AppTimetablePage QPushButton[btnTier="primary"],
QMainWindow#AppStudentPage QPushButton[btnTier="primary"],
QMainWindow#AppAttendancePage QPushButton[btnTier="primary"] {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
}
QMainWindow#AppTimetablePage QPushButton[btnTier="secondary"],
QMainWindow#AppStudentPage QPushButton[btnTier="secondary"],
QMainWindow#AppAttendancePage QPushButton[btnTier="secondary"] {
    background-color: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 9px 14px;
    font-weight: 600;
}
QMainWindow#AppTimetablePage QPushButton[btnTier="secondary"]:hover,
QMainWindow#AppStudentPage QPushButton[btnTier="secondary"]:hover,
QMainWindow#AppAttendancePage QPushButton[btnTier="secondary"]:hover {
    background-color: #f8fafc;
    border-color: #94a3b8;
}

QMainWindow#AppTimetablePage QLabel,
QMainWindow#AppStudentPage QLabel,
QMainWindow#AppAttendancePage QLabel {
    color: #334155;
    font-size: 13px;
}
QMainWindow#AppTimetablePage QComboBox,
QMainWindow#AppAttendancePage QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 28px;
}
QMainWindow#AppTimetablePage QCheckBox,
QMainWindow#AppAttendancePage QCheckBox {
    color: #334155;
    font-size: 13px;
}

/* Dialogs */
QDialog {
    background-color: #f8fafc;
}
QDialog QLabel {
    color: #1e293b;
    font-size: 13px;
}
QDialog QLineEdit, QDialog QSpinBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 8px;
    min-height: 26px;
}
"""


def _repolish(btn) -> None:
    app = QApplication.instance()
    if not app:
        return
    st = app.style()
    st.unpolish(btn)
    st.polish(btn)


def style_primary_button(btn) -> None:
    btn.setProperty("btnTier", "primary")
    _repolish(btn)


def style_secondary_button(btn) -> None:
    btn.setProperty("btnTier", "secondary")
    _repolish(btn)
