import struct

OPCODES = {
    "add": "000000", "sub": "000000", "and": "000000", "or": "000000", "slt": "000000",
    "lw": "100011", "sw": "101011", "addi": "001000", "beq": "000100", "bne": "000101",
    "j": "000010", "jal": "000011", "mul": "011100", "syscall": "000000", "addiu": "001001", "jr": "000000"
}

FUNCT_CODES = {
    "add": "100000", "sub": "100010", "and": "100100", "or": "100101",
    "slt": "101010", "jr": "001000", "mul": "000010"
}

REGISTER_MAP = {
    "$zero": "00000", "$t0": "01000", "$t1": "01001", "$t2": "01010", "$t3": "01011",
    "$s0": "10000", "$s1": "10001", "$s2": "10010", "$s3": "10011", "$a0": "00100",
    "$v0": "00010", "$ra": "11111", "$sp": "00100" , "$fp": "11110"
}

LABELS = {}
DATA_SECTION = {}
IN_DATA_SECTION = False
ADDRESS_COUNTER = 0

def parse_register(reg):
    reg = reg.strip(",") 
    if reg not in REGISTER_MAP:
        raise ValueError(f"Unsupported register: {reg}")
    print(f"Register: {reg}, Binary: {REGISTER_MAP[reg]}")
    return REGISTER_MAP[reg]


def parse_immediate(imm, bits=16):
    try:
        val = int(imm)
    except ValueError:
        raise ValueError(f"Invalid immediate value: {imm}")

    if val < -2**(bits-1) or val >= 2**(bits-1):
        raise ValueError(f"Immediate value {val} out of range for {bits}-bit representation.")
    return format(val & ((1 << bits) - 1), f"0{bits}b") 

def parse_address(addr):
    return format(int(addr), "026b")

def parse_offset(offset_reg):
    offset, reg = offset_reg.split("(")
    reg = reg.strip(")")
    return parse_immediate(offset), parse_register(reg)

def r_type_to_binary(instr, rs, rt, rd):
    opcode = OPCODES[instr]
    rs_bin = parse_register(rs)
    rt_bin = parse_register(rt) if rt else "00000"
    rd_bin = parse_register(rd) if rd else "00000"
    shamt = "00000"
    funct = FUNCT_CODES[instr]
    return f"{opcode}{rs_bin}{rt_bin}{rd_bin}{shamt}{funct}"


def i_type_to_binary(instr, rs, rt, imm):
    return f"{OPCODES[instr]}{parse_register(rs)}{parse_register(rt)}{parse_immediate(imm)}"

def j_type_to_binary(instr, address):
    return f"{OPCODES[instr]}{parse_address(address)}"

