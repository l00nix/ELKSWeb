/* ELKSWeb native ELKS display/input interface. SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef ELKSWEB_PLATFORM_H
#define ELKSWEB_PLATFORM_H

#define EW_SCREEN_WIDTH 640
#define EW_SCREEN_HEIGHT 200
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

/* Requires a PC CGA-compatible display and an ELKS console. Returns 0 or -1.
 * The default uses ELKS's scancode keyboard. Set ELKSWEB_COOKED_KEYS=1
 * for firmware configured with BIOS keyboard polling (fewer keys available).
 */
int ew_platform_init(void);
const char *ew_platform_error(void);
void ew_platform_shutdown(void);
int ew_getkey(void);                 /* Nonblocking; zero means no key. */

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
 * White is 1, black is 0. Glyph/bitmap background -1 is transparent.
 */
void ew_clear(int white);
void ew_pixel(int x, int y, int white);
void ew_hline(int x, int y, int width, int white);
void ew_vline(int x, int y, int height, int white);
void ew_fillrect(int x, int y, int width, int height, int white);
void ew_rect(int x, int y, int width, int height, int white);
void ew_bitmap(int x, int y, int width, int height,
               const unsigned char *bits, int stride, int fg, int bg);
void ew_glyph(int x, int y, unsigned char character, int fg, int bg);
void ew_glyph_scaled(int x, int y, unsigned char character, int fg, int bg, int scale);
void ew_text(int x, int y, const char *text, int fg, int bg);

#endif
