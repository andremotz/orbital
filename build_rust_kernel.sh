#!/bin/bash
set -euo pipefail

# Build-Script für den Rust-Kernel
echo "🔧 Kompiliere Rust-Kernel für Orbital-Simulation..."

cd "$(dirname "$0")"

if ! command -v cargo &> /dev/null; then
    echo "❌ Rust ist nicht installiert!"
    echo "   Installiere Rust mit: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

# Gegen denselben Interpreter bauen, der die Simulation ausführt. Sonst
# kompiliert PyO3 gegen eine andere Python-Version als die, die das Modul
# später lädt, und der Import scheitert.
if [ -n "${PYO3_PYTHON:-}" ]; then
    PYTHON="$PYO3_PYTHON"
elif [ -x ".venv/bin/python" ]; then
    PYTHON="$(pwd)/.venv/bin/python"
else
    PYTHON="$(command -v python3)"
fi

echo "🐍 Baue gegen: $PYTHON ($("$PYTHON" --version 2>&1))"

cd rust_kernel
PYO3_PYTHON="$PYTHON" cargo build --release

# Python importiert Extensions nur als .so -- auch auf macOS, wo cargo eine
# .dylib erzeugt. Die Datei muss zudem exakt so heißen wie das Modul.
BUILT=""
for candidate in target/release/liborbital_rust_kernel.so \
                 target/release/liborbital_rust_kernel.dylib; do
    if [ -f "$candidate" ]; then
        BUILT="$candidate"
        break
    fi
done

if [ -z "$BUILT" ]; then
    echo "❌ Kompilat nicht gefunden!"
    exit 1
fi

cp "$BUILT" ../orbital_rust_kernel.so
echo "📁 Bibliothek nach orbital_rust_kernel.so kopiert"

cd ..
if "$PYTHON" -c "import orbital_rust_kernel" 2>/dev/null; then
    echo "✅ Rust-Kernel erfolgreich kompiliert und importierbar!"
else
    echo "❌ Kompilat lässt sich nicht importieren!"
    "$PYTHON" -c "import orbital_rust_kernel"
    exit 1
fi

echo ""
echo "🎯 Nächste Schritte:"
echo "   1. Paritätstest:  $PYTHON -m unittest discover tests"
echo "   2. Benchmark:     $PYTHON main_rust_accelerated.py benchmark"
