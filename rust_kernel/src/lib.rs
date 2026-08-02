//! Rust-Kernel für die RK4-Integration der Orbital-Simulation.
//!
//! Die Semantik ist bewusst identisch zu `physics/integrator.py`: alle Körper
//! werden gemeinsam durch die vier RK4-Stufen gezogen, Beschleunigungen sind
//! echte SI-Werte in m/s^2, und der Manöver-Schub geht als konstante
//! Zusatzbeschleunigung über den gesamten Schritt ein. Weicht eine der beiden
//! Implementierungen ab, schlägt `tests/test_rust_parity.py` fehl.

use numpy::{PyArray1, PyArray2, PyArrayMethods, PyUntypedArrayMethods};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// Komponenten je Zustandsvektor. Muss mit `DIMENSIONS` in
/// `data/constants.py` übereinstimmen.
const DIMENSIONS: usize = 3;

/// Abplattung eines Körpers: Koeffizient J2, Äquatorradius und Polrichtung.
///
/// Die Polrichtung ist ein Einheitsvektor im Bezugssystem der Simulation.
/// Ein `j2` von null schaltet den Beitrag ab.
pub struct Oblateness {
    pub j2: f64,
    pub equatorial_radius: f64,
    pub pole: [f64; DIMENSIONS],
}

/// Gravitative Beschleunigung aller Körper in m/s^2.
///
/// `positions` und das Ergebnis sind flach als [x0, y0, z0, x1, y1, z1, ...]
/// abgelegt. `mus` sind die Standard-Gravitationsparameter GM, nicht Massen.
/// Der Schub wird direkt aufaddiert, damit die Stufen ihn mitführen.
fn accelerations(
    positions: &[f64],
    mus: &[f64],
    thrust: &[f64],
    oblateness: &[Oblateness],
    out: &mut [f64],
) {
    let n = mus.len();
    out.copy_from_slice(thrust);

    let mut delta = [0.0; DIMENSIONS];

    for i in 0..n {
        // Nur die obere Dreiecksmatrix auswerten und Newtons drittes Gesetz
        // ausnutzen -- halbiert die Anzahl der Wurzelberechnungen.
        for j in (i + 1)..n {
            let mut distance_squared = 0.0;
            for axis in 0..DIMENSIONS {
                let component = positions[j * DIMENSIONS + axis] - positions[i * DIMENSIONS + axis];
                delta[axis] = component;
                distance_squared += component * component;
            }

            if distance_squared == 0.0 {
                continue;
            }

            let inverse_cube = 1.0 / (distance_squared * distance_squared.sqrt());
            let pull_i = mus[j] * inverse_cube;
            let pull_j = mus[i] * inverse_cube;

            for axis in 0..DIMENSIONS {
                out[i * DIMENSIONS + axis] += pull_i * delta[axis];
                out[j * DIMENSIONS + axis] -= pull_j * delta[axis];
            }
        }
    }

    add_oblateness(positions, mus, oblateness, out);
}

/// Zusatzbeschleunigung durch die Äquatorwulst abgeplatteter Körper.
///
/// Die Wulst liegt um die Rotationsachse, die im Bezugssystem der Simulation
/// im Allgemeinen nicht mit der z-Achse zusammenfällt. Deshalb wird der
/// Abstandsvektor in Anteile längs und quer zur Polachse zerlegt.
fn add_oblateness(
    positions: &[f64],
    mus: &[f64],
    oblateness: &[Oblateness],
    out: &mut [f64],
) {
    let n = mus.len();

    for (source, shape) in oblateness.iter().enumerate() {
        if shape.j2 == 0.0 {
            continue;
        }

        let scale = -1.5 * shape.j2 * mus[source] * shape.equatorial_radius
            * shape.equatorial_radius;

        for target in 0..n {
            if target == source {
                continue;
            }

            let mut offset = [0.0; DIMENSIONS];
            let mut distance_squared = 0.0;
            let mut along_pole = 0.0;
            for axis in 0..DIMENSIONS {
                let component =
                    positions[target * DIMENSIONS + axis] - positions[source * DIMENSIONS + axis];
                offset[axis] = component;
                distance_squared += component * component;
                along_pole += component * shape.pole[axis];
            }

            if distance_squared == 0.0 {
                continue;
            }

            let distance = distance_squared.sqrt();
            let ratio_squared = (along_pole / distance) * (along_pole / distance);
            let factor = scale / (distance_squared * distance_squared * distance);

            let perpendicular_weight = 1.0 - 5.0 * ratio_squared;
            let pole_weight = 3.0 - 5.0 * ratio_squared;

            for axis in 0..DIMENSIONS {
                let perpendicular = offset[axis] - along_pole * shape.pole[axis];
                out[target * DIMENSIONS + axis] += factor
                    * (perpendicular_weight * perpendicular
                        + pole_weight * along_pole * shape.pole[axis]);
            }
        }
    }
}

