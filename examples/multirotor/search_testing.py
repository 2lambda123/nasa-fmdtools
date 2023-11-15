# -*- coding: utf-8 -*-
"""
Created on Mon Nov  6 18:45:28 2023

@author: dhulse
"""
from fmdtools.sim.search import SimpleProblem, BaseProblem
from examples.multirotor.test_multirotor import ex_soc_opt, sp, sp2

import networkx as nx
import numpy as np


from fmdtools.analyze.common import setup_plot



def descost(*x):
    batcostdict = {'monolithic': 0, 'series-split': 300,
                   'parallel-split': 300, 'split-both': 600}
    linecostdict = {'quad': 0, 'hex': 1000, 'oct': 2000}
    return [*batcostdict.values()][x[0]]+[*batcostdict.values()][x[1]]

def set_con(*x):
    return 0.5 - float(0 <= x[0] <= 3 and 0 <= x[1] <= 2)

sp0 = SimpleProblem("bat", "linearch")
sp0.add_objective("cost", descost)
sp0.add_constraint("set", set_con, comparator="less")
sp0.cost(1,1)


class ProblemArchitecture(BaseProblem):

    def __init__(self):
        self.problems = {}
        self.variables = {}
        self.connectors = {}
        self.problem_graph = nx.DiGraph()
        super().__init__()

    def add_connector_variable(self, name, *varnames):
        self.connectors[name] = {v: np.nan for v in varnames}
        self.problem_graph.add_node(name)

    def add_problem(self, name, problem, inputs=[], outputs=[]):
        if self.problems:
            upstream_problem = [*self.problems][-1]
            self.problem_graph.add_edge(upstream_problem, name,
                                        label = "next")
        self.problems[name] = problem
        self.problem_graph.add_node(name, order = len(self.problems))

        for con in inputs:
            self.problem_graph.add_edge(con, name, label="input")
        for con in outputs:
            self.problem_graph.add_edge(name, con, label="output")

        self.variables.update({name+"."+k: v for k, v in problem.variables.items()})
        self.objectives.update({name+"."+k: v
                                for k, v in problem.objectives.items()})
        self.constraints.update({name+"."+k: v
                                 for k, v in problem.constraints.items()})

    def update_problem(self, probname, *x):
        # TODO: need a way update upstream sims and then update problem
        #x_upstream = 
        self.problems[probname].update_objectives(*x)

    def update_problem_outputs(self, probname):
        outputs = self.get_outputs(probname)
        for output, outputdict in outputs.items():
            outputdict = {o: self.problems[probname].variables[o] for o in outputdict}
            self.connectors[output] = outputdict

    def find_inputs(self, probname):
        return [e[0] for e in self.problem_graph.in_edges(probname)
                if self.problem_graph.edges[e]['label']=='input']

    def find_outputs(self, probname):
        return [e[1] for e in self.problem_graph.out_edges(probname)
                if self.problem_graph.edges[e]['label']=='output']

    def get_inputs(self, probname):
        return {c: self.connectors[c] for c in self.find_inputs(probname)}

    def get_outputs(self, probname):
        return {c: self.connectors[c] for c in self.find_outputs(probname)}

    def get_downstream_sims(self, probname):
        return [s for s in nx.traversal.bfs_tree(self.problem_graph, probname)
                if s != probname]

    def get_upstream_sims(self, probname):
        return [s for s in
                nx.traversal.bfs_tree(self.problem_graph, probname, reverse=True)
                if s != probname]

    def get_connections(self):
        return {k: v for k, v in self.problem_graph.edges().items()}

    def show_sequence(self):
        fig, ax = setup_plot()
        pos = nx.kamada_kawai_layout(self.problem_graph, dim=2)
        nx.draw(self.problem_graph, pos=pos)
        orders = nx.get_node_attributes(self.problem_graph, "order")
        names = nx.get_node_attributes(self.problem_graph, "label")
        labels = {node: str(orders[node]) + ": " + node if node in orders else node
                  for node in self.problem_graph}
        nx.draw_networkx_labels(self.problem_graph, pos, labels=labels)
        edge_labels = nx.get_edge_attributes(self.problem_graph, "label")
        nx.draw_networkx_edge_labels(self.problem_graph, pos, edge_labels=edge_labels)
        return fig, ax


pa = ProblemArchitecture()
pa.add_connector_variable("vars", "bat", "linearch")
pa.add_problem("arch_cost", sp0, outputs=["vars"])

pa.add_problem("arch_performance", ex_soc_opt, inputs=["vars"])
#pa.add_problem("mechfault_recovery", sp, inputs=["vars"])
#pa.add_problem("charge_resilience", sp2, inputs=["vars"])

pa.show_sequence()

pa.get_downstream_sims("arch_cost")

pa.update_problem_outputs("arch_cost")

# Fault set / sequence generator
# def gen_single_fault_times(fd, *x):
#     sequences = []
#     for i, fault in enumerate(fd.faults):
#         seq = Sequence.from_fault(fault, x[i])
#         sequences.append(seq)
#     return sequences


#seqs = gen_single_fault_times(fd1, *[i for i in range(len(fd1.faults))])


#expd1("series-split", "oct")

# two types of variables:
# parameter variable
# varnames + mapping
# -> creation of a parameterdomain to sample from
# -> mapping tells us whether to sample directly or call mapping first

# scenario variable
# fault or disturbance
# fault variable is the time or type of fault
# disturbance is the time or str of disturbance
# maybe we have a domain for these?
# faultdomain - callable in terms of what?
# disturbancedomain - callable in terms of what?
if __name__ == "__main__":
    import doctest
    doctest.testmod(verbose=True)