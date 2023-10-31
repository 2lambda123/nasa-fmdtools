"""
Description: Translates simulation outputs to pandas tables for display, export, etc.

Uses methods:
- :meth:`result_summary_fmea`: Make a table of endclass metrics, along with degraded
functions/flows.
- :meth:`result_summary:` Make a a table of a summary dictionary from a given model run.
- :meth:`nominal_stats`: Makes a table of quantities of interest from endclasses from a
nominal approach.

and classes:
- :class:`FMEA`: Class defining FMEA tables (with plotting/tabular export).
- :class:`Comparison`: Class defining metric comparison (with plot/tab export).
"""
# File Name: analyze/tabulate.py
# Author: Daniel Hulse
# Created: November 2019 (Refactored April 2020)

import pandas as pd
import numpy as np
from fmdtools.analyze.result import Result
from fmdtools.analyze.plot import multiplot_helper, make_consolidated_legend
from fmdtools.analyze.plot import multiplot_legend_title
from matplotlib import colors as mcolors
from matplotlib import pyplot as plt
from collections import UserDict

# stable methods:


def result_summary_fmea(endresult, mdlhist, *attrs, metrics=()):
    """
    Make full fmea table with degraded attributes noted.

    Parameters
    ----------
    endresult : Result
        Result (over scenarios) to get metrics from
    mdlhist : History
        History (over scenarios) to get degradations/faults from
    *attrs : strs
        Model constructs to check if faulty/degraded.
    metrics : tuple, optional
        Metrics to include from endresult. The default is ().

    Returns
    -------
    pandas.DataFrame
        Table of metrics and degraded functions/flows over scenarios
    """
    from fmdtools.analyze.result import History
    deg_summaries = {}
    fault_summaries = {}
    mdlhist = mdlhist.nest(levels=1)
    for scen, hist in mdlhist.items():
        hist_comp = History(faulty=hist, nominal=mdlhist.nominal)
        hist_summary = hist_comp.get_fault_degradation_summary(*attrs)
        deg_summaries[scen] = str(hist_summary.degraded)
        fault_summaries[scen] = str(hist_summary.faulty)
    degradedtable = pd.DataFrame(deg_summaries, index=['degraded'])
    faulttable = pd.DataFrame(fault_summaries, index=['faulty'])
    simplefmea = endresult.create_simple_fmea(*metrics)
    fulltable = pd.concat([degradedtable, faulttable, simplefmea.transpose()])
    return fulltable.transpose()


def result_summary(endresult, mdlhist, *attrs):
    """
    Make a pandas table of results (degraded functions/flows, etc.) of a single run.

    Parameters
    ----------
    endresult : Result
        Result with end-state classification
    mdlhist : History
        History of model states
    *attrs : str
        Names of attributes to check in the history for degradation/faulty.

    Returns
    -------
    table : pd.DataFrame
        Table with summary
    """
    hist_summary = mdlhist.get_fault_degradation_summary(*attrs)
    if 'endclass' in endresult:
        endresult = endresult['endclass']
    table = pd.DataFrame(endresult.data, index=[0])
    table['degraded'] = [hist_summary.degraded]
    table['faulty'] = [hist_summary.faulty]
    return table


