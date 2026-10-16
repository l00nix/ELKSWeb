#include "elksweb.h"
#include <arpa/inet.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#ifdef EW_HOST_TEST
#include <netdb.h>
#endif

extern int ew_net_progress(const char *message);
int ew_fetch_truncated;
int ew_document_type;
char ew_document_media[64];
static int response_type;
static unsigned char response_charset;
static char response_media[64];
static int fd = -1;
static int response_status;
static int fail(const char *s);
static int segmented_output;
static int spool_fd = -1;
static unsigned char spool_buffer[512];
static unsigned spool_size;
static int spool_flush(void) {
  unsigned done = 0;
  while (done < spool_size) {
    int n = write(spool_fd, spool_buffer + done, spool_size - done);
    if (n < 0 && errno == EINTR) continue;
    if (n <= 0) return fail("Cannot write image cache");
    done += n;
  }
  spool_size = 0;
  return 0;
}
static int store_byte(char EW_FAR *out, uint32_t pos, unsigned char value) {
  if (spool_fd >= 0) {
    spool_buffer[spool_size++] = value;
    if (spool_size == sizeof(spool_buffer) && spool_flush()) return -1;
  } else if (segmented_output) {
    if (ew_source_put(pos, value)) return fail(ew_source_error());
  } else out[(unsigned)pos] = value;
  return 0;
}
static unsigned char incoming[512];
static unsigned pos, have;
static time_t deadline;
static char failure[96];
static int terminate_output(char EW_FAR *out, uint32_t count) {
  /* File downloads are binary payloads; only string destinations need NUL. */
  return spool_fd >= 0 ? 0 : store_byte(out, count, 0);
}
static int fail(const char *s) {
  if (s != failure)
    strncpy(failure, s, sizeof(failure) - 1);
  failure[sizeof(failure) - 1] = 0;
  return -1;
}
static int ci_prefix(const char *a, const char *b) {
  while (*b)
    if (tolower((unsigned char)*a++) != tolower((unsigned char)*b++))
      return 0;
  return 1;
}
static int media_is(const char *value, const char *type) {
  unsigned n = strlen(type);
  return ci_prefix(value, type) &&
         (!value[n] || value[n] == ';' || value[n] == ' ' || value[n] == '\t');
}
static int content_type(const char *value) {
  if (media_is(value, "text/html") || media_is(value, "application/xhtml+xml"))
    return EW_CONTENT_HTML;
  if (media_is(value, "text/plain")) return EW_CONTENT_TEXT;
  if (media_is(value, "image/gif") || media_is(value, "image/png") ||
      media_is(value, "image/jpeg")) return EW_CONTENT_IMAGE;
  return EW_CONTENT_BINARY;
}
static int file_type(const char *path) {
  const char *extension = strrchr(path, '.');
  if (!extension) return EW_CONTENT_HTML;
  if (media_is(extension, ".txt") || media_is(extension, ".text"))
    return EW_CONTENT_TEXT;
  if (media_is(extension, ".gif") || media_is(extension, ".png") ||
      media_is(extension, ".jpg") || media_is(extension, ".jpeg"))
    return EW_CONTENT_IMAGE;
  return EW_CONTENT_HTML;
}
static int getbyte(void) {
  int n;
  fd_set reads;
  struct timeval tv;
  while (pos == have) {
    if (time(NULL) > deadline)
      return fail("Server timed out");
    if (ew_net_progress("Receiving..."))
      return fail("Loading cancelled");
    FD_ZERO(&reads);
    FD_SET(fd, &reads);
    tv.tv_sec = 0;
    tv.tv_usec = 100000;
    n = select(fd + 1, &reads, NULL, NULL, &tv);
    if (n < 0) {
      if (errno == EINTR)
        continue;
      return fail("Network read failed");
    }
    if (!n)
      continue;
    n = read(fd, incoming, sizeof(incoming));
    if (n < 0) {
      if (errno == EAGAIN || errno == EINTR)
        continue;
      return fail("Network read failed");
    }
    if (!n)
      return -2;
    pos = 0;
    have = n;
    deadline = time(NULL) + 20;
  }
  return incoming[pos++];
}
static int line(char *buf, unsigned cap) {
  unsigned n = 0;
  int c;
  while ((c = getbyte()) >= 0) {
    if (c == '\n') {
      buf[n] = 0;
      return n;
    }
    if (c != '\r') {
      if (n + 1 >= cap)
        return fail("HTTP header too long");
      buf[n++] = c;
    }
  }
  return fail(c == -2 ? "Incomplete HTTP response" : failure);
}
static int sendall(const char *s) {
  unsigned n = strlen(s);
  int k;
  while (n) {
    k = write(fd, s, n);
    if (k < 0 && errno == EINTR)
      continue;
    if (k <= 0)
      return fail("Cannot send HTTP request");
    s += k;
    n -= k;
  }
  return 0;
}
int ew_host_is_ipv4(const char *host) {
  unsigned part;
  for (part = 0; part < 4; ++part) {
    unsigned value = 0, digits = 0;
    while (*host >= '0' && *host <= '9') {
      if (++digits > 3)
        return 0;
      value = value * 10 + *host++ - '0';
    }
    if (!digits || value > 255)
      return 0;
    if (part == 3)
      return *host == 0;
    if (*host++ != '.')
      return 0;
  }
  return 0;
}
static int connecthost(const char *host, unsigned port) {
  struct sockaddr_in sa;
  unsigned long address;
#ifdef EW_HOST_TEST
  struct hostent *he = gethostbyname(host);
  if (!he)
    return fail("Host name not found");
  memcpy(&address, he->h_addr, 4);
#else
  /* ELKS in_gethostbyname assumes every digit-leading name is an address.
   * Names such as 68k.news must reach DNS rather than its permissive in_aton.
   * Preserve /etc/hosts lookup for ordinary names and strict IPv4 literals.
   */
  address = isdigit((unsigned char)host[0]) && !ew_host_is_ipv4(host)
                ? in_resolv(host, NULL, NULL)
                : in_gethostbyname(host);
  if (!address)
    return fail("Host name not found");
#endif
  fd = socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0)
    return fail("Network unavailable: start ELKS net first");
  memset(&sa, 0, sizeof(sa));
  sa.sin_family = AF_INET;
  sa.sin_port = 0;
  sa.sin_addr.s_addr = INADDR_ANY;
  if (bind(fd, (struct sockaddr *)&sa, sizeof(sa)) < 0)
    return fail("Cannot bind socket");
  sa.sin_port = htons(port);
  sa.sin_addr.s_addr = address;
