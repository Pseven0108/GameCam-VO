# Actual IPC call graph

`native_child_v2 -> IPCPolicy.install_arena -> _native_runtime -> DepthVideo.__init__ -> multiprocessing.Value -> sharedctypes.Value/RawValue -> BufferWrapper -> Heap.malloc -> Arena -> tempfile.mkstemp -> os.unlink -> mmap`

The bounded adapter invokes Tracking directly. It does not execute upstream run.py or SLAM.run, which set spawn. The actual default here is fork; both fork and spawn were exercised by real CPU tests.

Required in the current mapping=false path: DepthVideo.counter Value and its synchronization lock. Upstream Printer Lock/Queue/Value is replaced by the bounded printer. SLAM.run Event/Pipe/optional visualization queues, Mapper Lock, and example visualization Queue are outside this bounded run. CUDA timing Event calls are not multiprocessing IPC. No SharedMemory API call was found in the bounded native path.

Full source hits:

- `baselines/droid_w/prior_sources/FiT3D/train_feat_gaussian.py:54`: `iter_start = torch.cuda.Event(enable_timing = True)`
- `baselines/droid_w/prior_sources/FiT3D/train_feat_gaussian.py:55`: `iter_end = torch.cuda.Event(enable_timing = True)`
- `baselines/droid_w/upstream/run.py:32`: `torch.multiprocessing.set_start_method('spawn')`
- `baselines/droid_w/upstream/src/depth_video.py:34`: `self.counter = Value('i', 0) # current keyframe count`
- `baselines/droid_w/upstream/src/mapper.py:289`: `with Lock():`
- `baselines/droid_w/upstream/src/slam.py:279`: `mp.set_start_method("spawn", force=True)`
- `baselines/droid_w/upstream/src/slam.py:280`: `exit_event = mp.Event()`
- `baselines/droid_w/upstream/src/slam.py:282`: `m_pipe, t_pipe = mp.Pipe()`
- `baselines/droid_w/upstream/src/slam.py:284`: `q_main2vis = mp.Queue() if self.cfg['gui'] else None`
- `baselines/droid_w/upstream/src/slam.py:285`: `q_vis2main = mp.Queue() if self.cfg['gui'] else None`
- `baselines/droid_w/upstream/src/utils/Printer.py:46`: `self.msg_lock = mp.Lock()`
- `baselines/droid_w/upstream/src/utils/Printer.py:47`: `self.msg_queue = mp.Queue()`
- `baselines/droid_w/upstream/src/utils/Printer.py:48`: `self.progress_counter = mp.Value('i', 0)`
- `baselines/droid_w/upstream/src/utils/cuda_timer.py:9`: `self.start = torch.cuda.Event(enable_timing=True)`
- `baselines/droid_w/upstream/src/utils/cuda_timer.py:10`: `self.end = torch.cuda.Event(enable_timing=True)`
- `baselines/droid_w/upstream/thirdparty/lietorch/examples/rgbdslam/viz.py:136`: `self.queue = Queue()`

Arena unlinks its named file after opening it; mmap and the fd can remain in the allocator cache until interpreter exit. Unlink is not a claim that the mapping vanished immediately. Native semaphores are covered by normal fork/spawn lifecycle checks, not a global Python-audit mediation claim.
