#ifndef ELKSWEB_FONT_H
#define ELKSWEB_FONT_H
#define EW_FONT_X_SCALE 1
#define EW_BODY_HEIGHT 13
#define EW_SMALL_HEIGHT 10
#define EW_LARGE_HEIGHT 14
#define EW_CONTROL_HEIGHT (EW_BODY_HEIGHT+4)
#define EW_SELECT_ROW (EW_BODY_HEIGHT+2)
#ifdef __ia16__
#define EW_FONT_FAR __far
#else
#define EW_FONT_FAR
#endif

/* Public-domain fixed ASCII faces; no runtime scaling. */
int ew_font_char_width(unsigned char c, int is_bold);
int ew_font_height(int is_bold);
int ew_font_width(const char EW_FONT_FAR *text, unsigned count, int is_bold);
void ew_font_draw(int x, int y, unsigned char c, int fg, int bg, int is_bold);

/* Synthetic oblique: upper rows shift right by 1-2 pixels; advance unchanged. */
void ew_font_draw_italic(int x, int y, unsigned char c, int fg, int bg, int is_bold);

int ew_face_height(int size);
int ew_face_advance(int bold,int size);
int ew_face_width(const char EW_FONT_FAR *s,unsigned n,int bold,int size);
void ew_face_draw(int x,int y,unsigned char c,int fg,int bg,int bold,int italic,int size);
#endif