#ifdef EW_HOST_TEST
  if (connect(fd, (struct sockaddr *)&sa, sizeof(sa)) < 0)
    return fail("Connection failed");
#else
  if (in_connect(fd, (struct sockaddr *)&sa, sizeof(sa), 10) < 0)
    return fail("Connection failed or timed out");
#endif
  return 0;
}
static int32_t request(const char *url, char EW_FAR *out, uint32_t cap, char *location,
                   unsigned lc, const char *post) {
  static char host[96], path[EW_URL], header[EW_URL + 128], target[EW_URL];
  const char *p, *e, *proxy;
  unsigned n, port = 80;
  uint32_t count = 0;
  long length = -1, chunk = 0;
  int chunked = 0, status, c;
  failure[0] = 0;
  location[0] = 0;
  response_type = EW_CONTENT_HTML;
  response_charset = EW_CHARSET_UTF8;
  strcpy(response_media, "text/html");
  pos = have = 0;
  if (!ci_prefix(url, "http://"))
    return fail(ci_prefix(url, "https://")
                    ? "HTTPS requires an HTTP proxy service"
                    : "Unsupported URL protocol");
  p = url + 7;
  e = p;
  while (*e && *e != '/' && *e != ':' && *e != '?' && *e != '#')
    e++;
  n = e - p;
  if (!n || n >= sizeof(host))
    return fail("Invalid host name");
  memcpy(host, p, n);
  host[n] = 0;
  if (*e == ':') {
    char *q;
    long pp = strtol(e + 1, &q, 10);
    if (q == e + 1 || pp < 1 || pp > 65535)
      return fail("Invalid port");
    port = (unsigned)pp;
    e = q;
  }
  if (*e == '?') {
    path[0] = '/';
    if (strlen(e) + 2 > sizeof(path))
      return fail("URL too long");
    strcpy(path + 1, e);
  } else {
    if (strlen(e) >= sizeof(path))
      return fail("URL too long");
    strcpy(path, *e ? e : "/");
  }
  p = strchr(path, '#');
  if (p)
    path[p - path] = 0;
  if (!path[0])
    strcpy(path, "/");
  strcpy(target, path);
  proxy = getenv("HTTP_PROXY");
  if (proxy && *proxy) {
    if (ci_prefix(proxy, "http://"))
      proxy += 7;
    p = strchr(proxy, ':');
    n = p ? (unsigned)(p - proxy) : strlen(proxy);
    if (!n || n >= sizeof(host))
      return fail("Invalid HTTP_PROXY");
    memcpy(host, proxy, n);
    host[n] = 0;
    port = p ? (unsigned)atoi(p + 1) : 80;
    if (!port)
      return fail("Invalid proxy port");
    strcpy(target, url);
    {
      char *fragment = strchr(target, '#');
      if (fragment)
        *fragment = 0;
    }
  }
  if (ew_net_progress("Connecting..."))
    return fail("Loading cancelled");
  if (connecthost(host, port))
    return -1;
  snprintf(header, sizeof(header), "%s %s HTTP/1.0\r\n", post ? "POST" : "GET",
           target);
  if (sendall(header))
    return -1;
  p = url + 7;
  e = p;
  while (*e && *e != '/' && *e != '?' && *e != '#')
    e++;
  n = e - p;
  if (n + 9 >= sizeof(header))
    return fail("Host header too long");
  memcpy(header, "Host: ", 6);
  memcpy(header + 6, p, n);
  strcpy(header + 6 + n, "\r\n");
  if (sendall(header))
    return -1;
  if (sendall("User-Agent: ELKSWeb/0.1\r\nAccept: "
              "text/html,image/gif,*/*\r\nConnection: close\r\n"))
    return -1;
  if (post) {
    snprintf(header, sizeof(header),
             "Content-Type: "
             "application/x-www-form-urlencoded\r\nContent-Length: %u\r\n",
             (unsigned)strlen(post));
    if (sendall(header))
      return -1;
  }
  if (sendall("\r\n") || (post && sendall(post)))
    return -1;
  deadline = time(NULL) + 20;
  if (line(header, sizeof(header)) < 0)
    return -1;
  if (strncmp(header, "HTTP/", 5) || !(p = strchr(header, ' ')))
    return fail("Invalid HTTP response");
  if (!isdigit((unsigned char)p[1]) || !isdigit((unsigned char)p[2]) ||
      !isdigit((unsigned char)p[3]) || (p[4] && p[4] != ' '))
    return fail("Invalid HTTP status");
  status = atoi(p + 1);
  response_status = status;
  while ((c = line(header, sizeof(header))) > 0) {
    p = strchr(header, ':');
    if (!p)
      continue;
    p++;
    while (*p == ' ' || *p == '\t')
      p++;
    if (ci_prefix(header, "Content-Length:")) {
      char *end;
      long parsed;
      if (!isdigit((unsigned char)*p))
        return fail("Invalid content length");
      errno = 0;
      parsed = strtol(p, &end, 10);
      while (*end == ' ' || *end == '\t')
        end++;
      if (errno || *end || parsed < 0)
        return fail("Invalid content length");
      if (length >= 0 && length != parsed)
        return fail("Conflicting content lengths");
      length = parsed;
    }
    if (ci_prefix(header, "Transfer-Encoding:") && ci_prefix(p, "chunked"))
      chunked = 1;
    if (ci_prefix(header, "Content-Type:")) {
      int charset = ew_charset_parameter(p);
      response_charset = charset < 0 ? EW_CHARSET_UTF8 : charset;
      response_type = content_type(p);
      strncpy(response_media, p, sizeof(response_media) - 1);
      response_media[sizeof(response_media) - 1] = 0;
    }
    if (ci_prefix(header, "Location:")) {
      if (strlen(p) >= lc)
        return fail("Redirect URL too long");
      strcpy(location, p);
    }
  }
  if (c < 0)
    return -1;
  if (status >= 300 && status < 400 && location[0])
    return 0;
  if (status < 200 || status > 599) {
    snprintf(failure, sizeof(failure), "HTTP error %d", status);
    return -1;
  }
  if (status == 204) {
    if (terminate_output(out, 0)) return -1;
    return 0;
  }
  if (chunked)
    length = -1; /* Transfer-Encoding overrides Content-Length. */
  if (segmented_output && response_type == EW_CONTENT_BINARY)
    cap = 0x7ffffffeUL; /* Downloads stream to disk, never the HTML buffers. */
  while (length != 0) {
    if (chunked && chunk == 0) {
      if (line(header, sizeof(header)) < 0)
        return -1;
      {
        char *q;
        errno = 0;
        chunk = strtol(header, &q, 16);
        if (!isxdigit((unsigned char)header[0]) || q == header ||
            (*q && *q != ';') || errno || chunk < 0)
          return fail("Invalid chunk length");
      }
      if (!chunk)
        break;
    }
    c = getbyte();
    if (c < 0) {
      if (c == -2 && length < 0 && !chunked)
        break;
      return fail(c == -2 ? "Incomplete HTTP body" : failure);
    }
    if (count + 1 >= cap) {
      ew_fetch_truncated = 1;
      break;
    }
    if (store_byte(out, count++, c)) return -1;
    if (length > 0)
      length--;
    if (chunked && !--chunk) {
      if (getbyte() != '\r' || getbyte() != '\n')
        return fail("Invalid chunk boundary");
    }
  }
  if (terminate_output(out, count)) return -1;
  return count;
}
static int32_t fetch(const char *url, char EW_FAR *out, uint32_t cap, char *final_url,
             char *error, unsigned ec, const char *post) {
  static char current[EW_URL], location[EW_URL], next[EW_URL];
  unsigned hops = 0;
  uint32_t n;
  int32_t result = -1;
  FILE *f;
  const char *path;
  ew_fetch_truncated = 0;
  response_type = EW_CONTENT_HTML;
  response_charset = EW_CHARSET_UTF8;
  strcpy(response_media, "text/html");
  failure[0] = 0;
  if (!ec || !cap || (!out && !segmented_output && spool_fd < 0))
    return -1;
  error[0] = 0;
  for (path = url; *path; ++path)
    if ((unsigned char)*path < 32 || *path == 127) {
      strncpy(error, "Invalid control character in URL", ec - 1);
      error[ec - 1] = 0;
      return -1;
    }
  if (strlen(url) >= sizeof(current)) {
    strncpy(error, "URL too long", ec - 1);
    error[ec - 1] = 0;
    return -1;
  }
  strcpy(current, url);
  while (1) {
    if (!ew_url_scheme(current) || ci_prefix(current, "file:")) {
      path = current;
      if (ci_prefix(path, "file://"))
        path += 7;
      else if (ci_prefix(path, "file:"))
        path += 5;
      strcpy(next, path);
      {
        char *fragment = strchr(next, '#');
        if (fragment)
          *fragment = 0;
      }
      f = fopen(next, "rb");
      if (!f) {
        fail("Cannot open local file");
        break;
      }
      response_type = file_type(next);
      response_charset = EW_CHARSET_UTF8;
      strcpy(response_media, response_type == EW_CONTENT_TEXT ? "text/plain" :
                               response_type == EW_CONTENT_IMAGE ? "image" : "text/html");
      n = 0;
      while (n < cap - 1) {
        unsigned want, got, i;
        uint32_t remaining = cap - 1 - n;
        want = remaining > sizeof(incoming) ? sizeof(incoming) : (unsigned)remaining;
        /* ELKS stdio operates on near buffers. Copy each bounded read to
         * the source segment without passing a far pointer to libc.
         */
        got = fread(incoming, 1, want, f);
        for (i = 0; i < got; ++i) {
          if (store_byte(out, n++, incoming[i])) { fclose(f); goto done; }
        }
        if (got < want)
          break;
      }
      if (ferror(f)) {
        fclose(f);
        fail("Cannot read local file");
        break;
      }
      ew_fetch_truncated = fgetc(f) != EOF;
      fclose(f);
      if (terminate_output(out, n)) break;
      result = n;
      break;
    }
    result = request(current, out, cap, location, sizeof(location), post);
    if (fd >= 0) {
      close(fd);
      fd = -1;
    }
    if (result < 0)
      break;
    if (!location[0] || response_status < 300 || response_status >= 400)
      break;
    if (++hops > 5) {
      result = fail("Too many redirects");
      break;
    }
    if (ew_resolve_url(current, location, next, sizeof(next))) {
      result = fail("Redirect URL too long");
      break;
    }
    strcpy(current, next);
    if (response_status != 307 && response_status != 308)
      post = NULL;
  }
done:
  if (result < 0) {
    strncpy(error, failure, ec - 1);
    error[ec - 1] = 0;
  } else
    strcpy(final_url, current);
  return result;
}

