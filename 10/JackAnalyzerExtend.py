import os
import re


class SymbolTable:
    '''
    以注释方式解析全部的 identifier，用于测试
    XML 的注释格式未 <!-- This is a comment --> 
    '''

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

    def var_count(self, kind):
        kind_count = self.symbol_count[kind]
        self.symbol_count[kind] += 1
        return kind_count

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
        # if self.kind_of(name) is None:
        #     return '', '', ''
        # else:
        return self.kind_of(name), self.type_of(name), self.index_of(name)


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
        self.symbol_mapping = {
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            '&': '&amp;',
        }
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
            self._in_block_comments = not jack_code.startswith('*/')
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
                    if token in self.symbol_mapping:
                        token = self.symbol_mapping[token]
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

    def tokenizing(self, jack_path, xmlT_path):
        xmlT_codes = []
        xmlT_start = ['<tokens>']
        xmlT_end = ['</tokens>']
        with open(jack_path, 'r', encoding='utf8') as fpr:
            for jack_code in fpr:
                xmlT_codes += self.tokenizing_line(jack_code)
        with open(xmlT_path, 'w', encoding='utf8') as fpw:
            fpw.write('\n'.join(xmlT_start + xmlT_codes + xmlT_end))

        self._reset_state()
        return xmlT_codes


