#include <assert.h>
#include <stdio.h>
#include "elks_mouse.h"
#include "elks_platform.h"

int main(void)
{
    struct ew_mouse_packet state = {{0,0,0},0};
    int x, y;
    unsigned buttons;
    assert(!ew_mouse_packet_byte(&state, 0, 0, &x, &y, &buttons));
    assert(!ew_mouse_packet_byte(&state, 0x09, 0, &x, &y, &buttons));
    assert(!ew_mouse_packet_byte(&state, 200, 0, &x, &y, &buttons));
    assert(ew_mouse_packet_byte(&state, 1, 0, &x, &y, &buttons));
    assert(x == 200 && y == -1 && buttons == EW_MOUSE_LEFT);
    ew_mouse_packet_byte(&state, 0x3a, 0, &x, &y, &buttons);
    ew_mouse_packet_byte(&state, 1, 0, &x, &y, &buttons);
    assert(ew_mouse_packet_byte(&state, 200, 0, &x, &y, &buttons));
    assert(x == -255 && y == 56 && buttons == EW_MOUSE_RIGHT);
    ew_mouse_packet_byte(&state, 0xcc, 0, &x, &y, &buttons);
    ew_mouse_packet_byte(&state, 200, 0, &x, &y, &buttons);
    assert(ew_mouse_packet_byte(&state, 200, 0, &x, &y, &buttons));
    assert(x == 0 && y == 0 && buttons == EW_MOUSE_MIDDLE);
    /* Serial header can resynchronize a partial packet. */
    assert(!ew_mouse_packet_byte(&state, 0x40, 1, &x, &y, &buttons));
    assert(!ew_mouse_packet_byte(&state, 0x6c, 1, &x, &y, &buttons));
    assert(!ew_mouse_packet_byte(&state, 10, 1, &x, &y, &buttons));
    assert(ew_mouse_packet_byte(&state, 63, 1, &x, &y, &buttons));
    assert(x == 10 && y == -1 && buttons == EW_MOUSE_LEFT);
    /* A physical 7-bit Microsoft mouse received by an 8-bit UART can have
     * bit 7 set. It is not part of the protocol. Exercise all signed deltas,
     * both buttons, and all combinations of that unused bit in each byte. */
    {
        int want_x, want_y, mask;
        unsigned want_buttons;
        for (want_x = -128; want_x < 128; ++want_x)
        for (want_y = -128; want_y < 128; ++want_y)
        for (want_buttons = 0; want_buttons < 4; ++want_buttons)
        for (mask = 0; mask < 8; ++mask) {
            unsigned ux = (unsigned char)want_x, uy = (unsigned char)want_y;
            unsigned char header = 0x40 | (ux >> 6) | ((uy >> 6) << 2) |
                ((want_buttons & EW_MOUSE_LEFT) ? 0x20 : 0) |
                ((want_buttons & EW_MOUSE_RIGHT) ? 0x10 : 0);
            state.count = 0;
            ew_mouse_packet_byte(&state, header | ((mask & 1) ? 0x80 : 0), 1, &x, &y, &buttons);
            ew_mouse_packet_byte(&state, (ux & 63) | ((mask & 2) ? 0x80 : 0), 1, &x, &y, &buttons);
            if (!ew_mouse_packet_byte(&state, (uy & 63) | ((mask & 4) ? 0x80 : 0), 1, &x, &y, &buttons) ||
                x != want_x || y != want_y || buttons != want_buttons) {
                fprintf(stderr, "Serial packet mismatch dx=%d dy=%d buttons=%u high-bit-mask=%d\n",
                        want_x, want_y, want_buttons, mask);
                return 1;
            }
        }
    }
    puts("mouse packet tests passed");
    return 0;
}
