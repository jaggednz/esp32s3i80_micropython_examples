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

# Run your board's display, touch, I2C and LVGL task-handler
# initialization before this section.

import i2c
from tilt_maze import TiltSensor, TiltMaze

imu_device = i2c.I2C.Device(
    bus=i2c_bus,
    dev_id=0x6B,  # Check your board: some use 0x6A.
    reg_bits=8,
)

# Keep a reference so the game and its LVGL timer remain alive.
game = TiltMaze(TiltSensor(imu_device))