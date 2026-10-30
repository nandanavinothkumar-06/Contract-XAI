import pandas as pd
from typing import Dict, Tuple

def check_leakage(train: pd.DataFrame, val: pd.DataFrame, test: pd.DataFrame, group_col: str, text_col: str) -> Tuple[bool, Dict]:
    """Checks for data leakage across splits."""
    leakage_details = {}
    
    train_groups = set(train[group_col].dropna().unique()) if not train.empty else set()
    val_groups = set(val[group_col].dropna().unique()) if not val.empty else set()
    test_groups = set(test[group_col].dropna().unique()) if not test.empty else set()
    
    val_leakage = train_groups.intersection(val_groups)
    test_leakage = train_groups.intersection(test_groups)
    val_test_leakage = val_groups.intersection(test_groups)
    
    train_texts = set(train[text_col].dropna().unique()) if not train.empty else set()
    val_texts = set(val[text_col].dropna().unique()) if not val.empty else set()
    test_texts = set(test[text_col].dropna().unique()) if not test.empty else set()
    
    val_text_leakage = train_texts.intersection(val_texts)
    test_text_leakage = train_texts.intersection(test_texts)
    val_test_text_leakage = val_texts.intersection(test_texts)
    
    has_leakage = False
    
    if val_leakage:
        has_leakage = True
        leakage_details['train_val_leak'] = list(val_leakage)
        
    if test_leakage:
        has_leakage = True
        leakage_details['train_test_leak'] = list(test_leakage)
        
    if val_test_leakage:
        has_leakage = True
        leakage_details['val_test_leak'] = list(val_test_leakage)
        
    if val_text_leakage:
        has_leakage = True
        leakage_details['train_val_text_overlap'] = list(val_text_leakage)
        
    if test_text_leakage:
        has_leakage = True
        leakage_details['train_test_text_overlap'] = list(test_text_leakage)
        
    if val_test_text_leakage:
        has_leakage = True
        leakage_details['val_test_text_overlap'] = list(val_test_text_leakage)
        
    return has_leakage, leakage_details
