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
    'label': 'C_LABEL',
    'goto': 'C_GOTO',
    'if-goto': 'C_IF',
    'function': 'C_FUNCTION',
    'return': 'C_RETURN',
    'call': 'C_CALL',
}

MEMORY_SEGMENT = {
    'local': 'LCL',
    'argument': 'ARG',
    'this': 'THIS',
    'that': 'THAT',
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
        self._cfg_reset()

    def _cfg_reset(self):
        self.file_name = None
        self.jmp_cnt = 0
        self.function_name = None
        self.function_ret_cnt = 0

    def _ignore_white_space(self, vm_code):
        return vm_code.split('//')[0].strip()

    def _parser(self, vm_code):
        vm_code_tokens = vm_code.split()
        command_type = COMMAND_TYPE[vm_code_tokens[0]]
        arg1 = vm_code_tokens[0] if command_type == 'C_ARITHMETIC' else None  # C_RETURN
        arg2 = None
        if len(vm_code_tokens) > 1:  # C_PUSH, C_POP, C_LABEL, C_IF, C_GOTO,  C_FUNCTION, C_CALL
            arg1 = vm_code_tokens[1]
        if len(vm_code_tokens) > 2:  # C_PUSH, C_POP, C_FUNCTION, C_CALL
            arg2 = int(vm_code_tokens[2])
        # print(command_type, arg1, arg2)
        return command_type, arg1, arg2

    def _BI_JMP(self, arg1):
        # 这部分是为了服务与二元布尔值计算使用的 jump label
        # jmp_cnt 标记可以满足 同一个文件内的所有 jump label 唯一
        # file_name 标记可以满足 跨文件的所有 jump lable 唯一
        self.jmp_cnt += 1
        return [
            'D=M-D',
            f'@{self.file_name}$conditiontrue.{self.jmp_cnt}',
            BI_JMP[arg1],
            'D=0',                 # false D = 0 = 00000...
            f'@{self.file_name}$nextinstruction.{self.jmp_cnt}',
            '0;JMP',
            f'({self.file_name}$conditiontrue.{self.jmp_cnt})',
            'D=-1',                 # true D = -1 = 11111...
            f'({self.file_name}$nextinstruction.{self.jmp_cnt})'
        ]

    def _memory_segment(self, command_type, arg1, arg2):
        # 计算 根地址偏移量需要用 D，抽取栈变量也需要用到 D，先抽取后访问 D 会变污染
        # 当前解决方案是建立中转指针tempAddr
        if arg2 == 0:
            return [
                f'@{MEMORY_SEGMENT[arg1]}',
                'A=M',
                {'C_PUSH': 'D=M', 'C_POP': 'M=D'}[command_type],
            ]
        else:
            if command_type == 'C_PUSH':
                return [
                    f'@{arg2}',
                    'D=A',
                    f'@{MEMORY_SEGMENT[arg1]}',
                    'A=M+D',
                    'D=M',
                ]
            elif command_type == 'C_POP':  # D Conflict
                return [
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

    def _temp(self, command_type, arg2):
        if arg2 == 0:
            return [
                f'@5',
                {'C_PUSH': 'D=M', 'C_POP': 'M=D'}[command_type],
            ]
        else:
            if command_type == 'C_PUSH':
                return [
                    f'@{arg2}',
                    'D=A',
                    f'@5',
                    'A=A+D',
                    'D=M',
                ]
            elif command_type == 'C_POP':  # D Conflict
                return [
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

    def _constant(self, arg2):  # only C_PUSH
        return [
            f'@{arg2}',
            'D=A',
        ]

    def _static(self, command_type, arg2):
        return [
            f'@{self.file_name}.{arg2}',
            {'C_PUSH': 'D=M', 'C_POP': 'M=D'}[command_type],
        ]

    def _pointer(self, command_type, arg2):
        arg = 'THIS' if arg2 == 0 else 'THAT'
        return [
            f'@{arg}',
            {'C_PUSH': 'D=M', 'C_POP': 'M=D'}[command_type],
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
                asm_code = self._memory_segment('C_PUSH', arg1,  arg2)
            elif arg1 == 'temp':
                asm_code = self._temp('C_PUSH', arg2)
            elif arg1 == 'constant':
                asm_code = self._constant(arg2)
            elif arg1 == 'static':
                asm_code = self._static('C_PUSH', arg2)
            elif arg1 == 'pointer':
                asm_code = self._pointer('C_PUSH', arg2)
            asm_code += PATTERN['push_D_in_stack']
        elif command_type == 'C_POP':  # D <- Stack Then M <- D
            if arg1 in MEMORY_SEGMENT:
                asm_code = self._memory_segment('C_POP', arg1, arg2)
            elif arg1 == 'temp':
                asm_code = self._temp('C_POP', arg2)
            elif arg1 == 'static':
                asm_code = self._static('C_POP', arg2)
            elif arg1 == 'pointer':
                asm_code = self._pointer('C_POP', arg2)

            if not ((arg1 in MEMORY_SEGMENT or arg1 == 'temp') and arg2 > 0):  # if not D-conflict:
                asm_code = PATTERN['extract_y'] + asm_code
        elif command_type == 'C_GOTO':
            asm_code = [
                f'@{self.function_name}${arg1}',
                '0;JMP',
            ]
        elif command_type == 'C_LABEL':
            asm_code = [
                f'({self.function_name}${arg1})'
            ]
        elif command_type == 'C_IF':
            asm_code = PATTERN['extract_y'] + [
                f'@{self.function_name}${arg1}',
                'D;JNE',  # if cond means if cond != 0
            ]
        elif command_type == 'C_CALL':
            # 采用隐藏规则 .vm 内函数名规则 fileName.functionName，故不额外补充名称
            retAddressLabel = f'{self.function_name}$ret.{self.function_ret_cnt}'
            self.function_ret_cnt += 1

            asm_code = [
                f'@{retAddressLabel}',
                'D=A',
            ] + PATTERN['push_D_in_stack'] + [  # push retAddressLabel
                '@LCL',
                'D=M',
            ] + PATTERN['push_D_in_stack'] + [  # push local
                '@ARG',
                'D=M',
            ] + PATTERN['push_D_in_stack'] + [  # push argument
                '@THIS',
                'D=M',
            ] + PATTERN['push_D_in_stack'] + [  # push this
                '@THAT',
                'D=M',
            ] + PATTERN['push_D_in_stack'] + [  # push that
                '@SP',
                'D=M',
                '@5',
                'D=D-A',
                f'@{arg2}',
                'D=D-A',
                '@ARG',
                'M=D',  # ARG = SP - 5 - nArgs
                '@SP',
                'D=M',
                '@LCL',
                'M=D',  # LCL = SP
                f'@{arg1}',
                '0;JMP',  # goto function
                f'({retAddressLabel})',  # set retAddressLabel
            ]
        elif command_type == 'C_FUNCTION':
            # 所有 .vm 文件内都只有函数，return不能代表一个函数的结束
            # 直到遇见下一个函数才能重制计数器与函数名

            self.function_name = arg1
            self.function_ret_cnt = 0
            asm_code = [
                f'({self.function_name})',
            ]
            for i in range(arg2):  # set all locals = 0
                asm_code += [
                    '@0',
                    'D=A',
                ] + PATTERN['push_D_in_stack']
        elif command_type == 'C_RETURN':
            asm_code = [
                '@LCL',
                'D=M',
                '@endFrame',
                'M=D',  # endFrame = LCL; D = LCL = endFrame
                '@5',
                'A=D-A',
                'D=M',  # D = *(endFrame - 5)
                '@retAddr',
                'M=D',  # retAddr = D
            ] + PATTERN['extract_y'] + [
                '@ARG',
                'A=M',
                'M=D',  # *ARG = D = *pop()
                '@ARG',
                'D=M',
                '@SP',
                'M=D+1',  # SP = ARG + 1
                '@endFrame',
                'D=M',
                '@1',
                'A=D-A',
                'D=M',
                '@THAT',
                'M=D',  # THAT = *(endFrame - 1)
                '@endFrame',
                'D=M',
                '@2',
                'A=D-A',
                'D=M',
                '@THIS',
                'M=D',  # THIS = *(endFrame - 2)
                '@endFrame',
                'D=M',
                '@3',
                'A=D-A',
                'D=M',
                '@ARG',
                'M=D',  # ARG = *(endFrame - 3)
                '@endFrame',
                'D=M',
                '@4',
                'A=D-A',
                'D=M',
                '@LCL',
                'M=D',  # LCL = *(endFrame - 4)
                '@retAddr',
                'A=M',
                '0;JMP',  # goto Addr
            ]
            # self.function_name = None  # return 必然意味着退出了一个函数的编译，进入全局空间
        return asm_code

    def translate_file(self, vm_path, write_asm_file=True):
        with open(vm_path, 'r', encoding='utf8') as fpr:
            head, tail = os.path.split(vm_path)
            self.file_name, ext = os.path.splitext(tail)
            asm_path = os.path.join(head, self.file_name + '.asm')
            asm_codes = []
            for vm_code in fpr:
                vm_code = self._ignore_white_space(vm_code)
                if len(vm_code) > 0:
                    command_type, arg1, arg2 = self._parser(vm_code)
                    asm_code = self._code_writer(command_type, arg1, arg2)
                    asm_codes += asm_code
        self._cfg_reset()

        if write_asm_file:
            with open(asm_path, 'w', encoding='utf8') as fpw:
                fpw.writelines([code + '\n' for code in asm_codes])
        return asm_codes

    def _boot(self):
        return [
            '@256',
            'D=A',
            '@SP',
            'M=D',  # SP = 256
        ] + self._code_writer('C_CALL', 'Sys.init', 0)

    def translate(self, vm_path):
        fname, ext = os.path.splitext(vm_path)
        if ext == '.vm':  # single file
            self.translate_file(vm_path)
        else:  # project directory
            for root, _, files in os.walk(vm_path):
                vm_files = [f for f in files if os.path.splitext(f)[-1] == '.vm']
                if len(vm_files) == 1 and vm_files[0] != 'Sys.vm':
                    self.translate_file(os.path.join(root, vm_files[0]))
                else:
                    asm_codes = self._boot()
                    for f in vm_files:
                        asm_codes += self.translate_file(os.path.join(root, f), False)
                    head, tail = os.path.split(root)
                    asm_path = os.path.join(root, tail + '.asm')
                    with open(asm_path, 'w', encoding='utf8') as fpw:
                        fpw.writelines([code + '\n' for code in asm_codes])


if __name__ == '__main__':
    vm_translator = VMtranslator()
    for root, dirs, files in os.walk('./ProgramFlow'):
        if len(dirs) == 0:
            vm_translator.translate(root)
    for root, dirs, files in os.walk('./FunctionCalls'):
        if len(dirs) == 0:
            vm_translator.translate(root)

    # vm_translator.translate('./ProgramFlow/BasicLoop/BasicLoop.vm')
    # vm_translator.translate('./ProgramFlow/FibonacciSeries/FibonacciSeries.vm')
    # vm_translator.translate('./FunctionCalls/SimpleFunction/SimpleFunction.vm')
    # vm_translator.translate('./FunctionCalls/FibonacciElement')
    # vm_translator.translate('./FunctionCalls/')
