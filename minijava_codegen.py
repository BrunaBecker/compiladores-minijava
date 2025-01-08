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
            self.symbol_table = {clazz["name"]: {} for clazz in node["classes"]}
            self.symbol_table[node["main_class"]["class_name"]] = {}
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
        self.symbol_table[class_name] = {"fields": {}, "methods": {}, "extends": node.get("extends")}
        
        # Add fields to the class
        for var in node.get("fields", []):  # Assuming `fields` holds class-level variables
            self.symbol_table[class_name]["fields"][var["name"]] = var["var_type"]
        
        # Add methods to the class
        for method in node["methods"]:
            method_name = method["name"]
            self.symbol_table[class_name]["methods"][method_name] = {
                "parameters": {param["name"]: param["param_type"] for param in method["parameters"]},
                "local_variables": {var["name"]: var["var_type"] for var in method["local_variables"]}
            }
            self.check_method(method)

    def check_method(self, node):
        method_table = {}
        for param in node["parameters"]:
            param_name = param["name"]
            method_table[param_name] = param["param_type"]
        for var in node["local_variables"]:
            var_name = var["name"]
            method_table[var_name] = var["var_type"]

        # self.symbol_table[node["name"]] = method_table

        for command in node["commands"]:
            self.check_command(command, method_table)

    def check_command(self, node, method_table=None):
        if method_table is None:
            method_table = {}  # Initialize with an empty dictionary if None is passed

        if node["type"] == "Assignment":
            var_name = node["target"]
            print(f"Checking variable '{var_name}' in method table: {method_table}")  # Debug print for variable check
            if var_name not in method_table and var_name not in self.symbol_table[class_name]["fields"]:
                raise SemanticError(f"Variable '{var_name}' is not declared in the current or outer scope.")