class BaseTab(UserDict):
    """
    Base class for tables that extends Userdict.

    Userdict has structure {metric: {comp_group: value}} which enables plots/tables.

    Attributes
    factors : list
        List of factors in the table
    """

    def sort_by_factors(self, *factors):
        """
        Sort the table by its factors.

        Parameters
        ----------
        *factor : str/int
            Name of factor(s) to sort by, in order of sorting. (non-included factors
                                                                will be sorted last)
        """
        factors = list(factors)
        factors.reverse()
        other_factors = [f for f in self.factors if f not in factors]
        all_factors = other_factors + factors
        for factor in all_factors:
            self.sort_by_factor(factor)

    def sort_by_factor(self, factor, reverse=False):
        """
        Sort the table by the given factor.

        Parameters
        ----------
        factor : str/int
            Name or index of factor to sort by.
        reverse : bool, optional
            Whether to sort in descending order. The default is False.
        """
        metric = [*self.keys()][0]
        keys = [k for k in self[metric].keys()]
        ex_key = keys[0]

        if hasattr(self, 'factors') and type(factor) == str:
            value = self.factors.index(factor)

        order = np.argsort([k[value] for k in keys], axis=0, kind='stable')

        if reverse:
            order = order[::-1]
        ordered_keys = [keys[o] for o in order]
        for met in self.keys():
            self[met] = {k: self[met][k] for k in ordered_keys}

    def sort_by_metric(self, metric, reverse=False):
        """
        Sort the table by a given metric.

        Parameters
        ----------
        metric : str
            Name of metric to sort by.
        reverse : bool, optional
            Whether to sort in descending order. The default is False.
        """
        keys = [*self[metric].keys()]
        vals = [*self[metric].values()]
        order = np.argsort(vals)
        if reverse:
            order = order[::-1]
        ordered_keys = [keys[o] for o in order]
        for met in self.keys():
            self[met] = {k: self[met][k] for k in ordered_keys}

    def all_metrics(self):
        """Return metrics in Table."""
        return [*self.keys()]

    def as_table(self, sort_by=False, ascending=False, sort=True):
        """
        Return pandas table of the Table.

        Parameters
        ----------
        sort_by : str, optional
            Column value to sort the table by. The default is False.
        ascending : bool, optional
            Whether to sort in ascending order. The default is False.

        Returns
        -------
        fmea_table : DataFrame
            pandas table with given metrics grouped as
        """
        if not sort_by:
            if "expected cost" in self.all_metrics():
                sort_by = "expected cost"
            else:
                sort_by = self.all_metrics()[-1]

        table = pd.DataFrame(self.data)
        if sort_by not in self.all_metrics():
            sort_by = self.all_metrics()[0]
        if sort: 
            table = table.sort_values(sort_by, ascending=ascending)
        return table

    def as_plot(self, metric, title="", fig=False, ax=False, figsize=(6, 4),
                xlab='', xlab_ang=-90, ylab='', color_factor='',
                pallette=[*mcolors.TABLEAU_COLORS.keys()], suppress_legend=False,
                suppress_ticklabels=False, **kwargs):
        """
        Return bar plot of a metric in the comparison.

        Parameters
        ----------
        metric : str
            Metric to plot.
        title : str, optional
            Title to use (if not default). The default is "".
        fig : figure
            Matplotlib figure object
        ax : axis
            Corresponding matplotlib axis
        figsize : tuple, optional
            Figsize (if fig not provided). The default is (6, 4).
        xlab : str, optional
            label for x-axis. The default is ''.
        xlab_ang : number
            Angle to tilt the xlabel at. The default is 90.
        ylab : str, optional
            label for y-axis. The default is ''.
        color_factor : ''
            Factor to label with a color (instead of the x-axis)
        pallette : list
            list of colors to . Defaults to matplotlib.colors.TABLEAU_COLORS.
        suppress_legend : bool
            Whether to suppress the generated legend (for multiplots)
        suppress_ticklabels : bool
            Whether to suppress tick labels.
        **kwargs : kwargs
            Keyword arguments to ax.bar

        Returns
        -------
        fig : figure
            Matplotlib figure object
        ax : axis
            Corresponding matplotlib axis
        """
        # add figure
        if not ax:
            fig, ax = plt.subplots(figsize=figsize)
        met_dict = self[metric]

        # sort into color vs tick bars
        all_factors = [*met_dict.keys()]
        if color_factor:
            if type(color_factor) == int:
                c_fact = color_factor
                color_factor = self.factors[c_fact]
            else:
                c_fact = self.factors.index(color_factor)
            color_factors = [k[c_fact] for k in all_factors]
            color_options = list(set(color_factors))
            colors = [pallette[color_options.index(c)] for c in color_factors]
            factors = [tuple([k for i, k in enumerate(k) if i != c_fact])
                       for k in all_factors]
        else:
            factors = all_factors
            color_factors = ['' for k in factors]
            colors = [pallette[0] for factor in factors]
        factors = [str(k[0]) if len(k) == 1 else str(k) for k in factors]
        x = [i for i, k in enumerate(factors)]
        values = np.array([*met_dict.values()])

        # degermine error bars
        if metric+"_lb" in self:
            lb_err = values - np.array([*self[metric+"_lb"].values()])
            ub_err = np.array([*self[metric+"_ub"].values()]) - values
            errs = [lb_err, ub_err]
        else:
            errs = 0.0

        # plot bars
        ax.bar(x, values, yerr=errs, color=colors, label=color_factors, **kwargs)

        # label axes
        if not xlab:
            non_color_factors = [f for f in self.factors if f != color_factor]
            if len(non_color_factors) == 1:
                ax.set_xlabel(non_color_factors[0])
            else:
                ax.set_xlabel(str(non_color_factors))

        if not suppress_ticklabels:
            ax.set_xticks(x)
            ax.set_xticklabels(factors)
        else:
            ax.set_xticks([])
        ax.tick_params(axis='x', rotation=xlab_ang)
        # legend, title, etc.
        if color_factor and not suppress_legend:
            make_consolidated_legend(ax, title=color_factor)
        if ylab:
            ax.set_ylab(ylab)
        if title:
            ax.set_title(title)
        return fig, ax

    def as_plots(self, *metrics, cols=1, figsize='default', titles={},
                 legend_loc=-1, title='', v_padding=None, h_padding=None,
                 title_padding=0.0, xlab='', **kwargs):
        """
        Plot multiple metrics on multiple plots.

        Parameters
        ----------
        *metrics : str
            Metrics to plot.
        cols : int, optional
            Number of columns. The default is 2.
        figsize : str, optional
            Figure size. The default is 'default'.
        titles : dict, optional
            Individual plot titles. The default is {}.
        legend_loc : str
            Plot to put the legend on. The default is -1 (the last plot).
        title : str
            Overall title for the plots. the default is '
        v_padding : float
            Vertical padding between plots.
        h_padding : float
            Horizontal padding between plots.
        title_padding : float
            Padding for the overall title
        xlab : str
            Label for the x-axis. Default is '', which generates it automatically.
        **kwargs : kwargs
            Keyword arguments to BaseTab.as_plot

        Returns
        -------
        fig : figure
            Matplotlib figure object
        ax : axis
            Corresponding matplotlib axis
        """
        if not metrics:
            metrics = self.all_metrics()
        fig, axs, cols, rows, subplot_titles = multiplot_helper(cols, *metrics,
                                                                figsize=figsize,
                                                                titles=titles)
        for i, metric in enumerate(metrics):
            if i >= (rows-1)*cols:
                xlabel = xlab
            else:
                xlabel = ' '
            fig, ax = self.as_plot(metric, title=subplot_titles[metric], xlab=xlabel,
                                   ax=axs[i], fig=fig, suppress_legend=True,
                                   **kwargs)

        color_factor = kwargs.get('color_factor', '')
        if not color_factor:
            legend_loc = False

        multiplot_legend_title(metrics, axs, ax, title=title,
                               v_padding=v_padding, h_padding=h_padding,
                               title_padding=title_padding,
                               legend_loc=legend_loc,
                               legend_title=color_factor)
        return fig, axs

