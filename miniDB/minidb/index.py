class HashIndex:
    def __init__(self, column_name: str):
        self.column_name = column_name
        # Maps key_value -> list of matching row indices (e.g., {1: [0], "David": [0, 2]})
        self.index: dict[any, list[int]] = {}

    def build(self, rows: list[dict]):
        """Populate or rebuild the index from a list of rows."""
        self.index.clear()
        for idx, row in enumerate(rows):
            val = row.get(self.column_name)
            if val is not None:
                if val not in self.index:
                    self.index[val] = []
                self.index[val].append(idx)

    def add(self, key_val, row_idx: int):
        """Update index incrementally when a row is inserted."""
        if key_val is not None:
            if key_val not in self.index:
                self.index[key_val] = []
            self.index[key_val].append(row_idx)

    def lookup(self, key_val) -> list[int]:
        """Returns row indices matching the given key value in O(1) time."""
        return self.index.get(key_val, [])