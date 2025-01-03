from minijava_scanner import MiniJavaScanner
import json

class ParserError(Exception):
    pass

def print_syntax_tree(node, prefix="", is_last=True):
    connector = "└── " if is_last else "├── "
    if isinstance(node, dict):
        node_type = node.get("type", "Unknown")
        print(f"{prefix}{connector}{node_type}")
        prefix += "    " if is_last else "│   "
        keys = [k for k in node.keys() if k != "type"]
        for i, key in enumerate(keys):
            is_last_key = i == len(keys) - 1
            print(f"{prefix}{'└── ' if is_last_key else '├── '}{key}:")
            print_syntax_tree(node[key], prefix + ("    " if is_last_key else "│   "), is_last_key)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            is_last_item = i == len(node) - 1
            print_syntax_tree(item, prefix, is_last_item)
    else:
        print(f"{prefix}{connector}{node}")


class MiniJavaParserLL1:
    def __init__(self, tokens):
        self.tokens = tokens
        self.current_index = 0

    def current_token(self):
        return self.tokens[self.current_index] if self.current_index < len(self.tokens) else None

    def consume(self, expected_type=None, expected_value=None):
        token = self.current_token()
        if not token:
            raise ParserError(f"Unexpected end of input, expected {expected_type or expected_value}")
        if expected_type and token[0] != expected_type:
            raise ParserError(f"Expected token type {expected_type}, but got {token[0]} : {token[1]}")
        if expected_value and token[1] != expected_value:
            raise ParserError(f"Expected token value '{expected_value}', but got '{token[1]}'")
        self.current_index += 1
        return token

    def parse_program(self):
        """
        PROG -> MAIN {CLASSE}
        """
        main_class = self.parse_main()
        classes = []
        while self.current_token():
            classes.append(self.parse_class())
        return {"type": "Program", "main_class": main_class, "classes": classes}

    def parse_main(self):
        """
        MAIN -> class id '{' public static void main '(' String '[' ']' id ')' '{' CMD '}' '}'
        """
        self.consume("RESERVED", "class")
        class_name = self.consume("IDENTIFIER")[1]
        self.consume("PUNCTUATION", "{")
        self.consume("RESERVED", "public")
        self.consume("RESERVED", "static")
        self.consume("RESERVED", "void")
        self.consume("RESERVED", "main")
        self.consume("PUNCTUATION", "(")
        self.consume("RESERVED", "String")
        self.consume("PUNCTUATION", "[")
        self.consume("PUNCTUATION", "]")
        arg_name = self.consume("IDENTIFIER")[1]
        self.consume("PUNCTUATION", ")")
        self.consume("PUNCTUATION", "{")
        commands = self.parse_commands()
        self.consume("PUNCTUATION", "}")
        self.consume("PUNCTUATION", "}")
        return {"type": "MainClass", "class_name": class_name, "argument_name": arg_name, "commands": commands}

    def parse_params(self):
        """
        PARAMS -> TIPO id {, TIPO id}
        """
        parameters = []

        # Primeiro parâmetro
        param_type = self.parse_type()
        param_name = self.consume("IDENTIFIER")[1]
        parameters.append({"type": "Parameter", "param_type": param_type, "name": param_name})

        # Parâmetros adicionais, separados por vírgula
        while self.current_token() and self.current_token()[1] == ",":
            self.consume("PUNCTUATION", ",")
            param_type = self.parse_type()
            param_name = self.consume("IDENTIFIER")[1]
            parameters.append({"type": "Parameter", "param_type": param_type, "name": param_name})

        return parameters


    def parse_class(self):
        """
        CLASSE -> class id [extends id] '{' {VAR} {METODO} '}'
        """
        self.consume("RESERVED", "class")
        class_name = self.consume("IDENTIFIER")[1]
        parent_name = None
        if self.current_token() and self.current_token()[1] == "extends":
            self.consume("RESERVED", "extends")
            parent_name = self.consume("IDENTIFIER")[1]
        self.consume("PUNCTUATION", "{")
        variables = []
        methods = []
        while self.current_token() and self.current_token()[1] not in {"}"}:
            if self.current_token()[1] == "public":
                methods.append(self.parse_method())
            else:
                variables.append(self.parse_variable())
        self.consume("PUNCTUATION", "}")
        return {"type": "Class", "name": class_name, "parent": parent_name, "variables": variables, "methods": methods}

    def parse_type(self):
        """
        TIPO -> int '[' ']' | boolean | int | id
        """
        token = self.consume("RESERVED")
        
        # Tipo `int[]`
        if token[1] == "int" and self.current_token() and self.current_token()[1] == "[":
            self.consume("PUNCTUATION", "[")
            self.consume("PUNCTUATION", "]")
            return "int[]"

        # Tipos `int` ou `boolean`
        if token[1] in {"int", "boolean"}:
            return token[1]

        # Tipo como identificador (nome de classe)
        if token[0] == "IDENTIFIER":
            return token[1]

        raise ParserError(f"Unexpected token in type: {token}")


    def parse_variable(self):
        """
        VAR -> TIPO id ;
        """
        var_type = self.parse_type()
        var_name = self.consume("IDENTIFIER")[1]
        self.consume("PUNCTUATION", ";")
        return {"type": "Variable", "var_type": var_type, "name": var_name}

    def parse_method(self):
        """
        METODO -> public TIPO id '(' [PARAMS] ')' '{' {VAR} {CMD} return EXP ; '}'
        """
        self.consume("RESERVED", "public")
        return_type = self.parse_type()
        method_name = self.consume("IDENTIFIER")[1]
        self.consume("PUNCTUATION", "(")
        parameters = self.parse_params() if self.current_token() and self.current_token()[0] != "PUNCTUATION" else []
        self.consume("PUNCTUATION", ")")
        self.consume("PUNCTUATION", "{")
        local_variables = []
        commands = []
        while self.current_token() and self.current_token()[1] != "return":
            if self.current_token()[0] == "RESERVED" and self.current_token()[1] in {"int", "boolean"}:
                local_variables.append(self.parse_variable())
            else:
                commands.append(self.parse_command())
        self.consume("RESERVED", "return")
        return_expression = self.parse_expression()
        self.consume("PUNCTUATION", ";")
        self.consume("PUNCTUATION", "}")
        return {
            "type": "Method",
            "return_type": return_type,
            "name": method_name,
            "parameters": parameters,
            "local_variables": local_variables,
            "commands": commands,
            "return_expression": return_expression,
        }

    def parse_commands(self):
        """
        CMD -> {CMD}
        """
        commands = []
        while self.current_token() and self.current_token()[1] != "}":
            commands.append(self.parse_command())
        return commands

    def parse_command(self):
        """
        CMD -> '{' {CMD} '}' 
             | id = EXP ;
             | id '[' EXP ']' = EXP ;
             | System.out.println '(' EXP ')' ;
             | if '(' EXP ')' CMD [else CMD]
             | while '(' EXP ')' CMD
        """
        token = self.current_token()

        # Bloco de comandos: '{' {CMD} '}'
        if token[1] == "{":
            self.consume("PUNCTUATION", "{")
            commands = self.parse_commands()
            self.consume("PUNCTUATION", "}")
            return {"type": "Block", "commands": commands}

        # Comando de impressão: System.out.println '(' EXP ')'
        elif token[1] == "System.out.println":
            self.consume("RESERVED", "System.out.println")
            self.consume("PUNCTUATION", "(")
            expression = self.parse_expression()
            self.consume("PUNCTUATION", ")")
            self.consume("PUNCTUATION", ";")
            return {"type": "Print", "expression": expression}

        # Comando condicional: if '(' EXP ')' CMD [else CMD]
        elif token[1] == "if":
            self.consume("RESERVED", "if")
            self.consume("PUNCTUATION", "(")
            condition = self.parse_expression()
            self.consume("PUNCTUATION", ")")
            if_true = self.parse_command()
            if_false = None
            if self.current_token() and self.current_token()[1] == "else":
                self.consume("RESERVED", "else")
                if_false = self.parse_command()
            return {"type": "If", "condition": condition, "if_true": if_true, "if_false": if_false}

        # Comando de repetição: while '(' EXP ')' CMD
        elif token[1] == "while":
            self.consume("RESERVED", "while")
            self.consume("PUNCTUATION", "(")
            condition = self.parse_expression()
            self.consume("PUNCTUATION", ")")
            body = self.parse_command()
            return {"type": "While", "condition": condition, "body": body}

        # Atribuição: id = EXP ;
        elif token[0] == "IDENTIFIER":
            identifier = self.consume("IDENTIFIER")[1]
            if self.current_token() and self.current_token()[1] == "=":
                self.consume("OPERATOR", "=")
                value = self.parse_expression()
                self.consume("PUNCTUATION", ";")
                return {"type": "Assignment", "target": identifier, "value": value}

            # Atribuição de array: id '[' EXP ']' = EXP ;
            elif self.current_token() and self.current_token()[1] == "[":
                self.consume("PUNCTUATION", "[")
                index = self.parse_expression()
                self.consume("PUNCTUATION", "]")
                self.consume("OPERATOR", "=")
                value = self.parse_expression()
                self.consume("PUNCTUATION", ";")
                return {"type": "ArrayAssignment", "target": identifier, "index": index, "value": value}

        raise ParserError(f"Unexpected token in command: {token}")

    def parse_expression(self):
        """
        EXP -> REXP {&& REXP}
        """
        left = self.parse_rexp()
        while self.current_token() and self.current_token()[1] == "&&":
            self.consume("OPERATOR", "&&")
            right = self.parse_rexp()
            left = {"type": "LogicalAnd", "left": left, "right": right}
        return left

    def parse_rexp(self):
        """
        REXP -> AEXP {(< | == | !=) AEXP}
        """
        left = self.parse_aexp()
        while self.current_token() and self.current_token()[1] in {"<", "==", "!="}:
            operator = self.consume("OPERATOR")[1]
            right = self.parse_aexp()
            left = {"type": "RelationalOp", "operator": operator, "left": left, "right": right}
        return left

    def parse_aexp(self):
        """
        AEXP -> MEXP {(+ | -) MEXP}
        """
        left = self.parse_mexp()
        while self.current_token() and self.current_token()[1] in {"+", "-"}:
            operator = self.consume("OPERATOR")[1]
            right = self.parse_mexp()
            left = {"type": "ArithmeticOp", "operator": operator, "left": left, "right": right}
        return left

    def parse_mexp(self):
        """
        MEXP -> SEXP {* SEXP}
        """
        left = self.parse_sexp()
        while self.current_token() and self.current_token()[1] == "*":
            self.consume("OPERATOR", "*")
            right = self.parse_sexp()
            left = {"type": "ArithmeticOp", "operator": "*", "left": left, "right": right}
        return left

    def parse_sexp(self):
        """
        SEXP -> true | false | num | null | new int '[' EXP ']' | '(' EXP ')' | PEXP
        """
        token = self.current_token()

        # true | false
        if token[1] in {"true", "false"}:
            self.consume("RESERVED")
            return {"type": "BooleanLiteral", "value": token[1] == "true"}

        # num
        elif token[0] == "NUMBER":
            self.consume("NUMBER")
            return {"type": "Number", "value": int(token[1])}

        # null
        elif token[1] == "null":
            self.consume("RESERVED", "null")
            return {"type": "NullLiteral"}

        # new int '[' EXP ']'
        elif token[1] == "new" and self.tokens[self.current_index + 1][1] == "int":
            self.consume("RESERVED", "new")
            self.consume("RESERVED", "int")
            self.consume("PUNCTUATION", "[")
            size = self.parse_expression()
            self.consume("PUNCTUATION", "]")
            return {"type": "NewArray", "element_type": "int", "size": size}

        # '(' EXP ')'
        elif token[1] == "(":
            self.consume("PUNCTUATION", "(")
            expression = self.parse_expression()
            self.consume("PUNCTUATION", ")")
            return expression

        # PEXP
        else:
            return self.parse_pexp()
        
    def parse_pexp(self):
        """
        PEXP -> id | this | new id '(' ')' | '(' EXP ')' | PEXP . id | PEXP . id '(' [EXPS] ')' | PEXP '[' EXP ']'
        """
        token = self.current_token()

        # id
        if token[0] == "IDENTIFIER":
            identifier = self.consume("IDENTIFIER")[1]
            left = {"type": "Identifier", "name": identifier}

        # this
        elif token[1] == "this":
            self.consume("RESERVED", "this")
            left = {"type": "This"}

        # new id '(' ')'
        elif token[1] == "new":
            self.consume("RESERVED", "new")
            class_name = self.consume("IDENTIFIER")[1]
            self.consume("PUNCTUATION", "(")
            self.consume("PUNCTUATION", ")")
            left = {"type": "NewObject", "class_name": class_name}

        # '(' EXP ')'
        elif token[1] == "(":
            self.consume("PUNCTUATION", "(")
            left = self.parse_expression()
            self.consume("PUNCTUATION", ")")

        else:
            raise ParserError(f"Unexpected token in primary expression: {token}")

        # Processar extensões de PEXP
        while self.current_token() and self.current_token()[1] in {".", "["}:
            if self.current_token()[1] == ".":
                # PEXP . id
                self.consume("PUNCTUATION", ".")
                method_or_field = self.consume("IDENTIFIER")[1]
                if self.current_token() and self.current_token()[1] == "(":
                    # PEXP . id '(' [EXPS] ')'
                    self.consume("PUNCTUATION", "(")
                    arguments = []
                    if self.current_token()[1] != ")":
                        arguments = self.parse_exps()
                    self.consume("PUNCTUATION", ")")
                    left = {
                        "type": "MethodCall",
                        "target": left,
                        "method_name": method_or_field,
                        "arguments": arguments,
                    }
                else:
                    left = {
                        "type": "FieldAccess",
                        "target": left,
                        "field_name": method_or_field,
                    }

            elif self.current_token()[1] == "[":
                # PEXP '[' EXP ']'
                self.consume("PUNCTUATION", "[")
                index = self.parse_expression()
                self.consume("PUNCTUATION", "]")
                left = {"type": "ArrayAccess", "array": left, "index": index}

        return left

    def parse_exps(self):
        """
        EXPS -> EXP {, EXP}
        """
        expressions = [self.parse_expression()]
        while self.current_token() and self.current_token()[1] == ",":
            self.consume("PUNCTUATION", ",")
            expressions.append(self.parse_expression())
        return {"type": "ExpressionList", "expressions": expressions}
    
# Execução do Parser
if __name__ == "__main__":
    code = """class Factorial{
        public static void main(String[] a){
            System.out.println(new Fac().ComputeFac(10));
        }
    }
    class Fac {
        public int ComputeFac(int num){
            int num_aux;
            if (num < 1)
                num_aux = 1;
            else
                num_aux = num * (this.ComputeFac(num-1));
            return num_aux ;
        }
    }"""

    scanner = MiniJavaScanner()
    tokens = scanner.tokenize(code)

    parser = MiniJavaParserLL1(tokens)
    syntax_tree = parser.parse_program()

    formatted_output = json.dumps(syntax_tree, indent=4)
    print("Syntax Tree:")
    print_syntax_tree(syntax_tree)


