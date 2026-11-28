# Common local memory allocator setting

Moving-window BASE_002 initialized, then hit CUDA OOM in the native correlation
pyramid's factor-removal copy. At failure PyTorch reported 3.32GiB allocated,
2.26GiB reserved but unallocated, and a 1.26GiB pending contiguous allocation.
No complete trajectory or comparison score was produced.

Set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True for every subsequent local
arm. This changes allocation management, without changing image size, neural
weights, graph limits, mathematical expressions, seed or optimization settings.
Preserve BASE_002 and start BASE_003 in a fresh process. This is a bounded local
engineering retry, not a remote formal-run restart. No other application is
terminated to make room.
