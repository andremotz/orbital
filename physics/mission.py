def get_acceleration_by_mission(massive_object, time_step):
    """Fügt Beschleunigung durch Missionsdaten hinzu"""
    force_extra = 0.0

    list_maneuvers = massive_object.list_maneuvers

    if massive_object.name == "Chandrayaan-2":
        test = 1

    if len(list_maneuvers) > 0:
        test = 1

        for maneuver in list_maneuvers:
            if time_step > maneuver.time_start and time_step < maneuver.time_duration:
                force_extra += maneuver.force
                print("adding extra force: %s", force_extra)

    return force_extra 