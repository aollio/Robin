#!/usr/bin/env python3
from functools import partial
import logging
from lexer import PeekTokenLexer
from robin.util import log_def
from robin import ast
from lexer import tokens
from robin.settings import INDENT_LENGTH

__author__ = 'Aollio Hou'
__email__ = 'aollio@outlook.com'

log_def = log_def(name='parser')
logger = logging.getLogger('parser')


###############################################################################
#                                                                             #
#  Parser                                                                     #
#                                                                             #
###############################################################################

class Parser:
    def __init__(self, lexer: PeekTokenLexer):
        self.lexer = lexer
        self.indent = 0
        self.current_token = lexer.next_token()

    def error(self, type=None, value=None):
        msg = 'Invalid syntax. Unknown identity %s. ' % (self.current_token,)
        if type:
            msg += 'Need Token %r, %r' % (type, value)
        raise Exception(msg)

    def eat(self, type):
        if self.current_token.type == type:
            self.current_token = self.lexer.next_token()
        else:
            self.error(type)

    @log_def
    def program(self):
        """
        Program.
            <program> -> <block>
        :return:
        """
        return ast.Program(self.block())

    @log_def
    def function_def(self):
        """
        Function definition.
            <function_def> -> DEF <variable> <argument_list> COLON NEWLINE INDENT <block>
        :return:
        """
        # todo using <params_list> replace the <argument_list>
        token = self.current_token
        self.eat('def')
        name = self.variable()
        params = self.argument_list()
        self.eat(':')
        self.eat(tokens.NEWLINE)
        self.indent += 1
        block = self.block()
        self.indent -= 1

        return ast.FunctionDef(name=name, params=params, block=block)

    @log_def
    def block(self):
        """
        A code Block.
            <block> -> <statement> | <statement> (<statement>)*
        :return:
        """
        result = []
        while self.check_indent() and self.current_token.value != tokens.EOF:
            self.eat_indent()
            result.append(self.statement())
        return ast.Block(children=result)

    @log_def
    def statement(self):
        """
        A statement tokens.
             <statement> -> <assign_statement>
                         -> <function_call> NEWLINE
                         -> <empty>
                         -> <if_statement>
                         -> <while_statement>
                         -> <function_def>
        :return:
        """
        statement = None
        # 分辨是赋值，还是函数调用
        if self.current_token.type == tokens.ID:
            if self.lexer.peek_token() is None:
                statement = self.empty()
            elif self.lexer.peek_token().value == tokens.delimiter['(']:
                statement = self.function_call()
                self.eat(tokens.NEWLINE)
            elif self.lexer.peek_token().value == tokens.delimiter['=']:
                statement = self.assign_statement()
            else:
                statement = self.empty()
        elif self.current_token.value == tokens.keywords.IF:
            statement = self.if_statement()
        elif self.current_token.value == tokens.keywords.WHILE:
            statement = self.while_statement()
        elif self.current_token.value == tokens.keywords.DEF:
            statement = self.function_def()
        else:
            statement = self.empty()

        return statement

    @log_def
    def function_call(self):
        """
        Function call.
            <function_call> -> <variable> <argument_list>
        :return:
        """
        fun_name = self.variable()
        arg_list = self.argument_list()
        return ast.FunctionCall(name=fun_name, args=arg_list)

    @log_def
    def argument_list(self) -> list:
        """
        Arguments list.
            <argument_list> -> LPAREN (<expr> (COMMA <expr>)*)? RPAREN
        :return:
        """
        args = []
        self.eat("(")
        if self.current_token.value != ')':
            args.append(self.expr())
            while self.current_token.value == ',':
                self.eat(',')
                args.append(self.expr())
        self.eat(')')
        return args

    @log_def
    def while_statement(self):
        """
        `while` statement:
            <while_statement> -> WHILE <expression> COLON NEWLINE INDENT <block> DEDENT
        :return:
        """
        token = self.current_token
        self.eat('while')
        condition = self.expr()
        self.eat(':')
        self.eat(tokens.NEWLINE)
        self.indent += 1
        right_block = self.block()
        self.indent -= 1

        return ast.While(condition=condition, token=token, block=right_block)

    @log_def
    def if_statement(self):
        """
        `if` statement:
            <if_statement> -> IF <expr> COLON NEWLINE INDENT <block> <elif_statement>

        :return:
        """
        token = self.current_token
        self.eat('if')
        condition = self.expr()
        self.eat(':')
        self.eat(tokens.NEWLINE)

        self.indent += 1
        right_block = self.block()
        self.indent -= 1
        wrong_block = self.elif_statement()

        return ast.If(condition=condition, token=token, right_block=right_block, wrong_block=wrong_block)

    @log_def
    def elif_statement(self):
        """
        `elif` statement:
            <elif_statement> -> ELIF <expr> COLON NEWLINE INDENT <block> <elif_statement>*
                             -> ELSE COLON NEWLINE INDENT <block>
                             -> <empty>
        :return:
        """
        if self.current_token.value == 'elif':
            token = self.current_token
            self.eat('elif')
            condition = self.expr()
            self.eat(':')
            self.eat(tokens.NEWLINE)
            self.indent += 1
            right_block = self.block()
            self.indent -= 1
            wrong_block = self.elif_statement()
            return ast.If(condition, token, right_block, wrong_block)
        elif self.current_token.value == tokens.keywords.ELSE:
            self.eat('else')
            self.eat(':')
            self.eat(tokens.NEWLINE)

            self.indent += 1
            block = self.block()
            self.indent -= 1
            return block
        else:
            return self.empty()

    @log_def
    def empty(self):
        if self.current_token.type == tokens.NEWLINE:
            self.eat(tokens.NEWLINE)
        return ast.EmptyOp()

    @log_def
    def assign_statement(self):
        """
        Assign statementokens.
            <assign_statement> -> <variable> ASSIGN <expr> NEWLINE
        :return:
        """
        left = self.variable()
        token = self.current_token
        self.eat('=')
        right = self.expr()
        self.eat(tokens.NEWLINE)
        return ast.Assign(left=left, token=token, right=right)

    @log_def
    def variable(self):
        """
        A variable.
            <variable> -> Identity
        :return:
        """
        vartoken = self.current_token
        self.eat(tokens.ID)
        return ast.Var(token=vartoken)

    @log_def
    def expr(self):
        """
        A expression statementokens.
            <expr> -> <term_plus_minus> ((EQUAL|LESS_THAN|LESS_EQUAL|GREAT_THAN|GREAT_EQUAL) <term_plus_minus>)*
        :return:
        """
        node = self.term_plus_minus()

        while self.current_token.value in tokens.operator:
            # operator plus or minus
            op = self.current_token
            self.eat(self.current_token.value)
            right = self.term_plus_minus()
            node = ast.Op(left=node, op=op, right=right)

        return node

    @log_def
    def term_plus_minus(self):
        """
        One or Two terms of addition or subtraction.
            <term_plus_minus> -> <term_mul_div> ((PLUS|MINUS) <term_mul_div>)*
        :return:
        """
        node = self.term_mul_div()

        while self.current_token.value in '+-':
            # operator plus or minus
            op = self.current_token
            self.eat(self.current_token.type)
            right = self.term_mul_div()
            node = ast.Op(left=node, op=op, right=right)

        return node

    @log_def
    def term_mul_div(self):
        """
        One or Two terms of multiplication or division.
            <term_mul_div> -> <factor> ((MUL|DIV) <factor>)*
        :return:
        """
        node = self.factor()

        while self.current_token.value in '*/':
            op = self.current_token
            self.eat(self.current_token.value)
            right = self.factor()

            node = ast.Op(left=node, op=op, right=right)

        return node

    @log_def
    def factor(self):
        """
        A factor.
            <factor> -> (+|-) <factor>
                     -> CONST_INTEGER
                     -> <variable>
                     -> LPAREN <expr> RPAREN
                     -> <function_call>
                     -> tokens.keywords['True']
                     -> CONST_REGULAR_STR
        :return:
        """

        if self.current_token.type in '+-':
            op = self.current_token
            if self.current_token.type == '+':
                self.eat('+')
                return ast.UnaryOp(op=op, expr=self.factor())
            elif self.current_token.value == '-':
                self.eat('-')
                return ast.UnaryOp(op=op, expr=self.factor())

        elif self.current_token.type == tokens.NUMBER:
            integer = self.current_token
            self.eat(self.current_token.type)
            return ast.Num(integer)

        elif self.current_token.type == tokens.ID:
            if self.lexer.peek_token().type == '(':
                return self.function_call()
            else:
                return self.variable()
        elif self.current_token.type == '(':
            self.eat('(')
            expr = self.expr()
            self.eat(')')
            return expr
        elif self.current_token.type in ('True', 'False'):
            booltoken = self.current_token
            print(booltoken)
            self.eat(self.current_token.type)
            return ast.Bool(booltoken)
        elif self.current_token.type == tokens.STRING:
            strtoken = self.current_token
            self.eat(tokens.STRING)
            return ast.RegularStr(strtoken)

    @log_def
    def parse(self):
        print('begin parse')
        node = self.program()
        # if self.current_token.value != EOF:
        #     self.error(need=EOF)
        return node

    @log_def
    def check_indent(self):
        indent = self.indent
        if indent == 0:
            return True
        if self.current_token.type != tokens.INDENT:
            return False

        if self.indent * INDENT_LENGTH != self.current_token.value:
            return False
        return True

    @log_def
    def eat_indent(self):
        indent = self.indent
        if self.current_token.type == tokens.INDENT:
            if indent * INDENT_LENGTH != self.current_token.value:
                raise IndentationError()
            self.eat(tokens.INDENT)

    def __repr__(self):
        return '<%s>' % self.__class__.__name__


def _main():
    import argparse
    import os
    parser = argparse.ArgumentParser("Simple pascal interpreter.")
    parser.add_argument('file', help='the pascal file name')
    args = parser.parse_args()
    text = open(file=os.path.join(__file__, args.file), encoding='utf-8').read()
    lexer = PeekTokenLexer(text)
    parser = Parser(lexer)
    # parser
    root_node = parser.parse()
    return root_node


if __name__ == '__main__':
    import logging

    logging.basicConfig(level=logging.INFO)
    _main()
