"""
All custom Exceptions
"""


# traceback from exceptions that inherit from this class are suppressed
class CommandLineError(Exception):
    """The traceback of all CommandLineError's is supressed when the
    errors occur on the command line to provide a useful command line
    interface.
    """

    def render(self, msg):
        return msg % vars(self)


class NeuralDependencyError(ImportError):
    def __init__(self, func_name=None):
        if func_name:
            message = (
                f"Function '{func_name}' requires neural dependencies. "
                "Install with: pip install g2p[neural]"
            )
        else:
            message = "This operation requires neural dependencies. Install with: pip install g2p[neural]"
        super().__init__(message)


class MappingMissing(CommandLineError):
    def __init__(self, in_lang, out_lang):
        super().__init__(self)
        self.in_lang = in_lang
        self.out_lang = out_lang

    def __str__(self):
        return self.render(
            "\n"
            'There is no mapping between the languages "%(in_lang)s" and "%(out_lang)s", \n'
            "please make sure you spelled the name correctly or go to\n"
            "https://g2p-studio.herokuapp.com/api/v1/langs for a list of mappings"
        )


class NoPath(CommandLineError):
    def __init__(self, in_lang, out_lang):
        super().__init__(self)
        self.in_lang = in_lang
        self.out_lang = out_lang

    def __str__(self):
        return self.render(
            "\n"
            'There is no g2p path between the languages "%(in_lang)s" and "%(out_lang)s", \n'
            "please make sure you spelled the name correctly or go to\n"
            "https://g2p-studio.herokuapp.com/api/v1/langs for a list of mappings"
        )


class InvalidNormalization(CommandLineError):
    def __init__(self, norm):
        super().__init__(self)
        self.norm = norm

    def __str__(self):
        return self.render(
            "\n"
            'You provided an invalid argument "%(norm)s" to normalize with. \n'
            'Please use "none" or "NFC", "NFKC", "NFD", or "NFKD"\n'
        )


class MalformedMapping(CommandLineError):
    def __init__(self, message=""):
        super().__init__(self)
        if message:
            self.message = "\n\n" + message
        else:
            self.message = ""

    def __str__(self):
        return self.render(
            "\n"
            "There is something wrong with your mapping. \n"
            "You might be missing some keywords or \n"
            'Not all of the input and output pairs in your mapping have values for "in" and "out"\n'
            'You may need to rerun "g2p update" after resolving this problem.\n'
            "Please refer to the documentation and fix your mapping." + self.message
        )


class IncorrectFileType(CommandLineError):
    def __init__(self, msg):
        super().__init__(self)
        self.msg = msg

    def __str__(self):
        return self.render(self.msg)


class InvalidLanguageCode(CommandLineError):
    def __init__(self, lang):
        super().__init__(self)
        self.lang = lang

    def __str__(self):
        return self.render('No language called: "%(lang)s".')


class RecursionError(CommandLineError):
    def __init__(self, msg):
        super().__init__(self)
        self.msg = msg

    def __str__(self):
        return self.render(self.msg)