/// Führt einen RK4-Schritt für das gesamte System aus.
///
/// `positions` und `velocities` werden in place fortgeschrieben.
pub fn rk4_step(
    positions: &mut [f64],
    velocities: &mut [f64],
    mus: &[f64],
    thrust: &[f64],
    oblateness: &[Oblateness],
    time_step: f64,
) {
    let len = positions.len();
    let half_step = time_step / 2.0;

    let mut scratch_positions = vec![0.0; len];
    let mut scratch_velocities = vec![0.0; len];

    // k*_location ist die Geschwindigkeit der Stufe, k*_velocity ihre Beschleunigung
    let mut k1_acceleration = vec![0.0; len];
    let mut k2_acceleration = vec![0.0; len];
    let mut k3_acceleration = vec![0.0; len];
    let mut k4_acceleration = vec![0.0; len];

    accelerations(positions, mus, thrust, oblateness, &mut k1_acceleration);
    let k1_velocity = velocities.to_vec();

    for i in 0..len {
        scratch_positions[i] = positions[i] + k1_velocity[i] * half_step;
        scratch_velocities[i] = velocities[i] + k1_acceleration[i] * half_step;
    }
    accelerations(&scratch_positions, mus, thrust, oblateness, &mut k2_acceleration);
    let k2_velocity = scratch_velocities.clone();

    for i in 0..len {
        scratch_positions[i] = positions[i] + k2_velocity[i] * half_step;
        scratch_velocities[i] = velocities[i] + k2_acceleration[i] * half_step;
    }
    accelerations(&scratch_positions, mus, thrust, oblateness, &mut k3_acceleration);
    let k3_velocity = scratch_velocities.clone();

    for i in 0..len {
        scratch_positions[i] = positions[i] + k3_velocity[i] * time_step;
        scratch_velocities[i] = velocities[i] + k3_acceleration[i] * time_step;
    }
    accelerations(&scratch_positions, mus, thrust, oblateness, &mut k4_acceleration);
    let k4_velocity = scratch_velocities.clone();

    let weight = time_step / 6.0;
    for i in 0..len {
        positions[i] += weight
            * (k1_velocity[i] + 2.0 * (k2_velocity[i] + k3_velocity[i]) + k4_velocity[i]);
        velocities[i] += weight
            * (k1_acceleration[i]
                + 2.0 * (k2_acceleration[i] + k3_acceleration[i])
                + k4_acceleration[i]);
    }
}

/// Ein RK4-Schritt für das gesamte System.
///
/// Erwartet `mus` (n,) als Standard-Gravitationsparameter GM, `positions`
/// (n, 3), `velocities` (n, 3) und `thrust` (n, 3) in m/s^2. `j2` (n,),
/// `equatorial_radii` (n,) und `poles` (n, 3) beschreiben die Abplattung;
/// ein j2 von null lässt den Körper als Kugel gelten. Zurück kommen neue
/// Positionen und Geschwindigkeiten als frische Arrays.
#[pyfunction]
fn rk4_step_python(
    py: Python<'_>,
    mus: &Bound<'_, PyArray1<f64>>,
    positions: &Bound<'_, PyArray2<f64>>,
    velocities: &Bound<'_, PyArray2<f64>>,
    thrust: &Bound<'_, PyArray2<f64>>,
    j2: &Bound<'_, PyArray1<f64>>,
    equatorial_radii: &Bound<'_, PyArray1<f64>>,
    poles: &Bound<'_, PyArray2<f64>>,
    time_step: f64,
) -> PyResult<(Py<PyArray2<f64>>, Py<PyArray2<f64>>)> {
    let n_objects = mus.len();

    for (name, array) in [
        ("positions", positions),
        ("velocities", velocities),
        ("thrust", thrust),
        ("poles", poles),
    ] {
        let shape = array.shape();
        if shape != [n_objects, DIMENSIONS] {
            return Err(PyValueError::new_err(format!(
                "{} muss die Form ({}, {}) haben, ist aber {:?}",
                name, n_objects, DIMENSIONS, shape
            )));
        }
    }

    for (name, array) in [("j2", j2), ("equatorial_radii", equatorial_radii)] {
        if array.len() != n_objects {
            return Err(PyValueError::new_err(format!(
                "{} muss {} Einträge haben, hat aber {}",
                name,
                n_objects,
                array.len()
            )));
        }
    }

    // to_vec() verlangt zusammenhängenden Speicher und meldet sonst sauber
    // einen Fehler, statt wie as_slice() undefiniertes Verhalten zu riskieren.
    let mus_vec = mus.to_vec()?;
    let mut positions_vec = positions.to_vec()?;
    let mut velocities_vec = velocities.to_vec()?;
    let thrust_vec = thrust.to_vec()?;
    let j2_vec = j2.to_vec()?;
    let radii_vec = equatorial_radii.to_vec()?;
    let poles_vec = poles.to_vec()?;

    let oblateness: Vec<Oblateness> = (0..n_objects)
        .map(|i| {
            let mut pole = [0.0; DIMENSIONS];
            pole.copy_from_slice(&poles_vec[i * DIMENSIONS..(i + 1) * DIMENSIONS]);
            Oblateness {
                j2: j2_vec[i],
                equatorial_radius: radii_vec[i],
                pole,
            }
        })
        .collect();

    // Der GIL wird für die reine Zahlenarbeit freigegeben
    py.detach(|| {
        rk4_step(
            &mut positions_vec,
            &mut velocities_vec,
            &mus_vec,
            &thrust_vec,
            &oblateness,
            time_step,
        )
    });

    let new_positions = PyArray2::from_vec2(py, &to_rows(&positions_vec))?;
    let new_velocities = PyArray2::from_vec2(py, &to_rows(&velocities_vec))?;

    Ok((new_positions.into(), new_velocities.into()))
}

/// Formt einen flachen [x0, y0, z0, x1, ...]-Puffer in Zeilen um.
fn to_rows(flat: &[f64]) -> Vec<Vec<f64>> {
    flat.chunks(DIMENSIONS).map(|row| row.to_vec()).collect()
}

#[pymodule]
fn orbital_rust_kernel(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(rk4_step_python, m)?)?;
    Ok(())
}
