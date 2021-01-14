import spidev
from datetime import datetime
from time import sleep
from influxdb import InfluxDBClient
# uses the "spidev" package ('sudo pip3 install spidev')
# check dtparam=spi=on --> in /boot/config.txt or (set via 'sudo raspi-config')

class MCP3201(object):
    """
    Functions for reading the MCP3201 12-bit A/D converter using the SPI bus either in MSB- or LSB-mode
    """
    def __init__(self, SPI_BUS, CE_PIN):
        """
        initializes the device, takes SPI bus address (which is always 0 on newer Raspberry models)
        and sets the channel to either CE0 = 0 (GPIO pin BCM 8) or CE1 = 1 (GPIO pin BCM 7)
        """
        if SPI_BUS not in [0, 1]:
            raise ValueError('wrong SPI-bus: {0} setting (use 0 or 1)!'.format(SPI_BUS))
        if CE_PIN not in [0, 1]:
            raise ValueError('wrong CE-setting: {0} setting (use 0 for CE0 or 1 for CE1)!'.format(CE_PIN))
        self._spi = spidev.SpiDev()
        self._spi.open(SPI_BUS, CE_PIN)
        self._spi.max_speed_hz = 1500000
        pass

    def readADC_MSB(self):
        """
        Reads 2 bytes (byte_0 and byte_1) and converts the output code from the MSB-mode:
        byte_0 holds two ?? bits, the null bit, and the 5 MSB bits (B11-B07),
        byte_1 holds the remaning 7 MBS bits (B06-B00) and B01 from the LSB-mode, which has to be removed.
        """
        bytes_received = self._spi.xfer2([0x00, 0x00])

        MSB_1 = bytes_received[1]
        MSB_1 = MSB_1 >> 1  # shift right 1 bit to remove B01 from the LSB mode

        MSB_0 = bytes_received[0] & 0b00011111  # mask the 2 unknown bits and the null bit
        MSB_0 = MSB_0 << 7  # shift left 7 bits (i.e. the first MSB 5 bits of 12 bits)

        return MSB_0 + MSB_1


    def convert_to_voltage(self, adc_output, VREF=5.0):
        """
        Calculates analogue voltage from the digital output code (ranging from 0-4095)
        VREF could be adjusted here (standard uses the 3V3 rail from the Rpi)
        """
        return adc_output * (VREF / (2 ** 12 - 1))



if __name__ == '__main__':
    SPI_bus = 0
    MCP3201_voltage = MCP3201(SPI_bus, 0)
    MCP3201_current = MCP3201(SPI_bus, 1)

    client = InfluxDBClient('localhost', 8086, 'root', 'root', 'pi2')

    try:
        while True:
            ADC_output_code = MCP3201_voltage.readADC_MSB()
            voltage = MCP3201_voltage.convert_to_voltage(ADC_output_code)

            ADC_output_code = 4095 - MCP3201_current.readADC_MSB()
            current = MCP3201_current.convert_to_voltage(ADC_output_code)
            print("MCP3201 voltage: %0.4f V & %0.4f A = %0.4f W" % (voltage, current, voltage * current))

            json_body  = [
                {
                    "measurement": "power",
                    "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "fields": {
                        "value": voltage * current
                    }
                }
            ]

            client.write_points(json_body)

            sleep(0.01)  
    except (KeyboardInterrupt):
        print('\n', "Exit on Ctrl-C: Good bye!")

    except:
        print("Other error or exception occurred!")
        raise

    finally:
        print()