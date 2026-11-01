"""Repository-level distribution invariants, independent of installed skills."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import skill_bundle


class DistributionContractTests(unittest.TestCase):
    def test_sources_cover_every_curated_identity_and_default_is_bounded(self):
        manifest = skill_bundle.load_manifest(ROOT / 'references/skill-sources.json')
        catalog = json.loads((ROOT / 'references/capabilities.json').read_text())
        entries = {entry['id']: entry for entry in manifest['skills']}
        self.assertTrue({card['id'] for card in catalog['entries']} <= set(entries))
        self.assertEqual(manifest['profiles']['default']['skills'], [])
        for profile in ['python_starter','r_starter','all_public']:
            self.assertTrue(manifest['profiles'][profile]['skills'])
            self.assertTrue(all(entries[sid]['status']=='verified_public' for sid in manifest['profiles'][profile]['skills']))
        for source in manifest['skills']:
            if source['status']=='verified_public':
                self.assertEqual(len(source['ref']),40)
                self.assertIn('license',source)
            else:
                self.assertTrue(source['reason'])

    def test_examples_are_results_not_silent_fitting_workflows(self):
        import csv
        with (ROOT/'examples/comparison/accepted-results.csv').open() as stream:
            rows=list(csv.DictReader(stream))
        self.assertGreaterEqual(len(rows),3)
        self.assertEqual(set(rows[0]),{'term','estimate','lower','upper','group'})
        for row in rows:
            self.assertLessEqual(float(row['lower']),float(row['estimate']))
            self.assertLessEqual(float(row['estimate']),float(row['upper']))
            self.assertTrue(row['group'])


if __name__=='__main__':
    unittest.main()
