import pickle

from patchwork import dbviz


with open("test-db", 'rb') as f:
    db = pickle.load(f)

dbviz.draw(db, "/tmp/dbgraph.png")
