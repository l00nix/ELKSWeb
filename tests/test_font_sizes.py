"""Real C parser font-size mapping, nesting and bounded stack behavior."""
import ctypes as C
import unittest
import test_core_regression as core

def setUpModule():core.setUpModule()
def tearDownModule():core.tearDownModule()

class FontSizes(unittest.TestCase):
 def styles(self,html):
  core.LIB.ew_parse(html,b'http://host/')
  result={}
  for i in range(core.LIB.qa_runs()):
   if core.LIB.qa_run_kind(i)==0:
    for c in C.string_at(core.LIB.qa_run_data(i),core.LIB.qa_run_length(i)):
     if c!=32:result[chr(c)]=core.LIB.qa_style(i)
  return result
 def test_sizes_one_through_seven_map_to_three_available_tiers(self):
  values=self.styles(b''.join(b'<font size="'+str(i).encode()+b'">'+str(i).encode()+b'</font>' for i in range(1,8)))
  self.assertEqual([values[str(i)]&36 for i in range(1,8)],[32,32,0,0,4,4,4])
 def test_font_five_overrides_heading_three(self):
  values=self.styles(b'<h3><font size="5">A</font>B</h3>C')
  self.assertEqual(values['A']&36,4);self.assertEqual(values['B']&36,0);self.assertEqual(values['C']&36,0)
 def test_nested_font_and_color_only_restore_prior_size(self):
  values=self.styles(b'<small>A<font size="5">B<font color="red">C</font>D</font>E</small>F')
  self.assertEqual([values[c]&36 for c in 'ABCDEF'],[32,4,4,4,32,0])
 def test_relative_sizes_clamp_and_restore(self):
  values=self.styles(b'<font size="+2">A<font size="-2">B</font>C</font>D<font size="-2">E</font>F')
  self.assertEqual([values[c]&36 for c in 'ABCDEF'],[4,32,4,0,32,0])
 def test_huge_numeric_sizes_are_bounded(self):
  values=self.styles(b'<font size="+999999999999999999999">A</font><font size="-999999999999999999999">B</font>C')
  self.assertEqual([values[c]&36 for c in 'ABC'],[4,32,0])
 def test_overflowed_size_stack_flags_limit_and_restores(self):
  values=self.styles(b'<small>'*33+b'A'+b'</small>'*33+b'B')
  self.assertTrue(core.LIB.qa_truncated());self.assertEqual(values['A']&36,32);self.assertEqual(values['B']&36,0)
 def test_small_big_nesting_does_not_leak_size(self):
  values=self.styles(b'<big>A<small>B<big>C</big>D</small>E</big>F')
  self.assertEqual([values[c]&36 for c in 'ABCDEF'],[4,32,4,32,4,0])

if __name__=='__main__':unittest.main()
