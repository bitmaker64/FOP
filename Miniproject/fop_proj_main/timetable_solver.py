"""
University / school timetable generation using constraint satisfaction with
backtracking, MRV (minimum remaining values), LCV (least constraining value),
and forward checking. Suitable for modest instance sizes (typical departments).

Hard constraints enforced:
  - Teacher, section (class group), and room are never double-booked
  - Multi-period blocks stay on one day and do not cross lunch or end-of-day
  - Lab sessions use rooms marked as lab; lectures avoid labs when non-lab exists
  - Optional per-teacher caps: max periods per day, max consecutive teaching stretch
  - Optional teacher unavailable slots

The solver is deterministic given a fixed random seed for tie-breaking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Optional


@dataclass(frozen=True)
class Room:
    room_id: str
    capacity: int
    is_lab: bool = False


@dataclass
class Teacher:
    teacher_id: int
    name: str = ""
    max_periods_per_day: int = 8
    """Maximum teaching periods on any single day (lunch does not count)."""
    max_consecutive_periods: int = 5
    """Longest allowed contiguous block of teaching on a day."""
    unavailable: frozenset[tuple[int, int]] = field(default_factory=frozenset)
    """Frozen set of (day_index, period_index) where this teacher cannot teach."""


@dataclass
class Section:
    section_id: str
    label: str = ""
    size: int = 40


@dataclass
class CourseRequirement:
    subject: str
    teacher_id: int
    section_id: str
    periods_per_week: int
    slot_duration: int = 1
    """Consecutive periods per meeting (2 = double lab / extended lecture)."""
    needs_lab: bool = False


@dataclass
class ScheduleProblem:
    day_names: tuple[str, ...]
    periods_per_day: int
    lunch_periods: frozenset[int]
    """Period indices (0-based) that are blocked globally (e.g. lunch)."""
    rooms: list[Room]
    sections: list[Section]
    teachers: list[Teacher]
    requirements: list[CourseRequirement]

    def teacher_map(self) -> dict[int, Teacher]:
        return {t.teacher_id: t for t in self.teachers}


@dataclass(frozen=True)
class LessonUnit:
    uid: int
    subject: str
    teacher_id: int
    section_id: str
    duration: int
    needs_lab: bool


@dataclass(frozen=True)
class ScheduledEntry:
    day: int
    period_start: int
    duration: int
    room_id: str
    subject: str
    teacher_id: int
    section_id: str


@dataclass
class TimetableResult:
    entries: list[ScheduledEntry]
    problem: ScheduleProblem


def expand_requirements(requirements: list[CourseRequirement]) -> list[LessonUnit]:
    """Turn weekly requirements into atomic lesson units (each placement is one unit)."""
    units: list[LessonUnit] = []
    uid = 0
    for req in requirements:
        if req.periods_per_week <= 0 or req.slot_duration <= 0:
            continue
        for _ in range(req.periods_per_week):
            uid += 1
            units.append(
                LessonUnit(
                    uid=uid,
                    subject=req.subject,
                    teacher_id=req.teacher_id,
                    section_id=req.section_id,
                    duration=req.slot_duration,
                    needs_lab=req.needs_lab,
                )
            )
    return units


class _Occupancy:
    __slots__ = ("problem", "teacher_day_period", "section_day_period", "room_day_period")

    def __init__(self, problem: ScheduleProblem):
        self.problem = problem
        self.teacher_day_period: set[tuple[int, int, int]] = set()
        self.section_day_period: set[tuple[str, int, int]] = set()
        self.room_day_period: set[tuple[str, int, int]] = set()

    def _periods_for_block(self, day: int, start_p: int, duration: int) -> list[tuple[int, int]]:
        return [(day, start_p + k) for k in range(duration)]

    def can_place(
        self,
        unit: LessonUnit,
        day: int,
        start_p: int,
        room: Room,
        tmap: dict[int, Teacher],
    ) -> bool:
        p = self.problem
        if start_p < 0 or start_p + unit.duration > p.periods_per_day:
            return False
        slots = self._periods_for_block(day, start_p, unit.duration)
        for _, period in slots:
            if period in p.lunch_periods:
                return False

        teacher = tmap.get(unit.teacher_id)
        if teacher:
            for _, period in slots:
                if (day, period) in teacher.unavailable:
                    return False

        for d, period in slots:
            if (unit.teacher_id, d, period) in self.teacher_day_period:
                return False
            if (unit.section_id, d, period) in self.section_day_period:
                return False
            if (room.room_id, d, period) in self.room_day_period:
                return False

        if unit.needs_lab and not room.is_lab:
            return False
        if not unit.needs_lab and room.is_lab:
            # Prefer non-lab for lectures when possible; still allow if only labs exist
            if any(not r.is_lab for r in p.rooms):
                return False

        sec = next((s for s in p.sections if s.section_id == unit.section_id), None)
        if sec and room.capacity < sec.size:
            return False

        if teacher:
            periods_today = {pr for (tid, dy, pr) in self.teacher_day_period if tid == unit.teacher_id and dy == day}
            for _, pr in slots:
                periods_today.add(pr)
            if len(periods_today) > teacher.max_periods_per_day:
                return False
            if _longest_consecutive(sorted(periods_today)) > teacher.max_consecutive_periods:
                return False

        return True

    def place(self, unit: LessonUnit, day: int, start_p: int, room: Room) -> None:
        for d, period in self._periods_for_block(day, start_p, unit.duration):
            self.teacher_day_period.add((unit.teacher_id, d, period))
            self.section_day_period.add((unit.section_id, d, period))
            self.room_day_period.add((room.room_id, d, period))

    def unplace(self, unit: LessonUnit, day: int, start_p: int, room: Room) -> None:
        for d, period in self._periods_for_block(day, start_p, unit.duration):
            self.teacher_day_period.discard((unit.teacher_id, d, period))
            self.section_day_period.discard((unit.section_id, d, period))
            self.room_day_period.discard((room.room_id, d, period))


def _longest_consecutive(periods_sorted: list[int]) -> int:
    if not periods_sorted:
        return 0
    best = cur = 1
    for i in range(1, len(periods_sorted)):
        if periods_sorted[i] == periods_sorted[i - 1] + 1:
            cur += 1
            best = max(best, cur)
        elif periods_sorted[i] != periods_sorted[i - 1]:
            cur = 1
    return best


def _compatible_rooms(unit: LessonUnit, problem: ScheduleProblem) -> list[Room]:
    if unit.needs_lab:
        return [r for r in problem.rooms if r.is_lab]
    non_lab = [r for r in problem.rooms if not r.is_lab]
    return non_lab if non_lab else list(problem.rooms)


def _enumerate_placements(
    unit: LessonUnit, occ: _Occupancy, tmap: dict[int, Teacher]
) -> list[tuple[int, int, Room]]:
    p = occ.problem
    out: list[tuple[int, int, Room]] = []
    rooms = _compatible_rooms(unit, p)
    for day in range(len(p.day_names)):
        for start_p in range(p.periods_per_day):
            if start_p + unit.duration > p.periods_per_day:
                break
            for room in rooms:
                if occ.can_place(unit, day, start_p, room, tmap):
                    out.append((day, start_p, room))
    return out


def _directly_conflicting_units(unit: LessonUnit, others: list[LessonUnit]) -> list[LessonUnit]:
    """Units that compete for the same teacher or section (main propagation for LCV)."""
    return [o for o in others if o.teacher_id == unit.teacher_id or o.section_id == unit.section_id]


def _lcv_sort_key(
    candidate: tuple[int, int, Room],
    unit: LessonUnit,
    occ: _Occupancy,
    others: list[LessonUnit],
    tmap: dict[int, Teacher],
) -> tuple[int, int, str]:
    """
    Least constraining value (approximation): among directly conflicting unassigned
    lessons, prefer placements that shrink their domains the least.
    """
    day, start_p, room = candidate
    occ.place(unit, day, start_p, room)
    blocked = 0
    for o in others:
        dom = _enumerate_placements(o, occ, tmap)
        blocked += max(0, len(dom) - 1)
    occ.unplace(unit, day, start_p, room)
    return (blocked, day * 100 + start_p, room.room_id)


def generate_timetable(
    problem: ScheduleProblem,
    *,
    random_seed: int = 42,
) -> Optional[TimetableResult]:
    """
    Build a complete weekly timetable or return None if over-constrained.

    Uses recursive backtracking with MRV variable ordering and LCV value ordering.
    """
    units = expand_requirements(problem.requirements)
    if not units:
        return TimetableResult(entries=[], problem=problem)

    tmap = problem.teacher_map()
    occ = _Occupancy(problem)
    rng = random.Random(random_seed)

    # Initial MRV order: tightest units first (seeded jitter breaks symmetric ties)
    def domain_size(u: LessonUnit) -> int:
        return len(_enumerate_placements(u, occ, tmap))

    sizes = [(domain_size(u), rng.random(), u) for u in units]
    sizes.sort(key=lambda x: (x[0], x[1]))
    initial_order = [u for _, _, u in sizes]

    entries: list[ScheduledEntry] = []

    def backtrack(pool: list[LessonUnit]) -> bool:
        if not pool:
            return True
        # Dynamic MRV among remaining
        best_u: Optional[LessonUnit] = None
        best_dom: Optional[list[tuple[int, int, Room]]] = None
        best_len = 10**9
        for u in pool:
            dom = _enumerate_placements(u, occ, tmap)
            if not dom:
                return False
            if len(dom) < best_len:
                best_len = len(dom)
                best_u = u
                best_dom = dom
        assert best_u is not None and best_dom is not None
        others = [x for x in pool if x is not best_u]
        lcv_scope = _directly_conflicting_units(best_u, others)
        dom_sorted = sorted(
            best_dom,
            key=lambda c: (_lcv_sort_key(c, best_u, occ, lcv_scope, tmap), c[2].room_id),
        )

        for day, start_p, room in dom_sorted:
            if not occ.can_place(best_u, day, start_p, room, tmap):
                continue
            occ.place(best_u, day, start_p, room)
            entries.append(
                ScheduledEntry(
                    day=day,
                    period_start=start_p,
                    duration=best_u.duration,
                    room_id=room.room_id,
                    subject=best_u.subject,
                    teacher_id=best_u.teacher_id,
                    section_id=best_u.section_id,
                )
            )
            rest = [x for x in pool if x is not best_u]
            if backtrack(rest):
                return True
            entries.pop()
            occ.unplace(best_u, day, start_p, room)
        return False

    if not backtrack(initial_order):
        return None

    entries.sort(key=lambda e: (e.section_id, e.day, e.period_start))
    return TimetableResult(entries=entries, problem=problem)


def default_demo_problem() -> ScheduleProblem:
    """
    Example campus model aligned loosely with five faculty groups (teacher ids 1–5).
    Adjust rooms, lunch, and requirements to match your institution.
    """
    days = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
    lunch = frozenset({3})  # period index 3 = 4th slot (typical lunch band)

    rooms = [
        Room("A-101", 50, False),
        Room("A-102", 50, False),
        Room("A-103", 50, False),
        Room("B-201", 45, False),
        Room("B-202", 45, False),
        Room("LAB-1", 45, True),
        Room("LAB-2", 45, True),
    ]

    sections = [
        Section("G1", "Group 1 (Advisor 1)", 40),
        Section("G2", "Group 2 (Advisor 2)", 40),
        Section("G3", "Group 3 (Advisor 3)", 38),
        Section("G4", "Group 4 (Advisor 4)", 36),
        Section("G5", "Group 5 (Advisor 5)", 35),
    ]

    teachers = [
        Teacher(1, "Faculty 1", max_periods_per_day=8, max_consecutive_periods=5),
        Teacher(2, "Faculty 2", max_periods_per_day=8, max_consecutive_periods=5),
        Teacher(3, "Faculty 3", max_periods_per_day=8, max_consecutive_periods=5),
        Teacher(4, "Faculty 4", max_periods_per_day=8, max_consecutive_periods=5),
        Teacher(5, "Faculty 5", max_periods_per_day=8, max_consecutive_periods=5),
    ]

    requirements: list[CourseRequirement] = [
        CourseRequirement("Data Structures", 1, "G1", 3, 1, False),
        CourseRequirement("Operating Systems", 1, "G1", 2, 2, True),
        CourseRequirement("Discrete Math", 2, "G2", 4, 1, False),
        CourseRequirement("DBMS Lab", 2, "G2", 1, 2, True),
        CourseRequirement("Computer Networks", 3, "G3", 3, 1, False),
        CourseRequirement("CN Lab", 3, "G3", 1, 2, True),
        CourseRequirement("Software Eng.", 4, "G4", 3, 1, False),
        CourseRequirement("Mini Project", 4, "G4", 2, 2, True),
        CourseRequirement("Theory of Comp.", 5, "G5", 3, 1, False),
        CourseRequirement("Compiler Lab", 5, "G5", 2, 2, True),
    ]

    return ScheduleProblem(
        day_names=days,
        periods_per_day=8,
        lunch_periods=lunch,
        rooms=rooms,
        sections=sections,
        teachers=teachers,
        requirements=requirements,
    )


def format_grid(
    result: TimetableResult,
    *,
    section_id: Optional[str] = None,
) -> tuple[list[str], list[list[str]]]:
    """
    Build row labels (time slots) and column labels (days) with cell text for a section.
    If section_id is None, uses the first section in the problem.
    """
    p = result.problem
    sid = section_id or (p.sections[0].section_id if p.sections else "")
    rows = p.periods_per_day
    cols = len(p.day_names)
    grid: list[list[str]] = [["" for _ in range(cols)] for _ in range(rows)]

    for e in result.entries:
        if e.section_id != sid:
            continue
        for k in range(e.duration):
            pr = e.period_start + k
            if 0 <= pr < rows and 0 <= e.day < cols:
                cell = f"{e.subject}\n{e.room_id}"
                if grid[pr][e.day]:
                    grid[pr][e.day] += " | " + cell.split("\n")[0]
                else:
                    grid[pr][e.day] = cell

    headers = list(p.day_names)
    row_labels = []
    for i in range(rows):
        label = f"P{i + 1}"
        if i in p.lunch_periods:
            label += " (break)"
        row_labels.append(label)
    return row_labels, grid
