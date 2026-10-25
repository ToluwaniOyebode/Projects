"""Prevent unsupported actions from producing a misleading accuracy metric."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('review_eval', Path(__file__).resolve().parents[1]/'scripts/evaluate_reviewed.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_unsupported_cases_remain_visible_and_accuracy_is_undefined():
    cases = [dict(truth='off_ball', prediction=dict(action='carry'))]
    result = module.summarize(cases, ['carry', 'pass'])
    assert result['total_reviewed'] == 1
    assert result['unsupported_targets'] == 1
    assert result['supported_target_accuracy'] is None
    assert result['scope_coverage'] == 0


def test_mixed_scope_reports_both_denominators():
    cases = [dict(truth='pass',prediction=dict(action='pass')),
             dict(truth='receive',prediction=dict(action='carry')),
             dict(truth='off_ball',prediction=dict(action='carry'))]
    result = module.summarize(cases, ['carry','pass','receive'])
    assert result['supported_target_accuracy'] == .5
    assert result['scope_coverage'] == 2/3
    assert result['unsupported_targets'] == 1
