/* Native C GIF87a/89a first-frame reader; no DOS or C++ dependencies.
 * Format reference: https://www.w3.org/Graphics/GIF/spec-gif89a.txt
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#include "gif.h"
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#ifdef __ia16__
#include <malloc.h>
#define far_alloc(n) fmemalloc((unsigned long)(n))
#define far_free(p) fmemfree(p)
#else
#define far_alloc(n) malloc(n)
#define far_free(p) free(p)
#endif

#define LZW_CODES 4096U
#define LZW_PREFIX_BYTES (LZW_CODES * sizeof(uint16_t))
#define LZW_TAIL_BYTES (LZW_CODES * 2U)

struct lzw_workspace {
    uint16_t EW_GIF_FAR *prefix;
    unsigned char EW_GIF_FAR *suffix, *stack;
};

static void lzw_free(struct lzw_workspace *w, int split)
{
    if (split && w->suffix) far_free(w->suffix);
    if (w->prefix) far_free(w->prefix);
}

static int lzw_alloc(struct lzw_workspace *w, int split)
{
    /* Preserve the mono path's existing 16K slab. Color decode may have
     * smaller free extents, even when total capacity is enough. */
    w->prefix = far_alloc(LZW_PREFIX_BYTES + (split ? 0U : LZW_TAIL_BYTES));
    if (!w->prefix) return -1;
    w->suffix = split ? far_alloc(LZW_TAIL_BYTES) :
        (unsigned char EW_GIF_FAR *)(w->prefix + LZW_CODES);
    if (!w->suffix) return -1;
    w->stack = w->suffix + LZW_CODES;
    return 0;
}

struct color_workspace {
    unsigned char rgb[256][3];      /* Palette, six bits per channel. */
    unsigned char pair[256];        /* Main colour high nibble, partner low. */
    unsigned char mix[256];         /* Partner share in 16ths; 255 = unset. */
    uint16_t xmap[];                /* Stored column, or 0xffff if dropped. */
};

struct reader {
    const unsigned char EW_GIF_FAR *data;
    unsigned length, pos, block_left;
    unsigned long bit_buffer;
    unsigned bit_count;
    unsigned dither_shift;
    /* Colour decoding: canvas size, opacity stride, current stored row. */
    unsigned canvas_width, canvas_height, opacity_stride;
    unsigned row_offset, opacity_offset, dest_row;
    unsigned char color, identity, skip_row;
};

static int byte_read(struct reader *r)
{
    if (r->pos == r->length) return -1;
    return r->data[r->pos++];
}

static int skip(struct reader *r, unsigned bytes)
{
    if (bytes > r->length - r->pos) return 0;
    r->pos += bytes;
    return 1;
}

static unsigned word_at(const unsigned char EW_GIF_FAR *p)
{
    return p[0] | ((unsigned)p[1] << 8);
}

static int skip_blocks(struct reader *r)
{
    int count;
    while ((count = byte_read(r)) > 0)
        if (!skip(r, (unsigned)count)) return 0;
    return count == 0;
}

static int palette(struct reader *r, unsigned count, unsigned char *gray,
                   struct color_workspace EW_GIF_FAR *w)
{
    unsigned i, red, green, blue;
    if (count * 3U > r->length - r->pos) return 0;
    for (i = 0; i < count; ++i) {
        red = r->data[r->pos++];
        green = r->data[r->pos++];
        blue = r->data[r->pos++];
        gray[i] = (unsigned char)((red * 77U + green * 150U + blue * 29U) >> 8);
        if (w) {
            w->rgb[i][0] = red >> 2; w->rgb[i][1] = green >> 2;
            w->rgb[i][2] = blue >> 2; w->mix[i] = 255;
        }
    }
    return 1;
}

