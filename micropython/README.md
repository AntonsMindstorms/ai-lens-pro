# AI Lens Pro library for MicroPython

A MicroPython driver for the **ELECFREAKS AI Lens Pro** AI camera, made for the [LMS-ESP32](https://www.antonsmindstorms.com/product/powerful-lms-esp32-board-for-spike-and-mindstorms/). It works on any MicroPython board with I2C.

## Install

1. Flash MicroPython onto the LMS-ESP32 with the [LMS-ESP32 firmware tool](https://firmware.antonsmindstorms.com) (in Chrome or Edge, no installation needed).
2. Copy [ailenspro.py](ailenspro.py) to the board, with Thonny, [ViperIDE](https://viper-ide.org) or `mpremote cp micropython/ailenspro.py :`.

## First program

```python
from ailenspro import AILensPro, OBJECT

lens = AILensPro(scl=2, sda=33)    # the pins your camera is on
lens.switch_to(OBJECT)

while True:
    lens.update()
    if lens.sees('person'):
        p = lens.find('person')
        print('person at', p.x, p.y, 'confidence', p.confidence)
```

Without arguments, `AILensPro()` uses SCL = GPIO 4 and SDA = GPIO 5. You can also pass your own bus: `AILensPro(i2c=I2C(...))`.

## Examples

| Example | What it does |
| --- | --- |
| [uRemote: line, cards and pose](examples/uremote/) | A SPIKE Prime robot follows a line, drives by picture cards, or prints poses. Pybricks programs in blocks and Python. |
| [PUPRemote: cards and line](examples/pupremote/) | The same line follower and card robot, with the standard Pybricks firmware. |
| [pose.py](examples/pose.py) | Prints the pose and the wrist positions in the terminal. |

## API

**Setup**

| | |
| --- | --- |
| `AILensPro(i2c=None, scl=4, sda=5, freq=100000, address=0x60, wait=True, timeout_ms=3000)` | Raises `OSError` when the lens does not answer. |
| `switch_to(app, wait=True)` | `FACE`, `EXPRESSION`, `GESTURE`, `POSE`, `OBJECT`, `TRACKING`, `BALL`, `CARD`, `COLOR`, `LINE`, `OCR`, `CODE`, `SELF_LEARNING`, `RHYTHM`, `MAIN_MENU`, `CAMERA`, `PHOTOS`, `SETTINGS`, `FILE_MANAGER`, or the name as text. Returns `True` when the lens is in that function. By default it waits for the switch (a few seconds). With `wait=False` it only sends the request and returns `False` until the lens has switched: call it again on every loop when something else must keep running, such as a LEGO hub waiting for an answer. |
| `read_app()`, `app_name`, `is_connected()` | The active function, and whether the lens answers. |
| `light(on=True, brightness=80)` | Fill light on/off, 5–100 %. |

**Results**

| | |
| --- | --- |
| `update()` | Returns the list of `Target`s, or `None` if reading failed (the previous results are kept). |
| `results`, `count`, `largest`, `closest` | All targets (largest first), how many the lens reports, the largest target, and the one nearest the image center. |
| `sees(what='anything')`, `find(what)`, `find_all(what)` | Look up targets by name or id. Not case sensitive. |
| `Target` | `.x .y .width .height .id .name .confidence .color` (`(r, g, b)` or `None`), `.keypoints` (17 `(x, y)` for poses), `.keypoint('left wrist')`, `.area`. |
| `text` | OCR text or QR / barcode content. |
| `line_detected`, `line_offset`, `line_angle`, `line_direction(tolerance=10)` | Line following. The offset (−320 left … 320 right) is measured at the middle of the line; the angle is in degrees, negative when the line bends left. |
| `line_near_end`, `line_far_end`, `line_center` | `(x, y)` of the end of the line nearest the bottom of the screen, the end nearest the top, and its middle. The origin is the bottom center of the screen, x to the right and y up, so the top left corner is (−320, 480). When the line leaves through a side, the near end is where it does. `(0, 0)` when no line is detected, so check `line_detected` first. |
| `line_length` | Length of the detected line in pixels. |
| `blinks`, `mouth_opens` | Face recognition counters. |
| `red_ball`, `blue_ball` | Ball colors seen. |
| `tracking_lost` | Object tracking state. |
| `rhythm_recognized`, `bpm`, `beats`, `rhythm_duration_ms` | Rhythm detection. |

**Commands**

| | |
| --- | --- |
| `set_color_mode('basic' / 'learned')` | Color recognition mode. |
| `start_tracking(x1, y1, x2, y2)`, `stop_tracking()` | Object tracking. |
| `learn(id)`, `forget(id=0)` | Self learning. |
| `set_ocr_region(...)`, `clear_ocr_region()` | Limit text recognition to a box. |
| `record_rhythm(seconds)`, `start_rhythm_recording()`, `stop_rhythm_recording()`, `analyse_audio_file(path)` | Rhythm detection. |
| `connect_wifi(ssid, password)`, `wifi_connected()` | The lens' own Wi-Fi. |

What `id` and `name` mean per function is listed in the [main README](../README.md#both-libraries-support-every-ai-lens-pro-function).

## Notes

- The I2C bus runs at 100 kHz, like the official ELECFREAKS extension. Results are read in chunks of 10 bytes with a CRC check.
- A few fields are not documented by ELECFREAKS, so the library doesn't use them: what a ball's id means (use `red_ball` / `blue_ball`), and the position of QR codes and barcodes (their x/y are 0).
- The line result holds more than the official extension reads: both ends of the line, its center and its length. These were decoded on the real device and are available as `line_near_end`, `line_far_end`, `line_center` and `line_length`.

More LEGO robotics projects and the LMS-ESP32 board: [antonsmindstorms.com](https://www.antonsmindstorms.com).
