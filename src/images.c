/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "../image/gif.h"
#include "../image/dimensions.h"
#include "../font/body_font.h"
#include "elks_platform.h"
#include "elksweb.h"
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#define IMAGE_LIMIT 8
static struct ew_gif images[IMAGE_LIMIT];
static unsigned image_count;
static unsigned natural_width[IMAGE_LIMIT], natural_height[IMAGE_LIMIT];
static char EW_FAR *image_urls;
static char document_error[96];
const char *ew_image_document_error(void) { return document_error; }
static int document_fail(const char *message) {
  strncpy(document_error, message, sizeof(document_error)-1);
  document_error[sizeof(document_error)-1]=0;
  return -1;
}
static int image_find(const char *url) {
  unsigned i;
  for (i = 0; i < image_count; ++i) {
    const char EW_FAR *p = image_urls + i * EW_URL;
    const char *q = url;
    while (*p && *p == *q) { ++p; ++q; }
    if (!*p && !*q) return (int)i;
  }
  return -1;
}
int ew_image_lookup(const char *url, unsigned *width, unsigned *height) {
  int i = image_find(url);
  if (width) *width = i < 0 ? 0 : natural_width[i];
  if (height) *height = i < 0 ? 0 : natural_height[i];
  return i >= 0 && images[i].pixels ? i : -1;
}
void ew_images_clear(void) {
  unsigned i;
  for (i = 0; i < image_count; i++) ew_gif_free(&images[i]);
  image_count = 0;
  memset(natural_width, 0, sizeof(natural_width));
  memset(natural_height, 0, sizeof(natural_height));
  ew_far_free(image_urls);
  image_urls = NULL;
}
int ew_images_load_document(const char *url) {
  static unsigned char header[512];
  unsigned char EW_FAR *compressed;
  unsigned i, amount, head, width=0, height=0;
  int known, gif, result;
  ew_images_clear();
  document_error[0]=0;
  if (!url || strlen(url)>=EW_URL) return document_fail("Image URL too long");
  if (!ew_source_length) return document_fail("Empty image document");
  if (ew_source_error()[0]) return document_fail(ew_source_error());
  head=ew_source_length>sizeof(header) ? sizeof(header) : (unsigned)ew_source_length;
  for (i=0;i<head;++i) header[i]=ew_source_byte((uint32_t)i);
  if (ew_source_error()[0]) return document_fail(ew_source_error());
  known=ew_image_dimensions(header,head,&width,&height);
  gif=head>=6 && !memcmp(header,"GIF8",4) &&
      (header[4]=='7' || header[4]=='9') && header[5]=='a';
  image_urls=ew_far_alloc((unsigned long)IMAGE_LIMIT*EW_URL);
  if (!image_urls) return document_fail("Not enough memory for image URL");
  ew_copy_to_far(image_urls,url,strlen(url)+1);
  image_count=1;
  natural_width[0]=width;
  natural_height[0]=height;
  if (known && !gif) {
    document_fail("Image dimensions available; PNG/JPEG pixels are unsupported");
    return 1;
  }
  if (gif && ew_source_length>EW_SOURCE) {
    document_fail("GIF document exceeds 60000-byte decoder limit");
    return known ? 1 : -1;
  }
  amount=ew_source_length>EW_SOURCE ? EW_SOURCE : (unsigned)ew_source_length;
  compressed=ew_far_alloc(amount);
  if (!compressed) {
    document_fail("Not enough memory to decode image");
    return known ? 1 : -1;
  }
  for (i=0;i<amount;++i) compressed[i]=ew_source_byte((uint32_t)i);
  if (ew_source_error()[0]) {
    ew_far_free(compressed);
    return document_fail(ew_source_error());
  }
  known=ew_image_dimensions(compressed,amount,&natural_width[0],&natural_height[0]);
  result=ew_gif_decode_aspect(compressed,amount,&images[0],ew_pixel_aspect);
  ew_far_free(compressed);
  if (result==EW_GIF_OK) return 0;
  document_fail(gif ? ew_gif_error(result) :
      known ? "Image dimensions available; PNG/JPEG pixels are unsupported" :
              "Unrecognized or incomplete image document");
  return known ? 1 : -1;
}
static int load_image(const char *url, struct ew_gif *image,
                      unsigned *width, unsigned *height) {
  static char final[EW_URL], error[96], path[40];
  static unsigned char chunk[512];
  unsigned attempt, count, i;
  int fd = -1, got, result = -1;
  int32_t size;
  unsigned char EW_FAR *compressed = NULL;
  for (attempt = 0; attempt < 16; ++attempt) {
    snprintf(path, sizeof(path), "/tmp/ei%04x%02x.gif", (unsigned)getpid() & 0xffffU, attempt);
    fd = open(path, O_RDWR | O_CREAT | O_EXCL, 0600);
    if (fd >= 0) break;
    if (errno != EEXIST) return -1;
  }
  if (fd < 0) return -1;
  size = ew_fetch_to_fd(url, fd, EW_SOURCE, final, error, sizeof(error));
  if (size <= 0 || lseek(fd, 0L, SEEK_SET) < 0) goto done;
  compressed = ew_far_alloc((unsigned long)size);
  if (!compressed) goto done;
  count = 0;
  while ((uint32_t)count < (uint32_t)size) {
    unsigned want = (unsigned)size - count;
    if (want > sizeof(chunk)) want = sizeof(chunk);
    got = read(fd, chunk, want);
    if (got < 0 && errno == EINTR) continue;
    if (got <= 0) goto done;
    for (i = 0; i < (unsigned)got; ++i) compressed[count++] = chunk[i];
  }
  ew_image_dimensions(compressed, (unsigned)size, width, height);
  result = ew_gif_decode_aspect(compressed, (unsigned)size, image,
                               ew_pixel_aspect) == EW_GIF_OK ? 0 : -1;
done:
  ew_far_free(compressed);
  close(fd);
  unlink(path);
  return result;
}
void ew_images_load(void) {
  unsigned i;
  static char url[EW_URL];
  for (i = 0; i < ew_doc.run_count; i++) {
    struct ew_run EW_FAR *r = &ew_doc.runs[i];
    int index;
    if (r->kind != EW_RUN_IMAGE) continue;
    ew_copy_from_far(url, ew_doc.text + r->off, sizeof(url));
    index = image_find(url);
    if (index >= 0) {
      if (images[index].pixels) r->style = index;
      continue;
    }
    if (image_count == IMAGE_LIMIT) continue;
    if (!image_urls) image_urls = ew_far_alloc((unsigned long)IMAGE_LIMIT * EW_URL);
    if (!image_urls) break;
    index = image_count++;
    ew_copy_to_far(image_urls + (unsigned)index * EW_URL, url, strlen(url) + 1);
    if (!load_image(url, &images[index], &natural_width[index],
                    &natural_height[index])) r->style = index;
  }
}
static unsigned image_alt_offset(const struct ew_run EW_FAR *r) {
  unsigned pos, end;
  if (!r || r->kind!=EW_RUN_IMAGE || !ew_doc.text || r->off>=ew_doc.text_len) return 0;
  pos=r->off;
  end=(unsigned long)pos+EW_URL<ew_doc.text_len ? pos+EW_URL : ew_doc.text_len;
  while (pos<end && ew_doc.text[pos]) ++pos;
  return pos<end && pos+1<ew_doc.text_len ? pos+1 : 0;
}
const char EW_FAR *ew_image_alt(const struct ew_run EW_FAR *r) {
  unsigned start=image_alt_offset(r), pos=start, n=0;
  if (!start) return NULL;
  while (pos<ew_doc.text_len && n<EW_IMAGE_ALT && ew_doc.text[pos]) { ++pos; ++n; }
  return pos<ew_doc.text_len && n<EW_IMAGE_ALT ? ew_doc.text+start : NULL;
}
int ew_image_is_map(const struct ew_run EW_FAR *r) {
  const char EW_FAR *alt=ew_image_alt(r);
  unsigned pos=image_alt_offset(r);
  if (!alt) return 0;
  while (*alt++) ++pos;
  return pos+1<ew_doc.text_len && (ew_doc.text[pos+1]&EW_LINK_ISMAP)!=0;
}
int ew_image_map_point(const struct ew_run EW_FAR *r,int x,int y,
                       unsigned *map_x,unsigned *map_y) {
  unsigned i,j,width,height;
  if (!ew_image_is_map(r) || !r->n || !r->w || x<0 || y<0 ||
      (unsigned)x>=r->n || (unsigned)y>=r->w || !map_x || !map_y) return -1;
  width=r->n; height=(unsigned)r->w*ew_pixel_aspect;
  for (i=0;i<image_count;++i) {
    const char EW_FAR *cached=image_urls+i*EW_URL;
    const char EW_FAR *url=ew_doc.text+r->off;
    for (j=0;j<EW_URL && url[j] && url[j]==cached[j];++j) {}
    if (j<EW_URL && !url[j] && !cached[j]) {
      if (natural_width[i]) width=natural_width[i];
      if (natural_height[i]) height=natural_height[i];
      break;
    }
  }
  *map_x=(unsigned)((unsigned long)(unsigned)x*width/r->n);
  *map_y=(unsigned)((unsigned long)(unsigned)y*height/r->w);
  return 0;
}
static void image_placeholder(const struct ew_run EW_FAR *r,int x,int y,
                               int top,int bottom,int inverse) {
  const char EW_FAR *alt=ew_image_alt(r);
  long right=(long)x+r->n-1, last=(long)y+r->w-1;
  int left=x<0 ? 0 : x, end=right>=EW_SCREEN_WIDTH ? EW_SCREEN_WIDTH-1 : (int)right;
  int first=y<top ? top : y, finish=last>=bottom ? bottom-1 : (int)last;
  int col,row,cursor,advance,color=inverse ? 1 : 0;
  for (col=left;col<=end;++col) {
    if (y>=top && y<bottom) ew_pixel(col,y,color);
    if (last>=top && last<bottom && last!=y) ew_pixel(col,(int)last,color);
  }
  for (row=first;row<=finish;++row) {
    if (x>=0 && x<EW_SCREEN_WIDTH) ew_pixel(x,row,color);
    if (right>=0 && right<EW_SCREEN_WIDTH && right!=x) ew_pixel((int)right,row,color);
  }
  /* Keep glyphs inside the image; the active display clip crops partial
   * rows at viewport/exposed-strip edges, just like ordinary page text. */
  if (y+10<=top || y+2>=bottom || r->w<12) return;
  if (x+2>=0 && (long)x+11<right && x+11<EW_SCREEN_WIDTH)
    ew_body_draw(x+2,y+2,'?',color,-1,0,0);
  cursor=x+12;
  while (alt && *alt) {
    advance=ew_body_char_width((unsigned char)*alt,0);
    if ((long)cursor+advance>=right || cursor+advance>EW_SCREEN_WIDTH) break;
    if (cursor>=0) ew_body_draw(cursor,y+2,(unsigned char)*alt,color,-1,0,0);
    cursor+=advance;
    ++alt;
  }
}
/* Reduce coverage before dithering again: sampling one bit from an already
 * dithered image can turn a gray patch entirely white. Three coverage bands
 * (white, black, transparent) retain both tone and transparent background.
 * The largest box is 640*480, so counts/products must be 32-bit on ELKS.
 */
