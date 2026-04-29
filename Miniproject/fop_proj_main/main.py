import html
import os
import sys

from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QGraphicsOpacityEffect,
    QWidget,
)
from PyQt6.QtGui import QFont, QFontDatabase, QIcon
from PyQt6.QtCore import Qt, QEasingCurve, QPropertyAnimation

from ui_login import Ui_MainWindow as Ui_LoginScreen
from ui_dashboard import Ui_MainWindow as Ui_DashboardScreen
from ui_timetablepg import Ui_MainWindow as Ui_timetable
from ui_studentpg import Ui_MainWindow as Ui_student
from ui_attendancepg import Ui_MainWindow as Ui_attendance
from timetable_ui import ProfessionalTimetableWidget
import backend_bridge as bb
from app_theme import APP_STYLESHEET, style_primary_button, style_secondary_button

if sys.platform == "win32":
    import ctypes

    myappid = "mycompany.myproduct.subproduct.version"
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except OSError:
        pass

APP_STATE = {
    "faculty_id": None,
    "is_admin": False,
    "display_name": "",
}


def _clamp_widget_fonts(root: QWidget) -> None:
    """Qt Designer often sets pointSize -1; QFont warns when that propagates."""
    for w in root.findChildren(QWidget):
        f = w.font()
        if f.pointSize() <= 0:
            nf = QFont(f)
            nf.setPointSize(10)
            w.setFont(nf)


class LoginFailedPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(300, 200)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.box = QFrame(self)
        self.box.setStyleSheet(
            """
            QFrame {
                background-color: rgba(20, 20, 20, 240);
                border-radius: 20px;
            }
            QLabel { color: white; border: none; background: transparent; }
            QPushButton {
                background-color: #007AFF; color: white; border-radius: 10px;
                padding: 8px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #005bb5; }
            """
        )
        box_layout = QVBoxLayout(self.box)
        box_layout.setContentsMargins(20, 30, 20, 20)
        box_layout.setSpacing(15)
        title_label = QLabel("Login Failed")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)
        sub_label = QLabel("Incorrect username or password")
        sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font1 = QFont()
        font1.setPointSize(10)
        sub_label.setFont(font1)
        try_again_btn = QPushButton("Try Again")
        try_again_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try_again_btn.clicked.connect(self.accept)
        box_layout.addWidget(title_label)
        box_layout.addWidget(sub_label)
        box_layout.addWidget(try_again_btn)
        main_layout.addWidget(self.box)


class AddFacultyDialog(QDialog):
    """Append a single faculty row to faculty.dat (does not replace CSV import)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add faculty member")
        self.setMinimumWidth(420)
        form = QFormLayout(self)
        self.id_spin = QSpinBox()
        self.id_spin.setRange(1, 999)
        self.name_edit = QLineEdit()
        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 60)
        self.max_spin.setValue(24)
        form.addRow("Faculty ID (unique)", self.id_spin)
        form.addRow("Full name", self.name_edit)
        form.addRow("Username", self.user_edit)
        form.addRow("Password", self.pass_edit)
        form.addRow("Max teaching hours / week", self.max_spin)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _try_accept(self):
        bb.set_working_directory()
        try:
            bb.load_library()
        except bb.BackendError:
            QMessageBox.critical(
                self,
                "Backend",
                "Native library missing. Build with: make",
            )
            return
        fid = self.id_spin.value()
        existing = {r["id"] for r in bb.read_all_faculty_records()}
        if fid in existing:
            QMessageBox.warning(
                self,
                "Duplicate ID",
                "That faculty ID already exists in faculty.dat. Choose another ID.",
            )
            return
        name = self.name_edit.text().strip()
        user = self.user_edit.text().strip()
        pw = self.pass_edit.text()
        if not name or not user or not pw:
            QMessageBox.warning(self, "Missing fields", "Fill in name, username, and password.")
            return
        if not bb.add_faculty_record(fid, name, user, pw, self.max_spin.value()):
            QMessageBox.warning(self, "Error", "Could not append to faculty.dat.")
            return
        self.accept()


class AddClassroomDialog(QDialog):
    """Append one classroom to rooms.dat (importing rooms.csv replaces the whole file)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add classroom / lab location")
        self.setMinimumWidth(440)
        form = QFormLayout(self)
        self.id_spin = QSpinBox()
        self.id_spin.setRange(1, 999)
        self.id_spin.setToolTip(
            "Unique room id stored in rooms.dat. "
            "The timetable solver loads up to 32 rooms — prefer ids 1–32."
        )
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Wing A — Room 204 or LAB North")
        self.lab_cb = QCheckBox("Laboratory / computer lab space")
        self.lab_cb.setToolTip(
            "Lab-flagged rooms host practical sessions; theory classes use regular classrooms."
        )
        form.addRow("Room ID (unique)", self.id_spin)
        form.addRow("Location / room name", self.name_edit)
        form.addRow("", self.lab_cb)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _try_accept(self):
        bb.set_working_directory()
        try:
            bb.load_library()
        except bb.BackendError:
            QMessageBox.critical(
                self,
                "Backend",
                "Native library missing. Build with: make",
            )
            return
        rid = self.id_spin.value()
        existing = {r["id"] for r in bb.read_all_room_records()}
        if rid in existing:
            QMessageBox.warning(
                self,
                "Duplicate ID",
                "That room ID already exists in rooms.dat. Choose another ID.",
            )
            return
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Enter a classroom or lab location name.")
            return
        if not bb.add_room_record(rid, name, self.lab_cb.isChecked()):
            QMessageBox.warning(self, "Error", "Could not append to rooms.dat.")
            return
        self.accept()


