# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only release identity checks. Fixtures never qualify/release an OS."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / 'tools/validate_release.py'
FILES = ('docs/releases/CODENAMES.md', 'release/codenames.json',
         'release/current.json', 'release/boards/lenovo-83n3.json')
EXPECTED = (('0.1','Maverick'),('0.2','Chaffee'),('0.3','Hellcat'),('0.4','Viper'),
    ('0.5','Raptor'),('0.6','Pershing'),('0.7','Apache'),('0.8','Wolverine'),
    ('0.9','Nighthawk'),('1.0','Sherman'),('1.1','Mustang'),('1.2','Bulldog'),
    ('1.3','Corsair'),('1.4','Phantom'),('1.5','Super Sherman'),('2.0','Abrams'),
    ('2.1','Thunderbolt'),('2.2','Bradley'),('2.3','Stryker'),('2.4','Paladin'),
    ('3.0','Blackbird'),('3.1','Spectre'),('3.2','Hornet'),('3.3','Valkyrie'),('4.0','Banshee'))

class ReleaseIdentity(unittest.TestCase):
    def setUp(self):
        self.assertTrue(VALIDATOR.is_file(), 'release validator is not implemented yet')
        self.mod = types.ModuleType('release_validator_checked')
        self.mod.__file__ = str(VALIDATOR)
        exec(compile(VALIDATOR.read_bytes(), str(VALIDATOR), 'exec'), self.mod.__dict__)
        base = Path(os.environ['TMPDIR']) if os.name == 'nt' else Path.home()/'.cache/froodz-release-tests'
        base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='release-inert-', dir=base)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in FILES:
            target = self.root/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT/name).read_bytes())
        self.catalog = json.loads((self.root/FILES[1]).read_bytes())
        self.current = json.loads((self.root/FILES[2]).read_bytes())
        self.board = json.loads((self.root/FILES[3]).read_bytes())

    def save(self, name, value):
        (self.root/name).write_text(json.dumps(value, ensure_ascii=False)+'\n', encoding='utf-8')

    def rejects(self):
        with self.assertRaises(self.mod.ValidationError): self.mod.validate(self.root)

    def test_actual_repository_metadata_is_consistent_not_qualified(self):
        result = self.mod.validate(ROOT)
        self.assertEqual(25, result['codename_count'])
        self.assertEqual('0.1.0-dev', result['product_version'])
        self.assertIs(False, result['release_authorized'])
        self.assertEqual('DEVELOPMENT_METADATA_ONLY', result['scope'])

    def test_all_25_exact_selected_pairings(self):
        self.mod.validate(self.root)
        self.assertEqual(EXPECTED, tuple((row['series'],row['codename']) for row in self.catalog['entries']))
        for version, name in EXPECTED:
            with self.subTest(version=version):
                self.assertEqual(name, self.mod.codename_for(version+'.0', self.catalog))

    def test_patch_keeps_selected_codename(self):
        for value,name in [('1.0.7','Sherman'),('1.5.1','Super Sherman'),('2.0.9','Abrams'),
                           ('0.1.1-alpha.1','Maverick'),('0.9.0-rc.2','Nighthawk')]:
            with self.subTest(value=value): self.assertEqual(name, self.mod.codename_for(value,self.catalog))

    def test_malformed_version_is_not_repaired(self):
        for value in ['1.05.0','v1.5.0',' 1.5.0','1.5.0 ','1.5','1.5.01','1.5.0-rc.0']:
            with self.subTest(value=value):
                with self.assertRaises(self.mod.ValidationError): self.mod.codename_for(value,self.catalog)

    def test_unassigned_4_1_is_refused(self):
        with self.assertRaises(self.mod.ValidationError): self.mod.codename_for('4.1.0',self.catalog)

    def test_owner_authority_byte_change_refuses(self):
        path = self.root/FILES[0]
        path.write_bytes(path.read_bytes()+b'\n')
        self.rejects()

    def test_literal_authority_digest_is_bound(self):
        self.catalog['authority_sha256'] = 'a'*61
        self.save(FILES[1],self.catalog)
        self.rejects()

    def test_arbitrary_authority_path_is_refused(self):
        self.catalog['authority_document'] = '../outside.md'
        self.save(FILES[1],self.catalog)
        self.rejects()

    def test_codename_substitution_is_refused(self):
        self.catalog['entries'][0]['codename'] = 'Changed'
        self.save(FILES[1],self.catalog)
        self.rejects()

    def test_super_sherman_cannot_be_renumbered(self):
        row = next(row for row in self.catalog['entries'] if row['codename']=='Super Sherman')
        row['series'] = '1.6'
        self.save(FILES[1],self.catalog)
        self.rejects()

    def test_missing_selected_name_is_refused(self):
        self.catalog['entries'].pop()
        self.save(FILES[1],self.catalog)
        self.rejects()

    def test_reordered_sequence_is_refused(self):
        self.catalog['entries'][0],self.catalog['entries'][1] = self.catalog['entries'][1],self.catalog['entries'][0]
        self.save(FILES[1],self.catalog)
        self.rejects()

    def test_duplicate_series_is_refused(self):
        self.catalog['entries'][1]['series'] = '0.1'
        self.save(FILES[1],self.catalog)
        self.rejects()

    def test_extra_future_name_is_refused(self):
        self.catalog['entries'].append(copy.deepcopy(self.catalog['entries'][-1]))
        self.catalog['entries'][-1]['series'] = '4.1'
        self.save(FILES[1],self.catalog)
        self.rejects()

    def test_selected_stage_is_not_changed(self):
        self.catalog['entries'][4]['intended_stage'] = 'alpha'
        self.save(FILES[1],self.catalog)
        self.rejects()

    def test_official_display_string_is_exact(self):
        self.catalog['entries'][0]['display_name'] = 'Froodz OS 0.1 Maverick'
        self.save(FILES[1],self.catalog)
        self.rejects()

    def test_super_sherman_slug_is_distinct_from_display_name(self):
        row = next(row for row in self.catalog['entries'] if row['series']=='1.5')
        self.assertEqual('Super Sherman',row['codename'])
        self.assertEqual('super-sherman',row['slug'])
        row['slug'] = 'sherman'
        self.save(FILES[1],self.catalog)
        self.rejects()

    def test_component_version_is_not_product_version(self):
        self.current['development_version'] = '1.1.2'
        self.save(FILES[2],self.current)
        self.rejects()

    def test_plain_version_cannot_claim_development(self):
        self.current['development_version'] = '0.1.0'
        self.save(FILES[2],self.current)
        self.rejects()

    def test_mismatched_current_codename_is_refused(self):
        self.current['codename'] = 'Mustang'
        self.save(FILES[2],self.current)
        self.rejects()

    def test_current_release_authority_cannot_be_true(self):
        self.current['release_authorized'] = True
        self.save(FILES[2],self.current)
        self.rejects()

    def test_integer_zero_is_not_false_authority(self):
        self.current['release_authorized'] = 0
        self.save(FILES[2],self.current)
        self.rejects()

    def test_publication_authority_cannot_be_true(self):
        self.current['publication_authorized'] = True
        self.save(FILES[2],self.current)
        self.rejects()

    def test_native_acceptance_cannot_be_invented(self):
        self.current['native_acceptance'] = True
        self.save(FILES[2],self.current)
        self.rejects()

    def test_no_qualified_release_is_fabricated(self):
        self.current['qualified_release'] = '0.1.0-alpha.1'
        self.save(FILES[2],self.current)
        self.rejects()

    def test_no_build_id_is_fabricated(self):
        self.current['build_id'] = 'invented-new-image'
        self.save(FILES[2],self.current)
        self.rejects()

    def test_unexpected_readiness_field_is_refused(self):
        self.current['stable'] = True
        self.save(FILES[2],self.current)
        self.rejects()

    def test_wrong_architecture_is_refused(self):
        self.current['architecture'] = 'x86_64'
        self.save(FILES[2],self.current)
        self.rejects()

    def test_board_cannot_be_fully_supported(self):
        self.board['support_level'] = 'fully-supported'
        self.save(FILES[3],self.board)
        self.rejects()

    def test_unaccepted_touchpad_cannot_be_marked_accepted(self):
        self.board['capabilities']['touchpad'] = 'accepted'
        self.save(FILES[3],self.board)
        self.rejects()

    def test_accepted_home_is_preserved_not_retested(self):
        self.assertEqual('accepted_different_boot',self.board['capabilities']['home_persistence'])
        self.mod.validate(self.root)

    def test_duplicate_json_key_is_refused(self):
        raw = (self.root/FILES[2]).read_bytes().replace(b'{',b'{"codename":"Changed",',1)
        (self.root/FILES[2]).write_bytes(raw)
        self.rejects()

    def test_nonstandard_json_constant_is_refused(self):
        raw = (self.root/FILES[2]).read_bytes().replace(b'null',b'NaN',1)
        (self.root/FILES[2]).write_bytes(raw)
        self.rejects()

    def test_oversized_metadata_is_refused(self):
        (self.root/FILES[1]).write_bytes(b' '*200000)
        self.rejects()

    def test_missing_metadata_is_refused(self):
        (self.root/FILES[2]).unlink()
        self.rejects()

    def test_cli_is_read_only_and_disclaims_qualification(self):
        before = {name:hashlib.sha256((self.root/name).read_bytes()).hexdigest() for name in FILES}
        out = io.StringIO()
        with mock.patch.object(sys,'stdout',out): self.assertEqual(0,self.mod.main(['--root',str(self.root)]))
        self.assertEqual('DEVELOPMENT_METADATA_ONLY',json.loads(out.getvalue())['scope'])
        self.assertEqual(before,{name:hashlib.sha256((self.root/name).read_bytes()).hexdigest() for name in FILES})

