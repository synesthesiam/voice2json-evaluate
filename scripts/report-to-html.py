#!/usr/bin/env python3
"""Convert voice2json JSON report to HTML."""
import sys
import json
import argparse
from datetime import datetime

from yattag import Doc, indent

# -----------------------------------------------------------------------------


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(prog="report2html.py")
    parser.add_argument("--title", default="Report")
    parser.add_argument("--sub-title")
    args, _ = parser.parse_known_args()

    # -------------------------------------------------------------------------

    title = args.title
    if args.sub_title:
        title = f"{title} ({args.sub_title})"

    results = json.load(sys.stdin)
    stats = results

    expected = results["expected"]
    actual = results["actual"]

    # -------------------------------------------------------------------------

    doc, tag, text = Doc().tagtext()
    doc.asis("<!DOCTYPE html>")

    with tag("html"):
        with tag("head"):
            with tag("title"):
                text(title)

            with tag("style", type="text/css"):
                doc.asis(css())

        with tag("body"):
            with tag("h1"):
                text(title)

            with tag("p"):
                text(f"Date: {datetime.now()}%")

            with tag("p"):
                text(
                    f"Intent/Entity Accuracy: {stats['intent_entity_accuracy']*100:.2f}%"
                )

            with tag("p"):
                text(f"Intent Accuracy: {stats['intent_accuracy']*100:.2f}%")

            with tag("p"):
                text(f"Entity Accuracy: {stats['entity_accuracy']*100:.2f}%")

            with tag("p"):
                text(
                    f"Transcription Accuracy: {stats['transcription_accuracy']*100:.2f}%"
                )

            with tag("p"):
                text(
                    f"Average Transcription Speed-Up: {stats['average_transcription_speedup']:.2f}x"
                )

            with tag("table", klass="pure-table pure-table-bordered"):
                with tag("thead"):
                    with tag("th"):
                        text("Key")

                    with tag("th"):
                        text("Intent")

                    with tag("th"):
                        text("Text")

                    with tag("th"):
                        text("Errors")

                with tag("tbody"):
                    for key, actual_intent in sorted(
                        actual.items(), key=lambda kv: sort_score(kv[1]), reverse=True
                    ):
                        expected_intent = expected[key]
                        expected_intent_name = expected_intent["intent"]["name"]
                        expected_entities = expected_intent.get("entities", [])

                        wer = actual_intent["word_error"]
                        num_errors = wer["errors"]
                        expected_text = " ".join(wer["reference"])

                        actual_intent_name = actual_intent["intent"]["name"]
                        actual_text = " ".join(wer["hypothesis"])
                        actual_entities = actual_intent.get("entities", [])

                        row_class = "match"
                        if actual_intent_name != expected_intent_name:
                            row_class = "error"

                        wrong_entities = actual_intent.get("wrong_entities", [])
                        missing_entities = actual_intent.get("missing_entities", [])
                        if len(wrong_entities) > 0 or len(missing_entities) > 0:
                            if actual_intent_name == expected_intent_name:
                                row_class = "warn"
                            else:
                                row_class = "error"

                        # Expected
                        with tag("tr"):
                            # Key
                            with tag("td"):
                                text(key)

                            # Intent
                            with tag("td"):
                                text(expected_intent_name)

                            # Text
                            with tag("td"):
                                with tag("tt"):
                                    text(expected_text)

                            # Errors
                            with tag("td"):
                                text("")

                        with tag("tr"):
                            # Key
                            with tag("td"):
                                doc.asis(
                                    "&#9733;" if actual_text == expected_text else ""
                                )

                            # Intent
                            with tag("td"):
                                text("")

                            # Text
                            with tag("td"):
                                with tag("tt"):
                                    text(entity_str(expected_entities))

                            # Errors
                            with tag("td"):
                                text("")

                        # Actual
                        with tag("tr", klass=row_class):
                            # Key
                            with tag("td"):
                                text(key)

                            # Intent
                            with tag("td"):
                                text(actual_intent_name)

                            # Text
                            with tag("td"):
                                with tag("tt"):
                                    text(actual_text)

                            # Errors
                            with tag("td"):
                                text(num_errors)

                        with tag("tr", klass=row_class):
                            # Key
                            with tag("td"):
                                text("")

                            # Intent
                            with tag("td"):
                                text("")

                            # Text
                            with tag("td"):
                                with tag("tt"):
                                    text(entity_str(actual_entities))

                            # Errors
                            with tag("td"):
                                text("")

                        # Empty row
                        with tag("tr", klazz="black"):
                            for i in range(4):
                                with tag("td"):
                                    text("")

        # Timestamp
        with tag("hr"):
            pass

        with tag("p"):
            text(str(datetime.now()))

    print(indent(doc.getvalue()))


# -----------------------------------------------------------------------------


def entity_str(entities):
    return ", ".join(
        f"{e['entity']} = {e['value']}"
        for e in sorted(entities, key=lambda ev: ev["entity"])
    )


def sort_score(intent):
    if intent["intent"]["name"] != intent["expected_intent_name"]:
        return 100

    return len(intent["wrong_entities"]) + len(["missing_entities"])


# -----------------------------------------------------------------------------


def css():
    return """
/*!
Pure v1.0.0
Copyright 2013 Yahoo!
Licensed under the BSD License.
https://github.com/yahoo/pure/blob/master/LICENSE.md
*/
.pure-table {
    /* Remove spacing between table cells (from Normalize.css) */
    border-collapse: collapse;
    border-spacing: 0;
    empty-cells: show;
    border: 1px solid #cbcbcb;
}

.pure-table caption {
    color: #000;
    font: italic 85%/1 arial, sans-serif;
    padding: 1em 0;
    text-align: center;
}

.pure-table td,
.pure-table th {
    border-left: 1px solid #cbcbcb;/*  inner column border */
    border-width: 0 0 0 1px;
    font-size: inherit;
    margin: 0;
    overflow: visible; /*to make ths where the title is really long work*/
    padding: 0.5em 1em; /* cell padding */
}

/* Consider removing this next declaration block, as it causes problems when
there's a rowspan on the first cell. Case added to the tests. issue#432 */
.pure-table td:first-child,
.pure-table th:first-child {
    border-left-width: 0;
}

.pure-table thead {
    background-color: #e0e0e0;
    color: #000;
    text-align: left;
    vertical-align: bottom;
}

/*
striping:
   even - #fff (white)
   odd  - #f2f2f2 (light gray)
*/
.pure-table td {
    background-color: transparent;
}
.pure-table-odd td {
    background-color: #f2f2f2;
}

/* nth-child selector for modern browsers */
.pure-table-striped tr:nth-child(2n-1) td {
    background-color: #f2f2f2;
}

/* BORDERED TABLES */
.pure-table-bordered td {
    border-bottom: 1px solid #cbcbcb;
}
.pure-table-bordered tbody > tr:last-child > td {
    border-bottom-width: 0;
}


/* HORIZONTAL BORDERED TABLES */

.pure-table-horizontal td,
.pure-table-horizontal th {
    border-width: 0 0 1px 0;
    border-bottom: 1px solid #cbcbcb;
}
.pure-table-horizontal tbody > tr:last-child > td {
    border-bottom-width: 0;
}

.match {
    background-color: #CFC;
}

.mismatch {
    background-color: #CFF;
}

.warn {
    background-color: #FFC;
}

.error {
    background-color: #FCC;
}

.highlight {
    background-color: #ACF;
}

.black {
    background-color: #000;
}
"""


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
