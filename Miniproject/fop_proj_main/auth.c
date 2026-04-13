#include <stdio.h>
#include <string.h>

int verify(const char* username, const char* password)
{
    if (strcmp(username, "Vikram Sarabhai Iyer") == 0 && strcmp(password, "VSI#Quantum@2026") == 0) return 1;
    if (strcmp(username, "Ananya Chatterjee") == 0 && strcmp(password, "Shakes-Pear-Ananya!") == 0) return 1;
    if (strcmp(username, "Rajeshwari Deshpande") == 0 && strcmp(password, "Pi-is-Life#3.14RD") == 0) return 1;
    if (strcmp(username, "Arjun Malhotra") == 0 && strcmp(password, "Arjun@-88") == 0) return 1;
    if (strcmp(username, "Meenakshi Menon") == 0 && strcmp(password, "Meena!H2O") == 0) return 1;
    if (strcmp(username, "admin") == 0 && strcmp(password, "123") == 0) return 1;
    return 0;
}