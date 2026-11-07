# UPb standards

Reference-material data for U–Pb and trace-element reduction. The initial
library is the format-2 TOML library from UPbRPy. Each material file records
source quantities and links to citations in `sources.toml`.

Point UPbRPy at this directory or its `library.toml`. Use a fixed Git revision
when reproducing a reduction. Keep isotope systems, initial Pb, radiogenic
ratios, total ratios, and uncertainty conventions distinct. Add documented
source quantities and list new records in `library.toml`.

The older UPbRPy wide CSV is a separate compatibility archive. This repository
contains the curated TOML records.

## Desktop checks

Keep an authenticated clone at `~/UPbRPy/upb-standards` for both desktop
apps. Set `UPB_STANDARDS_DIR` before launching an app to use another clone.
Git must be on the app's path. Use your Git credential helper for access
to this private repository.

In Updates, **Check standards** compares the checkout's TOML files with
GitHub main and lists differences. It fetches Git metadata for comparison.
If GitHub is unavailable, it uses the last checked revision when available.
In Studio, choose **File → Reference Material Library** and select
`library.toml` to adopt a reviewed library explicitly. Record the Git
revision and the library digest when archiving a reduction.
