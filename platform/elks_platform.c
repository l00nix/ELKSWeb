/* ELKSWeb CGA/EGA monochrome and VGA/Tandy/PCjr 16-colour framebuffer and
 * console backend, using the native ia16 ABI.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#include "elks_platform.h"
#include "elks_keys.h"
#include "elks_mouse.h"
#include "elks_tandy.h"
#include "../src/version.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
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
int ew_screen_height=200,ew_pixel_aspect=2,ew_screen_width=640,ew_color;
/* Kernel-certified colour segment: 9800h Tandy, 1800h PCjr, 0 none. */
static unsigned color_segment;
static int planar_color;
static unsigned video_bytes=16384;
static int clip_right=640, clip_top, clip_bottom=480;
static unsigned long escape_started;
static int cursor_x = -1, cursor_y;
static unsigned char cursor_saved[4][24][3];
static unsigned char cursor_hand;

/* BIOS owns its register conventions; preserve C's segment/frame registers.
 * Only 8086 instructions are used. AL returns the active video mode for AH=0f.
 */
#ifdef EW_PLATFORM_TEST
#define bios_video ew_test_bios_video
#define video_register ew_test_video_register
#define color_probe ew_test_color_probe
unsigned ew_test_color_probe(void);
void ew_test_latch_copy(unsigned to, unsigned from, unsigned count);
#else
/* Mode 09h borrows conventional RAM. Only the kernel knows whether that RAM
 * was reserved at boot, so a machine name or BIOS mode test is not enough. */
