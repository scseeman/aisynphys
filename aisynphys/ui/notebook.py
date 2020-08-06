"""Commonly used routines when working with jupyter / matplotlib
"""
import numpy as np
import matplotlib
import matplotlib.cm
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from textwrap import wrap
from scipy import stats
from aisynphys.cell_class import CellClass
from neuroanalysis.data import TSeries
from neuroanalysis.baseline import float_mode
from aisynphys.avg_response_fit import response_query, sort_responses
from aisynphys.data import PulseResponseList


def heatmap(data, row_labels, col_labels, ax=None, ax_labels=None, bg_color=None,
            cbar_kw={}, cbarlabel="", **kwargs):
    """
    Create a heatmap from a numpy array and two lists of labels.
    
    Modified from https://matplotlib.org/3.1.0/gallery/images_contours_and_fields/image_annotated_heatmap.html

    Parameters
    ----------
    data
        A 2D numpy array of shape (N, M).
    row_labels
        A list or array of length N with the labels for the rows.
    col_labels
        A list or array of length M with the labels for the columns.
    ax
        A `matplotlib.axes.Axes` instance to which the heatmap is plotted.  If
        not provided, use current axes or create a new one.  Optional.
    ax_labels
        (x, y) axis labels
    bg_color
        Background color shown behind transparent pixels
    cbar_kw
        A dictionary with arguments to `matplotlib.Figure.colorbar`.  Optional.
    cbarlabel
        The label for the colorbar.  Optional.
    **kwargs
        All other arguments are forwarded to `imshow`.
    """

    if not ax:
        ax = plt.gca()

    if bg_color is not None:
        bg = np.empty(data.shape[:2] + (3,))
        bg[:] = matplotlib.colors.to_rgb(bg_color)        
        ax.imshow(bg)
        
    # Plot the heatmap
    im = ax.imshow(data, **kwargs)

    # Create colorbar
    cbar = ax.figure.colorbar(im, ax=ax, **cbar_kw)
    cbar.ax.set_ylabel(cbarlabel, rotation=-90, va="bottom")
    

    # We want to show all ticks...
    ax.set_xticks(np.arange(data.shape[1]))
    ax.set_yticks(np.arange(data.shape[0]))
    # ... and label them with the respective list entries.
    ax.set_xticklabels(col_labels)
    ax.set_yticklabels(row_labels)

    # Let the horizontal axes labeling appear on top.
    ax.tick_params(top=True, bottom=False, labeltop=True, labelbottom=False)

    # Rotate the tick labels and set their alignment.
    plt.setp(ax.get_xticklabels(), rotation=-30, ha="right", rotation_mode="anchor")

    ax.set_xticks(np.arange(data.shape[1]+1)-.5, minor=True)
    ax.set_yticks(np.arange(data.shape[0]+1)-.5, minor=True)
    ax.tick_params(which="minor", bottom=False, left=False)

    if ax_labels is not None:
        ax.set_ylabel(ax_labels[1], size=16)
        ax.set_xlabel(ax_labels[0], size=16)
        ax.xaxis.set_label_position('top')
    
    return im, cbar


def annotate_heatmap(im, labels, data=None, textcolors=("black", "white"),
                     threshold=None, **textkw):
    """
    A function to annotate a heatmap.

    Modified from https://matplotlib.org/3.1.0/gallery/images_contours_and_fields/image_annotated_heatmap.html

    Parameters
    ----------
    im
        The AxesImage to be labeled.
    labels
        Array of strings to display in each cell
    textcolors
        A list or array of two color specifications.  The first is used for
        values below a threshold, the second for those above.  Optional.
    **kwargs
        All other arguments are forwarded to each call to `text` used to create
        the text labels.
    """
    pixels, _, _, _ = im.make_image(renderer=None, unsampled=True)

    # Set default alignment to center, but allow it to be
    # overwritten by textkw.
    kw = dict(horizontalalignment="center", verticalalignment="center")
    kw.update(textkw)

    # Loop over the data and create a `Text` for each "pixel".
    # Change the text's color depending on the data.
    texts = []
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            px_color = pixels[i,j]
            if isinstance(px_color, np.ma.core.MaskedArray):
                px_color = px_color.data
            kw['color'] =  textcolors[int(np.mean(px_color[:3]) < 128)]
            text = im.axes.text(j, i, labels[i, j], **kw)
            texts.append(text)

    return texts


