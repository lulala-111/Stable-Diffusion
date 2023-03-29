# #!/bin/bash
#########################################################
# Uncomment and change the variables below to your need:#
#########################################################

# install metrics tool
sudo apt install nano
pip install aioprometheus[starlette]

# check the downloads, can take while on a fresh disk.
# perhaps better to use rsync? but want to avoid credentials
# do not run and subprocess because otherwsie several insttances may get launched due to restart attempts
cd /workspace/stable-diffusion-webui/models/Stable-diffusion/
python download.py
cd /workspace/stable-diffusion-webui/

# Install directory without trailing slash
install_dir="/workspace"

# Name of the subdirectory
#clone_dir="stable-diffusion-webui"

# Commandline arguments for webui.py, for example: export COMMANDLINE_ARGS="--medvram --opt-split-attention"
export COMMANDLINE_ARGS="--port 3000 --xformers --api --api-auth bashable:g46tTaGtrU3hAfmMbgNq --api-log --nowebui --ckpt /workspace/stable-diffusion-webui/models/Stable-diffusion/deliberate_v2.safetensors --listen --enable-insecure-extension-access"

# python3 executable
#python_cmd="python3"

# git executable
#export GIT="git"

# python3 venv without trailing slash (defaults to ${install_dir}/${clone_dir}/venv)
# venv_dir="/workspace/venv"

# script to launch to start the app
#export LAUNCH_SCRIPT="launch.py"

# install command for torch
#export TORCH_COMMAND="pip install torch==1.12.1+cu113 --extra-index-url https://download.pytorch.org/whl/cu113"

# Requirements file to use for stable-diffusion-webui
#export REQS_FILE="requirements_versions.txt"

# Fixed git repos
#export K_DIFFUSION_PACKAGE=""
#export GFPGAN_PACKAGE=""

# Fixed git commits
#export STABLE_DIFFUSION_COMMIT_HASH=""
#export TAMING_TRANSFORMERS_COMMIT_HASH=""
#export CODEFORMER_COMMIT_HASH=""
#export BLIP_COMMIT_HASH=""

# Uncomment to enable accelerated launch
#export ACCELERATE="True"

###########################################

