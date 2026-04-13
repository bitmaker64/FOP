#include "backend.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_FACULTY 100

static void faculty_sanitize_strings(struct Faculty *f) {
    if (!f)
        return;
    f->name[sizeof(f->name) - 1] = '\0';
    f->username[sizeof(f->username) - 1] = '\0';
    f->password[sizeof(f->password) - 1] = '\0';
}

/* ================= LOGIN ================= */

int loginAdmin(const char* username, const char* password) {
    return (strcmp(username, "admin") == 0 &&
            strcmp(password, "admin123") == 0);
}

int loginFaculty(const char* username, const char* password, int* outFacultyID) {
    FILE *fp = fopen("faculty.dat", "rb");
    if (!fp) return 0;

    struct Faculty f;
    while (fread(&f, sizeof(f), 1, fp) == 1) {
        faculty_sanitize_strings(&f);
        if (strcmp(f.username, username) == 0 &&
            strcmp(f.password, password) == 0) {
            *outFacultyID = f.id;
            fclose(fp);
            return 1;
        }
    }

    fclose(fp);
    return 0;
}

/* ================= FACULTY ================= */

int addFaculty(int id, const char* name,
               const char* username,
               const char* password,
               int max_hours) {

    FILE *fp = fopen("faculty.dat", "ab");
    if (!fp) return 0;

    struct Faculty f;
    memset(&f, 0, sizeof(f));
    f.id = id;
    strncpy(f.name, name, sizeof(f.name) - 1);
    strncpy(f.username, username, sizeof(f.username) - 1);
    strncpy(f.password, password, sizeof(f.password) - 1);
    f.max_hours_per_week = max_hours;
    f.current_hours = 0;

    fwrite(&f, sizeof(f), 1, fp);
    fclose(fp);
    return 1;
}

/* ================= REQUIREMENTS ================= */

int addRequirementAdvanced(int division_id,
                           const char* subject,
                           int faculty_id,
                           int sessions_per_week,
                           int duration_slots,
                           int batch_id,
                           int requires_lab_room) {
    FILE *fp = fopen("requirements.dat", "ab");
    if (!fp) return 0;

    struct SubjectRequirement r;
    memset(&r, 0, sizeof(r));
    r.division_id = division_id;
    strncpy(r.subject, subject, sizeof(r.subject) - 1);
    r.faculty_id = faculty_id;
    r.required_hours = sessions_per_week;
    r.assigned_hours = 0;
    r.duration_slots = (duration_slots == 2) ? 2 : 1;
    r.batch_id = batch_id < 0 ? 0 : batch_id;
    r.requires_lab_room = requires_lab_room ? 1 : 0;

    fwrite(&r, sizeof(r), 1, fp);
    fclose(fp);
    return 1;
}

int addRequirement(int division_id,
                   const char* subject,
                   int faculty_id,
                   int required_hours) {
    return addRequirementAdvanced(division_id, subject, faculty_id, required_hours,
                                  1, 0, 0);
}

/* ================= RESET LOAD ================= */

static void resetFacultyLoads() {
    FILE *fp = fopen("faculty.dat", "rb+");
    if (!fp) return;

    struct Faculty f;
    while (fread(&f, sizeof(f), 1, fp) == 1) {
        f.current_hours = 0;
        fseek(fp, -(long)sizeof(f), SEEK_CUR);
        fwrite(&f, sizeof(f), 1, fp);
    }

    fclose(fp);
}

/* ================= GENERATE TIMETABLE (recess-aware labs + rooms + batches) ================= */

#define TT_MAX_UNITS 512
#define TT_MAX_REQS 256
#define TT_FAC_MAP 256
#define TT_MAX_CAND 640

typedef struct {
    int division_id;
    int faculty_id;
    int batch_id;
    int duration;
    int use_lab_room;
    char subject[50];
} TTUnit;

static struct SubjectRequirement g_tt_reqs[TT_MAX_REQS];
static int g_tt_n_reqs;
static TTUnit g_tt_units[TT_MAX_UNITS];
static int g_tt_n_units;

static struct RoomRec g_tt_rooms[MAX_ROOMS];
static int g_tt_n_rooms;

static int g_tt_fac_max[TT_FAC_MAP];
static int g_tt_fac_hours[TT_FAC_MAP];

