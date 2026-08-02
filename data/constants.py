# Physikalische Konstanten
CONST_GRAVITY = 6.6743 * 10 ** -11

# Zustände werden dreikomponentig geführt. Die Simulation rechnete früher in
# der Ebene; das schloss reale Bahnen aus, weil etwa die Mondbahn rund 5,1
# Grad gegen die Ekliptik geneigt ist und ein Mondtransfer damit zwingend
# Anteile ausserhalb der Ebene hat.
DIMENSIONS = 3

# Fenster-Größen
WIDTH, HEIGHT = 900, 900
WIDTHD2, HEIGHTD2 = WIDTH/2., HEIGHT/2. 