/* Tandy 1000 / PCjr mode 09h raster: 320x200, 16 colours, packed pixels.
 * Only 8086 instructions; no page-register or palette programming.
 * SPDX-License-Identifier: GPL-2.0-or-later */
#include "elks_tandy.h"

ew_tandy_bytes ew_tandy_video;

#ifdef __ia16__
/* The framebuffer is one segment, so row moves and fills stay inside it.
 * String instructions matter on an 8088: a C far-pointer loop is ~10x slower. */
static void move_bytes(unsigned to, unsigned from, unsigned count)
{
    unsigned segment = (unsigned)((unsigned long)ew_tandy_video >> 16);
    __asm__ volatile (
        "push %%ds\n\tpush %%es\n\tmov %%ax, %%ds\n\tmov %%ax, %%es\n\tcld\n\t"
        "shr $1, %%cx\n\trep movsw\n\tjnc 1f\n\tmovsb\n1:\t"
        "pop %%es\n\tpop %%ds"
        : "+S"(from), "+D"(to), "+c"(count) : "a"(segment) : "cc", "memory");
}
static void fill_bytes(unsigned to, unsigned value, unsigned count)
{
    unsigned segment = (unsigned)((unsigned long)ew_tandy_video >> 16);
    __asm__ volatile (
        "push %%es\n\tmov %%dx, %%es\n\tcld\n\t"
        "shr $1, %%cx\n\trep stosw\n\tjnc 1f\n\tstosb\n1:\tpop %%es"
        : "+D"(to), "+c"(count) : "a"(value * 0x0101U), "d"(segment)
        : "cc", "memory");
}
static void put_bytes(unsigned to, const unsigned char *from, unsigned count)
{
    unsigned segment = (unsigned)((unsigned long)ew_tandy_video >> 16);
    __asm__ volatile (
        "push %%es\n\tmov %%ax, %%es\n\tcld\n\t"
        "shr $1, %%cx\n\trep movsw\n\tjnc 1f\n\tmovsb\n1:\tpop %%es"
        : "+S"(from), "+D"(to), "+c"(count) : "a"(segment) : "cc", "memory");
}
static void get_bytes(unsigned char *to, unsigned from, unsigned count)
{
    unsigned segment = (unsigned)((unsigned long)ew_tandy_video >> 16);
    __asm__ volatile (
        "push %%ds\n\tpush %%es\n\tpush %%ss\n\tpop %%es\n\tmov %%ax, %%ds\n\tcld\n\t"
        "rep movsb\n\tpop %%es\n\tpop %%ds"
        : "+S"(from), "+D"(to), "+c"(count) : "a"(segment) : "cc", "memory");
}
#else
static void get_bytes(unsigned char *to, unsigned from, unsigned count)
{
    while (count--) *to++ = ew_tandy_video[from++];
}
static void move_bytes(unsigned to, unsigned from, unsigned count)
{
    while (count--) ew_tandy_video[to++] = ew_tandy_video[from++];
}
static void fill_bytes(unsigned to, unsigned value, unsigned count)
{
    while (count--) ew_tandy_video[to++] = (unsigned char)value;
}
static void put_bytes(unsigned to, const unsigned char *from, unsigned count)
{
    while (count--) ew_tandy_video[to++] = *from++;
}
#endif

void ew_tandy_clear(int color)
{
    unsigned bank;
    /* 50 rows per bank; leave the 192 unused bytes after each untouched. */
    for (bank = 0; bank < 4; ++bank)
        fill_bytes(bank << 13, (unsigned)(color & 15) * 17U, 8000);
}

void ew_tandy_pixel(int x, int y, int color)
{
    ew_tandy_bytes p = ew_tandy_video + EW_TANDY_OFFSET(x, y);
    if (x & 1) *p = (*p & 0xf0) | (color & 15);
    else *p = (*p & 0x0f) | ((color & 15) << 4);
}

void ew_tandy_hline(int x, int y, int width, int color)
{
    unsigned offset = EW_TANDY_OFFSET(x, y);
    color &= 15;
    if (x & 1) {
        ew_tandy_video[offset] = (ew_tandy_video[offset] & 0xf0) | color;
        ++offset;
        --width;
    }
    if (width >> 1) fill_bytes(offset, (unsigned)color * 17U, (unsigned)width >> 1);
    if (width & 1) {
        offset += (unsigned)width >> 1;
        ew_tandy_video[offset] = (ew_tandy_video[offset] & 0x0f) | (color << 4);
    }
}

