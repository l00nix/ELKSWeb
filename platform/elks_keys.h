/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef ELKSWEB_KEYS_H
#define ELKSWEB_KEYS_H

struct ew_key_state {
    unsigned char shifts, ctrls, caps, num, locks_down, extended, pause_left;
    unsigned char escape_state, digits;
    unsigned int parameter;
};

void ew_keys_reset(struct ew_key_state *state);
int ew_keys_scancode(struct ew_key_state *state, unsigned char byte);
int ew_keys_tty(struct ew_key_state *state, unsigned char byte);
int ew_keys_timeout(struct ew_key_state *state);

#endif
