# Copyright 2020 Virginia Polytechnic Institute and State University.
""" OpenFOAM I/O.

These functions are accesible from ``dafi.random_field.foam``.
"""

# standard library imports
import os
import shutil
import re
import subprocess

# third party imports
import numpy as np

# global variables
NDIM = {'scalar': 1,
        'vector': 3,
        'symmTensor': 6,
        'tensor': 9}


# get mesh properties by running OpenFOAM shell utilities
def _bash_source_of(file=None):
    """ System-specific file to source OpenFOAM on the subprocess call. 

    Most installation on linux should not require this. 

    Parameters
    ----------
    file : str
        Name (path) of file that sources OpenFOAM.

    Returns
    -------
    bash_command : str
        Shell command to source OpenFOAM.
    """
    if file == None:
        bash_command = ""
    else:
        bash_command = f"source {file} > /dev/null 2>&1; "
    return bash_command


def _check0(foam_case):
    """ Create OpenFOAM 0 directory if it does not exist.

    Copies the 0.orig folder if the 0 folder does not exist.

    Parameters
    ----------
    foam_case : str
        Name (path) of OF case directory.

    Returns
    -------
    dirCreated : bool
        Whether the 0 directory was created. If it exists already
        returns *'False'*.
    """
    dst = os.path.join(foam_case, '0')
    dirCreated = False
    if not os.path.isdir(dst):
        src = os.path.join(foam_case, '0.orig')
        shutil.copytree(src, dst)
        dirCreated = True
    return dirCreated


def _checkMesh(foam_case, foam_rc=None):
    """ Create OpenFOAM mesh if it does not exist.

    Requires OpenFOAM to be sourced. Calls ``blockMesh`` utility.

    Parameters
    ----------
    foam_case : str
        Name (path) of OF case directory.

    foam_rc : str
        File for sourcing OpenFOAM.

    Returns
    -------
    meshCreated : bool
        Whether the mesh was created. If mesh existed already returns
        *`False`*.
    """
    meshdir = os.path.join(foam_case, 'constant', 'polyMesh')
    meshCreated = False
    if not os.path.isdir(meshdir):
        bash_command = _bash_source_of(foam_rc)
        bash_command += "blockMesh -case " + foam_case
        subprocess.call(bash_command, shell=True)
        meshCreated = True
    return meshCreated


def get_number_cells(foam_case='.', foam_rc=None):
    """ Get the number of cells in an OpenFOAM case.

    Requires OpenFOAM to be sourced, since it calls the ``checkMesh``
    utility.

    Parameters
    ----------
    foam_case : str
        Name (path) of OF case directory.

    foam_rc : str
        File for sourcing OpenFOAM.

    Returns
    -------
    ncells : int
        Number of cells.
    """
    bash_command = _bash_source_of(foam_rc)
    bash_command += "checkMesh -case " + foam_case + \
        " -time '0' | grep '    cells:'"
    cells = subprocess.check_output(bash_command, shell=True)
    cells = cells.decode("utf-8").replace('\n', '').split(':')[1].strip()
    return int(cells)


def get_cell_centres(foam_case='.', group='internalField',  keep_file=False,
                     foam_rc=None):
    """ Get the coordinates of cell centers in an OpenFOAM case.

    Requires OpenFOAM to be sourced.

    Parameters
    ----------
    foam_case : str
        Name (path) of OF case directory.

    keep_file : bool
        Whether to keep the file (C) generated by the OpenFOAM
        post-processing utility. 

    foam_rc : str
        File for sourcing OpenFOAM.

    Returns
    -------
    coords : ndarray
        Cell center coordinates (x, y, z).
        *dtype=float*, *ndim=2*, *shape=(ncells, 3)*
    """
    timedir = '0'
    del0 = _check0(foam_case)
    delMesh = _checkMesh(foam_case)
    bash_command = _bash_source_of(foam_rc)
    bash_command += "postProcess -func writeCellCentres " + \
        "-case " + foam_case + f" -time '{timedir}' " + "> /dev/null"
    subprocess.call(bash_command, shell=True)
    os.remove(os.path.join(foam_case, timedir, 'Cx'))
    os.remove(os.path.join(foam_case, timedir, 'Cy'))
    os.remove(os.path.join(foam_case, timedir, 'Cz'))
    file = os.path.join(foam_case, timedir, 'C')
    coords = read_cell_centres(file, group=group)
    if not keep_file:
        os.remove(file)
    if del0:
        shutil.rmtree(os.path.join(foam_case, timedir))
    if delMesh:
        shutil.rmtree(os.path.join(foam_case, 'constant', 'polyMesh'))
    return coords


