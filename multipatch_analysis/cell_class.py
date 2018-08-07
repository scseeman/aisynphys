
from __future__ import print_function, division

from collections import OrderedDict
from .database import database as db
from .morphology import Morphology
from . import constants


class CellClass(object):
    """Represents a class of cells as a list of selection criteria.
    """

    def __init__(self, **criteria):
        self.criteria = criteria

    @property
    def name(self):
        name = []

        target_layer = self.criteria.get('target_layer')
        if target_layer is not None:
            name.append('L' + target_layer)

        if self.criteria.get('pyramidal') is True:
            name.append('pyr')

        cre_type = self.criteria.get('cre_type')
        if cre_type is not None:
            name.append(cre_type)
        
        return ' '.join(name)

    @property
    def is_excitatory(self):
        cre = self.criteria.get('cre_type')
        pyr = self.criteria.get('pyramidal')
        return cre == 'unknown' or cre in constants.EXCITATORY_CRE_TYPES or pyr is True

    def __contains__(self, cell):
        morpho = cell.morphology
        for k, v in self.criteria.items():
            if hasattr(cell, k):
                if getattr(cell, k) != v:
                    return False
            elif hasattr(morpho, k):
                if getattr(morpho, k) != v:
                    return False
            else:
                raise Exception('Cannot use "%s" for cell typing; attribute not found on cell or cell.morphology' % k)
        return True

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, a):
        """Cell class is considered equal to its *name* to allow it to be indexed from a dict more
        easily::

            cc = CellClass(cre_type='sst', layer='6')
            cc.name => 'L6 sst'
            {cc: 1}['L6 sst'] => 1 
        """
        if isinstance(a, str):
            return a == self.name
        else:
            return object.__eq__(self, a)

    def __repr__(self):
        return "<CellClass %s>" % self.name

    def __str__(self):
        return self.name


def classify_cells(cell_classes, cells=None, pairs=None, session=None):
    """Given cell class definitions and a list of cells, return a dict indicating which cells
    are members of each class.

    Parameters
    ----------
    cell_classes : dict
        Dict of {class_name: class_criteria}, where each *class_criteria* value describes selection criteria for a cell class.
    cells : list | None
        List of Cell instances to be classified.
    pairs : list | None
        List of pairs from which cells will be collected. May not be used with *cells* or *session*
    session: Session | None
        If *cells* is not provided, then a database session may be given instead from which
        cells will be selected.
    """
    if pairs is not None:
        assert cells is None, "cells and pairs arguments are mutually exclusive"
        assert session is None, "session and pairs arguments are mutually exclusive"
        cells = set([p.pre_cell for p in pairs] + [p.post_cell for p in pairs])
    if cells is None:
        cells = session.query(db.Cell, db.Cell.cre_type, db.Cell.target_layer, Morphology.pyramidal).join(Morphology)
    cell_groups = OrderedDict([(cell_class, set()) for cell_class in cell_classes])
    for cell in cells:
        for cell_class in cell_classes:
            if cell in cell_class:
                cell_groups[cell_class].add(cell)
    return cell_groups