def show_connectivity_matrix(ax, results, pre_cell_classes, post_cell_classes, class_labels, cmap, norm, ctype='distance_adjusted', cbarlabel='Adjusted connection probability', alpha=True):
    """Display a connectivity matrix.

    This function uses matplotlib to display a heatmap representation of the output generated by
    aisynphys.connectivity.measure_connectivity(). Each element in the matrix is colored by connection 
    probability, and the connection probability confidence interval is used to set the transparency 
    such that the elements with the most data (and smallest confidence intervals) will appear
    in more bold colors. 

    Parameters
    ----------
    ax : matplotlib.axes
        The matplotlib axes object on which to draw the connectivity matrix
    results : dict
        Output of aisynphys.connectivity.measure_connectivity. This structure maps
        (pre_class, post_class) onto the results of the connectivity analysis.
    pre_cell_classes : list
        List of presynaptic cell classes in the order they should be displayed
    post_cell_classes : list
        List of postsynaptic cell classes in the order they should be displayed
    class_labels : dict
        Maps {cell_class: label} to give the strings to display for each cell class.
    cmap : matplotlib colormap instance
        The colormap used to generate colors for each matrix element
    norm : matplotlib normalize instance
        Normalize instance used to normalize connection probability values before color mapping
    ctype: string
        'chemical' or 'electrical'
    distance_adjusted: bool
        If True, use distance-adjusted connectivity metrics. See 
        ``aisynphys.connectivity.measure_connectivity(sigma)``.
    cbarlabel: string
        label for color bar
    alpha : float
        If True, apply transparency based on width of confidence intervals
    """
    # convert dictionary of results to a 2d array of connection probabilities
    shape = (len(pre_cell_classes), len(post_cell_classes))
    cprob = np.zeros(shape)
    cprob_alpha = np.zeros(shape)
    cprob_str = np.zeros(shape, dtype=object)

    for i,pre_class in enumerate(pre_cell_classes):
        for j,post_class in enumerate(post_cell_classes):
            result = results[pre_class, post_class]
            if ctype == 'chemical':
                found = result['n_connected']
                if distance_adjusted:
                    cp, cp_lower_ci, cp_upper_ci = result['adjusted_connectivity']
                else:
                    cp, cp_lower_ci, cp_upper_ci = result['connection_probability']
            if ctype == 'electrical':
                found = result['n_gaps']
                cp, cp_lower_ci, cp_upper_ci = result['gap_probability']

            cprob[i,j] = cp
            cprob_str[i,j] = "" if result['n_probed'] == 0 else "%d/%d" % (found, result['n_probed'])
            cprob_alpha[i,j] = 1.0 - 2.0 * (cp_upper_ci - cp_lower_ci)

    # map connection probability to RGB colors
    mapper = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)
    cprob_rgba = mapper.to_rgba(np.clip(cprob, 0.01, 1.0))

    # apply alpha based on confidence intervals
    if alpha:
        cprob_rgba[:, :, 3] = np.clip(cprob_alpha, 0, 1)

    # generate lists of labels to display along the pre- and postsynaptic axes
    pre_class_labels = [class_labels[cls] for cls in pre_cell_classes]
    post_class_labels = [class_labels[cls] for cls in post_cell_classes]

    # draw the heatmap with axis labels and colorbar
    im, cbar = heatmap(cprob_rgba, pre_class_labels, post_class_labels, ax=ax, 
        ax_labels=('postsynaptic', 'presynaptic'),
        bg_color=(0.7, 0.7, 0.7),
        cmap=cmap, norm=norm, 
        cbarlabel=cbarlabel, 
        cbar_kw={'shrink':0.5})

    # draw text over each matrix element
    labels = annotate_heatmap(im, cprob_str, data=cprob)
    
    return im, cbar, labels


