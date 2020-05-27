# voice2json Evaluation

Automated system for evaluating [voice2json](https://voice2json.org) on a dataset of WAV files with ground truth transcriptions and intents.

## Dataset Format

Datasets are stored in the `datasets` directory with the following structure:

* `datasets/`
    * `<dataset name>/`
        * `profiles/`
            * `<profile name>/`
                * `bin/`
                    * Scripts to override voice2json commands (`print-downloads`, `train-profile`, `transcribe-wav`, and `recognize-intent`)
                    * Arguments are separated by `--` with preceeding arguments for `voice2json` and succeeding arguments for the command
        * `wav/`
            * Directory with WAV files to transcribe
            * Should match `wav_name` in `truth.jsonl` (e.g., `wav/XXXX.wav`)
        * `truth.jsonl`
            * [jsonl](http://jsonlines.org/) file with one line per WAV file (ground truth)
            * Format from [`recognize-intent`](https://voice2json.org/commands.html#recognize-intent)
            * `wav_name` key should be WAV path relative to dataset directory (e.g., `wav/XXXX.wav`)

## Running

To get started:

```bash
$ git clone https://github.com/synesthesiam/voice2json-evaluate
$ cd voice2json-evaluate
$ make
```

After the virtual environment is created:

```bash
$ make run
```

When finished, check the `results` directory for a CSV summary file and reports for each profile. See the `profiles` directory for all downloaded and generated artifacts.

The evaluation is done using [doit](https://pydoit.org/), so re-running `make run` after adding a new dataset or changing relevant files should only re-compute what's necessary. If you get stuck or want to start fresh, run `make clean` or delete the `.doit.db` file.
