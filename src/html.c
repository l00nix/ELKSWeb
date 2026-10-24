#include "../font/body_font.h"
#include "../platform/elks_platform.h"
#include "../font/font.h"
#include "elksweb.h"
#include "latin.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct ew_document ew_doc;
int ew_image_reflow;
unsigned char ew_document_charset;
static unsigned char parse_charset;
static short px, py, indent, lineheight;
static unsigned char style, inform, inpre, parse_full;
static unsigned char heading_bold;
static struct { unsigned char tag, size; } size_stack[32];
static unsigned size_depth, size_overflow;
static unsigned short linkid;
static char fields[32][112];
static unsigned field_count;
struct select_option {
  unsigned short owner;
  const char EW_FAR *label;
  const char EW_FAR *value;
};
static struct select_option options[64];
static unsigned option_count, select_id;
static unsigned char select_style;
static struct {
  const char EW_FAR *name;
  unsigned short run_index;
} anchors[64];
static unsigned anchor_count;
static unsigned merge_start;
static struct {
  short parent, base;
  unsigned next;
  unsigned char ordered;
} lists[12];
static unsigned list_depth;
static unsigned center_depth, line_first;
static void align_line(void);
static char empty_field[1];
static const char EW_FAR *parse_source;
static const char EW_FAR *parse_tail;
static uint32_t parse_length;
static int file_source;
static unsigned pre_column;
static unsigned char source_byte(uint32_t offset) {
  if (offset >= parse_length)
    return 0;
  if (file_source)
    return ew_source_byte(offset);
  return offset < EW_SOURCE || !parse_tail
             ? parse_source[(unsigned)offset]
             : parse_tail[(unsigned)(offset - EW_SOURCE)];
}
static const char *base_url;
struct table_cell {
  unsigned short first, last;
  short x, y, width, height;
  unsigned char row, col, span;
};
struct table_context {
  struct table_cell cells[32];
  short widths[8], heights[16], x, y;
  short cell_x, cell_y, cell_indent, saved_indent;
  unsigned short first, requested, cell_requested;
  unsigned char active, border, count, row, col, open;
  unsigned char padding, spacing, span, columns, rows, row_open;
  unsigned char saved_style, cell_style;
  unsigned short minimum[8], cell_minimum, word_width;
  uint32_t source;
  unsigned char eligible, plan, automatic;
};
static struct table_context table, saved_table;
static unsigned table_ignored;
struct table_plan {
  uint32_t source;
  unsigned short widths[8];
  unsigned char columns;
};
static struct table_plan table_plans[16];
static unsigned char table_plan_count, table_replay;
static void table_minimum(unsigned width) {
  if (!table_replay && table.open && table.eligible && width>table.cell_minimum)
    table.cell_minimum=width>16000 ? 16000 : width;
}
static int char_width(unsigned char c, unsigned st) {
  if (st & EW_MONO)
    return ew_mono_char_width(c, !!(st & EW_BOLD), st & EW_SMALL ? 0 : st & EW_LARGE ? 2 : 1);
  if (st & EW_SMALL)
    return ew_small_char_width(c, !!(st & EW_BOLD));
  return st & EW_LARGE ? ew_font_char_width(c, !!(st & EW_BOLD))
                       : ew_body_char_width(c, !!(st & EW_BOLD));
}
static int text_width(const char EW_FAR *text, unsigned n, unsigned st) {
  if (st & EW_MONO)
    return ew_mono_width(text, n, !!(st & EW_BOLD), st & EW_SMALL ? 0 : st & EW_LARGE ? 2 : 1);
  if (st & EW_SMALL)
    return ew_small_width(text, n, !!(st & EW_BOLD));
  return st & EW_LARGE ? ew_font_width(text, n, !!(st & EW_BOLD))
                       : ew_body_width(text, n, !!(st & EW_BOLD));
}

static int ci(const char *a, const char *b) {
  while (*a && *b) {
    if (tolower((unsigned char)*a++) != tolower((unsigned char)*b++))
      return 0;
  }
  return !*a && !*b;
}
/* Encoding identifiers are shared with HTTP metadata. Unknown labels leave
 * the current decoder unchanged; labels never affect URL/form attribute bytes. */
