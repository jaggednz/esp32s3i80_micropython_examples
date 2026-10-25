import gc9a01
import lcd_bus
import lvgl as lv
import task_handler
from micropython import const


WIDTH = const(240)
HEIGHT = const(240)
BACKLIGHT_PIN = const(42)
RESET_PIN = const(21)
DC_PIN = const(18)
CS_PIN = const(2)
WR_PIN = const(3)
FREQ = const(2_000_000)
FRAMEBUFFER_SIZE = const(WIDTH * 10 * 2)  # Ten RGB565 rows.


display_bus = lcd_bus.I80Bus(
    dc=DC_PIN,
    wr=WR_PIN,
    cs=CS_PIN,
    freq=FREQ,
    data0=10,
    data1=11,
    data2=12,
    data3=13,
    data4=14,
    data5=15,
    data6=16,
    data7=17,
)

framebuffer_flags = lcd_bus.MEMORY_INTERNAL | lcd_bus.MEMORY_DMA
framebuffer1 = display_bus.allocate_framebuffer(FRAMEBUFFER_SIZE, framebuffer_flags)
framebuffer2 = display_bus.allocate_framebuffer(FRAMEBUFFER_SIZE, framebuffer_flags)

lv.init()
display = gc9a01.GC9A01(
    data_bus=display_bus,
    frame_buffer1=framebuffer1,
    frame_buffer2=framebuffer2,
    display_width=WIDTH,
    display_height=HEIGHT,
    reset_pin=RESET_PIN,
    reset_state=gc9a01.STATE_LOW,
    backlight_pin=BACKLIGHT_PIN,
    backlight_on_state=gc9a01.STATE_HIGH,
    color_space=lv.COLOR_FORMAT.RGB565,
    color_byte_order=gc9a01.BYTE_ORDER_BGR,
    rgb565_byte_swap=True,
)
display.init()
display.set_backlight(100)
task_handler.TaskHandler()
