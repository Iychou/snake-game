"""
╔══════════════════════════════════════════════════════╗
║      SPACE INVADERS  ─  ADVANCED EDITION             ║
║  pip install pygame  →  python space_invaders_advanced.py ║
╚══════════════════════════════════════════════════════╝

Controls:
  Arrow keys / WASD  ─ move
  SPACE              ─ shoot
  P                  ─ pause
  R (game-over)      ─ restart

Features:
  • 5 alien types with unique bullet patterns
  • Boss every 3 levels (3 phases, shield bar)
  • 6 power-ups: Rapid, Triple, Laser, Shield, Nuke, Slow
  • Particle system (explosions, engine trails, sparks)
  • Screen-shake on big hits
  • Scrolling parallax starfield
  • Combo multiplier system
  • Destructible shields with pixel erosion
  • High-score persistence (local file)
  • Wave announcement banners
  • Pause screen
"""

import pygame
import random
import sys
import math
import os
import json

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
W, H        = 900, 720
FPS         = 60
SAVE_FILE   = "si_save.json"

# Palette
BLACK   = (0,   0,   0)
WHITE   = (255, 255, 255)
NEON_G  = (57,  255,  20)
NEON_B  = (0,  200, 255)
NEON_P  = (200,  80, 255)
NEON_R  = (255,  60,  60)
NEON_Y  = (255, 220,   0)
NEON_O  = (255, 140,   0)
GRAY    = (120, 120, 120)
DARK    = (15,   15,  25)

ROW_COL = [NEON_R, NEON_O, NEON_Y, NEON_B, NEON_P]

POWERUP_TYPES = ["rapid", "triple", "laser", "shield", "nuke", "slow"]
POWERUP_COLS  = {
    "rapid":  (255, 200,   0),
    "triple": (0,   200, 255),
    "laser":  (255,  60,  60),
    "shield": (57,  255,  20),
    "nuke":   (200,  80, 255),
    "slow":   (200, 200, 255),
}

# ─────────────────────────────────────────────────────────────────────────────
# FONT HELPER
# ─────────────────────────────────────────────────────────────────────────────
_font_cache: dict = {}

def font(size: int, bold=True) -> pygame.font.Font:
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("monospace", size, bold=bold)
    return _font_cache[key]

def draw_text(surf, text, x, y, colour=WHITE, size=22, center=False, alpha=255):
    f   = font(size)
    img = f.render(text, True, colour)
    if alpha < 255:
        img.set_alpha(alpha)
    if center:
        x -= img.get_width() // 2
    surf.blit(img, (x, y))

def draw_text_outline(surf, text, x, y, colour, outline=(0,0,0), size=22, center=False):
    for dx, dy in ((-1,-1),(1,-1),(-1,1),(1,1)):
        draw_text(surf, text, x+dx, y+dy, outline, size, center)
    draw_text(surf, text, x, y, colour, size, center)

# ─────────────────────────────────────────────────────────────────────────────
# PARTICLE SYSTEM
# ─────────────────────────────────────────────────────────────────────────────
class Particle:
    __slots__ = ('x','y','vx','vy','life','max_life','colour','size','gravity')

    def __init__(self, x, y, vx, vy, life, colour, size=3, gravity=0.0):
        self.x, self.y   = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.life        = life
        self.max_life    = life
        self.colour      = colour
        self.size        = size
        self.gravity     = gravity

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vy += self.gravity
        self.vx *= 0.97
        self.life -= 1

    def draw(self, surf):
        a    = self.life / self.max_life
        r,g,b= self.colour
        col  = (int(r*a), int(g*a), int(b*a))
        sz   = max(1, int(self.size * a))
        pygame.draw.circle(surf, col, (int(self.x), int(self.y)), sz)


