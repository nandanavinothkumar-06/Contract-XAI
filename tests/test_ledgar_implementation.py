import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

import src.models.run_task019_experiments as task019
import src.models.run_task019_experiments as task019

@patch('src.models.run_task019_experiments.get_ledgar_data')
@patch('src.models.run_task019_experiments.prepare_trainer')
def test_run_ledgar_validates_sizes(mock_prepare, mock_get_data):
    mock_get_data.return_value = pd.DataFrame([
        {"split": "train", "text": "A", "labels": ["L1"]}
    ])
    
    with pytest.raises(AssertionError) as exc:
        task019.run_ledgar()
        
    assert "Expected 12608 labels" in str(exc.value)

@patch('src.models.run_task019_experiments.get_ledgar_data')
def test_run_ledgar_full_mocked(mock_get_data):
    pass