class CompilationEngine:
    def __init__(self):
        # self.op = ('+', '-', '*', '/', '&', '|', '<', '>', '=')
        self.op = ('+', '-', '*', '/', '&amp;', '|', '&lt;', '&gt;', '=')
        self.unary_op = ('-', '~')
        self.keyword_constant = ('true', 'false', 'null', 'this')
        self.symbol_table = SymbolTable()
        self._reset()

    def _reset(self):
        self.xml = []
        self.idx = 0
        self.xmlT = None

    def _get_token(self, offset=0):
        return self.xmlT[self.idx + offset]

    def _extract_token(self, offset=0):
        token = self._get_token(offset)
        token_type = re.search(r'</(.+)>', token).group(1)
        token_val = re.search(r'> (.+) <', token).group(1)
        return token_type, token_val

    def _check_token(self, offset, rule_val=None, rule_type=None):
        # token = self._get_token(offset)
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
        return check

    def _check_current(self, rule_val=None, rule_type=None):
        return self._check_token(0, rule_val, rule_type)

    def _check_next(self, rule_val=None, rule_type=None):
        return self._check_token(1, rule_val, rule_type)

    def _write_token(self, rule_val=None, rule_type=None):
        # when you write, you must be write current token
        assert self._check_current(rule_val, rule_type), 'Compilation Error'
        self.xml.append(self._get_token())
        self.idx += 1

    def _write_symbol(self, var_name):
        symbol_info = self.symbol_table.query_of(var_name)
        self.xml[-1] += f' <!-- {symbol_info[0]} {symbol_info[1]} {symbol_info[2]} -->'

    def _compile_class(self, xmlT_codes):
        self.xml.append('<class>')
        self._write_token('class')
        self._write_token(None, 'identifier')  # className
        self._write_token('{')
        self._compile_classVarDec()
        self._complie_subroutineDec()
        self._write_token('}')
        self.xml.append('</class>')

    def _compile_classVarDec(self):
        while self._check_current(('static', 'field')):
            self.xml.append('<classVarDec>')
            _, var_kind = self._extract_token()
            self._write_token(('static', 'field'))
            _, var_type = self._extract_token()
            self._write_token(('int', 'char', 'boolean'), 'identifier')  # type
            _, var_name = self._extract_token()
            self._write_token(None, 'identifier')
            self.symbol_table.define(var_name, var_type, var_kind)
            while self._check_current(','):
                self._write_token(',')
                _, var_name = self._extract_token()
                self.symbol_table.define(var_name, var_type, var_kind)
                self._write_token(None, 'identifier')
            self._write_token(';')
            self.xml.append('</classVarDec>')
            print(self.symbol_table.class_symbol_table)

    def _complie_subroutineDec(self):
        while self._check_current(('constructor', 'function', 'method')):
            self.symbol_table.start_subroutine()
            self.xml.append('<subroutineDec>')
            self._write_token(('constructor', 'function', 'method'))
            self._write_token(('int', 'char', 'boolean', 'void'), 'identifier')
            _, subroutine_name = self._extract_token()
            self._write_token(None, 'identifier')  # subroutineName
            self._write_token('(')
            self._complie_parameterList()
            self._write_token(')')
            self._complie_subroutineBody()
            print(subroutine_name)
            print(self.symbol_table.subroutine_symbol_table)

            self.xml.append('</subroutineDec>')

    def _complie_parameterList(self):
        self.xml.append('<parameterList>')
        if self._check_current(('int', 'char', 'boolean'), 'identifier'):
            _, var_type = self._extract_token()
            self._write_token(('int', 'char', 'boolean', 'identifier',))
            _, var_name = self._extract_token()
            self._write_token(None, 'identifier')
            self.symbol_table.define(var_name, var_type, 'argument')
            while self._check_current(','):
                self._write_token(',')
                _, var_type = self._extract_token()
                self._write_token(('int', 'char', 'boolean'), 'identifier')
                _, var_name = self._extract_token()
                self._write_token(None, 'identifier')
                self.symbol_table.define(var_name, var_type, 'argument')
        self.xml.append('</parameterList>')

    def _complie_subroutineBody(self):
        self.xml.append('<subroutineBody>')
        self._write_token('{')
        self._compile_varDec()
        self._compile_statements()
        self._write_token('}')
        self.xml.append('</subroutineBody>')

    def _compile_varDec(self):
        while self._check_current('var'):
            self.xml.append('<varDec>')
            self._write_token('var')
            _, var_type = self._extract_token()
            self._write_token(('int', 'char', 'boolean'), 'identifier')
            _, var_name = self._extract_token()
            self._write_token(None, 'identifier')
            self.symbol_table.define(var_name, var_type, 'local')
            while self._check_current(','):
                self._write_token(',')
                _, var_name = self._extract_token()
                self._write_token(None, 'identifier')
                self.symbol_table.define(var_name, var_type, 'local')
            self._write_token(';')
            self.xml.append('</varDec>')

    def _compile_statements(self):
        self.xml.append('<statements>')
        self._compile_statement()
        self.xml.append('</statements>')

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
        self.xml.append('<letStatement>')
        self._write_token('let')
        _, var_name = self._extract_token()
        self._write_token(None, 'identifier')
        self._write_symbol(var_name)
        if self._check_current('['):
            self._write_token('[')
            self._compile_expression()
            self._write_token(']')
        self._write_token('=')
        self._compile_expression()
        self._write_token(';')
        self.xml.append('</letStatement>')

    def _compile_ifStatement(self):
        self.xml.append('<ifStatement>')
        self._write_token('if')
        self._write_token('(')
        self._compile_expression()
        self._write_token(')')
        self._write_token('{')
        self._compile_statements()
        self._write_token('}')
        if self._check_current('else'):
            self._write_token('else')
            self._write_token('{')
            self._compile_statements()
            self._write_token('}')
        self.xml.append('</ifStatement>')

    def _compile_whileStatement(self):
        self.xml.append('<whileStatement>')
        self._write_token('while')
        self._write_token('(')
        self._compile_expression()
        self._write_token(')')
        self._write_token('{')
        self._compile_statements()
        self._write_token('}')
        self.xml.append('</whileStatement>')

    def _compile_doStatement(self):
        self.xml.append('<doStatement>')
        self._write_token('do')
        self._compile_subroutineCall()
        self._write_token(';')
        self.xml.append('</doStatement>')

    def _compile_returnStatement(self):
        self.xml.append('<returnStatement>')
        self._write_token('return')
        if not self._check_current(';'):
            self._compile_expression()
        self._write_token(';')
        self.xml.append('</returnStatement>')

    def _compile_expression(self):
        self.xml.append('<expression>')
        self._compile_term()
        while self._check_current(self.op):
            self._write_token(self.op)
            self._compile_term()
        self.xml.append('</expression>')

    def _compile_term(self):
        self.xml.append('<term>')
        if self._check_current(None, 'integerConstant'):
            self._write_token(None, 'integerConstant')
        elif self._check_current(None, 'stringConstant'):
            self._write_token(None, 'stringConstant')
        elif self._check_current(self.keyword_constant):
            self._write_token(self.keyword_constant)
        elif self._check_current('('):
            self._write_token('(')
            self._compile_expression()
            self._write_token(')')
        elif self._check_current(self.unary_op):
            self._write_token(self.unary_op)
            self._compile_term()
        else:  # varName | varName[] | subroutineName() | (className|varName).
            if self._check_next('['):
                self._write_token(None, 'identifier')
                self._write_token('[')
                self._compile_expression()
                self._write_token(']')
            elif self._check_next(('(', '.')):
                self._compile_subroutineCall()
            else:
                self._write_token(None, 'identifier')

        self.xml.append('</term>')

    def _compile_subroutineCall(self):
        if not self._check_next('.'):
            self._write_token(None, 'identifier')
            self._write_token('(')
            self._compile_expressionList()
            self._write_token(')')
        else:
            self._write_token(None, 'identifier')
            self._write_token('.')
            self._write_token(None, 'identifier')
            self._write_token('(')
            self._compile_expressionList()
            self._write_token(')')

    def _compile_expressionList(self):
        self.xml.append('<expressionList>')
        if not self._check_current(')'):
            self._compile_expression()
            while self._check_current(','):
                self._write_token(',')
                self._compile_expression()
        self.xml.append('</expressionList>')

    def parser(self, xmlT_codes, xml_path):
        self.xmlT = xmlT_codes
        self._compile_class(xmlT_codes)
        # print(self.xml)
        with open(xml_path, 'w', encoding='utf8') as fpw:
            fpw.write('\n'.join(self.xml))
            fpw.write('\n')
        self._reset()


