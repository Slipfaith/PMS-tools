import importlib

def test_imports():
    # Ensure main modules import without errors
    for module in ['controller', 'core.converters.excel_converter']:
        importlib.import_module(module)
