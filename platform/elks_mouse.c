/* Optional ELKS tty mouse input. SPDX-License-Identifier: GPL-2.0-or-later */
#include "elks_platform.h"
#include "elks_mouse.h"
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <errno.h>

static int mouse_fd = -1, protocol, saved;
static int mouse_x, mouse_y;
static unsigned mouse_buttons;
static struct termios mouse_term;
static struct ew_mouse_packet packet;

void ew_mouse_init(void)
{
    const char *type = getenv("ELKSWEB_MOUSE");
    const char *port;
    struct termios term;
    if (mouse_fd >= 0 || (type && !strcmp(type, "none"))) return;
    protocol = type && !strcmp(type, "ms");
    if (type && !protocol && strcmp(type, "ps2")) return;
    port = getenv("ELKSWEB_MOUSE_PORT");
    if (!port || !*port) {
        /* Never seize a serial console or network connection by guessing. */
        if (protocol) return;
        port = "/dev/psaux";
    }
    mouse_fd = open(port, O_RDONLY | O_EXCL | O_NOCTTY | O_NONBLOCK);
    if (mouse_fd < 0) return;
    if (tcgetattr(mouse_fd, &mouse_term) < 0) goto failed;
    saved = 1;
    term = mouse_term;
    term.c_lflag &= ~(ECHO | ECHONL | ICANON | IEXTEN | ISIG);
    term.c_iflag &= ~(ICRNL | INLCR | IGNCR | ISTRIP | IXON | IXOFF | BRKINT | INPCK);
    term.c_cflag &= ~(CSIZE | PARENB);
    term.c_cflag |= CS8 | CREAD;
    term.c_cc[VMIN] = term.c_cc[VTIME] = 0;
    if (protocol) {
        cfsetispeed(&term, B1200);
        cfsetospeed(&term, B1200);
    }
    if (tcsetattr(mouse_fd, TCSANOW, &term) < 0) goto failed;
    memset(&packet, 0, sizeof(packet));
    mouse_x = EW_SCREEN_WIDTH / 2;
    mouse_y = EW_SCREEN_HEIGHT / 2;
    mouse_buttons = 0;
    return;
failed:
    ew_mouse_shutdown();
}

int ew_mouse_present(void) { return mouse_fd >= 0; }

void ew_mouse_shutdown(void)
{
    if (mouse_fd < 0) return;
    if (saved) tcsetattr(mouse_fd, TCSANOW, &mouse_term);
    close(mouse_fd);
    mouse_fd = -1;
    saved = 0;
}

int ew_mouse_read(struct ew_mouse_event *event)
{
    unsigned char byte;
    unsigned buttons;
    int n, budget = 24, dx, dy, x, y;
    if (!event || mouse_fd < 0) return 0;
    while (budget--) {
        n = read(mouse_fd, &byte, 1);
        if (n != 1) {
            if (n < 0 && errno != EAGAIN && errno != EINTR) ew_mouse_shutdown();
            return 0;
        }
        if (!ew_mouse_packet_byte(&packet, byte, protocol, &dx, &dy, &buttons)) continue;
        x = mouse_x + dx;
        y = mouse_y + dy;
        if (x < 0) x = 0;
        if (y < 0) y = 0;
        if (x >= EW_SCREEN_WIDTH) x = EW_SCREEN_WIDTH - 1;
        if (y >= EW_SCREEN_HEIGHT) y = EW_SCREEN_HEIGHT - 1;
        if (x == mouse_x && y == mouse_y && buttons == mouse_buttons) continue;
        event->x = mouse_x = x;
        event->y = mouse_y = y;
        event->pressed = buttons & ~mouse_buttons;
        event->released = mouse_buttons & ~buttons;
        event->buttons = mouse_buttons = buttons;
        return 1;
    }
    return 0;
}
