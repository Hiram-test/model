# Complete archive delivery recovery

The scientific calculations and frozen results are bound to commit `05aca702bc0f8cf308d6cf9ddefc9caaf0567c10`. This addition changes packaging only.

The original archive execution channel reported exit 120 while the filesystem reported no available space. Ten archive pieces were independently sealed and saved. The next incomplete piece is retained byte for byte. No cause is inferred from these observations.

`complex_archive_recover_delivery.py` is an explicitly scoped, single-use recovery script. It verifies the exact ordered prefix and source SHA-256 identities; writes remaining evidence to a separate directory with exclusive creation; watches the original output for further activity; verifies every completed ZIP and member; and checks exact total coverage. It refuses an unsafe restart over an existing recovery directory. Its recorded paths and ten-part prefix are specific to this delivery.

The finite memory check includes clean filesystem cache. During this delivery, clean cached reads of the declared source files were released with read-only `POSIX_FADV_DONTNEED`; no file contents changed. No scientific training, tuning, or testing was repeated as part of packaging recovery.

The final download index carries the archive completion and upload receipts separately from the scientific qualification gates. Complete delivery does not change any accuracy, physical-consistency, or reference-fidelity HOLD.
