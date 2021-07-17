import os
import re


class SymbolTable:
    def __init__(self):
        self.class_symbol_table = {}
        self.subroutine_symbol_table = {}
        self.symbol_count = {
            'static': 0, 'field': 0, 'argument': 0, 'local': 0,  # VAR => LOCAL
        }

    def start_subroutine(self):
        self.subroutine_symbol_table = {}
        self.symbol_count['argument'] = 0
        self.symbol_count['local'] = 0

    def define(self, var_name, var_type, var_kind):
        if var_kind in ['static', 'field']:
            symbol_table = self.class_symbol_table
        else:
            symbol_table = self.subroutine_symbol_table
        symbol_table[var_name] = {
            'type': var_type,
            'kind': var_kind,
            'index': self.var_count(var_kind)
        }
        self.var_inc(var_kind)

    def var_inc(self, kind):
        self.symbol_count[kind] += 1

    def var_count(self, kind):
        return self.symbol_count[kind]

    def _property_of(self, var_name, var_property):
        if var_name in self.subroutine_symbol_table:
            return self.subroutine_symbol_table[var_name][var_property]
        elif var_name in self.class_symbol_table:
            return self.class_symbol_table[var_name][var_property]
        else:
            return None

    def kind_of(self, name):
        # return None means the name is subroutineName or className (in an error-free Jack code)
        return self._property_of(name, 'kind')

    def type_of(self, name):
        return self._property_of(name, 'type')

    def index_of(self, name):
        return self._property_of(name, 'index')

    def query_of(self, name):
        return self.kind_of(name), self.type_of(name), self.index_of(name)


class VMWriter:
    def __init__(self, vm_path):
        self.vm = []
        self.vm_path = vm_path
        self.arithmetic_mapping = {
            '+': 'add',
            '-': {False: 'neg', True: 'sub'},
            '*': 'call Math.multiply 2',
            '/': 'call Math.divide 2',
            '&': 'and',
            '|': 'or',
            '<': 'lt',
            '>': 'gt',
            '=': 'eq',
            '~': 'not',
        }

    def _write(self, vm_code):
        self.vm.append(vm_code)

    def write_push(self, segment, index):
        if segment == 'field':
            segment = 'this'
        self._write(f'push {segment} {index}')

    def write_pop(self, segment, index):
        if segment == 'field':
            segment = 'this'
        self._write(f'pop {segment} {index}')

    def write_arithmetic(self, command, sub_flag=True):
        if command == '-':
            vm_code = self.arithmetic_mapping[command][sub_flag]
        else:
            vm_code = self.arithmetic_mapping[command]
        self._write(vm_code)

    def write_label(self, label):
        self._write(f'label {label}')

    def write_goto(self, label):
        self._write(f'goto {label}')

    def write_if(self, label):
        self._write(f'if-goto {label}')

    def write_call(self, name, n_args):
        self._write(f'call {name} {n_args}')

    def write_function(self, name, n_locals):
        self._write(f'function {name} {n_locals}')

    def write_return(self):
        self._write('return')

    def write_file(self):
        with open(self.vm_path, 'w', encoding='utf8') as fpw:
            fpw.write('\n'.join(self.vm))
            fpw.write('\n')

    def reset(self):
        self.vm = []
        self.vm_path = None