static int code_read(struct reader *r, unsigned bits)
{
    int byte;
    unsigned value;
    while (r->bit_count < bits) {
        if (!r->block_left) {
            byte = byte_read(r);
            if (byte <= 0) return -1;
            r->block_left = (unsigned)byte;
        }
        byte = byte_read(r);
        if (byte < 0) return -1;
        --r->block_left;
        r->bit_buffer |= (unsigned long)byte << r->bit_count;
        r->bit_count += 8;
    }
    value = (unsigned)r->bit_buffer & ((1U << bits) - 1);
    r->bit_buffer >>= bits;
    r->bit_count -= bits;
    return value;
}

/* Ordered monochrome dithering keeps working memory independent of width. */
static unsigned char mono(unsigned char gray, unsigned x, unsigned y)
{
    static const unsigned char bayer[16] = {0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5};
    return gray > bayer[((y & 3) << 2) | (x & 3)] * 16U + 7U;
}

static void emit(struct ew_gif *out, unsigned x, unsigned y, unsigned char gray,
                 int opaque, unsigned dither_shift)
{
    unsigned offset = y * out->stride + (x >> 3);
    unsigned char mask = 0x80U >> (x & 7);
    if (mono(gray, x, y >> dither_shift)) out->pixels[offset] |= mask;
    else out->pixels[offset] &= ~mask;
    if (opaque && out->opacity) out->opacity[offset] |= mask;
}

static const unsigned char bayer4[16] = {0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5};
/* IBM RGBI colours as the Tandy and PCjr show them, six bits per channel. */
static const unsigned char rgbi[16][3] = {
    {0,0,0},{0,0,42},{0,42,0},{0,42,42},{42,0,0},{42,0,42},{42,21,0},{42,42,42},
    {21,21,21},{21,21,63},{21,63,21},{21,63,63},{63,21,21},{63,21,63},{63,63,21},{63,63,63}};

static unsigned nearest(int red, int green, int blue)
{
    unsigned i, best = 0, distance, least = 65535U;
    int dr, dg, db;
    for (i = 0; i < 16; ++i) {
        dr = rgbi[i][0] - red; dg = rgbi[i][1] - green; db = rgbi[i][2] - blue;
        distance = (unsigned)(dr * dr) * 2U + (unsigned)(dg * dg) * 4U + (unsigned)(db * db);
        if (distance < least) { least = distance; best = i; }
    }
    return best;
}

/* Choose the closest colour, then the colour closest to the mirror image of
 * the error, and the share of the second that lands nearest the target. Done
 * once per palette entry actually used, never per pixel. */
static void quantize(struct color_workspace EW_GIF_FAR *w, unsigned index)
{
    int target[3], other[3], delta, along;
    unsigned i, first, second;
    long dot = 0, length = 0;
    static const unsigned char weight[3] = {2, 4, 1};
    for (i = 0; i < 3; ++i) target[i] = w->rgb[index][i];
    first = nearest(target[0], target[1], target[2]);
    for (i = 0; i < 3; ++i) {
        other[i] = 2 * target[i] - rgbi[first][i];
        if (other[i] < 0) other[i] = 0;
        if (other[i] > 63) other[i] = 63;
    }
    second = nearest(other[0], other[1], other[2]);
    for (i = 0; i < 3; ++i) {
        delta = rgbi[second][i] - rgbi[first][i];
        along = target[i] - rgbi[first][i];
        dot += (long)weight[i] * delta * along;
        length += (long)weight[i] * delta * delta;
    }
    w->pair[index] = (unsigned char)((first << 4) | second);
    /* Never more than half: beyond that the partner would be the nearer. */
    w->mix[index] = length > 0 && dot > 0 ?
        (unsigned char)(dot * 16 >= length * 8 ? 8 : (dot * 16 + length / 2) / length) : 0;
}

/* Rows arrive whole but, when interlaced, out of order. A reduced image keeps
 * the first source row and column that maps to each stored row and column. */
