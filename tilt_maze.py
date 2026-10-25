import lvgl as lv
import random
import time


class TiltSensor:
    """QMI8658C accelerometer using repository i2c.I2C.Device API."""

    def __init__(self, device):
        self.device = device
        self.buf = bytearray(6)
        self.one = bytearray(1)

        device.read_mem(0x00, self.one)
        if self.one[0] != 0x05:
            raise RuntimeError("QMI8658C not detected")

        self.write(0x08, 0x00)  # Disable sensors while configuring
        self.write(0x02, 0x40)  # Auto-increment, little-endian
        self.write(0x03, 0x06)  # Accelerometer: +/-2g, 125 Hz
        self.write(0x06, 0x00)  # No motion-on-demand
        self.write(0x08, 0x01)  # Enable accelerometer only
        time.sleep_ms(50)

    def write(self, register, value):
        self.one[0] = value
        self.device.write_mem(register, self.one)

    def read(self):
        self.device.read_mem(0x35, self.buf)
        values = []
        for i in (0, 2, 4):
            value = self.buf[i] | (self.buf[i + 1] << 8)
            if value & 0x8000:
                value -= 65536
            values.append(value / 16384.0)
        return values


class TiltMaze:
    # 7x7 logical rooms, with walls between them:
    # 15x15 tiles at 10 pixels per tile.
    N = 15
    TILE = 10

    # Adjust these to match the sensor's mounting/display rotation.
    SWAP_XY = False
    X_SIGN = 1
    Y_SIGN = 1

    DEAD_ZONE = 0.12
    FILTER = 0.25

    def __init__(self, sensor):
        self.sensor = sensor
        self.grid = []
        self.won = False
        self.failed = False
        self.cal_count = 0
        self.last_move = time.ticks_ms()
        self.last_direction = None

        self.screen = lv.obj()
        self.screen.remove_style_all()
        self.screen.set_size(240, 240)
        self.screen.set_style_bg_color(lv.color_hex(0x101820), 0)
        self.screen.set_style_bg_opa(lv.OPA.COVER, 0)
        self.screen.remove_flag(lv.obj.FLAG.SCROLLABLE)

        self.status = lv.label(self.screen)
        self.status.set_style_text_color(lv.color_white(), 0)
        self.status.set_text("Hold level")
        self.status.align(lv.ALIGN.TOP_MID, 0, 18)

        self.board = lv.obj(self.screen)
        self.board.remove_style_all()
        self.board.set_pos(45, 45)
        self.board.set_size(150, 150)
        self.board.set_style_bg_color(lv.color_hex(0x192B36), 0)
        self.board.set_style_bg_opa(lv.OPA.COVER, 0)
        self.board.remove_flag(lv.obj.FLAG.SCROLLABLE)

        self.new_button = lv.button(self.screen)
        self.new_button.set_size(80, 26)
        self.new_button.align(lv.ALIGN.BOTTOM_MID, 0, -8)
        self.new_button.set_style_radius(13, 0)
        label = lv.label(self.new_button)
        label.set_text("NEW")
        label.center()
        self.new_button.add_event_cb(
            self.new_game, lv.EVENT.CLICKED, None
        )

        lv.screen_load(self.screen)
        self.new_game()
        self.timer = lv.timer_create(self.update, 40, None)

    def axes(self):
        x, y, _ = self.sensor.read()
        if self.SWAP_XY:
            x, y = y, x
        return x * self.X_SIGN, y * self.Y_SIGN

    def rectangle(self, x, y, width, height, color, rounded=False):
        obj = lv.obj(self.board)
        obj.remove_style_all()
        obj.set_pos(x, y)
        obj.set_size(width, height)
        obj.set_style_bg_color(lv.color_hex(color), 0)
        obj.set_style_bg_opa(lv.OPA.COVER, 0)
        if rounded:
            obj.set_style_radius(lv.RADIUS_CIRCLE, 0)
        obj.remove_flag(lv.obj.FLAG.CLICKABLE)
        obj.remove_flag(lv.obj.FLAG.SCROLLABLE)
        return obj

    def make_maze(self):
        # 1 = wall, 0 = passage.
        n = self.N
        grid = [bytearray([1] * n) for _ in range(n)]
        grid[1][1] = 0
        stack = [(1, 1)]

        # Randomized depth-first search connects every room.
        while stack:
            x, y = stack[-1]
            choices = []
            for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2)):
                nx, ny = x + dx, y + dy
                if 1 <= nx < n - 1 and 1 <= ny < n - 1:
                    if grid[ny][nx]:
                        choices.append((nx, ny))

            if not choices:
                stack.pop()
                continue

            nx, ny = random.choice(choices)
            grid[(y + ny) // 2][(x + nx) // 2] = 0
            grid[ny][nx] = 0
            stack.append((nx, ny))

        return grid

    def draw_maze(self):
        self.board.clean()
        tile = self.TILE

        # Merge horizontal wall runs to reduce LVGL object count.
        for y, row in enumerate(self.grid):
            x = 0
            while x < self.N:
                if not row[x]:
                    x += 1
                    continue
                start = x
                while x < self.N and row[x]:
                    x += 1
                self.rectangle(
                    start * tile, y * tile,
                    (x - start) * tile, tile, 0x718898
                )

        self.rectangle(
            self.goal_x * tile + 1, self.goal_y * tile + 1,
            8, 8, 0x36DC83, True
        )
        self.ball = self.rectangle(0, 0, 6, 6, 0xFFD166, True)
        self.position_ball()

    def position_ball(self):
        self.ball.set_pos(
            self.player_x * self.TILE + 2,
            self.player_y * self.TILE + 2
        )

    def new_game(self, event=None):
        self.grid = self.make_maze()
        self.player_x = self.player_y = 1
        self.goal_x = self.goal_y = self.N - 2
        self.won = False
        self.failed = False
        self.steps = 0

        self.cal_count = 0
        self.sum_x = self.sum_y = 0.0
        self.zero_x = self.zero_y = 0.0
        self.filtered_x = self.filtered_y = 0.0
        self.last_direction = None
        self.last_move = time.ticks_ms()

        self.status.set_text("Hold level")
        self.status.align(lv.ALIGN.TOP_MID, 0, 18)
        self.draw_maze()

    def update(self, timer):
        if self.failed or self.won:
            return

        try:
            x, y = self.axes()
        except OSError:
            # Stop polling until NEW is pressed.
            self.failed = True
            self.status.set_text("IMU error")
            self.status.align(lv.ALIGN.TOP_MID, 0, 18)
            return

        # Average 25 samples without blocking the UI.
        if self.cal_count < 25:
            self.sum_x += x
            self.sum_y += y
            self.cal_count += 1
            if self.cal_count == 25:
                self.zero_x = self.sum_x / 25
                self.zero_y = self.sum_y / 25
                self.status.set_text("Tilt to move")
                self.status.align(lv.ALIGN.TOP_MID, 0, 18)
            return

        self.filtered_x += self.FILTER * (
            x - self.zero_x - self.filtered_x
        )
        self.filtered_y += self.FILTER * (
            y - self.zero_y - self.filtered_y
        )
        x, y = self.filtered_x, self.filtered_y

        strength = max(abs(x), abs(y))
        if strength < self.DEAD_ZONE:
            self.last_direction = None
            return

        # Move along the strongest tilt axis, never diagonally.
        if abs(x) > abs(y):
            direction = (1 if x > 0 else -1, 0)
        else:
            direction = (0, 1 if y > 0 else -1)

        now = time.ticks_ms()
        interval = max(100, int(320 - strength * 350))

        if direction == self.last_direction:
            if time.ticks_diff(now, self.last_move) < interval:
                return

        self.last_direction = direction
        self.last_move = now

        dx, dy = direction
        nx, ny = self.player_x + dx, self.player_y + dy
        if not (0 <= nx < self.N and 0 <= ny < self.N):
            return
        if self.grid[ny][nx]:
            return

        self.player_x, self.player_y = nx, ny
        self.steps += 1
        self.position_ball()

        if (nx, ny) == (self.goal_x, self.goal_y):
            self.won = True
            self.status.set_text("Won! %d steps" % self.steps)
            self.status.align(lv.ALIGN.TOP_MID, 0, 18)