#!/usr/bin/env python3
"""doit file"""
import csv
import json
import logging
import shlex
import typing
from dataclasses import dataclass
from pathlib import Path

import rhasspynlu
from doit import create_after

DOIT_CONFIG = {"action_string_formatting": "new"}

# Directory of this file
_DIR = Path(__file__).parent

_LOGGER = logging.getLogger("dodo")
logging.basicConfig(level=logging.DEBUG)

# -----------------------------------------------------------------------------

# Number of parallel jobs to run during transcription/recognition
JOBS = 10

# Directory containing git submodules for each dataset
datasets_dir = _DIR / "datasets"

# Directory where profile artifacts are downloaded and processed
profiles_dir = _DIR / "profiles"

# Directory where results should be stored for each condition.
results_dir = _DIR / "results"


@dataclass
class DatasetProfile:
    """Names and paths for a dataset profile."""

    dataset: str
    dataset_dir: Path
    profile: str
    in_profile_dir: Path
    out_profile_dir: Path
    results_dir: Path


# -----------------------------------------------------------------------------


def iter_profiles() -> typing.Iterable[DatasetProfile]:
    """Yield DatasetProfile object for each dataset profile."""
    for ds_dir in datasets_dir.glob("*"):
        if not ds_dir.is_dir():
            # Skip files
            continue

        dataset = ds_dir.name

        # Descend into each profile directory
        ds_profiles_dir = ds_dir / "profiles"
        for ds_profile_dir in ds_profiles_dir.glob("*"):
            if not ds_profile_dir.is_dir():
                # Skip files
                continue

            profile = ds_profile_dir.name
            out_profile_dir = profiles_dir / dataset / profile
            profile_results_dir = results_dir / profile

            yield DatasetProfile(
                dataset=dataset,
                dataset_dir=ds_dir,
                profile=profile,
                in_profile_dir=ds_profile_dir,
                out_profile_dir=out_profile_dir,
                results_dir=profile_results_dir,
            )


_PROFILES = list(iter_profiles())

# -----------------------------------------------------------------------------


def task_download_profiles():
    """Downloads missing files for all dataset profiles."""
    download_files = _DIR / "scripts" / "download-files.sh"

    for p in _PROFILES:
        p.out_profile_dir.mkdir(parents=True, exist_ok=True)

        # Check for user-provided "print-downloads" script
        print_downloads = maybe_user_bin(
            p.in_profile_dir,
            "print-downloads",
            "--profile",
            shlex.quote(str(p.out_profile_dir)),
        )

        # Download task
        yield {
            "name": f"{p.dataset}_{p.profile}_download",
            "targets": [p.out_profile_dir / "print-downloads.txt"],
            "actions": [f"{print_downloads} | '{download_files}' > {{targets}}"],
        }


@create_after(executed="download_profiles")
def task_copy_profiles():
    """Copy user-provided profile artifacts to profile directories."""
    for p in _PROFILES:
        p.out_profile_dir.mkdir(parents=True, exist_ok=True)

        yield {
            "name": f"{p.dataset}_{p.profile}_copy",
            "file_dep": [f for f in p.in_profile_dir.rglob("*") if f.is_file()],
            "actions": [f"rsync -aL '{p.in_profile_dir}/' '{p.out_profile_dir}/'"],
        }


@create_after(executed="copy_profiles")
def task_train_profiles():
    """Train all dataset profiles."""
    for p in _PROFILES:
        p.results_dir.mkdir(parents=True, exist_ok=True)

        file_dep = get_user_files(p.out_profile_dir)
        intent_gz = p.out_profile_dir / "intent.pickle.gz"
        train_results = p.results_dir / "train-profile.txt"

        train_profile = maybe_user_bin(
            p.in_profile_dir,
            "train-profile",
            "--profile",
            shlex.quote(str(p.out_profile_dir)),
            "--debug",
        )

        yield {
            "name": f"{p.dataset}_{p.profile}_train",
            "file_dep": file_dep,
            "targets": [intent_gz, train_results],
            "actions": [f"{train_profile} > '{train_results}'"],
        }


