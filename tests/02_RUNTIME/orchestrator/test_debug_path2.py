import sys
def test_paths():
    for i, p in enumerate(sys.path):
        print(f"  [{i}] {p}")
