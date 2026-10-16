FrogFind local fixture for ELKSWeb

Copy index.htm, http.htm, results.htm, article.htm, images.htm and frog.gif
into /root/frog on a test image, then run:
  elksweb -video cga /root/frog/index.htm
Image and sample navigation links are relative. No PHP/network is needed
for these sample actions. External attribution links are not test actions.
The local page uses links because a file query string is currently treated
as part of its filename. http.htm has fixed sample forms, not live search.

Local HTTP test from this repository root:
  python3 -m http.server 18787 --bind 127.0.0.1 --directory tests/fixtures/frogfind
QEMU user-network guests: http://10.0.2.2:18787/http.htm

mirror.htm is the unmodified mirror homepage captured in this session.
It is provenance evidence, not an offline working search form.
index.htm/http.htm derive its layout with explicit local-fixture changes.
The unchanged GIF matches http://frogfind.8088retro.com/frog.gif and has
transparency/two animation frames. Only the first frame is expected.
PROVENANCE.json and COPYING.txt retain source, hashes and attribution.
