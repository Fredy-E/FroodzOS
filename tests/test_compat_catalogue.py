# SPDX-License-Identifier: GPL-2.0-or-later
"""The compatibility catalogue is generated from tools/compat-catalogue.py; the committed files must match and stay well formed."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compat_catalogue', ROOT / 'tools' / 'compat-catalogue.py')
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)


class Catalogue(unittest.TestCase):
    def test_committed_files_match_generator(self):
        tsv, md = cc.render()
        self.assertEqual((ROOT / 'docs/compat/formats.tsv').read_text(encoding='utf-8'), tsv)
        self.assertEqual((ROOT / 'docs/compat/SUMMARY.md').read_text(encoding='utf-8'), md)

    def test_rows_are_well_formed_and_unique(self):
        rows = list(cc.rows())
        self.assertGreaterEqual(len(rows), 300)
        exts = [r[0] for r in rows]
        self.assertEqual(len(exts), len(set(exts)))
        for ext, cat, ceiling, phase, handlers, today, note in rows:
            self.assertEqual(ext, ext.lower())
            self.assertNotIn(' ', ext)
            self.assertIn(ceiling, cc.CEILINGS)
            self.assertIn(phase, cc.PHASES)
            self.assertIn(today, ('partial', 'no'))
            self.assertTrue(handlers and note and cat)
        # the owner's named targets must stay in the catalogue
        for must in ('zip', 'rar', 'iso', 'docx', 'xlsx', 'exe', 'apk', 'dmg'):
            self.assertIn(must, exts)

    def test_documents_quote_the_current_count(self):
        n = str(len(list(cc.rows())))
        for doc in ('README.md', 'docs/releases/UNIVERSAL-COMPATIBILITY.md'):
            text = (ROOT / doc).read_text(encoding='utf-8')
            self.assertIn('**%s extensions' % n if doc == 'README.md' else '**%s in' % n, text, doc)

    def test_infeasible_rows_never_claim_a_phase(self):
        for ext, cat, ceiling, phase, *_ in cc.rows():
            if ceiling == 'notfeasible':
                self.assertEqual(phase, 'never', ext)


if __name__ == '__main__':
    unittest.main()
