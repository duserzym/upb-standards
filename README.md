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
