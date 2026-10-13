import contextlib
import io
import json
import unittest
from engine.__main__ import main

class CLITests(unittest.TestCase):
    def run_cli(self,args):
        out,err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            status=main(args)
        return status,out.getvalue(),err.getvalue()

    def test_indexed_and_full_cli_agree(self):
        status,left,err=self.run_cli(['--plot','P-0003'])
        self.assertEqual(status,0)
        status,right,err=self.run_cli(['--plot','P-0003','--access','indexed'])
        self.assertEqual(status,0)
        a,b=json.loads(left),json.loads(right)
        self.assertEqual(a['source_result'],b['source_result'])
        self.assertEqual(a['source_metadata_sha256'],b['source_metadata_sha256'])
        self.assertEqual(b['access_method'],'indexed')

    def test_unknown_plot_returns_structured_error(self):
        status,out,err=self.run_cli(['--plot','P-NOT-SUPPLIED'])
        self.assertEqual(status,2)
        self.assertEqual(out,'')
        self.assertEqual(json.loads(err)['error'],'ValueError')

if __name__=='__main__':
    unittest.main()
