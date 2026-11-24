# Next minimal repair scope

The new blocker is the exact installed `timm.layers.format:Format` from timm 0.9.10. Its source SHA-256 is `8b4d8d2d76d65cfbf8589092505e0c9d28d0a7af7df941abe59deb9cc664dfae`. It subclasses `str, Enum`; the live value is `Format.NHWC`. This type existed in the previous historical object graph and is independent of all ConfigDict nodes.

A future explicitly approved adapter should pin the exact class, version and source SHA; encode member name and value; restore the original installed enum member; preserve object memo and singleton identity; reject unknown subclasses and inconsistent name/value pairs. Test all four members, aliases, mapping values/keys, cycles through parent objects, identity-based spatial/channel helpers, incorrect pins and unsupported classes. Do not convert it to an ordinary string or create a replacement non-singleton member.

This task did not implement the enum adapter. ConfigDict corrections consumed remain 1/2; the unused ConfigDict round is not a general adapter budget. Full real-model fresh-process output and gradient hashes must pass after the new type is supported. More unsupported states may still be exposed; this report does not claim Format is the last blocker.

Before sealing C0, finish and CPU-test the already authorized stage-qualified restore19/short80/formal487 continuation. Current restore_check only loads; existing several RGB080 guards, a tracker loop cap, missing formal entry and filler stream handling are pending. Keep the original algorithm and all approval/floor/state checks. No GPU launch is allowed until the complete CPU gate succeeds.
