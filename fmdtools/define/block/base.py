# -*- coding: utf-8 -*-
"""
Description: A module to define blocks.

- :class:`Simulable`: Superclass for architectures and blocks.
- :class:`Block`: Superclass for Functions, Components, Actions, etc.
"""
import itertools
import copy
import inspect
import warnings
from recordclass import dataobject, astuple

from fmdtools.define.base import set_var, get_var
from fmdtools.define.object.base import BaseObject
from fmdtools.define.container.parameter import SimParam
from fmdtools.define.container.time import Time
from fmdtools.define.flow.base import Flow
from fmdtools.analyze.result import Result
from fmdtools.analyze.common import get_sub_include
from fmdtools.analyze.history import History, init_indicator_hist


class Simulable(BaseObject):
    """
    Base class for object which simulate (blocks and architectures).

    Note that classes solely based on Simulable may not be able to be simulated.
    """

    __slots__ = ('p', 'sp', 'r', 't', 'h', 'track', 'flows', 'is_copy')
    container_t = Time
    default_sp = {}
    default_track = ["all"]
    container_sp = SimParam

    def __init__(self, name='', roletypes=[], track={}, **kwargs):
        """
        Instantiate internal Simulable attributes.

        Parameters
        ----------
        name: str
            Name for the Simulable
        roletypes : list
            Names of roles (e.g., ['container'] etc)
        track: dict
            tracking dictionary
        """
        self.is_copy = False
        self.flows = dict()

        if not track:
            self.track = self.default_track
        else:
            self.track = track

        if 'sp' in kwargs:
            sp = {**self.default_sp, **kwargs['sp']}
        else:
            sp = {**self.default_sp}
        loc_kwargs = {**kwargs, 'sp': sp}
        BaseObject.__init__(self, name=name, roletypes=roletypes, **loc_kwargs)

    def add_flow_hist(self, hist, timerange, track):
        """
        Create a history of flows for the Simulable and appends it to the History hist.

        Parameters
        ----------
        h : History
            History to append flow history to
        timerange : iterable, optional
            Time-range to initialize the history over. The default is None.
        track : list/str/dict, optional
            argument specifying attributes for :func:`get_sub_include'.
            The default is None.
        """
        flow_track = get_sub_include('flows', track)
        if flow_track:
            hist['flows'] = History()
            for flowname, flow in self.flows.items():
                fh = flow.create_hist(timerange, get_sub_include(flowname, flow_track))
                if fh:
                    hist.flows[flowname] = fh

    def update_seed(self, seed=[]):
        """
        Update seed and propogates update to contained actions/components.

        (keeps seeds in sync)

        Parameters
        ----------
        seed : int, optional
            Random seed. The default is [].
        """
        if seed and hasattr(self, 'r'):
            self.r.update_seed(seed)

    def find_classification(self, scen, mdlhists):
        """
        Classify the results of the simulation (placeholder).

        Parameters
        ----------
        scen     : Scenario
            Scenario defining the model run.
        mdlhists : History
            History for the simulation(s)

        Returns
        -------
        endclass: Result
            Result dictionary with rate, cost, and expecte_cost values
        """
        return Result({'rate': scen.rate, 'cost': 1, 'expected_cost': scen.rate})

    def new_params(self, p={}, sp={}, r={}, track={}, **kwargs):
        """
        Create a copy of the defining immutable parameters for use in a new Simulable.

        Parameters
        ----------
        p     : dict
            Parameter args to update
        sp    : dict
            SimParam args to update
        r     : dict
            Rand args to update
        track : dict
            track kwargs to update.

        Returns
        -------
        param_dict: dict
            Dict with immutable parameters/options. (e.g., 'p', 'sp', 'track')
        """
        param_dict = {}
        if hasattr(self, 'p'):
            param_dict['p'] = self.p.copy_with_vals(**p)
        if hasattr(self, 'sp'):
            param_dict['sp'] = self.sp.copy_with_vals(**sp)
        if not r and hasattr(self, 'r'):
            param_dict['r'] = {'seed': self.r.seed}
        if not track:
            param_dict['track'] = copy.deepcopy(self.track)
        return param_dict

    def new(self, **kwargs):
        """
        Create a new Model with the same parameters as the current model.

        Can initiate with with changes to mutable parameters (p, sp, track, rand etc.).
        """
        return self.__class__(**self.new_params(**kwargs))

    def get_fxns(self):
        """
        Get fxns associated with the Simulable (self if Function, self.fxns if Model).

        Returns
        -------
        fxns: dict
            Dict with structure {fxnname: fxnobj}
        """
        if hasattr(self, 'fxns'):
            fxns = self.fxns
        else:
            fxns = {self.name: self}
        return fxns

    def get_vars(self, *variables, trunc_tuple=True):
        """
        Get variable values in the simulable.

        Parameters
        ----------
        *variables : list/string
            Variables to get from the model. Can be specified as a list
            ['fxnname2', 'comp1', 'att2'], or a str 'fxnname.comp1.att2'

        Returns
        -------
        variable_values: tuple
            Values of variables. Passes (non-tuple) single value if only one variable.
        """
        if type(variables) == str:
            variables = [variables]
        variable_values = [None]*len(variables)
        for i, var in enumerate(variables):
            if type(var) == str:
                var = var.split(".")
            if var[0] in ['functions', 'fxns']:
                f = self.get_fxns()[var[1]]
                var = var[2:]
            elif var[0] == 'flows':
                f = self.flows[var[1]]
                var = var[2:]
            elif var[0] in self.get_fxns():
                f = self.get_fxns()[var[0]]
                var = var[1:]
            elif var[0] in self.flows:
                f = self.flows[var[0]]
                var = var[1:]
            else:
                f = self
            variable_values[i] = get_var(f, var)
        if len(variable_values) == 1 and trunc_tuple:
            return variable_values[0]
        else:
            return tuple(variable_values)

    def get_scen_rate(self, fxnname, faultmode, time, phasemap={}, weight=1.0):
        """
        Get the scenario rate for the given single-fault scenario.

        Parameters
        ----------
        fxnname: str
            Name of the function with the fault
        faultmode: str
            Name of the fault mode
        time: int
            Time when the scenario is to occur
        phasemap : PhaseMap, optional
            Map of phases/modephases that define operations the mode will be injected
            during (and maps to the opportunity vector phases). The default is {}.
        weight : int, optional
            Scenario weight (e.g., if more than one scenario is sampled for the fault).
            The default is 1.

        Returns
        -------
        rate: float
            Rate of the scenario
        """
        fxn = self.get_fxns()[fxnname]
        fm = fxn.m.faultmodes.get(faultmode, False)
        if not fm:
            raise Exception("faultmode "+faultmode+" not in "+str(fxn.m.__class__))
        else:
            sim_time = self.sp.times[-1] - self.sp.times[0] + self.sp.dt
            rate = fm.calc_rate(time, phasemap=phasemap, sim_time=sim_time,
                                sim_units=self.sp.units, weight=weight)
        return rate


