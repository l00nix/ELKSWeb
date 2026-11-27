/* Count resolver calls and simulate a stale cached connection. Network I/O
 * otherwise uses real loopback sockets and the production fetcher. */
#include <netdb.h>
#include <sys/socket.h>
#include <errno.h>
static unsigned qa_lookups, qa_connect_failures;
unsigned qa_dns_lookups(void) { return qa_lookups; }
void qa_dns_fail_connections(unsigned count) { qa_connect_failures = count; }
static struct hostent *qa_resolve(const char *host) {
  (void)host;
  ++qa_lookups;
  return gethostbyname("127.0.0.1");
}
static int qa_connect(int fd, const struct sockaddr *address, socklen_t size) {
  if (qa_connect_failures) {
    --qa_connect_failures;
    errno = ECONNREFUSED;
    return -1;
  }
  return connect(fd, address, size);
}
#define gethostbyname qa_resolve
#define connect qa_connect
#include "../src/net.c"
