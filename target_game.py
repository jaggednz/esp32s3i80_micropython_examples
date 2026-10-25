import cst816s
import i2c
import lvgl as lv
import urandom
from micropython import const

from display_setup import HEIGHT, WIDTH


I2C_SCL_PIN = const(9)
I2C_SDA_PIN = const(8)
I2C_FREQ = const(100_000)
TOUCH_RESET_PIN = const(0)
TARGET_SIZE = const(42)
HEADER_HEIGHT = const(70)
MOVE_INTERVAL_MS = const(1_000)
SUCCESS_DELAY_MS = const(300)


def random_position():
    x = urandom.getrandbits(16) % (WIDTH - TARGET_SIZE)
    y = HEADER_HEIGHT + urandom.getrandbits(16) % (HEIGHT - HEADER_HEIGHT - TARGET_SIZE)
    return x, y


def move_target(timer=None):
    target.set_style_bg_color(lv.color_hex(0xFF6B35), 0)
    target_label.set_text("TAP")
    target.remove_state(lv.STATE.DISABLED)
    target.set_pos(*random_position())


def show_next_target(timer):
    timer.delete()
    move_target()


def hit_target(event):
    score[0] += 1
    score_label.set_text("Score: {}".format(score[0]))
    target.add_state(lv.STATE.DISABLED)
    target.set_style_bg_color(lv.color_hex(0x3DDC84), 0)
    target_label.set_text("HIT!")
    lv.timer_create(show_next_target, SUCCESS_DELAY_MS, None)


# Creating the touch controller also registers it with LVGL.
i2c_bus = i2c.I2C.Bus(
    host=0,
    scl=I2C_SCL_PIN,
    sda=I2C_SDA_PIN,
    freq=I2C_FREQ,
    use_locks=False,
)
touch_device = i2c.I2C.Device(
    bus=i2c_bus,
    dev_id=cst816s.I2C_ADDR,
    reg_bits=cst816s.BITS,
)
touch = cst816s.CST816S(touch_device, reset_pin=TOUCH_RESET_PIN)

if not touch.is_calibrated:
    touch.calibrate()


screen = lv.screen_active()
screen.clean()
screen.set_style_bg_color(lv.color_hex(0x102030), 0)

title = lv.label(screen)
title.set_text("Tap the target")
title.align(lv.ALIGN.TOP_MID, 0, 30)

score = [0]
score_label = lv.label(screen)
score_label.set_text("Score: 0")
score_label.align(lv.ALIGN.TOP_MID, 0, 8)

target = lv.button(screen)
target.set_size(TARGET_SIZE, TARGET_SIZE)
target.set_style_bg_color(lv.color_hex(0xFF6B35), 0)
target.add_event_cb(hit_target, lv.EVENT.CLICKED, None)

target_label = lv.label(target)
target_label.set_text("TAP")
target_label.center()

move_target()
lv.timer_create(move_target, MOVE_INTERVAL_MS, None)
