/* Test-only layout digest and parse-pass counter for reflow tests.
 * Linked with -Wl,--wrap=ew_document_reset so every parse_document pass is counted. */
#include "elksweb.h"
#include <stdint.h>
int __real_ew_document_reset(void);
static unsigned qa_passes;
int __wrap_ew_document_reset(void) { ++qa_passes; return __real_ew_document_reset(); }
unsigned qa_parse_passes(void) { unsigned n = qa_passes; qa_passes = 0; return n; }
static uint64_t mix(uint64_t h, const void *data, unsigned long n) {
  const unsigned char *p = data;
  while (n--) { h ^= *p++; h *= 1099511628211ULL; }
  return h;
}
uint64_t qa_layout_digest(void) {
  uint64_t h = 1469598103934665603ULL;
  h = mix(h, ew_doc.title, sizeof(ew_doc.title));
  h = mix(h, &ew_doc.run_count, sizeof(ew_doc.run_count));
  h = mix(h, &ew_doc.text_len, sizeof(ew_doc.text_len));
  h = mix(h, &ew_doc.link_count, sizeof(ew_doc.link_count));
  h = mix(h, &ew_doc.truncated, sizeof(ew_doc.truncated));
  h = mix(h, &ew_doc.height, sizeof(ew_doc.height));
  if (ew_doc.runs) h = mix(h, ew_doc.runs, (unsigned long)ew_doc.run_count * sizeof(*ew_doc.runs));
  if (ew_doc.text) h = mix(h, ew_doc.text, ew_doc.text_len);
  return h;
}