int ew_charset_name(const char *name) {
  char label[20];
  unsigned n = 0;
  while (isspace((unsigned char)*name)) ++name;
  if (*name == '\'' || *name == '"') ++name;
  while (*name && *name != ';' && *name != '\'' && *name != '"' &&
         !isspace((unsigned char)*name)) {
    if (n == sizeof(label) - 1) return -1;
    label[n++] = tolower((unsigned char)*name++);
  }
  label[n] = 0;
  if (!strcmp(label, "utf-8") || !strcmp(label, "utf8")) return EW_CHARSET_UTF8;
  if (!strcmp(label, "iso-8859-1") || !strcmp(label, "latin1")) return EW_CHARSET_LATIN1;
  if (!strcmp(label, "windows-1252") || !strcmp(label, "cp1252")) return EW_CHARSET_CP1252;
  if (!strcmp(label, "iso-8859-2") || !strcmp(label, "latin2")) return EW_CHARSET_LATIN2;
  if (!strcmp(label, "windows-1250") || !strcmp(label, "cp1250")) return EW_CHARSET_CP1250;
  return -1;
}
int ew_charset_parameter(const char *value) {
  const char *key;
  unsigned n, i;
  char quote;
  while (*value) {
    while (*value == ';' || isspace((unsigned char)*value)) ++value;
    key = value;
    while (*value && *value != ';' && *value != '=' &&
           !isspace((unsigned char)*value)) ++value;
    n = (unsigned)(value - key);
    while (isspace((unsigned char)*value)) ++value;
    if (*value == '=') {
      ++value;
      while (isspace((unsigned char)*value)) ++value;
      if (n == 7) {
        for (i = 0; i < 7 && tolower((unsigned char)key[i]) == "charset"[i]; ++i) {}
        if (i == 7) return ew_charset_name(value);
      }
    }
    quote = 0;
    while (*value) {
      if (quote) { if (*value == quote) quote = 0; }
      else if (*value == '\'' || *value == '"') quote = *value;
      else if (*value == ';') { ++value; break; }
      ++value;
    }
  }
  return -1;
}
static void newline(int gap) {
  align_line();
  line_first = ew_doc.run_count;
  if (px > indent) {
    py += lineheight + gap;
    px = indent;
    lineheight = style & EW_SMALL ? EW_SMALL_HEIGHT : style & EW_LARGE ? EW_LARGE_HEIGHT : EW_BODY_HEIGHT;
  } else if (gap && py) {
    py += gap;
  }
  if (py > 16000) {
    py = 16000;
    ew_doc.truncated = 1;
  }
}
static struct ew_run EW_FAR *run(unsigned kind) {
  struct ew_run EW_FAR *r;
  if (ew_doc.run_count >= EW_RUNS) {
    ew_doc.truncated = parse_full = 1;
    return NULL;
  }
  r = &ew_doc.runs[ew_doc.run_count++];
  ew_zero_far(r, sizeof(*r));
  r->x = px;
  r->y = py;
  r->style = style;
  r->kind = kind;
  r->link = linkid;
  return r;
}
static unsigned run_width(const struct ew_run EW_FAR *r) {
  if (r->kind == EW_RUN_TEXT)
    return text_width(ew_doc.text + r->off, r->n, r->style);
  if (r->kind == EW_RUN_IMAGE || r->kind == EW_RUN_RULE ||
      r->kind == EW_RUN_BOX)
    return r->n;
  return r->w;
}
static unsigned run_height(const struct ew_run EW_FAR *r) {
  if (r->kind == EW_RUN_BOX)
    return r->off ? r->off : r->w;
  if (r->kind == EW_RUN_IMAGE)
    return r->w;
  if (r->kind == EW_RUN_RULE)
    return 1;
  if (r->kind == EW_RUN_TEXT)
    return r->style & EW_SMALL ? EW_SMALL_HEIGHT : r->style & EW_LARGE ? EW_LARGE_HEIGHT : EW_BODY_HEIGHT;
  if (r->kind == EW_RUN_BULLET)
    return 8;
  return EW_CONTROL_HEIGHT;
}
static void align_line(void) {
  unsigned i;
  int left = 624, right = 0, shift;
  if (!center_depth || table.active)
    return;
  for (i = line_first; i < ew_doc.run_count; i++) {
    struct ew_run EW_FAR *r = &ew_doc.runs[i];
    int end;
    if (r->y != py || r->kind == EW_RUN_RULE)
      continue;
    end = r->x + run_width(r);
    if (r->x < left)
      left = r->x;
    if (end > right)
      right = end;
  }
  if (right <= left)
    return;
  shift = (624 - (right - left)) / 2 - left;
  if (shift < -left) shift = -left;
  for (i = line_first; i < ew_doc.run_count; i++)
    if (ew_doc.runs[i].y == py && ew_doc.runs[i].kind != EW_RUN_RULE)
      ew_doc.runs[i].x += shift;
}
/* Table values stay bounded before narrowing to native 16-bit geometry. */
static unsigned table_number(const char *value, unsigned limit) {
  unsigned long number=0;
  while (*value==' ' || *value=='\t') ++value;
  if (*value=='+') ++value;
  while (*value>='0' && *value<='9') {
    number=number*10+*value++-'0';
    if (number>limit) return limit;
  }
  return (unsigned)number;
}
static unsigned table_dimension(const char *value, unsigned available) {
  unsigned number=table_number(value,16000);
  if (strchr(value,'%')) {
    if (number>100) number=100;
    return (unsigned)((unsigned long)available*number/100);
  }
  return number;
}
static short table_position(long value) {
  if (value<0) { ew_doc.truncated=1; return 0; }
  if (value>16000) { ew_doc.truncated=1; return 16000; }
  return (short)value;
}
static void table_cell_close(void) {
  struct table_cell *c;
  unsigned i;
  long right, bottom, width, height;
  if (!table.open) return;
  table.open=0;
  if (table.count==32) { ew_doc.truncated=1; return; }
  c=&table.cells[table.count++];
  c->first=table.first;
  c->last=ew_doc.run_count;
  c->x=table.cell_x;
  c->y=table.cell_y;
  for (i=c->first;i<c->last;++i) {
    const struct ew_run EW_FAR *r=&ew_doc.runs[i];
    if (i==c->first || r->x<c->x) c->x=r->x;
    if (i==c->first || r->y<c->y) c->y=r->y;
  }
  right=c->x; bottom=c->y;
  for (i=c->first;i<c->last;++i) {
    const struct ew_run EW_FAR *r=&ew_doc.runs[i];
    long edge=(long)r->x+run_width(r);
    if (edge>right) right=edge;
    edge=(long)r->y+run_height(r);
    if (edge>bottom) bottom=edge;
  }
  width=right-c->x+2U*table.padding;
  height=bottom-c->y+2U*table.padding;
  if (width<table.cell_requested) width=table.cell_requested;
  if (table.cell_minimum>16000-2U*table.padding) table.cell_minimum=16000;
  else table.cell_minimum+=2U*table.padding;
  if (table.cell_minimum<table.cell_requested) table.cell_minimum=table.cell_requested;
  if (table.cell_minimum>table.minimum[table.col]) table.minimum[table.col]=table.cell_minimum;
  c->width=table_position(width);
  c->height=table_position(height);
  c->row=table.row;
  c->col=table.col;
  c->span=table.span;
  if (c->span==1 && c->width>table.widths[c->col])
    table.widths[c->col]=c->width;
  if (c->height>table.heights[c->row]) table.heights[c->row]=c->height;
  table.col+=c->span;
  if (table.col>table.columns) table.columns=table.col;
  if (table.row+1>table.rows) table.rows=table.row+1;
  indent=table.cell_indent;
  style=table.cell_style;
  px=indent;
  lineheight=EW_BODY_HEIGHT;
}
static void table_box(long x, long y, long width, long height) {
  struct ew_run EW_FAR *r;
  if (width<=0 || height<=0 || x>=16000 || y>=16000) return;
  px=table_position(x); py=table_position(y);
  if (width>16000-px) { width=16000-px; ew_doc.truncated=1; }
  if (height>16000-py) { height=16000-py; ew_doc.truncated=1; }
  r=run(EW_RUN_BOX);
  if (r) {
    r->n=(unsigned)width;
    r->off=(unsigned)height;
    r->w=height>255 ? 255 : (unsigned)height;
    r->link=0;
  }
}
/* Cache integer-only plans; a second ordinary parse rebuilds all identities. */
static void table_measure(void) {
  unsigned i, preferred, minimum;
  long low=0, high=0, target, extra, flex, share;
  struct table_plan *plan;
  if (table_replay || !table.eligible || !table.automatic || !table.columns ||
      table_plan_count==16) return;
  for (i=0;i<table.columns;++i) {
    minimum=table.minimum[i];
    preferred=table.widths[i];
    low+=minimum; high+=preferred>minimum ? preferred : minimum;
  }
  target=(table.requested ? (long)table.requested : 624L-table.x)-
          (table.columns+1)*(long)table.spacing;
  if (target<low) target=low;
  if (target>=high) return;
  plan=&table_plans[table_plan_count++];
  plan->source=table.source; plan->columns=table.columns;
  extra=target-low; flex=high-low;
  for (i=0;i<table.columns;++i) {
    minimum=table.minimum[i];
    preferred=(unsigned)table.widths[i]>minimum ? table.widths[i]-minimum : 0;
    share=flex ? extra*preferred/flex : 0;
    plan->widths[i]=minimum+(unsigned)share;
    extra-=share; flex-=preferred;
  }
}
static void table_finish(void) {
  unsigned i,j,cols;
  long x,y,width,height,total,extra,bottom;
  short restore_indent;
  unsigned char restore_style;
  table_cell_close();
  cols=table.columns;
  table_measure();
  /* Single-column cells establish minima; spanning cells add only their
   * missing width, including the spacing already inside the span. */
  for (i=0;i<table.count;++i) {
    struct table_cell *c=&table.cells[i];
    if (c->span<2) continue;
    total=(c->span-1)*table.spacing;
    for (j=c->col;j<c->col+c->span;++j) total+=table.widths[j];
    extra=c->width-total;
    for (j=0;extra>0 && j<c->span;++j) {
      long share=(extra+c->span-j-1)/(c->span-j);
      table.widths[c->col+j]=table_position((long)table.widths[c->col+j]+share);
      extra-=share;
    }
  }
  total=(cols+1)*table.spacing;
  for (j=0;j<cols;++j) total+=table.widths[j];
  extra=(long)table.requested-total;
  for (j=0;extra>0 && j<cols;++j) {
    long share=(extra+cols-j-1)/(cols-j);
    table.widths[j]=table_position((long)table.widths[j]+share);
    total+=share; extra-=share;
  }
  if (!cols && table.requested>total) total=table.requested;
  bottom=(long)table.y+(table.rows+1)*table.spacing;
  for (j=0;j<table.rows;++j) bottom+=table.heights[j];
  for (i=0;i<table.count;++i) {
    struct table_cell *c=&table.cells[i];
    x=(long)table.x+table.spacing;
    y=(long)table.y+table.spacing;
    for (j=0;j<c->col;++j) x+=(long)table.widths[j]+table.spacing;
    for (j=0;j<c->row;++j) y+=(long)table.heights[j]+table.spacing;
    width=(c->span-1)*table.spacing;
    for (j=c->col;j<c->col+c->span;++j) width+=table.widths[j];
    height=table.heights[c->row];
    for (j=c->first;j<c->last;++j) {
      struct ew_run EW_FAR *r=&ew_doc.runs[j];
      r->x=table_position((long)r->x+x+table.padding-c->x);
      r->y=table_position((long)r->y+y+table.padding-c->y);
    }
    if (table.border) table_box(x,y,width,height);
  }
  if (table.border) table_box(table.x,table.y,total,bottom-table.y);
  restore_indent=table.saved_indent;
  restore_style=table.saved_style;
  if (saved_table.active) {
    memcpy(&table,&saved_table,sizeof(table));
    memset(&saved_table,0,sizeof(saved_table));
  } else table.active=0;
  indent=px=restore_indent;
  style=restore_style;
  py=table_position(bottom);
  lineheight=EW_BODY_HEIGHT;
  line_first=ew_doc.run_count;
}
/* Explicit cell widths constrain normal text, while intrinsic items may grow
 * the column. Auto columns still use the viewport until final table placement. */
