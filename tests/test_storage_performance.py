"""Storage correctness and bounded operation counts, using actual memory.c.

The temporary copy adds counters to the existing far-string comparison loop;
production storage/control flow is otherwise unchanged. No timing assertion or
claim about emulated 8088 elapsed time is made.
"""
import ctypes as C
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def fingerprint(value):
    result = 0
    for byte in value:
        result = ((result * 33) ^ byte) & 65535
    return result


class StoragePerformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='elksweb-storage-')
        directory = pathlib.Path(cls.temp.name)
        source = (ROOT / 'src/memory.c').read_text()
        loop = 'while (*p && *p == *q)'
        assert source.count(loop) == 1
        source = source.replace(loop, 'while ((++qa_comparisons, *p) && *p == *q)')
        (directory / 'memory-instrumented.c').write_text(source)
        (directory / 'probe.c').write_text(r'''
#include "elksweb.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>
struct ew_document ew_doc;
static unsigned long qa_comparisons, qa_seeks, qa_reads;
static int counted_seek(FILE *f, long p, int whence) {
  ++qa_seeks;
  return fseek(f,p,whence);
}
static size_t counted_read(void *p,size_t size,size_t n,FILE *f) {
  ++qa_reads;
  return fread(p,size,n,f);
}
#define fseek counted_seek
#define fread counted_read
#include "memory-instrumented.c"
void qa_counters_reset(void) { qa_comparisons=qa_seeks=qa_reads=0; }
unsigned long qa_compare_count(void) { return qa_comparisons; }
unsigned long qa_seek_count(void) { return qa_seeks; }
unsigned long qa_read_count(void) { return qa_reads; }
uintptr_t qa_store(const char *s,int link) {
  const char *p=ew_store_url(s);
  if (p && link && ew_doc.link_count<EW_LINKS)
    ew_doc.links[ew_doc.link_count++].url=p;
  return (uintptr_t)p;
}
void qa_control(void) {
  if (ew_doc.link_count<EW_LINKS) ew_doc.links[ew_doc.link_count++].url=NULL;
}
int qa_spool(const unsigned char *bytes,unsigned long n) {
  unsigned long i;
  if (ew_source_begin()) return -1;
  for (i=0;i<n;++i) if (ew_source_put(i,bytes[i])) return -1;
  return ew_source_finish(n);
}
''')
        library = directory / 'storage.dylib'
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-I'+str(ROOT/'src'), str(directory/'probe.c'), '-o', str(library)],
                       check=True, capture_output=True)
        cls.lib = C.CDLL(str(library))
        cls.lib.qa_store.argtypes = [C.c_char_p, C.c_int]
        cls.lib.qa_store.restype = C.c_size_t
        cls.lib.qa_spool.argtypes = [C.c_void_p, C.c_ulong]
        cls.lib.ew_source_byte.argtypes = [C.c_uint32]
        cls.lib.ew_source_byte.restype = C.c_ubyte
        for name in ('compare', 'seek', 'read'):
            getattr(cls.lib, 'qa_'+name+'_count').restype = C.c_ulong
        cls.lib.ew_source_error.restype = C.c_char_p

    @classmethod
    def tearDownClass(cls):
        cls.lib.ew_source_free()
        cls.temp.cleanup()

    def setUp(self):
        self.lib.ew_source_free()
        self.assertEqual(self.lib.ew_document_reset(), 0)
        self.lib.qa_counters_reset()

    def test_long_common_prefix_avoids_quadratic_far_comparison(self):
        prefix = b'http://news.invalid/article?' + b'x'*500
        urls = [prefix + str(i).encode() for i in range(234)]
        pointers = [self.lib.qa_store(url, 1) for url in urls]
        self.assertTrue(all(pointers))
        self.assertEqual(len(set(pointers)), len(urls))
        old_minimum = sum(range(len(urls))) * len(prefix)
        self.assertLess(self.lib.qa_compare_count(), old_minimum // 100)
        for url, pointer in zip(urls, pointers):
            self.assertEqual(C.string_at(pointer), url)
            self.assertEqual(self.lib.qa_store(url, 0), pointer)

    def test_hash_collision_keeps_distinct_urls(self):
        seen = {}
        for number in range(65537):
            url = b'http://host/' + str(number).encode()
            hash_value = fingerprint(url)
            if hash_value in seen:
                first, second = seen[hash_value], url
                break
            seen[hash_value] = url
        else:
            self.fail('No 16-bit collision found')
        a = self.lib.qa_store(first, 1)
        b = self.lib.qa_store(second, 1)
        self.assertNotEqual(a, b)
        self.assertGreater(self.lib.qa_compare_count(), 0)
        self.assertEqual(C.string_at(a), first)
        self.assertEqual(C.string_at(b), second)
        self.assertEqual(self.lib.qa_store(first, 0), a)
        self.assertEqual(self.lib.qa_store(second, 0), b)

    def test_links_controls_and_nonlink_storage_reset(self):
        self.lib.qa_control()
        self.lib.qa_store(b'anchor-before-link', 0)
        a = self.lib.qa_store(b'http://host/one', 1)
        self.lib.qa_store(b'option label', 0)
        self.assertEqual(self.lib.qa_store(b'http://host/one', 0), a)
        self.assertEqual(self.lib.ew_document_reset(), 0)
        b = self.lib.qa_store(b'http://host/two', 1)
        c = self.lib.qa_store(b'http://host/one', 1)
        self.assertNotEqual(b, c)
        self.assertEqual(C.string_at(c), b'http://host/one')
        self.assertEqual(self.lib.qa_store(b'http://host/two', 0), b)

    def test_sequential_spool_crosses_64k_without_refill_seeks(self):
        data = bytes(i % 251 for i in range(100104))
        self.assertEqual(self.lib.qa_spool(data, len(data)), 0)
        self.lib.qa_counters_reset()
        for offset, expected in enumerate(data):
            self.assertEqual(self.lib.ew_source_byte(offset), expected)
        self.assertEqual(self.lib.qa_seek_count(), 0)
        self.assertEqual(self.lib.qa_read_count(), (len(data)+511)//512)
        self.assertEqual(self.lib.ew_source_byte(len(data)), 0)
        self.assertEqual(self.lib.ew_source_error(), b'')

    def test_backward_lookahead_replay_short_final_block(self):
        data = bytes(i % 251 for i in range(1301))
        self.assertEqual(self.lib.qa_spool(data, len(data)), 0)
        self.lib.qa_counters_reset()
        for offset in (0, 511, 512, 511, 512, 1024, 1300, 0, 1023, 1024):
            self.assertEqual(self.lib.ew_source_byte(offset), data[offset])
        self.assertEqual(self.lib.qa_seek_count(), 2)
        self.assertEqual(self.lib.ew_source_error(), b'')
        replacement = b'new document'
        self.assertEqual(self.lib.qa_spool(replacement, len(replacement)), 0)
        self.lib.qa_counters_reset()
        for offset, expected in enumerate(replacement):
            self.assertEqual(self.lib.ew_source_byte(offset), expected)
        self.assertEqual(self.lib.qa_seek_count(), 0)


if __name__ == '__main__':
    unittest.main()
