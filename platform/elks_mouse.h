/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef ELKSWEB_MOUSE_H
#define ELKSWEB_MOUSE_H

struct ew_mouse_packet {
    unsigned char bytes[3], count;
};
/* Protocol values: 0 = PS/2, 1 = Microsoft serial. */
int ew_mouse_packet_byte(struct ew_mouse_packet *state, unsigned char byte,
                         int protocol, int *dx, int *dy, unsigned *buttons);
void ew_mouse_init(void);
void ew_mouse_shutdown(void);

#endif
