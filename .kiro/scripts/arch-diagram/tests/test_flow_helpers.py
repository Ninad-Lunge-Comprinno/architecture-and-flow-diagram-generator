"""Unit tests for the extracted flow-layout helpers.

These lock the behaviour of the pieces pulled out of ``_flow_layout`` during the
M2 decomposition so they can be reasoned about and changed independently.
"""

import generate_diagram as gd


class TestMinimiseFlowCrossings:
    def test_returns_order_for_every_node(self):
        # Two layers, a simple A/B -> C/D bipartite graph.
        layers = {0: ["a", "b"], 1: ["c", "d"]}
        layer_ids = [0, 1]
        order_in_layer = {"a": 0, "b": 1, "c": 0, "d": 1}
        incoming = {"a": [], "b": [], "c": ["a"], "d": ["b"]}
        outgoing = {"a": ["c"], "b": ["d"], "c": [], "d": []}
        order = {"a": 0, "b": 1, "c": 2, "d": 3}

        result = gd._minimise_flow_crossings(
            layers, layer_ids, order_in_layer, incoming, outgoing, order
        )
        assert set(result) == {"a", "b", "c", "d"}
        # Each layer's positions are a contiguous 0..n-1 permutation.
        assert sorted(result[n] for n in layers[0]) == [0, 1]
        assert sorted(result[n] for n in layers[1]) == [0, 1]

    def test_reduces_crossings_for_inverted_bipartite(self):
        # a->d, b->c with initial order a<b and c<d forces a crossing; the
        # heuristic should find an ordering with zero crossings.
        layers = {0: ["a", "b"], 1: ["c", "d"]}
        layer_ids = [0, 1]
        order_in_layer = {"a": 0, "b": 1, "c": 0, "d": 1}
        incoming = {"a": [], "b": [], "c": ["b"], "d": ["a"]}
        outgoing = {"a": ["d"], "b": ["c"], "c": [], "d": []}
        order = {"a": 0, "b": 1, "c": 2, "d": 3}

        best = gd._minimise_flow_crossings(
            layers, layer_ids, order_in_layer, incoming, outgoing, order
        )
        crossings = gd._count_crossings(layers, layer_ids, best, outgoing)
        assert crossings == 0


class TestPackFlowRows:
    def test_siblings_get_distinct_integer_rows(self):
        # One source fanning out to two same-scope children in the next layer.
        layers = {0: ["src"], 1: ["a", "b"]}
        layer_ids = [0, 1]
        scope = {"src": "cloud", "a": "cloud", "b": "cloud"}
        incoming = {"src": [], "a": ["src"], "b": ["src"]}
        outgoing = {"src": ["a", "b"], "a": [], "b": []}
        order_in_layer = {"src": 0, "a": 0, "b": 1}

        rows = gd._pack_flow_rows(
            layers, layer_ids, scope, incoming, outgoing, order_in_layer
        )
        assert set(rows) == {"src", "a", "b"}
        # Siblings must not share a row and rows are whole numbers.
        assert rows["a"] != rows["b"]
        assert all(float(v).is_integer() for v in rows.values())
        assert all(v >= 0 for v in rows.values())

    def test_linear_chain_inherits_parent_row(self):
        layers = {0: ["a"], 1: ["b"], 2: ["c"]}
        layer_ids = [0, 1, 2]
        scope = {"a": "cloud", "b": "cloud", "c": "cloud"}
        incoming = {"a": [], "b": ["a"], "c": ["b"]}
        outgoing = {"a": ["b"], "b": ["c"], "c": []}
        order_in_layer = {"a": 0, "b": 0, "c": 0}

        rows = gd._pack_flow_rows(
            layers, layer_ids, scope, incoming, outgoing, order_in_layer
        )
        # A straight chain stays on a single row.
        assert rows["a"] == rows["b"] == rows["c"]
