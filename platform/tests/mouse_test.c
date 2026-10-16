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
    puts("mouse packet tests passed");
    return 0;
}
