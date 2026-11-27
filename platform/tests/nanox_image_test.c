/* Exercise scaled GIF drawing through the real Nano-X row implementation.
 * Pixel correctness (including scaling phase) has a separate independent
 * coverage oracle in tests/test_pixels_scaling.py. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <nano-X.h>
#include "../../src/images.c"

struct ew_document ew_doc;
static unsigned bitmaps, fills, pixels;
static unsigned char source[80*80], cover[80*80];

void GrSetGCForeground(GR_GC_ID gc, GR_COLOR color)
{ (void)gc; (void)color; }
void GrFillRect(GR_DRAW_ID id, GR_GC_ID gc, GR_COORD x, GR_COORD y,
                GR_SIZE w, GR_SIZE h)
{ (void)id; (void)gc; (void)x; (void)y; (void)w; (void)h; ++fills; }
void GrBitmap(GR_DRAW_ID id, GR_GC_ID gc, GR_COORD x, GR_COORD y,
              GR_SIZE w, GR_SIZE h, GR_BITMAP *bitmap)
{
    int col, row, stride=(w+15)/16;
    (void)id; (void)gc;
    assert(x>=0 && x+w<=640 && y>=32 && y+h<=180);
    assert(h==1);
    ++bitmaps;
    for(row=0;row<h;++row) for(col=0;col<w;++col)
        if(bitmap[row*stride+col/16] & (0x8000U>>(col&15))) ++pixels;
}

int main(void)
{
    struct ew_run run;
    unsigned i, expected, cases=0;
    int inverse, transparent, strip, enlarged;
    memset(&run,0,sizeof(run));
    run.kind=EW_RUN_IMAGE;
    image_count=1;
    images[0].height=80;
    images[0].pixels=source;
    ew_screen_width=640; ew_screen_height=200; ew_pixel_aspect=2; ew_color=0;
    ew_clip(640,32,180);
    for(enlarged=0;enlarged<2;++enlarged) {
        images[0].width=enlarged ? 160 : 640;
        images[0].stride=images[0].width/8;
        run.n=320; run.w=40;
        for(i=0;i<sizeof(source);++i) { source[i]=i&1 ? 0x33 : 0xcc; cover[i]=0xf0; }
        for(transparent=0;transparent<2;++transparent)
        for(inverse=0;inverse<2;++inverse)
        for(strip=0;strip<2;++strip) {
            images[0].opacity=transparent ? cover : NULL;
            fills=bitmaps=pixels=0;
            ew_image_draw(&run,160,40,strip ? 70 : 32,180,inverse);
            expected=strip ? 10 : 40;
            assert(!fills); /* No per-pixel drawing requests. */
            assert(bitmaps>0 && bitmaps<=2*expected);
            if(!transparent) assert(pixels==320*expected);
            ++cases;
        }
    }
    printf("Nano-X scaled GIF requests: %u cases; 320x40 opaque redraw <=80 bitmaps, 0 pixel fills\n",cases);
    return 0;
}