class FMEA(BaseTab):
    def __init__(self, res, fs, metrics=[], weight_metrics=[], avg_metrics=[],
                 perc_metrics=[], mult_metrics={}, extra_classes={},
                 group_by=('function', 'fault'), mdl={}, mode_types={},
                 empty_as=0.0):
        """
        Make a user-definable fmea of the endclasses of a set of fault scenarios.

        Parameters
        ----------
        res : Result
            Result corresponding to the the simulation runs
        fs : sampleapproach/faultsample
            FaultSample used for the underlying probability model of the set of scens.
        metrics : list
            generic unweighted metrics to query. metrics are summed over grouped scens.
            The default is []. 'all' presents all metrics.
        weight_metrics: list
            weighted metrics to query. weight metrics are summed over groups.
            The default is ['rate'].
        avg_metrics: list
            metrics to average and query. The default is ['cost'].
            avg_metrics are averaged over groups, rather than a total.
        perc_metrics : list, optional
            metrics to treat as indicator variables to calculate a percentage.
            perc_metrics are treated as indicator variables and averaged over groups.
            The default is [].
        mult_metrics : dict, optional
            mult_metrics are new metrics calculated by multiplying existing metrics.
            (e.g., to calculate expectations or risk values like an expected cost/RPN)
            The default is {"expected cost":['rate', 'cost']}.
        extra_classes : dict, optional
            An additional set of endclasses to include in the table.
            The default is {}.
        group_by : tuple, optional
            Way of grouping fmea rows by scenario fields.
            The default is ('function', 'fault').
        mode_types : set
            Mode types to group by in 'mode type' option
        mdl : Model
            Model for use in 'fxnclassfault' and 'fxnclass' options
        empty_as : float/'nan'
            How to calculate stats of empty variables (for avg_metrics). Default is 0.0.
        """
        self.factors = group_by
        grouped_scens = fs.get_scen_groups(*group_by)

        if type(metrics) == str:
            metrics = [metrics]
        if type(weight_metrics) == str:
            weight_metrics = [weight_metrics]
        if type(perc_metrics) == str:
            perc_metrics = [perc_metrics]
        if type(avg_metrics) == str:
            avg_metrics = [avg_metrics]

        if not metrics and not weight_metrics and not perc_metrics and not avg_metrics and not mult_metrics:
            # default fmea is a cost-based table
            weight_metrics = ["rate"]
            avg_metrics = ["cost"]
            mult_metrics = {"expected cost": ['rate', 'cost']}

        res.update(extra_classes)

        allmetrics = metrics+weight_metrics+avg_metrics+perc_metrics+[*mult_metrics.keys()]

        fmeadict = {m: dict.fromkeys(grouped_scens) for m in allmetrics}
        for group, ids in grouped_scens.items():
            sub_result = Result({scenid: res.get(scenid) for scenid in ids})
            for metric in metrics + weight_metrics:
                fmeadict[metric][group] = sum([res.get(scenid).get('endclass.'+metric)
                                               for scenid in ids])
            for metric in perc_metrics:
                fmeadict[metric][group] = sub_result.percent(metric)
            for metric in avg_metrics:
                fmeadict[metric][group] = sub_result.average(metric, empty_as=empty_as)
            for metric, to_mult in mult_metrics.items():
                fmeadict[metric][group] = sum([np.prod([res.get(scenid).get('endclass.'+m)
                                                        for m in to_mult])
                                               for scenid in ids])
        self.data = fmeadict


