/* ELKSWeb display and input over the Nano-X client protocol.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#ifdef ELKSWEB_NANOX
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <nano-X.h>
#include "elks_platform.h"
#include "../font/font.h"
#include "../src/version.h"

int ew_screen_width, ew_screen_height, ew_pixel_aspect = 1, ew_color;
static GR_WINDOW_ID window;
static GR_GC_ID gc;
static int clip_right, clip_top, clip_bottom, color = -1;
static int exposed, closed, pending_mouse;
static const char *error;
static struct ew_mouse_event mouse;
static unsigned buttons;
static const GR_COLOR palette[16] = {
    GR_RGB(0,0,0), GR_RGB(0,0,170), GR_RGB(0,170,0), GR_RGB(0,170,170),
    GR_RGB(170,0,0), GR_RGB(170,0,170), GR_RGB(170,85,0), GR_RGB(170,170,170),
    GR_RGB(85,85,85), GR_RGB(85,85,255), GR_RGB(85,255,85), GR_RGB(85,255,255),
    GR_RGB(255,85,85), GR_RGB(255,85,255), GR_RGB(255,255,85), GR_RGB(255,255,255)
};

/* Opt-in file diagnostics must not write to the PC-98 text plane. Preserve
 * errno so a failed logging attempt cannot replace a connection error. */
static void lifecycle_log(const char *stage, int err)
{
    const char *path = getenv("ELKSWEB_NX_LOG");
    int saved_errno = errno;
    FILE *file;
    if (!path || !*path) return;
    file = fopen(path, "a");
    if (file) {
        if (err >= 0) fprintf(file, "webnx: %s errno=%d\n", stage, err);
        else fprintf(file, "webnx: %s\n", stage);
        fclose(file);
    }
    errno = saved_errno;
}

static void close_connection(void)
{
    lifecycle_log("GrClose begin", -1);
    GrClose();
    lifecycle_log("GrClose end", -1);
}

static void foreground(int ink)
{
    ink = ew_color ? ink & 15 : ink ? 15 : 0;
    if (ink == color) return;
    color = ink;
    GrSetGCForeground(gc, palette[ink]);
}

int ew_platform_init(const char *mode)
{
    GR_SCREEN_INFO info;
    if (mode && strcmp(mode, "nanox") && strcmp(mode, "pc98")) {
        error = "this build uses Nano-X; select -video nanox or -video pc98";
        return -1;
    }
    lifecycle_log("GrOpen begin", -1);
    if (GrOpen() < 0) {
        lifecycle_log("GrOpen failed", errno);
        error = "cannot connect to Nano-X; check server availability and free memory";
        return -1;
    }
    lifecycle_log("connected", -1);
    GrGetScreenInfo(&info);
    if (info.cols < 320 || info.cols > 640 || info.rows < 200 || info.rows > 480) {
        error = "unsupported Nano-X desktop size";
        close_connection();
        return -1;
    }
    ew_screen_width = info.cols;
    ew_screen_height = info.rows;
    ew_color = info.ncolors >= 16;
    ew_clip(ew_screen_width, 0, ew_screen_height);
    window = GrNewWindowEx(GR_WM_PROPS_NODECORATE, EW_APP_NAME, GR_ROOT_WINDOW_ID,
                           0, 0, ew_screen_width, ew_screen_height, GR_RGB(0,0,0));
    gc = GrNewGC();
    if (!window || !gc) {
        error = "cannot create Nano-X window";
        close_connection();
        return -1;
    }
    GrSetGCUseBackground(gc, GR_FALSE);
    /* The initial draw covers the new window; avoid queuing a duplicate
     * map exposure, but handle all subsequent exposures normally. */
    GrMapWindow(window);
    GrSelectEvents(window, GR_EVENT_MASK_EXPOSURE | GR_EVENT_MASK_KEY_DOWN |
                   GR_EVENT_MASK_MOUSE_POSITION | GR_EVENT_MASK_BUTTON_DOWN |
                   GR_EVENT_MASK_BUTTON_UP | GR_EVENT_MASK_CLOSE_REQ);
    GrSetFocus(window);
    lifecycle_log("window ready", -1);
    return 0;
}

