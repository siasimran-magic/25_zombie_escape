import pygame
import random
import math
import time

WIDTH, HEIGHT = 800, 560
FPS = 60
BG = (30, 35, 25)

# Gameplay settings
PLAYER_SPEED = 4
MAX_HP = 3
CLIP_SIZE = 12
RELOAD_TIME_FRAMES = 120  # 2.0 seconds at 60 FPS
INVINCIBLE_FRAMES = 75    # 1.25 seconds invincibility window
EXPLOSION_RADIUS = 120

# Strategic quadrant placement for explosive barrels
BARREL_POSITIONS = [
    (160, 140),
    (640, 140),
    (160, 420),
    (640, 420)
]


class Zombie:
    SPEED = 1.5
    MAX_HP = 3
    SIZE = 30
    COLOR = (60, 140, 60)
    SCORE_VALUE = 10

    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, self.SIZE, self.SIZE)
        self.x = float(x)
        self.y = float(y)
        self.color = self.COLOR
        self.hp = self.MAX_HP
        self.speed = self.SPEED
        self.wobble = random.uniform(0, 6.28)
        self.frame = 0

    def update(self, player_pos):
        px, py = player_pos
        cx, cy = self.rect.center
        dx, dy = px - cx, py - cy
        dist = (dx**2 + dy**2)**0.5
        if dist:
            self.x += (dx / dist) * self.speed
            self.y += (dy / dist) * self.speed
            self.rect.x = round(self.x)
            self.rect.y = round(self.y)
        self.frame += 1

    def hit(self):
        self.hp -= 1
        return self.hp <= 0

    def draw(self, screen):
        wobble_y = int(math.sin(self.frame * 0.2) * 3)
        draw_rect = self.rect.move(0, wobble_y)
        pygame.draw.rect(screen, self.color, draw_rect, border_radius=5)
        # Scaled eye placement
        eye_y = draw_rect.y + int(draw_rect.height * 0.3)
        eye_r = max(2, int(draw_rect.width * 0.12))
        eye_x1 = draw_rect.x + int(draw_rect.width * 0.25)
        eye_x2 = draw_rect.x + int(draw_rect.width * 0.65)
        for ex in [eye_x1, eye_x2]:
            pygame.draw.circle(screen, (200, 40, 40), (ex, eye_y), eye_r)


class FastZombie(Zombie):
    """Fast Zombie: higher speed (2.8), 1 HP, smaller size (22x22)."""
    SPEED = 2.8
    MAX_HP = 1
    SIZE = 22
    COLOR = (140, 190, 50)
    SCORE_VALUE = 15

    def __init__(self, x, y):
        super().__init__(x, y)


class TankZombie(Zombie):
    """Tank Zombie: lower speed (0.8), 6 HP, larger size (44x44)."""
    SPEED = 0.8
    MAX_HP = 6
    SIZE = 44
    COLOR = (45, 95, 55)
    SCORE_VALUE = 25

    def __init__(self, x, y):
        super().__init__(x, y)

    def draw(self, screen):
        super().draw(screen)
        # Durability indicator above tank
        wobble_y = int(math.sin(self.frame * 0.2) * 3)
        bar_w = self.rect.width
        bar_h = 4
        bar_x = self.rect.x
        bar_y = self.rect.y + wobble_y - 7
        pygame.draw.rect(screen, (50, 20, 20), (bar_x, bar_y, bar_w, bar_h))
        fill_w = int(bar_w * (max(0, self.hp) / self.MAX_HP))
        pygame.draw.rect(screen, (200, 40, 40), (bar_x, bar_y, fill_w, bar_h))


def spawn_zombie(width, height, player_rect, margin=120, zombie_cls=None):
    if zombie_cls is None:
        zombie_cls = random.choices(
            [Zombie, FastZombie, TankZombie],
            weights=[50, 30, 20],
            k=1
        )[0]
    size = zombie_cls.SIZE
    while True:
        x = random.randint(0, width - size)
        y = random.randint(45, height - size)  # Avoid spawning inside top HUD
        rect = pygame.Rect(x, y, size, size)
        if not rect.colliderect(player_rect.inflate(margin, margin)):
            return zombie_cls(x, y)


