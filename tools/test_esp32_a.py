"""Compile and execute the firmware's production logic on the host."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
json_include = root / "firmware/.pio/libdeps/esp32-a/ArduinoJson/src"
if not json_include.exists():
    raise SystemExit("Install firmware dependencies first: pio pkg install -d firmware")
with tempfile.TemporaryDirectory() as directory:
    for source in sorted((root / "firmware/test").glob("test_*.cpp")):
        binary = str(Path(directory) / source.stem)
        subprocess.run(["g++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                        "-I", str(root / "firmware/include"), "-I", str(json_include),
                        str(source), "-o", binary], check=True)
        subprocess.run([binary], check=True)
