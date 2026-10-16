/* Actual browser renderer with a recording host framebuffer. Every write,
 * including same-color writes, is counted. Cursor sprite is intentionally off;
 * driver cursor/physical framebuffer behavior is covered separately. */
#define main qa_unused_repaint_main
#include "../src/main.c"
#undef main

int ew_screen_height=200, ew_pixel_aspect=2;
static unsigned writes[480][640];
static unsigned char pixels[480][640];
static int clip_right=640, clip_top, clip_bottom=200;
static unsigned clears;
void ew_clip(int right,int top_y,int bottom_y) {
  clip_right=right;clip_top=top_y;clip_bottom=bottom_y;
}
void ew_pixel(int x,int y,int color) {
  if(x<0 || x>=640 || y<0 || y>=ew_screen_height ||
     x>=clip_right || y<clip_top || y>=clip_bottom)return;
  ++writes[y][x];pixels[y][x]=!!color;
}
void ew_hline(int x,int y,int width,int color) {
  int i;for(i=0;i<width;i++)ew_pixel(x+i,y,color);
}
void ew_vline(int x,int y,int height,int color) {
  int i;for(i=0;i<height;i++)ew_pixel(x,y+i,color);
}
void ew_fillrect(int x,int y,int width,int height,int color) {
  int i;for(i=0;i<height;i++)ew_hline(x,y+i,width,color);
}
void ew_rect(int x,int y,int width,int height,int color) {
  if(width<=0 || height<=0)return;
  ew_hline(x,y,width,color);ew_hline(x,y+height-1,width,color);
  ew_vline(x,y,height,color);ew_vline(x+width-1,y,height,color);
}
void ew_clear(int color) {
  int x,y;++clears;
  /* Real clear writes the entire framebuffer; it does not obey clipping. */
  for(y=0;y<ew_screen_height;y++)for(x=0;x<640;x++) {
    ++writes[y][x];pixels[y][x]=!!color;
  }
}
void ew_cursor_show(int x,int y) {(void)x;(void)y;}
void ew_cursor_hide(void) {}
void ew_cursor_shape(int hand) {(void)hand;}
int ew_platform_init(const char *mode) {(void)mode;return 0;}
void ew_platform_shutdown(void) {}
const char *ew_platform_error(void) {return "";}
int ew_getkey(void) {return 0;}
int ew_mouse_present(void) {return 0;}
int ew_mouse_read(struct ew_mouse_event *event) {(void)event;return 0;}
void qa_repaint_writes_reset(void) {memset(writes,0,sizeof(writes));clears=0;}
unsigned long qa_repaint_writes(int x0,int y0,int x1,int y1) {
  unsigned long n=0;int x,y;
  for(y=y0;y<y1;y++)for(x=x0;x<x1;x++)n+=writes[y][x];
  return n;
}
unsigned qa_repaint_clears(void) {return clears;}
void qa_repaint_prepare(const char *html,int height) {
  int hi;
  for(hi=0;hi<hcount;hi++)ew_far_free(history[hi]);
  memset(history,0,sizeof(history));hcount=0;hpos=-1;
  ew_images_clear();ew_source_free();
  ew_screen_height=height;ew_pixel_aspect=height==200?2:1;
  ew_clip(640,0,height);
  focused=hovered=select_open=-1;
  scroll=hscroll=editing=download_edit=stopping=mouse_active=inverse=0;
  chrome=1;field_pos=address_pos=selectall=0;
  strcpy(current,"http://fixture.invalid/page.htm");strcpy(address,current);
  status[0]=0;
  ew_parse(html,current);measure_page();
  dirty=31;draw();qa_repaint_writes_reset();
}
void qa_repaint_key(int which) {
  static const int codes[]={EW_KEY_DOWN,EW_KEY_PGDN,EW_KEY_TAB,EW_KEY_F6,
    EW_KEY_LEFT,EW_KEY_ESC,EW_KEY_F2,EW_KEY_F3,EW_KEY_RIGHT};
  key(which>=0 && which<9 ? codes[which] : which);
  if(dirty)draw();
}
void qa_repaint_status(const char *s) {message(s);if(dirty)draw();}
void qa_repaint_progress(const char *s) {ew_net_progress(s);}
void qa_repaint_hover(int x,int y) {
  struct ew_mouse_event e;memset(&e,0,sizeof(e));e.x=x;e.y=y;
  mouse_event(&e);if(dirty)draw();
}
void qa_repaint_edges(void) {
  unsigned i;
  /* Place alternating real glyph/box/rule runs across the viewport edges.
   * DOWN moves10px; top and bottom examples therefore straddle by4px. */
  for(i=0;i<ew_doc.run_count;i++) {
    struct ew_run *r=&ew_doc.runs[i];
    r->x=i%2 ? 620 : -4;
    r->y=i%2 ? bottom()-top()+6 : 6;
  }
  ew_doc.height=2000;key(EW_KEY_DOWN);
  /* Isolate the page pass to distinguish leaked glyph/control writes from
   * legitimate footer updates. The page bit is1 in both old/new main.c. */
  dirty=1;draw();
}
void qa_repaint_cleanup(void) {ew_images_clear();ew_source_free();}
static unsigned char snapshot[480][640];
void qa_repaint_snapshot(void) {memcpy(snapshot,pixels,sizeof(snapshot));}
unsigned qa_repaint_difference(int x0,int y0,int x1,int y1) {
  unsigned n=0;int x,y;
  for(y=y0;y<y1;y++)for(x=x0;x<x1;x++)n+=pixels[y][x]!=snapshot[y][x];
  return n;
}
int qa_repaint_load(const char *url) {int r=load(url,NULL,1);if(dirty)draw();return r;}
void qa_repaint_bad_address(const char *url) {
  key(EW_KEY_F6);strncpy(address,url,sizeof(address)-1);draw();
  qa_repaint_writes_reset();key(EW_KEY_ENTER);if(dirty)draw();
}
int qa_repaint_download(void) {return download_edit;}
void qa_repaint_save(const char *path) {
  strncpy(download_name,path,sizeof(download_name)-1);
  key(EW_KEY_ENTER);if(dirty)draw();
}

void qa_repaint_click_back(void) {
  struct ew_mouse_event e;memset(&e,0,sizeof(e));e.x=15;e.y=12;
  e.buttons=e.pressed=EW_MOUSE_LEFT;mouse_event(&e);if(dirty)draw();
}
int qa_repaint_editing(void) {return editing;}
unsigned qa_repaint_full_equivalence(void) {
  qa_repaint_snapshot();dirty=31;draw();
  return qa_repaint_difference(0,0,640,ew_screen_height);
}