class BaseComparison(BaseTab):
    def __init__(self, res, scen_groups, metrics=['cost'],
                 default_stat="expected", stats={}, ci_metrics=[], ci_kwargs={}):
        """
        Parameters
        ----------
        res : Result
            Result with the given metrics over a number of scenarios.
        scen_groups : dict
            Grouped scenarios.
        metrics : list
            metrics in res to tabulate over time. Default is ['cost'].
        default_stat : str
            statistic to take for given metrics my default.
            (e.g., 'average', 'percent'... see Result methods). Default is 'expected'.
        stats : dict
            Non-default statistics to take for each individual metric.
            e.g. {'cost': 'average'}. Default is {}
        ci_metrics : list
            Metrics to calculate a confidence interval for (using bootstrap_ci).
            Default is [].
        ci_kwargs : dict
            kwargs to bootstrap_ci
        """
        met_dict = {met: {} for met in metrics}
        met_dict.update({met+"_lb": {} for met in ci_metrics})
        met_dict.update({met+"_ub": {} for met in ci_metrics})

        for fact_tup, scens in scen_groups.items():
            sub_res = res.get_scens(*scens)
            for met in metrics+ci_metrics:
                if met in stats:
                    stat = stats[met]
                else:
                    stat = default_stat
                if met in ci_metrics:
                    try:
                        mv, lb, ub = sub_res.get_metric_ci(met, metric=stat,
                                                           **ci_kwargs)
                    except TypeError as e:
                        raise Exception("Invalid method: " + str(stat) + ", " +
                                        "Can only use ci for metrics w- numpy method " +
                                        "provided for stat (not str).") from e
                    met_dict[met][fact_tup] = mv
                    met_dict[met+"_lb"][fact_tup] = lb
                    met_dict[met+"_ub"][fact_tup] = ub
                else:
                    met_dict[met][fact_tup] = sub_res.get_metric(met, metric=stat)
        self.data = met_dict