static void color_row(struct reader *r, const struct ew_gif *out, unsigned y)
{
    unsigned long scaled;
    r->skip_row = 1;
    if (y >= r->canvas_height) return;
    if (out->height == r->canvas_height) r->dest_row = y;
    else {
        scaled = (unsigned long)y * out->height;
        r->dest_row = (unsigned)(scaled / r->canvas_height);
        if (y && (unsigned)((scaled - out->height) / r->canvas_height) == r->dest_row)
            return;
    }
    r->skip_row = 0;
    r->row_offset = r->dest_row * out->stride;
    r->opacity_offset = r->dest_row * r->opacity_stride;
}

static void emit_color(struct reader *r, struct ew_gif *out,
                       struct color_workspace EW_GIF_FAR *w, unsigned x,
                       unsigned index, int opaque)
{
    unsigned offset;
    unsigned char color;
    if (!r->identity) x = w->xmap[x];
    if (x == 0xffffU) return;
    if (w->mix[index] == 255) quantize(w, index);
    color = w->pair[index];
    color = bayer4[((r->dest_row & 3) << 2) | (x & 3)] < w->mix[index] ?
            color & 15 : color >> 4;
    offset = r->row_offset + (x >> 1);
    if (x & 1) out->pixels[offset] = (out->pixels[offset] & 0xf0) | color;
    else out->pixels[offset] = (out->pixels[offset] & 0x0f) | (unsigned char)(color << 4);
    if (opaque && out->opacity)
        out->opacity[r->opacity_offset + (x >> 3)] |= 0x80U >> (x & 7);
}

#ifdef __ia16__
/* ia16 GCC 6.3's loop optimizer ICEs on the far dictionary access below.
 * Keep the workaround confined to decoding; ordinary -Os remains enabled.
 */
