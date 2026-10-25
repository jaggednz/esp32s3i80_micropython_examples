import lcd_bus
from micropython import const

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

th = task_handler.TaskHandler()

scrn = lv.screen_active()
scrn.set_style_bg_color(lv.color_hex(0x202020), 0)

# IMPORTANT! If you do not calibrate screen, touch will be inverted on the X axis!
# Only needs to be done once, then calibration will be saved
if not indev.is_calibrated:
    indev.calibrate()
    

slider = lv.slider(scrn)
slider.set_size(180, 10)
slider.set_range(0,100)
slider.set_value(50, False)
#slider.center()

vslider = lv.slider(scrn)
vslider.set_size(20, 180)  # width, height
vslider.center()
vslider.set_range(0, 100)
vslider.set_value(50, False)

label = lv.label(scrn)
label.set_text("Animating slider")
label.align(lv.ALIGN.TOP_MID, 0, 20)

value_label = lv.label(scrn)
value_label.align(lv.ALIGN.BOTTOM_MID, 0, -30)
value_label.set_text("0")

import tca6408

intdev = i2c.I2C.Device(bus=i2c_bus, dev_id=tca6408.I2C_ADDR, reg_bits=tca6408.BITS)  # same bus as the IMU

io = tca6408.TCA6408(intdev, int_pin=45,        # GPIO wired to the expander's INT
                     inputs=0xFF,            # P0-P3 inputs, P4-P7 outputs
                     active_low=0xFF)        # buttons short to ground
io.on_change(lambda pin, pressed: print(pin, pressed))
#lv.timer_create(lambda t: io.poll(), 10, None)   # or use lvgl_keypad()
 
tca6408.lvgl_keypad(io,{4: lv.KEY.ENTER, 5: lv.KEY.NEXT, 3: lv.KEY.PREV})

