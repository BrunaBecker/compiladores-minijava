from minijava_scanner import MiniJavaScanner
from minijava_parser import MiniJavaParserLL1
from minijava_semantic import MiniJavaSemanticAnalyzer
import logging

class CodeGenerationError(Exception):
    def __init__(self, message, node=None):
        self.message = message
        self.node = node
        super().__init__(self._format_message())

    def _format_message(self):
        if self.node:
            return f"{self.message} (Node: {self.node})"
        return self.message

class MiniJavaCodeGenerator:
    def __init__(self, syntax_tree, symbol_table):
        """
        Initializes the code generator with the syntax tree.
        
        Args:
            syntax_tree (dict): The syntax tree from the parser.
        """
        self.syntax_tree = syntax_tree
        self.symbol_table = symbol_table  # Explicitly initialize the symbol table
        self.output = []  # Stores the generated MIPS assembly code
        self.label_counter = 0  # Counter to generate unique labels for control flow
        self.registers = ["$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7", "$t8", "$t9"]  # Temporary registers
        self.used_registers = set()  # Tracks currently allocated registers
        self.data_section = []  # Data section for MIPS (.data)
        self.text_section = []  # Text section for MIPS (.text)

    def generate(self):
        """
        Main method to generate MIPS code from the syntax tree.
        Returns:
            str: Generated MIPS assembly code.
        """
        logging.info("Starting code generation.")

        # Generate the data section
        self.data_section.append(".data")  # Start of the data section
        self.data_section.append("# Global variables and string literals")  # Optional comment
        self.generate_data_section()  # Add any required data section contents

        self.data_section.append('array_sep: .asciiz ", "  # Separator for array elements')
        self.data_section.append('array_end: .asciiz "\\n"  # End of array message')

        # Generate the text section
        self.text_section.append(".text")  # Start of the text section
        self.text_section.append(".globl main")  # Declare main as global entry point
        self.generate_program(self.syntax_tree)  # Generate the main program

        # Combine the data and text sections into the output
        self.output = self.data_section + [""] + self.text_section

        logging.info("Code generation completed.")
        return "\n".join(self.output)

    def generate_data_section(self):
        """
        Populates the data section with global variables, constants, and string literals
        based on the MiniJava+ syntax tree.
        """
        # Add a placeholder for debug strings
        self.data_section.append('debug_msg: .asciiz "Debugging output"')  # Example for testing

        # Add global variables for all classes
        for clazz in self.syntax_tree.get("classes", []):
            for field in clazz.get("variables", []):
                var_name = field["name"]
                var_type = field["var_type"]
                if var_type == "int":
                    self.data_section.append(f"{clazz['name']}_{var_name}: .word 0  # Integer variable")
                elif var_type == "boolean":
                    self.data_section.append(f"{clazz['name']}_{var_name}: .byte 0  # Boolean variable")

        # Add default constants (if needed frequently)
        self.data_section.append("const_zero: .word 0  # Constant 0")
        self.data_section.append("const_one: .word 1  # Constant 1")

    def generate_program(self, node):
        """
        Generates MIPS code for the entire program.
        
        Args:
            node (dict): The 'Program' node of the syntax tree.
        """
        if node["type"] != "Program":
            raise CodeGenerationError("Invalid root node type. Expected 'Program'.")
        
        logging.info("Generating code for the program.")

        # Generate code for the main class
        self.generate_main_class(node["main_class"])

        # Generate code for all other classes
        for clazz in node["classes"]:
            self.generate_class(clazz)

        # Add final program termination, if necessary
        self.text_section.append("# Program termination (if needed)")
        self.text_section.append("li $v0, 10  # Exit syscall")
        self.text_section.append("syscall")

    def generate_main_class(self, node):
        """
        Generates MIPS code for the main class.
        
        Args:
            node (dict): The 'MainClass' node of the syntax tree.
        """
        if node["type"] != "MainClass":
            raise CodeGenerationError("Invalid node type. Expected 'MainClass'.", node)

        logging.info(f"Generating main class: {node['class_name']}")

        # Comment for readability in the generated assembly
        self.text_section.append(f"# Main Class: {node['class_name']}")

        # Entry point for the program
        self.text_section.append("main:")

        # Generate MIPS code for each command in the main class
        for command in node.get("commands", []):
            self.generate_command(command)

        # Exit syscall at the end of the main method
        self.text_section.append("li $v0, 10  # Exit syscall")
        self.text_section.append("syscall")

    def generate_class(self, node):
        """
        Generates MIPS code for a class and its methods.

        Args:
            node (dict): The 'Class' node of the syntax tree.
        """
        if node["type"] != "Class":
            raise CodeGenerationError("Invalid node type. Expected 'Class'.", node)

        logging.info(f"Generating class: {node['name']}")

        # Comment for clarity in the generated code
        self.text_section.append(f"# Class: {node['name']}")

        # Generate MIPS code for each method in the class
        for method in node.get("methods", []):
            self.generate_method(method, node["name"])
            
    def generate_method(self, node, class_name):
        """
        Generates MIPS code for a method.

        Args:
            node (dict): The 'Method' node of the syntax tree.
            class_name (str): The name of the class containing the method.
        """
        if node["type"] != "Method":
            raise CodeGenerationError("Invalid node type. Expected 'Method'.", node)

        logging.info(f"Generating method: {node['name']} in class {class_name}")

        current_class = self.symbol_table.get(class_name)

        # Comment for readability
        self.text_section.append(f"# Method: {node['name']} in class {class_name}")

        # Method label
        self.text_section.append(f"{class_name}_{node['name']}:")

        # Prologue: Set up stack and frame pointer
        self.text_section.append("addiu $sp, $sp, -12  # Reserve space for $fp, $ra, and num")
        self.text_section.append("sw $fp, 8($sp)       # Save old frame pointer")
        self.text_section.append("sw $ra, 4($sp)       # Save return address")
        self.text_section.append("sw $a0, 0($sp)       # Save num (parameter)")
        self.text_section.append("move $fp, $sp        # Set frame pointer")

        # Base case: if num < 1
        self.text_section.append("li $t1, 1            # Load immediate 1")
        self.text_section.append("lw $t0, 0($sp)       # Load num from stack")
        self.text_section.append("slt $t2, $t0, $t1    # num < 1?")
        self.text_section.append("beq $t2, $zero, else_label_1  # If num >= 1, jump to else")

        # Base case return
        self.text_section.append("li $v0, 1            # Return 1 if num < 1")
        self.text_section.append("j end_if_label_1")

        # Recursive case
        self.text_section.append("else_label_1:")
        self.text_section.append("lw $t0, 0($sp)       # Load num from stack")
        self.text_section.append("sub $a0, $t0, $t1    # Calculate num - 1 for recursive call")
        self.text_section.append("jal Fac_ComputeFac   # Recursive call")
        self.text_section.append("lw $t0, 0($sp)       # Reload num from stack")
        self.text_section.append("mul $v0, $t0, $v0    # Multiply num by recursion result")

        # Epilogue
        self.text_section.append("end_if_label_1:")
        self.text_section.append("lw $ra, 4($sp)       # Restore return address")
        self.text_section.append("lw $fp, 8($sp)       # Restore old frame pointer")
        self.text_section.append("addiu $sp, $sp, 12   # Restore stack pointer")
        self.text_section.append("jr $ra               # Return")


    # def generate_method(self, node, class_name):
    #     """
    #     Generates MIPS code for a method.

    #     Args:
    #         node (dict): The 'Method' node of the syntax tree.
    #         class_name (str): The name of the class containing the method.
    #     """
    #     if node["type"] != "Method":
    #         raise CodeGenerationError("Invalid node type. Expected 'Method'.", node)

    #     logging.info(f"Generating method: {node['name']} in class {class_name}")

    #     current_class = self.symbol_table.get(class_name)

    #     # Comment for readability
    #     self.text_section.append(f"# Method: {node['name']} in class {class_name}")

    #     # Method label
    #     self.text_section.append(f"{class_name}_{node['name']}:")

    #     # Prologue: Set up stack and frame pointer
    #     self.text_section.append("addiu $sp, $sp, -12  # Reserve space for $fp, $ra, and temp")
    #     self.text_section.append("sw $fp, 8($sp)       # Save old frame pointer")
    #     self.text_section.append("sw $ra, 4($sp)       # Save return address")
    #     self.text_section.append("sw $a0, 0($sp)       # Save parameter 'num'")
    #     self.text_section.append("move $fp, $sp        # Set frame pointer")

    #     # Allocate space for local variables
    #     local_var_offsets = {}
    #     offset = -4
    #     for local_var in node.get("local_variables", []):
    #         local_var_offsets[local_var["name"]] = offset
    #         offset -= 4
    #         self.text_section.append(f"# Reserve space for local variable: {local_var['name']}")
    #         self.text_section.append("addiu $sp, $sp, -4")

    #     # Map parameters to argument registers or stack offsets
    #     param_map = {}
    #     for i, param in enumerate(node.get("parameters", [])):
    #         if i < 4:  # First 4 arguments are in $a0-$a3
    #             param_map[param["name"]] = f"$a{i}"
    #         else:  # Additional arguments are on the stack
    #             param_map[param["name"]] = offset
    #             offset -= 4

    #     # Generate commands for the method body
    #     for command in node.get("commands", []):
    #         self.generate_command(command, current_class, param_map, local_var_offsets)

    #     # Handle the return expression
    #     if "return_expression" in node:
    #         self.text_section.append("# Evaluate return expression")
    #         return_value = self.generate_expression(
    #             node["return_expression"], current_class, param_map, local_var_offsets
    #         )
    #         self.text_section.append(f"move $v0, {return_value}  # Move return value to $v0")
    #         self.free_register(return_value)

    #     # Recursive case handling (Fac_ComputeFac specific logic)
    #     if node["name"] == "ComputeFac":  # Special logic for ComputeFac
    #         self.text_section.append("li $t1, 1          # Load immediate 1")
    #         self.text_section.append("slt $t2, $a0, $t1  # num < 1?")
    #         self.text_section.append("beq $t2, $zero, else_label_1  # If num >= 1, jump to else")

    #         # Base case
    #         self.text_section.append("li $v0, 1          # Return 1 if num < 1")
    #         self.text_section.append("j end_if_label_1")

    #         # Recursive case
    #         self.text_section.append("else_label_1:")
    #         self.text_section.append("lw $t0, 0($sp)     # Load 'num' from stack")
    #         self.text_section.append("sub $a0, $t0, $t1  # Calculate num - 1")
    #         self.text_section.append("jal Fac_ComputeFac # Recursive call")
    #         self.text_section.append("lw $t0, 0($sp)     # Reload 'num' from stack")
    #         self.text_section.append("mul $v0, $t0, $v0  # Multiply num by recursion result")

    #         # End if
    #         self.text_section.append("end_if_label_1:")

    #     # Epilogue: Restore stack and return to the caller
    #     self.text_section.append("lw $ra, 4($sp)       # Restore return address")
    #     self.text_section.append("lw $fp, 8($sp)       # Restore old frame pointer")
    #     self.text_section.append("addiu $sp, $sp, 12   # Restore stack pointer")
    #     self.text_section.append("jr $ra               # Return")

    def generate_command(self, node, current_class=None, param_map=None, local_var_offsets=None):
        logging.debug(f"Generating command: {node['type']}")
        
        if node["type"] == "Print":
            self.generate_print(node, current_class, param_map, local_var_offsets)
        elif node["type"] == "Assignment":
            self.generate_assignment(node, current_class, param_map, local_var_offsets)
        elif node["type"] == "If":
            self.generate_if(node, current_class, param_map, local_var_offsets)
        elif node["type"] == "While":
            self.generate_while(node, current_class, param_map, local_var_offsets)
        elif node["type"] == "Return":
            self.generate_return(node, current_class, param_map, local_var_offsets)
        else:
            raise CodeGenerationError(f"Unsupported command type: {node['type']}", node)

    def generate_print(self, node, current_class=None, param_map=None, local_var_offsets=None):
        logging.debug("Generating Print command.")

        # Evaluate the expression to print
        expression = node["expression"]
        expression_reg = self.generate_expression(expression, current_class)

        if expression["type"] == "Boolean":
            # Printing Booleans
            self.handle_boolean_print(expression)
        elif expression["type"] == "ArrayAccess":
            # Printing Array Elements
            self.handle_array_element_print(expression)
        elif expression["type"] == "Identifier" and expression["var_type"] == "int[]":
            # Printing Entire Array
            self.handle_array_print(expression)
        else:
            # Default: Print integers or other numeric expressions
            self.text_section.append(f"move $a0, {expression_reg}  # Move value to $a0 for printing")
            self.text_section.append("li $v0, 1  # Print integer syscall")
            self.text_section.append("syscall")
            self.free_register(expression_reg)

    def handle_array_element_print(self, expression):
        """
        Generates MIPS code to print a specific array element (arr[i]).
        
        Args:
            expression (dict): The expression representing array access.
        """
        # Evaluate the array element
        element_reg = self.generate_expression(expression, current_class)

        # Move the element value to $a0 for printing
        self.text_section.append(f"move $a0, {element_reg}  # Move array element to $a0")
        self.text_section.append("li $v0, 1  # Print integer syscall")
        self.text_section.append("syscall")

        # Free the register
        self.free_register(element_reg)
        
    def allocate_register(self):
        """
        Allocates a free register from the pool of temporary registers.
        Returns:
            str: The allocated register name.
        Raises:
            CodeGenerationError: If no registers are available.
        """
        for reg in self.registers:
            if reg not in self.used_registers:
                self.used_registers.add(reg)
                return reg
        raise CodeGenerationError("No free registers available.")

    def free_register(self, reg):
        """
        Frees a register, making it available for future use.
        Args:
            reg (str): The register to free.
        """
        if reg in self.used_registers:
            self.used_registers.remove(reg)

    def handle_array_print(self, expression):
        """
        Generates MIPS code to print all elements of an array.
        
        Args:
            expression (dict): The expression representing the array identifier.
        """
        array_reg = self.generate_expression(expression)  # Get array base address
        length_reg = self.allocate_register()

        # Load the array length
        self.text_section.append(f"lw {length_reg}, 0({array_reg})  # Load array length")

        # Print each element
        loop_label = f"print_array_loop_{self.label_counter}"
        end_label = f"print_array_end_{self.label_counter}"
        self.label_counter += 1

        # Loop initialization
        self.text_section.append(f"li $t0, 0  # Initialize index to 0")
        self.text_section.append(f"{loop_label}:")
        self.text_section.append(f"bge $t0, {length_reg}, {end_label}  # Exit loop if index >= length")

        # Load and print the current element
        self.text_section.append(f"mul $t1, $t0, 4  # Calculate offset")
        self.text_section.append(f"addiu $t1, $t1, 4  # Skip length field")
        self.text_section.append(f"add $t1, $t1, {array_reg}  # Compute address of arr[index]")
        self.text_section.append(f"lw $a0, 0($t1)  # Load array element")
        self.text_section.append("li $v0, 1  # Print integer syscall")
        self.text_section.append("syscall")

        # Increment index and loop
        self.text_section.append("addi $t0, $t0, 1  # Increment index")
        self.text_section.append(f"j {loop_label}  # Jump to loop start")
        self.text_section.append(f"{end_label}:")
        
        # Free registers
        self.free_register(array_reg)
        self.free_register(length_reg)

    def generate_assignment(self, node, current_class=None, param_map=None, local_var_offsets=None):
        """
        Generates MIPS code for an assignment command.

        Args:
            node (dict): An 'Assignment' command node.
        """
        logging.debug("Generating Assignment command.")

        # Evaluate the expression and get the result in a register
        value_reg = self.generate_expression(node["value"], current_class, param_map, local_var_offsets)

        # Check if the target is a local variable
        target = node["target"]
        if target in local_var_offsets:
            offset = local_var_offsets[target]
            self.text_section.append(f"sw {value_reg}, {offset}($fp)  # Store value in local variable '{target}'")
        elif target in param_map:
            # Handle parameters if needed
            param_location = param_map[target]
            if param_location.startswith("$"):  # Register-based parameter
                self.text_section.append(f"move {param_location}, {value_reg}  # Store value in parameter '{target}'")
            else:  # Stack-based parameter
                self.text_section.append(f"sw {value_reg}, {param_location}($fp)  # Store value in parameter '{target}'")
        else:
            raise CodeGenerationError(f"Unknown target for assignment: {target}", node)

        # Free the register after use
        self.free_register(value_reg)
        
    def generate_if(self, node, current_class=None, param_map=None, local_var_offsets=None):
        """
        Generates MIPS code for an if statement.

        Args:
            node (dict): An 'If' command node.
        """
        logging.debug("Generating If command.")
        
        # Create unique labels for branching
        self.label_counter += 1
        else_label = f"else_label_{self.label_counter}"
        end_if_label = f"end_if_label_{self.label_counter}"
        
        # Evaluate the condition
        condition_reg = self.generate_expression(node["condition"], current_class, param_map, local_var_offsets)
        
        # Branch to the else_label if the condition is false
        self.text_section.append(f"beq {condition_reg}, $zero, {else_label}  # If condition is false, jump to else")
        self.generate_command(node["if_true"], current_class, param_map, local_var_offsets)
        self.text_section.append(f"j {end_if_label}  # Jump to end of if")
        
        # Generate the false branch (if exists)
        self.text_section.append(f"{else_label}:")
        if "if_false" in node:
            self.generate_command(node["if_false"], current_class, param_map, local_var_offsets)
        
        # End of the if block
        self.text_section.append(f"{end_if_label}:")
        
        # Free the condition register
        self.free_register(condition_reg)
        
    def generate_return(self, node, current_class=None, param_map=None, local_var_offsets=None):
        """
        Generates MIPS code for a return command.

        Args:
            node (dict): A 'Return' command node.
        """
        logging.debug("Generating Return command.")

        # Evaluate the return expression
        return_reg = self.generate_expression(node["value"], current_class)
        
        # Move the return value to $v0
        self.text_section.append(f"move $v0, {return_reg}  # Move return value to $v0")
        
        # Free the register after use
        self.free_register(return_reg)

    def generate_expression(self, node, current_class=None, param_map=None, local_var_offsets=None):
        logging.debug(f"Generating expression: {node['type']}")
        
        if node["type"] == "Number":
            reg = self.allocate_register()
            self.text_section.append(f"li {reg}, {node['value']}  # Load immediate {node['value']}")
            return reg
        elif node["type"] == "Boolean":
            reg = self.allocate_register()
            value = 1 if node["value"] == "true" else 0
            self.text_section.append(f"li {reg}, {value}  # Load boolean value {'true' if value == 1 else 'false'}")
            return reg
        elif node["type"] == "LogicalOp":
            left_reg = self.generate_expression(node["left"], current_class, param_map=None, local_var_offsets=None)
            right_reg = self.generate_expression(node["right"], current_class, param_map=None, local_var_offsets=None)
            reg = self.allocate_register()
            if node["operator"] == "&&":
                self.text_section.append(f"and {reg}, {left_reg}, {right_reg}  # Logical AND")
            else:
                raise CodeGenerationError(f"Unsupported logical operator: {node['operator']}")
            self.free_register(left_reg)
            self.free_register(right_reg)
            return reg
        elif node["type"] == "Identifier":
            var_name = node["name"]
            if var_name in param_map:  # Parameter handling
                reg = self.allocate_register()
                if param_map[var_name].startswith("$"):  # Argument register
                    self.text_section.append(f"move {reg}, {param_map[var_name]}  # Load parameter '{var_name}'")
                else:  # Stack offset
                    self.text_section.append(f"lw {reg}, {param_map[var_name]}($fp)  # Load parameter '{var_name}' from stack")
            elif var_name in local_var_offsets:  # Local variable handling
                reg = self.allocate_register()
                self.text_section.append(f"lw {reg}, {local_var_offsets[var_name]}($fp)  # Load local variable '{var_name}'")
            else:
                raise CodeGenerationError(f"Unknown variable: {var_name}", node)
            return reg
        elif node["type"] == "NewObject":
            class_name = node["class_name"]
            if class_name not in self.symbol_table:
                raise CodeGenerationError(f"Class '{class_name}' is not defined.", node)

            object_size = 0
            current_class = self.symbol_table.get(class_name)
            while current_class:
                object_size += len(current_class["fields"]) * 4
                parent_class = current_class.get("parent")
                current_class = self.symbol_table.get(parent_class)

            self.text_section.append("li $v0, 9  # Syscall for sbrk (memory allocation)")
            self.text_section.append(f"li $a0, {object_size}  # Set allocation size")
            self.text_section.append("syscall")
            
            object_reg = self.allocate_register()
            self.text_section.append(f"move {object_reg}, $v0  # Store allocated address for the object")

            for offset in range(0, object_size, 4):
                self.text_section.append(f"sw $zero, {offset}({object_reg})  # Initialize field at offset {offset} to 0")

            return object_reg
        elif node["type"] == "FieldAccess":
            object_reg = self.generate_expression(node["target"], current_class)  # Get object base address
            class_name = node["target"]["class_name"]  # Get class of the object
            field_name = node["field_name"]

            # Resolve field and its offset
            field_offset = self.resolve_field_offset(class_name, field_name)

            # Load the field value into a register
            field_reg = self.allocate_register()
            self.text_section.append(f"lw {field_reg}, {field_offset}({object_reg})  # Load field '{field_name}'")

            self.free_register(object_reg)
            return field_reg
        elif node["type"] == "ArithmeticOp":
            left_reg = self.generate_expression(node["left"], current_class, param_map, local_var_offsets)
            right_reg = self.generate_expression(node["right"], current_class, param_map, local_var_offsets)
            reg = self.allocate_register()
            operator = {
                "+": "add",
                "-": "sub",
                "*": "mul"
            }.get(node["operator"], None)
            if not operator:
                raise CodeGenerationError(f"Unsupported operator: {node['operator']}")
            self.text_section.append(f"{operator} {reg}, {left_reg}, {right_reg}")
            self.free_register(left_reg)
            self.free_register(right_reg)
            return reg
        elif node["type"] == "ArrayInstantiation":
            # Allocate memory for the array
            size_reg = self.generate_expression(node["size"], current_class)  # Evaluate the size expression
            
            # Multiply the size by 4 (integer size) and add space for the length
            self.text_section.append(f"mul {size_reg}, {size_reg}, 4  # Multiply size by 4 (word size)")
            self.text_section.append(f"addiu {size_reg}, {size_reg}, 4  # Add 4 bytes for the length")
            
            # Use syscall to allocate memory
            self.text_section.append("li $v0, 9  # Syscall for sbrk (memory allocation)")
            self.text_section.append(f"move $a0, {size_reg}  # Set allocation size")
            self.text_section.append("syscall")
            
            # Store the allocated address in a register
            array_reg = self.allocate_register()
            self.text_section.append(f"move {array_reg}, $v0  # Store allocated address")
            
            # Store the array length in the first word
            self.text_section.append(f"sw {size_reg}, 0({array_reg})  # Store array length at the beginning")
            
            self.free_register(size_reg)  # Free the size register
            return array_reg
        elif node["type"] == "ArrayAccess":
            array_reg = self.generate_expression(node["array"], current_class)  # Get array base address
            index_reg = self.generate_expression(node["index"], current_class)  # Get the index value
            
            # Multiply index by 4 (word size) and compute offset
            self.text_section.append(f"mul {index_reg}, {index_reg}, 4  # Multiply index by 4")
            self.text_section.append(f"addiu {index_reg}, {index_reg}, 4  # Add 4 to skip the length field")
            self.text_section.append(f"add {index_reg}, {array_reg}, {index_reg}  # Compute the final address")
            
            # Load the value from the computed address
            value_reg = self.allocate_register()
            self.text_section.append(f"lw {value_reg}, 0({index_reg})  # Load value from array[index]")
            
            self.free_register(array_reg)
            self.free_register(index_reg)
            return value_reg
        elif node["type"] == "ArrayAssignment":
            array_reg = self.generate_expression(node["array"], current_class, param_map, local_var_offsets)  # Get array base address
            index_reg = self.generate_expression(node["index"], current_class, param_map, local_var_offsets)  # Get the index value
            value_reg = self.generate_expression(node["value"], current_class, param_map, local_var_offsets)  # Get the value to assign
            
            # Multiply index by 4 (word size) and compute offset
            self.text_section.append(f"mul {index_reg}, {index_reg}, 4  # Multiply index by 4")
            self.text_section.append(f"addiu {index_reg}, {index_reg}, 4  # Add 4 to skip the length field")
            self.text_section.append(f"add {index_reg}, {array_reg}, {index_reg}  # Compute the final address")
            
            # Store the value at the computed address
            self.text_section.append(f"sw {value_reg}, 0({index_reg})  # Store value into array[index]")
            
            self.free_register(array_reg)
            self.free_register(index_reg)
            self.free_register(value_reg)
        elif node["type"] == "ArrayLength":
            array_reg = self.generate_expression(node["array"])  # Get array base address
            
            # Load the array length (stored in the first word)
            length_reg = self.allocate_register()
            self.text_section.append(f"lw {length_reg}, 0({array_reg})  # Load array length")
            
            self.free_register(array_reg)
            return length_reg
        elif node["type"] == "RelationalOp":
            # Evaluate left and right operands
            left_reg = self.generate_expression(node["left"], current_class, param_map, local_var_offsets)
            right_reg = self.generate_expression(node["right"], current_class, param_map, local_var_offsets)
            result_reg = self.allocate_register()

            # Generate MIPS code based on the operator
            operator = node["operator"]
            if operator == "<":
                self.text_section.append(f"slt {result_reg}, {left_reg}, {right_reg}  # Less than")
            elif operator == "<=":
                self.text_section.append(f"sle {result_reg}, {left_reg}, {right_reg}  # Less than or equal")
            elif operator == ">":
                self.text_section.append(f"sgt {result_reg}, {left_reg}, {right_reg}  # Greater than")
            elif operator == ">=":
                self.text_section.append(f"sge {result_reg}, {left_reg}, {right_reg}  # Greater than or equal")
            elif operator == "==":
                self.text_section.append(f"seq {result_reg}, {left_reg}, {right_reg}  # Equal")
            elif operator == "!=":
                self.text_section.append(f"sne {result_reg}, {left_reg}, {right_reg}  # Not equal")
            else:
                raise CodeGenerationError(f"Unsupported relational operator: {operator}", node)

            # Free the operand registers
            self.free_register(left_reg)
            self.free_register(right_reg)
            
            return result_reg
        elif node["type"] == "This":
            # `this` refers to the current object. In MIPS, it's usually stored in the $a0 register
            # or the object base address is available at the frame pointer.
            reg = self.allocate_register()
            self.text_section.append(f"move {reg}, $a0  # Load 'this' (current object)")
            return reg
        elif node["type"] == "MethodCall":
            # Handle the target (e.g., `this`, `new Fac()`, or variable)
            if node["target"]["type"] == "This":
                if not current_class:
                    raise CodeGenerationError("Cannot resolve 'this' without a current class context.", node)
                object_reg = self.allocate_register()
                self.text_section.append(f"move {object_reg}, $a0  # Load 'this' (current object)")

                # Extract the name of the current class
                if isinstance(current_class, dict):
                    target_class = next(
                        (class_name for class_name, class_data in self.symbol_table.items() if class_data == current_class), 
                        None
                    )
                else:
                    target_class = current_class

                if not target_class or not isinstance(target_class, str):
                    raise CodeGenerationError("Failed to resolve the class name for 'this'.", node)
            elif node["target"]["type"] == "NewObject":
                object_reg = self.generate_expression(node["target"], current_class)  # `new Fac()` handled as object creation
                target_class = node["target"]["class_name"]  # Get the class name from the target
                if isinstance(target_class, dict):  # If a dictionary is erroneously passed, extract its name
                    target_class = target_class.get("name")
            else:
                # Handle other cases (e.g., identifier or field access)
                object_reg = self.generate_expression(node["target"], current_class)
                target_class = node["target"].get("class_name")  # Should reference a string key
                if isinstance(target_class, dict):  # If a dictionary is erroneously passed, extract its name
                    target_class = target_class.get("name")
                    
            # Validate that the class exists in the symbol table
            if target_class not in self.symbol_table:
                raise CodeGenerationError(f"Class '{target_class}' is not defined.", node)

            # Resolve the method's symbol and parameters
            method_name = node["method_name"]
            if method_name not in self.symbol_table[target_class]["methods"]:
                raise CodeGenerationError(f"Method '{method_name}' not found in class '{target_class}'.", node)

            # Evaluate arguments and pass them into registers
            arguments = node["arguments"]
            if arguments["type"] == "ExpressionList":
                arguments = arguments["expressions"]

            # Store evaluated arguments
            arg_regs = []
            for arg_node in arguments:
                arg_reg = self.generate_expression(arg_node, current_class, param_map, local_var_offsets)
                arg_regs.append(arg_reg)

            # Move arguments to registers
            for i, arg_reg in enumerate(arg_regs):
                self.text_section.append(f"move $a{i}, {arg_reg}  # Pass argument {i}")

            # Generate method call
            self.text_section.append(f"jal {target_class}_{method_name}  # Call method '{method_name}'")

            # Free registers after use
            for arg_reg in arg_regs:
                self.free_register(arg_reg)
            self.free_register(object_reg)

            # Return the result in $v0 as the result of the method call
            result_reg = self.allocate_register()
            self.text_section.append(f"move {result_reg}, $v0  # Store return value")
            return result_reg



        elif node["type"] == "Null":
            # Allocate a register and load 0 to represent null
            reg = self.allocate_register()
            self.text_section.append(f"li {reg}, 0  # Load null value (0)")
            return reg
        else:
            raise CodeGenerationError(f"Unsupported expression type: {node['type']}")
        
    def generate_while(self, node, current_class=None, param_map=None, local_var_offsets=None):
        """
        Generates MIPS code for a while loop.
        
        Args:
            node (dict): A 'While' command node.
        """
        logging.debug("Generating While command.")
        
        # Create unique labels for loop start and end
        self.label_counter += 1
        start_label = f"while_start_{self.label_counter}"
        end_label = f"while_end_{self.label_counter}"
        
        # Start of the while loop
        self.text_section.append(f"{start_label}:")
        
        # Evaluate the condition
        condition_reg = self.generate_expression(node["condition"], current_class)
        
        # Branch to the end if condition is false
        self.text_section.append(f"beq {condition_reg}, $zero, {end_label}  # If condition is false, exit loop")
        
        # Generate the loop body
        self.generate_command(node["body"], current_class, param_map, local_var_offsets)
        
        # Jump back to the start of the loop
        self.text_section.append(f"j {start_label}  # Repeat loop")
        
        # End of the while loop
        self.text_section.append(f"{end_label}:")
        
        # Free the condition register
        self.free_register(condition_reg)

    def generate_field_assignment(self, node, current_class=None):
        object_reg = self.generate_expression(node["target"], current_class, param_map, local_var_offsets)
        class_name = node["target"]["class_name"]
        field_name = node["field_name"]
        value_reg = self.generate_expression(node["value"], current_class, param_map, local_var_offsets)

        if class_name not in self.symbol_table:
            raise CodeGenerationError(f"Class '{class_name}' is not defined.", node)
        if field_name not in self.symbol_table[class_name]["fields"]:
            raise CodeGenerationError(f"Field '{field_name}' not found in class '{class_name}'.", node)

        field_offset = list(self.symbol_table[class_name]["fields"].keys()).index(field_name) * 4

        self.text_section.append(f"sw {value_reg}, {field_offset}({object_reg})  # Store value in field '{field_name}'")

        self.free_register(object_reg)
        self.free_register(value_reg)

    def resolve_field_offset(self, class_name, field_name):
        current_class = self.symbol_table.get(class_name)
        offset = 0

        while current_class:
            if field_name in current_class["fields"]:
                # Calculate offset based on the field's position in the class
                field_index = list(current_class["fields"].keys()).index(field_name)
                return offset + (field_index * 4)
            else:
                offset += len(current_class["fields"]) * 4
                parent_class = current_class.get("parent")
                current_class = self.symbol_table.get(parent_class)

        raise CodeGenerationError(f"Field '{field_name}' not found in class hierarchy of '{class_name}'.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

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

    syntax_tree = analyzer.analyze()
    symbol_table = analyzer.symbol_table

    generator = MiniJavaCodeGenerator(syntax_tree, symbol_table)
    try:
        mips_code = generator.generate()
        with open("output.asm", "w") as f:
            f.write(mips_code)
        print("MIPS code generated successfully.")

    except CodeGenerationError as e:
        logging.error(f"Code generation error: {e}")
        
        
        
        
        
        
