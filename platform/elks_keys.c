/* Native XT/AT set-1 and ELKS terminal key decoding.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#include "elks_platform.h"
#include "elks_keys.h"
#include <string.h>

void ew_keys_reset(struct ew_key_state *s)
{
    memset(s, 0, sizeof(*s));
}

static int navigation(unsigned char scan)
{
    switch (scan) {
    case 0x47: return EW_KEY_HOME;
    case 0x48: return EW_KEY_UP;
    case 0x49: return EW_KEY_PGUP;
    case 0x4b: return EW_KEY_LEFT;
    case 0x4d: return EW_KEY_RIGHT;
    case 0x4f: return EW_KEY_END;
    case 0x50: return EW_KEY_DOWN;
    case 0x51: return EW_KEY_PGDN;
    case 0x53: return EW_KEY_DELETE;
    default: return 0;
    }
}

int ew_keys_scancode(struct ew_key_state *s, unsigned char byte)
{
    static const char plain[] =
        "\0\0331234567890-=\b\tqwertyuiop[]\r\0asdfghjkl;'`\0\\zxcvbnm,./\0*\0 ";
    static const char shifted[] =
        "\0\033!@#$%^&*()_+\b\tQWERTYUIOP{}\r\0ASDFGHJKL:\"~\0|ZXCVBNM<>?\0*\0 ";
    static const char keypad[] = "789-456+1230.";
    unsigned char scan, release, ext, bit;
    int c, use_shift;

    if (s->pause_left) { --s->pause_left; return 0; }
    if (byte == 0xe1) { s->pause_left = 5; return 0; }
    if (byte == 0xe0) { s->extended = 1; return 0; }
    ext = s->extended;
    s->extended = 0;
    release = byte & 0x80;
    scan = byte & 0x7f;

    /* E0 2a/36 are synthetic PrintScreen/keypad shift bytes. */
    if (!ext && (scan == 0x2a || scan == 0x36)) {
        bit = scan == 0x2a ? 1 : 2;
        if (release) s->shifts &= ~bit; else s->shifts |= bit;
        return 0;
    }
    if (scan == 0x1d) {
        bit = ext ? 2 : 1;
        if (release) s->ctrls &= ~bit; else s->ctrls |= bit;
        return 0;
    }
    if (!ext && (scan == 0x3a || scan == 0x45)) {
        bit = scan == 0x3a ? 1 : 2;
        if (release) s->locks_down &= ~bit;
        else if (!(s->locks_down & bit)) {
            if (scan == 0x3a) s->caps ^= 1; else s->num ^= 1;
            s->locks_down |= bit;
        }
        return 0;
    }
    if (release) return 0;
    if (ext) {
        if (scan == 0x1c) return EW_KEY_ENTER;
        if (scan == 0x35) return '/';
        return navigation(scan);
    }
    if (scan >= 0x3b && scan <= 0x44) return EW_KEY_F1 + scan - 0x3b;
    if (scan >= 0x47 && scan <= 0x53) {
        if (scan == 0x4a || scan == 0x4e || (s->num ^ !!s->shifts))
            return keypad[scan - 0x47];
        return navigation(scan);
    }
    if (scan == 0x0f && s->shifts) return EW_KEY_BACKTAB;
    if (scan >= sizeof(plain) - 1) return 0;
    c = (unsigned char)plain[scan];
    use_shift = !!s->shifts;
    if (c >= 'a' && c <= 'z') use_shift ^= s->caps;
    if (use_shift) c = (unsigned char)shifted[scan];
    if (s->ctrls && ((c >= '@' && c <= '_') || (c >= 'a' && c <= 'z')))
        c &= 31;
    return c;
}

static int escape_key(unsigned char c)
{
    if (c >= 'a' && c <= 'j') return EW_KEY_F1 + c - 'a';
    switch (c) {
    case 'A': return EW_KEY_UP;
    case 'B': return EW_KEY_DOWN;
    case 'C': return EW_KEY_RIGHT;
    case 'D': return EW_KEY_LEFT;
    case 'H': return EW_KEY_HOME;
    case 'F': return EW_KEY_END;
    case 'Z': return EW_KEY_BACKTAB;
    case '5': return EW_KEY_PGUP;
    case '6': return EW_KEY_PGDN;
    default: return 0;
    }
}

int ew_keys_tty(struct ew_key_state *s, unsigned char c)
{
    unsigned char state = s->escape_state;
    int result = 0;
    if (!state) {
        if (c == 27) { s->escape_state = 1; return 0; }
        if (c == '\n') return EW_KEY_ENTER;
        if (c == 127) return EW_KEY_BACKSPACE;
        return c;
    }
    if (state == 1 && (c == '[' || c == 'O')) {
        s->escape_state = c == '[' ? 2 : 3;
        s->digits = 0;
        s->parameter = 0;
        return 0;
    }
    if (state == 2 && c >= '0' && c <= '9') {
        if (++s->digits > 3) { s->escape_state = 0; return 0; }
        s->parameter = s->parameter * 10 + c - '0';
        return 0;
    }
    s->escape_state = 0;
    if (state == 2 && c == '~') {
        switch (s->parameter) {
        case 1: case 7: result = EW_KEY_HOME; break;
        case 4: case 8: result = EW_KEY_END; break;
        case 3: result = EW_KEY_DELETE; break;
        case 5: result = EW_KEY_PGUP; break;
        case 6: result = EW_KEY_PGDN; break;
        case 11: result = EW_KEY_F1; break;
        case 12: result = EW_KEY_F2; break;
        case 13: result = EW_KEY_F3; break;
        case 14: result = EW_KEY_F4; break;
        case 15: result = EW_KEY_F5; break;
        case 17: result = EW_KEY_F6; break;
        case 18: result = EW_KEY_F7; break;
        case 19: result = EW_KEY_F8; break;
        case 20: result = EW_KEY_F9; break;
        case 21: result = EW_KEY_F10; break;
        }
    } else if (state == 3 && c >= 'P' && c <= 'S') {
        result = EW_KEY_F1 + c - 'P';
    } else {
        result = escape_key(c);
    }
    return result;
}

int ew_keys_timeout(struct ew_key_state *s)
{
    int result = s->escape_state == 1 ? EW_KEY_ESC : 0;
    s->escape_state = 0;
    return result;
}
