# -*- coding: utf-8 -*-
"""
Description: A module for methods used commonly in model definition constructs.

Functions contained in this module:

- :func:`get_var`:Gets the variable value of the object
- :func:`set_var`:Sets variable of the object to a given value
- :func:`is_iter`: Checks whether a data type should be interpreted as an iterable or
not.
- :func:`check_pickleability`:Checks to see which attributes of an object will pickle
  (and thus parallelize)"
- :func:`init_obj_attr`:Initializes attributes to a given object
- :func:`init_obj_dict`: Create a dict in an object for the attribute 'spec'.
- :func:`get_obj_track`:Gets tracking params for a given object (block, model, etc)
- :func:`t_key`:Used to generate keys for a given (float) time that is queryable as
  an attribute of an object/dict

"""
import dill
import pickle
import time
from recordclass import asdict


def check_pickleability(obj, verbose=True, try_pick=False, pause=0.2):
    """Check to see which attributes of an object will pickle (and parallelize)."""
    from pickle import PicklingError
    unpickleable = []
    try:
        itera = vars(obj)
    except:
        itera = {a: getattr(obj, a) for a in obj.__slots__}
    for name, attribute in itera.items():
        print(name)
        time.sleep(pause)
        try:
            if not dill.pickles(attribute):
                unpickleable = unpickleable + [name]
        except ValueError as e:
            raise ValueError("Problem in " + name +
                             " with attribute " + str(attribute)) from e
        if try_pick:
            try:
                a = pickle.dumps(attribute)
                b = pickle.loads(a)
            except:
                raise Exception(obj.name + " will not pickle")
    if try_pick:
        try:
            a = pickle.dumps(obj)
            b = pickle.loads(a)
        except PicklingError as e:
            raise Exception(obj.name + " will not pickle") from e
    if verbose:
        if unpickleable:
            print("The following attributes will not pickle: " + str(unpickleable))
        else:
            print("The object is pickleable")
    return unpickleable


class BaseObject(object):
    __slots__ = ('name', 'containers', 'indicators')

    def __init__(self, name='', **kwargs):
        if not name:
            self.name = self.__class__.__name__.lower()
        else:
            self.name = name
        self.init_indicators()
        self.init_roles('container', **kwargs)

    def init_roles(self, roletype, **kwargs):
        """
        Initialize the roles for a given object.

        Roles defined using container_x in its class variables for the attribute x.

        Object is instantiated with the attribute x corresponding to output of container_x.

        Parameters
        ----------
        roletype : str
            Role to initialize (e.g., 'container'). If none provided, initializes all.
        **kwargs : dict
            Dictionary arguments (or already instantiated objects) to use for the
            attributes.
        """
        # creates tuple of roles at .roletypes
        container_collection = roletype + 's'
        roles = tuple([at[len(roletype)+1:]
                       for at in dir(self) if at.startswith(roletype+'_')])
        setattr(self, container_collection, roles)

        # initialize roles and add as attributes to the object
        for rolename in roles:
            container_initializer = getattr(self, roletype+'_'+rolename)
            if rolename in kwargs:
                container_args = kwargs[rolename]
                if type(container_args) != dict:
                    container_args = asdict(container_args)
            else:
                container_args = {}
            container = container_initializer(**container_args)
            container.check_role(rolename)
            setattr(self, rolename, container)

    def init_dict(self, spec, name_end="s", set_attr=False):
        """
        Create a collection dict for the attribute 'spec'.

        Works by finding all attributes from the obj's parameter with the name 'spec' in
        them and adding them to the dict. Adds the dict to the object.

        Parameters
        ----------
        obj : object
            Object with _spec_ attributes
        spec : str
            Name of the attributes to initialize
        set_attr : bool
            Whether to also add the individual attributes attr to the obj
        sub_obj : str
            Sub-object to form the object from (e.g., 'p' if defined in a parameter).
            Default is '', which gets from obj.
        """
        spec_len = len(spec) + 1
        specs = {p[spec_len:]: self.p[p] for p in self.p.__fields__ if spec in p}
        specname = spec + name_end
        setattr(self, specname, specs)
        if set_attr:
            for s_name in specs:
                setattr(self, s_name, specs[s_name])

    def init_indicators(self):
        self.indicators = tuple([at[9:] for at in dir(self)
                                 if at.startswith('indicate_')])

    def get_indicators(self):
        """
        Gets the names of the indicators

        Returns
        -------
        indicators : dict
            dict of indicator names and their associated method handles.
        """
        return {i: getattr(self, 'indicate_'+i) for i in self.indicators}

    def return_true_indicators(self, time):
        """
        Get list of indicators.

        Parameters
        ----------
        time : float
            Time to execute the indicator method at.

        Returns
        -------
        list
            List of inticators that return true at time

        """
        return [f for f, ind in self.get_indicators().items() if ind(time)]

    def get_track(obj, track, all_possible=()):
        """
        Get tracking params for a given object (block, model, etc).

        Parameters
        ----------
        track : track
            str/tuple. Attributes to track.
            'all' tracks all fields
            'default' tracks fields defined in default_track for the dataobject
            'none' tracks none of the fields

        Returns
        -------
        track : tuple
            fields to track
        """
        if track == 'default':
            track = obj.default_track
        if track == 'all':
            track = all_possible
        elif track in ['none', False]:
            track = ()
        elif type(track) == str:
            track = (track,)
        return track
