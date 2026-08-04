"""Gemeinsames Erscheinungsbild für Abbildungen und Animationen.

Farben und Achsenstil liegen hier, damit Standbilder und Animationen nicht
auseinanderlaufen. Die Zuordnung ist durchgehend dieselbe: blau ist die
Wirklichkeit, orange die Simulation, grün eine Referenz oder das erwartete
Verhalten, rot ein Manöver oder eine Abweichung.

Dieses Modul legt bewusst kein matplotlib-Backend fest. Ein Skript, das nur
Dateien schreibt, wählt "Agg"; die Live-Vorschau braucht dagegen ein
interaktives Backend, und ein hier erzwungenes Agg würde sie unmöglich machen.
"""

BACKGROUND = "#111318"
FOREGROUND = "#e8e8ea"
GRID = "#2a2d35"

REAL = "#4da3ff"
SIMULATED = "#ff9d4d"
ACCENT = "#5ddba0"
WARN = "#ff6b6b"

# Feste Farbe je Himmelskörper. Mitlaufende Namen im Bild sind bei mehreren
# Körpern nicht zu beherrschen -- sie überlappen, verdecken die Bahn oder
# laufen aus dem Diagramm. Eine feste Legende und wiedererkennbare Farben
# lösen dasselbe Problem, ohne sich zu bewegen.
#
# Keine davon darf REAL oder SIMULATED zu nahe kommen: diese beiden gehören
# den Bahnen, und eine Verwechslung zwischen Körper und Bahn wäre schlimmer
# als zwei ähnliche Planeten.
BODY_COLOURS = {
    "Sun": "#ffd24d",
    "Mercury": "#9aa0a6",
    "Venus": "#e8c39e",
    "Earth": "#6fd7e8",
    "Moon": "#d8d8dc",
    "Mars": "#e07a5f",
    "Jupiter": "#c9a227",
    "Saturn": "#c2b280",
    "Titan": "#a8b5a2",
}

# Für Körper ohne eigenen Eintrag -- etwa Raumfahrzeuge, die ohnehin in der
# Farbe der Simulation gezeichnet werden
UNKNOWN_BODY = "#8f96a3"


def body_colour(name):
    """Farbe eines Himmelskörpers, mit Rückfall auf ein neutrales Grau."""
    return BODY_COLOURS.get(name, UNKNOWN_BODY)


def style_axes(axes, title, xlabel, ylabel):
    """Setzt Hintergrund, Beschriftung und Gitter auf das gemeinsame Schema."""
    axes.set_facecolor(BACKGROUND)
    axes.set_title(title, color=FOREGROUND, fontsize=13, pad=12)
    axes.set_xlabel(xlabel, color=FOREGROUND, fontsize=10)
    axes.set_ylabel(ylabel, color=FOREGROUND, fontsize=10)
    axes.tick_params(colors=FOREGROUND, labelsize=9)
    axes.grid(True, color=GRID, linewidth=0.6)
    for spine in axes.spines.values():
        spine.set_color(GRID)


def style_legend(axes, fontsize=9, **kwargs):
    """Legende im dunklen Schema; matplotlib färbt den Text sonst schwarz."""
    legend = axes.legend(facecolor=BACKGROUND, edgecolor=GRID,
                         fontsize=fontsize, **kwargs)
    for text in legend.get_texts():
        text.set_color(FOREGROUND)
    return legend
