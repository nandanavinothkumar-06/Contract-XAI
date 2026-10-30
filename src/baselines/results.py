import json
import os
from datetime import datetime, timezone
from typing import Dict, Any

def save_experiment_result(result: Dict[str, Any], output_dir: str = "results/baselines", is_test_fixture: bool = False):
    """Saves structured experiment result."""
    if is_test_fixture:
        output_dir = "results/test_fixtures"
        
    os.makedirs(output_dir, exist_ok=True)
    
    exp_id = result.get("experiment_id", "unknown_exp")
    filepath = os.path.join(output_dir, f"{exp_id}.json")
    
    result['timestamp'] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
        
    # Append to global csv
    csv_path = os.path.join(output_dir, "baseline_results.csv")
    file_exists = os.path.isfile(csv_path)
    
    with open(csv_path, 'a', encoding='utf-8') as f:
        if not file_exists:
            f.write("experiment_id,dataset,task,model,status,macro_f1,micro_f1,timestamp\n")
            
        metrics = result.get("metrics", {})
        macro_f1 = metrics.get("macro_f1", "")
        micro_f1 = metrics.get("micro_f1", "")
        
        row = f"{exp_id},{result.get('dataset', '')},{result.get('task', '')},{result.get('model', '')},{result.get('status', '')},{macro_f1},{micro_f1},{result['timestamp']}\n"
        f.write(row)
