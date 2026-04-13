# Native backend for Python UI (ctypes)
CC = gcc
CFLAGS = -std=c99 -Wall -Wextra -fPIC
SRC = backend.c
HDR = backend.h

UNAME_S := $(shell uname -s 2>/dev/null || echo unknown)

ifeq ($(UNAME_S),Darwin)
  OUT = libbackend.dylib
  LDFLAGS = -dynamiclib
else ifeq ($(OS),Windows_NT)
  OUT = backend.dll
  LDFLAGS = -shared
else
  OUT = libbackend.so
  LDFLAGS = -shared
endif

all: $(OUT)

$(OUT): $(SRC) $(HDR)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $(OUT) $(SRC)

clean:
	rm -f libbackend.dylib libbackend.so backend.dll *.o

.PHONY: all clean
