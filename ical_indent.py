#!/usr/bin/env python
from __future__ import print_function
import fileinput

START_PREFIX = 'begin:'
END_PREFIX = 'end:'
INDENT = " "*4

class IcsParseError(Exception):
    def __init__(*args, **kwargs):
        super(Exception, self).__init__(*args, **kwargs)


class TimezoneStripper(object):
    _in_timezone = False
    def __init__(self, lines):
        self.lines = lines

    def __iter__(self):
        for line in self.lines:
            _line = line.strip().upper()
            if _line == BEGIN_VTIMEZONE:
                self._in_timezone = True

            if not self._in_timezone:
                yield line

            if _line == END_VTIMEZONE:
                self._in_timezone = False



def main():
    types = []
    indent_depth = 0
    for line in TimezoneStripper(fileinput.input()):
        line = line.strip()
        
        if line.lower().startswith(END_PREFIX):
            end_type = line[len(END_PREFIX):]
            start_type = types.pop()
            if start_type.lower() != end_type.lower():
                raise IcsParseError(
                    '{}:{}:Mismatched END of {}, expected {}'.format(
                        fileinput.filename(), 
                        fileinput.filelineno(), 
                        end_type, 
                        start_type))
            indent_depth -= 1

        print((INDENT*indent_depth)+line)

        if line.lower().startswith(START_PREFIX):
            start_type = line[len(START_PREFIX):]
            types.append(start_type)
            indent_depth += 1

if __name__ == '__main__': main()