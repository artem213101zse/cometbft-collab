#!/bin/sh
# Однократно генерирует конфиги 4 нод (общий genesis, ключи валидаторов, peers)
set -e
if [ -f /build/node0/config/genesis.json ]; then echo "testnet already initialized"; exit 0; fi
cometbft testnet --v 4 --o /build --hostname-prefix node
for i in 0 1 2 3; do
  cfg=/build/node$i/config/config.toml
  sed -i "s#^proxy_app = .*#proxy_app = \"tcp://abci$i:26658\"#" $cfg
  sed -i 's#^laddr = "tcp://127.0.0.1:26657"#laddr = "tcp://0.0.0.0:26657"#' $cfg
  sed -i 's#^timeout_commit = .*#timeout_commit = "1s"#' $cfg
  sed -i 's#^addr_book_strict = .*#addr_book_strict = false#' $cfg
done
chmod -R 777 /build
echo "testnet initialized"
