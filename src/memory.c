/* Segmented storage outside the application's near data segment.
 * SPDX-License-Identifier: GPL-2.0-or-later
 */
#include "elksweb.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#ifdef __ia16__
#include <malloc.h>
#endif

char EW_FAR *ew_source;
char EW_FAR *ew_source_tail;
uint32_t ew_source_length;
static char EW_FAR *document_text;
static struct ew_run EW_FAR *document_runs;
#define URL_BANK_SIZE 8192U
#define URL_BANKS 16
static char EW_FAR *urls[URL_BANKS];
static unsigned url_used[URL_BANKS];
static FILE *source_file;
static char source_path[40];
static char source_error[64];
static unsigned char source_cache[512];
static uint32_t source_cache_base, source_write_pos;
static unsigned source_cache_size;
static int source_writing;

const char *ew_source_error(void) { return source_error; }
static int source_fail(const char *message) {
  strncpy(source_error, message, sizeof(source_error) - 1);
  source_error[sizeof(source_error) - 1] = 0;
  return -1;
}
void ew_source_abort(void) {
  if (source_file) fclose(source_file);
  source_file = NULL;
  if (source_path[0]) unlink(source_path);
  source_path[0] = 0;
  source_writing = 0;
  source_cache_size = 0;
  ew_source_length = 0;
}
int ew_source_begin(void) {
  unsigned attempt;
  int fd = -1;
  ew_source_abort();
  source_error[0] = 0;
  /* Rendered text/runs are independent: failed navigation retains the page.
   * Reclaim legacy source segments before writing the disk-backed source.
   */
  ew_far_free(ew_source); ew_far_free(ew_source_tail);
  ew_source = ew_source_tail = NULL;
  for (attempt = 0; attempt < 16; ++attempt) {
    snprintf(source_path, sizeof(source_path), "/tmp/ew%04x%02x.htm",
             (unsigned)getpid() & 0xffffU, attempt);
    fd = open(source_path, O_RDWR | O_CREAT | O_EXCL, 0600);
    if (fd >= 0) break;
    if (errno != EEXIST) { source_path[0] = 0; return source_fail("Cannot create page cache in /tmp"); }
  }
  if (fd < 0) { source_path[0] = 0; return source_fail("Cannot create private page cache"); }
  source_file = fdopen(fd, "w+b");
  if (!source_file) {
    close(fd); unlink(source_path); source_path[0] = 0;
    return source_fail("Cannot open page cache stream");
  }
  source_writing = 1;
  source_write_pos = 0;
  source_cache_size = 0;
  return 0;
}
int ew_source_finish(uint32_t length) {
  if (!source_file || fflush(source_file) || fseek(source_file, 0L, SEEK_SET))
    return source_fail("Cannot flush or rewind page cache");
  ew_source_length = length;
  source_writing = 0;
  source_cache_size = 0;
  return 0;
}
unsigned char ew_source_byte(uint32_t offset) {
  if (!source_file || source_error[0] || offset >= ew_source_length) return 0;
  if (!source_cache_size || offset < source_cache_base ||
      offset >= source_cache_base + source_cache_size) {
    source_cache_base = offset & ~511UL;
    source_cache_size = 0;
    if (fseek(source_file, (long)source_cache_base, SEEK_SET)) {
      source_fail("Cannot seek page cache"); return 0;
    }
    source_cache_size = fread(source_cache, 1, sizeof(source_cache), source_file);
    if (!source_cache_size || ferror(source_file)) {
      source_fail("Cannot read page cache"); return 0;
    }
  }
  if (offset >= source_cache_base + source_cache_size) {
    source_fail("Incomplete page cache"); return 0;
  }
  return source_cache[(unsigned)(offset - source_cache_base)];
}
void EW_FAR *ew_far_alloc(unsigned long size)
{
#ifdef __ia16__
  return fmemalloc(size);
#else
  return malloc(size);
#endif
}
void ew_far_free(void EW_FAR *p)
{
  if (!p) return;
#ifdef __ia16__
  fmemfree(p);
#else
  free(p);
#endif
}
void ew_zero_far(void EW_FAR *dst, unsigned size)
{
  unsigned char EW_FAR *d = dst;
  while (size--) *d++ = 0;
}
void ew_copy_to_far(void EW_FAR *dst, const void *src, unsigned size)
{
  unsigned char EW_FAR *d = dst;
  const unsigned char *s = src;
  while (size--) *d++ = *s++;
}
void ew_copy_from_far(char *dst, const char EW_FAR *src, unsigned cap)
{
  if (!cap) return;
  while (--cap && src && *src) *dst++ = *src++;
  *dst = 0;
}
int ew_source_init(void)
{
  if (ew_source) return 0;
  ew_source = ew_far_alloc(EW_SOURCE);
  if (!ew_source) return -1;
  ew_source[0] = 0;
  return 0;
}
int ew_source_put(uint32_t offset, unsigned char value)
{
  if (source_writing) {
    if (offset >= 0x7ffffffeUL) return source_fail("File exceeds cache limit");
    if (offset != source_write_pos || fputc(value, source_file) == EOF)
      return source_fail("Cannot write page cache");
    ++source_write_pos;
    return 0;
  }
  if (offset >= EW_DOCUMENT_SOURCE) return source_fail("Page source exceeds cache limit");
  if (offset < EW_SOURCE) {
    ew_source[(unsigned)offset] = value;
  } else {
    if (!ew_source_tail) ew_source_tail = ew_far_alloc(EW_SOURCE);
    if (!ew_source_tail) return -1;
    ew_source_tail[(unsigned)(offset - EW_SOURCE)] = value;
  }
  return 0;
}
int ew_document_reset(void)
{
  if (!document_text) document_text = ew_far_alloc(EW_TEXT);
  if (!document_runs) document_runs = ew_far_alloc((unsigned long)EW_RUNS * sizeof(*document_runs));
  memset(&ew_doc, 0, sizeof(ew_doc));
  ew_doc.text = document_text;
  ew_doc.runs = document_runs;
  memset(url_used, 0, sizeof(url_used));
  if (!document_text || !document_runs) {
    strcpy(ew_doc.title, "Not enough memory for document");
    ew_doc.truncated = 1;
    return -1;
  }
  return 0;
}
void ew_document_trim(void)
{
  unsigned bank;
  /* Keep one small bank ready; return unused banks after reflow completes. */
  for (bank = 1; bank < URL_BANKS; ++bank) {
    if (!url_used[bank]) { ew_far_free(urls[bank]); urls[bank] = 0; }
  }
}
const char EW_FAR *ew_store_url(const char *url)
{
  unsigned bank, len = strlen(url) + 1, i;
  /* Common news pages repeat article URLs. Deduplicate before allocation. */
  for (i = 0; i < ew_doc.link_count; ++i) {
    const char EW_FAR *p = ew_doc.links[i].url;
    const char *q = url;
    if (!p) continue;
    while (*p && *p == *q) { ++p; ++q; }
    if (!*p && !*q) return ew_doc.links[i].url;
  }
  for (bank = 0; bank < URL_BANKS; ++bank) {
    if ((unsigned long)url_used[bank] + len > URL_BANK_SIZE) continue;
    if (!urls[bank]) urls[bank] = ew_far_alloc(URL_BANK_SIZE);
    if (urls[bank]) {
      char EW_FAR *p = urls[bank] + url_used[bank];
      ew_copy_to_far(p, url, len);
      url_used[bank] += len;
      return p;
    }
  }
  return 0;
}
void ew_source_free(void)
{
  unsigned bank;
  ew_source_abort();
  ew_far_free(ew_source); ew_far_free(ew_source_tail);
  ew_far_free(document_text); ew_far_free(document_runs);
  for (bank = 0; bank < URL_BANKS; ++bank) {
    ew_far_free(urls[bank]); urls[bank] = 0;
  }
  ew_source = ew_source_tail = document_text = 0;
  document_runs = 0;
  ew_source_length = 0;
  memset(&ew_doc, 0, sizeof(ew_doc));
}
