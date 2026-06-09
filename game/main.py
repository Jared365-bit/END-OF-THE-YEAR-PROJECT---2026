import pygame
import json
import random
import os

pygame.init()
WIDTH, HEIGHT = 800, 450
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Cyberpunk Runner")
clock = pygame.time.Clock()

# ─── COLORS ──────────────────────────────────────────────────────────────────
BLACK        = (10, 10, 15)
NEON_CYAN    = (0, 255, 240)
NEON_PINK    = (255, 0, 127)
WHITE        = (255, 255, 255)

# Obstacle palette
OBS_DARK     = (15, 25, 40)
OBS_MID      = (38, 60, 88)
OBS_STEEL    = (65, 100, 132)
OBS_GLOW     = (0, 210, 200)
OBS_WARN     = (225, 130, 0)
OBS_DANGER   = (210, 35, 60)

# ─── GAME VARIABLES ──────────────────────────────────────────────────────────
SAVE_FILE     = "cyber_save.json"
current_state = "MENU"
score         = 0
high_score    = 0
level         = 1
game_speed    = 7.0
FLOOR_Y       = 325

# ─── BACKGROUND  ────────────
_bg_loaded = False
for _name in ["pixel-art-sci-fi-city-260nw-2513324703.jpg", "background.jpg", "bg.jpg"]:
    try:
        _raw = pygame.image.load(_name).convert()
        bg_image = pygame.transform.scale(_raw, (WIDTH, HEIGHT))
        _bg_loaded = True
        break
    except (pygame.error, FileNotFoundError, OSError):
        pass
if not _bg_loaded:
    bg_image = pygame.Surface((WIDTH, HEIGHT))
    bg_image.fill((20, 30, 50))

bg_scroll = 0.0   # single float, mod WIDTH — guarantees seamless tiling

# ─── CUSTOMISATION ────────────────────────────────────────────────────────────
TRAIL_COLORS   = {"CYAN": NEON_CYAN, "PINK": NEON_PINK}
selected_trail = "CYAN"

# ─── SAVE / LOAD ──────────────────────────────────────────────────────────────
def load_game():
    global high_score, selected_trail
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE) as f:
                d = json.load(f)
                high_score     = d.get("high_score", 0)
                selected_trail = d.get("selected_trail", "CYAN")
        except Exception:
            pass

def save_game():
    with open(SAVE_FILE, "w") as f:
        json.dump({"high_score": high_score, "selected_trail": selected_trail}, f)

load_game()

# ─── TEXT ─────────────────────────────────────────────────────────────────────
font = pygame.font.SysFont("Courier New", 24, bold=True)
def draw_text(text, color, x, y):
    screen.blit(font.render(text, True, color), (x, y))



P = 4

def px(surf, color, col, row, w=1, h=1):
    """Paint a w×h block of macro-pixels at grid position (col, row)."""
    pygame.draw.rect(surf, color, (col * P, row * P, w * P, h * P))


def make_rubble():
    """
    Irregular heap of broken bridge / concrete debris.
    Low obstacle — easy to clear with a normal jump.
    """
    cols    = random.randint(10, 16)
    profile = [random.randint(3, 8) for _ in range(cols)]
    rows    = max(profile)
    surf    = pygame.Surface((cols * P, rows * P), pygame.SRCALPHA)

    for c, ht in enumerate(profile):
        for r in range(rows - ht, rows):
            depth = r - (rows - ht)
            if depth == 0:
                col = random.choice([OBS_STEEL, OBS_MID])   # top face lighter
            elif random.random() < 0.06:
                col = OBS_GLOW                                # scattered tech shards
            else:
                col = random.choice([OBS_DARK, OBS_MID, OBS_MID])
            px(surf, col, c, r)

    rect = pygame.Rect(WIDTH + 10, FLOOR_Y - rows * P, cols * P, rows * P)
    return surf, rect


