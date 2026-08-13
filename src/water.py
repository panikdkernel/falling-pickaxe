import pygame
import pymunk
import random

class WaterParticle:
    def __init__(self, space, x, y, radius=12, lifespan=8000):
        self.space = space
        self.radius = radius
        self.lifespan = lifespan
        self.spawn_time = pygame.time.get_ticks()
        self.dead = False

        mass = 5
        inertia = pymunk.moment_for_circle(mass, 0, radius, (0, 0))
        self.body = pymunk.Body(mass, inertia)
        self.body.position = x, y
        # Give it a slight random downward velocity so it splashes
        self.body.velocity = (random.uniform(-100, 100), random.uniform(50, 300))

        self.shape = pymunk.Circle(self.body, radius, (0, 0))
        self.shape.elasticity = 0.0 # No bounciness, liquids don't bounce
        self.shape.friction = 0.0   # Zero friction so it flows perfectly
        self.shape.collision_type = 4 # Water collision type
        self.space.add(self.body, self.shape)

    def update(self, current_time=None):
        if self.dead:
            return
            
        if current_time is None:
            current_time = pygame.time.get_ticks()
            
        if current_time - self.spawn_time >= self.lifespan:
            self.dead = True
            self.space.remove(self.body, self.shape)

    @staticmethod
    def draw_fluid(water_particles, screen, camera):
        if not water_particles:
            return
            
        # We assume all particles spawn around the same time for the wave, so we use the first one for age/alpha
        first_wp = water_particles[0]
        current_time = pygame.time.get_ticks()
        age = current_time - first_wp.spawn_time
        alpha = 180
        if age > first_wp.lifespan - 2000:
            progress = (age - (first_wp.lifespan - 2000)) / 2000
            alpha = int(180 * (1 - progress))
            alpha = max(0, min(255, alpha))
            
        color = (0, 150, 255, alpha)
        
        # We need a surface for the fluid to support alpha properly
        # To optimize, we can draw directly to screen with a solid color, but alpha looks better.
        # However, drawing many alpha lines on a large surface is slow. Let's do it on a screen-sized surface once.
        # screen is already passed in as internal_surface, which supports blitting.
        # If we draw directly to screen, the overlapping alpha will stack and look messy.
        # So we draw to a temporary surface.
        w, h = screen.get_size()
        fluid_surface = pygame.Surface((w, h), pygame.SRCALPHA)
        
        import math
        draw_radius = int(water_particles[0].radius * 1.8)
        max_dist = draw_radius * 2.8
        line_width = int(draw_radius * 1.8)
        
        # Precompute screen coordinates
        coords = []
        for wp in water_particles:
            if not wp.dead:
                px = int(wp.body.position.x - camera.offset_x)
                py = int(wp.body.position.y - camera.offset_y)
                coords.append((px, py))
                pygame.draw.circle(fluid_surface, color, (px, py), draw_radius)
                
        # Draw bridges between close particles
        for i in range(len(coords)):
            x1, y1 = coords[i]
            for j in range(i + 1, len(coords)):
                x2, y2 = coords[j]
                # Fast distance check using bounding box first
                if abs(x1 - x2) < max_dist and abs(y1 - y2) < max_dist:
                    dist = math.hypot(x2 - x1, y2 - y1)
                    if dist < max_dist:
                        pygame.draw.line(fluid_surface, color, (x1, y1), (x2, y2), line_width)
                        
        screen.blit(fluid_surface, (0, 0))
