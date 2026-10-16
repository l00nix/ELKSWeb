/* PS/2 and Microsoft serial packet readers. SPDX-License-Identifier: GPL-2.0-or-later */
#include "elks_mouse.h"
#include "elks_platform.h"

int ew_mouse_packet_byte(struct ew_mouse_packet *s, unsigned char byte,
                         int protocol, int *dx, int *dy, unsigned *buttons)
{
    unsigned char flags;
    int x, y;
    if (protocol) {
        if (byte & 0x40) { s->bytes[0] = byte; s->count = 1; return 0; }
        if (!s->count || (byte & 0x80)) { s->count = 0; return 0; }
    } else if (!s->count && !(byte & 0x08)) return 0;
    s->bytes[s->count++] = byte;
    if (s->count < 3) return 0;
    s->count = 0;
    flags = s->bytes[0];
    if (protocol) {
        x = ((flags & 3) << 6) | (s->bytes[1] & 63);
        y = ((flags & 12) << 4) | (s->bytes[2] & 63);
        if (x & 128) x -= 256;
        if (y & 128) y -= 256;
        *buttons = ((flags & 32) ? EW_MOUSE_LEFT : 0) |
                   ((flags & 16) ? EW_MOUSE_RIGHT : 0);
    } else {
        /* PS/2 deltas are signed NINE-bit values. Casting the data byte to
         * signed char incorrectly reverses large positive/negative motion.
         */
        x = s->bytes[1] - ((flags & 16) ? 256 : 0);
        y = ((flags & 32) ? 256 : 0) - s->bytes[2];
        if (flags & 64) x = 0;
        if (flags & 128) y = 0;
        *buttons = flags & 7;
    }
    *dx = x; *dy = y;
    return 1;
}
