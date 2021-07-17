import os

COMMAND_TYPE = {
    'add': 'C_ARITHMETIC',
    'sub': 'C_ARITHMETIC',
    'neg': 'C_ARITHMETIC',
    'eq': 'C_ARITHMETIC',
    'gt': 'C_ARITHMETIC',
    'lt': 'C_ARITHMETIC',
    'and': 'C_ARITHMETIC',
    'or': 'C_ARITHMETIC',
    'not': 'C_ARITHMETIC',
    'push': 'C_PUSH',
    'pop': 'C_POP',
}

MEMORY_SEGMENT = {
    'local': 'LCL',
    'argument': 'ARG',
    'this': 'THIS',
    'that': 'THAT',
    # 'temp': '5',
}

BI_OPS = {  # x -> M, y -> D
    'add': ['D=D+M'],
    'sub': ['D=M-D'],
    'and': ['D=D&M'],
    'or': ['D=D|M'],
}

BI_JMP = {  # x -> M, y -> D
    'eq': 'D;JEQ',  # x == y
    'gt': 'D;JGT',  # x > y
    'lt': 'D;JLT',  # x < y
}


U_OPS = {  # y -> D
    'neg': ['D=-D'],
    'not': ['D=!D'],
}

PATTERN = {
    'extract_x_y': [  # x -> M, y -> D
        '@SP',
        'M=M-1',             # sp --; 指向二元操作符的第二个参数 y 的位置
        '@SP',
        'A=M',
        'D=M',               # D = *sp; y 存入 D
        '@SP',
        'M=M-1',             # sp --; 指向二元操作符的第一个参数 x 的位置
        'A=M',               # x 映射存入 M
    ],
    'extract_y': [  # y -> D
        '@SP',
        'M=M-1',             # sp --; 指向二元操作符的第二个参数 y 的位置
        '@SP',
        'A=M',
        'D=M',               # D = *sp; y 存入 D
    ],
    'push_D_in_stack': [
        '@SP',
        'A=M',
        'M=D',               # *sp = D;
        '@SP',
        'M=M+1',             # sp ++;
    ]
}


