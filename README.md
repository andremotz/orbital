# orbital
Orbital, a N-Body Gravitation simulator

It was the Indian Space Agency’s Chandrayaan-2 mission that another time picked up my interest: If you have seen their impressive trans moon injection-manoeuvres you get the idea how impressive and interesting such mission-planning can be.

## done so far
- Implement simple Newton-laws
- N-Bodies: Rocket should rotate around Moon, Moon should rotate around Earth, Earth should rotate around Sun
- Correct Runge-Kutta 4th order, integrating all bodies simultaneously (verified 4th order convergence)
- 3D state vectors, so inclined orbits are representable — the Moon's orbit carries its real 5.145° tilt against the ecliptic
- Rust kernel via PyO3 for the RK4 step, kept bit-identical to the Python path by parity tests (measured ~7.4x speedup on 4 bodies)
- Mission- & object-data moved from source-code to external JSON config (`data/scenarios/`)
- NASA Horizons integration — real initial states, and Chandrayaan-2's actually flown trajectory as ground truth
- Burn profile derived *from* that trajectory: propagating ballistically between ephemeris samples and booking the unexplained velocity change as Δv recovers all six published ISRO manoeuvres to within minutes
- Earth's J2 oblateness, and standard gravitational parameters (GM) instead of mass × G
- Verification in layers: analytic kernel checks, mission milestones, and tracking against the real trajectory

## in progress
- Implement simple UI “Cockpit” for zoom & focus-control, visualise interesting data like individual distances, polar-coordinates
- Visualise several interesting cases, eg. Chandrayaan-2, Apollo 13, Voyager 1/2, …

## backlog/nice to have
- **targeting** — the biggest remaining gap. Burns fire at fixed absolute times, so once the trajectory drifts even slightly they hit the wrong orbital phase and the orbit raising stops working. Real missions re-target continuously. Firing burns at perigee rather than by the clock would already help a lot.
- more perturbations: the other planets, solar radiation pressure, higher terms of Earth's gravity field. A few m/s per perigee pass are still unaccounted for.
- a 3D view — the simulation is 3D, but every view still projects onto the ecliptic
- collision response — impacts are currently detected and reported, but not physically resolved

## how well does it actually work?

`python verification.py` compares a run against the real Chandrayaan-2
trajectory from JPL Horizons. Starting from real initial states, the purely
ballistic phase tracks reality to **545 km after three days** — on a trajectory
that swings between 6,550 and 51,500 km altitude.

After the first burn it diverges, and honestly so: the manoeuvres replay at
fixed absolute times without any targeting, so a small phase drift means the
burn no longer happens at perigee where it would raise the apogee. The real
apogee climbs to 148,000 km; the simulated one stays near 61,000 km. That gap
is a guidance problem, not a physics one — which is exactly what the layered
verification is there to tell apart.

## running it

```bash
python -m unittest discover tests   # full test suite
python verification.py              # mission verification report
./build_rust_kernel.sh              # optional: build the Rust kernel
python main_matplotlib.py           # matplotlib visualisation
```

Simulation data lives in `data/scenarios/*.json` — all SI units, with sources
and known limitations recorded alongside the values.

## animations
[![Orbital Earth around Sun](https://img.youtube.com/vi/Tnh3-dnT3iw/0.jpg)](https://www.youtube.com/watch?v=Tnh3-dnT3iw)

[![Orbital Rocket around Earth](https://img.youtube.com/vi/6ElpsQva-jI/0.jpg)](https://www.youtube.com/watch?v=6ElpsQva-jI)

## out of scope
NASA and other space-agencies have their own useful and more precise tools like GMAT. Hence, it makes no sense to replace their tools.
