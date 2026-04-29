"""
Load native backend (libbackend) and expose timetable/auth helpers.
Data files (faculty.dat, requirements.dat, rooms.dat, timetable.dat) live in APP_ROOT.
"""
from __future__ import annotations

import ctypes
import os
import struct
import sys
from ctypes import POINTER, byref, c_char_p, c_int, c_void_p

APP_ROOT = os.path.dirname(os.path.abspath(__file__))


def set_working_directory() -> None:
    os.chdir(APP_ROOT)


def _library_candidates():
    base = APP_ROOT
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    names = []
    if sys.platform == "darwin":
        names.append(os.path.join(base, "libbackend.dylib"))
    elif sys.platform == "win32":
        names.append(os.path.join(base, "backend.dll"))
        names.append(os.path.join(base, "libbackend.dll"))
    else:
        names.append(os.path.join(base, "libbackend.so"))
    names.append(os.path.join(APP_ROOT, "libbackend.dylib"))
    names.append(os.path.join(APP_ROOT, "libbackend.so"))
    names.append(os.path.join(APP_ROOT, "backend.dll"))
    return names


class BackendError(Exception):
    pass


_lib: ctypes.CDLL | None = None


def load_library() -> ctypes.CDLL:
    global _lib
    if _lib is not None:
        return _lib
    set_working_directory()
    last_err = None
    for path in _library_candidates():
        if not os.path.isfile(path):
            continue
        try:
            _lib = ctypes.CDLL(path)
            break
        except OSError as e:
            last_err = e
    if _lib is None:
        raise BackendError(
            "Native backend not found. Build with: make (macOS/Linux) "
            "or compile backend.c to backend.dll on Windows. "
            f"Last error: {last_err!r}"
        )
    _lib.loginAdmin.argtypes = [c_char_p, c_char_p]
    _lib.loginAdmin.restype = c_int
    _lib.loginFaculty.argtypes = [c_char_p, c_char_p, POINTER(c_int)]
    _lib.loginFaculty.restype = c_int
    _lib.generateTimetable.argtypes = []
    _lib.generateTimetable.restype = c_int
    _lib.getFacultySchedule.argtypes = [c_int, POINTER(c_void_p), POINTER(c_int)]
    _lib.getFacultySchedule.restype = c_int
    _lib.freeSchedule.argtypes = [c_void_p]
    _lib.freeSchedule.restype = None
    _lib.getFacultyName.argtypes = [c_int, c_char_p]
    _lib.getFacultyName.restype = c_int
    _lib.importFacultyCSV.argtypes = []
    _lib.importFacultyCSV.restype = c_int
    _lib.importRequirementCSV.argtypes = []
    _lib.importRequirementCSV.restype = c_int
    _lib.importRoomsCSV.argtypes = []
    _lib.importRoomsCSV.restype = c_int
    _lib.addFaculty.argtypes = [c_int, c_char_p, c_char_p, c_char_p, c_int]
    _lib.addFaculty.restype = c_int
    _lib.reportAbsence.argtypes = [c_int, c_int, c_int, POINTER(c_int)]
    _lib.reportAbsence.restype = c_int
    _lib.addRoom.argtypes = [c_int, c_char_p, c_int]
    _lib.addRoom.restype = c_int
    return _lib


# --- Binary layout (matches GCC/clang on macOS / typical 64-bit LP64) ---
LECTURE_BIN = struct.Struct("@i 50s 10s 5i")  # 84 bytes
FACULTY_BIN = struct.Struct("@i 50s 30s 30s i i")  # 124 bytes (matches struct Faculty)
ROOM_BIN = struct.Struct("@i 32s i")  # 40 bytes


def _dec_str(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()


def read_all_lectures() -> list[dict]:
    """Read timetable.dat without ctypes (portable if layout matches)."""
    path = os.path.join(APP_ROOT, "timetable.dat")
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, "rb") as f:
        data = f.read()
    step = LECTURE_BIN.size
    for off in range(0, len(data), step):
        chunk = data[off : off + step]
        if len(chunk) < step:
            break
        fid, subj, div, day, slot, dur, rid, batch = LECTURE_BIN.unpack(chunk)
        out.append(
            {
                "faculty_id": fid,
                "subject": _dec_str(subj),
                "division": _dec_str(div),
                "day": day,
                "slot": slot,
                "duration": dur if dur >= 1 else 1,
                "room_id": rid,
                "batch_id": batch,
            }
        )
    return out


