/* Bounded GIF/PNG/JPEG metadata without pixel decoding.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#include "dimensions.h"

static unsigned big16(const unsigned char EW_GIF_FAR *p)
{
  return ((unsigned)p[0] << 8) | p[1];
}
static unsigned png_size(const unsigned char EW_GIF_FAR *p)
{
  if (p[0] || p[1]) return 65535U;
  return big16(p + 2);
}
int ew_image_dimensions(const unsigned char EW_GIF_FAR *p, unsigned n,
                        unsigned *width, unsigned *height)
{
  unsigned w = 0, h = 0, pos, marker, size, components;
  if (!p) return 0;
  if (n >= 10 && p[0] == 'G' && p[1] == 'I' && p[2] == 'F' &&
      p[3] == '8' && (p[4] == '7' || p[4] == '9') && p[5] == 'a') {
    w = p[6] | ((unsigned)p[7] << 8);
    h = p[8] | ((unsigned)p[9] << 8);
  } else if (n >= 24 && p[0] == 137 && p[1] == 'P' && p[2] == 'N' &&
             p[3] == 'G' && p[4] == 13 && p[5] == 10 && p[6] == 26 &&
             p[7] == 10 && !p[8] && !p[9] && !p[10] && p[11] == 13 &&
             p[12] == 'I' && p[13] == 'H' && p[14] == 'D' && p[15] == 'R') {
    w = png_size(p + 16);
    h = png_size(p + 20);
  } else if (n >= 4 && p[0] == 255 && p[1] == 216) {
    pos = 2;
    while (pos < n) {
      if (p[pos++] != 255) return 0;
      while (pos < n && p[pos] == 255) ++pos;
      if (pos == n) return 0;
      marker = p[pos++];
      if (!marker || marker == 217 || marker == 218) return 0;
      if (marker == 1 || marker == 216 || (marker >= 208 && marker <= 215))
        continue;
      if (n - pos < 2) return 0;
      size = big16(p + pos);
      if (size < 2 || size > n - pos) return 0;
      if (marker >= 192 && marker <= 207 && marker != 196 &&
          marker != 200 && marker != 204) {
        if (size < 8) return 0;
        components = p[pos + 7];
        if (!components || size < 8U + 3U * components) return 0;
        h = big16(p + pos + 3);
        w = big16(p + pos + 5);
        break;
      }
      pos += size;
    }
  }
  if (!w || !h) return 0;
  if (width) *width = w;
  if (height) *height = h;
  return 1;
}
