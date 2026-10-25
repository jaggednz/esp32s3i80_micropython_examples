"""Tilt-controlled rolling ball for lvgl_micropython + QMI8658C (6DOF fusion).

Tilt the board and the ball rolls downhill, bounces off the screen edges and
slowly comes to rest. Only roll and pitch are used, so the missing
magnetometer (and the resulting yaw drift) doesn't matter.

Run this after your normal display / touch initialisation (see main()).
"""
import math
import time

# ----------------------------------------------------------------- tuning --
BALL_RADIUS = 14        # pixels
GRAVITY_PX = 900.0      # px/s^2 of acceleration when the board is tilted 90 degrees
DAMPING = 0.6           # rolling friction, 1/s (higher = stops sooner)
BOUNCE = 0.55           # 0 = dead stop at walls, 1 = perfectly elastic
REST_SPEED = 8.0        # px/s: slower than this after a wall hit, the ball sticks
MAX_DT = 0.1            # s: cap on a single physics step (e.g. after a UI stall)

# Chip-to-screen mapping. See the notes after the code for how to set these.
FLIP = True             # QMI8658C(flip=...): chip Z points down when the board lies flat
SWAP_XY = False
INVERT_X = False
INVERT_Y = False

UI_PERIOD_MS = 16       # LVGL timer period (~60 fps target)
SHOW_DEBUG = True       # roll/pitch text in the corner


# ---------------------------------------------------------------- physics --
def tilt_to_accel(roll_deg, pitch_deg):
    """In-plane gravity (px/s^2) from roll/pitch, mapped onto screen x/y."""
    r = math.radians(roll_deg)
    p = math.radians(pitch_deg)

    # gravity direction in the device frame, projected onto the board's plane
    gx = math.sin(p)
    gy = -math.cos(p) * math.sin(r)

    if SWAP_XY:
        gx, gy = gy, gx
    if INVERT_X:
        gx = -gx
    if INVERT_Y:
        gy = -gy

    return gx * GRAVITY_PX, gy * GRAVITY_PX


class BallPhysics:
    def __init__(self, width, height, radius):
        self.xmin = radius
        self.xmax = width - radius
        self.ymin = radius
        self.ymax = height - radius
        self.x = width / 2
        self.y = height / 2
        self.vx = 0.0
        self.vy = 0.0

    def step(self, ax, ay, dt):
        if dt > MAX_DT:
            dt = MAX_DT

        self.vx += ax * dt
        self.vy += ay * dt

        drag = 1.0 - DAMPING * dt
        if drag < 0.0:
            drag = 0.0
        self.vx *= drag
        self.vy *= drag

        self.x += self.vx * dt
        self.y += self.vy * dt

        if self.x < self.xmin:
            self.x = self.xmin
            self.vx = 0.0 if -self.vx < REST_SPEED else -self.vx * BOUNCE
        elif self.x > self.xmax:
            self.x = self.xmax
            self.vx = 0.0 if self.vx < REST_SPEED else -self.vx * BOUNCE

        if self.y < self.ymin:
            self.y = self.ymin
            self.vy = 0.0 if -self.vy < REST_SPEED else -self.vy * BOUNCE
        elif self.y > self.ymax:
            self.y = self.ymax
            self.vy = 0.0 if self.vy < REST_SPEED else -self.vy * BOUNCE


# ------------------------------------------------------------------- main --
_keep = []  # keep references so the garbage collector can't free the timer/objects


