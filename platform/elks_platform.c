/* ELKSWeb CGA framebuffer and console backend, using the native ia16 ABI.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#include "elks_platform.h"
#include "elks_keys.h"
#include "elks_mouse.h"
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <sys/ioctl.h>
#include <sys/time.h>
#include <linuxmt/ntty.h>

typedef unsigned char __far *far_bytes;
#define FAR_BYTES(seg, off) ((far_bytes)(((unsigned long)(seg) << 16) | (unsigned)(off)))

static int console_fd = -1;
static int locked, raw_keys, term_saved, old_mode = -1;
static struct termios saved_term;
static struct ew_key_state keys;
static const char *last_error = "";
static far_bytes video = FAR_BYTES(0xb800, 0);
static far_bytes font = FAR_BYTES(0xf000, 0xfa6e);
static unsigned long escape_started;
static int cursor_x = -1, cursor_y;
static unsigned char cursor_saved[12][2];
static unsigned char cursor_hand;

/* BIOS owns its register conventions; preserve C's segment/frame registers.
 * Only 8086 instructions are used. AL returns the active video mode for AH=0f.
 */
static unsigned bios_video(unsigned ax)
{
    __asm__ volatile (
        "push %%ds\n\tpush %%es\n\tpush %%bp\n\tpush %%si\n\tpush %%di\n\t"
        "int $0x10\n\t"
        "pop %%di\n\tpop %%si\n\tpop %%bp\n\tpop %%es\n\tpop %%ds"
        : "+a" (ax) : : "bx", "cx", "dx", "cc", "memory");
    return ax;
}

static far_bytes bios_font(void)
{
    unsigned offset, segment;
    /* EGA/VGA returns its 8x8 ROM font. Earlier CGA BIOSes leave the
     * supplied original-PC ROM address intact when function 11 is absent.
     */
    __asm__ volatile (
        "push %%ds\n\tpush %%es\n\tpush %%bp\n\tpush %%si\n\tpush %%di\n\t"
        "mov $0xf000, %%ax\n\tmov %%ax, %%es\n\tmov $0xfa6e, %%bp\n\t"
        "mov $0x1130, %%ax\n\tmov $0x0300, %%bx\n\tint $0x10\n\t"
        "mov %%es, %%dx\n\tmov %%bp, %%ax\n\t"
        "pop %%di\n\tpop %%si\n\tpop %%bp\n\tpop %%es\n\tpop %%ds"
        : "=a" (offset), "=d" (segment) : : "bx", "cx", "cc", "memory");
    return FAR_BYTES(segment, offset);
}

static unsigned long milliseconds(void)
{
    struct timeval now;
    gettimeofday(&now, 0);
    return (unsigned long)now.tv_sec * 1000UL + now.tv_usec / 1000;
}

const char *ew_platform_error(void) { return last_error; }

static void drain_input(void)
{
    unsigned char discarded[16];
    int count = 16;
    /* ELKS currently treats TCSETSF like TCSETS; explicitly discard queued
     * bytes when switching between translated input and raw scan codes.
     */
    while (count-- && read(console_fd, discarded, sizeof(discarded)) > 0) {}
}

