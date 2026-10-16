/* Host test adapters only. Compile the actual native browser core unchanged. */
#include "elksweb.h"
int ew_screen_height=200, ew_pixel_aspect=2;
int ew_net_progress(const char *message) { (void)message; return 0; }
void ew_pixel(int x, int y, int color) { (void)x; (void)y; (void)color; }
void ew_fillrect(int x, int y, int w, int h, int color) { (void)x; (void)y; (void)w; (void)h; (void)color; }
void ew_vline(int x,int y,int h,int color) { ew_fillrect(x,y,1,h,color); }
const char *qa_title(void) { return ew_doc.title; }
unsigned qa_runs(void) { return ew_doc.run_count; }
unsigned qa_links(void) { return ew_doc.link_count; }
unsigned qa_truncated(void) { return ew_doc.truncated; }
int qa_style(unsigned n) { return n < ew_doc.run_count ? ew_doc.runs[n].style : -1; }
int qa_x(unsigned n) { return n < ew_doc.run_count ? ew_doc.runs[n].x : -1; }
int qa_y(unsigned n) { return n < ew_doc.run_count ? ew_doc.runs[n].y : -1; }
const char *qa_link(unsigned n) { return n < ew_doc.link_count ? ew_doc.links[n].url : ""; }
unsigned qa_text_len(void) { return ew_doc.text_len; }
unsigned qa_link_limit(void) { return EW_LINKS; }
unsigned qa_text_limit(void) { return EW_TEXT; }
unsigned qa_url_limit(void) { return EW_URL; }
unsigned qa_run_link(unsigned n) { return n < ew_doc.run_count ? ew_doc.runs[n].link : 0; }
/* No decoded image cache in parser-only tests; intrinsic dimensions unknown. */
#ifndef EW_QA_REAL_IMAGES
int ew_image_lookup(const char *url, unsigned *width, unsigned *height)
{ (void)url; (void)width; (void)height; return -1; }
#endif
const char *qa_run_data(unsigned n) { return n < ew_doc.run_count ? ew_doc.text + ew_doc.runs[n].off : ""; }
unsigned qa_run_length(unsigned n) { return n < ew_doc.run_count ? ew_doc.runs[n].n : 0; }
unsigned qa_run_kind(unsigned n) { return n < ew_doc.run_count ? ew_doc.runs[n].kind : 255; }
unsigned qa_small_style(void) { return EW_SMALL; }
unsigned qa_link_kind(unsigned n) { return n < ew_doc.link_count ? ew_doc.links[n].kind : 255; }
unsigned qa_link_checked(unsigned n) { return n < ew_doc.link_count ? ew_doc.links[n].checked : 0; }
const char *qa_link_value(unsigned n) { return n < ew_doc.link_count ? ew_doc.links[n].value : ""; }
unsigned qa_run_width_field(unsigned n) { return n < ew_doc.run_count ? ew_doc.runs[n].w : 0; }
