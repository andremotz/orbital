"""Tests für Horizons-Anbindung, Bahnelemente und Delta-v-Manöver.

Kein Test geht ins Netz: der Parser arbeitet auf einer eingebetteten Antwort,
die Referenzbahn kommt aus dem Cache im Repository.
"""

import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.constants import GM_EARTH
from data.horizons import (
    BODY_IDS,
    HorizonsError,
    build_query,
    load_cache,
    parse_vectors,
)
from models.maneuver import Maneuver
from physics.elements import elements_from_state
from physics.mission import get_mission_acceleration
from tests.test_physics import make_object

# Gekürzter, aber formattreuer Auszug einer echten Horizons-Antwort
SAMPLE_RESPONSE = """
*******************************************************************************
Target body name: Earth (399)                     {source: DE441}
Output units    : KM-S
Reference frame : Ecliptic of J2000.0
*******************************************************************************
$$SOE
2458686.500000000 = A.D. 2019-Jul-22 00:00:00.0000 TDB
 X = 7.292229516071694E+07 Y =-1.333685701232687E+08 Z = 6.336824780039489E+03
 VX= 2.565031556544730E+01 VY= 1.416712833545106E+01 VZ=-3.066511129983240E-04
2458687.500000000 = A.D. 2019-Jul-23 00:00:00.0000 TDB
 X = 7.512820351567061E+07 Y =-1.321257787936269E+08 Z = 6.299708354696631E+03
 VX= 2.541117068041232E+01 VY= 1.460061831851279E+01 VZ=-5.551485167334391E-04
$$EOE
*******************************************************************************
"""


class TestHorizonsParsing(unittest.TestCase):
    """Der Parser muss Werte korrekt lesen und nach SI umrechnen."""

    def test_reads_all_records(self):
        records = parse_vectors(SAMPLE_RESPONSE)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["jd"], 2458686.5)

    def test_converts_kilometres_to_metres(self):
        record = parse_vectors(SAMPLE_RESPONSE)[0]

        # Horizons liefert km und km/s, intern wird in m und m/s gerechnet
        self.assertAlmostEqual(record["location"][0], 7.292229516071694e10, places=0)
        self.assertAlmostEqual(record["velocity"][0], 2.565031556544730e4, places=3)

    def test_reads_values_without_space_after_equals(self):
        """Negative Werte stehen direkt am Gleichheitszeichen."""
        record = parse_vectors(SAMPLE_RESPONSE)[0]
        self.assertAlmostEqual(record["location"][1], -1.333685701232687e11, places=0)

    def test_keeps_full_precision(self):
        """Gerundete Startwerte wären in dieser Rechnung wertlos.

        Sieben signifikante Stellen entsprächen bei einer Erdposition schon
        rund zehn Kilometern.
        """
        record = parse_vectors(SAMPLE_RESPONSE)[0]
        self.assertEqual(repr(record["location"][0]), repr(7.292229516071694e10))

    def test_rejects_response_without_ephemeris(self):
        with self.assertRaises(HorizonsError):
            parse_vectors("No ephemeris for target prior to A.D. 2019-JUL-22")


class TestHorizonsQuery(unittest.TestCase):
    """Die Abfrage muss das richtige Bezugssystem anfordern."""

    def test_requests_ecliptic_frame_and_vectors(self):
        query = build_query("Earth", "2019-07-22", "2019-07-23", "1d", "500@0")

        self.assertIn("ECLIPTIC", query)
        self.assertIn("VECTORS", query)
        self.assertIn("KM-S", query)

    def test_resolves_known_body_names_to_ids(self):
        query = build_query("Chandrayaan-2", "2019-07-22", "2019-07-23", "1d", "500@0")

        self.assertEqual(BODY_IDS["Chandrayaan-2"], "-152")
        self.assertIn("-152", query)


