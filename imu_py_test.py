from machine import I2C, Pin
import struct, math, time

ADDR = 0x6B          # 0x6A or 0x6B depending on SA0, see the scan below
G = 9.80665

# Registers
WHO_AM_I, CTRL1, CTRL2, CTRL3, CTRL5, CTRL6, CTRL7 = 0x00, 0x02, 0x03, 0x04, 0x06, 0x07, 0x08
STATUS0, DQW_L, RESET = 0x2E, 0x49, 0x60

# AE settings
SODR = 0b101                      # AE output rate: 0=1,1=2,2=4,3=8,4=16,5=32,6=64 Hz
AE_HZ = (1, 2, 4, 8, 16, 32, 64)[SODR]
DT = 1.0 / AE_HZ
KP = 0.02                         # tilt-correction gain (per AE sample)

i2c = I2C(0, sda=Pin(8), scl=Pin(9), freq=400_000)
print("I2C devices:", [hex(a) for a in i2c.scan()])

def wr(reg, val): i2c.writeto_mem(ADDR, reg, bytes([val]))
def rd(reg, n=1): return i2c.readfrom_mem(ADDR, reg, n)

# --- init ---
assert rd(WHO_AM_I)[0] == 0x05, "QMI8658 not found"
wr(RESET, 0xB0)                   # soft reset
time.sleep_ms(200)                # datasheet: ~150 ms turn-on
wr(CTRL1, 0x60)                   # address auto-increment on (0x60 is what QST/Waveshare drivers use)
wr(CTRL2, (0b010 << 4) | 0x03)    # accel +/-8 g, 940 Hz (6DOF)
wr(CTRL3, (0b101 << 4) | 0x03)    # gyro +/-512 dps, 940 Hz
wr(CTRL5, 0x00)                   # LPFs off
wr(CTRL6, SODR)                   # AE ODR, sMoD=0 (streaming, not motion-on-demand)
wr(CTRL7, 0x0B)                   # sEN | gEN | aEN
time.sleep_ms(300)                # gyro turn-on + filter settling

# --- quaternion helpers ---
def qmul(a, b):
    aw, ax, ay, az = a; bw, bx, by, bz = b
    return (aw*bw - ax*bx - ay*by - az*bz,
            aw*bx + ax*bw + ay*bz - az*by,
            aw*by - ax*bz + ay*bw + az*bx,
            aw*bz + ax*by - ay*bx + az*bw)

def qnorm(q):
    n = math.sqrt(sum(c*c for c in q))
    return tuple(c/n for c in q)

def from_tilt(ax, ay, az):        # roll/pitch from gravity, yaw = 0
    r = math.atan2(ay, az)
    p = math.atan2(-ax, math.sqrt(ay*ay + az*az))
    cr, sr, cp, sp = math.cos(r/2), math.sin(r/2), math.cos(p/2), math.sin(p/2)
    return (cr*cp, sr*cp, cr*sp, -sr*sp)

def euler(q):
    w, x, y, z = q
    roll  = math.atan2(2*(w*x + y*z), 1 - 2*(x*x + y*y))
    pitch = math.asin(max(-1, min(1, 2*(w*y - z*x))))
    yaw   = math.atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z))
    return [math.degrees(a) for a in (roll, pitch, yaw)]

def read_ae():
    # dQW,dQX,dQY,dQZ,dVX,dVY,dVZ (int16 LE), AE_REG1, AE_REG2
    v = struct.unpack('<7hBB', rd(DQW_L, 16))
    dq = qnorm(tuple(c / 16384 for c in v[0:4]))     # 16384 LSB per unit
    dv = tuple(c / 1024 for c in v[4:7])             # 1024 LSB per m/s
    return dq, dv, v[7], v[8]

# --- wait for first AE sample, seed orientation from gravity ---
while not (rd(STATUS0)[0] & 0x08):    # STATUS0.sDA
    time.sleep_ms(2)
_, dv, _, _ = read_ae()
q = qnorm(from_tilt(*dv))

# --- main loop ---
while True:
    if not (rd(STATUS0)[0] & 0x08):
        time.sleep_ms(2)
        continue

    dq, dv, ae1, ae2 = read_ae()
    if ae1 & 0x3F or ae2 & 0x07:
        print("clip/overflow flags:", hex(ae1), hex(ae2))

    # 1) integrate the on-chip orientation increment
    q = qnorm(qmul(q, dq))

    # 2) roll/pitch correction from dV (gravity) when not accelerating much
    mag = math.sqrt(sum(c*c for c in dv))
    if 0.9 < mag / (G * DT) < 1.1:
        ax, ay, az = (c / mag for c in dv)
        w, x, y, z = q
        vx = 2*(x*z - w*y)                    # estimated "up" in body frame
        vy = 2*(w*x + y*z)
        vz = w*w - x*x - y*y + z*z
        ex = ay*vz - az*vy                    # cross(measured, estimated)
        ey = az*vx - ax*vz
        ez = ax*vy - ay*vx
        q = qnorm(qmul(q, (1.0, 0.5*KP*ex, 0.5*KP*ey, 0.5*KP*ez)))

    r, p, yw = euler(q)
    print("roll %7.2f  pitch %7.2f  yaw %7.2f" % (r, p, yw))