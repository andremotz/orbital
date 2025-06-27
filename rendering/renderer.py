import pygame
from data.constants import WIDTHD2, HEIGHTD2
from .utils import calc_days_from_time

def pygame_draw(listMassiveObjects, surface, zoom, scroll_x, scroll_y, time):
    """Zeichnet alle massiven Objekte auf dem pygame Surface"""
    currentMassiveObject_id = 0

    # Auto-follow Erde
    for currentMassiveObject in listMassiveObjects:
        if currentMassiveObject.name == "Earth":
            state_latest = currentMassiveObject.getLatestState()
            x = state_latest.vec_location[0]
            y = state_latest.vec_location[1]

            x_converted = WIDTHD2 + zoom * WIDTHD2 * (x - WIDTHD2) / WIDTHD2
            y_converted = HEIGHTD2 + zoom * HEIGHTD2 * (y - HEIGHTD2) / HEIGHTD2

            scroll_x = - (x_converted - WIDTHD2)
            scroll_y = - (y_converted - HEIGHTD2)

    # Zeichne alle Objekte
    for currentMassiveObject in listMassiveObjects:
        state_latest = currentMassiveObject.getLatestState()
        x = state_latest.vec_location[0]
        y = state_latest.vec_location[1]

        x_converted = scroll_x + WIDTHD2 + zoom * WIDTHD2 * (x-WIDTHD2) / WIDTHD2
        y_converted = scroll_y + HEIGHTD2 + zoom * HEIGHTD2 * (y-HEIGHTD2) / HEIGHTD2

        radius_converted = currentMassiveObject.radius * zoom
        color = currentMassiveObject.color

        pygame.draw.circle(surface, color,
                           (int(x_converted),
                            int(y_converted)),
                           int(radius_converted), 0)

        currentMassiveObject_id += 1

    pygame.display.flip()
    pygame.display.set_caption("days: %s, zoom: %s, time %s" %
                               (calc_days_from_time(time),
                                round(zoom, 20),
                                time)
                               ) 