def read_all_faculty_records() -> list[dict]:
    """Read faculty.dat (ids and metadata; passwords omitted; first row wins if duplicate ids)."""
    path = os.path.join(APP_ROOT, "faculty.dat")
    if not os.path.isfile(path):
        return []
    out: list[dict] = []
    seen: set[int] = set()
    with open(path, "rb") as f:
        data = f.read()
    step = FACULTY_BIN.size
    for off in range(0, len(data), step):
        chunk = data[off : off + step]
        if len(chunk) < step:
            break
        fid, name, user, _pw, mx, cur = FACULTY_BIN.unpack(chunk)
        if fid in seen:
            continue
        seen.add(fid)
        out.append(
            {
                "id": fid,
                "name": _dec_str(name),
                "username": _dec_str(user),
                "max_hours_per_week": mx,
                "current_hours": cur,
            }
        )
    return out


def read_all_room_records() -> list[dict]:
    """Read rooms.dat: id, location name, is_lab flag (first row wins if duplicate ids)."""
    path = os.path.join(APP_ROOT, "rooms.dat")
    if not os.path.isfile(path):
        return []
    out: list[dict] = []
    seen: set[int] = set()
    with open(path, "rb") as f:
        data = f.read()
    step = ROOM_BIN.size
    for off in range(0, len(data), step):
        chunk = data[off : off + step]
        if len(chunk) < step:
            break
        rid, name, is_lab = ROOM_BIN.unpack(chunk)
        if rid in seen:
            continue
        seen.add(rid)
        out.append(
            {
                "id": rid,
                "name": _dec_str(name),
                "is_lab": bool(is_lab),
            }
        )
    return out


def read_room_map() -> dict[int, str]:
    return {r["id"]: r["name"] for r in read_all_room_records()}


def login_admin(username: str, password: str) -> bool:
    lib = load_library()
    return bool(
        lib.loginAdmin(username.encode("utf-8"), password.encode("utf-8"))
    )


def login_faculty(username: str, password: str) -> int | None:
    lib = load_library()
    out = c_int(-1)
    ok = lib.loginFaculty(
        username.encode("utf-8"), password.encode("utf-8"), byref(out)
    )
    if ok:
        return int(out.value)
    return None


def import_all_csvs() -> tuple[bool, str]:
    """Rebuild faculty.dat, rooms.dat, and requirements.dat from CSV files."""
    lib = load_library()
    if not lib.importFacultyCSV():
        return False, "faculty.csv import failed (missing file or invalid rows)."
    if not lib.importRoomsCSV():
        return False, "rooms.csv import failed."
    if not lib.importRequirementCSV():
        return False, "requirements.csv import failed."
    return True, ""


def import_rooms_csv() -> tuple[bool, str]:
    """Rebuild rooms.dat from rooms.csv (classroom / lab locations)."""
    lib = load_library()
    if not lib.importRoomsCSV():
        return False, "rooms.csv import failed (missing file or invalid rows)."
    return True, ""


def add_room_record(room_id: int, location_name: str, is_lab: bool) -> bool:
    """Append one room to rooms.dat (use a new unique id)."""
    lib = load_library()
    return bool(
        lib.addRoom(
            int(room_id),
            location_name.encode("utf-8"),
            1 if is_lab else 0,
        )
    )


def add_faculty_record(
    faculty_id: int,
    name: str,
    username: str,
    password: str,
    max_hours_per_week: int,
) -> bool:
    """Append one faculty record to faculty.dat (use a new unique id)."""
    lib = load_library()
    return bool(
        lib.addFaculty(
            int(faculty_id),
            name.encode("utf-8"),
            username.encode("utf-8"),
            password.encode("utf-8"),
            int(max_hours_per_week),
        )
    )