class Student(QMainWindow):
    def __init__(self, stack_controller):
        super().__init__()
        self.stack = stack_controller
        self.setObjectName("AppStudentPage")
        self.setStyleSheet("")
        self.ui = Ui_student()
        self.ui.setupUi(self)
        style_secondary_button(self.ui.back_button)
        self.ui.back_button.clicked.connect(self.back)


    def back(self):
        self.stack.setCurrentIndex(1)


class Attendance(QMainWindow):
    def __init__(self, stack_controller):
        super().__init__()
        self.stack = stack_controller
        self.setObjectName("AppAttendancePage")
        self.setStyleSheet("")
        self.ui = Ui_attendance()
        self.ui.setupUi(self)
        cw = self.ui.centralwidget
        outer = QVBoxLayout(cw)
        outer.setContentsMargins(20, 16, 20, 20)
        top = QHBoxLayout()
        top.addStretch()
        top.addWidget(self.ui.back_button)
        outer.addLayout(top)

        self.info = QLabel(
            "If you will be absent for a teaching period, choose the day and starting period. "
            "For a 2-period lab, pick the first period of that block. "
            "Substitutes are chosen first from faculty who teach the same subject in "
            "requirements.csv (lab sessions prefer colleagues with a lab line for that course), "
            "then by the lightest weekly load. If no subject match exists, any free faculty "
            "within hour limits is used."
        )
        self.info.setWordWrap(True)
        outer.addWidget(self.info)

        self.faculty_form = QWidget()
        ff = QFormLayout(self.faculty_form)
        self.day_combo = QComboBox()
        for i, name in enumerate(
            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        ):
            self.day_combo.addItem(name, i + 1)
        self.slot_combo = QComboBox()
        for s in range(1, 9):
            self.slot_combo.addItem(f"Period {s}", s)
        ff.addRow("Day", self.day_combo)
        ff.addRow("Starting period", self.slot_combo)
        self.report_btn = QPushButton("Report absence & assign substitute")
        self.report_btn.clicked.connect(self._report_absence)
        ff.addRow(self.report_btn)
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        ff.addRow(self.status_lbl)
        outer.addWidget(self.faculty_form)

        self.admin_note = QLabel("Absence reporting is available when you sign in as faculty (not admin).")
        self.admin_note.setWordWrap(True)
        outer.addWidget(self.admin_note)
        outer.addStretch()

        style_secondary_button(self.ui.back_button)
        style_primary_button(self.report_btn)
        self.ui.back_button.clicked.connect(self.back)

    def showEvent(self, event):
        super().showEvent(event)
        fac = APP_STATE.get("faculty_id")
        adm = APP_STATE.get("is_admin", False)
        is_fac = fac is not None and not adm
        self.faculty_form.setVisible(is_fac)
        self.info.setVisible(is_fac)
        self.admin_note.setVisible(not is_fac)

    def _backend_ready(self) -> bool:
        try:
            bb.load_library()
            return True
        except bb.BackendError:
            return False

    def _report_absence(self):
        fid = APP_STATE.get("faculty_id")
        if fid is None or APP_STATE.get("is_admin"):
            return
        if not self._backend_ready():
            QMessageBox.critical(
                self,
                "Backend",
                "Native library missing. Run `make` in the project folder.",
            )
            return
        bb.set_working_directory()
        day = int(self.day_combo.currentData())
        slot = int(self.slot_combo.currentData())
        sub_id = bb.report_absence(int(fid), day, slot)
        if sub_id is None:
            QMessageBox.warning(
                self,
                "Could not assign substitute",
                "There may be no class at that time, or no other faculty is free "
                "within their weekly hour limit.",
            )
            self.status_lbl.setText("")
            return
        sub_name = bb.faculty_display_name(sub_id) or f"ID {sub_id}"
        self.status_lbl.setText(
            f"Substitute assigned: {sub_name} (faculty id {sub_id}). Timetable file updated."
        )
        QMessageBox.information(
            self,
            "Substitute assigned",
            f"Your session is assigned to {sub_name} for that slot.",
        )

    def back(self):
        self.stack.setCurrentIndex(1)



