"""Open an anim_*.blend looking through the camera, material shading, and start playback.

  blender.exe assets/models/anim_truck.blend --python assets/blender/play.py
"""
import bpy


def _play():
    win = bpy.context.window_manager.windows[0]
    for area in win.screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            space.region_3d.view_perspective = "CAMERA"
            space.shading.type = "MATERIAL"
            space.overlay.show_overlays = False
    with bpy.context.temp_override(window=win, screen=win.screen):
        bpy.ops.screen.animation_play()
    return None


bpy.app.timers.register(_play, first_interval=1.5)
