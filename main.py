import pygame
from collections import defaultdict

# Import der modularen Komponenten
from data.constants import WIDTH, HEIGHT
from data.celestial_objects import get_massive_objects
from physics.integrator import calculate_state_new
from rendering.renderer import pygame_draw


def main():
    """Hauptfunktion der Orbital-Simulation"""
    # initialize the pygame module
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    running = True
    
    #zoom = (10**-9) / 0.85 / 0.85 / 0.85 / 0.85 / 0.85 / 0.85 # Fokus Sun
    zoom = 10 ** -6 # Fokus Erde
    zoom = (10 ** -6) / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2  # Fokus Chandrayaan-2
    scroll_x = 0
    scroll_y = 0
    keysPressed = defaultdict(bool)

    list_massiveobjects = get_massive_objects()

    time = 0
    time_step = 60

    while running:
        time += time_step

        # Berechne neue Zustände für alle Objekte
        for massiveObject_1 in list_massiveobjects:
            state_new = calculate_state_new(massiveObject_1, list_massiveobjects, time_step)
            massiveObject_1.addState(state_new)

        # Event handling
        for event in pygame.event.get():
            # only do something if the event is of type QUIT
            if event.type == pygame.QUIT:
                # change the value to False, to exit the main loop
                running = False
            elif event.type in [pygame.KEYDOWN, pygame.KEYUP]:
                keysPressed[event.key] = event.type == pygame.KEYDOWN

        # Keyboard controls
        if keysPressed[pygame.K_DOWN]:
            zoom /= 0.85
            screen.fill((0, 0, 0))
        if keysPressed[pygame.K_UP]:
            zoom /= 1.2
            screen.fill((0, 0, 0))
        if keysPressed[pygame.K_ESCAPE]:
            return False
        if keysPressed[pygame.K_w]:
            scroll_y += 10
            screen.fill((0, 0, 0))
        if keysPressed[pygame.K_s]:
            scroll_y -= 10
            screen.fill((0, 0, 0))
        if keysPressed[pygame.K_a]:
            scroll_x += 10
            screen.fill((0, 0, 0))
        if keysPressed[pygame.K_d]:
            scroll_x -= 10
            screen.fill((0, 0, 0))

        # Rendering
        pygame_draw(list_massiveobjects, screen, zoom, scroll_x, scroll_y, time)


if __name__ == "__main__":
    main() 