class JackTokenizer:
    def __init__(self, debug=False):
        self.keyword = [
            'class', 'constructor', 'function', 'method',
            'field', 'static', 'var', 'int', 'char', 'boolean',
            'void', 'true', 'false', 'null', 'this', 'let', 'do',
            'if', 'else', 'while', 'return',
        ]
        self.symbol = [
            '{', '}', '(', ')', '[', ']', '.', ',', ';', '+', '-', '*',
            '/', '&', '|', '<', '>', '=', '~',
        ]
        self._in_block_comments = False

    def _reset_state(self):
        self._in_block_comments = False

    def _ignore_white_space(self, jack_code):
        '''
        处理 line comments 与 block comments 并提供简单的检查
        '''
        jack_code = jack_code.strip()
        if self._in_block_comments:
            assert jack_code.startswith('*')
            self._in_block_comments = not (jack_code.startswith('*/') or jack_code.endswith('*/'))
            jack_code = ''
        else:
            if jack_code.startswith('/**'):
                # block comment can be used as line comment
                self._in_block_comments = not jack_code.endswith('*/')
                jack_code = ''
            jack_code = jack_code.split('//')[0].strip()  # no line comment
        # print(jack_code)
        return jack_code

    def _mark_up_token(self, jack_xml, token_val, token_type):
        jack_xml.append(
            f"<{token_type}> {token_val} </{token_type}>"
        )

    def tokenizing_line(self, jack_code):
        jack_code = self._ignore_white_space(jack_code)
        # 所有标准符号加上空格作为切分符号
        symbols_reg = '([' + ''.join(['\\' + s for s in self.symbol]) + '\s])'
        tokens = re.split(symbols_reg, jack_code)
        tokens = [token for token in tokens if len(token) > 0]
        # print(symbols_reg)
        # print(tokens)
        jack_xml = []
        _in_string = False
        _string_token = ''
        for token in tokens:
            if _in_string:
                _string_token += token
                _in_string = not token.endswith('"')
                if not _in_string:
                    self._mark_up_token(jack_xml, _string_token[1:-1], 'stringConstant')
            else:
                if token == ' ':  # 空格如果是 stringConstant 内部内容则需要保留
                    continue
                if token in self.keyword:
                    self._mark_up_token(jack_xml, token, 'keyword')
                elif token in self.symbol:
                    self._mark_up_token(jack_xml, token, 'symbol')
                elif re.match(r'\d', token):
                    self._mark_up_token(jack_xml, token, 'integerConstant')
                elif token.startswith('"'):
                    _string_token += token
                    _in_string = not token.endswith('"')
                    if not _in_string:
                        self._mark_up_token(jack_xml, token[1:-1], 'stringConstant')
                else:
                    self._mark_up_token(jack_xml, token, 'identifier')
        return jack_xml

    def tokenizing(self, jack_path):
        xmlT_codes = []
        with open(jack_path, 'r', encoding='utf8') as fpr:
            for jack_code in fpr:
                xmlT_codes += self.tokenizing_line(jack_code)
        self._reset_state()
        return xmlT_codes


