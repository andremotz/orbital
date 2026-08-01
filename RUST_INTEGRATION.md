# 🚀 Rust-Integration für Orbital-Simulation

Diese Integration bringt die Performance-kritischen Runge-Kutta-Berechnungen in einen Rust-Kernel, um die Simulationsgeschwindigkeit erheblich zu verbessern.

## 🎯 Warum Rust?

- **Performance**: 5-50x schneller als Python für numerische Berechnungen
- **Speichersicherheit**: Keine Memory-Leaks oder Buffer-Overflows
- **Parallele Verarbeitung**: Effiziente Multi-Threading-Unterstützung
- **Nahtlose Integration**: PyO3 ermöglicht einfache Python-Bindings

## 📁 Projektstruktur

```
orbital/
├── rust_kernel/                 # Rust-Kernel für RK4-Berechnungen
│   ├── Cargo.toml              # Rust-Projektkonfiguration
│   └── src/lib.rs              # Hauptimplementierung
├── rust_integration.py         # Python-Interface für Rust-Kernel
├── main_rust_accelerated.py    # Beschleunigte Hauptsimulation (pygame)
├── main_matplotlib_rust.py     # Beschleunigte matplotlib-Visualisierung
├── rust_trail_optimizer.py     # Optimierte Trail-Verarbeitung
├── test_rust_integration.py    # Test-Suite für Integration
├── test_matplotlib_rust.py     # Test-Suite für matplotlib
├── build_rust_kernel.sh        # Build-Script
└── RUST_INTEGRATION.md         # Diese Datei
```

## 🛠️ Installation

### 1. Rust installieren

```bash
# Rust installieren
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env

# Prüfen
cargo --version
```

### 2. Rust-Kernel kompilieren

```bash
./build_rust_kernel.sh
```

Das Script baut gegen denselben Interpreter, der die Simulation ausführt
(bevorzugt `.venv/bin/python`), legt das Ergebnis als `orbital_rust_kernel.so`
ab und prüft, dass es sich importieren lässt.

Zwei Fallstricke, die das Script abnimmt:

- **Dateiendung**: Python importiert Extensions nur als `.so`. Auf macOS
  erzeugt cargo aber eine `.dylib` -- die muss umbenannt werden, sonst bleibt
  der Kernel unsichtbar.
- **Linker**: Auf macOS darf eine Python-Extension nicht gegen libpython
  linken. `rust_kernel/.cargo/config.toml` setzt dafür
  `-undefined dynamic_lookup`; ohne das bricht der Linker mit
  "symbol(s) not found" ab.

### 3. Python-Dependencies

Keine zusätzlichen. PyO3 und die numpy-Bindings sind Rust-Crates und werden
von cargo geholt; auf Python-Seite genügt das `numpy` aus `requirements.txt`.

PyO3 muss die verwendete Python-Version unterstützen -- die Crates in
`Cargo.toml` sind auf 0.26 gepinnt, was Python bis 3.14 abdeckt.

## 🚀 Verwendung

### Standard-Simulation mit Rust-Beschleunigung

```bash
python main_rust_accelerated.py
```

**Neue Tasten:**
- `b`: Performance-Benchmark ausführen
- `r`: Zwischen Rust und Python umschalten

### Rust-beschleunigte matplotlib-Visualisierung

```bash
python main_matplotlib_rust.py
```

**Erweiterte Tasten:**
- `t`: Zwischen Rust und Python umschalten
- `b`: Performance-Benchmark ausführen
- `SPACE`: Pause/Play
- `+/-`: Zoom In/Out
- `o`: Focus wechseln
- `↑/↓`: Geschwindigkeit ändern
- `r`: Simulation zurücksetzen

### Dedizierter Benchmark-Modus

```bash
python main_rust_accelerated.py benchmark
```

### Integration in bestehende Simulation

```python
from rust_integration import RustAcceleratedIntegrator

# Erstelle beschleunigten Integrator
integrator = RustAcceleratedIntegrator(use_rust=True)

# Verwende statt calculate_state_new
integrator.calculate_states_batch(massive_objects, time_step)
```

## 📊 Performance-Vergleich

### Gemessene Werte

Gemessen auf Apple Silicon, 4 Körper, identische Startbedingungen für beide
Läufe (der Benchmark arbeitet auf Kopien, siehe `MassiveObject.copy()`):

| Szenario | Python | Rust | Speedup |
|----------|--------|------|---------|
| 4 Objekte, 20000 Schritte | 0.688s | 0.093s | **7.4x** |

Der Python-Pfad ist über NumPy vektorisiert, deshalb fällt der Vorsprung
kleiner aus, als ein Vergleich gegen Schleifen-Code vermuten ließe. Bei
deutlich mehr Körpern verschiebt sich das Bild zugunsten von Rust, weil der
Aufwand quadratisch mit der Körperzahl wächst.