def get_metric_data(metric, db, pre_classes=None, post_classes=None, pair_query_args=None):
    pair_query_args = pair_query_args or {}

    metrics = {
        #                               name                         unit   scale alpha  db columns                                    colormap      log     clim           text format
        'psp_amplitude':               ('PSP Amplitude',             'mV',  1e3,  1,     [db.Synapse.psp_amplitude],                   'bwr',        False,  (-1.5, 1.5),       "%0.2f mV"),
        'psp_rise_time':               ('PSP Rise Time',             'ms',  1e3,  0.5,   [db.Synapse.psp_rise_time],                   'viridis_r',  True,  (1, 10),        "%0.2f ms"),
        'psp_decay_tau':               ('PSP Decay Tau',             'ms',  1e3,  1,     [db.Synapse.psp_decay_tau],                   'viridis_r',  False,  (0, 20),       "%0.2f ms"),
        'psc_amplitude':               ('PSC Amplitude',             'mV',  1e3,  1,     [db.Synapse.psc_amplitude],                   'bwr',        False,  (-1, 1),       "%0.2f mV"),
        'psc_rise_time':               ('PSC Rise Time',             'ms',  1e3,  1,     [db.Synapse.psc_rise_time],                   'viridis_r',  False,  (0, 6),        "%0.2f ms"),
        'psc_decay_tau':               ('PSC Decay Tau',             'ms',  1e3,  1,     [db.Synapse.psc_decay_tau],                   'viridis_r',  False,  (0, 20),       "%0.2f ms"),
        'latency':                     ('Latency',                   'ms',  1e3,  1,     [db.Synapse.latency],                         'viridis_r',  False,  (0.5, 3),       "%0.2f ms"),
        'stp_initial_50hz':            ('Paired pulse STP',          '',    1,    1,     [db.Dynamics.stp_initial_50hz],               'bwr',        False,  (-0.5, 0.5),   "%0.2f"),
        'stp_induction_50hz':          ('Train induced STP',         '',    1,    1,     [db.Dynamics.stp_induction_50hz],             'bwr',        False,  (-0.5, 0.5),   "%0.2f"),
        'stp_recovery_250ms':          ('STP Recovery',              '',    1,    1,     [db.Dynamics.stp_recovery_250ms],             'bwr',        False,  (-0.5, 0.5),   "%0.2f"),
        'pulse_amp_90th_percentile':   ('PSP Amplitude 90th %%ile',  'mV',  1e3,  1.5,   [db.Dynamics.pulse_amp_90th_percentile],      'bwr',        False,  (-1.5, 1.5),    "%0.2f mV"),
        'junctional_conductance':      ('Junctional Conductance',    'nS',  1e9,  1,     [db.GapJunction.junctional_conductance],      'virdis',     False,  (0, 10),        "%0.2f nS"),
        'coupling_coeff_pulse':        ('Coupling Coefficient',       '',   1,    1,     [db.GapJunction.coupling_coeff_pulse],   'virdis',    False,  (0, 1),         "%0.2f"),
    }
    metric_name, units, scale, alpha, columns, cmap, cmap_log, clim, cell_fmt = metrics[metric]

    if pre_classes is None or post_classes is None:
        return None, metric_name, units, scale, alpha, cmap, cmap_log, clim, cell_fmt

    pairs = db.matrix_pair_query(
        pre_classes=pre_classes,
        post_classes=post_classes,
        pair_query_args=pair_query_args,
        columns=columns,
    )

    pairs_has_metric = pairs[~pairs[metric].isnull()]
    return pairs_has_metric, metric_name, units, scale, alpha, cmap, cmap_log, clim, cell_fmt

