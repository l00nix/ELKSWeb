#!/usr/bin/env python3
"""Audit linked 16-bit code bytes and report the ELKS near-memory budget.

This is a static ISA gate, not proof of correct execution on an 8088. Only
ELF sections carrying SHF_EXECINSTR are examined; .data/.bss are excluded.
Any uncovered or ambiguously decoded byte fails closed rather than passing.
"""
import argparse
import hashlib
import json
import pathlib
import re
import struct
import sys


def elf_code(path):
    data = path.read_bytes()
    if data[:6] != b'\x7fELF\x01\x01':
        raise ValueError('Expected ELF32 little endian')
    hdr = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    shoff, shentsize, shnum, shstrndx = hdr[6], hdr[11], hdr[12], hdr[13]
    headers = [struct.unpack_from('<IIIIIIIIII', data, shoff+i*shentsize)
               for i in range(shnum)]
    names_hdr = headers[shstrndx]
    names = data[names_hdr[4]:names_hdr[4]+names_hdr[5]]
    sections = {}
    for h in headers:
        if not h[2] & 4 or h[1] == 8 or not h[5]:
            continue
        name = names[h[0]:].split(b'\0', 1)[0].decode()
        sections[name] = (h[3], data[h[4]:h[4]+h[5]])
    return sections


def memory_report(path):
    data = path.read_bytes()
    if len(data) < 32:
        raise ValueError('Truncated ELKS executable')
    magic, hlen, _, version, text, initialized, bss, entry, heap, stack, syms = \
        struct.unpack_from('<IBBHIIIIHHI', data)
    if hlen not in (32, 48, 64):
        raise ValueError('Unsupported ELKS header')
    if version != 1:
        raise ValueError('Expected ELKS version 1 heap/stack header')
    effective_heap, effective_stack = heap or 4096, stack or 4096
    total = initialized+bss+effective_heap+effective_stack
    return {
        'header_bytes': hlen, 'header_version': version,
        'text_bytes': text, 'data_bytes': initialized, 'bss_bytes': bss,
        'header_heap_bytes': heap, 'header_stack_bytes': stack,
        'effective_heap_bytes': effective_heap, 'effective_stack_bytes': effective_stack,
        'near_static_bytes': initialized+bss,
        'near_total_before_arguments_environment': total,
        'remaining_before_arguments_environment': 65520-total,
        'minimum_argument_environment_reserve': 1024,
        'memory_gate_pass': total+1024 <= 65520,
        'note': 'Zero header heap/stack fields select ELKS INIT_HEAP/INIT_STACK defaults of 4096 each. argv/envp also consume near space.'
    }


def audit(executable, elf, disassembly, link_map=None):
    sections = elf_code(elf)
    covered = {name: set() for name in sections}
    padding = {name: set() for name in sections}
    if link_map:
        for address, size in re.findall(r'^\s*\*\* zero fill\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)', link_map.read_text(), re.M):
            address, size = int(address,16), int(size,16)
            for name,(base,code) in sections.items():
                offset=address-base
                if 0<=offset and offset+size<=len(code) and code[offset:offset+size]==bytes(size):
                    padding[name].update(range(offset,offset+size))
    current = None
    bad, ambiguities = [], []
    memory = memory_report(executable)
    executable_bytes = executable.read_bytes()
    if '.text' in sections:
        actual_text = executable_bytes[memory['header_bytes']:memory['header_bytes']+memory['text_bytes']]
        if actual_text != sections['.text'][1]:
            ambiguities.append({'reason':'ELKS executable .text differs from retained linked ELF'})
    instruction_count = 0
    pattern = re.compile(r'^\s*([0-9a-f]+):\s*((?:[0-9a-f]{2}\s+)+)\s*(\S.*)$')
    for line in disassembly.read_text().splitlines():
        match = re.match(r'Disassembly of section (.+):', line)
        if match:
            current = match.group(1)
            continue
        match = pattern.match(line)
        if not match or current not in sections:
            continue
        address, raw, asm = int(match[1], 16), bytes.fromhex(match[2]), match[3]
        base, code = sections[current]
        offset = address-base
        if offset < 0 or code[offset:offset+len(raw)] != raw:
            ambiguities.append({'address':hex(address), 'reason':'disassembly does not match ELF bytes'})
            continue
        covered[current].update(range(offset, offset+len(raw)))
        if set(range(offset,offset+len(raw))).issubset(padding[current]):
            continue
        instruction_count += 1
        if '(bad)' in asm or asm.startswith(('.byte', '.word', '.long')):
            ambiguities.append({'address':hex(address), 'reason':asm})
            continue
        # Original 8086 prefixes: segment overrides, LOCK, REPNE and REP.
        index = 0
        while index < len(raw) and raw[index] in (0x26,0x2e,0x36,0x3e,0xf0,0xf2,0xf3):
            index += 1
        if index == len(raw):
            ambiguities.append({'address':hex(address), 'reason':'prefix without opcode'})
            continue
        opcode = raw[index]
        reason = None
        if 0x60 <= opcode <= 0x6f or opcode in (0x0f,0xc0,0xc1,0xc8,0xc9):
            reason = '80186-or-later opcode/prefix'
        elif opcode in (0xd6,0xf1):
            reason = 'undocumented/reserved original-8086 opcode'
        elif 0xd8 <= opcode <= 0xdf:
            reason = 'requires an x87 coprocessor'
        if reason:
            bad.append({'section':current, 'address':hex(address),
                        'bytes':raw.hex(' '), 'instruction':asm, 'reason':reason})
    coverage = {}
    for name, (_, code) in sections.items():
        missing = len(code)-len(covered[name])
        coverage[name] = {'bytes':len(code), 'decoded_bytes':len(covered[name]), 'linker_zero_padding_bytes':len(padding[name]), 'uncovered_bytes':missing}
        if missing:
            ambiguities.append({'section':name, 'reason':f'{missing} executable bytes not decoded'})
    return {
        'executable_sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),
        'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),
        'instructions':instruction_count, 'code_sections':coverage,
        'isa_static_pass':bool(sections) and not bad and not ambiguities,
        'forbidden_instructions':bad, 'ambiguities':ambiguities,
        'memory':memory, 'real_8088_execution':'not verified',
        'limits':'Linear decoding of ELF executable sections; inline data in executable sections requires manual review if rejected. Static ISA compatibility does not prove timing, BIOS compatibility or actual 8088 execution.'
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('executable',type=pathlib.Path)
    parser.add_argument('elf',type=pathlib.Path)
    parser.add_argument('disassembly',type=pathlib.Path)
    parser.add_argument('--output',type=pathlib.Path)
    parser.add_argument('--map',dest='link_map',type=pathlib.Path)
    args=parser.parse_args()
    report=audit(args.executable,args.elf,args.disassembly,args.link_map)
    rendered=json.dumps(report,indent=2)+'\n'
    if args.output:
        args.output.write_text(rendered)
        print('ISA audit: '+('PASS' if report['isa_static_pass'] else 'FAIL')+
              '; near memory '+str(report['memory']['near_total_before_arguments_environment'])+
              '/65520 before argv/env; report: '+str(args.output))
        if not report['isa_static_pass'] or not report['memory']['memory_gate_pass']:
            sys.stderr.write(rendered)
    else:sys.stdout.write(rendered)
    return 0 if report['isa_static_pass'] and report['memory']['memory_gate_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
