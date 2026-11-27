# Actual environment blocker, not a new approval request

Current trusted endpoint is sc01-ssh.gpuhome.cc:31454, ED25519 pin SHA256:u1vPsq3oZJFNIp4O3T2wFQLTXqBDLRhR8QmjJ9cw4VA. Strict checking remained on.

nvidia-smi returned Exec format error. A second read-only check found no /dev/nvidia* nodes. The original DROID-W Python environment reports PyTorch **2.1.0+cu118**, CUDA build **11.8**, **cuda_available=False**, **visible_device_count=0**. Merely seeing host driver files is not evidence that this container has a GPU.

/dev/shm is2GiB; data disk available11946180608bytes at this check. The original installed extension was found and SHA256 is **6dcf8de36cadc2174023b649b026f04e61b1231420d98763cc5aa3b294a91c3e**. No model was loaded, no CUDA kernel or SLAM experiment was launched, no extension was rebuilt/replaced. Only read-only resource/identity queries were made remotely.

The existing Task011B GPU authorization remains approved. No new per-arm approval is requested. The missing input is a reachable *GPU-enabled* instance/SSH command, already requested asynchronously. Do not reboot, remount devices, alter drivers, allocate another GPU or delete history to bypass this blocker. Recheck resources/identities on the actual card-enabled instance, then continue the already approved R2/R3 scope.
