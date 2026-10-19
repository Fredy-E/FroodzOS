"""Portable tests for publication checksum/path/privacy gates."""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('publication_verifier', ROOT / 'tools/verify-publication.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class PublicationTests(unittest.TestCase):
    def fixture(self, files):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        records = []
        for name, value in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
            records.append(hashlib.sha256(value).hexdigest() + '  ' + name)
        (root / 'SHA256SUMS').write_bytes(('\n'.join(records) + '\n').encode('ascii'))
        return root

    def test_fresh_tree_without_git(self):
        self.assertEqual(MOD.verify(self.fixture({'README.md': b'hello\n'}))['files_verified'], 1)

    def test_changed_bytes_refused(self):
        root = self.fixture({'file': b'one'})
        (root / 'file').write_bytes(b'two')
        with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
            MOD.verify(root)

    def test_missing_file_refused(self):
        root = self.fixture({'file': b'one'})
        (root / 'file').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing file'):
            MOD.verify(root)

    def test_unlisted_file_refused(self):
        root = self.fixture({'file': b'one'})
        (root / 'extra').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'Unlisted file'):
            MOD.verify(root)

    def test_private_key_refused_even_with_valid_hash(self):
        with self.assertRaisesRegex(ValueError, 'Forbidden private/binary'):
            MOD.verify(self.fixture({'example.key': b'fictional test placeholder'}))

    def test_binary_image_refused_even_with_valid_hash(self):
        with self.assertRaisesRegex(ValueError, 'Forbidden private/binary'):
            MOD.verify(self.fixture({'example.efi': b'fictional test placeholder'}))

    def test_compressed_archive_refused_even_with_valid_hash(self):
        with self.assertRaisesRegex(ValueError, 'Forbidden private/binary'):
            MOD.verify(self.fixture({'example.tar.gz': b'fictional test placeholder'}))

    def test_zip_refused_even_with_valid_hash(self):
        with self.assertRaisesRegex(ValueError, 'Forbidden private/binary'):
            MOD.verify(self.fixture({'example.zip': b'fictional test placeholder'}))

    def test_invalid_digest_not_repaired(self):
        with self.assertRaisesRegex(ValueError, 'Malformed'):
            MOD.checksum_entries('not-a-sha256  file\n')

    def test_traversal_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            MOD.checksum_entries('a' * 64 + '  ../escape\n')

    def test_duplicate_refused(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            MOD.checksum_entries(('a' * 64 + '  file\n') * 2)

    def test_crlf_checksum_refused(self):
        root = self.fixture({'file': b'one'})
        sums = root / 'SHA256SUMS'
        sums.write_bytes(sums.read_bytes().replace(b'\n', b'\r\n'))
        with self.assertRaisesRegex(ValueError, 'LF'):
            MOD.verify(root)

if __name__ == '__main__':
    unittest.main()