static unsigned char g_tt_assigned[TT_MAX_UNITS];
static unsigned char g_tt_uday[TT_MAX_UNITS];
static unsigned char g_tt_uslot[TT_MAX_UNITS];
static int g_tt_uroom[TT_MAX_UNITS];

static void tt_seed_default_rooms(void) {
    static const struct {
        const char *n;
        int lab;
    } defs[] = {{"AB 104", 0}, {"AB 003", 0}, {"AB 303", 0}, {"AB 708", 0},
                {"AB 105", 0}, {"AB 106", 0}, {"AB 201", 0}, {"AB 202", 0},
                {"LAB A", 1},  {"LAB B", 1},  {"LAB C", 1},  {"LAB D", 1}};
    int n = (int)(sizeof(defs) / sizeof(defs[0]));
    g_tt_n_rooms = n;
    for (int i = 0; i < n; i++) {
        g_tt_rooms[i].id = i + 1;
        strncpy(g_tt_rooms[i].name, defs[i].n, sizeof(g_tt_rooms[i].name) - 1);
        g_tt_rooms[i].name[sizeof(g_tt_rooms[i].name) - 1] = '\0';
        g_tt_rooms[i].is_lab = defs[i].lab;
    }
}

static int tt_load_rooms(void) {
    FILE *fp = fopen("rooms.dat", "rb");
    if (!fp) {
        tt_seed_default_rooms();
        return 1;
    }
    g_tt_n_rooms = 0;
    struct RoomRec r;
    while (g_tt_n_rooms < MAX_ROOMS &&
           fread(&r, sizeof(r), 1, fp) == 1) {
        g_tt_rooms[g_tt_n_rooms++] = r;
    }
    fclose(fp);
    if (g_tt_n_rooms == 0)
        tt_seed_default_rooms();
    return 1;
}

static int tt_load_requirements(void) {
    FILE *fp = fopen("requirements.dat", "rb");
    if (!fp)
        return 0;
    g_tt_n_reqs = 0;
    while (g_tt_n_reqs < TT_MAX_REQS &&
           fread(&g_tt_reqs[g_tt_n_reqs], sizeof(struct SubjectRequirement), 1, fp) == 1) {
        struct SubjectRequirement *q = &g_tt_reqs[g_tt_n_reqs];
        if (q->duration_slots != 2)
            q->duration_slots = 1;
        if (q->batch_id < 0)
            q->batch_id = 0;
        q->requires_lab_room = q->requires_lab_room ? 1 : 0;
        g_tt_n_reqs++;
    }
    fclose(fp);
    return 1;
}

static void tt_build_units(void) {
    g_tt_n_units = 0;
    for (int i = 0; i < g_tt_n_reqs; i++) {
        struct SubjectRequirement *r = &g_tt_reqs[i];
        if (r->required_hours <= 0)
            continue;
        int dur = (r->duration_slots == 2) ? 2 : 1;
        int use_lab = r->requires_lab_room ? 1 : 0;
        if (dur == 2)
            use_lab = 1;
        for (int h = 0; h < r->required_hours; h++) {
            if (g_tt_n_units >= TT_MAX_UNITS)
                return;
            g_tt_units[g_tt_n_units].division_id = r->division_id;
            g_tt_units[g_tt_n_units].faculty_id = r->faculty_id;
            g_tt_units[g_tt_n_units].batch_id = r->batch_id;
            g_tt_units[g_tt_n_units].duration = dur;
            g_tt_units[g_tt_n_units].use_lab_room = use_lab;
            strncpy(g_tt_units[g_tt_n_units].subject, r->subject,
                    sizeof(g_tt_units[0].subject) - 1);
            g_tt_units[g_tt_n_units].subject[sizeof(g_tt_units[0].subject) - 1] = '\0';
            g_tt_n_units++;
        }
    }
}

static int tt_load_faculty_caps(void) {
    memset(g_tt_fac_max, 0, sizeof(g_tt_fac_max));
    memset(g_tt_fac_hours, 0, sizeof(g_tt_fac_hours));
    FILE *fp = fopen("faculty.dat", "rb");
    if (!fp)
        return 0;
    struct Faculty f;
    while (fread(&f, sizeof(f), 1, fp) == 1) {
        if (f.id >= 0 && f.id < TT_FAC_MAP)
            g_tt_fac_max[f.id] = f.max_hours_per_week;
    }
    fclose(fp);
    return 1;
}

