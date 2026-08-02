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
- Two-layer verification: analytic kernel checks + mission scenarios with historical milestones

## in progress
- Implement simple UI “Cockpit” for zoom & focus-control, visualise interesting data like individual distances, polar-coordinates
- Visualise several interesting cases, eg. Chandrayaan-2, Apollo 13, Voyager 1/2, …

## backlog/nice to have
- connect to NASA Horizons-data :-) — now that states are 3D, real ephemerides can be used directly
- real burn profile for Chandrayaan-2: the six Earth-bound orbit raisings and the trans-lunar injection are still placeholders, so the probe never leaves Earth orbit
- a 3D view — the simulation is 3D, but every view still projects onto the ecliptic
- collision response — impacts are currently detected and reported, but not physically resolved

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