static int line_right(void) {
  int right=624;
  if (table.open && table.cell_requested) {
    right=(int)table.cell_requested-2*(int)table.padding;
    if (right>624) right=624;
    if (right<=indent) right=indent+1;
  }
  return right;
}
static void word(const char *s, unsigned n, int space) {
  struct ew_run EW_FAR *r;
  unsigned count = n, take, width;
  int spacing = char_width(' ', style);
  int separate, right=inpre ? 16000 : line_right();
  if (!n)
    return;
  if (inpre) pre_column = (pre_column + n) & 7;
  width = text_width(s, n, style);
  if (!table_replay && table.open && table.eligible) {
    if (space || px==indent) table.word_width=0;
    table.word_width+=width;
    if (table.word_width>624) table.word_width=624;
    table_minimum(inpre ? px+width : indent+table.word_width);
  }
  if (!inpre && px > indent && px + (int)width + (space ? spacing : 0) > right)
    newline(0);
  /* A cell cannot make a normal word narrower. Retain the existing viewport
   * split for exceptionally long words, and always leave room for one glyph. */
  if (!inpre && table.open && table.cell_requested && (int)width>right-indent)
    right=(int)width>624-indent ? 624 : indent+(int)width;
  separate = space && px > indent;
  if (separate)
    px += spacing;
  if ((unsigned long)ew_doc.text_len + n + separate >= EW_TEXT) {
    ew_doc.truncated = parse_full = 1;
    return;
  }
  while (count) {
    width = 0;
    take = 0;
    while (take < count &&
           px + (int)width + char_width((unsigned char)s[take], style) <= right) {
      width += char_width((unsigned char)s[take], style);
      take++;
    }
    if (!take) {
      if (inpre) { ew_doc.truncated = 1; return; }
      newline(0);
      continue;
    }
    r = ew_doc.run_count ? &ew_doc.runs[ew_doc.run_count - 1] : NULL;
    if (r && ew_doc.run_count > merge_start && r->kind == EW_RUN_TEXT &&
        r->style == style && r->link == linkid &&
        r->y == py && r->off + r->n == ew_doc.text_len &&
        r->x + (int)run_width(r) == px - (separate ? spacing : 0)) {
      if (separate) {
        ew_doc.text[ew_doc.text_len++] = ' ';
        r->n++;
      }
      r->n += take;
    } else {
      r = run(EW_RUN_TEXT);
      if (!r)
        return;
      r->off = ew_doc.text_len;
      r->n = take;
    }
    {
      int height = style & EW_SMALL ? EW_SMALL_HEIGHT : style & EW_LARGE ? EW_LARGE_HEIGHT : EW_BODY_HEIGHT;
      if (r == &ew_doc.runs[line_first] || lineheight < height)
        lineheight = height;
    }
    ew_copy_to_far(ew_doc.text + ew_doc.text_len, s, take);
    ew_doc.text_len += take;
    px += width;
    s += take;
    count -= take;
    separate = 0;
    if (count && !inpre)
      newline(0);
  }
}
/* Entity code points are 32-bit even on the native 16-bit compiler. */
static int entity_value(const char *name, unsigned long *value) {
  static const struct {
    const char *name;
    unsigned long value;
  } names[] = {
    {"amp",38}, {"lt",60}, {"gt",62}, {"quot",34}, {"apos",39},
    {"nbsp",160}, {"ndash",0x2013}, {"mdash",0x2014},
    {"lsquo",0x2018}, {"rsquo",0x2019}, {"sbquo",0x201a},
    {"ldquo",0x201c}, {"rdquo",0x201d}, {"bdquo",0x201e},
    {"hellip",0x2026}, {"bull",0x2022}, {"middot",183},
    {"laquo",171}, {"raquo",187}, {"ensp",0x2002}, {"emsp",0x2003},
    {"thinsp",0x2009}, {"minus",0x2212}, {"copy",169}, {"reg",174},
    {"trade",0x2122}, {"euro",0x20ac}, {"pound",163}, {"yen",165},
    {"cent",162}, {"times",215}, {"divide",247}, {"plusmn",177},
    {"deg",176}, {"micro",181}
  };
  unsigned i, digit, base = 10;
  unsigned long number = 0;
  const char *p;
  if (name[0] != '#') {
    for (i = 0; i < sizeof(latin_entities) / sizeof(latin_entities[0]); ++i)
      if (!strcmp(name, latin_entities[i].name)) {
        *value = latin_entities[i].code; return 1;
      }
    for (i = 0; i < sizeof(names) / sizeof(names[0]); ++i)
      if (ci(name, names[i].name)) { *value = names[i].value; return 1; }
    return 0;
  }
  p = name + 1;
  if (*p == 'x' || *p == 'X') { base = 16; ++p; }
  if (!*p) return 0;
  while (*p) {
    if (*p >= '0' && *p <= '9') digit = *p - '0';
    else if (*p >= 'a' && *p <= 'f') digit = *p - 'a' + 10;
    else if (*p >= 'A' && *p <= 'F') digit = *p - 'A' + 10;
    else return 0;
    if (digit >= base) return 0;
    if (number <= 0x10ffffUL) number = number * base + digit;
    ++p;
  }
  if (!number || number > 0x10ffffUL ||
      (number >= 0xd800UL && number <= 0xdfffUL)) number = 0xfffd;
  *value = number;
  return 1;
}
static unsigned long entity(uint32_t *p) {
  uint32_t s = *p;
  char name[16];
  unsigned n = 0, c;
  unsigned long value;
  while ((c = source_byte(s)) && n < sizeof(name) - 1 &&
         (isalnum((unsigned char)c) || c == '#')) {
    name[n++] = c;
    ++s;
  }
  name[n] = 0;
  if (source_byte(s) != ';' || !entity_value(name, &value)) return '&';
  *p = s + 1;
  return value;
}
static unsigned text_character(unsigned long value) {
  if (value >= 32 && value < 127) return (unsigned)value;
  if (value == 9 || value == 10 || value == 13 || value == 160 ||
      (value >= 0x2000 && value <= 0x200a) || value == 0x202f ||
      value == 0x205f || value == 0x3000) return ' ';
  if ((value >= 0x2010 && value <= 0x2015) || value == 0x2212 ||
      value == 0x96 || value == 0x97) return '-';
  if ((value >= 0x2018 && value <= 0x201b) || value == 0x2032 ||
      value == 0x91 || value == 0x92) return '\'';
  if ((value >= 0x201c && value <= 0x201f) || value == 0x2033 ||
      value == 171 || value == 187 || value == 0x93 || value == 0x94) return '"';
  if (value == 0x2026 || value == 0x85) return 0x2026;
  if (value == 0x2022 || value == 183 || value == 0x95) return '*';
  if (value == 215) return 'x';
  if (value == 247) return '/';
  if (value >= 192 && value < 384) return latin_ascii[value - 192];
  return '?';
}
static const char *text_expansion(unsigned long value) {
  switch (value) {
    case 0xc6: return "AE"; case 0xe6: return "ae";
    case 0x152: return "OE"; case 0x153: return "oe";
    case 0xdf: return "ss"; case 0xde: return "TH"; case 0xfe: return "th";
    case 0xa9: return "(c)"; case 0xae: return "(R)";
    case 0x2122: return "TM"; case 0x20ac: return "EUR";
    case 0xa3: return "GBP"; case 0xa5: return "JPY";
    case 0xb0: return "deg"; case 0xb1: return "+/-";
    case 0x2026: case 0x85: return "...";
  }
  return NULL;
}
/* Unicode mappings generated from Python's standard cp1252/iso8859_2/cp1250
 * codecs. Only high-byte ranges differing from Latin-1 need lookup storage. */
static const unsigned short cp1252_unicode[32] = {
  0x20ac,0xfffd,0x201a,0x0192,0x201e,0x2026,0x2020,0x2021,
  0x02c6,0x2030,0x0160,0x2039,0x0152,0xfffd,0x017d,0xfffd,
  0xfffd,0x2018,0x2019,0x201c,0x201d,0x2022,0x2013,0x2014,
  0x02dc,0x2122,0x0161,0x203a,0x0153,0xfffd,0x017e,0x0178,
};
static const unsigned short latin2_unicode[96] = {
  0x00a0,0x0104,0x02d8,0x0141,0x00a4,0x013d,0x015a,0x00a7,
  0x00a8,0x0160,0x015e,0x0164,0x0179,0x00ad,0x017d,0x017b,
  0x00b0,0x0105,0x02db,0x0142,0x00b4,0x013e,0x015b,0x02c7,
  0x00b8,0x0161,0x015f,0x0165,0x017a,0x02dd,0x017e,0x017c,
  0x0154,0x00c1,0x00c2,0x0102,0x00c4,0x0139,0x0106,0x00c7,
  0x010c,0x00c9,0x0118,0x00cb,0x011a,0x00cd,0x00ce,0x010e,
  0x0110,0x0143,0x0147,0x00d3,0x00d4,0x0150,0x00d6,0x00d7,
  0x0158,0x016e,0x00da,0x0170,0x00dc,0x00dd,0x0162,0x00df,
  0x0155,0x00e1,0x00e2,0x0103,0x00e4,0x013a,0x0107,0x00e7,
  0x010d,0x00e9,0x0119,0x00eb,0x011b,0x00ed,0x00ee,0x010f,
  0x0111,0x0144,0x0148,0x00f3,0x00f4,0x0151,0x00f6,0x00f7,
  0x0159,0x016f,0x00fa,0x0171,0x00fc,0x00fd,0x0163,0x02d9,
};
static const unsigned short cp1250_unicode[128] = {
  0x20ac,0xfffd,0x201a,0xfffd,0x201e,0x2026,0x2020,0x2021,
  0xfffd,0x2030,0x0160,0x2039,0x015a,0x0164,0x017d,0x0179,
  0xfffd,0x2018,0x2019,0x201c,0x201d,0x2022,0x2013,0x2014,
  0xfffd,0x2122,0x0161,0x203a,0x015b,0x0165,0x017e,0x017a,
  0x00a0,0x02c7,0x02d8,0x0141,0x00a4,0x0104,0x00a6,0x00a7,
  0x00a8,0x00a9,0x015e,0x00ab,0x00ac,0x00ad,0x00ae,0x017b,
  0x00b0,0x00b1,0x02db,0x0142,0x00b4,0x00b5,0x00b6,0x00b7,
  0x00b8,0x0105,0x015f,0x00bb,0x013d,0x02dd,0x013e,0x017c,
  0x0154,0x00c1,0x00c2,0x0102,0x00c4,0x0139,0x0106,0x00c7,
  0x010c,0x00c9,0x0118,0x00cb,0x011a,0x00cd,0x00ce,0x010e,
  0x0110,0x0143,0x0147,0x00d3,0x00d4,0x0150,0x00d6,0x00d7,
  0x0158,0x016e,0x00da,0x0170,0x00dc,0x00dd,0x0162,0x00df,
  0x0155,0x00e1,0x00e2,0x0103,0x00e4,0x013a,0x0107,0x00e7,
  0x010d,0x00e9,0x0119,0x00eb,0x011b,0x00ed,0x00ee,0x010f,
  0x0111,0x0144,0x0148,0x00f3,0x00f4,0x0151,0x00f6,0x00f7,
  0x0159,0x016f,0x00fa,0x0171,0x00fc,0x00fd,0x0163,0x02d9,
};
static unsigned long legacy_character(unsigned first, unsigned charset) {
  if (charset == EW_CHARSET_CP1250 && first >= 128) return cp1250_unicode[first - 128];
  if (charset == EW_CHARSET_CP1252 && first >= 128 && first < 160) return cp1252_unicode[first - 128];
  if (charset == EW_CHARSET_LATIN2 && first >= 160) return latin2_unicode[first - 160];
  return first;
}
static unsigned long utf8_character(uint32_t *p) {
  uint32_t start = *p;
  unsigned first = source_byte(start), count, i, c;
  unsigned long value, minimum;
  ++*p;
  if (first < 128) return first;
  if (parse_charset != EW_CHARSET_UTF8) return legacy_character(first, parse_charset);
  if (first >= 0xc2 && first <= 0xdf) { count=1; value=first&31; minimum=128; }
  else if (first >= 0xe0 && first <= 0xef) { count=2; value=first&15; minimum=2048; }
  else if (first >= 0xf0 && first <= 0xf4) { count=3; value=first&7; minimum=65536UL; }
  else return 0xfffd;
  for (i=1; i<=count; ++i) {
    c=source_byte(start+i);
    if ((c&0xc0)!=0x80) return 0xfffd;
    value=(value<<6)|(c&63);
  }
  *p=start+count+1;
  if (value<minimum || value>0x10ffffUL ||
      (value>=0xd800UL && value<=0xdfffUL)) return 0xfffd;
  return value;
}
/* Controls are canonical UTF-8. Their saved source charset is used only when
 * submitting; this avoids ambiguous mixtures of legacy bytes and entities. */