int ew_platform_init(void)
{
    struct termios term;
    const char *cooked;
    if (console_fd >= 0) return 0;
    last_error = "Cannot open the controlling console";
    console_fd = open("/dev/tty", O_RDWR | O_NONBLOCK);
    if (console_fd < 0) return -1;
    last_error = "Cannot read console settings";
    if (tcgetattr(console_fd, &saved_term) < 0) goto failed;
    term_saved = 1;
    term = saved_term;
    term.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
    term.c_iflag &= ~(ICRNL | INLCR | IGNCR | ISTRIP | IXON | IXOFF | BRKINT);
    term.c_cc[VMIN] = 0;
    term.c_cc[VTIME] = 0;
    last_error = "Cannot set console input mode";
    if (tcsetattr(console_fd, TCSAFLUSH, &term) < 0) goto failed;
    drain_input();
    last_error = "Console is busy or does not support graphics";
    if (ioctl(console_fd, DCGET_GRAPH, (void *)0) < 0) goto failed;
    locked = 1;
    cooked = getenv("ELKSWEB_COOKED_KEYS");
    if (!cooked || cooked[0] != '1') {
        last_error = "Cannot enable raw console keyboard";
        if (ioctl(console_fd, DCSET_KRAW, (void *)0) < 0) goto failed;
        raw_keys = 1;
    }
    ew_keys_reset(&keys);
    old_mode = bios_video(0x0f00) & 0x7f;
    bios_video(0x0006);
    last_error = "BIOS could not select CGA 640x200 graphics";
    if ((bios_video(0x0f00) & 0x7f) != 6) goto failed;
    font = bios_font();
    ew_clear(1);
    ew_mouse_init();
    last_error = "";
    return 0;
failed:
    ew_platform_shutdown();
    return -1;
}

void ew_platform_shutdown(void)
{
    int had_video = old_mode >= 0;
    if (console_fd < 0) return;
    ew_cursor_hide();
    ew_mouse_shutdown();
    if (raw_keys) {
        ioctl(console_fd, DCREL_KRAW, (void *)0);
        raw_keys = 0;
    }
    drain_input();
    if (old_mode >= 0) {
        bios_video((unsigned)old_mode);
        old_mode = -1;
    }
    if (locked) {
        ioctl(console_fd, DCREL_GRAPH, (void *)0);
        locked = 0;
    }
    if (term_saved) {
        tcsetattr(console_fd, TCSAFLUSH, &saved_term);
        term_saved = 0;
    }
    /* Synchronize the kernel's logical cursor with the cleared BIOS screen. */
    if (had_video) write(console_fd, "\033[H\033[2J", 7);
    close(console_fd);
    console_fd = -1;
}

int ew_getkey(void)
{
    unsigned char byte;
    int key, count = 32;
    if (console_fd < 0) return 0;
    while (count-- && read(console_fd, &byte, 1) == 1) {
        if (raw_keys) {
            key = ew_keys_scancode(&keys, byte);
        } else {
            if (!keys.escape_state && byte == 27) escape_started = milliseconds();
            key = ew_keys_tty(&keys, byte);
        }
        if (key) return key;
    }
    if (!raw_keys && keys.escape_state && milliseconds() - escape_started >= 100UL)
        return ew_keys_timeout(&keys);
    return 0;
}

static unsigned scan_offset(int x, int y)
{
    return ((unsigned)y & 1) * 8192U + ((unsigned)y >> 1) * 80U + ((unsigned)x >> 3);
}

void ew_clear(int white)
{
    unsigned n;
    unsigned char value = white ? 255 : 0;
    for (n = 0; n < 16384U; ++n) video[n] = value;
}

void ew_pixel(int x, int y, int white)
{
    unsigned offset;
    unsigned char mask;
    if ((unsigned)x >= EW_SCREEN_WIDTH || (unsigned)y >= EW_SCREEN_HEIGHT) return;
    offset = scan_offset(x, y);
    mask = 0x80U >> (x & 7);
    if (white) video[offset] |= mask; else video[offset] &= ~mask;
}

void ew_hline(int x, int y, int width, int white)
{
    unsigned offset;
    unsigned char mask, value = white ? 255 : 0;
    if (width <= 0 || y < 0 || y >= EW_SCREEN_HEIGHT || x >= EW_SCREEN_WIDTH) return;
    if (x < 0) { if (x <= -width) return; width += x; x = 0; }
    if (width > EW_SCREEN_WIDTH - x) width = EW_SCREEN_WIDTH - x;
    offset = scan_offset(x, y);
    if (x & 7) {
        int count = 8 - (x & 7);
        if (count > width) count = width;
        mask = (unsigned char)((255U >> (x & 7)) &
                              (255U << (8 - (x & 7) - count)));
        if (white) video[offset] |= mask; else video[offset] &= ~mask;
        ++offset;
        width -= count;
    }
    while (width >= 8) { video[offset++] = value; width -= 8; }
    if (width) {
        mask = (unsigned char)(255U << (8 - width));
        if (white) video[offset] |= mask; else video[offset] &= ~mask;
    }
}

