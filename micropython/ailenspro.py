"""
ailenspro.py - MicroPython driver for the ELECFREAKS PlanetX AI Lens Pro (EF05074)

Works on any MicroPython board with I2C. Defaults are set for the LMS-ESP32
(SCL = GPIO4, SDA = GPIO5), so on that board this is enough:

    from ailenspro import AILensPro, CARD

    lens = AILensPro()
    lens.switch_to(CARD)
    while True:
        lens.update()
        if lens.sees('stop'):
            print('Stop!')

After each update(), `lens.results` holds a list of Target objects, largest
first. Every Target has the same attributes, whatever the function:

    x, y           centre of the target in screen pixels (screen is 640 x 480)
    width, height  size in pixels (0 when the function has no box)
    id             numeric id (card id, object class, learned id, color id, ...)
    name           text label ('stop', 'person', 'happy', learned name, OCR text, ...)
    confidence     0..100
    color          (r, g, b) tuple for color recognition, otherwise None
    keypoints      list of 17 (x, y) tuples for pose recognition, otherwise None

The protocol was reverse engineered from the official ELECFREAKS MakeCode
extension (github.com/elecfreaks/pxt-PlanetX-AI).

Copyright (c) Anton's Mindstorms - https://www.antonsmindstorms.com
License: GNU General Public License v3.0 (see LICENSE).
"""

import time

try:
    from micropython import const
except ImportError:  # CPython, for desktop tests
    def const(x):
        return x

try:
    _ticks_ms = time.ticks_ms
    _ticks_diff = time.ticks_diff
    _sleep_ms = time.sleep_ms
except AttributeError:  # CPython, for desktop tests
    def _ticks_ms():
        return int(time.monotonic() * 1000)

    def _ticks_diff(a, b):
        return a - b

    def _sleep_ms(ms):
        time.sleep(ms / 1000)

__version__ = '1.0.0'

I2C_ADDRESS = const(0x60)

# ---------------------------------------------------------------- functions
# These are the AI Lens Pro "apps". Use them with switch_to().
MAIN_MENU = const(0x01)
FACE = const(0x10)
SELF_LEARNING = const(0x11)
GESTURE = const(0x12)
FILE_MANAGER = const(0x13)
PHOTOS = const(0x14)
CAMERA = const(0x15)
SETTINGS = const(0x16)
RHYTHM = const(0x1B)
BALL = const(0x1E)
OBJECT = const(0x1F)
OCR = const(0x20)
LINE = const(0x21)
TRACKING = const(0x22)
EXPRESSION = const(0x23)
POSE = const(0x24)
COLOR = const(0x25)
CARD = const(0x26)
CODE = const(0x27)

APP_NAMES = {
    MAIN_MENU: 'main menu',
    FACE: 'face recognition',
    SELF_LEARNING: 'self learning',
    GESTURE: 'gesture recognition',
    FILE_MANAGER: 'file manager',
    PHOTOS: 'photos',
    CAMERA: 'camera',
    SETTINGS: 'settings',
    RHYTHM: 'rhythm recognition',
    BALL: 'ball recognition',
    OBJECT: 'object recognition',
    OCR: 'text recognition',
    LINE: 'line following',
    TRACKING: 'object tracking',
    EXPRESSION: 'expression recognition',
    POSE: 'pose recognition',
    COLOR: 'color recognition',
    CARD: 'card recognition',
    CODE: 'QR and barcodes',
}

# ------------------------------------------------------------- name tables
CARD_NAMES = (
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    'A', 'B', 'C', 'D', 'E',
    'forward', 'turn around', 'left', 'right', 'stop',
    'cat', 'dog', 'mouse', 'apple', 'pear', 'grapes', 'airplane', 'car',
    'ship', 'pen', 'ruler', 'microbit', 'clock', 'cup', 'umbrella',
)

# Color recognition in 'basic' mode, ids 1..6
BASIC_COLOR_NAMES = ('red', 'green', 'blue', 'white', 'black', 'yellow')

# Expression ids as sent by the device
EXPRESSION_NAMES = ('angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral')

# Pose ids 1..9
POSE_NAMES = ('standing', 'hand up', 'both hands up', 'squatting', 'bending',
              'sitting', 'falling', 'kneeling', 'running')

