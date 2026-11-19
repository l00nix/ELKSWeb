/* Recovered native /dev/ems bounded-copy adapter. No DOS INT 67h.
 * Mapping and register ownership stay in the existing ELKS kernel driver.
 * SPDX-License-Identifier: GPL-2.0-or-later */
#include "elks_store.h"
#if defined(__ia16__) || defined(EW_STORE_EMS_HOST_TEST)
#include <fcntl.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/ioctl.h>
/* Match the recovered experimental linuxmt/ems.h. Kept private so builds
 * with ordinary ELKS headers still work; this does not introduce a new ABI. */
#ifndef EMS_GETINFO
#define EMS_GETINFO 1
#define EMS_ALLOC 2
#define EMS_FREE 3
#define EMS_READ 4
#define EMS_WRITE 5
struct ems_info { unsigned short pages, free, frame, port; };
struct ems_xfer { unsigned short handle, count; unsigned long offset; char *buf; };
#endif
static int fd = -1;
static unsigned users;
static void close_unused(void) {
    if (!users && fd >= 0) { close(fd); fd = -1; }
}
unsigned ew_store_ems_alloc(unsigned long bytes) {
    struct ems_info info;
    unsigned short pages;
    const char *wanted = getenv("ELKSWEB_EMS");
    if (wanted && wanted[0] == '0') return 0;
    if (fd < 0) {
        fd = open("/dev/ems", O_RDWR);
        if (fd < 0) return 0;
        if (ioctl(fd, EMS_GETINFO, &info) < 0 || !info.pages) {
            close_unused(); return 0;
        }
    }
    pages = (unsigned short)((bytes + 16383UL) >> 14);
    if (!pages || ioctl(fd, EMS_ALLOC, &pages) < 0 || !pages) {
        close_unused(); return 0;
    }
    ++users;
    return pages; /* kernel replaces page count with handle */
}
void ew_store_ems_free(unsigned handle) {
    if (fd < 0 || !handle) return;
    ioctl(fd, EMS_FREE, handle);
    if (users) --users;
    close_unused();
}
int ew_store_ems_copy(unsigned handle, unsigned long offset,
                       unsigned char *buffer, unsigned count, int write) {
    struct ems_xfer x;
    x.handle = handle; x.offset = offset; x.buf = (char *)buffer; x.count = count;
    return fd < 0 || ioctl(fd, write ? EMS_WRITE : EMS_READ, &x) < 0 ? -1 : 0;
}
#else
/* Ordinary hosts have no native ELKS EMS service. */
unsigned ew_store_ems_alloc(unsigned long bytes) { (void)bytes; return 0; }
void ew_store_ems_free(unsigned handle) { (void)handle; }
int ew_store_ems_copy(unsigned h, unsigned long o, unsigned char *b, unsigned n, int w) {
    (void)h; (void)o; (void)b; (void)n; (void)w; return -1;
}
#endif
