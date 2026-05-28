"""Observer Fleet Mathematics.

Send ships into infinity. Classify what returns.
"""

from .fleet import (
    ObserverFleet,
    ObserverShip,
    calibrate_against_random,
    classify_z_fingerprint,
    score_landscape,
    z_fingerprint,
)

__all__ = [
    "ObserverShip",
    "ObserverFleet",
    "score_landscape",
    "calibrate_against_random",
    "z_fingerprint",
    "classify_z_fingerprint",
]