class TimeTable(QMainWindow):
    def __init__(self, stack_controller):
        super().__init__()
        self.setObjectName("AppTimetablePage")
        self.setStyleSheet("")
        self.stack = stack_controller
        self.ui = Ui_timetable()
        self.ui.setupUi(self)
        self.ui.back_button.clicked.connect(self.back)

        cw = self.ui.centralwidget
        root = QVBoxLayout(cw)
        root.setContentsMargins(16, 48, 16, 16)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(QLabel("Division"))
        self.division_combo = QComboBox()
        self.division_combo.setMinimumWidth(200)
        top.addWidget(self.division_combo)
        self.my_only_cb = QCheckBox("Show only my classes")
        self.my_only_cb.toggled.connect(self._refresh)
        top.addWidget(self.my_only_cb)
        self.generate_btn = QPushButton("Generate timetable")
        self.generate_btn.clicked.connect(self._run_generate)
        top.addWidget(self.generate_btn)
        self.refresh_btn = QPushButton("Reload from file")
        self.refresh_btn.clicked.connect(self._refresh)
        top.addWidget(self.refresh_btn)
        top.addStretch()
        top.addWidget(self.ui.back_button)
        root.addLayout(top)

        self.admin_row = QWidget()
        admin_lay = QHBoxLayout(self.admin_row)
        admin_lay.setSpacing(10)
        admin_lay.setContentsMargins(0, 4, 0, 0)
        self.import_csv_btn = QPushButton("Import all data CSVs")
        self.import_csv_btn.setToolTip(
            "Rebuild faculty.dat, rooms.dat, and requirements.dat from faculty.csv, "
            "rooms.csv (classroom locations), and requirements.csv."
        )
        self.import_csv_btn.clicked.connect(self._import_csvs)
        self.import_rooms_btn = QPushButton("Import classrooms (rooms.csv)")
        self.import_rooms_btn.setToolTip(
            "Rebuild rooms.dat only from rooms.csv — columns: id, name, is_lab (0=classroom, 1=lab)."
        )
        self.import_rooms_btn.clicked.connect(self._import_rooms_only)
        self.add_classroom_btn = QPushButton("Add classroom…")
        self.add_classroom_btn.setToolTip("Append one room or lab to rooms.dat without replacing the CSV.")
        self.add_classroom_btn.clicked.connect(self._open_add_classroom)
        admin_lay.addWidget(self.import_csv_btn)
        admin_lay.addWidget(self.import_rooms_btn)
        admin_lay.addWidget(self.add_classroom_btn)
        admin_lay.addStretch()
        root.addWidget(self.admin_row)
        self.admin_row.setVisible(False)

        style_primary_button(self.generate_btn)
        style_secondary_button(self.refresh_btn)
        style_primary_button(self.import_csv_btn)
        style_primary_button(self.import_rooms_btn)
        style_primary_button(self.add_classroom_btn)
        style_secondary_button(self.ui.back_button)

        self.tt_view = ProfessionalTimetableWidget()
        root.addWidget(self.tt_view)

        self._lectures: list[dict] = []
        self._update_my_only_visibility()
        self._fill_division_combo()
        self.division_combo.currentIndexChanged.connect(lambda _: self._refresh())
        self._update_admin_timetable_tools()
        self._refresh()

    def _backend_ready(self) -> bool:
        try:
            bb.load_library()
            return True
        except bb.BackendError:
            return False

    def _update_admin_timetable_tools(self):
        adm = APP_STATE.get("is_admin", False)
        self.admin_row.setVisible(adm)

    def _import_rooms_only(self):
        if not self._backend_ready():
            QMessageBox.critical(
                self,
                "Backend",
                "Native library missing. From the project folder run: make",
            )
            return
        bb.set_working_directory()
        ok, msg = bb.import_rooms_csv()
        if not ok:
            QMessageBox.warning(self, "Import failed", msg)
            return
        QMessageBox.information(
            self,
            "Classrooms imported",
            "rooms.dat was rebuilt from rooms.csv. Generate or reload the timetable as needed.",
        )
        self._refresh()

    def _open_add_classroom(self):
        if not self._backend_ready():
            QMessageBox.critical(
                self,
                "Backend",
                "Native library missing. From the project folder run: make",
            )
            return
        dlg = AddClassroomDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(
                self,
                "Classroom added",
                "Room appended to rooms.dat. Importing rooms.csv again will replace the entire room list.",
            )
            self._refresh()

    def _import_csvs(self):
        if not self._backend_ready():
            QMessageBox.critical(
                self,
                "Backend",
                "Native library missing. From the project folder run: make",
            )
            return
        bb.set_working_directory()
        ok, msg = bb.import_all_csvs()
        if not ok:
            QMessageBox.warning(self, "Import failed", msg)
            return
        QMessageBox.information(
            self,
            "Import complete",
            "Imported faculty.csv, rooms.csv, and requirements.csv into binary .dat files. "
            "Use Generate timetable when you are ready.",
        )
        self._refresh()

    def _update_my_only_visibility(self):
        fid = APP_STATE.get("faculty_id")
        admin = APP_STATE.get("is_admin")
        self.my_only_cb.setVisible(bool(fid is not None and not admin))

    def _fill_division_combo(self):
        prev = self.division_combo.currentData()
        self.division_combo.blockSignals(True)
        self.division_combo.clear()
        divs = sorted({str(L["division"]) for L in self._lectures if L.get("division")})
        self.division_combo.addItem("All divisions", "All divisions")
        for d in divs:
            self.division_combo.addItem(f"Division {d}", d)
        if prev is not None:
            for i in range(self.division_combo.count()):
                if self.division_combo.itemData(i) == prev:
                    self.division_combo.setCurrentIndex(i)
                    break
            else:
                self.division_combo.setCurrentIndex(0)
        else:
            self.division_combo.setCurrentIndex(0)
        self.division_combo.blockSignals(False)

    def _run_generate(self):
        if not self._backend_ready():
            QMessageBox.critical(
                self,
                "Backend",
                "Native library missing. From the project folder run: make\n"
                "(Windows: build backend.c as backend.dll in this directory.)",
            )
            return
        bb.set_working_directory()
        if not bb.generate_timetable_native():
            QMessageBox.warning(
                self,
                "Timetable",
                "Could not build a feasible timetable. Check requirements.dat, "
                "faculty hour caps, and rooms — then try again.",
            )
            return
        self._refresh()

    def _refresh(self):
        bb.set_working_directory()
        self._lectures = bb.read_all_lectures()
        self._fill_division_combo()
        self._update_my_only_visibility()
        rooms = bb.read_room_map()
        div_data = self.division_combo.currentData()
        div_filter = div_data if div_data else "All divisions"
        lectures = list(self._lectures)
        if self.my_only_cb.isVisible() and self.my_only_cb.isChecked():
            fid = APP_STATE.get("faculty_id")
            if fid is not None:
                lectures = [L for L in lectures if int(L.get("faculty_id", -1)) == int(fid)]
        title = "Faculty of Engineering & Technology — Weekly Timetable"
        div_line = (
            f"Division {div_filter}"
            if div_filter != "All divisions"
            else "All divisions (overview)"
        )
        meta = (
            "College-wide view · 8 periods with scheduled recess · "
            "2-period sessions are lab blocks (pairs 1–2, 3–4, 5–6, 7–8) · "
            "At most one lab/practical block per division per day (other periods are theory)"
        )
        self.tt_view.set_banner(title=title, division_line=div_line, meta_line=meta)
        self.tt_view.populate(lectures, room_names=rooms, division_filter=div_filter)

    def showEvent(self, event):
        super().showEvent(event)
        self._update_my_only_visibility()
        self._update_admin_timetable_tools()
        # Reload file when tab opens (timetable may have changed elsewhere)
        self._refresh()

    def back(self):
        self.stack.setCurrentIndex(1)