class JackAnalyzer:
    def __init__(self):
        self.jack_tokenizer = JackTokenizer()
        self.compilation_engine = CompilationEngine()

    def syntax_analyzer_file(self, jack_path):
        head, tail = os.path.split(jack_path)
        fname, ext = os.path.splitext(tail)
        xmlT_path = os.path.join(head, fname + 'T_dev.xml')  # token.xml
        xmlT_codes = self.jack_tokenizer.tokenizing(jack_path, xmlT_path)
        xml_path = os.path.join(head, fname + '_dev.xml')
        self.compilation_engine.parser(xmlT_codes, xml_path)

    def syntax_analyzer(self, jack_path):
        fname, ext = os.path.splitext(jack_path)
        if ext == '.jack':  # single file
            self.syntax_analyzer_file(jack_path)
        else:  # project directory
            for root, _, files in os.walk(jack_path):
                for f in files:
                    if os.path.splitext(f)[-1] == '.jack':
                        self.syntax_analyzer_file(os.path.join(root, f))


if __name__ == '__main__':
    import subprocess
    jack_analyzer = JackAnalyzer()

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

                jack_analyzer.syntax_analyzer(root)

                for f in jack_filename:
                    # tokenizing_answer = os.path.join(root, f + 'T.xml')
                    # tokenizing_dev = os.path.join(root, f + 'T_dev.xml')
                    # print(f'Tokenizing Check: {tokenizing_answer}')
                    # subprocess.run([text_comparer, tokenizing_answer, tokenizing_dev], check=True)
                    parser_answer = os.path.join(root, f + '.xml')
                    parser_dev = os.path.join(root, f + '_dev.xml')
                    print(f'Parsing Check: {parser_answer}')
                    subprocess.run([text_comparer, parser_answer, parser_dev], check=True)
    # full_test()
    # jack_analyzer.syntax_analyzer('./Square\Main.jack')
    jack_analyzer.syntax_analyzer('./Square\Main.jack')