class Block(Simulable):
    """
    Superclass for Function and Component subclasses.

    Has functions for model setup, querying state, reseting the model

    Attributes
    ----------
    p : Parameter
        Internal Parameter for the block. Instanced from container_p
    s : State
        Internal State of the block. Instanced from container_s.
    m : Mode
        Internal Mode for the block. Instanced from container_m
    r : Rand
        Internal Rand for the block. Instanced from container_r
    t : Time
        Internal Time for the block. Instanced from container_t
    name : str
        Block name
    flows : dict
        Dictionary of flows included in the Block (if any are added via flow_flowname)
    is_copy : bool
        Marker for whether the object is a copy.
    """

    __slots__ = ['s', 'm']
    default_track = ['s', 'm', 'r', 't', 'i']

    def __init__(self, name='', flows={}, **kwargs):
        """
        Instance superclass. Called by Function and Component classes.

        Parameters
        ----------
        name : str
            Name for the Block instance.
        flows :dict
            Flow objects passed from the model level.
        kwargs : kwargs
            Roles and tracking to override the defaults. See Simulable.__init__
        """
        Simulable.__init__(self, name=name, **kwargs)
        self.assoc_flows(flows=flows)
        self.update_seed()

    def assoc_flows(self, flows={}):
        """
        Associate flows with the given Simulable.

        Flows must be defined with the flow_ class variable pointing to the class to
        initialize (e.g., flow_flowname = FlowClass).

        Parameters
        ----------
        flows : dict, optional
            If flows is provided AND it contains a flowname corresponding to the
            function's flowname, it will be used instead (so that it can act as a
            connection to the rest of the model)
        """
        if hasattr(self, 'flownames'):
            flows = {self.flownames.get(fn, fn): flow for fn, flow in flows.items()}
        flows = flows.copy()
        for init_att in dir(self):
            if init_att.startswith("flow_"):
                att = getattr(self, init_att)
                attname = init_att[5:]
                if (inspect.isclass(att) and
                        issubclass(att, Flow) and
                        not (attname in self.flows)):
                    if attname in flows:
                        self.flows[attname] = flows.pop(attname)
                    else:
                        self.flows[attname] = att(attname)
                    if not isinstance(self, dataobject):
                        setattr(self, attname, self.flows[attname])
        if flows:
            warnings.warn("these flows sent from model "+str([*flows.keys()])
                          + " not added to class "+str(self.__class__))

    def get_typename(self):
        """
        Get the name of the type (Block for Blocks).

        Returns
        -------
        typename: str
            Block
        """
        return "Block"

    def is_static(self):
        """Check if Block has static execution step."""
        return (getattr(self, 'behavior', False) or
                getattr(self, 'static_behavior', False) or
                (hasattr(self, 'aa') and getattr(self.aa, 'proptype', '') == 'static'))

    def is_dynamic(self):
        """Check if Block has dynamic execution step."""
        return (hasattr(self, 'dynamic_behavior') or
                (hasattr(self, 'aa') and getattr(self.aa, 'proptype', '') == 'dynamic'))

    def __repr__(self):
        """
        Provide a repl-friendly string showing the states of the Block.

        Returns
        -------
        repr: str
            console string
        """
        if hasattr(self, 'name'):
            fxnstr = getattr(self, 'name', '')+' '+self.__class__.__name__+'\n'
            for at in ['s', 'm']:
                at_container = getattr(self, at, False)
                if at_container:
                    fxnstr = fxnstr+"- "+at_container.__repr__()+'\n'
            return fxnstr
        else:
            return 'New uninitialized '+self.__class__.__name__

    def get_rand_states(self, auto_update_only=False):
        """
        Get dict of random states from block and associated actions/components.

        Parameters
        ----------
        auto_update_only

        Returns
        -------
        rand_states : dict
            Random states from the block and associated actions/components.
        """
        if hasattr(self, 'r'):
            rand_states = self.r.get_rand_states(auto_update_only)
        if hasattr(self, 'ca'):
            rand_states.update(self.ca.get_rand_states(auto_update_only=auto_update_only))
        if hasattr(self, 'aa'):
            for actname, act in self.aa.actions.items():
                if act.get_rand_states(auto_update_only=auto_update_only):
                    rand_states[actname] = act.get_rand_states(auto_update_only=auto_update_only)
        return rand_states

    def choose_rand_fault(self, faults, default='first', combinations=1):
        """
        Randomly chooses a fault or combination of faults to insert in fxn.m.

        Parameters
        ----------
        faults : list
            list of fault modes to choose from
        default : str/list, optional
            Default fault to inject when model is run deterministically.
            The default is 'first', which chooses the first in the list.
            Can provide a mode as a str or a list of modes
        combinations : int, optional
            Number of combinations of faults to elaborate and select from.
            The default is 1, which just chooses single fault modes.
        """
        if hasattr(self, 'r') and getattr(self.r, 'run_stochastic', True):
            faults = [list(x) for x in itertools.combinations(faults, combinations)]
            self.m.add_fault(*self.r.rng.choice(faults))
        elif default == 'first':
            self.m.add_fault(faults[0])
        elif type(default) == str:
            self.m.add_fault(default)
        else:
            self.m.add_fault(*default)

    def get_flowtypes(self):
        """
        Return the names of the flow types in the model.

        Returns
        -------
        flowtypes : set
            Set of flow type names in the model.
        """
        return {obj.__class__.__name__ for name, obj in self.flows.items()}

    def copy(self, *args, **kwargs):
        """
        Copy the block with its current attributes.

        Parameters
        ----------
        args   : tuple
            New arguments to use to instantiate the block, (e.g., flows, p, s)
        kwargs :
            New kwargs to use to instantiate the block.

        Returns
        -------
        cop : Block
            copy of the exising block
        """
        cop = self.__new__(self.__class__)
        cop.is_copy = True
        try:
            paramdict = self.new_params(**kwargs)
            cop.__init__(self.name, *args, **paramdict)
            cop.assign_roles('container', self)
        except TypeError as e:
            raise Exception("Poor specification of "+str(self.__class__)) from e
        if hasattr(self, 'h'):
            cop.h = self.h.copy()
        return cop

    def return_mutables(self):
        """
        Return all mutable values in the block.

        Used in static propagation steps to check if the block has changed.

        Returns
        -------
        states : tuple
            tuple of all states in the block
        """
        mutes = [getattr(self, mut).return_mutables() for mut in self.containers
                 if mut not in ['p', 'sp']]
        return tuple(mutes)

    def return_probdens(self):
        """Get the probability density associated with Block and things it contains."""
        state_pd = self.r.return_probdens()
        if hasattr(self, 'ca'):
            for compname, comp in self.ca.components:
                state_pd *= comp.return_probdens()
        if hasattr(self, 'aa'):
            for actionname, action in self.aa.actions:
                state_pd *= action.return_probdens()
        return state_pd

    def create_hist(self, timerange, track='default'):
        """
        Initialize state history of the model mdl over the timerange.

        A pointer to the history is then stored at self.h.

        Parameters
        ----------
        timerange : array
            Numpy array of times to initialize in the dictionary.
        track : 'all' or dict, 'none', optional
            Which model states to track over time, which can be given as 'all' or a
            dict of form {'functions':{'fxn1':'att1'}, 'flows':{'flow1':'att1'}}
            The default is 'all'.

        Returns
        -------
        fxnhist : dict
            A dictionary history of each recorded block property over the given timehist
        """
        if hasattr(self, 'h'):
            return self.h
        else:
            all_track = self.default_track+['flows']
            track = self.get_track(track, all_track)
            if track:
                hist = History()
                init_indicator_hist(self, hist, timerange, track)
                self.add_flow_hist(hist, timerange, track)
                other_tracks = [t for t in track if t not in ('i', 'flows')]
                for at in other_tracks:
                    at_track = get_sub_include(at, track)
                    attr = getattr(self, at, False)
                    if attr:
                        at_h = attr.create_hist(timerange, at_track)
                        if at_h:
                            hist[at] = at_h

                self.h = hist.flatten()
                return self.h
            else:
                return History()

    def propagate(self, time, faults={}, disturbances={}, run_stochastic=False):
        """
        Inject and propagates faults through the graph at one time-step.

        Parameters
        ----------
        time : float
            The current timestep.
        faults : dict
            Faults to inject during this propagation step.
            With structure {fname: ['fault1', 'fault2'...]}
        disturbances : dict
            Variables to change during this propagation step.
            With structure {'var1': value}
        run_stochastic : bool
            Whether to run stochastic behaviors or use default values. Default is False.
            Can set as 'track_pdf' to calculate/track the probability densities of
            random states over time.
        """
        # Step 0: Update block states with disturbances
        for var, val in disturbances.items():
            set_var(self, var, val)
        faults = faults.get(self.name, [])

        # Step 1: Run Dynamic Propagation Methods in Order Specified
        # and Inject Faults if Applicable
        if hasattr(self, 'dynamic_loading_before'):
            self.dynamic_loading_before(self, time)
        if self.is_dynamic():
            self("dynamic", time=time, faults=faults, run_stochastic=run_stochastic)
        if hasattr(self, 'dynamic_loading_after'):
            self.dynamic_loading_after(self, time)

        # Step 2: Run Static Propagation Methods
        active = True
        oldmutables = self.return_mutables()
        flows_mutables = {f: fl.return_mutables() for f, fl in self.flows.items()}
        while active:
            if self.is_static():
                self("static", time=time, faults=faults, run_stochastic=run_stochastic)

            if hasattr(self, 'static_loading'):
                self.static_loading(time)
            # Check to see what flows now have new values and add connected functions
            # (done for each because of communications potential)
            active = False
            newmutables = self.return_mutables()
            if oldmutables != newmutables:
                active = True
                oldmutables = newmutables
            for flowname, fl in self.flows.items():
                newflowmutables = fl.return_mutables()
                if flows_mutables[flowname] != newflowmutables:
                    active = True
                    flows_mutables[flowname] = newflowmutables
