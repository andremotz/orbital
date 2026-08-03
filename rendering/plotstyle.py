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


def style_legend(axes, **kwargs):
    """Legende im dunklen Schema; matplotlib färbt den Text sonst schwarz."""
    legend = axes.legend(facecolor=BACKGROUND, edgecolor=GRID, fontsize=9, **kwargs)
    for text in legend.get_texts():
        text.set_color(FOREGROUND)
    return legend
