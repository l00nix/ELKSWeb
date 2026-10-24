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

struct lzw_workspace {
    uint16_t prefix[4096];
    unsigned char suffix[4096];
    unsigned char stack[4096];
};

struct reader {
    const unsigned char EW_GIF_FAR *data;
    unsigned length, pos, block_left;
    unsigned long bit_buffer;
    unsigned bit_count;
    unsigned dither_shift;
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

static int palette(struct reader *r, unsigned count, unsigned char *gray)
{
    unsigned i, red, green, blue;
    if (count * 3U > r->length - r->pos) return 0;
    for (i = 0; i < count; ++i) {
        red = r->data[r->pos++];
        green = r->data[r->pos++];
        blue = r->data[r->pos++];
        gray[i] = (unsigned char)((red * 77U + green * 150U + blue * 29U) >> 8);
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

#ifdef __ia16__
/* ia16 GCC 6.3's loop optimizer ICEs on the far dictionary access below.
 * Keep the workaround confined to decoding; ordinary -Os remains enabled.
 */
__attribute__((optimize("no-tree-loop-optimize")))
#endif
static int decode_pixels(struct reader *r, struct ew_gif *out,
                         unsigned left, unsigned top, unsigned width, unsigned height,
                         int interlaced, const unsigned char *gray, unsigned colors,
                         int transparent, struct lzw_workspace EW_GIF_FAR *w)
{
    static const unsigned char starts[4] = {0,4,2,1}, steps[4] = {8,8,4,2};
    int minimum = byte_read(r), code, previous = -1, first = 0, original;
    unsigned clear, end, available, bits, depth, x = 0, y = 0, pass = 0;
    unsigned long produced = 0, expected = (unsigned long)width * height;
    if (minimum < 0) return EW_GIF_TRUNCATED;
    if (minimum < 2 || minimum > 8) return EW_GIF_BAD_DATA;
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
            w->stack[depth++] = (unsigned char)first;
            code = previous;
        }
        while ((unsigned)code >= clear) {
            if ((unsigned)code <= end || (unsigned)code >= available || depth >= 4095)
                return EW_GIF_BAD_DATA;
            w->stack[depth++] = w->suffix[code];
            code = w->prefix[code];
        }
        first = code;
        w->stack[depth++] = (unsigned char)first;
        while (depth) {
            unsigned char index = w->stack[--depth];
            if (produced >= expected || index >= colors) return EW_GIF_BAD_DATA;
            emit(out, left + x, top + y, gray[index], index != transparent,
                 r->dither_shift);
            ++produced;
            if (++x == width) {
                x = 0;
                if (!interlaced) ++y;
                else {
                    y += steps[pass];
                    while (y >= height && pass < 3) y = starts[++pass];
                }
            }
        }
        if (previous >= 0 && available < 4096) {
            w->prefix[available] = (uint16_t)previous;
            w->suffix[available] = (unsigned char)first;
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

int ew_gif_decode_aspect(const unsigned char EW_GIF_FAR *data, unsigned length,
                         struct ew_gif *out, unsigned pixel_aspect)
{
    struct reader r;
    struct lzw_workspace EW_GIF_FAR *workspace = 0;
    unsigned char gray[256];
    unsigned width, height, left, top, colors = 0, bytes, i, x, y;
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
    r.data = data; r.length = length; r.pos = 13;
    r.block_left = r.bit_count = 0; r.bit_buffer = 0;
    if (data[10] & 0x80) {
        colors = 2U << (data[10] & 7);
        if (!palette(&r, colors, gray)) goto failed;
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
        if (!width || !height || left >= out->width || top >= out->height ||
            width > out->width - left || height > out->height - top) {
            result = EW_GIF_BAD_DATA; goto failed;
        }
        if (flags & 0x80) {
            colors = 2U << (flags & 7);
            if (!palette(&r, colors, gray)) goto failed;
        }
        if (!colors || transparent >= (int)colors) { result = EW_GIF_BAD_DATA; goto failed; }
        bytes = out->stride * out->height;
        out->pixels = far_alloc(bytes);
        if (transparent >= 0) out->opacity = far_alloc(bytes);
        workspace = far_alloc(sizeof(*workspace));
        if (!out->pixels || !workspace || (transparent >= 0 && !out->opacity)) {
            result = EW_GIF_NO_MEMORY; goto failed;
        }
        for (i = 0; i < bytes; ++i) {
            out->pixels[i] = 0;
            if (out->opacity) out->opacity[i] = 0;
        }
        /* A full-canvas first frame writes every pixel, including transparent
         * indices. Only partial frames need the logical-screen background. */
        if (left || top || width != out->width || height != out->height)
            for (y = 0; y < out->height; ++y)
                for (x = 0; x < out->width; ++x)
                    emit(out, x, y, background, 0, r.dither_shift);
        result = decode_pixels(&r, out, left, top, width, height, flags & 0x40,
                               gray, colors, transparent, workspace);
        far_free(workspace);
        workspace = 0;
        if (result != EW_GIF_OK) goto failed;
        return EW_GIF_OK;
    }
failed:
    if (workspace) far_free(workspace);
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
