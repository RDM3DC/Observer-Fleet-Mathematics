"""Mission 007-style blind navigation demo."""

from __future__ import annotations

from observer_fleet.fleet import (
    ObserverFleet,
    calibrate_against_random,
    classify_z_fingerprint,
    z_fingerprint,
)
from observer_fleet.landscapes import (
    GENERATOR_LIBRARY,
    champernowne_digits,
    fibonacci_digits,
    mutate_digits,
    pi_digits,
    prime_digits,
    random_digits,
    repeating_cycle,
    square_digits,
    thue_morse_digits,
)
from observer_fleet.ships import GENERIC_SHIPS, build_witness_ships


def main() -> None:
    n = 1200
    controls = [random_digits(n, seed=707007 + i) for i in range(20)]

    fleet = ObserverFleet.from_functions(
        GENERIC_SHIPS,
        build_witness_ships(GENERATOR_LIBRARY),
    )
    baseline = calibrate_against_random(controls, fleet)

    mysteries = {
        "Mystery_A": fibonacci_digits(n),
        "Mystery_B": random_digits(n, seed=98765),
        "Mystery_C": mutate_digits(prime_digits(n), rate=0.02, seed=44),
        "Mystery_D": pi_digits(n),
        "Mystery_E": repeating_cycle(n, "7890123456"),
        "Mystery_F": square_digits(n),
        "Mystery_G": thue_morse_digits(n),
        "Mystery_H": champernowne_digits(n),
    }

    print("Observer Fleet Mathematics: Blind Navigation Demo")
    print("=" * 58)

    for name, landscape in mysteries.items():
        z = z_fingerprint(landscape, fleet, baseline)
        result = classify_z_fingerprint(z)

        print(f"{name:10s} -> {result['prediction']}")
        print(f"             confidence: {result['confidence']}")
        print(f"             generic_abs_z: {result['generic_abs_z']:.3f}")
        print(f"             dominant_witness_z: {result['dominant_witness_z']:.3f}")
        print()


if __name__ == "__main__":
    main()
