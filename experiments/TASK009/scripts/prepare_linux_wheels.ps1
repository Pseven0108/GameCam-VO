$ErrorActionPreference='Stop'
$taskRoot='D:\aaa\GameCam-VO-TASK009'
$env:TEMP='D:\aaa\tmp\gamecam-vo'
$env:TMP=$env:TEMP
$env:PIP_CACHE_DIR='D:\aaa\caches\pip'
$taskWheels="$taskRoot\runtime\linux-wheels"
@('torch==2.7.1+cu128','torchvision==0.22.1+cu128','numpy==2.2.6') | Set-Content -LiteralPath "$taskRoot\runtime\linux-constraints.txt" -Encoding ascii
& 'D:\aaa\envs\gamecam-vo\python.exe' -B -m pip download --dest $taskWheels --find-links $taskWheels --constraint "$taskRoot\runtime\linux-constraints.txt" --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 --platform linux_x86_64 --python-version 3.10 --implementation cp --abi cp310 --only-binary=:all: opencv-python-headless==4.11.0.86 scikit-learn matplotlib tqdm PyYAML colorama tensorboard munch evo rich einops safetensors timm==1.0.24 huggingface-hub kornia ninja setuptools wheel
exit $LASTEXITCODE
