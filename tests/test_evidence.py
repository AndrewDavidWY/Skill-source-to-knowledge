import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from validate_evidence import validate
from render_brief import render


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        text = '完全合成材料\n目标是减少交接遗漏。\n尚未验证效果。\n'
        (self.root / 'source.md').write_text(text, encoding='utf-8')
        self.data = {
            'schema_version': 1, 'title': '合成试点', 'material_mode': 'synthetic-demo',
            'as_of': '2026-11-03', 'scope_note': '仅覆盖合成文本。',
            'sources': [{'id': 'S1', 'title': '计划', 'creator': '合成示例', 'source_type': '规划', 'path': 'source.md',
                         'sha256': hashlib.sha256(text.encode()).hexdigest(),
                         'document_date': '2020-01-01', 'event_date': 'unknown', 'version': 'v1',
                         'access': 'synthetic', 'reuse_basis': 'synthetic',
                         'rights_note': '原创合成内容。', 'coverage': '全部三行。'}],
            'claims': [{'id': 'C1', 'text': '资料提出减少遗漏的目标。', 'kind': 'historical-plan',
                        'publication': 'ready', 'limits': '未证明效果。',
                        'citations': [{'source_id': 'S1', 'start_line': 2, 'end_line': 3,
                                       'quote': '目标是减少交接遗漏。\n尚未验证效果。', 'relation': 'supports'}]}],
        }

    def errors(self, public=True):
        return validate(self.data, self.root, public)

    def test_valid_synthetic(self):
        self.assertEqual([], self.errors())

    def test_hash_change(self):
        (self.root / 'source.md').write_text('changed')
        self.assertTrue(any('hash mismatch' in e for e in self.errors()))

    def test_quote_mismatch(self):
        self.data['claims'][0]['citations'][0]['quote'] = '效果已经实现。'
        self.assertTrue(any('quote does not match' in e for e in self.errors()))

    def test_out_of_range(self):
        self.data['claims'][0]['citations'][0]['end_line'] = 20
        self.assertTrue(any('exceeds source' in e for e in self.errors()))

    def test_boolean_not_line_number(self):
        self.data['claims'][0]['citations'][0]['start_line'] = True
        self.assertTrue(any('invalid line range' in e for e in self.errors()))

    def test_unknown_source(self):
        self.data['claims'][0]['citations'][0]['source_id'] = 'missing'
        self.assertTrue(any('unknown source_id' in e for e in self.errors()))

    def test_duplicate_ids(self):
        self.data['sources'].append(copy.deepcopy(self.data['sources'][0]))
        self.data['claims'].append(copy.deepcopy(self.data['claims'][0]))
        errors = self.errors()
        self.assertTrue(any('duplicate source id' in e for e in errors))
        self.assertTrue(any('duplicate claim id' in e for e in errors))

    def test_duplicate_resolved_path(self):
        duplicate = copy.deepcopy(self.data['sources'][0])
        duplicate.update(id='S2', path='./source.md')
        self.data['sources'].append(duplicate)
        self.assertTrue(any('path already registered' in e for e in self.errors()))

    def test_public_restricted_and_hold(self):
        self.data['material_mode'] = 'research-draft'
        self.data['sources'][0].update(access='restricted', reuse_basis='permission')
        self.data['claims'][0]['publication'] = 'hold'
        self.assertEqual([], self.errors(public=False))
        self.assertTrue(any('public bundle' in e for e in self.errors()))
        self.assertTrue(any('held' in e for e in self.errors()))

    def test_public_access_not_reuse_permission(self):
        self.data['material_mode'] = 'research-draft'
        self.data['sources'][0].update(access='public', reuse_basis='unknown')
        self.assertTrue(any('public bundle' in e for e in self.errors()))

    def test_synthetic_source_cannot_be_mislabeled(self):
        self.data['sources'][0]['reuse_basis'] = 'permission'
        self.assertTrue(any('must agree' in e for e in self.errors()))

    def test_source_path_cannot_escape(self):
        for path in ('../source.md', '/etc/passwd'):
            self.data['sources'][0]['path'] = path
            self.assertTrue(any('inside' in e for e in self.errors()))

    def test_symlink_cannot_escape(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'outside.md'
            target.write_text('outside')
            (self.root / 'escape.md').symlink_to(target)
            self.data['sources'][0]['path'] = 'escape.md'
            self.assertTrue(any('inside' in e for e in self.errors()))

    def test_version_cycle(self):
        self.data['sources'][0]['supersedes'] = ['S1']
        self.assertTrue(any('cycle' in e for e in self.errors()))

    def test_unknown_version(self):
        self.data['sources'][0]['supersedes'] = ['missing']
        self.assertTrue(any('unknown supersedes' in e for e in self.errors()))

    def test_no_support_reference(self):
        self.data['claims'][0]['citations'][0]['relation'] = 'context'
        self.assertTrue(any('supports citation' in e for e in self.errors()))

    def test_malformed_types_return_errors(self):
        variants = [None, [], {'sources': {}}, {'schema_version': True}]
        for value in variants:
            self.assertTrue(validate(value, self.root))
        for key in ('material_mode', 'as_of'):
            changed = copy.deepcopy(self.data)
            changed[key] = []
            self.assertTrue(validate(changed, self.root))
        for key in ('id', 'path', 'access', 'reuse_basis', 'sha256', 'supersedes'):
            changed = copy.deepcopy(self.data)
            changed['sources'][0][key] = {'invalid': True}
            self.assertTrue(validate(changed, self.root))

    def test_renderer_discloses_synthetic_and_limits(self):
        output = render(self.data)
        self.assertIn('均为虚构', output)
        self.assertIn('未证明效果', output)
        self.assertIn('L2–L3', output)
        self.assertIn(self.data['sources'][0]['sha256'], output)

    def test_renderer_neutralizes_active_html(self):
        self.data['claims'][0]['text'] = '<script>alert(1)</script> [bad](https://example.invalid)'
        self.assertNotIn('<script>', render(self.data))
        self.assertNotIn('[bad](', render(self.data))

    def test_repository_pilot_and_reproducible_brief(self):
        manifest = ROOT / 'examples/synthetic-pilot/evidence.json'
        data = json.loads(manifest.read_text(encoding='utf-8'))
        self.assertEqual([], validate(data, manifest.parent, public=True))
        self.assertEqual((manifest.parent / 'traceable-brief.md').read_text(), render(data))

    def test_cli_rejects_invalid_json_without_output(self):
        manifest = self.root / 'bad.json'
        manifest.write_text('{')
        run = subprocess.run([sys.executable, str(ROOT / 'scripts/render_brief.py'), str(manifest)], capture_output=True, text=True)
        self.assertEqual(1, run.returncode)
        self.assertEqual('', run.stdout)
        self.assertIn('manifest cannot be loaded', run.stderr)

    def test_cli_success_does_not_mutate_source(self):
        manifest = self.root / 'evidence.json'
        manifest.write_text(json.dumps(self.data))
        before = (self.root / 'source.md').read_bytes()
        run = subprocess.run([sys.executable, str(ROOT / 'scripts/render_brief.py'), str(manifest), '--public'], capture_output=True, text=True)
        self.assertEqual(0, run.returncode)
        self.assertEqual(before, (self.root / 'source.md').read_bytes())
        self.assertEqual('', run.stderr)


if __name__ == '__main__':
    unittest.main()