#ifndef MEM_GETTANDY
#define MEM_GETTANDY 14
#endif
#ifndef MEM_GETPCJR
#define MEM_GETPCJR 15
#endif
static unsigned color_probe(void)
{
    unsigned segment = 0;
    int fd = open("/dev/kmem", O_RDONLY);
    if (fd < 0) return 0;
    if (ioctl(fd, MEM_GETTANDY, &segment) < 0 || segment != 0x9800) {
        segment = 0;
        if (ioctl(fd, MEM_GETPCJR, &segment) < 0 || segment != 0x1800) segment = 0;
    }
    close(fd);
    return segment;
}
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
    color_segment=0;
    if ((ax&255)==0x1a && ((bx&255)==7 || (bx&255)==8)) return 7;
    color_segment=color_probe();
    caps=(bios_video(0x0f00,0)&0x7f)==7 ? 0 : 1;
    bx=0xff10;
    bios_video(0x1200,&bx);
    /* EGA color display, at least 128KB. A 64KB or monochrome EGA cannot
     * provide the four-plane mode used here. Unsupported BIOS leaves BL=10. */
    if (!(bx&0xff00) && (bx&255)>=1 && (bx&255)<=3) caps|=3;
    if (color_segment) caps|=8;
    return caps;
}
static void console_puts(const char *text)
{
    write(console_fd, text, strlen(text));
}
static int video_choose(const char *name, unsigned caps)
{
    char choice[16];
    int mode, n;
    if (!name) {
        console_puts("ELKSWeb " EW_VERSION " display:\n");
        if (caps&1) console_puts(caps&8 ? "  1 CGA 640x200 monochrome\n" : "  1 CGA 640x200 (default)\n");
        if (caps&2) console_puts("  2 EGA 640x350\n");
        if (caps&4) console_puts("  3 VGA 640x480 16 colors\n  5 VGA 640x480 monochrome\n");
        if (caps&8) console_puts(color_segment==0x1800 ? "  4 PCjr 320x200 16 colors (default)\n" :
                         "  4 Tandy 320x200 16 colors (default)\n");
        console_puts(caps&8 ? "Select a listed mode or Q to quit, then press Enter: " :
              "Select 1/2/3/5 or Q to quit, then press Enter: ");
        /* ELKS canonical editing applies within one read, so read the whole
         * selection before entering raw mode. Reject and drain long lines. */
        n = read(console_fd,choice,sizeof(choice));
        if (n <= 0) return 0;
        if (choice[n-1] != '\n') {
            while ((n=read(console_fd,choice,sizeof(choice)))>0 && choice[n-1]!='\n') {}
            choice[0] = 0;
        } else if (n > 2) choice[0] = 0;
        if (choice[0]=='q' || choice[0]=='Q' || choice[0]==27) return 0;
        name=choice[0]=='\n' ? (caps&8 ? "tandy" : "cga") : choice[0]=='1' ? "cga" :
             choice[0]=='2' ? "ega" : choice[0]=='3' ? "vga" : choice[0]=='4' ? "tandy" : choice[0]=='5' ? "vga-mono" : "";
    }
    mode=!strcmp(name,"cga") ? EW_VIDEO_CGA : !strcmp(name,"ega") ? EW_VIDEO_EGA :
         (!strcmp(name,"vga") || !strcmp(name,"vga-mono")) ? EW_VIDEO_VGA :
         !strcmp(name,"tandy") || !strcmp(name,"pcjr") ? EW_VIDEO_TANDY : -1;
    last_error="Unknown display: choose cga, ega, vga, vga-mono, tandy or pcjr";
    if (mode<0) return -1;
    last_error=mode==EW_VIDEO_TANDY ?
        "Color needs the Tandy (tandyvideo=1) or PCjr kernel video reservation" :
        "Requested graphics mode is unavailable on this adapter";
    if (!(caps&(mode==EW_VIDEO_CGA ? 1 : mode==EW_VIDEO_EGA ? 2 :
                mode==EW_VIDEO_VGA ? 4 : 8))) return -1;
    planar_color=mode==EW_VIDEO_VGA && strcmp(name,"vga-mono");
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
    /* Graphics always use the local display. Use its keyboard as well,
     * regardless of the launching terminal or a serial /dev/console. */
    last_error = "Keyboard not found on /dev/tty1";
    console_fd = open("/dev/tty1", O_RDWR);
    if (console_fd < 0) return -1;
    last_error = "Console is busy or does not support graphics";
    if (ioctl(console_fd, DCGET_GRAPH, (void *)0) < 0) goto failed;
    locked = 1;
    last_error = "Cannot read console settings";
    if (tcgetattr(console_fd, &saved_term) < 0) goto failed;
    term_saved = 1;
    term = saved_term;
    if (!requested) {
        /* ELKS suppresses text and echo while graphics are locked. The
         * initial probe rejects a busy console; reacquire after the menu. */
        ioctl(console_fd, DCREL_GRAPH, (void *)0);
        locked = 0;
        term.c_lflag |= ICANON | ECHO;
        term.c_iflag = (term.c_iflag & ~(INLCR | IGNCR)) | ICRNL;
        last_error = "Cannot set console input mode";
        if (tcsetattr(console_fd, TCSANOW, &term) < 0) goto failed;
    }
    mode=video_choose(requested,video_capabilities());
    if (mode<=0) {
        ew_platform_shutdown();
        return mode ? -1 : 1;
    }
    if (!locked) {
        last_error = "Console is busy or does not support graphics";
        if (ioctl(console_fd, DCGET_GRAPH, (void *)0) < 0) goto failed;
        locked = 1;
    }
    last_error = "Cannot set console input flags";
    if (fcntl(console_fd, F_SETFL, O_RDWR | O_NONBLOCK) < 0) goto failed;
    term = saved_term;
    term.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
    term.c_iflag &= ~(ICRNL | INLCR | IGNCR | ISTRIP | IXON | IXOFF | BRKINT);
    term.c_cc[VMIN] = 0;
    term.c_cc[VTIME] = 0;
    last_error = "Cannot set console input mode";
    if (tcsetattr(console_fd, TCSAFLUSH, &term) < 0) goto failed;
    drain_input();
    cooked = getenv("ELKSWEB_COOKED_KEYS");
    /* The PCjr kernel reads its keyboard through the BIOS: there are no raw
     * scan codes to enable, only translated characters and escape sequences. */
    if (color_segment != 0x1800 && (!cooked || cooked[0] != '1')) {
        last_error = "Cannot enable raw console keyboard";
        if (ioctl(console_fd, DCSET_KRAW, (void *)0) < 0) goto failed;
        raw_keys = 1;
    }
    ew_keys_reset(&keys);
    /* The original Tandy 1000 keyboard has its own arrow/Home scan codes. */
    cooked = getenv("ELKSWEB_KEYBOARD");
    keys.tandy = cooked && *cooked ? !strcmp(cooked, "tandy") : color_segment == 0x9800;
    old_mode = bios_video(0x0f00,0) & 0x7f;
    bios_video(mode,0);
    last_error = "BIOS could not select the requested graphics mode";
    if ((bios_video(0x0f00,0) & 0x7f) != (unsigned)mode) goto failed;
    ew_color=mode==EW_VIDEO_TANDY || planar_color;
    ew_screen_width=mode==EW_VIDEO_TANDY ? EW_TANDY_WIDTH : 640;
    ew_screen_height=mode==EW_VIDEO_CGA || mode==EW_VIDEO_TANDY ? 200 : mode==EW_VIDEO_EGA ? 350 : 480;
    ew_pixel_aspect=mode==EW_VIDEO_CGA ? 2 : 1;
    if (mode==EW_VIDEO_TANDY) ew_tandy_video=FAR_BYTES(color_segment,0);
    video_bytes=mode==EW_VIDEO_CGA ? 16384U : (unsigned)ew_screen_height*80U;
    video=FAR_BYTES(mode==EW_VIDEO_CGA ? 0xb800 : 0xa000,0);
    if (mode!=EW_VIDEO_CGA && mode!=EW_VIDEO_TANDY) {
        /* Write identical CPU bytes to all four planes; read plane 0. */
        video_register(0x3c4,0x0f02);
        video_register(0x3ce,0x0001);
        video_register(0x3ce,0x0003);
        video_register(0x3ce,0x0004);
        video_register(0x3ce,0x0005);
        video_register(0x3ce,0xff08);
    }
    ew_clip(EW_SCREEN_WIDTH, 0, EW_SCREEN_HEIGHT);
    ew_clear(ew_color ? EW_WHITE : 1);
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
    /* A cancelled selector still has a blocking descriptor. */
    if (term_saved && fcntl(console_fd, F_SETFL, O_RDWR | O_NONBLOCK) >= 0)
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

/* All monochrome framebuffers fit inside one segment. Bulk fills use the
 * same 8086 string operations as the colour backend; partial edge bytes are
 * still masked by ew_hline. Preserve ES for the caller. */
static void fill_video(unsigned to, unsigned char value, unsigned count)
{
#ifdef __ia16__
    unsigned segment = (unsigned)((unsigned long)video >> 16);
    to += (unsigned)(unsigned long)video;
    __asm__ volatile (
        "push %%es\n\tmov %%dx, %%es\n\tcld\n\t"
        "shr $1, %%cx\n\trep stosw\n\tjnc 1f\n\tstosb\n1:\tpop %%es"
        : "+D"(to), "+c"(count) : "a"((unsigned)value * 0x0101U), "d"(segment)
        : "cc", "memory");
#else
    while (count--) video[to++] = value;
#endif
}

/* Mode 12h uses RGBI bits in four independent 38400-byte planes.
 * Read and write the same plane for every read/modify/write operation.
 * All callers select explicitly; no register-state cache can become stale. */
static void select_plane(unsigned plane)
{
    video_register(0x3c4, ((1U << plane) << 8) | 2);
    video_register(0x3ce, (plane << 8) | 4);
}

/* Each byte read loads all four VGA latches. Write mode 1 then stores
 * those latches together. Use byte string moves: a word read would replace
 * the first byte's latches before its destination write. DS/ES are preserved;
 * each row fits one segment and source/destination rows do not overlap. */
static void latch_copy(unsigned to, unsigned from, unsigned count)
{
#ifdef EW_PLATFORM_TEST
    ew_test_latch_copy(to, from, count);
#elif defined(__ia16__)
    unsigned segment = (unsigned)((unsigned long)video >> 16);
    to += (unsigned)(unsigned long)video;
    from += (unsigned)(unsigned long)video;
    __asm__ volatile (
        "push %%ds\n\tpush %%es\n\tmov %%ax, %%ds\n\tmov %%ax, %%es\n\t"
        "cld\n\trep movsb\n\tpop %%es\n\tpop %%ds"
        : "+S"(from), "+D"(to), "+c"(count) : "a"(segment) : "cc", "memory");
#else
    while (count--) video[to++] = video[from++];
#endif
}

/* Scroll the byte-aligned content viewport, preserving chrome and padding.
 * Positive delta moves pixels up. Row order protects overlapping source data,
 * including odd scanline shifts across the CGA interleaved banks. */
void ew_scroll(int top, int bottom, int delta)
{
    int y, end, step;
    unsigned from, to, n;
    if (top < 0 || bottom > EW_SCREEN_HEIGHT || top >= bottom || !delta ||
        delta >= bottom - top || delta <= top - bottom) return;
    if (ew_color && !planar_color) { ew_tandy_scroll(top, bottom, delta, EW_PAGE_WIDTH >> 1); return; }
    if (planar_color) {
        video_register(0x3c4, 0x0f02); /* Enable writes to all planes. */
        video_register(0x3ce, 0x0105); /* Write mode 1, read mode 0. */
    }
    if (delta > 0) { y=top; end=bottom-delta; step=1; }
    else { y=bottom-1; end=top-delta-1; step=-1; }
    for (; y!=end; y+=step) {
        from=scan_offset(0,y+delta);
        to=scan_offset(0,y);
        if (planar_color) latch_copy(to, from, EW_PAGE_WIDTH >> 3);
        else for (n=0; n<(unsigned)(EW_PAGE_WIDTH >> 3); ++n) video[to+n]=video[from+n];
    }
    if (planar_color) video_register(0x3ce, 0x0005); /* Restore CPU-data writes. */
}

void ew_clip(int right, int top, int bottom)
{
    clip_right=right;
    clip_top=top;
    clip_bottom=bottom;
}

void ew_clear(int white)
{
    unsigned char value = white ? 255 : 0;
    unsigned plane;
    if (ew_color && !planar_color) { ew_tandy_clear(white); return; }
    if (planar_color) {
        for (plane=0; plane<4; ++plane) {
            select_plane(plane);
            fill_video(0, white & (1U << plane) ? 255 : 0, video_bytes);
        }
        return;
    }
    fill_video(0, value, video_bytes);
}

void ew_pixel(int x, int y, int white)
{
    unsigned offset, plane;
    unsigned char mask;
    if ((unsigned)x >= (unsigned)clip_right || y < clip_top ||
        y >= clip_bottom || (unsigned)y >= (unsigned)EW_SCREEN_HEIGHT) return;
    if (ew_color && !planar_color) { ew_tandy_pixel(x, y, white); return; }
    offset = scan_offset(x, y);
    mask = 0x80U >> (x & 7);
    for (plane=0; plane<(planar_color ? 4U : 1U); ++plane) {
        if (planar_color) select_plane(plane);
        if (planar_color ? !!(white & (1U << plane)) : white) video[offset] |= mask;
        else video[offset] &= ~mask;
    }
}

void ew_row1(int x, int y, const unsigned char *line, const unsigned char *mask,
             unsigned source_bit, int width, int inverse)
{
    unsigned offset, phase, take, shift, index;
    unsigned char bits, cover, edge;
    if (ew_color || width <= 0 || x >= clip_right || y < clip_top ||
        y >= clip_bottom || y < 0 || y >= EW_SCREEN_HEIGHT) return;
    if (x < 0) {
        if (x <= -width) return;
        source_bit += (unsigned)-x; width += x; x = 0;
    }
    if (width > clip_right - x) width = clip_right - x;
    offset = scan_offset(x, y);
    phase = (unsigned)x & 7;
    while (width > 0) {
        take = 8 - phase;
        if (take > (unsigned)width) take = (unsigned)width;
        shift = source_bit & 7; index = source_bit >> 3;
        bits = (unsigned char)(line[index] << shift);
        cover = mask ? (unsigned char)(mask[index] << shift) : 255;
        /* Read a second byte only if the requested bits cross its boundary. */
        if (shift + take > 8) {
            bits |= line[index + 1] >> (8 - shift);
            if (mask) cover |= mask[index + 1] >> (8 - shift);
        }
        if (inverse) bits ^= 255;
        edge = (unsigned char)((255U >> phase) & (255U << (8 - phase - take)));
        cover = (cover >> phase) & edge;
        bits >>= phase;
        if (cover == 255) video[offset] = bits;
        else if (cover) video[offset] = (video[offset] & ~cover) | (bits & cover);
        ++offset; source_bit += take; width -= take; phase = 0;
    }
}

static void mono_hline(int x, int y, int width, int white)
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
    if (width >= 8) {
        unsigned count = (unsigned)width >> 3;
        fill_video(offset, value, count);
        offset += count;
        width &= 7;
    }
    if (width) {
        mask = (unsigned char)(255U << (8 - width));
        if (white) video[offset] |= mask; else video[offset] &= ~mask;
    }
}

