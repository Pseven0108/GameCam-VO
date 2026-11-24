# Storage audit

The latest read-only audit measured 21,892,710,400 bytes (20.3892 GiB) free on the data filesystem. The mandatory floor remains 10 GiB. No native C0 was written.

The CPU fixture contains 9,237,037,052 unique logical storage bytes. It reuses 798 verified historical Tensor payload files (1,633,177,144 compressed bytes) by hard link and adds 51 fixture storage files (32,710,147 compressed bytes), plus 2,348,778 metadata bytes. Hard links are a private CPU-fixture reuse technique; native C0 may not bypass its saver or admission checks.

The original CPU snapshot retains all 800 files, and all 798 payload SHA values plus both metadata checks pass after the failure. The new fixture has 851 files (849 payloads plus two metadata files). Neither is a native C0.

Real C0 compressed size, fresh GPU arena peak, and full 487-frame continuation storage remain UNVERIFIED. Do not substitute the highly compressible synthetic CPU cache for real initialized geometry. An owned file-backed arena remains 2,246,400,000 bytes. Before real capture, preserve the floor while budgeting actual immutable C0 and one writable arena, using the existing exact lossless saver accounting. No historical cleanup was performed.