class WelcomeWindow(QMainWindow):
    def __init__(self, stack_controller):
        super().__init__()
        self.setObjectName("AppWelcomePage")
        self.stack = stack_controller
        self.ui = Ui_DashboardScreen()
        self.ui.setupUi(self)
        style_secondary_button(self.ui.signout_button)
        self.ui.label_welcome.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.ui.label_welcome.setAutoFillBackground(False)
        self.opacity_effect = QGraphicsOpacityEffect(self.ui.label_welcome)
        self.ui.label_welcome.setGraphicsEffect(self.opacity_effect)
        self.ui.card_layout2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ui.card_layout.setSpacing(36)
        self.ui.card_timetable.setObjectName("dashCard")
        self.ui.card_attendance.setObjectName("dashCard")
        self.ui.card_student.setObjectName("dashCard")
        self.ui.card_timetable.clicked.connect(self.timetable_viewer)
        self.ui.card_student.clicked.connect(self.student_viewer)
        self.ui.card_attendance.clicked.connect(self.attendance_viewer)
        self.admin_strip = QFrame(self.ui.centralwidget)
        self.admin_strip.setObjectName("AdminToolbar")
        outer_adm = QVBoxLayout(self.admin_strip)
        outer_adm.setContentsMargins(12, 10, 12, 10)
        outer_adm.setSpacing(8)
        hdr = QLabel("Administrator — data & classrooms")
        hdr.setStyleSheet("color: #e2e8f0; font-weight: 700; font-size: 13px;")
        outer_adm.addWidget(hdr)
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.btn_import_csv_dash = QPushButton("Import all data CSVs")
        self.btn_add_faculty_dash = QPushButton("Add faculty…")
        self.btn_import_csv_dash.setToolTip(
            "Import faculty.csv, rooms.csv (classrooms/labs), and requirements.csv into .dat files."
        )
        self.btn_import_rooms_dash = QPushButton("Import classrooms (rooms.csv)")
        self.btn_import_rooms_dash.setToolTip("Rebuild rooms.dat from rooms.csv only.")
        self.btn_add_classroom_dash = QPushButton("Add classroom…")
        self.btn_add_classroom_dash.setToolTip("Append a single room or lab to rooms.dat.")
        self.btn_import_csv_dash.clicked.connect(self._import_csvs_dashboard)
        self.btn_add_faculty_dash.clicked.connect(self._open_add_faculty)
        self.btn_import_rooms_dash.clicked.connect(self._import_rooms_dashboard)
        self.btn_add_classroom_dash.clicked.connect(self._open_add_classroom_dash)
        row1.addWidget(self.btn_import_csv_dash)
        row1.addWidget(self.btn_add_faculty_dash)
        row1.addStretch()
        outer_adm.addLayout(row1)
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(self.btn_import_rooms_dash)
        row2.addWidget(self.btn_add_classroom_dash)
        row2.addStretch()
        outer_adm.addLayout(row2)
        style_primary_button(self.btn_import_csv_dash)
        style_primary_button(self.btn_add_faculty_dash)
        style_primary_button(self.btn_import_rooms_dash)
        style_primary_button(self.btn_add_classroom_dash)
        self.ui.verticalLayout.insertWidget(1, self.admin_strip)
        self.admin_strip.setVisible(False)
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(1500)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_anim.start()
        self.ui.signout_button.clicked.connect(self.signout)

        self._subtitle = QLabel(
            "Faculty of Engineering & Technology · Weekly timetables, attendance & student insights"
        )
        self._subtitle.setObjectName("dashboard_subtitle")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle.setWordWrap(True)
        idx = self.ui.verticalLayout.indexOf(self.ui.card_layout2)
        if idx >= 0:
            self.ui.verticalLayout.insertWidget(idx + 1, self._subtitle)

    def _backend_ok(self) -> bool:
        try:
            bb.load_library()
            return True
        except bb.BackendError:
            return False

    def _import_csvs_dashboard(self):
        if not self._backend_ok():
            QMessageBox.critical(
                self,
                "Backend",
                "Could not load libbackend. Run `make` in the project folder.",
            )
            return
        bb.set_working_directory()
        ok, msg = bb.import_all_csvs()
        if not ok:
            QMessageBox.warning(self, "Import failed", msg)
            return
        QMessageBox.information(
            self,
            "Import complete",
            "Imported faculty.csv, rooms.csv, and requirements.csv. "
            "Open Timetable and choose Generate timetable when ready.",
        )

    def _open_add_faculty(self):
        if not self._backend_ok():
            QMessageBox.critical(
                self,
                "Backend",
                "Could not load libbackend. Run `make` in the project folder.",
            )
            return
        dlg = AddFacultyDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(
                self,
                "Faculty added",
                "Record appended to faculty.dat. Re-importing faculty.csv will replace the whole file.",
            )

    def _import_rooms_dashboard(self):
        if not self._backend_ok():
            QMessageBox.critical(
                self,
                "Backend",
                "Could not load libbackend. Run `make` in the project folder.",
            )
            return
        bb.set_working_directory()
        ok, msg = bb.import_rooms_csv()
        if not ok:
            QMessageBox.warning(self, "Import failed", msg)
            return
        QMessageBox.information(
            self,
            "Classrooms imported",
            "rooms.dat was rebuilt from rooms.csv.",
        )

    def _open_add_classroom_dash(self):
        if not self._backend_ok():
            QMessageBox.critical(
                self,
                "Backend",
                "Could not load libbackend. Run `make` in the project folder.",
            )
            return
        dlg = AddClassroomDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            QMessageBox.information(
                self,
                "Classroom added",
                "Room appended to rooms.dat. Re-importing rooms.csv replaces the full room list.",
            )

    def apply_role(self):
        admin = APP_STATE.get("is_admin", False)
        self.admin_strip.setVisible(admin)
        self.ui.card_attendance.setVisible(not admin)

    def update_name(self, name):
        safe = html.escape(name or "")
        welcome_html = f"""
                <div style="font-family: 'Cedarville Cursive';">
                <span style='color: #FFFFFF; font-size: 80px; font-weight: bold;'>Welcome </span>
                <span style='color: #FFFFFF; font-size: 80px; font-weight: bold;'>{safe}!</span>
            </div>
        """
        self.ui.label_welcome.setText(welcome_html)

    def timetable_viewer(self):
        self.stack.setCurrentIndex(2)

    def student_viewer(self):
        self.stack.setCurrentIndex(3)

    def attendance_viewer(self):
        self.stack.setCurrentIndex(4)

    def signout(self):
        APP_STATE["faculty_id"] = None
        APP_STATE["is_admin"] = False
        APP_STATE["display_name"] = ""
        login = getattr(self.stack, "login_page", None) or self.stack.widget(0)
        login.ui.password_input.clear()
        login.ui.username_input.clear()
        self.stack.setCurrentIndex(0)


