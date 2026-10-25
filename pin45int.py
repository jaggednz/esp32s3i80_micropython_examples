from machine import Pin, disable_irq, enable_irq
from time import sleep_ms

pin = Pin(45, Pin.IN)
changed = False

def on_change(p):
    global changed
    changed = True

pin.irq(
    trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
    handler=on_change
)

try:
    while True:
        irq_state = disable_irq()
        pending = changed
        changed = False
        enable_irq(irq_state)

        if pending:
            print("GPIO 45 changed. Current value:", pin.value())

        sleep_ms(10)
finally:
    pin.irq(handler=None)