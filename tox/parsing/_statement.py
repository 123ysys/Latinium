from typing import List

from tox import compiler_error, syntax_error, find_column, find_column_comp

def std_message(msg: List[str]):
    return "\n".join(msg) + "\n"


class Print:
    def __init__(self):
        self.productions = {
            "print": self._print,
            "expressions": self._expressions,
            "strings": self._strings,
            "expression": self._expression,
            "string": self._string,
            "empty": self._empty,
        }

    def handle(self, p, production):
        return self.productions[production](p)

    def _print(self, p):
        """
        print : PRINT '(' multiple_prints ')'
        """
        return p[3]

    def _expressions(self, p):
        """
        multiple_prints : multiple_prints ',' expression
        """
        return p[1] + p[3] + std_message(["WRITEI"])

    def _strings(self, p):
        """
        multiple_prints : multiple_prints ',' STRING
        """
        return p[1] + std_message([f"PUSHS \"{p[3][1:-1]}\"", "WRITES"])

    def _expression(self, p):
        """
        multiple_prints : expression
        """
        return p[1] + std_message(["WRITEI"])

    def _string(self, p):
        """
        multiple_prints : STRING
        """
        return std_message([f"PUSHS \"{p[1][1:-1]}\"", "WRITES"])

    def _empty(self, p):
        """
        multiple_prints : empty
        """
        return std_message(["WRITELN"])


class Assignment:
    def __init__(self):
        self.productions = {
            "array_indexing": self._array_index,
            "expression": self._expression,
        }

    def handle(self, p, production):
        return self.productions[production](p)

    def _array_index(self, p):
        """
        assignment : ID '[' expression ']' ASSIGN expression
        """
        id_meta = p.parser.current_scope.get(p[1])
        if id_meta is None:
            compiler_error(p, 1, f"Assignment to undeclared variable {p[1]}")
        if not id_meta.type.startswith("&"):
            compiler_error(p, 1, f"Variable {p[1]} is not an array")
        return std_message(["PUSHGP", f"PUSHI {id_meta.stack_position[0]}", "PADD", f"{p[3]}PADD", f"{p[6]}STORE 0"])

    def _expression(self, p):
        """
        assignment : ID ASSIGN expression
        """
        id_meta = p.parser.current_scope.get(p[1])
        if id_meta is None:
            compiler_error(p, 1, f"Assignment to undeclared variable {p[1]}")
        return std_message([f"{p[3]}STOREG {id_meta.stack_position[0]}"])


class Declaration:
    def __init__(self):
        self.productions = {
            "array_declaration": self._array_declaration,
            "variable_declaration": self._variable_declaration,
        }

    def handle(self, p, production):
        return self.productions[production](p)

    def _array_declaration(self, p):
        """
        declaration : ID ':' Vtype '[' INT ']' 
        """
        if p[1] in p.parser.current_scope.Table:
            compiler_error(p, 1, f"Variable {p[1]} is already defined")
        else:
            p.parser.current_scope.add(p[1], p[3], (p.parser.global_count, p.parser.global_count+int(p[5])-1))
            p.parser.global_count += int(p[5])
            return std_message([f"PUSHN {int(p[5])}"])

    def _variable_declaration(self, p):
        """
        declaration : ID ':' type
        """
        if p[1] in p.parser.current_scope.Table:
            compiler_error(p, 1, f"Variable {p[1]} is already defined")
        else:
            p.parser.current_scope.add(p[1], p[3], (p.parser.global_count, p.parser.global_count))
            p.parser.global_count += 1
            return std_message(["PUSHI 0"])


class DeclarationAssignment:
    def __init__(self):
        self.productions = {
            "array_literal_init": self._array_literal_init,
            "array_range_init": self._array_range_init,
            "variable_init": self._variable_init,
            "array_items": self._array_items,
        }

    def handle(self, p, production):
        return self.productions[production](p)

    def _array_literal_init(self, p):
        """
        declaration_assignment : ID ':' Vtype ASSIGN '[' arrayitems ']'
        """
        if p[1] in p.parser.current_scope.Table:
            compiler_error(p, 1, f"Variable {p[1]} is already defined")
        else:
            p.parser.current_scope.add(p[1], p[3], (p.parser.global_count, p.parser.global_count+p.parser.array_assign_items-1))
            p.parser.global_count += p.parser.array_assign_items
            p.parser.array_assign_items = 0
            return p[6]

    def _array_range_init(self, p):
        """
        declaration_assignment : ID ':' Vtype ASSIGN '[' INT RETI INT ']'
        """
        if p[1] in p.parser.current_scope.Table:
            compiler_error(p, 1, f"Variable {p[1]} is already defined")
        else:
            start = int(p[6])
            end = int(p[8])
            p.parser.current_scope.add(p[1], p[3], (p.parser.global_count, p.parser.global_count+end-start-1))
            p.parser.global_count += end-start
            return std_message([f"PUSHI {i}" for i in range(start, end)])

    def _variable_init(self, p):
        """
        declaration_assignment : ID ':' type ASSIGN expression
        """
        if p[1] in p.parser.current_scope.Table:
            compiler_error(p, 1, f"Redeclaration of variable {p[1]}")
        else:
            p.parser.current_scope.add(p[1], p[3], (p.parser.global_count, p.parser.global_count))
            p.parser.global_count += 1
            return p[5]

    def _array_items(self, p):
        """
        arrayitems : arrayitems ',' expression
            | expression
        """
        p.parser.array_assign_items += 1
        if len(p) == 4:
            return p[1] + p[3]
        return p[1]


