/* Fixed 6x13 body face from public-domain X.Org fonts. */
#ifndef ELKSWEB_BODY_FONT_H
#define ELKSWEB_BODY_FONT_H
#include "font.h"
int ew_body_char_width(unsigned char c,int bold);
int ew_body_height(int bold);
int ew_body_width(const char EW_FONT_FAR *text,unsigned count,int bold);
void ew_body_draw(int x,int y,unsigned char c,int fg,int bg,int bold,int italic);
/* Fixed 6x10 small face. */
int ew_small_char_width(unsigned char c,int bold);
int ew_small_height(int bold);
int ew_small_width(const char EW_FONT_FAR *text,unsigned count,int bold);
void ew_small_draw(int x,int y,unsigned char c,int fg,int bg,int bold,int italic);
/* Fixed cells: small 6x10, body 6x13, large 7x14. */
int ew_mono_char_width(unsigned char c,int bold,int size);
int ew_mono_height(int size);
int ew_mono_width(const char EW_FONT_FAR *text,unsigned count,int bold,int size);
void ew_mono_draw(int x,int y,unsigned char c,int fg,int bg,int bold,int italic,int size);
#endif
