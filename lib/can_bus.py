import time
from rp2350_can import RP2350_CAN

# MCP2515 / XL2515 register addresses
_CANINTF   = 0x2C
_CANINTE   = 0x2B
_RXM0SIDH  = 0x20
_RXM0SIDL  = 0x21
_RXM1SIDH  = 0x24
_RXM1SIDL  = 0x25
_RXB0CTRL  = 0x60
_RXB0SIDH  = 0x61
_RXB0SIDL  = 0x62
_RXB0DLC   = 0x65
_RXB0D0    = 0x66
_RXB1CTRL  = 0x70
_RXB1SIDH  = 0x71
_RXB1SIDL  = 0x72
_RXB1DLC   = 0x75
_RXB1D0    = 0x76

# OBD-II Mode 01 PIDs
PID_ECT = 0x05
PID_RPM = 0x0C
PID_IAT = 0x0F
PID_AFR = 0x44

_OBD_REQUEST_ID  = 0x7DF
_OBD_RESPONSE_ID = 0x7E8

# Default broadcast frame ID guess for ND Miata RPM — must be confirmed by sniffing.
# Until verified, the broadcast path is disabled and RPM is acquired via PID 0x0C.
RPM_BROADCAST_ID = None

_OBD_POLL_INTERVAL_MS = 100
_RPM_FALLBACK_TIMEOUT_MS = 1000


def _c_to_f(c):
    return c * 9 / 5 + 32


class CanBus:
    """Thin wrapper around the Waveshare RP2350_CAN driver.

    - Reconfigures the receive filter to accept every standard ID.
    - Drains both RX buffers per poll (the vendor driver only reads RXB0).
    - Round-robin polls OBD-II PIDs on 0x7DF and decodes 0x7E8 responses.
    - Caches latest values in `self.latest`.
    """

    def __init__(self, rate_kbps="500KBPS"):
        self._can = RP2350_CAN(rate_kbps=rate_kbps)
        self._open_filter()

        self.latest = {'RPM': None, 'ECT': None, 'IAT': None, 'AFR': None}

        self._poll_pids = [PID_ECT, PID_IAT, PID_AFR]
        self._poll_idx = 0
        self._last_request_ms = time.ticks_ms()
        self._last_rpm_ms = self._last_request_ms

    def _open_filter(self):
        c = self._can
        # Set RXB0/RXB1 to "receive any, no filters" (RXM bits = 11)
        c.write_byte(_RXB0CTRL, 0x60)
        c.write_byte(_RXB1CTRL, 0x60)
        # Zero both mask registers so all SID bits are "don't care"
        c.write_byte(_RXM0SIDH, 0x00)
        c.write_byte(_RXM0SIDL, 0x00)
        c.write_byte(_RXM1SIDH, 0x00)
        c.write_byte(_RXM1SIDL, 0x00)
        # Clear interrupt flags, enable RX0 and RX1 full interrupts
        c.write_byte(_CANINTF, 0x00)
        c.write_byte(_CANINTE, 0x03)

    def poll(self):
        self._drain_rx()

        now = time.ticks_ms()
        if time.ticks_diff(now, self._last_request_ms) >= _OBD_POLL_INTERVAL_MS:
            pid = self._poll_pids[self._poll_idx]
            self._can.send(_OBD_REQUEST_ID, [0x02, 0x01, pid, 0, 0, 0, 0, 0])
            self._poll_idx = (self._poll_idx + 1) % len(self._poll_pids)
            self._last_request_ms = now

        # If broadcast RPM is silent (or unconfigured) for too long, fall back to polling 0x0C.
        if (self.latest['RPM'] is None and
                PID_RPM not in self._poll_pids and
                time.ticks_diff(now, self._last_rpm_ms) > _RPM_FALLBACK_TIMEOUT_MS):
            self._poll_pids.append(PID_RPM)

    def _drain_rx(self):
        c = self._can
        # Reset the IRQ hint; the loop below is the real authority.
        c.recv_flag = False

        while True:
            flags = c.read_byte(_CANINTF) & 0x03
            if flags == 0:
                return

            if flags & 0x01:
                can_id, data = self._read_buffer(_RXB0SIDH, _RXB0SIDL, _RXB0DLC, _RXB0D0)
                # Atomically clear RX0IF only — a frame may have arrived in RXB1
                # since we read CANINTF, and a read-modify-write would lose it.
                self._bit_modify(_CANINTF, 0x01, 0x00)
                self._dispatch(can_id, data)

            if flags & 0x02:
                can_id, data = self._read_buffer(_RXB1SIDH, _RXB1SIDL, _RXB1DLC, _RXB1D0)
                self._bit_modify(_CANINTF, 0x02, 0x00)
                self._dispatch(can_id, data)

    def _bit_modify(self, reg, mask, value):
        """MCP2515 BIT MODIFY instruction (0x05). Only valid on a subset of
        registers, but CANINTF is one of them — preferred over write_byte
        for clearing a single interrupt flag without racing the hardware."""
        c = self._can
        c.cs(0)
        c.spi.write(bytearray([0x05, reg, mask, value]))
        c.cs(1)

    def _read_buffer(self, sidh_reg, sidl_reg, dlc_reg, d0_reg):
        c = self._can
        sid_h = c.read_byte(sidh_reg)
        sid_l = c.read_byte(sidl_reg)
        can_id = (sid_h << 3) | (sid_l >> 5)
        dlc = c.read_byte(dlc_reg) & 0x0F
        buf = bytearray(dlc)
        for i in range(dlc):
            buf[i] = c.read_byte(d0_reg + i)
        return can_id, buf

    def _dispatch(self, can_id, data):
        if can_id == _OBD_RESPONSE_ID and len(data) >= 3 and data[1] == 0x41:
            self._decode_obd(data[2], data)
            return

        if RPM_BROADCAST_ID is not None and can_id == RPM_BROADCAST_ID and len(data) >= 2:
            # Placeholder decode — actual byte layout for ND Miata RPM
            # must be confirmed by sniffing. Default: high byte first, /4.
            rpm = ((data[0] << 8) | data[1]) / 4
            self.latest['RPM'] = rpm
            self._last_rpm_ms = time.ticks_ms()

    def _decode_obd(self, pid, data):
        if pid == PID_ECT and len(data) >= 4:
            self.latest['ECT'] = _c_to_f(data[3] - 40)
        elif pid == PID_IAT and len(data) >= 4:
            self.latest['IAT'] = _c_to_f(data[3] - 40)
        elif pid == PID_RPM and len(data) >= 5:
            self.latest['RPM'] = ((data[3] << 8) | data[4]) / 4
            self._last_rpm_ms = time.ticks_ms()
        elif pid == PID_AFR and len(data) >= 5:
            lam = ((data[3] << 8) | data[4]) / 32768
            self.latest['AFR'] = lam * 14.7
