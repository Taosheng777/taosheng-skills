# Backend Selection

Preserve an explicit Python/R choice and the project's existing plotting workflow.
Otherwise use the decision table and the available environment to choose a suitable
backend. A missing preference alone is not a blocker. Ask only if a material delivery
constraint cannot be inferred. A read-only audit of an existing figure needs no choice.

## Quick decision table

| Recommend R when | Recommend Python when |
|---|---|
| The user brings R scripts, RData/RDS, Seurat objects, DESeq2/limma outputs, survival models, or ggplot templates | The data pipeline is already Python, NumPy/Pandas arrays, PyTorch/TensorFlow outputs, image arrays, or simulation output |
| The target plot is `ggplot2`, `patchwork`, `ComplexHeatmap`, `ggtree`, `circlize`, `survminer`, `maftools`, or Seurat/UMAP-heavy | The target plot needs low-level custom layout, Matplotlib patches, image plates, subplot mosaics, or custom drawing primitives |
| The user provides an R template collection or an existing R plotting workflow | The user wants a self-contained script with matplotlib/seaborn/statsmodels and no R dependency |
| Heatmap annotations are biologically rich and multi-layered | Image panels and quantitative panels need tight pixel/axis control |

If either backend can do the job, honor the user's preference. Do not switch
backends for aesthetics alone.

## Reproducible backend and inspection

Keep plotting code and final assembly in the selected backend. Do not silently redraw
an explicitly requested R figure in Python, or vice versa. Inspect the actual exported
artifact using available viewers, PDF/SVG rasterizers, and format validation tools;
inspection does not require the plotting engine and must not substitute an approximation.

If the runtime or a required package is missing, inspect existing project and bundled
environments first. Use an equivalent available environment or install within existing
authorization. A new installation permission blocks only that installation/rendering
step; prepare source data, the selected-backend script, and a precise blocker meanwhile.
If you selected the default yourself, use a compatible available alternative when it
preserves the requested formats and reproducibility, and disclose the change.

## Default stacks

### R

- Core plotting: `ggplot2`
- Multi-panel assembly: `patchwork`
- Heatmaps: `ComplexHeatmap`, `circlize`
- Direct labels: `ggrepel`
- Survival/clinical: `survival`, `survminer`, `forestplot`, `ggplot2`
- Single-cell/omics: `Seurat`, `SingleCellExperiment`, `ComplexHeatmap`, `ggtree`
- Export: `svglite`, `grDevices::cairo_pdf`, `ragg`

### Python

- Core plotting: `matplotlib`
- Statistical plots: `seaborn`
- Layout: `subplot_mosaic`, `GridSpec`
- Tables/model output: `pandas`, `numpy`, `statsmodels`
- Images: `matplotlib.imshow`, `skimage`, `tifffile` when needed
- Export: `fig.savefig(... .svg/.pdf/.tiff)`, `svg.fonttype='none'`,
  `pdf.fonttype=42`

## Mixed workflow rule

Use the selected plotting backend for final assembly. Other languages may prepare
data and existing inspection tools may validate the real exports. Keep stable source
data beside the plotting script when needed for reproduction; do not redraw substitute
previews that could hide defects in the delivered artifact.

## Recommendation language

Use direct language:

```text
For this figure I recommend R because the main burden is ComplexHeatmap-style
omics annotation and patchwork assembly. I will still keep the export contract
SVG/PDF/TIFF with editable text.
```

```text
For this figure I recommend Python because the key panel is a custom image plate
with quantitative overlays and a subplot_mosaic layout. Matplotlib gives tighter
control over the raster and vector layers.
```
