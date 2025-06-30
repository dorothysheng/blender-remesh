# Blender CLI Remesh Tool

A command-line tool for remeshing and reducing triangles in 3D models using Blender.

Remesh and reduce triangles in 3D models to make smaller files by calling blender's built-in modifiers from command line with optimized strategy.

![Blender CLI Remesh Tool](readme_screenshots/blender%20cli%20remesh%20tool.png)

## Setup

1. **Install Blender**  
   Get it from [blender.org](https://www.blender.org/download/)

## How To Use

1. Put .obj files in `input/` folder
2. Open command line
3. Run this command:

   **Default (50% reduction):**
   ```bash
   blender --background --python remesh.py
   ```

   **Custom reduction:**
   ```bash
   # 30% reduction
   blender --background --python remesh.py --reduction 0.3
   
   # 70% reduction
   blender --background --python remesh.py -r 0.7
   ```

   **If blender is not in your PATH:**
   ```bash
   "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python remesh.py --reduction 0.3
   ```

4. Check `output/` folder for results

## Parameters

- `--reduction` or `-r`: How much to reduce (0.0 to 1.0)
  - `0.3` = 30% reduction
  - `0.5` = 50% reduction (default)

## Input/Output

- **Input**: .obj files in `input/` folder
- **Output**: Files with `_remeshed_50p.obj` suffix in `output/` folder

## Requirements

- Blender 4.4+
- .obj files with 3D models