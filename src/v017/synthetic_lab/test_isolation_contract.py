from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
LAB = ROOT / "src/v017/synthetic_lab"


def main():
    files = sorted(
        p.relative_to(ROOT).as_posix()
        for p in LAB.glob("*.py")
    )

    print("lab files:")
    for path in files:
        print(" ", path)

    required = {
        "src/v017/synthetic_lab/__init__.py",
        "src/v017/synthetic_lab/scenario.py",
        "src/v017/synthetic_lab/frame_source.py",
        "src/v017/synthetic_lab/progression.py",
        "src/v017/synthetic_lab/test_frame_source.py",
        "src/v017/synthetic_lab/test_isolation_contract.py",
    }

    assert required.issubset(set(files))

    print()
    print("SYNTHETIC LAB ISOLATION CONTRACT: PASS")


if __name__ == "__main__":
    main()
