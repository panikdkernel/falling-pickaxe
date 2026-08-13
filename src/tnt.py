import pygame
import pymunk
import math
import random
from constants import BLOCK_SIZE
from constants import CHUNK_HEIGHT, CHUNK_WIDTH
from chunk import chunks
from explosion import Explosion

class Tnt:
    _font = None

    def __init__(self, space, x, y, texture_atlas, atlas_items, sound_manager, owner_name=None, velocity=0, rotation=0, mass=70):
        print("Spawning TNT")
        self.texture_atlas = texture_atlas
        self.atlas_items = atlas_items

        rect = atlas_items["block"]["tnt"]  
        self.texture = texture_atlas.subsurface(rect)

        width, height = self.texture.get_size()

        self.name = "tnt"

        self.velocity = velocity
        self.rotation = rotation
        self.space = space

        inertia = pymunk.moment_for_box(mass, (width, height))
        self.body = pymunk.Body(mass, inertia)
        self.body.position = (x, y)
        self.body.angle = math.radians(rotation)

        # Create a hitbox
        self.shape = pymunk.Poly.create_box(self.body, (width, height))
        self.shape.elasticity = 1  # No bounce
        self.shape.collision_type = 3 # Identifier for collisions
        self.shape.friction = 0.7
        self.shape.block_ref = self  # Reference to the block object

        self.sound_manager = sound_manager
        self.sound_manager.play_sound("tnt")

        self.space.add(self.body, self.shape)

        handler = space.add_collision_handler(3, 2)  # TNT & Block collision
        handler.post_solve = self.on_collision

        self.detonated = False
        self.spawn_time = pygame.time.get_ticks()

        # Owner name (nick from chat)
        self.owner_name = owner_name
        if Tnt._font is None:
            Tnt._font = pygame.font.Font(None, 70)
        self.font = Tnt._font

        # The blink alpha must live in the pixels rather than come from set_alpha(). main.py's
        # internal_surface inherits the display format, which on macOS carries an alpha channel
        # that sprite blits leave at 0; a set_alpha() overlay then composites against a
        # transparent destination and renders solid white. draw() refills this each frame.
        self._overlay_surface = pygame.Surface(self.texture.get_size(), pygame.SRCALPHA)
        self._overlay_surface.fill((255, 255, 255))

    def on_collision(self, arbiter, space, data):
        # Small random rotation on collision
        self.body.angle += random.choice([0.01, -0.01])

    def _explode_with_radius(self, explosions, explosion_radius, damage_scale, particle_count):
        self.detonated = True
        radius_sq = explosion_radius * explosion_radius
        chunk_width_px = CHUNK_WIDTH * BLOCK_SIZE
        chunk_height_px = CHUNK_HEIGHT * BLOCK_SIZE

        min_chunk_x = int((self.body.position.x - explosion_radius) // chunk_width_px)
        max_chunk_x = int((self.body.position.x + explosion_radius) // chunk_width_px)
        min_chunk_y = int((self.body.position.y - explosion_radius) // chunk_height_px)
        max_chunk_y = int((self.body.position.y + explosion_radius) // chunk_height_px)

        for chunk_x in range(min_chunk_x, max_chunk_x + 1):
            for chunk_y in range(min_chunk_y, max_chunk_y + 1):
                chunk = chunks.get((chunk_x, chunk_y))
                if chunk is None:
                    continue
                for row in chunk:
                    for block in row:
                        if block is None or getattr(block, "destroyed", False):
                            continue

                        dx = block.body.position.x - self.body.position.x
                        dy = block.body.position.y - self.body.position.y
                        dist_sq = dx * dx + dy * dy

                        if dist_sq <= radius_sq:
                            distance = math.sqrt(dist_sq)
                            damage = int(100 * damage_scale * (1 - (distance / explosion_radius)))
                            block.hp -= damage

        explosion = Explosion(self.body.position, self.texture_atlas, self.atlas_items, particle_count=particle_count)
        explosions.append(explosion)

    def explode(self, explosions):
        explosion_radius = 3 * BLOCK_SIZE  # Explosion radius in pixels
        self._explode_with_radius(explosions, explosion_radius, 1, 20)

    def update(self, tnt_list, explosions, camera, current_time=None):
        if self.detonated:
            self.space.remove(self.body, self.shape)
            if self in tnt_list:
                tnt_list.remove(self)
            return

        # Limit falling speed (terminal velocity)
        if self.body.velocity.y > 1000:
            self.body.velocity = (self.body.velocity.x, 1000)

        if current_time is None:
            current_time = pygame.time.get_ticks()
        if current_time - self.spawn_time >= 4000:
            self.explode(explosions)
            camera.shake(10, 10)  # Shake camera for 10 frames with intensity 10

    def draw(self, screen, camera):
        if self.detonated:
            return

        # Draw TNT texture with rotation
        rotated_image = pygame.transform.rotate(self.texture, -math.degrees(self.body.angle))
        rect = rotated_image.get_rect(center=(self.body.position.x, self.body.position.y))
        rect.y -= camera.offset_y
        rect.x -= camera.offset_x
        screen.blit(rotated_image, rect)

        # Blinking effect: pulsating white overlay
        blink_period = 500  # 1 second cycle
        current_time = pygame.time.get_ticks() % blink_period
        brightness = (math.sin(current_time / blink_period * 2 * math.pi) + 1) / 2  # range 0-1
        alpha = int(brightness * 192)  # maximum 75% opacity

        self._overlay_surface.fill((255, 255, 255, alpha))
        rotated_overlay = pygame.transform.rotate(self._overlay_surface, -math.degrees(self.body.angle))
        overlay_rect = rotated_overlay.get_rect(center=(self.body.position.x, self.body.position.y))
        overlay_rect.y -= camera.offset_y
        overlay_rect.x -= camera.offset_x
        screen.blit(rotated_overlay, overlay_rect)

        # Draw owner name above TNT
        if self.owner_name:
            text_surface = self.font.render(self.owner_name, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(self.body.position.x - camera.offset_x, self.body.position.y - 55 - camera.offset_y))
            shadow = self.font.render(self.owner_name, True, (0, 0, 0))
            shadow_rect = shadow.get_rect(center=(self.body.position.x + 1 - camera.offset_x, self.body.position.y - 54 - camera.offset_y))
            screen.blit(shadow, shadow_rect)
            screen.blit(text_surface, text_rect)

class MegaTnt(Tnt):
    def __init__(self, space, x, y, texture_atlas, atlas_items, sound_manager, owner_name=None, velocity=0, rotation=0, mass=100):
        super().__init__(space, x, y, texture_atlas, atlas_items, sound_manager, owner_name, velocity, rotation, mass)
        print("Spawning MegaTNT")
        self.name = "mega_tnt"
        self.scale_multiplier = 2

        rect = atlas_items["block"]["mega_tnt"]
        self.texture = pygame.transform.scale_by(texture_atlas.subsurface(rect), self.scale_multiplier)

        width, height = self.texture.get_size()
        self.shape.unsafe_set_vertices(pymunk.Poly.create_box(self.body, (width, height)).get_vertices())
        self._overlay_surface = pygame.Surface(self.texture.get_size(), pygame.SRCALPHA)
        self._overlay_surface.fill((255, 255, 255))

    def explode(self, explosions):
        explosion_radius = 3 * BLOCK_SIZE * self.scale_multiplier
        self._explode_with_radius(explosions, explosion_radius, self.scale_multiplier, 40)

    def update(self, tnt_list, explosions, camera, current_time=None):
        if self.detonated:
            self.space.remove(self.body, self.shape)
            if self in tnt_list:
                tnt_list.remove(self)
            return

        # Limit falling speed (terminal velocity)
        if self.body.velocity.y > 1000:
            self.body.velocity = (self.body.velocity.x, 1000)

        if current_time is None:
            current_time = pygame.time.get_ticks()
        if current_time - self.spawn_time >= 4000:
            self.explode(explosions)
            camera.shake(15, 30)  # Shake camera for 15 frames with intensity 15

    def draw(self, screen, camera):
        if self.detonated:
            return

        rotated_image = pygame.transform.rotate(self.texture, -math.degrees(self.body.angle))
        rect = rotated_image.get_rect(center=(self.body.position.x, self.body.position.y))
        rect.y -= camera.offset_y
        rect.x -= camera.offset_x
        screen.blit(rotated_image, rect)

        # Blinking effect: pulsating white overlay
        blink_period = 500
        current_time = pygame.time.get_ticks() % blink_period
        brightness = (math.sin(current_time / blink_period * 2 * math.pi) + 1) / 2
        alpha = int(brightness * 192)

        self._overlay_surface.fill((255, 255, 255, alpha))
        rotated_overlay = pygame.transform.rotate(self._overlay_surface, -math.degrees(self.body.angle))
        overlay_rect = rotated_overlay.get_rect(center=(self.body.position.x, self.body.position.y))
        overlay_rect.y -= camera.offset_y
        overlay_rect.x -= camera.offset_x
        screen.blit(rotated_overlay, overlay_rect)

        # Draw owner name above MegaTNT
        if self.owner_name:
            text_surface = self.font.render(self.owner_name, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(self.body.position.x - camera.offset_x, self.body.position.y - 55 - camera.offset_y))
            shadow = self.font.render(self.owner_name, True, (0, 0, 0))
            shadow_rect = shadow.get_rect(center=(self.body.position.x + 1 - camera.offset_x, self.body.position.y - 54 - camera.offset_y))
            screen.blit(shadow, shadow_rect)
            screen.blit(text_surface, text_rect)

import math
import random
import pygame
import pymunk

# This code will be appended to tnt.py

class Bomb(Tnt):
    def __init__(self, space, x, y, texture_atlas, atlas_items, sound_manager, owner_name=None, velocity=0, rotation=0, mass=80):
        super().__init__(space, x, y, texture_atlas, atlas_items, sound_manager, owner_name, velocity, rotation, mass)
        self.name = "bomb"
        
        rect = atlas_items["block"]["bomb"]
        self.texture = texture_atlas.subsurface(rect)
        
        self.radius = int(self.texture.get_width() / 2)
        
        self.space.remove(self.shape)
        self.shape = pymunk.Circle(self.body, self.radius)
        self.shape.elasticity = 0.95
        self.shape.friction = 0.5
        self.shape.collision_type = 3
        self.shape.block_ref = self
        self.space.add(self.shape)
        
        self.spawn_time = pygame.time.get_ticks()

        width, height = self.texture.get_size()
        self._overlay_surface = pygame.Surface((width, height), pygame.SRCALPHA)

    def explode(self, explosions):
        explosion_radius = int(3 * BLOCK_SIZE * 1.5)
        self._explode_with_radius(explosions, explosion_radius, 2, 30)

    def update(self, tnt_list, explosions, camera, current_time=None):
        if self.detonated:
            self.space.remove(self.body, self.shape)
            if self in tnt_list:
                tnt_list.remove(self)
            return

        if current_time is None:
            current_time = pygame.time.get_ticks()
            
        if current_time - self.spawn_time >= 3000:
            self.explode(explosions)
            camera.shake(20, 20)

    def draw(self, screen, camera):
        if self.detonated:
            return
            
        # Draw Bomb texture with rotation
        rotated_image = pygame.transform.rotate(self.texture, -math.degrees(self.body.angle))
        rect = rotated_image.get_rect(center=(self.body.position.x, self.body.position.y))
        rect.y -= camera.offset_y
        rect.x -= camera.offset_x
        screen.blit(rotated_image, rect)
        
        # Blinking effect: pulsating white overlay
        blink_period = 500
        current_time = pygame.time.get_ticks() % blink_period
        brightness = (math.sin(current_time / blink_period * 2 * math.pi) + 1) / 2
        alpha = int(brightness * 192)

        self._overlay_surface.fill((0, 0, 0, 0)) # clear previous
        pygame.draw.circle(self._overlay_surface, (255, 255, 255, alpha), (self.radius, self.radius), self.radius)
        rotated_overlay = pygame.transform.rotate(self._overlay_surface, -math.degrees(self.body.angle))
        overlay_rect = rotated_overlay.get_rect(center=(self.body.position.x, self.body.position.y))
        overlay_rect.y -= camera.offset_y
        overlay_rect.x -= camera.offset_x
        screen.blit(rotated_overlay, overlay_rect)
        
        if self.owner_name:
            text_surface = self.font.render(self.owner_name, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(self.body.position.x - camera.offset_x, self.body.position.y - self.radius - 20 - camera.offset_y))
            shadow = self.font.render(self.owner_name, True, (0, 0, 0))
            shadow_rect = shadow.get_rect(center=(self.body.position.x + 1 - camera.offset_x, self.body.position.y - self.radius - 19 - camera.offset_y))
            screen.blit(shadow, shadow_rect)
            screen.blit(text_surface, text_rect)

class Meteor(Tnt):
    def __init__(self, space, x, y, texture_atlas, atlas_items, sound_manager, owner_name=None, velocity=(0, 2000), mass=500):
        super().__init__(space, x, y, texture_atlas, atlas_items, sound_manager, owner_name, 0, 0, mass)
        self.name = "meteor"
        
        self.body.velocity = velocity
        
        self.radius = int(BLOCK_SIZE * 1.5)
        
        self.space.remove(self.shape)
        self.shape = pymunk.Circle(self.body, self.radius)
        self.shape.elasticity = 0.0
        self.shape.friction = 1.0
        self.shape.collision_type = 3
        self.shape.block_ref = self
        self.space.add(self.shape)
        
        self.particles = []

    def explode(self, explosions):
        explosion_radius = int(3 * BLOCK_SIZE * 3)
        self._explode_with_radius(explosions, explosion_radius, 4, 60)

    def on_collision(self, arbiter, space, data):
        if not getattr(self, "detonated", False):
            self.detonate_flag = True

    def update(self, tnt_list, explosions, camera, current_time=None):
        if self.detonated:
            self.space.remove(self.body, self.shape)
            if self in tnt_list:
                tnt_list.remove(self)
            return

        px, py = self.body.position
        for _ in range(5):
            self.particles.append([px + random.randint(-self.radius, self.radius),
                                   py - self.radius, random.randint(10, 20)])

        if getattr(self, "detonate_flag", False):
            self.explode(explosions)
            camera.shake(30, 40)

    def draw(self, screen, camera):
        if self.detonated:
            return
            
        px = int(self.body.position.x - camera.offset_x)
        py = int(self.body.position.y - camera.offset_y)
        
        for p in self.particles[:]:
            p[1] -= random.uniform(5, 10)
            p[2] -= 0.5
            if p[2] <= 0:
                self.particles.remove(p)
            else:
                color = random.choice([(255, 69, 0), (255, 140, 0), (255, 215, 0)])
                pygame.draw.circle(screen, color, (int(p[0] - camera.offset_x), int(p[1] - camera.offset_y)), int(p[2]))

        pygame.draw.circle(screen, (100, 50, 20), (px, py), self.radius)
        
        if self.owner_name:
            text_surface = self.font.render(self.owner_name, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(px, py - self.radius - 20))
            shadow = self.font.render(self.owner_name, True, (0, 0, 0))
            shadow_rect = shadow.get_rect(center=(px + 1, py - self.radius - 19))
            screen.blit(shadow, shadow_rect)
            screen.blit(text_surface, text_rect)
