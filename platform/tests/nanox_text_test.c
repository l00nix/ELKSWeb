/* Exercise the actual Nano-X glyph packer using Nano-X's 16-bit bitmap type.
 * Link with elks_nanox.c, font.c and dead-section elimination, against the
 * Nano-X headers used by toolchain/build-nanox.sh. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <nano-X.h>
#include "../elks_platform.h"
#include "../../font/font.h"

#define WIDTH 640
#define HEIGHT 36
static unsigned char pixels[HEIGHT][WIDTH], reference[HEIGHT][WIDTH];
static unsigned ink, calls, payload, right, top, bottom;

void GrSetGCForeground(GR_GC_ID gc, GR_COLOR color)
{
    (void)gc;
    ink = color ? 1 : 0;
}

void GrFillRect(GR_DRAW_ID id, GR_GC_ID gc, GR_COORD x, GR_COORD y,
                GR_SIZE w, GR_SIZE h)
{
    int row;
    (void)id; (void)gc;
    assert(x >= 0 && (unsigned)(x + w) <= right);
    assert(y >= (int)top && (unsigned)(y + h) <= bottom);
    for (row = y; row < y + h; ++row)
        memset(pixels[row] + x, ink, w);
}

void GrBitmap(GR_DRAW_ID id, GR_GC_ID gc, GR_COORD x, GR_COORD y,
              GR_SIZE w, GR_SIZE h, GR_BITMAP *bitmap)
{
    int row, col, stride = (w + 15) / 16;
    (void)id; (void)gc;
    assert(w > 0 && h > 0);
    assert(x >= 0 && (unsigned)(x + w) <= right);
    assert(y >= (int)top && (unsigned)(y + h) <= bottom);
    ++calls;
    payload += stride * h * sizeof(*bitmap);
    for (row = 0; row < h; ++row)
        for (col = 0; col < w; ++col)
            if (bitmap[row * stride + col / 16] & (0x8000U >> (col & 15)))
                pixels[y + row][x + col] = ink;
}

static void draw_text(int x, int y, int size, int bold, int italic, int mixed)
{
    static const unsigned char s[] =
        "WAVy zig-zag \277x\240QK\017jLMr pink and violet!"
        " words cross every bitmap boundary in both directions.";
    int i, advance = ew_face_advance(bold, size);
    for (i = 0; i < (int)sizeof(s) - 1; ++i) {
        int fg = !mixed || (i / 7) % 2 ? 15 : 0;
        int bg = mixed && i % 13 == 7 ? 0 : -1;
        int line = y + (mixed && i % 5 == 0 ? 1 : 0);
        ew_face_draw(x, line, s[i], fg, bg, bold, italic, size);
        x += advance;
    }
}

int main(void)
{
    unsigned base_calls, base_payload;
    int x, y, size, bold, italic, mixed, cases = 0;
    ew_screen_width = WIDTH;
    ew_screen_height = HEIGHT;
    ew_color = 1;
    top = 6;
    bottom = 21;
    for (right = 19; right <= WIDTH; right += 207) {
        ew_clip(right, top, bottom);
        for (x = -17; x < 22; x += 2)
            for (y = -4; y < 25; y += 3)
                for (size = 0; size < 3; ++size)
                    for (bold = 0; bold < 2; ++bold)
                        for (italic = 0; italic < 2; ++italic)
                            for (mixed = 0; mixed < 2; ++mixed) {
                                memset(pixels, 2, sizeof(pixels));
                                draw_text(x, y, size, bold, italic, mixed);
                                memcpy(reference, pixels, sizeof(reference));
                                memset(pixels, 2, sizeof(pixels));
                                ew_nanox_text_begin();
                                draw_text(x, y, size, bold, italic, mixed);
                                ew_nanox_text_end();
                                assert(!memcmp(pixels, reference, sizeof(pixels)));
                                ++cases;
                            }
    }
    right = WIDTH;
    ew_clip(right, top, bottom);
    calls = payload = 0;
    draw_text(2, 8, 1, 0, 1, 0);
    base_calls = calls;
    base_payload = payload;
    calls = payload = 0;
    ew_nanox_text_begin();
    draw_text(2, 8, 1, 0, 1, 0);
    ew_nanox_text_end();
    assert(calls * 4 < base_calls && payload < base_payload);
    printf("%d pixel comparisons; italic line: %u -> %u bitmap calls, %u -> %u payload bytes\n",
           cases, base_calls, calls, base_payload, payload);
    return 0;
}
