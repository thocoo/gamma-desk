import numpy as np
from .base import RecordTable

def compare(table1, table2, value_column_name, index_column_name=None):

    if index_column_name is None:
        valcol1 = table1.sa[value_column_name]
        valcol2 = table2.sa[value_column_name]
        
        difflocs = np.where(valcol1 != valcol2)                
        
        difftable = RecordTable()
        difftable.add_column('value1', data=valcol1[difflocs])
        difftable.add_column('value2', data=valcol2[difflocs])
        
        
    else:
        ind1 = table1.sa[index_column_name]
        ind2 = table2.sa[index_column_name]
        
        valcol1 = table1.colnames.index(value_column_name)
        valcol2 = table2.colnames.index(value_column_name)
        
        locs1 = dict(zip(ind1, range(len(ind1))))
        locs2 = dict(zip(ind2, range(len(ind2))))   
        
        indices = sorted(set(ind1).union(set(ind2)))
        
        difftable = RecordTable(['index', 'value1', 'value2'])
        
        for ind in indices:
            loc1 = locs1.get(ind, None)
            loc2 = locs2.get(ind, None)
            rec1 = None if loc1 is None else table1[loc1]
            rec2 = None if loc2 is None else table2[loc2]
            if rec1[valcol1] != rec2[valcol2]:
                difftable.add_row((ind, rec1[valcol1], rec2[valcol2]))
            
    return difftable