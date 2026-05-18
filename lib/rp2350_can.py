from machine import Pin, SPI, PWM, I2C
import time

XL2515_SPI_PORT = 1
XL2515_SCLK_PIN = 10
XL2515_MOSI_PIN = 11
XL2515_MISO_PIN = 12
XL2515_CS_PIN = 9
XL2515_INT_PIN = 8

filter_id = 0x123

class RP2350_CAN:
    def __init__(self, rate_kbps = "125KBPS", spi_cs = XL2515_CS_PIN, irq = XL2515_INT_PIN, spi_port = XL2515_SPI_PORT, spi_clk = XL2515_SCLK_PIN,spi_mosi = XL2515_MOSI_PIN, spi_miso = XL2515_MISO_PIN,  spi_freq=10_000_000):
        self.can_rate_arr = {
            "5KBPS"   : [0xBF, 0xFF, 0x87],
            "10KBPS"  : [0x5F, 0xFF, 0x87],
            "20KBPS"  : [0x18, 0XA4, 0x04],
            "50KBPS"  : [0x09, 0XA4, 0x04],
            "100KBPS" : [0x04, 0x9E, 0x03],
            "125KBPS" : [0x03, 0x9E, 0x03],
            "250KBPS" : [0x01, 0x1E, 0x03],
            "500KBPS" : [0x00, 0x9E, 0x03],
            "800KBPS" : [0x00, 0x92, 0x02],
            "1000KBPS": [0x00, 0x82, 0x02],
        }

        self.spi = SPI(spi_port, spi_freq, polarity = 0, phase = 0, bits = 8, sck = Pin(spi_clk), mosi = Pin(spi_mosi), miso = Pin(spi_miso))
        self.cs = Pin(spi_cs, Pin.OUT)
        self.cs(1)
        self.int = Pin(irq, Pin.IN, Pin.PULL_UP)
        self.int.irq(handler = self.int_callback, trigger = Pin.IRQ_FALLING)
        self.recv_flag = False
        self.reset()
        time.sleep(0.1)
        self.config(rate_kbps)

    def config(self, rate_kbps):
        CNF3 = 0x28
        CNF2 = 0x29
        CNF1 = 0x2A

        TXB0SIDH = 0x31
        TXB0SIDL = 0x32
        TXB0DLC = 0x35

        RXB0SIDH = 0x61
        RXB0SIDL = 0x62
        RXB0CTRL = 0x60
        RXB0DLC = 0x65

        RXF0SIDH = 0x00
        RXF0SIDL = 0x01
        RXM0SIDH = 0x20
        RXM0SIDL = 0x21

        CANINTF = 0x2C
        CANINTE = 0x2B

        CANCTRL = 0x0F
        REQOP_NORMAL = 0x00
        CLKOUT_ENABLED = 0x04
        CANSTAT = 0x0E
        OPMODE_NORMAL = 0x00

        self.write_byte(CNF1, self.can_rate_arr[rate_kbps][0])
        self.write_byte(CNF2, self.can_rate_arr[rate_kbps][1])
        self.write_byte(CNF3, self.can_rate_arr[rate_kbps][2])
        self.write_byte(TXB0SIDH, 0xFF);
        self.write_byte(TXB0SIDL, 0xE0);
        self.write_byte(TXB0DLC, 0x40 | 0x08);

        # Set RX
        self.write_byte(RXB0SIDH, 0x00);
        self.write_byte(RXB0SIDL, 0x60);
        self.write_byte(RXB0CTRL, 0x00); # To receive all IDs, change this to 0x60
        self.write_byte(RXB0DLC, 0x08);

        self.write_byte(RXF0SIDH, (filter_id >> 3) & 0XFF)
        self.write_byte(RXF0SIDL, (filter_id & 0x07) << 5)
        self.write_byte(RXM0SIDH, 0xFF);
        self.write_byte(RXM0SIDL, 0xE0);

        # can int
        self.write_byte(CANINTF, 0x00); # clean interrupt flag
        self.write_byte(CANINTE, 0x01); # Receive Buffer 0 Full Interrupt Enable Bit

        self.write_byte(CANCTRL, REQOP_NORMAL | CLKOUT_ENABLED)
        dummy = self.read_byte(CANSTAT)
        if ((dummy & 0xe0) != OPMODE_NORMAL):
            print("OPMODE_NORMAL")
            self.write_byte(CANCTRL, REQOP_NORMAL | CLKOUT_ENABLED) #set normal mode

    def send(self, can_id, data):
        TXB0CTRL = 0x30
        TXB0SIDH = 0x31
        TXB0SIDL = 0x32
        TXB0EID8 = 0x33
        TXB0EID0 = 0x34
        TXB0DLC  = 0x35
        TXB0D0   = 0x36
        dly = 0
        while ((self.read_byte(TXB0CTRL) & 0x08) and (dly < 50)):
            dly += 1
            time.sleep_ms(1)

        self.write_byte(TXB0SIDH, (can_id >> 3) & 0XFF)
        self.write_byte(TXB0SIDL, (can_id & 0x07) << 5)

        self.write_byte(TXB0EID8, 0)
        self.write_byte(TXB0EID0, 0)
        self.write_byte(TXB0DLC, len(data))
        for i in range(len(data)):
            self.write_byte(TXB0D0 + i, data[i])
        self.write_byte(TXB0CTRL, 0x08)

    def recv(self):
        RXB0SIDH = 0x61
        RXB0SIDL = 0x62
        CANINTF = 0x2C
        CANINTE = 0x2B
        RXB0DLC = 0x65
        RXB0D0 = 0x66

        if self.recv_flag == False:
            return None
        self.recv_flag = False

        sid_h = self.read_byte(RXB0SIDH)
        sid_l = self.read_byte(RXB0SIDL)
        can_id = (sid_h << 3) | (sid_l >> 5)
        print("ID:", hex(can_id))

        while True:
            if (self.read_byte(CANINTF) & 0x01):
                len = self.read_byte(RXB0DLC)
                buf = bytearray(len)
                for i in range(len):
                   buf[i] = self.read_byte(RXB0D0 + i)
                self.write_byte(CANINTF, 0);
                self.write_byte(CANINTE, 0x01)  # enable
                self.write_byte(RXB0SIDH, 0x00) # clean
                self.write_byte(RXB0SIDL, 0x60)
                return buf

    def int_callback(self, pin):
        self.recv_flag = True

    def reset(self):
        CAN_RESET = 0xC0
        self.cs(0)
        self.spi.write(bytearray([CAN_RESET]))
        self.cs(1)

    def read_byte(self, reg):
        CAN_READ = 0x03
        self.cs(0)
        self.spi.write(bytearray([CAN_READ, reg]))
        data = self.spi.read(1)
        self.cs(1)

        return data[0]
    def write_byte(self, reg, data):
        CAN_WRITE = 0x02
        self.cs(0)
        self.spi.write(bytearray([CAN_WRITE, reg, data]))
        self.cs(1)

if __name__ == "__main__":
    can = RP2350_CAN()
    while True:
        can.send(0x123, [0x12, 0x34, 0x56, 0x78, 0x87, 0x65, 0x43, 0x21])
        recv_data = can.recv()
        if recv_data != None:
            print("recv:", [hex(i) for i in recv_data])
        time.sleep(1)
