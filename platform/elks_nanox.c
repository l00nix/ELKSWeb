/* ELKSWeb display and input over the Nano-X client protocol.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#ifdef ELKSWEB_NANOX
#include <string.h>
#include <nano-X.h>
#include "elks_platform.h"

int ew_screen_width, ew_screen_height, ew_pixel_aspect = 1, ew_color;
static GR_WINDOW_ID window;
static GR_GC_ID gc;
static int clip_right, clip_top, clip_bottom, color = -1;
static int exposed, pending_mouse;
static const char *error;
static struct ew_mouse_event mouse;
static unsigned buttons;
static const GR_COLOR palette[16] = {
    GR_RGB(0,0,0), GR_RGB(0,0,170), GR_RGB(0,170,0), GR_RGB(0,170,170),
    GR_RGB(170,0,0), GR_RGB(170,0,170), GR_RGB(170,85,0), GR_RGB(170,170,170),
    GR_RGB(85,85,85), GR_RGB(85,85,255), GR_RGB(85,255,85), GR_RGB(85,255,255),
    GR_RGB(255,85,85), GR_RGB(255,85,255), GR_RGB(255,255,85), GR_RGB(255,255,255)
};

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
    if (GrOpen() < 0) {
        error = "cannot connect to Nano-X (start nxstart first)";
        return -1;
    }
    GrGetScreenInfo(&info);
    if (info.cols < 320 || info.cols > 640 || info.rows < 200 || info.rows > 480) {
        error = "unsupported Nano-X desktop size";
        GrClose();
        return -1;
    }
    ew_screen_width = info.cols;
    ew_screen_height = info.rows;
    ew_color = info.ncolors >= 16;
    ew_clip(ew_screen_width, 0, ew_screen_height);
    window = GrNewWindowEx(GR_WM_PROPS_NODECORATE, "ELKSWeb", GR_ROOT_WINDOW_ID,
                           0, 0, ew_screen_width, ew_screen_height, GR_RGB(0,0,0));
    gc = GrNewGC();
    if (!window || !gc) {
        error = "cannot create Nano-X window";
        GrClose();
        return -1;
    }
    GrSetGCUseBackground(gc, GR_FALSE);
    GrSelectEvents(window, GR_EVENT_MASK_EXPOSURE | GR_EVENT_MASK_KEY_DOWN |
                   GR_EVENT_MASK_MOUSE_POSITION | GR_EVENT_MASK_BUTTON_DOWN |
                   GR_EVENT_MASK_BUTTON_UP | GR_EVENT_MASK_CLOSE_REQ);
    GrMapWindow(window);
    GrSetFocus(window);
    return 0;
}

const char *ew_platform_error(void)
{
    return error;
}

void ew_platform_shutdown(void)
{
    GrClose();
}

int ew_platform_exposed(void)
{
    int result = exposed;
    exposed = 0;
    return result;
}

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
        if ((key == 'l' || key == 'L') && (modifiers & MWKMOD_CTRL))
            return 12;
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
    GrGetNextEventTimeout(&event, GR_TIMEOUT_POLL);
    switch (event.type) {
    case GR_EVENT_TYPE_EXPOSURE: exposed = 1; break;
    case GR_EVENT_TYPE_CLOSE_REQ: return EW_KEY_ESC;
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

void ew_nanox_glyph(int x, int y, const unsigned char *glyph, int advance,
                    int height, int fg, int bg, int bold, int italic)
{
    GR_BITMAP bitmap[14];
    int row, skip, rows = height;
    int width = advance + (italic ? (height-1)/6 : 0);
    if (bg >= 0) ew_fillrect(x, y, advance, height, bg);
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
    foreground(fg);
    GrBitmap(window, gc, x, y+skip, width, rows-skip, bitmap);
}
#endif
