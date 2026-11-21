"""Throwaway spike: check a JSON schema against TinyFish output_schema rules (docs, Nov 2026)."""
import json
import sys

ALLOWED = {"anyOf", "enum", "format", "items", "maxItems", "maximum", "minItems", "minimum",
           "nullable", "properties", "propertyOrdering", "required", "type"}
FORMATS = {"date", "date-time", "duration", "time"}


def check(node, path, depth, errs):
    if isinstance(node, bool):
        errs.append(f"{path}: boolean schema node")
        return
    if depth > 10:
        errs.append(f"{path}: nesting depth > 10")
    for k in node:
        if k not in ALLOWED:
            errs.append(f"{path}: keyword '{k}' not allowed")
    t = node.get("type")
    if isinstance(t, list):
        errs.append(f"{path}: type arrays not supported, use nullable")
    if "enum" in node and (t != "string" or not all(isinstance(v, str) for v in node["enum"])):
        errs.append(f"{path}: enum needs type string and string values")
    if "format" in node and (t != "string" or node["format"] not in FORMATS):
        errs.append(f"{path}: bad format")
    if any(k in node for k in ("items", "minItems", "maxItems")) and t != "array":
        errs.append(f"{path}: array keywords on non-array")
    if any(k in node for k in ("minimum", "maximum")) and t not in ("number", "integer"):
        errs.append(f"{path}: min/max on non-number")
    props = node.get("properties", {})
    for r in node.get("required", []):
        if r not in props:
            errs.append(f"{path}: required '{r}' not in properties")
    order = node.get("propertyOrdering")
    if order is not None and (len(set(order)) != len(order) or not set(order) <= set(props)):
        errs.append(f"{path}: propertyOrdering invalid")
    for name, sub in props.items():
        check(sub, f"{path}/properties/{name}", depth + 1, errs)
    if "items" in node:
        check(node["items"], f"{path}/items", depth + 1, errs)


if __name__ == "__main__":
    schema = json.load(open(sys.argv[1]))
    errs = []
    if schema.get("type") != "object" or "anyOf" in schema:
        errs.append("#: top level must be type object without anyOf")
    if len(json.dumps(schema)) > 64 * 1024:
        errs.append("#: schema > 64KB")
    check(schema, "#", 1, errs)
    print("OK" if not errs else "\n".join(errs))
    sys.exit(1 if errs else 0)
