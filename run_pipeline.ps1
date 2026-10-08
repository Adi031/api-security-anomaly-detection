Write-Host "Resetting DB..."
python init_sqlite.py

Write-Host "Running normal traffic (120s)..."
python traffic-simulator/simulator.py --users 200 --duration 120

Write-Host "Running massive attacks..."
python generate_attacks.py

Write-Host "Running experiments (5 seeds)..."
python run_experiments.py

Write-Host "Done!"
