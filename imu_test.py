import time
from machine import I2C, Pin
import lvgl as lv
import qmi8658c

# Run your board-specific display/LVGL setup before this script.
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




# EDIT these values for your board.
I2C_ID = 0
IMU_ADDR = qmi8658c.I2C_ADDR  # Driver default: 0x6B


class IMUDevice:
    """Adapt machine.I2C to the interface used by QMI8658C."""

    def __init__(self, bus, address):
        self.bus = bus
        self.address = address

    def read_mem(self, register, buffer):
        self.bus.readfrom_mem_into(self.address, register, buffer)

    def write_mem(self, register, buffer):
        self.bus.writeto_mem(self.address, register, buffer)


bus = I2C(
    I2C_ID,
    sda=Pin(_SDA),
    scl=Pin(_SCL),
    freq=400_000,
)

addresses = bus.scan()
print("I2C devices:", [hex(address) for address in addresses])

if IMU_ADDR not in addresses:
    raise RuntimeError(
        "IMU not found at 0x%02X; check pins, power and address" % IMU_ADDR
    )

imu = qmi8658c.QMI8658C(IMUDevice(bus, IMU_ADDR))
time.sleep_ms(100)
imu.calibrate()

screen = lv.screen_active()

label = lv.label(screen)
label.set_text("QMI8658C\nStarting...")
label.align(lv.ALIGN.CENTER, 0, 0)


def update_imu(timer):
    try:
        roll, pitch, yaw = imu.read()
        temperature = imu.temperature
    
        
        label.set_text(
            "QMI8658C\n\n"
            "Roll:  %7.2f\n"
            "Pitch: %7.2f\n"
            "Yaw:   %7.2f\n\n"
            "Temp: %.1f C"
            % (roll, pitch, yaw, temperature)
        )
    except Exception as error:
        label.set_text("IMU read failed:\n%s" % error)
        print("IMU read failed:", error)


# Keep a reference to the timer.
imu_timer = lv.timer_create(update_imu, 100, None)
update_imu(None)


# Your existing LVGL event loop services this timer.
# Do not start a second LVGL loop here.