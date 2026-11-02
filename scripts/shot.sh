#!/bin/zsh
# Screenshot the simulator to <out>.png at 460x1000 (the coordinate space step.sh uses).
D=${TUT_DEVICE:-C9D73B92-B6E5-4CE1-BCBD-56503E21E226}
xcrun simctl io $D screenshot $1.png >/dev/null 2>&1 && sips -Z 1000 $1.png >/dev/null && echo $1.png