class VMtranslator:
    def __init__(self):
        self.fname = None
        self.jmp_cnt = -1

    def _ignore_white_space(self, vm_code):
        return vm_code.split('//')[0].strip()

    def _parser(self, vm_code):
        vm_code_tokens = vm_code.split()
        command_type = COMMAND_TYPE[vm_code_tokens[0]]
        arg1 = vm_code_tokens[0] if command_type == 'C_ARITHMETIC' else None
        arg2 = None
        if len(vm_code_tokens) > 1:
            arg1 = vm_code_tokens[1]
            arg2 = int(vm_code_tokens[2])
        return command_type, arg1, arg2

    def _BI_JMP(self, arg1):
        self.jmp_cnt += 1
        return [
            'D=M-D',
            f'@conditiontrue.{self.jmp_cnt}',
            BI_JMP[arg1],
            'D=0',                 # false D = 0 = 00000...
            f'@nextinstruction.{self.jmp_cnt}',
            '0;JMP',
            f'(conditiontrue.{self.jmp_cnt})',
            'D=-1',                 # true D = -1 = 11111...
            f'(nextinstruction.{self.jmp_cnt})'
        ]

    def _code_writer(self, command_type, arg1, arg2):
        asm_code = []
        if command_type == 'C_ARITHMETIC':
            if arg1 in BI_OPS:
                asm_code = PATTERN['extract_x_y'] + BI_OPS[arg1]
            elif arg1 in BI_JMP:
                asm_code = PATTERN['extract_x_y'] + self._BI_JMP(arg1)
            elif arg1 in U_OPS:
                asm_code = PATTERN['extract_y'] + U_OPS[arg1]
            asm_code += PATTERN['push_D_in_stack']
        elif command_type == 'C_PUSH':  # D <- M Then Stack <- D
            if arg1 in MEMORY_SEGMENT:
                if arg2 == 0:
                    asm_code = [
                        f'@{MEMORY_SEGMENT[arg1]}',
                        'A=M',
                        'D=M',
                    ]
                else:
                    asm_code = [
                        f'@{arg2}',
                        'D=A',
                        f'@{MEMORY_SEGMENT[arg1]}',
                        'A=M+D',
                        'D=M',
                    ]
            elif arg1 == 'temp':
                if arg2 == 0:
                    asm_code = [
                        f'@5',
                        'D=M',
                    ]
                else:
                    asm_code = [
                        f'@{arg2}',
                        'D=A',
                        f'@5',
                        'A=A+D',
                        'D=M',
                    ]
            elif arg1 == 'constant':
                asm_code = [
                    f'@{arg2}',
                    'D=A',
                ]
            elif arg1 == 'static':
                asm_code = [
                    f'@{self.fname}.{arg2}',
                    'D=M',
                ]
            elif arg1 == 'pointer':
                arg = 'THIS' if arg2 == 0 else 'THAT'
                asm_code = [
                    f'@{arg}',
                    'D=M',
                ]
            asm_code += PATTERN['push_D_in_stack']
        elif command_type == 'C_POP':  # D <- Stack Then M <- D
            if arg1 in MEMORY_SEGMENT:
                if arg2 == 0:
                    asm_code = [
                        f'@{MEMORY_SEGMENT[arg1]}',
                        'A=M',
                        'M=D',
                    ]
            elif arg1 == 'temp':
                if arg2 == 0:
                    asm_code = [
                        f'@5',
                        'M=D',
                    ]
            elif arg1 == 'static':
                asm_code = [
                    f'@{self.fname}.{arg2}',
                    'M=D',
                ]
            elif arg1 == 'pointer':
                arg = 'THIS' if arg2 == 0 else 'THAT'
                asm_code = [
                    f'@{arg}',
                    'M=D',
                ]
            asm_code = PATTERN['extract_y'] + asm_code
            if arg1 in MEMORY_SEGMENT or arg1 == 'temp' and arg2 > 0:  # 解决 D 污染问题
                # 计算 根地址偏移量需要用 D，抽取栈变量也需要用到 D，先抽取后访问 D 会变污染
                # 当前解决方案是建立中转指针tempAddr
                if arg1 == 'temp':
                    asm_code = [
                        f'@{arg2}',
                        'D=A',
                        f'@5',
                        'D=A+D',
                        '@tempAddr',
                        'M=D',
                    ] + PATTERN['extract_y'] + [
                        '@tempAddr',
                        'A=M',
                        'M=D',
                    ]
                else:
                    asm_code = [
                        f'@{arg2}',
                        'D=A',
                        f'@{MEMORY_SEGMENT[arg1]}',
                        'D=M+D',
                        '@tempAddr',
                        'M=D',
                    ] + PATTERN['extract_y'] + [
                        '@tempAddr',
                        'A=M',
                        'M=D',
                    ]

        return asm_code

    def translate(self, vm_path):
        with open(vm_path, 'r', encoding='utf8') as fpr:
            head, tail = os.path.split(vm_path)
            self.fname, ext = os.path.splitext(tail)
            asm_path = os.path.join(head, self.fname + '.asm')
            with open(asm_path, 'w', encoding='utf8') as fpw:
                for vm_code in fpr:
                    vm_code = self._ignore_white_space(vm_code)
                    if len(vm_code) > 0:
                        command_type, arg1, arg2 = self._parser(vm_code)
                        asm_code = self._code_writer(command_type, arg1, arg2)
                        fpw.writelines([code + '\n' for code in asm_code])
        self.jmp_cnt = 0


if __name__ == '__main__':
    vm_paths = []
    for root, _, files in os.walk('./'):
        for f in files:
            if os.path.splitext(f)[-1] == '.vm':
                vm_paths.append(os.path.join(root, f))

    vm_translator = VMtranslator()
    for vm_path in vm_paths:
        vm_translator.translate(vm_path)
