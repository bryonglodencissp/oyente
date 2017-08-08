import re
import json
from utils import run_solc_compiler

class SourceMap:
    position_groups = {}
    filename = ""

    def __init__(self, cname, filename):
        self.cname = cname
        self.__class__.filename = filename
        self.source = self.__load_source()
        self.line_break_positions = self.__load_line_break_positions()
        if not self.__class__.position_groups:
            self.__class__.position_groups = self.__load_position_groups()
        self.positions = self.__load_positions()
        self.instr_positions = {}

    def set_instr_positions(self, pc, pos_idx):
        self.instr_positions[pc] = self.positions[pos_idx]

    def find_source_code(self, pc):
        pos = self.instr_positions[pc]
        begin = pos['begin']
        end = pos['end']
        return self.source[begin:end]

    def to_str(self, pc):
        position = self.__get_position(pc)
        source_code = self.find_source_code(pc)
        s = "%s:%s:%s\n" % (self.cname, position['begin']['line'], position['begin']['column'])
        s += source_code + "\n"
        s += "^"
        return s

    def __load_source(self):
        source = ""
        with open(self.__get_filename(), 'r') as f:
            source = f.read()
        return source

    def __load_line_break_positions(self):
        return [i for i, letter in enumerate(self.source) if letter == '\n']

    @classmethod
    def __load_position_groups(cls):
        cmd = "solc  --optimize --asm-json %s"
        out = run_solc_compiler(cmd, cls.filename)
        out = out[0]

        reg = r"======= (.*?) =======\nEVM assembly:\n"
        out = re.compile(reg).split(out)
        out = out[1:]
        out = dict(zip(out[0::2], out[1::2]))

        c_asm = {}
        for cname in out:
            try:
                idx = out[cname].index("}{") + 1
                c_asm[cname] = out[cname][:idx]
            except:
                continue
        return cls.__extract_position_groups(c_asm)

    @classmethod
    def __extract_position_groups(cls, c_asm):
        for cname in c_asm:
            asm = json.loads(c_asm[cname])
            asm = asm[".code"]
            pattern = re.compile("^tag")
            asm = [instr for instr in asm if not pattern.match(instr["name"])]
            c_asm[cname] = asm
        return c_asm

    def __load_positions(self):
        return self.__class__.position_groups[self.cname]

    def __get_position(self, pc):
        pos = self.instr_positions[pc]
        return self.__convert_offset_to_line_column(pos)

    def __convert_offset_to_line_column(self, pos):
        ret = {}
        ret['begin'] = None
        ret['end'] = None
        if pos['begin'] >= 0 and (pos['end'] - pos['begin'] + 1) >= 0:
            ret['begin'] = self.__convert_from_char_pos(pos['begin'])
            ret['end'] = self.__convert_from_char_pos(pos['end'])
        return ret

    def __convert_from_char_pos(self, pos):
        line = self.__find_lower_bound(pos, self.line_break_positions)
        if self.line_break_positions[line] != pos:
            line += 1
        begin_col = 0 if line == 0 else self.line_break_positions[line - 1] + 1
        col = pos - begin_col
        return {'line': line, 'column': col}

    def __find_lower_bound(self, target, array):
        start = 0
        length = len(array)
        while length > 0:
            half = length >> 1
            middle = start + half
            if array[middle] <= target:
                length = length - 1 - half
                start = middle + 1
            else:
                length = half
        return start - 1

    def __get_filename(self):
        return self.cname.split(":")[0]