/* Shared fixed-font entry points. SPDX-License-Identifier: GPL-2.0-or-later */
#include "body_font.h"
int ew_body_char_width(unsigned char c,int bold) {(void)c;return ew_face_advance(bold,1);}
int ew_body_height(int bold) {(void)bold;return EW_BODY_HEIGHT;}
int ew_body_width(const char EW_FONT_FAR *s,unsigned n,int bold) {return ew_face_width(s,n,bold,1);}
void ew_body_draw(int x,int y,unsigned char c,int fg,int bg,int bold,int italic) {ew_face_draw(x,y,c,fg,bg,bold,italic,1);}
int ew_small_char_width(unsigned char c,int bold) {(void)c;return ew_face_advance(bold,0);}
int ew_small_height(int bold) {(void)bold;return EW_SMALL_HEIGHT;}
int ew_small_width(const char EW_FONT_FAR *s,unsigned n,int bold) {return ew_face_width(s,n,bold,0);}
void ew_small_draw(int x,int y,unsigned char c,int fg,int bg,int bold,int italic) {ew_face_draw(x,y,c,fg,bg,bold,italic,0);}
int ew_mono_char_width(unsigned char c,int bold,int size) {(void)c;return ew_face_advance(bold,size);}
int ew_mono_height(int size) {return ew_face_height(size);}
int ew_mono_width(const char EW_FONT_FAR *s,unsigned n,int bold,int size) {return ew_face_width(s,n,bold,size);}
void ew_mono_draw(int x,int y,unsigned char c,int fg,int bg,int bold,int italic,int size) {ew_face_draw(x,y,c,fg,bg,bold,italic,size);}