const char *ew_platform_error(void)
{
    return error;
}

void ew_platform_shutdown(void)
{
    close_connection();
}

int ew_platform_exposed(void)
{
    int result = exposed;
    exposed = 0;
    return result;
}

int ew_platform_closed(void) { return closed; }

static int translate(GR_KEY key, GR_KEYMOD modifiers)
{
    if (key >= MWKEY_F1 && key <= MWKEY_F10)
        return EW_KEY_F1 + key - MWKEY_F1;
    switch (key) {
    case MWKEY_UP: return EW_KEY_UP;
    case MWKEY_DOWN: return EW_KEY_DOWN;
    case MWKEY_LEFT: return EW_KEY_LEFT;
    case MWKEY_RIGHT: return EW_KEY_RIGHT;
    case MWKEY_PAGEUP: return EW_KEY_PGUP;
    case MWKEY_PAGEDOWN: return EW_KEY_PGDN;
    case MWKEY_HOME: return EW_KEY_HOME;
    case MWKEY_END: return EW_KEY_END;
    case MWKEY_DELETE: return EW_KEY_DELETE;
    case MWKEY_TAB:
        return modifiers & MWKMOD_SHIFT ? EW_KEY_BACKTAB : EW_KEY_TAB;
    default:
        /* Servers may send either ASCII control bytes or a letter with CTRL.
         * Preserve both forms, including Tab/Backspace and existing Ctrl-L. */
        if ((modifiers & MWKMOD_CTRL) &&
            ((key >= 'a' && key <= 'z') || (key >= 'A' && key <= 'Z')))
            return EW_CTRL(key);
        return key < 128 ? key : EW_KEY_NONE;
    }
}

static void mouse_event(int x, int y, GR_BUTTON state)
{
    unsigned next = 0;
    if (state & MWBUTTON_L) next |= EW_MOUSE_LEFT;
    if (state & MWBUTTON_R) next |= EW_MOUSE_RIGHT;
    if (state & MWBUTTON_M) next |= EW_MOUSE_MIDDLE;
    mouse.x = x;
    mouse.y = y;
    mouse.buttons = next;
    mouse.pressed = next & ~buttons;
    mouse.released = buttons & ~next;
    buttons = next;
    pending_mouse = 1;
}

int ew_getkey(void)
{
    GR_EVENT event;
    if (pending_mouse) return EW_KEY_NONE;
    /* Complete the event exchange before issuing more drawing requests.
     * Timeout polling leaves a GetNextEvent reply outstanding. On ELKS's
     * small Unix sockets, queued replies can fill the server-to-client pipe
     * while a redraw fills the other direction, blocking both processes in
     * write(). CheckNextEvent returns NONE when no event is queued and does
     * not leave an asynchronous reply behind. */
    GrCheckNextEvent(&event);
    switch (event.type) {
    case GR_EVENT_TYPE_EXPOSURE: exposed = 1; break;
    case GR_EVENT_TYPE_CLOSE_REQ:
        closed = 1;
        return EW_KEY_ESC;
    case GR_EVENT_TYPE_KEY_DOWN:
        return translate(event.keystroke.ch, event.keystroke.modifiers);
    case GR_EVENT_TYPE_MOUSE_POSITION:
        mouse_event(event.mouse.x, event.mouse.y, event.mouse.buttons);
        break;
    case GR_EVENT_TYPE_BUTTON_DOWN:
    case GR_EVENT_TYPE_BUTTON_UP:
        mouse_event(event.button.x, event.button.y, event.button.buttons);
        break;
    }
    return EW_KEY_NONE;
}

/* Transfers do not dispatch mouse actions. Consume their events here so a
 * pending pointer update cannot block the following Escape or close request,
 * or replay a click against the newly loaded page. Keep the button state. */
int ew_nanox_progress_key(void)
{
    int key;
    do {
        pending_mouse = 0;
        key = ew_getkey();
    } while (pending_mouse);
    return key;
}

