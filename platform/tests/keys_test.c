/* Host regression tests for the actual native key decoder. */
#include <assert.h>
#include <stdio.h>
#include "elks_platform.h"
#include "elks_keys.h"

static int sequence(struct ew_key_state *s, const char *text)
{
    int key = 0;
    while (*text) key = ew_keys_tty(s, (unsigned char)*text++);
    return key;
}

int main(void)
{
    struct ew_key_state s;
    ew_keys_reset(&s);
    assert(ew_keys_scancode(&s, 0x1e) == 'a');
    assert(ew_keys_scancode(&s, 0x2a) == 0);
    assert(ew_keys_scancode(&s, 0x1e) == 'A');
    assert(ew_keys_scancode(&s, 0x0f) == EW_KEY_BACKTAB);
    assert(ew_keys_scancode(&s, 0x36) == 0);
    assert(ew_keys_scancode(&s, 0xaa) == 0);
    assert(ew_keys_scancode(&s, 0x1e) == 'A'); /* Other shift still held. */
    assert(ew_keys_scancode(&s, 0xb6) == 0);
    assert(ew_keys_scancode(&s, 0x0f) == EW_KEY_TAB);
    ew_keys_scancode(&s, 0x3a);
    ew_keys_scancode(&s, 0x3a); /* CapsLock repeat must not toggle again. */
    assert(ew_keys_scancode(&s, 0x1e) == 'A');
    ew_keys_scancode(&s, 0xba);
    ew_keys_scancode(&s, 0x3a);
    assert(ew_keys_scancode(&s, 0x1e) == 'a');
    ew_keys_scancode(&s, 0x1d);
    assert(ew_keys_scancode(&s, 0x26) == 12); /* Ctrl+L */
    ew_keys_scancode(&s, 0x9d);
    assert(ew_keys_scancode(&s, 0x3c) == EW_KEY_F2);
    assert(ew_keys_scancode(&s, 0x40) == EW_KEY_F6);
    assert(ew_keys_scancode(&s, 0xe0) == 0);
    assert(ew_keys_scancode(&s, 0x48) == EW_KEY_UP);
    assert(ew_keys_scancode(&s, 0xe0) == 0);
    assert(ew_keys_scancode(&s, 0xc8) == 0);
    ew_keys_scancode(&s, 0x45);
    assert(ew_keys_scancode(&s, 0x48) == '8');
    ew_keys_scancode(&s, 0xe0);
    assert(ew_keys_scancode(&s, 0x48) == EW_KEY_UP); /* NumLock doesn't change arrow. */
    ew_keys_scancode(&s, 0xe0);
    ew_keys_scancode(&s, 0x2a); /* Ignore PrintScreen fake shift. */
    assert(s.shifts == 0);
    assert(ew_keys_scancode(&s, 0x01) == EW_KEY_ESC);
    assert(ew_keys_scancode(&s, 0x1c) == EW_KEY_ENTER);
    assert(ew_keys_scancode(&s, 0x0e) == EW_KEY_BACKSPACE);

    ew_keys_reset(&s);
    assert(sequence(&s, "\033b") == EW_KEY_F2); /* ELKS scancode translated. */
    assert(sequence(&s, "\033[f") == EW_KEY_F6); /* ELKS BIOS translated. */
    assert(sequence(&s, "\033[A") == EW_KEY_UP);
    assert(sequence(&s, "\033[6~") == EW_KEY_PGDN);
    assert(sequence(&s, "\033[Z") == EW_KEY_BACKTAB);
    assert(sequence(&s, "\033[3~") == EW_KEY_DELETE);
    assert(sequence(&s, "\033OP") == EW_KEY_F1);
    assert(sequence(&s, "\033[17~") == EW_KEY_F6);
    assert(sequence(&s, "\033") == 0);
    assert(ew_keys_timeout(&s) == EW_KEY_ESC);
    assert(sequence(&s, "\033[") == 0);
    assert(ew_keys_timeout(&s) == 0); /* A partial escape must not quit. */
    assert(sequence(&s, "\033[9999A") == 'A'); /* Bounded malformed CSI. */
    assert(sequence(&s, "x") == 'x');
    puts("keyboard decoder tests passed");
    return 0;
}