class Barrel:
    """Explosive barrel placed on the map."""
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 32, 32)
        self.exploded = False

    def explode(self, engine):
        """Detonate the barrel once, spawning explosion and destroying nearby zombies."""
        if self.exploded:
            return []
        self.exploded = True
        if self in engine.barrels:
            engine.barrels.remove(self)

        engine.explosions.append(Explosion(self.rect.centerx, self.rect.centery, EXPLOSION_RADIUS))

        destroyed = []
        for z in engine.zombies[:]:
            dist = math.hypot(z.rect.centerx - self.rect.centerx, z.rect.centery - self.rect.centery)
            if dist <= EXPLOSION_RADIUS:
                if z in engine.zombies:
                    engine.zombies.remove(z)
                    engine.kills += 1
                    engine.kill_score += z.SCORE_VALUE
                    destroyed.append(z)
        return destroyed

    def draw(self, screen):
        pygame.draw.rect(screen, (190, 70, 30), self.rect, border_radius=4)
        pygame.draw.line(screen, (240, 210, 50), (self.rect.left + 5, self.rect.top + 5), (self.rect.right - 5, self.rect.bottom - 5), 3)
        pygame.draw.line(screen, (240, 210, 50), (self.rect.left + 5, self.rect.bottom - 5), (self.rect.right - 5, self.rect.top + 5), 3)
        pygame.draw.rect(screen, (90, 30, 15), self.rect, 2, border_radius=4)


class Explosion:
    """Expanding explosion blast effect."""
    def __init__(self, x, y, radius=EXPLOSION_RADIUS):
        self.x = x
        self.y = y
        self.radius = radius
        self.duration = 18
        self.timer = self.duration

    def update(self):
        self.timer -= 1
        return self.timer > 0

    def draw(self, screen):
        progress = 1.0 - (self.timer / self.duration)
        current_r = int(self.radius * (0.3 + 0.7 * progress))
        if current_r <= 0:
            return
        surf = pygame.Surface((current_r * 2, current_r * 2), pygame.SRCALPHA)
        alpha = int(220 * (1.0 - progress))
        pygame.draw.circle(surf, (255, 120, 20, alpha), (current_r, current_r), current_r)
        core_r = max(1, int(current_r * 0.5))
        pygame.draw.circle(surf, (255, 240, 100, min(255, alpha + 35)), (current_r, current_r), core_r)
        screen.blit(surf, (self.x - current_r, self.y - current_r))


