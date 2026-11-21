/* ELKSWeb native ELKS display/input interface. SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef ELKSWEB_PLATFORM_H
#define ELKSWEB_PLATFORM_H

extern int ew_screen_width, ew_screen_height, ew_pixel_aspect;
/* Nonzero in colour modes: colours are then 0..15 (IBM RGBI
 * order) everywhere a monochrome mode takes white=1/black=0. */
extern int ew_color;
#define EW_SCREEN_WIDTH ew_screen_width
/* The page occupies everything left of the scroll bar. */
#define EW_BAR_WIDTH (ew_screen_width == 320 ? 8 : 16)
#define EW_PAGE_WIDTH (ew_screen_width - EW_BAR_WIDTH)
#define EW_SCREEN_HEIGHT ew_screen_height
#define EW_VIDEO_CGA 6
#define EW_VIDEO_EGA 16
#define EW_VIDEO_VGA 18
#define EW_VIDEO_TANDY 9
#define EW_BLACK 0
#define EW_BLUE 1
#define EW_GREEN 2
#define EW_CYAN 3
#define EW_RED 4
#define EW_MAGENTA 5
#define EW_BROWN 6
#define EW_SILVER 7
#define EW_GRAY 8
#define EW_LIGHT_BLUE 9
#define EW_YELLOW 14
#define EW_WHITE 15
#define EW_FONT_WIDTH 8
#define EW_FONT_HEIGHT 8

enum ew_key {
    EW_KEY_NONE = 0,
    EW_KEY_BACKSPACE = 8,
    EW_KEY_TAB = 9,
    EW_KEY_ENTER = 13,
    EW_KEY_ESC = 27,
    EW_KEY_UP = 256,
    EW_KEY_DOWN, EW_KEY_LEFT, EW_KEY_RIGHT,
    EW_KEY_PGUP, EW_KEY_PGDN, EW_KEY_HOME, EW_KEY_END,
    EW_KEY_BACKTAB, EW_KEY_DELETE,
    EW_KEY_F1, EW_KEY_F2, EW_KEY_F3, EW_KEY_F4, EW_KEY_F5,
    EW_KEY_F6, EW_KEY_F7, EW_KEY_F8, EW_KEY_F9, EW_KEY_F10
};

/* A null mode asks on the text console; cga/ega/vga/vga-mono/tandy/pcjr bypass the prompt.
 * Returns0 on success,1 on user cancellation,-1 on failure. An unsupported
 * adapter is rejected before changing video mode; console settings are
 * restored on cancellation, failure and shutdown. Input uses /dev/tty1. */
int ew_platform_init(const char *mode);
const char *ew_platform_error(void);
void ew_platform_shutdown(void);
int ew_getkey(void);                 /* Nonblocking; zero means no key. */
#ifdef ELKSWEB_NANOX
int ew_platform_exposed(void);
void ew_nanox_glyph(int x, int y, const unsigned char *glyph, int advance,
                    int height, int fg, int bg, int bold, int italic);
#endif

#define EW_MOUSE_LEFT 1
#define EW_MOUSE_RIGHT 2
#define EW_MOUSE_MIDDLE 4
struct ew_mouse_event {
    int x, y;
    unsigned buttons, pressed, released;
};
int ew_mouse_present(void);
/* Returns one changed packet at a time; never blocks. */
int ew_mouse_read(struct ew_mouse_event *event);
/* Hide the software cursor before repainting, then show it afterward. */
void ew_cursor_show(int x, int y);
void ew_cursor_hide(void);
/* Zero selects arrow; nonzero selects hand. Redraws safely if visible. */
void ew_cursor_shape(int hand);

/* Coordinates and dimensions are pixels. Drawing is clipped to the screen.
 * White is 1, black is 0; in the colour mode the same argument is a colour
 * 0..15. Glyph/bitmap background -1 is transparent.
 */
/* Restrict subsequent primitives to [0,right) x [top,bottom).
 * Restore the full screen before chrome or software-cursor drawing. */
void ew_clip(int right, int top, int bottom);
/* Move the page columns (x below EW_PAGE_WIDTH) inside [top,bottom); positive delta moves pixels up.
 * Caller hides the cursor and repaints the exposed strip. No clipping applied. */
void ew_scroll(int top, int bottom, int delta);
void ew_clear(int white);
/* Colour mode only: draw width packed 4-bit pixels at (x,y), clipped like any
 * other primitive. The row starts at nibble x&1 of line[0], so bytes line up
 * with the display; a non-null mask has one bit per pixel, set where opaque. */
void ew_row4(int x, int y, const unsigned char *line, const unsigned char *mask,
             int width);
void ew_pixel(int x, int y, int white);
/* Monochrome packed row. Read width bits starting at source_bit; mask bits
 * select opaque pixels (NULL means all). Clipping preserves surrounding bits.
 * The caller supplies enough source bytes for that bit range. */
void ew_row1(int x, int y, const unsigned char *line, const unsigned char *mask,
             unsigned source_bit, int width, int inverse);
void ew_hline(int x, int y, int width, int white);
void ew_vline(int x, int y, int height, int white);
void ew_fillrect(int x, int y, int width, int height, int white);
void ew_rect(int x, int y, int width, int height, int white);

#endif
