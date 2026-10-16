/* Test-only allocation injection. Production memory.c is included unchanged. */
#include <stdlib.h>
#include <stddef.h>
#include <stdio.h>
#include <fcntl.h>
#include <errno.h>
static unsigned qa_calls, qa_fail_at, qa_live;
static void *qa_fault_malloc(size_t size)
{
  void *p;
  ++qa_calls;
  if (qa_fail_at && qa_calls >= qa_fail_at) return NULL;
  p = malloc(size);
  if (p) ++qa_live;
  return p;
}
static void qa_fault_free(void *p)
{
  if (p) { --qa_live; free(p); }
}
void qa_allocator_reset(unsigned fail_at) { qa_calls = 0; qa_fail_at = fail_at; }
unsigned qa_allocator_live(void) { return qa_live; }
static unsigned qa_io_fail;
void qa_io_reset(unsigned failure) { qa_io_fail = failure; }
static int qa_fault_open(const char *path, int flags, unsigned mode)
{ if (qa_io_fail & 1) { errno=EACCES; return -1; } return open(path,flags,mode); }
static int qa_fault_putc(int c,FILE *stream)
{ if (qa_io_fail & 2) { errno=ENOSPC;return EOF; } return fputc(c,stream); }
static int qa_fault_seek(FILE *stream,long offset,int origin)
{ if (qa_io_fail & 4) { errno=EIO;return -1; } return fseek(stream,offset,origin); }
static size_t qa_fault_read(void *p,size_t n,size_t count,FILE *stream)
{ if (qa_io_fail & 8) { errno=EIO;return 0; } return fread(p,n,count,stream); }
static int qa_fault_flush(FILE *stream)
{ if (qa_io_fail & 16) { errno=ENOSPC;return EOF; } return fflush(stream); }
#define open qa_fault_open
#define fputc qa_fault_putc
#define fseek qa_fault_seek
#define fread qa_fault_read
#define fflush qa_fault_flush
#define malloc qa_fault_malloc
#define free qa_fault_free
#include "../src/memory.c"
