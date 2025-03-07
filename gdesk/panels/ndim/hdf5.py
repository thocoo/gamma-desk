"""Saving and loading of hdf5 files in a ndim context"""

try:
    import h5py
    has_h5py = True
except ModuleNotFoundError:
    has_h5py = False


def load_ndim_from_hdf5(filepath):
    """Load one multi dim (>2) file from a hdf5 file

    If multiple ndim arrays are found then it asks the user which one to load.
    It throws an ImportError when no dataset with more than 2 dims is found.

    :param filepath: pathlib.Path uri to file to load
    :return: ndarray, key_name, list with dim names, list with dim scales (name, scale)
    """
    if not has_h5py:
        raise ModuleNotFoundError("h5py needs to be present for this to work")
    if not has_h5py:
        raise ModuleNotFoundError("Module h5py not found so cant open this file")
    file = h5py.File(filepath)
    keys = []
    file.visit(lambda key: keys.append(key) if isinstance(file[key], h5py.Dataset) else None)
    possible_candidates = list()
    for k in keys:
        if len(file[k].shape) > 2:
            possible_candidates.append(k)
    if len(possible_candidates) == 1:
        key = possible_candidates[0]
    elif len(possible_candidates) > 1:
        question = (f"The hdf5 file contains multiple ndim data sets.\n"
                    f"Select which one to view:")
        for pci, pc in enumerate(possible_candidates):
            question += f"\n {pci}: {pc}"
        key = possible_candidates[int(input(question))]
    else:
        raise ImportError("The hdf5 file has no data with more than 2 dims.")

    ds = file[key]
    dim_names = [d.label for d in ds.dims]
    dim_scales = list()
    for d in ds.dims:
        try:
            dim_scales.append((d.keys()[0], d[0][:]))
        except IndexError:
            dim_scales.append((None, None))
    return ds[...], key, dim_names, dim_scales


def save_ndim_to_hdf5(filepath, data, data_name=None, dim_names=None, dim_scales=None):
    """Save multi dim ndarray to hdf5 file

    :param filepath: pathlib.Path location to save the file
    :param data: numpy ndarray
    :param data_name: name to store the data under
    :param dim_names: list with names for each dimension
    :param dim_scales: tuple with (name, scale) for each dimension
    :return: None
    """
    if not has_h5py:
        raise ModuleNotFoundError("h5py needs to be present for this to work")
    if data_name is None:
        data_name = 'gdesk_ndim_data'
    if dim_names is None:
        dim_names = [None] * data.ndim
    if dim_scales is None:
        dim_scales = [(None, None)] * data.ndim

    h = h5py.File(filepath, 'w')
    h.create_dataset(data_name, data=data, compression='gzip')
    for dim in range(data.ndim):
        if dim_names[dim] is not None:
            h[data_name].dims[dim].label = dim_names[dim]
        scale_name, scale = dim_scales[dim]
        if scale is not None:
            h[f'scales/dim_{dim}'] = scale
            if scale_name is not None:
                h[f'scales/dim_{dim}'].make_scale(scale_name)
            else:
                h[f'scales/dim_{dim}'].make_scale(f"dim_{dim}_scale")
            h[data_name].dims[dim].attach_scale(h[f'scales/dim_{dim}'])
    h.close()