def main():
    import lcd_bus
    from micropython import const
    import qmi8658c  # NOQA

    # display settings
    _WIDTH = const(240)
    _HEIGHT = const(240)
    _BL = const(42)
    _RST = const(21)
    _DC = const(18)
    _CS = const(2)
    _WR = const(3)
    _FREQ = const(2_000_000)
    _DATA0 = const(10)
    _DATA1 = const(11)
    _DATA2 = const(12)
    _DATA3 = const(13)
    _DATA4 = const(14)
    _DATA5 = const(15)
    _DATA6 = const(16)
    _DATA7 = const(17)
    _BUFFER_SIZE = const(240*10*2) # 10 Rows of RGB565 is 2 Bytes per pixel

    # I2C
    _SCL = const(9)
    _SDA = const(8)
    _TP_FREQ = const(100000)

    display_bus = lcd_bus.I80Bus(
        dc=_DC,
        wr=_WR,
        cs=_CS,
        freq=_FREQ,
        data0=_DATA0,
        data1=_DATA1,
        data2=_DATA2,
        data3=_DATA3,
        data4=_DATA4,
        data5=_DATA5,
        data6=_DATA6,
        data7=_DATA7
    )

    fb1 = display_bus.allocate_framebuffer(_BUFFER_SIZE, lcd_bus.MEMORY_INTERNAL | lcd_bus.MEMORY_DMA)
    fb2 = display_bus.allocate_framebuffer(_BUFFER_SIZE, lcd_bus.MEMORY_INTERNAL | lcd_bus.MEMORY_DMA)

    import gc9a01  # NOQA
    import lvgl as lv  # NOQA

    lv.init()

    display = gc9a01.GC9A01(
        data_bus=display_bus,
        frame_buffer1=fb1,
        frame_buffer2=fb2,
        display_width=_WIDTH,
        display_height=_HEIGHT,
        reset_pin=_RST,                 # GPIO 21, matching Arduino
        reset_state=gc9a01.STATE_LOW,
        backlight_pin=_BL,
        backlight_on_state=gc9a01.STATE_HIGH,
        color_space=lv.COLOR_FORMAT.RGB565,
        color_byte_order=gc9a01.BYTE_ORDER_BGR,
        rgb565_byte_swap=True,
    )

    import i2c  # NOQA
    import task_handler  # NOQA
    import cst816s  # NOQA
    _TOUCH_RST_PIN = const(0x00)

    display.init()

    i2c_bus = i2c.I2C.Bus(host=0, scl=_SCL, sda=_SDA, freq=_TP_FREQ, use_locks=False)
    touch_dev = i2c.I2C.Device(bus=i2c_bus, dev_id=cst816s.I2C_ADDR, reg_bits=cst816s.BITS)

    indev = cst816s.CST816S(touch_dev, reset_pin=_TOUCH_RST_PIN)

    #display.invert_colors()

    #if not indev.is_calibrated:
    #    display.set_backlight(100)
    #    indev.calibrate()
    # you want to rotate the display after the calibration has been done in order
    # to keep the corners oriented properly.
    #display.set_rotation(lv.DISPLAY_ROTATION._90)

    display.set_backlight(100)

    # ---- your existing display (+ touch) initialisation goes here, unchanged ----
    # e.g. create the bus, the display driver, call display.init(), etc.

    # TaskHandler runs lv.timer_handler() for you; skip if your setup already has one.
    th = task_handler.TaskHandler()  # NOQA
    _keep.append(th)

    #i2c_bus = I2C.Bus(host=0, sda=8, scl=9, freq=400000)
    dev = i2c.I2C.Device(bus=i2c_bus, dev_id=qmi8658c.I2C_ADDR, reg_bits=qmi8658c.BITS)
    imu = qmi8658c.QMI8658C(dev, flip=FLIP)

    print("Hold the board still, calibrating gyro...")
    imu.calibrate_gyro()
    print("Done. Tilt the board.")

    scr = lv.screen_active()
    width = scr.get_width()
    height = scr.get_height()

    scr.set_style_bg_color(lv.color_hex(0x10151C), 0)
    scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

    ball = lv.obj(scr)
    ball.set_size(BALL_RADIUS * 2, BALL_RADIUS * 2)
    ball.set_style_radius(lv.RADIUS_CIRCLE, 0)
    ball.set_style_bg_color(lv.color_hex(0xFF6A00), 0)
    ball.set_style_bg_opa(255, 0)
    ball.set_style_border_width(0, 0)
    ball.set_style_pad_all(0, 0)
    ball.set_style_shadow_width(14, 0)
    ball.set_style_shadow_color(lv.color_hex(0x000000), 0)
    ball.set_style_shadow_opa(160, 0)
    ball.set_style_shadow_offset_x(3, 0)
    ball.set_style_shadow_offset_y(4, 0)
    ball.remove_flag(lv.obj.FLAG.SCROLLABLE)

    label = None
    if SHOW_DEBUG:
        label = lv.label(scr)
        label.set_style_text_color(lv.color_hex(0x8899AA), 0)
        label.align(lv.ALIGN.TOP_LEFT, 6, 4)
        label.set_text("")

    phys = BallPhysics(width, height, BALL_RADIUS)
    ball.set_pos(int(phys.x - BALL_RADIUS), int(phys.y - BALL_RADIUS))

    state = [time.ticks_us(), 0]  # last timestamp, frame counter

    def step(timer):
        now = time.ticks_us()
        dt = time.ticks_diff(now, state[0]) / 1000000.0
        state[0] = now

        roll, pitch, _yaw = imu.read()
        ax, ay = tilt_to_accel(roll, pitch)
        phys.step(ax, ay, dt)
        ball.set_pos(int(phys.x - BALL_RADIUS), int(phys.y - BALL_RADIUS))

        if label is not None:
            state[1] += 1
            if state[1] % 10 == 0:  # updating text every frame is wasteful
                label.set_text("roll %6.1f  pitch %6.1f" % (roll, pitch))

    timer = lv.timer_create(step, UI_PERIOD_MS, None)
    _keep.extend((imu, ball, label, timer, step))


if __name__ == "__main__":
    main()