def pair_class_metric_scatter(metrics, db, pair_classes, pair_query_args, ax):
    """To create scatter plots from get_metric_data for specific pair_classes. In this case pair_classes is a list of
    tuples of specific pre->post class pairs instead of all combos from a list of pre-classes
    and post-classes

    Parameters
    -----------
    metrics : list 
        correspond to keys in metrics dict of `get_metric_data`
    db : SynPhys database 
    pair_classes : list
        list of tuples of CellClass (pre_class, post_class)
    pair_query_args : dict
        arguments to pass to db.pair_query

    Outputs
    --------
    Vertically stacked scatter plots for each metric (y) and pair_class (x)
    """
    pre_classes = {pair_class[0].name: pair_class[0] for pair_class in pair_classes}
    post_classes = {pair_class[1].name: pair_class[1] for pair_class in pair_classes}
    pair_classes = ['%s→%s' % (pc[0], pc[1]) for pc in pair_classes]
    for i, metric in enumerate(metrics):
        pairs_has_metric, metric_name, units, scale, _, _, _, _, _ = get_metric_data(metric, db, pre_classes=pre_classes, post_classes=post_classes, pair_query_args=pair_query_args)
        pairs_has_metric['pair_class'] = pairs_has_metric['pre_class'] + '→' + pairs_has_metric['post_class']
        pairs_has_metric = pairs_has_metric[pairs_has_metric['pair_class'].isin(pair_classes)]
        pairs_has_metric[metric] *= scale
        plot = sns.swarmplot(x='pair_class', y=metric, data=pairs_has_metric, ax=ax[i], size=6, palette='muted', edgecolor='black', alpha=0.8)
        sns.barplot(x='pair_class', y=metric, data=pairs_has_metric, ax=ax[i], ci=None, facecolor=(1, 1, 1, 0), edgecolor='black')
        
        if i == len(metrics) - 1:
            ax[i].set_xlabel('pre→post class', size=12)
            ax[i].set_xticklabels(plot.get_xticklabels(), rotation=45, horizontalalignment='right', fontsize='medium')
        else:
            ax[i].set_xlabel('')
            ax[i].set_xticklabels('')
        label = metric_name + ' (%s)'%units
        label = '\n'.join(wrap(label, 20))
        ax[i].set_ylabel(label, size=10)
        ax[i].set_yticklabels([], minor=True)
        ax[i].spines['right'].set_visible(False)
        ax[i].spines['top'].set_visible(False)
        ax[i].yaxis.set_ticks_position('left')
        if 'Amp' in metric_name:
            ax[i].axhline(y=0, color='k', linewidth=1)
            ax[i].spines['bottom'].set_visible(False)
            ax[i].tick_params(axis='x', bottom=False, top=False)
        else:
            ax[i].xaxis.set_ticks_position('bottom')


def metric_stats(metric, db, pre_classes, post_classes, pair_query_args):
    pairs_has_metric, _, units, scale, _, _, _, _, _ = get_metric_data(metric, db, pre_classes=pre_classes, post_classes=post_classes, pair_query_args=pair_query_args)
    pairs_has_metric[metric] = pairs_has_metric[metric].apply(pd.to_numeric)*scale
    summary = pairs_has_metric.groupby(['pre_class', 'post_class']).describe(percentiles=[0.5])
    return summary[metric], units


