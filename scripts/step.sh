#!/bin/zsh
# Record ONE tutorial step as its own short clip (avoids simctl long-recording time drift).
# usage: step.sh <workdir> <name> tap X Y
#        step.sh <workdir> <name> type "text"
#        step.sh <workdir> <name> swipe X1 Y1 X2 Y2
#        step.sh <workdir> <name> key Enter   (then edit steps.txt to name|key|Enter|X|Y| to draw a ring on the key)
#        (no "wait" steps: simctl only writes frames on change, so a static clip is empty)
# Coords are in a 460x1000 screenshot space (what shot.sh produces). Simulator: iPhone 17, 402x874 pt.
W=$1; N=$2; shift 2
D=${TUT_DEVICE:-C9D73B92-B6E5-4CE1-BCBD-56503E21E226}   # iPhone 17
mkdir -p $W/clips $W/flows
echo '{"sw":460,"sh":1000}' > $W/layout.json
f=$W/flows/$N.yaml; printf 'appId: %s\n---\n' ${TUT_APP:-com.apple.mobilesafari} > $f   # TUT_APP = bundle id for a native app
case $1 in
  tap)   printf -- '- tapOn:\n    point: "%s,%s"\n' $(( $2*402/460 )) $(( $3*402/460 )) >> $f;;
  type)  printf -- '- inputText: "%s"\n' "$2" >> $f;;
  swipe) printf -- '- swipe:\n    start: "%s,%s"\n    end: "%s,%s"\n    duration: 900\n' $(( $2*402/460 )) $(( $3*402/460 )) $(( $4*402/460 )) $(( $5*402/460 )) >> $f;;
  key)   printf -- '- pressKey: %s\n' "$2" >> $f;;      # e.g. key Enter
  wait)  ;;
  *) echo "unknown action $1"; exit 2;;
esac
xcrun simctl io $D recordVideo --codec=h264 --force $W/clips/$N.mp4 >/dev/null 2>&1 &
RP=$!; sleep 2.5
if [[ $1 == wait ]]; then sleep $2; else
  ~/.maestro/bin/maestro --device $D test $f 2>&1 | grep -oE "(Tap on point|Input text|Swipe|Press).*(COMPLETED|FAILED)|Exception.*" | head -2
fi
sleep 2.5; kill -INT $RP; wait $RP 2>/dev/null
ffmpeg -v error -y -i $W/clips/$N.mp4 -vf "fps=30,scale=720:1566:flags=lanczos" -c:v libx264 -crf 18 -preset fast -g 15 -pix_fmt yuv420p -an $W/clips/$N-cfr.mp4 && rm $W/clips/$N.mp4
# replace any earlier take of this step
grep -v "^$N|" $W/steps.txt > $W/steps.tmp 2>/dev/null; mv $W/steps.tmp $W/steps.txt 2>/dev/null
echo "$N|$1|$2|$3|$4|$5" >> $W/steps.txt
echo "recorded $N ($(ffprobe -v error -show_entries format=duration -of csv=p=0 $W/clips/$N-cfr.mp4)s)"