def translate_line(line):
    global ADDRESS_COUNTER
    line = line.split("#")[0].strip() 
    if not line:
        return None

    parts = line.split()
    instr = parts[0]

    if instr != "syscall" and len(parts) < 2:
        raise ValueError(f"Instruction '{line}' is missing operands.")

    if instr in OPCODES:
        if instr in FUNCT_CODES:  
            if instr == "jr": 
                if len(parts) != 2:
                    raise ValueError(f"R-type instruction '{line}' is missing or has extra operands.")
                binary = f"{OPCODES[instr]}{parse_register(parts[1])}000000000000000{FUNCT_CODES[instr]}"
            else:
                if len(parts) < 4:
                    raise ValueError(f"R-type instruction '{line}' is missing operands.")
                binary = r_type_to_binary(instr, parts[2], parts[3], parts[1])
        elif instr in {"lw", "sw"}:  
            if len(parts) < 3:
                raise ValueError(f"I-type instruction '{line}' is missing operands.")
            rt = parse_register(parts[1])
            offset, base = parse_offset(parts[2])
            binary = f"{OPCODES[instr]}{base}{rt}{offset}"
        elif instr in {"addi", "addiu", "beq", "bne"}:
            if len(parts) < 4:
                raise ValueError(f"I-type instruction '{line}' is missing operands.")
            rs = parse_register(parts[2])
            rt = parse_register(parts[1])
            if instr in {"beq", "bne"}: 
                label = parts[3]
                offset = (LABELS[label] - (ADDRESS_COUNTER + 4)) // 4
                imm = parse_immediate(str(offset), 16)
            else:
                imm = parse_immediate(parts[3])
            binary = f"{OPCODES[instr]}{rs}{rt}{imm}"
        elif instr in {"j", "jal"}: 
            if len(parts) < 2:
                raise ValueError(f"J-type instruction '{line}' is missing operands.")
            label = parts[1]
            address = LABELS[label] // 4
            binary = j_type_to_binary(instr, address)
        elif instr == "syscall":
            binary = "00000000000000000000000000001100"
        else:
            raise ValueError(f"Unknown instruction: {instr}")

        ADDRESS_COUNTER += 4
        return binary
    elif instr in {"li", "move"}: 
        if len(parts) < 3:
            raise ValueError(f"Pseudoinstruction '{line}' is missing operands.")
        if instr == "li":
            binary = i_type_to_binary("addi", "$zero", parts[1], parts[2])
        elif instr == "move":
            binary = r_type_to_binary("add", parts[2], "$zero", parts[1])
        ADDRESS_COUNTER += 4
        return binary
    else:
        raise ValueError(f"Unknown instruction: {instr}")



def translate_file(input_file, output_file):
    with open(input_file, "r") as infile, open(output_file, "w") as outfile:
        for line in infile:
            binary = translate_line(line)
            if binary:
                outfile.write(binary + "\n")
    
def pass_one(input_file):
    global LABELS, DATA_SECTION, IN_DATA_SECTION, ADDRESS_COUNTER
    ADDRESS_COUNTER = 0
    IN_DATA_SECTION = False

    with open(input_file, "r") as infile:
        for line in infile:
            line = line.split("#")[0].strip() 
            if not line:
                continue

            if line.startswith(".data"):
                IN_DATA_SECTION = True
                continue
            elif line.startswith(".text"):
                IN_DATA_SECTION = False
                continue
            elif line.startswith(".globl"):
                continue

            if IN_DATA_SECTION:
                parts = line.split()
                if len(parts) < 3:
                    print(f"Error: Invalid .data directive: {line}")
                    continue

                label = parts[0].strip(":")
                directive = parts[1]
                value = " ".join(parts[2:])
                if directive == ".word":
                    DATA_SECTION[label] = int(value)
                elif directive == ".asciiz":
                    DATA_SECTION[label] = value.strip('"')
                else:
                    print(f"Warning: Unsupported data directive: {directive}")
                continue

            if ":" in line:
                label = line.split(":")[0]
                LABELS[label] = ADDRESS_COUNTER
                continue

            ADDRESS_COUNTER += 4

def pass_two(input_file, output_file):
    global ADDRESS_COUNTER
    ADDRESS_COUNTER = 0

    with open(input_file, "r") as infile, open(output_file, "wb") as outfile: 
        for line in infile:
            line = line.split("#")[0].strip() 
            if not line or line.startswith(".") or ":" in line:
                continue

            try:
                binary = translate_line(line)
                if binary:
                    instruction_int = int(binary, 2)
                    instruction_bytes = struct.pack(">I", instruction_int) 
                    outfile.write(instruction_bytes) 
            except ValueError as e:
                print(f"Error in line '{line}': {e}")


if __name__ == "__main__":
    INPUT_FILE = "output.asm"
    OUTPUT_FILE = "output.bin"

    print("Performing Pass One...")
    pass_one(INPUT_FILE)
    print("Pass One complete. Labels and Data Section collected.")

    print(f"Performing Pass Two to translate {INPUT_FILE} to binary...")
    pass_two(INPUT_FILE, OUTPUT_FILE)
    print(f"Translation complete. Binary file saved to {OUTPUT_FILE}.")