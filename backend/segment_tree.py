"""Segment-tree data structure used for dated budget totals and peak spending.

Each leaf represents one day; each parent stores the combined value for its
interval. Budget Buddy uses sum trees for range totals and a max tree to find
the largest daily needs-and-wants total.

The structure supports point updates and inclusive range queries in O(log n).
Its associative combine operation and identity value define the aggregate:
addition with identity 0 for sums, or max with identity 0 for nonnegative
spending values. Indexes are zero-based.
"""
import operator  # Supplies the addition operation used by SumSegmentTree.


class SegmentTree:
    def __init__(self, size, combine=operator.add, identity=0):
        if not isinstance(size, int) or size <= 0:
            raise ValueError("size must be a positive integer")  
            # A tree needs at least one indexed value.
        self.n = size
        self.combine = combine       # Associative operation used to aggregate child intervals.
        self.identity = identity     # Aggregate returned for a query interval with no overlap.
        self.tree = [identity] * (4 * size)   # Array storage for interval aggregates.
        self.leaves = [identity] * size       # Current value at each day index.

    @classmethod
    def from_list(cls, values, combine=operator.add, identity=0):
        st = cls(len(values), combine, identity)  
        # Initialize the leaves, then compute all parent interval aggregates.
        st.leaves = list(values)
        st._build(1, 0, st.n - 1)
        return st

    def _build(self, node, lo, hi):
        if lo == hi:
            # A leaf represents the value at one day index.
            self.tree[node] = self.leaves[lo]
            return
        mid = (lo + hi) // 2
        self._build(2 * node, lo, mid)
        self._build(2 * node + 1, mid + 1, hi)
        self.tree[node] = self.combine(self.tree[2 * node], self.tree[2 * node + 1])

    def _check(self, i):
        # Every valid index must identify a day in this tree.
        if not isinstance(i, int) or not 0 <= i < self.n:
            raise IndexError(f"index {i} out of range 0..{self.n - 1}")

    def get(self, index):
        self._check(index)
        return self.leaves[index]

    def update(self, index, value):
        """Replace the value at `index`. O(log n)."""
        self._check(index)
        self.leaves[index] = value
        self._update(1, 0, self.n - 1, index, value)

    def add(self, index, delta):
        """Add `delta` to the value at `index`. O(log n)."""
        self.update(index, self.get(index) + delta)

    def _update(self, node, lo, hi, index, value):
        if lo == hi:
            # Replace the selected day's leaf value.
            self.tree[node] = value
            return
        mid = (lo + hi) // 2
        if index <= mid:
            self._update(2 * node, lo, mid, index, value)
        else:
            self._update(2 * node + 1, mid + 1, hi, index, value)
        # Recompute aggregates on the path back to the root.
        self.tree[node] = self.combine(self.tree[2 * node], self.tree[2 * node + 1])

    def query(self, left, right):
        """Combine all values from `left` to `right`, inclusive. O(log n)."""
        self._check(left)
        self._check(right)
        # An inclusive query must start no later than it ends.
        if left > right:
            raise ValueError("left must be <= right")
        return self._query(1, 0, self.n - 1, left, right)

    def _query(self, node, lo, hi, left, right):
        if right < lo or hi < left:
            # No overlap: return the aggregate's identity value.
            return self.identity
        if left <= lo and hi <= right:
            # Full overlap: this node already stores the requested aggregate.
            return self.tree[node]
        # Partial overlap: query both child intervals and combine their results.
        mid = (lo + hi) // 2
        return self.combine(
            self._query(2 * node, lo, mid, left, right),
            self._query(2 * node + 1, mid + 1, hi, left, right),
        )


class SumSegmentTree(SegmentTree):
    def __init__(self, size):
        # Addition makes each node the sum of daily values in its interval.
        super().__init__(size, operator.add, 0)


class MaxSegmentTree(SegmentTree):
    def __init__(self, size):
        # max makes each node the largest daily value in its interval.
        super().__init__(size, max, 0)
        