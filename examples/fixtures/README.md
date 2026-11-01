# Synthetic inputs for route dry-runs

All values and labels in this directory are synthetic. These small files give reviewers a real existing-code or existing-figure input without requiring private research data.

| File | Purpose |
|---|---|
| `existing_forest.R` | Existing ggplot2 code using accepted estimates and confidence intervals; edit style without refitting |
| `existing_roc.py` | Existing Matplotlib code using accepted ROC coordinates; no model training |
| `existing_plot.m` | Existing MATLAB code; preserve the language when planning publication layout/export changes |
| `final_figure.svg` | A vector figure for planning QA of dimensions, typography and embedded content |

Reading these files supports a routing decision. It does not prove the R, Python or MATLAB backend has rendered successfully. Actual drawing tasks must check the selected environment and inspect their output.
