/* ELKSWeb CGA/EGA/VGA monochrome framebuffer and console backend, using the native ia16 ABI.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#include "elks_platform.h"
#include "elks_keys.h"
#include "elks_mouse.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <sys/ioctl.h>
#include <sys/time.h>
#ifndef EW_PLATFORM_TEST
#include <linuxmt/ntty.h>
#else
#include "platform_test.h"
#endif

typedef unsigned char __far *far_bytes;
#ifndef FAR_BYTES
#define FAR_BYTES(seg, off) ((far_bytes)(((unsigned long)(seg) << 16) | (unsigned)(off)))
#endif

static int console_fd = -1;
static int locked, raw_keys, term_saved, old_mode = -1;
static struct termios saved_term;
static struct ew_key_state keys;
static const char *last_error = "";
static far_bytes video = FAR_BYTES(0xb800, 0);
int ew_screen_height=200, ew_pixel_aspect=2;
static unsigned video_bytes=16384;
static int clip_right=640, clip_top, clip_bottom=480;
static unsigned long escape_started;
static int cursor_x = -1, cursor_y;
static unsigned char cursor_saved[12][2];
static unsigned char cursor_hand;

/* BIOS owns its register conventions; preserve C's segment/frame registers.
 * Only 8086 instructions are used. AL returns the active video mode for AH=0f.
 */
#ifdef EW_PLATFORM_TEST
#define bios_video ew_test_bios_video
#define video_register ew_test_video_register
#else
static unsigned bios_video(unsigned ax, unsigned *result)
{
    unsigned bx=result ? *result : 0;
    __asm__ volatile (
        "push %%ds\n\tpush %%es\n\tpush %%bp\n\tpush %%si\n\tpush %%di\n\t"
        "int $0x10\n\t"
        "pop %%di\n\tpop %%si\n\tpop %%bp\n\tpop %%es\n\tpop %%ds"
        : "+a" (ax), "+b" (bx) : : "cx", "dx", "cc", "memory");
    if (result) *result=bx;
    return ax;
}
static void video_register(unsigned port, unsigned value)
{
    __asm__ volatile ("out %%ax, %%dx" : : "a"(value), "d"(port));
}
#endif
static unsigned video_capabilities(void)
{
    unsigned bx=0, ax=bios_video(0x1a00,&bx), caps;
    if ((ax&255)==0x1a && ((bx&255)==7 || (bx&255)==8)) return 7;
    caps=(bios_video(0x0f00,0)&0x7f)==7 ? 0 : 1;
    bx=0xff10;
    bios_video(0x1200,&bx);
    /* EGA color display, at least 128KB. A 64KB or monochrome EGA cannot
     * provide the four-plane mode used here. Unsupported BIOS leaves BL=10. */
    if (!(bx&0xff00) && (bx&255)>=1 && (bx&255)<=3) caps|=3;
    return caps;
}
static int video_choose(const char *name, unsigned caps)
{
    char choice='\n', tail;
    int mode;
    if (!name) {
        if (!isatty(0)) { last_error="Use -video cga, ega or vga without a terminal"; return -1; }
        puts("ELKSWeb display (monochrome):");
        if (caps&1) puts("  1 CGA 640x200 (default)");
        if (caps&2) puts("  2 EGA 640x350");
        if (caps&4) puts("  3 VGA 640x480");
        fputs("Select 1/2/3 or Q to quit, then press Enter: ",stdout); fflush(stdout);
        if (read(0,&choice,1)!=1) return 0;
        if (choice!='\n') while (read(0,&tail,1)==1 && tail!='\n') {}
        if (choice=='q' || choice=='Q' || choice==27) return 0;
        name=choice=='\n' || choice=='1' ? "cga" : choice=='2' ? "ega" : choice=='3' ? "vga" : "";
    }
    mode=!strcmp(name,"cga") ? EW_VIDEO_CGA : !strcmp(name,"ega") ? EW_VIDEO_EGA :
         !strcmp(name,"vga") ? EW_VIDEO_VGA : -1;
    last_error="Unknown display: choose cga, ega or vga";
    if (mode<0) return -1;
    last_error="Requested graphics mode is unavailable on this adapter";
    if (!(caps&(mode==EW_VIDEO_CGA ? 1 : mode==EW_VIDEO_EGA ? 2 : 4))) return -1;
    return mode;
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

int ew_platform_init(const char *requested)
{
    struct termios term;
    const char *cooked;
    int mode;
    if (console_fd >= 0) return 0;
    mode=video_choose(requested,video_capabilities());
    if (mode<=0) return mode ? -1 : 1;
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
    old_mode = bios_video(0x0f00,0) & 0x7f;
    bios_video(mode,0);
    last_error = "BIOS could not select the requested graphics mode";
    if ((bios_video(0x0f00,0) & 0x7f) != (unsigned)mode) goto failed;
    ew_screen_height=mode==EW_VIDEO_CGA ? 200 : mode==EW_VIDEO_EGA ? 350 : 480;
    ew_pixel_aspect=mode==EW_VIDEO_CGA ? 2 : 1;
    video_bytes=mode==EW_VIDEO_CGA ? 16384U : (unsigned)ew_screen_height*80U;
    video=FAR_BYTES(mode==EW_VIDEO_CGA ? 0xb800 : 0xa000,0);
    if (mode!=EW_VIDEO_CGA) {
        /* Write identical CPU bytes to all four planes; read plane 0. */
        video_register(0x3c4,0x0f02);
        video_register(0x3ce,0x0001);
        video_register(0x3ce,0x0003);
        video_register(0x3ce,0x0004);
        video_register(0x3ce,0x0005);
        video_register(0x3ce,0xff08);
    }
    ew_clip(640, 0, EW_SCREEN_HEIGHT);
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
        bios_video((unsigned)old_mode,0);
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
    if (ew_screen_height!=200) return (unsigned)y*80U+((unsigned)x>>3);
    return ((unsigned)y & 1) * 8192U + ((unsigned)y >> 1) * 80U + ((unsigned)x >> 3);
}

void ew_clip(int right, int top, int bottom)
{
    clip_right=right;
    clip_top=top;
    clip_bottom=bottom;
}

void ew_clear(int white)
{
    unsigned n;
    unsigned char value = white ? 255 : 0;
    for (n = 0; n < video_bytes; ++n) video[n] = value;
}

void ew_pixel(int x, int y, int white)
{
    unsigned offset;
    unsigned char mask;
    if ((unsigned)x >= (unsigned)clip_right || y < clip_top ||
        y >= clip_bottom || (unsigned)y >= (unsigned)EW_SCREEN_HEIGHT) return;
    offset = scan_offset(x, y);
    mask = 0x80U >> (x & 7);
    if (white) video[offset] |= mask; else video[offset] &= ~mask;
}

void ew_hline(int x, int y, int width, int white)
{
    unsigned offset;
    unsigned char mask, value = white ? 255 : 0;
    if (width <= 0 || y < clip_top || y >= clip_bottom ||
        y < 0 || y >= EW_SCREEN_HEIGHT || x >= clip_right) return;
    if (x < 0) { if (x <= -width) return; width += x; x = 0; }
    if (width > clip_right - x) width = clip_right - x;
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
