# Custom PyInstaller hook for pandas
# Note: This will show warnings about numba during build, but that's OK
# Filtering them out causes runtime errors because pandas code references them
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# Collect all pandas submodules (including _numba stubs)
hiddenimports = collect_submodules('pandas')

# Collect data files and binaries
datas = collect_data_files('pandas', include_py_files=False)
binaries = collect_dynamic_libs('pandas')
