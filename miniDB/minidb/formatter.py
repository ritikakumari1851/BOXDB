class TableFormatter:
    @staticmethod
    def format(rows: list[dict]) -> str:
        if not rows:
            return "Empty set (0 rows)"

        # 1. Extract all unique column headers across all rows
        headers = list(dict.fromkeys(k for row in rows for k in row.keys()))

        # 2. Compute max width for each column (accounting for header & data length)
        col_widths = {}
        for h in headers:
            max_len = len(str(h))
            for row in rows:
                val_str = str(row.get(h, ""))
                if len(val_str) > max_len:
                    max_len = len(val_str)
            col_widths[h] = max_len

        # 3. Construct border line (e.g., +-------+-------+)
        border = "+" + "+".join("-" * (col_widths[h] + 2) for h in headers) + "+"

        # 4. Format header row
        header_row = "|" + "|".join(f" {str(h).ljust(col_widths[h])} " for h in headers) + "|"

        # 5. Format data rows
        data_rows = []
        for row in rows:
            line = "|" + "|".join(
                f" {str(row.get(h, '')).ljust(col_widths[h])} " for h in headers
            ) + "|"
            data_rows.append(line)

        # 6. Combine all lines into the final ASCII table string
        output = [
            border,
            header_row,
            border,
            *data_rows,
            border,
            f"({len(rows)} row(s) returned)"
        ]
        return "\n".join(output)