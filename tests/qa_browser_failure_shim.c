/* Host-only driver for actual main.c navigation and download state machines. */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <sys/types.h>
static unsigned save_fault, save_written, save_interrupt;
static int cancel_key;
static int qa_save_open(const char *path,int flags,...)
{
  if (save_fault&1) { errno=EACCES;return -1; }
  return open(path,flags,0600);
}
static ssize_t qa_save_write(int fd,const void *data,size_t size)
{
  if ((save_fault&32) && !save_interrupt++) { errno=EINTR;return -1; }
  if ((save_fault&2) && save_written>=23) { errno=ENOSPC;return -1; }
  if (save_fault&64) return 0;
  if ((save_fault&2) && size>23-save_written) size=23-save_written;
  if ((save_fault&16) && size>17) size=17;
  {
    ssize_t n=write(fd,data,size);
    if (n>0) save_written+=(unsigned)n;
    return n;
  }
}
static int qa_save_close(int fd)
{
  int result=close(fd);
  if (save_fault&4) { errno=EIO;return -1; }
  return result;
}
static int qa_save_unlink(const char *path)
{
  if (save_fault&8) { errno=EACCES;return -1; }
  return unlink(path);
}
#define main qa_unused_browser_main
#define open qa_save_open
#define write qa_save_write
#define close qa_save_close
#define unlink qa_save_unlink
#include "../src/main.c"
#undef main
#undef open
#undef write
#undef close
#undef unlink
/* Keep actual parser query adapters, but main.c owns network progress. */
#define ew_net_progress qa_unused_net_progress
#include "qa_core_shim.c"
#undef ew_net_progress
void ew_clip(int r,int t,int b) {(void)r;(void)t;(void)b;}
void ew_scroll(int t,int b,int d) {(void)t;(void)b;(void)d;}
void ew_clear(int c) {(void)c;}
void ew_hline(int x,int y,int w,int c) {(void)x;(void)y;(void)w;(void)c;}
void ew_rect(int x,int y,int w,int h,int c) {(void)x;(void)y;(void)w;(void)h;(void)c;}
void ew_cursor_show(int x,int y) {(void)x;(void)y;}
void ew_cursor_hide(void) {}
void ew_cursor_shape(int shape) {(void)shape;}
int ew_platform_init(const char *mode) {(void)mode;return 0;}
void ew_platform_shutdown(void) {}
const char *ew_platform_error(void) {return "";}
int ew_mouse_read(struct ew_mouse_event *event) {(void)event;return 0;}
int ew_mouse_present(void) {return 0;}
int ew_getkey(void) {int k=cancel_key;cancel_key=0;return k;}
void qa_browser_reset(void)
{
  int i;
  ew_images_clear();
  for(i=0;i<hcount;i++)ew_far_free(history[i]);
  memset(history,0,sizeof(history));hcount=0;hpos=-1;
  ew_source_free();
  current[0]=address[0]=status[0]=0;
  focused=hovered=select_open=-1;
  scroll=hscroll=editing=download_edit=stopping=0;
  save_fault=save_written=save_interrupt=0;cancel_key=0;
}
int qa_browser_load(const char *url) {return load(url,NULL,1);}
const char *qa_browser_status(void) {return status;}
const char *qa_browser_current(void) {return current;}
int qa_browser_download_open(void) {return download_edit;}
int qa_browser_history_count(void) {return hcount;}
void qa_browser_back(void) {history_go(hpos-1);}
void qa_browser_save(const char *path,unsigned fault,int cancel)
{
  strncpy(download_name,path,sizeof(download_name)-1);
  download_name[sizeof(download_name)-1]=0;
  save_fault=fault;save_written=save_interrupt=0;
  cancel_key=cancel ? EW_KEY_ESC : 0;
  key(EW_KEY_ENTER);
}
void qa_browser_cancel_download(void) {key(EW_KEY_ESC);}