/* Recess after periods 2, 4, 6 — lab (duration 2) may only start at 1,3,5,7. */
static int tt_valid_lab_pair_start(int start_slot) {
    return start_slot == 1 || start_slot == 3 || start_slot == 5 || start_slot == 7;
}

static int tt_valid_start_for_duration(int dur, int start_slot) {
    if (start_slot < 1 || start_slot > MAX_SLOTS)
        return 0;
    if (dur == 1)
        return 1;
    if (dur == 2) {
        if (!tt_valid_lab_pair_start(start_slot))
            return 0;
        return (start_slot + 1 <= MAX_SLOTS);
    }
    return 0;
}

static int tt_ranges_overlap(int d1, int s1, int len1, int d2, int s2, int len2) {
    if (d1 != d2)
        return 0;
    int e1 = s1 + len1 - 1;
    int e2 = s2 + len2 - 1;
    return !(e1 < s2 || e2 < s1);
}

static int tt_student_groups_clash(int div_a, int ba, int div_b, int bb) {
    if (div_a != div_b)
        return 0;
    if (ba == 0 || bb == 0)
        return 1;
    return ba == bb;
}

static int tt_room_matches_unit(const TTUnit *u, int ridx) {
    if (ridx < 0 || ridx >= g_tt_n_rooms)
        return 0;
    if (u->use_lab_room) {
        return g_tt_rooms[ridx].is_lab != 0;
    }
    int has_class = 0;
    for (int i = 0; i < g_tt_n_rooms; i++) {
        if (!g_tt_rooms[i].is_lab) {
            has_class = 1;
            break;
        }
    }
    if (has_class && g_tt_rooms[ridx].is_lab)
        return 0;
    return 1;
}

/** Lab / practical session for per-day cap: 2-slot block or explicit lab-room requirement. */
static int tt_unit_is_division_lab_session(const TTUnit *u) {
    int dur = u->duration < 1 ? 1 : u->duration;
    if (dur >= 2)
        return 1;
    return u->use_lab_room != 0;
}

static int tt_can_place(int uid, int day, int start_slot, int room_idx) {
    TTUnit *u = &g_tt_units[uid];
    int dur = u->duration < 1 ? 1 : u->duration;
    if (dur > 2)
        dur = 2;

    if (day < 1 || day > MAX_DAYS)
        return 0;
    if (!tt_valid_start_for_duration(dur, start_slot))
        return 0;
    if (u->faculty_id < 0 || u->faculty_id >= TT_FAC_MAP)
        return 0;
    if (g_tt_fac_max[u->faculty_id] <= 0)
        return 0;
    if (g_tt_fac_hours[u->faculty_id] + dur > g_tt_fac_max[u->faculty_id])
        return 0;
    if (!tt_room_matches_unit(u, room_idx))
        return 0;

    for (int j = 0; j < g_tt_n_units; j++) {
        if (!g_tt_assigned[j])
            continue;
        int jd = g_tt_units[j].duration < 1 ? 1 : g_tt_units[j].duration;
        if (!tt_ranges_overlap(day, start_slot, dur, (int)g_tt_uday[j], (int)g_tt_uslot[j], jd))
            continue;
        if (g_tt_units[j].faculty_id == u->faculty_id)
            return 0;
        if (tt_student_groups_clash(u->division_id, u->batch_id, g_tt_units[j].division_id,
                                    g_tt_units[j].batch_id))
            return 0;
        if (g_tt_uroom[j] == room_idx)
            return 0;
    }

    /* At most one lab/practical block per division per day; other sessions are theory. */
    if (tt_unit_is_division_lab_session(u)) {
        for (int j = 0; j < g_tt_n_units; j++) {
            if (!g_tt_assigned[j])
                continue;
            if (g_tt_units[j].division_id != u->division_id)
                continue;
            if (!tt_unit_is_division_lab_session(&g_tt_units[j]))
                continue;
            if ((int)g_tt_uday[j] == day)
                return 0;
        }
    }
    return 1;
}

static int tt_count_options(int uid) {
    int n = 0;
    for (int d = 1; d <= MAX_DAYS; d++) {
        for (int s = 1; s <= MAX_SLOTS; s++) {
            if (!tt_valid_start_for_duration(g_tt_units[uid].duration, s))
                continue;
            for (int ri = 0; ri < g_tt_n_rooms; ri++) {
                if (tt_can_place(uid, d, s, ri))
                    n++;
            }
        }
    }
    return n;
}

