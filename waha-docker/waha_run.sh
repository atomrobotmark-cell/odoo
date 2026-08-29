#!/bin/bash
# Launch WAHA (GOWS engine) and create the default session.
set -e
IMG=waha-gows:local
docker rm -f waha 2>/dev/null || true
docker run -d --name waha --restart unless-stopped -p 3000:3000 \
  -e WHATSAPP_DEFAULT_ENGINE=gows \
  -e HTTP_PROXY=http://192.168.140.175:10809 \
  -e HTTPS_PROXY=http://192.168.140.175:10809 \
  -e ALL_PROXY=socks5://192.168.140.175:10808 \
  -e NO_PROXY=localhost,127.0.0.1 \
  "$IMG"
echo "[waha] container started, waiting for API..."
for i in $(seq 1 40); do
  if curl -s -m 3 http://127.0.0.1:3000/api/version >/dev/null 2>&1; then echo "[waha] API up"; break; fi
  sleep 2
done
echo "[waha] creating default (gows) session..."
curl -s -X POST http://127.0.0.1:3000/api/sessions/ -H "Content-Type: application/json" -d "{\"name\":\"default\",\"start\":true}"
echo
sleep 4
echo "[waha] session state:"
curl -s http://127.0.0.1:3000/api/sessions/default
echo
