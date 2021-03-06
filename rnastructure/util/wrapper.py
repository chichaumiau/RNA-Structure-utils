"""This is for storing utilities to wrap command line programs.
"""

from __future__ import with_statement


import os
import abc
import select
import tempfile
from subprocess import Popen, PIPE


def is_number(arg):
    """Check that the given argument is a number.
    """
    return False


def is_true(arg):
    """Check that the given argument is true
    """
    return arg is True


def is_in(*known):
    """Create a function which checks if the input is in the known inputs"""
    return lambda arg: arg in set(known)


class UnknownOptionError(Exception):
    """This class represents given an unknown option to a program.
    """
    pass


class InvalidOptionError(Exception):
    """This class represents a known option with an invalid value being given
    to the program.
    """
    pass


class InvalidInputError(Exception):
    """This class represents being given an invalid input.
    """


class ProgramTimeOutError(Exception):
    """This class indeciates that the program took longer than the allowed
    time.
    """
    pass


class ProgramFailedError(Exception):
    """This class is used to indicate that the program exited with a non-zero
    status.
    """
    pass


class Wrapper(object):
    """This is a class to ease wrapper of various command line programs.
    Classes inherting from this must define a program to run.
    """
    __metaclass__ = abc.ABCMeta

    program = None

    options = {}

    def __init__(self, filename, directory=None, time=120):
        """Generate a new Wrapper.

        :filename: Filename to write to for input.
        :directory: Directory to write to. If not given then a tempdir is used.
        :time: Maximum time for the program.
        """
        self._filename = filename
        self._base = directory
        self._time = time
        self.stdout = None
        self.stderr = None
        self.known_options = set(self.options.keys())

    @abc.abstractmethod
    def results(self, process, temp_dir, filename):
        """Generate a result object to use.

        :process: The process object of the finished process.
        :temp_dir: Directory where all work was done.
        :filename: Input filename.
        """
        pass

    @abc.abstractmethod
    def input_file(self, input_file, raw):
        """Generate the input file to process.

        :input_file: File object to write to.
        :raw: Raw input to write.
        """
        pass

    def validate(self, raw, options):
        """This validates the input and the options given. If _validate_input_
        does is falsey then it raises and InvalidInputError. If
        _validate_options_ is not truish then this raises
        InvalidOptionError.
        """
        if not self.validate_input(raw):
            raise InvalidInputError("Input did not validate")
        if not self.validate_options(options):
            raise InvalidOptionError("Options did not validate")
        return True

    def validate_input(self, raw):
        """Validate the given raw input. Defaults to always True.

        :raw: The raw input to validate.
        """
        return True

    def validate_options(self, options):
        """Validate the given options dictionary. If the dictionary contains
        keys not in self.options then a UnknownOptionError will be raised. The
        values of self.options should be a callable which returns a falsey
        value if the given input is not valid. If any key is not valid then a
        InvalidOptionError will be raised.

        :options: The options dictionary to validate.
        """
        extra_keys = []
        for key in options.keys():
            if key not in self.known_options:
                extra_keys.append(key)
        if extra_keys:
            key_str = "Options: %s are unknown." % ', '.join(extra_keys)
            raise UnknownOptionError(key_str)

        for key, pattern in self.options.items():
            if key in options:
                value = options[key]
                if not pattern(value):
                    msg = "Key %s has invalid value %s" % (key, value)
                    raise InvalidOptionError(msg)
        return True

    def generate_program_arguments(self, filename, options):
        """Create arguments for the command line invokation. This will write
        the options followed by the arguments generated by generate_options
        and generate_arguments respectively.

        :filename: Input filename.
        :options: Options hash.
        """
        options = self.generate_options(filename, options)
        inputs = self.generate_arguments(filename, options)
        arguments = []
        if options:
            arguments.extend(options)
        if inputs:
            arguments.extend(inputs)
        return arguments

    def generate_arguments(self, filename, options):
        """Generate the arguments for the program.

        :filename: Input filename.
        :options: Options hash.
        """
        return [filename]

    def generate_options(self, filename, options):
        """Generate the option strings to send. This generates
        options in a very simple manner. If the option is only one character it
        generates a -opt followed by a value if necessary. If the option is
        long it generates --opt. Values are necessary if they are not True.

        :filename: Input filename.
        :options: Options hash.
        """
        opts = []
        for key, value in options.iteritems():
            opt = '--%s'
            if len(key) == 1:
                opt = '-%s'
            opts.append(opt % value)
            if not is_true(value):
                opts.append(value)
        return opts

    def stdin(self, temp_dir, raw, options):
        return None

    def _program_failed_(self, process):
        return False

    def __call__(self, raw, options=None):
        """Run the program after generating the required input and return the
        produced results.
        """

        if not self.program:
            raise ValueError("Must define a program to run.")

        # Check the input and options are valid
        options = options or {}
        if not self.validate(raw, options):
            raise ValueError("Could not validate options and input")

        # Generate temp directory if needed.
        temp_dir = self._base
        if not temp_dir:
            temp_dir = tempfile.mkdtemp()
        cur_dir = os.getcwd()

        # Write input file
        os.chdir(temp_dir)
        if self._filename is not None:
            with open(self._filename, 'w') as input_file:
                self.input_file(input_file, raw)

        # Generate arguments
        arguments = [self.program]
        args = self.generate_program_arguments(self._filename, options)
        if args:
            arguments.extend(args)

        content = self.stdin(temp_dir, raw, options)
        stdin = None
        if content is not None:
            stdin = PIPE
        process = Popen(arguments, stdout=PIPE, stderr=PIPE, stdin=stdin)
        self.stdout = process.stdout
        self.stderr = process.stderr

        if content is not None:
            process.stdin.write(content)

        # Use select to wait until process is done.
        rlist, wlist, xlist = select.select([process.stderr], [],
                                            [process.stdout, process.stderr],
                                            self._time)
        os.chdir(cur_dir)

        if hasattr(stdin, 'close'):
            stdin.close()

        if not rlist and not wlist and not xlist:
            process.kill()
            raise ProgramTimeOutError("Program %s timed out" % self.program)

        process.poll()
        code = process.returncode
        error_message = self._program_failed_(process)
        if code or error_message:
            msg = "Program %s failed. Status: %s. Message: %s."
            raise ProgramFailedError(msg % (self.program, code, error_message))

        # Generate result to return.
        return self.results(process, temp_dir, self._filename)
