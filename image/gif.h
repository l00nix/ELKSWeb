/* Bounded first-frame GIF decoder for ELKSWeb. SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef ELKSWEB_GIF_H
#define ELKSWEB_GIF_H

#ifdef __ia16__
#define EW_GIF_FAR __far
#else
#define EW_GIF_FAR
#endif

#define EW_GIF_MAX_WIDTH 640
#define EW_GIF_MAX_HEIGHT 480

struct ew_gif {
    unsigned width, height, stride;
    /* depth 0/1: one bit per pixel, MSB first; 1 is white.
     * depth 4: two pixels per byte, left pixel in the high nibble, IBM RGBI
     * colour 0..15; stride is then (width+1)/2 and opacity is (width+7)/8. */
    unsigned char EW_GIF_FAR *pixels;
    unsigned char EW_GIF_FAR *opacity; /* NULL means all opaque; 1 is opaque. */
    unsigned char depth;
};

enum ew_gif_result {
    EW_GIF_OK = 0,
    EW_GIF_BAD_HEADER,
    EW_GIF_TOO_LARGE,
    EW_GIF_TRUNCATED,
    EW_GIF_BAD_DATA,
    EW_GIF_NO_MEMORY
};

/* Output must be empty; free any previous image before reusing it.
 * Input may be released as soon as this function returns. Failed calls leave
 * output empty. Uses far allocations on ELKS, ordinary malloc on host tests.
 * Decodes one frame, with interlace, local palettes and transparency.
 */
int ew_gif_decode(const unsigned char EW_GIF_FAR *data, unsigned length, struct ew_gif *out);
/* Keep the stored dimensions unchanged, but phase monochrome dithering for
 * the display's natural vertical reduction: 1 for square pixels, 2 for CGA.
 * This avoids discarding half the Bayer rows when CGA samples every other row.
 * Arbitrary HTML resizes still use nearest-neighbor sampling, not area filtering.
 */
int ew_gif_decode_aspect(const unsigned char EW_GIF_FAR *data, unsigned length,
                         struct ew_gif *out, unsigned pixel_aspect);
/* Sixteen-colour decode for the Tandy/PCjr display. The image is reduced
 * while decoding, keeping its proportions, until it fits max_width x
 * max_height, so storage is bounded by the caller rather than by the file:
 * at most (max_width+1)/2*max_height bytes plus a one-bit opacity plane.
 * out->width/height are the stored size. Palette entries become an ordered
 * dither of the two closest fixed RGBI colours. */
int ew_gif_decode_color(const unsigned char EW_GIF_FAR *data, unsigned length,
                        struct ew_gif *out, unsigned max_width, unsigned max_height);
void ew_gif_free(struct ew_gif *image);
/* Each destination, when non-NULL, needs image->stride bytes (at most 80).
 * Returns stride, or zero for a row outside the image.
 */
unsigned ew_gif_copy_row(const struct ew_gif *image, unsigned row,
                         unsigned char *pixels, unsigned char *opacity);
const char *ew_gif_error(int result);

#endif