> Frühere Fassungen dieses Dokuments nannten 5–50x. Diese Zahlen waren nicht
> gemessen, und der damalige Benchmark verglich zwei *unterschiedliche*
> Verfahren auf *unterschiedlichen* Daten — die Python- und Rust-Kernel
> rechneten nicht dasselbe, und beide Läufe teilten sich dieselben Objekte.

### Benchmark ausführen

```python
from rust_integration import PerformanceBenchmark
from data.celestial_objects import get_massive_objects

benchmark = PerformanceBenchmark()
objects = get_massive_objects()
results = benchmark.benchmark_simulation(objects, time_steps=1000)
```

## 🔧 Technische Details

### Rust-Implementierung

- **Algorithmus**: identisches RK4 wie Python -- alle Körper werden gemeinsam
  durch die vier Stufen gezogen, Beschleunigungen sind echte SI-Werte, und der
  Manöver-Schub geht als Zusatzbeschleunigung ein.
- **Absicherung**: `tests/test_rust_parity.py` hält beide Implementierungen
  aufeinander fest -- ein Schritt bis auf 1e-12, 5000 Schritte bis auf 1e-9.
  Ohne diesen Test ist ein Geschwindigkeitsvergleich wertlos, weil er sonst
  zwei verschiedene Verfahren vergleicht.
- **Optimierungen**:
  - Nur die obere Dreiecksmatrix der Paare, Newtons drittes Gesetz halbiert
    die Wurzelberechnungen
  - GIL wird für die Zahlenarbeit freigegeben (`Python::detach`)
  - Formprüfung der Eingabe-Arrays statt ungeprüfter `as_slice()`-Zugriffe

Rayon wurde entfernt: die frühere Parallelisierung lief über die Körper, was
bei simultaner Integration falsch ist und bei vier Körpern ohnehin nur
Overhead bedeutet.

### Python-Bindings

- **PyO3**: Nahtlose Integration zwischen Rust und Python
- **NumPy**: Effiziente Array-Operationen
- **Fallback**: Automatischer Wechsel zu Python bei Fehlern

### Speicherverwaltung

- **Rust**: Automatische Speicherverwaltung ohne Garbage Collection
- **Python**: Minimale Kopien, direkte Array-Operationen
- **Interop**: Zero-copy-Übertragung zwischen Rust und Python

## 🐛 Troubleshooting

### Rust-Kernel kompiliert nicht

```bash
# Prüfe Rust-Installation
cargo --version

# Aktualisiere Rust
rustup update

# Clean build
cd rust_kernel
cargo clean
cargo build --release
```

### Python kann Rust-Kernel nicht laden

```bash
# Prüfe ob Bibliothek existiert
ls -la orbital_rust_kernel.*

# Setze Python-Pfad
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Teste Import
python -c "import orbital_rust_kernel; print('OK')"
```

### Performance ist nicht besser

1. **Prüfe ob Rust verwendet wird**: Drücke `r` in der Simulation
2. **Kompiliere mit Optimierungen**: `cargo build --release`
3. **Prüfe Benchmark-Ergebnisse**: Führe `python main_rust_accelerated.py benchmark` aus

## 🔮 Erweiterungsmöglichkeiten

### Weitere Optimierungen

1. **SIMD-Instruktionen**: Explizite Nutzung von AVX/SSE
2. **GPU-Beschleunigung**: CUDA/OpenCL-Integration
3. **Adaptive Zeitschritte**: Variable Schrittweiten basierend auf Genauigkeit
4. **Hierarchische Algorithmen**: Barnes-Hut oder Fast Multipole Method

### Zusätzliche Features

1. **Mehrkörper-Problem**: Effiziente N-Body-Simulationen
2. **Kollisionserkennung**: Physikalische Interaktionen
3. **Lagrange-Punkte**: Spezielle Bahnberechnungen
4. **Relativistische Effekte**: Einstein'sche Korrekturen

## 📚 Lernressourcen

### Rust lernen

- [Rust Book](https://doc.rust-lang.org/book/)
- [Rust by Example](https://doc.rust-lang.org/rust-by-example/)
- [PyO3 Documentation](https://pyo3.rs/)

### Numerische Integration

- [Runge-Kutta Methods](https://en.wikipedia.org/wiki/Runge%E2%80%93Kutta_methods)
- [N-Body Problem](https://en.wikipedia.org/wiki/N-body_problem)
- [Orbital Mechanics](https://en.wikipedia.org/wiki/Orbital_mechanics)

## 🤝 Beitragen

1. Fork das Repository
2. Erstelle einen Feature-Branch
3. Implementiere Verbesserungen
4. Führe Tests aus
5. Erstelle Pull Request

## 📄 Lizenz

Gleiche Lizenz wie das Hauptprojekt.

---

**Viel Spaß beim Lernen von Rust und der Beschleunigung deiner Orbital-Simulation! 🚀**
