# Inline the starter GLBs into the design prototypes so each opens as one file.
import base64, pathlib
here = pathlib.Path(__file__).parent
out = here.parents[2] / "cad" / "out"
glb = {k: base64.b64encode((out / f).read_bytes()).decode() for k, f in [("__GLB_WHEELED__", "starter.glb"), ("__GLB_AR4__", "starter_ar4.glb")]}
for name in ["onboarding", "bombot"]:
    src = (here / f"{name}.src.html").read_text()
    for key, data in glb.items():
        src = src.replace(key, data)
    (here / f"{name}.html").write_text(src)
    print("wrote", name + ".html", len(src) // 1024, "KB")
