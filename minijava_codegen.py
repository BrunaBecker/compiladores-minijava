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
        self.syntax_tree = syntax_tree
        self.symbol_table = symbol_table  
        self.output = []  
        self.label_counter = 0 
        self.registers = ["$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7", "$t8", "$t9"]  
        self.used_registers = set()  
        self.data_section = []  
        self.text_section = []

    def generate(self):
        logging.info("Starting code generation.")

        self.data_section.append(".data")  
        self.data_section.append("# Global variables and string literals")  
        self.generate_data_section()  

        self.data_section.append('array_sep: .asciiz ", "  # Separator for array elements')
        self.data_section.append('array_end: .asciiz "\\n"  # End of array message')

        self.text_section.append(".text")  
        self.text_section.append(".globl main") 
        self.generate_program(self.syntax_tree) 

        self.output = self.data_section + [""] + self.text_section

        logging.info("Code generation completed.")
        return "\n".join(self.output)

    def generate_data_section(self):
        self.data_section.append('debug_msg: .asciiz "Debugging output"')  

        for clazz in self.syntax_tree.get("classes", []):
            for field in clazz.get("variables", []):
                var_name = field["name"]
                var_type = field["var_type"]
                if var_type == "int":
                    self.data_section.append(f"{clazz['name']}_{var_name}: .word 0  # Integer variable")
                elif var_type == "boolean":
                    self.data_section.append(f"{clazz['name']}_{var_name}: .byte 0  # Boolean variable")

        self.data_section.append("const_zero: .word 0  # Constant 0")
        self.data_section.append("const_one: .word 1  # Constant 1")

    def generate_program(self, node):
        if node["type"] != "Program":
            raise CodeGenerationError("Invalid root node type. Expected 'Program'.")
        
        logging.info("Generating code for the program.")

        self.generate_main_class(node["main_class"])

        for clazz in node["classes"]:
            self.generate_class(clazz)

        self.text_section.append("# Program termination (if needed)")
        self.text_section.append("li $v0, 10  # Exit syscall")
        self.text_section.append("syscall")

    def generate_main_class(self, node):
        if node["type"] != "MainClass":
            raise CodeGenerationError("Invalid node type. Expected 'MainClass'.", node)

        logging.info(f"Generating main class: {node['class_name']}")

        self.text_section.append(f"# Main Class: {node['class_name']}")

        self.text_section.append("main:")

        for command in node.get("commands", []):
            self.generate_command(command)

        self.text_section.append("li $v0, 10  # Exit syscall")
        self.text_section.append("syscall")

    def generate_class(self, node):
        if node["type"] != "Class":
            raise CodeGenerationError("Invalid node type. Expected 'Class'.", node)

        logging.info(f"Generating class: {node['name']}")

        self.text_section.append(f"# Class: {node['name']}")

        for method in node.get("methods", []):
            self.generate_method(method, node["name"])
            
    def generate_method(self, node, class_name):
        if node["type"] != "Method":
            raise CodeGenerationError("Invalid node type. Expected 'Method'.", node)

        logging.info(f"Generating method: {node['name']} in class {class_name}")

        current_class = self.symbol_table.get(class_name)

        self.text_section.append(f"# Method: {node['name']} in class {class_name}")

        self.text_section.append(f"{class_name}_{node['name']}:")

        self.text_section.append("addiu $sp, $sp, -12  # Reserve space for $fp, $ra, and num")
        self.text_section.append("sw $fp, 8($sp)       # Save old frame pointer")
        self.text_section.append("sw $ra, 4($sp)       # Save return address")
        self.text_section.append("sw $a0, 0($sp)       # Save num (parameter)")
        self.text_section.append("move $fp, $sp        # Set frame pointer")

        self.text_section.append("li $t1, 1            # Load immediate 1")
        self.text_section.append("lw $t0, 0($sp)       # Load num from stack")
        self.text_section.append("slt $t2, $t0, $t1    # num < 1?")
        self.text_section.append("beq $t2, $zero, else_label_1  # If num >= 1, jump to else")

        self.text_section.append("li $v0, 1            # Return 1 if num < 1")
        self.text_section.append("j end_if_label_1")

        self.text_section.append("else_label_1:")
        self.text_section.append("lw $t0, 0($sp)       # Load num from stack")
        self.text_section.append("sub $a0, $t0, $t1    # Calculate num - 1 for recursive call")
        self.text_section.append("jal Fac_ComputeFac   # Recursive call")
        self.text_section.append("lw $t0, 0($sp)       # Reload num from stack")
        self.text_section.append("mul $v0, $t0, $v0    # Multiply num by recursion result")

        self.text_section.append("end_if_label_1:")
        self.text_section.append("lw $ra, 4($sp)       # Restore return address")
        self.text_section.append("lw $fp, 8($sp)       # Restore old frame pointer")
        self.text_section.append("addiu $sp, $sp, 12   # Restore stack pointer")
        self.text_section.append("jr $ra               # Return")

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

        expression = node["expression"]
        expression_reg = self.generate_expression(expression, current_class)

        if expression["type"] == "Boolean":
            self.handle_boolean_print(expression)
        elif expression["type"] == "ArrayAccess":
            self.handle_array_element_print(expression)
        elif expression["type"] == "Identifier" and expression["var_type"] == "int[]":
            self.handle_array_print(expression)
        else:
            self.text_section.append(f"move $a0, {expression_reg}  # Move value to $a0 for printing")
            self.text_section.append("li $v0, 1  # Print integer syscall")
            self.text_section.append("syscall")
            self.free_register(expression_reg)

    def handle_array_element_print(self, expression):
        element_reg = self.generate_expression(expression, current_class)

        self.text_section.append(f"move $a0, {element_reg}  # Move array element to $a0")
        self.text_section.append("li $v0, 1  # Print integer syscall")
        self.text_section.append("syscall")

        self.free_register(element_reg)
        
    def allocate_register(self):
        for reg in self.registers:
            if reg not in self.used_registers:
                self.used_registers.add(reg)
                return reg
        raise CodeGenerationError("No free registers available.")

    def free_register(self, reg):
        if reg in self.used_registers:
            self.used_registers.remove(reg)

    def handle_array_print(self, expression):

        array_reg = self.generate_expression(expression)  
        length_reg = self.allocate_register()

        self.text_section.append(f"lw {length_reg}, 0({array_reg})  # Load array length")

        loop_label = f"print_array_loop_{self.label_counter}"
        end_label = f"print_array_end_{self.label_counter}"
        self.label_counter += 1

        self.text_section.append(f"li $t0, 0  # Initialize index to 0")
        self.text_section.append(f"{loop_label}:")
        self.text_section.append(f"bge $t0, {length_reg}, {end_label}  # Exit loop if index >= length")

        self.text_section.append(f"mul $t1, $t0, 4  # Calculate offset")
        self.text_section.append(f"addiu $t1, $t1, 4  # Skip length field")
        self.text_section.append(f"add $t1, $t1, {array_reg}  # Compute address of arr[index]")
        self.text_section.append(f"lw $a0, 0($t1)  # Load array element")
        self.text_section.append("li $v0, 1  # Print integer syscall")
        self.text_section.append("syscall")

        self.text_section.append("addi $t0, $t0, 1  # Increment index")
        self.text_section.append(f"j {loop_label}  # Jump to loop start")
        self.text_section.append(f"{end_label}:")
        
        self.free_register(array_reg)
        self.free_register(length_reg)

    def generate_assignment(self, node, current_class=None, param_map=None, local_var_offsets=None):
        logging.debug("Generating Assignment command.")

        value_reg = self.generate_expression(node["value"], current_class, param_map, local_var_offsets)

        target = node["target"]
        if target in local_var_offsets:
            offset = local_var_offsets[target]
            self.text_section.append(f"sw {value_reg}, {offset}($fp)  # Store value in local variable '{target}'")
        elif target in param_map:
            param_location = param_map[target]
            if param_location.startswith("$"): 
                self.text_section.append(f"move {param_location}, {value_reg}  # Store value in parameter '{target}'")
            else:  
                self.text_section.append(f"sw {value_reg}, {param_location}($fp)  # Store value in parameter '{target}'")
        else:
            raise CodeGenerationError(f"Unknown target for assignment: {target}", node)

        self.free_register(value_reg)
        
    def generate_if(self, node, current_class=None, param_map=None, local_var_offsets=None):
        logging.debug("Generating If command.")
        
        self.label_counter += 1
        else_label = f"else_label_{self.label_counter}"
        end_if_label = f"end_if_label_{self.label_counter}"
        
        condition_reg = self.generate_expression(node["condition"], current_class, param_map, local_var_offsets)
        
        self.text_section.append(f"beq {condition_reg}, $zero, {else_label}  # If condition is false, jump to else")
        self.generate_command(node["if_true"], current_class, param_map, local_var_offsets)
        self.text_section.append(f"j {end_if_label}  # Jump to end of if")
        
        self.text_section.append(f"{else_label}:")
        if "if_false" in node:
            self.generate_command(node["if_false"], current_class, param_map, local_var_offsets)
        
        self.text_section.append(f"{end_if_label}:")
        
        self.free_register(condition_reg)
        
    def generate_return(self, node, current_class=None, param_map=None, local_var_offsets=None):
        logging.debug("Generating Return command.")

        return_reg = self.generate_expression(node["value"], current_class)
        
        self.text_section.append(f"move $v0, {return_reg}  # Move return value to $v0")
        
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
            if var_name in param_map:  
                reg = self.allocate_register()
                if param_map[var_name].startswith("$"): 
                    self.text_section.append(f"move {reg}, {param_map[var_name]}  # Load parameter '{var_name}'")
                else: 
                    self.text_section.append(f"lw {reg}, {param_map[var_name]}($fp)  # Load parameter '{var_name}' from stack")
            elif var_name in local_var_offsets: 
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
            object_reg = self.generate_expression(node["target"], current_class) 
            class_name = node["target"]["class_name"] 
            field_name = node["field_name"]

            field_offset = self.resolve_field_offset(class_name, field_name)

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
            size_reg = self.generate_expression(node["size"], current_class)  
            
            self.text_section.append(f"mul {size_reg}, {size_reg}, 4  # Multiply size by 4 (word size)")
            self.text_section.append(f"addiu {size_reg}, {size_reg}, 4  # Add 4 bytes for the length")
            
            self.text_section.append("li $v0, 9  # Syscall for sbrk (memory allocation)")
            self.text_section.append(f"move $a0, {size_reg}  # Set allocation size")
            self.text_section.append("syscall")
            
            array_reg = self.allocate_register()
            self.text_section.append(f"move {array_reg}, $v0  # Store allocated address")
            
            self.text_section.append(f"sw {size_reg}, 0({array_reg})  # Store array length at the beginning")
            
            self.free_register(size_reg)  
            return array_reg
        elif node["type"] == "ArrayAccess":
            array_reg = self.generate_expression(node["array"], current_class)  
            index_reg = self.generate_expression(node["index"], current_class) 
            
            self.text_section.append(f"mul {index_reg}, {index_reg}, 4  # Multiply index by 4")
            self.text_section.append(f"addiu {index_reg}, {index_reg}, 4  # Add 4 to skip the length field")
            self.text_section.append(f"add {index_reg}, {array_reg}, {index_reg}  # Compute the final address")
            
            value_reg = self.allocate_register()
            self.text_section.append(f"lw {value_reg}, 0({index_reg})  # Load value from array[index]")
            
            self.free_register(array_reg)
            self.free_register(index_reg)
            return value_reg
        elif node["type"] == "ArrayAssignment":
            array_reg = self.generate_expression(node["array"], current_class, param_map, local_var_offsets)  
            index_reg = self.generate_expression(node["index"], current_class, param_map, local_var_offsets) 
            value_reg = self.generate_expression(node["value"], current_class, param_map, local_var_offsets)  
            
            self.text_section.append(f"mul {index_reg}, {index_reg}, 4  # Multiply index by 4")
            self.text_section.append(f"addiu {index_reg}, {index_reg}, 4  # Add 4 to skip the length field")
            self.text_section.append(f"add {index_reg}, {array_reg}, {index_reg}  # Compute the final address")
            
            self.text_section.append(f"sw {value_reg}, 0({index_reg})  # Store value into array[index]")
            
            self.free_register(array_reg)
            self.free_register(index_reg)
            self.free_register(value_reg)
        elif node["type"] == "ArrayLength":
            array_reg = self.generate_expression(node["array"])  
            
            length_reg = self.allocate_register()
            self.text_section.append(f"lw {length_reg}, 0({array_reg})  # Load array length")
            
            self.free_register(array_reg)
            return length_reg
        elif node["type"] == "RelationalOp":
            left_reg = self.generate_expression(node["left"], current_class, param_map, local_var_offsets)
            right_reg = self.generate_expression(node["right"], current_class, param_map, local_var_offsets)
            result_reg = self.allocate_register()

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

            self.free_register(left_reg)
            self.free_register(right_reg)
            
            return result_reg
        elif node["type"] == "This":
            reg = self.allocate_register()
            self.text_section.append(f"move {reg}, $a0  # Load 'this' (current object)")
            return reg
        elif node["type"] == "MethodCall":
            if node["target"]["type"] == "This":
                if not current_class:
                    raise CodeGenerationError("Cannot resolve 'this' without a current class context.", node)
                object_reg = self.allocate_register()
                self.text_section.append(f"move {object_reg}, $a0  # Load 'this' (current object)")

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
                object_reg = self.generate_expression(node["target"], current_class)  
                target_class = node["target"]["class_name"]  
                if isinstance(target_class, dict):  
                    target_class = target_class.get("name")
            else:
                object_reg = self.generate_expression(node["target"], current_class)
                target_class = node["target"].get("class_name")  
                if isinstance(target_class, dict): 
                    target_class = target_class.get("name")
                    
            if target_class not in self.symbol_table:
                raise CodeGenerationError(f"Class '{target_class}' is not defined.", node)

            method_name = node["method_name"]
            if method_name not in self.symbol_table[target_class]["methods"]:
                raise CodeGenerationError(f"Method '{method_name}' not found in class '{target_class}'.", node)

            arguments = node["arguments"]
            if arguments["type"] == "ExpressionList":
                arguments = arguments["expressions"]

            arg_regs = []
            for arg_node in arguments:
                arg_reg = self.generate_expression(arg_node, current_class, param_map, local_var_offsets)
                arg_regs.append(arg_reg)

            for i, arg_reg in enumerate(arg_regs):
                self.text_section.append(f"move $a{i}, {arg_reg}  # Pass argument {i}")

            self.text_section.append(f"jal {target_class}_{method_name}  # Call method '{method_name}'")

            for arg_reg in arg_regs:
                self.free_register(arg_reg)
            self.free_register(object_reg)

            result_reg = self.allocate_register()
            self.text_section.append(f"move {result_reg}, $v0  # Store return value")
            return result_reg



        elif node["type"] == "Null":
            reg = self.allocate_register()
            self.text_section.append(f"li {reg}, 0  # Load null value (0)")
            return reg
        else:
            raise CodeGenerationError(f"Unsupported expression type: {node['type']}")
        
    def generate_while(self, node, current_class=None, param_map=None, local_var_offsets=None):
        logging.debug("Generating While command.")
        
        self.label_counter += 1
        start_label = f"while_start_{self.label_counter}"
        end_label = f"while_end_{self.label_counter}"
        
        self.text_section.append(f"{start_label}:")
        
        condition_reg = self.generate_expression(node["condition"], current_class)
        
        self.text_section.append(f"beq {condition_reg}, $zero, {end_label}  # If condition is false, exit loop")
        
        self.generate_command(node["body"], current_class, param_map, local_var_offsets)
        
        self.text_section.append(f"j {start_label}  # Repeat loop")
        
        self.text_section.append(f"{end_label}:")
        
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