int ew_mouse_read(struct ew_mouse_event *event)
{
    if (!pending_mouse) return 0;
    *event = mouse;
    pending_mouse = 0;
    return 1;
}

/* Nano-X owns, draws and clips the pointer. */
void ew_cursor_show(int x, int y) { (void)x; (void)y; }
void ew_cursor_hide(void) {}
void ew_cursor_shape(int hand) { (void)hand; }

void ew_clip(int right, int top, int bottom)
{
    clip_right = right < ew_screen_width ? right : ew_screen_width;
    clip_top = top > 0 ? top : 0;
    clip_bottom = bottom < ew_screen_height ? bottom : ew_screen_height;
}

void ew_clear(int ink)
{
    foreground(ink);
    GrFillRect(window, gc, 0, 0, ew_screen_width, ew_screen_height);
}

void ew_fillrect(int x, int y, int width, int height, int ink)
{
    if (width <= 0 || height <= 0 || x >= clip_right || y >= clip_bottom) return;
    if (x < 0) { if (x <= -width) return; width += x; x = 0; }
    if (y < clip_top) {
        if (y <= clip_top - height) return;
        height -= clip_top - y;
        y = clip_top;
    }
    if (width > clip_right-x) width = clip_right-x;
    if (height > clip_bottom-y) height = clip_bottom-y;
    foreground(ink);
    GrFillRect(window, gc, x, y, width, height);
}

void ew_hline(int x, int y, int width, int ink) { ew_fillrect(x,y,width,1,ink); }
void ew_vline(int x, int y, int height, int ink) { ew_fillrect(x,y,1,height,ink); }
void ew_pixel(int x, int y, int ink) { ew_fillrect(x,y,1,1,ink); }

void ew_rect(int x, int y, int width, int height, int ink)
{
    long right = (long)x + width - 1, bottom = (long)y + height - 1;
    if (width <= 0 || height <= 0) return;
    ew_hline(x, y, width, ink);
    ew_vline(x, y, height, ink);
    if (bottom >= 0 && bottom < ew_screen_height) ew_hline(x, (int)bottom, width, ink);
    if (right >= 0 && right < ew_screen_width) ew_vline((int)right, y, height, ink);
}

void ew_row1(int x, int y, const unsigned char *line, const unsigned char *mask,
             unsigned bit, int width, int inverse)
{
    int i, count, ink;
    GR_BITMAP bitmap[40];
    if (width <= 0 || x >= clip_right || y < clip_top || y >= clip_bottom) return;
    if (x < 0) { if (x <= -width) return; bit += (unsigned)-x; width += x; x = 0; }
    if (width > clip_right-x) width = clip_right-x;
    for (ink = 0; ink <= 1; ++ink) {
        memset(bitmap, 0, ((width+15)/16)*sizeof(*bitmap));
        count = 0;
        for (i = 0; i < width; ++i) {
            unsigned b = bit+i, m = 0x80U >> (b&7);
            if ((!mask || (mask[b>>3]&m)) && (!!(line[b>>3]&m) ^ !!inverse) == ink) {
                bitmap[i>>4] |= 0x8000U >> (i&15);
                count++;
            }
        }
        if (count) {
            foreground(ink);
            GrBitmap(window, gc, x, y, width, 1, bitmap);
        }
    }
}

void ew_row4(int x, int y, const unsigned char *line, const unsigned char *mask,
             int width)
{
    int i, start = 0, last = -1;
    unsigned phase = x & 1;
    if (width <= 0 || x < 0 || x >= clip_right || y < clip_top || y >= clip_bottom) return;
    if (width > clip_right-x) width = clip_right-x;
    for (i=0; i<width; ++i) {
        unsigned n = phase+i;
        /* Packed pixels are phased to x; opacity starts at bit zero. */
        int ink = (!mask || (mask[i>>3] & (0x80U >> (i&7))))
                   ? (line[n>>1] >> ((n&1) ? 0 : 4)) & 15 : -1;
        if (ink == last) continue;
        if (last >= 0) ew_hline(x+start, y, i-start, last);
        last = ink;
        start = i;
    }
    if (last >= 0) ew_hline(x+start, y, width-start, last);
}