def get_cell_volumes(foam_case='.', keep_file=False, foam_rc=None):
    """ Get the volume of each cell in an OpenFOAM case.

    Requires OpenFOAM to be sourced.

    Parameters
    ----------
    foam_case : str
        Name (path) of OF case directory.

    keep_file : bool
        Whether to keep the file (V) generated by the OpenFOAM
        post-processing utility.

    foam_rc : str
        File for sourcing OpenFOAM.

    Returns
    -------
    vol : ndarray
        Cell volumes.
        *dtype=float*, *ndim=1*, *shape=(ncells)*
    """
    timedir = '0'
    del0 = _check0(foam_case)
    delMesh = _checkMesh(foam_case)
    bash_command = _bash_source_of(foam_rc)
    bash_command += "postProcess -func writeCellVolumes " + \
        "-case " + foam_case + f" -time {timedir} " + "> /dev/null"
    subprocess.call(bash_command, shell=True)
    file = os.path.join(foam_case, timedir, 'V')
    vol = read_cell_volumes(file)
    if not keep_file:
        os.remove(file)
    if del0:
        shutil.rmtree(os.path.join(foam_case, timedir))
    if delMesh:
        shutil.rmtree(os.path.join(foam_case, 'constant', 'polyMesh'))
    return vol


def get_neighbors(foam_case='.'):
    """ Get the neighbors of each cell (connectivity). 

    Parameters
    ----------
    foam_case : str
        Name (path) of OF case directory.

    Returns
    -------
    connectivity : dictionary
        The keys are cell's index and the values are a list of indices 
        for the cells that neighbor it. 
    """
    # create mesh if needed
    timedir = '0'
    del0 = _check0(foam_case)
    delMesh = _checkMesh(foam_case)
    ncells = get_number_cells(foam_case)

    # read mesh files
    mesh_dir = os.path.join(foam_case, 'constant', 'polyMesh')
    owner = read_scalar_field(os.path.join(mesh_dir, 'owner'), ' ')
    neighbour = read_scalar_field(os.path.join(mesh_dir, 'neighbour'), ' ')

    # keep internal faces only
    nintfaces = len(neighbour)
    owner = owner[:nintfaces]

    #
    connectivity = {cellid: [] for cellid in range(ncells)}
    for iowner, ineighbour in zip(owner, neighbour):
        connectivity[int(iowner)].append(int(ineighbour))
        connectivity[int(ineighbour)].append(int(iowner))

    if del0:
        shutil.rmtree(os.path.join(foam_case, timedir))
    if delMesh:
        shutil.rmtree(os.path.join(foam_case, 'constant', 'polyMesh'))

    return connectivity


# read fields
def read_field(file, ndim, group='internalField'):
    """ Read the field values from an OpenFOAM field file.

    Can read either the internal field or a specified boundary.

    Parameters
    ----------
    file : str
        Name of OpenFOAM field file.
    ndim : int
        Field dimension (e.g. 1 for scalar field).
    group : str
        Name of the group to read: *'internalField'* or name of specific
        boundary.

    Returns
    -------
    data : ndarray
        Field values on specified group.
        *dtype=float*, *ndim=2*, *shape=(ncells, ndim)*
    """
    # read file
    with open(file, 'r') as f:
        content = f.read()
    # keep file portion after specified group
    content = content.partition(group)[2]
    # data structure
    whole_number = r"([+-]?[\d]+)"
    decimal = r"([\.][\d]*)"
    exponential = r"([Ee][+-]?[\d]+)"
    floatn = f"{whole_number}{{1}}{decimal}?{exponential}?"
    if ndim == 1:
        data_structure = f"({floatn}\\n)+"
    else:
        data_structure = r'(\(' + f"({floatn}" + r"(\ ))" + \
            f"{{{ndim-1}}}{floatn}" + r"\)\n)+"
    # extract data
    pattern = r'\(\n' + data_structure + r'\)'
    data_str = re.compile(pattern).search(content).group()
    # convert to numpy array
    data_str = data_str.replace('(', '').replace(')', '').replace('\n', ' ')
    data_str = data_str.strip()
    data = np.fromstring(data_str, dtype=float, sep=' ')
    if ndim > 1:
        data = data.reshape([-1, ndim])
    return data


