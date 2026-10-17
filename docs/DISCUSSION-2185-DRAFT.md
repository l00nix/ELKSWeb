# Conversational draft for ELKS discussion #2185

For review only — not posted. Intended destination: [Graphical Web browser](https://github.com/ghaerr/elks/discussions/2185).

Publication note (not part of the reply): use this after the repository and release downloads are public. Confirm that the screenshot link works publicly and review the outstanding QA status before posting. The unresolved cold-boot exit anomaly remains documented in the repository; this wording does not close that gate.

---

This issue inspired me to start looking into a web browser for ELKS and, with the help of some coding apps, I came up with this beta: **ELKSWeb 0.1**.

It takes inspiration from MicroWeb, but is written in C using the native ELKS toolchain, with 8088-compatible machines in mind. For networking, it uses ELKS's own **`ktcp` implementation** through the native socket interfaces.

I've been trying it out on my HP 200LX systems as well as in emulators, and it's been fun seeing pages like 68k.news running on them. It's still an early beta, with plenty of limitations, but basic HTTP browsing and GIF images are working. Here's 68k.news in ELKSWeb 0.1, captured in QEMU:

![ELKSWeb 0.1 displaying 68k.news in QEMU](https://raw.githubusercontent.com/l00nix/ELKSWeb/main/docs/screenshots/68k-news-0.1-qemu.png)

The downloads, installation instructions, known limitations and more technical details are on GitHub: **[ELKSWeb](https://github.com/l00nix/ELKSWeb)**.

I'd really welcome testers and feedback, along with any feature requests. I can't promise every idea will be feasible given the memory, hardware and other limitations we're working with, but I'd love to hear what people would find useful.