class LoginWindow(QMainWindow):
    def __init__(self, stack_controller):
        super().__init__()
        self.setObjectName("AppLoginPage")
        self.stack = stack_controller
        self.ui = Ui_LoginScreen()
        self.ui.setupUi(self)
        self.ui.login_button.clicked.connect(self.authenticate)
        self.ui.show_password_checkbox.toggled.connect(self.toggle_password)
        self._backend_ok = False
        try:
            bb.ensure_demo_data_files()
            bb.load_library()
            self._backend_ok = True
        except bb.BackendError:
            self._backend_ok = False

    def authenticate(self):
        username = self.ui.username_input.text().strip()
        password = self.ui.password_input.text()
        if not self._backend_ok:
            try:
                bb.ensure_demo_data_files()
                bb.load_library()
                self._backend_ok = True
            except bb.BackendError:
                QMessageBox.critical(
                    self,
                    "Backend",
                    "Could not load libbackend. Run `make` in the project folder first "
                    "(or place backend.dll here on Windows).",
                )
                return
        bb.set_working_directory()
        if bb.login_admin(username, password):
            APP_STATE["is_admin"] = True
            APP_STATE["faculty_id"] = None
            APP_STATE["display_name"] = username
            welcome = self.stack.widget(1)
            welcome.update_name(APP_STATE["display_name"])
            welcome.apply_role()
            self.stack.setCurrentIndex(1)
            return

        fid = bb.login_faculty(username, password)
        if fid is not None:
            APP_STATE["is_admin"] = False
            APP_STATE["faculty_id"] = fid
            APP_STATE["display_name"] = bb.faculty_display_name(fid) or username
            welcome = self.stack.widget(1)
            welcome.update_name(APP_STATE["display_name"])
            welcome.apply_role()
            self.stack.setCurrentIndex(1)
            return
        LoginFailedPopup(self).exec()

    def toggle_password(self):
        if self.ui.show_password_checkbox.isChecked():
            self.ui.password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.ui.password_input.setEchoMode(QLineEdit.EchoMode.Password)