class ParticleSystem:
    def __init__(self):
        self.particles: list[Particle] = []

    def emit(self, n, x, y, colours, speed=4, life=40, size=3, gravity=0.05):
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(speed * 0.3, speed)
            col = random.choice(colours)
            self.particles.append(Particle(
                x, y, math.cos(ang)*spd, math.sin(ang)*spd,
                random.randint(life//2, life), col, size, gravity
            ))

    def emit_directed(self, n, x, y, ang_deg, spread_deg, colour, speed=5, life=30, size=2):
        for _ in range(n):
            ang = math.radians(ang_deg + random.uniform(-spread_deg/2, spread_deg/2))
            spd = random.uniform(speed * 0.5, speed)
            self.particles.append(Particle(
                x, y, math.cos(ang)*spd, math.sin(ang)*spd,
                random.randint(life//2, life), colour, size, 0
            ))

    def update(self):
        self.particles = [p for p in self.particles if p.life > 0]
        for p in self.particles:
            p.update()

    def draw(self, surf):
        for p in self.particles:
            p.draw(surf)

# ─────────────────────────────────────────────────────────────────────────────
# STARS (parallax)
# ─────────────────────────────────────────────────────────────────────────────
class StarField:
    def __init__(self, n=200):
        self.stars = []
        for _ in range(n):
            x     = random.uniform(0, W)
            y     = random.uniform(0, H)
            layer = random.randint(1, 3)   # 1=far, 3=near
            b     = random.randint(60, 220)
            self.stars.append([x, y, layer, b])

    def update(self, speed=0.5):
        for s in self.stars:
            s[1] += s[2] * speed * 0.3
            if s[1] > H:
                s[1] = 0
                s[0] = random.uniform(0, W)

    def draw(self, surf):
        for x, y, layer, b in self.stars:
            c = (b, b, b)
            r = layer - 1 if layer > 1 else 1
            if layer == 1:
                surf.set_at((int(x), int(y)), c)
            else:
                pygame.draw.circle(surf, c, (int(x), int(y)), r - 1)

# ─────────────────────────────────────────────────────────────────────────────
# SCREEN SHAKE
# ─────────────────────────────────────────────────────────────────────────────
class ScreenShake:
    def __init__(self):
        self.duration = 0
        self.intensity = 0

    def start(self, duration=12, intensity=8):
        self.duration  = max(self.duration, duration)
        self.intensity = max(self.intensity, intensity)

    def get_offset(self):
        if self.duration <= 0:
            return (0, 0)
        ox = random.uniform(-self.intensity, self.intensity)
        oy = random.uniform(-self.intensity, self.intensity)
        self.duration  -= 1
        self.intensity *= 0.9
        return (int(ox), int(oy))

# ─────────────────────────────────────────────────────────────────────────────
# PIXEL ALIEN SPRITES
# ─────────────────────────────────────────────────────────────────────────────
# 7×6 bitmaps; 2 frames each for animation
ALIEN_MAPS = [
    # type 0 – Crab (frame A / B)
    [
        ["..###..", ".#...#.", "#######", "##.#.##", "#######", ".#...#."],
        ["..###..", ".#...#.", "#######", "##.#.##", "#######", "#.....#"],
    ],
    # type 1 – Squid
    [
        ["..###..", "#######", "#.###.#", "#######", "..#.#..", ".#...#."],
        ["..###..", "#######", "#.###.#", "#######", "..#.#..", "#.....#"],
    ],
    # type 2 – Bug
    [
        [".#####.", "#######", "##.#.##", "#######", "#.###.#", ".#...#."],
        [".#####.", "#######", "##.#.##", "#######", "#.###.#", "#.....#"],
    ],
    # type 3 – Spider
    [
        ["#.###.#", ".#####.", "##.#.##", ".#####.", "#.....#", ".#...#."],
        ["#.###.#", ".#####.", "##.#.##", ".#####.", ".#...#.", "#.....#"],
    ],
    # type 4 – Moth
    [
        ["#.###.#", "##.#.##", "#######", ".#.#.#.", "##...##", ".#...#."],
        ["#.###.#", "##.#.##", "#######", ".#.#.#.", ".#...#.", "##...##"],
    ],
]

def draw_alien_sprite(surf, atype, frame, colour, cx, cy, scale=4):
    rows = ALIEN_MAPS[atype % len(ALIEN_MAPS)][frame % 2]
    W2   = len(rows[0]) * scale // 2
    H2   = len(rows) * scale // 2
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == '#':
                pygame.draw.rect(surf, colour,
                    (cx - W2 + c*scale, cy - H2 + r*scale, scale, scale))

# ─────────────────────────────────────────────────────────────────────────────
# BULLET TYPES
# ─────────────────────────────────────────────────────────────────────────────
class Bullet:
    def __init__(self, x, y, vx, vy, colour, damage=1, owner='player', btype='normal'):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.colour  = colour
        self.damage  = damage
        self.owner   = owner   # 'player' or 'alien'
        self.btype   = btype   # 'normal','laser','spiral','wave'
        self.alive   = True
        self.age     = 0
        self.w       = 4 if btype != 'laser' else 6
        self.h       = 16 if btype != 'laser' else 30

    def update(self):
        self.age += 1
        if self.btype == 'spiral':
            self.vx = math.cos(self.age * 0.15) * 3
        elif self.btype == 'wave':
            self.vx = math.sin(self.age * 0.2) * 3
        self.x += self.vx
        self.y += self.vy
        if self.y < -40 or self.y > H + 40 or self.x < -20 or self.x > W + 20:
            self.alive = False

    @property
    def rect(self):
        return pygame.Rect(self.x - self.w//2, self.y - self.h//2, self.w, self.h)

    def draw(self, surf):
        if self.btype == 'laser':
            for i in range(3):
                alpha_col = tuple(max(0, c - i*60) for c in self.colour)
                pygame.draw.rect(surf, alpha_col,
                    (self.x - self.w//2 + i, self.y - self.h//2, self.w - i*2, self.h))
            # glow tip
            pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y - self.h//2)), 4)
        else:
            pygame.draw.rect(surf, self.colour, self.rect)
            # bright core
            inner = (min(255, self.colour[0]+80),
                     min(255, self.colour[1]+80),
                     min(255, self.colour[2]+80))
            pygame.draw.rect(surf, inner,
                (self.x - 1, self.y - self.h//2 + 2, 2, self.h - 4))

# ─────────────────────────────────────────────────────────────────────────────
# POWER-UP
# ─────────────────────────────────────────────────────────────────────────────
class PowerUp:
    SIZE = 28

    def __init__(self, x, y, ptype):
        self.x, self.y = float(x), float(y)
        self.ptype     = ptype
        self.colour    = POWERUP_COLS[ptype]
        self.alive     = True
        self.age       = 0

    @property
    def rect(self):
        s = self.SIZE
        return pygame.Rect(self.x - s//2, self.y - s//2, s, s)

    def update(self):
        self.y   += 1.5
        self.age += 1
        if self.y > H + 40:
            self.alive = False

    def draw(self, surf):
        s    = self.SIZE
        cx, cy = int(self.x), int(self.y)
        pulse= 1 + 0.15 * math.sin(self.age * 0.15)
        r    = int(s * pulse // 2)
        pygame.draw.circle(surf, self.colour, (cx, cy), r, 2)
        pygame.draw.circle(surf, self.colour, (cx, cy), r - 5)
        label = {'rapid':'R','triple':'T','laser':'L',
                 'shield':'S','nuke':'N','slow':'?'}[self.ptype]
        draw_text(surf, label, cx, cy - 8, WHITE, 16, center=True)

# ─────────────────────────────────────────────────────────────────────────────
# SHIELD BLOCK (pixel-eroded)
# ─────────────────────────────────────────────────────────────────────────────
class Shield:
    BLOCK = 8
    COLS  = 9
    ROWS  = 5

    def __init__(self, cx, y):
        self.cx = cx
        self.y  = y
        self.grid = [[True] * self.COLS for _ in range(self.ROWS)]
        # Arch cut-out at bottom centre
        for r in range(2, self.ROWS):
            for c in range(3, 6):
                self.grid[r][c] = False

    @property
    def rect(self):
        W2 = self.COLS * self.BLOCK // 2
        return pygame.Rect(self.cx - W2, self.y, self.COLS * self.BLOCK, self.ROWS * self.BLOCK)

    def hit(self, bx, by):
        W2 = self.COLS * self.BLOCK // 2
        ox = int(bx - (self.cx - W2))
        oy = int(by - self.y)
        c  = ox // self.BLOCK
        r  = oy // self.BLOCK
        # Erode 3×3 area
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                rr, cc = r + dr, c + dc
                if 0 <= rr < self.ROWS and 0 <= cc < self.COLS:
                    if random.random() < 0.6:
                        self.grid[rr][cc] = False
        return True

    def collides(self, rect):
        W2 = self.COLS * self.BLOCK // 2
        if not self.rect.colliderect(rect):
            return False
        # Check individual blocks
        for r in range(self.ROWS):
            for c in range(self.COLS):
                if not self.grid[r][c]:
                    continue
                bx = self.cx - W2 + c * self.BLOCK
                by = self.y  + r * self.BLOCK
                br = pygame.Rect(bx, by, self.BLOCK, self.BLOCK)
                if rect.colliderect(br):
                    return True
        return False

    def draw(self, surf):
        W2 = self.COLS * self.BLOCK // 2
        for r in range(self.ROWS):
            for c in range(self.COLS):
                if not self.grid[r][c]:
                    continue
                bx = self.cx - W2 + c * self.BLOCK
                by = self.y  + r * self.BLOCK
                pygame.draw.rect(surf, NEON_G,
                    (bx, by, self.BLOCK - 1, self.BLOCK - 1))
                pygame.draw.rect(surf, (0, 180, 50),
                    (bx + 1, by + 1, self.BLOCK - 3, self.BLOCK - 3))

# ─────────────────────────────────────────────────────────────────────────────
# ALIEN
# ─────────────────────────────────────────────────────────────────────────────
class Alien:
    def __init__(self, col, row, atype, colour, x, y, hp=1):
        self.col, self.row = col, row
        self.atype   = atype
        self.colour  = colour
        self.x, self.y = float(x), float(y)
        self.hp      = hp
        self.max_hp  = hp
        self.alive   = True
        self.frame   = 0
        self.hit_flash = 0

    def pts(self):
        return (self.atype + 1) * 10

    @property
    def rect(self):
        return pygame.Rect(self.x - 22, self.y - 16, 44, 32)

    def draw(self, surf):
        col = WHITE if self.hit_flash > 0 else self.colour
        if self.hit_flash > 0:
            self.hit_flash -= 1
        draw_alien_sprite(surf, self.atype, self.frame, col,
                          int(self.x), int(self.y), scale=4)
        # HP bar for tougher aliens
        if self.max_hp > 1:
            bw = 40
            frac = self.hp / self.max_hp
            pygame.draw.rect(surf, GRAY, (self.x - bw//2, self.y + 20, bw, 4))
            pygame.draw.rect(surf, NEON_G,
                (self.x - bw//2, self.y + 20, int(bw * frac), 4))

# ─────────────────────────────────────────────────────────────────────────────
# UFO
# ─────────────────────────────────────────────────────────────────────────────
class UFO:
    SPEED = 3.5
    HP    = 5

    def __init__(self):
        self.x     = -60.0
        self.y     = 55.0
        self.hp    = self.HP
        self.alive = True
        self.pts   = random.choice([50, 100, 150, 200, 300])
        self.age   = 0

    @property
    def rect(self):
        return pygame.Rect(self.x - 30, self.y - 14, 60, 28)

    def update(self):
        self.x   += self.SPEED
        self.age += 1
        if self.x > W + 80:
            self.alive = False

    def draw(self, surf):
        cx, cy = int(self.x), int(self.y)
        pulse  = abs(math.sin(self.age * 0.1))
        col    = (255, int(50 + 50*pulse), int(50 + 50*pulse))
        pygame.draw.ellipse(surf, col, (cx-30, cy-10, 60, 22))
        pygame.draw.ellipse(surf, (255, 150, 150), (cx-16, cy-22, 32, 18))
        for i in range(-2, 3):
            pygame.draw.circle(surf, (255, 220, 0), (cx + i*11, cy+6), 3)
        # hp dots
        for i in range(self.HP):
            c = NEON_G if i < self.hp else GRAY
            pygame.draw.circle(surf, c, (cx - 20 + i*10, cy - 28), 4)

# ─────────────────────────────────────────────────────────────────────────────
# BOSS
# ─────────────────────────────────────────────────────────────────────────────
class Boss:
    MAX_HP_PHASES = [120, 80, 60]
    COLOURS = [NEON_R, NEON_O, NEON_P]

    def __init__(self, level):
        self.x      = float(W // 2)
        self.y      = 100.0
        self.phase  = 0
        self.hp     = self.MAX_HP_PHASES[0]
        self.max_hp = self.MAX_HP_PHASES[0]
        self.alive  = True
        self.age    = 0
        self.shoot_timer = 0
        self.move_angle  = 0.0
        self.level  = level
        self.hit_flash = 0
        self.pts    = 5000 + level * 1000

    @property
    def colour(self):
        return self.COLOURS[self.phase % 3]

    @property
    def rect(self):
        return pygame.Rect(self.x - 50, self.y - 36, 100, 72)

    def update(self, bullets_out: list, ps: ParticleSystem, player_x: float):
        self.age       += 1
        self.move_angle += 0.018 + self.phase * 0.007
        self.x          = W/2 + math.cos(self.move_angle) * (W/3)
        self.y          = 100 + math.sin(self.move_angle * 0.7) * 50
        self.shoot_timer += 1
        rate = max(20, 55 - self.phase * 12 - self.level * 2)

        if self.hit_flash > 0:
            self.hit_flash -= 1

        if self.shoot_timer >= rate:
            self.shoot_timer = 0
            self._shoot(bullets_out, player_x)

        # Engine trail
        if self.age % 2 == 0:
            ps.emit(2, self.x + random.uniform(-20,20),
                    self.y + 40, [self.colour, NEON_O], speed=1.5,
                    life=20, size=4, gravity=0.05)

    def _shoot(self, bullets_out, player_x):
        phase = self.phase
        cx, cy = self.x, self.y + 40
        if phase == 0:
            # aimed burst
            dx = player_x - cx
            dy = H - cy
            dist = max(1, math.hypot(dx, dy))
            for i in range(-1, 2):
                ang = math.atan2(dy, dx) + i * 0.25
                bullets_out.append(Bullet(cx, cy,
                    math.cos(ang)*5, math.sin(ang)*5,
                    self.colour, damage=1, owner='alien', btype='normal'))
        elif phase == 1:
            # 8-way spiral
            for i in range(8):
                ang = math.radians(i * 45 + self.age * 3)
                bullets_out.append(Bullet(cx, cy,
                    math.cos(ang)*4, math.sin(ang)*4,
                    self.colour, damage=1, owner='alien', btype='normal'))
        else:
            # Wave + aimed
            for i in range(5):
                ang = math.radians(-30 + i*15)
                bullets_out.append(Bullet(cx, cy,
                    math.sin(ang)*4, 6,
                    self.colour, damage=2, owner='alien', btype='wave'))

    def take_hit(self, dmg):
        self.hp        -= dmg
        self.hit_flash  = 6
        if self.hp <= 0:
            if self.phase < 2:
                self.phase  += 1
                self.hp      = self.MAX_HP_PHASES[self.phase]
                self.max_hp  = self.hp
                return 'phase'
            else:
                self.alive = False
                return 'dead'
        return 'hit'

    def draw(self, surf):
        cx, cy = int(self.x), int(self.y)
        col    = WHITE if self.hit_flash > 0 else self.colour

        # Body hexagon approximation
        pts = []
        for i in range(6):
            ang = math.radians(i * 60 - 90)
            pts.append((cx + math.cos(ang)*50, cy + math.sin(ang)*36))
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, BLACK, pts, 3)

        # Core
        pygame.draw.circle(surf, WHITE, (cx, cy), 16)
        pygame.draw.circle(surf, col,   (cx, cy), 11)

        # Phase indicator diamonds
        for i in range(3):
            dc = col if i >= self.phase else GRAY
            ox = -20 + i * 20
            pygame.draw.polygon(surf, dc, [
                (cx+ox, cy-40), (cx+ox+8, cy-32),
                (cx+ox, cy-24), (cx+ox-8, cy-32)])

        # HP bar
        bw = 200
        bx = W//2 - bw//2
        by = 10
        pygame.draw.rect(surf, GRAY, (bx, by, bw, 14))
        frac = self.hp / self.max_hp
        bar_col = [NEON_G, NEON_Y, NEON_R][self.phase]
        pygame.draw.rect(surf, bar_col, (bx, by, int(bw*frac), 14))
        pygame.draw.rect(surf, WHITE, (bx, by, bw, 14), 2)
        draw_text(surf, f"BOSS  HP", W//2, by, WHITE, 18, center=True)

# ─────────────────────────────────────────────────────────────────────────────
# PLAYER
# ─────────────────────────────────────────────────────────────────────────────
class Player:
    SPEED     = 6
    MAX_HP    = 5
    IFRAMES   = 90

    def __init__(self):
        self.x      = float(W // 2)
        self.y      = float(H - 60)
        self.hp     = self.MAX_HP
        self.alive  = True
        self.iframes= 0
        self.age    = 0
        # power-up state
        self.rapid_t  = 0
        self.triple_t = 0
        self.laser_t  = 0
        self.shield_t = 0
        self.slow_t   = 0
        self.shoot_cd = 0
        self.score    = 0

    @property
    def rect(self):
        return pygame.Rect(self.x - 20, self.y - 22, 40, 36)

    def update(self, keys):
        self.age    += 1
        self.iframes = max(0, self.iframes - 1)
        self.shoot_cd= max(0, self.shoot_cd - 1)
        self.rapid_t  = max(0, self.rapid_t  - 1)
        self.triple_t = max(0, self.triple_t - 1)
        self.laser_t  = max(0, self.laser_t  - 1)
        self.shield_t = max(0, self.shield_t - 1)
        self.slow_t   = max(0, self.slow_t   - 1)

        if keys[pygame.K_LEFT]  or keys[pygame.K_a]:
            self.x = max(24, self.x - self.SPEED)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.x = min(W - 24, self.x + self.SPEED)

    def shoot(self) -> list:
        rate = 8 if self.rapid_t > 0 else (18 if self.laser_t > 0 else 14)
        if self.shoot_cd > 0:
            return []
        self.shoot_cd = rate
        bullets = []
        if self.laser_t > 0:
            bullets.append(Bullet(self.x, self.y - 30, 0, -18,
                NEON_R, damage=3, owner='player', btype='laser'))
        elif self.triple_t > 0:
            for dx in (-0.5, 0, 0.5):
                bullets.append(Bullet(self.x, self.y - 24, dx*4, -14,
                    NEON_B, damage=1, owner='player'))
        else:
            bullets.append(Bullet(self.x, self.y - 24, 0, -14,
                NEON_G, damage=1, owner='player'))
        return bullets

    def take_hit(self, dmg=1) -> bool:
        if self.iframes > 0 or self.shield_t > 0:
            return False
        self.hp     -= dmg
        self.iframes = self.IFRAMES
        if self.hp <= 0:
            self.alive = False
        return True

    def apply_powerup(self, ptype):
        dur = 300  # 5 seconds
        if ptype == 'rapid':   self.rapid_t  = dur
        elif ptype == 'triple': self.triple_t = dur
        elif ptype == 'laser':  self.laser_t  = dur
        elif ptype == 'shield': self.shield_t = dur
        elif ptype == 'slow':   self.slow_t   = dur

    def draw(self, surf):
        if self.iframes > 0 and (self.iframes // 6) % 2 == 1:
            return
        cx, cy = int(self.x), int(self.y)

        # Shield bubble
        if self.shield_t > 0:
            pulse = abs(math.sin(self.age * 0.1))
            r     = int(34 + pulse * 4)
            s     = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (57, 255, 20, 60), (r, r), r)
            pygame.draw.circle(s, (57, 255, 20, 180), (r, r), r, 2)
            surf.blit(s, (cx - r, cy - r))

        # Ship body
        col = NEON_G if self.laser_t == 0 else NEON_R
        if self.rapid_t > 0:  col = NEON_Y
        if self.triple_t > 0: col = NEON_B

        pts = [
            (cx,      cy - 24),
            (cx - 22, cy + 16),
            (cx - 10, cy + 10),
            (cx - 10, cy + 16),
            (cx + 10, cy + 16),
            (cx + 10, cy + 10),
            (cx + 22, cy + 16),
        ]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 1)
        pygame.draw.rect(surf, WHITE, (cx - 3, cy - 24, 6, 14))

        # Engine glow
        ec = (min(255, col[0]+80), min(255, col[1]+80), min(255, col[2]+80))
        pygame.draw.circle(surf, ec, (cx, cy + 12), 5)

        # HP pips
        for i in range(self.MAX_HP):
            c = NEON_G if i < self.hp else (40, 40, 40)
            pygame.draw.rect(surf, c, (10 + i * 18, H - 18, 14, 8))

# ─────────────────────────────────────────────────────────────────────────────
# COMBO DISPLAY
# ─────────────────────────────────────────────────────────────────────────────
class ComboDisplay:
    def __init__(self):
        self.count   = 0
        self.timer   = 0
        self.multiplier = 1
        self.pop_list= []  # [(x,y,text,colour,age,max_age)]

    def hit(self, x, y, base_pts) -> int:
        self.count  += 1
        self.timer   = 90
        self.multiplier = 1 + self.count // 5
        mult_pts = base_pts * self.multiplier
        col = [WHITE, NEON_G, NEON_Y, NEON_O, NEON_R][min(4, self.multiplier-1)]
        self.pop_list.append([x, y, f"+{mult_pts}", col, 0, 45])
        return mult_pts

    def update(self):
        self.timer = max(0, self.timer - 1)
        if self.timer == 0:
            self.count = 0
            self.multiplier = 1
        self.pop_list = [p for p in self.pop_list if p[4] < p[5]]
        for p in self.pop_list:
            p[1] -= 1.2
            p[4] += 1

    def draw(self, surf):
        for x, y, text, col, age, max_age in self.pop_list:
            a = int(255 * (1 - age/max_age))
            draw_text(surf, text, int(x), int(y), col, 18, center=True, alpha=a)
        if self.count >= 3:
            col = [WHITE, NEON_G, NEON_Y, NEON_O, NEON_R][min(4, self.multiplier-1)]
            draw_text_outline(surf, f"x{self.multiplier} COMBO!",
                W//2, H//2 - 80, col, size=30, center=True)

# ─────────────────────────────────────────────────────────────────────────────
# BANNER (wave announce)
# ─────────────────────────────────────────────────────────────────────────────
class Banner:
    def __init__(self):
        self.text   = ""
        self.sub    = ""
        self.timer  = 0
        self.colour = WHITE

    def show(self, text, sub="", duration=120, colour=NEON_G):
        self.text   = text
        self.sub    = sub
        self.timer  = duration
        self.colour = colour

    def update(self):
        self.timer = max(0, self.timer - 1)

    def draw(self, surf):
        if self.timer <= 0:
            return
        a   = min(255, self.timer * 4)
        s   = pygame.Surface((W, 120), pygame.SRCALPHA)
        s.fill((0, 0, 0, min(180, a)))
        surf.blit(s, (0, H//2 - 60))
        draw_text(surf, self.text, W//2, H//2 - 40, self.colour, 48, center=True, alpha=a)
        if self.sub:
            draw_text(surf, self.sub, W//2, H//2 + 10, WHITE, 22, center=True, alpha=a)

# ─────────────────────────────────────────────────────────────────────────────
# HIGH SCORE
# ─────────────────────────────────────────────────────────────────────────────
def load_hi() -> int:
    try:
        with open(SAVE_FILE) as f:
            return json.load(f).get('hi', 0)
    except Exception:
        return 0

def save_hi(score: int):
    try:
        with open(SAVE_FILE, 'w') as f:
            json.dump({'hi': score}, f)
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# WAVE BUILDER
# ─────────────────────────────────────────────────────────────────────────────
def build_wave(level: int) -> list[Alien]:
    cols       = min(11, 7 + level // 2)
    rows       = min(6,  4 + level // 3)
    aliens     = []
    h_gap      = max(50, 68 - level * 2)
    v_gap      = max(44, 56 - level * 2)
    left       = (W - cols * h_gap) // 2 + h_gap // 2
    top        = 100

    hp_table   = [1, 1, 2, 2, 3]  # row → hp

    for row in range(rows):
        atype  = row % len(ALIEN_MAPS)
        colour = ROW_COL[row % len(ROW_COL)]
        hp     = hp_table[min(row, len(hp_table)-1)] + level // 3
        for col in range(cols):
            a = Alien(col, row, atype, colour,
                      left + col * h_gap, top + row * v_gap, hp=hp)
            aliens.append(a)
    return aliens

# ─────────────────────────────────────────────────────────────────────────────
# GAME
# ─────────────────────────────────────────────────────────────────────────────
class Game:
    MOVE_BASE    = 40
    STEP_X       = 14
    STEP_DOWN    = 22
    BOSS_EVERY   = 3

    def __init__(self, screen: pygame.Surface):
        self.screen   = screen
        self.canvas   = pygame.Surface((W, H))
        self.shake    = ScreenShake()
        self.stars    = StarField(220)
        self.ps       = ParticleSystem()
        self.combo    = ComboDisplay()
        self.banner   = Banner()
        self.hi_score = load_hi()
        self.state    = 'title'
        self._new_game()

    # ── setup ──────────────────────────────────────────────────────────────
    def _new_game(self):
        self.score    = 0
        self.level    = 1
        self.player   = Player()
        self.aliens   : list[Alien]  = []
        self.bullets  : list[Bullet] = []
        self.powerups : list[PowerUp]= []
        self.shields  : list[Shield] = []
        self.boss     : Boss | None  = None
        self.ufo      : UFO  | None  = None
        self.ufo_timer= random.randint(400, 700)
        self.move_dir = 1
        self.move_timer = 0
        self.anim_frame = 0
        self.nuke_flash = 0
        self.pause    = False
        self.over_timer = 0
        self._start_level()

    def _start_level(self):
        self._build_shields()
        self.bullets  = []
        self.powerups = []
        self.ufo      = None
        self.ufo_timer= random.randint(400, 700)
        self.move_dir = 1
        self.move_timer = 0

        if self.level % self.BOSS_EVERY == 0:
            self.aliens = []
            self.boss   = Boss(self.level)
            self.banner.show(f"⚠  BOSS  WAVE  {self.level}  ⚠",
                             "GOOD LUCK!", 150, NEON_R)
        else:
            self.boss   = None
            self.aliens = build_wave(self.level)
            self.banner.show(f"WAVE  {self.level}",
                             f"INVADERS: {len(self.aliens)}", 100, NEON_G)

    def _build_shields(self):
        self.shields = []
        n   = 4
        gap = W // (n + 1)
        for i in range(n):
            self.shields.append(Shield(gap * (i+1), H - 145))

    # ── properties ─────────────────────────────────────────────────────────
    @property
    def alive_aliens(self):
        return [a for a in self.aliens if a.alive]

    def _move_rate(self):
        alive = len(self.alive_aliens)
        total = len(self.aliens) or 1
        frac  = 1 - alive / total
        base  = max(4, self.MOVE_BASE - (self.level - 1) * 4)
        return max(4, int(base * (1 - frac * 0.8)))

    # ── main update ────────────────────────────────────────────────────────
    def update(self):
        keys = pygame.key.get_pressed()

        if self.state == 'title':
            self.stars.update(0.3)
            return

        if self.state in ('over', 'win_all'):
            self.stars.update(0.2)
            self.ps.update()
            self.over_timer += 1
            return

        if self.pause:
            return

        self.stars.update(0.5)
        self.banner.update()
        self.combo.update()
        self.ps.update()
        self.nuke_flash = max(0, self.nuke_flash - 1)

        # Player
        p = self.player
        p.update(keys)
        if keys[pygame.K_SPACE] or keys[pygame.K_UP] or keys[pygame.K_w]:
            self.bullets.extend(p.shoot())

        # Engine trail
        if self.player.age % 3 == 0:
            self.ps.emit_directed(1, p.x, p.y + 18, 90, 20,
                                  (80, 255, 120), speed=3, life=18, size=3)

        # UFO
        self.ufo_timer -= 1
        if self.ufo_timer <= 0 and self.ufo is None:
            self.ufo = UFO()
            self.ufo_timer = random.randint(500, 900)
        if self.ufo:
            self.ufo.update()
            if not self.ufo.alive:
                self.ufo = None

        # Boss
        if self.boss:
            self.boss.update(self.bullets, self.ps, p.x)
            self._check_boss_hits()
            if not self.boss.alive:
                self._kill_boss()

        # Aliens movement
        else:
            self._move_aliens()
            self._alien_shoot()

        # Bullets
        for b in self.bullets:
            b.update()
        self.bullets = [b for b in self.bullets if b.alive]

        # Power-ups
        for pu in self.powerups:
            pu.update()
        self.powerups = [pu for pu in self.powerups if pu.alive]

        self._check_player_bullets()
        self._check_alien_bullets()
        self._check_powerups()
        self._check_alien_reach()
        self._check_wave_clear()

    # ── alien movement ─────────────────────────────────────────────────────
    def _move_aliens(self):
        rate  = self._move_rate()
        slow  = self.player.slow_t > 0
        if slow:
            rate = rate * 3
        self.move_timer += 1
        if self.move_timer < rate:
            return
        self.move_timer = 0
        self.anim_frame ^= 1

        xs = [a.x for a in self.alive_aliens]
        if not xs:
            return
        shift = False
        nl = min(xs) + self.STEP_X * self.move_dir
        nr = max(xs) + self.STEP_X * self.move_dir
        if nl < 30 or nr > W - 30:
            self.move_dir *= -1
            shift = True

        for a in self.alive_aliens:
            a.frame = self.anim_frame
            if shift:
                a.y += self.STEP_DOWN
            else:
                a.x += self.STEP_X * self.move_dir

    # ── alien shooting ─────────────────────────────────────────────────────
    def _alien_shoot(self):
        alive = self.alive_aliens
        if not alive:
            return
        rate  = max(18, 70 - self.level * 5)
        if self.player.slow_t > 0:
            rate = rate * 2
        # only bottom aliens in each column can shoot
        columns: dict = {}
        for a in alive:
            if a.col not in columns or a.row > columns[a.col].row:
                columns[a.col] = a
        shooters = list(columns.values())
        if random.randint(0, rate) == 0 and shooters:
            shooter = random.choice(shooters)
            btype   = 'normal'
            if self.level >= 4 and random.random() < 0.2:
                btype = 'spiral'
            if self.level >= 7 and random.random() < 0.15:
                btype = 'wave'
            spd = min(10, 5 + self.level * 0.4)
            self.bullets.append(Bullet(shooter.x, shooter.y + 20,
                0, spd, shooter.colour, damage=1, owner='alien', btype=btype))

    # ── collision helpers ───────────────────────────────────────────────────
    def _check_player_bullets(self):
        pbullets = [b for b in self.bullets if b.owner == 'player' and b.alive]
        for b in pbullets:
            # shields
            for sh in self.shields:
                if sh.collides(b.rect):
                    sh.hit(b.x, b.y)
                    b.alive = False
                    break
            if not b.alive:
                continue
            # aliens
            for a in self.alive_aliens:
                if b.rect.colliderect(a.rect):
                    a.hp        -= b.damage
                    a.hit_flash  = 6
                    b.alive      = False
                    self.ps.emit(8, a.x, a.y, [a.colour, WHITE, NEON_Y],
                                 speed=4, life=25, size=3)
                    if a.hp <= 0:
                        a.alive = False
                        pts = self.combo.hit(a.x, a.y, a.pts())
                        self.score     += pts
                        self.hi_score   = max(self.hi_score, self.score)
                        self.ps.emit(20, a.x, a.y, [a.colour, WHITE, NEON_Y],
                                     speed=6, life=40, size=4, gravity=0.08)
                        self.shake.start(6, 4)
                        if random.random() < 0.08 + self.level * 0.01:
                            self._drop_powerup(a.x, a.y)
                    break
            if not b.alive:
                continue
            # UFO
            if self.ufo and b.rect.colliderect(self.ufo.rect):
                self.ufo.hp -= b.damage
                b.alive = False
                self.ps.emit(6, self.ufo.x, self.ufo.y,
                             [NEON_R, NEON_O, WHITE], speed=4, life=20)
                if self.ufo.hp <= 0:
                    pts = self.combo.hit(self.ufo.x, self.ufo.y, self.ufo.pts)
                    self.score    += pts
                    self.hi_score  = max(self.hi_score, self.score)
                    self.ps.emit(30, self.ufo.x, self.ufo.y,
                                 [NEON_R, NEON_O, WHITE, NEON_Y],
                                 speed=7, life=50, size=5, gravity=0.06)
                    self.shake.start(10, 8)
                    self.ufo.alive = False
                    self.ufo = None

    def _check_boss_hits(self):
        if not self.boss:
            return
        pbullets = [b for b in self.bullets if b.owner == 'player' and b.alive]
        for b in pbullets:
            if b.rect.colliderect(self.boss.rect):
                result = self.boss.take_hit(b.damage)
                b.alive = False
                self.ps.emit(10, b.x, b.y,
                             [self.boss.colour, WHITE], speed=5, life=25, size=4)
                if result == 'phase':
                    self.shake.start(20, 14)
                    self.banner.show("PHASE TRANSITION!", "", 80, NEON_O)
                    self.ps.emit(60, self.boss.x, self.boss.y,
                                 [self.boss.colour, WHITE, NEON_Y],
                                 speed=10, life=60, size=6, gravity=0.05)
                elif result == 'dead':
                    pass  # handled in update

    def _kill_boss(self):
        b = self.boss
        pts = self.combo.hit(b.x, b.y, b.pts)
        self.score    += pts
        self.hi_score  = max(self.hi_score, self.score)
        self.ps.emit(120, b.x, b.y,
                     [b.colour, NEON_O, NEON_Y, WHITE],
                     speed=14, life=80, size=7, gravity=0.04)
        self.shake.start(30, 18)
        self.banner.show("BOSS  DEFEATED!", f"+{b.pts} pts", 160, NEON_G)
        self.boss = None
        for _ in range(3):
            self._drop_powerup(
                random.uniform(W*0.2, W*0.8),
                random.uniform(H*0.2, H*0.5))
        save_hi(self.hi_score)

    def _check_alien_bullets(self):
        abullets = [b for b in self.bullets if b.owner == 'alien' and b.alive]
        p = self.player
        for b in abullets:
            # shields
            for sh in self.shields:
                if sh.collides(b.rect):
                    sh.hit(b.x, b.y)
                    b.alive = False
                    break
            if not b.alive:
                continue
            # player
            if b.rect.colliderect(p.rect):
                if p.take_hit(b.damage):
                    b.alive = False
                    self.ps.emit(15, p.x, p.y,
                                 [NEON_G, WHITE, NEON_Y], speed=5, life=30, size=4)
                    self.shake.start(12, 10)
                    if not p.alive:
                        self.state = 'over'
                        save_hi(self.hi_score)
                        self.ps.emit(60, p.x, p.y,
                                     [NEON_G, WHITE, NEON_O],
                                     speed=10, life=70, size=6, gravity=0.05)

    def _check_powerups(self):
        for pu in self.powerups:
            if not pu.alive:
                continue
            if pu.rect.colliderect(self.player.rect):
                if pu.ptype == 'nuke':
                    self._nuke()
                else:
                    self.player.apply_powerup(pu.ptype)
                pu.alive = False
                self.ps.emit(20, pu.x, pu.y,
                             [pu.colour, WHITE], speed=5, life=30, size=4)

    def _nuke(self):
        self.nuke_flash = 30
        self.shake.start(25, 15)
        for a in self.alive_aliens:
            a.alive = False
            self.ps.emit(12, a.x, a.y, [a.colour, WHITE, NEON_Y],
                         speed=6, life=35, size=4, gravity=0.06)
            pts = self.combo.hit(a.x, a.y, a.pts())
            self.score    += pts
            self.hi_score  = max(self.hi_score, self.score)
        if self.boss:
            for _ in range(10):
                result = self.boss.take_hit(5)
                if result == 'dead':
                    self._kill_boss()
                    break
        self.banner.show("N U K E !", "", 80, NEON_P)

    def _check_alien_reach(self):
        for a in self.alive_aliens:
            if a.y > self.player.y - 20:
                self.state = 'over'
                save_hi(self.hi_score)
                return

    def _check_wave_clear(self):
        if self.state != 'title' and self.state not in ('over', 'win_all'):
            if self.boss is None and not self.alive_aliens:
                self.level += 1
                if self.level > 15:
                    self.state = 'win_all'
                    save_hi(self.hi_score)
                else:
                    self._start_level()

    def _drop_powerup(self, x, y):
        ptype = random.choice(POWERUP_TYPES)
        self.powerups.append(PowerUp(x, y, ptype))

    # ── draw ───────────────────────────────────────────────────────────────
    def draw(self):
        c = self.canvas
        c.fill(DARK)
        self.stars.draw(c)

        if self.state == 'title':
            self._draw_title(c)
        elif self.state == 'over':
            self._draw_game(c)
            self._draw_over(c)
        elif self.state == 'win_all':
            self._draw_game(c)
            self._draw_win(c)
        elif self.pause:
            self._draw_game(c)
            self._draw_pause(c)
        else:
            self._draw_game(c)

        # Nuke flash
        if self.nuke_flash > 0:
            fl = pygame.Surface((W, H), pygame.SRCALPHA)
            a  = int(200 * self.nuke_flash / 30)
            fl.fill((200, 80, 255, a))
            c.blit(fl)

        # Screen shake blit
        ox, oy = self.shake.get_offset()
        self.screen.fill(BLACK)
        self.screen.blit(c, (ox, oy))
        pygame.display.flip()

    def _draw_game(self, c):
        # Shields
        for sh in self.shields:
            sh.draw(c)

        # Power-ups
        for pu in self.powerups:
            pu.draw(c)

        # Aliens
        for a in self.alive_aliens:
            a.draw(c)

        # Boss
        if self.boss:
            self.boss.draw(c)

        # UFO
        if self.ufo:
            self.ufo.draw(c)

        # Bullets
        for b in self.bullets:
            b.draw(c)

        # Player
        self.player.draw(c)

        # Particles
        self.ps.draw(c)

        # Combo
        self.combo.draw(c)

        # Banner
        self.banner.draw(c)

        # HUD
        self._draw_hud(c)

    def _draw_hud(self, c):
        # Top bar
        pygame.draw.line(c, NEON_G, (0, 44), (W, 44), 2)
        draw_text(c, f"SCORE  {self.score:08d}",  10,  8, NEON_G, 22)
        draw_text(c, f"HI  {self.hi_score:08d}", W//2, 8, WHITE, 22, center=True)
        draw_text(c, f"LVL {self.level}", W-100, 8, NEON_B, 22)

        # Power-up timers (bottom bar)
        y = H - 36
        x = W - 10
        pups = [
            ('SLOW',   self.player.slow_t,   NEON_B),
            ('SHIELD', self.player.shield_t,  NEON_G),
            ('LASER',  self.player.laser_t,   NEON_R),
            ('3X',     self.player.triple_t,  NEON_B),
            ('RAPID',  self.player.rapid_t,   NEON_Y),
        ]
        for label, t, col in pups:
            if t > 0:
                bar = int(60 * t / 300)
                x  -= 75
                pygame.draw.rect(c, (40,40,40), (x, y, 60, 8))
                pygame.draw.rect(c, col, (x, y, bar, 8))
                draw_text(c, label, x + 30, y - 18, col, 14, center=True)

    def _draw_title(self, c):
        # Animate some aliens as decoration
        t = pygame.time.get_ticks() // 500
        for i, (atype, col, x, y) in enumerate([
            (0, NEON_R, W//2 - 140, 300),
            (1, NEON_O, W//2 -  70, 300),
            (2, NEON_Y, W//2,       300),
            (3, NEON_B, W//2 +  70, 300),
            (4, NEON_P, W//2 + 140, 300),
        ]):
            draw_alien_sprite(c, atype, (t+i)%2, col, x, y, scale=4)

        draw_text_outline(c, "SPACE  INVADERS", W//2, 120,
                          NEON_G, size=54, center=True)
        draw_text(c, "ADVANCED  EDITION", W//2, 185,
                  NEON_B, 26, center=True)

        rows = [
            (NEON_R, "50 PTS", 0),
            (NEON_O, "40 PTS", 1),
            (NEON_Y, "30 PTS", 2),
            (NEON_B, "20 PTS", 3),
            (NEON_P, "10 PTS", 4),
        ]
        for col, label, i in rows:
            draw_alien_sprite(c, i, 0, col, W//2 - 80, 380 + i*44, scale=3)
            draw_text(c, label, W//2 - 50, 370 + i*44, col, 18)

        draw_text(c, f"HI SCORE:  {self.hi_score:08d}",
                  W//2, 610, WHITE, 24, center=True)

        if (pygame.time.get_ticks() // 500) % 2 == 0:
            draw_text_outline(c, "PRESS  SPACE  TO  START",
                              W//2, 660, NEON_G, size=30, center=True)

        draw_text(c, "WASD/ARROWS: MOVE   SPACE: SHOOT   P: PAUSE",
                  W//2, 700, GRAY, 16, center=True)

    def _draw_over(self, c):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 160))
        c.blit(s, (0, 0))
        draw_text_outline(c, "GAME  OVER", W//2, H//2 - 80,
                          NEON_R, size=56, center=True)
        draw_text(c, f"SCORE:  {self.score:08d}", W//2, H//2,
                  WHITE, 30, center=True)
        draw_text(c, f"HI SCORE:  {self.hi_score:08d}", W//2, H//2+40,
                  NEON_Y, 26, center=True)
        draw_text(c, f"REACHED WAVE {self.level}", W//2, H//2+80,
                  NEON_B, 22, center=True)
        if (pygame.time.get_ticks()//500)%2==0:
            draw_text(c, "PRESS  R  TO  RESTART", W//2, H//2+130,
                      NEON_G, 26, center=True)

    def _draw_win(self, c):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 160))
        c.blit(s, (0, 0))
        draw_text_outline(c, "YOU  WIN!", W//2, H//2 - 80,
                          NEON_G, size=60, center=True)
        draw_text(c, "EARTH  IS  SAVED!", W//2, H//2,
                  NEON_B, 28, center=True)
        draw_text(c, f"FINAL SCORE: {self.score:08d}", W//2, H//2+50,
                  NEON_Y, 30, center=True)
        if (pygame.time.get_ticks()//500)%2==0:
            draw_text(c, "PRESS  R  TO  PLAY  AGAIN", W//2, H//2+110,
                      NEON_G, 26, center=True)

    def _draw_pause(self, c):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 140))
        c.blit(s, (0, 0))
        draw_text_outline(c, "PAUSED", W//2, H//2 - 30,
                          NEON_Y, size=52, center=True)
        draw_text(c, "P = RESUME", W//2, H//2+40, WHITE, 26, center=True)

    # ── events ──────────────────────────────────────────────────────────────
    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        k = event.key

        if self.state == 'title':
            if k in (pygame.K_SPACE, pygame.K_RETURN):
                self.state = 'playing'
            return

        if self.state in ('over', 'win_all'):
            if k == pygame.K_r:
                self._new_game()
                self.state = 'playing'
            return

        if k == pygame.K_p:
            self.pause = not self.pause

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("SPACE INVADERS  –  ADVANCED EDITION")
    clock  = pygame.time.Clock()
    game   = Game(screen)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                save_hi(game.hi_score)
                pygame.quit()
                sys.exit()
            game.handle_event(event)

        game.update()
        game.draw()
        clock.tick(FPS)


if __name__ == "__main__":
    main()