class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 32, 32)
        self.color = (60, 160, 220)
        self.bullets = []
        self.shoot_cooldown = 0
        self.hp = MAX_HP
        self.ammo = CLIP_SIZE
        self.is_reloading = False
        self.reload_timer = 0
        self.invincible_timer = 0

    def move(self, keys, width, height):
        dx = dy = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]: dy = -PLAYER_SPEED
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: dy = PLAYER_SPEED
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: dx = -PLAYER_SPEED
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx = PLAYER_SPEED
        self.rect.x = max(0, min(width - self.rect.width, self.rect.x + dx))
        self.rect.y = max(40, min(height - self.rect.height, self.rect.y + dy))

        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1

        if self.invincible_timer > 0:
            self.invincible_timer -= 1

        if self.is_reloading:
            self.reload_timer -= 1
            if self.reload_timer <= 0:
                self.ammo = CLIP_SIZE
                self.is_reloading = False

    def take_damage(self, amount=1):
        """Apply valid damage to the player if not currently invincible, clamping HP >= 0."""
        if self.invincible_timer <= 0 and self.hp > 0:
            self.hp = max(0, self.hp - amount)
            self.invincible_timer = INVINCIBLE_FRAMES
            return True
        return False

    def start_reload(self):
        """Trigger a reload if not already reloading and magazine is not full."""
        if self.is_reloading or self.ammo >= CLIP_SIZE:
            return False
        self.is_reloading = True
        self.reload_timer = RELOAD_TIME_FRAMES
        return True

    def shoot(self, target_pos):
        """Fire a bullet consuming 1 ammo. Blocks firing when empty or reloading."""
        if self.is_reloading:
            return False
        if self.ammo <= 0:
            self.start_reload()
            return False
        if self.shoot_cooldown > 0:
            return False

        cx, cy = self.rect.center
        tx, ty = target_pos
        dx, dy = tx - cx, ty - cy
        dist = (dx**2 + dy**2)**0.5
        if dist == 0:
            return False

        vx, vy = dx / dist * 10, dy / dist * 10
        self.bullets.append([cx - 4, cy - 4, vx, vy])
        self.shoot_cooldown = 15
        self.ammo -= 1

        if self.ammo <= 0:
            self.start_reload()
        return True

    def update_bullets(self, width, height):
        live = []
        for b in self.bullets:
            b[0] += b[2]
            b[1] += b[3]
            if 0 <= b[0] <= width and 0 <= b[1] <= height:
                live.append(b)
        self.bullets = live

    def draw(self, screen):
        # Draw live bullets
        for b in self.bullets:
            pygame.draw.circle(screen, (255, 220, 60), (int(b[0]), int(b[1])), 5)

        # Invincibility feedback (shield aura & body blink)
        if self.invincible_timer > 0:
            pygame.draw.circle(screen, (100, 220, 255), self.rect.center, 24, 2)
            if (self.invincible_timer // 6) % 2 == 1:
                return

        pygame.draw.rect(screen, self.color, self.rect, border_radius=6)


class GameEngine:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Zombie Escape")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 19, bold=True)
        self.big_font = pygame.font.SysFont("monospace", 44, bold=True)
        self.reset()

    def reset(self):
        self.player = Player(WIDTH // 2, HEIGHT // 2)
        self.zombies = [spawn_zombie(WIDTH, HEIGHT, self.player.rect) for _ in range(4)]
        self.barrels = [Barrel(x, y) for x, y in BARREL_POSITIONS]
        self.explosions = []
        self.kill_score = 0
        self.score = 0
        self.wave = 1
        self.kills = 0
        self.kills_to_next = 8
        self.game_over = False
        self.start_time = time.time()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    if self.game_over:
                        self.reset()
                    else:
                        self.player.start_reload()
                elif event.key == pygame.K_ESCAPE:
                    return False
            if event.type == pygame.MOUSEBUTTONDOWN and not self.game_over:
                if event.button == 1:  # Left click to shoot
                    self.player.shoot(event.pos)
                elif event.button == 3:  # Right click to manual reload
                    self.player.start_reload()
        return True

    def update(self):
        if self.game_over:
            return

        if self.player.hp <= 0:
            self.game_over = True
            return

        keys = pygame.key.get_pressed()
        self.player.move(keys, WIDTH, HEIGHT)
        self.player.update_bullets(WIDTH, HEIGHT)

        # Update active explosion animations
        self.explosions = [exp for exp in self.explosions if exp.update()]

        # Zombie movement & health damage handling
        for z in self.zombies:
            z.update(self.player.rect.center)
            if z.rect.colliderect(self.player.rect):
                if self.player.take_damage(1):
                    if self.player.hp <= 0:
                        self.game_over = True
                        return

        # Bullets hitting explosive barrels
        for barrel in self.barrels[:]:
            if barrel.exploded:
                continue
            barrel_hit = False
            for b in self.player.bullets[:]:
                bx, by = int(b[0]), int(b[1])
                b_rect = pygame.Rect(bx - 4, by - 4, 8, 8)
                if barrel.rect.colliderect(b_rect):
                    if b in self.player.bullets:
                        self.player.bullets.remove(b)
                    barrel_hit = True
                    break
            if barrel_hit:
                barrel.explode(self)

        # Bullets hitting zombies
        dead = []
        for z in self.zombies:
            for b in self.player.bullets[:]:
                bx, by = int(b[0]), int(b[1])
                b_rect = pygame.Rect(bx - 4, by - 4, 8, 8)
                if z.rect.colliderect(b_rect):
                    if b in self.player.bullets:
                        self.player.bullets.remove(b)
                    if z.hit():
                        dead.append(z)
                        break

        for z in dead:
            if z in self.zombies:
                self.zombies.remove(z)
                self.kills += 1
                self.kill_score += z.SCORE_VALUE

        # Wave progression
        if self.kills >= self.kills_to_next:
            self.kills = max(0, self.kills - self.kills_to_next)
            self.wave += 1
            self.kills_to_next = 8 + self.wave * 2
            for _ in range(self.wave + 3):
                self.zombies.append(spawn_zombie(WIDTH, HEIGHT, self.player.rect))

        # Maintain active horde so player is never left on an empty map
        desired_zombies = 3 + self.wave
        while len(self.zombies) < desired_zombies:
            self.zombies.append(spawn_zombie(WIDTH, HEIGHT, self.player.rect))

        # Score accurately accumulates kill score + elapsed survival seconds
        elapsed_survival = int(time.time() - self.start_time)
        self.score = self.kill_score + elapsed_survival

    def draw(self):
        self.screen.fill(BG)
        # Background grid
        for x in range(0, WIDTH, 60):
            pygame.draw.line(self.screen, (40, 45, 35), (x, 40), (x, HEIGHT), 1)
        for y in range(40, HEIGHT, 60):
            pygame.draw.line(self.screen, (40, 45, 35), (0, y), (WIDTH, y), 1)

        # Draw entities
        for barrel in self.barrels:
            barrel.draw(self.screen)
        for z in self.zombies:
            z.draw(self.screen)
        self.player.draw(self.screen)
        for exp in self.explosions:
            exp.draw(self.screen)

        # Top HUD bar
        hud_bg = pygame.Rect(0, 0, WIDTH, 40)
        pygame.draw.rect(self.screen, (15, 20, 15), hud_bg)
        pygame.draw.line(self.screen, (50, 70, 50), (0, 40), (WIDTH, 40), 2)

        ammo_str = f"RELOAD ({self.player.reload_timer / FPS:.1f}s)" if self.player.is_reloading else f"{self.player.ammo}/{CLIP_SIZE}"
        
        # Display HP with dedicated clear color coding (green/yellow/red)
        hp_color = (90, 225, 90) if self.player.hp >= 3 else ((240, 210, 50) if self.player.hp == 2 else (235, 65, 65))
        hp_surf = self.font.render(f"HP: {self.player.hp}/{MAX_HP}", True, hp_color)
        self.screen.blit(hp_surf, (12, 10))

        # Distinct color coding for Ammo (Gold when full/high, Orange when <= 3, Red when empty/reloading)
        ammo_color = (235, 65, 65) if self.player.is_reloading or self.player.ammo == 0 else ((240, 180, 50) if self.player.ammo <= 3 else (245, 230, 90))
        ammo_surf = self.font.render(f"  |  AMMO: {ammo_str}", True, ammo_color)
        self.screen.blit(ammo_surf, (12 + hp_surf.get_width(), 10))

        hud_text = (
            f"  |  WAVE: {self.wave}  |  "
            f"KILLS: {self.kills}/{self.kills_to_next}  |  "
            f"SCORE: {self.score}"
        )
        hud = self.font.render(hud_text, True, (160, 220, 120))
        self.screen.blit(hud, (12 + hp_surf.get_width() + ammo_surf.get_width(), 10))

        # Game over screen
        if self.game_over:
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 175))
            self.screen.blit(ov, (0, 0))
            m = self.big_font.render("DEVOURED!", True, (200, 45, 45))
            s = self.font.render(f"Wave {self.wave}  |  Final Score {self.score}  |  Press R to Restart", True, (220, 220, 220))
            self.screen.blit(m, (WIDTH // 2 - m.get_width() // 2, HEIGHT // 2 - 40))
            self.screen.blit(s, (WIDTH // 2 - s.get_width() // 2, HEIGHT // 2 + 20))

        pygame.display.flip()

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()


if __name__ == "__main__":
    engine = GameEngine()
    engine.run()