class TestGroundTruthCache(unittest.TestCase):
    """Die mitgelieferte Referenzbahn muss brauchbar sein."""

    def test_truth_cache_is_present_and_ordered(self):
        records = load_cache("chandrayaan2_truth")["records"]

        self.assertGreater(len(records), 20)
        julian_dates = [record["jd"] for record in records]
        self.assertEqual(julian_dates, sorted(julian_dates))

    def test_initial_state_covers_every_body(self):
        states = load_cache("chandrayaan2_initial_state")["states"]

        for name in ("Sun", "Earth", "Moon", "Chandrayaan-2"):
            with self.subTest(body=name):
                self.assertEqual(len(states[name]["location"]), 3)

    def test_detected_maneuvers_match_the_published_schedule(self):
        """Die aus der Bahn gewonnenen Burns müssen den ISRO-Terminen folgen.

        Zeitpunkte laut ISRO, in UTC umgerechnet. Die Erkennung arbeitet mit
        zehn Minuten Auflösung, daher die grosszügige Toleranz.
        """
        detected = load_cache("chandrayaan2_maneuvers")["maneuvers"]
        burns = [entry for entry in detected if entry["delta_v"] > 50.0]

        published = {
            "2019-Jul-25 19": "EBN#2",
            "2019-Jul-29 09": "EBN#3",
            "2019-Aug-02 09": "EBN#4",
            "2019-Aug-06 09": "EBN#5",
            "2019-Aug-13 20": "TLI",
            "2019-Aug-20 03": "LOI",
        }

        found = {entry["start"][:14] for entry in burns}
        for stamp, label in published.items():
            with self.subTest(maneuver=label):
                self.assertIn(stamp, found, f"{label} nicht wiedergefunden")

    def test_quiet_residual_is_small(self):
        """Ohne Manöver muss die Rechnung der realen Bahn eng folgen.

        Sonst liessen sich Burns nicht von Modellfehlern trennen.
        """
        summary = load_cache("chandrayaan2_maneuvers")

        self.assertLess(summary["quiet_residual_median"], 0.1,
                        "Restabweichung zu gross, Burn-Erkennung wäre unzuverlässig")


class TestOrbitalElements(unittest.TestCase):
    """Bahnelemente aus Zustandsvektoren."""

    def circular_state(self, radius=7.0e6):
        speed = math.sqrt(GM_EARTH / radius)
        return np.array([radius, 0.0, 0.0]), np.array([0.0, speed, 0.0])

    def test_circular_orbit_has_zero_eccentricity(self):
        location, velocity = self.circular_state()
        elements = elements_from_state(location, velocity, GM_EARTH)

        self.assertAlmostEqual(elements.eccentricity, 0.0, places=12)
        self.assertAlmostEqual(elements.semi_major_axis / 7.0e6, 1.0, places=12)

    def test_apsides_match_a_known_ellipse(self):
        periapsis, apoapsis = 6.6e6, 4.2e7
        semi_major_axis = (periapsis + apoapsis) / 2.0
        eccentricity = (apoapsis - periapsis) / (apoapsis + periapsis)
        speed = math.sqrt(GM_EARTH * (2.0 / periapsis - 1.0 / semi_major_axis))

        elements = elements_from_state(
            [periapsis, 0.0, 0.0], [0.0, speed, 0.0], GM_EARTH
        )

        self.assertAlmostEqual(elements.periapsis / periapsis, 1.0, places=9)
        self.assertAlmostEqual(elements.apoapsis / apoapsis, 1.0, places=9)
        self.assertAlmostEqual(elements.eccentricity / eccentricity, 1.0, places=9)

    def test_inclination_is_recovered(self):
        radius = 7.0e6
        speed = math.sqrt(GM_EARTH / radius)
        angle = math.radians(28.5)

        elements = elements_from_state(
            [radius, 0.0, 0.0],
            [0.0, speed * math.cos(angle), speed * math.sin(angle)],
            GM_EARTH,
        )

        self.assertAlmostEqual(math.degrees(elements.inclination), 28.5, places=9)

    def test_hyperbolic_orbit_reports_no_apoapsis(self):
        radius = 7.0e6
        escape = math.sqrt(2.0 * GM_EARTH / radius)

        elements = elements_from_state(
            [radius, 0.0, 0.0], [0.0, escape * 1.2, 0.0], GM_EARTH
        )

        self.assertGreater(elements.eccentricity, 1.0)
        self.assertTrue(math.isinf(elements.apoapsis))
        self.assertTrue(math.isinf(elements.period))

    def test_elements_are_insensitive_to_orbital_phase(self):
        """Der Sinn der Grösse: gleiche Bahn, andere Stelle, gleiche Elemente.

        Genau deshalb taugen Elemente zum Bahnvergleich, wo der blosse
        Positionsabstand längst nur noch die Phase misst.
        """
        periapsis, apoapsis = 6.6e6, 4.2e7
        semi_major_axis = (periapsis + apoapsis) / 2.0
        speed_periapsis = math.sqrt(
            GM_EARTH * (2.0 / periapsis - 1.0 / semi_major_axis)
        )
        speed_apoapsis = math.sqrt(GM_EARTH * (2.0 / apoapsis - 1.0 / semi_major_axis))

        at_periapsis = elements_from_state(
            [periapsis, 0.0, 0.0], [0.0, speed_periapsis, 0.0], GM_EARTH
        )
        at_apoapsis = elements_from_state(
            [-apoapsis, 0.0, 0.0], [0.0, -speed_apoapsis, 0.0], GM_EARTH
        )

        self.assertAlmostEqual(
            at_periapsis.semi_major_axis / at_apoapsis.semi_major_axis, 1.0, places=9
        )
        self.assertAlmostEqual(
            at_periapsis.eccentricity / at_apoapsis.eccentricity, 1.0, places=9
        )


