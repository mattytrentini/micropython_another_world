"""ODROID Go hardware constants — GPIO pins, SPI config, ADC thresholds."""

# Display (ILI9341 over VSPI)
SPI_ID = 2         # VSPI
SPI_BAUD = 40_000_000
PIN_MOSI = 23
PIN_MISO = 19
PIN_SCLK = 18
PIN_DC = 21
PIN_CS_LCD = 5
PIN_BACKLIGHT = 14
DISPLAY_W = 320
DISPLAY_H = 240

# SD card (shares SPI bus with display)
PIN_CS_SD = 22

# Digital buttons (active LOW — 0 when pressed)
PIN_BTN_A = 32
PIN_BTN_B = 33
PIN_BTN_MENU = 13
PIN_BTN_SELECT = 27
PIN_BTN_START = 39   # input-only pin, external pull-up
PIN_BTN_VOLUME = 0   # external pull-up

# D-pad analog (ADC, 12-bit 0-4095, resistor ladder)
# Rest=0, LEFT/UP=4095, RIGHT/DOWN=~1850
PIN_JOY_X = 34
PIN_JOY_Y = 35
JOY_THRESH_MID_LOW = 800    # above = right (X) or down (Y)
JOY_THRESH_MID_HIGH = 2500  # above = left (X) or up (Y)

# Speaker
PIN_SPEAKER = 26
PIN_SPEAKER_EN = 25

# Battery ADC
PIN_BATTERY = 36

# Status LED
PIN_LED = 2
