#!/usr/bin/env python3
"""Private-audit contract and CLI regressions; these do not simulate LLM judgement."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from dedup_fixture import complete_dedup

ROOT = Path(__file__).resolve().parents[1]
KAI_PATH = ROOT / 'skills/kai-research/scripts/kai_prepare.py'
COLE_PATH = ROOT / 'skills/cole-varify/scripts/cole_varify.py'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


kai = module('kai_private_test', KAI_PATH)
cole = module('cole_private_test', COLE_PATH)


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def cli(script, *args):
    return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True)


def details(kind='trust-risk'):
    return dict(review_type=kind, scenario='An operator sets an unbounded fee affecting existing positions.',
                applicability='The setter applies to pending withdrawals.',
                existing_controls='The setter requires the fee-manager role; no range check is present.',
                recommendation='Bound the fee and preserve already accepted withdrawal terms.',
                tradeoffs='Versioning terms increases settlement complexity.', missing_context=[])


def hypothesis(kind='trust-risk', ident='KAI-02-001'):
    return dict(id=ident, title='Fee setter protection gap', claim='Fee changes affect pending withdrawals.',
                category='access-control', confidence='medium',
                evidence=[dict(file='src/Vault.sol', start_line=1, end_line=8)],
                jay_refs=dict(node_ids=[], edge_ids=[]),
                why_might_be_real='Read setter and settlement together.',
                why_might_be_false_positive='A deployment-level controller may constrain inputs.',
                next_validation_steps=['Verify the deployed fee controller.'], **details(kind))


def payload(items, version='2.0.0'):
    return dict(schema_version=version, run_id='private-test', agent_id=2, agent_name='access-control', hypotheses=items)


def judge(kind='trust-risk', classification='Info', ident='finding-001'):
    return dict(schema_version='2.0.0', candidate_id=ident, review_status='complete',
                title='Fee setter protection gap', finding_summary='A specific parameter guard is missing.',
                classification=classification, verdict=classification,
                required_conditions=[dict(condition='A fee manager can set the value.', status='depend on role' if kind == 'trust-risk' else 'true', evidence='src/Vault.sol:2')],
                reachability='The authorized operator can execute the setter.', code_reality='The setter has no range check.',
                protocol_semantics='Pending request terms should remain stable.', impact='Existing user terms can change.',
                poc=cole.empty_poc(), **details(kind))


def pending(ident='finding-001'):
    result = judge(ident=ident)
    for key in ('classification', 'verdict'):
        result.pop(key)
    result.update(review_status='needs_context', missing_context=[dict(question='Does the deployed controller constrain the fee?', required_evidence='Controller source and deployment address at the audit block.')])
    return result


class KaiPrivateTests(unittest.TestCase):
    def test_v2_types_and_legacy(self):
        for kind in sorted(kai.REVIEW_TYPES):
            with self.subTest(kind=kind):
                data = payload([hypothesis(kind)])
                self.assertEqual([], kai.validate_hypotheses(data))
                self.assertEqual([], cole.validate_kai_hypotheses(data, Path('fixture.json')))
        old = hypothesis('vulnerability')
        for key in (*kai.REVIEW_TEXT_FIELDS, 'review_type', 'missing_context'):
            old.pop(key)
        old['attack_sketch'] = 'An ordinary user bypasses the caller check and withdraws.'
        self.assertEqual([], kai.validate_hypotheses(payload([old], '1.0.0')))
        self.assertEqual([], cole.validate_kai_hypotheses(payload([old], '1.0.0'), Path('old.json')))

    def test_invalid_v2_fields(self):
        mutations = [dict(review_type='generic'), dict(review_type=[]), dict(scenario=''),
                     dict(missing_context=[dict(question='Which controller?')]), dict(verdict='Info'),
                     dict(classification='Info'), dict(evidence=[]),
                     dict(evidence=[dict(file='src/Vault.sol', start_line='ten', end_line=20)])]
        for changes in mutations:
            with self.subTest(changes=changes):
                data = payload([{**hypothesis(), **changes}])
                self.assertTrue(kai.validate_hypotheses(data))
                self.assertTrue(cole.validate_kai_hypotheses(data, Path('bad.json')))
        self.assertTrue(kai.validate_hypotheses([]))

    def test_context_index_and_all_bundles(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / 'src').mkdir()
            (root / 'src/Vault.sol').write_text('pragma solidity ^0.8.20; contract Vault { uint public fee; function setFee(uint x) external { fee=x; } }')
            supporting = ['README.md', 'docs/design.md', 'tests/withdraw.t.sol', 'script/deploy.s.sol', 'config/roles.json', 'foundry.toml']
            for name in supporting:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{}' if name.endswith('.json') else '# Audit fixture\n')
            (root / 'node_modules/pkg').mkdir(parents=True)
            (root / 'node_modules/pkg/README.md').write_text('dependency')
            (root / 'docs/external.md').symlink_to(root / 'README.md')
            context = root.parent / (root.name + '-context.txt')
            try:
                context.write_text('Client-stated: fee controller is a multisig; verify custody.')
                result = cli(KAI_PATH, 'prepare', root, '--run-id', 'private-test', '--context', context, '--files', 'src/Vault.sol')
                self.assertEqual(0, result.returncode, result.stderr)
                run = root / 'MasterWu/Kai/runs/private-test'
                manifest = json.loads((run / 'spawn-manifest.json').read_text())
                self.assertEqual('2.0.0', manifest['schema_version'])
                self.assertEqual(['src/Vault.sol'], manifest['scope_files'])
                self.assertEqual(sorted(supporting), manifest['audit_context']['supporting_files'])
                self.assertEqual(12, len(manifest['agents']))
                snapshot = json.loads((run / 'audit-context.json').read_text())
                context.write_text('Changed after preparation')
                self.assertIn('Client-stated', snapshot['client_context']['text'])
                for agent in manifest['agents']:
                    bundle = Path(agent['bundle_path']).read_text()
                    self.assertIn(snapshot['client_context']['text'], bundle)
                    self.assertIn('tests/withdraw.t.sol', bundle)
                    self.assertNotIn('Changed after preparation', bundle)
                jay = json.loads((root / 'MasterWu/Jay/jay-logic.json').read_text())
                self.assertEqual('1.0.0', jay['schema_version'])
                self.assertEqual(snapshot, manifest['audit_context'])
            finally:
                context.unlink(missing_ok=True)
            failure = cli(KAI_PATH, 'prepare', root, '--run-id', 'bad-context', '--context', 'missing.txt')
            self.assertNotEqual(0, failure.returncode)
            self.assertFalse((root / 'MasterWu/Kai/runs/bad-context').exists())


class ColePrivateTests(unittest.TestCase):
    def test_classification_gates(self):
        # Structured evidence gates: proving semantic truth remains the Judge's job.
        for name in ('fund loss', 'admin permission bypass', 'market stress without profit'):
            item = judge('vulnerability', 'High')
            item['title'] = name
            self.assertEqual([], cole.validate_judge_result(item, 'finding-001'))
        for kind in ('trust-risk', 'design-risk', 'hardening', 'engineering-quality'):
            self.assertEqual([], cole.validate_judge_result(judge(kind), 'finding-001'))
            inflated = judge(kind, 'Medium')
            self.assertTrue(cole.validate_judge_result(inflated, 'finding-001'))
        self.assertEqual([], cole.validate_judge_result(judge('engineering-quality', 'Gas'), 'finding-001'))
        for reason in ('Normal well-protected authority has no demonstrated gap.',
                       'Timelock suggestion lacks project-specific benefit.',
                       'Naming preference does not meet the engineering-quality threshold.'):
            rejected = judge('hardening', 'Invalid')
            rejected['rejection_reason'] = reason
            self.assertEqual([], cole.validate_judge_result(rejected, 'finding-001'))
        rejected.pop('rejection_reason')
        self.assertTrue(cole.validate_judge_result(rejected, 'finding-001'))
        wrong = judge()
        wrong['required_conditions'][0]['status'] = 'false'
        self.assertTrue(cole.validate_judge_result(wrong, 'finding-001'))

    def test_pending_has_no_severity_and_needs_specific_evidence(self):
        self.assertEqual([], cole.validate_judge_result(pending(), 'finding-001'))
        for field in ('classification', 'verdict', 'severity', 'final_id'):
            bad = pending()
            bad[field] = None
            self.assertTrue(cole.validate_judge_result(bad, 'finding-001'))
        for questions in ([], [{'question': 'Which config?'}], ['unknown']):
            bad = pending()
            bad['missing_context'] = questions
            self.assertTrue(cole.validate_judge_result(bad, 'finding-001'))
        bad = judge()
        bad['missing_context'] = pending()['missing_context']
        self.assertTrue(cole.validate_judge_result(bad, 'finding-001'))
        self.assertTrue(cole.validate_judge_result(None, 'finding-001'))

    def test_group_aggregation_preserves_details(self):
        agent = dict(agent_id=2, agent_name='access-control', hypotheses_path=Path('hypotheses.json'))
        a = hypothesis()
        b = hypothesis(ident='KAI-02-002')
        b['recommendation'] = 'Use an independent role with bounded parameters.'
        b['missing_context'] = pending()['missing_context']
        candidates = cole.dedupe_candidates([{**cole.normalize_hypothesis(agent, x), "dedupe_key": "parent-group"} for x in (a, b)])
        self.assertEqual(1, len(candidates))
        result = candidates[0]
        self.assertEqual(2, len(result['review_details']))
        self.assertEqual({a['recommendation'], b['recommendation']}, {d['recommendation'] for d in result['review_details']})
        self.assertEqual(b['missing_context'], result['missing_context'])
        self.assertEqual('medium', result['confidence'])
        other = {**a, 'review_type': 'vulnerability'}
        self.assertEqual(2, len(cole.dedupe_candidates([{**cole.normalize_hypothesis(agent, x), "dedupe_key": x["review_type"]} for x in (a, other)])))

    def test_cli_merge_pending_resume_and_malformed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            run = root / 'MasterWu/Kai/runs/private-test'
            agent = run / 'agents/02-access-control'
            one, two = hypothesis('vulnerability'), hypothesis('trust-risk', 'KAI-02-002')
            one.update(title='Permission bypass', claim='Any user can reach privileged withdrawal.')
            two['missing_context'] = pending()['missing_context']
            write_json(agent / 'hypotheses.json', payload([one, two]))
            (agent / 'report.md').write_text('# completed')
            audit_context = dict(client_context={'file':'client.md', 'text':'Verify controller custody.'}, supporting_files=['tests/withdraw.t.sol'])
            write_json(run / 'spawn-manifest.json', dict(schema_version='2.0.0', runtime='solidity', audit_context=audit_context,
                agents=[dict(agent_id=2, agent_name='access-control', agent_dir=str(agent), hypotheses_path=str(agent/'hypotheses.json'), report_path=str(agent/'report.md'))]))
            proc = cli(COLE_PATH, 'collect', root, '--run', run)
            self.assertEqual(0, proc.returncode, proc.stderr)
            out = root / 'MasterWu/cole/runs/private-test'
            complete_dedup(COLE_PATH, out)
            candidate_path = out / 'candidates.json'
            data = json.loads(candidate_path.read_text())
            self.assertEqual(audit_context, data['audit_context'])
            write_json(out / 'preflight.json', dict(schema_version='2.0.0', status='skipped-local-build'))
            custom_judges = root / 'custom-judges'
            proc = cli(COLE_PATH, 'prepare-judges', candidate_path, '--out', custom_judges)
            self.assertEqual(0, proc.returncode, proc.stderr)
            manifest_path = custom_judges / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            for entry, candidate in zip(manifest['judges'], data['candidates']):
                bundle = Path(entry['bundle_path']).read_text()
                self.assertIn('Verify controller custody.', bundle)
                self.assertIn('skipped-local-build', bundle)
                record = judge('vulnerability', 'High', candidate['id']) if candidate['review_type']=='vulnerability' else pending(candidate['id'])
                write_json(Path(entry['output_json']), record)
            proc = cli(COLE_PATH, 'apply-judges', candidate_path, '--manifest', manifest_path)
            self.assertEqual(0, proc.returncode, proc.stderr)
            result_path = out / 'results.json'
            merged = json.loads(result_path.read_text())
            self.assertEqual(1, len(merged['findings']))
            self.assertEqual(1, len(merged['pending_questions']))
            deferred = merged['pending_questions'][0]
            self.assertNotIn('classification', deferred)
            self.assertNotIn('final_id', deferred)
            self.assertEqual(two['recommendation'], deferred['candidate']['recommendation'])
            self.assertEqual(audit_context, merged['audit_context'])
            self.assertEqual([], cole.validate_results(merged, data))
            report = (out / 'wreport.md').read_text()
            self.assertIn('Pending Client Questions', report)
            self.assertIn('Local build was skipped', report)
            self.assertNotIn('Bounty Recommendation', report)
            self.assertEqual(0, cli(COLE_PATH, 'render-report', result_path).returncode)
            # Reject hidden execution claims in source-only mode.
            invalid_result = copy.deepcopy(merged)
            invalid_result['findings'][0]['poc'].update(path='test/poc.sol', test_result='passed')
            self.assertTrue(cole.validate_results(invalid_result, data))
            # Resume just the deferred Judge without changing candidate identity/provenance.
            entry = next(e for e in manifest['judges'] if e['candidate_id']==deferred['candidate_id'])
            write_json(Path(entry['output_json']), judge(ident=deferred['candidate_id']))
            proc = cli(COLE_PATH, 'apply-judges', candidate_path, '--manifest', manifest_path)
            self.assertEqual(0, proc.returncode, proc.stderr)
            complete = json.loads(result_path.read_text())
            self.assertEqual([], complete['pending_questions'])
            self.assertEqual(2, len(complete['findings']))
            resumed = next(f for f in complete['findings'] if f['candidate_id']==deferred['candidate_id'])
            self.assertEqual(deferred['source_hypotheses'], resumed['source_hypotheses'])
            self.assertEqual('Info', resumed['classification'])
            self.assertEqual([], cole.validate_results(complete, data))
            # Malformed/missing/duplicate/extra output must not overwrite a good report.
            previous = result_path.read_text()
            Path(entry['output_json']).unlink()
            self.assertNotEqual(0, cli(COLE_PATH, 'apply-judges', candidate_path, '--manifest', manifest_path).returncode)
            Path(entry['output_json']).write_text('{')
            self.assertNotEqual(0, cli(COLE_PATH, 'apply-judges', candidate_path, '--manifest', manifest_path).returncode)
            write_json(Path(entry['output_json']), judge(ident=deferred['candidate_id']))
            duplicate = {**manifest, 'judges': manifest['judges'] + [entry]}
            write_json(manifest_path, duplicate)
            self.assertNotEqual(0, cli(COLE_PATH, 'apply-judges', candidate_path, '--manifest', manifest_path).returncode)
            extra = dict(entry, candidate_id='finding-999', output_json=str(root/'extra.json'))
            write_json(Path(extra['output_json']), judge(ident='finding-999'))
            write_json(manifest_path, {**manifest, 'judges':manifest['judges']+[extra]})
            self.assertNotEqual(0, cli(COLE_PATH, 'apply-judges', candidate_path, '--manifest', manifest_path).returncode)
            self.assertEqual(previous, result_path.read_text())
            # Pending and completed sections cannot duplicate or omit candidates.
            broken = copy.deepcopy(merged)
            broken['pending_questions'][0]['candidate_id'] = broken['findings'][0]['candidate_id']
            self.assertTrue(cole.validate_results(broken, data))
            broken = copy.deepcopy(merged)
            broken['pending_questions'] = []
            self.assertTrue(cole.validate_results(broken, data))


if __name__ == '__main__':
    selection = sys.argv[1] if len(sys.argv)>1 else 'all'
    suite = unittest.TestSuite()
    for name, cls in [('kai', KaiPrivateTests), ('cole', ColePrivateTests)]:
        if selection in ('all', name):
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if outcome.wasSuccessful() else 1)
