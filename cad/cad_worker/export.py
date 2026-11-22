from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh

# (node name, mesh in world mm, rgba): display-only geometry that is not CadQuery solids.
Mesh = tuple[str, trimesh.Trimesh, tuple[float, float, float, float]]

# glTF is Y up; the CAD world is Z up. CadQuery's own GLB writer applies the same turn.
Z_UP_TO_Y_UP = trimesh.transformations.rotation_matrix(-np.pi / 2, (1, 0, 0))


def export(
    assy: cq.Assembly, out_dir: Path, stem: str, extra_meshes: list[Mesh] | None = None
) -> dict[str, Path]:
    """GLB for the viewer, STEP for engineering. The STEP holds only the CadQuery parts;
    `extra_meshes` (e.g. the AR4 links) go into the GLB only."""
    out_dir.mkdir(parents=True, exist_ok=True)
    glb = out_dir / f"{stem}.glb"
    step = out_dir / f"{stem}.step"
    if extra_meshes:
        _scene_glb(assy, extra_meshes, glb)
    else:
        assy.export(str(glb))
    assy.export(str(step))
    return {"glb": glb, "step": step}


def _tessellate(child: cq.Assembly, tolerance: float = 0.1) -> trimesh.Trimesh:
    obj = child.obj
    shape = cq.Compound.makeCompound(obj.vals()) if isinstance(obj, cq.Workplane) else obj
    shape = shape.moved(child.loc)
    verts, tris = shape.tessellate(tolerance, 0.2)
    return trimesh.Trimesh([v.toTuple() for v in verts], tris)


def _scene_glb(assy: cq.Assembly, extra: list[Mesh], path: Path) -> None:
    """One flat glTF scene: a named node per CadQuery child and per extra mesh."""
    parts: list[Mesh] = [
        (c.name, _tessellate(c), c.color.toTuple() if c.color else (0.7, 0.7, 0.7, 1.0))
        for c in assy.children
    ]
    scene = trimesh.Scene()
    for name, mesh, rgba in parts + list(extra):
        mesh = mesh.smooth_shaded  # split normals at sharp edges: flat faces, round cylinders
        mesh.visual = trimesh.visual.TextureVisuals(
            material=trimesh.visual.material.PBRMaterial(
                name=f"{name}_mat",
                baseColorFactor=[round(c * 255) for c in rgba],
                metallicFactor=0.3,
                roughnessFactor=0.5,
                doubleSided=True,
            )
        )
        mesh.apply_transform(Z_UP_TO_Y_UP)
        scene.add_geometry(mesh, node_name=name, geom_name=name)
    path.write_bytes(scene.export(file_type="glb"))
