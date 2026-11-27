"""Forkserver CPU-only library preload; no model or GPU state inherited."""
import json
import os
from pathlib import Path
import torch
import cv2
import yaml
import torchvision
import lietorch
import droid_backends
import scipy.sparse
from scipy.spatial.transform import Rotation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot
from sklearn.decomposition import PCA
from torch.utils.tensorboard import SummaryWriter
import sys

if torch.cuda.is_initialized():
    raise RuntimeError('Forbidden: CUDA initialized in forkserver preload')
if 'torch_scatter' in sys.modules or 'src.depth_video' in sys.modules:
    raise RuntimeError('Native modules must be imported fresh after child installs original scatter compatibility')
STATUS={'CPU_libraries_preloaded':True,'server_pid':os.getpid(),'CUDA_initialized':False,
        'model_instantiated':False,'checkpoint_loaded':False,'torch':torch.__version__,
        'native_classes_preloaded':False,'scatter_compat_installed_in_fresh_child_only':True}