def read_scalar_field(file, group='internalField'):
    """ Read an OpenFOAM scalar field file.

    See :py:meth:`read_field` for more information.
    """
    return read_field(file, NDIM['scalar'], group=group)


def read_vector_field(file, group='internalField'):
    """ Read an OpenFOAM vector field file.

    See :py:meth:`read_field` for more information.
    """
    return read_field(file, NDIM['vector'], group=group)


def read_symmTensor_field(file, group='internalField'):
    """ Read an OpenFOAM symmTensor field file.

    See :py:meth:`read_field` for more information.
    """
    return read_field(file, NDIM['symmTensor'], group=group)


def read_tensor_field(file, group='internalField'):
    """ Read an OpenFOAM tensor field file.

    See :py:meth:`read_field` for more information.
    """
    return read_field(file, NDIM['tensor'], group=group)


def read_cell_centres(file='C', group='internalField'):
    """ Read an OpenFOAM mesh coordinate file.

    See :py:meth:`read_field` for more information.
    """
    return read_vector_field(file, group=group)


def read_cell_volumes(file='V'):
    """ Read an OpenFOAM mesh volume file.

    See :py:meth:`read_field` for more information.
    """
    return read_scalar_field(file, group='internalField')


# read entire field file
def _read_logo(content):
    """ Read info from logo in file header. """
    def _read_logo(pat):
        pattern = pat + r":\s+\S+"
        data_str = re.compile(pattern).search(content).group()
        return data_str.split(':')[1].strip()

    info = {}
    for pat in ['Version', 'Website']:
        info[pat] = _read_logo(pat)
    return info


def _read_header_info(content):
    """ Read info from info section in file header. """
    def _read_header(pat):
        pattern = pat + r"\s+\S+;"
        data_str = re.compile(pattern).search(content).group()
        return data_str.split(pat)[1][:-1].strip()

    info = {}
    foam_class = _read_header('class').split('Field')[0].split('vol')[1]
    info['foam_class'] = foam_class[0].lower() + foam_class[1:]
    info['name'] = _read_header('object')
    try:
        info['location'] = _read_header('location')
    except AttributeError:
        info['location'] = None
    return info


