"""Read-only extraction of the existing Asset cleaning function; synthetic input only."""
import ast
import json
import sys
from pathlib import Path
from unittest.mock import patch
import pandas as pd

root = Path(__file__).resolve().parents[2]
tree = ast.parse((root / 'app.py').read_text(encoding='utf-8'))
names = {'load_and_clean_asset_data', 'find_year_end_comparison_date'}
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
for node in functions:
    node.decorator_list = []
module = ast.Module(body=functions, type_ignores=[])
class Status:
    def error(self, text):
        raise RuntimeError(text)
namespace = {'pd': pd, 'st': Status()}
exec(compile(ast.fix_missing_locations(module), 'app.py (read-only functions)', 'exec'), namespace)
source = json.load(sys.stdin)
def read_synthetic(*args, sheet_name, **kwargs):
    frame = pd.DataFrame(source['sheets'][sheet_name])
    # Explicit float fixture columns isolate arithmetic parity from pandas 3 integer upcast restrictions.
    if sheet_name == 'Asset':
        frame = frame.astype({'Balance': 'float64', 'BalanceInMYR': 'float64', 'InterestRate': 'float64'})
    return frame
with patch.object(pd, 'read_excel', side_effect=read_synthetic):
    rows, corrections = namespace['load_and_clean_asset_data']('synthetic-only.xlsx')
date = max(rows['ReportingDate'])
snapshot = rows[rows['ReportingDate'] == date]
interest = snapshot[snapshot['InterestRate'] > 0]
output = {
    'total': float(snapshot['BalanceInMYR'].sum()),
    'yield': float((interest['BalanceInMYR'] * interest['InterestRate']).sum() / interest['BalanceInMYR'].sum()),
    'liquid': float(snapshot[snapshot['CashLiquidity'].isin(['Very High', 'High'])]['BalanceInMYR'].sum()),
    'converted': rows['BalanceInMYR'].tolist(),
    'corrections': len(corrections),
}
json.dump(output, sys.stdout)