void ew_vline(int x, int y, int height, int white)
{
    if (height <= 0 || x < 0 || x >= EW_SCREEN_WIDTH || y >= EW_SCREEN_HEIGHT) return;
    if (y < 0) { if (y <= -height) return; height += y; y = 0; }
    if (height > EW_SCREEN_HEIGHT - y) height = EW_SCREEN_HEIGHT - y;
    while (height--) ew_pixel(x, y++, white);
}

void ew_fillrect(int x, int y, int width, int height, int white)
{
    if (height <= 0 || y >= EW_SCREEN_HEIGHT) return;
    if (y < 0) { if (y <= -height) return; height += y; y = 0; }
    if (height > EW_SCREEN_HEIGHT - y) height = EW_SCREEN_HEIGHT - y;
    while (height--) ew_hline(x, y++, width, white);
}

void ew_rect(int x, int y, int width, int height, int white)
{
    long right = (long)x + width - 1, bottom = (long)y + height - 1;
    if (width <= 0 || height <= 0) return;
    ew_hline(x, y, width, white);
    ew_vline(x, y, height, white);
    if (bottom >= 0 && bottom < EW_SCREEN_HEIGHT) ew_hline(x, (int)bottom, width, white);
    if (right >= 0 && right < EW_SCREEN_WIDTH) ew_vline((int)right, y, height, white);
}

void ew_bitmap(int x, int y, int width, int height,
               const unsigned char *bits, int stride, int fg, int bg)
{
    int row, col, sx = 0, sy = 0, color;
    long right = (long)x + width, bottom = (long)y + height;
    if (!bits || stride <= 0 || width <= 0 || height <= 0 ||
        x >= EW_SCREEN_WIDTH || y >= EW_SCREEN_HEIGHT || right <= 0 || bottom <= 0) return;
    if (x < 0) { sx = -x; x = 0; }
    if (y < 0) { sy = -y; y = 0; }
    if (right > EW_SCREEN_WIDTH) right = EW_SCREEN_WIDTH;
    if (bottom > EW_SCREEN_HEIGHT) bottom = EW_SCREEN_HEIGHT;
    for (row = y; row < bottom; ++row, ++sy) {
        const unsigned char *source = bits + (unsigned)sy * stride;
        for (col = x; col < right; ++col) {
            unsigned bit = sx + col - x;
            color = source[bit >> 3] & (0x80U >> (bit & 7)) ? fg : bg;
            if (color >= 0) ew_pixel(col, row, color);
        }
    }
}

void ew_glyph(int x, int y, unsigned char character, int fg, int bg)
{
    int row, col;
    unsigned char bits;
    if (x <= -8 || x >= EW_SCREEN_WIDTH || y <= -8 || y >= EW_SCREEN_HEIGHT) return;
    /* Original CGA ROM contains only the lower 128 glyphs. */
    if (font == FAR_BYTES(0xf000, 0xfa6e) && character >= 128) character = '?';
    for (row = 0; row < 8; ++row) {
        bits = font[(unsigned)character * 8 + row];
        if (!(x & 7) && x >= 0 && x < EW_SCREEN_WIDTH && y + row >= 0 && y + row < EW_SCREEN_HEIGHT) {
            unsigned offset = scan_offset(x, y + row);
            if (bg < 0) {
                if (fg) video[offset] |= bits; else video[offset] &= ~bits;
            } else {
                video[offset] = (fg ? bits : 0) | (bg ? (unsigned char)~bits : 0);
            }
        } else {
            for (col = 0; col < 8; ++col) {
                int color = bits & (0x80U >> col) ? fg : bg;
                if (color >= 0) ew_pixel(x + col, y + row, color);
            }
        }
    }
}

