import lcd_bus
from micropython import const
import random

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

if not indev.is_calibrated:
    display.set_backlight(100)
    indev.calibrate()
# you want to rotate the display after the calibration has been done in order
# to keep the corners oriented properly.
#display.set_rotation(lv.DISPLAY_ROTATION._90)

display.set_backlight(100)

th = task_handler.TaskHandler()

# ---------------- Game ----------------
CENTER = _WIDTH // 2
ROUND_TIME = 30

scr = lv.screen_active()
scr.set_style_bg_color(lv.color_hex(0x101820), 0)
scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

# Circular ring to show the playable area
ring = lv.obj(scr)
ring.set_size(_WIDTH, _HEIGHT)
ring.center()
ring.set_style_radius(lv.RADIUS_CIRCLE, 0)
ring.set_style_bg_opa(lv.OPA.TRANSP, 0)
ring.set_style_border_color(lv.color_hex(0x00ADB5), 0)
ring.set_style_border_width(3, 0)
ring.remove_flag(lv.obj.FLAG.CLICKABLE)

score_lbl = lv.label(scr)
score_lbl.set_style_text_color(lv.color_white(), 0)
score_lbl.align(lv.ALIGN.TOP_MID, 0, 25)

time_lbl = lv.label(scr)
time_lbl.set_style_text_color(lv.color_hex(0xFFD369), 0)
time_lbl.align(lv.ALIGN.BOTTOM_MID, 0, -25)

# The target dot
dot = lv.button(scr)
dot.set_style_radius(lv.RADIUS_CIRCLE, 0)
dot.set_style_bg_color(lv.color_hex(0xFF2E63), 0)
dot.add_flag(lv.obj.FLAG.HIDDEN)

# Start / restart button
start_btn = lv.button(scr)
start_btn.set_size(110, 50)
start_btn.center()
start_btn.set_style_radius(25, 0)
start_lbl = lv.label(start_btn)
start_lbl.set_text("START")
start_lbl.center()

state = {"score": 0, "time": ROUND_TIME, "size": 50, "running": False}


def update_labels():
    score_lbl.set_text("Score: %d" % state["score"])
    time_lbl.set_text("%ds" % state["time"])


def place_dot():
    size = state["size"]
    # Pick a random point that keeps the whole dot inside the round screen
    max_r = CENTER - size // 2 - 8
    while True:
        x = random.randint(-max_r, max_r)
        y = random.randint(-max_r, max_r)
        if x * x + y * y <= max_r * max_r:
            break
    dot.set_size(size, size)
    dot.set_pos(CENTER + x - size // 2, CENTER + y - size // 2)


def move_period():
    # Dot jumps faster as it gets smaller
    return 400 + state["size"] * 20


def on_move_timer(t):
    if state["running"]:
        place_dot()


def on_tick_timer(t):
    if not state["running"]:
        return
    state["time"] -= 1
    update_labels()
    if state["time"] <= 0:
        game_over()


def on_dot_clicked(e):
    if not state["running"]:
        return
    state["score"] += 1
    state["size"] = max(20, state["size"] - 2)
    move_timer.set_period(move_period())
    update_labels()
    place_dot()


def start_game(e=None):
    state.update(score=0, time=ROUND_TIME, size=50, running=True)
    start_btn.add_flag(lv.obj.FLAG.HIDDEN)
    dot.remove_flag(lv.obj.FLAG.HIDDEN)
    move_timer.set_period(move_period())
    place_dot()
    update_labels()


def game_over():
    state["running"] = False
    dot.add_flag(lv.obj.FLAG.HIDDEN)
    start_lbl.set_text("AGAIN\n%d pts" % state["score"])
    start_lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
    start_btn.set_size(120, 60)
    start_btn.remove_flag(lv.obj.FLAG.HIDDEN)


dot.add_event_cb(on_dot_clicked, lv.EVENT.PRESSED, None)
start_btn.add_event_cb(start_game, lv.EVENT.CLICKED, None)

move_timer = lv.timer_create(on_move_timer, move_period(), None)
tick_timer = lv.timer_create(on_tick_timer, 1000, None)

update_labels()