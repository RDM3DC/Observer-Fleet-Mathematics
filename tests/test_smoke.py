from observer_fleet.fleet import ObserverFleet, calibrate_against_random, classify_z_fingerprint, z_fingerprint
from observer_fleet.landscapes import GENERATOR_LIBRARY, fibonacci_digits, random_digits
from observer_fleet.ships import GENERIC_SHIPS, build_witness_ships


def test_fibonacci_witness_smoke():
    n = 300
    controls = [random_digits(n, seed=10 + i) for i in range(5)]
    fleet = ObserverFleet.from_functions(GENERIC_SHIPS, build_witness_ships(GENERATOR_LIBRARY))
    baseline = calibrate_against_random(controls, fleet)
    z = z_fingerprint(fibonacci_digits(n), fleet, baseline)
    result = classify_z_fingerprint(z)
    assert "fibonacci_digits" in result["prediction"]
