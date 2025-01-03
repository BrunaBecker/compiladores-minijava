from minijava_scanner import MiniJavaScanner
from minijava_parser import MiniJavaParserLL1

class SemanticError(Exception):
    pass

class MiniJavaSemanticAnalyzer:
    def __init__(self, syntax_tree):
        self.syntax_tree = syntax_tree
        self.symbol_table = {}

    def analyze(self):
        self.check_program(self.syntax_tree)
        return self.syntax_tree

    def check_program(self, node):
        if node["type"] == "Program":
            self.symbol_table = {node["main_class"]["class_name"]: {}}
            for clazz in node["classes"]:
                self.symbol_table[clazz["name"]] = {}

            print("Initial Symbol Table:")
            print(self.symbol_table)  # Debug print for symbol table initialization

            # Check the main class and other classes
            self.check_main_class(node["main_class"])
            for clazz in node["classes"]:
                self.check_class(clazz)
                
    def check_main_class(self, node):
        if node["type"] != "MainClass":
            raise SemanticError(f"Expected 'MainClass', but got {node['type']}")
        class_name = node["class_name"]
        for command in node["commands"]:
            self.check_command(command, {})

    def check_class(self, node):
        class_name = node["name"]
        self.symbol_table[class_name] = {}
        for method in node["methods"]:
            self.check_method(method)

    def check_method(self, node):
        method_table = {}
        for param in node["parameters"]:
            param_name = param["name"]
            method_table[param_name] = param["param_type"]
        for var in node["local_variables"]:
            var_name = var["name"]
            method_table[var_name] = var["var_type"]

        self.symbol_table[node["name"]] = method_table
        print(f"Symbol Table for method '{node['name']}':")
        print(method_table)  # Debug print for method-level symbol table

        for command in node["commands"]:
            self.check_command(command, method_table)

    def check_command(self, node, method_table=None):
        if method_table is None:
            method_table = {}  # Initialize with an empty dictionary if None is passed

        if node["type"] == "Assignment":
            var_name = node["target"]
            print(f"Checking variable '{var_name}' in method table: {method_table}")  # Debug print for variable check
            if var_name not in method_table:
                raise SemanticError(f"Semantic Error: Variable '{var_name}' is not declared in the current scope.")
        # Handle other command types as needed


