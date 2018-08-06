import random


class Abcid(object):
    """
    Readable alternative to UUID for debugging

    Prep
    ----
    Download the word list::
    $ cd <directory from which you run patchwork>
    $ wget https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt
    """

    def __init__(self, seed=None):
        self.path   = "words_alpha.txt"
        self.words  = []
        self.random = random.Random(seed)
        self.state  = 0


    def load_words(self):
        with open(self.path, 'r') as f:
            self.words = [s.strip() for s in f.readlines()]


    def abcid(self):
        # return "-".join(self.random.choices(self.words, k=2))
        try:
            return str(self.state)
        finally:
            self.state += 1
