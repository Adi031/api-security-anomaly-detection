import os
import subprocess
import json
import numpy as np

def run_cmd(cmd):
    subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL)

seeds = [42, 123, 456, 789, 999]
results = {'dense': {'precision': [], 'recall': [], 'auc': []}, 
           'lstm': {'precision': [], 'recall': [], 'auc': []}}

# We need a way to pass the seed to the scripts.
# Since we hardcoded `random.seed(42)` in the scripts, we can either patch them on the fly, 
# or just let the user know this script patches them.

for seed in seeds:
    print(f"Running iteration with seed {seed}...")
    
    # Patch the scripts with the current seed
    for script in ['ml-pipeline/features/feature_builder.py', 'ml-pipeline/features/sequence_builder.py', 'ml-pipeline/training/train_dense_ae.py', 'ml-pipeline/training/train_lstm_ae.py']:
        with open(script, 'r', encoding='utf-8') as f:
            content = f.read()
        import re
        content = re.sub(r'random\.seed\(\d+\)', f'random.seed({seed})', content)
        content = re.sub(r'np\.random\.seed\(\d+\)', f'np.random.seed({seed})', content)
        content = re.sub(r'torch\.manual_seed\(\d+\)', f'torch.manual_seed({seed})', content)
        with open(script, 'w', encoding='utf-8') as f:
            f.write(content)
            
    run_cmd('python ml-pipeline/features/feature_builder.py')
    run_cmd('python ml-pipeline/features/sequence_builder.py')
    run_cmd('python ml-pipeline/training/train_dense_ae.py')
    run_cmd('python ml-pipeline/training/train_lstm_ae.py')
    run_cmd('python ml-pipeline/training/evaluate.py')
    run_cmd('python ml-pipeline/training/evaluate.py --model lstm_ae --threshold-path ml-pipeline/saved_models/lstm_threshold.json')
    
    for model in ['dense_ae', 'lstm_ae']:
        with open(f'ml-pipeline/saved_models/evaluation/{model}_results.json', 'r') as f:
            res = json.load(f)
            key = 'dense' if 'dense' in model else 'lstm'
            results[key]['precision'].append(res['precision'])
            results[key]['recall'].append(res['recall'])
            results[key]['auc'].append(res['auc_roc'])

print("\n" + "="*50)
print("EXPERIMENT RESULTS (5 SEEDS)")
print("="*50)
for model in ['dense', 'lstm']:
    print(f"\n{model.upper()} MODEL:")
    for metric in ['precision', 'recall', 'auc']:
        vals = results[model][metric]
        print(f"  {metric.capitalize()}: {np.mean(vals):.4f} ± {np.std(vals):.4f}")
print("="*50)
