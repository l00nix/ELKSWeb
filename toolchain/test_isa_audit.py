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
    def run_audit(self,code,instructions,padding=None,far_code=None,far_dis='',actual_far=None):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            # Real ELF32 sections; far code belongs to the medium-model image.
            payloads=[('.text',6,0x10000,code)]
            if far_code is not None:payloads.append(('.fartext',6,0x20000,far_code))
            payloads.append(('.data',3,0x30000,b'\x68\xc9'))
            names=b'\0';indices={}
            for name in [x[0] for x in payloads]+['.shstrtab']:
                indices[name]=len(names);names+=name.encode()+b'\0'
            shnum=len(payloads)+2;content=52+shnum*40
            head=struct.pack('<16sHHIIIIIHHHHHH',b'\x7fELF\x01\x01'+b'\0'*10,
                             2,3,1,0x10000,0,52,0,52,0,0,40,shnum,shnum-1)
            sections=[(0,)*10];data=b''
            for name,flags,address,blob in payloads:
                sections.append((indices[name],1,flags,address,content+len(data),len(blob),0,0,1,0))
                data+=blob
            sections.append((indices['.shstrtab'],3,0,0,content+len(data),len(names),0,0,1,0))
            elf=root/'app.elf'
            elf.write_bytes(head+b''.join(struct.pack('<10I',*x) for x in sections)+data+names)
            app=root/'app';hlen=64 if far_code is not None else 32
            native=struct.pack('<IBBHIIIIHHI',0x04300301,hlen,0,1,len(code),16,64,0,0,0,0)
            if far_code is not None:native+=bytes(16)+struct.pack('<4I',len(far_code),0,0,0)
            native+=code
            if far_code is not None:native+=far_code if actual_far is None else actual_far
            app.write_bytes(native)
            dis=root/'app.dis'
            dis.write_text('Disassembly of section .text:\n'+instructions+
                           '\nDisassembly of section .fartext:\n'+far_dis+
                           '\nDisassembly of section .data:\n 30000: 68 c9    invalid-data\n')
            link_map=None
            if padding:
                link_map=root/'app.map';link_map.write_text(padding)
            return module.audit(app,elf,dis,link_map)

    def test_medium_payload_and_far_instruction_coverage(self):
        result=self.run_audit(b'\xc3',' 10000: c3    ret',far_code=b'\xcb',far_dis=' 20000: cb    retf')
        self.assertTrue(result['isa_static_pass'])
        self.assertEqual(result['memory']['total_text_bytes'],2)

    def test_medium_native_far_payload_must_match_elf(self):
        result=self.run_audit(b'\xc3',' 10000: c3    ret',far_code=b'\xcb',far_dis=' 20000: cb    retf',actual_far=b'\x90')
        self.assertFalse(result['isa_static_pass'])
        self.assertIn('.fartext',result['ambiguities'][0]['reason'])

    def test_medium_far_payload_rejects_80186_opcode(self):
        result=self.run_audit(b'\xc3',' 10000: c3    ret',far_code=b'\x68\x01\x00',far_dis=' 20000: 68 01 00    push 0x1')
        self.assertFalse(result['isa_static_pass'])
        self.assertEqual(result['forbidden_instructions'][0]['section'],'.fartext')

    def test_medium_far_payload_cannot_be_omitted_from_disassembly(self):
        result=self.run_audit(b'\xc3',' 10000: c3    ret',far_code=b'\xcb')
        self.assertFalse(result['isa_static_pass'])

    def test_far_jump_operand_is_not_decoded_as_instruction(self):
        result=self.run_audit(b'\xea\x68\xc9\x00\x10',' 10000: ea 68 c9 00 10    jmp 0x1000:0xc968')
        self.assertTrue(result['isa_static_pass'])

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
