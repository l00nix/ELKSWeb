/* Native fixed bitmap fonts. Runtime GPL-2.0-or-later; glyphs public domain. */
#include "font.h"
#include "../platform/elks_platform.h"
#include "fixed_data.h"
int ew_face_height(int size) { return size==0 ? EW_SMALL_HEIGHT : size==2 ? EW_LARGE_HEIGHT : EW_BODY_HEIGHT; }
int ew_face_advance(int bold,int size) { return size==2 || (size==0 && bold) ? 7 : 6; }
int ew_face_width(const char EW_FONT_FAR *s,unsigned n,int bold,int size) {
    unsigned width=0,advance=ew_face_advance(bold,size);
    while(n-- && *s++) { if(width>32767U-advance)return 32767; width+=advance; }
    return width;
}
void ew_face_draw(int x,int y,unsigned char c,int fg,int bg,int bold,int italic,int size) {
    unsigned index=size ? (size==2 ? 3 : 1)+!!bold : 0;
    int row,col,height=ew_face_height(size),advance=ew_face_advance(bold,size),skew;
    const unsigned char *glyph;
    unsigned char bits;
    if(x < -10 || x>=EW_SCREEN_WIDTH || y<=-height || y>=EW_SCREEN_HEIGHT)return;
    if(c==160)c=' ';
    if(c<32 || c>126)c='?';
    glyph=faces[index]+(c-32)*height;
    if(bg>=0)ew_fillrect(x,y,advance,height,bg);
    for(row=0;row<height;row++) {
        bits=glyph[row]; if(size==0 && bold)bits|=bits>>1;
        skew=italic ? (height-1-row)/6 : 0;
        for(col=0;col<advance;col++,bits<<=1)
            if(bits&128)ew_pixel(x+col+skew,y+row,fg);
    }
}
int ew_font_char_width(unsigned char c,int bold) { (void)c;return ew_face_advance(bold,2); }
int ew_font_height(int bold) { (void)bold;return EW_LARGE_HEIGHT; }
int ew_font_width(const char EW_FONT_FAR *s,unsigned n,int bold) {return ew_face_width(s,n,bold,2);}
void ew_font_draw(int x,int y,unsigned char c,int fg,int bg,int bold) {ew_face_draw(x,y,c,fg,bg,bold,0,2);}
void ew_font_draw_italic(int x,int y,unsigned char c,int fg,int bg,int bold) {ew_face_draw(x,y,c,fg,bg,bold,1,2);}
