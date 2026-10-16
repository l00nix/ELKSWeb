/* Route actual GIF decoder allocations through the shared fault tracker. */
#include <stdlib.h>
extern void *qa_resource_malloc(size_t size);
extern void qa_resource_free(void *p);
#define malloc qa_resource_malloc
#define free qa_resource_free
#include "../image/gif.c"