if __name__ == '__main__':
    report = Path(sys.argv[sys.argv.index('--report')+1]) if '--report' in sys.argv else None
    if report is not None and report.exists(): raise RuntimeError('new report only')
    if os.name == 'posix' and (os.getuid()!=1001 or os.geteuid()!=1001
            or os.environ.get('WSL_DISTRO_NAME')!='CachyOSBuilder'
            or os.environ.get('PATH')!='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'):
        raise RuntimeError('authorized named builder/clean PATH only')
    ids = []
    class Recording(unittest.TextTestResult):
        def startTest(self,test):
            ids.append(test.id())
            super().startTest(test)
    result = unittest.TextTestRunner(verbosity=2,resultclass=Recording).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseIdentity))
    if report:
        with report.open('x',encoding='utf-8') as handle:
            json.dump({'scope':'DEVELOPMENT_METADATA_ONLY; no runtime/hardware/release acceptance',
                'testsRun':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
                'skips':len(result.skipped),'test_ids':ids,'passed':result.wasSuccessful(),
                'python_version':sys.version,'uid':os.getuid() if hasattr(os,'getuid') else None,
                'source_files':{name:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
                    for name in (*FILES,'testing/test_release_metadata.py','tools/validate_release.py')
                    if (ROOT/name).is_file() for raw in [(ROOT/name).read_bytes()]}},handle,indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