void ew_hline(int x, int y, int width, int color)
{
    unsigned plane;
    if (ew_color && !planar_color) {
        if (width<=0 || y<clip_top || y>=clip_bottom || y<0 ||
            y>=EW_SCREEN_HEIGHT || x>=clip_right) return;
        if (x<0) { if (x<=-width) return; width+=x; x=0; }
        if (width>clip_right-x) width=clip_right-x;
        ew_tandy_hline(x,y,width,color);
        return;
    }
    for (plane=0; plane<(planar_color ? 4U : 1U); ++plane) {
        if (planar_color) select_plane(plane);
        mono_hline(x,y,width,planar_color ? !!(color & (1U << plane)) : color);
    }
}

void ew_row4(int x, int y, const unsigned char *line, const unsigned char *mask,
             int width)
{
    if (!ew_color || x < 0 || x >= clip_right || y < clip_top || y >= clip_bottom ||
        y < 0 || y >= EW_SCREEN_HEIGHT) return;
    if (width > clip_right - x) width = clip_right - x;
    if (width > 0 && !planar_color) ew_tandy_row(x, y, line, mask, (unsigned)width);
    else if (width > 0) {
        unsigned plane, i, n, offset, take, phase;
        unsigned char bits, cover, pixel;
        for (plane=0; plane<4; ++plane) {
            select_plane(plane);
            for (i=0; i<(unsigned)width; i+=take) {
                phase=(x+i)&7;
                take=8-phase;
                if (take>(unsigned)width-i) take=width-i;
                bits=cover=0;
                for (n=0; n<take; ++n) {
                    unsigned at=i+n+(x&1);
                    unsigned char bit=0x80U>>(phase+n);
                    if (mask && !(mask[(i+n)>>3] & (0x80U>>((i+n)&7)))) continue;
                    pixel=at&1 ? line[at>>1]&15 : line[at>>1]>>4;
                    cover|=bit;
                    if (pixel & (1U<<plane)) bits|=bit;
                }
                offset=scan_offset(x+i,y);
                if (cover==255) video[offset]=bits;
                else if (cover) video[offset]=(video[offset]&~cover)|bits;
            }
        }
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
    int row, col;
    unsigned offset, plane;
    if (cursor_x < 0) return;
    if (ew_color && !planar_color) { ew_tandy_cursor_hide(); cursor_x = -1; return; }
    for (plane=0; plane<(planar_color ? 4U : 1U); ++plane) {
        if (planar_color) select_plane(plane);
        for (row = 0; row < 24 && cursor_y + row < EW_SCREEN_HEIGHT; ++row) {
            offset = scan_offset(cursor_x, cursor_y + row);
            for (col = 0; col < 3 && (cursor_x >> 3) + col < 80; ++col)
                video[offset + col] = cursor_saved[plane][row][col];
        }
    }
    cursor_x = -1;
}

void ew_cursor_show(int x, int y)
{
    /* Original ELKSWeb arrow and pointing hand, drawn for this backend.
     * Double each bitmap pixel for a visible 16-column/24-row pointer.
     * The raised index finger begins at the logical pointer position. */
#include "cursor_bitmap.h"
    int row, col;
    unsigned offset, plane;
    const unsigned char *bits, *line;
    if (x == cursor_x && y == cursor_y) return;
    ew_cursor_hide();
    if (x < 0 || x >= EW_SCREEN_WIDTH || y < 0 || y >= EW_SCREEN_HEIGHT) return;
    cursor_x = x; cursor_y = y;
    if (ew_color && !planar_color) { ew_tandy_cursor_show(x, y, cursor_hand); return; }
    bits = &cursor_bitmap[cursor_hand][x & 7][0][0];
    for (plane=0; plane<(planar_color ? 4U : 1U); ++plane) {
        if (planar_color) select_plane(plane);
        for (row = 0; row < 24 && y + row < EW_SCREEN_HEIGHT; ++row) {
            offset = scan_offset(x, y + row);
            line = bits + (row >> 1) * 6;
            for (col = 0; col < 3 && (x >> 3) + col < 80; ++col) {
                cursor_saved[plane][row][col] = video[offset + col];
                video[offset + col] = (cursor_saved[plane][row][col] & ~line[col]) | line[col + 3];
            }
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