__attribute__((optimize("no-tree-loop-optimize")))
#endif
static int decode_pixels(struct reader *r, struct ew_gif *out,
                         unsigned left, unsigned top, unsigned width, unsigned height,
                         int interlaced, const unsigned char *gray, unsigned colors,
                         int transparent, const struct lzw_workspace *w,
                         struct color_workspace EW_GIF_FAR *color)
{
    static const unsigned char starts[4] = {0,4,2,1}, steps[4] = {8,8,4,2};
    int minimum = byte_read(r), code, previous = -1, first = 0, original;
    unsigned clear, end, available, bits, depth, x = 0, y = 0, pass = 0;
    unsigned long produced = 0, expected = (unsigned long)width * height;
    /* One monochrome row in near memory avoids a far read/modify/write and
     * a stride multiplication for every decoded pixel. Only the frame's
     * bytes are copied; edge bits and the logical-screen background survive.
     * Colour retains its independent packed-nibble path. */
    uint16_t EW_GIF_FAR *prefix = w->prefix;
    unsigned char EW_GIF_FAR *suffix = w->suffix;
    unsigned char EW_GIF_FAR *stack = w->stack;
    unsigned char row_bits[EW_GIF_MAX_WIDTH / 8], row_opacity[EW_GIF_MAX_WIDTH / 8];
    static const unsigned char threshold[16] = {
        7,135,39,167,199,71,231,103,55,183,23,151,247,119,215,87};
    unsigned row_offset = 0, row_byte = 0, row_first = left >> 3;
    unsigned row_end = (left + width + 7) >> 3, n;
    unsigned char row_mask = 0;
    const unsigned char *row_threshold = threshold;
    if (minimum < 0) return EW_GIF_TRUNCATED;
    if (minimum < 2 || minimum > 8) return EW_GIF_BAD_DATA;
    if (r->color) color_row(r, out, top);
    clear = 1U << minimum;
    end = clear + 1;
    available = end + 1;
    bits = minimum + 1;
    for (;;) {
        code = code_read(r, bits);
        if (code < 0) return EW_GIF_TRUNCATED;
        if (code == (int)clear) {
            available = end + 1;
            bits = minimum + 1;
            previous = -1;
            continue;
        }
        if (code == (int)end) {
            if (produced != expected) return EW_GIF_BAD_DATA;
            if (!skip(r, r->block_left) || !skip_blocks(r)) return EW_GIF_TRUNCATED;
            return EW_GIF_OK;
        }
        if ((unsigned)code > available || code >= 4096) return EW_GIF_BAD_DATA;
        original = code;
        depth = 0;
        if ((unsigned)code == available) {
            if (previous < 0) return EW_GIF_BAD_DATA;
            stack[depth++] = (unsigned char)first;
            code = previous;
        }
        while ((unsigned)code >= clear) {
            if ((unsigned)code <= end || (unsigned)code >= available || depth >= 4095)
                return EW_GIF_BAD_DATA;
            stack[depth++] = suffix[code];
            code = prefix[code];
        }
        first = code;
        stack[depth++] = (unsigned char)first;
        while (depth) {
            unsigned char index = stack[--depth];
            if (produced >= expected || index >= colors) return EW_GIF_BAD_DATA;
            if (!r->color) {
                if (!x) {
                    row_offset = (top + y) * out->stride;
                    for (n = row_first; n < row_end; ++n) {
                        row_bits[n] = out->pixels[row_offset + n];
                        if (out->opacity) row_opacity[n] = out->opacity[row_offset + n];
                    }
                    row_byte = row_first; row_mask = 0x80U >> (left & 7);
                    row_threshold = threshold + ((((top + y) >> r->dither_shift) & 3) << 2);
                }
                if (gray[index] > row_threshold[(left + x) & 3]) row_bits[row_byte] |= row_mask;
                else row_bits[row_byte] &= ~row_mask;
                if (index != transparent && out->opacity) row_opacity[row_byte] |= row_mask;
                row_mask >>= 1;
                if (!row_mask) { row_mask = 128; ++row_byte; }
            } else if (!r->skip_row)
                emit_color(r, out, color,
                           left + x, index, index != transparent);
            ++produced;
            if (++x == width) {
                if (!r->color)
                    for (n = row_first; n < row_end; ++n) {
                        out->pixels[row_offset + n] = row_bits[n];
                        if (out->opacity) out->opacity[row_offset + n] = row_opacity[n];
                    }
                x = 0;
                if (!interlaced) ++y;
                else {
                    y += steps[pass];
                    while (y >= height && pass < 3) y = starts[++pass];
                }
                if (r->color) color_row(r, out, y < height ? top + y : 65535U);
            }
        }
        if (previous >= 0 && available < 4096) {
            prefix[available] = (uint16_t)previous;
            suffix[available] = (unsigned char)first;
            if (++available == (1U << bits) && bits < 12) ++bits;
        }
        previous = original;
    }
}

static int signature(const unsigned char EW_GIF_FAR *data)
{
    return data[0] == 'G' && data[1] == 'I' && data[2] == 'F' &&
           data[3] == '8' && (data[4] == '7' || data[4] == '9') && data[5] == 'a';
}

int ew_gif_decode(const unsigned char EW_GIF_FAR *data, unsigned length, struct ew_gif *out)
{
    return ew_gif_decode_aspect(data, length, out, 1);
}

static int decode(const unsigned char EW_GIF_FAR *data, unsigned length,
                  struct ew_gif *out, unsigned pixel_aspect,
                  unsigned max_width, unsigned max_height);

int ew_gif_decode_aspect(const unsigned char EW_GIF_FAR *data, unsigned length,
                         struct ew_gif *out, unsigned pixel_aspect)
{
    return decode(data, length, out, pixel_aspect, 0, 0);
}

int ew_gif_decode_color(const unsigned char EW_GIF_FAR *data, unsigned length,
                        struct ew_gif *out, unsigned max_width, unsigned max_height)
{
    if (!max_width || !max_height || max_width > EW_GIF_MAX_WIDTH) return EW_GIF_BAD_DATA;
    return decode(data, length, out, 1, max_width, max_height);
}

