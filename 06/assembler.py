import os
SYMBOL_TABLE_RX = {f'R{i}': i for i in range(16)}
SYMBOL_TABLE = {'SCREEN': 16384, 'KBD': 24576, 'SP': 0, 'LCL': 1, 'ARG': 2, 'THIS': 3, 'THAT': 4}
SYMBOL_TABLE.update(SYMBOL_TABLE_RX)
JUMP_TABLE = {
    'JGT': '001', 'JEQ': '010', 'JGE': '011',
    'JLT': '100', 'JNE': '101', 'JLE': '110',
    'JMP': '111'
}
DEST_TABLE = {
    'M': '001', 'D': '010', 'MD': '011',
    'A': '100', 'AM': '101', 'AD': '110',
    'AMD': '111'
}
COMP_TABLE_A = {
    '0': '101010',
    '1': '111111',
    '-1': '111010',
    'D': '001100',
    'A': '110000',
    '!D': '001101',
    '!A': '110001',
    '-D': '001111',
    '-A': '110011',
    'D+1': '011111',
    'A+1': '110111',
    'D-1': '001110',
    'A-1': '110010',
    'D+A': '000010',
    'D-A': '010011',
    'A-D': '000111',
    'D&A': '000000',
    'D|A': '010101',
}
COMP_TABLE_M = {comp.replace('A', 'M'): '1' + val for comp, val in COMP_TABLE_A.items() if 'A' in comp}
COMP_TABLE = {comp: '0' + val for comp, val in COMP_TABLE_A.items()}
COMP_TABLE.update(COMP_TABLE_M)


class Assembler:
    def __init__(self):
        self.asm = None
        self.hack_path = None
        self.hack = None
        self.symbol_table = None
        self.dest_table = DEST_TABLE
        self.comp_table = COMP_TABLE
        self.jump_table = JUMP_TABLE

    def load_asm(self, asm_path):
        with open(asm_path, 'r', encoding='utf8') as fp:
            self.asm = [line for line in fp.readlines()]
        head, tail = os.path.split(asm_path)
        fname, ext = os.path.splitext(tail)
        self.hack_path = os.path.join(head, fname + '.hack')
        self.symbol_table = SYMBOL_TABLE.copy()
        print(f'LOAD {asm_path} COMPELTED!')

    def ignore_white_space(self):
        self.asm = [code.split('//')[0].strip() for code in self.asm]
        self.asm = [code for code in self.asm if len(code) > 0]

    def extract_label(self):
        cnt = 0  # next #number of valid instruction
        labels = []
        for code in self.asm:
            if code.startswith('('):
                label = code[1:-1]
                labels.append(label)
            else:
                for label in labels:
                    self.symbol_table[label] = cnt
                labels = []
                cnt += 1
        self.asm = [code for code in self.asm if not code.startswith('(')]

    def instruction_to_binary(self):
        var_cnt = 16
        hack = []
        for code in self.asm:
            if code.startswith('@'):
                instruction = code[1:]
                try:
                    instruction = int(instruction)
                except ValueError:
                    if instruction not in self.symbol_table:  # extract variables
                        self.symbol_table[instruction] = var_cnt
                        var_cnt += 1
                    instruction = self.symbol_table[instruction]
                code_binary = bin(instruction)[2:]  # int to binary
                if len(code_binary) <= 15:
                    code_binary = '0' * (15 - len(code_binary)) + code_binary
                else:
                    code_binary = code_binary[-15:]
                code_binary = '0' + code_binary
            else:
                instruction = code.split(';')
                jump_binary = self.jump_table[instruction[1]] if len(instruction) > 1 else '000'
                instruction = instruction[0].split('=')
                dest_binary = self.dest_table[instruction[0]] if len(instruction) > 1 else '000'
                comp_binary = self.comp_table[instruction[-1]]
                code_binary = '111' + comp_binary + dest_binary + jump_binary
            hack.append(code_binary)
        self.hack = hack

    def save_hack(self, custom_path=None):
        hack_path = self.hack_path if custom_path is None else custom_path
        with open(hack_path, 'w', encoding='utf8') as fp:
            for code in self.hack:
                fp.write(code+'\n')
        print(f'SAVE .hack file in {hack_path}!')

    def asm_compile(self):
        self.ignore_white_space()
        self.extract_label()
        self.instruction_to_binary()
        self.save_hack()


if __name__ == '__main__':
    assembler = Assembler()
    for path in ['./add/Add.asm', './max/Max.asm', './rect/Rect.asm', './pong/Pong.asm']:
        assembler.load_asm(path)
        assembler.asm_compile()
