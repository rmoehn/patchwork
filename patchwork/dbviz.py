import collections

import graphviz
import jinja2

from patchwork.datastore import Datastore, Address
from patchwork.hypertext import RawHypertext, Workspace

Entry = collections.namedtuple("Entry", ["symbol", "location"])

workspace_template = """<
<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" BGCOLOR="#AACCFF">
<TR><TD COLSPAN="{{ entries|count }}">{{ workspace_loc }}</TD></TR>
<TR>
    {% for e in entries %}
    <TD PORT="{{e.symbol}}">{{e.symbol}}</TD>
    {% endfor %}
</TR>
</TABLE>>
"""


def workspace_node(g: graphviz.Digraph, a: Address, w: Workspace):
    entries = []
    entries.append(Entry("Q", w.question_link.location))
    #entries.append(Entry("P", w.scratchpad_link.location))

    for (i, (sq_link, answer_p, final_ws_p)) in enumerate(w.subquestions):
        entries.append(Entry("S{}".format(i), sq_link.location))

    entries.append(Entry("A", w.answer_promise.location))
    entries.append(Entry("F", w.final_workspace_promise.location))

    template = jinja2.Template(workspace_template)
    label = template.render(workspace_loc=a.location, entries=entries)
    g.node(a.location, label=label, shape='plain')
    for e in entries:
        color = "#0055D4" if e.symbol == 'Q' else "#000000"
        g.edge("{}:{}".format(a.location, e.symbol), e.location, color=color)


rawhypertext_template = """<
<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" BGCOLOR="#AADE87">
<TR>
    <TD COLSPAN="{{ chunks|count|default("1", boolean=True) }}">
        {{ rawhypertext_loc }}
    </TD>
</TR>
{% if chunks %}
    <TR>
        {% for c in chunks %}
            {% if c is string %}
                <TD>{{ c }}</TD>
            {% else %}
                <TD PORT="{{c.location}}">[]</TD>
            {% endif %}
        {% endfor %}
    </TR>
{% endif %}
</TABLE>>
"""


def rawhypertext_node(g: graphviz.Digraph, a: Address, r: RawHypertext):
    template = jinja2.Template(rawhypertext_template)
    label = template.render(rawhypertext_loc=a.location, chunks=r.chunks)
    g.node(a.location, label=label, shape='plain')
    for c in r.chunks:
        if isinstance(c, Address):
            g.edge("{}:{}".format(a.location, c.location), c.location)


def make_graph(db: Datastore):
    g = graphviz.Digraph(engine="dot")

    for a in db.promises:
        g.node(a.location, shape='box', style='rounded')

    for alias, address in db.aliases.items():
        g.edge(alias.location, address.location, style="dotted")

    # TODO: Use Python 3.8 type-based dispatch for this.
    for a in db.content:
        data = db.dereference(a)
        if isinstance(data, RawHypertext):
            rawhypertext_node(g, a, data)
        elif isinstance(data, Workspace):
            workspace_node(g, a, data)



    return g



def draw(db, path):
    g = make_graph(db)
    print(g.source)
    g.render(path, view=True)
