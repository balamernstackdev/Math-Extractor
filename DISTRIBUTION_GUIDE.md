# How to Build and Share "Math Extractor"

I have renamed the application to **Math Extractor.exe**. Follow these steps to build and share it with your team.

## 1. Build the Application
Double-click the `build_release.bat` file in your project folder.

This script will:
1.  Build the standalone `Math Extractor.exe` using PyInstaller.
2.  Package it into an installer (`MathExtractorInstaller.exe`) using Inno Setup.

> **Note:** The build process may take a few minutes. Wait for the "SUCCESS!" message.

## 2. Locate the Files to Share
Once the build finishes, you will have two options for sharing:

### Option A: Professional Installer (Recommended)
Navigate to:
`installer/Output/`

Share the file:
**`MathExtractorInstaller.exe`**

*   **Why:** This handles everything for your team (creates shortcuts, installs required C++ runtimes, places files in Program Files).
*   **Best for:** Non-technical team members.

### Option B: Standalone EXE (Quick Share)
Navigate to:
`dist/`

Share the file:
**`Math Extractor.exe`**

*   **Why:** Good for quick testing without installing.
*   **Warning:** Might fail if their computer lacks specific C++ libraries (though the installer handles this).

## 3. How to Update
If you make code changes, just run `build_release.bat` again. The old files will be cleaned up and new ones created automatically.
