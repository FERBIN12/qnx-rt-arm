#!/usr/bin/env bash
# Boot the mkqnximage QNX 8.0 x86_64 image under QEMU/KVM with user-mode networking
# (no root/bridge needed). Guest sees the host as 10.0.2.2; host ssh -> guest via localhost:2222.
set -euo pipefail
cd "$(dirname "$0")/../vm"
exec qemu-system-x86_64 -enable-kvm -cpu host -smp 2 -m 1G \
  -kernel output/ifs.bin -drive file=output/disk-qemu.vmdk,if=ide,id=drv0 \
  -netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22 -device virtio-net-pci,netdev=net0 \
  -object rng-random,filename=/dev/urandom,id=rng0 -device virtio-rng-pci,rng=rng0 \
  -serial file:qemu-serial.log -monitor none -display none
