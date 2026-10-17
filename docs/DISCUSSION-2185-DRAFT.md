# Published response to ELKS discussion #2185

Published: [Graphical Web browser — ELKSWeb 0.1 announcement](https://github.com/ghaerr/elks/discussions/2185#discussioncomment-18987882).

---

This issue inspired me to start looking into a web browser for ELKS and, with the help of some coding apps, I came up with this beta: **ELKSWeb 0.1**.

It takes inspiration from MicroWeb, but is written in C using the native ELKS toolchain, with 8088-compatible machines in mind. For networking, it uses ELKS's own **`ktcp` implementation** through the native socket interfaces.

I have been trying it out on my HP 200LX systems as well as in emulators, and it has been fun seeing pages like 68k.news running on them. It is still an early beta, with plenty of limitations, but basic HTTP browsing and GIF images are working. Here is 68k.news in ELKSWeb 0.1, captured in QEMU:

![ELKSWeb 0.1 displaying 68k.news in QEMU](https://raw.githubusercontent.com/l00nix/ELKSWeb/main/docs/screenshots/68k-news-0.1-qemu.png)

Here is my [FrogFind mirror](http://frogfind.8088retro.com/) in ELKSWeb 0.1, showing the homepage with its frog GIF. This was captured in QEMU.

![FrogFind mirror homepage and frog GIF in ELKSWeb 0.1](https://raw.githubusercontent.com/l00nix/ELKSWeb/main/docs/screenshots/frogfind-0.1-qemu.png)

The downloads, installation instructions, known limitations and more technical details are on GitHub: **[ELKSWeb](https://github.com/l00nix/ELKSWeb)**.

I would really welcome testers and feedback, along with any feature requests. I will not promise every idea will be feasible given the memory, hardware and other limitations we are working with, but I would love to hear what people would find useful.