if __name__ == "__main__":
    bb.set_working_directory()
    bb.ensure_demo_data_files()

    app = QApplication(sys.argv)
    _base = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(_base, "icon.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    _cedarville = os.path.join(
        _base, "Cedarville_Cursive", "Cedarville_Cursive", "CedarvilleCursive-Regular.ttf"
    )
    _inter = os.path.join(_base, "Inter", "Inter-VariableFont_opsz,wght.ttf")
    if os.path.isfile(_cedarville):
        font_id1 = QFontDatabase.addApplicationFont(_cedarville)
        families1 = QFontDatabase.applicationFontFamilies(font_id1)
        if families1:
            print(f"Cedarville font: {families1[0]}")

    if os.path.isfile(_inter):
        font_id = QFontDatabase.addApplicationFont(_inter)
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            print(f"Inter font: {families[0]}")

    app.setStyleSheet(
        """
        QLabel#label_welcome {
            font-family: 'Inter', 'Inter Variable', sans-serif;
            font-size: 42px;
            background: transparent;
            border: none;
        }
        """
        + APP_STYLESHEET
    )

    stack = QStackedWidget()
    stack.setWindowTitle("Faculty Assistant")
    stack.resize(1280, 900)

    welcome_page = WelcomeWindow(stack)
    login_page = LoginWindow(stack)
    timetable_page = TimeTable(stack)
    student_page = Student(stack)
    attendance_page = Attendance(stack)

    stack.addWidget(login_page)
    stack.addWidget(welcome_page)
    stack.addWidget(timetable_page)
    stack.addWidget(student_page)
    stack.addWidget(attendance_page)
    stack.login_page = login_page

    for i in range(stack.count()):
        _clamp_widget_fonts(stack.widget(i))

    stack.show()
    sys.exit(app.exec())