class MiniJavaCodeGenerator:
    def __init__(self, syntax_tree):
        self.syntax_tree = syntax_tree
        self.instructions = []
        self.symbol_table = {}
        self.stack_offset = 0
        self.label_counter = 0  # Counter for unique labels
    
    def get_unique_label(self, base):
        label = f"{base}_{self.label_counter}"
        self.label_counter += 1
        return label

    def allocate_variable(self, name):
        self.stack_offset -= 4
        self.symbol_table[name] = self.stack_offset  # Store offset in symbol table
        self.instructions.append(f"    # Allocated {name} at offset {self.stack_offset}")
        return self.stack_offset

    def generate(self):
        print("Starting MIPS code generation...")  # Debug print
        self.generate_program(self.syntax_tree)
        print("MIPS code generation completed.")  # Debug print
        return "\n".join(self.instructions)

    def generate_program(self, node):
        if node["type"] == "Program":
            print("Generating MIPS for Program...")  # Debug print
            self.instructions.append(".data")
            self.instructions.append("newline: .asciiz \"\\n\"")  # Newline for printing
            self.instructions.append(".text")
            self.instructions.append(".globl main")
            print("Generating MIPS for Main class...")  # Debug print
            self.generate_main_class(node["main_class"])
            for clazz in node["classes"]:
                self.generate_class(clazz)

    def generate_main_class(self, node):
        print(f"Generating MIPS for Main class '{node['class_name']}'...")  # Debug print
        self.instructions.append("main:")
        method_table = {}  # Main class doesn't have local variables
        for command in node["commands"]:
            self.generate_command(command, method_table)  # Pass method_table here
        self.instructions.append("# Program exit")
        self.instructions.append("    li $v0, 10")  # Exit syscall
        self.instructions.append("    syscall")

    def generate_class(self, node):
        for method in node["methods"]:
            self.instructions.append(f"{node['name']}_{method['name']}:")
            self.generate_method(method)

    def generate_method(self, node):
        print(f"Generating MIPS for Method '{node['name']}'...")  # Debug print
        method_table = {}

        # Allocate stack space for parameters and local variables
        for param in node.get("parameters", []):
            method_table[param["name"]] = self.allocate_variable(param["name"])
        for var in node.get("local_variables", []):
            method_table[var["name"]] = self.allocate_variable(var["name"])

        # Save the return address on the stack
        self.instructions.append(f"{node['name']}:")
        self.instructions.append("    addi $sp, $sp, -4")  # Space for return address
        self.instructions.append("    sw $ra, 0($sp)")     # Save return address

        # Generate commands in the method body
        for command in node["commands"]:
            self.generate_command(command, method_table)

        # Restore the return address and stack pointer
        self.instructions.append("    lw $ra, 0($sp)")  # Restore return address
        self.instructions.append("    addi $sp, $sp, 4")  # Free stack space
        self.instructions.append("    jr $ra")  # Return

    def generate_command(self, node, method_table):
        if node["type"] == "Assignment":
            self.evaluate_expression(node["value"], method_table)
            offset = method_table[node["target"]]
            self.instructions.append(f"    sw $t0, {offset}($sp)")  # Store result
        elif node["type"] == "Print":
            self.evaluate_expression(node["expression"], method_table)
            self.instructions.append("    li $v0, 1")  # Print integer syscall
            self.instructions.append("    move $a0, $t0")
            self.instructions.append("    syscall")
        elif node["type"] == "If":
            self.generate_if(node, method_table)
        elif node["type"] == "While":
            self.generate_while(node, method_table)
        elif node["type"] == "Return":
            self.evaluate_expression(node["value"], method_table)
            self.instructions.append("    move $v0, $t0  # Return value")
            self.instructions.append("    jr $ra")
        elif node["type"] == "MethodCall":
            # Push arguments in reverse order
            for arg in reversed(node["arguments"]):
                self.evaluate_expression(arg, method_table)
                self.instructions.append("    addi $sp, $sp, -4")
                self.instructions.append("    sw $t0, 0($sp)")
            # Call the method
            self.instructions.append(f"    jal {node['method_name']}")
            # Clean up the stack after the call
            self.instructions.append(f"    addi $sp, $sp, {4 * len(node['arguments'])}")
            # Save the result in $t0
            self.instructions.append("    move $t0, $v0")
        else:
            raise ValueError(f"Unsupported command type: {node['type']}")


    def evaluate_condition(self, node):
        self.evaluate_expression(node)
        self.instructions.append("    # Result of condition is in $t0")

    def generate_if(self, node, method_table):
        else_label = self.get_unique_label("else")
        end_if_label = self.get_unique_label("end_if")

        # Evaluate the condition
        self.evaluate_expression(node["condition"], method_table)
        self.instructions.append(f"    beqz $t0, {else_label}")

        # Generate the true branch
        self.generate_command(node["if_true"], method_table)
        self.instructions.append(f"    j {end_if_label}")

        # Generate the false branch
        self.instructions.append(f"{else_label}:")
        if "if_false" in node:
            self.generate_command(node["if_false"], method_table)

        # End label
        self.instructions.append(f"{end_if_label}:")

    def generate_while(self, node, method_table):
        start_label = self.get_unique_label("while_start")
        end_label = self.get_unique_label("while_end")
        self.instructions.append(f"{start_label}:")
        self.evaluate_expression(node["condition"], method_table)
        self.instructions.append(f"    beqz $t0, {end_label}")
        self.generate_command(node["body"], method_table)
        self.instructions.append(f"    j {start_label}")
        self.instructions.append(f"{end_label}:")

    def evaluate_expression(self, node, method_table):
        print(f"Evaluating node: {node}")  # Debugging statement
        if not isinstance(node, dict):
            raise ValueError(f"Invalid node structure: {node}")
        if "type" not in node:
            raise ValueError(f"Node missing 'type' key: {node}")
        if node["type"] == "Number":
            self.instructions.append(f"    li $t0, {node['value']}")  # Load constant
        elif node["type"] == "Identifier":
            offset = method_table.get(node["name"])
            if offset is None:
                raise ValueError(f"Undefined variable: {node['name']}")
            self.instructions.append(f"    lw $t0, {offset}($sp)")  # Load variable
        elif node["type"] == "ArithmeticOp":
            self.evaluate_expression(node["left"], method_table)
            self.instructions.append("    move $t1, $t0")
            self.evaluate_expression(node["right"], method_table)
            if node["operator"] == "*":
                self.instructions.append("    mul $t0, $t1, $t0")
            elif node["operator"] == "+":
                self.instructions.append("    add $t0, $t1, $t0")
            elif node["operator"] == "-":
                self.instructions.append("    sub $t0, $t1, $t0")
        elif node["type"] == "MethodCall":
            # Handle target
            self.evaluate_expression(node["target"], method_table)
            self.instructions.append("    move $t1, $t0  # Save target object")

            # Extract arguments properly
            if isinstance(node["arguments"], dict) and node["arguments"].get("type") == "ExpressionList":
                arguments = node["arguments"].get("expressions", [])
            else:
                raise ValueError(f"Invalid arguments for MethodCall: {node}")

            # Push arguments onto the stack
            for arg in reversed(arguments):
                self.evaluate_expression(arg, method_table)
                self.instructions.append("    addi $sp, $sp, -4")
                self.instructions.append("    sw $t0, 0($sp)")

            # Call the method
            self.instructions.append(f"    jal {node['method_name']}")

            # Clean up the stack
            self.instructions.append(f"    addi $sp, $sp, {4 * len(arguments)}")

            # Store result
            self.instructions.append("    move $t0, $v0")




# Example usage
if __name__ == "__main__":
    # Exemplo de código MiniJava+
    code = """
    class Factorial {
        public static void main(String[] a) {
            System.out.println(new Fac().ComputeFac(10));
        }
    }

    class Fac {
        public int ComputeFac(int num) {
            int num_aux;
            if (num < 1)
                num_aux = 1;
            else
                num_aux = num * (this.ComputeFac(num - 1));
            return num_aux;
        
        }
    }
    """
    
    scanner = MiniJavaScanner()
    tokens = scanner.tokenize(code)

    parser = MiniJavaParserLL1(tokens)
    syntax_tree = parser.parse_program()

    analyzer = MiniJavaSemanticAnalyzer(syntax_tree)
    try:
        syntax_tree = analyzer.analyze()
        print("Semantic analysis completed successfully.")
    except SemanticError as e:
        print(f"Semantic error: {e}")

    generator = MiniJavaCodeGenerator(syntax_tree)
    mips_code = generator.generate()
    with open("output.asm", "w") as f:
        f.write(mips_code)
    print("MIPS code generated successfully.")