/* Rows never share bytes, so each row moves forward; only the row order
 * depends on direction. Odd deltas cross banks and need no special case. */
void ew_tandy_scroll(int top, int bottom, int delta, unsigned count)
{
    int y, end, step;
    if (delta > 0) { y = top; end = bottom - delta; step = 1; }
    else { y = bottom - 1; end = top - delta - 1; step = -1; }
    for (; y != end; y += step)
        move_bytes(EW_TANDY_OFFSET(0, y), EW_TANDY_OFFSET(0, y + delta), count);
}

void ew_tandy_row(int x, int y, const unsigned char *line,
                  const unsigned char *mask, unsigned width)
{
    unsigned offset = EW_TANDY_OFFSET(x, y), i = 0, n;
    unsigned char keep, merged[EW_TANDY_ROW_BYTES + 1];
    if (!width) return;
    if (mask) {
        /* Fetch the row once, merge in near memory, store it once: far
         * read-modify-write per pixel is several times slower on an 8088. */
        n = (width + (x & 1) + 1) >> 1;
        get_bytes(merged, offset, n);
        for (; i < width; ++i) {
            if (!(mask[i >> 3] & (0x80U >> (i & 7)))) continue;
            n = i + (x & 1);
            keep = n & 1 ? 0xf0 : 0x0f;
            merged[n >> 1] = (merged[n >> 1] & keep) | (line[n >> 1] & ~keep);
        }
        put_bytes(offset, merged, (width + (x & 1) + 1) >> 1);
        return;
    }
    if (x & 1) {
        ew_tandy_video[offset] = (ew_tandy_video[offset] & 0xf0) | (line[0] & 0x0f);
        ++offset; ++line; --width;
    }
    put_bytes(offset, line, width >> 1);
    if (width & 1) {
        offset += width >> 1;
        ew_tandy_video[offset] =
            (ew_tandy_video[offset] & 0x0f) | (line[width >> 1] & 0xf0);
    }
}

/* Original ELKSWeb arrow and hand at their native 8x12 size: black outline,
 * white interior. Up to five bytes per row are saved under the pointer. */
static const unsigned char outline[2][12] = {
    {0x80,0xc0,0xe0,0xf0,0xf8,0xfc,0xfe,0xff,0xf8,0xd8,0x8c,0x0c},
    {0xc0,0xe0,0xe0,0xe0,0xfc,0xfe,0xff,0xff,0xff,0x7e,0x3e,0x3c}};
static const unsigned char interior[2][12] = {
    {0,0,0x40,0x60,0x70,0x78,0x7c,0x60,0x60,0x40,0,0},
    {0,0x40,0x40,0x40,0x40,0x54,0x54,0x7e,0x3e,0x3c,0x1c,0}};
static unsigned char saved[12][5];
static int saved_x = -1, saved_y;

void ew_tandy_cursor_hide(void)
{
    int row, col;
    unsigned offset;
    if (saved_x < 0) return;
    for (row = 0; row < 12 && saved_y + row < EW_TANDY_HEIGHT; ++row) {
        offset = EW_TANDY_OFFSET(saved_x, saved_y + row);
        for (col = 0; col < 5 && (saved_x >> 1) + col < EW_TANDY_ROW_BYTES; ++col)
            ew_tandy_video[offset + col] = saved[row][col];
    }
    saved_x = -1;
}

void ew_tandy_cursor_show(int x, int y, int hand)
{
    int row, col;
    unsigned offset;
    unsigned char edge, fill;
    ew_tandy_cursor_hide();
    saved_x = x; saved_y = y;
    for (row = 0; row < 12 && y + row < EW_TANDY_HEIGHT; ++row) {
        offset = EW_TANDY_OFFSET(x, y + row);
        for (col = 0; col < 5 && (x >> 1) + col < EW_TANDY_ROW_BYTES; ++col)
            saved[row][col] = ew_tandy_video[offset + col];
        edge = outline[hand][row];
        fill = interior[hand][row];
        for (col = 0; col < 8 && x + col < EW_TANDY_WIDTH; ++col, edge <<= 1, fill <<= 1)
            if (edge & 0x80) ew_tandy_pixel(x + col, y + row, fill & 0x80 ? 15 : 0);
    }
}