def ei_hist_plot(ax, metric, bin_edges, db, pair_query_args):
    ei_classes = {'ex': CellClass(cell_class_nonsynaptic='ex'), 'in': CellClass(cell_class_nonsynaptic='in')}
    
    pairs_has_metric, metric_name, units, scale, _, _, _, _, _ = get_metric_data(metric, db, ei_classes, ei_classes, pair_query_args=pair_query_args)
    ex_pairs = pairs_has_metric[pairs_has_metric['pre_class']=='ex']
    in_pairs = pairs_has_metric[pairs_has_metric['pre_class']=='in']
    if 'amp' in metric:
        ax[0].hist(ex_pairs[metric]*scale, bins=bin_edges, color=(0.8, 0.8, 0.8), label='All Excitatory Synapses')
        ax[1].hist(in_pairs[metric]*scale, bins=bin_edges, color=(0.8, 0.8, 0.8), label='All Inhibitory Synapses')
    else:
        ax[0].hist(pairs_has_metric[metric]*scale, bins=bin_edges, color=(0.8, 0.8, 0.8), label='All Synapses')
        ax[1].hist(pairs_has_metric[metric]*scale, bins=bin_edges, color=(0.8, 0.8, 0.8), label='All Synapses')

    ee_pairs = ex_pairs[ex_pairs['post_class']=='ex']
    ei_pairs = ex_pairs[ex_pairs['post_class']=='in']
    ax[0].hist(ee_pairs[metric]*1e3, bins=bin_edges, color='red', alpha=0.6, label='E->E Synapses')
    ax[0].hist(ei_pairs[metric]*1e3, bins=bin_edges, color='pink', alpha=0.8, label='E->I Synapses')
    ax[0].legend(frameon=False)

    ii_pairs = in_pairs[in_pairs['post_class']=='in']
    ie_pairs = in_pairs[in_pairs['post_class']=='ex']
    ax[1].hist(ii_pairs[metric]*1e3, bins=bin_edges, color='blue', alpha=0.4, label='I->I Synapses')
    ax[1].hist(ie_pairs[metric]*1e3, bins=bin_edges, color='purple', alpha=0.4, label='I->E Synapses')
    ax[1].legend(frameon=False)
    
    ax[0].spines['right'].set_visible(False)
    ax[0].spines['top'].set_visible(False)
    ax[1].spines['right'].set_visible(False)
    ax[1].spines['top'].set_visible(False)
    ax[1].set_xlabel('%s (%s)' % (metric_name, units))
    ax[1].set_ylabel('Number of Synapses', fontsize=12)

    #KS test
    excitatory = stats.ks_2samp(ee_pairs[metric], ei_pairs[metric])
    inhibitory = stats.ks_2samp(ii_pairs[metric], ie_pairs[metric])
    print('Two-sample KS test for %s' % metric)
    print('Excitatory: p = %0.3e' % excitatory[1])
    print('Inhibitory: p = %0.3e' % inhibitory[1])


def cell_class_matrix(pre_classes, post_classes, metric, class_labels, ax, db, pair_query_args=None):
    pairs_has_metric, metric_name, units, scale, alpha, cmap, cmap_log, clim, cell_fmt = get_metric_data(metric, db, pre_classes, post_classes, pair_query_args=pair_query_args)
    metric_data = pairs_has_metric.groupby(['pre_class', 'post_class']).aggregate(lambda x: np.mean(x))
    error = pairs_has_metric.groupby(['pre_class', 'post_class']).aggregate(lambda x: np.std(x))
    count = pairs_has_metric.groupby(['pre_class', 'post_class']).count()

    cmap = matplotlib.cm.get_cmap(cmap)
    if cmap_log:
        norm = matplotlib.colors.LogNorm(vmin=clim[0], vmax=clim[1], clip=False)
    else:
        norm = matplotlib.colors.Normalize(vmin=clim[0], vmax=clim[1], clip=False)

    shape = (len(pre_classes), len(post_classes))
    data = np.zeros(shape)
    data_alpha = np.zeros(shape)
    data_str = np.zeros(shape, dtype=object)

    for i, pre_class in enumerate(pre_classes):
        for j, post_class in enumerate(post_classes):
            try:
                value = getattr(metric_data.loc[pre_class].loc[post_class], metric)
                n = getattr(count.loc[pre_class].loc[post_class], metric)
                std = getattr(error.loc[pre_class].loc[post_class], metric)
                if n == 1:
                    value = np.nan
            except KeyError:
                value = np.nan
            data[i, j] = value * scale
            data_str[i, j] = cell_fmt % (value * scale) if np.isfinite(value) else ""
            data_alpha[i, j] = 1-alpha*((std*scale)/np.sqrt(n)) if np.isfinite(value) else 0 
            
    pre_labels = [class_labels[cls] for cls in pre_classes]
    post_labels = [class_labels[cls] for cls in post_classes]
    mapper = matplotlib.cm.ScalarMappable(cmap=cmap, norm=norm)
    data_rgb = mapper.to_rgba(data)
    data_rgb[:,:,3] = np.clip(data_alpha, 0, metric_data[metric].max()*scale)

    im, cbar = heatmap(data_rgb, pre_labels, post_labels,
                    ax=ax,
                    ax_labels=('postsynaptic', 'presynaptic'),
                    bg_color=(0.8, 0.8, 0.8),
                    cmap=cmap,
                    norm=norm,
                    cbarlabel=metric_name,
                    cbar_kw={'shrink':0.5})

    text = annotate_heatmap(im, data_str, data=data)

    return pairs_has_metric


