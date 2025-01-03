import tkinter as tk
from tkinter import scrolledtext, messagebox
from minijava_scanner import MiniJavaScanner
from minijava_parser import MiniJavaParserLL1
from graphviz import Digraph

def draw_syntax_tree(tree, graph=None, parent_name=None):
    if graph is None:
        graph = Digraph()
        graph.node("root", "Program")
        parent_name = "root"

    if isinstance(tree, dict):
        node_name = f"{parent_name}_{id(tree)}"
        graph.node(node_name, tree.get("type", "Unknown"))
        graph.edge(parent_name, node_name)
        for key, value in tree.items():
            if key != "type":
                draw_syntax_tree(value, graph, node_name)
    elif isinstance(tree, list):
        for item in tree:
            draw_syntax_tree(item, graph, parent_name)
    else:
        node_name = f"{parent_name}_{id(tree)}"
        graph.node(node_name, str(tree))
        graph.edge(parent_name, node_name)
    return graph

def generate_tree():
    code = code_input.get("1.0", tk.END).strip()
    if not code:
        messagebox.showerror("Erro", "Por favor, insira um código.")
        return

    try:
        scanner = MiniJavaScanner()
        tokens = scanner.tokenize(code)
        parser = MiniJavaParserLL1(tokens)
        syntax_tree = parser.parse_program()

        graph = draw_syntax_tree(syntax_tree)
        graph.render("syntax_tree", format="png", cleanup=True)
        messagebox.showinfo("Árvore Gerada", "A árvore foi salva como 'syntax_tree.png'.")

    except Exception as e:
        messagebox.showerror("Erro ao gerar árvore", str(e))

root = tk.Tk()
root.title("Gerador de Árvore Sintática - MiniJava")

tk.Label(root, text="Insira o código MiniJava:").pack()
code_input = scrolledtext.ScrolledText(root, height=10, width=50)
code_input.pack()

generate_button = tk.Button(root, text="Gerar Árvore Sintática", command=generate_tree)
generate_button.pack()

root.mainloop()

