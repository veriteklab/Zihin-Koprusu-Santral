import re
from itertools import zip_longest


class LooseVersion:
    def __init__(self, vstring=None):
        self.vstring = ""
        self.version = []
        if vstring is not None:
            self.parse(vstring)

    def parse(self, vstring):
        self.vstring = str(vstring)
        parcalar = re.findall(r"[0-9]+|[A-Za-z]+", self.vstring)
        temiz = []
        for parca in parcalar:
            temiz.append(int(parca) if parca.isdigit() else parca.lower())
        self.version = temiz
        return self

    def _cmp(self, other):
        if not isinstance(other, LooseVersion):
            other = LooseVersion(other)
        for a, b in zip_longest(self.version, other.version, fillvalue=0):
            if a == b:
                continue
            return -1 if a < b else 1
        return 0

    def __lt__(self, other):
        return self._cmp(other) < 0

    def __le__(self, other):
        return self._cmp(other) <= 0

    def __eq__(self, other):
        return self._cmp(other) == 0

    def __ge__(self, other):
        return self._cmp(other) >= 0

    def __gt__(self, other):
        return self._cmp(other) > 0

    def __repr__(self):
        return f"LooseVersion('{self.vstring}')"
