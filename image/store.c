/* Bounded, opaque storage for one image consumer.
 * SPDX-License-Identifier: GPL-2.0-or-later */
#include "store.h"
#include "../platform/elks_store.h"
#include <stdlib.h>
#ifdef __ia16__
#include <malloc.h>
#define FAR __far
#define take(n) fmemalloc((unsigned long)(n))
#define give(p) fmemfree(p)
#else
#define FAR
#define take(n) malloc(n)
#define give(p) free(p)
#endif
/* Small independent far allocations keep 8088 copies inside each segment.
 * This private prototype bounds one image to eight 16K banks. */
#define BANK 16384U
#define BANKS 8
struct ew_store {
    unsigned long size;
    unsigned ems, banks;
    unsigned char FAR *ram[BANKS];
};
void ew_store_free(struct ew_store *s) {
    unsigned i;
    if (!s) return;
    if (s->ems) ew_store_ems_free(s->ems);
    for (i = 0; i < s->banks; ++i) give(s->ram[i]);
    free(s);
}
struct ew_store *ew_store_alloc(unsigned long bytes) {
    struct ew_store *s;
    unsigned long left;
    unsigned n;
    if (!bytes || bytes > (unsigned long)BANK * BANKS) return 0;
    s = calloc(1, sizeof(*s));
    if (!s) return 0;
    s->size = bytes;
    s->ems = ew_store_ems_alloc(bytes);
    if (s->ems) return s;
    for (left = bytes; left; left -= n) {
        n = left > BANK ? BANK : (unsigned)left;
        s->ram[s->banks] = take(n);
        if (!s->ram[s->banks]) { ew_store_free(s); return 0; }
        ++s->banks;
    }
    return s;
}
static int copy(struct ew_store *s, unsigned long offset,
                unsigned char *buf, unsigned count, int write) {
    unsigned bank, at, n, i;
    unsigned char FAR *p;
    /* Subtraction after ordering prevents wrap at ULONG_MAX. Validate all
     * bounds before invoking a backend or changing any destination byte. */
    if (!s || offset > s->size || (unsigned long)count > s->size - offset ||
        (count && !buf)) return -1;
    if (!count) return 0;
    if (s->ems) return ew_store_ems_copy(s->ems, offset, buf, count, write);
    while (count) {
        bank = (unsigned)(offset >> 14); at = (unsigned)offset & (BANK - 1);
        n = BANK - at; if (n > count) n = count;
        p = s->ram[bank] + at;
        if (write) for (i = 0; i < n; ++i) p[i] = buf[i];
        else for (i = 0; i < n; ++i) buf[i] = p[i];
        count -= n; buf += n; offset += n;
    }
    return 0;
}
int ew_store_write(struct ew_store *s, unsigned long o, const unsigned char *b, unsigned n) {
    return copy(s, o, (unsigned char *)b, n, 1);
}
int ew_store_read(struct ew_store *s, unsigned long o, unsigned char *b, unsigned n) {
    return copy(s, o, b, n, 0);
}
