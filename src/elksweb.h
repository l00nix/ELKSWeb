#ifndef ELKSWEB_H
#define ELKSWEB_H
#include <stddef.h>
#include <stdint.h>
#ifdef __ia16__
#define EW_FAR __far
#else
#define EW_FAR
#endif
#define EW_URL 768
#define EW_SOURCE 60000U
#define EW_DOCUMENT_SOURCE 120000UL
#define EW_TEXT 24576
#define EW_RUNS 1024
#define EW_LINKS 256
#define EW_HISTORY 8
#define EW_FIELD_VALUE 80
#define EW_BOLD 1
#define EW_UNDERLINE 2
#define EW_LARGE 4
#define EW_PRE 8
#define EW_ITALIC 16
#define EW_SMALL 32
#define EW_MONO 64
#define EW_RUN_TEXT 0
#define EW_RUN_RULE 1
#define EW_RUN_FIELD 2
#define EW_RUN_CHECK 3
#define EW_RUN_BUTTON 4
#define EW_RUN_IMAGE 5
#define EW_RUN_BOX 6
#define EW_RUN_BULLET 7
#define EW_RUN_PASSWORD 8
#define EW_RUN_RADIO 9
#define EW_RUN_SELECT 10
#define EW_RUN_TEXTAREA 11
#define EW_CONTROL_VALUE 1
#define EW_LINK_ISMAP 2
#define EW_IMAGE_ALT 128
#define EW_CHARSET_UTF8 0
#define EW_CHARSET_LATIN1 1
#define EW_CHARSET_CP1252 2
#define EW_CHARSET_LATIN2 3
#define EW_CHARSET_CP1250 4
extern unsigned char ew_document_charset;
unsigned ew_text_step(const char EW_FAR *s, unsigned position, int direction);
unsigned ew_display_text(const char EW_FAR *s, char *out, unsigned cap,
                         unsigned cursor, int password);
int ew_charset_name(const char *name);
int ew_charset_parameter(const char *content_type);
#define EW_CONTENT_HTML 0
#define EW_CONTENT_TEXT 1
#define EW_CONTENT_IMAGE 2
#define EW_CONTENT_BINARY 3
extern int ew_document_type;
extern char ew_document_media[64];
struct ew_run {
  short x, y;
  unsigned short off, n;
  unsigned short link;
  unsigned char style, kind, w;
};
struct ew_link {
  const char EW_FAR *url;
  char *name;
  char *value;
  unsigned char kind, checked, form, flags;
};
struct ew_form {
  char action[EW_URL];
  unsigned char post;
};
struct ew_document {
  char title[80];
  char EW_FAR *text;
  struct ew_run EW_FAR *runs;
  struct ew_link links[EW_LINKS];
  struct ew_form forms[4];
  unsigned short text_len, run_count;
  unsigned short link_count;
  unsigned char form_count, truncated;
  short height;
};
extern struct ew_document ew_doc;
extern char EW_FAR *ew_source;
int ew_source_init(void);
void ew_source_free(void);
extern char EW_FAR *ew_source_tail;
extern uint32_t ew_source_length;
int ew_source_put(uint32_t offset, unsigned char value);
int ew_document_reset(void);
void ew_copy_from_far(char *dst, const char EW_FAR *src, unsigned cap);
void ew_copy_to_far(void EW_FAR *dst, const void *src, unsigned size);
void ew_zero_far(void EW_FAR *dst, unsigned size);
const char EW_FAR *ew_store_url(const char *url);
void ew_parse_source(const char *base);
void ew_parse_text_source(const char *base);
int ew_anchor_y(const char *fragment);
void ew_parse_image_source(const char *url);
int32_t ew_fetch_document(const char *url, char *final_url, char *error,
                          unsigned errorcap, const char *post);
void ew_images_clear(void);
void ew_images_load(void);
int ew_images_load_document(const char *url);
const char *ew_image_document_error(void);
const char EW_FAR *ew_image_alt(const struct ew_run EW_FAR *run);
int ew_image_is_map(const struct ew_run EW_FAR *run);
int ew_image_map_point(const struct ew_run EW_FAR *run, int x, int y,
                       unsigned *map_x, unsigned *map_y);
/* Caller must set the display clip to the viewport or exposed scroll strip. */
void ew_image_draw(const struct ew_run EW_FAR *run, int x, int y, int top, int bottom,
                   int inverse);
void ew_parse(const char EW_FAR *html, const char *base);
int ew_resolve_url(const char *base, const char *ref, char *out, unsigned size);
int ew_host_is_ipv4(const char *host);
int32_t ew_fetch(const char *url, char EW_FAR *out, unsigned cap, char *final_url,
             char *error, unsigned errorcap, const char *post);
int ew_form_url(unsigned link, char *url, unsigned cap, char *post,
                unsigned postcap);
void EW_FAR *ew_far_alloc(unsigned long size);
void ew_far_free(void EW_FAR *ptr);
int ew_image_lookup(const char *url, unsigned *width, unsigned *height);
int ew_source_begin(void);
int ew_source_finish(uint32_t length);
void ew_source_abort(void);
unsigned char ew_source_byte(uint32_t offset);
const char *ew_source_error(void);
int32_t ew_fetch_to_fd(const char *url, int output_fd, uint32_t cap,
                       char *final_url, char *error, unsigned errorcap);
void ew_document_trim(void);
const char *ew_url_scheme(const char *url);
unsigned ew_select_count(unsigned link);
const char EW_FAR *ew_select_label(unsigned link, unsigned index);
int ew_select_index(unsigned link);
int ew_select_choose(unsigned link, unsigned index);
int ew_radio_choose(unsigned link);
#endif
