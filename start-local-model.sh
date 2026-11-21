#!/usr/bin/env bash
# Start the tested Qwen model in Ubuntu/WSL for local development.
set -euo pipefail
cd -- "$(dirname -- "$0")"
backend=${1:-gpu}
case "$backend" in
  gpu|cpu) ;;
  *) echo "Usage: bash start-local-model.sh [gpu|cpu]" >&2; exit 2 ;;
esac
if [[ "$backend" == gpu && ! -e /dev/dxg && ! -e /dev/nvidia0 ]]; then
  echo "No NVIDIA device is visible to Linux. Check nvidia-smi, or use: bash start-local-model.sh cpu" >&2
  exit 1
fi

mkdir -p models
exec 9>models/.setup.lock
flock 9

fetch() {
  local file="$1" checksum="$2" url="$3"
  if [[ -f "$file" ]] && printf '%s  %s\n' "$checksum" "$file" | sha256sum --check --status; then
    return
  fi
  curl -fL --retry 2 "$url" -o "$file.part"
  printf '%s  %s\n' "$checksum" "$file.part" | sha256sum --check
  mv -- "$file.part" "$file"
}

release=https://github.com/ggml-org/llama.cpp/releases/download/b12603
unpack() {
  local name="$1" checksum="$2" dest="$3"
  if [[ -f "$dest/.ready-b12603" ]]; then return; fi
  fetch "models/$name" "$checksum" "$release/$name"
  mkdir -p "$dest"
  tar -xzf "models/$name" --strip-components=1 -C "$dest"
  touch "$dest/.ready-b12603"
}

bin="models/b12603-$backend"
layers=0
if [[ "$backend" == gpu ]]; then
  runtime="models/b12603-cuda-runtime"
  unpack "llama-b12603-bin-ubuntu-cuda-12.8-x64.tar.gz" 3d0691d514db955c1b8562dddf452da0bf9a8e7ca56e0694ebb7b3b9eeaf0ad7 "$bin"
  unpack "cudart-llama-b12603-bin-ubuntu-cuda-12.8-x64.tar.gz" ebfed8b1aaa2687b034dcc192f7a9adc41815223c5092144e54f2ec0a5e0d6eb "$runtime"
  export LD_LIBRARY_PATH="$PWD/$runtime:$PWD/$bin:/usr/lib/wsl/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  devices=$("$bin/llama-server" --list-devices 2>&1)
  printf '%s\n' "$devices"
  if [[ "$devices" != *CUDA0:* ]]; then
    echo "llama.cpp did not find a CUDA device. Check the NVIDIA Windows driver, or use: bash start-local-model.sh cpu" >&2
    exit 1
  fi
  layers=auto
else
  unpack "llama-b12603-bin-ubuntu-x64.tar.gz" 1bb44c7887cbef0bacdd17d6c074526e7e772fa6026459b1c05b9a5cc96396a8 "$bin"
fi
weights="https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/892322e1c0d25bf63f43c26df479b666d74e7a1b/Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
fetch models/qwen.gguf 3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597 "$weights"
flock -u 9
exec 9>&-
exec "$bin/llama-server" -m models/qwen.gguf --alias kio --host 127.0.0.1 --port 8080 \
  -ngl "$layers" -c 12288 -np 1 -t 8 --cache-ram 0 -ub 128
