#!/usr/bin/env bash
# Fetch only the Franka Panda model from MuJoCo Menagerie (Apache-2.0) into third_party/.
set -e; cd "$(dirname "$0")/.."
[ -f third_party/mujoco_menagerie/franka_emika_panda/panda_nohand.xml ] && { echo "menagerie already present"; exit 0; }
mkdir -p third_party
git clone --depth 1 --filter=blob:none --sparse https://github.com/google-deepmind/mujoco_menagerie third_party/mujoco_menagerie
git -C third_party/mujoco_menagerie sparse-checkout set franka_emika_panda
echo "ok: third_party/mujoco_menagerie/franka_emika_panda"