def read_field_file(file):
    """ Read a complete OpenFOAM field file.

    This includes header information not just the field values.
    The output can be directly used to write the file again, e.g.

    .. code-block:: python

        >>> content = read_field_file(file)
        >>> write_field_file(**content).

    Parameters
    ----------
    file : str
        Name (path) of OpenFOAM field file.

    Returns
    -------
    info : dictionary
        The contents of the file organized with the same structure as
        the inputs to the :py:meth:`write_field_file` method. See
        :py:meth:`write_field_file` for more information.
    """
    with open(file, 'r') as f:
        content = f.read()
    info = {}
    info['file'] = file

    # read logo
    logo_info = _read_logo(content)
    info['foam_version'] = logo_info['Version']
    info['website'] = logo_info['Website']

    # read header
    header_info = _read_header_info(content)
    info['foam_class'] = header_info['foam_class']
    info['name'] = header_info['name']
    info['location'] = header_info['location']

    # dimension
    pattern = r"dimensions\s+.+"
    data_str = re.compile(pattern).search(content).group()
    info['dimensions'] = data_str.split('dimensions')[1][:-1].strip()

    # internalField: uniform/nonuniform
    internal = {}
    pattern = r'internalField\s+\S+\s+.+'
    data_str = re.compile(pattern).search(content).group()
    if data_str.split()[1] == 'uniform':
        internal['uniform'] = True
        tmp = data_str.split('uniform')[1].strip()[:-1]
        tmp = tmp.replace('(', '').replace(')', '').split()
        internal['value'] = np.array([float(i) for i in tmp])
    else:
        internal['uniform'] = False
        internal['value'] = read_field(file, NDIM[info['foam_class']])
    info['internal_field'] = internal

    # boundaries: type and value(optional)
    #   value can be uniform/nonuniform scalar/(multi)
    boundaries = []
    bcontent = content.split('boundaryField')[1].strip()[1:].strip()
    pattern = r'\w+' + r'[\s\n]*' + r'\{' + r'[\w\s\n\(\);\.\<\>\-+]+' + r'\}'
    boundaries_raw = re.compile(pattern).findall(bcontent)
    for bc in boundaries_raw:
        ibc = {}
        # name
        pattern = r'[\w\s\n]+' + r'\{'
        name = re.compile(pattern).search(bc).group()
        name = name.replace('{', '').strip()
        ibc['name'] = name
        # type
        pattern = r'type\s+\w+;'
        type = re.compile(pattern).search(bc).group()
        type = type.split('type')[1].replace(';', '').strip()
        ibc['type'] = type
        # value
        if 'value' in bc:
            value = {}
            v = bc.split('value')[1]
            if v.split()[0] == 'uniform':
                value['uniform'] = True
                v = v.split('uniform')[1]
                tmp = v.replace('}', '').replace(';', '').strip()
                tmp = tmp.replace('(', '').replace(')', '').split()
                if len(tmp) == 1:
                    value['data'] = float(tmp[0])
                else:
                    value['data'] = np.array([float(i) for i in tmp])
            else:
                value['uniform'] = False
                value['data'] = read_field(
                    file, NDIM[info['foam_class']], group=ibc['name'])
        else:
            value = None
        ibc['value'] = value
        boundaries.append(ibc)
    info['boundaries'] = boundaries
    return info


def read_header(file):
    """ Read the information in an OpenFOAM file header.

    Parameters
    ----------
    file : str
        Name (path) of OpenFOAM file.

    Returns
    -------
    info : dictionary
        The information in the file header.
    """
    with open(file, 'r') as f:
        content = f.read()
    info = {}
    info['file'] = file

    # read logo
    logo_info = _read_logo(content)
    info['foam_version'] = logo_info['Version']
    info['website'] = logo_info['Website']

    # read header
    header_info = _read_header_info(content)
    info['foam_class'] = header_info['foam_class']
    info['name'] = header_info['name']
    info['location'] = header_info['location']

    return info


def read_controlDict():
    # TODO: Implement.
    # read header logo
    # read header info
    # read content
    raise NotImplementedError()


# write fields
def foam_sep():
    """ Write a separation comment line.

    Used by :py:meth:`write_field_file`.

    Returns
    -------
    sep : str
        Separation comment string
    """
    return '\n// ' + '* '*37 + '//'


def foam_header_logo(foam_version, website):
    """ Write the logo part of the OpenFOAM file header.

    Used by :py:meth:`write_field_file`.

    Parameters
    ----------
    foam_version : str
        OpenFOAM version to write in the header.
    website : str
        OpenFOAM website to write in the header.

    Returns
    -------
    header : str
        OpenFOAM file header logo.
    """
    def header_line(str1, str2):
        return f'\n| {str1:<26}| {str2:<48}|'

    header_start = '/*' + '-'*32 + '*- C++ -*' + '-'*34 + '*\\'
    header_end = '\n\\*' + '-'*75 + '*/'
    logo = ['=========',
            r'\\      /  F ield',
            r' \\    /   O peration',
            r'  \\  /    A nd',
            r'   \\/     M anipulation',
            ]
    info = ['',
            'OpenFOAM: The Open Source CFD Toolbox',
            f'Version:  {foam_version}',
            f'Website:  {website}',
            '',
            ]
    # create header
    header = header_start
    for l, i in zip(logo, info):
        header += header_line(l, i)
    header += header_end
    return header