def make_spikes():
    """
    Upward metal security spikes on a base plate.
    Medium-tall obstacle — requires a full jump.
    """
    n   = random.randint(3, 6)
    sw  = 3                           # spike width in macro-pixels (must be odd)
    sh  = random.randint(7, 11)       # spike height
    bh  = 3                           # base plate height
    gap = 1                           # gap between spikes
    cols = n * sw + (n - 1) * gap
    rows = sh + bh
    surf = pygame.Surface((cols * P, rows * P), pygame.SRCALPHA)


    for c in range(cols):
        px(surf, OBS_DARK,  c, sh)
        px(surf, OBS_STEEL, c, sh + 1)
        px(surf, OBS_MID,   c, sh + 2)

    
    for s in range(n):
        base_c = s * (sw + gap)
        for c in range(sw):
            dist      = abs(c - sw // 2)   # 0 = centre, grows toward edge
            spike_top = dist * 2            # row where this column begins
            for r in range(spike_top, sh):
                is_tip = (c == sw // 2 and r < spike_top + 2)
                px(surf, OBS_WARN if is_tip else OBS_STEEL, base_c + c, r)

    rect = pygame.Rect(WIDTH + 10, FLOOR_Y - rows * P, cols * P, rows * P)
    return surf, rect


def make_wall_chunk():
    """
    Fragment of a destroyed building — dark blue-grey with pixel windows.
    Tall, narrow obstacle — requires early jump reaction.
    """
    cols = random.randint(6, 10)
    rows = random.randint(10, 15)
    surf = pygame.Surface((cols * P, rows * P), pygame.SRCALPHA)

    for c in range(cols):
        for r in range(rows):
            # Crumbled top-right corner for a broken look
            if c >= cols - 2 and r <= 2 and random.random() < 0.65:
                continue
            shade = OBS_MID if (c + r) % 3 != 1 else OBS_DARK
            px(surf, shade, c, r)

    # Pixel windows
    for _ in range(random.randint(2, 5)):
        wc  = random.randint(0, cols - 2)
        wr  = random.randint(1, rows - 3)
        lit = random.random() < 0.4
        win = OBS_GLOW if lit else (5, 10, 20)
        for dc in range(2):
            for dr in range(2):
                if wc + dc < cols and wr + dr < rows:
                    px(surf, win, wc + dc, wr + dr)

    rect = pygame.Rect(WIDTH + 10, FLOOR_Y - rows * P, cols * P, rows * P)
    return surf, rect


def make_barrier():
    """
    Security checkpoint barrier: two posts + a warning-striped arm.
    Wide, low obstacle — tests timing rather than jump height.
    """
    cols = random.randint(9, 14)
    rows = random.randint(5, 8)
    surf = pygame.Surface((cols * P, rows * P), pygame.SRCALPHA)

    # Vertical posts
    for r in range(rows):
        px(surf, OBS_STEEL, 0,        r)
        px(surf, OBS_STEEL, cols - 1, r)

   
    for c in range(cols):
        stripe = OBS_WARN if (c // 2) % 2 == 0 else OBS_DARK
        px(surf, stripe, c, 0)
        px(surf, stripe, c, 1)

    # Warning lights on post tops
    px(surf, OBS_GLOW,   0,        2)
    px(surf, OBS_DANGER, cols - 1, 2)

    rect = pygame.Rect(WIDTH + 10, FLOOR_Y - rows * P, cols * P, rows * P)
    return surf, rect


FACTORIES = [make_rubble, make_spikes, make_wall_chunk, make_barrier]

# ─── SPRITE SHEET LAYOUT
SPRITE_COL_START = 128
SPRITE_COL_W     = 57

ANIM_DEFS = {
    "HURT":       (43,  42, 2),
    "IDLE":       (99,  44, 4),
    "JUMP":       (150, 48, 4),
    "PUNCH":      (213, 43, 6),
    "RUN":        (271, 42, 6),
    "RUN_ATTACK": (329, 40, 6),
}

# ─── PLAYER ───────────────────────────────────────────────────────────────────
class Player:
    def __init__(self):
        self.rect       = pygame.Rect(100, FLOOR_Y - 60, 30, 60)
        self.velocity_y = 0
        self.is_jumping = False

        
        self.trail   = []
        self._world_x = 0.0

        # Load sprite sheet
        try:
            raw = pygame.image.load("2x9zPD-removebg-preview.png").convert()
        except pygame.error:
            raw = pygame.Surface((612, 408))

        self.animations = {}
        for name, (y0, rh, nf) in ANIM_DEFS.items():
            frames = []
            for col in range(nf):
                x    = SPRITE_COL_START + col * SPRITE_COL_W
                cell = pygame.Surface((SPRITE_COL_W, rh))
                cell.fill((0, 0, 0))
                cell.blit(raw, (0, 0), (x, y0, SPRITE_COL_W, rh))
                cell.set_colorkey((0, 0, 0))
                sh = 80
                sw = int(SPRITE_COL_W * sh / rh)
                frames.append(pygame.transform.scale(cell, (sw, sh)))
            self.animations[name] = frames

        self.action      = "RUN"
        self.frame_index = 0.0
        self.anim_speed  = 0.20

    def jump(self):
        if not self.is_jumping:
            self.velocity_y  = -14
            self.is_jumping  = True
            self.action      = "JUMP"
            self.frame_index = 0.0

    def update(self):
        # Physics
        self.velocity_y += 0.6
        self.rect.y     += self.velocity_y
        if self.rect.bottom >= FLOOR_Y:
            self.rect.bottom = FLOOR_Y
            self.velocity_y  = 0
            if self.is_jumping:
                self.is_jumping  = False
                self.action      = "RUN"
                self.frame_index = 0.0

        # Animation state
        if not self.is_jumping:
            self.action = "RUN" if current_state == "PLAYING" else "IDLE"
        frames = self.animations[self.action]
        self.frame_index = (self.frame_index + self.anim_speed) % len(frames)

        # ── Trail ──────────────────────────────────────────────────────────────
        # Advance the virtual world-x by game_speed each frame.
        # When we draw, older points have a smaller world_x than the current
        # one, so they render to the LEFT of the player — a proper motion trail.
        self._world_x += game_speed
        self.trail.append((self._world_x, float(self.rect.centery)))
        MAX_TRAIL = 8
        if len(self.trail) > MAX_TRAIL:
            self.trail.pop(0)

    def draw(self):
        # ── Trail ──────────────────────────────────────────────────────────────
        if len(self.trail) >= 2:
            latest_wx = self.trail[-1][0]
            color     = TRAIL_COLORS[selected_trail]
            n         = len(self.trail)
            for i, (wx, wy) in enumerate(self.trail):
                frac = (i + 1) / n   # 0 < frac <= 1, grows toward player
                sx   = int(self.rect.centerx - (latest_wx - wx))
                sy   = int(wy)

                # Subtle glow halo — fades to nothing at the tail
                glow_r = max(1, int(5 * frac))
                glow_c = tuple(int(c * frac * 0.20) for c in color)
                pygame.draw.circle(screen, glow_c, (sx, sy), glow_r)

                # Small bright core — 1-3 px, fully fades out at tail
                core_r = max(1, int(3 * frac))
                core_c = tuple(int(c * frac) for c in color)
                pygame.draw.circle(screen, core_c, (sx, sy), core_r)

        # ── Sprite ─────────────────────────────────────────────────────────────
        frame    = self.animations[self.action][int(self.frame_index)]
        img_rect = frame.get_rect()
        img_rect.midbottom = self.rect.midbottom
        screen.blit(frame, img_rect.topleft)


# ─── OBSTACLE ─────────────────────────────────────────────────────────────────
class Obstacle:
    def __init__(self):
        self.surf, self.rect = random.choice(FACTORIES)()

    def update(self):
        self.rect.x -= int(game_speed)

    def draw(self):
        screen.blit(self.surf, self.rect.topleft)


# ─── INIT ─────────────────────────────────────────────────────────────────────
player         = Player()
obstacles      = []
obstacle_timer = 0

# ─── MAIN LOOP ────────────────────────────────────────────────────────────────
running = True
while running:
    clock.tick(60)
    screen.fill(BLACK)

    # ── Seamless background scroll ─────────────────────────────────────────────
    # bg_scroll goes 0 → WIDTH then wraps.  Two blits: at -bx and WIDTH-bx.
    # At any bx value they are exactly WIDTH apart → zero-gap guarantee.
    if current_state == "PLAYING":
        bg_scroll = (bg_scroll + game_speed * 0.35) % WIDTH
    bx = int(bg_scroll)
    screen.blit(bg_image, (-bx, 0))
    screen.blit(bg_image, (WIDTH - bx, 0))

    # ── Events ────────────────────────────────────────────────────────────────
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if current_state == "MENU":
                if event.key == pygame.K_SPACE:
                    current_state = "PLAYING"
                if event.key == pygame.K_c:
                    selected_trail = "PINK" if selected_trail == "CYAN" else "CYAN"
                    save_game()
            elif current_state == "PLAYING":
                if event.key == pygame.K_SPACE:
                    player.jump()
            elif current_state == "GAME_OVER":
                if event.key == pygame.K_SPACE:
                    player         = Player()
                    obstacles      = []
                    score          = 0
                    level          = 1
                    game_speed     = 7.0
                    current_state  = "PLAYING"

    # ── State machine ─────────────────────────────────────────────────────────
    if current_state == "MENU":
        player.update()
        player.draw()
        draw_text("CYBERPUNK RUNNER",              NEON_CYAN, WIDTH//2 - 120, 100)
        draw_text("[SPACE] TO START",              WHITE,     WIDTH//2 - 110, 180)
        draw_text(f"[C] TRAIL: {selected_trail}", NEON_PINK, WIDTH//2 - 120, 240)
        draw_text(f"HIGH SCORE: {high_score}",    WHITE,     WIDTH//2 -  90, 300)
        
    elif current_state == "PLAYING":
        score += 1
        if score % 500 == 0:
            level      += 1
            game_speed += 1.5

        player.update()
        player.draw()

        obstacle_timer += 1
        if obstacle_timer > random.randint(70, 140):
            obstacles.append(Obstacle())
            obstacle_timer = 0

        for obs in obstacles[:]:
            obs.update()
            obs.draw()
            if player.rect.colliderect(obs.rect):
                player.action = "HURT"
                current_state = "GAME_OVER"
                if score > high_score:
                    high_score = score
                    save_game()
            if obs.rect.right < 0:
                obstacles.remove(obs)

        draw_text(f"SCORE: {score}",                        WHITE,     20, 20)
        draw_text(f"LEVEL: {level}  SPD: {game_speed:.1f}", NEON_CYAN, 20, 50)

    elif current_state == "GAME_OVER":
        player.update()
        player.draw()
        draw_text("SYSTEM CRASHED",            NEON_PINK, WIDTH//2 - 100, 120)
        draw_text(f"FINAL SCORE: {score}",     WHITE,     WIDTH//2 -  90, 180)
        draw_text(f"HIGH SCORE: {high_score}", NEON_CYAN, WIDTH//2 -  90, 220)
        draw_text("[SPACE] TO REBOOT",         WHITE,     WIDTH//2 - 110, 300)

    pygame.display.flip()

pygame.quit()