static unsigned long string_character(const char EW_FAR *s, unsigned *position) {
  unsigned start=*position, first=(unsigned char)s[start], count, i, c;
  unsigned long value, minimum;
  if (!first) return 0;
  ++*position;
  if (first<128) return first;
  if (first>=0xc2 && first<=0xdf) { count=1; value=first&31; minimum=128; }
  else if (first>=0xe0 && first<=0xef) { count=2; value=first&15; minimum=2048; }
  else if (first>=0xf0 && first<=0xf4) { count=3; value=first&7; minimum=65536UL; }
  else return 0xfffd;
  for (i=1;i<=count;++i) {
    c=(unsigned char)s[start+i];
    if ((c&0xc0)!=0x80) return 0xfffd;
    value=(value<<6)|(c&63);
  }
  if (value<minimum || value>0x10ffffUL || (value>=0xd800UL && value<=0xdfffUL)) return 0xfffd;
  *position=start+count+1;
  return value;
}
unsigned ew_text_step(const char EW_FAR *s, unsigned position, int direction) {
  unsigned p=0, previous=0;
  if (direction>0) { string_character(s,&position); return position; }
  while (p<position && s[p]) { previous=p; string_character(s,&p); }
  return previous;
}
/* Return the display offset corresponding to a UTF-8 byte cursor. Expansion
 * glyphs stay a single editing unit; passwords mask Unicode characters. */
unsigned ew_display_text(const char EW_FAR *s, char *out, unsigned cap,
                         unsigned cursor, int password) {
  unsigned p=0, n=0, caret=0, start;
  unsigned long value;
  const char *expansion;
  char single[2];
  if (!cap) return 0;
  while (s && s[p]) {
    start=p; value=string_character(s,&p);
    expansion=password ? "*" : text_expansion(value);
    if (!expansion) {
      single[0]=text_character(value); single[1]=0; expansion=single;
      if (!password && value>=0x300 && value<=0x36f) expansion="";
    }
    while (*expansion && n<cap-1) out[n++]=*expansion++;
    if (p<=cursor) caret=n;
    if (start>=cursor && n>=cap-1) break;
  }
  out[n]=0;
  return caret;
}
/* Attribute entities become UTF-8, while original URL/submission bytes stay
 * unchanged. Display-only callers may normalize legacy bytes before rendering.
 */
static unsigned attribute_value(const char *s, unsigned length, char *out,
                                unsigned cap, int normalize) {
  unsigned pos=0, count=0, written=0, i, n, bytes;
  int encode;
  unsigned long value;
  char name[16];
  unsigned char encoded[4];
  while (pos<length) {
    bytes=1;
    encode=0;
    encoded[0]=(unsigned char)s[pos++];
    if (normalize && parse_charset == EW_CHARSET_UTF8 && encoded[0]>=128) {
      i=pos-1; string_character(s,&i);
      if (i<=length) {
        bytes=i-pos+1;
        for (n=1;n<bytes;++n) encoded[n]=(unsigned char)s[pos+n-1];
        pos=i;
      }
    }
    if (normalize && parse_charset != EW_CHARSET_UTF8 && encoded[0]>=128) {
      value=legacy_character(encoded[0], parse_charset);
      if (value==0xfffd) value=encoded[0]; /* Preserve undefined legacy bytes. */
      encode=1;
    }
    if (encoded[0]=='&') {
      i=pos; n=0;
      while (i<length && n<sizeof(name)-1 &&
             (isalnum((unsigned char)s[i]) || s[i]=='#')) name[n++]=s[i++];
      name[n]=0;
      if (i<length && s[i]==';' && entity_value(name,&value)) {
        pos=i+1; encode=1;
      }
    }
    if (encode) {
        if (value<128) encoded[0]=value;
        else if (value<2048) {
          bytes=2; encoded[0]=0xc0|(value>>6); encoded[1]=0x80|(value&63);
        } else if (value<65536UL) {
          bytes=3; encoded[0]=0xe0|(value>>12); encoded[1]=0x80|((value>>6)&63);
          encoded[2]=0x80|(value&63);
        } else {
          bytes=4; encoded[0]=0xf0|(value>>18); encoded[1]=0x80|((value>>12)&63);
          encoded[2]=0x80|((value>>6)&63); encoded[3]=0x80|(value&63);
        }
    }
    if (cap && count+bytes<cap) {
      for (i=0;i<bytes;++i) out[written++]=encoded[i];
    }
    count+=bytes;
  }
  if (cap) out[written]=0;
  return count;
}
static unsigned attr_mode(const char *tag, const char *name, char *out,
                          unsigned cap, int normalize) {
  const char *p = tag, *a, *v;
  unsigned n;
  char key[32], quote;
  out[0] = 0;
  while (*p && !isspace((unsigned char)*p))
    p++;
  while (*p) {
    while (isspace((unsigned char)*p) || *p == '/')
      p++;
    a = p;
    while (isalnum((unsigned char)*p) || *p == '-' || *p == '_')
      p++;
    n = (unsigned)(p - a);
    if (!n) {
      if (*p)
        p++;
      continue;
    }
    if (n >= sizeof(key))
      n = sizeof(key) - 1;
    memcpy(key, a, n);
    key[n] = 0;
    while (isspace((unsigned char)*p))
      p++;
    if (*p != '=') {
      if (ci(key, name)) {
        strncpy(out, "1", cap);
        out[cap - 1] = 0;
        return 1;
      }
      continue;
    }
    p++;
    while (isspace((unsigned char)*p))
      p++;
    quote = (*p == '\'' || *p == '"') ? *p++ : 0;
    v = p;
    while (*p && (quote ? *p != quote : !isspace((unsigned char)*p)))
      p++;
    n = (unsigned)(p - v);
    if (ci(key, name)) {
      if (quote && !*p) {
        out[0] = 0;
        return cap; /* Never turn a clipped quoted value into a new URL. */
      }
      return attribute_value(v, n, out, cap, normalize);
    }
    if (quote && *p)
      p++;
  }
  return 0;
}
static unsigned attr(const char *tag, const char *name, char *out, unsigned cap) {
  return attr_mode(tag, name, out, cap, 0);
}
/* Display values and controls normalize to UTF-8. Resource URLs retain bytes. */
static unsigned attr_utf8(const char *tag, const char *name, char *out, unsigned cap) {
  return attr_mode(tag, name, out, cap, 1);
}
static unsigned add_link(unsigned kind, const char *url) {
  static char resolved[EW_URL];
  struct ew_link *l;
  const char EW_FAR *stored = NULL;
  if (ew_doc.link_count >= EW_LINKS || (kind && field_count == 32)) {
    ew_doc.truncated = 1;
    return 0;
  }
  if (url) {
    if (ew_resolve_url(base_url, url, resolved, sizeof(resolved)) < 0 ||
        !(stored = ew_store_url(resolved))) {
      ew_doc.truncated = 1;
      return 0;
    }
  }
  l = &ew_doc.links[ew_doc.link_count++];
  memset(l, 0, sizeof(*l));
  l->kind = kind;
  l->form = inform;
  l->url = stored;
  l->name = l->value = empty_field;
  if (kind) {
    l->flags = parse_charset << 2;
    l->name = fields[field_count];
    l->value = fields[field_count++] + 32;
    l->name[0] = l->value[0] = 0;
  }
  return ew_doc.link_count;
}
static int attribute_present(const char *tag, const char *wanted) {
  const char *p=tag, *start;
  char key[32], quote;
  unsigned n;
  while (*p && !isspace((unsigned char)*p)) ++p;
  while (*p) {
    while (isspace((unsigned char)*p) || *p=='/') ++p;
    start=p;
    while (isalnum((unsigned char)*p) || *p=='-' || *p=='_') ++p;
    n=(unsigned)(p-start);
    if (!n) { if (*p) ++p; continue; }
    if (n<sizeof(key)) {
      memcpy(key,start,n); key[n]=0;
      if (ci(key,wanted)) return 1;
    }
    while (isspace((unsigned char)*p)) ++p;
    if (*p!='=') continue;
    ++p; while (isspace((unsigned char)*p)) ++p;
    quote=(*p=='\'' || *p=='"') ? *p++ : 0;
    while (*p && (quote ? *p!=quote : !isspace((unsigned char)*p))) ++p;
    if (quote && *p) ++p;
  }
  return 0;
}
static int control_tag(uint32_t p, const char *name, int closing) {
  if (source_byte(p++)!='<') return 0;
  if (closing && source_byte(p++)!='/') return 0;
  while (*name) if (tolower(source_byte(p++))!=*name++) return 0;
  return source_byte(p)=='>' || source_byte(p)=='/' || isspace(source_byte(p));
}
static void control_text(uint32_t *position, const char *closing, int option,
                         char *out, unsigned cap) {
  static char raw[EW_URL];
  uint32_t p=*position;
  unsigned n=0, c;
  char quote;
  while ((c=source_byte(p))) {
    if (control_tag(p,closing,1) ||
        (option && (control_tag(p,"option",0) || control_tag(p,"option",1))))
      break;
    if (option && c=='<') {
      ++p; quote=0;
      while ((c=source_byte(p))) {
        ++p;
        if (!quote && c=='>') break;
        if (c=='\'' || c=='"') { if ((unsigned char)quote==c) quote=0; else if (!quote) quote=c; }
      }
      continue;
    }
    ++p;
    if (option && isspace((unsigned char)c)) {
      if (!n || raw[n-1]==' ') continue;
      c=' ';
    }
    if (n<sizeof(raw)-1) raw[n++]=c;
    else ew_doc.truncated=1;
  }
  if (option && n && raw[n-1]==' ') --n;
  raw[n]=0;
  if (attribute_value(raw,n,out,cap,1)>=cap) ew_doc.truncated=1;
  *position=p;
}
static void control_run(unsigned kind) {
  struct ew_link *l=&ew_doc.links[linkid-1];
  struct ew_run EW_FAR *r;
  unsigned w, i, label_width;
  char display[3*EW_FIELD_VALUE];
  if (kind==6) return;
  ew_display_text(l->value[0]?l->value:"Submit",display,sizeof(display),0,0);
  w=(kind==EW_RUN_CHECK || kind==EW_RUN_RADIO) ? 12 :
      kind==EW_RUN_BUTTON ? ew_body_width(display,strlen(display),0)+12 : 212;
  if (kind==EW_RUN_SELECT) {
    w=12;
    for (i=0;i<option_count;++i) if (options[i].owner==linkid-1) {
      ew_display_text(options[i].label,display,sizeof(display),0,0);
      label_width=ew_body_width(display,strlen(display),0);
      if (label_width>w) w=label_width;
    }
    w+=15;
  }
  if (w>240) w=240;
  table_minimum(indent+w);
  if (px+(int)w>line_right()) newline(0);
  r=run(kind);
  if (r) r->w=w;
  px+=w+3;
  if (lineheight<EW_CONTROL_HEIGHT) lineheight=EW_CONTROL_HEIGHT;
}
static void select_finish(void) {
  unsigned short saved_link=linkid;
  unsigned char saved_style=style;
  if (!select_id) return;
  linkid=select_id;
  style=select_style;
  control_run(EW_RUN_SELECT);
  select_id=0;
  linkid=saved_link;
  style=saved_style;
}
unsigned ew_select_count(unsigned link) {
  unsigned i, count=0;
  for (i=0;i<option_count;++i) if (options[i].owner==link) ++count;
  return count;
}
static struct select_option *select_option(unsigned link, unsigned index) {
  unsigned i;
  for (i=0;i<option_count;++i)
    if (options[i].owner==link && !index--) return &options[i];
  return NULL;
}
const char EW_FAR *ew_select_label(unsigned link, unsigned index) {
  struct select_option *option=select_option(link,index);
  return option ? option->label : NULL;
}
int ew_select_index(unsigned link) {
  if (link>=ew_doc.link_count || ew_doc.links[link].kind!=EW_RUN_SELECT ||
      ew_doc.links[link].checked==255) return -1;
  return ew_doc.links[link].checked;
}
int ew_select_choose(unsigned link, unsigned index) {
  struct select_option *option;
  if (link>=ew_doc.link_count || ew_doc.links[link].kind!=EW_RUN_SELECT) return -1;
  option=select_option(link,index);
  if (!option) return -1;
  ew_doc.links[link].checked=index;
  {
    unsigned p=0, next=0;
    while (option->label[next]) {
      p=next; string_character(option->label,&next);
      if (next>=EW_FIELD_VALUE) break;
      p=next;
    }
    ew_copy_from_far(ew_doc.links[link].value,option->label,p+1);
  }
  return 0;
}
int ew_radio_choose(unsigned link) {
  unsigned i;
  struct ew_link *chosen;
  if (link>=ew_doc.link_count || ew_doc.links[link].kind!=EW_RUN_RADIO) return -1;
  chosen=&ew_doc.links[link];
  if (chosen->name[0])
    for (i=0;i<ew_doc.link_count;++i)
      if (ew_doc.links[i].kind==EW_RUN_RADIO && ew_doc.links[i].form==chosen->form &&
          !strcmp(ew_doc.links[i].name,chosen->name)) ew_doc.links[i].checked=0;
  chosen->checked=1;
  return 0;
}
/* Read from far source without narrowing its pointer into a libc near API.
 * Comparison stops immediately at NUL, including short comment prefixes.
 */