class CompilationEngine:
    def __init__(self):
        self.op = ('+', '-', '*', '/', '&', '|', '<', '>', '=')
        self.unary_op = ('-', '~')
        self.keyword_constant = ('true', 'false', 'null', 'this')
        self._reset()

    def _reset(self):
        self.class_name = None
        self.symbol_table = None
        self.idx = 0
        self.tokens = None
        self.vm_writer = None
        self.label_cnt = 0

    def _start_subroutine(self):
        self.symbol_table.start_subroutine()
        self.subroutine_name = None
        self.subroutine_type = None
        self.subroutine_kind = None

    def _get_token(self, offset=0):
        return self.tokens[self.idx + offset]

    def _extract_token(self, offset=0):
        token = self._get_token(offset)
        token_type = re.search(r'</(.+)>', token).group(1)
        token_val = re.search(r'> (.+) <', token).group(1)
        return token_type, token_val

    def _check_token(self, offset, rule_val=None, rule_type=None):
        token_type, token_val = self._extract_token(offset)

        if isinstance(rule_type, tuple):
            check_type = token_type in rule_type
        else:
            check_type = token_type == rule_type

        if isinstance(rule_val, tuple):
            check_val = token_val in rule_val
        else:
            check_val = token_val == rule_val
        check = check_type or check_val
        return check, token_type, token_val

    def _check_current(self, rule_val=None, rule_type=None):
        return self._check_token(0, rule_val, rule_type)[0]

    def _check_next(self, rule_val=None, rule_type=None):
        return self._check_token(1, rule_val, rule_type)[0]

    def _confirm(self, rule_val=None, rule_type=None):
        # check_token & read continue
        check, token_type, token_val = self._check_token(0, rule_val, rule_type)
        assert check, 'Compilation Error'
        self.idx += 1
        return token_type, token_val

    def _label_pair(self):
        label1 = f'LABEL1_{self.label_cnt}'
        label2 = f'LABEL2_{self.label_cnt}'
        self.label_cnt += 1  # L1, L2
        return label1, label2

    def _compile_class(self):
        self._confirm('class')
        _, self.class_name = self._confirm(None, 'identifier')  # className
        self._confirm('{')
        self._compile_classVarDec()
        self._complie_subroutineDec()
        self._confirm('}')

    def _compile_classVarDec(self):
        while self._check_current(('static', 'field')):
            _, var_kind = self._confirm(('static', 'field'))
            _, var_type = self._confirm(('int', 'char', 'boolean'), 'identifier')  # type
            _, var_name = self._confirm(None, 'identifier')
            self.symbol_table.define(var_name, var_type, var_kind)
            while self._check_current(','):
                self._confirm(',')
                _, var_name = self._confirm(None, 'identifier')
                self.symbol_table.define(var_name, var_type, var_kind)
            self._confirm(';')

    def _complie_subroutineDec(self):
        while self._check_current(('constructor', 'function', 'method')):
            self._start_subroutine()
            _, self.subroutine_kind = self._confirm(('constructor', 'function', 'method'))
            _, self.subroutine_type = self._confirm(('int', 'char', 'boolean', 'void'), 'identifier')
            _, self.subroutine_name = self._confirm(None, 'identifier')  # subroutineName
            self._confirm('(')
            self._complie_parameterList()
            self._confirm(')')
            self._complie_subroutineBody()

    def _complie_parameterList(self):
        n_args = 0
        if self.subroutine_kind == 'method':
            self.symbol_table.define('this', self.class_name, 'argument')
        if self._check_current(('int', 'char', 'boolean'), 'identifier'):
            _, var_type = self._confirm(('int', 'char', 'boolean'), 'identifier')
            _, var_name = self._confirm(None, 'identifier')
            self.symbol_table.define(var_name, var_type, 'argument')
            n_args += 1
            while self._check_current(','):
                self._confirm(',')
                _, var_type = self._confirm(('int', 'char', 'boolean'), 'identifier')
                _, var_name = self._confirm(None, 'identifier')
                self.symbol_table.define(var_name, var_type, 'argument')
                n_args += 1
        return n_args

    def _complie_subroutineBody(self):
        self._confirm('{')
        n_locals = self._compile_varDec()
        self.vm_writer.write_function(f'{self.class_name}.{self.subroutine_name}', n_locals)
        if self.subroutine_kind == 'constructor':
            # 注意内存分配依据是 field，不足的内存分配会导致 StackOverflow
            self.vm_writer.write_push('constant', self.symbol_table.var_count('field'))
            self.vm_writer.write_call('Memory.alloc', 1)
            self.vm_writer.write_pop('pointer', 0)
        elif self.subroutine_kind == 'method':
            self.vm_writer.write_push('argument', 0)  # VMtranslater will translate ARG = argument 0
            self.vm_writer.write_pop('pointer', 0)
        self._compile_statements()
        self._confirm('}')

    def _compile_varDec(self):
        n_locals = 0
        while self._check_current('var'):
            self._confirm('var')
            _, var_type = self._confirm(('int', 'char', 'boolean'), 'identifier')
            _, var_name = self._confirm(None, 'identifier')
            self.symbol_table.define(var_name, var_type, 'local')
            n_locals += 1
            while self._check_current(','):
                self._confirm(',')
                _, var_name = self._confirm(None, 'identifier')
                self.symbol_table.define(var_name, var_type, 'local')
                n_locals += 1
            self._confirm(';')
        return n_locals

    def _compile_statements(self):
        self._compile_statement()

    def _compile_statement(self):
        while self._check_current(('let', 'if', 'while', 'do', 'return')):
            if self._check_current('let'):
                self._compile_letStatement()
            elif self._check_current('if'):
                self._compile_ifStatement()
            elif self._check_current('while'):
                self._compile_whileStatement()
            elif self._check_current('do'):
                self._compile_doStatement()
            else:
                self._compile_returnStatement()

    def _compile_letStatement(self):
        self._confirm('let')
        _, identifier_name = self._confirm(None, 'identifier')
        var_kind, var_type, var_idx = self.symbol_table.query_of(identifier_name)
        if self._check_current('['):  # Array
            self.vm_writer.write_push(var_kind, var_idx)
            self._confirm('[')
            self._compile_expression()
            self._confirm(']')
            self.vm_writer.write_arithmetic('+')
            self._confirm('=')
            self._compile_expression()
            self._confirm(';')
            self.vm_writer.write_pop('temp', 0)
            self.vm_writer.write_pop('pointer', 1)
            self.vm_writer.write_push('temp', 0)
            self.vm_writer.write_pop('that', 0)
        else:
            self._confirm('=')
            self._compile_expression()
            self._confirm(';')
            self.vm_writer.write_pop(var_kind, var_idx)

    def _compile_ifStatement(self):
        label1, label2 = self._label_pair()
        self._confirm('if')
        self._confirm('(')
        self._compile_expression()
        self._confirm(')')
        self.vm_writer.write_arithmetic('~')
        self.vm_writer.write_if(label1)
        self._confirm('{')
        self._compile_statements()
        self._confirm('}')
        self.vm_writer.write_goto(label2)
        self.vm_writer.write_label(label1)
        if self._check_current('else'):
            self._confirm('else')
            self._confirm('{')
            self._compile_statements()
            self._confirm('}')
        self.vm_writer.write_label(label2)

    def _compile_whileStatement(self):
        label1, label2 = self._label_pair()
        self._confirm('while')
        self.vm_writer.write_label(label1)
        self._confirm('(')
        self._compile_expression()
        self._confirm(')')
        self.vm_writer.write_arithmetic('~')
        self.vm_writer.write_if(label2)
        self._confirm('{')
        self._compile_statements()
        self._confirm('}')
        self.vm_writer.write_goto(label1)
        self.vm_writer.write_label(label2)

    def _compile_doStatement(self):
        self._confirm('do')
        self._compile_subroutineCall()
        self._confirm(';')
        # 所有 subroutine 都会有返回值，但是在 do 语句中返回值没有意义（不会参与任何赋值），需要马上移除返回值
        self.vm_writer.write_pop('temp', 0)

    def _compile_returnStatement(self):
        self._confirm('return')
        if not self._check_current(';'):
            self._compile_expression()
        self._confirm(';')
        if self.subroutine_type == 'void':
            # void 函数没有返回值，效果都是函数副作用
            # 所以需要一个虚拟值用于占位，以满足 Jack 语言要求
            self.vm_writer.write_push('constant', 0)
        self.vm_writer.write_return()

    def _compile_expression(self):
        self._compile_term()
        while self._check_current(self.op):
            _, op = self._confirm(self.op)
            self._compile_term()
            self.vm_writer.write_arithmetic(op, True)

    def _compile_term(self):
        if self._check_current(None, 'integerConstant'):
            _, int_val = self._confirm(None, 'integerConstant')
            self.vm_writer.write_push('constant', int_val)
        elif self._check_current(None, 'stringConstant'):
            _, str_val = self._confirm(None, 'stringConstant')
            self.vm_writer.write_push('constant', len(str_val))
            self.vm_writer.write_call('String.new', 1)  # 利用返回值简化编译
            for c in str_val:
                self.vm_writer.write_push('constant', ord(c))
                self.vm_writer.write_call('String.appendChar', 2)

        elif self._check_current(self.keyword_constant):
            _, keyword_val = self._confirm(self.keyword_constant)
            if keyword_val == 'this':
                self.vm_writer.write_push('pointer', 0)
            elif keyword_val == 'true':
                self.vm_writer.write_push('constant', 1)
                self.vm_writer.write_arithmetic('-', False)
            else:  # false & null
                self.vm_writer.write_push('constant', 0)
        elif self._check_current('('):
            self._confirm('(')
            self._compile_expression()
            self._confirm(')')
        elif self._check_current(self.unary_op):
            _, unary_op = self._confirm(self.unary_op)
            self._compile_term()
            self.vm_writer.write_arithmetic(unary_op, False)
        else:  # varName | varName[] | subroutineName() | (className|varName).
            if self._check_next('['):  # Array
                _, identifier_name = self._confirm(None, 'identifier')
                var_kind, var_type, var_idx = self.symbol_table.query_of(identifier_name)
                self.vm_writer.write_push(var_kind, var_idx)
                self._confirm('[')
                self._compile_expression()
                self._confirm(']')
                self.vm_writer.write_arithmetic('+')
                self.vm_writer.write_pop('pointer', 1)  # 锚定位置
                self.vm_writer.write_push('that', 0)  # 读取数据

            elif self._check_next(('(', '.')):
                self._compile_subroutineCall()
            else:
                _, identifier_name = self._confirm(None, 'identifier')
                var_kind, var_type, var_idx = self.symbol_table.query_of(identifier_name)
                self.vm_writer.write_push(var_kind, var_idx)

    def _compile_subroutineCall(self):
        if not self._check_next('.'):
            #  subroutineName() 其实是一个特殊写法，忽略了调用前的 varName
            #  subroutineName() 默认是操作现状态内的 object，保持对象根地址不变
            #  因此直接压入 THIS 根地址
            self.vm_writer.write_push('pointer', 0)
            _, callee_name = self._confirm(None, 'identifier')
            self._confirm('(')
            n_args = self._compile_expressionList()
            self._confirm(')')
            self.vm_writer.write_call(f'{self.class_name}.{callee_name}', n_args + 1)
        else:  # className.subroutineName | VarName.subroutineName
            _, identifier_name = self._confirm(None, 'identifier')
            var_kind, var_type, var_idx = self.symbol_table.query_of(identifier_name)
            if var_kind is None:  # className => Constructor | function
                self._confirm('.')
                _, callee_name = self._confirm(None, 'identifier')
                self._confirm('(')
                n_args = self._compile_expressionList()
                self._confirm(')')
                self.vm_writer.write_call(f'{identifier_name}.{callee_name}', n_args)
            else:  # VarName => Method
                self.vm_writer.write_push(var_kind, var_idx)
                self._confirm('.')
                _, callee_name = self._confirm(None, 'identifier')
                self._confirm('(')
                n_args = self._compile_expressionList()
                self._confirm(')')
                self.vm_writer.write_call(f'{var_type}.{callee_name}', n_args + 1)

    def _compile_expressionList(self):
        n_args = 0
        if not self._check_current(')'):
            self._compile_expression()
            n_args += 1
            while self._check_current(','):
                self._confirm(',')
                self._compile_expression()
                n_args += 1
        return n_args

    def parser(self, tokens, vm_path):
        self.tokens = tokens
        self.symbol_table = SymbolTable()
        self.vm_writer = VMWriter(vm_path)
        self._compile_class()
        self.vm_writer.write_file()
        # print(self.symbol_table.class_symbol_table)
        self._reset()