# Pose keypoints, in the order of Target.keypoints
KEYPOINTS = (
    'nose', 'left eye', 'right eye', 'left ear', 'right ear',
    'left shoulder', 'right shoulder', 'left elbow', 'right elbow',
    'left wrist', 'right wrist', 'left hip', 'right hip',
    'left knee', 'right knee', 'left ankle', 'right ankle',
)

# 80 COCO classes used by object recognition; the device also sends the name.
OBJECT_NAMES = (
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train',
    'truck', 'boat', 'traffic light', 'fire hydrant', 'stop sign',
    'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
    'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag',
    'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite',
    'baseball bat', 'baseball glove', 'skateboard', 'surfboard',
    'tennis racket', 'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon',
    'bowl', 'banana', 'apple', 'sandwich', 'orange', 'broccoli', 'carrot',
    'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch', 'potted plant',
    'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
    'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
    'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear',
    'hair drier', 'toothbrush',
)

SCREEN_WIDTH = const(640)
SCREEN_HEIGHT = const(480)

# ---------------------------------------------------------- protocol consts
_CMD_REG_READ = const(0x21)
_CMD_APP_FRAME = const(0x30)
_REG_APP_ID = const(0)
_REG_RESULT = const(100)
_REG_WIFI = const(0x10)

_APP_CMD_AUDIO_PATH = const(0x37)
_APP_CMD_RHYTHM = const(0x38)
_APP_CMD_AUDIO_START = const(0x3A)
_APP_CMD_WIFI_CONNECT = const(0x41)
_APP_CMD_WIFI_STATUS = const(0x42)
_APP_CMD_WIFI_ACK = const(0x43)
_APP_CMD_COLOR_MODE = const(0x44)
_APP_CMD_OCR_REGION = const(0x45)
_APP_CMD_LIGHT = const(0x46)
_APP_CMD_TRACKING = const(0x47)
_APP_CMD_LEARN = const(0x48)

_WIFI_STATUS_READY = const(0x11)
_WIFI_CONNECT_RECEIVED = const(0x12)
_WIFI_ERROR = const(0x13)
_WIFI_PUBLIC_READY = const(4)
_WIFI_FAILED = const(5)


def _crc8(data, length):
    """CRC-8, polynomial 0x07, init 0x00."""
    crc = 0
    for i in range(length):
        crc ^= data[i]
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def _u16(buf, i):
    return buf[i] | (buf[i + 1] << 8)


def _i16(buf, i):
    v = buf[i] | (buf[i + 1] << 8)
    return v - 0x10000 if v & 0x8000 else v


def _text(buf, i, n):
    if n <= 0:
        return ''
    try:
        return bytes(buf[i:i + n]).decode('utf-8')
    except Exception:  # invalid UTF-8
        return ''.join(chr(b) if b < 128 else '?' for b in buf[i:i + n])


def _le16(v):
    v = max(0, min(0xFFFF, int(v)))
    return (v & 0xFF, v >> 8)


class Target:
    """One thing the AI Lens Pro sees."""

    __slots__ = ('x', 'y', 'width', 'height', 'id', 'name', 'confidence',
                 'color', 'keypoints')

    def __init__(self, x=0, y=0, width=0, height=0, id=0, name='',
                 confidence=0, color=None, keypoints=None):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.id = id
        self.name = name
        self.confidence = confidence
        self.color = color
        self.keypoints = keypoints

    @property
    def area(self):
        return self.width * self.height

    def keypoint(self, name):
        """(x, y) of a pose keypoint such as 'left wrist', or None if not visible."""
        if not self.keypoints:
            return None
        p = self.keypoints[KEYPOINTS.index(name)]
        return None if p[0] < 0 else p

    def __repr__(self):
        s = 'Target(name={!r}, id={}, x={}, y={}, w={}, h={}, conf={}'.format(
            self.name, self.id, self.x, self.y, self.width, self.height,
            self.confidence)
        if self.color is not None:
            s += ', color={}'.format(self.color)
        return s + ')'