static int reduced_pixel(const struct ew_gif *image, unsigned left, unsigned top,
                         unsigned right, unsigned bottom, unsigned x, unsigned y) {
  static const unsigned char bayer[16]={0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5};
  unsigned row,col,at,mask;
  unsigned char bits,coverage;
  unsigned long opaque=0,white=0,threshold;
  if (right==left) ++right;
  if (bottom==top) ++bottom;
  threshold=(unsigned long)(right-left)*(bottom-top)*
            (2*bayer[((y&3)<<2)|(x&3)]+1);
  for (row=top;row<bottom;++row) {
    at=row*image->stride+(left>>3);
    mask=0;
    for (col=left;col<right;++col) {
      if (!mask) {
        mask=0x80U>>(col&7);
        bits=image->pixels[at];
        coverage=image->opacity ? image->opacity[at] : 255;
        ++at;
      }
      if (coverage&mask) {
        ++opaque;
        if (bits&mask) ++white;
      }
      mask>>=1;
    }
  }
  if ((opaque<<5)<=threshold) return -1;
  return (white<<5)>threshold;
}
void ew_image_draw(const struct ew_run EW_FAR *r, int x, int y, int top, int bottom,
                   int inverse) {
  unsigned row, col, sy, sx, first_row, last_row, first_col, last_col;
  unsigned start_sx, start_error, x_error, y_error, x_step, y_step;
  unsigned x_remainder, y_remainder, previous_row=65535U;
  unsigned char bits[80], opacity[80];
  unsigned long scaled;
  int screen_x, screen_y, reduce, color;
  unsigned end_y;
  struct ew_gif *image;
  if (top<0) top=0;
  if (bottom>EW_SCREEN_HEIGHT) bottom=EW_SCREEN_HEIGHT;
  if (!r->n || !r->w || top>=bottom || y>=bottom ||
      (long)y+r->w<=top || x>=EW_SCREEN_WIDTH || (long)x+r->n<=0)
    return;
  if (r->style >= image_count || !images[r->style].pixels) {
    image_placeholder(r,x,y,top,bottom,inverse);
    return;
  }
  image = &images[r->style];
  reduce=image->width>r->n || image->height/(unsigned)ew_pixel_aspect>r->w;
  first_col=x<0 ? (unsigned)(-(long)x) : 0;
  last_col=(long)x+r->n>EW_SCREEN_WIDTH ? (unsigned)(EW_SCREEN_WIDTH-(long)x) : r->n;
  first_row=y<top ? (unsigned)(top-(long)y) : 0;
  last_row=(long)y+r->w>bottom ? (unsigned)(bottom-(long)y) : r->w;
  /* Division is confined to setup. The quotient/remainder recurrence is
   * exactly floor(destination * source_size / destination_size), including
   * clipped starts and both enlargement and reduction, without a map buffer.
   */
  scaled=(unsigned long)first_col*image->width;
  start_sx=(unsigned)(scaled/r->n);
  start_error=(unsigned)(scaled%r->n);
  x_step=image->width/r->n;
  x_remainder=image->width%r->n;
  scaled=(unsigned long)first_row*image->height;
  sy=(unsigned)(scaled/r->w);
  y_error=(unsigned)(scaled%r->w);
  y_step=image->height/r->w;
  y_remainder=image->height%r->w;
  screen_y=y<top ? top : y;
  for (row=first_row;row<last_row;++row,++screen_y) {
    end_y=sy+y_step+(y_error>=r->w-y_remainder);
    if (!reduce && sy!=previous_row) {
      ew_gif_copy_row(image,sy,bits,opacity);
      previous_row=sy;
    }
    sx=start_sx;
    x_error=start_error;
    screen_x=x<0 ? 0 : x;
    for (col=first_col;col<last_col;++col,++screen_x) {
      if (reduce) {
        color=reduced_pixel(image,sx,sy,
                            sx+x_step+(x_error>=r->n-x_remainder),end_y,col,row);
        if (color>=0) ew_pixel(screen_x,screen_y,color^inverse);
      } else if (opacity[sx>>3] & (0x80U>>(sx&7)))
        ew_pixel(screen_x,screen_y,!!(bits[sx>>3] & (0x80U>>(sx&7))) ^ inverse);
      sx+=x_step;
      /* Subtract before adding so even a 65535-pixel destination cannot
       * overflow the native unsigned 16-bit remainder accumulator. */
      if (x_error>=r->n-x_remainder) {
        x_error-=r->n-x_remainder;
        ++sx;
      } else x_error+=x_remainder;
    }
    sy+=y_step;
    if (y_error>=r->w-y_remainder) {
      y_error-=r->w-y_remainder;
      ++sy;
    } else y_error+=y_remainder;
  }
}
