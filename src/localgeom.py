"""Local boundary geometry inside a radius-R disk around a point (used by EXP02 and EXP06).

Classes (checked in this order):
  open edge (water/gap)   disk touches no neighbouring polygon (coastline, ZCTA gap)
  junction (3+ regions)   3 or more polygons intersect the disk
  multi-edge / sliver     own boundary enters the disk as 2+ separate pieces
  bent / corner           own boundary inside the disk is >10% longer than the straight chord
  straight                otherwise
"""
import numpy as np
import shapely


def n_pieces(geoms):
    out = np.zeros(len(geoms), dtype=int)
    for i, gm in enumerate(geoms):
        try:
            if gm is None or gm.is_empty:
                continue
            if gm.geom_type == "GeometryCollection":
                lines = [p for p in gm.geoms if p.geom_type in ("LineString", "MultiLineString")]
                if not lines:
                    continue
                gm = shapely.union_all(lines)
            if gm.geom_type == "MultiLineString":
                gm = shapely.line_merge(gm)
            out[i] = shapely.get_num_geometries(gm)
        except Exception:
            out[i] = -1
    return out


def classify(L, x, y, own, d, R):
    """Geometry class for points (x, y) inside polygon `own`, at distance d (< R) from its boundary."""
    disks = shapely.buffer(shapely.points(x, y), R, quad_segs=32)
    inp, _ = L.tree.query(disks, predicate="intersects")
    n_reg = np.bincount(inp, minlength=len(x))
    seg = shapely.intersection(L.bounds[own], disks)
    bend = shapely.length(seg) / (2 * np.sqrt(np.maximum(R * R - np.asarray(d) ** 2, 1e-9)))
    pieces = n_pieces(seg)
    cls = np.where(n_reg <= 1, "open edge (water/gap)",
          np.where(n_reg >= 3, "junction (3+ regions)",
          np.where(pieces >= 2, "multi-edge / sliver",
          np.where(bend > 1.10, "bent / corner", "straight"))))
    return cls, n_reg, pieces, bend
