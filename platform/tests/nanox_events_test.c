/* Exercise the real Nano-X event adapter with deterministic server events.
 * Link elks_nanox.c with unused-section elimination and Nano-X headers. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <nano-X.h>
#include "../elks_platform.h"

static GR_EVENT events[16];
static unsigned count, next, polls;

void GrCheckNextEvent(GR_EVENT *event)
{
    ++polls;
    if (next < count) *event = events[next++];
    else {
        memset(event, 0, sizeof(*event));
        event->type = GR_EVENT_TYPE_NONE;
    }
}

static GR_EVENT *push(GR_EVENT_TYPE type)
{
    GR_EVENT *event;
    assert(count < sizeof(events) / sizeof(events[0]));
    event = &events[count++];
    memset(event, 0, sizeof(*event));
    event->type = type;
    return event;
}

static void queue_reset(void)
{
    assert(next == count);
    count = next = polls = 0;
}

int main(void)
{
    GR_EVENT *event;
    struct ew_mouse_event mouse;
    const char *controls = "lrdvtgbfnwih";
    unsigned i;

    /* Cooked PC-98/ELKS bytes and modifier-bearing server events must agree.
     * Ordinary letters, Tab and Backspace must retain their meanings. */
    for (i = 0; controls[i]; ++i) {
        event = push(GR_EVENT_TYPE_KEY_DOWN);
        event->keystroke.ch = controls[i];
        event->keystroke.modifiers = MWKMOD_CTRL;
        assert(ew_getkey() == EW_CTRL(controls[i]));
        event = push(GR_EVENT_TYPE_KEY_DOWN);
        event->keystroke.ch = controls[i] - 'a' + 'A';
        event->keystroke.modifiers = MWKMOD_CTRL | MWKMOD_SHIFT;
        assert(ew_getkey() == EW_CTRL(controls[i]));
        event = push(GR_EVENT_TYPE_KEY_DOWN);
        event->keystroke.ch = EW_CTRL(controls[i]);
        assert(ew_getkey() == EW_CTRL(controls[i]));
        event = push(GR_EVENT_TYPE_KEY_DOWN);
        event->keystroke.ch = controls[i];
        assert(ew_getkey() == controls[i]);
        queue_reset();
    }

    /* Normal dispatch preserves down/up order and never overwrites an unread
     * click with a later event. */
    event = push(GR_EVENT_TYPE_BUTTON_DOWN);
    event->button.buttons = MWBUTTON_L;
    event->button.x = 12;
    event->button.y = 34;
    push(GR_EVENT_TYPE_BUTTON_UP);
    assert(ew_getkey() == EW_KEY_NONE && polls == 1);
    assert(ew_getkey() == EW_KEY_NONE && polls == 1);
    assert(ew_mouse_read(&mouse));
    assert(mouse.x == 12 && mouse.y == 34);
    assert(mouse.buttons == EW_MOUSE_LEFT && mouse.pressed == EW_MOUSE_LEFT);
    assert(!mouse.released);
    assert(ew_getkey() == EW_KEY_NONE && polls == 2);
    assert(ew_mouse_read(&mouse));
    assert(!mouse.buttons && !mouse.pressed && mouse.released == EW_MOUSE_LEFT);
    assert(!ew_mouse_read(&mouse));
    queue_reset();

    /* Entering a transfer with a pending event must not latch out Escape.
     * Both queued motion and button events are discarded, not replayed. */
    event = push(GR_EVENT_TYPE_MOUSE_POSITION);
    event->mouse.x = 45;
    assert(ew_getkey() == EW_KEY_NONE);
    event = push(GR_EVENT_TYPE_BUTTON_DOWN);
    event->button.buttons = MWBUTTON_L;
    event = push(GR_EVENT_TYPE_MOUSE_POSITION);
    event->mouse.buttons = MWBUTTON_L;
    push(GR_EVENT_TYPE_BUTTON_UP);
    event = push(GR_EVENT_TYPE_KEY_DOWN);
    event->keystroke.ch = 27;
    assert(ew_nanox_progress_key() == EW_KEY_ESC);
    assert(next == count && !ew_mouse_read(&mouse));
    assert(!ew_platform_closed());
    queue_reset();

    /* Exposure survives transfer polling and is acknowledged once. */
    push(GR_EVENT_TYPE_MOUSE_POSITION);
    push(GR_EVENT_TYPE_EXPOSURE);
    assert(ew_nanox_progress_key() == EW_KEY_NONE);
    assert(ew_platform_exposed());
    assert(!ew_platform_exposed());
    assert(!ew_mouse_read(&mouse));
    queue_reset();

    /* A held button remains held after discarded transfer input; the first
     * normal motion cannot synthesize another button press. */
    event = push(GR_EVENT_TYPE_BUTTON_DOWN);
    event->button.buttons = MWBUTTON_L;
    assert(ew_nanox_progress_key() == EW_KEY_NONE);
    event = push(GR_EVENT_TYPE_MOUSE_POSITION);
    event->mouse.buttons = MWBUTTON_L;
    assert(ew_getkey() == EW_KEY_NONE);
    assert(ew_mouse_read(&mouse));
    assert(mouse.buttons == EW_MOUSE_LEFT && !mouse.pressed && !mouse.released);
    queue_reset();

    /* A close request cannot be mistaken for a modal Escape cancellation:
     * the application can inspect the latched flag independently. */
    push(GR_EVENT_TYPE_MOUSE_POSITION);
    push(GR_EVENT_TYPE_CLOSE_REQ);
    assert(ew_nanox_progress_key() == EW_KEY_ESC);
    assert(ew_platform_closed() && ew_platform_closed());
    assert(!ew_mouse_read(&mouse));
    assert(ew_getkey() == EW_KEY_NONE);
    assert(ew_platform_closed());
    puts("Nano-X event tests passed");
    return 0;
}
