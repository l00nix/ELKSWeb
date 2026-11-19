/* Private image-storage prototype; not an ELKS ABI. SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef EW_STORE_H
#define EW_STORE_H
struct ew_store;
/* Opaque ownership. No window, physical address or mapping escapes here.
 * Copy buffers are near pointers; 0 succeeds, -1 rejects/fails. Allocations
 * are uninitialized. Calls are synchronous and must not be re-entered. */
struct ew_store *ew_store_alloc(unsigned long bytes);
int ew_store_write(struct ew_store *, unsigned long offset,
                   const unsigned char *buffer, unsigned count);
int ew_store_read(struct ew_store *, unsigned long offset,
                  unsigned char *buffer, unsigned count);
void ew_store_free(struct ew_store *);
#endif
