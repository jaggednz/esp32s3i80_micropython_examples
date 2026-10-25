import bluetooth
import cst816s
import i2c
import lvgl as lv
import math
import time
from micropython import const

from display_setup import HEIGHT, WIDTH


I2C_SCL_PIN = const(9)
I2C_SDA_PIN = const(8)
I2C_FREQ = const(100_000)
TOUCH_RESET_PIN = const(0)

BLE_MIDI_UUID = bluetooth.UUID("03B80E5A-EDE8-4B33-A751-6CE34EC4C700")
BLE_MIDI_CHARACTERISTIC_UUID = bluetooth.UUID("7772E5DB-3868-4112-A1A9-F2669D106BF3")
MIDI_SERVICE = (
    BLE_MIDI_UUID,
    ((BLE_MIDI_CHARACTERISTIC_UUID, bluetooth.FLAG_NOTIFY),),
)
ADV_INTERVAL_US = const(100_000)
MIDI_CHANNEL = const(0)
VELOCITY = const(100)
NOTE_DURATION_MS = const(350)

CENTER = const(WIDTH // 2)
PLAY_RADIUS = const(105)
CENTER_RADIUS = const(38)
SECTOR_COLORS = (0xE94F37, 0xF6AE2D, 0x4EBA6F, 0x3E8EDE, 0x9B5DE5)
INTERVALS = (4, 5, 7, 10, 14)
INTERVAL_LABELS = ("3rd", "4th", "5th", "7th", "9th")
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def advertise_midi():
    name = b"IntMIDI"
    full_name = b"Interval MIDI"
    service_uuid = bytes.fromhex("00C704EC346C51A7334B18ED5A0EB803")
    advertising_data = bytearray((2, 0x01, 0x06))
    advertising_data.extend((len(name) + 1, 0x09))
    advertising_data.extend(name)
    advertising_data.extend((len(service_uuid) + 1, 0x07))
    advertising_data.extend(service_uuid)
    response_data = bytearray((len(full_name) + 1, 0x09))
    response_data.extend(full_name)
    ble.gap_advertise(
        ADV_INTERVAL_US,
        adv_data=advertising_data,
        resp_data=response_data,
    )


def ble_irq(event, data):
    if event == 1:  # Central connected.
        connections.add(data[0])
        if status_label:
            status_label.set_text("MIDI connected")
    elif event == 2:  # Central disconnected.
        connections.discard(data[0])
        if status_label:
            status_label.set_text("Advertising MIDI")
        advertise_midi()


def midi_message(status, note, velocity):
    # BLE MIDI packets begin with two timestamp bytes. A single packet can
    # contain a complete MIDI channel-voice message.
    timestamp = time.ticks_ms() & 0x1FFF
    return bytes((
        0x80 | ((timestamp >> 7) & 0x3F),
        0x80 | (timestamp & 0x7F),
        status,
        note,
        velocity,
    ))


def send_note(note, velocity):
    packet = midi_message(0x90 | MIDI_CHANNEL, note, velocity)
    for connection in connections:
        ble.gatts_notify(connection, midi_handle, packet)


def stop_note(timer):
    send_note(active_note[0], 0)
    timer.delete()


def play_note(note):
    if active_note[0] is not None:
        send_note(active_note[0], 0)

    active_note[0] = note
    send_note(note, VELOCITY)
    lv.timer_create(stop_note, NOTE_DURATION_MS, None)


def note_name(note):
    return "{}{}".format(NOTE_NAMES[note % 12], note // 12 - 1)


def sector_at(x, y):
    dx = x - CENTER
    dy = y - CENTER
    distance_squared = dx * dx + dy * dy
    if distance_squared < CENTER_RADIUS * CENTER_RADIUS:
        return None
    if distance_squared > PLAY_RADIUS * PLAY_RADIUS:
        return None

    angle = (math.atan2(dy, dx) + math.pi / 2) % (2 * math.pi)
    return int(angle / (2 * math.pi / len(INTERVALS)))


def play_interval(event):
    point = event.get_point()
    sector = sector_at(point.x, point.y)
    if sector is None:
        return

    new_root = root_note[0] + INTERVALS[sector]
    root_note[0] = new_root
    root_label.set_text(note_name(new_root))
    interval_label.set_text("{}: {}".format(INTERVAL_LABELS[sector], note_name(new_root)))
    play_note(new_root)


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


ble = bluetooth.BLE()
ble.active(True)
ble.irq(ble_irq)
((midi_handle,),) = ble.gatts_register_services((MIDI_SERVICE,))
connections = set()
status_label = None
advertise_midi()


screen = lv.screen_active()
screen.clean()
screen.set_style_bg_color(lv.color_hex(0x101820), 0)
screen.remove_flag(lv.obj.FLAG.SCROLLABLE)

for index in range(len(INTERVALS)):
    start_angle = index * 72 - 90
    end_angle = start_angle + 72
    arc = lv.arc(screen)
    arc.set_size(PLAY_RADIUS * 2, PLAY_RADIUS * 2)
    arc.center()
    arc.set_range(0, 360)
    arc.set_rotation(start_angle)
    arc.set_value(72)
    arc.set_style_arc_width(46, lv.PART.INDICATOR)
    arc.set_style_arc_color(lv.color_hex(SECTOR_COLORS[index]), lv.PART.INDICATOR)
    arc.set_style_arc_opa(lv.OPA.TRANSP, lv.PART.MAIN)
    arc.remove_flag(lv.obj.FLAG.CLICKABLE)

    label = lv.label(screen)
    label.set_text(INTERVAL_LABELS[index])
    angle = math.radians(index * 72 - 54)
    label_x = CENTER + int(math.cos(angle) * 78)
    label_y = CENTER + int(math.sin(angle) * 78)
    label.set_pos(label_x - label.get_width() // 2, label_y - label.get_height() // 2)

touch_area = lv.obj(screen)
touch_area.set_size(PLAY_RADIUS * 2, PLAY_RADIUS * 2)
touch_area.center()
touch_area.set_style_bg_opa(lv.OPA.TRANSP, 0)
touch_area.set_style_border_opa(lv.OPA.TRANSP, 0)
touch_area.set_style_radius(lv.RADIUS_CIRCLE, 0)
touch_area.add_event_cb(play_interval, lv.EVENT.CLICKED, None)

root_note = [60]  # C4
active_note = [None]

root_label = lv.label(screen)
root_label.set_text(note_name(root_note[0]))
root_label.set_style_text_color(lv.color_white(), 0)
root_label.align(lv.ALIGN.CENTER, 0, -8)

interval_label = lv.label(screen)
interval_label.set_text("Choose an interval")
interval_label.set_style_text_color(lv.color_hex(0xD5E1E8), 0)
interval_label.align(lv.ALIGN.CENTER, 0, 15)

status_label = lv.label(screen)
status_label.set_text("Advertising MIDI")
status_label.set_style_text_color(lv.color_hex(0xD5E1E8), 0)
status_label.align(lv.ALIGN.TOP_MID, 0, 12)
