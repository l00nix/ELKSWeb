"""Safety checks for the static executable-only opcode gate."""
import importlib.util
import pathlib
import struct
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('isa_audit',pathlib.Path(__file__).with_name('isa-audit.py'))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ISAGateTests(unittest.TestCase):
    def run_audit(self,code,instructions,padding=None):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            # Real ELF32 headers with executable .text and non-executable .data.
            names=b'\0.text\0.data\0.shstrtab\0'
            shoff=52
            content=52+4*40
            head=struct.pack('<16sHHIIIIIHHHHHH',b'\x7fELF\x01\x01'+b'\0'*10,
                             2,3,1,0x10000,0,shoff,0,52,0,0,40,4,3)
            sections=[(0,)*10,(1,1,6,0x10000,content,len(code),0,0,1,0),
                      (7,1,3,0x20000,content+len(code),2,0,0,1,0),
                      (13,3,0,0,content+len(code)+2,len(names),0,0,1,0)]
            elf=root/'app.elf'
            elf.write_bytes(head+b''.join(struct.pack('<10I',*s) for s in sections)+code+b'\x68\xc9'+names)
            app=root/'app'
            app.write_bytes(struct.pack('<IBBHIIIIHHI',0x04300301,32,0,1,len(code),16,64,0,0,0,0)+code)
            dis=root/'app.dis'
            dis.write_text('Disassembly of section .text:\n'+instructions+
                           '\nDisassembly of section .data:\n 20000: 68 c9    invalid-data\n')
            link_map=None
            if padding:
                link_map=root/'app.map'
                link_map.write_text(padding)
            return module.audit(app,elf,dis,link_map)

    def test_immediate_value_is_not_an_opcode(self):
        result=self.run_audit(b'\xb8\x68\xc9\xc3', ' 10000: b8 68 c9    mov ax,0xc968\n 10003: c3    ret')
        self.assertTrue(result['isa_static_pass'])

    def test_reject_80186_push_immediate(self):
        result=self.run_audit(b'\x68\x01\x00', ' 10000: 68 01 00    push 0x1')
        self.assertFalse(result['isa_static_pass'])
        self.assertEqual(len(result['forbidden_instructions']),1)

    def test_reject_386_prefix_after_segment_override(self):
        result=self.run_audit(b'\x26\x66\x90',' 10000: 26 66 90    es xchg eax,eax')
        self.assertFalse(result['isa_static_pass'])

    def test_uncovered_code_fails_closed(self):
        result=self.run_audit(b'\x90\xc3',' 10000: 90    nop')
        self.assertFalse(result['isa_static_pass'])
        self.assertTrue(result['ambiguities'])

    def test_linker_declared_zero_padding_is_not_an_instruction(self):
        result=self.run_audit(b'\xc3\0',' 10000: c3    ret\n 10001: 00    .byte 0x0',
                              ' ** zero fill 0x00010001 0x1\n')
        self.assertTrue(result['isa_static_pass'])
        self.assertEqual(result['code_sections']['.text']['linker_zero_padding_bytes'],1)

    def test_map_cannot_exempt_nonzero_instruction_bytes(self):
        result=self.run_audit(b'\xc3\xc9',' 10000: c3    ret\n 10001: c9    leave',
                              ' ** zero fill 0x00010001 0x1\n')
        self.assertFalse(result['isa_static_pass'])


if __name__=='__main__':unittest.main()
