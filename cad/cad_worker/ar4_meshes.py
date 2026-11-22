"""The real AR4 links (Annin's MK3 meshes, see assets/ar4/NOTICE.md), posed for the viewer.

The meshes are display only: no fit check reads them, and they are not in the STEP export.
Each STL is in its own URDF link frame, in metres. `link_transforms` chains the joint origins
from ar_macro.xacro and maps the result into the CAD worker's world frame (mm, Z up, J1 on the
Z axis, the arm reaching towards +X, J2 at (64.2, 0, 169.8) on an axis along Y).

link_1 models Annin's own J2 motor on the turret's -Y side. `posed_links` cuts it away so the
generated J2 drive in arm.py is the only drive on screen.
"""

from functools import cache
from pathlib import Path

import numpy as np
import trimesh
from trimesh.transformations import euler_matrix, rotation_matrix, translation_matrix

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "ar4"

# (link, joint origin xyz in m, joint origin rpy, joint axis) from ar_macro.xacro; l6 from mk3.yaml.
JOINTS = [
    ("link_1", (0, 0, 0), (np.pi, 0, 0), (0, 0, 1)),
    ("link_2", (0, 0.0642, -0.16977), (np.pi / 2, 0, -np.pi / 2), (0, 0, -1)),
    ("link_3", (0, -0.305, 0.007), (0, 0, np.pi), (0, 0, -1)),
    ("link_4", (0, 0, 0), (np.pi / 2, 0, -np.pi / 2), (0, 0, -1)),
    ("link_5", (0, 0, -0.22263), (np.pi, 0, -np.pi / 2), (1, 0, 0)),
    ("link_6", (0, 0, 0.041), (0, 0, np.pi), (0, 0, 1)),
]

# All joints at zero: upper arm straight up, forearm reaching forward (+X).
Q_DEMO = (0.0,) * 6

# URDF base frame -> world: metres to mm, then turn the arm from -Y to +X.
WORLD = rotation_matrix(np.pi / 2, (0, 0, 1)) @ np.diag([1000.0, 1000.0, 1000.0, 1.0])

# Outer face of the turret's J2 side plate (link_1 mesh, measured at Q_DEMO). Annin's J2 motor
# starts here and runs out to y = -122; the generated gearbox bolts onto this face instead.
TURRET_FACE_Y = -57.1

NODE_NAMES = {
    "base_link": "base",
    "link_1": "turret",
    "link_2": "upper_arm",
    "link_3": "elbow",
    "link_4": "forearm",
    "link_5": "wrist",
    "link_6": "flange",
}

ALUMINIUM = (0.78, 0.79, 0.80, 1.0)
AR4_BLUE = (0.10, 0.25, 0.75, 1.0)
COLORS = {"upper_arm": AR4_BLUE}


def link_transforms(q=Q_DEMO) -> dict[str, np.ndarray]:
    """World pose (4x4, mm) of each link frame for joint angles q (radians)."""
    poses = {"base_link": WORLD.copy()}
    chain = np.eye(4)
    for (link, xyz, rpy, axis), angle in zip(JOINTS, q, strict=True):
        chain = (
            chain
            @ translation_matrix(xyz)
            @ euler_matrix(*rpy, "sxyz")
            @ rotation_matrix(angle, axis)
        )
        poses[link] = WORLD @ chain
    return poses


@cache
def _raw(link: str) -> trimesh.Trimesh:
    return trimesh.load_mesh(ASSETS / f"{link}.STL")


def _without_j2_motor(link_1: trimesh.Trimesh) -> trimesh.Trimesh:
    """Drop every face that reaches past the turret face (y < TURRET_FACE_Y at Q_DEMO)."""
    y = trimesh.transform_points(link_1.vertices, link_transforms()["link_1"])[:, 1]
    keep = (y[link_1.faces] >= TURRET_FACE_Y - 0.5).all(axis=1)
    out = link_1.copy()
    out.update_faces(keep)
    out.remove_unreferenced_vertices()
    return out


def posed_links(q=Q_DEMO) -> list[tuple[str, trimesh.Trimesh, tuple[float, float, float, float]]]:
    """(node name, mesh in world mm, rgba) for each AR4 link, ready for the GLB."""
    poses = link_transforms(q)
    out = []
    for link, name in NODE_NAMES.items():
        mesh = _raw(link)
        if link == "link_1":
            mesh = _without_j2_motor(mesh)
        mesh = mesh.copy()
        mesh.apply_transform(poses[link])
        out.append((name, mesh, COLORS.get(name, ALUMINIUM)))
    return out
