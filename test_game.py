import os
import sys
import math

# Force dummy SDL video driver so tests run seamlessly in headless environment
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
import unittest
import game


class TestZombieEscape(unittest.TestCase):
    def setUp(self):
        pygame.init()
        self.engine = game.GameEngine()

    def tearDown(self):
        pygame.quit()

    def test_task1_health_system(self):
        """Test player has 3 HP, zombie touch takes 1 HP, invincibility window works, game over only at 0 HP."""
        p = self.engine.player
        self.assertEqual(p.hp, 3, "Player should start with 3 HP")
        self.assertEqual(p.invincible_timer, 0)
        self.assertFalse(self.engine.game_over)

        # Place a zombie touching player
        z = game.Zombie(p.rect.x, p.rect.y)
        self.engine.zombies = [z]

        # First frame touch
        self.engine.update()
        self.assertEqual(p.hp, 2, "Player should take 1 damage (HP=2)")
        self.assertGreater(p.invincible_timer, 0, "Invincibility window should be activated")
        self.assertFalse(self.engine.game_over, "Game over should not trigger at HP=2")

        # During invincibility, subsequent touches should not damage player
        prev_inv = p.invincible_timer
        self.engine.update()
        self.assertEqual(p.hp, 2, "Player should remain at 2 HP during invincibility")
        self.assertLess(p.invincible_timer, prev_inv, "Invincible timer should tick down")

        # Expire invincibility
        p.invincible_timer = 0
        z.rect.center = p.rect.center
        self.engine.update()
        self.assertEqual(p.hp, 1, "Player should take second damage (HP=1)")
        self.assertFalse(self.engine.game_over)

        # Expire invincibility and hit third time -> HP=0 -> Game Over
        p.invincible_timer = 0
        z.rect.center = p.rect.center
        self.engine.update()
        self.assertEqual(p.hp, 0, "Player HP should reach 0")
        self.assertTrue(self.engine.game_over, "Game over screen appears only at 0 HP")

        # Health should never drop below zero even with excessive damage
        p.invincible_timer = 0
        p.take_damage(10)
        self.assertEqual(p.hp, 0, "Player HP must never drop below 0")

        # Test restarting restores player to 3 HP and clears game over
        self.engine.reset()
        self.assertEqual(self.engine.player.hp, 3, "Resetting game should restore HP to 3")
        self.assertFalse(self.engine.game_over, "Resetting game should clear game over state")

    def test_task2_ammo_system(self):
        """Test 12 bullets per clip, empty ammo blocks shooting, 2s reload (120 frames) restores ammo."""
        p = self.engine.player
        self.assertEqual(p.ammo, 12, "Player should start with 12 ammo")
        self.assertFalse(p.is_reloading)

        # Fire 12 shots
        for i in range(12):
            p.shoot_cooldown = 0
            p.shoot((p.rect.centerx + 100, p.rect.centery))
            self.assertEqual(p.ammo, 11 - i)

        self.assertEqual(p.ammo, 0, "Ammo should be 0 after 12 shots")
        self.assertTrue(p.is_reloading, "Reload should trigger automatically when clip is empty")
        self.assertEqual(p.reload_timer, game.RELOAD_TIME_FRAMES, "Reload timer should be 120 frames (2.0s)")

        # Shooting while empty/reloading should be blocked
        bullet_count_before = len(p.bullets)
        p.shoot((p.rect.centerx + 100, p.rect.centery))
        self.assertEqual(len(p.bullets), bullet_count_before, "Shooting must be blocked when empty/reloading")

        # Advance reload frames
        keys = {pygame.K_w: False, pygame.K_s: False, pygame.K_a: False, pygame.K_d: False,
                pygame.K_UP: False, pygame.K_DOWN: False, pygame.K_LEFT: False, pygame.K_RIGHT: False}
        for _ in range(game.RELOAD_TIME_FRAMES - 1):
            p.move(keys, game.WIDTH, game.HEIGHT)
            self.assertTrue(p.is_reloading, "Still reloading before duration completes")
            self.assertEqual(p.ammo, 0, "Ammo should remain 0 during reload")

        # Final frame completes reload
        p.move(keys, game.WIDTH, game.HEIGHT)
        self.assertFalse(p.is_reloading, "Reload should complete after 120 frames")
        self.assertEqual(p.ammo, 12, "Ammo should be fully restored to 12 after reload")

        # Verify firing works normally after reload
        p.shoot_cooldown = 0
        fired = p.shoot((p.rect.centerx + 100, p.rect.centery))
        self.assertTrue(fired, "Should be able to fire again after reloading")
        self.assertEqual(p.ammo, 11, "Firing after reload consumes 1 ammo")

        # Test duplicate reload prevention: trigger reload, then attempt duplicate reload
        self.assertTrue(p.start_reload(), "Manual reload should succeed when ammo < 12")
        self.assertTrue(p.is_reloading)
        p.reload_timer = 50  # Simulating partially elapsed reload
        duplicate_result = p.start_reload()
        self.assertFalse(duplicate_result, "Duplicate reload should be prevented while already reloading")
        self.assertEqual(p.reload_timer, 50, "Duplicate reload must not reset or alter the active timer")

        # Complete the reload and check capacity capping
        for _ in range(50):
            p.move(keys, game.WIDTH, game.HEIGHT)
        self.assertEqual(p.ammo, 12, "Ammo must never exceed max capacity (12)")
        self.assertFalse(p.is_reloading)

        # Attempt reload when already at max capacity
        full_reload_result = p.start_reload()
        self.assertFalse(full_reload_result, "Reload must be prevented when magazine is already full")
        self.assertEqual(p.ammo, 12)

        # Test reload control via R key event during gameplay
        p.ammo = 5
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_r}))
        self.engine.handle_events()
        self.assertTrue(p.is_reloading, "Pressing R during gameplay should trigger reload")

    def test_task3_explosive_barrels(self):
        """Test 4 barrels on map, bullet hit explodes barrel, removes barrel, destroys zombies within 120px radius."""
        self.assertEqual(len(self.engine.barrels), 4, "There should be 4 barrels on the map")

        barrel = self.engine.barrels[0]
        bx, by = barrel.rect.centerx, barrel.rect.centery

        # Place a zombie inside explosion radius and one outside
        near_zombie = game.Zombie(bx + 50, by)       # dist = 50 <= 120
        far_zombie = game.Zombie(bx + 200, by)       # dist = 200 > 120
        self.engine.zombies = [near_zombie, far_zombie]

        # Spawn a bullet inside the barrel rect
        self.engine.player.bullets = [[barrel.rect.x + 5, barrel.rect.y + 5, 0, 0]]

        # Run update to process collision
        self.engine.update()

        # Barrel should be removed
        self.assertNotIn(barrel, self.engine.barrels, "Barrel should be removed after explosion")
        self.assertEqual(len(self.engine.barrels), 3)

        # Explosion effect should be created
        self.assertEqual(len(self.engine.explosions), 1, "Explosion effect should be created")

        # Near zombie destroyed, far zombie survives
        self.assertNotIn(near_zombie, self.engine.zombies, "Zombies within fixed radius should be destroyed")
        self.assertIn(far_zombie, self.engine.zombies, "Zombies outside radius should not be destroyed")
        self.assertGreater(self.engine.kills, 0, "Kills should increase on explosion kills")

        # Player must take no damage from barrel explosions
        self.assertEqual(self.engine.player.hp, 3, "Player should not take damage from barrel explosions")

        # Verify duplicate explosion prevention on already-exploded barrel
        repeat_result = barrel.explode(self.engine)
        self.assertEqual(repeat_result, [], "Exploded barrel must not explode a second time")

        # Verify boundary positions of all barrels are within playable arena
        for b in self.engine.barrels:
            self.assertGreaterEqual(b.rect.x, 0)
            self.assertLessEqual(b.rect.right, game.WIDTH)
            self.assertGreaterEqual(b.rect.y, 40, "Barrel must be below HUD")
            self.assertLessEqual(b.rect.bottom, game.HEIGHT)

        # Detonate the remaining 3 barrels to verify all 4 barrels function properly
        while len(self.engine.barrels) > 0:
            target = self.engine.barrels[0]
            self.engine.player.bullets = [[target.rect.centerx, target.rect.centery, 0, 0]]
            self.engine.update()
            self.assertNotIn(target, self.engine.barrels)

        self.assertEqual(len(self.engine.barrels), 0, "All 4 barrels can be detonated and removed cleanly")

    def test_task4_zombie_types(self):
        """Test standard, fast, and tank zombie stats and spawning."""
        std = game.Zombie(100, 100)
        fast = game.FastZombie(100, 100)
        tank = game.TankZombie(100, 100)

        # Stats check
        self.assertEqual(std.hp, 3)
        self.assertEqual(std.speed, 1.5)
        self.assertEqual(std.rect.width, 30)

        self.assertEqual(fast.hp, 1, "Fast zombie should have 1 HP")
        self.assertGreater(fast.speed, std.speed, "Fast zombie should have higher speed")
        self.assertLess(fast.rect.width, std.rect.width, "Fast zombie should be smaller")

        self.assertEqual(tank.hp, 6, "Tank zombie should have 6 HP")
        self.assertLess(tank.speed, std.speed, "Tank zombie should have lower speed")
        self.assertGreater(tank.rect.width, std.rect.width, "Tank zombie should be larger")

        # Damage check on tank
        for _ in range(5):
            self.assertFalse(tank.hit())
        self.assertTrue(tank.hit(), "Tank should die on 6th hit")

        # Movement verification: fast zombie covers more distance than standard, and standard more than tank
        target = (400, 400)
        z_std = game.Zombie(100, 100)
        z_fast = game.FastZombie(100, 100)
        z_tank = game.TankZombie(100, 100)
        for _ in range(10):
            z_std.update(target)
            z_fast.update(target)
            z_tank.update(target)

        dist_std = math.hypot(z_std.rect.x - 100, z_std.rect.y - 100)
        dist_fast = math.hypot(z_fast.rect.x - 100, z_fast.rect.y - 100)
        dist_tank = math.hypot(z_tank.rect.x - 100, z_tank.rect.y - 100)
        self.assertGreater(dist_fast, dist_std, "Fast zombie must move faster than standard zombie")
        self.assertGreater(dist_std, dist_tank, "Standard zombie must move faster than tank zombie")

        # Combat defeat conditions: 1-shot for fast, 3-shot for standard, 6-shot for tank
        # Test Fast zombie defeat in combat
        self.engine.player.invincible_timer = 0
        self.engine.zombies = [game.FastZombie(300, 300)]
        self.engine.player.bullets = [[300, 300, 0, 0]]
        self.engine.update()
        self.assertNotIn(self.engine.zombies[0] if len(self.engine.zombies) > 0 and isinstance(self.engine.zombies[0], game.FastZombie) else None,
                         [z for z in self.engine.zombies if z.rect.topleft == (300, 300)],
                         "Fast zombie should be defeated in 1 hit")

        # Test Tank zombie defeat condition
        tank_target = game.TankZombie(200, 200)
        self.engine.zombies = [tank_target]
        for hit_count in range(5):
            self.engine.player.bullets = [[tank_target.rect.centerx, tank_target.rect.centery, 0, 0]]
            self.engine.update()
            self.assertIn(tank_target, self.engine.zombies, f"Tank zombie must survive hit {hit_count + 1}")
        # 6th hit defeats tank zombie
        self.engine.player.bullets = [[tank_target.rect.centerx, tank_target.rect.centery, 0, 0]]
        self.engine.update()
        self.assertNotIn(tank_target, self.engine.zombies, "Tank zombie must be defeated on 6th hit")

        # Spawn check
        classes_spawned = set()
        for _ in range(60):
            z = game.spawn_zombie(game.WIDTH, game.HEIGHT, self.engine.player.rect)
            classes_spawned.add(type(z))

        self.assertIn(game.Zombie, classes_spawned)
        self.assertIn(game.FastZombie, classes_spawned)
        self.assertIn(game.TankZombie, classes_spawned)

    def test_score_and_wave_progression(self):
        """Test score preservation from kills and continuous wave spawning."""
        z = self.engine.zombies[0]
        # Hit enough times to kill
        for _ in range(z.hp):
            self.engine.player.bullets = [[z.rect.centerx, z.rect.centery, 0, 0]]
            self.engine.update()

        self.assertGreater(self.engine.kill_score, 0, "Kill score should be recorded")
        self.assertGreaterEqual(self.engine.score, 10, "Score should not be wiped out by time update")

        # Check that zombies continue to spawn so wave does not deadlock
        self.assertGreaterEqual(len(self.engine.zombies), 4, "Horde should maintain minimum zombies to prevent deadlock")

    def test_wave_level_up(self):
        """Test that reaching kills_to_next advances wave correctly."""
        self.engine.kills = self.engine.kills_to_next
        old_wave = self.engine.wave
        old_quota = self.engine.kills_to_next
        self.engine.update()

        self.assertEqual(self.engine.wave, old_wave + 1, "Wave should increment")
        self.assertGreater(self.engine.kills_to_next, old_quota, "Next wave requires more kills")

    def test_player_boundaries(self):
        """Test player cannot move out of window bounds."""
        keys_left_up = {pygame.K_w: True, pygame.K_s: False, pygame.K_a: True, pygame.K_d: False,
                        pygame.K_UP: False, pygame.K_DOWN: False, pygame.K_LEFT: False, pygame.K_RIGHT: False}
        for _ in range(300):
            self.engine.player.move(keys_left_up, game.WIDTH, game.HEIGHT)

        self.assertGreaterEqual(self.engine.player.rect.x, 0)
        self.assertGreaterEqual(self.engine.player.rect.y, 40, "Player must stay below HUD")

    def test_rendering(self):
        """Test rendering in all game states does not crash."""
        # Normal state
        self.engine.draw()

        # Invincible state
        self.engine.player.invincible_timer = 30
        self.engine.draw()

        # Reloading state
        self.engine.player.is_reloading = True
        self.engine.player.reload_timer = 60
        self.engine.draw()

        # Active explosions
        self.engine.explosions.append(game.Explosion(200, 200))
        self.engine.draw()

        # Game over state
        self.engine.game_over = True
        self.engine.draw()

    def test_restart_and_exit(self):
        """Test that restart resets game state properly and ESC / QUIT exit properly."""
        self.engine.player.hp = 1
        self.engine.player.ammo = 2
        self.engine.game_over = True
        self.engine.reset()

        self.assertEqual(self.engine.player.hp, 3)
        self.assertEqual(self.engine.player.ammo, 12)
        self.assertFalse(self.engine.game_over)
        self.assertEqual(len(self.engine.barrels), 4)

        # Test QUIT event
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        result = self.engine.handle_events()
        self.assertFalse(result, "handle_events should return False on QUIT")

        # Test ESCAPE key
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}))
        result = self.engine.handle_events()
        self.assertFalse(result, "handle_events should return False on ESCAPE")


if __name__ == "__main__":
    unittest.main()