class JackCompiler:
    def __init__(self):
        self.jack_tokenizer = JackTokenizer()
        self.compilation_engine = CompilationEngine()

    def compile_jack_file(self, jack_path):
        head, tail = os.path.split(jack_path)
        fname, ext = os.path.splitext(tail)
        tokens = self.jack_tokenizer.tokenizing(jack_path)
        vm_path = os.path.join(head, fname + '.vm')
        self.compilation_engine.parser(tokens, vm_path)

    def compile_jack(self, jack_path):
        fname, ext = os.path.splitext(jack_path)
        if ext == '.jack':  # single file
            self.compile_jack_file(jack_path)
        else:  # project directory
            for root, _, files in os.walk(jack_path):
                for f in files:
                    if os.path.splitext(f)[-1] == '.jack':
                        self.compile_jack_file(os.path.join(root, f))


if __name__ == '__main__':
    import subprocess
    jack_compiler = JackCompiler()

    def full_test():
        text_comparer = 'TextComparer.bat'
        for root, dirs, files in os.walk('./'):
            if len(dirs) == 0:
                # print(root == './ExpressionLessSquare')
                jack_filename = []
                for f in files:
                    file_name, ext = os.path.splitext(f)
                    if ext == '.jack':
                        jack_filename.append(file_name)
                jack_compiler.compile_jack(root)
    full_test()
    # jack_compiler.compile_jack('./Seven')
    # jack_compiler.compile_jack('./ConvertToBin')
    # jack_compiler.compile_jack('./Square')
    # jack_compiler.compile_jack('./Average')
    # jack_compiler.compile_jack('./Pong')
    # jack_compiler.compile_jack('./ComplexArrays')