def get_pair(expt_id, pre_cell, post_cell, db):
    expt = db.query(db.Experiment).filter(db.Experiment.ext_id==expt_id).all()[0]
    pairs = expt.pairs
    pair = pairs[(pre_cell, post_cell)]
    return pair


def map_color_by_metric(pair, metric, cmap, norm, scale):
    synapse = pair.synapse
    try:
        value= getattr(synapse, metric)*scale
    except:
        dynamics =pair.dynamics
        value = getattr(dynamics, metric)*scale
    mapper = matplotlib.cm.ScalarMappable(cmap=cmap, norm=norm)
    color = mapper.to_rgba(value)
    return color


def plot_metric_pairs(pair_list, metric, db, ax, align='pulse', norm_amp=None, perc=False):
    pairs = [get_pair(eid, pre, post, db) for eid, pre, post in pair_list]
    _, metric_name, units, scale, _, cmap, cmap_log, clim, _ = get_metric_data(metric, db)
    cmap = matplotlib.cm.get_cmap(cmap)
    if cmap_log:
        norm = matplotlib.colors.LogNorm(vmin=clim[0], vmax=clim[1], clip=False)
    else:
        norm = matplotlib.colors.Normalize(vmin=clim[0], vmax=clim[1], clip=False)
    colors = [map_color_by_metric(pair, metric, cmap, norm, scale) for pair in pairs]
    for i, pair in enumerate(pairs):
        s = db.session()
        q= response_query(s, pair, max_ind_freq=50)
        prs = [q.PulseResponse for q in q.all()]
        sort_prs = sort_responses(prs)
        prs = sort_prs[('ic', -55)]['qc_pass']
        if pair.synapse.synapse_type=='ex':
            prs = prs + sort_prs[('ic', -70)]['qc_pass']
        if perc:
            prs_amp = [abs(pr.pulse_response_fit.fit_amp) for pr in prs]
            amp_85, amp_95 = np.percentile(prs_amp, [85, 95])
            mask = (prs_amp >= amp_85) & (prs_amp <= amp_95)
            prs = np.asarray(prs)[mask]
        prl = PulseResponseList(prs)
        post_ts = prl.post_tseries(align='spike', bsub=True, bsub_win=0.1e-3)
        trace = post_ts.mean()*scale
        if norm_amp=='exc':
            trace = post_ts.mean()/pair.synapse.psp_amplitude
        if norm_amp=='inh':
            trace = post_ts.mean()/pair.synapse.psp_amplitude*-1
        latency = pair.synapse.latency
        if align=='pulse':
            trace.t0 = trace.t0 - latency

        ax.plot(trace.time_values*scale, trace.data, color=colors[i], linewidth=2)
        ax.set_xlim(-2, 10)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)


