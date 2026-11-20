"""
Desktop tests for micropython/ailenspro.py, using a simulated AI Lens Pro.

Run with:  python3 tests/test_ailenspro.py   (or pytest)

The fake device implements the I2C protocol as used by the official
ELECFREAKS MakeCode extension: packets AA cmd len params crc8, register
reads with command 0x21 and app commands wrapped in command 0x30.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'micropython'))

import ailenspro as al  # noqa: E402


def le16(v):
    return list(struct.pack('<H', v & 0xFFFF))


class FakeLens:
    def __init__(self, app=al.MAIN_MENU):
        self.app = app
        self.results = {}       # app id -> bytes at register 100
        self.wifi = bytes(8)    # register 0x10
        self.sent = []          # (cmd, payload) of app commands
        self.pending = None
        self.reads = 0
        self.max_read = 0
        self.present = True
        self.switch_reads = 0   # app id reads before a switch takes effect
        self.switching = None   # (target app, reads left)

    # machine.I2C API -------------------------------------------------------
    def writeto(self, addr, buf):
        if not self.present or addr != 0x60:
            raise OSError(19)
        buf = bytes(buf)
        assert buf[0] == 0xAA, 'bad header'
        cmd, n = buf[1], buf[2]
        assert len(buf) == n + 4, 'bad length'
        assert al._crc8(buf, n + 3) == buf[n + 3], 'bad crc'
        params = buf[3:3 + n]
        if cmd == 0x21:
            reg = (params[0] << 8) | params[1]
            length = (params[2] << 8) | params[3]
            self.pending = (reg, length)
        elif cmd == 0x30:
            assert params[0] == 0 and params[1] == len(params) - 2
            frame = params[2:]
            assert frame[0] == 0xFF and frame[1] == 0xF9
            fcmd, flen = frame[2], frame[3]
            payload = bytes(frame[4:4 + flen])
            assert len(payload) == flen
            self.sent.append((fcmd, payload))
            if fcmd in al.APP_NAMES:
                if self.switch_reads:
                    self.switching = (fcmd, self.switch_reads)
                else:
                    self.app = fcmd
            if fcmd == 0x42:  # wifi status request -> mailbox with same seq
                self.wifi = bytes([0xA5, 1, 0x11, payload[0], 4, 0x07, 0, 0])
            if fcmd == 0x41:  # wifi connect -> receipt
                self.wifi = bytes([0xA5, 1, 0x12, payload[0], 1, 0x01, 0, 0])
        else:
            raise AssertionError('unexpected command 0x%02X' % cmd)

    def readfrom(self, addr, n):
        if not self.present:
            raise OSError(19)
        reg, length = self.pending
        assert n == length + 1
        self.reads += 1
        self.max_read = max(self.max_read, n)
        if reg < 0x10:
            if self.switching:
                target, left = self.switching
                self.switching = (target, left - 1) if left > 1 else None
                if left <= 1:
                    self.app = target
            mem = bytes([self.app]) + bytes(15)
            base = 0
        elif reg < 100:
            mem, base = self.wifi + bytes(64), 0x10
        else:
            mem, base = self.results.get(self.app, b'') + bytes(400), 100
        data = mem[reg - base:reg - base + length]
        return data + bytes([al._crc8(data, length)])


def make(app=al.MAIN_MENU, **kw):
    dev = FakeLens(app)
    return dev, al.AILensPro(i2c=dev, **kw)


# ------------------------------------------------------------------ tests
def test_crc_known_value():
    # CRC-8/SMBUS check value for "123456789" is 0xF4
    assert al._crc8(b'123456789', 9) == 0xF4


def test_switch_without_waiting():
    dev, lens = make(al.LINE)
    dev.switch_reads = 2
    dev.results[al.CARD] = bytes(2)
    lens.results = ['stale']
    assert not lens.switch_to(al.CARD, wait=False)
    assert dev.sent == [(al.CARD, b'\x00')]
    assert not lens.switch_to(al.CARD, wait=False)      # asked once, not again
    assert len(dev.sent) == 1
    assert lens.switch_to(al.CARD, wait=False)          # lens got there
    assert lens.app == al.CARD and lens.results == []
    assert lens.switch_to(al.CARD, wait=False) and len(dev.sent) == 1


def test_not_found_raises():
    dev = FakeLens()
    dev.present = False
    try:
        al.AILensPro(i2c=dev, timeout_ms=50)
    except OSError:
        return
    raise AssertionError('expected OSError')


def test_switch_and_app_name():
    dev, lens = make()
    assert lens.app_name == 'main menu'
    assert lens.switch_to(al.CARD)
    assert dev.app == al.CARD and dev.sent[-1] == (al.CARD, b'\x00')
    assert lens.switch_to('Face Recognition')
    assert dev.app == al.FACE


def test_light():
    dev, lens = make()
    lens.light(True, 150)
    assert dev.sent[-1] == (0x46, bytes([1, 100]))
    lens.light(True, 1)
    assert dev.sent[-1] == (0x46, bytes([1, 5]))
    lens.light(False)
    assert dev.sent[-1] == (0x46, bytes([0, 0]))


def test_cards_sorted_largest_first_and_chunked():
    dev, lens = make(al.CARD)
    recs = [
        [19, 90] + le16(100) + le16(200) + le16(40),   # stop, small
        [3, 80] + le16(300) + le16(250) + le16(120),   # '3', large
    ]
    dev.results[al.CARD] = bytes([2, 2] + recs[0] + recs[1])
    res = lens.update()
    assert lens.count == 2
    assert [t.name for t in res] == ['3', 'stop']
    assert res[0].width == res[0].height == 120
    assert lens.sees('stop') and lens.sees(19) and lens.sees('3') and lens.sees(3)
    assert not lens.sees('left')
    assert lens.find('STOP').x == 100
    assert lens.closest.name == '3'
    assert dev.max_read <= 11  # 10-byte chunks + crc


def test_ball():
    dev, lens = make(al.BALL)
    rec = [1, 77] + le16(320) + le16(240) + le16(50) + le16(52)
    dev.results[al.BALL] = bytes([1, 0x40 | 1] + rec)
    lens.update()
    assert lens.sees('red ball') and not lens.sees('blue ball')
    t = lens.largest
    assert (t.x, t.y, t.width, t.height, t.confidence) == (320, 240, 50, 52, 77)


def test_objects_with_labels():
    dev, lens = make(al.OBJECT)
    a = [15, 88] + le16(100) + le16(110) + le16(30) + le16(40) + [3] + list(b'cat')
    b = [0, 95] + le16(400) + le16(200) + le16(100) + le16(300) + [0]  # no label
    dev.results[al.OBJECT] = bytes([2, 2] + a + b)
    res = lens.update()
    assert [t.name for t in res] == ['person', 'cat']
    assert res[1].confidence == 88 and res[1].id == 15


def test_face_learned():
    dev, lens = make(al.FACE)
    raw = [1, 2, 93, 4, 1, 1] + le16(200) + le16(100) + le16(300) + le16(220) + [5] + list(b'Anton') + [1]
    dev.results[al.FACE] = bytes(raw)
    lens.update()
    t = lens.largest
    assert (t.x, t.y, t.width, t.height) == (250, 160, 100, 120)
    assert t.name == 'Anton' and t.id == 2 and t.confidence == 93
    assert lens.blinks == 4 and lens.mouth_opens == 1 and lens.count == 1


def test_face_unknown():
    dev, lens = make(al.FACE)
    raw = [0, 0xFF, 10, 0, 0, 1] + le16(10) + le16(10) + le16(50) + le16(70) + [0] + [2]
    dev.results[al.FACE] = bytes(raw)
    lens.update()
    assert lens.count == 2 and lens.largest.name == '' and lens.largest.id == 0


def test_expression():
    dev, lens = make(al.EXPRESSION)
    rec = [0, 3, 70] + le16(320) + le16(200) + le16(80) + le16(90) + [5] + list(b'Happy')
    dev.results[al.EXPRESSION] = bytes([1, 1] + rec)
    lens.update()
    assert lens.sees('happy') and lens.largest.width == 80 and lens.largest.name == 'Happy'
    assert lens.largest.height == 90 and lens.largest.id == 3


def test_pose_keypoints():
    dev, lens = make(al.POSE)
    kp = []
    for k in range(17):
        kp += le16(0xFFFF if k == 0 else 100 + k) + le16(200 + k)
    rec = [1, 2, 80] + le16(320) + le16(240) + le16(200) + le16(400) + kp + [7] + list(b'hand up')
    assert len(rec) == 80 + 7
    dev.results[al.POSE] = bytes([2, 1, 1, 1] + rec)
    lens.update()
    t = lens.largest
    assert t.name == 'hand up' and t.id == 2
    assert t.keypoint('nose') is None
    assert t.keypoint('left wrist') == (109, 209)


def test_color_basic_and_learned():
    dev, lens = make(al.COLOR)
    dev.results[al.COLOR] = bytes([1, 1, 90, 200, 10, 20, 0])
    lens.update()
    assert lens.color_mode == 'basic' and lens.sees('red')
    assert lens.largest.color == (200, 10, 20)

    rec = le16(7) + [60] + le16(100) + le16(120) + le16(30) + le16(40) + [1, 2, 3] + [4] + list(b'pink')
    dev.results[al.COLOR] = bytes([0, 1, 1] + rec)
    lens.update()
    assert lens.color_mode == 'learned'
    assert lens.sees(7) and lens.sees('pink') and lens.largest.color == (1, 2, 3)

    lens.set_color_mode('learned')
    assert dev.sent[-1] == (0x44, b'\x00')


def test_line():
    dev, lens = make(al.LINE)
    raw = [1] + [0] * 13 + le16(-80) + le16(-15) + [0, 0]
    dev.results[al.LINE] = bytes(raw)
    lens.update()
    assert lens.line_detected and lens.line_offset == -80 and lens.line_angle == -15
    assert lens.line_direction(10) == 'left' and lens.line_direction(20) == 'center'
    # not reported by the lens: not detected means no target, no target point
    dev.results[al.LINE] = bytes(20)
    lens.update()
    assert not lens.line_detected and lens.line_near_end == (0, 0)


def line_row(text):
    return bytes(int(v) for v in text.split())


def test_line_ends_from_hardware_dump():
    # Real rows captured with examples/line_dump.py, checked against photos
    # of the lens screen. Reported with the origin at the bottom centre.
    dev, lens = make(al.LINE)
    # vertical line on the left
    dev.results[al.LINE] = line_row('1 0 114 0 1 0 122 0 222 1 118 0 239 0 54 255 0 0 221 1')
    lens.update()
    assert lens.line_offset == -202 and lens.line_angle == 0 and lens.line_length == 477
    assert lens.line_far_end == (-206, 479) and lens.line_near_end == (-198, 2)
    assert lens.line_center == (-202, 241)
    assert (lens.results[0].x, lens.results[0].y) == (118, 239)   # screen coordinates
    # diagonal from top left to bottom right
    dev.results[al.LINE] = line_row('1 0 56 0 1 0 92 2 222 1 74 1 239 0 10 0 208 255 214 2')
    lens.update()
    assert lens.line_angle == -48 and lens.line_length == 726
    assert lens.line_far_end == (-264, 479) and lens.line_near_end == (284, 2)
    # ends reported near end first: sorting by y puts them right
    dev.results[al.LINE] = line_row('1 0 9 0 222 1 229 1 1 0 247 0 239 0 183 255 44 0 161 2')
    lens.update()
    assert lens.line_far_end == (165, 479) and lens.line_near_end == (-311, 2)
    # leaves through the left edge, never reaching the bottom
    dev.results[al.LINE] = line_row('1 1 1 0 16 1 126 2 41 0 63 1 156 0 255 255 70 0 165 2')
    lens.update()
    assert lens.line_far_end == (318, 439) and lens.line_near_end == (-319, 208)
    assert lens.line_center == (-1, 324)


def test_tracking():
    dev, lens = make(al.TRACKING)
    lens.start_tracking(0, 0, 700, 500)
    assert dev.sent[-1] == (0x47, bytes([1] + le16(0) + le16(0) + le16(640) + le16(480)))
    dev.results[al.TRACKING] = bytes([1, 1, 0, 66, 1] + le16(300) + le16(200) + le16(50) + le16(60))
    lens.update()
    assert lens.tracking_lost and lens.largest.x == 300 and lens.largest.confidence == 66


def test_ocr_and_code():
    dev, lens = make(al.OCR)
    dev.results[al.OCR] = bytes([1, 85, 5] + list(b'HELLO'))
    lens.update()
    assert lens.text == 'HELLO' and lens.largest.confidence == 85
    lens.switch_to(al.CODE)
    dev.results[al.CODE] = bytes([1, 1] + [0] * 10 + [11, 0] + list(b'microblocks'))
    lens.update()
    assert lens.text == 'microblocks' and lens.largest.id == 1


def test_gesture_and_self_learning():
    dev, lens = make(al.GESTURE)
    dev.results[al.GESTURE] = bytes([1, 2, 70, 0] + le16(320) + le16(240) + le16(80) + le16(90) + [4] + list(b'okay'))
    lens.update()
    assert lens.sees('okay') and lens.largest.width == 80
    lens.switch_to(al.SELF_LEARNING)
    dev.results[al.SELF_LEARNING] = bytes([1, 5, 99, 0])
    lens.update()
    assert lens.sees(5) and lens.largest.confidence == 99
    lens.learn(5)
    assert dev.sent[-1] == (0x48, bytes([1, 5]))
    lens.forget()
    assert dev.sent[-1] == (0x48, bytes([2, 0]))


def test_rhythm():
    dev, lens = make(al.RHYTHM)
    dev.results[al.RHYTHM] = bytes([1] + le16(120) + le16(16) + le16(85))
    lens.update()
    assert lens.rhythm_recognized and lens.bpm == 120 and lens.beats == 16
    assert lens.rhythm_duration_ms == 8500
    lens.analyse_audio_file('/a.wav')
    assert dev.sent[-2] == (0x37, bytes([6]) + b'/a.wav') and dev.sent[-1] == (0x3A, b'\x01')


def test_menu_clears_results():
    dev, lens = make(al.CARD)
    dev.results[al.CARD] = bytes([1, 1, 19, 90] + le16(1) + le16(2) + le16(3))
    lens.update()
    assert lens.sees('stop')
    dev.app = al.CAMERA
    lens.update()
    assert lens.results == [] and not lens.sees()


def test_wifi():
    dev, lens = make()
    assert lens.connect_wifi('net', 'secret', timeout_ms=2000)
    fcmd, payload = [s for s in dev.sent if s[0] == 0x41][0]
    assert payload[1:] == bytes([3, 6]) + b'netsecret'
    assert lens.wifi_connected()
    assert dev.sent[-1][0] == 0x43  # mailbox acknowledged


if __name__ == '__main__':
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print('ok    ', name)
            except Exception as e:  # noqa: BLE001
                failed += 1
                print('FAIL  ', name, repr(e))
    print('\n%d failed' % failed if failed else '\nall tests passed')
    sys.exit(1 if failed else 0)
