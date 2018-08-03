import collections

import graphviz

from patchwork.datastore import Datastore, Address
from patchwork.hypertext import RawHypertext, Workspace

Entry = collections.namedtuple("Entry", ["symbol", "location"])

def workspace_node(g: graphviz.Digraph, a: Address, w: Workspace):
    entries = []
    entries.append(Entry("Q", w.question_link.location))
    entries.append(Entry("P", w.scratchpad_link.location))

    for (i, (sq_link, answer_p, final_ws_p)) in enumerate(w.subquestions):
        entries.append(Entry("S{}".format(i), sq_link.location))

    identifier = "W." + a.location

    label = " | ".join("<{symbol}> {symbol}".format(symbol=e.symbol) for e in
                       entries)
    g.node(identifier, label=label, shape='record')
    g.edge(a.location, identifier)
    for e in entries:
        g.edge("{}:{}".format(identifier, e.symbol), e.location)




def make_graph(db: Datastore):
    g = graphviz.Digraph(engine="dot")
    for a in db.content:
        g.node(a.location)

        data = db.dereference(a)
        if isinstance(data, RawHypertext):
            for c in data.chunks:
                if isinstance(c, Address):
                    g.edge(a.location, c.location)
        elif isinstance(data, Workspace):
            workspace_node(g, a, data)



    return g


def draw(db, path):
    g = make_graph(db)
    print(g.source)
    g.render(path, view=True)