static int tt_aggregate_hours_ok(void) {
    int need[TT_FAC_MAP];
    memset(need, 0, sizeof(need));
    for (int i = 0; i < g_tt_n_units; i++) {
        int id = g_tt_units[i].faculty_id;
        int dur = g_tt_units[i].duration < 1 ? 1 : g_tt_units[i].duration;
        if (id < 0 || id >= TT_FAC_MAP || g_tt_fac_max[id] <= 0)
            return 0;
        need[id] += dur;
        if (need[id] > g_tt_fac_max[id])
            return 0;
    }
    return 1;
}

typedef struct {
    unsigned char d, s;
    unsigned short room_idx;
    int score;
} TTCand;

static int tt_cand_cmp(const void *pa, const void *pb) {
    const TTCand *a = (const TTCand *)pa;
    const TTCand *b = (const TTCand *)pb;
    if (b->score != a->score)
        return (b->score > a->score) - (b->score < a->score);
    if (a->d != b->d)
        return (int)a->d - (int)b->d;
    if (a->s != b->s)
        return (int)a->s - (int)b->s;
    return (int)a->room_idx - (int)b->room_idx;
}

static int tt_lcv_related(int a, int b) {
    if (a == b)
        return 0;
    return (g_tt_units[a].faculty_id == g_tt_units[b].faculty_id) ||
           (g_tt_units[a].division_id == g_tt_units[b].division_id);
}

static int tt_solve_dfs(void) {
    int placed = 0;
    int i;
    for (i = 0; i < g_tt_n_units; i++) {
        if (g_tt_assigned[i])
            placed++;
    }
    if (placed == g_tt_n_units)
        return 1;

    int best = -1;
    int best_m = 100000;
    for (i = 0; i < g_tt_n_units; i++) {
        if (g_tt_assigned[i])
            continue;
        int m = tt_count_options(i);
        if (m == 0)
            return 0;
        if (m < best_m) {
            best_m = m;
            best = i;
        }
    }

    TTCand cand[TT_MAX_CAND];
    int nc = 0;
    for (int d = 1; d <= MAX_DAYS; d++) {
        for (int s = 1; s <= MAX_SLOTS; s++) {
            if (!tt_valid_start_for_duration(g_tt_units[best].duration, s))
                continue;
            for (int ri = 0; ri < g_tt_n_rooms; ri++) {
                if (!tt_can_place(best, d, s, ri))
                    continue;
                if (nc >= TT_MAX_CAND)
                    goto cand_done;
                int dur = g_tt_units[best].duration < 1 ? 1 : g_tt_units[best].duration;

                g_tt_assigned[best] = 1;
                g_tt_uday[best] = (unsigned char)d;
                g_tt_uslot[best] = (unsigned char)s;
                g_tt_uroom[best] = ri;
                g_tt_fac_hours[g_tt_units[best].faculty_id] += dur;

                int damage = 0;
                for (int u = 0; u < g_tt_n_units; u++) {
                    if (g_tt_assigned[u])
                        continue;
                    if (!tt_lcv_related(best, u))
                        continue;
                    damage += tt_count_options(u);
                }

                g_tt_fac_hours[g_tt_units[best].faculty_id] -= dur;
                g_tt_assigned[best] = 0;

                cand[nc].d = (unsigned char)d;
                cand[nc].s = (unsigned char)s;
                cand[nc].room_idx = (unsigned short)ri;
                cand[nc].score = damage;
                nc++;
            }
        }
    }
cand_done:

    if (nc == 0)
        return 0;
    if (nc > 1)
        qsort(cand, (size_t)nc, sizeof(cand[0]), tt_cand_cmp);

    for (i = 0; i < nc; i++) {
        int d = cand[i].d;
        int s = cand[i].s;
        int ri = (int)cand[i].room_idx;
        int dur = g_tt_units[best].duration < 1 ? 1 : g_tt_units[best].duration;
        if (!tt_can_place(best, d, s, ri))
            continue;
        g_tt_assigned[best] = 1;
        g_tt_uday[best] = (unsigned char)d;
        g_tt_uslot[best] = (unsigned char)s;
        g_tt_uroom[best] = ri;
        g_tt_fac_hours[g_tt_units[best].faculty_id] += dur;
        if (tt_solve_dfs())
            return 1;
        g_tt_fac_hours[g_tt_units[best].faculty_id] -= dur;
        g_tt_assigned[best] = 0;
    }
    return 0;
}

