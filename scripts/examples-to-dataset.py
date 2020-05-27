#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path

import jsonlines


# -----------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(prog="examples-to-dataset.py")
    parser.add_argument(
        "examples_directory", help="Directory with WAV files and JSON intents"
    )
    parser.add_argument("output_file", help="jsonl output file")
    parser.add_argument(
        "--dataset-directory",
        default=os.getcwd(),
        help="Base directory of dataset (default: cwd)",
    )
    args = parser.parse_args()

    examples_dir = Path(args.examples_directory)
    dataset_dir = Path(args.dataset_directory)

    with open(args.output_file, "w") as output_file:
        with jsonlines.Writer(output_file) as out:
            for wav_path in examples_dir.glob("*.wav"):
                json_path = wav_path.with_suffix(".json")
                if not json_path.is_file():
                    continue

                wav_name = str(wav_path.relative_to(dataset_dir))

                with open(json_path, "r") as json_file:
                    intent = json.load(json_file)

                intent["wav_name"] = wav_name
                out.write(intent)


# -----------------------------------------------------------------------------


if __name__ == "__main__":
    main()
