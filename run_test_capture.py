"""
Quick verification - Read and display the test results
"""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "test_meeting_demo.py"],
    capture_output=True,
    text=True,
    cwd=r"D:\test-r&d\mathpix_clone"
)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nExit Code: {result.returncode}")
