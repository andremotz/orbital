"""Tests für die Missions-Animationen.

Gerendert wird hier nichts -- ein Lauf dauert Minuten und schriebe Dateien.
Geprüft wird die Logik davor: Zeitraster, Sichtfeldnachführung und dass die
Missionsangaben zu den Szenarien passen.
"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import make_animations
from data.horizons import load_cache
from data.scenario import load_named_scenario


class TestTiming(unittest.TestCase):
    """Jede Animation läuft genau so lange, wie für sie angegeben."""

    def test_frame_count_matches_the_requested_duration(self):
        for key in make_animations.MISSIONS:
            with self.subTest(mission=key):
                runtime, fps, frames = make_animations.timing(key)
                self.assertEqual(frames, int(round(runtime * fps)))
                self.assertAlmostEqual(frames / fps, runtime, places=6)

    def test_cassini_runs_longer_than_the_lunar_missions(self):
        """Sieben Jahre in zwanzig Sekunden liessen die Vorbeiflüge
        vorbeihuschen; eine Minute gibt ihnen Raum."""
        self.assertGreaterEqual(make_animations.timing("cassini_cruise")[0], 60.0)
        self.assertGreater(make_animations.timing("cassini_cruise")[0],
                           make_animations.timing("chandrayaan2")[0] * 2)

    def test_trajectory_is_sampled_finer_than_the_frame_rate(self):
        """Sonst geriete der Bahnschweif zum Vieleck.

        Chandrayaans früher Orbit dauert rund 13,8 Stunden. Bei 500 Bildern
        über 46 Tage entfielen darauf nur sechs Stützstellen -- die Ellipse
        sähe aus wie ein Sechseck.
        """
        self.assertGreater(make_animations.SAMPLES_PER_FRAME, 1)

        duration = make_animations.MISSIONS["chandrayaan2"]["duration"]
        samples = (make_animations.timing("chandrayaan2")[2]
                   * make_animations.SAMPLES_PER_FRAME)
        step = duration / samples

        early_orbit_period = 13.8 * 3600.0
        self.assertGreater(early_orbit_period / step, 20.0,
                           "Zu wenige Stützstellen je Umlauf für eine glatte Bahn")


class TestViewLimits(unittest.TestCase):
    """Das Sichtfeld folgt der Bahn, ohne zu ruckeln oder zurückzuspringen."""

    def growing_track(self, count=600):
        """Bahn, deren Ausdehnung über die Zeit zunimmt."""
        angle = np.linspace(0.0, 40.0, count)
        radius = np.linspace(1.0e7, 4.0e8, count)
        return np.column_stack([radius * np.cos(angle), radius * np.sin(angle)])

    def test_never_zooms_back_in(self):
        """Ein schrumpfendes Bild wirkt wie ein Fehler, nicht wie Absicht."""
        track = self.growing_track()
        times = np.linspace(0.0, 4.0e6, len(track))

        limits = make_animations.view_limits(track, track, times, None, None)

        self.assertTrue(np.all(np.diff(limits) >= -1e-9),
                        "Sichtfeld wird zwischendurch enger")

    def test_shrinking_track_keeps_the_wide_view(self):
        """Auch wenn die Sonde zurückkommt, bleibt die Ansicht weit."""
        track = self.growing_track()[::-1]
        times = np.linspace(0.0, 4.0e6, len(track))

        limits = make_animations.view_limits(track, track, times, None, None)

        self.assertTrue(np.all(np.diff(limits) >= -1e-9))

    def test_track_stays_inside_the_view(self):
        """Was gezeichnet wird, muss auch im Bild liegen."""
        track = self.growing_track()
        times = np.linspace(0.0, 4.0e6, len(track))

        limits = make_animations.view_limits(track, track, times, None, None)

        # Der Zoom zieht geglättet nach; über den ganzen Lauf muss die Bahn
        # aber erfasst sein
        self.assertGreaterEqual(limits[-1], np.max(np.abs(track)) * 0.99)

    def test_changes_are_gradual(self):
        """Sprunghafte Sichtfeldwechsel wären im Bild ein Zucken."""
        track = self.growing_track()
        times = np.linspace(0.0, 4.0e6, len(track))

        limits = make_animations.view_limits(track, track, times, None, None)
        relative_jumps = np.diff(limits) / limits[:-1]

        self.assertLess(float(np.max(relative_jumps)), 0.08)

    def test_reference_track_is_included(self):
        """Die reale Bahn hat ein eigenes Zeitraster und muss trotzdem passen."""
        track = self.growing_track() * 0.5
        times = np.linspace(0.0, 4.0e6, len(track))

        reference_seconds = np.linspace(0.0, 4.0e6, 40)
        reference = self.growing_track(40)

        without = make_animations.view_limits(track, track, times, None, None)
        with_reference = make_animations.view_limits(
            track, track, times, reference_seconds, reference
        )

        self.assertGreater(with_reference[-1], without[-1],
                           "Die weiter reichende reale Bahn liefe aus dem Bild")

    def test_minimum_extent_keeps_the_first_frames_readable(self):
        """Ohne Untergrenze zoomte der Anfang auf einen Punkt."""
        tiny = np.full((10, 2), 1.0e5)
        times = np.linspace(0.0, 1000.0, 10)

        limits = make_animations.view_limits(tiny, tiny, times, None, None)

        self.assertGreaterEqual(float(limits[0]), 1.5e7)


class TestMissionRegistry(unittest.TestCase):
    """Die Angaben in MISSIONS müssen zu den Szenarien und Caches passen."""

    def test_every_mission_has_a_scenario(self):
        for key, mission in make_animations.MISSIONS.items():
            with self.subTest(mission=key):
                scenario = load_named_scenario(key)
                self.assertIsNotNone(scenario.body(mission["body"]))

    def test_every_mission_has_a_fine_reference_track(self):
        """Die groben Truth-Caches reichen zum Animieren nicht.

        Bei 12-Stunden-Abtastung bekaeme Chandrayaans 13,8-Stunden-Orbit sechs
        Punkte, und die Ellipse geriete zum Sechseck. Gefordert ist deshalb ein
        Raster, das die Missionsdauer in mindestens 500 Stuetzstellen zerlegt --
        so viele Bilder hat die Animation.
        """
        for key, mission in make_animations.MISSIONS.items():
            with self.subTest(mission=key):
                records = load_cache(mission["truth"])["records"]
                self.assertGreater(len(records), make_animations.timing(key)[2])

    def test_duration_stays_within_the_reference_data(self):
        """Sonst liefe die Animation über das Ende der Referenz hinaus."""
        for key, mission in make_animations.MISSIONS.items():
            with self.subTest(mission=key):
                records = load_cache(mission["truth"])["records"]
                span = (records[-1]["jd"] - records[0]["jd"]) * 86400.0
                self.assertLessEqual(mission["duration"], span * 1.02)

    def test_reference_track_is_trimmed_to_the_animation(self):
        seconds, positions = make_animations.reference_track("artemis2", 100_000.0)

        self.assertIsNotNone(seconds)
        self.assertLessEqual(float(seconds.max()), 100_000.0)
        self.assertEqual(len(seconds), len(positions))


if __name__ == "__main__":
    unittest.main()


class TestFrameConfiguration(unittest.TestCase):
    """Bezugspunkt und Kontextkörper sind pro Mission wählbar."""

    def test_every_mission_names_its_frame(self):
        for key, mission in make_animations.MISSIONS.items():
            with self.subTest(mission=key):
                for field in ("center", "context", "barycentric", "scale", "unit"):
                    self.assertIn(field, mission)

    def test_frame_bodies_exist_in_the_scenario(self):
        from data.scenario import load_named_scenario

        for key, mission in make_animations.MISSIONS.items():
            with self.subTest(mission=key):
                scenario = load_named_scenario(key)
                names = {body.name for body in scenario.bodies}
                self.assertIn(mission["center"], names)
                for companion in mission["context"]:
                    self.assertIn(companion, names)

    def test_lunar_missions_are_geocentric_and_cassini_is_not(self):
        """Der Bezug entscheidet, ob die Referenzbahn umgerechnet werden muss.

        Beides zu verwechseln kostet über eine Million Kilometer -- genau
        daran ist ein früherer Meilenstein gescheitert.
        """
        self.assertFalse(make_animations.MISSIONS["chandrayaan2"]["barycentric"])
        self.assertTrue(make_animations.MISSIONS["cassini_cruise"]["barycentric"])
        self.assertEqual(make_animations.MISSIONS["cassini_cruise"]["center"], "Sun")


class TestAnchoring(unittest.TestCase):
    """Verankerung an den Vorbeiflügen."""

    def test_only_cassini_is_anchored(self):
        """Über eine Mondmission lässt sich durchrechnen, über eine
        Vorbeiflugkette nicht."""
        self.assertIsNone(make_animations.MISSIONS["chandrayaan2"].get("anchors"))
        self.assertIsNotNone(make_animations.MISSIONS["cassini_cruise"].get("anchors"))

    def test_anchors_are_ordered_and_inside_the_mission(self):
        from data.horizons import load_cache

        epoch = load_cache("cassini_truth_fine")["records"][0]["jd"]
        anchors = make_animations.load_anchors("cassini_cruise", epoch)

        self.assertGreaterEqual(len(anchors), 4)
        times = [a["time"] for a in anchors]
        self.assertEqual(times, sorted(times))
        self.assertGreater(times[0], 0.0)
        self.assertLess(times[-1],
                        make_animations.MISSIONS["cassini_cruise"]["duration"])

    def test_anchors_carry_a_full_state(self):
        from data.horizons import load_cache

        epoch = load_cache("cassini_truth_fine")["records"][0]["jd"]
        for anchor in make_animations.load_anchors("cassini_cruise", epoch):
            with self.subTest(anchor=anchor["label"]):
                self.assertEqual(len(anchor["location"]), 3)
                self.assertEqual(len(anchor["velocity"]), 3)
                self.assertTrue(anchor["label"])

    def test_anchor_labels_name_the_encounters(self):
        from data.horizons import load_cache

        epoch = load_cache("cassini_truth_fine")["records"][0]["jd"]
        labels = {a["label"] for a in
                  make_animations.load_anchors("cassini_cruise", epoch)}

        for expected in ("Venus 1", "Venus 2", "Earth", "Jupiter"):
            with self.subTest(label=expected):
                self.assertIn(expected, labels)

    def test_missions_without_anchors_return_nothing(self):
        self.assertEqual(make_animations.load_anchors("artemis2", 0.0), [])
