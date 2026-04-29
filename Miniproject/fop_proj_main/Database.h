#ifndef DATABASE_H
#define DATABASE_H

#ifdef BUILDING_DLL
    #define DLL_EXPORT __declspec(dllexport)
#else
    #define DLL_EXPORT __declspec(dllimport)
#endif

struct db {
    char name[50];
    int prn;
    float cgpa;
    int teacher;
};

struct tdb {
    int teacher_sr_no;
    char teacher_name[50];
    char password[50];
};

DLL_EXPORT int initDatabase(const char* studentFile, const char* teacherFile);
DLL_EXPORT int getStudentCount(int teacherNum);
DLL_EXPORT struct db* getStudentsForTeacher(int teacherNum, int* outCount);
DLL_EXPORT void freeStudents(struct db* ptr);
DLL_EXPORT struct tdb getTeacher(int teacherNum);
DLL_EXPORT struct tdb* getTeacherTable(int* outCount);


#endif