def show_distance_profiles(ax, results, colors, class_labels):
    """ Display connection probability vs distance plots
    Parameters
    -----------
    ax : matplotlib.axes
        The matplotlib axes object on which to make the plots
    results : dict
        Output of aisynphys.connectivity.measure_distance. This structure maps
        (pre_class, post_class) onto the results of the connectivity as a function of distance.
    colors: dict
        color to draw each (pre_class, post_class) connectivity profile. Keys same as results.
        To color based on overall connection probability use color_by_conn_prob.
    class_labels : dict
        Maps {cell_class: label} to give the strings to display for each cell class.
    """

    for i, (pair_class, result) in enumerate(results.items()):
        pre_class, post_class = pair_class
        plot = ax[i]
        xvals = result['bin_edges']
        xvals = (xvals[:-1] + xvals[1:])*0.5e6
        cp = result['conn_prob']
        lower = result['lower_ci']
        upper = result['upper_ci']

        color = colors[pair_class]
        color2 = list(color)
        color2[-1] = 0.2
        mid_curve = plot.plot(xvals, cp, color=color, linewidth=2.5)
        lower_curve = plot.fill_between(xvals, lower, cp, color=color2)
        upper_curve = plot.fill_between(xvals, upper, cp, color=color2)
        
        plot.set_title('%s -> %s' % (class_labels[pre_class], class_labels[post_class]))
        if i == len(ax)-1:
            plot.set_xlabel('Distance (um)')
            plot.set_ylabel('Connection Probability')
        
    return ax


def color_by_conn_prob(pair_group_keys, connectivity, norm, cmap):
    """ Return connection probability mapped color from show_connectivity_matrix
    """
    colors = {}
    for key in pair_group_keys:
        cp = connectivity[key]['connection_probability'][0]
        mapper = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)
        color = mapper.to_rgba(np.clip(cp, 0.01, 1.0))
        colors[key] = color

    return colors


def data_matrix(data_df, cell_classes, metric=None, scale=1, unit=None, cmap=None, norm=None, alpha=2):
    """ Return data and labels to make a matrix using heatmap and annotate_heatmap. Similar to 
    show_connectivity_matrix but for arbitrary data metrics.

    Parameters:
    -----------
    data_df : pandas dataframe 
        pairs with various metrics as column names along with the pre-class and post-class.
    cell_classes : list 
        cell classes included in the matrix, this assumes a square matrix.
    metric : str
        data metric to be displayed in matrix
    scale : float
        scale of the data
    unit : str
        unit for labels
    cmap : matplotlib colormap instance
        used to colorize the matrix
    norm : matplotlib normalize instance
        used to normalize the data before colorizing
    alpha : int
        used to desaturate low confidence data
    """

    shape = (len(cell_classes), len(cell_classes))
    data = np.zeros(shape)
    data_alpha = np.zeros(shape)
    data_str = np.zeros(shape, dtype=object)
    
    mean = data_df.groupby(['pre_class', 'post_class']).aggregate(lambda x: np.mean(x))
    error = data_df.groupby(['pre_class', 'post_class']).aggregate(lambda x: np.std(x))
    count = data_df.groupby(['pre_class', 'post_class']).count()
    
    for i, pre_class in enumerate(cell_classes):
        for j, post_class in enumerate(cell_classes):
            try:
                value = mean.loc[pre_class].loc[post_class][metric]
                std = error.loc[pre_class].loc[post_class][metric]
                n = count.loc[pre_class].loc[post_class][metric]
                if n == 1:
                    value = np.nan
                #data_df.loc[pre_class].loc[post_class][metric]
            except KeyError:
                value = np.nan
            data[i, j] = value*scale
            data_str[i, j] = "%0.2f %s" % (value*scale, unit) if np.isfinite(value) else ""
            data_alpha[i, j] = 1-alpha*((std*scale)/np.sqrt(n)) if np.isfinite(value) else 0 

    mapper = matplotlib.cm.ScalarMappable(cmap=cmap, norm=norm)
    data_rgb = mapper.to_rgba(data)
    max = mean[metric].max()*scale
    data_rgb[:,:,3] = np.clip(data_alpha, 0, max)
    return data_rgb, data_str
