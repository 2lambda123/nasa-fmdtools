# -*- coding: utf-8 -*-
"""
Defines label arguments for graph plotting.

Has classes:

- :class:`LabelStyle`: Holds kwargs for nx.draw_networkx_labels to be applied to labels
- :class:`EdgeLabelStyle`: Controls edge labels to ensure they do not rotate
- :class:`Labels`: Defines a set of labels to be drawn using draw_networkx_labels.

And Functions:
- :func:`label_for_entry`: Gets the label from an nx.graph for a given entry.
"""
import networkx as nx
from recordclass import dataobject, asdict


class LabelStyle(dataobject):
    """Holds kwargs for nx.draw_networkx_labels to be applied as a style for labels."""

    font_size: int = 12
    font_color: str = "k"
    font_weight: str = "normal"
    alpha: float = 1.0
    horizontalalignment: str = "center"
    verticalalignment: str = "center"
    clip_on: bool = False
    bbox: dict = dict(alpha=0)

    def kwargs(self):
        """Return kwargs for nx.draw_networkx_labels."""
        return asdict(self)


class EdgeLabelStyle(LabelStyle):
    """Holds kwargs for nx.draw_networkx_edge_labels."""

    rotate: bool = False


def label_for_entry(g, iterator, entryname):
    """
    Create the label dictionary for a given entry value of interest.

    Parameters
    ----------
    g : nx.graph
        Networkx graph structure to create labels for
    iterator : nx.graph.nodes/edges
        Property to iterate over (e.g., nodes or edges)
    entryname : str
        Property to get from the graph attributes. Options are:

        - 'id' : The name of the node/edge

        - 'last' : The last part (after all "_" characters) of the name of the node/edge

        - 'nodetype'/'edgetype' : The type property of the node or edge.

        - 'faults_and_indicators' : Fault and indicator properties from the node/edge

        - <str> : Any other property corresponding to the key in the node/edge dict

    Returns
    -------
    entryvals : dict
        Dictionary of values to show for the given entry
    """
    if entryname == "id":
        entryvals = {n: n for n in iterator}
    elif entryname == "last":
        entryvals = {n: n.split("_")[-1] for n in iterator}
    elif 'type' in entryname:
        entryvals = {n: '<'+v[entryname]+'>' for n, v in iterator.items()}
    elif entryname == 'faults_and_indicators':
        faults = nx.get_node_attributes(g, 'faults')
        indicators = nx.get_node_attributes(g, 'indicators')
        all_entries = [*faults, *indicators]
        entryvals = {n: faults.get(n, [])+indicators.get(n, []) for n in all_entries}
    elif 'Edge' in iterator.__class__.__name__:
        entryvals = nx.get_edge_attributes(g, entryname)
    elif 'Node' in iterator.__class__.__name__:
        entryvals = nx.get_node_attributes(g, entryname)
    else:
        entryvals = {}
    return entryvals


class Labels(dataobject, mapping=True):
    """
    Define a set of labels to be drawn using draw_networkx_labels.

    Labels have three distinct parts:

    - title (upper text for the node/edge)

    - title2 (if provided, uppder text for the node/edge after a colon)

    - subtext (lower text of the node/edge)

    Title and subtext may both be given different LabelStyles.
    """

    title: dict = {}
    title_style: LabelStyle = LabelStyle()
    subtext: dict = {}
    subtext_style: LabelStyle = LabelStyle()

    def from_iterator(g, iterator, LabStyle,
                      title='id', title2='', subtext='', **node_label_styles):
        """
        Construct the labels from an interator (nodes or edges).

        Parameters
        ----------
        g : nx.graph
            Networkx graph structure to create labels for
        iterator : nx.graph.nodes/edges
            Property to iterate over (e.g., nodes or edges)
        LabStyle : class
            Class to use for label styles (e.g., LabelStyle or EdgeStyle)
        title : str, optional
            entry for title text. (See :func:`label_for_entry` for options).
            The default is 'id'.
        title2 : str, optional
            entry for title text after the colon. (See :func:`label_for_entry` for
            options). The default is ''.
        subtext : str, optional
            entry for the subtext. (See :func:`label_for_entry` for options).
            The default is ''.
        **node_label_styles : dict
            LabStyle arguments to overwrite.

        Returns
        -------
        labs : Labels
            Labels corresponding to the given inputs
        """
        labs = Labels()
        for entry in ['title', 'title2', 'subtext']:
            entryval = vars()[entry]
            evals = label_for_entry(g, iterator, entryval)

            if evals:
                if entry == 'title':
                    labs.title = evals
                elif entry == 'title2':
                    labs.title = {k: v+': '+evals.get(k, '')
                                  for k, v in labs.title.items()}
                elif entry == 'subtext':
                    labs.subtext = evals

        node_labels = labs.iter_groups()
        for entry in node_labels:
            if len(labs) > 1:
                if entry == 'title':
                    verticalalignment = 'bottom'
                elif entry == 'subtext':
                    verticalalignment = 'top'
            else:
                verticalalignment = 'center'
            if entry == 'title' and 'Node' in iterator.__class__.__name__:
                font_weight = 'bold'
            else:
                font_weight = 'normal'
            def_style = dict(verticalalignment=verticalalignment,
                             font_weight=font_weight,
                             **node_label_styles.get(entry, {}))
            labs[entry+'_style'] = LabStyle(**def_style)
        return labs

    def iter_groups(self):
        """Return groups to iterate through when calling nx.draw_labels."""
        return [n for n in ['title', 'subtext'] if getattr(self, n)]

