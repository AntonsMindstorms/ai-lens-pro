# Pose recognition: print the pose and where the wrists are.
import time
from ailenspro import AILensPro, POSE

lens = AILensPro(scl=2,sda=33)
lens.switch_to(POSE)

while True:
    lens.update()
    person = lens.largest
    if person:
        print(person.name, '| left wrist', person.keypoint('left wrist'),
              '| right wrist', person.keypoint('right wrist'))
        if person.name == 'Both Hands Up':
            print('Hooray!')
    time.sleep_ms(200)
