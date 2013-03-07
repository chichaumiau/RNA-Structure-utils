import re

import rnastructure.secondary.basic as basic

START_PAIRS = re.compile('^/pairs\s*\[$')
END_PAIRS = re.compile('^\]\s*def$')
PAIR = re.compile('^\[(\d+)\s*(\d+)\]$')

START_COORD = re.compile('^/coor\s*\[$')
END_COORD = re.compile('^]\s*def$')
COORD = re.compile('^\[(\d+\.\d+)\s*(\d+\.\d+)\]$')

START_SEQUENCE = re.compile('^/sequence\s*\(\\$')
END_SEQUENCE = re.compile('^\)\s*def$')
SEQUENCE = re.compile('^(\w+)\\$')


class NoLocationAnnotations(Exception):
    """This error is raise when we cannot find the part of the postscript which
    specifies where to put the nucleotides.
    """
    pass


class NoPairsAnnotations(Exception):
    """This error is raised when we cannot find the pairing information in the
    psotscript.
    """
    pass


class NoSequenceAnnotation(Exception):
    """This exception is raised if we cannot find the part of the postscript
    that specifies the sequence.
    """
    pass


class Parser(basic.Parser):
    """This is a class to read a postscript file generated by the output of
    RNAalifold to get the 2D information as well as coordinates to draw an
    airport diagram.
    """

    # TODO: Make the parser smarter, no need for 3x reading.
    def __init__(self, stream):
        self.sequence = self.__sequence__(stream)
        #self.locations = self.__locations__(stream)
        #self.pairs = self.__pairs__(stream)
        #super(Parser, self).__init__(self.pairs)

    def __locations__(self, stream):
        found = False
        locations = []
        for line in stream:
            if START_COORD.match(line):
                found = True
            elif END_COORD.match(line):
                found = False
            match = COORD.match(line)
            if found and match:
                loc = (float(match.group(1)), float(match.group(2)))
                locations.append(loc)

        if not locations:
            raise NoLocationAnnotations("Could not find any pairs annotations")

        return locations

    def __pairs__(self, stream):
        found = False
        pairs = [None] * len(self.locations)
        for line in stream:
            if START_PAIRS.match(line):
                found = True
            elif END_PAIRS.match(line):
                found = False
            match = PAIR.match(line)
            if found and match:
                first = match.group(1)
                second = match.group(2)
                pairs.insert(first, second)
                pairs.insert(second, first)

        if not pairs:
            raise NoPairsAnnotations("Could not find any pairs annotations")

        return pairs

    def __sequence__(self, stream):
        found = False
        sequence = []
        for line in stream:
            line = line.rstrip()
            if START_SEQUENCE.match(line):
                found = True
            elif END_SEQUENCE.match(line):
                found = False

            match = SEQUENCE.match(line)
            if found and match:
                sequence.append(match.groups(1))

        return ''.join(sequence)