import json
from pathlib import Path
import tempfile
import unittest

import zstandard

import main


# StoredSeedInfo fields: data=1, signature=2, milestone=3, session country=6,
# permanent country=7, version=8. Field 20 is deliberately unknown to the patcher.
PREFIX = b'\x0a\x07payload\x12\x09signature\x18\x9b\x01'
SUFFIX = b'\x42\x0d155.0.8059.80\xa2\x01\x04keep'
ORIGINAL = PREFIX + b'\x32\x02cn\x3a\x02cn' + SUFFIX
EXPECTED = PREFIX + b'\x32\x02us\x3a\x02us' + SUFFIX


class SeedPatchingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.state = self.root / 'Local State'
        self.state.write_text(json.dumps({
            'variations_country': 'cn',
            'variations_permanent_consistency_country': ['155.0.8059.80', 'cn'],
            'profile': {'info_cache': {'Default': {'is_glic_eligible': False}}},
        }), encoding='utf-8')

    def write_seed(self, name, payload):
        path = self.root / name
        path.write_bytes(zstandard.ZstdCompressor().compress(payload))
        return path

    def patch(self):
        main.patch_local_state(str(self.root), '155.0.8059.80')

    def test_both_seeds_change_only_country_fields_and_keep_original_backups(self):
        paths = [self.write_seed(name, ORIGINAL) for name in (
            'VariationsSeedV2', 'VariationsSafeSeedV2')]
        originals = [path.read_bytes() for path in paths]
        self.patch()
        for path, original in zip(paths, originals):
            with self.subTest(name=path.name):
                self.assertEqual(zstandard.ZstdDecompressor().decompress(
                    path.read_bytes()), EXPECTED)
                self.assertEqual(Path(str(path) + '.bak').read_bytes(), original)
        state = json.loads(self.state.read_text(encoding='utf-8'))
        self.assertEqual(state['variations_country'], 'us')
        self.assertEqual(state['variations_permanent_consistency_country'],
                         ['155.0.8059.80', 'us'])
        self.assertTrue(state['profile']['info_cache']['Default']['is_glic_eligible'])
        patched = [path.read_bytes() for path in paths]
        self.patch()
        self.assertEqual([path.read_bytes() for path in paths], patched)
        self.assertEqual([Path(str(path) + '.bak').read_bytes() for path in paths],
                         originals)
        paths[0].write_bytes(zstandard.ZstdCompressor().compress(
            PREFIX + b'\x32\x02de\x3a\x02de' + SUFFIX))
        self.patch()
        self.assertEqual(zstandard.ZstdDecompressor().decompress(
            paths[0].read_bytes()), EXPECTED)
        self.assertEqual(Path(str(paths[0]) + '.bak').read_bytes(), originals[0])

    def test_missing_seed_files_keep_legacy_local_state_behavior(self):
        self.patch()
        self.assertEqual(json.loads(self.state.read_text(encoding='utf-8'))[
            'variations_country'], 'us')
        self.assertFalse((self.root / 'VariationsSeedV2').exists())
        self.assertFalse((self.root / 'VariationsSafeSeedV2').exists())

    def test_optional_missing_countries_are_added_without_changing_payload(self):
        path = self.write_seed('VariationsSeedV2', PREFIX + SUFFIX)
        self.patch()
        self.assertEqual(zstandard.ZstdDecompressor().decompress(path.read_bytes()),
                         PREFIX + SUFFIX + b'\x32\x02us\x3a\x02us')

    def test_country_length_changes_preserve_unknown_wire_fields(self):
        unknown_fields = (b'\x99\x01abcdefgh' + b'\xad\x01wxyz' +
                          b'\xb0\x01\x80\x01')
        path = self.write_seed('VariationsSeedV2',
                               PREFIX + b'\x32\x00\x3a\x03USA' + unknown_fields)
        self.patch()
        self.assertEqual(zstandard.ZstdDecompressor().decompress(path.read_bytes()),
                         PREFIX + b'\x32\x02us\x3a\x02us' + unknown_fields)

    def test_corrupt_seed_leaves_both_seeds_and_local_state_untouched(self):
        for invalid in (
                b'not zstd',
                zstandard.ZstdCompressor().compress(b'\x32\x05cn'),
                zstandard.ZstdCompressor().compress(b'\x30\x01'),
                zstandard.ZstdCompressor().compress(b'\x00'),
                zstandard.ZstdCompressor().compress(b'\x80' * 11),
                zstandard.ZstdCompressor().compress(ORIGINAL) + b'trailing data',
                zstandard.ZstdCompressor(write_content_size=False).compress(ORIGINAL)):
            with self.subTest(invalid=invalid):
                regular = self.write_seed('VariationsSeedV2', ORIGINAL)
                safe = self.root / 'VariationsSafeSeedV2'
                safe.write_bytes(invalid)
                originals = {p: p.read_bytes() for p in (regular, safe, self.state)}
                with self.assertRaises(ValueError):
                    self.patch()
                for path, original in originals.items():
                    self.assertEqual(path.read_bytes(), original)
                self.assertFalse(Path(str(regular) + '.bak').exists())


if __name__ == '__main__':
    unittest.main()