static int tt_write_output(void) {
    FILE *fp = fopen("timetable.dat", "wb");
    if (!fp)
        return 0;
    for (int i = 0; i < g_tt_n_units; i++) {
        struct Lecture lec;
        memset(&lec, 0, sizeof(lec));
        lec.faculty_id = g_tt_units[i].faculty_id;
        strncpy(lec.subject, g_tt_units[i].subject, sizeof(lec.subject) - 1);
        lec.subject[sizeof(lec.subject) - 1] = '\0';
        sprintf(lec.division, "%d", g_tt_units[i].division_id);
        lec.day = (int)g_tt_uday[i];
        lec.slot = (int)g_tt_uslot[i];
        lec.duration = g_tt_units[i].duration < 1 ? 1 : g_tt_units[i].duration;
        if (g_tt_uroom[i] >= 0 && g_tt_uroom[i] < g_tt_n_rooms)
            lec.room_id = g_tt_rooms[g_tt_uroom[i]].id;
        else
            lec.room_id = 0;
        lec.batch_id = g_tt_units[i].batch_id;
        fwrite(&lec, sizeof(lec), 1, fp);
    }
    fclose(fp);
    return 1;
}

static void tt_persist_faculty_hours(void) {
    FILE *fp = fopen("faculty.dat", "rb+");
    if (!fp)
        return;
    struct Faculty f;
    while (fread(&f, sizeof(f), 1, fp) == 1) {
        if (f.id >= 0 && f.id < TT_FAC_MAP) {
            f.current_hours = g_tt_fac_hours[f.id];
            fseek(fp, -(long)sizeof(f), SEEK_CUR);
            fwrite(&f, sizeof(f), 1, fp);
        }
    }
    fclose(fp);
}

int generateTimetable(void) {
    remove("timetable.dat");
    resetFacultyLoads();

    memset(g_tt_assigned, 0, sizeof(g_tt_assigned));
    memset(g_tt_uday, 0, sizeof(g_tt_uday));
    memset(g_tt_uslot, 0, sizeof(g_tt_uslot));
    for (int z = 0; z < TT_MAX_UNITS; z++)
        g_tt_uroom[z] = -1;

    if (!tt_load_requirements())
        return 0;
    tt_build_units();
    if (g_tt_n_units == 0)
        return 1;
    tt_load_rooms();
    if (!tt_load_faculty_caps())
        return 0;
    if (!tt_aggregate_hours_ok())
        return 0;

    if (!tt_solve_dfs()) {
        remove("timetable.dat");
        resetFacultyLoads();
        return 0;
    }

    if (!tt_write_output()) {
        remove("timetable.dat");
        resetFacultyLoads();
        return 0;
    }

    tt_persist_faculty_hours();
    return 1;
}

/* ================= GET SCHEDULE ================= */

int getFacultySchedule(int faculty_id,
                       struct Lecture** outLectures,
                       int* count) {
    /*
     * Single snapshot of timetable.dat avoids mismatch if the file changes
     * between two passes (idx vs total) or heap overflow if the second pass
     * sees more matching rows than the first.
     */
    FILE *fp = fopen("timetable.dat", "rb");
    if (!fp) return 0;

    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return 0;
    }
    long sz = ftell(fp);
    if (sz < 0) {
        fclose(fp);
        return 0;
    }
    if (sz == 0) {
        fclose(fp);
        *outLectures = NULL;
        *count = 0;
        return 1;
    }

    size_t recsz = sizeof(struct Lecture);
    if ((unsigned long)sz % (unsigned long)recsz != 0) {
        fclose(fp);
        return 0;
    }

    size_t nrec = (size_t)sz / recsz;
    struct Lecture *all = (struct Lecture *)malloc(nrec * recsz);
    if (!all) {
        fclose(fp);
        return 0;
    }

    rewind(fp);
    size_t got = fread(all, recsz, nrec, fp);
    fclose(fp);

    if (got != nrec) {
        free(all);
        return 0;
    }

    int total = 0;
    for (size_t i = 0; i < nrec; i++)
        if (all[i].faculty_id == faculty_id)
            total++;

    if (total == 0) {
        free(all);
        *outLectures = NULL;
        *count = 0;
        return 1;
    }

    struct Lecture *result =
        (struct Lecture *)malloc((size_t)total * sizeof(struct Lecture));
    if (!result) {
        free(all);
        return 0;
    }

    int idx = 0;
    for (size_t i = 0; i < nrec; i++)
        if (all[i].faculty_id == faculty_id)
            result[idx++] = all[i];

    free(all);
    *outLectures = result;
    *count = total;
    return 1;
}