def foam_header_info(name, foamclass, location=None, isfield=True):
    """ Write the info part of the OpenFOAM file header.

    Used by :py:meth:`write_field_file`.

    Parameters
    ----------
    name : str
        Field name (e.g. 'p').
    foamclass : str
        OpenFOAM class (e.g. 'scalar').
    location : str
        File location (optional).

    Returns
    -------
    header : str
        OpenFOAM file header info.
    """
    def header_line(str1, str2):
        return f'\n    {str1:<12}{str2};'

    VERSION = '2.0'
    FORMAT = 'ascii'
    if isfield:
        foamclass = 'vol' + foamclass[0].capitalize() + foamclass[1:] + 'Field'
    # create header
    header = 'FoamFile\n{'
    header += header_line('version', VERSION)
    header += header_line('format', FORMAT)
    header += header_line('class', foamclass)
    if location is not None:
        header += header_line('location', f'"{location}"')
    header += header_line('object', name)
    header += '\n}'
    return header


def write_controlDict(content, foam_version, website, ofcase=None):
    """
    Parameters
    ----------
    content : dict
        Content of controlDict.
    foam_version : str
        OpenFOAM version to write in the header.
    website : str
        OpenFOAM website to write in the header.
    ofcase : str
        OpenFOAM directory. File will be written to
        <ofcase>/system/controlDict. If *None* file will be written in
        current directory.

    Returns
    -------
    file_loc : str
        Location (absolute path) of file written.
    file_content : str
        Content written to file.
    """
    # create content
    file_str = foam_header_logo(foam_version, website) + '\n'
    file_str += foam_header_info('controlDict', 'dictionary', 'system', False)
    file_str += '\n' + foam_sep() + '\n'
    for key, val in content.items():
        file_str += f'\n{key:<16} {val};'
    file_str += '\n' + foam_sep()

    # write
    if ofcase is None:
        file = 'controlDict'
    else:
        file = os.path.join(ofcase, 'system', 'controlDict')
    with open(file, 'w') as f:
        f.write(file_str)
    return os.path.abspath(file), file_str


