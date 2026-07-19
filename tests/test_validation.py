from observer_fleet.fleet import ObserverFleet, calibrate_against_random, z_fingerprint
from observer_fleet.landscapes import GENERATOR_LIBRARY, fibonacci_digits, random_digits
from observer_fleet.ships import GENERIC_SHIPS, build_witness_ships
from observer_fleet.validation import (
    bootstrap_rate_interval,
    classification_stability,
    classify_with_thresholds,
    correlation_matrix,
    empirical_quantile,
    learn_thresholds,
    mean_absolute_off_diagonal_correlation,
)


def fleet_and_baseline(n=300):
    fleet = ObserverFleet.from_functions(GENERIC_SHIPS, build_witness_ships(GENERATOR_LIBRARY))
    baseline = calibrate_against_random([random_digits(n, seed=100 + i) for i in range(20)], fleet)
    return fleet, baseline


def test_empirical_quantile_is_conservative():
    assert empirical_quantile([1, 2, 3, 4, 5], 0.8) == 5.0


def test_learned_thresholds_classify_fibonacci_witness():
    n = 300
    fleet, baseline = fleet_and_baseline(n)
    thresholds = learn_thresholds(
        [random_digits(n, seed=1000 + i) for i in range(40)],
        fleet,
        baseline,
        witness_negative_landscapes=[("12" * 150), ("9876543210" * 30)],
    )
    result = classify_with_thresholds(z_fingerprint(fibonacci_digits(n), fleet, baseline), thresholds)
    assert result["prediction"] == "witness-confirmed: fibonacci_digits"


def test_bootstrap_interval_contains_observed_rate():
    outcomes = [True] * 8 + [False] * 2
    low, high = bootstrap_rate_interval(outcomes, resamples=500, seed=7)
    assert low <= 0.8 <= high


def test_correlation_summary_and_stability():
    matrix = correlation_matrix([
        {"a_z": 0.0, "b_z": 0.0},
        {"a_z": 1.0, "b_z": 1.0},
        {"a_z": 2.0, "b_z": 2.0},
    ])
    assert mean_absolute_off_diagonal_correlation(matrix) == 1.0
    assert classification_stability(["random", "random", "structured"]) == 2 / 3