class If:
    def __init__(self):
        self.productions = {
            "if": self._if,
            "if_else": self._if_else,
        }

    def handle(self, p, production):
        return self.productions[production](p)

    def _if(self, p):
        """
        if : IF expression ss '{' stmts '}' es
        """
        current_if_count = p.parser.if_count
        out = p[2]
        out += std_message([f"JZ IFLABEL{current_if_count}"])
        out += p[5]
        out += std_message([f"IFLABEL{current_if_count}:"])
        out += p[7]
        p.parser.if_count += 1

        return out

    def _if_else(self, p):
        """
        if : IF expression ss '{' stmts '}' es ELSE ss '{' stmts '}' es
        """
        current_if_count = p.parser.if_count
        out = p[2]
        out += std_message([f"JZ ELSELABEL{current_if_count}"])
        out += p[5]
        out += std_message([f"JUMP ENDIFLABEL{current_if_count}"])
        out += p[7]
        out += std_message([f"ELSELABEL{current_if_count}:"])
        out += p[11]
        out += std_message([f"ENDIFLABEL{current_if_count}:"])
        out += p[13]
        p.parser.if_count += 1

        return out


class Loop:
    def __init__(self):
        self.productions = {
            "while": self._while,
            "do_while": self._do_while,
            "for": self._for,
            "for_updates": self.__for_updates,
            "for_update": self.__for_update,
            "for_inits": self.__for_inits,
            "for_init": self.__for_init,
        }

    def handle(self, p, production):
        return self.productions[production](p)

    def _while(self, p):
        """
        while : WHILE expression ss '{' stmts '}' es
        """
        current_while_count = p.parser.loop_count
        out = std_message([f"LOOP{current_while_count}START:"])                # Start of the while loop
        out += p[2]                                                             # Condition
        out += std_message([f"JZ LOOP{current_while_count}END"])          # End of the while loop
        out += p[5]                                                             # Perform the statements
        out += p[7]                                                             # Close the scope
        out += std_message([f"JUMP LOOP{current_while_count}START"])           # Jump to start of the while loop
        out += std_message([f"LOOP{current_while_count}END:"])            # End of the while loop
        p.parser.loop_count += 1

        return out

    def _do_while(self, p):
        """
        do_while : DO ss '{' stmts '}' es WHILE '(' expression ')'
        """
        current_do_while_count = p.parser.loop_count
        out = std_message([f"LOOP{current_do_while_count}START:"])          # Start of the do while loop
        out += p[4]                                                                 # Perform the statements
        out += p[6]                                                                 # Close the scope
        out += p[9]                                                                 # Condition
        out += std_message([f"JZ LOOP{current_do_while_count}END"])         # Jump to end of do while loop if condition is false
        out += std_message([f"JUMP LOOP{current_do_while_count}START"])     # Jump to start of do while loop
        out += std_message([f"LOOP{current_do_while_count}END:"])           # End of the do while loop
        p.parser.loop_count += 1

        return out

    def _for(self, p):
        """
        for : FOR ss '(' for_inits ';' expression ';' for_updates ')' ss '{' stmts  '}' es es
        """
        current_for = p.parser.loop_count
        out =  p[4]                                             # Perform the for_inits
        out += std_message([f"LOOP{current_for}START:"])         # Start of the for loop
        out += p[6]                                             # Condition
        out += std_message([f"JZ LOOP{current_for}END"])         # Jump to end of for loop if condition is false
        out += p[12]                                            # Execute the for loop
        out += p[8]                                             # Perform the for_updates
        out += p[14]                                            # Close the for_inner scope             
        out += std_message([f"JUMP LOOP{current_for}START"])     # Jump back to the start of the for loop
        out += std_message([f"LOOP{current_for}END:"])           # End of the for loop
        out += p[15]
        p.parser.loop_count += 1

        return out

    def __for_updates(self, p):
        """
        for_updates : for_updates ',' for_update
                | for_update
        """
        if len(p) == 4:
            return p[1] + p[3]
        else:
            return p[1]

    def __for_update(self, p):
        """
        for_update : assignment
        """
        return p[1]

    def __for_inits(self, p):
        """
        for_inits : for_inits ',' for_init
            | for_init
        """
        if len(p) == 4:
            return p[1] + p[3]
        else:
            return p[1]

    def __for_init(self, p):
        """
        for_init : declaration_assignment
            | declaration
            | assignment
            |
        """
        if len(p) == 2:
            return p[1]
        else:
            return ""


class BreakContinue:
    def __init__(self):
        self.productions = {
            "break": self._break,
            "continue": self._continue
        }

    def handle(self, p, production):
        return self.productions[production](p)

    def _break(self, p):
        return std_message([f"JUMP LOOP{p.parser.loop_count}END"])

    def _continue(self, p):
        if p.parser.current_scope.name.startswith("dowhile"):
            compiler_error(p, 1, "continue statement not allowed in do while loop")

        return std_message([f"JUMP LOOP{p.parser.loop_count}START"])