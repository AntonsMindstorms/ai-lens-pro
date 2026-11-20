# LMS-ESP32 + AI Lens Pro, with 'line', 'card' and 'pose' commands for a
# Pybricks hub, over uRemote (https://github.com/AntonsMindstorms/uRemote).
# Copy uremote.py and ailenspro.py to the board and run this as main.py.
#
# The lens only switches function when the command needs another one than it
# is in now. A switch takes a few seconds; meanwhile the command returns its
# 'nothing seen' values right away (switch_to(..., wait=False) never blocks,
# so the hub does not time out waiting for a reply).
#
# Hub side (Pybricks), with the LMS-ESP32 on port A:
#
#   from uremote import uRemote
#   ur = uRemote('A')
#   detected, offset, angle = ur.line()
#   card_id, confidence = ur.card()
#   print(ur.pose())
#
# line: detected (0/1), offset of the line from the center of the screen
#   (-320 left .. 320 right) and its angle in degrees (negative = the line
#   bends left). All 0 when no line is seen.
# card: id and confidence (%) of the largest card. id is -1 when no card is
#   seen; 15 = forward, 16 = turn around, 17 = left, 18 = right.
# pose: the name of the pose the lens sees, such as 'Raise Hand', or -1.
from uremote import uRemote
from ailenspro import POSE, AILensPro, LINE, CARD

# Configure pins for your setup! 
AI_LENS_GREEN_WIRE = 2
AI_LENS_YELLOW_WIRE = 33
lens = AILensPro(scl=AI_LENS_GREEN_WIRE, sda=AI_LENS_YELLOW_WIRE) 

def line():
    if not lens.switch_to(LINE, wait=False) or lens.update() is None or not lens.line_detected:
        return 0, 0, 0
    return 1, lens.line_offset, lens.line_angle


def card():
    if not lens.switch_to(CARD, wait=False) or not lens.update():
        return -1, 0
    c = lens.results[0]             # largest card first
    return c.id, c.confidence

def pose():
    if not lens.switch_to(POSE, wait=False) or not lens.update():
        return -1
    p = lens.largest
    if p:
        return p.name
    return -1

ur = uRemote()

while True:
    ur.process()
