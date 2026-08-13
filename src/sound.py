import pygame

class SoundManager:
    def __init__(self):
        self.sounds = {}
        self.initialized = False
        try:
            pygame.mixer.init()  # Initialize the mixer
            pygame.mixer.set_num_channels(128)
            self.initialized = True
        except pygame.error as e:
            print(f"Warning: Could not initialize audio device: {e}")
            print("Running in silent mode.")

    def load_sound(self, name, path, volume=1.0):
        """Load a sound and set its volume"""
        if not self.initialized:
            return
        try:
            sound = pygame.mixer.Sound(str(path))
            sound.set_volume(volume)
            self.sounds[name] = sound
        except pygame.error as e:
            print(f"Failed to load sound {name}: {e}")

    def play_sound(self, name, loop=False):
        """Play a loaded sound"""
        if not self.initialized:
            return
        if name in self.sounds:
            self.sounds[name].play(loops=-1 if loop else 0)

    def stop_sound(self, name):
        """Stop a playing sound"""
        if not self.initialized:
            return
        if name in self.sounds:
            self.sounds[name].stop()

    def stop_all(self):
        """Stop all sounds"""
        if not self.initialized:
            return
        pygame.mixer.stop()
