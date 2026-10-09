"""segment_tree.py - Segment Tree abstract data type used by BudgetBuddy.

A segment tree stores one value per index (here: one value per DAY of the month)
and answers "combine everything from day L to day R" in O(log n), while a
point update also costs only O(log n).

The tree is generic: pass any associative `combine` function and its `identity`.
    sum tree : combine=add, identity=0   -> total spending in a range of days
    max tree : combine=max, identity=0   -> biggest single day in a range
Indexes are 0-based and ranges are inclusive on both ends.
"""
import operator   # Provides built-in functions like add, mul, etc. Useful for combining values in the tree.


class SegmentTree:
    def __init__(self, size, combine=operator.add, identity=0):
        if not isinstance(size, int) or size <= 0:
            raise ValueError("size must be a positive integer")  
            # Ensures the tree has a valid size. Prevents errors from invalid input.
        self.n = size
        self.combine = combine       # Function to combine values (e.g., sum, max). Defines the tree’s purpose.
        self.identity = identity     # Neutral element (0 for sum, -∞ for max). Used when ranges don’t overlap.
        self.tree = [identity] * (4 * size)   # Internal tree storage. 4n slots guarantee enough space.
        self.leaves = [identity] * size       # Stores actual values at each index (the "expenses" in BudgetBuddy).

    @classmethod
    def from_list(cls, values, combine=operator.add, identity=0):
        st = cls(len(values), combine, identity)  
        # Create a tree sized to fit the list of values.
        st.leaves = list(values)  
        # Copy values into leaves (like storing expenses for food, transport, etc.).
        st._build(1, 0, st.n - 1)  
        # Build the tree recursively from these values.
        return st

    def _build(self, node, lo, hi):
        if lo == hi:  
            # Base case: leaf node (represents a single expense category).
            self.tree[node] = self.leaves[lo]
            return
        mid = (lo + hi) // 2
        self._build(2 * node, lo, mid)  
        # Build left child (first half of expenses).
        self._build(2 * node + 1, mid + 1, hi)  
        # Build right child (second half of expenses).
        self.tree[node] = self.combine(self.tree[2 * node], self.tree[2 * node + 1])  
        # Parent stores combined result (e.g., total expenses of both halves).

    def _check(self, i):
        if not isinstance(i, int) or not 0 <= i < self.n:
            raise IndexError(f"index {i} out of range 0..{self.n - 1}")  
            # Validates index access. Prevents querying/updating invalid categories.

    def get(self, index):
        self._check(index)  
        # Ensure index is valid.
        return self.leaves[index]  
        # Return the expense value at that category.

    def update(self, index, value):
        """Replace the value at `index`. O(log n)."""
        self._check(index)  
        # Validate index.
        self.leaves[index] = value  
        # Update stored expense.
        self._update(1, 0, self.n - 1, index, value)  
        # Propagate change up the tree.

    def add(self, index, delta):
        """Add `delta` to the value at `index`. O(log n)."""
        self.update(index, self.get(index) + delta)  
        # Convenient way to increase an expense (e.g., add more transport cost).

    def _update(self, node, lo, hi, index, value):
        if lo == hi:  
            # Leaf node reached → update expense directly.
            self.tree[node] = value
            return
        mid = (lo + hi) // 2
        if index <= mid:
            self._update(2 * node, lo, mid, index, value)  
            # Update left child.
        else:
            self._update(2 * node + 1, mid + 1, hi, index, value)  
            # Update right child.
        self.tree[node] = self.combine(self.tree[2 * node], self.tree[2 * node + 1])  
        # Recalculate parent totals after update.

    def query(self, left, right):
        """Combine all values from `left` to `right`, inclusive. O(log n)."""
        self._check(left)
        self._check(right)
        if left > right:
            raise ValueError("left must be <= right")  
            # Prevent invalid range queries.
        return self._query(1, 0, self.n - 1, left, right)  
        # Perform recursive query.

    def _query(self, node, lo, hi, left, right):
        if right < lo or hi < left:  
            # No overlap → return identity (0 for sum).
            return self.identity
        if left <= lo and hi <= right:  
            # Full overlap → return stored value.
            return self.tree[node]
        mid = (lo + hi) // 2  
        # Partial overlap → split into left and right.
        return self.combine(
            self._query(2 * node, lo, mid, left, right),
            self._query(2 * node + 1, mid + 1, hi, left, right),
        )


class SumSegmentTree(SegmentTree):
    def __init__(self, size):
        super().__init__(size, operator.add, 0)  
        # Specialization: sums expenses (total spending).


class MaxSegmentTree(SegmentTree):
    def __init__(self, size):
        super().__init__(size, max, 0)  
        # Specialization: finds maximum expense (biggest spending category).
        