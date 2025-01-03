import re

class MiniJavaScanner:
    def __init__(self):
        # Padrões de tokens -- cada padrão é uma tupla (nome, expressão regular)
        self.token_patterns = [
            ("WHITESPACE", r"[ \n\t\r\f]+"),  # Espaços em branco
            ("COMMENT", r"//.*|/\*[\s\S]*?\*/"),  # Comentários
            ("RESERVED", r"\b(boolean|class|extends|public|static|void|main|String|return|int|if|else|while|System\.out\.println|length|true|false|this|new|null)\b"),  # Palavras reservadas
            ("IDENTIFIER", r"\b[a-zA-Z][a-zA-Z0-9_]*\b"),  # Identificadores
            ("NUMBER", r"\b\d+\b"),  # Numerais
            ("OPERATOR", r"<=|>=|==|!=|<|>|\+|-|\*|&&|!|="),  # Operadores
            ("PUNCTUATION", r"[()\[\]{},.;]"),  # Pontuação
        ]
        # Compilar os padrões
        self.compiled_patterns = [(name, re.compile(pattern)) for name, pattern in self.token_patterns]

    def tokenize(self, code):
        tokens = []
        position = 0
        while position < len(code):
            match = None
            for token_name, pattern in self.compiled_patterns:
                match = pattern.match(code, position)
                if match:
                    lexeme = match.group(0)
                    if token_name != "WHITESPACE" and token_name != "COMMENT":
                        tokens.append((token_name, lexeme))
                    position = match.end()
                    break
            if not match:
                raise SyntaxError(f"Unexpected character: {code[position]} at position {position}")
        return tokens

# Exemplo de uso
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

    for token in tokens:
        print(token)
