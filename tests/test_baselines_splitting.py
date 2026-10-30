import pandas as pd
from src.baselines.splitting import group_aware_split
from src.baselines.leakage import check_leakage

def test_group_aware_split():
    df = pd.DataFrame({
        'text': ['A', 'B', 'C', 'D', 'E'],
        'label': [1, 0, 1, 0, 1],
        'group': ['G1', 'G1', 'G2', 'G3', 'G3']
    })
    
    train, val, test = group_aware_split(df, 'group', test_size=0.5, random_state=42)
    # Check no group leakage
    has_leakage, _ = check_leakage(train, val, test, 'group', 'text')
    assert not has_leakage

def test_leakage_detection():
    train = pd.DataFrame({'group': ['G1', 'G2'], 'text': ['A', 'B']})
    val = pd.DataFrame({'group': ['G2', 'G3'], 'text': ['B', 'C']})
    test = pd.DataFrame({'group': ['G4'], 'text': ['D']})
    
    has_leakage, details = check_leakage(train, val, test, 'group', 'text')
    assert has_leakage
    assert 'G2' in details['train_val_leak']
    
def test_text_leakage_detection_train_val():
    train = pd.DataFrame({'group': ['G1'], 'text': ['Hello World']})
    val = pd.DataFrame({'group': ['G2'], 'text': ['Hello World']})
    test = pd.DataFrame({'group': ['G3'], 'text': ['Something Else']})
    
    has_leakage, details = check_leakage(train, val, test, 'group', 'text')
    assert has_leakage
    assert 'Hello World' in details['train_val_text_overlap']

def test_text_leakage_detection_train_test():
    train = pd.DataFrame({'group': ['G1'], 'text': ['Hello World']})
    val = pd.DataFrame({'group': ['G2'], 'text': ['Something Else']})
    test = pd.DataFrame({'group': ['G3'], 'text': ['Hello World']})
    
    has_leakage, details = check_leakage(train, val, test, 'group', 'text')
    assert has_leakage
    assert 'Hello World' in details['train_test_text_overlap']
    
def test_text_leakage_detection_val_test():
    train = pd.DataFrame({'group': ['G1'], 'text': ['Unique']})
    val = pd.DataFrame({'group': ['G2'], 'text': ['Hello World']})
    test = pd.DataFrame({'group': ['G3'], 'text': ['Hello World']})
    
    has_leakage, details = check_leakage(train, val, test, 'group', 'text')
    assert has_leakage
    assert 'Hello World' in details['val_test_text_overlap']

def test_text_leakage_clean():
    train = pd.DataFrame({'group': ['G1'], 'text': ['Train Text']})
    val = pd.DataFrame({'group': ['G2'], 'text': ['Val Text']})
    test = pd.DataFrame({'group': ['G3'], 'text': ['Test Text']})
    
    has_leakage, details = check_leakage(train, val, test, 'group', 'text')
    assert not has_leakage
    
def test_official_split():
    df = pd.DataFrame({
        'text': ['A', 'B', 'C'],
        'label': [1, 0, 1],
        'group': ['G1', 'G2', 'G3'],
        'split': ['train', 'validation', 'test']
    })
    train, val, test = group_aware_split(df, 'group', test_size=0.5, random_state=42)
    assert len(train) == 1
    assert train.iloc[0]['text'] == 'A'
    assert len(val) == 1
    assert val.iloc[0]['text'] == 'B'
    assert len(test) == 1
    assert test.iloc[0]['text'] == 'C'