def report_absence(faculty_id: int, day: int, slot: int) -> int | None:
    """
    Replace the faculty on their class at (day, slot) with a substitute.
    day: 1=Monday .. 5=Friday; slot: 1..8. Returns substitute faculty id or None.
    """
    lib = load_library()
    sub = c_int(-1)
    if not lib.reportAbsence(int(faculty_id), int(day), int(slot), byref(sub)):
        return None
    sid = int(sub.value)
    return sid if sid >= 0 else None


def faculty_display_name(faculty_id: int) -> str:
    try:
        lib = load_library()
    except BackendError:
        return ""
    buf = ctypes.create_string_buffer(128)
    if lib.getFacultyName(int(faculty_id), buf):
        return buf.value.decode("utf-8", errors="replace").strip()
    return ""


def generate_timetable_native() -> bool:
    lib = load_library()
    return bool(lib.generateTimetable())


def get_faculty_schedule_lectures(faculty_id: int) -> list[dict]:
    """Uses native allocator + freeSchedule."""
    lib = load_library()
    ptr = c_void_p()
    cnt = c_int(0)
    if not lib.getFacultySchedule(int(faculty_id), byref(ptr), byref(cnt)):
        return []
    n = int(cnt.value)
    addr = ptr.value
    if n <= 0 or not addr:
        return []
    nbytes = n * LECTURE_BIN.size
    raw = ctypes.string_at(addr, nbytes)
    lib.freeSchedule(c_void_p(addr))
    if len(raw) != nbytes:
        return []
    out = []
    step = LECTURE_BIN.size
    for off in range(0, len(raw), step):
        fid, subj, div, day, slot, dur, rid, batch = LECTURE_BIN.unpack(
            raw[off : off + step]
        )
        out.append(
            {
                "faculty_id": fid,
                "subject": _dec_str(subj),
                "division": _dec_str(div),
                "day": day,
                "slot": slot,
                "duration": dur if dur >= 1 else 1,
                "room_id": rid,
                "batch_id": batch,
            }
        )
    return out


def ensure_demo_data_files() -> None:
    """Create sample CSV + .dat if missing so first run works after import."""
    set_working_directory()
    fac_csv = os.path.join(APP_ROOT, "faculty.csv")
    req_csv = os.path.join(APP_ROOT, "requirements.csv")
    room_csv = os.path.join(APP_ROOT, "rooms.csv")
    if not os.path.isfile(fac_csv):
        with open(fac_csv, "w", encoding="utf-8") as f:
            f.write("id,name,username,password,max_hours\n")
            f.write("1,Dr. Sample Faculty,sample,sample123,24\n")
            f.write("2,Dr. Lab Faculty,lab,lab123,24\n")
    if not os.path.isfile(room_csv):
        with open(room_csv, "w", encoding="utf-8") as f:
            f.write("id,name,is_lab\n")
            for i, (n, lab) in enumerate(
                [
                    ("AB 104", 0),
                    ("AB 003", 0),
                    ("AB 303", 0),
                    ("AB 708", 0),
                    ("AB 105", 0),
                    ("LAB A", 1),
                    ("LAB B", 1),
                ],
                start=1,
            ):
                f.write(f"{i},{n},{lab}\n")
    if not os.path.isfile(req_csv):
        with open(req_csv, "w", encoding="utf-8") as f:
            f.write(
                "division_id,subject,faculty_id,sessions_per_week,duration_slots,batch_id,requires_lab\n"
            )
            f.write("2,PEACE,1,1,1,0,0\n")
            f.write("2,DMGT,1,3,1,0,0\n")
            f.write("2,FOP Theory,1,2,1,0,0\n")
            f.write("2,FOP Lab,2,2,2,1,1\n")
            f.write("2,EGR Lab,2,1,2,2,1\n")
            f.write("2,ESD,1,2,1,0,0\n")
    try:
        lib = load_library()
        if not os.path.isfile(os.path.join(APP_ROOT, "faculty.dat")):
            lib.importFacultyCSV()
        if not os.path.isfile(os.path.join(APP_ROOT, "rooms.dat")):
            lib.importRoomsCSV()
        if not os.path.isfile(os.path.join(APP_ROOT, "requirements.dat")):
            lib.importRequirementCSV()
    except BackendError:
        pass
