# TraceVeda Hardware

This folder contains the ESP32 firmware for the two monitoring nodes used in the TraceVeda prototype, along with component-level and earlier development sketches.

- **Storage Node:** monitors the storage environment and door state.
- **Truck Node:** monitors the transport environment, location, door state and payload weight.

Both final node sketches communicate with the TraceVeda backend using Wi-Fi and the IoT readings API.

## Contents

- [Final firmware](#final-firmware)
- [Hardware overview](#hardware-overview)
- [Pin mapping](#pin-mapping)
- [Power and wiring precautions](#power-and-wiring-precautions)
- [Firmware setup](#firmware-setup)
- [Backend communication](#backend-communication)
- [Development sketches](#development-sketches)
- [Known validation points](#known-validation-points)

## Final firmware

| Node | Firmware |
|---|---|
| Storage Node | [`Storage_Node_Final/Storage_Node_Final.ino`](Storage_Node_Final/Storage_Node_Final.ino) |
| Truck Node | [`Truck_Node_Final/Truck_Node_Final.ino`](Truck_Node_Final/Truck_Node_Final.ino) |

Use these two sketches as the final integrated firmware starting points. Sketches under `Development/` are retained for component testing and earlier development; they are not the final node firmware.

## Hardware overview

### Storage Node

| Component | Purpose |
|---|---|
| ESP32 development board | Reads sensors and communicates with the backend |
| DHT22 | Temperature and relative humidity |
| BH1750 | Ambient light intensity |
| Limit switch | Storage door/contact state |
| I²C LCD 20×4 | Local readings and node status |
| Red LED | Backend-directed alert indication |

### Truck Node

| Component | Purpose |
|---|---|
| ESP32 development board | Reads sensors and communicates with the backend |
| DHT22 | Temperature and relative humidity |
| BH1750 | Ambient light intensity |
| NEO-6M GPS | Latitude/longitude and GPS fix information |
| Limit switch | Transport-compartment door/contact state |
| 20 kg load cell with HX711 | Payload-weight measurement |
| I²C LCD 16×2 | Local readings and node status |
| Red LED | Backend-directed alert indication |

The MPU6050/MPU-6500 motion sensor was considered during an earlier development stage and then removed from the final Truck Node design. The old test sketch remains in `Development/` for historical reference only.

## Pin mapping

The following signal mappings are taken from the final firmware sketches.

### Storage Node

| Module / signal | ESP32 connection |
|---|---|
| DHT22 DATA | GPIO 4 |
| BH1750 SDA | GPIO 21 |
| BH1750 SCL | GPIO 22 |
| LCD SDA | GPIO 21 |
| LCD SCL | GPIO 22 |
| Limit switch signal | GPIO 27 (`INPUT_PULLUP`) |
| Red LED control | GPIO 25 |
| LCD I²C address | `0x27` |
| LCD size | 20 columns × 4 rows |

### Truck Node

| Module / signal | ESP32 connection |
|---|---|
| DHT22 DATA | GPIO 4 |
| BH1750 SDA | GPIO 21 |
| BH1750 SCL | GPIO 22 |
| LCD SDA | GPIO 21 |
| LCD SCL | GPIO 22 |
| GPS module TX → ESP32 RX | GPIO 16 (UART2 RX) |
| ESP32 TX → GPS module RX | GPIO 17 (UART2 TX) |
| Limit switch signal | GPIO 27 (`INPUT_PULLUP`) |
| HX711 DT / DOUT | GPIO 32 |
| HX711 SCK / CLK | GPIO 33 |
| Red LED control | GPIO 25 |
| LCD I²C address | `0x27` |
| LCD size | 16 columns × 2 rows |

### Limit-switch contact

The prototype wiring used the limit switch's **COM and NC** contacts. The firmware configures GPIO 27 with `INPUT_PULLUP`. Check the switch's physical state and continuity before installation, and confirm that the displayed OPEN/CLOSED interpretation matches the actual mechanical mounting.

## Power and wiring precautions

- Both ESP32 development boards were powered through USB during prototype testing.
- The connected modules used a mixture of 3.3 V and 5 V supplies; the LCD was an example of a 5 V module. Confirm the supply requirement of each exact breakout/module before wiring.
- ESP32 GPIO pins are **not 5 V tolerant**. Do not connect a 5 V logic output directly to an ESP32 input.
- Check I²C pull-up voltage. A 5 V LCD backpack may pull SDA/SCL up to 5 V; use a suitable level shifter or a verified 3.3 V-compatible arrangement where required.
- Connect grounds together when modules use separate supply rails, while ensuring the supply and signal levels are appropriate.
- Verify polarity, pin labels and current requirements before powering the circuit.
- The pin tables describe firmware signal assignments. They are not a substitute for checking the exact breakout-board pinout or creating a verified as-built electrical schematic.

## Firmware setup

### Requirements

- Arduino IDE.
- ESP32 board support installed in Arduino IDE.
- USB data cable suitable for the ESP32 development board.
- The modules listed in the node overview.
- The libraries included by the relevant sketch, such as:
  - `Wire`
  - `LiquidCrystal_I2C`
  - `BH1750`
  - `DHT`
  - `WiFi`
  - `HTTPClient`
  - `LittleFS`
  - `TinyGPSPlus` (Truck Node)
  - `HardwareSerial` (Truck Node)
  - `HX711` (Truck Node)

Install the required libraries using the Arduino IDE Library Manager or the library provider's recommended installation method. Library versions are not pinned in this repository.

### Upload a node

1. Open the relevant final `.ino` file in Arduino IDE.
2. Install the required libraries.
3. Select the ESP32 board type and the correct serial port.
4. Set the Wi-Fi SSID and password in the sketch.
5. Set the backend base URL and confirm that the IoT endpoint path is `/api/iot/readings`.
6. Set the device API key to the same value configured as `TRACEVEDA_DEVICE_API_KEY` in the backend.
7. Confirm the batch and storage/transport identifiers used by the prototype.
8. Check every wire, supply rail and common ground before powering the circuit.
9. Upload the sketch and open Serial Monitor at the baud rate configured in the sketch.
10. Confirm sensor detection, LCD output, Wi-Fi connection and backend receipt of readings.

The final sketches contain configuration placeholders or development values. Replace them with values for your own environment before flashing. Do not commit Wi-Fi passwords, backend credentials or real device keys.

## Backend communication

Both final sketches send IoT readings to:

```http
POST /api/iot/readings
```

The device authenticates with the `X-Device-Key` HTTP header. The key must match `TRACEVEDA_DEVICE_API_KEY` in `BACKEND/.env`.

The firmware includes:
- Sensor sampling and local LCD/serial output.
- Wi-Fi connectivity checks.
- HTTP telemetry upload.
- A RAM queue for pending readings.
- LittleFS-based buffering for readings that cannot be uploaded immediately.
- Backend-controlled red LED state handling.

The backend must be reachable from the network used by the ESP32. A computer's `localhost` address is not reachable from an ESP32 as the computer itself; use the computer's LAN IP for a local server, or a reachable deployed backend URL.

See [`../BACKEND/README.md`](../BACKEND/README.md) for backend setup and IoT API configuration.

## Development sketches

`Development/` contains earlier component and integration experiments.

```text
HARDWARE/
├── Storage_Node_Final/
│   └── Storage_Node_Final.ino
├── Truck_Node_Final/
│   └── Truck_Node_Final.ino
├── Development/
│   ├── Component_Testing/
│   │   ├── BH1750_Test/
│   │   ├── DHT22_Test/
│   │   ├── ESP32_Test/
│   │   ├── GPS_Test/
│   │   ├── LCD_16x2_Test/
│   │   ├── LCD_20x4_Test/
│   │   ├── Limit_Switch_Test/
│   │   ├── Load_Cell_HX711_Test/
│   │   └── MPU6050_Test/
│   ├── Storage_Node/
│   │   ├── Storage_I2C_Scanner/
│   │   ├── Storage_Node_Test/
│   │   ├── Storage_Node_Updated/
│   │   └── Storage_WiFi_Test/
│   └── Truck_Node/
│       └── Truck_Node_Test/
└── README.md
```

`Little_FS_Clear/` is a utility sketch that clears the ESP32 LittleFS filesystem. It is destructive to locally buffered files. Do not run it on a node containing readings that you need to preserve.

## Known validation points

- **Load-cell calibration:** the Truck Node uses a 20 kg load cell with an HX711. Calibration/zeroing issues were observed during prototype testing. The calibration constant in the sketch must not be treated as proof of accurate measurement. Recalibrate with known reference weights, verify zero after unloading, check mounting/mechanical loading and validate across the intended range before relying on the readings.
- **GPS reception:** GPS reception may be poor indoors. Validate the NEO-6M outdoors with adequate sky visibility and confirm a valid fix before interpreting coordinates.
- **Power and logic levels:** confirm the actual voltage requirements and I²C pull-up levels of the modules used in the build.
- **Limit-switch interpretation:** the prototype used COM and NC. Confirm the installed switch's mechanical state and firmware interpretation together.
- **Offline queue:** test connectivity loss and recovery in a controlled environment. Confirm that queued readings upload as expected before treating the node as deployment-ready.
- **Prototype status:** this documentation records the firmware mappings and known prototype behavior. It does not claim that a currently assembled device has been re-inspected or independently revalidated.

---

For the full project context, see the [main TraceVeda README](../README.md).
