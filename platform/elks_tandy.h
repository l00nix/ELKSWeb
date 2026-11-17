/* Tandy 1000 / PCjr mode 09h raster: 320x200, 16 colours, packed pixels.
 * SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef ELKSWEB_TANDY_H
#define ELKSWEB_TANDY_H

#ifdef __ia16__
typedef unsigned char __far *ew_tandy_bytes;
#else
typedef unsigned char *ew_tandy_bytes;
#endif

/* Four interleaved 8K banks: row y lives in bank y&3. Two pixels per byte,
 * left pixel in the high nibble. Set by the platform layer only after the
 * kernel has certified the reserved segment (9800h Tandy, 1800h PCjr). */
extern ew_tandy_bytes ew_tandy_video;
#define EW_TANDY_WIDTH 320
#define EW_TANDY_HEIGHT 200
#define EW_TANDY_ROW_BYTES 160
#define EW_TANDY_OFFSET(x, y) ((((unsigned)(y) & 3U) << 13) + \
    ((unsigned)(y) >> 2) * 160U + ((unsigned)(x) >> 1))

/* Callers clip: every coordinate below must already be on screen. */
void ew_tandy_clear(int color);
void ew_tandy_pixel(int x, int y, int color);
void ew_tandy_hline(int x, int y, int width, int color);
/* Move bytes 0..count-1 of each row in [top,bottom); positive delta is up. */
void ew_tandy_scroll(int top, int bottom, int delta, unsigned count);
/* Copy width packed pixels to (x,y). line holds them starting at nibble
 * x&1, so whole bytes line up with video bytes. A null mask is opaque;
 * otherwise bit 7-(i&7) of mask[i>>3] set means pixel i is drawn. */
void ew_tandy_row(int x, int y, const unsigned char *line,
                  const unsigned char *mask, unsigned width);
void ew_tandy_cursor_show(int x, int y, int hand);
void ew_tandy_cursor_hide(void);

#endif
