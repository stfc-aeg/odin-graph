# odin-graph
## Adding datasets:

### 1. Using a config file
For each dataset add a json object (see `example_config.json`)

### 2. From another adapter
Use `add_dataset()` and `add_avg_dataset()` methods.   
Call `initialize_tree()` after all datasets are added.
