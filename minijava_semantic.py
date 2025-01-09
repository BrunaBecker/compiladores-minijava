from minijava_scanner import MiniJavaScanner
from minijava_parser import MiniJavaParserLL1
import logging

class SemanticError(Exception):
    pass

class MiniJavaSemanticAnalyzer:
    def __init__(self, syntax_tree):
        self.syntax_tree = syntax_tree
        self.symbol_table = {}

    def analyze(self):
        self.collect_declarations(self.syntax_tree)
        
        logging.info("Symbol Table After First Pass (Declaration Collection):")
        logging.debug(self.symbol_table)
        
        self.validate_program(self.syntax_tree)
        return self.syntax_tree

    def collect_declarations(self, node):
        if node["type"] == "Program":
            main_class_name = node["main_class"]["class_name"]
            if main_class_name not in self.symbol_table:
                self.symbol_table[main_class_name] = {"fields": {}, "methods": {}, "extends": None}
            
            for clazz in node["classes"]:
                class_name = clazz["name"]
                if class_name not in self.symbol_table:
                    self.symbol_table[class_name] = {
                        "fields": {},
                        "methods": {},
                        "extends": clazz.get("extends")
                    }
                
                for var in clazz.get("fields", []):
                    self.symbol_table[class_name]["fields"][var["name"]] = var["var_type"]
                
                for method in clazz["methods"]:
                    method_name = method["name"]
                    if method_name in self.symbol_table[class_name]["methods"]:
                        raise SemanticError(f"Duplicate method name '{method_name}' in class '{class_name}'.")
                    self.symbol_table[class_name]["methods"][method_name] = {
                        "parameters": {param["name"]: param["param_type"] for param in method["parameters"]},
                        "return_type": method["return_type"]
                    }

    def validate_program(self, node):
        if node["type"] == "Program":
            self.validate_main_class(node["main_class"])
            
            for clazz in node["classes"]:
                self.validate_class(clazz)

    def validate_main_class(self, node):
        if node["type"] != "MainClass":
            raise SemanticError(f"Expected 'MainClass', but got {node['type']}")
        for command in node["commands"]:
            self.check_command(command, {"current_class": node["class_name"]})

    def validate_class(self, node):
        class_name = node["name"]
        for method in node["methods"]:
            self.validate_method(method, class_name)

    def validate_method(self, method, class_name):
        method_table = {"current_class": class_name}

        for param in method["parameters"]:
            param_name = param["name"]
            method_table[param_name] = param["param_type"]

        for var in method["local_variables"]:
            var_name = var["name"]
            if var_name in method_table:
                raise SemanticError(f"Duplicate local variable '{var_name}' in method '{method['name']}'.")
            method_table[var_name] = var["var_type"]

        for command in method["commands"]:
            self.check_command(command, method_table)

        if "return_expression" in method:
            return_type = self.get_expression_type(method["return_expression"], method_table)
            if return_type != method["return_type"]:
                raise SemanticError(
                    f"Return type mismatch in method '{method['name']}'. "
                    f"Expected '{method['return_type']}', got '{return_type}'."
                )

    def check_command(self, node, method_table=None):
        if method_table is None:
            method_table = {}  

        logging.debug(f"Processing command: {node['type']}")

        if node["type"] == "Assignment":
            var_name = node["target"]
            if var_name not in method_table:
                raise SemanticError(f"Variable '{var_name}' is not declared in the current or outer scope.")
            self.check_expression(node["value"], method_table)

        elif node["type"] == "If":
            self.check_expression(node["condition"], method_table)
            self.check_command(node["if_true"], method_table)
            if "if_false" in node:
                self.check_command(node["if_false"], method_table)

        elif node["type"] == "While":
            self.check_expression(node["condition"], method_table)
            self.check_command(node["body"], method_table)

        elif node["type"] == "Print":
            self.check_expression(node["expression"], method_table)

        elif node["type"] == "Return":
            self.check_expression(node["value"], method_table)

        elif node["type"] == "Block":
            for command in node["commands"]:
                self.check_command(command, method_table)

        elif node["type"] == "MethodCall":
            logging.debug(f"Validating method call: {node['method_name']} with arguments {node['arguments']}")
            self.validate_method_call(node, method_table)

        else:
            raise SemanticError(f"Unsupported command type: {node['type']}")

        if "expression" in node and node["type"] != "Print": 
            node["expression"] = self.simplify_expression(node["expression"])

    def check_expression(self, expression, method_table):
        if expression["type"] == "MethodCall":
            self.validate_method_call(expression, method_table)

        elif expression["type"] in ["ArithmeticOp", "RelationalOp", "LogicalOp"]:
            self.check_expression(expression["left"], method_table)
            self.check_expression(expression["right"], method_table)

        elif expression["type"] == "UnaryOp":
            self.check_expression(expression["operand"], method_table)

        elif expression["type"] == "Identifier":
            if expression["name"] not in method_table:
                raise SemanticError(f"Variable '{expression['name']}' is not declared.")

        elif expression["type"] == "Number":
            pass

        elif expression["type"] == "Boolean":
            pass

        elif expression["type"] == "NewObject":
            class_name = expression["class_name"]
            if class_name not in self.symbol_table:
                raise SemanticError(f"Class '{class_name}' is not defined.")

        elif expression["type"] == "This":
            if "current_class" not in method_table:
                raise SemanticError("'this' cannot be used outside a class context.")

        elif expression["type"] == "ArrayAccess":
            self.check_expression(expression["array"], method_table)
            self.check_expression(expression["index"], method_table)

        elif expression["type"] == "ArrayLength":
            self.check_expression(expression["array"], method_table)

        elif expression["type"] == "ArrayInstantiation":
            self.check_expression(expression["size"], method_table)

        elif expression["type"] == "ExpressionList":
            for expr in expression["expressions"]:
                self.check_expression(expr, method_table)

        else:
            raise SemanticError(f"Unsupported expression type: {expression['type']}")

    def validate_method_call(self, node, method_table):
        target = node["target"]
        method_name = node["method_name"]
        arguments = node["arguments"]["expressions"]

        if target["type"] == "NewObject":
            class_name = target["class_name"]
        elif target["type"] == "This":
            class_name = method_table.get("current_class")
        else:
            raise SemanticError(f"Unsupported method call target: {target}")

        logging.debug(f"Validating method call '{method_name}' in class '{class_name}'")
        logging.info(f"Symbol Table Entry for Class '{class_name}':")
        logging.debug(self.symbol_table.get(class_name, "Class not found"))

        if class_name not in self.symbol_table:
            raise SemanticError(f"Class '{class_name}' not found.")

        if method_name not in self.symbol_table[class_name]["methods"]:
            raise SemanticError(f"Method '{method_name}' not found in class '{class_name}'.")

        expected_parameters = self.symbol_table[class_name]["methods"][method_name]["parameters"]

        if len(arguments) != len(expected_parameters):
            raise SemanticError(
                f"Method '{method_name}' expects {len(expected_parameters)} arguments, "
                f"but {len(arguments)} were provided."
            )

        for i, (arg, (param_name, param_type)) in enumerate(zip(arguments, expected_parameters.items())):
            arg_type = self.get_expression_type(arg, method_table)
            if arg_type != param_type:
                raise SemanticError(
                    f"Argument {i + 1} of method '{method_name}' is of type '{arg_type}', "
                    f"but expected '{param_type}'."
                )

    def get_expression_type(self, expr, method_table):
        if expr["type"] == "Constant":
            return "int"  
        elif expr["type"] == "Variable":
            var_name = expr["name"]
            if var_name in method_table:
                return method_table[var_name]
            elif var_name in self.symbol_table[class_name]["fields"]:
                return self.symbol_table[class_name]["fields"][var_name]
            else:
                raise SemanticError(f"Variable '{var_name}' is not declared.")
        elif expr["type"] == "BinaryOperation":
            left_type = self.get_expression_type(expr["left"], method_table)
            right_type = self.get_expression_type(expr["right"], method_table)
            if left_type == right_type == "int":
                return "int"  
            else:
                raise SemanticError(f"Incompatible types in binary operation: {left_type} and {right_type}")
        elif expr["type"] == "FunctionCall":
            class_name = expr["target_class"]
            method_name = expr["method"]
            if class_name in self.symbol_table and method_name in self.symbol_table[class_name]["methods"]:
                return self.symbol_table[class_name]["methods"][method_name].get("return_type", "void")
            else:
                raise SemanticError(f"Method '{method_name}' not found in class '{class_name}'.")
        elif expr["type"] == "Number":
            return "int"
        elif expr["type"] == "Identifier":
            var_name = expr["name"]
            if var_name in method_table:
                return method_table[var_name]
            else:
                raise SemanticError(f"Variable '{var_name}' is not declared.")
        elif expr["type"] == "ArithmeticOp":
            left_type = self.get_expression_type(expr["left"], method_table)
            right_type = self.get_expression_type(expr["right"], method_table)
            if left_type == right_type == "int":
                return "int"
            else:
                raise SemanticError(f"Incompatible types in arithmetic operation: {left_type} and {right_type}")
        else:
            raise SemanticError(f"Unsupported expression type: {expr['type']}")

    def simplify_expression(self, expr):
        if expr["type"] == "BinaryOperation":
            left = self.simplify_expression(expr["left"])
            right = self.simplify_expression(expr["right"])

            if left["type"] == "Constant" and right["type"] == "Constant":
                value = self.evaluate_binary_operation(left["value"], right["value"], expr["operator"])
                return {"type": "Constant", "value": value}

            return {
                "type": "BinaryOperation",
                "left": left,
                "right": right,
                "operator": expr["operator"],
            }
        elif expr["type"] == "Constant":
            return expr  
        else:
            return expr  
        
    def evaluate_binary_operation(self, left, right, operator):
        if operator == "+":
            return left + right
        elif operator == "-":
            return left - right
        elif operator == "*":
            return left * right
        elif operator == "&&":
            return left and right
        elif operator == "<":
            return left < right
        elif operator == ">":
            return left > right
        elif operator == "==":
            return left == right
        elif operator == "!=":
            return left != right
        else:
            raise SemanticError(f"Unsupported operator '{operator}'")
        
    def resolve_inheritance(self):
        for class_name in self.symbol_table:
            logging.info(f"Resolving inheritance for class '{class_name}'")
            self.resolve_class_inheritance(class_name, set())

    def resolve_class_inheritance(self, class_name, visited):
        if class_name in visited:
            raise SemanticError(f"Cyclic inheritance detected in class '{class_name}'.")
        visited.add(class_name)

        parent_name = self.symbol_table[class_name]["extends"]
        if parent_name:
            if parent_name not in self.symbol_table:
                raise SemanticError(f"Class '{parent_name}', extended by '{class_name}', is not defined.")

            self.resolve_class_inheritance(parent_name, visited)

            parent = self.symbol_table[parent_name]
            child = self.symbol_table[class_name]

            for field, field_type in parent["fields"].items():
                if field not in child["fields"]:
                    child["fields"][field] = field_type

            for method, method_data in parent["methods"].items():
                if method not in child["methods"]:
                    child["methods"][method] = method_data
                else:
                    self.check_method_override(class_name, method, method_data, child["methods"][method])

    def check_method_override(self, class_name, method_name, parent_method, child_method):
        if parent_method["return_type"] != child_method["return_type"]:
            raise SemanticError(
                f"Method '{method_name}' in class '{class_name}' overrides with incompatible return type. "
                f"Expected '{parent_method['return_type']}', got '{child_method['return_type']}'."
            )

        if len(parent_method["parameters"]) != len(child_method["parameters"]):
            raise SemanticError(
                f"Method '{method_name}' in class '{class_name}' overrides with incompatible parameter count."
            )

        for (param_name, param_type), (child_param_name, child_param_type) in zip(
            parent_method["parameters"].items(), child_method["parameters"].items()
        ):
            if param_type != child_param_type:
                raise SemanticError(
                    f"Method '{method_name}' in class '{class_name}' overrides parameter '{param_name}' "
                    f"with incompatible type. Expected '{param_type}', got '{child_param_type}'."
                )


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    
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
    
    logging.info("Syntax Tree:")
    logging.debug(syntax_tree)  

    analyzer = MiniJavaSemanticAnalyzer(syntax_tree)
    try:
        syntax_tree = analyzer.analyze()
        logging.info("Semantic analysis completed successfully.")
        
        logging.info("Symbol Table After Semantic Analysis:")
        logging.debug(analyzer.symbol_table)  
    except SemanticError as e:
        logging.error(f"Semantic error: {e}", exc_info=True)
        
    print("\n\n\n")

    print(syntax_tree)