class AILensPro:
    """Driver for the AI Lens Pro.

    lens = AILensPro()                        # LMS-ESP32: SCL=4, SDA=5
    lens = AILensPro(scl=22, sda=21)          # other ESP32 boards
    lens = AILensPro(i2c=my_i2c)              # bring your own machine.I2C
    """

    def __init__(self, i2c=None, scl=4, sda=5, freq=100000,
                 address=I2C_ADDRESS, chunk=10, wait=True, timeout_ms=3000):
        if i2c is None:
            from machine import I2C, Pin
            i2c = I2C(1, scl=Pin(scl), sda=Pin(sda), freq=freq)
        self.i2c = i2c
        self.address = address
        self.chunk = max(1, min(30, chunk))  # bytes per register read
        self.app = None              # id of the active function, after update()
        self._switch_asked = None    # (function, ticks) of a non-blocking switch
        self.results = []            # list of Target, largest first
        self.count = 0               # how many targets the lens reports
        self.blinks = 0              # face recognition
        self.mouth_opens = 0         # face recognition
        self.line_detected = False   # line following
        self.line_offset = 0         # line following: -320 (left) .. +320 (right)
        self.line_angle = 0          # line following: degrees, negative = left
        self.line_length = 0         # line following: segment length in pixels
        # line following, origin = bottom centre of the screen, x to the
        # right, y up (so the top left corner is (-320, 480)); (0, 0) if no line
        self.line_near_end = (0, 0)  # (x, y) end of the line nearest the bottom
        self.line_far_end = (0, 0)   # (x, y) end of the line nearest the top
        self.line_center = (0, 0)    # (x, y) middle of the line
        self.tracking_lost = False   # object tracking
        self.red_ball = False        # ball recognition
        self.blue_ball = False       # ball recognition
        self.color_mode = None       # 'basic' or 'learned'
        self.rhythm_recognized = False
        self.bpm = 0
        self.beats = 0
        self.rhythm_duration_ms = 0
        self._wifi_seq = 0
        if wait and not self.wait_ready(timeout_ms):
            raise OSError('AI Lens Pro not found at I2C address 0x{:02X}. '
                          'Is it switched on and connected?'.format(address))

    # ============================================================ low level
    def _packet(self, cmd, params):
        n = len(params)
        pkt = bytearray(n + 4)
        pkt[0] = 0xAA
        pkt[1] = cmd
        pkt[2] = n
        pkt[3:3 + n] = bytes(params)
        pkt[n + 3] = _crc8(pkt, n + 3)
        return pkt

    def _write(self, cmd, params=b''):
        try:
            self.i2c.writeto(self.address, self._packet(cmd, params))
        except OSError:
            return False
        _sleep_ms(2)
        return True

    def _query(self, cmd, params, n):
        if not self._write(cmd, params):
            return None
        try:
            raw = self.i2c.readfrom(self.address, n + 1)
        except OSError:
            return None
        if len(raw) < n + 1 or _crc8(raw, n) != raw[n]:
            return None
        return raw[:n]

    def read_register(self, addr, length, retries=3):
        """Read `length` bytes starting at register `addr`. Returns bytes or None."""
        out = bytearray()
        while len(out) < length:
            n = min(self.chunk, length - len(out))
            a = addr + len(out)
            part = None
            for attempt in range(retries):
                if attempt:
                    _sleep_ms(2)
                part = self._query(_CMD_REG_READ, (a >> 8, a & 0xFF, 0, n), n)
                if part is not None:
                    break
            if part is None:
                return None
            out.extend(part)
        return bytes(out)

    def send(self, cmd, payload=b''):
        """Send a command to the active function (wrapped in I2C command 0x30)."""
        payload = bytes(payload)
        frame = bytes((0xFF, 0xF9, cmd, len(payload))) + payload
        if len(frame) > 253:
            raise ValueError('command too long')
        return self._write(_CMD_APP_FRAME, bytes((0, len(frame))) + frame)

    # ============================================================ basics
    def read_app(self):
        """Id of the active function, or None when the lens does not answer."""
        b = self.read_register(_REG_APP_ID, 1, retries=2)
        if b is None or b[0] not in APP_NAMES:
            return None
        return b[0]

    def is_connected(self):
        return self.read_app() is not None

    def wait_ready(self, timeout_ms=3000):
        """Wait until the lens answers. Returns True when it does."""
        start = _ticks_ms()
        while True:
            if self.is_connected():
                return True
            if _ticks_diff(_ticks_ms(), start) > timeout_ms:
                return False
            _sleep_ms(20)

    @property
    def app_name(self):
        """Name of the active function, e.g. 'card recognition'."""
        return APP_NAMES.get(self.read_app(), '')

    def switch_to(self, app, timeout_ms=6000, retries=3, wait=True):
        """Switch to a function, e.g. switch_to(CARD) or switch_to('card recognition').

        Returns True when the lens is in that function. If it is not yet:
        with wait=True (default) this blocks until it has switched (a few
        seconds) and returns True on success. With wait=False it never waits:
        it sends the switch request once (again after timeout_ms) and returns
        False; call it again later, e.g. on every loop, until it returns True.
        Use wait=False where something else must keep running meanwhile.
        """
        app = self._app_id(app)
        if self.read_app() == app:
            if self._switch_asked is not None and self._switch_asked[0] == app:
                self.results = []
                self.count = 0
            self._switch_asked = None
            self.app = app
            return True
        if not wait:
            now = _ticks_ms()
            asked = self._switch_asked
            if asked is None or asked[0] != app or _ticks_diff(now, asked[1]) > timeout_ms:
                self.send(app, b'\x00')
                self._switch_asked = (app, now)
            return False
        for attempt in range(retries + 1):
            if attempt:
                _sleep_ms(120)
            if not self.send(app, b'\x00'):
                return False
            start = _ticks_ms()
            misses = 0
            while _ticks_diff(_ticks_ms(), start) < timeout_ms:
                _sleep_ms(20)
                cur = self.read_app()
                if cur == app:
                    self.app = app
                    self.results = []
                    self.count = 0
                    return True
                misses = misses + 1 if cur is None else 0
                if misses >= 5:
                    return False
        return False

    @staticmethod
    def _app_id(app):
        if isinstance(app, str):
            for k, v in APP_NAMES.items():
                if v.lower() == app.lower():
                    return k
            raise ValueError('unknown function: ' + app)
        if app not in APP_NAMES:
            raise ValueError('unknown function id: {}'.format(app))
        return app

    def light(self, on=True, brightness=80):
        """Switch the white fill light on or off. Brightness 5..100 %."""
        brightness = int(brightness)
        if not on or brightness <= 0:
            return self.send(_APP_CMD_LIGHT, (0, 0))
        return self.send(_APP_CMD_LIGHT, (1, max(5, min(100, brightness))))

    # ============================================================ results
    def update(self):
        """Read the latest results of the active function.

        Returns the list of targets (largest first). When reading fails the
        previous results are kept and None is returned.
        """
        app = self.read_app()
        if app is None:
            return None
        self.app = app
        parser = self._PARSERS.get(app)
        if parser is None:  # menu, camera, photos, ...
            self.results = []
            self.count = 0
            return self.results
        found = parser(self)
        if found is None:
            return None
        count, results = found
        results.sort(key=lambda t: t.width * t.height, reverse=True)
        self.results = results
        self.count = max(count, len(results))
        return results

    def sees(self, what='anything'):
        """True when a target with this name or id is in the latest results.

        sees()            anything at all
        sees('stop')      by name (not case sensitive)
        sees(3)           by id
        sees('red ball')  ball recognition, by color
        """
        if what in ('', 'anything', None):
            return self.count > 0
        if what == 'red ball':
            return self.red_ball
        if what == 'blue ball':
            return self.blue_ball
        return self.find(what) is not None

    def find(self, what):
        """First (largest) target with this name or id, or None."""
        key = str(what).lower()
        for t in self.results:
            if t.name.lower() == key or str(t.id) == key:
                return t
        return None

    def find_all(self, what):
        key = str(what).lower()
        return [t for t in self.results if t.name.lower() == key or str(t.id) == key]

    @property
    def largest(self):
        """The largest target, or None."""
        return self.results[0] if self.results else None

    @property
    def closest(self):
        """The target closest to the centre of the image, or None."""
        best = None
        best_d = 0
        for t in self.results:
            d = (t.x - 320) ** 2 + (t.y - 240) ** 2
            if best is None or d < best_d:
                best, best_d = t, d
        return best

    @property
    def text(self):
        """Recognized text (OCR) or code content (QR / barcode), else ''."""
        if self.app in (OCR, CODE) and self.results:
            return self.results[0].name
        return ''

    def line_direction(self, tolerance=10):
        """'left', 'center', 'right' or None, based on the line angle."""
        if not self.line_detected:
            return None
        if self.line_angle < -tolerance:
            return 'left'
        if self.line_angle > tolerance:
            return 'right'
        return 'center'

    # ============================================================ commands
    def set_color_mode(self, mode='basic'):
        """'basic': recognize 6 standard colors at the centre of the image.
        'learned': find colors that were learned on the device (ids 1..30).
        """
        if mode not in ('basic', 'learned'):
            raise ValueError("mode must be 'basic' or 'learned'")
        if self.read_app() != COLOR:
            self.switch_to(COLOR)
        ok = self.send(_APP_CMD_COLOR_MODE, (1 if mode == 'basic' else 0,))
        _sleep_ms(30)
        return ok

    def start_tracking(self, x1=220, y1=140, x2=420, y2=340):
        """Start tracking the object inside this box (screen is 640 x 480)."""
        box = []
        for v, hi in ((x1, 640), (y1, 480), (x2, 640), (y2, 480)):
            box.extend(_le16(max(0, min(hi, v))))
        self.tracking_lost = False
        return self.send(_APP_CMD_TRACKING, bytes([1] + box))

    def stop_tracking(self):
        return self.send(_APP_CMD_TRACKING, (0,))

    def learn(self, id=1):
        """Self learning: learn the object at the centre of the image as id 1..30."""
        if not 1 <= id <= 30:
            raise ValueError('id must be 1..30')
        return self.send(_APP_CMD_LEARN, (1, id))

    def forget(self, id=0):
        """Self learning: forget learned id 1..30, or 0 to forget everything."""
        if not 0 <= id <= 30:
            raise ValueError('id must be 0..30')
        return self.send(_APP_CMD_LEARN, (2, id))

    def set_ocr_region(self, x1=0, y1=0, x2=640, y2=480):
        """Only recognize text inside this box."""
        # Limits as in the official extension.
        box = []
        for v, hi in ((x1, 480), (y1, 640), (x2, 480), (y2, 640)):
            box.extend(_le16(max(0, min(hi, v))))
        return self.send(_APP_CMD_OCR_REGION, bytes([1] + box))

    def clear_ocr_region(self):
        return self.send(_APP_CMD_OCR_REGION, (0,))

    def start_rhythm_recording(self):
        """Rhythm recognition: start recording with the lens microphone."""
        return self.send(_APP_CMD_RHYTHM, (0x03,))

    def stop_rhythm_recording(self):
        """Rhythm recognition: stop recording and analyse."""
        return self.send(_APP_CMD_RHYTHM, (0x02,))

    def record_rhythm(self, seconds=10):
        """Record for 1..25 seconds (blocking), then analyse. Call update() for results."""
        seconds = max(1, min(25, int(seconds)))
        self.start_rhythm_recording()
        _sleep_ms(seconds * 1000)
        return self.stop_rhythm_recording()

    def analyse_audio_file(self, path='/sound_touch/test.wav'):
        """Rhythm recognition on a .wav file on the lens SD card."""
        data = path.strip().encode('utf-8')[:248]
        if not data:
            return False
        if not self.send(_APP_CMD_AUDIO_PATH, bytes([len(data)]) + data):
            return False
        _sleep_ms(30)
        return self.send(_APP_CMD_AUDIO_START, (1,))

    # ============================================================ Wi-Fi
    def _next_wifi_seq(self):
        self._wifi_seq = (self._wifi_seq % 255) + 1
        return self._wifi_seq

    def _wifi_mailbox(self, want_type, want_seq, timeout_ms):
        """Wait for a Wi-Fi mailbox message. Returns (type, state, flags) or None."""
        start = _ticks_ms()
        while _ticks_diff(_ticks_ms(), start) < max(50, timeout_ms):
            h = self.read_register(_REG_WIFI, 8, retries=2)
            if (h is None or h[0] != 0xA5 or h[1] != 0x01 or h[2] == 0
                    or (want_type is not None and h[2] != want_type)
                    or (want_seq is not None and h[3] != want_seq)):
                _sleep_ms(20)
                continue
            self.send(_APP_CMD_WIFI_ACK, (h[2], h[3]))
            return h[2], h[4], h[5]
        return None

    def wifi_status(self):
        """(state, flags) of the lens Wi-Fi, or None. State 4 = online, 5 = failed."""
        seq = self._next_wifi_seq()
        if not self.send(_APP_CMD_WIFI_STATUS, (seq,)):
            return None
        msg = self._wifi_mailbox(_WIFI_STATUS_READY, seq, 450)
        return None if msg is None else (msg[1], msg[2])

    def wifi_connected(self):
        st = self.wifi_status()
        return bool(st and st[0] == _WIFI_PUBLIC_READY and st[1] & 0x04)

    def connect_wifi(self, ssid, password='', timeout_ms=60000):
        """Connect the lens itself to Wi-Fi (for remote file management)."""
        s = ssid.strip().encode('utf-8')
        p = password.encode('utf-8')
        if not s or len(s) > 127 or len(p) > 119 or len(s) + len(p) > 246:
            raise ValueError('ssid or password too long')
        seq = self._next_wifi_seq()
        payload = bytes((seq, len(s), len(p))) + s + p
        accepted = False
        for _ in range(5):
            if self.send(_APP_CMD_WIFI_CONNECT, payload):
                start = _ticks_ms()
                while _ticks_diff(_ticks_ms(), start) < 3500:
                    msg = self._wifi_mailbox(None, seq, 650)
                    if msg is None:
                        _sleep_ms(80)
                        continue
                    if msg[0] == _WIFI_CONNECT_RECEIVED:
                        accepted = True
                        break
                    if msg[0] == _WIFI_ERROR:
                        break
            if accepted:
                break
            _sleep_ms(120)
        if not accepted:
            return False
        start = _ticks_ms()
        while _ticks_diff(_ticks_ms(), start) < timeout_ms:
            st = self.wifi_status()
            if st and st[0] == _WIFI_PUBLIC_READY and st[1] & 0x04:
                return True
            if st and st[0] == _WIFI_FAILED:
                return False
            _sleep_ms(400)
        return False

    # ============================================================ parsers
    # Each parser returns (count, [Target, ...]) or None when reading failed.
    # Offsets follow the official ELECFREAKS extension.

    def _read_with_label(self, head_len, label_index, extra=0):
        head = self.read_register(_REG_RESULT, head_len, retries=2)
        if head is None:
            return None
        n = head[label_index]
        if n == 0 and not extra:
            return head
        return self.read_register(_REG_RESULT, head_len + n + extra)

    def _parse_face(self):
        raw = self._read_with_label(15, 14, extra=1)
        if raw is None:
            raw = self._read_with_label(15, 14)
            if raw is None:
                return None
        state, fid, conf = raw[0], raw[1], min(100, raw[2])
        if fid == 0xFF:
            fid = 0
        self.blinks = raw[3]
        self.mouth_opens = raw[4]
        x1, y1, x2, y2 = _u16(raw, 6), _u16(raw, 8), _u16(raw, 10), _u16(raw, 12)
        n = raw[14]
        name = _text(raw, 15, n) if state == 1 and fid > 0 else ''
        results = []
        if raw[5] and (x1 != x2 or y1 != y2):
            results.append(Target((x1 + x2) // 2, (y1 + y2) // 2, max(0, x2 - x1),
                                  max(0, y2 - y1), fid, name, conf))
        count = raw[15 + n] if len(raw) > 15 + n else len(results)
        return count, results

    def _parse_self_learning(self):
        raw = self._read_with_label(4, 3)
        if raw is None:
            return None
        results = []
        if raw[0] and raw[1] > 0:
            results.append(Target(id=raw[1], name=_text(raw, 4, raw[3]),
                                  confidence=min(100, raw[2])))
        return len(results), results

    def _parse_gesture(self):
        raw = self._read_with_label(13, 12)
        if raw is None:
            return None
        results = []
        if raw[0]:
            name = _text(raw, 13, raw[12]) if raw[1] > 0 else ''
            results.append(Target(_u16(raw, 4), _u16(raw, 6), _u16(raw, 8),
                                  _u16(raw, 10), raw[1], name, min(100, raw[2])))
        return len(results), results

    def _parse_rhythm(self):
        raw = self.read_register(_REG_RESULT, 7, retries=2)
        if raw is None:
            return None
        self.rhythm_recognized = raw[0] == 1
        self.bpm = _u16(raw, 1)
        self.beats = _u16(raw, 3)
        self.rhythm_duration_ms = _u16(raw, 5) * 100
        return 0, []

    def _parse_ball(self):
        head = self.read_register(_REG_RESULT, 2, retries=2)
        if head is None:
            self.red_ball = self.blue_ball = False
            return None
        rc = min(head[1] & 0x1F, head[0], 16)
        raw = self.read_register(_REG_RESULT, 2 + rc * 10) if rc else head
        if raw is None:
            return None
        self.red_ball = bool(head[1] & 0x40)
        self.blue_ball = bool(head[1] & 0x80)
        results = []
        for i in range(rc):
            o = 2 + i * 10
            results.append(Target(_u16(raw, o + 2), _u16(raw, o + 4), _u16(raw, o + 6),
                                  _u16(raw, o + 8), raw[o], 'ball', min(100, raw[o + 1])))
        return raw[0], results

    def _parse_card(self):
        head = self.read_register(_REG_RESULT, 2, retries=2)
        if head is None:
            return None
        rc = min(head[1], head[0], 16)
        raw = self.read_register(_REG_RESULT, 2 + rc * 8) if rc else head
        if raw is None:
            return None
        results = []
        for i in range(rc):
            o = 2 + i * 8
            cid = raw[o]
            size = _u16(raw, o + 6)
            name = CARD_NAMES[cid] if cid < len(CARD_NAMES) else str(cid)
            results.append(Target(_u16(raw, o + 2), _u16(raw, o + 4), size, size,
                                  cid, name, min(100, raw[o + 1])))
        return raw[0], results

    def _parse_labeled_records(self, head_len, max_records, record_len, max_label):
        """Generic reader for [count, record count, (record + label) ...]."""
        head = self.read_register(_REG_RESULT, head_len, retries=2)
        if head is None:
            return None
        rc = min(head[head_len - 1], head[head_len - 2], max_records)
        if rc == 0:
            return head, 0, head_len
        raw = self.read_register(_REG_RESULT, head_len + rc * (record_len + 1 + max_label))
        if raw is None:
            return None
        return raw, rc, head_len

    def _walk(self, raw, rc, offset, record_len, max_label, make):
        results = []
        for _ in range(rc):
            if offset + record_len + 1 > len(raw):
                break
            n = min(raw[offset + record_len], max_label)
            if offset + record_len + 1 + n > len(raw):
                break
            results.append(make(raw, offset, _text(raw, offset + record_len + 1, n)))
            offset += record_len + 1 + n
        return results

    def _parse_object(self):
        r = self._parse_labeled_records(2, 8, 10, 16)
        if r is None:
            return None
        raw, rc, off = r

        def make(b, o, label):
            oid = b[o]
            if not label and oid < len(OBJECT_NAMES):
                label = OBJECT_NAMES[oid]
            return Target(_u16(b, o + 2), _u16(b, o + 4), _u16(b, o + 6),
                          _u16(b, o + 8), oid, label, min(100, b[o + 1]))
        return raw[0], self._walk(raw, rc, off, 10, 16, make)

    def _parse_expression(self):
        r = self._parse_labeled_records(2, 10, 11, 12)
        if r is None:
            return None
        raw, rc, off = r

        def make(b, o, label):
            eid = b[o + 1]
            if not label and eid < len(EXPRESSION_NAMES):
                label = EXPRESSION_NAMES[eid]
            return Target(_u16(b, o + 3), _u16(b, o + 5), _u16(b, o + 7),
                          _u16(b, o + 9), eid, label, min(100, b[o + 2]))
        return raw[0], self._walk(raw, rc, off, 11, 12, make)

    def _parse_pose(self):
        head = self.read_register(_REG_RESULT, 4, retries=2)
        if head is None:
            return None
        if head[0] != 0x02:
            return 0, []
        count = head[2] if head[1] == 0x01 else 0
        rc = min(head[3], count, 1)
        if rc == 0:
            return count, []
        raw = self.read_register(_REG_RESULT, 4 + 80 + 24)
        if raw is None:
            return None

        def coord(b, i):
            v = _u16(b, i)
            return -1 if v == 0xFFFF else v

        def make(b, o, label):
            pid = b[o + 1]
            if not label and 1 <= pid <= len(POSE_NAMES):
                label = POSE_NAMES[pid - 1]
            kp = [(coord(b, o + 11 + k * 4), coord(b, o + 13 + k * 4)) for k in range(17)]
            return Target(coord(b, o + 3), coord(b, o + 5), coord(b, o + 7),
                          coord(b, o + 9), pid, label, min(100, b[o + 2]), keypoints=kp)
        return count, self._walk(raw, rc, 4, 79, 24, make)

    def _parse_color(self):
        head = self.read_register(_REG_RESULT, 7, retries=2)
        if head is None:
            return None
        if head[0] == 1:  # basic colors: one result for the image centre
            self.color_mode = 'basic'
            n = min(head[6], 12)
            raw = self.read_register(_REG_RESULT, 7 + n) if n else head
            if raw is None:
                return None
            cid = raw[1]
            if cid == 0:
                return 0, []
            name = _text(raw, 7, n)
            if not name and cid <= len(BASIC_COLOR_NAMES):
                name = BASIC_COLOR_NAMES[cid - 1]
            return 1, [Target(320, 240, 0, 0, cid, name, min(100, raw[2]),
                              color=(raw[3], raw[4], raw[5]))]
        self.color_mode = 'learned'
        rc = min(head[2], head[1], 10)
        raw = self.read_register(_REG_RESULT, 3 + rc * 27) if rc else head
        if raw is None:
            return None

        def make(b, o, label):
            return Target(_u16(b, o + 3), _u16(b, o + 5), _u16(b, o + 7),
                          _u16(b, o + 9), _u16(b, o), label, min(100, b[o + 2]),
                          color=(b[o + 11], b[o + 12], b[o + 13]))
        return raw[1], self._walk(raw, rc, 3, 14, 12, make)

    def _parse_line(self):
        raw = self.read_register(_REG_RESULT, 20, retries=2)
        if raw is None:
            return None
        # Layout decoded from hardware dumps (examples/line_dump.py), origin
        # top-left: 2-5 one end (x, y), 6-9 other end (x, y), in either order,
        # 10-13 centre (x, y), 14 offset = centre x - 320, 16 angle (negative
        # when the far end is left of the near end), 18 length.
        self.line_detected = raw[0] != 0
        self.line_offset = _i16(raw, 14)
        self.line_angle = _i16(raw, 16)
        self.line_length = _u16(raw, 18)
        if not self.line_detected:
            self.line_near_end = self.line_far_end = self.line_center = (0, 0)
            return 0, []
        a = (_u16(raw, 2), _u16(raw, 4))
        b = (_u16(raw, 6), _u16(raw, 8))
        far, near = (a, b) if a[1] <= b[1] else (b, a)
        c = (_u16(raw, 10), _u16(raw, 12))
        half, h = SCREEN_WIDTH // 2, SCREEN_HEIGHT
        self.line_near_end = (near[0] - half, h - near[1])
        self.line_far_end = (far[0] - half, h - far[1])
        self.line_center = (c[0] - half, h - c[1])
        return 1, [Target(c[0], c[1], name='line')]

    def _parse_tracking(self):
        head = self.read_register(_REG_RESULT, 2, retries=2)
        if head is None:
            return None
        rc = min(head[1], 1)
        raw = self.read_register(_REG_RESULT, 2 + rc * 11) if rc else head
        if raw is None:
            return None
        if rc == 0:
            self.tracking_lost = False
            return 0, []
        self.tracking_lost = raw[4] != 0
        return 1, [Target(_u16(raw, 5), _u16(raw, 7), _u16(raw, 9), _u16(raw, 11),
                          0, 'tracking', min(100, raw[3]))]

    def _parse_ocr(self):
        raw = self._read_with_label(3, 2)
        if raw is None:
            return None
        text = _text(raw, 3, min(raw[2], len(raw) - 3))
        if raw[0] != 1 or not text:
            return 0, []
        return 1, [Target(name=text, confidence=min(100, raw[1]))]

    def _parse_code(self):
        raw = self._read_with_label(14, 12)
        if raw is None:
            return None
        text = _text(raw, 14, min(raw[12], len(raw) - 14))
        if not raw[0] or not text:
            return 0, []
        # id 1 = QR code, 2 = barcode. A decoded code is certain: confidence 100.
        return 1, [Target(id=raw[1], name=text, confidence=100)]

    _PARSERS = {
        FACE: _parse_face,
        SELF_LEARNING: _parse_self_learning,
        GESTURE: _parse_gesture,
        RHYTHM: _parse_rhythm,
        BALL: _parse_ball,
        OBJECT: _parse_object,
        OCR: _parse_ocr,
        LINE: _parse_line,
        TRACKING: _parse_tracking,
        EXPRESSION: _parse_expression,
        POSE: _parse_pose,
        COLOR: _parse_color,
        CARD: _parse_card,
        CODE: _parse_code,
    }