void freeSchedule(struct Lecture* ptr) {
    if (ptr)
        free(ptr);
}

/* ================= REPORT ABSENCE ================= */

static int tt_lec_duration(const struct Lecture *L) {
    int d = L->duration;
    return (d < 1) ? 1 : d;
}

static int tt_lecture_covers_slot(const struct Lecture *L, int day, int slot) {
    if (L->day != day)
        return 0;
    int dur = tt_lec_duration(L);
    int end = L->slot + dur - 1;
    return slot >= L->slot && slot <= end;
}

static int tt_subject_eq(const char *a, const char *b) {
    char sa[51], sb[51];
    memcpy(sa, a, 50);
    memcpy(sb, b, 50);
    sa[50] = '\0';
    sb[50] = '\0';
    return strcmp(sa, sb) == 0;
}

static int tt_lectures_overlap(const struct Lecture *a, const struct Lecture *b) {
    if (a->day != b->day)
        return 0;
    int da = tt_lec_duration(a);
    int db = tt_lec_duration(b);
    int ae = a->slot + da - 1;
    int be = b->slot + db - 1;
    return !(ae < b->slot || be < a->slot);
}

static int tt_faculty_busy_at_lecture(FILE *tt_fp, int cand_id, const struct Lecture *block) {
    struct Lecture check;
    rewind(tt_fp);
    while (fread(&check, sizeof(check), 1, tt_fp) == 1) {
        if (check.faculty_id != cand_id)
            continue;
        if (tt_lectures_overlap(block, &check))
            return 1;
    }
    return 0;
}

#define SUBJ_REQ_CACHE 320

/**
 * Match quality for substitution (lower is better):
 * 0 = teaches this subject with lab-capable row when session is a lab block
 * 1 = teaches same subject (theory row) when substituting a lab
 * 2 = teaches same subject for a theory session
 * 100 = no requirements row for this faculty+subject (fallback pool)
 */
static int subst_subject_match_rank(const struct SubjectRequirement *reqs, int nreq,
                                    int cand_id, const struct Lecture *L) {
    int lec_lab = (tt_lec_duration(L) >= 2);
    int best = 100;

    for (int i = 0; i < nreq; i++) {
        const struct SubjectRequirement *r = &reqs[i];
        if (r->faculty_id != cand_id)
            continue;
        if (!tt_subject_eq(r->subject, L->subject))
            continue;
        /* same subject name in requirements */
        if (!lec_lab) {
            if (best > 2)
                best = 2;
        } else {
            if (r->duration_slots == 2 || r->requires_lab_room) {
                best = 0;
                break;
            }
            if (best > 1)
                best = 1;
        }
    }
    return best;
}

static int subst_pick_better(int rank_a, int load_a, int id_a,
                             int rank_b, int load_b, int id_b) {
    if (rank_a != rank_b)
        return rank_b < rank_a;
    if (load_a != load_b)
        return load_b < load_a;
    return id_b < id_a;
}

