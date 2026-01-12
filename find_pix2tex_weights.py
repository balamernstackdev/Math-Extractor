
try:
    from pix2tex.cli import LatexOCR
    import os
    
    print("Initializing LatexOCR...")
    model = LatexOCR()
    print(f"Checkpoint path: {model.args.checkpoint}")
    print(f"Config path: {model.args.config}")
    
    # Also check if the files exist
    if os.path.exists(model.args.checkpoint):
        print(f"FOUND CHECKPOINT: {os.path.abspath(model.args.checkpoint)}")
    else:
        print("Checkpoint file defined but NOT FOUND on disk.")
        
    if os.path.exists(model.args.config):
        print(f"FOUND CONFIG: {os.path.abspath(model.args.config)}")
        
except Exception as e:
    print(f"Error: {e}")