static int source_prefix(uint32_t p, const char *prefix) {
  while (*prefix) {
    if (source_byte(p) != *prefix)
      return 0;
    ++p;
    ++prefix;
  }
  return 1;
}
static uint32_t skip_comment(uint32_t p) {
  while (source_byte(p)) {
    if (source_prefix(p, "-->"))
      return p + 3;
    ++p;
  }
  return p;
}
static void add_anchor(const char *name) {
  unsigned i, j;
  const char EW_FAR *saved;
  if (!*name) return;
  for (i = 0; i < anchor_count; i++) {
    for (j = 0; name[j] && name[j] == anchors[i].name[j]; j++) {}
    if (!name[j] && !anchors[i].name[j]) return;
  }
  if (anchor_count == 64 || !(saved = ew_store_url(name))) {
    ew_doc.truncated = 1;
    return;
  }
  anchors[anchor_count].name = saved;
  anchors[anchor_count++].run_index = ew_doc.run_count;
  merge_start = ew_doc.run_count;
}
static int hex_digit(unsigned char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}
int ew_anchor_y(const char *fragment) {
  unsigned i, j;
  if (!*fragment) return 0;
  for (i = 0; i < anchor_count; i++) {
    const char *p = fragment;
    const char EW_FAR *name = anchors[i].name;
    int match = 1;
    j = 0;
    while (*p) {
      unsigned char c = *p++;
      if (c == '%' && p[0] && p[1] && hex_digit(p[0]) >= 0 &&
          hex_digit(p[1]) >= 0) {
        c = hex_digit(p[0]) * 16 + hex_digit(p[1]);
        p += 2;
      }
      if (!name[j] || c != (unsigned char)name[j]) { match = 0; break; }
      j++;
    }
    if (match && !*p && !name[j]) {
      unsigned index = anchors[i].run_index;
      return index < ew_doc.run_count ? ew_doc.runs[index].y : ew_doc.height;
    }
  }
  return -1;
}
/* Resource attributes retain their bytes; ALT is a bounded display string. */
static void image_alt_text(const char *input, char *output) {
  unsigned used=0, first, count, i, c;
  unsigned long value, minimum;
  while (*input && used<EW_IMAGE_ALT-1) {
    const char *expansion;
    first=(unsigned char)*input++;
    value=first;
    count=0; minimum=0;
    if (first>=0xc2 && first<=0xdf) { count=1; value=first&31; minimum=128; }
    else if (first>=0xe0 && first<=0xef) { count=2; value=first&15; minimum=2048; }
    else if (first>=0xf0 && first<=0xf4) { count=3; value=first&7; minimum=65536UL; }
    else if (first>=128) value=0xfffd;
    for (i=0;i<count;++i) {
      c=(unsigned char)input[i];
      if (!c || (c&0xc0)!=0x80) { value=0xfffd; break; }
      value=(value<<6)|(c&63);
    }
    if (i==count) input+=count;
    if (value<minimum || value>0x10ffffUL ||
        (value>=0xd800 && value<=0xdfff)) value=0xfffd;
    expansion=text_expansion(value);
    if (expansion) {
      while (*expansion && used<EW_IMAGE_ALT-1) output[used++]=*expansion++;
      if (*expansion) ew_doc.truncated=1;
    } else if (value<0x300 || value>0x36f) output[used++]=text_character(value);
  }
  output[used]=0;
  if (*input) ew_doc.truncated=1;
}
static void size_open(unsigned tag, unsigned size) {
  if (size_depth == 32) { size_overflow++; ew_doc.truncated = 1; return; }
  size_stack[size_depth].tag = tag;
  size_stack[size_depth++].size = style & (EW_SMALL | EW_LARGE);
  style = (style & ~(EW_SMALL | EW_LARGE)) | size;
}
static void size_close(unsigned tag) {
  unsigned i = size_depth;
  if (size_overflow) { size_overflow--; return; }
  while (i) {
    if (size_stack[--i].tag == tag) {
      style = (style & ~(EW_SMALL | EW_LARGE)) | size_stack[i].size;
      size_depth = i;
      return;
    }
  }
}
static void parse_document(const char *base, int plain_mode) {
  uint32_t p = 0;
  static char tag[EW_URL + 128], name[24], value[EW_URL], buf[128], skip[16];
  unsigned n, bn = 0;
  int space = 0, closing, title = 0, bold_depth = 0, underline_depth = 0;
  int tag_overflow;
  unsigned italic_depth = 0, mono_depth = 0, pre_depth = 0;
  char quote = 0;
  struct ew_run EW_FAR *r;
  struct ew_link *l;
  ew_image_reflow = 0;
  if (ew_document_reset())
    return;
  field_count = 0;
  anchor_count = 0;
  merge_start = 0;
  option_count = select_id = 0;
  list_depth = 0;
  center_depth = line_first = 0;
  memset(&table, 0, sizeof(table));
  memset(&saved_table, 0, sizeof(saved_table));
  table_ignored = 0;
  px = indent = 0;
  py = 0;
  lineheight = plain_mode ? EW_SMALL_HEIGHT : EW_BODY_HEIGHT;
  style = plain_mode ? EW_MONO | EW_SMALL : 0;
  heading_bold = 0;
  size_depth = size_overflow = 0;
  linkid = 0;
  inform = 0;
  inpre = plain_mode;
  pre_column = 0;
  parse_full = 0;
  skip[0] = 0;
  base_url = base;
  strcpy(ew_doc.title, "ELKSWeb");
  while (source_byte(p) && !parse_full) {
    if (!plain_mode && source_byte(p) == '<') {
      if (bn) {
        if (title) {
          n = strlen(ew_doc.title);
          if (n + bn < sizeof(ew_doc.title) - 1) {
            if (space && n)
              ew_doc.title[n++] = ' ';
            memcpy(ew_doc.title + n, buf, bn);
            ew_doc.title[n + bn] = 0;
          }
        } else if (!skip[0])
          word(buf, bn, space);
        bn = 0;
        space = 0;
      }
      if (source_prefix(p, "<!--")) {
        p = skip_comment(p + 4);
        continue;
      }
      p++;
      n = 0;
      quote = 0;
      tag_overflow = 0;
      while (source_byte(p)) {
        if (!quote && source_byte(p) == '>')
          break;
        if (source_byte(p) == '\'' || source_byte(p) == '"') {
          if (quote == source_byte(p))
            quote = 0;
          else if (!quote)
            quote = source_byte(p);
        }
        if (n < sizeof(tag) - 1)
          tag[n++] = source_byte(p);
        else
          tag_overflow = 1;
        p++;
      }
      tag[n] = 0;
      if (source_byte(p))
        p++;
      closing = tag[0] == '/';
      n = 0;
      while (tag[n + closing] && tag[n + closing] != '/' &&
             !isspace((unsigned char)tag[n + closing]) &&
             n < sizeof(name) - 1) {
        name[n] = tolower((unsigned char)tag[n + closing]);
        n++;
      }
      name[n] = 0;
      if (skip[0]) {
        if (closing && ci(name, skip))
          skip[0] = 0;
        continue;
      }
      if (ci(name, "script") || ci(name, "style")) {
        if (!closing)
          strcpy(skip, name);
        continue;
      }
      if (tag_overflow) {
        ew_doc.truncated = 1;
        continue;
      }
      if (!closing && ci(name, "meta")) {
        int charset = -1;
        if (attr(tag, "charset", value, sizeof(value))) charset = ew_charset_name(value);
        else if (attr(tag, "http-equiv", value, sizeof(value)) && ci(value, "content-type") &&
                 attr(tag, "content", value, sizeof(value))) charset = ew_charset_parameter(value);
        if (charset >= 0) parse_charset = charset;
        continue;
      }
      if (ci(name, "title")) {
        title = !closing;
        if (title)
          ew_doc.title[0] = 0;
        continue;
      }
      if (title)
        continue;
      if (!closing) {
        if (attr(tag, "id", value, sizeof(value))) add_anchor(value);
        if (ci(name, "a") && attr(tag, "name", value, sizeof(value)))
          add_anchor(value);
      }
      if (ci(name, "center")) {
        newline(0);
        if (closing) {
          if (center_depth)
            center_depth--;
        } else if (center_depth < 255)
          center_depth++;
        continue;
      }
      if (ci(name, "small") || ci(name, "big") || ci(name, "font")) {
        unsigned kind = ci(name, "font") ? 1 : ci(name, "small") ? 2 : 3;
        if (closing) size_close(kind);
        else {
          unsigned size = style & (EW_SMALL | EW_LARGE);
          if (kind == 2) size = EW_SMALL;
          else if (kind == 3) size = EW_LARGE;
          else if (attr(tag, "size", value, sizeof(value))) {
            long parsed = strtol(value, NULL, 10);
            int level;
            if (value[0] == '+' || value[0] == '-') {
              level = style & EW_SMALL ? 0 : style & EW_LARGE ? 2 : 1;
              level += parsed < -2 ? -2 : parsed > 2 ? 2 : (int)parsed;
              if (level < 0) level = 0;
              if (level > 2) level = 2;
            } else level = parsed == 1 || parsed == 2 ? 0 :
                           parsed == 0 || parsed == 3 || parsed == 4 ? 1 : 2;
            size = level == 0 ? EW_SMALL : level == 2 ? EW_LARGE : 0;
          }
          size_open(kind, size);
        }
        continue;
      }
      if (ci(name, "br")) {
        newline(1);
        continue;
      }
      if (ci(name, "p") || ci(name, "div") || ci(name, "section") ||
          ci(name, "blockquote")) {
        newline(4);
        continue;
      }
      if (name[0] == 'h' && name[1] >= '1' && name[1] <= '6' && !name[2]) {
        if (!closing && !py && !px)
          py = 6;
        else
          newline(4);
        if (closing) {
          heading_bold = 0;
          style &= ~(EW_BOLD | EW_LARGE);
          if (bold_depth)
            style |= EW_BOLD;
        } else {
          heading_bold = 1;
          style |= EW_BOLD;
          if (name[1] <= '2') style |= EW_LARGE;
          else style &= ~EW_LARGE;
        }
        continue;
      }
      if (ci(name, "b") || ci(name, "strong")) {
        if (closing) {
          if (bold_depth)
            --bold_depth;
        } else if (bold_depth < 255)
          ++bold_depth;
        if (bold_depth || heading_bold)
          style |= EW_BOLD;
        else
          style &= ~EW_BOLD;
        continue;
      }
      if (ci(name, "i") || ci(name, "em")) {
        if (closing) {
          if (italic_depth)
            --italic_depth;
        } else if (italic_depth < 32767U)
          ++italic_depth;
        if (italic_depth)
          style |= EW_ITALIC;
        else
          style &= ~EW_ITALIC;
        continue;
      }
      if (ci(name, "u")) {
        if (closing) {
          if (underline_depth)
            --underline_depth;
        } else if (underline_depth < 255)
          ++underline_depth;
        if (underline_depth || linkid)
          style |= EW_UNDERLINE;
        else
          style &= ~EW_UNDERLINE;
        continue;
      }
      if (ci(name, "code") || ci(name, "tt") || ci(name, "samp") || ci(name, "kbd")) {
        if (closing) { if (mono_depth) --mono_depth; }
        else if (mono_depth < 255) ++mono_depth;
        if (mono_depth || pre_depth) style |= EW_MONO;
        else style &= ~EW_MONO;
        continue;
      }
      if (ci(name, "pre")) {
        newline(2);
        if (closing) { if (pre_depth) --pre_depth; }
        else if (pre_depth < 255) ++pre_depth;
        inpre = pre_depth != 0;
        pre_column = 0;
        if (mono_depth || pre_depth) style |= EW_MONO;
        else style &= ~EW_MONO;
        continue;
      }
      if (ci(name, "ul") || ci(name, "ol")) {
        newline(2);
        if (closing) {
          if (list_depth)
            indent = lists[--list_depth].parent;
        } else if (list_depth < 12) {
          lists[list_depth].parent = indent;
          lists[list_depth].base = indent < 184 ? indent + 16 : 200;
          lists[list_depth].ordered = ci(name, "ol");
          lists[list_depth].next = 1;
          indent = lists[list_depth++].base;
        }
        px = indent;
        continue;
      }
      if (ci(name, "li")) {
        newline(0);
        if (!closing) {
          short base = list_depth ? lists[list_depth - 1].base : indent;
          indent = px = base;
          if (list_depth && lists[list_depth - 1].ordered) {
            char number[8];
            unsigned item = lists[list_depth - 1].next++;
            if (item > 9999)
              item = 9999;
            sprintf(number, "%u.", item);
            word(number, strlen(number), 0);
            px += 3;
          } else {
            r = run(EW_RUN_BULLET);
            if (r)
              r->w = 4;
            px = base + 13;
          }
          indent = px;
        }
        space = 0;
        continue;
      }
      if (ci(name, "table")) {
        if (closing) {
          if (table_ignored) --table_ignored;
          else if (table.active) table_finish();
        } else if (table_ignored || (table.active && saved_table.active)) {
          ++table_ignored;
          ew_doc.truncated=1;
        } else {
          if (table.active) {
            table.eligible=0;
            memcpy(&saved_table,&table,sizeof(table));
          }
          newline(0);
          memset(&table,0,sizeof(table));
          table.active=1;
          table.source=p;
          table.eligible=!saved_table.active;
          table.plan=255;
          if (table_replay) {
            for (n=0;n<table_plan_count;++n)
              if (table_plans[n].source==p) { table.plan=n; break; }
          }
          table.x=indent;
          table.y=py;
          table.saved_indent=indent;
          table.saved_style=style;
          table.padding=table.spacing=2;
          attr(tag,"border",value,sizeof(value));
          table.border=table_number(value,255)!=0;
          if (attr(tag,"cellpadding",value,sizeof(value)))
            table.padding=table_number(value,64);
          if (attr(tag,"cellspacing",value,sizeof(value)))
            table.spacing=table_number(value,64);
          attr(tag,"width",value,sizeof(value));
          table.requested=table_dimension(value,624);
        }
        continue;
      }
      if (ci(name, "tr")) {
        if (table_ignored) continue;
        if (table.active) {
          table_cell_close();
          if ((closing && table.row_open) || (!closing && table.col)) {
            if (table.row<15) ++table.row;
            else ew_doc.truncated=1;
            table.col=0;
          }
          table.row_open=!closing;
          px=indent;
        } else newline(2);
        continue;
      }
      if (ci(name, "td") || ci(name, "th")) {
        if (table_ignored) continue;
        if (table.active) {
          table_cell_close();
          if (!closing) {
            if (table.count>=32 || table.col>=8) {
              ew_doc.truncated=1;
              continue;
            }
            table.open=1;
            table.cell_minimum=table.word_width=0;
            table.first=ew_doc.run_count;
            table.cell_indent=indent;
            table.cell_style=style;
            indent=px=0;
            py=table.y;
            table.cell_x=px;
            table.cell_y=py;
            line_first=ew_doc.run_count;
            lineheight=EW_BODY_HEIGHT;
            attr(tag,"colspan",value,sizeof(value));
            table.span=table_number(value,8);
            if (!table.span) table.span=1;
            if (table.span>8-table.col) {
              table.span=8-table.col;
              ew_doc.truncated=1;
            }
            if (table.span!=1) table.eligible=0;
            attr(tag,"rowspan",value,sizeof(value));
            if (table_number(value,16)>1) table.eligible=0;
            attr(tag,"width",value,sizeof(value));
            table.cell_requested=table_dimension(value,
                table.requested ? table.requested : 624);
            if (!table.cell_requested) {
              table.automatic=1;
              if (table.plan!=255 && table.col<table_plans[table.plan].columns)
                table.cell_requested=table_plans[table.plan].widths[table.col];
            }
            if (ci(name,"th")) style|=EW_BOLD;
          }
        } else if (closing) {
          if (px>608) newline(0);
          else px+=16;
        }
        continue;
      }
      if (ci(name, "hr")) {
        newline(3);
        r = run(EW_RUN_RULE);
        if (r)
          r->n = 616;
        table_minimum(616);
        newline(3);
        continue;
      }
      if (ci(name, "a")) {
        if (closing) {
          linkid = 0;
          style &= ~EW_UNDERLINE;
        } else {
          if (attr(tag, "href", value, sizeof(value)) >= sizeof(value)) {
            ew_doc.truncated = 1;
            linkid = 0;
            continue;
          }
          if (value[0]) {
            linkid = add_link(0, value);
            style |= EW_UNDERLINE;
          }
        }
        continue;
      }
      if (ci(name, "form")) {
        select_finish();
        newline(2);
        if (closing)
          inform = 0;
        else if (ew_doc.form_count < 4) {
          struct ew_form *f = &ew_doc.forms[ew_doc.form_count++];
          inform = ew_doc.form_count;
          attr(tag, "action", value, sizeof(value));
          ew_resolve_url(base, value[0] ? value : base, f->action,
                         sizeof(f->action));
          attr(tag, "method", value, sizeof(value));
          f->post = ci(value, "post");
        }
        continue;
      }
      if (ci(name, "input") && !closing) {
        unsigned kind = EW_RUN_FIELD;
        attr(tag, "type", value, sizeof(value));
        if (ci(value, "hidden")) kind = 6;
        else if (ci(value, "submit") || ci(value, "button")) kind = EW_RUN_BUTTON;
        else if (ci(value, "checkbox")) kind = EW_RUN_CHECK;
        else if (ci(value, "radio")) kind = EW_RUN_RADIO;
        else if (ci(value, "password")) kind = EW_RUN_PASSWORD;
        linkid = add_link(kind, NULL);
        if (!linkid) continue;
        l = &ew_doc.links[linkid - 1];
        attr_utf8(tag, "name", l->name, 32);
        attr_utf8(tag, "value", l->value, EW_FIELD_VALUE);
        if (attribute_present(tag, "value")) l->flags |= EW_CONTROL_VALUE;
        l->checked = attribute_present(tag, "checked");
        if (kind == EW_RUN_RADIO && l->checked) ew_radio_choose(linkid - 1);
        control_run(kind);
        linkid = 0;
        continue;
      }
      if (ci(name, "select")) {
        if (closing) select_finish();
        else {
          select_finish();
          select_id = linkid = add_link(EW_RUN_SELECT, NULL);
          if (select_id) {
            l = &ew_doc.links[select_id - 1];
            attr_utf8(tag, "name", l->name, 32);
            l->checked = 255;
            select_style = style;
          }
          linkid = 0;
        }
        continue;
      }
      if (ci(name, "option") && !closing) {
        static char label[256], option_value[EW_URL];
        int selected = attribute_present(tag, "selected");
        int explicit_value = attribute_present(tag, "value");
        if (explicit_value) attr_utf8(tag, "value", option_value, sizeof(option_value));
        control_text(&p, "select", 1, label, sizeof(label));
        if (select_id && option_count < 64) {
          struct select_option *option = &options[option_count];
          unsigned ordinal = ew_select_count(select_id - 1);
          option->owner = select_id - 1;
          option->label = ew_store_url(label);
          option->value = ew_store_url(explicit_value ? option_value : label);
          if (option->label && option->value) {
            ++option_count;
            if (selected || ew_select_index(select_id - 1) < 0)
              ew_select_choose(select_id - 1, ordinal);
          } else ew_doc.truncated = 1;
        } else if (select_id) ew_doc.truncated = 1;
        continue;
      }
      if (ci(name, "textarea")) {
        if (!closing) {
          static char initial[EW_FIELD_VALUE];
          linkid = add_link(EW_RUN_TEXTAREA, NULL);
          if (linkid) {
            l = &ew_doc.links[linkid - 1];
            attr_utf8(tag, "name", l->name, 32);
          }
          control_text(&p, "textarea", 0, initial, sizeof(initial));
          if (linkid) {
            strcpy(ew_doc.links[linkid - 1].value, initial);
            control_run(EW_RUN_TEXTAREA);
          }
          linkid = 0;
        }
        continue;
      }
      if (ci(name, "img") && !closing) {
        static char resolved[EW_URL], alt[EW_IMAGE_ALT];
        int width = 16, height = 16, image_index;
        unsigned len, alt_len, natural_width = 16, natural_height = 16;
        int has_width, has_height, ismap;
        attr(tag, "src", value, sizeof(value));
        if (!value[0] ||
            ew_resolve_url(base_url, value, resolved, sizeof(resolved)))
          continue;
        attr_utf8(tag, "alt", value, sizeof(value));
        image_alt_text(value, alt);
        alt_len=strlen(alt)+1;
        ismap=linkid && attribute_present(tag,"ismap");
        image_index =
            ew_image_lookup(resolved, &natural_width, &natural_height);
        width = natural_width > 616 ? 616 : (int)natural_width;
        height = natural_height > 400 ? 400 : (int)natural_height;
        if (!width) width=alt[0] ? ew_body_width(alt,alt_len-1,0)+14 : 16;
        if (!height) height=24;
        attr(tag, "width", value, sizeof(value));
        has_width = !!value[0];
        if (has_width)
          width = atoi(value);
        attr(tag, "height", value, sizeof(value));
        has_height = !!value[0];
        if (has_height)
          height = atoi(value);
        if (width < 1)
          width = 1;
        if (width > 616)
          width = 616;
        if (height < 1)
          height = 1;
        if (height > 400)
          height = 400;
        if (has_width && !has_height && natural_width) {
          long scaled = (long)width * natural_height / natural_width;
          height = scaled > 400 ? 400 : (int)scaled;
        }
        if (has_height && !has_width && natural_height) {
          long scaled = (long)height * natural_width / natural_height;
          width = scaled > 616 ? 616 : (int)scaled;
        }
        /* CGA's 640x200 pixels are twice as tall as they are wide. */
        if (ew_pixel_aspect == 2) height = height / 2 + (height & 1);
        if (height < 1) height = 1;
        if (width < 1)
          width = 1;
        if (width > 616)
          width = 616;
        if (height < 1)
          height = 1;
        if (height > 200)
          height = 200;
        table_minimum(indent+width);
        if (px + width > line_right())
          newline(0);
        len = strlen(resolved) + 1;
        if ((unsigned long)ew_doc.text_len + len + alt_len + 1 >= EW_TEXT) {
          ew_doc.truncated = parse_full = 1;
          continue;
        }
        r = run(EW_RUN_IMAGE);
        if (!r)
          continue;
        if (!has_width || !has_height) ew_image_reflow = 1;
        r->off = ew_doc.text_len;
        r->n = width;
        r->w = height;
        r->style = image_index < 0 ? 255 : image_index;
        ew_copy_to_far(ew_doc.text + ew_doc.text_len, resolved, len);
        ew_doc.text_len += len;
        ew_copy_to_far(ew_doc.text + ew_doc.text_len, alt, alt_len);
        ew_doc.text_len += alt_len;
        ew_doc.text[ew_doc.text_len++]=ismap ? EW_LINK_ISMAP : 0;
        if (ismap) ew_doc.links[linkid-1].flags|=EW_LINK_ISMAP;
        px += width;
        if (lineheight < height + 2)
          lineheight = height + 2;
        continue;
      }
      continue;
    }
    if (skip[0] || select_id) {
      p++;
      continue;
    }
    if (isspace((unsigned char)source_byte(p))) {
      if (bn) {
        if (title) {
          n = strlen(ew_doc.title);
          if (n + bn + 1 < sizeof(ew_doc.title)) {
            if (n)
              ew_doc.title[n++] = ' ';
            memcpy(ew_doc.title + n, buf, bn);
            ew_doc.title[n + bn] = 0;
          }
        } else
          word(buf, bn, space);
        bn = 0;
      }
      if (inpre) {
        unsigned char whitespace = source_byte(p);
        if (whitespace == '\n') {
          int empty = px == indent;
          newline(0);
          if (empty) {
            if (py <= 16000 - lineheight) py += lineheight;
            else { py = 16000; ew_doc.truncated = 1; }
          }
          pre_column = 0;
        } else if (whitespace != '\r') {
          unsigned spaces = whitespace == '\t' ? 8 - pre_column : 1;
          while (spaces-- && !parse_full) word(" ", 1, 0);
        }
      }
      space = !inpre;
      p++;
      continue;
    }
    if (bn >= sizeof(buf) - 3) {
      if (!title)
        word(buf, bn, space);
      bn = 0;
      space = 0;
    }
    {
      unsigned long value;
      unsigned character;
      const char *expansion;
      if (!plain_mode && source_byte(p) == '&') { ++p; value = entity(&p); }
      else value = utf8_character(&p);
      character = text_character(value);
      expansion = text_expansion(value);
      if (expansion) while (*expansion) buf[bn++] = *expansion++;
      else if (value < 0x300 || value > 0x36f) buf[bn++] = (char)character;
    }
  }
  if (bn && !title)
    word(buf, bn, space);
  select_finish();
  while (table.active) {
    table.eligible=0;
    table_finish();
  }
  align_line();
  if (file_source && ew_source_error()[0])
    ew_doc.truncated = 1;
  ew_doc.height = py + lineheight + 8;
  ew_document_trim();
}
static void parse_html(const char *base) {
  unsigned char charset=parse_charset;
  table_plan_count=table_replay=0;
  parse_document(base,0);
  if (table_plan_count && !ew_doc.truncated) {
    table_replay=1;
    parse_charset=charset;
    parse_document(base,0);
    if (ew_doc.truncated) {
      /* Reflow must not discard content that fit before column negotiation. */
      table_plan_count=0;
      parse_charset=charset;
      parse_document(base,0);
    }
  }
  table_replay=0;
}
void ew_parse(const char EW_FAR *html, const char *base) {
  parse_charset = EW_CHARSET_UTF8;
  file_source = 0;
  parse_source = html;
  parse_tail = NULL;
  parse_length = EW_SOURCE;
  parse_html(base);
}
void ew_parse_source(const char *base) {
  parse_charset = ew_document_charset;
  file_source = 1;
  parse_source = ew_source;
  parse_tail = ew_source_tail;
  parse_length = ew_source_length;
  parse_html(base);
}
void ew_parse_text_source(const char *base) {
  parse_charset = ew_document_charset;
  file_source = 1;
  parse_source = ew_source;
  parse_tail = ew_source_tail;
  parse_length = ew_source_length;
  parse_document(base, 1);
}
void ew_parse_image_source(const char *url) {
  struct ew_run EW_FAR *r;
  unsigned width = 0, height = 0, len = strlen(url) + 1;
  unsigned limit = 200U * ew_pixel_aspect;
  int image = ew_image_lookup(url, &width, &height);
  if (ew_document_reset()) return;
  anchor_count = merge_start = 0;
  strcpy(ew_doc.title, "Image - ELKSWeb");
  if (!width || !height) { width = 64; height = 64; }
  if (width > 616) {
    height = (unsigned)((unsigned long)height * 616 / width);
    width = 616;
  }
  if (height > limit) {
    width = (unsigned)((unsigned long)width * limit / height);
    height = limit;
    if (!width) width = 1;
  }
  if (ew_pixel_aspect == 2) height = (height + 1UL) / 2;
  if (!height) height = 1;
  r = &ew_doc.runs[0];
  ew_zero_far(r, sizeof(*r));
  r->kind = EW_RUN_IMAGE;
  r->n = width;
  r->w = height;
  r->style = image < 0 ? 255 : image;
  ew_copy_to_far(ew_doc.text, url, len);
  ew_doc.text[len] = ew_doc.text[len + 1] = 0;
  ew_doc.text_len = len + 2;
  ew_doc.run_count = 1;
  ew_doc.height = height + 8;
  ew_document_trim();
}
static int enc_bytes(char *out, unsigned cap, unsigned *n, const char EW_FAR *s) {
  const char *hex = "0123456789ABCDEF";
  unsigned char c;
  while ((c = (unsigned char)*s++)) {
    unsigned need =
        (((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
         (c >= '0' && c <= '9')) || c == '-' || c == '_' || c == '.' || c == '~' || c == ' ')
            ? 1
            : 3;
    if (*n + need >= cap)
      return -1;
    if (((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
         (c >= '0' && c <= '9')) || c == '-' || c == '_' || c == '.' || c == '~')
      out[(*n)++] = c;
    else if (c == ' ')
      out[(*n)++] = '+';
    else {
      out[(*n)++] = '%';
      out[(*n)++] = hex[c >> 4];
      out[(*n)++] = hex[c & 15];
    }
  }
  out[*n] = 0;
  return 0;
}
static int enc(char *out, unsigned cap, unsigned *n,
               const char EW_FAR *s, unsigned charset) {
  unsigned p=0, start, byte;
  unsigned long value;
  char encoded[16];
  if (charset==EW_CHARSET_UTF8) return enc_bytes(out,cap,n,s);
  while (s[p]) {
    start=p; value=string_character(s,&p);
    if (value<128 || (value<256 && legacy_character((unsigned)value,charset)==0xfffd))
      byte=(unsigned)value;
    else {
      for (byte=128;byte<256;++byte)
        if (legacy_character(byte,charset)==value && value!=0xfffd) break;
    }
    if (byte<256) { encoded[0]=byte; encoded[1]=0; }
    else sprintf(encoded,"&#%lu;",value);
    if (enc_bytes(out,cap,n,encoded)) return -1;
    if (p==start) break;
  }
  return 0;
}
int ew_form_url(unsigned index, char *url, unsigned cap, char *post,
                unsigned pc) {
  unsigned n = 0, i, form;
  struct ew_form *f;
  struct ew_link *l;
  if (index >= ew_doc.link_count)
    return -1;
  form = ew_doc.links[index].form;
  if (!form || form > ew_doc.form_count)
    return -1;
  f = &ew_doc.forms[form - 1];
  post[0] = 0;
  for (i = 0; i < ew_doc.link_count; i++) {
    l = &ew_doc.links[i];
    if (l->form != form || !l->name[0] || l->kind == 0 ||
        ((l->kind == EW_RUN_CHECK || l->kind == EW_RUN_RADIO) && !l->checked) ||
        (l->kind == EW_RUN_BUTTON && i != index))
      continue;
    if (l->kind == EW_RUN_SELECT && ew_select_index(i) < 0) continue;
    if (n) {
      if (n + 1 >= pc)
        return -1;
      post[n++] = '&';
    }
    if (enc(post, pc, &n, l->name, l->flags >> 2))
      return -1;
    if (n + 1 >= pc)
      return -1;
    post[n++] = '=';
    if (l->kind == EW_RUN_SELECT) {
      struct select_option *option = select_option(i, l->checked);
      if (!option || enc(post, pc, &n, option->value, l->flags >> 2)) return -1;
    } else if (enc(post, pc, &n,
            l->value[0] ? l->value :
            ((l->kind == EW_RUN_CHECK || l->kind == EW_RUN_RADIO) &&
             !(l->flags & EW_CONTROL_VALUE)) ? "on" : "", l->flags >> 2))
      return -1;
  }
  if (strlen(f->action) >= cap)
    return -1;
  strcpy(url, f->action);
  if (!f->post && n) {
    char *fragment = strchr(url, '#');
    unsigned tail = fragment ? strlen(fragment) : 0;
    i = fragment ? (unsigned)(fragment - url) : strlen(url);
    if (i + tail + 1 + n >= cap)
      return -1;
    memmove(url + i + n + 1, url + i, tail + 1);
    url[i] = memchr(url, '?', i) ? '&' : '?';
    ++i;
    memcpy(url + i, post, n);
    post[0] = 0;
  }
  return 0;
}
