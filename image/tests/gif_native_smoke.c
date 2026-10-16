/* Compile with image/gif.c using the native ELKS toolchain, then run in QEMU.
 * Confirms far allocation, decoding, row copy and cleanup on the target ABI.
 */
#include "gif.h"
#include <stdio.h>

static const unsigned char white_pixel[] = {
    'G','I','F','8','7','a', 1,0,1,0, 0x80,0,0,
    0,0,0, 255,255,255,
    0x2c,0,0,0,0,1,0,1,0,0,
    2,2,0x4c,0x01,0,0x3b
};

int main(void)
{
    struct ew_gif image;
    unsigned char pixels[1], opacity[1];
    int result = ew_gif_decode(white_pixel, sizeof(white_pixel), &image);
    if (result) { printf("GIF_SMOKE_FAIL decode=%d\n", result); return 1; }
    if (image.width != 1 || image.height != 1 ||
        ew_gif_copy_row(&image, 0, pixels, opacity) != 1 ||
        !(pixels[0] & 128) || opacity[0] != 255) {
        puts("GIF_SMOKE_FAIL pixels");
        ew_gif_free(&image);
        return 2;
    }
    ew_gif_free(&image);
    if (image.pixels || image.opacity) { puts("GIF_SMOKE_FAIL cleanup"); return 3; }
    puts("ELKSWEB_GIF_SMOKE_OK");
    return 0;
}
