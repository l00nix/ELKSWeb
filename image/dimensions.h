/* Bounded raster metadata reader. SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef EW_IMAGE_DIMENSIONS_H
#define EW_IMAGE_DIMENSIONS_H
#include "gif.h"
/* Returns 1 for known nonzero dimensions, otherwise 0. Pixel decoding is
 * independent. PNG dimensions above the 16-bit layout range saturate at65535.
 */
int ew_image_dimensions(const unsigned char EW_GIF_FAR *data, unsigned length,
                        unsigned *width, unsigned *height);
#endif
