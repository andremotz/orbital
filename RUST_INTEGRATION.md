# 🚀 Rust-Integration für Orbital-Simulation

Diese Integration bringt die Performance-kritischen Runge-Kutta-Berechnungen in einen Rust-Kernel, um die Simulationsgeschwindigkeit erheblich zu verbessern.

## 🎯 Warum Rust?

- **Performance**: der RK4-Schritt selbst ist 5,7x schneller, mit
  Erdabplattung rund 15x (Messung unten). Ein ganzer Missionslauf gewinnt
  derzeit nur 1,8x, weil die Manöverlogik in Python bleibt.
- **Speichersicherheit**: Keine Memory-Leaks oder Buffer-Overflows
- **Nahtlose Integration**: PyO3 ermöglicht einfache Python-Bindings

Der Kernel rechnet single-threaded; bei vier Körpern lohnt keine
Parallelisierung (siehe unten).

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
`Cargo.toml` sind auf 0.30 gepinnt; die CI baut gegen Python 3.10 und 3.14.

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

Gemessen am 2026-11-22 auf Apple Silicon mit Python 3.14, die vier Körper
des Chandrayaan-2-Szenarios, 20000 Schritte zu 60 s, bester von drei Läufen.
Jeder Lauf lädt das Szenario frisch:

| Szenario | Python | Rust | Speedup |
|----------|--------|------|---------|
| ohne Manöver, alle Körper als Kugel | 0.53s | 0.090s | **5.8x** |
| ohne Manöver, mit Erdabplattung J2 | 1.44s | 0.093s | **15.4x** |
| mit den sechs Manövern des Szenarios und J2 | 3.25s | 1.79s | **1.8x** |

`PerformanceBenchmark` ist für die letzte Zeile nicht geeignet. Er arbeitet
zwar auf Kopien (`MassiveObject.copy()`), die teilen sich aber die
Manöver-Objekte: Was der erste Lauf zündet, gilt im zweiten als bereits
gezündet. So entstand zunächst eine geschönte Messung von 2.2x (WI-007).

Die letzte Zeile ist der Fall, der in `verification.py` und `targeting.py`
tatsächlich läuft. Dort kostet nicht mehr die Integration, sondern die
Manöverlogik: Vor jedem Schritt prüft Python jeden noch ausstehenden
Periapsis-Auslöser, also Bahnelemente und Zeit bis zum Periapsis. Das macht
rund 85 µs je Schritt aus, fast zwanzigmal so viel wie der Rust-Schritt
selbst (4.5 µs); ein Profil legt rund 93 % der Laufzeit in diese Prüfung. Schneller wird
ein Missionslauf erst, wenn diese Prüfung billiger wird oder seltener läuft
(WI-012 in docs/work-items.md).

Frühere Messungen an derselben Stelle (7.0x / 12.2x, im README 7.4x) liegen
in derselben Grössenordnung wie die ersten beiden Zeilen; sie stammen von
einem anderen Stand und lassen sich nicht mehr genau nachstellen.

Die Abplattung vergrössert den Abstand: Python wertet sie über eine Schleife
je abgeplattetem Körper mit NumPy-Zwischenarrays aus, Rust erledigt sie in
derselben Schleife wie die Gravitation ohne Zwischenspeicher.

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
- **Fallback**: Ist der Kernel nicht importierbar, rechnet Python. Wirft der
  Kernel während eines Schritts eine Exception, rechnet Python diesen Schritt
  -- still, mit einer Warnung auf stdout. Ein Fehler im Kernel fällt so nur
  als langsamerer Lauf auf (WI-008).

### Speicherverwaltung

- **Rust**: Automatische Speicherverwaltung ohne Garbage Collection
- **Interop**: Keine Zero-copy-Übertragung. Python sammelt je Schritt sieben
  Arrays aus den Körperobjekten, der Kernel kopiert jedes in einen `Vec` und
  baut das Ergebnis über `Vec<Vec<f64>>` neu auf. Bei vier Körpern ist das
  billig gegen die Manöverlogik, aber nicht gratis.

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
