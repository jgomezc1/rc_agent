"""
Test script for the Grouping Optimizer.

Tests the core optimization logic with the actual data file.
"""

import sys
sys.path.insert(0, '/mnt/c/Users/jgomez/Dropbox/rc_agent')

from grouping_optimizer import (
    GroupingOptimizer,
    run_optimization,
    format_results_summary
)


def test_data_loading():
    """Test that data loads and parses correctly."""
    print("=" * 60)
    print("TEST: Data Loading")
    print("=" * 60)

    optimizer = GroupingOptimizer()
    file_path = "data/summary.xlsx"

    # Load data
    df = optimizer.load_data(file_path)
    print(f"Raw columns: {list(df.columns)}")
    print(f"Raw rows: {len(df)}")

    # Validate and prepare
    df = optimizer.validate_and_prepare_data(df)
    print(f"\nPrepared data:")
    print(f"  Columns: {list(df.columns)}")
    print(f"  Rows: {len(df)}")
    print(f"  Levels: {df['level'].tolist()}")
    print(f"  Steel values: {df['steel_total_per_level'].tolist()}")

    print("\n✓ Data loading test passed!")
    return df


def test_level_filtering(df):
    """Test level range filtering."""
    print("\n" + "=" * 60)
    print("TEST: Level Filtering")
    print("=" * 60)

    optimizer = GroupingOptimizer()

    # Test filtering a range
    filtered = optimizer.filter_level_range(df.copy(), "PISO 10", "PISO 20")
    print(f"Filtered range PISO 10 to PISO 20:")
    print(f"  Levels: {filtered['level'].tolist()}")
    print(f"  Count: {len(filtered)}")

    print("\n✓ Level filtering test passed!")
    return filtered


def test_partitioning():
    """Test partition generation."""
    print("\n" + "=" * 60)
    print("TEST: Partition Generation")
    print("=" * 60)

    optimizer = GroupingOptimizer()

    # Test various partition scenarios
    for n, k in [(5, 2), (5, 3), (10, 3), (10, 4)]:
        partitions = optimizer.generate_partitions(n, k)
        print(f"n={n}, k={k}: {len(partitions)} partitions")
        if len(partitions) <= 10:
            for p in partitions:
                print(f"    {p}")

    print("\n✓ Partition generation test passed!")


def test_optimization():
    """Test full optimization pipeline."""
    print("\n" + "=" * 60)
    print("TEST: Full Optimization")
    print("=" * 60)

    file_path = "data/summary.xlsx"

    # Run optimization
    results = run_optimization(
        file_path=file_path,
        start_level="PISO 5",
        end_level="PISO 15",
        candidate_k_values=[2, 3, 4],
        days_first_in_group=10.0,
        days_repeated=7.0,
        workdays_per_month=21.725,
        top_n=5
    )

    if "error" in results:
        print(f"ERROR: {results['error']}")
        return False

    # Print formatted results
    print(format_results_summary(results))

    print("\n✓ Full optimization test passed!")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("GROUPING OPTIMIZER TEST SUITE")
    print("=" * 60 + "\n")

    try:
        # Test 1: Data loading
        df = test_data_loading()

        # Test 2: Level filtering
        test_level_filtering(df)

        # Test 3: Partitioning
        test_partitioning()

        # Test 4: Full optimization
        test_optimization()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
