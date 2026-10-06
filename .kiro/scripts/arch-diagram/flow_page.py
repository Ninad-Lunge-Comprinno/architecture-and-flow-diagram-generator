"""Flow-page builder: left-to-right ranked layout with crossing minimisation and orthogonal edge routing."""

from __future__ import annotations

import logging
import textwrap
from typing import Optional

import shapes
import layout

from diagram import Diagram, _label_html, _edge_label_html, ICON_SIZE
from spec import (
    SpecError,
    _check_unique_ids,
    _validate_services,
    _check_edges,
    _edge_style,
)

logger = logging.getLogger("arch_diagram")


def _route_flow_edge(src_box, tgt_box):
    """Choose directional anchors; Draw.io supplies the orthogonal path."""
    sx, sy, sw, sh = src_box
    tx, ty, tw, th = tgt_box
    source_cy = sy + sh / 2
    target_cy = ty + th / 2
    source_cx = sx + sw / 2
    target_cx = tx + tw / 2
    dx = target_cx - source_cx
    dy = target_cy - source_cy
    source_fraction = max(0.15, min(0.85, 0.5 + dy / 400))
    target_fraction = max(0.15, min(0.85, 0.5 - dy / 400))
    if abs(dx) >= abs(dy):
        exit_xy, entry_xy = ((1.0, source_fraction), (0.0, target_fraction)) if dx >= 0 else ((0.0, source_fraction), (1.0, target_fraction))
    else:
        source_fraction = max(0.15, min(0.85, 0.5 + dx / 400))
        target_fraction = max(0.15, min(0.85, 0.5 - dx / 400))
        exit_xy, entry_xy = ((source_fraction, 1.0), (target_fraction, 0.0)) if dy >= 0 else ((source_fraction, 0.0), (target_fraction, 1.0))
    return exit_xy, entry_xy, []


# ---------------------------------------------------------------------------
# Flow edge routing
# ---------------------------------------------------------------------------
# A flow page reads left to right, so a well-formed flow is mostly straight
# runs joined by a single bend. The router below keeps that property: a span
# whose two ends line up stays one segment, and every other edge takes a
# channel from the gutter it has to cross. Channels are tried from the gutter
# centre outwards, and one already claimed by another edge is only reused when
# the clean ones run out, so parallel arrows run side by side instead of
# stacking on top of each other.
FLOW_CHANNEL_STEP = 20.0   # pitch between parallel channels inside a gutter
FLOW_MIN_CHANNEL = 16.0    # keep channels this far clear of any box border
FLOW_PORT_MARGIN = 0.06    # keep ports inside this fraction of a box side
# Ports are allocated in 0..1 border fractions, so spacing is expressed in
# fractions too. 0.25 is one anchor step on the icon's declared connection
# points, which is what keeps two arrows off the same attachment point.
FLOW_PORT_STEP = 0.25
# Edge labels are drawn by draw.io at the path midpoint, so two arrows whose
# midpoints land in the same spot print their text on top of each other. The
# router shifts a label along its own segment instead, which keeps it on the
# line it belongs to.
FLOW_LABEL_FONT = 14.0
FLOW_LABEL_PAD = 10.0
FLOW_LABEL_LINE = 17.0
FLOW_LABEL_SLIDES = (0.0, 34.0, -34.0, 68.0, -68.0, 102.0, -102.0)


def _flow_label_size(label: str) -> tuple[float, float]:
    """Approximate the drawn size of a wrapped edge label.

    Mirrors :func:`_edge_label_html` so the estimate matches what draw.io wraps.
    """
    lines = textwrap.wrap(label, width=22, break_long_words=True,
                          break_on_hyphens=False) or [""]
    widest = max(len(line) for line in lines)
    return (widest * FLOW_LABEL_FONT * 0.55 + FLOW_LABEL_PAD,
            len(lines) * FLOW_LABEL_LINE + 8.0)


def _flow_path_length(path: list) -> float:
    return sum(abs(b[0] - a[0]) + abs(b[1] - a[1])
               for a, b in zip(path, path[1:]))


def _flow_point_at(path: list, distance: float) -> tuple:
    """Point ``distance`` arc-lengths along ``path``."""
    remaining = distance
    for a, b in zip(path, path[1:]):
        step = abs(b[0] - a[0]) + abs(b[1] - a[1])
        if step <= 0:
            continue
        if remaining <= step:
            ratio = remaining / step
            return (a[0] + (b[0] - a[0]) * ratio,
                    a[1] + (b[1] - a[1]) * ratio)
        remaining -= step
    return path[-1]


def _flow_rects_overlap(a: tuple, b: tuple, gap: float = 0.0) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return (ax < bx + bw + gap and bx < ax + aw + gap
            and ay < by + bh + gap and by < ay + ah + gap)


def _flow_label_offsets(edges, boxes, paths) -> dict:
    """Pick a per-edge label nudge that keeps label boxes clear of each other.

    draw.io centres an edge label on the path midpoint, so two arrows that
    share a midpoint region print their text on top of one another. Each label
    slides along its own segment — which keeps it on its own line — until its
    box clears every label already placed and every icon.
    """
    obstacles: list = [tuple(box) for box in boxes.values()]
    offsets: dict = {}
    for index, edge in enumerate(edges):
        path = paths[index]
        if path is None or not edge.get("label"):
            continue
        width, height = _flow_label_size(edge["label"])
        half = width / 2
        length = _flow_path_length(path)
        if length <= 0:
            continue
        middle = length / 2
        centre = _flow_point_at(path, middle)
        chosen = None
        for slide in FLOW_LABEL_SLIDES:
            distance = min(max(middle + slide, 0.0), length)
            spot = _flow_point_at(path, distance)
            delta = (spot[0] - centre[0], spot[1] - centre[1])
            box = (spot[0] - half, spot[1] - height / 2, width, height)
            if any(_flow_rects_overlap(box, other) for other in obstacles):
                continue
            chosen = delta
            break
        if chosen is None:
            chosen = (0.0, 0.0)
            spot = centre
        else:
            spot = (centre[0] + chosen[0], centre[1] + chosen[1])
        offsets[index] = chosen
        obstacles.append((spot[0] - half, spot[1] - height / 2, width, height))
    return offsets
FLOW_BEND_COST = 260.0     # cost of an extra bend, in pixels of length
FLOW_CHANNEL_COST = 150.0  # cost of reusing a channel another edge already took
# An arrow drawn through an icon is worse than two arrows meeting at a point, so
# it outweighs several crossings and is never traded away for them.
FLOW_ICON_COST = 60000.0
FLOW_CROSS_COST = 6000.0   # cost of crossing or overlapping another arrow
FLOW_DETOUR_OFFSETS = (44.0, 74.0, 104.0)  # heights tried for a blocked span
FLOW_BAND_REACH = 260.0    # how far a blocked span may look for a clear row
# Free vertical band the flow layout leaves between stacked rows, on top of a
# node's label. It has to exceed the padded routing obstacle on both sides or
# a vertical run has nowhere to cross.
FLOW_ROW_GUTTER = 60.0


