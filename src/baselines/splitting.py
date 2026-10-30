"""Group-aware deterministic splitting."""
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from typing import Tuple, List

def group_aware_split(
    df: pd.DataFrame, 
    group_col: str, 
    test_size: float = 0.2, 
    val_size: float = 0.0, 
    random_state: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Splits dataframe into train, val, test, ensuring groups are not leaked."""
    
    # If the dataset explicitly specifies an official split, use it!
    if 'split' in df.columns:
        train = df[df['split'] == 'train']
        val = df[df['split'] == 'validation']
        test = df[df['split'] == 'test']
        return train, val, test

    gss_test = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    
    groups = df[group_col]
    train_val_idx, test_idx = next(gss_test.split(df, groups=groups))
    
    train_val = df.iloc[train_val_idx]
    test = df.iloc[test_idx]
    
    if val_size > 0:
        # Calculate proportional val_size relative to train_val
        prop_val_size = val_size / (1.0 - test_size)
        gss_val = GroupShuffleSplit(n_splits=1, test_size=prop_val_size, random_state=random_state)
        tv_groups = train_val[group_col]
        train_idx, val_idx = next(gss_val.split(train_val, groups=tv_groups))
        
        train = train_val.iloc[train_idx]
        val = train_val.iloc[val_idx]
    else:
        train = train_val
        val = pd.DataFrame(columns=df.columns)
        
    return train, val, test
