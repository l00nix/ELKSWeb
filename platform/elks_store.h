/* Private backend hooks, not an ELKS ABI. SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef EW_STORE_BACKEND_H
#define EW_STORE_BACKEND_H
unsigned ew_store_ems_alloc(unsigned long bytes);
int ew_store_ems_copy(unsigned handle, unsigned long offset,
                       unsigned char *buffer, unsigned count, int write);
void ew_store_ems_free(unsigned handle);
#endif