def task_transcribe():
    """Transcribes WAV files."""
    for p in _PROFILES:
        p.results_dir.mkdir(parents=True, exist_ok=True)

        # Generate list of WAV files to transcribe
        truth_jsonl = p.dataset_dir / "truth.jsonl"
        wav_list = p.out_profile_dir / "wavs.txt"

        yield {
            "name": f"{p.dataset}_{p.profile}_wav_list",
            "file_dep": [truth_jsonl],
            "targets": [wav_list],
            "actions": [
                "jq --raw-output .wav_name < {dependencies} | sort | uniq > {targets}"
            ],
        }

        # Transcribe WAV files in parallel
        transcriptions = p.results_dir / "transcriptions.jsonl"
        transcribe_wav = maybe_user_bin(
            p.in_profile_dir,
            "transcribe-wav",
            "--profile",
            shlex.quote(str(p.out_profile_dir)),
            "--",
            "--relative-directory",
            shlex.quote(str(p.dataset_dir)),
            "--stdin-files",
        )

        file_dep = get_user_files(p.out_profile_dir)

        yield {
            "name": f"{p.dataset}_{p.profile}_transcribe",
            "file_dep": file_dep,
            "targets": [transcriptions],
            "actions": [
                f"cd '{p.dataset_dir}'"
                + f" && cat '{wav_list}' | parallel -k --pipe -n {JOBS} {transcribe_wav} > {{targets}}"
            ],
        }


def task_recognize():
    """Recognizes intents from transcriptions."""
    for p in _PROFILES:
        p.results_dir.mkdir(parents=True, exist_ok=True)

        transcriptions = p.results_dir / "transcriptions.jsonl"
        intents = p.results_dir / "intents.jsonl"

        recognize_intent = maybe_user_bin(
            p.in_profile_dir,
            "recognize-intent",
            "--profile",
            shlex.quote(str(p.out_profile_dir)),
        )

        yield {
            "name": f"{p.dataset}_{p.profile}_recognize",
            "file_dep": [transcriptions],
            "targets": [intents],
            "actions": [
                f"cat {{dependencies}} | parallel -k --pipe -n {JOBS} {recognize_intent} > {{targets}}"
            ],
        }


def task_report():
    """Generate report with statistics."""
    for p in _PROFILES:
        p.results_dir.mkdir(parents=True, exist_ok=True)

        truth = p.dataset_dir / "truth.jsonl"
        intents = p.results_dir / "intents.jsonl"

        # Create JSON report
        report_json = p.results_dir / "report.json"

        yield {
            "name": f"{p.dataset}_{p.profile}_report_json",
            "file_dep": [truth, intents],
            "targets": [report_json],
            "actions": [
                f"voice2json -p '{p.out_profile_dir}' test-examples --expected '{truth}' --actual '{intents}' | jq . > {{targets}}"
            ],
        }

        # Convert report to HTML
        report_html = p.results_dir / "report.html"
        report_to_html = _DIR / "scripts" / "report-to-html.py"

        yield {
            "name": f"{p.dataset}_{p.profile}_report_html",
            "file_dep": [report_json],
            "targets": [report_html],
            "actions": [
                f"'{report_to_html}' --title '{p.dataset}_{p.profile}' < {{dependencies}} > {{targets}}"
            ],
        }


