# LMS-ESP32 + AI Lens Pro, with 'line' and 'card' commands for a LEGO hub,
# over PUPRemote (https://github.com/antonvh/PUPRemote).
#
# The lens only switches function when the command needs another one than it
# is in now. A switch takes a few seconds; meanwhile the command returns its
# 'nothing seen' values right away (switch_to(..., wait=False) never blocks,
# so the heartbeat to the hub keeps running).
#
# Hub side (Pybricks), with the LMS-ESP32 on port A:
#
#   from pupremote_hub import PUPRemoteHub
#   pr = PUPRemoteHub('A')
#   pr.add_command('line', 'bhh')
#   pr.add_command('card', 'bb')
#   detected, offset, angle = pr.call('line')
#   card_id, confidence = pr.call('card')
#
# line: detected (0/1), offset of the line from the center of the screen
#   (-320 left .. 320 right) and its angle in degrees (negative = the line
#   bends left). All 0 when no line is seen.
# card: id and confidence (%) of the largest card. id is -1 when no card is
#   seen; 15 = forward, 16 = turn around, 17 = left, 18 = right.
from pupremote import PUPRemoteSensor
from ailenspro import POSE, AILensPro, LINE, CARD

# Configure pins for your setup! 
AI_LENS_GREEN_WIRE = 2
AI_LENS_YELLOW_WIRE = 33
lens = AILensPro(scl=AI_LENS_GREEN_WIRE, sda=AI_LENS_YELLOW_WIRE) 


def line():
    if not lens.switch_to(LINE, wait=False) or lens.update() is None or not lens.line_detected:
        return 0, 0, 0
    near, far = lens.line_near_end, lens.line_far_end
    return 1, lens.line_offset, lens.line_angle


def card():
    if not lens.switch_to(CARD, wait=False) or not lens.update():
        return -1, 0
    c = lens.results[0]             # largest card first
    return c.id, c.confidence


pr = PUPRemoteSensor(power=True)
pr.add_command('line', 'bhh')
pr.add_command('card', 'bb')

while True:
    pr.process()