def _flow_obstacle(box) -> tuple:
    """Routing obstacle for a flow node: the icon plus its label band, padded."""
    x, y, w, h = box
    return (x - 10, y - 10, w + 20, h + layout.LABEL_BAND + 20)


def _flow_center(box) -> tuple:
    x, y, w, h = box
    return (x + w / 2, y + h / 2)


def _flow_side_span(box, side: str) -> tuple:
    """The (lo, hi) range a port can slide along on one side of a box."""
    x, y, w, h = box
    return (y, y + h) if side in ("left", "right") else (x, x + w)


# The AWS resourceIcon stencil declares its legal connection points on
# ``points=`` in the style string. Landing an arrow anywhere else makes draw.io
# push the exit off the shape's outline, so ports are snapped to these anchors.
# A side has 5 of them: the two corners, the centre, and two quarter points.
FLOW_PORT_ANCHORS = (0.0, 0.25, 0.5, 0.75, 1.0)
# The two end anchors are the icon's corners, and a corner belongs to two sides
# at once — an arrow leaving the right side there would sit on the same pixel
# as one leaving the bottom side. Ports are therefore allocated from the three
# interior anchors only, which no other side can reach.
FLOW_PORT_CHOICES = (0.25, 0.5, 0.75)


def _flow_snap(value: float) -> float:
    """Snap a 0..1 border position to the nearest declared connection point."""
    return min(FLOW_PORT_ANCHORS, key=lambda anchor: (abs(anchor - value), anchor))


def _flow_port_point(box, side: str, along: float) -> tuple:
    """Absolute point on ``box``'s border at ``along`` on the given side."""
    x, y, w, h = box
    if side == "right":
        return (x + w, along)
    if side == "left":
        return (x, along)
    if side == "bottom":
        return (along, y + h)
    return (along, y)


def _flow_port_fraction(box, side: str, along: float) -> tuple:
    """draw.io exit/entry fractions for a point on a box border.

    The cross-axis fraction is snapped to a declared connection point so the
    arrow attaches to the icon's outline instead of being pulled off it.
    """
    x, y, w, h = box
    if side in ("left", "right"):
        return ((1.0 if side == "right" else 0.0),
                _flow_snap((along - y) / h))
    return (_flow_snap((along - x) / w), (1.0 if side == "bottom" else 0.0))


def _flow_simplify(points: list) -> list:
    """Drop duplicate and colinear waypoints so a path shows only real bends."""
    result: list = []
    for point in points:
        if result and abs(point[0] - result[-1][0]) < 0.01 \
                and abs(point[1] - result[-1][1]) < 0.01:
            continue
        result.append(point)
    index = 1
    while index < len(result) - 1:
        a, b, c = result[index - 1], result[index], result[index + 1]
        if (abs(a[0] - b[0]) < 0.01 and abs(b[0] - c[0]) < 0.01) or \
           (abs(a[1] - b[1]) < 0.01 and abs(b[1] - c[1]) < 0.01):
            del result[index]
            continue
        index += 1
    return result


def _flow_channels(band: tuple, used: set,
                   step: float = FLOW_CHANNEL_STEP) -> list:
    """Candidate offsets inside a gutter band, centre-out and reuse-last.

    A band is the free stretch of a gutter between the icon an edge leaves and
    the icon it enters, so a channel picked from it always clears both ends.
    """
    lo, hi = band
    if hi <= lo:
        return [round(lo, 1)]
    values = [lo + index * step for index in range(int((hi - lo) / step) + 1)]
    if hi - values[-1] > step * 0.4:
        values.append(hi)
    mid = (lo + hi) / 2
    return sorted({round(value, 1) for value in values},
                  key=lambda value: (value in used, abs(value - mid), value))


def _flow_shape(index, edges, boxes, forced: Optional[str] = None) -> str:
    """Pick the routing shape for one edge: ``"h"`` for a side-to-side run,
    ``"v"`` for a top-to-bottom one.

    The house bias prefers ``"h"`` for left-to-right flows so the main lane of
    the page stays one straight horizontal run. ``forced`` overrides that, which
    the rework loop uses to flip an edge whose preferred shape has nowhere to
    cross.

    Threshold: prefer "h" only when the horizontal distance clearly dominates
    (dx >= dy), so diagonally-placed icons (e.g. client above-left of cognito)
    get a "v" routing that exits top/bottom rather than side-to-side.
    """
    if forced:
        return forced
    scx, scy = _flow_center(boxes[edges[index]["source"]])
    tcx, tcy = _flow_center(boxes[edges[index]["target"]])
    dx, dy = tcx - scx, tcy - scy
    if abs(dx) < 1:
        return "v"
    if abs(dy) < 1:
        return "h"
    return "h" if abs(dx) >= abs(dy) else "v"


def _flow_sides(shape: str, dx: float, dy: float) -> tuple:
    """Source and target sides for a shape, facing each other."""
    if shape == "h":
        return ("right", "left") if dx >= 0 else ("left", "right")
    return ("bottom", "top") if dy >= 0 else ("top", "bottom")


def _flow_side_size(box, side: str) -> float:
    return _flow_side_span(box, side)[1] - _flow_side_span(box, side)[0]


