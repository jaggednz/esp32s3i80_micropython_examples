from machine import I2C, Pin
import time

ADDR = 0x6B                                   # 0x6A or 0x6B, check the scan output
i2c = I2C(0, sda=Pin(8), scl=Pin(9), freq=400_000)

CTRL1, CTRL2, CTRL3, CTRL7, CTRL8, CTRL9 = 0x02, 0x03, 0x04, 0x08, 0x09, 0x0A
CAL1_L = 0x0B                                 # CAL1_L..CAL4_H = 0x0B..0x12
STATUSINT, STATUS1, TAP_STATUS, STEP_CNT, RESET = 0x2D, 0x2F, 0x59, 0x5A, 0x60

def wr(reg, val): i2c.writeto_mem(ADDR, reg, bytes([val]))
def rd(reg, n=1): return i2c.readfrom_mem(ADDR, reg, n)

def set_cal(*vals):
    """Write CAL1_L, CAL1_H, CAL2_L, CAL2_H, CAL3_L, CAL3_H, CAL4_L, CAL4_H."""
    for i, v in enumerate(vals):
        wr(CAL1_L + i, v & 0xFF)

def ctrl9(cmd):
    wr(CTRL9, cmd)
    for _ in range(100):
        if rd(STATUSINT)[0] & 0x80:           # CmdDone
            wr(CTRL9, 0x00)                   # CTRL_CMD_ACK
            time.sleep_ms(2)
            return
        time.sleep_ms(2)
    raise OSError("CTRL9 command 0x%02X timed out" % cmd)

def init():
    print("I2C devices:", [hex(a) for a in i2c.scan()])
    assert rd(0x00)[0] == 0x05, "QMI8658 not found"
    # Docs list different values (0x79 / 0x7C), so this is a hint, not a reliable ID
    print("REVISION_ID: 0x%02X" % rd(0x01)[0])
    wr(RESET, 0xB0)
    time.sleep_ms(200)
    wr(CTRL1, 0x60)                           # address auto-increment
    wr(CTRL7, 0x00)                           # engines must be configured with sensors off
    wr(CTRL8, 0x80)                           # CTRL9 handshake via STATUSINT.bit7, engines off

# ---------------------------------------------------------------- TAP ----
def configure_tap(peak_win=20, priority=0, tap_win=50, dtap_win=250,
                  alpha=0.0625, gamma=0.25, peak_mag=0x0320, udm=0x0190):
    # Defaults are the datasheet's examples for 500 Hz ODR (windows are in samples)
    a, g = int(alpha * 128), int(gamma * 128)
    set_cal(peak_win, priority, tap_win, tap_win >> 8, dtap_win, dtap_win >> 8, 0, 0x01)
    ctrl9(0x0C)                               # CTRL_CMD_CONFIGURE_TAP, set 1
    set_cal(a, g, peak_mag, peak_mag >> 8, udm, udm >> 8, 0, 0x02)
    ctrl9(0x0C)                               # CTRL_CMD_CONFIGURE_TAP, set 2

def tap_test():
    init()
    configure_tap()
    wr(CTRL2, 0x24)                           # accel +/-8 g, 500 Hz accel-only (tap wants > 200 Hz)
    wr(CTRL8, 0x81)                           # keep STATUSINT handshake, enable tap engine
    wr(CTRL7, 0x01)                           # accel on, SyncSample OFF (tap needs non-sync mode)
    time.sleep_ms(100)
    print("Tap the board (flat on a table works well). Ctrl-C to stop.")
    while True:
        if rd(STATUS1)[0] & 0x02:             # TAP flag
            t = rd(TAP_STATUS)[0]
            num, axis, neg = t & 0x03, (t >> 4) & 0x03, t >> 7
            print("%s tap on %s axis, %s direction" % (
                {1: "SINGLE", 2: "DOUBLE"}.get(num, "?"),
                {0: "?", 1: "X", 2: "Y", 3: "Z"}[axis],
                "negative" if neg else "positive"))
            time.sleep_ms(50)
        time.sleep_ms(1)

# Pick one:
tap_test()