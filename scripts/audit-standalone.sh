#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

runtime_files="index.html booth.html manifesto/index.html architecture/index.html review/index.html review/review.js styles.css script.js scene.js booth.js booth-config.js"

echo "Checking runtime files for external network references..."
if grep -RInE 'https?://|//[A-Za-z0-9.-]+|@import|<iframe|<img[^>]+src="https?:|XMLHttpRequest|navigator\.sendBeacon' $runtime_files; then
  echo "External runtime dependency found. Zone Trip must remain standalone." >&2
  exit 1
fi

echo "Checking required local files..."
test -f index.html
test -f booth.html
test -f manifesto/index.html
test -f architecture/index.html
test -f review/index.html
test -f review/review.js
test -f styles.css
test -f script.js
test -f scene.js
test -f booth.js
test -f booth-config.js
test -f favicon.svg
test -f CNAME
grep -qx 'zonetrip.castalia.institute' CNAME
test -f HARDWARE.md
test -f PROCESSOR.md
test -f charter.md
test -f model.md
test -f docs/Zone_Trip_White_Paper_First_Review.pdf
test -f assets/stage-microphone-mobile.jpg
test -f assets/stage-microphone-desktop.jpg
test -f assets/stage-mirror-mobile.png
test -f assets/stage-mirror-desktop.png
test -f assets/microphone-overlay.png
test -f assets/mirror-mask.svg
test -f vendor/three/three.module.js
test -f vendor/three/LICENSE
test -f services/processor/app.py
test -f services/processor/epistemic.py
test -f services/processor/charter.md
cmp -s charter.md services/processor/charter.md
test -f services/processor/requirements.txt
test -f services/processor/Dockerfile
test -f services/processor/start.sh
test -f deploy/systemd/zonetrip-processor.service
test -x scripts/install-local-ai.sh
test -x scripts/deploy-cloud-run-processor.sh
test -x bin/zonetrip-serve
test -x bin/zonetrip-capture-once
test -x bin/zonetrip-review-day

echo "Standalone audit passed."