class TestDeltaVManeuvers(unittest.TestCase):
    """Manöver lassen sich über Delta-v statt über Schub beschreiben."""

    def test_delta_v_is_spread_over_the_burn(self):
        probe = make_object("P", 1000.0, [7.0e6, 0.0, 0.0], [0.0, 1000.0, 0.0],
                            is_heavy=False)
        probe.list_maneuvers.append(
            Maneuver(time_start=0, time_duration=100.0, delta_v=250.0)
        )

        acceleration = get_mission_acceleration(probe, 50.0)

        # 250 m/s über 100 s ergeben 2,5 m/s^2
        self.assertAlmostEqual(float(np.linalg.norm(acceleration)), 2.5, places=12)

    def test_delta_v_does_not_depend_on_mass(self):
        """Anders als Schub: Delta-v beschreibt die Bahnänderung direkt."""
        magnitudes = []
        for mass in (1000.0, 3850.0):
            probe = make_object("P", mass, [7.0e6, 0.0, 0.0], [0.0, 1000.0, 0.0],
                                is_heavy=False)
            probe.list_maneuvers.append(
                Maneuver(time_start=0, time_duration=100.0, delta_v=250.0)
            )
            magnitudes.append(float(np.linalg.norm(
                get_mission_acceleration(probe, 50.0)
            )))

        self.assertAlmostEqual(magnitudes[0], magnitudes[1], places=12)

    def test_force_still_depends_on_mass(self):
        magnitudes = []
        for mass in (1000.0, 2000.0):
            probe = make_object("P", mass, [7.0e6, 0.0, 0.0], [0.0, 1000.0, 0.0],
                                is_heavy=False)
            probe.list_maneuvers.append(
                Maneuver(time_start=0, time_duration=100.0, force=500.0)
            )
            magnitudes.append(float(np.linalg.norm(
                get_mission_acceleration(probe, 50.0)
            )))

        self.assertAlmostEqual(magnitudes[0] / magnitudes[1], 2.0, places=12)

    def test_requires_exactly_one_of_force_and_delta_v(self):
        with self.assertRaises(ValueError):
            Maneuver(0, 100.0)
        with self.assertRaises(ValueError):
            Maneuver(0, 100.0, force=10.0, delta_v=10.0)

    def test_rejects_non_positive_duration(self):
        with self.assertRaises(ValueError):
            Maneuver(0, 0.0, delta_v=10.0)


if __name__ == "__main__":
    unittest.main()
