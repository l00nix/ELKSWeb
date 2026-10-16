/* ELKSWeb: an original C browser for 8088-class ELKS machines.
 * SPDX-License-Identifier: GPL-2.0-or-later */
#include "../font/body_font.h"
#include "../font/font.h"
#include "elks_platform.h"
#include "elksweb.h"
#include "version.h"
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>

static char current[EW_URL], address[EW_URL], status[96];
static char EW_FAR *history[EW_HISTORY];
static short scroll, hscroll, painted_scroll;
static int page_width, hovered = -1;
static int focused = -1, editing = 0, selectall = 0, inverse = 0, chrome = 1;
/* Independent damage regions: ordinary page painting never erases chrome. */
#define DRAW_PAGE 1
#define DRAW_ADDRESS 2
#define DRAW_STATUS 4
#define DRAW_TITLE 8
#define DRAW_FRAME 16
#define DRAW_ALL 31
#define DRAW_SCROLL 32
static int hcount = 0, hpos = -1, dirty = DRAW_ALL;
static unsigned field_pos, address_pos;
static int mouse_active, mouse_x = 320, mouse_y = 100, scroll_drag, drag_offset;
static int load_images = 1;
static int select_open = -1, select_cursor, select_first;
static int select_x, select_y, select_width, select_rows;
static int download_edit;
static char download_name[128];
static unsigned download_pos;
static int download_button;
static volatile int stopping;
extern int ew_fetch_truncated;
static int top(void) { return chrome ? 22 : 0; }
static int bottom(void) { return EW_SCREEN_HEIGHT - (chrome ? 8 : 0); }
static int fg(void) { return inverse ? 1 : 0; }
static int bg(void) { return inverse ? 0 : 1; }
static int text_field(unsigned kind) {
  return kind == EW_RUN_FIELD || kind == EW_RUN_PASSWORD ||
         kind == EW_RUN_TEXTAREA;
}
static unsigned field_display(const struct ew_link *link, char *out) {
  return ew_display_text(link->value,out,3*EW_FIELD_VALUE,field_pos,
                         link->kind==EW_RUN_PASSWORD);
}
static unsigned field_start(const struct ew_link *link, const char *display,
                             unsigned caret, int width) {
  unsigned start=0, offset=0;
  char scratch[3*EW_FIELD_VALUE];
  while (start<field_pos && ew_body_width(display+offset,caret-offset,0)>width) {
    start=ew_text_step(link->value,start,1);
    offset=ew_display_text(link->value,scratch,sizeof(scratch),start,
                           link->kind==EW_RUN_PASSWORD);
  }
  return start;
}
static void select_geometry(void) {
  unsigned i;
  select_rows = ew_select_count(select_open);
  if (select_rows > 8) select_rows = 8;
  for (i = 0; i < ew_doc.run_count; i++) {
    struct ew_run EW_FAR *r = &ew_doc.runs[i];
    if ((int)r->link != select_open + 1) continue;
    select_x = r->x - hscroll;
    select_width = r->w;
    if (select_x + select_width > 624) select_x = 624 - select_width;
    if (select_x < 0) select_x = 0;
    select_y = top() + r->y - scroll + 12;
    if (select_y + select_rows * 10 + 2 > bottom())
      select_y = bottom() - select_rows * 10 - 2;
    if (select_y < top()) select_y = top();
    break;
  }
  if (select_cursor < select_first) select_first = select_cursor;
  if (select_cursor >= select_first + select_rows)
    select_first = select_cursor - select_rows + 1;
}
static void thumb(int *y, int *height) {
  int view = bottom() - top(), range = view - 2;
  *y = top() + 1;
  *height = range;
  if (ew_doc.height <= view)
    return;
  *height = (int)((long)range * view / ew_doc.height);
  if (*height < 8)
    *height = 8;
  *y += (int)((long)(range - *height) * scroll / (ew_doc.height - view));
}
static void draw(void);
static int text_width(const char EW_FAR *text, unsigned n, unsigned st) {
  if (st & EW_MONO)
    return ew_mono_width(text, n, !!(st & EW_BOLD),
                         st & EW_SMALL ? 0 : st & EW_LARGE ? 2 : 1);
  if (st & EW_SMALL)
    return ew_small_width(text, n, !!(st & EW_BOLD));
  return st & EW_LARGE ? ew_font_width(text, n, !!(st & EW_BOLD))
                       : ew_body_width(text, n, !!(st & EW_BOLD));
}
static int run_width(const struct ew_run EW_FAR *r) {
  if (r->kind == EW_RUN_TEXT) return text_width(ew_doc.text + r->off, r->n, r->style);
  if (r->kind == EW_RUN_IMAGE || r->kind == EW_RUN_BOX || r->kind == EW_RUN_RULE)
    return r->n;
  return r->w;
}
static int run_height(const struct ew_run EW_FAR *r) {
  if (r->kind == EW_RUN_BOX) return r->off ? r->off : r->w;
  if (r->kind == EW_RUN_IMAGE) return r->w;
  if (r->kind == EW_RUN_TEXT)
    return r->style & EW_SMALL ? 6 : r->style & EW_LARGE ? 10 : 8;
  return 12;
}
static void measure_page(void) {
  unsigned i;
  page_width = 624;
  for (i = 0; i < ew_doc.run_count; i++) {
    int right = ew_doc.runs[i].x + run_width(&ew_doc.runs[i]);
    if (right > page_width) page_width = right;
  }
}
static int hit_link(int x, int y) {
  unsigned i;
  if (x >= 624 || y < top() || y >= bottom()) return -1;
  for (i = 0; i < ew_doc.run_count; i++) {
    struct ew_run EW_FAR *r = &ew_doc.runs[i];
    int left = r->x - hscroll, y0 = r->y + top() - scroll;
    if (r->link && ew_doc.links[r->link - 1].kind == 0 &&
        x >= left && x < left + run_width(r) &&
        y >= y0 && y < y0 + run_height(r)) return r->link - 1;
  }
  return -1;
}
static void stopped(int sig) {
  (void)sig;
  stopping = 1;
}
static void message(const char *s) {
  strncpy(status, s, sizeof(status) - 1);
  status[sizeof(status) - 1] = 0;
  dirty |= DRAW_STATUS;
}
static void textn(int x, int y, const char EW_FAR *s, unsigned n, int f, int b,
                  unsigned st) {
  unsigned i;
  int start = x, bold = !!(st & EW_BOLD), large = !!(st & EW_LARGE);
  int small = !!(st & EW_SMALL), height = small ? 6 : large ? 10 : 8;
  if (b >= 0)
    ew_fillrect(x, y, text_width(s, n, st), height, b);
  for (i = 0; i < n; i++) {
    if (st & EW_MONO)
      ew_mono_draw(x, y, (unsigned char)s[i], f, -1, bold,
                   !!(st & EW_ITALIC), small ? 0 : large ? 2 : 1);
    else if (small)
      ew_small_draw(x, y, (unsigned char)s[i], f, -1, bold, !!(st & EW_ITALIC));
    else if (!large)
      ew_body_draw(x, y, (unsigned char)s[i], f, -1, bold, !!(st & EW_ITALIC));
    else if (st & EW_ITALIC)
      ew_font_draw_italic(x, y, (unsigned char)s[i], f, -1, bold);
    else
      ew_font_draw(x, y, (unsigned char)s[i], f, -1, bold);
    x += st & EW_MONO ? ew_mono_char_width((unsigned char)s[i], bold,
                                          small ? 0 : large ? 2 : 1)
         : small   ? ew_small_char_width((unsigned char)s[i], bold)
         : large ? ew_font_char_width((unsigned char)s[i], bold)
                 : ew_body_char_width((unsigned char)s[i], bold);
  }
  if (st & EW_UNDERLINE)
    ew_hline(start, y + height - 1, x - start, f);
}
static void centered_text(int y, const char *s, unsigned style) {
  unsigned n = strlen(s);
  while (n && text_width(s, n, style) > 608) n--;
  textn((624 - text_width(s, n, style)) / 2, y, s, n, fg(), bg(), style);
}
static void draw(void) {
  unsigned i;
  int x, y, f = fg(), b = bg(), t = top(), bot = bottom(), active;
  int paint_top = t, paint_bottom = bot, delta = scroll - painted_scroll;
  struct ew_run EW_FAR *r;
  struct ew_link *l;
  char temp[81];
  ew_cursor_hide();
  if (dirty & DRAW_FRAME) {
    ew_clear(b);
    dirty |= DRAW_ALL;
  }
  if ((dirty & (DRAW_PAGE | DRAW_SCROLL)) == DRAW_SCROLL) {
    if (!delta) dirty &= ~DRAW_SCROLL;
    else if (select_open < 0 && !download_edit && delta < bot-t && delta > t-bot) {
      ew_scroll(t, bot, delta);
      if (delta > 0) paint_top = bot-delta;
      else paint_bottom = t-delta;
    } else dirty |= DRAW_PAGE;
  }
  if (dirty & (DRAW_PAGE | DRAW_SCROLL)) {
    ew_clip(624, paint_top, paint_bottom);
    ew_fillrect(0, paint_top, 624, paint_bottom - paint_top, b);
    for (i = 0; !download_edit && i < ew_doc.run_count; i++) {
      r = &ew_doc.runs[i];
      x = r->x - hscroll;
      y = t + r->y - scroll;
      if (r->kind == EW_RUN_IMAGE) {
        ew_image_draw(r, x, y, paint_top, paint_bottom, inverse);
        continue;
      }
      if (y + run_height(r) <= paint_top || y >= paint_bottom)
        continue;
      active = !editing && r->link && (int)r->link == focused + 1;
      if (r->kind == EW_RUN_TEXT) {
        textn(x, y, ew_doc.text + r->off, r->n, active ? b : f, active ? f : b,
              r->style);
        continue;
      }
      if (r->kind == EW_RUN_BOX) {
        ew_rect(x, y, r->n, run_height(r), f);
        continue;
      }
      if (r->kind == EW_RUN_RULE) {
        ew_hline(x, y, r->n, f);
        continue;
      }
      if (r->kind == EW_RUN_BULLET) {
        ew_hline(x + 1, y + 2, 2, f);
        ew_hline(x, y + 3, 4, f);
        ew_hline(x + 1, y + 4, 2, f);
        continue;
      }
      if (!r->link)
        continue;
      l = &ew_doc.links[r->link - 1];
      ew_rect(x, y, r->w, 12, f);
      if (active)
        ew_rect(x + 1, y + 1, r->w - 2, 10, f);
      if (r->kind == EW_RUN_CHECK || r->kind == EW_RUN_RADIO) {
        if (r->kind == EW_RUN_RADIO) {
          ew_fillrect(x, y, 12, 12, b);
          ew_hline(x + 3, y + 1, 6, f);
          ew_hline(x + 3, y + 10, 6, f);
          ew_vline(x + 1, y + 3, 6, f);
          ew_vline(x + 10, y + 3, 6, f);
          ew_pixel(x + 2, y + 2, f);
          ew_pixel(x + 9, y + 2, f);
          ew_pixel(x + 2, y + 9, f);
          ew_pixel(x + 9, y + 9, f);
          if (active) ew_rect(x + 3, y + 3, 6, 6, f);
        }
        if (l->checked) {
          ew_hline(x + 3, y + 5, 6, f);
          ew_hline(x + 3, y + 6, 6, f);
        }
      } else {
        char display[3*EW_FIELD_VALUE];
        const char *value=display;
        unsigned start=0, caret, n;
        int available=r->w-(r->kind==EW_RUN_SELECT ? 15 : 6);
        caret=field_display(l,display);
        if (!l->value[0] && r->kind==EW_RUN_BUTTON) strcpy(display,"Submit");
        if (active && text_field(r->kind)) {
          start=field_start(l,display,caret,r->w-7);
          start=ew_display_text(l->value,display,sizeof(display),start,
                                r->kind==EW_RUN_PASSWORD);
        }
        n=strlen(display)-start;
        value+=start;
        while (n && ew_body_width(value,n,0)>available) --n;
        textn(x+3,y+2,value,n,f,b,0);
        if (active && text_field(r->kind) && caret-start<=n)
          ew_vline(x+3+ew_body_width(value,caret-start,0),y+2,8,f);
        if (r->kind == EW_RUN_SELECT) {
          ew_vline(x + r->w - 13, y, 12, f);
          ew_hline(x + r->w - 10, y + 4, 7, f);
          ew_hline(x + r->w - 9, y + 5, 5, f);
          ew_hline(x + r->w - 8, y + 6, 3, f);
        }
      }
    }
    painted_scroll = scroll;
    ew_clip(640, 0, EW_SCREEN_HEIGHT);
    ew_fillrect(625, t + 1, 14, bot - t - 2, b);
    if (dirty & DRAW_FRAME) ew_rect(624, t, 16, bot - t, f);
    if (!download_edit && ew_doc.height > bot - t) {
      int h, center;
      thumb(&y, &h);
      ew_hline(627, y, 10, f);
      ew_hline(627, y + h - 1, 10, f);
      ew_vline(626, y + 1, h - 2, f);
      ew_vline(637, y + 1, h - 2, f);
      center = y + h / 2;
      ew_hline(628, center - 2, 8, f);
      ew_hline(628, center, 8, f);
      ew_hline(628, center + 2, 8, f);
    }
  }
  if (chrome) {
    if (dirty & DRAW_FRAME) {
      ew_hline(0, 21, 640, f);
      ew_rect(0, 8, 30, 12, f);
      textn(12, 9, "<", 1, f, b, 0);
      ew_rect(32, 8, 29, 12, f);
      textn(43, 9, ">", 1, f, b, 0);
      ew_rect(63, 8, 577, 12, f);
      ew_hline(0, bot, 640, f);
    }
    if (dirty & DRAW_TITLE) {
      ew_fillrect(0, 0, 640, 8, b);
      strncpy(temp, download_edit ? "" : ew_doc.title, sizeof(temp) - 1);
      temp[80] = 0;
      textn((640 - ew_body_width(temp, strlen(temp), 0)) / 2, 0, temp,
            strlen(temp), f, b, 0);
    }
    if (dirty & DRAW_ADDRESS) {
      const char *s = editing || download_edit ? address : current;
      unsigned len = strlen(s), start = 0;
      ew_fillrect(64, 9, 575, 10, b);
      if (editing && !selectall) {
        while (start < address_pos &&
               ew_body_width(s + start, address_pos - start, 0) > 567)
          start++;
      }
      len -= start;
      while (len && ew_body_width(s + start, len, 0) > 568)
        len--;
      textn(66, 9, s + start, len, editing && selectall ? b : f,
            editing && selectall ? f : b, 0);
      if (editing && !selectall)
        ew_vline(66 + ew_body_width(
                          s + start,
                          address_pos > start ? address_pos - start : 0, 0),
                 9, 10, f);
    }
    if (dirty & DRAW_STATUS) {
      const char EW_FAR *s = status;
      if (!status[0] && !editing && hovered >= 0)
        s = ew_doc.links[hovered].url;
      else if (!status[0] && !editing && focused >= 0 && ew_doc.links[focused].kind == 0)
        s = ew_doc.links[focused].url;
      ew_fillrect(0, bot + 1, 640, 7, b);
      ew_copy_from_far(temp, s, 80);
      textn(0, EW_SCREEN_HEIGHT - 7, temp, strlen(temp), f, b, EW_SMALL);
    }
  }
  if (dirty & DRAW_PAGE) {
    ew_clip(624, t, bot);
    if (select_open >= 0) {
      int has_scroll = ew_select_count(select_open) > 8;
      select_geometry();
      ew_fillrect(select_x, select_y, select_width, select_rows * 10 + 2, b);
      ew_rect(select_x, select_y, select_width, select_rows * 10 + 2, f);
      for (i = 0; i < (unsigned)select_rows; i++) {
        unsigned n;
        int chosen = select_first + (int)i == select_cursor;
        const char EW_FAR *label = ew_select_label(select_open, select_first + i);
        ew_display_text(label,temp,sizeof(temp),0,0);
        n = strlen(temp);
        while (n && ew_body_width(temp, n, 0) > select_width - (has_scroll ? 19 : 6)) n--;
        if (chosen) ew_fillrect(select_x + 1, select_y + 1 + i * 10,
                               select_width - (has_scroll ? 15 : 2), 10, f);
        textn(select_x + 3, select_y + 2 + i * 10, temp, n,
              chosen ? b : f, chosen ? f : b, 0);
      }
      if (has_scroll) {
        int x = select_x + select_width - 13;
        int end = select_y + select_rows * 10 + 1;
        ew_vline(x, select_y, end - select_y, f);
        ew_hline(x + 4, select_y + 4, 3, f);
        ew_hline(x + 3, select_y + 5, 5, f);
        ew_hline(x + 2, select_y + 6, 7, f);
        ew_hline(x + 2, end - 6, 7, f);
        ew_hline(x + 3, end - 5, 5, f);
        ew_hline(x + 4, end - 4, 3, f);
      }
    }
    if (download_edit) {
      unsigned start = 0, n = strlen(download_name);
      centered_text(28, "Do you want to download this file?", EW_LARGE | EW_BOLD);
      ew_hline(8, 46, 608, f);
      centered_text(51, address, EW_SMALL | EW_BOLD);
      snprintf(temp, sizeof(temp), "Content type: %s", ew_document_media);
      centered_text(59, temp, EW_SMALL | EW_BOLD);
      snprintf(temp, sizeof(temp), "Size: %lu KB", (unsigned long)ew_source_length / 1024);
      centered_text(67, temp, EW_SMALL | EW_BOLD);
      ew_hline(8, 78, 608, f);
      ew_rect(77, 82, 468, 12, f);
      while (start < download_pos &&
             ew_body_width(download_name + start, download_pos - start, 0) > 457)
        start++;
      n -= start;
      while (n && ew_body_width(download_name + start, n, 0) > 460) n--;
      textn(80, 83, download_name + start, n, f, b, 0);
      if (!download_button)
        ew_vline(80 + ew_body_width(download_name + start, download_pos - start, 0),
                 83, 10, f);
      ew_rect(273, 102, 75, 12, f);
      if (download_button) ew_rect(274, 103, 73, 10, f);
      textn(281, 103, "Download", 8, f, b, 0);
    }
    ew_clip(640, 0, EW_SCREEN_HEIGHT);
  }
  dirty = 0;
  if (mouse_active)
    ew_cursor_show(mouse_x, mouse_y);
}
int ew_net_progress(const char *s) {
  int k = ew_getkey();
  if (k == EW_KEY_ESC || stopping)
    return 1;
  if (strcmp(status, s)) {
    message(s);
    draw();
  }
  return 0;
}
static int remember(const char *url) {
  int i, insert = hpos + 1;
  unsigned n = 0;
  char EW_FAR *slot;
  if (hpos >= 0 && hpos < hcount) {
    while (url[n] && url[n] == history[hpos][n]) n++;
    if (!url[n] && !history[hpos][n]) return 1;
  }
  if (insert > hcount) insert = hcount;
  slot = insert < hcount ? history[insert] :
         hcount == EW_HISTORY ? history[0] : ew_far_alloc(EW_URL);
  if (!slot) { hpos = hcount; return 0; }
  for (i = insert + 1; i < hcount; i++) {
    ew_far_free(history[i]); history[i] = NULL;
  }
  hcount = insert;
  if (hcount == EW_HISTORY) {
    memmove(history, history + 1, (EW_HISTORY - 1) * sizeof(history[0]));
    hcount--;
  }
  ew_copy_to_far(slot, url, strlen(url) + 1);
  history[hcount++] = slot;
  hpos = hcount - 1;
  return 1;
}
static int load(const char *url, const char *post, int add_history) {
  static char target[EW_URL], resolved[EW_URL], err[96];
  int32_t n;
  int history_limited = 0;
  /* History and reload already contain resolved identities. In particular,
   * a saved local /path must not inherit the current HTTP origin. */
  if (ew_resolve_url(add_history ? current : "", url, target, sizeof(target))) {
    message("Address is too long");
    return 0;
  }
  message("Loading...");
  draw();
  n = ew_fetch_document(target, resolved, err, sizeof(err), post);
  if (n < 0) {
    message(err);
    draw();
    return 0;
  }
  if (ew_document_type == EW_CONTENT_BINARY) {
    if (ew_fetch_truncated) { message("Download exceeds file size limit"); return 0; }
    strcpy(download_name, "/root/download.bin");
    strcpy(address, resolved);
    download_pos = strlen(download_name);
    download_edit = 1;
    download_button = 0;
    editing = 0;
    hovered = -1;
    ew_cursor_shape(0);
    if (!chrome) dirty |= DRAW_ALL;
    chrome = 1;
    select_open = -1;
    dirty |= DRAW_PAGE | DRAW_TITLE | DRAW_ADDRESS;
    message("Choose a filename for the download");
    return 0;
  }
  strcpy(current, resolved);
  strcpy(address, resolved);
  dirty |= DRAW_ADDRESS;
  ew_images_clear();
  message("Parsing...");
  draw();
  if (ew_document_type == EW_CONTENT_TEXT) ew_parse_text_source(current);
  else if (ew_document_type == EW_CONTENT_IMAGE) {
    ew_images_load_document(current);
    ew_parse_image_source(current);
  } else ew_parse_source(current);
  scroll = 0;
  hscroll = 0;
  hovered = -1;
  ew_cursor_shape(0);
  focused = -1;
  editing = 0;
  select_open = -1;
  if (add_history)
    history_limited = !remember(current);
  message("");
  dirty |= DRAW_PAGE | DRAW_TITLE | DRAW_ADDRESS;
  measure_page();
  draw();
  {
    int html_truncated = ew_fetch_truncated;
    if (load_images && ew_document_type == EW_CONTENT_HTML) {
      unsigned image_run;
      for (image_run = 0; image_run < ew_doc.run_count; ++image_run)
        if (ew_doc.runs[image_run].kind == EW_RUN_IMAGE) break;
      if (image_run < ew_doc.run_count) {
        ew_images_load();
        ew_parse_source(current);
        dirty |= DRAW_TITLE;
      }
    }
    ew_fetch_truncated = html_truncated;
  }
  measure_page();
  {
    const char *fragment = strchr(current, '#');
    int max = ew_doc.height - (bottom() - top());
    if (fragment) {
      int y = ew_anchor_y(fragment + 1);
      if (y >= 0) scroll = y;
      if (max < 0) max = 0;
      if (scroll > max) scroll = max;
    }
  }
  if (ew_document_type == EW_CONTENT_IMAGE && ew_image_document_error()[0])
    message(ew_image_document_error());
  else if (ew_source_error()[0])
    message(ew_source_error());
  else if (ew_doc.truncated || ew_fetch_truncated)
    message("Page truncated: memory limit reached");
  else if (history_limited)
    message("History unavailable: not enough memory");
  else
    message("");
  dirty |= DRAW_PAGE | DRAW_STATUS;
  return 1;
}
static void history_go(int index) {
  if (index < 0 || index >= hcount) return;
  if (editing) {
    editing = 0;
    dirty |= DRAW_PAGE | DRAW_ADDRESS | DRAW_STATUS;
  }
  ew_copy_from_far(address, history[index], sizeof(address));
  if (load(address, NULL, 0)) hpos = index;
}
static void image_map(const struct ew_run EW_FAR *r, int x, int y) {
  unsigned mx, my, length, at, extra;
  char suffix[24], *fragment;
  if (ew_image_map_point(r, x, y, &mx, &my)) return;
  ew_copy_from_far(address, ew_doc.links[r->link - 1].url, sizeof(address));
  length = strlen(address);
  fragment = strchr(address, '#');
  at = fragment ? (unsigned)(fragment - address) : length;
  snprintf(suffix, sizeof(suffix), "?%u,%u", mx, my);
  extra = strlen(suffix);
  if (length + extra >= sizeof(address)) { message("Image map URL is too long"); return; }
  memmove(address + at + extra, address + at, length - at + 1);
  memcpy(address + at, suffix, extra);
  load(address, NULL, 1);
}
static int same_radio(unsigned a, unsigned b) {
  struct ew_link *first = &ew_doc.links[a], *second = &ew_doc.links[b];
  return first->kind == EW_RUN_RADIO && second->kind == EW_RUN_RADIO &&
         first->name[0] && first->form == second->form && !strcmp(first->name, second->name);
}
static int radio_tabstop(unsigned index) {
  unsigned i, first = index;
  if (ew_doc.links[index].checked || !ew_doc.links[index].name[0]) return 1;
  for (i = 0; i < ew_doc.link_count; i++) if (same_radio(index, i)) {
    if (ew_doc.links[i].checked) return 0;
    if (i < first) first = i;
  }
  return first == index;
}
static void focus_visible(void) {
  unsigned i;
  for (i = 0; i < ew_doc.run_count; i++)
    if ((int)ew_doc.runs[i].link == focused + 1) {
      int y = ew_doc.runs[i].y;
      int x = ew_doc.runs[i].x;
      if (y < scroll)
        scroll = y;
      else if (y > scroll + bottom() - top() - 18)
        scroll = y - (bottom() - top()) + 18;
      if (x < hscroll) hscroll = x;
      else if (x >= hscroll + 624) hscroll = x - 608;
      break;
    }
  field_pos = ew_doc.links[focused].kind == EW_RUN_PASSWORD
                  ? strlen(ew_doc.links[focused].value) : 0;
  dirty |= DRAW_PAGE | DRAW_STATUS;
}
static void focus_next(int delta) {
  int tries = ew_doc.link_count;
  if (!tries) return;
  do {
    focused += delta;
    if (focused < 0) focused = ew_doc.link_count - 1;
    if (focused >= (int)ew_doc.link_count) focused = 0;
  } while ((ew_doc.links[focused].kind == 6 ||
            (ew_doc.links[focused].kind == EW_RUN_RADIO && !radio_tabstop(focused))) && --tries);
  focus_visible();
}
static void radio_move(int delta) {
  int next = focused, tries = ew_doc.link_count;
  while (tries--) {
    next += delta;
    if (next < 0) next = ew_doc.link_count - 1;
    if (next >= (int)ew_doc.link_count) next = 0;
    if (same_radio(focused, next)) {
      ew_radio_choose(next);
      focused = next;
      focus_visible();
      return;
    }
  }
}
static void activate(void) {
  static char url[EW_URL], post[512];
  struct ew_link *l;
  if (focused < 0)
    return;
  l = &ew_doc.links[focused];
  if (l->kind == 0) {
    ew_copy_from_far(url, l->url, sizeof(url));
    load(url, NULL, 1);
  } else if (l->kind == EW_RUN_CHECK) {
    l->checked = !l->checked;
    dirty |= DRAW_PAGE | DRAW_STATUS;
  } else if (l->kind == EW_RUN_RADIO) {
    ew_radio_choose(focused);
    dirty |= DRAW_PAGE | DRAW_STATUS;
  } else if (l->kind == EW_RUN_SELECT) {
    if (ew_select_count(focused)) {
      select_open = focused;
      select_cursor = ew_select_index(focused);
      if (select_cursor < 0) select_cursor = 0;
      select_first = 0;
      dirty |= DRAW_PAGE | DRAW_STATUS;
    }
  } else if (l->kind == EW_RUN_BUTTON || text_field(l->kind)) {
    if (ew_form_url(focused, url, sizeof(url), post, sizeof(post)))
      message("Cannot submit form");
    else
      load(url, ew_doc.forms[l->form - 1].post ? post : NULL, 1);
  }
}
static void key(int k) {
  int max = ew_doc.height - (bottom() - top());
  unsigned n;
  if (download_edit) {
    n = strlen(download_name);
    if (k == EW_KEY_ESC) { download_edit = 0; dirty |= DRAW_TITLE | DRAW_ADDRESS; message("Download cancelled"); }
    else if (k == EW_KEY_TAB || k == EW_KEY_BACKTAB) download_button = !download_button;
    else if (k == EW_KEY_F6 || k == 12) { download_edit = 0; dirty |= DRAW_TITLE; key(k); }
    else if (k == EW_KEY_ENTER || (download_button && k == ' ')) {
      static unsigned char buffer[512];
      uint32_t offset = 0;
      int out = open(download_name, O_WRONLY | O_CREAT | O_EXCL, 0600);
      int failed = 0;
      if (out < 0) { message(errno == EEXIST ? "File exists: choose another name" :
                             "Cannot create download file"); return; }
      while (offset < ew_source_length && !failed) {
        unsigned i, count = ew_source_length - offset > sizeof(buffer) ?
                             sizeof(buffer) : (unsigned)(ew_source_length - offset);
        unsigned done = 0;
        for (i = 0; i < count; i++) buffer[i] = ew_source_byte(offset + i);
        if (ew_source_error()[0] || ew_net_progress("Saving file...")) {
          failed = 1; break;
        }
        while (done < count) {
          int wrote = write(out, buffer + done, count - done);
          if (wrote < 0 && errno == EINTR) continue;
          if (wrote <= 0) { failed = 1; break; }
          done += wrote;
        }
        offset += count;
      }
      if (close(out)) failed = 1;
      if (failed) {
        message(unlink(download_name) ? "Save failed; incomplete file remains" :
                "Save failed or cancelled; incomplete file removed");
      } else { download_edit = 0; dirty |= DRAW_TITLE | DRAW_ADDRESS; message("File saved"); }
    } else if (download_button) { /* Typing does not edit an unfocused field. */ }
    else if (k == EW_KEY_HOME) download_pos = 0;
    else if (k == EW_KEY_END) download_pos = n;
    else if (k == EW_KEY_LEFT && download_pos) download_pos--;
    else if (k == EW_KEY_RIGHT && download_pos < n) download_pos++;
    else if (k == EW_KEY_BACKSPACE && download_pos) {
      download_pos--;
      memmove(download_name + download_pos, download_name + download_pos + 1,
               n - download_pos);
    } else if (k == EW_KEY_DELETE && download_pos < n)
      memmove(download_name + download_pos, download_name + download_pos + 1,
               n - download_pos);
    else if (k >= 32 && k < 127 && n + 1 < sizeof(download_name)) {
      memmove(download_name + download_pos + 1, download_name + download_pos,
               n - download_pos + 1);
      download_name[download_pos++] = k;
    }
    dirty |= DRAW_PAGE | DRAW_STATUS;
    return;
  }
  if (select_open >= 0) {
    int count = ew_select_count(select_open);
    if (k == EW_KEY_UP && select_cursor > 0) select_cursor--;
    else if (k == EW_KEY_DOWN && select_cursor + 1 < count) select_cursor++;
    else if (k == EW_KEY_HOME) select_cursor = 0;
    else if (k == EW_KEY_END) select_cursor = count - 1;
    else if (k == EW_KEY_ENTER || k == ' ') {
      ew_select_choose(select_open, select_cursor);
      select_open = -1;
    } else if (k == EW_KEY_ESC) select_open = -1;
    else if (k == EW_KEY_TAB || k == EW_KEY_BACKTAB || k == EW_KEY_F6) {
      select_open = -1;
      key(k);
    }
    dirty |= DRAW_PAGE | DRAW_STATUS;
    return;
  }
  if (k == EW_KEY_F6 || k == 12) {
    if (!chrome) dirty |= DRAW_ALL;
    dirty |= DRAW_ADDRESS;
    editing = 1;
    chrome = 1;
    selectall = 1;
    address_pos = 0;
    strcpy(address, current);
    dirty |= DRAW_PAGE | DRAW_STATUS;
    return;
  }
  if (k == EW_KEY_F2) {
    inverse = !inverse;
    dirty |= DRAW_ALL;
    return;
  }
  if (k == EW_KEY_F3) {
    chrome = !chrome;
    dirty |= DRAW_ALL;
    return;
  }
  if (editing) {
    n = strlen(address);
    if (k == EW_KEY_ESC) {
      editing = 0;
      dirty |= DRAW_ADDRESS | DRAW_PAGE | DRAW_STATUS;
      return;
    }
    if (k == EW_KEY_ENTER) {
      editing = 0;
      dirty |= DRAW_ADDRESS | DRAW_PAGE | DRAW_STATUS;
      load(address, NULL, 1);
      return;
    }
    if (address_pos > n)
      address_pos = n;
    if (k == EW_KEY_LEFT) {
      if (selectall) {
        address_pos = 0;
        selectall = 0;
      } else if (address_pos)
        address_pos--;
      dirty |= DRAW_ADDRESS;
      return;
    }
    if (k == EW_KEY_RIGHT) {
      if (selectall) {
        address_pos = n;
        selectall = 0;
      } else if (address_pos < n)
        address_pos++;
      dirty |= DRAW_ADDRESS;
      return;
    }
    if (k == EW_KEY_HOME) {
      address_pos = 0;
      selectall = 0;
      dirty |= DRAW_ADDRESS;
      return;
    }
    if (k == EW_KEY_END) {
      address_pos = n;
      selectall = 0;
      dirty |= DRAW_ADDRESS;
      return;
    }
    if (k == EW_KEY_BACKSPACE || k == EW_KEY_DELETE) {
      if (selectall) {
        address[0] = 0;
        address_pos = 0;
      } else if (k == EW_KEY_BACKSPACE && address_pos) {
        address_pos--;
        memmove(address + address_pos, address + address_pos + 1,
                n - address_pos);
      } else if (k == EW_KEY_DELETE && address_pos < n)
        memmove(address + address_pos, address + address_pos + 1,
                n - address_pos);
      selectall = 0;
      dirty |= DRAW_ADDRESS;
      return;
    }
    if (k >= 32 && k < 127) {
      if (selectall) {
        address[0] = 0;
        n = address_pos = 0;
      }
      selectall = 0;
      if (n + 1 < sizeof(address)) {
        memmove(address + address_pos + 1, address + address_pos,
                n - address_pos + 1);
        address[address_pos++] = k;
      }
      dirty |= DRAW_ADDRESS;
    }
    return;
  }
  if (k == EW_KEY_ESC) {
    stopping = 1;
    return;
  }
  if (k == EW_KEY_F5) {
    load(current, NULL, 0);
    return;
  }
  if (k == EW_KEY_TAB) {
    focus_next(1);
    return;
  }
  if (k == EW_KEY_BACKTAB) {
    focus_next(-1);
    return;
  }
  if (k == EW_KEY_ENTER) {
    activate();
    return;
  }
  if (k == ' ' && focused >= 0 &&
      (ew_doc.links[focused].kind == EW_RUN_CHECK ||
       ew_doc.links[focused].kind == EW_RUN_RADIO ||
       ew_doc.links[focused].kind == EW_RUN_SELECT)) {
    activate();
    return;
  }
  if (focused >= 0 && ew_doc.links[focused].kind == EW_RUN_SELECT &&
      (k == EW_KEY_UP || k == EW_KEY_DOWN)) {
    int index = ew_select_index(focused) + (k == EW_KEY_UP ? -1 : 1);
    if (index >= 0 && index < (int)ew_select_count(focused))
      ew_select_choose(focused, index);
    dirty |= DRAW_PAGE | DRAW_STATUS;
    return;
  }
  if (focused >= 0 && ew_doc.links[focused].kind == EW_RUN_RADIO &&
      (k == EW_KEY_UP || k == EW_KEY_DOWN || k == EW_KEY_LEFT || k == EW_KEY_RIGHT)) {
    radio_move(k == EW_KEY_UP || k == EW_KEY_LEFT ? -1 : 1);
    return;
  }
  if (focused >= 0 && text_field(ew_doc.links[focused].kind)) {
    struct ew_link *l = &ew_doc.links[focused];
    n = strlen(l->value);
    if (field_pos > n)
      field_pos = n;
    if (k == EW_KEY_LEFT) {
      field_pos=ew_text_step(l->value,field_pos,-1);
      dirty |= DRAW_PAGE | DRAW_STATUS;
      return;
    }
    if (k == EW_KEY_RIGHT) {
      field_pos=ew_text_step(l->value,field_pos,1);
      dirty |= DRAW_PAGE | DRAW_STATUS;
      return;
    }
    if (k == EW_KEY_HOME) {
      field_pos = 0;
      dirty |= DRAW_PAGE | DRAW_STATUS;
      return;
    }
    if (k == EW_KEY_END) {
      field_pos = n;
      dirty |= DRAW_PAGE | DRAW_STATUS;
      return;
    }
    if (k == EW_KEY_BACKSPACE || k == EW_KEY_DELETE) {
      unsigned end=field_pos;
      if (k==EW_KEY_BACKSPACE && field_pos)
        field_pos=ew_text_step(l->value,field_pos,-1);
      else if (k==EW_KEY_DELETE && field_pos<n)
        end=ew_text_step(l->value,field_pos,1);
      memmove(l->value+field_pos,l->value+end,n-end+1);
      dirty |= DRAW_PAGE | DRAW_STATUS;
      return;
    }
    if (k >= 32 && k < 127) {
      if (n + 1 < EW_FIELD_VALUE) {
        memmove(l->value + field_pos + 1, l->value + field_pos,
                n - field_pos + 1);
        l->value[field_pos++] = k;
      }
      dirty |= DRAW_PAGE | DRAW_STATUS;
      return;
    }
  }
  if (k == EW_KEY_BACKSPACE) {
    if (hpos > 0)
      history_go(hpos - 1);
    return;
  }
  if (k == EW_KEY_RIGHT) {
    hscroll += 8;
    if (hscroll > page_width - 624) hscroll = page_width - 624;
    dirty |= DRAW_PAGE | DRAW_STATUS;
    return;
  }
  if (k == EW_KEY_LEFT) {
    hscroll -= 8;
    if (hscroll < 0) hscroll = 0;
    dirty |= DRAW_PAGE | DRAW_STATUS;
    return;
  }
  if (k == EW_KEY_UP)
    scroll -= 10;
  else if (k == EW_KEY_DOWN)
    scroll += 10;
  else if (k == EW_KEY_PGUP)
    scroll -= bottom() - top() - 10;
  else if (k == EW_KEY_PGDN)
    scroll += bottom() - top() - 10;
  else if (k == EW_KEY_HOME)
    scroll = 0;
  else if (k == EW_KEY_END)
    scroll = max;
  else
    return;
  if (scroll < 0)
    scroll = 0;
  if (max < 0)
    max = 0;
  if (scroll > max)
    scroll = max;
  dirty |= DRAW_SCROLL;
}
static void mouse_event(const struct ew_mouse_event *event) {
  unsigned i;
  int y, width, height;
  mouse_x = event->x;
  mouse_y = event->y;
  mouse_active = 1;
  if (download_edit) {
    if (event->pressed & EW_MOUSE_LEFT) {
      if (mouse_y >= 102 && mouse_y < 114 && mouse_x >= 273 && mouse_x < 348)
        key(EW_KEY_ENTER);
      else if (mouse_y >= 82 && mouse_y < 94 && mouse_x >= 77 && mouse_x < 545) {
        unsigned start = 0;
        while (start < download_pos &&
               ew_body_width(download_name + start, download_pos - start, 0) > 457)
          start++;
        download_pos = start;
        while (download_name[download_pos] && 80 +
               ew_body_width(download_name + start, download_pos - start + 1, 0) < mouse_x)
          download_pos++;
        download_button = 0;
        dirty |= DRAW_PAGE | DRAW_STATUS;
      } else if (mouse_y >= 8 && mouse_y < 20) {
        download_edit = 0;
        dirty |= DRAW_PAGE | DRAW_TITLE | DRAW_ADDRESS;
        if (mouse_x >= 63) key(EW_KEY_F6);
        else message("Download cancelled");
      }
    }
    ew_cursor_show(mouse_x, mouse_y);
    return;
  }
  if (select_open >= 0 && (event->pressed & EW_MOUSE_LEFT)) {
    select_geometry();
    if (ew_select_count(select_open) > 8 &&
        mouse_x >= select_x + select_width - 13 && mouse_x < select_x + select_width &&
        mouse_y > select_y && mouse_y < select_y + select_rows * 10 + 1) {
      if (mouse_y < select_y + 12 && select_first > 0) select_first--;
      else if (mouse_y >= select_y + select_rows * 10 - 10 &&
               select_first + select_rows < (int)ew_select_count(select_open))
        select_first++;
      if (select_cursor < select_first) select_cursor = select_first;
      if (select_cursor >= select_first + select_rows)
        select_cursor = select_first + select_rows - 1;
      dirty |= DRAW_PAGE | DRAW_STATUS;
      return;
    }
    if (mouse_x >= select_x && mouse_x < select_x + select_width &&
        mouse_y > select_y && mouse_y < select_y + 1 + select_rows * 10)
      ew_select_choose(select_open, select_first + (mouse_y - select_y - 1) / 10);
    select_open = -1;
    dirty |= DRAW_PAGE | DRAW_STATUS;
    return;
  }
  if (!(event->buttons & EW_MOUSE_LEFT))
    scroll_drag = 0;
  if ((event->pressed & EW_MOUSE_LEFT) && mouse_x >= 624 && mouse_y >= top() &&
      mouse_y < bottom()) {
    int thumb_y, thumb_h;
    thumb(&thumb_y, &thumb_h);
    drag_offset = mouse_y >= thumb_y && mouse_y < thumb_y + thumb_h
                      ? mouse_y - thumb_y
                      : thumb_h / 2;
    scroll_drag = 1;
  }
  if (scroll_drag) {
    int thumb_y, thumb_h, range;
    int max = ew_doc.height - (bottom() - top());
    thumb(&thumb_y, &thumb_h);
    range = bottom() - top() - 2 - thumb_h;
    if (max < 0)
      max = 0;
    scroll =
        range > 0
            ? (int)((long)(mouse_y - top() - 1 - drag_offset) * max / range)
            : 0;
    if (scroll < 0)
      scroll = 0;
    if (scroll > max)
      scroll = max;
    dirty |= DRAW_SCROLL;
    return;
  }
  if (!(event->pressed & EW_MOUSE_LEFT)) {
    int over = select_open >= 0 ? -1 : hit_link(mouse_x, mouse_y);
    if (over != hovered) { hovered = over; dirty |= DRAW_STATUS; }
    ew_cursor_shape(over >= 0);
    ew_cursor_show(mouse_x, mouse_y);
    return;
  }
  if (chrome && mouse_y >= 8 && mouse_y < 20) {
    if (mouse_x < 31) {
      if (hpos > 0)
        history_go(hpos - 1);
    } else if (mouse_x < 62) {
      if (hpos + 1 < hcount)
        history_go(hpos + 1);
    } else
      key(EW_KEY_F6);
    return;
  }
  if (mouse_y < top() || mouse_y >= bottom())
    return;
  if (editing) dirty |= DRAW_ADDRESS | DRAW_STATUS;
  editing = 0;
  for (i = 0; i < ew_doc.run_count; i++) {
    struct ew_run EW_FAR *r = &ew_doc.runs[i];
    if (!r->link)
      continue;
    y = top() + r->y - scroll;
    height = r->kind == EW_RUN_IMAGE  ? r->w
             : r->kind == EW_RUN_TEXT ? (r->style & EW_SMALL   ? 6
                                         : r->style & EW_LARGE ? 10
                                                               : 8)
                                      : 12;
    width = r->kind == EW_RUN_TEXT
                ? text_width(ew_doc.text + r->off, r->n, r->style)
            : r->kind == EW_RUN_IMAGE ? (int)r->n
                                      : (int)r->w;
    if (mouse_x >= r->x - hscroll && mouse_x < r->x - hscroll + width && mouse_y >= y &&
        mouse_y < y + height) {
      unsigned start=0, offset=0, caret, next;
      char display[3*EW_FIELD_VALUE];
      struct ew_link *link=&ew_doc.links[r->link-1];
      if (text_field(link->kind)) {
        caret=field_display(link,display);
        if (focused==(int)r->link-1)
          start=field_start(link,display,caret,r->w-7);
        offset=ew_display_text(link->value,display,sizeof(display),start,
                                link->kind==EW_RUN_PASSWORD);
      }
      focused=r->link-1;
      field_pos=start;
      dirty |= DRAW_PAGE | DRAW_STATUS;
      if (text_field(link->kind)) {
        while (link->value[field_pos]) {
          next=ew_text_step(link->value,field_pos,1);
          caret=ew_display_text(link->value,display,sizeof(display),next,
                                 link->kind==EW_RUN_PASSWORD);
          if (r->x-hscroll+3+ew_body_width(display+offset,caret-offset,0)>=mouse_x)
            break;
          field_pos=next;
        }
      } else if (r->kind == EW_RUN_IMAGE && ew_image_is_map(r) &&
                 ew_doc.links[focused].kind == 0)
        image_map(r, mouse_x - (r->x - hscroll), mouse_y - y);
      else
        activate();
      return;
    }
  }
  focused = -1;
  dirty |= DRAW_PAGE | DRAW_STATUS;
}
int main(int argc, char **argv) {
  const char *url = "/root/welcome.htm", *video_mode=NULL;
  int k, i;
  struct ew_mouse_event event;
  for (i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--version")) {
      puts("ELKSWeb " EW_VERSION);
      return 0;
    } else if (!strcmp(argv[i], "-invert"))
      inverse = 1;
    else if (!strcmp(argv[i], "-video") && i+1<argc)
      video_mode=argv[++i];
    else if (!strcmp(argv[i], "-noimages"))
      load_images = 0;
    else if (!strcmp(argv[i], "-help") || !strcmp(argv[i], "--help")) {
      puts("ELKSWeb " EW_VERSION "\nUsage: elksweb [-video cga|ega|vga] [-invert] [-noimages] [http://URL or file]\n"
           "F6/Ctrl-L address  Tab links  Enter activate  F5 reload\n"
           "F2 invert  F3 hide bars  arrows/PgUp/PgDn scroll  Esc exit");
      return 0;
    } else if (argv[i][0] == '-') {
      fprintf(stderr, "ELKSWeb: unknown option %s\n", argv[i]);
      return 2;
    } else
      url = argv[i];
  }
  k=ew_platform_init(video_mode);
  if (k) {
    if (k<0) fprintf(stderr, "ELKSWeb: %s\n", ew_platform_error());
    ew_source_free();
    return k<0 ? 1 : 0;
  }
  signal(SIGINT, stopped);
  signal(SIGTERM, stopped);
  strcpy(ew_doc.title, "ELKSWeb " EW_VERSION);
  strcpy(status, "Starting...");
  draw();
  load(url, NULL, 1);
  while (!stopping) {
    if (dirty)
      draw();
    k = ew_getkey();
    if (k) {
      if (hovered >= 0) { hovered = -1; dirty |= DRAW_STATUS; }
      ew_cursor_shape(0);
      mouse_active = 0;
      ew_cursor_hide();
      key(k);
    } else if (ew_mouse_read(&event))
      mouse_event(&event);
    else
      usleep(10000);
  }
  ew_images_clear();
  for (i = 0; i < hcount; i++) ew_far_free(history[i]);
  ew_platform_shutdown();
  ew_source_free();
  printf("ELKSWeb closed.\n");
  return 0;
}
