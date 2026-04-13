#include "Database.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define MAX_LINE_SIZE 1024
#define STUDENTS_PER_TEACHER 10
#define TOTAL_STUDENTS (STUDENTS_PER_TEACHER * 10)

static struct db sdb[TOTAL_STUDENTS];
static struct tdb tableB[TOTAL_STUDENTS];

int initDatabase(const char* studentFile, const char* teacherFile) {
    FILE *fp1 = fopen(studentFile, "r");
    FILE *fp2 = fopen(teacherFile, "r");
    if (!fp1 || !fp2) return 1;

    char line[MAX_LINE_SIZE];
    int countA = 0, countB = 0;

    while (fgets(line, MAX_LINE_SIZE, fp1) && countA < TOTAL_STUDENTS) {
        char *ptr = strtok(line, ",");
        if (ptr) strcpy(sdb[countA].name, ptr);

        ptr = strtok(NULL, ",");
        if (ptr) sdb[countA].teacher = atoi(ptr);

        ptr = strtok(NULL, ",");
        if (ptr) sdb[countA].prn = atol(ptr);

        ptr = strtok(NULL, ",");
        if (ptr) sdb[countA].cgpa = atof(ptr);

        countA++;
    }

    while (fgets(line, MAX_LINE_SIZE, fp2) && countB < TOTAL_STUDENTS) {
        char *ptr = strtok(line, ",");
        if (ptr) tableB[countB].teacher_sr_no = atoi(ptr);

        ptr = strtok(NULL, ",");
        if (ptr) {
            ptr[strcspn(ptr, "\r\n")] = '\0';   // trim newline
            strcpy(tableB[countB].teacher_name, ptr);
        }

        ptr = strtok(NULL, ",");
        if (ptr) {
            ptr[strcspn(ptr, "\r\n")] = '\0';   // trim newline
            strcpy(tableB[countB].password, ptr);
        }

        countB++;
    }

    fclose(fp1);
    fclose(fp2);
    return 0;
}

int getStudentCount(int teacherNum) {
    int count = 0;
    if (teacherNum == 0) {
        for(int i=0;i<TOTAL_STUDENTS;i++) count++;
    }
    else {
        for(int i=0;i<TOTAL_STUDENTS;i++) if(sdb[i].teacher == teacherNum) count++;
    }
    return count;
}

struct db* getStudentsForTeacher(int teacherNum, int* outCount) {
    int count = getStudentCount(teacherNum);
    *outCount = count;

    struct db* result = malloc(count * sizeof(struct db));
    if (!result) return NULL;

    int idx = 0;
    if (teacherNum == 0) {
        for (int i = 0; i < TOTAL_STUDENTS; i++) {
            result[idx++] = sdb[i];
        }
    }
    else{
        for (int i = 0; i < TOTAL_STUDENTS; i++) {
            if (sdb[i].teacher == teacherNum) {
                result[idx++] = sdb[i];
            }
        }
    }
    return result;
}

void freeStudents(struct db* ptr) {
    free(ptr);
}

struct tdb getTeacher(int teacherNum) {
    return tableB[teacherNum];
}

struct tdb* getTeacherTable(int* outCount) {
    if (outCount) *outCount = TOTAL_STUDENTS;
    return tableB;
}