def write_field_file(name, foam_class, dimensions, internal_field,
                     boundaries, foam_version, website, location=None,
                     file=None):
    """ Write an OpenFOAM field file.

    Parameters
    ----------
    name : str
        Field name (e.g. 'p').
    foam_class : str
        OpenFOAM class (e.g. 'scalar').
    dimensions : str or list
        Field dimensions in SI units using OpenFOAM convention
        (e.g. '[0 2 -2 0 0 0 0]').
        Alternatively can be a list of 7 or 3 integers. If three (MLT)
        zeros will be appended at the end, i.e. [M L T 0 0 0 0].
    internal_field : dictionary
        Dictionary containing internal field information. See note below
        for more information.
    boundaries : list
        List containing one dictionary per boundary. Each dictionary
        contains the required information on that boundary. See note
        below for more information.
    foam_version : str
        OpenFOAM version to write in the header.
    website : str
        OpenFOAM website to write in the header.
    location : str
        File location (optional).
    file : str
        File name (path) where to write field. If *'None'* will write in
        current directory using the field name as the file name.

    Returns
    -------
    file_loc : str
        Location (absolute path) of file written.
    file_content : str
        Content written to file.

    Note
    ----
    **internal_field**
        The ``internal_field`` dictionary must have the following
        entries:

            * **uniform** - *bool*
                Whether the internal field has uniform or nonuniform
                value.
            * **value** - *float* or *ndarray*
                The uniform or nonuniform values of the internal field.

    **boundaries**
        Each boundary dictionary in the ``boundaries`` list must have
        the following entries:

            * **name** - *str*
                Boundary name.
            * **type** - *str*
                Boundary type.
            * **value** - *dict* (optional)
                Dictionary with same entries as the *'internal_field'*
                dictionary.
    """
    def _foam_field(uniform, value, foamclass=None):
        def _list_to_foamstr(inlist):
            outstr = ''
            for l in inlist:
                outstr += f'{l} '
            return outstr.strip()

        def _foam_nonuniform(data):
            field = f'{len(data)}\n('
            if data.ndim == 1:
                for d in data:
                    field += f'\n{d}'
            elif data.ndim == 2:
                for d in data:
                    field += f'\n({_list_to_foamstr(d)})'
            else:
                raise ValueError('"data" cannot have more than 2 dimensions.')
            field += '\n)'
            return field

        if uniform:
            # list type
            if isinstance(value, (list, np.ndarray)):
                if isinstance(value, np.ndarray):
                    # value = np.atleast_1d(np.squeeze(value))
                    value = np.squeeze(value)
                    if value.ndim != 1:
                        err_msg = 'Uniform data should have one dimension.'
                        raise ValueError(err_msg)
                value = f'({_list_to_foamstr(value)})'
            field = f'uniform {value}'
        else:
            if foamclass is None:
                raise ValueError('foamclass required for nonuniform data.')
            value = np.squeeze(value)
            field = f'nonuniform List<{foamclass}>'
            field += '\n' + _foam_nonuniform(value)
        return field

    def _foam_dimensions(dimensions):
        if isinstance(dimensions, list):
            if len(dimensions) == 3:
                dimensions = dimensions.append([0, 0, 0, 0])
            elif len(dimensions) != 7:
                raise ValueError('Dimensions must be length 3 or 7.')
            str = ''
            for idim in dimensions:
                str += f'{idim} '
            dimensions = f'[{str.strip()}]'
        return dimensions

    # create string
    file_str = foam_header_logo(foam_version, website)
    file_str += '\n' + foam_header_info(name, foam_class, location)
    file_str += '\n' + foam_sep()
    file_str += '\n'*2 + f'dimensions      {_foam_dimensions(dimensions)};'
    file_str += '\n'*2 + 'internalField   '
    file_str += _foam_field(
        internal_field['uniform'], internal_field['value'], foam_class) + ';'
    file_str += '\n\nboundaryField\n{'
    for bc in boundaries:
        file_str += '\n' + ' '*4 + bc["name"] + '\n' + ' '*4 + '{'
        file_str += '\n' + ' '*8 + 'type' + ' '*12 + bc["type"] + ';'
        write_value = False
        if 'value' in bc:
            if bc['value'] is not None:
                write_value = True
        if write_value:
            data = _foam_field(
                bc['value']['uniform'], bc['value']['data'], foam_class)
            file_str += '\n' + ' '*8 + 'value' + ' '*11 + data + ';'
        file_str += '\n' + ' '*4 + '}'
    file_str += '\n}\n' + foam_sep()

    # write to file
    if file is None:
        file = name
    with open(file, 'w') as f:
        f.write(file_str)
    return os.path.abspath(file), file_str


