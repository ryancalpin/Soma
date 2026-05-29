"""Write the assembled numpy volume as a NIfTI file for the NiiVue viewer.

NiiVue ingests NIfTI directly and provides multi-planar reconstruction, 3D render
and a 4D time scrubber, so emitting NIfTI does most of the viewer work for free.

Spacing is unknown (no DICOM metadata), so we assume isotropic in-plane spacing and
encode an adjustable slice (Z) aspect in the affine; the user can fine-tune it later.
"""

from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np

from ..models import OutputKind


def write_nifti(
    arr: np.ndarray,
    out_path: Path,
    output_kind: OutputKind,
    z_aspect: float = 1.0,
) -> Path:
    """Convert ``arr`` to NIfTI on disk and return the path.

    NIfTI is X,Y,Z(,T) ordered, so we transpose from our Z/T-first layout.
    """
    is_rgb = arr.ndim >= 3 and arr.shape[-1] == 3 and output_kind != OutputKind.CINE_2D_TIME

    if output_kind == OutputKind.VOLUME_3D:
        # [Z,Y,X] -> [X,Y,Z]
        data = np.transpose(arr, (2, 1, 0)) if not is_rgb else np.transpose(arr, (2, 1, 0, 3))
        zooms = (1.0, 1.0, float(z_aspect))
    elif output_kind == OutputKind.VOLUME_4D:
        # [T,Z,Y,X] -> [X,Y,Z,T]
        data = np.transpose(arr, (3, 2, 1, 0))
        zooms = (1.0, 1.0, float(z_aspect), 1.0)
    else:  # CINE_2D_TIME: [T,Y,X(,3)] -> [X,Y,1,T]
        if arr.ndim == 4:  # RGB cine: collapse to grayscale for NIfTI scalar field
            arr = arr.mean(axis=-1).astype(arr.dtype)
        t, y, x = arr.shape
        data = np.transpose(arr, (2, 1, 0)).reshape(x, y, 1, t)
        zooms = (1.0, 1.0, 1.0, 1.0)

    data = np.ascontiguousarray(data)
    img = nib.Nifti1Image(data, affine=np.diag(list(zooms[:3]) + [1.0]))
    img.header.set_zooms(zooms)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    nib.save(img, str(out_path))
    return out_path
