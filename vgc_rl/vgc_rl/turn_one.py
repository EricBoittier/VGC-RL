from __future__ import annotations


def parse_field_slots(spec: str) -> tuple[int, int]:
    parts = spec.replace(" ", "").split(",")

    if len(parts) != 2:
        raise ValueError(f"expected two comma-separated party indices, got {spec!r}")

    return int(parts[0]), int(parts[1])


def parse_brought_quad(spec: str) -> tuple[int, int, int, int]:
    parts = spec.replace(" ", "").split(",")

    if len(parts) != 4:
        raise ValueError(f"expected four comma-separated brought roster indices, got {spec!r}")

    vals = tuple(sorted(int(p) for p in parts))

    if len(set(vals)) != 4:
        raise ValueError("brought roster indices must be four distinct values")

    return vals