/* Keep using ordinary clipped Nano-X drawing. On PC-98 the ELKS server's
 * overlapping screen copies are not safe for downward scrolling, and its
 * small clip implementation cannot report hidden blit sources. Batch text
 * instead of copying potentially stale pixels from the visible screen. */
#define TEXT_WORDS 4
#define TEXT_WIDTH (TEXT_WORDS * 16)
static GR_BITMAP text_bits[EW_LARGE_HEIGHT * TEXT_WORDS];
static int text_batch, text_x, text_y, text_width, text_rows, text_ink;

static void flush_text(void)
{
    int stride, row, word;
    if (!text_width) return;
    stride = (text_width + 15) >> 4;
    if (stride != TEXT_WORDS)
        for (row = 1; row < text_rows; ++row)
            for (word = 0; word < stride; ++word)
                text_bits[row * stride + word] = text_bits[row * TEXT_WORDS + word];
    foreground(text_ink);
    GrBitmap(window, gc, text_x, text_y, text_width, text_rows, text_bits);
    text_width = 0;
}

void ew_nanox_text_begin(void) { text_batch = 1; }
void ew_nanox_text_end(void)
{
    flush_text();
    text_batch = 0;
}

static void append_glyph(int x, int y, int width, int rows, int ink,
                         const GR_BITMAP *bitmap)
{
    int offset, shift, row;
    GR_BITMAP *out;
    if (text_width && (y != text_y || rows != text_rows || ink != text_ink ||
                       x < text_x || x + width - text_x > TEXT_WIDTH))
        flush_text();
    if (!text_width) {
        text_x = x;
        text_y = y;
        text_rows = rows;
        text_ink = ink;
        memset(text_bits, 0, rows * TEXT_WORDS * sizeof(*text_bits));
    }
    offset = x - text_x;
    if (offset + width > text_width) text_width = offset + width;
    out = text_bits + (offset >> 4);
    shift = offset & 15;
    for (row = 0; row < rows; ++row, out += TEXT_WORDS) {
        unsigned bits = bitmap[row];
        *out |= bits >> shift;
        if (shift + width > 16) out[1] |= bits << (16 - shift);
    }
}

void ew_nanox_glyph(int x, int y, const unsigned char *glyph, int advance,
                    int height, int fg, int bg, int bold, int italic)
{
    GR_BITMAP bitmap[EW_LARGE_HEIGHT];
    int row, skip, rows = height;
    int width = advance + (italic ? (height-1)/6 : 0);
    if (bg >= 0) {
        flush_text();
        ew_fillrect(x, y, advance, height, bg);
    }
    if (y < clip_top) {
        skip = clip_top-y;
        if (skip >= height) return;
    } else skip = 0;
    if (y + height > clip_bottom) rows = clip_bottom-y;
    if (rows <= skip || x >= clip_right || x <= -width) return;
    for (row=skip; row<rows; ++row) {
        unsigned bits = (unsigned)glyph[row] << 8;
        if (bold) bits |= bits >> 1;
        bits &= 0xffffU << (16-advance);
        if (italic) bits >>= (height-1-row)/6;
        if (x < 0) bits <<= -x;
        bitmap[row-skip] = bits;
    }
    if (x < 0) { width += x; x = 0; }
    if (width > clip_right-x) width = clip_right-x;
    if (text_batch && bg < 0) {
        /* The final right clip can cut a bitmap word. Do not let the unused
         * bits become visible when ORed into the larger bitmap. */
        if (width < advance + (italic ? (height-1)/6 : 0))
            for (row = 0; row < rows-skip; ++row)
                bitmap[row] &= 0xffffU << (16-width);
        append_glyph(x, y+skip, width, rows-skip, fg, bitmap);
    } else {
        foreground(fg);
        GrBitmap(window, gc, x, y+skip, width, rows-skip, bitmap);
    }
}
#endif