static int decode(const unsigned char EW_GIF_FAR *data, unsigned length,
                  struct ew_gif *out, unsigned pixel_aspect,
                  unsigned max_width, unsigned max_height)
{
    struct reader r;
    struct lzw_workspace workspace = {0,0,0};
    struct color_workspace EW_GIF_FAR *color_workspace = 0;
    unsigned char gray[256];
    unsigned width, height, left, top, colors = 0, bytes, i, x, y;
    unsigned canvas_width, canvas_height, error;
    unsigned char flags, background = 255;
    int marker, transparent = -1, result = EW_GIF_TRUNCATED;
    if (!out) return EW_GIF_BAD_DATA;
    memset(out, 0, sizeof(*out));
    if (pixel_aspect != 1 && pixel_aspect != 2) return EW_GIF_BAD_DATA;
    r.dither_shift = pixel_aspect == 2;
    if (!data || length < 6 || !signature(data))
        return EW_GIF_BAD_HEADER;
    if (length < 13) return EW_GIF_TRUNCATED;
    out->width = word_at(data + 6);
    out->height = word_at(data + 8);
    if (!out->width || !out->height || out->width > EW_GIF_MAX_WIDTH || out->height > EW_GIF_MAX_HEIGHT) {
        memset(out, 0, sizeof(*out));
        return EW_GIF_TOO_LARGE;
    }
    out->stride = (out->width + 7) >> 3;
    canvas_width = out->width; canvas_height = out->height;
    r.data = data; r.length = length; r.pos = 13;
    r.block_left = r.bit_count = 0; r.bit_buffer = 0;
    r.color = max_width != 0;
    if (r.color) {
        r.canvas_width = canvas_width; r.canvas_height = canvas_height;
        if (out->width > max_width) {
            out->height = (unsigned)((unsigned long)out->height * max_width / out->width);
            out->width = max_width;
        }
        if (out->height > max_height) {
            out->width = (unsigned)((unsigned long)canvas_width * max_height / canvas_height);
            out->height = max_height;
        }
        if (!out->width) out->width = 1;
        if (!out->height) out->height = 1;
        out->depth = 4;
        out->stride = (out->width + 1) >> 1;
        r.opacity_stride = (out->width + 7) >> 3;
        r.identity = out->width == canvas_width;
        color_workspace = far_alloc(sizeof(*color_workspace) +
            (r.identity ? 0U : canvas_width * sizeof(uint16_t)));
        if (!color_workspace || lzw_alloc(&workspace, 1)) {
            result = EW_GIF_NO_MEMORY; goto failed;
        }
        /* floor(x*stored/canvas) by error accumulation; keep first of each. */
        if (!r.identity)
            for (x = 0, y = 0, error = 0; x < canvas_width; ++x) {
                color_workspace->xmap[x] = !x || error < out->width ? (uint16_t)y : 0xffffU;
                error += out->width;
                if (error >= canvas_width) { error -= canvas_width; ++y; }
            }
    }
    if (data[10] & 0x80) {
        colors = 2U << (data[10] & 7);
        if (!palette(&r, colors, gray, color_workspace)) goto failed;
        if (data[11] < colors) background = gray[data[11]];
    }
    while ((marker = byte_read(&r)) >= 0) {
        if (marker == 0x21) {
            marker = byte_read(&r);
            if (marker < 0) goto failed;
            if (marker == 0xf9) {
                if (byte_read(&r) != 4 || r.length - r.pos < 5) goto failed;
                transparent = r.data[r.pos] & 1 ? r.data[r.pos + 3] : -1;
                r.pos += 4;
                if (byte_read(&r) != 0) { result = EW_GIF_BAD_DATA; goto failed; }
            } else {
                if (!skip_blocks(&r)) goto failed;
                if (marker == 0x01) transparent = -1; /* GCE scope consumed by plain text. */
            }
            continue;
        }
        if (marker != 0x2c) { result = EW_GIF_BAD_DATA; goto failed; }
        if (r.length - r.pos < 9) goto failed;
        left = word_at(data + r.pos); top = word_at(data + r.pos + 2);
        width = word_at(data + r.pos + 4); height = word_at(data + r.pos + 6);
        flags = data[r.pos + 8]; r.pos += 9;
        if (!width || !height || left >= canvas_width || top >= canvas_height ||
            width > canvas_width - left || height > canvas_height - top) {
            result = EW_GIF_BAD_DATA; goto failed;
        }
        if (flags & 0x80) {
            colors = 2U << (flags & 7);
            if (!palette(&r, colors, gray, color_workspace)) goto failed;
        }
        if (!colors || transparent >= (int)colors) { result = EW_GIF_BAD_DATA; goto failed; }
        bytes = out->stride * out->height;
        out->pixels = far_alloc(bytes);
        if (transparent >= 0)
            out->opacity = far_alloc(r.color ? r.opacity_stride * out->height : bytes);
        if (!out->pixels || (transparent >= 0 && !out->opacity) ||
            (!r.color && lzw_alloc(&workspace, 0))) {
            result = EW_GIF_NO_MEMORY; goto failed;
        }
        /* Colour: the uncovered canvas is the nearest solid background. */
        x = r.color && (data[10] & 0x80) && data[11] < colors ?
            nearest(color_workspace->rgb[data[11]][0], color_workspace->rgb[data[11]][1],
                    color_workspace->rgb[data[11]][2]) * 17U : r.color ? 255 : 0;
        for (i = 0; i < bytes; ++i) out->pixels[i] = (unsigned char)x;
        if (out->opacity)
            for (i = r.color ? r.opacity_stride * out->height : bytes; i--;)
                out->opacity[i] = 0;
        /* A full-canvas first frame writes every pixel, including transparent
         * indices. Only partial frames need the logical-screen background. */
        if (!r.color && (left || top || width != out->width || height != out->height))
            for (y = 0; y < out->height; ++y)
                for (x = 0; x < out->width; ++x)
                    emit(out, x, y, background, 0, r.dither_shift);
        result = decode_pixels(&r, out, left, top, width, height, flags & 0x40,
                               gray, colors, transparent, &workspace, color_workspace);
        if (result != EW_GIF_OK) goto failed;
        lzw_free(&workspace, r.color);
        if (color_workspace) far_free(color_workspace);
        return EW_GIF_OK;
    }
failed:
    lzw_free(&workspace, r.color);
    if (color_workspace) far_free(color_workspace);
    ew_gif_free(out);
    return result;
}