def _flow_place_ports(desired: list, lo: float, hi: float, step: float,
                      pinned: list) -> dict:
    """Place ports along one box side, keeping room between them.

    ``pinned`` lists the positions that must keep their exact coordinate — an
    end that sits directly opposite its partner needs it to stay a straight
    arrow. Everything else takes the nearest free spot, so a fan-out opens up
    without pushing a straight run out of line.

    Results are snapped to the icon's declared connection points, so two arrows
    that land close together still leave from two distinct anchors.
    """
    def to_fraction(value: float) -> float:
        return _flow_snap((min(hi, max(lo, value)) - lo) / (hi - lo)
                           if hi > lo else 0.5)

    placed: dict = {}
    taken: list = []
    for index in pinned:
        value = to_fraction(desired[index])
        # Two ends can both be pinned to the same spot when several partners
        # line up. Only the first keeps it; the rest step aside, otherwise both
        # arrows leave from one connection point.
        if any(abs(value - other) < step for other in taken):
            value = next((anchor for anchor in FLOW_PORT_CHOICES
                          if all(abs(anchor - other) >= step
                                 for other in taken)), value)
        placed[index] = value
        taken.append(value)
    for index in sorted(set(range(len(desired))) - set(pinned)):
        # Prefer the anchor nearest the wanted spot, otherwise the first free
        # anchor scanning outwards, so a fan-out spreads while a lone arrow
        # still points straight at its partner.
        wanted = to_fraction(desired[index])
        candidates = sorted(FLOW_PORT_CHOICES,
                            key=lambda anchor: (abs(anchor - wanted), anchor))
        free = [anchor for anchor in candidates
                if all(abs(anchor - other) >= step for other in taken)]
        if not free:
            continue
        placed[index] = free[0]
        taken.append(free[0])
    if len(placed) < len(desired):
        # More arrows than anchors on this side: share anchors evenly rather
        # than dropping arrows off the icon altogether.
        slots = sorted(range(len(desired)), key=lambda i: (desired[i], i))
        count = len(slots)
        for position, index in enumerate(slots):
            placed[index] = FLOW_PORT_CHOICES[
                min(len(FLOW_PORT_CHOICES) - 1,
                    position * len(FLOW_PORT_CHOICES) // max(1, count))]
    return placed


def _plan_flow_ports(edges, boxes, order, shapes) -> dict:
    """Choose a side, and a position on that side, for both ends of every edge.

    Ports are allocated per (node, side) so several arrows leaving the same
    border fan out instead of stacking, while an end whose partner sits
    directly opposite stays pinned and keeps a single straight segment.
    """
    slots: dict = {}
    for index in order:
        edge = edges[index]
        s, t = edge.get("source"), edge.get("target")
        if s not in boxes or t not in boxes:
            continue
        sb, tb = boxes[s], boxes[t]
        scx, scy = _flow_center(sb)
        tcx, tcy = _flow_center(tb)
        shape = shapes[index]
        s_side, t_side = _flow_sides(shape, tcx - scx, tcy - scy)
        if shape == "h":
            wants, cross = (tcy, scy), abs(tcy - scy)
        else:
            wants, cross = (tcx, scx), abs(tcx - scx)
        for which, node_id, side, want in (
                ("source", s, s_side, wants[0]),
                ("target", t, t_side, wants[1])):
            slots.setdefault((node_id, side), []).append(
                (index, which, want, cross < 1))
    plan: dict = {}
    for (node_id, side), keys in slots.items():
        box = boxes[node_id]
        span = _flow_side_span(box, side)
        size = span[1] - span[0]
        lo, hi = span[0] + size * FLOW_PORT_MARGIN, \
            span[1] - size * FLOW_PORT_MARGIN
        # Order the arrows on this side by where their opposite ends sit, so a
        # fan-out assigns ports top-to-bottom (left/right sides) or
        # left-to-right (top/bottom sides) instead of in arrival order. The
        # ``want`` field already holds the opposite endpoint's coordinate on
        # the relevant axis (y for left/right, x for top/bottom), and the
        # original index is the deterministic tie-break.
        keys = sorted(keys, key=lambda key: (key[2], key[0]))
        desired = [want for _, _, want, _ in keys]
        pinned = [position for position, key in enumerate(keys) if key[3]]
        fractions = _flow_place_ports(desired, lo, hi, FLOW_PORT_STEP, pinned)
        for position, key in enumerate(keys):
            plan[(key[0], key[1])] = (side, lo + (hi - lo) * fractions[position])
    return plan


def _flow_options(index, edges, boxes, plan, rects, used_channels):
    """Candidate ``(channel, points)`` routes for one edge.

    An aligned pair gets a single segment plus a few over/under detours. Any
    other pair gets a one-bend route through a channel taken from the gutter it
    has to cross, ordered from the gutter centre outwards. When that channel
    would have to cross another arrow, a two-bend variant steps sideways into
    the gutter of a neighbouring row first, so the edge goes around the
    crossing instead of through it.
    """
    edge = edges[index]
    s, t = edge["source"], edge["target"]
    sb, tb = boxes[s], boxes[t]
    s_side, s_along = plan[(index, "source")]
    t_side, t_along = plan[(index, "target")]
    # Snap s_along / t_along to the nearest declared connection-point anchor
    # on their respective box side.  _flow_port_fraction does the same snap
    # when computing exit/entry fractions, so the path endpoint and the
    # draw.io connection-point fraction always agree — eliminating the
    # sub-pixel y-mismatch that caused diagonal attachment at icon borders.
    def _snap_along(box, side, along):
        span = _flow_side_span(box, side)
        lo_s, hi_s = span
        size = hi_s - lo_s
        if size <= 0:
            return along
        frac = _flow_snap((along - lo_s) / size)
        return lo_s + frac * size

    s_along = _snap_along(sb, s_side, s_along)
    t_along = _snap_along(tb, t_side, t_along)
    start = _flow_port_point(sb, s_side, s_along)
    goal = _flow_port_point(tb, t_side, t_along)
    so, to = rects[s], rects[t]
    found: list = []
    if s_side in ("left", "right"):
        if start[0] <= goal[0]:
            lo, hi = so[0] + so[2] + FLOW_MIN_CHANNEL, to[0] - FLOW_MIN_CHANNEL
            near, far = so, to
        else:
            lo, hi = to[0] + to[2] + FLOW_MIN_CHANNEL, so[0] - FLOW_MIN_CHANNEL
            near, far = to, so
        if hi < lo:  # the two icons touch: cross the seam itself
            lo = hi = (lo + hi) / 2
        if abs(start[1] - goal[1]) < 0.01:
            found.append((None, [start, goal]))
            mid_x = (start[0] + goal[0]) / 2
            for offset in FLOW_DETOUR_OFFSETS:
                for level in (start[1] - offset, start[1] + offset):
                    found.append((None, [start, (mid_x, start[1]), (mid_x, level),
                                         (goal[0], level), goal]))
            # A node sitting between two aligned ends blocks the straight shot
            # for good. Step out into a free column, use a free row band, then
            # step back in, so the span goes around the blocker.
            for column in _flow_columns(rects, start[0], goal[0], used_channels):
                for level in _flow_bands(rects, start[1], used_channels):
                    found.append((("y", level),
                                  [start, (column, start[1]), (column, level),
                                   (goal[0], level), goal]))
        else:
            channels = _flow_channels((lo, hi), used_channels)
            for value in channels:
                found.append((("x", value),
                              [start, (value, start[1]), (value, goal[1]), goal]))
            # Escape routes: leave the gutter sideways at once, run along a
            # free row band, then come back in. Two extra bends, but they pass
            # arrows that a straight channel would have to cross.
            for level in _flow_rows(rects, min(start[1], goal[1]),
                                    max(start[1], goal[1]), used_channels):
                found.append((("y", level),
                              [start, (start[0], level), (goal[0], level), goal]))
    else:
        if start[1] <= goal[1]:
            lo, hi = so[1] + so[3] + FLOW_MIN_CHANNEL, to[1] - FLOW_MIN_CHANNEL
        else:
            lo, hi = to[1] + to[3] + FLOW_MIN_CHANNEL, so[1] - FLOW_MIN_CHANNEL
        if hi < lo:
            lo = hi = (lo + hi) / 2
        if abs(start[0] - goal[0]) < 0.01:
            found.append((None, [start, goal]))
            mid_y = (start[1] + goal[1]) / 2
            for offset in FLOW_DETOUR_OFFSETS:
                for column in (start[0] - offset, start[0] + offset):
                    found.append((None, [start, (start[0], mid_y), (column, mid_y),
                                         (column, goal[1]), goal]))
        else:
            channels = _flow_channels((lo, hi), used_channels)
            for value in channels:
                found.append((("y", value),
                              [start, (start[0], value), (goal[0], value), goal]))
            for column in _flow_columns(rects, min(start[0], goal[0]),
                                        max(start[0], goal[0]), used_channels):
                found.append((("x", column),
                              [start, (column, start[1]), (column, goal[1]), goal]))
    return found


def _flow_rows(rects, lo: float, hi: float, used: set,
               step: float = FLOW_CHANNEL_STEP) -> list:
    """Horizontal bands between stacked icons that span the y range ``lo..hi``.

    These are the clear rows an edge can duck into to get around an arrow
    crossing its gutter.
    """
    return _flow_corridors(rects, lo, hi, used, 1, step)


def _flow_bands(rects, around: float, used: set,
                reach: float = FLOW_BAND_REACH,
                step: float = FLOW_CHANNEL_STEP) -> list:
    """Free row bands within ``reach`` of ``around``, used to bypass a blocker.

    A straight span with a node in the middle of it has to leave its own row to
    get past, so the candidate heights come from every clear horizontal band
    near the row rather than a fixed set of offsets that may all be occupied.
    """
    return _flow_corridors(rects, around - reach, around + reach, used, 1, step)


def _flow_columns(rects, lo: float, hi: float, used: set,
                  step: float = FLOW_CHANNEL_STEP) -> list:
    """Vertical corridors between side-by-side icons spanning ``lo..hi``."""
    return _flow_corridors(rects, lo, hi, used, 0, step)


def _flow_corridors(rects, lo: float, hi: float, used: set, axis: int,
                    step: float) -> list:
    """Free offsets along one axis between the icons, for the other axis's
    detours. ``axis`` 0 is a column corridor (a free x), 1 a row band (a free
    y). Only offsets that no icon occupies within the span are returned, so a
    detour never needs to be checked against the source or the target again.
    """
    if hi - lo < 1:
        return []
    blocked: list = []
    for rx, ry, rw, rh in rects.values():
        if axis == 0:
            blocked.append((rx, rx + rw))
        else:
            blocked.append((ry, ry + rh))
    free: list = []
    cursor = lo
    for begin, end in sorted(blocked):
        if end <= cursor or begin >= hi:
            continue
        # An obstacle that starts above the range still blocks from ``cursor``
        # onwards, so the free gap before it is the one already collected.
        if begin - FLOW_MIN_CHANNEL >= cursor:
            free.append((cursor, begin - FLOW_MIN_CHANNEL))
        cursor = max(cursor, end + FLOW_MIN_CHANNEL)
    if hi - FLOW_MIN_CHANNEL >= cursor:
        free.append((cursor, hi - FLOW_MIN_CHANNEL))
    values: list = []
    for begin, end in free:
        if end < begin:
            continue
        count = int((end - begin) / step) + 1
        for index in range(count):
            values.append(begin + index * step)
    mid = (lo + hi) / 2
    return sorted({round(value, 1) for value in values},
                  key=lambda value: (value in used, abs(value - mid), value))


def _flow_crossing_edges(paths, order, clashes) -> set:
    """Edges taking part in a crossing, keeping the longer one of each pair.

    The longer edge of a pair is the one worth re-planning: it has more room to
    step aside than the short hop that both arrows want to make.
    """
    out: set = set()
    for a in range(len(order)):
        for b in range(a + 1, len(order)):
            if clashes(paths[order[a]], paths[order[b]]):
                out.add(order[b])
    return out


def _flow_penalty(points, source, target, others, over_icon, clashes) -> float:
    """Cost of one candidate route: length, bends, and every conflict it makes.

    Routing, the repair pass, and the pass selection all rank candidates with
    this one function. A single scale is what keeps them from disagreeing — a
    repair that lowers the total here is never rejected by the outer loop for
    moving a crossing from one arrow to another.
    """
    cost = sum(abs(a[0] - b[0]) + abs(a[1] - b[1])
               for a, b in zip(points, points[1:]))
    cost += FLOW_BEND_COST * (len(points) - 2)
    cost += FLOW_ICON_COST * int(over_icon(points, source, target))
    cost += FLOW_CROSS_COST * sum(1 for other in others if clashes(points, other))
    return cost


def _flow_conflict_score(paths, usable, edges, over_icon, clashes) -> float:
    """Total conflict cost of a whole set of routed paths."""
    routed = [paths[index] for index in usable]
    total = 0.0
    for position, index in enumerate(usable):
        total += FLOW_ICON_COST * int(
            over_icon(paths[index], edges[index]["source"],
                      edges[index]["target"]))
        total += FLOW_CROSS_COST * sum(
            1 for other in routed[position + 1:] if clashes(paths[index], other))
    return total


def _flow_repair(paths, order, edges, boxes, plan, rects, over_icon, clashes,
                 rounds: int = 3):
    """Re-pick the route of every clashing edge against the finished routes.

    Routing one edge at a time lets an early, long edge claim the only clean
    channel and leave a later one with nothing better than a crossing. Here the
    paths are already fixed, so each clashing edge is re-evaluated against all
    the others and only moved when that lowers the conflict cost.
    """
    for _ in range(rounds):
        improved = False
        for position, index in enumerate(order):
            s, t = edges[index]["source"], edges[index]["target"]
            others = [paths[other] for other in order if other != index]
            if not over_icon(paths[index], s, t) and \
                    not any(clashes(paths[index], path) for path in others):
                continue
            current = _flow_penalty(paths[index], s, t, others,
                                    over_icon, clashes)
            best = None
            for _, points in _flow_options(index, edges, boxes, plan, rects, set()):
                points = _flow_simplify(points)
                cost = _flow_penalty(points, s, t, others, over_icon, clashes)
                if best is None or cost < best[0]:
                    best = (cost, points)
            if best is not None and best[0] < current:
                paths[index] = best[1]
                improved = True
        if not improved:
            break
    return paths


def _route_flow_edges(edges, boxes, max_passes: int = 3):
    """Route flow edges through the gutters between nodes.

    Each pass picks a routing shape per edge, allocates ports on the borders
    those shapes need, and then lets every edge choose between the channels of
    its gutter. A pass that still leaves an edge crossing an icon is retried
    with that edge's shape flipped, so a target sitting in an occupied column
    is approached from the side instead. The best pass wins.

    Returns a list aligned with ``edges`` holding
    ``(exit_xy, entry_xy, waypoints)`` for every edge whose endpoints are
    placed, or None for an edge that references an unknown node.
    """
    import routing as shared_routing

    rects = {node_id: _flow_obstacle(box) for node_id, box in boxes.items()}
    usable = [index for index, edge in enumerate(edges)
              if edge.get("source") in boxes and edge.get("target") in boxes]

    def span(index) -> float:
        scx, scy = _flow_center(boxes[edges[index]["source"]])
        tcx, tcy = _flow_center(boxes[edges[index]["target"]])
        return abs(tcx - scx) + abs(tcy - scy)

    def over_icon(points, source, target) -> bool:
        return any(node_id not in (source, target)
                   and shared_routing._polyline_hits_rect(points, rect)
                   for node_id, rect in rects.items())

    def clashes(points, other) -> bool:
        for a, b in zip(points, points[1:]):
            for c, d in zip(other, other[1:]):
                if shared_routing._segments_overlap(a, b, c, d) or \
                        shared_routing._segments_cross(a, b, c, d):
                    return True
        return False

    by_span = sorted(usable, key=lambda i: -span(i))
    forced: dict = {}
    best = None
    for _ in range(max_passes):
        shapes = {index: _flow_shape(index, edges, boxes, forced.get(index))
                  for index in usable}
        plan = _plan_flow_ports(edges, boxes, by_span, shapes)

        def straight(index) -> bool:
            return abs(plan[(index, "source")][1]
                       - plan[(index, "target")][1]) < 0.01

        # Straight spans go down first: they are the backbone every detour has
        # to dodge, so they should not have to move for a longer edge later on.
        order = sorted(usable, key=lambda i: (0 if straight(i) else 1, -span(i)))
        used_channels: set = set()
        routed: list = []
        paths: dict = {}
        for index in order:
            s, t = edges[index]["source"], edges[index]["target"]
            best_edge = None
            for channel, points in _flow_options(
                    index, edges, boxes, plan, rects, used_channels):
                points = _flow_simplify(points)
                cost = _flow_penalty(points, s, t, routed, over_icon, clashes)
                if channel is not None and channel[1] in used_channels:
                    cost += FLOW_CHANNEL_COST
                if best_edge is None or cost < best_edge[0]:
                    best_edge = (cost, channel, points)
            _, channel, points = best_edge
            if channel is not None:
                used_channels.add(channel[1])
            routed.append(points)
            paths[index] = points

        # Repair first: it can clear crossings that another pass would only
        # shuffle around, and it runs against the same cost the passes use.
        paths = _flow_repair(paths, order, edges, boxes, plan, rects,
                             over_icon, clashes)
        score = _flow_conflict_score(paths, usable, edges, over_icon, clashes)
        if best is None or score < best[0]:
            best = (score, plan, paths, shapes)
        if score == 0:
            break
        # Edges still in conflict are candidates for a shape flip: an arrow that
        # has to cross another one on this axis may clear it on the other. Only
        # the longer edge of a crossing pair is flipped, so short backbone runs
        # stay put.
        blocked = {index for index in usable
                   if over_icon(paths[index], edges[index]["source"],
                                edges[index]["target"])}
        stuck = set(blocked) | _flow_crossing_edges(paths, order, clashes)
        progressed = False
        for index in sorted(stuck, key=lambda i: -span(i)):
            if forced.get(index) != shapes[index]:
                forced[index] = "v" if shapes[index] == "h" else "h"
                progressed = True
        if not progressed:
            break

    _, plan, paths, _ = best
    label_offsets = _flow_label_offsets(edges, boxes, paths)
    result: list = [None] * len(edges)
    for index in usable:
        sb, tb = boxes[edges[index]["source"]], boxes[edges[index]["target"]]
        s_side, s_along = plan[(index, "source")]
        t_side, t_along = plan[(index, "target")]
        # Snap to the nearest icon anchor so exit/entry fractions exactly
        # match the first/last path segment — preventing diagonal attachment.
        def _snap_along(box, side, along):
            lo_s, hi_s = _flow_side_span(box, side)
            size = hi_s - lo_s
            if size <= 0:
                return along
            frac = _flow_snap((along - lo_s) / size)
            return lo_s + frac * size
        s_along = _snap_along(sb, s_side, s_along)
        t_along = _snap_along(tb, t_side, t_along)
        points = paths[index]
        result[index] = (_flow_port_fraction(sb, s_side, s_along),
                         _flow_port_fraction(tb, t_side, t_along),
                         points[1:-1],
                         label_offsets.get(index))

    routed = [paths[index] for index in usable]
    icon_hits = sum(1 for index in usable
                    if over_icon(paths[index], edges[index]["source"],
                                 edges[index]["target"]))
    edge_hits = sum(1 for a in range(len(routed)) for b in range(a + 1, len(routed))
                    if clashes(routed[a], routed[b]))
    if icon_hits or edge_hits:
        logger.warning(
            "flow routing: %d edges routed with %d icon and %d edge crossings",
            len(routed), icon_hits, edge_hits,
        )
    else:
        logger.info(
            "flow routing: %d edges routed with no icon/edge conflicts", len(routed)
        )
    return result


def _count_crossings(layers: dict[int, list[str]], layer_ids: list[int],
                     order_in_layer: dict[str, int],
                     outgoing: dict[str, list[str]]) -> int:
    """Count edge crossings between every pair of adjacent layers.

    For an A->B edge pair (a1->b1, a2->b2) with a1,a2 in layer A and b1,b2 in
    layer B, the two edges cross when their endpoints are in opposite vertical
    order on each side, i.e. (order[a1] < order[a2]) != (order[b1] < order[b2]).
    """
    total = 0
    for upper, lower in zip(layer_ids, layer_ids[1:]):
        lower_set = set(layers[lower])
        # Collect A->B edges as (order_in_layer[a], order_in_layer[b]) pairs.
        pairs: list[tuple[int, int]] = []
        for a in layers[upper]:
            oa = order_in_layer.get(a, 0)
            for b in outgoing.get(a, []):
                if b in lower_set:
                    pairs.append((oa, order_in_layer.get(b, 0)))
        for i in range(len(pairs)):
            a1, b1 = pairs[i]
            for j in range(i + 1, len(pairs)):
                a2, b2 = pairs[j]
                if a1 == a2 or b1 == b2:
                    continue
                if (a1 < a2) != (b1 < b2):
                    total += 1
    return total


def _minimise_flow_crossings(layers: dict[int, list[str]], layer_ids: list[int],
                             order_in_layer: dict[str, int],
                             incoming: dict[str, list[str]],
                             outgoing: dict[str, list[str]],
                             order: dict[str, int]) -> dict[str, int]:
    """Reduce edge crossings with Sugiyama-style median sweeps.

    Sweeps the layers forward and backward, reordering each layer by the MEDIAN
    position of a node's neighbours in the adjacent layer. Median (not average)
    is the classic Eades-Wei heuristic and resists outliers pulling a node
    off-centre. After each full pass crossings are counted and the best ordering
    seen is kept. Mutates ``layers`` in place and returns the best
    ``order_in_layer`` mapping.
    """
    def _median(values: list[int]) -> float:
        values = sorted(values)
        count = len(values)
        mid = count // 2
        if count % 2:
            return float(values[mid])
        return (values[mid - 1] + values[mid]) / 2.0

    best_order = dict(order_in_layer)
    best_crossings = _count_crossings(layers, layer_ids, order_in_layer, outgoing)
    for _ in range(8):
        # Forward sweep: order each layer by the median of its predecessors.
        for layer_index in layer_ids[1:]:
            layer = layers[layer_index]
            keys = {}
            for nid in layer:
                preds = incoming[nid]
                if preds:
                    med = _median([order_in_layer.get(p, 0) for p in preds])
                else:
                    med = order_in_layer.get(nid, 0)
                keys[nid] = (med, order[nid])
            layer.sort(key=lambda nid: keys[nid])
            order_in_layer.update({nid: i for i, nid in enumerate(layer)})
        # Backward sweep: order each layer by the median of its successors.
        for layer_index in reversed(layer_ids[:-1]):
            layer = layers[layer_index]
            keys = {}
            for nid in layer:
                succs = outgoing[nid]
                if succs:
                    med = _median([order_in_layer.get(c, 0) for c in succs])
                else:
                    med = order_in_layer.get(nid, 0)
                keys[nid] = (med, order[nid])
            layer.sort(key=lambda nid: keys[nid])
            order_in_layer.update({nid: i for i, nid in enumerate(layer)})
        crossings = _count_crossings(layers, layer_ids, order_in_layer, outgoing)
        if crossings < best_crossings:
            best_crossings = crossings
            best_order = dict(order_in_layer)
    return best_order


def _pack_flow_rows(layers: dict[int, list[str]], layer_ids: list[int],
                    scope: dict[str, str], incoming: dict[str, list[str]],
                    outgoing: dict[str, list[str]],
                    order_in_layer: dict[str, int]) -> dict[str, float]:
    """Assign each node an integer row, carrying chains and packing siblings.

    Siblings are packed only when they share a rank and scope. Cross-scope edges
    inherit the parent's row, which keeps a Cloud-to-VPC path aligned instead of
    stretching it across a separate vertical band.

    Rows are whole steps apart. Averaging two parents' rows would otherwise
    place a node half a step from its neighbour, and half a step is less than an
    icon plus its label — the two obstacles then overlap and an edge has no clear
    band left to cross between them.
    """
    row_pos: dict[str, float] = {}
    for layer_index in layer_ids:
        layer = layers[layer_index]
        for node_scope in ("external", "cloud", "vpc"):
            members = [nid for nid in layer if scope[nid] == node_scope]
            if not members:
                continue
            desired = {}
            for row, nid in enumerate(members):
                parents = [p for p in incoming[nid] if p in row_pos]
                if parents:
                    parent_row = sum(row_pos[p] for p in parents) / len(parents)
                    # When a VPC producer has parallel outputs, put its Cloud
                    # dependency on a neighboring row. This keeps the VPC frame
                    # external and leaves the main horizontal continuation clear.
                    vpc_parents = [p for p in parents if scope[p] == "vpc"]
                    leaves_vpc = node_scope == "cloud" and bool(vpc_parents)
                    has_sibling_path = any(len(outgoing[p]) > 1 for p in vpc_parents)
                    is_terminal = not outgoing[nid]
                    if leaves_vpc and has_sibling_path:
                        # Push cross-scope children away from the VPC lane.
                        # Terminal nodes (dead ends) need only a 1-row offset
                        # for frame separation; non-terminals need 2 to leave
                        # room for their continuation path.
                        offset = 1 if is_terminal else 2
                        desired[nid] = (parent_row - offset if parent_row >= offset
                                        else parent_row + offset)
                    else:
                        desired[nid] = parent_row
                else:
                    desired[nid] = float(row)
            occupied_rows: list[int] = []
            for nid in sorted(members, key=lambda item: (desired[item],
                                                         order_in_layer[item])):
                target_row = max(0, int(round(desired[nid])))
                candidates = [target_row]
                for offset in range(1, len(members) + 2):
                    candidates.extend((target_row - offset, target_row + offset))
                row = next(candidate for candidate in sorted(
                    candidates, key=lambda value: (abs(value - target_row), value)
                ) if candidate >= 0 and all(
                    abs(candidate - placed) >= 1 for placed in occupied_rows
                ))
                row_pos[nid] = float(row)
                occupied_rows.append(row)
    return row_pos


def _flow_layout(nodes: list[dict], edges: list[dict],
                 groups: Optional[list[dict]] = None) -> dict[str, tuple[float, float]]:
    """Lay out a directed flow in left-to-right ranks and scope lanes.

    Connected peers are ordered to reduce crossings. Non-VPC AWS nodes use the
    main left-to-right lane; VPC members use a right-hand lane so the VPC frame
    never encloses unrelated Cloud services. Shared external clients stay on
    the left even when response edges point back to them; terminal external
    destinations sit beyond the Cloud boundary.
    """
    # Keep a readable gutter for labels without stretching simple flows across
    # the page. Rows must clear a node's whole routing obstacle (icon plus its
    # wrapped label, padded) with room to spare, otherwise vertically adjacent
    # icons leave no free band for an edge to cross and every vertical run is
    # forced through a neighbour.
    step_x = ICON_SIZE + 160
    step_y = ICON_SIZE + layout.LABEL_BAND + FLOW_ROW_GUTTER
    pad_x = pad_y = 100
    ids = [node["id"] for node in nodes]
    node_by_id = {node["id"]: node for node in nodes}
    order = {nid: i for i, nid in enumerate(ids)}
    incoming = {nid: [] for nid in ids}
    outgoing = {nid: [] for nid in ids}
    actor_services = {"user", "users", "mobile_client", "iot_device"}
    scope = {}
    for nid, node in node_by_id.items():
        declared = node.get("scope")
        if declared is not None and declared not in {"external", "cloud", "vpc"}:
            raise SpecError(f"Node {nid!r} has invalid flow scope {declared!r}.")
        scope[nid] = declared or (
            "external" if node.get("service") in actor_services else "cloud"
        )
    vpc_members = {nid for nid, node_scope in scope.items() if node_scope == "vpc"}
    for group in groups or []:
        if group.get("kind", "vpc") == "vpc":
            vpc_members.update(group.get("members", []) or [])
    for nid in vpc_members:
        if nid in scope:
            scope[nid] = "vpc"

    for edge in edges:
        src, tgt = edge.get("source"), edge.get("target")
        if src in outgoing and tgt in incoming:
            outgoing[src].append(tgt)
            incoming[tgt].append(src)

    # A client actor can both initiate requests and receive responses/events.
    # Treat its incoming response edges as feedback for ranking so they do not
    # turn an otherwise left-to-right flow into a cycle. Keep the full graph
    # below for branch ordering, placement, and routing.
    rank_incoming = {nid: [] for nid in ids}
    rank_outgoing = {nid: [] for nid in ids}
    for edge in edges:
        src, tgt = edge.get("source"), edge.get("target")
        if src not in rank_outgoing or tgt not in rank_incoming:
            continue
        if scope[tgt] == "external" and outgoing[tgt]:
            continue
        rank_outgoing[src].append(tgt)
        rank_incoming[tgt].append(src)

    indegree = {nid: len(rank_incoming[nid]) for nid in ids}
    queue = [nid for nid in ids if indegree[nid] == 0]
    external_sources = {nid for nid in queue if scope[nid] == "external"}
    rank = {nid: (1 if external_sources and nid not in external_sources else 0)
            for nid in queue}
    placed = []
    while queue:
        nid = queue.pop(0)
        placed.append(nid)
        for child in rank_outgoing[nid]:
            rank[child] = max(rank.get(child, 0), rank[nid] + 1)
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    cyclic = [nid for nid in ids if nid not in placed]
    if cyclic:
        final_rank = max((rank[nid] for nid in placed), default=-1) + 1
        rank.update({nid: final_rank for nid in cyclic})

    layers: dict[int, list[str]] = {}
    for nid in ids:
        layers.setdefault(rank.get(nid, 0), []).append(nid)
    layer_ids = sorted(layers)
    order_in_layer = {nid: i for layer in layers.values()
                      for i, nid in enumerate(layer)}

    # Sugiyama-style crossing minimisation (see _minimise_flow_crossings).
    order_in_layer = _minimise_flow_crossings(
        layers, layer_ids, order_in_layer, incoming, outgoing, order
    )
    for layer_index in layer_ids:
        layers[layer_index].sort(key=lambda nid: order_in_layer[nid])

    # Carry each chain's row through the graph, then pack siblings (see
    # _pack_flow_rows).
    row_pos = _pack_flow_rows(layers, layer_ids, scope, incoming, outgoing,
                              order_in_layer)

    cloud_nodes = [nid for nid in ids if scope[nid] == "cloud"]
    vpc_nodes = [nid for nid in ids if scope[nid] == "vpc"]
    cloud_max_rank = max((rank[nid] for nid in cloud_nodes), default=0)
    vpc_min_rank = min((rank[nid] for nid in vpc_nodes), default=0)
    # Keep the complete VPC frame to the right of non-VPC AWS services. This
    # preserves scope without reserving a tall, empty band beneath every flow.
    vpc_rank_offset = max(0, cloud_max_rank + 1 - vpc_min_rank)
    positions: dict[str, tuple[float, float]] = {}
    for nid in cloud_nodes:
        positions[nid] = (pad_x + rank[nid] * step_x,
                          pad_y + row_pos[nid] * step_y)
    for nid in vpc_nodes:
        positions[nid] = (pad_x + (rank[nid] + vpc_rank_offset) * step_x,
                          pad_y + row_pos[nid] * step_y)

    # Shared client actors remain on the left even when response/event edges
    # point back to them. Only terminal external destinations sit beyond AWS.
    external_targets = [nid for nid in ids if scope[nid] == "external"
                        and incoming[nid] and not outgoing[nid]]
    internal_right = max((x + ICON_SIZE for nid, (x, _) in positions.items()
                          if scope[nid] != "external"), default=pad_x + ICON_SIZE)
    target_x = internal_right + step_x - ICON_SIZE
    for nid in ids:
        if scope[nid] != "external":
            continue
        # A client that both receives content and sends telemetry belongs
        # between all adjacent steps, not on top of only its return path.
        neighbors = incoming[nid] + outgoing[nid]
        neighbor_ys = [positions[n][1] for n in neighbors if n in positions]
        y = (sum(neighbor_ys) / len(neighbor_ys)) if neighbor_ys else pad_y
        x = target_x if nid in external_targets else pad_x
        positions[nid] = (x, y)

    return positions


def build_flow_page(page: dict, default_provider: str, diagram_id: str,
                    meta: Optional[dict] = None) -> Diagram:
    """Build a flow page using a layered left-to-right layout.

    Nodes follow topological ranks, with branches stacked in rows and VPC
    members separated from other AWS services. Spec nodes may override layout
    positions with explicit 'x' and 'y' fields.
    """
    nodes = page.get("nodes", [])
    if not nodes:
        raise SpecError(f"Flow page {page.get('name')!r} has no 'nodes'.")

    elements: list[tuple[str, dict]] = []
    for node in nodes:
        if "id" not in node:
            raise SpecError(f"A node on flow page {page.get('name')!r} is missing 'id'.")
        if "service" not in node:
            raise SpecError(f"Node {node.get('id')!r} is missing 'service'.")
        elements.append((node["id"], node))
    ids = _check_unique_ids(elements, page.get("name", "flow"))
    _validate_services(elements, default_provider)
    _check_edges(page.get("edges", []), ids, page.get("name", "flow"))

    diagram = Diagram(name=page.get("name", "Flow Diagram"), diagram_id=diagram_id)

    # Compute left-to-right layered positions (spec x/y overrides if provided).
    auto_pos = _flow_layout(nodes, page.get("edges", []), page.get("groups", []))
    header_y = 280 if meta is not None else 0
    boxes: dict[str, tuple[float, float, float, float]] = {}
    frame_boxes: list[tuple[float, float, float, float]] = []

    for node in nodes:
        nid = node["id"]
        auto_x, auto_y = auto_pos.get(nid, (40, 60))
        x = node.get("x", auto_x)
        y = node.get("y", auto_y + header_y)
        boxes[nid] = (x, y, ICON_SIZE, ICON_SIZE)

    # AWS flow pages use the same cloud boundary as the architecture examples.
    # Source actors stay outside; AWS service nodes sit within the boundary.
    aws_boxes = [boxes[node["id"]] for node in nodes
                 if node.get("provider", default_provider) == "aws"
                 and node.get("scope") != "external"
                 and node.get("service") not in {
                     "user", "users", "mobile_client", "iot_device",
                 }]
    if aws_boxes:
        cloud_left = min(box[0] for box in aws_boxes) - 80
        cloud_top = max(20, min(box[1] for box in aws_boxes) - 120)
        cloud_right = max(box[0] + box[2] for box in aws_boxes) + 80
        cloud_bottom = max(box[1] + box[3] for box in aws_boxes) + layout.LABEL_BAND + 60
        diagram.add_container(
            "cloud", label=page.get("cloud_label", "AWS Cloud"),
            x=cloud_left, y=cloud_top,
            width=cloud_right - cloud_left, height=cloud_bottom - cloud_top,
            cell_id=f"{diagram_id}-cloud",
        )
        frame_boxes.append((cloud_left, cloud_top,
                            cloud_right - cloud_left, cloud_bottom - cloud_top))

    node_ids = {node["id"] for node in nodes}
    for group in page.get("groups", []) or []:
        members = group.get("members", []) or []
        missing = set(members) - node_ids
        if not members or missing:
            raise SpecError(
                f"Flow group {group.get('id')!r} needs valid member node ids; "
                f"unknown: {', '.join(sorted(missing)) or '(no members)'}."
            )
        kind = group.get("kind", "vpc")
        try:
            shapes.get_container(kind)
        except shapes.UnknownContainerError as exc:
            raise SpecError(f"Flow group {group.get('id')!r} has invalid kind {kind!r}.") from exc
        member_boxes = [boxes[nid] for nid in members]
        left = min(box[0] for box in member_boxes) - 55
        top = min(box[1] for box in member_boxes) - 75
        right = max(box[0] + box[2] for box in member_boxes) + 55
        bottom = max(box[1] + box[3] + layout.LABEL_BAND for box in member_boxes) + 45
        diagram.add_container(
            kind, label=group.get("label"), x=left, y=top,
            width=right - left, height=bottom - top,
            cell_id=f"{diagram_id}-{group.get('id', 'group')}",
        )
        frame_boxes.append((left, top, right - left, bottom - top))

    for node in nodes:
        nid = node["id"]
        x, y, _, _ = boxes[nid]
        diagram.add_icon(
            provider=node.get("provider", default_provider),
            service=node["service"],
            label=node.get("label"),
            x=x,
            y=y,
            cell_id=nid,
        )

    # Keep the branded title in the page header, as in the flow examples.
    if meta is not None:
        brand_x, brand_width = 40, 240.9
        diagram.add_comprinno_mark(x=brand_x, y=45)
        diagram.add_title_block(meta, x=brand_x + brand_width + 20, y=0)

    # Outer border enclosing all flow nodes
    if boxes:
        content = list(boxes.values()) + frame_boxes
        bx = 0 if meta is not None else min(b[0] for b in content) - 40
        by = 0 if meta is not None else min(b[1] for b in content) - 40
        right = max([b[0] + b[2] for b in content] + ([780] if meta is not None else []))
        bottom = max(
            max(b[1] + b[3] + layout.LABEL_BAND for b in boxes.values()),
            max((b[1] + b[3] for b in frame_boxes), default=0),
        )
        diagram.add_outer_border(bx, by, right - bx + 40, bottom - by + 40, margin=0)

    # Local import keeps the module importable without the routing engine
    # (e.g. lightweight unit tests) and avoids any circular-import risk.
    import routing as _flow_routing

    all_flow_edges = page.get("edges", []) or []
    icon_ids_flow = {node["id"] for node in nodes if node["id"] in boxes}

    # Build bounds from all node positions.
    bx_vals = [b[0] for b in boxes.values()] + [b[0] + b[2] for b in boxes.values()]
    by_vals = [b[1] for b in boxes.values()] + [b[1] + b[3] for b in boxes.values()]
    flow_bounds = (min(bx_vals) - 40, min(by_vals) - 40,
                   max(bx_vals) + 40, max(by_vals) + 40)

    # Separate auto-routable edges from spec-overridden ones. Edges carrying
    # hand-placed geometry keep their explicit ports/waypoints below.
    auto_edge_pairs = [
        (e["source"], e["target"])
        for e in all_flow_edges
        if e.get("source") in boxes and e.get("target") in boxes
        and not (e.get("source_point") or e.get("target_point") or e.get("waypoints"))
    ]

    # Route with the A* grid router (same engine as the architecture page).
    try:
        bfs_routes, bfs_endpoints, bfs_conflicts = _flow_routing.route_all_edges(
            auto_edge_pairs, boxes, icon_ids_flow, flow_bounds)
    except Exception as exc:  # pragma: no cover - defensive fallback
        # Fall back to the legacy channel router if the grid router fails.
        logger.warning(
            "flow routing: A* router failed (%s); falling back to channel router",
            exc,
        )
        bfs_routes, bfs_endpoints, bfs_conflicts = {}, {}, None
        _legacy = _route_flow_edges(all_flow_edges, boxes)
        for edge_index, edge in enumerate(all_flow_edges):
            if edge_index < len(_legacy) and _legacy[edge_index] is not None:
                e_xy, en_xy, wps, _lbl = _legacy[edge_index]
                ekey = (edge["source"], edge["target"])
                bfs_endpoints[ekey] = (e_xy, en_xy)
                bfs_routes[ekey] = ([None] + list(wps or []) + [None])

    # Report conflicts.
    if bfs_conflicts:
        n_ic = sum(1 for c in bfs_conflicts if c[0] == "edge_icon")
        n_ee = sum(1 for c in bfs_conflicts if c[0] == "edge_edge")
        logger.warning(
            "flow routing: %d edges routed with %d icon and %d edge crossings",
            len(auto_edge_pairs), n_ic, n_ee,
        )
    elif bfs_conflicts is not None:
        logger.info(
            "flow routing: %d edges routed with no icon/edge conflicts",
            len(auto_edge_pairs),
        )

    for edge in all_flow_edges:
        src, tgt = edge["source"], edge["target"]
        exit_xy = entry_xy = None
        waypoints = None
        ekey = (src, tgt)
        if ekey in bfs_routes and bfs_routes[ekey]:
            path = bfs_routes[ekey]
            exit_xy, entry_xy = bfs_endpoints[ekey]
            waypoints = [tuple(p) for p in path[1:-1] if p is not None] \
                if len(path) > 2 else []
            # Apply anchor snapping: snap port fractions to declared connection
            # points to prevent diagonal attachment (same fix as arch page).
            # When the fraction changes, also update the first waypoint coordinate
            # so the first segment stays orthogonal.
            if src in boxes and exit_xy:
                sb = boxes[src]
                side = ("right" if exit_xy[0] == 1.0
                        else "left" if exit_xy[0] == 0.0
                        else "bottom" if exit_xy[1] == 1.0
                        else "top")
                lo_s, hi_s = _flow_side_span(sb, side)
                size = hi_s - lo_s
                if size > 0:
                    along = lo_s + (exit_xy[1] if side in ("left", "right")
                                    else exit_xy[0]) * size
                    snapped_frac = _flow_snap((along - lo_s) / size)
                    snapped_along = lo_s + snapped_frac * size
                    if side in ("left", "right"):
                        old_frac = exit_xy[1]
                        exit_xy = (exit_xy[0], snapped_frac)
                        # Update first waypoint to match snapped y so first segment stays horizontal
                        if waypoints and abs(old_frac - snapped_frac) > 0.01:
                            wp0 = waypoints[0]
                            waypoints = [(wp0[0], snapped_along)] + list(waypoints[1:])
                    else:
                        old_frac = exit_xy[0]
                        exit_xy = (snapped_frac, exit_xy[1])
                        # Update first waypoint to match snapped x so first segment stays vertical
                        if waypoints and abs(old_frac - snapped_frac) > 0.01:
                            wp0 = waypoints[0]
                            waypoints = [(snapped_along, wp0[1])] + list(waypoints[1:])
        # Spec overrides always win.
        if edge.get("source_point"):
            exit_xy = tuple(float(v) for v in edge["source_point"].split(","))
        if edge.get("target_point"):
            entry_xy = tuple(float(v) for v in edge["target_point"].split(","))
        if edge.get("waypoints"):
            waypoints = [tuple(p) for p in edge["waypoints"]]
        # Strip any dashed styling: flow edges render solid.
        solid_edge = dict(edge)
        solid_edge.pop("dashed", None)
        if solid_edge.get("style"):
            style_parts = str(solid_edge["style"]).split(";")
            solid_edge["style"] = ";".join(
                part for part in style_parts
                if part and not part.startswith("dashed=")
            )
        diagram.add_edge(
            source=src,
            target=tgt,
            label=edge.get("label", ""),
            style=_edge_style(solid_edge),
            waypoints=waypoints,
            exit_xy=exit_xy,
            entry_xy=entry_xy,
        )
    return diagram