def task_summary():
    """Generate CSV summary file for all profiles."""
    results_dir.mkdir(parents=True, exist_ok=True)

    def make_summary(targets):
        """Writes summary CSV."""
        with open(targets[0], "w") as out_file:
            writer = csv.DictWriter(
                out_file,
                fieldnames=[
                    "dataset",
                    "profile",
                    "training_seconds",
                    "transcription_accuracy",
                    "intent_entity_accuracy",
                    "average_transcription_speedup",
                    "average_recognize_seconds",
                    "num_wavs",
                    "num_sentences",
                ],
            )

            writer.writeheader()

            for p in _PROFILES:
                sentences_ini = p.out_profile_dir / "sentences.ini"
                slots_dir = p.out_profile_dir / "slots"
                report_json = p.results_dir / "report.json"
                train_results = p.results_dir / "train-profile.txt"

                with open(report_json, "r") as report_file:
                    report = json.load(report_file)

                # Get training time
                training_time = ""
                with open(train_results, "r") as training_file:
                    for line in training_file:
                        line = line.strip().lower()
                        if line.startswith("training completed in"):
                            training_time = "{0:.02f}".format(float(line.split()[3]))

                # Get sentence count
                sentence_count = 0

                with open(sentences_ini, "r") as sentences_file:
                    intents = rhasspynlu.parse_ini(sentences_file)

                sentences, replacements = rhasspynlu.ini_jsgf.split_rules(intents)

                if slots_dir.is_dir():
                    slot_replacements = rhasspynlu.slots.get_slot_replacements(
                        intents, slots_dirs=[slots_dir]
                    )

                    # Merge with existing replacements
                    for slot_key, slot_values in slot_replacements.items():
                        replacements[slot_key] = slot_values

                # Calculate number of possible sentences per intent
                intent_counts = rhasspynlu.ini_jsgf.get_intent_counts(
                    sentences, replacements, exclude_slots=False
                )

                sentence_count = sum(intent_counts.values())

                # Calculate average recognition time
                recognize_seconds = []
                for actual_value in report["actual"].values():
                    recognize_seconds.append(actual_value["recognize_seconds"])

                # Write CSV row
                writer.writerow(
                    {
                        "dataset": p.dataset,
                        "profile": p.profile,
                        "training_seconds": training_time,
                        "transcription_accuracy": "{0:.02f}".format(
                            report["transcription_accuracy"]
                        ),
                        "intent_entity_accuracy": "{0:.02f}".format(
                            report["intent_entity_accuracy"]
                        ),
                        "average_transcription_speedup": "{0:.02f}".format(
                            report["average_transcription_speedup"]
                        ),
                        "num_wavs": report["num_wavs"],
                        "num_sentences": sentence_count,
                        "average_recognize_seconds": sum(recognize_seconds)
                        / len(recognize_seconds),
                    }
                )

    # Create summary task
    file_dep: typing.List[Path] = []
    summary_csv = results_dir / "summary.csv"

    for p in _PROFILES:
        sentences_ini = p.out_profile_dir / "sentences.ini"
        report_json = p.results_dir / "report.json"
        train_results = p.results_dir / "train-profile.txt"

        file_dep.extend([sentences_ini, train_results, report_json])

        # Add slots
        slots_dir = p.out_profile_dir / "slots"
        if slots_dir.is_dir():
            file_dep.extend([f for f in slots_dir.rglob("*") if f.is_file()])

    yield {
        "name": "summary_csv",
        "file_dep": file_dep,
        "targets": [summary_csv],
        "actions": [(make_summary)],
    }


# -----------------------------------------------------------------------------


def get_user_files(out_profile_dir: Path) -> typing.List[Path]:
    """Get paths of all user-created profile files."""
    user_files = [out_profile_dir / "sentences.ini"]

    for user_dir_name in ["slots", "slot_programs", "converters"]:
        user_dir = out_profile_dir / user_dir_name
        if user_dir.is_dir():
            user_files.extend([f for f in user_dir.rglob("*") if f.is_file()])

    custom_words = out_profile_dir / "custom_words.txt"
    if custom_words.is_file():
        user_files.append(custom_words)

    return user_files


def maybe_user_bin(in_profile_dir: Path, command_name: str, *args) -> str:
    """Check for user-provided bin for voice2json commmand."""
    command = []

    command_bin = in_profile_dir / "bin" / command_name
    if command_bin.is_file():
        command.append(str(command_bin))
        command.extend(args)
    else:
        command.append("voice2json")

        # Split args based on --
        before_args = []
        after_args = []
        before = True
        for arg in args:
            if arg == "--":
                before = False
            elif before:
                before_args.append(arg)
            else:
                after_args.append(arg)

        command.extend(before_args)
        command.append(command_name)
        command.extend(after_args)

    return " ".join(command)