int reportAbsence(int faculty_id, int day, int slot, int* substitute_id) {

    FILE *tt_fp = fopen("timetable.dat", "rb+");
    FILE *fac_fp = fopen("faculty.dat", "rb+");

    if (!tt_fp || !fac_fp) {
        if (tt_fp) fclose(tt_fp);
        if (fac_fp) fclose(fac_fp);
        return 0;
    }

    struct Lecture lec;
    struct Lecture found;
    int found_flag = 0;

    while (fread(&lec, sizeof(lec), 1, tt_fp) == 1) {
        if (lec.faculty_id == faculty_id && tt_lecture_covers_slot(&lec, day, slot)) {
            found = lec;
            found_flag = 1;
            break;
        }
    }

    if (!found_flag) {
        fclose(tt_fp);
        fclose(fac_fp);
        return 0;
    }

    int need_hours = tt_lec_duration(&found);

    struct SubjectRequirement req_cache[SUBJ_REQ_CACHE];
    int nreq = 0;
    {
        FILE *rq = fopen("requirements.dat", "rb");
        if (rq) {
            while (nreq < SUBJ_REQ_CACHE &&
                   fread(&req_cache[nreq], sizeof(req_cache[0]), 1, rq) == 1)
                nreq++;
            fclose(rq);
        }
    }

    struct Faculty best_pref;
    struct Faculty best_fallback;
    int has_pref = 0;
    int has_fb = 0;
    int p_rank = 100, p_load = 0, p_id = 0;
    int fb_load = 999999, fb_id = 999999;

    rewind(fac_fp);
    struct Faculty f;
    while (fread(&f, sizeof(f), 1, fac_fp) == 1) {

        if (f.id == faculty_id)
            continue;
        if (f.current_hours + need_hours > f.max_hours_per_week)
            continue;

        if (tt_faculty_busy_at_lecture(tt_fp, f.id, &found))
            continue;

        int rank = subst_subject_match_rank(req_cache, nreq, f.id, &found);

        if (rank < 100) {
            if (!has_pref || subst_pick_better(p_rank, p_load, p_id, rank, f.current_hours, f.id)) {
                best_pref = f;
                has_pref = 1;
                p_rank = rank;
                p_load = f.current_hours;
                p_id = f.id;
            }
        } else {
            if (!has_fb || f.current_hours < fb_load ||
                (f.current_hours == fb_load && f.id < fb_id)) {
                best_fallback = f;
                has_fb = 1;
                fb_load = f.current_hours;
                fb_id = f.id;
            }
        }
    }

    struct Faculty best;
    if (has_pref)
        best = best_pref;
    else if (has_fb)
        best = best_fallback;
    else {
        fclose(tt_fp);
        fclose(fac_fp);
        return 0;
    }

    *substitute_id = best.id;

    rewind(tt_fp);
    while (fread(&lec, sizeof(lec), 1, tt_fp) == 1) {
        if (lec.faculty_id == faculty_id && tt_lecture_covers_slot(&lec, day, slot)) {

            lec.faculty_id = best.id;
            fseek(tt_fp, -(long)sizeof(lec), SEEK_CUR);
            fwrite(&lec, sizeof(lec), 1, tt_fp);
            fflush(tt_fp);
            break;
        }
    }

    rewind(fac_fp);
    while (fread(&f, sizeof(f), 1, fac_fp) == 1) {
        if (f.id == best.id) {
            f.current_hours += need_hours;
            fseek(fac_fp, -(long)sizeof(f), SEEK_CUR);
            fwrite(&f, sizeof(f), 1, fac_fp);
            fflush(fac_fp);
            break;
        }
    }

    rewind(fac_fp);
    while (fread(&f, sizeof(f), 1, fac_fp) == 1) {
        if (f.id == faculty_id) {
            f.current_hours -= need_hours;
            if (f.current_hours < 0)
                f.current_hours = 0;
            fseek(fac_fp, -(long)sizeof(f), SEEK_CUR);
            fwrite(&f, sizeof(f), 1, fac_fp);
            fflush(fac_fp);
            break;
        }
    }

    fclose(tt_fp);
    fclose(fac_fp);
    return 1;
}

