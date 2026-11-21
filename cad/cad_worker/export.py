from pathlib import Path

import cadquery as cq


def export(assy: cq.Assembly, out_dir: Path, stem: str) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    glb = out_dir / f"{stem}.glb"
    step = out_dir / f"{stem}.step"
    assy.export(str(glb))
    assy.export(str(step))
    return {"glb": glb, "step": step}