void ew_gif_free(struct ew_gif *image)
{
    if (!image) return;
    if (image->pixels) far_free(image->pixels);
    if (image->opacity) far_free(image->opacity);
    memset(image, 0, sizeof(*image));
}

unsigned ew_gif_copy_row(const struct ew_gif *image, unsigned row,
                         unsigned char *pixels, unsigned char *opacity)
{
    unsigned i, offset;
    if (!image || !image->pixels || row >= image->height) return 0;
    offset = row * image->stride;
    for (i = 0; i < image->stride; ++i) {
        if (pixels) pixels[i] = image->pixels[offset + i];
        if (opacity) opacity[i] = image->opacity ? image->opacity[offset + i] : 255;
    }
    return image->stride;
}

const char *ew_gif_error(int result)
{
    switch (result) {
    case EW_GIF_OK: return "OK";
    case EW_GIF_BAD_HEADER: return "Not a GIF87a/89a image";
    case EW_GIF_TOO_LARGE: return "GIF exceeds 640x480 image limit";
    case EW_GIF_TRUNCATED: return "Incomplete GIF data";
    case EW_GIF_BAD_DATA: return "Invalid GIF data";
    case EW_GIF_NO_MEMORY: return "Not enough memory for GIF";
    default: return "GIF error";
    }
}
