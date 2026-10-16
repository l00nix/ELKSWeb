#include "elksweb.h"
#include <ctype.h>
#include <string.h>

/* A scheme exists only at the start of a URI, never inside its query. */
const char *ew_url_scheme(const char *url) {
  const char *p = url;
  if (!isalpha((unsigned char)*p)) return NULL;
  ++p;
  while (isalnum((unsigned char)*p) || *p == '+' || *p == '-' || *p == '.') ++p;
  return *p == ':' ? p : NULL;
}
static const char *hierarchical_scheme(const char *url) {
  const char *p = ew_url_scheme(url);
  return p && p[1] == '/' && p[2] == '/' ? p : NULL;
}
static int copy(char *out, unsigned cap, const char *s, unsigned n) {
  if (n >= cap)
    return -1;
  memcpy(out, s, n);
  out[n] = 0;
  return 0;
}
/* Resolve references with bounded output and RFC-style dot segments. */
int ew_resolve_url(const char *base, const char *ref, char *out, unsigned cap) {
  static char tmp[EW_URL], norm[EW_URL];
  const char *scheme, *path, *end, *r;
  unsigned prefix = 0, n = 0, top = 0, i;
  unsigned short marks[64];
  if (!base)
    base = "";
  if (!*ref) {
    unsigned len = (unsigned)strcspn(base, "#");
    return copy(out, cap, base, len);
  }
  while (*ref && isspace((unsigned char)*ref))
    ref++;
  if (ew_url_scheme(ref)) {
    if (copy(tmp, sizeof(tmp), ref, strlen(ref)))
      return -1;
  } else {
    scheme = hierarchical_scheme(base);
    if (!strncmp(ref, "//", 2) && scheme) {
      prefix = (unsigned)(scheme - base) + 1;
    } else if (*ref == '#' || *ref == '?') {
      end = base + strcspn(base, *ref == '#' ? "#" : "?#");
      prefix = (unsigned)(end - base);
    } else if (*ref == '/') {
      if (scheme) {
        end = scheme + 3 + strcspn(scheme + 3, "/?#");
        prefix = (unsigned)(end - base);
      }
    } else {
      end = base + strcspn(base, "?#");
      path = end;
      while (path > base && path[-1] != '/')
        path--;
      if (scheme && path <= scheme + 3) {
        prefix = (unsigned)(end - base);
        if (prefix + 1 >= sizeof(tmp))
          return -1;
        memcpy(tmp, base, prefix);
        tmp[prefix++] = '/';
        goto append;
      }
      prefix = (unsigned)(path - base);
    }
    if (prefix >= sizeof(tmp))
      return -1;
    memcpy(tmp, base, prefix);
  append:
    if (prefix + strlen(ref) >= sizeof(tmp))
      return -1;
    strcpy(tmp + prefix, ref);
  }
  scheme = hierarchical_scheme(tmp);
  if (scheme) {
    path = scheme + 3 + strcspn(scheme + 3, "/?#");
    if (*path != '/') path = NULL;
  } else if (ew_url_scheme(tmp) && strncmp(tmp, "file:", 5)) {
    return copy(out, cap, tmp, strlen(tmp));
  } else path = tmp;
  if (!path || *ref == '#' || *ref == '?')
    return copy(out, cap, tmp, strlen(tmp));
  prefix = (unsigned)(path - tmp);
  memcpy(norm, tmp, prefix);
  n = prefix;
  if (*path == '/')
    norm[n++] = *path++;
  while (*path && *path != '?' && *path != '#') {
    r = path;
    while (*path && *path != '/' && *path != '?' && *path != '#')
      path++;
    i = (unsigned)(path - r);
    if (i == 1 && r[0] == '.') {
    } else if (i == 2 && r[0] == '.' && r[1] == '.') {
      if (top)
        n = marks[--top];
    } else if (i) {
      if (top >= 64 || n + i + 1 >= sizeof(norm))
        return -1;
      marks[top++] = n;
      memcpy(norm + n, r, i);
      n += i;
      if (*path == '/')
        norm[n++] = '/';
    }
    if (*path == '/')
      path++;
  }
  if (n + strlen(path) >= sizeof(norm))
    return -1;
  strcpy(norm + n, path);
  return copy(out, cap, norm, strlen(norm));
}
