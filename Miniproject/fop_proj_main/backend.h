#ifndef BACKEND_H
#define BACKEND_H

/**
 * Weekly grid: Monday..Friday (change MAX_DAYS to 6 for Saturday).
 * Eight 1-hour teaching slots per day, matching typical university grids where
 * recess falls *between* slots (after 2, 4, 6) — labs must not span a break.
 */
#define MAX_DAYS 5
#define MAX_SLOTS 8
/** Supported division_id range in requirements (1..MAX_DIVISIONS). */
#define MAX_DIVISIONS 24

/** Max parallel rooms the solver will track (see rooms.dat or built-in defaults). */
#define MAX_ROOMS 32

struct Faculty {
    int id;
    char name[50];
    char username[30];
    char password[30];
    int max_hours_per_week;
    int current_hours;
};

/**
 * required_hours = weekly sessions (each session lasts duration_slots).
 * duration_slots: 1 = single theory/tutorial period; 2 = contiguous lab (two periods
 *   in the same pair: 1-2, 3-4, 5-6, or 7-8 — cannot cross recess).
 * batch_id: 0 = entire division in that session; >0 = lab batch (parallel groups).
 * requires_lab_room: 1 = must be placed in a room marked as lab.
 */
struct SubjectRequirement {
    int division_id;
    char subject[50];
    int faculty_id;
    int required_hours;
    int assigned_hours;
    int duration_slots;
    int batch_id;
    int requires_lab_room;
};

/**
 * slot = first period of the meeting; duration 2 occupies slot and slot+1.
 * room_id matches RoomRec.id from rooms.dat (or defaults).
 */
struct Lecture {
    int faculty_id;
    char subject[50];
    char division[10];
    int day;
    int slot;
    int duration;
    int room_id;
    int batch_id;
};

struct RoomRec {
    int id;
    char name[32];
    int is_lab;
};

int loginAdmin(const char* username, const char* password);
int loginFaculty(const char* username, const char* password, int* outFacultyID);

int addFaculty(int id, const char* name,
               const char* username,
               const char* password,
               int max_hours);

int addRequirement(int division_id,
                   const char* subject,
                   int faculty_id,
                   int required_hours);

int addRequirementAdvanced(int division_id,
                           const char* subject,
                           int faculty_id,
                           int sessions_per_week,
                           int duration_slots,
                           int batch_id,
                           int requires_lab_room);

/** Builds timetable.dat; returns 1 if all requirements placed, 0 if infeasible or I/O error. */
int generateTimetable(void);

int getFacultySchedule(int faculty_id,
                       struct Lecture** outLectures,
                       int* count);
/**
 * Assign a substitute using requirements.dat: prefers faculty who teach the same
 * course (lab-qualified rows for 2-period sessions), then lowest weekly load.
 * If none qualify, falls back to any free faculty within hour caps.
 */
int reportAbsence(int faculty_id, int day, int slot, int* substitute_id);

int importFacultyCSV(void);
int importRequirementCSV(void);
int importRoomsCSV(void);
/** Append one room to rooms.dat (unique id; re-importing rooms.csv replaces the file). */
int addRoom(int id, const char *name, int is_lab);
int getFacultyName(int faculty_id, char* name_buffer);
void freeSchedule(struct Lecture* ptr);

#endif
