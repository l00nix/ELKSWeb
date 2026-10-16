/* Deterministic bounded host fuzzing of actual C layout and URL code.
 * Run with ASan/UBSan. This cannot prove 16-bit execution compatibility. */
#include "elksweb.h"
int ew_screen_height=200, ew_pixel_aspect=2;
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static uint32_t state = UINT32_C(0x1868088);
void ew_pixel(int x,int y,int color) { (void)x; (void)y; (void)color; }
void ew_fillrect(int x,int y,int w,int h,int color) { (void)x; (void)y; (void)w; (void)h; (void)color; }
void ew_vline(int x,int y,int h,int color) { ew_fillrect(x,y,1,h,color); }
int ew_image_lookup(const char *url,unsigned *width,unsigned *height) { (void)url;(void)width;(void)height;return -1; }
static unsigned rnd(void) { state=state*UINT32_C(1664525)+UINT32_C(1013904223); return state>>16; }
static const char *tokens[]={"text ","— ‘quote’ … ","&#x110000;","&unknown;","<center>","</center>","<small>","</small>","<b>","</b>","<i>","</i>","<p>","</p>","<br/>","<br>","</td>","<td>","<tr>","</tr>","<ul>","</ul>","<li>","&amp;","&#0;","&#65535;","<!--","-->","<script>","</script>","<title>","</title>","<a href='../path?q=x#f'>","</a>","<input type='checkbox' checked name='x'>","<form action='/submit'>","<select name='pick'>","</select>","<option value='a&amp;b' selected>","<option>","</option>","<textarea name='notes'>","</textarea>","<input type='password' name='p'>","<input type='radio' name='r' checked>","<a name='point'></a>","<p id='target'>","</form>","\n", "<img src='/x.gif' alt='image'>", "<", ">", "'", "\"", "&notfinished", "<pre>", "</pre>", "<code>", "</code>", "<tt>", "</tt>", "<kbd>", "</kbd>", "<samp>", "</samp>", "\t", "\r\n", "<h6>", "</h6>", "<h1>", "</h1>", "<table border='1'>", "<table border=1 width=180><tr><td>label</td><td>one two three four five six</td></tr></table>", "<table><tr><td>one two</td><td>three four</td></tr></table><table><tr><td>next</td></tr></table>", "<td width='1'>", "<td width='40'>", "<th width='25%'>", "<table cellpadding='64'><tr><td width='1'><ul><li>nested words here<ul><li>inner</li></ul></li></ul>", "<td colspan='2' rowspan='3'>", "<table width='9999999' cellspacing='65535' cellpadding='65535'>", "</table>"};
int main(int argc,char **argv) {
 char *html=malloc(EW_SOURCE+1), ref[EW_URL+20], url[EW_URL+16];
 char form_url[EW_URL+16], post[512+16], display[240+16];
 unsigned round,n,i,j,len;int status;
 if(!html)return 2;
 for(round=0;round<10000;round++) {
  n=0;len=rnd()%EW_SOURCE;
  while(n<len){const char *t=tokens[rnd()%(sizeof(tokens)/sizeof(tokens[0]))];unsigned l=strlen(t);if(l>len-n)l=len-n;memcpy(html+n,t,l);n+=l;}
  html[n]=0;ew_parse(html,"http://host/a/b.htm?q=x#f");
  if(ew_doc.run_count>EW_RUNS||ew_doc.text_len>=EW_TEXT||ew_doc.link_count>EW_LINKS){fprintf(stderr,"document bounds round %u\n",round);return 3;}
  for(i=0;i<ew_doc.run_count;i++){struct ew_run *r=&ew_doc.runs[i];if(r->x<0||r->x>16000||r->y<0||r->y>16000||(r->off+r->n>ew_doc.text_len&&r->kind==EW_RUN_TEXT)||r->link>ew_doc.link_count){fprintf(stderr,"run bounds round %u run %u x=%d y=%d off=%u n=%u kind=%u\n",round,i,r->x,r->y,r->off,r->n,r->kind);if(argc>1){FILE *f=fopen(argv[1],"wb");if(f){fwrite(html,1,n,f);fclose(f);}}return 4;}}
  for(i=0;i<ew_doc.link_count;i++)if(ew_doc.links[i].kind) {
   unsigned cursor=rnd()%(strlen(ew_doc.links[i].value)+1);
   memset(form_url,0x5a,sizeof(form_url));memset(post,0x5a,sizeof(post));
   status=ew_form_url(i,form_url,EW_URL,post,512);
   for(j=EW_URL;j<sizeof(form_url);j++)if(form_url[j]!=0x5a)return 8;
   for(j=512;j<sizeof(post);j++)if(post[j]!=0x5a)return 9;
   if(!status&&(!memchr(form_url,0,EW_URL)||!memchr(post,0,512)))return 10;
   memset(display,0x5a,sizeof(display));
   ew_display_text(ew_doc.links[i].value,display,240,cursor,ew_doc.links[i].kind==EW_RUN_PASSWORD);
   for(j=240;j<sizeof(display);j++)if(display[j]!=0x5a)return 11;
   if(!memchr(display,0,240))return 12;
   if(ew_text_step(ew_doc.links[i].value,cursor,1)>strlen(ew_doc.links[i].value))return 13;
   if(ew_text_step(ew_doc.links[i].value,cursor,-1)>strlen(ew_doc.links[i].value))return 14;
  }
  len=rnd()%(sizeof(ref)-1);for(j=0;j<len;j++)ref[j]="abcdefghijklmnopqrstuvwxyz./?#:%& "[rnd()%34];ref[len]=0;
  memset(url,0x5a,sizeof(url));status=ew_resolve_url("http://host/a/b.htm?x#f",ref,url,EW_URL);
  for(j=EW_URL;j<sizeof(url);j++)if(url[j]!=0x5a){fprintf(stderr,"URL guard round %u\n",round);return 5;}
  if(!status&&!memchr(url,0,EW_URL)){fprintf(stderr,"URL terminator round %u\n",round);return 6;}
 }
 /* Explicit 16-bit layout accumulation edge from the independent regression. */
 for(i=0;i<2050;i++)memcpy(html+i*5,"</td>",5);memcpy(html+10250,"X",2);
 ew_parse(html,"http://host/");if(ew_doc.run_count&&ew_doc.runs[0].x<0)return 7;
 ew_source_free();free(html);puts("{\"iterations\":10000,\"seed\":\"01868088\",\"html_url_bounds\":\"pass\",\"native_16bit_execution\":\"not_tested\"}");return 0;
}