int32_t ew_fetch(const char *url, char EW_FAR *out, unsigned cap, char *final_url,
                 char *error, unsigned ec, const char *post) {
  segmented_output = 0;
  return fetch(url, out, cap, final_url, error, ec, post);
}
int32_t ew_fetch_document(const char *url, char *final_url, char *error,
                          unsigned ec, const char *post) {
  int32_t size;
  if (ew_source_begin()) {
    if (ec) { strncpy(error, ew_source_error(), ec - 1); error[ec-1] = 0; }
    return -1;
  }
  segmented_output = 1;
  size = fetch(url, NULL, EW_DOCUMENT_SOURCE, final_url, error, ec, post);
  segmented_output = 0;
  if (size >= 0 && ew_source_finish((uint32_t)size)) {
    if (ec) { strncpy(error, ew_source_error(), ec - 1); error[ec-1] = 0; }
    size = -1;
  }
  if (size < 0) ew_source_abort();
  else {
    ew_document_type = response_type;
    ew_document_charset = response_charset;
    strcpy(ew_document_media, response_media);
  }
  return size;
}

int32_t ew_fetch_to_fd(const char *url, int output_fd, uint32_t cap,
                       char *final_url, char *error, unsigned ec) {
  int32_t size;
  if (output_fd < 0) return -1;
  segmented_output = 0;
  spool_fd = output_fd;
  spool_size = 0;
  size = fetch(url, NULL, cap, final_url, error, ec, NULL);
  if (size >= 0 && spool_flush()) {
    size = -1;
    if (ec) { strncpy(error, failure, ec - 1); error[ec - 1] = 0; }
  }
  spool_fd = -1;
  spool_size = 0;
  return size;
}
