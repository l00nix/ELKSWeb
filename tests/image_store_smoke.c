/* One image round-trip through opaque storage, with optional recovered ELKS
 * banked EMS model. No native ABI/hardware claim. SPDX-License-Identifier: GPL-2.0-or-later
 *
 * Normal host: cc -I./src tests/image_store_smoke.c image/gif.c image/store.c -o smoke
 * Recovered model: add -DEMS_MODEL_SOURCE='"/absolute/elkscmd/test/other/test_ems_host.c"'
 * Input: a 616x200 transparent GIF (packed pixels + mask exceed 64K).
 * The focused run uses RGBI stripes, transparent index 0, interlace on.
 * Run: ./smoke image.gif (and ELKSWEB_EMS=0 ./smoke image.gif for fallback).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <stdarg.h>
#include "../image/gif.h"
#include "../image/store.h"
#ifdef EMS_MODEL_SOURCE
/* Reuse the existing driver model but do not run its blanket test main. */
#define main recovered_unused_main
#include EMS_MODEL_SOURCE
#undef main
static unsigned opened, allocated, released;
static int model_open(const char *path, int flags, ...) {
    (void)flags;
    if (strcmp(path, "/dev/ems")) return -1;
    ++opened; return 17;
}
static int model_close(int descriptor) {
    (void)descriptor; ems_release_all(); return 0;
}
static int model_ioctl(int descriptor, unsigned long command, ...) {
    va_list args;
    struct ems_xfer *x;
    struct ems_info *info;
    unsigned short *pages;
    int result;
    (void)descriptor;
    va_start(args, command);
    switch (command) {
    case EMS_GETINFO:
        info = va_arg(args, struct ems_info *);
        info->pages = ems_pages; info->free = ems_free_pages();
        info->frame = ems_frame; info->port = ems_port;
        result = 0; break;
    case EMS_ALLOC:
        pages = va_arg(args, unsigned short *); result = ems_alloc(*pages);
        if (result > 0) { *pages = result; ++allocated; result = 0; }
        break;
    case EMS_FREE:
        result = ems_free(va_arg(args, unsigned)); ++released; break;
    case EMS_READ: case EMS_WRITE:
        x = va_arg(args, struct ems_xfer *);
        result = ems_transfer(x->handle, x->offset, x->buf, x->count, command == EMS_WRITE);
        break;
    default: result = -1;
    }
    va_end(args); return result;
}
#define EW_STORE_EMS_HOST_TEST
#define open model_open
#define close model_close
#define ioctl model_ioctl
#endif
#include "../platform/elks_store.c"
#ifdef EMS_MODEL_SOURCE
#undef open
#undef close
#undef ioctl
#endif
#define REQUIRE(c) do { if (!(c)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#c); return 1; } } while (0)
static int same_far(const unsigned char *a, const unsigned char EW_GIF_FAR *b, unsigned n) {
    while (n--) if (*a++ != *b++) return 0;
    return 1;
}
int main(int argc, char **argv) {
    struct ew_gif ordinary, stored;
    FILE *f;
    unsigned char *data, row[320], mask[80], before[2], after[2];
    long length;
    unsigned y, stride;
    unsigned long bytes;
#ifdef EMS_MODEL_SOURCE
    const char *disabled = getenv("ELKSWEB_EMS");
    boot(0x268, 0xE000, 0);
    sim_scramble = 1; /* mapping never survives a copy piece */
#endif
    REQUIRE(argc == 2);
    f = fopen(argv[1], "rb"); REQUIRE(f);
    REQUIRE(!fseek(f, 0, SEEK_END)); length = ftell(f);
    REQUIRE(length > 0 && length <= 60000); rewind(f);
    data = malloc(length); REQUIRE(data);
    REQUIRE(fread(data, 1, length, f) == (unsigned long)length); fclose(f);
    REQUIRE(ew_gif_decode_color(data, length, &ordinary, 616, 200) == EW_GIF_OK);
    REQUIRE(ew_gif_decode_color_store(data, length, &stored, 616, 200) == EW_GIF_OK);
    REQUIRE(stored.store && !stored.pixels && !stored.opacity);
    REQUIRE(stored.width == ordinary.width && stored.height == ordinary.height);
    stride = (stored.width + 7) >> 3;
    for (y = 0; y < stored.height; ++y) {
        REQUIRE(!ew_store_read(stored.store, (unsigned long)y*stored.stride, row, stored.stride));
        REQUIRE(same_far(row, ordinary.pixels + (unsigned long)y*ordinary.stride, stored.stride));
        if (stored.masked) {
            REQUIRE(!ew_store_read(stored.store, stored.opacity_at + (unsigned long)y*stride, mask, stride));
            REQUIRE(same_far(mask, ordinary.opacity + (unsigned long)y*stride, stride));
        }
    }
    bytes = stored.opacity_at + (stored.masked ? (unsigned long)stride*stored.height : 0);
    REQUIRE(bytes > 65536UL); /* image crosses 16K banks and the 64K offset */
    REQUIRE(!ew_store_read(stored.store, 16383UL, before, 2));
    REQUIRE(ew_store_write(stored.store, ULONG_MAX, before, 2) == -1);
    REQUIRE(ew_store_write(stored.store, bytes-1, before, 2) == -1);
    REQUIRE(ew_store_read(stored.store, bytes+1, after, 0) == -1);
    REQUIRE(!ew_store_read(stored.store, bytes, NULL, 0));
    REQUIRE(!ew_store_read(stored.store, 16383UL, after, 2) && !memcmp(before,after,2));
    ew_gif_free(&stored); ew_gif_free(&ordinary); free(data);
    REQUIRE(!stored.store);
#ifdef EMS_MODEL_SOURCE
    REQUIRE(ems_free_pages() == 128);
    if (disabled && disabled[0] == '0') REQUIRE(!opened && !allocated);
    else REQUIRE(opened == 1 && allocated == 1 && released == 1);
    printf("PASS image pixels/mask, wide offsets, bounds, cleanup; EMS model allocations=%u\n",allocated);
#else
    puts("PASS image pixels/mask, wide offsets, bounds, cleanup; no native EMS service (RAM fallback)");
#endif
    return 0;
}
