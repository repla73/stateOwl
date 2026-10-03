from __future__ import annotations
import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
spec=importlib.util.spec_from_file_location('r2bench',ROOT/'benchmarks/r2_read_benchmark.py');bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)
class R2BenchmarkRegression(unittest.TestCase):
 def test_fixed_router_scale_and_resolution_contract(self):
  exact0=bench.run(0,'exact');exact1k=bench.run(1000,'exact');current=bench.run(1000,'current')
  self.assertEqual(exact0['ref_resolutions'],0);self.assertEqual(exact1k['ref_resolutions'],0);self.assertEqual(current['ref_resolutions'],1)
  self.assertEqual(exact0['model_visible_bytes'],exact1k['model_visible_bytes']);self.assertEqual(exact0['provider_operations'],exact1k['provider_operations'])
 def test_batch_shares_provider_work_and_growing_router_is_visible(self):
  single=bench.run(1000,'current');batch=bench.run(1000,'current',batch=True);small=bench.run(0,'exact',True);large=bench.run(250,'exact',True)
  self.assertEqual(batch['ref_resolutions'],1);self.assertEqual(batch['file_fetches'],single['file_fetches']);self.assertGreater(large['returned_bytes'],small['returned_bytes'])
if __name__=='__main__':unittest.main()