def write(version, fieldname, internal_field, boundaries, location=None,
          file=None):
    """ Write an OpenFOAM field file for one of the pre-specified fields.

    The implemented fields are: 'p', 'k', 'epsilon', 'omega', 'nut',
    'Cx', 'Cy', 'Cz', 'V', 'U', 'C', 'Tau', 'grad(U)'.
    This calls :py:meth:`write_field_file` but requires less information.

    Parameters
    ----------
    version : str
        OpenFOAM version. Must be length 1 (e.g. '7') or 4 (e.g. '1912').
    fieldname : str
        One of the pre-defined fields.
    internal_field : dictionary
        See :py:meth:`write_field_file`.
    boundaries : list
        See :py:meth:`write_field_file`.
    location : str
        See :py:meth:`write_field_file`.
    file : str
        See :py:meth:`write_field_file`.
    """
    def field_info(fieldname):
        def get_foam_class(fieldname):
            scalarlist = ['p', 'k', 'epsilon', 'omega', 'nut', 'Cx', 'Cy',
                          'Cz', 'V']
            if fieldname in scalarlist:
                foam_class = 'scalar'
            elif fieldname in ['U', 'C']:
                foam_class = 'vector'
            elif fieldname == 'Tau':
                foam_class = 'symmTensor'
            elif fieldname == 'grad(U)':
                foam_class = 'tensor'
            return foam_class

        def get_dimensions(fieldname):
            #  1 - Mass (kg)
            #  2 - Length (m)
            #  3 - Time (s)
            #  4 - Temperature (K)
            #  5 - Quantity (mol)
            #  6 - Current (A)
            #  7 - Luminous intensity (cd)
            if fieldname == 'U':
                dimensions = '[ 0 1 -1 0 0 0 0]'
            elif fieldname in ['p', 'k', 'Tau']:
                dimensions = '[0 2 -2 0 0 0 0]'
            elif fieldname == 'phi':
                dimensions = '[0 3 -1 0 0 0 0]'
            elif fieldname == 'epsilon':
                dimensions = '[0 2 -3 0 0 0 0]'
            elif fieldname in ['omega', 'grad(U)']:
                dimensions = '[0 0 -1 0 0 0 0]'
            elif fieldname == 'nut':
                dimensions = '[0 2 -1 0 0 0 0]'
            elif fieldname in ['C', 'Cx', 'Cy', 'Cz']:
                dimensions = '[0 1 0 0 0 0 0]'
            elif fieldname == 'V':
                dimensions = '[0 3 0 0 0 0 0]'
            return dimensions

        field = {'name': fieldname,
                 'class': get_foam_class(fieldname),
                 'dimensions': get_dimensions(fieldname)}
        return field

    def version_info(version):
        # string ('7' or '1912')
        website = 'www.openfoam.'
        if len(version) == 1:
            version += '.x'
            website += 'org'
        elif len(version) == 4:
            version = 'v' + version
            website += 'com'
        foam = {'version': version,
                'website': website}
        return foam

    foam = version_info(version)
    field = field_info(fieldname)

    file_path, file_str = write_field_file(
        foam_version=foam['version'],
        website=foam['website'],
        name=field['name'],
        foam_class=field['class'],
        dimensions=field['dimensions'],
        internal_field=internal_field,
        boundaries=boundaries,
        location=location,
        file=file)
    return file_path, file_str


def write_p(version, internal, boundaries, location=None, file=None):
    """ Write a pressure field file.

    See :func:`~dafi.random_field.foam_utilities.write` for more
    information.
    """
    return write(version, 'p', internal, boundaries, location, file)


def write_U(version, internal, boundaries, location=None, file=None):
    """ Write a velocity field file.

    See :func:`~dafi.random_field.foam_utilities.write` for more
    information.
    """
    return write(version, 'U', internal, boundaries, location, file)


def write_Tau(version, internal, boundaries, location=None, file=None):
    """ Write a Reynolds stress field file.

    See  :func:`~dafi.random_field.foam_utilities.write` for more
    information.
    """
    return write(version, 'Tau', internal, boundaries, location, file)


def write_nut(version, internal, boundaries, location=None, file=None):
    """ Write an eddy viscosity field file.

    See  :func:`~dafi.random_field.foam_utilities.write` for more
    information.
    """
    return write(version, 'nut', internal, boundaries, location, file)


def write_k(version, internal, boundaries, location=None, file=None):
    """ Write a turbulent kinetic energy (TKE) field file.

    See :func:`~dafi.random_field.foam_utilities.write` for more
    information.
    """
    return write(version, 'k', internal, boundaries, location, file)


def write_epsilon(version, internal, boundaries, location=None, file=None):
    """ Write a TKE dissipation rate field file.

    See :func:`~dafi.random_field.foam_utilities.write` for more
    information.
    """
    return write(version, 'epsilon', internal, boundaries, location, file)


def write_omega(version, internal, boundaries, location=None, file=None):
    """ Write a TKE specific dissipation rate field file.

    See :func:`~dafi.random_field.foam_utilities.write` for more
    information.
    """
    return write(version, 'omega', internal, boundaries, location, file)
