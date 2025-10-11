#!/usr/bin/env python3
"""
Unit tests for Phase-1 RS Selector

Tests for decoding, filtering, scoring, and Pareto frontier computation.
"""

import unittest
import tempfile
import json
import os
from rs_selector import (
    RSObjective, load_catalog, decode_rs_code, build_objective_weights,
    apply_constraints, normalize_metrics, score_weighted_sum,
    pareto_front, explain_tradeoff, get_top_k_recommendations,
    ConstraintError
)


class TestRSSelector(unittest.TestCase):
    """Test suite for RS Selector functionality"""

    def setUp(self):
        """Set up test data"""
        self.sample_catalog = {
            "AG_EM_5a8_L50": {
                "steel_tonnage": 98.5,
                "concrete_volume": 3850,
                "steel_cost": 147750,
                "concrete_cost": 308000,
                "manhours": 600,
                "duration_days": 68,
                "co2_tonnes": 534,
                "constructibility_index": 2.7,
                "bar_geometries": 240
            },
            "TR_6_L10": {
                "steel_tonnage": 92.0,
                "concrete_volume": 3820,
                "steel_cost": 138000,
                "concrete_cost": 305600,
                "manhours": 570,
                "duration_days": 63,
                "co2_tonnes": 505,
                "constructibility_index": 2.5,
                "bar_geometries": 210
            },
            "EM_6a6_L100": {
                "steel_tonnage": 90.0,
                "concrete_volume": 3810,
                "steel_cost": 135000,
                "concrete_cost": 304800,
                "manhours": 560,
                "duration_days": 62,
                "co2_tonnes": 498,
                "constructibility_index": 2.4,
                "bar_geometries": 200
            }
        }

    def test_decode_rs_code_valid_formats(self):
        """Test RS code decoding with valid formats"""
        # Test grouped EM with range
        result = decode_rs_code("AG_EM_5a8_L50")
        expected = {
            'grouped': True,
            'join': 'EM',
            'bars': {'min': 5, 'max': 8},
            'L': 50
        }
        self.assertEqual(result, expected)

        # Test non-grouped TR with single bar
        result = decode_rs_code("TR_6_L10")
        expected = {
            'grouped': False,
            'join': 'TR',
            'bars': {'min': 6, 'max': 6},
            'L': 10
        }
        self.assertEqual(result, expected)

        # Test EM with same min/max
        result = decode_rs_code("EM_6a6_L100")
        expected = {
            'grouped': False,
            'join': 'EM',
            'bars': {'min': 6, 'max': 6},
            'L': 100
        }
        self.assertEqual(result, expected)

    def test_decode_rs_code_invalid_formats(self):
        """Test RS code decoding with invalid formats"""
        invalid_codes = [
            "INVALID_CODE",
            "AG_XX_5a8_L50",  # Invalid join
            "XX_EM_5a8_L50",  # Invalid prefix (not AG)
            "AG_EM_L50",      # Missing bars
            "AG_EM_5a8",      # Missing L
            "AG_EM_5a8_50",   # Missing L prefix
            ""
        ]

        for code in invalid_codes:
            with self.assertRaises(ValueError):
                decode_rs_code(code)

    def test_build_objective_weights(self):
        """Test objective weight building"""
        # Test MIN_COST preset
        weights = build_objective_weights(RSObjective.MIN_COST)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)
        self.assertEqual(weights['steel_cost'], 0.45)
        self.assertEqual(weights['concrete_cost'], 0.25)

        # Test BALANCED preset
        weights = build_objective_weights(RSObjective.BALANCED)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=6)
        # All weights should be equal (1/8)
        expected_weight = 1/8
        for weight in weights.values():
            self.assertAlmostEqual(weight, expected_weight, places=6)

    def test_apply_constraints_mnemonic(self):
        """Test constraint application for mnemonic constraints"""
        # Test join constraint
        result = apply_constraints(
            self.sample_catalog,
            join=['EM']
        )
        expected_codes = {'AG_EM_5a8_L50', 'EM_6a6_L100'}
        self.assertEqual(set(result.keys()), expected_codes)

        # Test grouped constraint
        result = apply_constraints(
            self.sample_catalog,
            grouped=True
        )
        expected_codes = {'AG_EM_5a8_L50'}
        self.assertEqual(set(result.keys()), expected_codes)

        # Test L constraint
        result = apply_constraints(
            self.sample_catalog,
            L=[10, 50]
        )
        expected_codes = {'AG_EM_5a8_L50', 'TR_6_L10'}
        self.assertEqual(set(result.keys()), expected_codes)

        # Test bars range constraint
        result = apply_constraints(
            self.sample_catalog,
            bars='5-8'
        )
        expected_codes = {'AG_EM_5a8_L50'}
        self.assertEqual(set(result.keys()), expected_codes)

        # Test bars single value constraint
        result = apply_constraints(
            self.sample_catalog,
            bars='6'
        )
        expected_codes = {'AG_EM_5a8_L50', 'TR_6_L10', 'EM_6a6_L100'}
        self.assertEqual(set(result.keys()), expected_codes)

    def test_apply_constraints_kpi(self):
        """Test constraint application for KPI constraints"""
        # Test steel_cost constraint
        result = apply_constraints(
            self.sample_catalog,
            kpi_filters={'steel_cost': ('<=', 140000)}
        )
        expected_codes = {'TR_6_L10', 'EM_6a6_L100'}
        self.assertEqual(set(result.keys()), expected_codes)

        # Test duration_days constraint
        result = apply_constraints(
            self.sample_catalog,
            kpi_filters={'duration_days': ('<', 65)}
        )
        expected_codes = {'TR_6_L10', 'EM_6a6_L100'}
        self.assertEqual(set(result.keys()), expected_codes)

        # Test multiple KPI constraints (AND logic)
        result = apply_constraints(
            self.sample_catalog,
            kpi_filters={
                'steel_cost': ('<=', 140000),
                'co2_tonnes': ('<', 500)
            }
        )
        expected_codes = {'EM_6a6_L100'}
        self.assertEqual(set(result.keys()), expected_codes)

    def test_apply_constraints_invalid_kpi(self):
        """Test constraint application with invalid KPI"""
        with self.assertRaises(ConstraintError):
            apply_constraints(
                self.sample_catalog,
                kpi_filters={'invalid_metric': ('<=', 100)}
            )

    def test_normalize_metrics(self):
        """Test metric normalization"""
        metrics = ['steel_cost', 'duration_days']
        normalized = normalize_metrics(self.sample_catalog, metrics)

        # Check that normalized values exist
        for rs_code, data in normalized.items():
            self.assertIn('steel_cost_norm', data)
            self.assertIn('duration_days_norm', data)

        # Check that min value maps to 0 and max to 1
        steel_costs = [data['steel_cost'] for data in self.sample_catalog.values()]
        min_cost = min(steel_costs)
        max_cost = max(steel_costs)

        for rs_code, data in normalized.items():
            if data['steel_cost'] == min_cost:
                self.assertEqual(data['steel_cost_norm'], 0.0)
            elif data['steel_cost'] == max_cost:
                self.assertEqual(data['steel_cost_norm'], 1.0)

    def test_score_weighted_sum(self):
        """Test weighted sum scoring"""
        metrics = ['steel_cost', 'duration_days']
        normalized = normalize_metrics(self.sample_catalog, metrics)

        weights = {'steel_cost': 0.7, 'duration_days': 0.3}
        scores = score_weighted_sum(normalized, weights)

        # Check that we get scores for all RS
        self.assertEqual(len(scores), len(self.sample_catalog))

        # Check that scores are sorted (lower is better)
        for i in range(len(scores) - 1):
            self.assertLessEqual(scores[i][1], scores[i + 1][1])

        # Check that scores are in valid range [0, 1]
        for rs_code, score in scores:
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_pareto_front(self):
        """Test Pareto frontier computation"""
        metrics = ['steel_cost', 'duration_days', 'co2_tonnes']
        normalized = normalize_metrics(self.sample_catalog, metrics)

        pareto_set = pareto_front(normalized, metrics)

        # Pareto set should not be empty
        self.assertGreater(len(pareto_set), 0)

        # All RS codes in Pareto set should exist in catalog
        for rs_code in pareto_set:
            self.assertIn(rs_code, self.sample_catalog)

    def test_explain_tradeoff(self):
        """Test trade-off explanation"""
        rs1 = "AG_EM_5a8_L50"
        rs2 = "TR_6_L10"

        explanation = explain_tradeoff(rs1, rs2, self.sample_catalog, RSObjective.MIN_COST)

        # Should return a non-empty string
        self.assertIsInstance(explanation, str)
        self.assertGreater(len(explanation), 0)

        # Should contain some comparison information
        self.assertTrue(any(word in explanation.lower() for word in ['vs', 'steel', 'days', 'em', 'tr']))

    def test_get_top_k_recommendations(self):
        """Test complete recommendation pipeline"""
        result = get_top_k_recommendations(
            catalog=self.sample_catalog,
            objective=RSObjective.MIN_COST,
            k=2
        )

        # Check result structure
        self.assertIn('recommendations', result)
        self.assertIn('rationale', result)
        self.assertIn('pareto_frontier', result)
        self.assertIn('total_candidates', result)

        # Check recommendations
        recommendations = result['recommendations']
        self.assertLessEqual(len(recommendations), 2)
        self.assertGreater(len(recommendations), 0)

        # Check recommendation structure
        rec = recommendations[0]
        self.assertIn('rs_code', rec)
        self.assertIn('score', rec)
        self.assertIn('data', rec)

        # Check that total_candidates matches input
        self.assertEqual(result['total_candidates'], len(self.sample_catalog))

    def test_load_catalog_file_operations(self):
        """Test catalog loading with various file conditions"""
        # Test successful loading
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.sample_catalog, f)
            temp_path = f.name

        try:
            loaded_catalog = load_catalog(temp_path)
            self.assertEqual(loaded_catalog, self.sample_catalog)
        finally:
            os.unlink(temp_path)

        # Test file not found
        with self.assertRaises(FileNotFoundError):
            load_catalog("nonexistent_file.json")

        # Test invalid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = f.name

        try:
            with self.assertRaises(ValueError):
                load_catalog(temp_path)
        finally:
            os.unlink(temp_path)

        # Test missing required fields
        incomplete_catalog = {
            "RS_001": {
                "steel_cost": 100000
                # Missing other required fields
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(incomplete_catalog, f)
            temp_path = f.name

        try:
            with self.assertRaises(ValueError):
                load_catalog(temp_path)
        finally:
            os.unlink(temp_path)

    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Empty catalog
        empty_result = get_top_k_recommendations(
            catalog={},
            objective=RSObjective.BALANCED,
            k=5
        )
        self.assertEqual(len(empty_result['recommendations']), 0)

        # Single RS catalog
        single_catalog = {"TR_6_L10": self.sample_catalog["TR_6_L10"]}
        single_result = get_top_k_recommendations(
            catalog=single_catalog,
            objective=RSObjective.BALANCED,
            k=5
        )
        self.assertEqual(len(single_result['recommendations']), 1)

        # Constraints that eliminate all options
        no_match_result = get_top_k_recommendations(
            catalog=self.sample_catalog,
            objective=RSObjective.BALANCED,
            k=5,
            kpi_filters={'steel_cost': ('<=', 50000)}  # Impossible constraint
        )
        self.assertEqual(len(no_match_result['recommendations']), 0)


def run_tests():
    """Run all tests"""
    unittest.main(verbosity=2)


if __name__ == "__main__":
    run_tests()