/* Native C proportional bitmap font API. Runtime/generator: GPL-2.0-or-later.
 * Font images retain the independent Adobe/DEC license in COPYING. */
#ifndef ELKSWEB_FONT_H
#define ELKSWEB_FONT_H
#define EW_FONT_X_SCALE 2
#ifdef __ia16__
#define EW_FONT_FAR __far
#else
#define EW_FONT_FAR
#endif

/* Printable ASCII; unsupported bytes render '?', NBSP renders a space.
 * is_bold chooses independently supplied BDF bold glyphs (not synthesized).
 * y is the top of a 10-pixel line box: ascent 8, descent 2.
 * Glyphs and advances are doubled horizontally for CGA 640x200 aspect.
 */
int ew_font_char_width(unsigned char c, int is_bold);
int ew_font_height(int is_bold);
int ew_font_width(const char EW_FONT_FAR *text, unsigned count, int is_bold);
void ew_font_draw(int x, int y, unsigned char c, int fg, int bg, int is_bold);

/* Synthetic oblique: upper rows shift right by 1-2 pixels; advance unchanged. */
void ew_font_draw_italic(int x, int y, unsigned char c, int fg, int bg, int is_bold);

#endif
