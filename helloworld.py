import lvgl as lv
import i2c
import cst816s
import tca6408
from micropython import const
from display_setup import display


# Touch controller I2C pins.
I2C_SCL_PIN = const(9)
I2C_SDA_PIN = const(8)
I2C_FREQ = const(100_000)
TOUCH_RESET_PIN = const(0)

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

# Calibration is stored after the first successful run.
if not touch.is_calibrated:
    touch.calibrate()


screen = lv.screen_active()
screen.set_style_bg_color(lv.color_hex(0x202020), 0)

slider = lv.slider(screen)
slider.set_size(180, 10)
slider.set_range(0, 100)
slider.set_value(50, False)

vertical_slider = lv.slider(screen)
vertical_slider.set_size(20, 180)
vertical_slider.center()
vertical_slider.set_range(0, 100)
vertical_slider.set_value(50, False)

label = lv.label(screen)
label.set_text("Animating slider")
label.align(lv.ALIGN.TOP_MID, 0, 20)

value_label = lv.label(screen)
value_label.set_text("0")
value_label.align(lv.ALIGN.BOTTOM_MID, 0, -30)


expander_device = i2c.I2C.Device(
    bus=i2c_bus,
    dev_id=tca6408.I2C_ADDR,
    reg_bits=tca6408.BITS,
)
buttons = tca6408.TCA6408(
    expander_device,
    int_pin=45,
    inputs=0xFF,
    active_low=0xFF,
)
buttons.on_change(lambda pin, pressed: print(pin, pressed))
tca6408.lvgl_keypad(buttons, {4: lv.KEY.ENTER, 5: lv.KEY.NEXT, 3: lv.KEY.PREV})
