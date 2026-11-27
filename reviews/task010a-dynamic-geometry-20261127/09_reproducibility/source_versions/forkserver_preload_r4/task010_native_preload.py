"""Forkserver CPU-only library preload; no model or GPU state inherited."""
import json
import os
from pathlib import Path
import torch
import cv2
import yaml
from gamecam.compat.torch_scatter_python import install
install()
from src.utils.Printer import TrivialPrinter
from src.modules.droid_net import DroidNet
from src.depth_video import DepthVideo
from src.frontend import Frontend
from src.backend import Backend
from src.trajectory_filler import PoseTrajectoryFiller
from torch.utils.tensorboard import SummaryWriter

if torch.cuda.is_initialized():
    raise RuntimeError('Forbidden: CUDA initialized in forkserver preload')
STATUS={'CPU_libraries_preloaded':True,'server_pid':os.getpid(),'CUDA_initialized':False,
        'model_instantiated':False,'checkpoint_loaded':False,'torch':torch.__version__}