void ew_text(int x, int y, const char *text, int fg, int bg)
{
    if (!text) return;
    while (*text && x < EW_SCREEN_WIDTH) {
        ew_glyph(x, y, (unsigned char)*text++, fg, bg);
        if (x > EW_SCREEN_WIDTH - 8) break;
        x += 8;
    }
}

void ew_glyph_scaled(int x, int y, unsigned char character, int fg, int bg, int scale)
{
    int row, col, color;
    unsigned char bits;
    if (scale == 1) { ew_glyph(x, y, character, fg, bg); return; }
    if (scale != 2 || x <= -16 || x >= EW_SCREEN_WIDTH ||
        y <= -16 || y >= EW_SCREEN_HEIGHT) return;
    if (font == FAR_BYTES(0xf000, 0xfa6e) && character >= 128) character = '?';
    for (row = 0; row < 8; ++row) {
        bits = font[(unsigned)character * 8 + row];
        for (col = 0; col < 8; ++col) {
            color = bits & (0x80U >> col) ? fg : bg;
            if (color >= 0) ew_fillrect(x + col * 2, y + row * 2, 2, 2, color);
        }
    }
}

void ew_cursor_hide(void)
{
    int row;
    unsigned offset;
    if (cursor_x < 0) return;
    for (row = 0; row < 12 && cursor_y + row < EW_SCREEN_HEIGHT; ++row) {
        offset = scan_offset(cursor_x, cursor_y + row);
        video[offset] = cursor_saved[row][0];
        if ((cursor_x >> 3) < 79) video[offset + 1] = cursor_saved[row][1];
    }
    cursor_x = -1;
}

void ew_cursor_show(int x, int y)
{
    /* Original ELKSWeb arrow and pointing hand, drawn for this backend.
     * Both fit the same eight-column/twelve-row saved-background footprint.
     * The raised index finger begins at the logical pointer position. */
    static const unsigned char outline[2][12] = {
        {0x80,0xc0,0xe0,0xf0,0xf8,0xfc,0xfe,0xff,0xf8,0xd8,0x8c,0x0c},
        {0xc0,0xe0,0xe0,0xe0,0xfc,0xfe,0xff,0xff,0xff,0x7e,0x3e,0x3c}
    };
    static const unsigned char interior[2][12] = {
        {0,0,0x40,0x60,0x70,0x78,0x7c,0x60,0x60,0x40,0,0},
        {0,0x40,0x40,0x40,0x40,0x54,0x54,0x7e,0x3e,0x3c,0x1c,0}
    };
    int row, col;
    unsigned offset;
    ew_cursor_hide();
    if (x < 0 || x >= EW_SCREEN_WIDTH || y < 0 || y >= EW_SCREEN_HEIGHT) return;
    cursor_x = x; cursor_y = y;
    for (row = 0; row < 12 && y + row < EW_SCREEN_HEIGHT; ++row) {
        offset = scan_offset(x, y + row);
        cursor_saved[row][0] = video[offset];
        if ((x >> 3) < 79) cursor_saved[row][1] = video[offset + 1];
        for (col = 0; col < 8; ++col) {
            if (outline[cursor_hand][row] & (0x80U >> col))
                ew_pixel(x + col, y + row, !!(interior[cursor_hand][row] & (0x80U >> col)));
        }
    }
}

void ew_cursor_shape(int hand)
{
    int x, y;
    hand = !!hand;
    if (cursor_hand == hand) return;
    x = cursor_x; y = cursor_y;
    ew_cursor_hide();
    cursor_hand = hand;
    if (x >= 0) ew_cursor_show(x, y);
}
