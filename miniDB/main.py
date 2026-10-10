from minidb.lexer import tokenize
from minidb.parser import Parser
from minidb.engine import ExecutionEngine
from minidb.formatter import TableFormatter  # Added formatter import

def main():
    engine = ExecutionEngine()
    print("--- MiniDB Custom Query Language Shell ---")
    print("Try running: GET users.name orders.product orders.price FROM users JOIN orders ON users.id = orders.user_id")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            query = input("MiniDB > ")
            if query.strip().lower() == "exit":
                break
            if not query.strip():
                continue

            # 1. Lexing
            tokens = tokenize(query)
            
            # 2. Parsing
            parser = Parser(tokens)
            ast = parser.parse()
            
            # 3. Execution
            results = engine.execute(ast)
            
            # 4. Display output formatted as ASCII table (or raw status string for INSERT/UPDATE/DELETE)
            print("\nResult:")
            if isinstance(results, list):
                print(TableFormatter.format(results))
            else:
                print(results)
            print("-" * 50 + "\n")

        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == "__main__":
    main()