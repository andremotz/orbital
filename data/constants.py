# Physikalische Konstanten
CONST_GRAVITY = 6.6743 * 10 ** -11

# Standard-Gravitationsparameter GM in m^3/s^2, aus JPL DE440.
#
# In der Himmelsmechanik rechnet man mit GM statt mit Masse und
# Gravitationskonstante getrennt: GM lässt sich aus Bahnbeobachtungen auf über
# zehn Stellen bestimmen, während G nur auf etwa fünf Stellen gemessen ist.
# Massen werden als GM/G abgeleitet und erben diese Unsicherheit. Rechnet man
# umgekehrt G*M, holt man sich den Fehler zurück: mit M = 1,989e30 liegt das
# Produkt um 3e-4 neben dem wahren GM der Sonne, was die Erdbahn in sechs
# Stunden bereits um knapp 0,04 m/s verfehlt.
GM_SUN = 1.32712440041279419e20
GM_EARTH = 3.98600435507e14
GM_MOON = 4.90280001963e12

# Für interplanetare Bahnen. Bei den Riesenplaneten ist es der Wert des
# jeweiligen Systems, also samt Monden -- deren Bahnen werden hier nicht
# einzeln geführt, und aus der Ferne wirkt ohnehin nur die Summe.
GM_VENUS = 3.24858592e14
GM_MARS_SYSTEM = 4.282837362e13
GM_JUPITER_SYSTEM = 1.267127641e17
GM_SATURN_SYSTEM = 3.794058484e16
GM_TITAN = 8.978138376e12

# Zustände werden dreikomponentig geführt. Die Simulation rechnete früher in
# der Ebene; das schloss reale Bahnen aus, weil etwa die Mondbahn rund 5,1
# Grad gegen die Ekliptik geneigt ist und ein Mondtransfer damit zwingend
# Anteile ausserhalb der Ebene hat.
DIMENSIONS = 3

# Fenster-Größen
WIDTH, HEIGHT = 900, 900
WIDTHD2, HEIGHTD2 = WIDTH/2., HEIGHT/2. 