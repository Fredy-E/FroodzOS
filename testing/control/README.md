# Historical control-media helpers

**Archive only. These are not current USB preparation instructions.**

Several scripts in this directory were used in early control experiments and
can format a selected disk, write raw physical media or change files on a USB.
They retain historical target/model/path assumptions. Do not run them against
an arbitrary disk or use their old authorization comments as new permission.

The currently accepted workflow preserves the existing USB partition table,
filesystem and recovery images and uses separately approved, identity-checked,
backed-up, flushed and independently read-back-verified **file-only** changes.
Physical boots are owner-executed. See [current status](../../docs/STATUS.md).
No formatting, raw write or hardware boot is performed by source verification.
