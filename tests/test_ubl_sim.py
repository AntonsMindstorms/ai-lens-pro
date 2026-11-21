"""
Runs "microblocks/AI Lens Pro.ubl" in a small GP interpreter (gp_sim.py)
against the simulated AI Lens Pro from test_ailenspro.py.

Run with:  python3 tests/test_ubl_sim.py   (or pytest)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from gp_sim import Interp  # noqa: E402
from test_ailenspro import FakeLens, le16, al  # noqa: E402

UBL = os.path.join(HERE, '..', 'microblocks', 'AI Lens Pro.ubl')


def make(app=al.MAIN_MENU):
    dev = FakeLens(app)
    gp = Interp(UBL, dev)
    gp.call('AI Lens Pro init')
    assert gp.said == [], gp.said
    return dev, gp


def value(gp, prop, index=1):
    return gp.call('AI Lens Pro value', prop, index)


def info(gp, what):
    return gp.call('AI Lens Pro info', what)


def command(gp, what, *value):
    return gp.call('AI Lens Pro command', what, *value)


def test_init_with_lms_esp32_pins():
    dev = FakeLens()
    gp = Interp(UBL, dev)
    gp.call('AI Lens Pro init', 5, 4)
    assert gp.pins == (5, 4) and gp.freq == 100000 and gp.said == []
    assert info(gp, 'connected') is True


def test_init_not_found():
    dev = FakeLens()
    dev.present = False
    gp = Interp(UBL, dev)
    gp.call('AI Lens Pro init')
    assert gp.said and 'not found' in gp.said[0]
    assert info(gp, 'connected') is False


def test_switch_function_and_light():
    dev, gp = make()
    assert info(gp, 'function') == 'main menu'
    gp.call('AI Lens Pro switch to', 'card recognition')
    assert dev.app == al.CARD and dev.sent[-1] == (al.CARD, b'\x00')
    assert info(gp, 'function') == 'card recognition'
    gp.call('AI Lens Pro light', 80)
    assert dev.sent[-1] == (0x46, bytes([1, 80]))
    gp.call('AI Lens Pro light', 3)
    assert dev.sent[-1] == (0x46, bytes([1, 5]))
    gp.call('AI Lens Pro light', 0)
    assert dev.sent[-1] == (0x46, bytes([0, 0]))


def test_cards():
    dev, gp = make(al.CARD)
    dev.results[al.CARD] = bytes([2, 2]
                                 + [19, 90] + le16(100) + le16(200) + le16(40)
                                 + [3, 80] + le16(300) + le16(250) + le16(120))
    gp.call('AI Lens Pro update')
    assert gp.call('AI Lens Pro count') == 2
    assert value(gp, 'name', 1) == '3' and value(gp, 'name', 2) == 'stop'
    assert value(gp, 'x', 2) == 100 and value(gp, 'width', 1) == 120
    assert value(gp, 'confidence', 1) == 80
    assert info(gp, 'name') == '3' and info(gp, 'id') == 3 and info(gp, 'confidence') == 80
    assert gp.call('AI Lens Pro sees', 'STOP') is True
    assert gp.call('AI Lens Pro sees', 19) is True
    assert gp.call('AI Lens Pro sees', 'left') is False
    assert gp.call('AI Lens Pro sees', 'anything') is True
    assert gp.call('AI Lens Pro find', 'stop') == 2
    assert info(gp, 'closest to center') == 1
    assert value(gp, 'x', 'stop') == 100 and value(gp, 'name', 'Stop') == 'stop'
    assert value(gp, 'x', 'cat') == 0
    assert value(gp, 'name', 3) == '' and value(gp, 'x', 9) == 0
    assert dev.max_read <= 11


def test_balls():
    dev, gp = make(al.BALL)
    dev.results[al.BALL] = bytes([1, 0x80 | 1, 2, 77] + le16(320) + le16(240) + le16(50) + le16(52))
    gp.call('AI Lens Pro update')
    assert gp.call('AI Lens Pro sees', 'blue ball') is True
    assert gp.call('AI Lens Pro sees', 'red ball') is False
    assert [value(gp, p) for p in ('x', 'y', 'width', 'height', 'id', 'name', 'confidence')] == \
        [320, 240, 50, 52, 2, 'ball', 77]


def test_objects():
    dev, gp = make(al.OBJECT)
    a = [15, 88] + le16(100) + le16(110) + le16(30) + le16(40) + [3] + list(b'cat')
    b = [0, 95] + le16(400) + le16(200) + le16(100) + le16(300) + [6] + list(b'person')
    dev.results[al.OBJECT] = bytes([2, 2] + a + b)
    gp.call('AI Lens Pro update')
    assert value(gp, 'name', 1) == 'person' and value(gp, 'name', 2) == 'cat'
    assert value(gp, 'id', 2) == 15 and value(gp, 'height', 2) == 40
    assert gp.call('AI Lens Pro sees', 'Cat') is True


def test_face():
    dev, gp = make(al.FACE)
    dev.results[al.FACE] = bytes([1, 2, 93, 4, 1, 1] + le16(200) + le16(100) + le16(300) + le16(220)
                                 + [5] + list(b'Anton') + [1])
    gp.call('AI Lens Pro update')
    assert [value(gp, p) for p in ('x', 'y', 'width', 'height', 'id', 'name', 'confidence')] == \
        [250, 160, 100, 120, 2, 'Anton', 93]
    assert info(gp, 'blinks') == 4
    assert info(gp, 'mouth opens') == 1


def test_expressions():
    dev, gp = make(al.EXPRESSION)
    a = [0, 3, 70] + le16(320) + le16(200) + le16(80) + le16(90) + [0]
    b = [1, 4, 60] + le16(100) + le16(100) + le16(20) + le16(20) + [3] + list(b'Sad')
    dev.results[al.EXPRESSION] = bytes([2, 2] + a + b)
    gp.call('AI Lens Pro update')
    assert value(gp, 'name', 1) == 'happy' and value(gp, 'name', 2) == 'Sad'
    assert gp.call('AI Lens Pro sees', 'sad') is True


def test_pose():
    dev, gp = make(al.POSE)
    kp = []
    for k in range(17):
        kp += le16(0xFFFF if k == 0 else 100 + k) + le16(200 + k)
    rec = [1, 3, 80] + le16(320) + le16(240) + le16(200) + le16(400) + kp + [0]
    dev.results[al.POSE] = bytes([2, 1, 1, 1] + rec)
    gp.call('AI Lens Pro update')
    assert value(gp, 'name') == 'both hands up' and value(gp, 'id') == 3
    assert info(gp, 'name') == 'both hands up' and info(gp, 'confidence') == 80
    dev.results[al.POSE] = bytes([2, 1, 0, 0])
    gp.call('AI Lens Pro update')
    assert info(gp, 'name') == '' and info(gp, 'id') == -1 and info(gp, 'confidence') == 0
    dev.results[al.POSE] = bytes([2, 1, 1, 1] + rec)
    gp.call('AI Lens Pro update')
    assert value(gp, 'height') == 400
    assert gp.call('AI Lens Pro keypoint', 'x', 'nose') == -1
    assert gp.call('AI Lens Pro keypoint', 'x', 'left wrist') == 109
    assert gp.call('AI Lens Pro keypoint', 'y', 'right ankle') == 216


def test_color():
    dev, gp = make(al.COLOR)
    dev.results[al.COLOR] = bytes([1, 6, 90, 250, 240, 10, 0])
    gp.call('AI Lens Pro update')
    assert value(gp, 'name') == 'yellow' and value(gp, 'color') == 0xFAF00A
    rec = le16(7) + [60] + le16(100) + le16(120) + le16(30) + le16(40) + [1, 2, 3] + [4] + list(b'pink')
    dev.results[al.COLOR] = bytes([0, 1, 1] + rec)
    gp.call('AI Lens Pro update')
    assert value(gp, 'id') == 7 and value(gp, 'name') == 'pink' and value(gp, 'color') == 0x010203
    assert value(gp, 'width') == 30 and gp.call('AI Lens Pro sees', 7) is True
    command(gp, 'learned colors')
    assert dev.sent[-1] == (0x44, b'\x00')
    command(gp, 'basic colors')
    assert dev.sent[-1] == (0x44, b'\x01')


def test_line():
    dev, gp = make(al.LINE)
    dev.results[al.LINE] = bytes([1] + [0] * 13 + le16(-80) + le16(25) + [0, 0])
    gp.call('AI Lens Pro update')
    assert info(gp, 'line offset') == -80
    assert info(gp, 'line angle') == 25
    assert info(gp, 'line detected') is True
    assert info(gp, 'line direction') == 'right'
    assert value(gp, 'x') == 240
    dev.results[al.LINE] = bytes([1] + [0] * 13 + le16(10) + le16(-5) + [0, 0])
    gp.call('AI Lens Pro update')
    assert info(gp, 'line direction') == 'center' and value(gp, 'x') == 330
    dev.results[al.LINE] = bytes(20)
    gp.call('AI Lens Pro update')
    assert info(gp, 'line direction') == 'none'
    assert gp.call('AI Lens Pro count') == 0


def test_tracking():
    dev, gp = make(al.TRACKING)
    command(gp, 'start tracking')
    assert dev.sent[-1] == (0x47, bytes([1] + le16(220) + le16(140) + le16(420) + le16(340)))
    dev.results[al.TRACKING] = bytes([1, 1, 0, 66, 1] + le16(300) + le16(200) + le16(50) + le16(60))
    gp.call('AI Lens Pro update')
    assert info(gp, 'tracking lost') is True
    assert value(gp, 'x') == 300 and value(gp, 'height') == 60 and value(gp, 'confidence') == 66
    command(gp, 'stop tracking')
    assert dev.sent[-1] == (0x47, b'\x00')


def test_text_and_code():
    dev, gp = make(al.OCR)
    dev.results[al.OCR] = bytes([1, 85, 5] + list(b'HELLO'))
    gp.call('AI Lens Pro update')
    assert info(gp, 'text') == 'HELLO'
    gp.call('AI Lens Pro text region', 10, 20, 900, 900)
    assert dev.sent[-1] == (0x45, bytes([1] + le16(10) + le16(20) + le16(480) + le16(640)))
    command(gp, 'clear text region')
    assert dev.sent[-1] == (0x45, b'\x00')
    gp.call('AI Lens Pro switch to', 'QR and barcodes')
    dev.results[al.CODE] = bytes([1, 2] + [0] * 10 + [4, 0] + list(b'1234'))
    gp.call('AI Lens Pro update')
    assert info(gp, 'text') == '1234' and value(gp, 'id') == 2


def test_gesture_learning():
    dev, gp = make(al.GESTURE)
    dev.results[al.GESTURE] = bytes([1, 2, 70, 0] + le16(320) + le16(240) + le16(80) + le16(90) + [4] + list(b'okay'))
    gp.call('AI Lens Pro update')
    assert gp.call('AI Lens Pro sees', 'okay') is True and value(gp, 'height') == 90
    gp.call('AI Lens Pro switch to', 'self learning')
    dev.results[al.SELF_LEARNING] = bytes([1, 5, 99, 3] + list(b'cup'))
    gp.call('AI Lens Pro update')
    assert value(gp, 'name') == 'cup' and gp.call('AI Lens Pro sees', 5) is True
    command(gp, 'learn ID', 5)
    assert dev.sent[-1] == (0x48, bytes([1, 5]))
    command(gp, 'learn ID', 31)
    assert dev.sent[-1] == (0x48, bytes([1, 5]))  # ignored
    command(gp, 'learn ID')                       # collapsed block: ID 1
    assert dev.sent[-1] == (0x48, bytes([1, 1]))
    command(gp, 'forget ID')                      # collapsed block: forget all
    assert dev.sent[-1] == (0x48, bytes([2, 0]))
    command(gp, 'forget ID', 7)
    assert dev.sent[-1] == (0x48, bytes([2, 7]))


def test_rhythm():
    dev, gp = make(al.RHYTHM)
    t0 = gp.clock
    command(gp, 'record rhythm (s)', 3)
    assert dev.sent[-2:] == [(0x38, b'\x03'), (0x38, b'\x02')] and gp.clock - t0 >= 3000
    command(gp, 'analyse sound file', '/a.wav')
    assert dev.sent[-2] == (0x37, bytes([6]) + b'/a.wav') and dev.sent[-1] == (0x3A, b'\x01')
    dev.results[al.RHYTHM] = bytes([1] + le16(120) + le16(16) + le16(85))
    gp.call('AI Lens Pro update')
    assert info(gp, 'rhythm recognized') is True
    assert info(gp, 'bpm') == 120
    assert info(gp, 'beats') == 16
    assert info(gp, 'rhythm duration (ms)') == 8500


def test_menu_clears_and_failed_read_keeps():
    dev, gp = make(al.CARD)
    dev.results[al.CARD] = bytes([1, 1, 19, 90] + le16(1) + le16(2) + le16(3))
    gp.call('AI Lens Pro update')
    assert gp.call('AI Lens Pro sees', 'stop') is True
    dev.present = False
    gp.call('AI Lens Pro update')  # read fails: keep previous results
    assert gp.call('AI Lens Pro sees', 'stop') is True
    dev.present = True
    dev.app = al.CAMERA
    gp.call('AI Lens Pro update')
    assert gp.call('AI Lens Pro sees', 'anything') is False


def test_results_list_sorted():
    dev, gp = make(al.CARD)
    recs = []
    for cid, size in ((20, 10), (21, 50), (22, 30), (23, 50)):
        recs += [cid, 50] + le16(1) + le16(1) + le16(size)
    dev.results[al.CARD] = bytes([4, 4] + recs)
    gp.call('AI Lens Pro update')
    names = [r[5] for r in info(gp, 'all results')]
    assert names[2:] == ['mouse', 'cat'] and set(names[:2]) == {'dog', 'apple'}


def test_wifi():
    dev, gp = make()
    gp.call('AI Lens Pro connect WiFi', 'net', 'secret')
    assert gp.said == []
    payload = [p for c, p in dev.sent if c == 0x41][0]
    assert payload[1:] == bytes([3, 6]) + b'netsecret'
    assert info(gp, 'WiFi connected') is True
    assert dev.sent[-1][0] == 0x43


if __name__ == '__main__':
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print('ok    ', name)
            except Exception as e:  # noqa: BLE001
                failed += 1
                print('FAIL  ', name, type(e).__name__, e)
    print('\n%d failed' % failed if failed else '\nall tests passed')
    sys.exit(1 if failed else 0)
