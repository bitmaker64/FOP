#!/usr/bin/env python3
"""
Generate faculty.csv, rooms.csv, requirements.csv:
  - 20 divisions (division_id 1..20)
  - 48 faculty, 32 rooms (max for native solver)
  - 4 engineering courses per division (3 theory + 1 two-period lab) = 80 weekly units
    (tuned so generateTimetable() completes; denser schedules often fail or take very long)

Run: python3 scripts/gen_rich_sample_csvs.py
"""
from __future__ import annotations

import csv
import os
import sys

DIVISIONS = 20
N_FACULTY = 48
MAX_HOURS = 26
N_ROOMS = 32

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 4 rows/div × 20 = 80 units — feasible for the C backtracking solver
# No commas in subject strings — native importRequirementCSV() splits on commas only.
ROWS = [
    ("Engineering Mathematics – III & Transform Methods", 1, 1, 0, 0),
    ("Data Structures / Algorithms / Competitive Programming", 1, 1, 0, 0),
    ("Operating Systems · LINUX Internals & Virtualization", 1, 1, 0, 0),
    ("Networks · Embedded & Hardware Laboratory", 1, 2, 1, 1),
]


def hours_for(sessions: int, dur: int) -> int:
    return sessions * dur


def main() -> None:
    load: dict[int, int] = {i: 0 for i in range(1, N_FACULTY + 1)}

    def assign_faculty(need_h: int) -> int:
        candidates = [
            fid
            for fid in range(1, N_FACULTY + 1)
            if load[fid] + need_h <= MAX_HOURS
        ]
        if not candidates:
            raise SystemExit(
                f"No faculty can take {need_h} h/week; raise N_FACULTY or MAX_HOURS"
            )
        fid = min(candidates, key=lambda f: (load[f], f))
        load[fid] += need_h
        return fid

    req_rows: list[list] = []
    for div in range(1, DIVISIONS + 1):
        for subj, sess, dur, batch, rlab in ROWS:
            h = hours_for(sess, dur)
            fid = assign_faculty(h)
            req_rows.append([div, subj, fid, sess, dur, batch, rlab])

    surnames = (
        "Menon,Kulkarni,Deshpande,Iyer,Nair,Joshi,Patil,Rao,Shah,Mehta,"
        "Choudhury,Banerjee,Reddy,Singh,Kapoor,Verma,Saxena,Pillai,Bose,Ghosh,"
        "Krishnan,Narayan,Bhatia,Malhotra,Chatterjee,Sen,Das,Agarwal,Khanna,Tiwari,"
        "Mishra,Pandey,Yadav,Kaur,Gill,Anand,Varma,Shetty,Hegde,Prasad"
    ).split(",")

    fac_path = os.path.join(ROOT, "faculty.csv")
    with open(fac_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "username", "password", "max_hours"])
        w.writerow(
            [1, "Dr. Sample Faculty (Programme Coordinator)", "sample", "sample123", 28]
        )
        for i in range(2, N_FACULTY + 1):
            sn = surnames[(i - 2) % len(surnames)]
            w.writerow(
                [
                    i,
                    f"Prof. {['A','S','R','K','M','P','V','N'][i % 8]}. {sn}",
                    f"faculty{i:02d}",
                    f"Pass{i:02d}!eng",
                    MAX_HOURS,
                ]
            )

    theory = [
        "North Wing · 101",
        "North Wing · 102",
        "North Wing · 201",
        "East Block · A301",
        "East Block · A302",
        "Central Hall · C105",
        "Central Hall · C106",
        "Innovation Hub · 01",
        "Innovation Hub · 02",
        "Seminar Hall · I",
        "Seminar Hall · II",
        "Annexe · R101",
        "Annexe · R102",
        "Tower · T3-01",
        "Tower · T3-02",
        "Tower · T4-01",
        "Library Studio · LS1",
        "Library Studio · LS2",
        "Learning Commons · LC1",
        "Learning Commons · LC2",
    ]
    labs = [
        "Computing Lab – Alpha",
        "Computing Lab – Beta",
        "Networks & Security Lab",
        "Microprocessor & IoT Lab",
        "Database & OS Lab",
        "Embedded & Robotics Lab",
        "Physics & Chemistry Lab",
        "Electronics Workshop",
        "CAD & Simulation Lab",
        "Project & Design Studio",
        "Open Lab – Ground",
        "Open Lab – First",
    ]
    room_path = os.path.join(ROOT, "rooms.csv")
    with open(room_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "is_lab"])
        rid = 1
        for name in theory:
            if rid > N_ROOMS:
                break
            w.writerow([rid, name, 0])
            rid += 1
        for name in labs:
            if rid > N_ROOMS:
                break
            w.writerow([rid, name, 1])
            rid += 1
        while rid <= N_ROOMS:
            w.writerow([rid, f"General Classroom · {rid:02d}", 0])
            rid += 1

    req_path = os.path.join(ROOT, "requirements.csv")
    with open(req_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "division_id",
                "subject",
                "faculty_id",
                "sessions_per_week",
                "duration_slots",
                "batch_id",
                "requires_lab",
            ]
        )
        for row in req_rows:
            w.writerow(row)

    mx = max(load.values())
    print(f"Wrote {fac_path}, {room_path}, {req_path}", file=sys.stderr)
    print(
        f"Divisions: {DIVISIONS}; requirement rows: {len(req_rows)}; "
        f"max faculty load: {mx} h/week",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
