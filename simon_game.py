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
PAD_SIZE = const(68)
PAD_GAP = const(8)
PAD_TOP = const(58)
STEP_DELAY_MS = const(1_200)
FLASH_DURATION_MS = const(900)
NEXT_ROUND_DELAY_MS = const(700)
RESTART_DELAY_MS = const(1_500)

PAD_COLORS = (0xD94545, 0x3F9B59, 0x3D70CC, 0xD6A23A)
LIT_COLORS = (0xFF7878, 0x71D88C, 0x73A5FF, 0xFFD66E)


def set_pads_enabled(enabled):
    for pad in pads:
        if enabled:
            pad.remove_state(lv.STATE.DISABLED)
        else:
            pad.add_state(lv.STATE.DISABLED)


def set_pad_color(index, color):
    pads[index].set_style_bg_color(lv.color_hex(color), 0)


def reset_pad(index):
    set_pad_color(index, PAD_COLORS[index])


def reset_tapped_pad(timer, index):
    reset_pad(index)
    timer.delete()


def flash_tapped_pad(index):
    set_pad_color(index, LIT_COLORS[index])
    lv.timer_create(
        lambda timer, index=index: reset_tapped_pad(timer, index),
        FLASH_DURATION_MS,
        None,
    )


def play_step(timer):
    if playback_lit[0]:
        reset_pad(sequence[playback_step[0]])
        playback_step[0] += 1
        playback_lit[0] = False

        if playback_step[0] == len(sequence):
            timer.delete()
            set_pads_enabled(True)
            message.set_text("Your turn")
        else:
            timer.set_period(STEP_DELAY_MS)
        return

    set_pad_color(sequence[playback_step[0]], LIT_COLORS[sequence[playback_step[0]]])
    playback_lit[0] = True
    timer.set_period(FLASH_DURATION_MS)


def play_sequence(timer=None):
    set_pads_enabled(False)
    message.set_text("Watch closely")
    playback_step[0] = 0
    playback_lit[0] = False
    lv.timer_create(play_step, STEP_DELAY_MS, None)


def start_round(timer=None):
    if timer:
        timer.delete()

    sequence.append(urandom.getrandbits(16) % len(pads))
    score_label.set_text("Round: {}".format(len(sequence)))
    player_step[0] = 0
    play_sequence()


def restart_game(timer):
    timer.delete()
    sequence.clear()
    start_round()


def press_pad(index):
    flash_tapped_pad(index)

    if index != sequence[player_step[0]]:
        set_pads_enabled(False)
        message.set_text("Wrong! Restarting...")
        lv.timer_create(restart_game, RESTART_DELAY_MS, None)
        return

    player_step[0] += 1
    if player_step[0] == len(sequence):
        set_pads_enabled(False)
        message.set_text("Correct!")
        lv.timer_create(start_round, NEXT_ROUND_DELAY_MS, None)


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
title.set_text("SIMON")
title.align(lv.ALIGN.TOP_MID, 0, 10)

score_label = lv.label(screen)
score_label.set_text("Round: 0")
score_label.align(lv.ALIGN.TOP_MID, 0, 30)

message = lv.label(screen)
message.set_text("Get ready")
message.align(lv.ALIGN.BOTTOM_MID, 0, -18)

pads = []
for index, (x, y) in enumerate(
    (
        (WIDTH // 2 - PAD_GAP - PAD_SIZE, PAD_TOP),
        (WIDTH // 2 + PAD_GAP, PAD_TOP),
        (WIDTH // 2 - PAD_GAP - PAD_SIZE, PAD_TOP + PAD_SIZE + PAD_GAP),
        (WIDTH // 2 + PAD_GAP, PAD_TOP + PAD_SIZE + PAD_GAP),
    )
):
    pad = lv.button(screen)
    pad.set_size(PAD_SIZE, PAD_SIZE)
    pad.set_pos(x, y)
    pad.set_style_bg_color(lv.color_hex(PAD_COLORS[index]), 0)
    pad.add_event_cb(
        lambda event, index=index: press_pad(index),
        lv.EVENT.CLICKED,
        None,
    )
    pads.append(pad)

sequence = []
player_step = [0]
playback_step = [0]
playback_lit = [False]
start_round()