class Comparison(BaseComparison):
    def __init__(self, res, samp, factors=['time'], **kwargs):
        """
        Make a table of the statistic for given metrics over given factors.

        Parameters
        ----------
        res : Result
            Result with the given metrics over a number of scenarios.
        samp : BaseSample
            Sample object used to generate the scenarios
        factors : list
            Factors (Scenario properties e.g., 'name', 'time', 'var') in samp to take
            statistic over. Default is ['time']
        **kwargs : kwargs
            keyword arguments to BaseComparison

        Returns
        -------
        met_table : dataframe
            pandas dataframe with the statistic of the metric over the corresponding
            set of scenarios for the given factor level.

        Examples
        -------
        >>> from fmdtools.sim.sample import exp_ps
        >>> from fmdtools.analyze.result import Result
        >>> res = Result({k.name: Result({'a': k.p['x']**2, "b": k.p['y']*k.p['x'], 'rate':k.rate}) for i, k in enumerate(exp_ps.scenarios())})
        >>> res = res.flatten()

        # example 1: checking the x = x^2 accross variables
        >>> comp = Comparison(res, exp_ps, metrics=['a'], factors=['p.x'], default_stat='average')
        >>> comp.sort_by_factors("p.x")
        >>> comp
        {'a': {(0,): 0.0, (1,): 1.0, (2,): 4.0, (3,): 9.0, (4,): 16.0, (5,): 25.0, (6,): 36.0, (7,): 49.0, (8,): 64.0, (9,): 81.0, (10,): 100.0}}
        >>> comp.as_table()
                a
        10  100.0
        9    81.0
        8    64.0
        7    49.0
        6    36.0
        5    25.0
        4    16.0
        3     9.0
        2     4.0
        1     1.0
        0     0.0
        >>> fig, ax = comp.as_plot("a")

        # example 2: viewing interaction between x and y:
        >>> comp = Comparison(res, exp_ps, metrics=['b'], factors=['p.x', 'p.y'], default_stat='average')
        >>> comp.sort_by_factors("p.x", "p.y")
        >>> comp.as_table(sort=False)
                   b
        0  1.0   0.0
           2.0   0.0
           3.0   0.0
           4.0   0.0
        1  1.0   1.0
           2.0   2.0
           3.0   3.0
           4.0   4.0
        2  1.0   2.0
           2.0   4.0
           3.0   6.0
           4.0   8.0
        3  1.0   3.0
           2.0   6.0
           3.0   9.0
           4.0  12.0
        4  1.0   4.0
           2.0   8.0
           3.0  12.0
           4.0  16.0
        5  1.0   5.0
           2.0  10.0
           3.0  15.0
           4.0  20.0
        6  1.0   6.0
           2.0  12.0
           3.0  18.0
           4.0  24.0
        7  1.0   7.0
           2.0  14.0
           3.0  21.0
           4.0  28.0
        8  1.0   8.0
           2.0  16.0
           3.0  24.0
           4.0  32.0
        9  1.0   9.0
           2.0  18.0
           3.0  27.0
           4.0  36.0
        10 1.0  10.0
           2.0  20.0
           3.0  30.0
           4.0  40.0
        >>> fig, ax = comp.as_plot("b", color_factor="p.y", figsize=(10, 4))
        """
        self.factors = factors
        scen_groups = samp.get_scen_groups(*factors)
        super().__init__(res, scen_groups, **kwargs)



class NestedComparison(BaseComparison):
    def __init__(self, res, samp, samp_factors, samps, samps_factors, **kwargs):
        """
        Make a nested table of the statistic for samples taken in other samples.

        Parameters
        ----------
        res : Result
            Result with the given metrics over a number of scenarios.
        samp : BaseSample
            Sample object used to generate the scenarios
        samp_factors : list
            Factors (Scenario properties e.g., 'name', 'time', 'var') in samp to take
            statistic over. Default is ['time']
        samps : dict
            Sample objects used to generate the scenarios. {'name': samp}
        samps_factors : list
            Factors (Scenario properties e.g., 'name', 'time', 'var') in samp to take
            statistic over in the apps. Default is ['time']
        **kwargs : kwargs
            keyword arguments to BaseComparison

        Returns
        -------
        met_table : dataframe
            pandas dataframe with the statistic of the metric over the corresponding
            set of scenarios for the given factor level.
        """
        overall_scen_groups = {}
        scen_groups = samp.get_scen_groups(*samp_factors)
        for n_samp in samps.values():
            n_scen_groups = n_samp.get_scen_groups(*samps_factors)
            for scen_group, scens in scen_groups.items():
                for n_scen_group, n_scens in n_scen_groups.items():
                    k = tuple(list(scen_group)+list(n_scen_group))
                    v = [s+"."+ns for s in scens for ns in n_scens]
                    overall_scen_groups[k] = v

        self.factors = samp_factors + samps_factors
        super().__init__(res, overall_scen_groups, **kwargs)


if __name__ == "__main__":
    import doctest
    doctest.testmod(verbose=True)