int importRequirementCSV(void) {

    FILE *csv = fopen("requirements.csv", "r");
    if (csv == NULL)
        return 0;

    FILE *dat = fopen("requirements.dat", "wb");
    if (dat == NULL) {
        fclose(csv);
        return 0;
    }

    char line[300];

    fgets(line, sizeof(line), csv);

    while (fgets(line, sizeof(line), csv)) {

        struct SubjectRequirement r;
        memset(&r, 0, sizeof(r));
        char *token;

        token = strtok(line, ",");
        if (!token) continue;
        r.division_id = atoi(token);

        token = strtok(NULL, ",");
        if (!token) continue;
        token[strcspn(token, "\r\n")] = 0;
        strncpy(r.subject, token, sizeof(r.subject) - 1);

        token = strtok(NULL, ",");
        if (!token) continue;
        r.faculty_id = atoi(token);

        token = strtok(NULL, ",");
        if (!token) continue;
        r.required_hours = atoi(token);

        r.assigned_hours = 0;
        r.duration_slots = 1;
        r.batch_id = 0;
        r.requires_lab_room = 0;

        token = strtok(NULL, ",\r\n");
        if (token && token[0] != '\r' && token[0] != '\n') {
            r.duration_slots = (atoi(token) == 2) ? 2 : 1;
            token = strtok(NULL, ",\r\n");
            if (token && token[0] != '\r' && token[0] != '\n') {
                r.batch_id = atoi(token);
                token = strtok(NULL, ",\r\n");
                if (token && token[0] != '\r' && token[0] != '\n')
                    r.requires_lab_room = atoi(token) ? 1 : 0;
            }
        }

        fwrite(&r, sizeof(r), 1, dat);
    }

    fclose(csv);
    fclose(dat);

    return 1;
}

int addRoom(int id, const char *name, int is_lab) {
    FILE *fp = fopen("rooms.dat", "ab");
    if (!fp)
        return 0;
    struct RoomRec r;
    memset(&r, 0, sizeof(r));
    r.id = id;
    if (name)
        strncpy(r.name, name, sizeof(r.name) - 1);
    r.name[sizeof(r.name) - 1] = '\0';
    r.is_lab = is_lab ? 1 : 0;
    fwrite(&r, sizeof(r), 1, fp);
    fclose(fp);
    return 1;
}

int importRoomsCSV(void) {
    FILE *csv = fopen("rooms.csv", "r");
    if (csv == NULL)
        return 0;

    FILE *dat = fopen("rooms.dat", "wb");
    if (dat == NULL) {
        fclose(csv);
        return 0;
    }

    char line[200];
    fgets(line, sizeof(line), csv);

    while (fgets(line, sizeof(line), csv)) {
        struct RoomRec r;
        memset(&r, 0, sizeof(r));
        char *token = strtok(line, ",");
        if (!token) continue;
        r.id = atoi(token);
        token = strtok(NULL, ",");
        if (!token) continue;
        token[strcspn(token, "\r\n")] = 0;
        strncpy(r.name, token, sizeof(r.name) - 1);
        token = strtok(NULL, ",\r\n");
        if (token)
            r.is_lab = atoi(token) ? 1 : 0;
        fwrite(&r, sizeof(r), 1, dat);
    }

    fclose(csv);
    fclose(dat);
    return 1;
}

int importFacultyCSV(void) {

    FILE *csv = fopen("faculty.csv", "r");
    if (csv == NULL)
        return 0;

    FILE *dat = fopen("faculty.dat", "wb");  // overwrite old file
    if (dat == NULL) {
        fclose(csv);
        return 0;
    }

    char line[200];

    // Skip header
    fgets(line, sizeof(line), csv);

    while (fgets(line, sizeof(line), csv)) {

        struct Faculty f;
        char *token;

        token = strtok(line, ",");
        if (!token) continue;
        f.id = atoi(token);

        token = strtok(NULL, ",");
        if (!token) continue;
        token[strcspn(token, "\r\n")] = 0;
        strncpy(f.name, token, sizeof(f.name) - 1);

        token = strtok(NULL, ",");
        if (!token) continue;
        token[strcspn(token, "\r\n")] = 0;
        strncpy(f.username, token, sizeof(f.username) - 1);

        token = strtok(NULL, ",");
        if (!token) continue;
        token[strcspn(token, "\r\n")] = 0;
        strncpy(f.password, token, sizeof(f.password) - 1);

        token = strtok(NULL, ",");
        if (!token) continue;
        f.max_hours_per_week = atoi(token);

        f.current_hours = 0;

        fwrite(&f, sizeof(f), 1, dat);
    }

    fclose(csv);
    fclose(dat);

    return 1;
}

int getFacultyName(int faculty_id, char* name_buffer) {

    FILE *fp = fopen("faculty.dat", "rb");
    if (!fp) return 0;

    struct Faculty f;

    while (fread(&f, sizeof(f), 1, fp) == 1) {
        if (f.id == faculty_id) {
            faculty_sanitize_strings(&f);
            strncpy(name_buffer, f.name, 127);
            name_buffer[127] = '\0';
            fclose(fp);
            return 1;
        }
    }

    fclose(fp);
    return 0;
}