"""Compile and execute the firmware's production logic on the host."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    binary = str(Path(directory) / "test_gateway")
    subprocess.run(["g++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                    "-I", str(root / "firmware/include"),
                    str(root / "firmware/test/test_core.cpp"), "-o", binary], check=True)
    subprocess.run([binary], check=True)