class MiniJavaCodeGenerator:
    def __init__(self, syntax_tree, symbol_table):
        self.syntax_tree = syntax_tree
        self.symbol_table = symbol_table  
        self.instructions = []
        self.stack_offset = 0
        self.label_counter = 0

    def get_unique_label(self, base):
        label = f"{base}_{self.label_counter}"
        self.label_counter += 1
        return label

    def allocate_variable(self, name):
        self.stack_offset -= 4
        offset = self.stack_offset
        self.symbol_table[name] = offset
        self.instructions.append(f"    # Allocated {name} at offset {offset}")
        return offset

    def generate(self):
        print("Starting MIPS code generation...")
        self.generate_program(self.syntax_tree)
        print("MIPS code generation completed.")
        return "\n".join(self.instructions)

    def generate_program(self, node):
        if node["type"] == "Program":
            print("Generating MIPS for Program...")
            self.instructions.append(".data")
            self.instructions.append("newline: .asciiz \"\\n\"")
            self.instructions.append(".text")
            self.instructions.append(".globl main")
            self.generate_main_class(node["main_class"])
            for clazz in node["classes"]:
                self.generate_class(clazz)

    def generate_main_class(self, node):
        print(f"Generating MIPS for Main class '{node['class_name']}'...")
        self.instructions.append("main:")
        method_table = {}
        for command in node["commands"]:
            self.generate_command(command, method_table)
        self.instructions.append("# Program exit")
        self.instructions.append("    li $v0, 10")
        self.instructions.append("    syscall")

    def generate_class(self, node):
        self.current_class = node["name"] 
        for method in node["methods"]:
            qualified_name = f"{node['name']}_{method['name']}"
            self.instructions.append(f"{qualified_name}:")
            self.generate_method(method)

    def generate_method(self, node):
        class_name = self.get_enclosing_class_name(node) 
        qualified_name = f"{class_name}_{node['name']}"
        
        print(f"Generating MIPS for Method '{qualified_name}'...")  

        # Method label
        self.instructions.append(f"{qualified_name}:")
        
        # Prologue: Adjust stack pointer and save necessary registers
        self.instructions.append(f"    addi $sp, $sp, {4 * len(node['arguments'])}  # Restore stack")
        self.instructions.append("    sw $ra, 0($sp)      # Save return address")
        self.instructions.append("    sw $s0, 4($sp)      # Save current object reference")
        self.instructions.append("    sw $s1, 8($sp)      # Save caller's $s1")

        # Save current object reference into $s0
        self.instructions.append("    move $s0, $a0  # Set 'this' reference for the method")

        # Map method parameters and variables
        method_table = {}
        param_offset = 12  # Start after saved registers
        for param in node.get("parameters", []):
            method_table[param["name"]] = param_offset
            param_offset += 4  # Move to the next stack slot for parameters

        var_offset = -4  # Local variables grow negatively on the stack
        for var in node.get("local_variables", []):
            method_table[var["name"]] = var_offset
            var_offset -= 4

        # Update stack offset for local variables
        self.stack_offset = var_offset

        # Generate method body
        for command in node["commands"]:
            self.generate_command(command, method_table)

        # Epilogue: Restore $ra, $s0, and $s1
        self.instructions.append("    lw $s0, 4($sp)")
        self.instructions.append("    lw $s1, 8($sp)")
        self.instructions.append("    lw $ra, 0($sp)")
        self.instructions.append("    addi $sp, $sp, 12")
        self.instructions.append("    jr $ra")
        self.instructions.append("    move $s0, $a0  # Restore 'this'")


    def generate_command(self, node, method_table):
        if node["type"] == "Assignment":
            self.evaluate_expression(node["value"], method_table)
            offset = method_table[node["target"]]
            self.instructions.append(f"    sw $t0, {offset}($sp)")
        elif node["type"] == "Print":
            self.evaluate_expression(node["expression"], method_table)
            self.instructions.append("    li $v0, 1")
            self.instructions.append("    move $a0, $t0")
            self.instructions.append("    syscall")
        elif node["type"] == "If":
            self.generate_if(node, method_table)
        elif node["type"] == "While":
            self.generate_while(node, method_table)
        elif node["type"] == "Return":
            self.evaluate_expression(node["value"], method_table)
            self.instructions.append("    move $v0, $t0")
        elif node["type"] == "MethodCall":
            print(f"Debug: MethodCall node structure: {node}")

            # Handle method calls
            target = node["target"]
            method_name = node["method_name"]

            # Evaluate the target object (e.g., `new Fac()`)
            self.evaluate_expression(target, method_table)
            self.instructions.append("    move $t1, $t0  # Save target object reference")

            # Push arguments onto the stack
            arguments = node["arguments"]  # Assuming arguments is a list of expressions
            if isinstance(arguments, list):
                for arg in reversed(arguments):  # Reverse to maintain correct argument order
                    self.evaluate_expression(arg, method_table)
                    self.instructions.append("    addi $sp, $sp, -4")
                    self.instructions.append("    sw $t0, 0($sp)")
            else:
                raise ValueError(f"Unexpected arguments format: {arguments}")


            # Set 'this' for the method call (target object reference)
            self.instructions.append("    move $a0, $t1  # Set 'this' for the method call")

            # Generate the method label
            class_name = target.get("class_name", self.current_class)  # Fallback to current class
            qualified_method_name = f"{class_name}_{method_name}"
            self.instructions.append(f"    jal {qualified_method_name}")

            # Restore 'this' after the method call
            self.instructions.append("    move $s0, $a0  # Restore 'this'")

            # Clean up the stack after the call
            self.instructions.append(f"    addi $sp, $sp, {4 * len(expressions)}  # Restore stack")

            # Save the method's return value
            self.instructions.append("    move $t0, $v0")
            
        else:
            raise ValueError(f"Unsupported command type: {node['type']}")

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
        if node["type"] == "Number":
            # Load an immediate value into $t0
            self.instructions.append(f"    li $t0, {node['value']}")

        elif node["type"] == "Identifier":
            # Load a variable's value from the stack or register
            if node["name"] in method_table:
                offset = method_table[node["name"]]
                self.instructions.append(f"    lw $t0, {offset}($sp)")
            elif node["name"] in self.symbol_table[self.current_class]["fields"]:
                # Access a field variable
                field_offset = self.symbol_table[self.current_class]["fields"][node["name"]]
                self.instructions.append(f"    lw $t0, {field_offset}($s0)")
            else:
                raise ValueError(f"Variable '{node['name']}' not found in method or class scope.")

        elif node["type"] == "ArithmeticOp":
            # Evaluate arithmetic operations
            left = node["left"]
            right = node["right"]

            # Evaluate left operand
            self.evaluate_expression(left, method_table)
            self.instructions.append("    move $t1, $t0")  # Save left operand in $t1

            # Evaluate right operand
            self.evaluate_expression(right, method_table)

            # Perform the operation
            if node["operator"] == "+":
                self.instructions.append("    add $t0, $t1, $t0")
            elif node["operator"] == "-":
                self.instructions.append("    sub $t0, $t1, $t0")
            elif node["operator"] == "*":
                self.instructions.append("    mul $t0, $t1, $t0")
            else:
                raise ValueError(f"Unsupported operator: {node['operator']}")

        elif node["type"] == "MethodCall":
            # Debugging to inspect node structure
            print(f"Debug: MethodCall node structure: {node}")
            
            # Handle method calls
            target = node["target"]
            method_name = node["method_name"]

            # Evaluate the target object (e.g., `new Fac()`)
            self.evaluate_expression(target, method_table)
            self.instructions.append("    move $t1, $t0  # Save target object reference")

            # Push arguments onto the stack
            for arg in reversed(node["arguments"]):
                self.evaluate_expression(arg, method_table)
                self.instructions.append("    addi $sp, $sp, -4")
                self.instructions.append("    sw $t0, 0($sp)")

            # Set 'this' for the method call (target object reference)
            self.instructions.append("    move $a0, $t1  # Set 'this' for the method call")

            # Generate the method label
            class_name = target.get("class_name", self.current_class)  # Fallback to current class
            qualified_method_name = f"{class_name}_{method_name}"
            self.instructions.append(f"    jal {qualified_method_name}")

            # Restore 'this' after the method call
            self.instructions.append("    move $s0, $a0  # Restore 'this'")

            # Clean up the stack after the call
            self.instructions.append(f"    addi $sp, $sp, {4 * len(node['arguments'])}  # Restore stack")

            # Save the method's return value
            self.instructions.append("    move $t0, $v0")

        elif node["type"] == "NewObject":
            # Handle object creation
            class_name = node["class_name"]
            if class_name not in self.symbol_table:
                raise ValueError(f"Class '{class_name}' not found in the symbol table during code generation.")

            size = self.get_class_size(class_name)
            self.instructions.append(f"    li $a0, {size}")  # Allocate space for object
            self.instructions.append("    li $v0, 9")       # Syscall for memory allocation
            self.instructions.append("    syscall")         # Perform allocation
            self.instructions.append("    move $t0, $v0")   # Store allocated object address in $t0

        elif node["type"] == "This":
            # Load the current object reference into $t0
            self.instructions.append("    move $t0, $s0")

        else:
            raise ValueError(f"Unsupported expression type: {node['type']}")

    def analyze_expression(self, node):
        if node["type"] == "ArithmeticOp":
            left = self.analyze_expression(node["left"])
            right = self.analyze_expression(node["right"])
            if left["type"] == "Number" and right["type"] == "Number":
                return {"type": "Number", "value": eval(f"{left['value']} {node['operator']} {right['value']}")}
        return node
    
    def get_class_size(self, class_name):
        if class_name not in self.symbol_table:
            raise ValueError(f"Class '{class_name}' not found in the symbol table.")
        
        size = len(self.symbol_table[class_name]["fields"]) * 4
        
        parent_class = self.symbol_table[class_name].get("extends")
        while parent_class:
            size += len(self.symbol_table[parent_class]["fields"]) * 4
            parent_class = self.symbol_table[parent_class].get("extends")
        
        return max(size, 4)


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
        
        print("Symbol Table After Semantic Analysis:")
        print(analyzer.symbol_table)
    except SemanticError as e:
        print(f"Semantic error: {e}")

    generator = MiniJavaCodeGenerator(syntax_tree, analyzer.symbol_table)
    mips_code = generator.generate()
    with open("output.asm", "w") as f:
        f.write(mips_code)
    print("MIPS code generated successfully.")
