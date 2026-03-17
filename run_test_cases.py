from __future__ import annotations

import subprocess
from pathlib import Path


def normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    lines = [line for line in lines if line != ""]
    return "\n".join(lines)


def cap_output_lines(text: str, max_lines: int = 70) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    kept = lines[:max_lines]
    kept.append(f"... [truncated: showing first {max_lines} of {len(lines)} lines]")
    return "\n".join(kept) + "\n"


CASES: list[dict] = [
    {"file": "T01_simple_math.txt", "mode": "exact", "expected": "14"},
    {"file": "T02_math_parentheses.txt", "mode": "exact", "expected": "20"},
    {"file": "T03_float_promotion.txt", "mode": "exact", "expected": "7.5\n3.5"},
    {"file": "T04_complex_math_func_array.txt", "mode": "exact", "expected": "9"},
    {
        "file": "T05_simple_boolean_relops.txt",
        "mode": "exact",
        "expected": "True\nFalse\nTrue\nFalse\nTrue",
    },
    {"file": "T06_complex_boolean.txt", "mode": "exact", "expected": "True\nTrue\nFalse"},
    {"file": "T07_nested_complex_logical.txt", "mode": "exact", "expected": "False"},
    {"file": "T08_for_loop_sum.txt", "mode": "exact", "expected": "15"},
    {"file": "T09_while_loop.txt", "mode": "exact", "expected": "3\n2\n1"},
    {"file": "T10_repeat_until.txt", "mode": "exact", "expected": "0\n1\n2"},
    {"file": "T11_record_field_access.txt", "mode": "exact", "expected": "21\n99.5"},
    {"file": "T12_multi_dim_array.txt", "mode": "exact", "expected": "6"},
    {"file": "T13_casts_valid.txt", "mode": "exact", "expected": "123\n10.0\nTrue\n6"},
    {"file": "T14_function_return_array_valid.txt", "mode": "exact", "expected": "7\n8"},
    {"file": "T15_scan_input.txt", "mode": "exact", "expected": "Hello!!!"},
    {
        "file": "T16_void_function.txt",
        "mode": "exact",
        "expected": "3\n3",
    },
    {"file": "T17_function_calling_function.txt", "mode": "exact", "expected": "5"},
    {
        "file": "T18_function_multiple_calls.txt",
        "mode": "exact",
        "expected": "2\n3\n4",
    },
    {"file": "T19_recursion_factorial.txt", "mode": "exact", "expected": "120"},
    {
        "file": "T20_scope_assignment_persistence.txt",
        "mode": "exact",
        "expected": "2",
    },
    {
        "file": "E01_wrong_param_count.txt",
        "mode": "contains",
        "expected": ["INCORRECT-PARAMETER-COUNT ERROR"],
    },
    {
        "file": "E02_wrong_param_type.txt",
        "mode": "contains",
        "expected": ["INCORRECT-PARAMETER-TYPE ERROR"],
    },
    {
        "file": "E03_return_in_main.txt",
        "mode": "contains",
        "expected": ["MISPLACED-RETURN ERROR"],
    },
    {
        "file": "E04_non_void_missing_return.txt",
        "mode": "contains",
        "expected": ["NON-EXHAUSTIVE-RETURNS ERROR"],
    },
    {
        "file": "E05_const_reassign.txt",
        "mode": "contains",
        "expected": ["CONSTANT-RE-ASSIGNMENT ERROR"],
    },
    {
        "file": "E06_mutable_constant_array.txt",
        "mode": "contains",
        "expected": ["MUTABLE-CONSTANT ERROR"],
    },
    {
        "file": "E07_undeclared_var.txt",
        "mode": "contains",
        "expected": ["NON-EXISTENT-NAME ERROR"],
    },
    {
        "file": "E08_undeclared_type.txt",
        "mode": "contains",
        "expected": ["NON-EXISTENT-NAME ERROR"],
    },
    {
        "file": "E09_array_index_non_int.txt",
        "mode": "contains",
        "expected": ["INVALID-INDEX-TYPE"],
    },
    {
        "file": "E10_assignment_type_mismatch.txt",
        "mode": "contains",
        "expected": ["TYPE-MISMATCH ERROR"],
    },
    {
        "file": "E11_invalid_condition_type.txt",
        "mode": "contains",
        "expected": ["INVALID-CONDITION ERROR"],
    },
    {
        "file": "E12_invalid_cast_target.txt",
        "mode": "contains",
        "expected": ["NON-EXISTENT-NAME ERROR"],
    },
    {
        "file": "E13_scan_non_string_target.txt",
        "mode": "contains",
        "expected": ["INCORRECT-PARAMETER-TYPE ERROR"],
    },
    {
        "file": "E14_recursive_record_direct.txt",
        "mode": "contains",
        "expected": ["RECURSIVE-TYPE-DEFINITION ERROR"],
    },
    {
        "file": "E15_array_write_oob_runtime.txt",
        "mode": "contains",
        "expected": ["Array index out of bounds"],
    },
    {
        "file": "E16_array_assignment_shape_mismatch_runtime.txt",
        "mode": "contains",
        "expected": ["Array assignment shape mismatch"],
    },
    {
        "file": "E17_array_return_shape_mismatch_runtime.txt",
        "mode": "contains",
        "expected": ['Invalid array return in "bad"'],
    },
    {
        "file": "E18_multiple_defined_variable.txt",
        "mode": "contains",
        "expected": ['NAME-COLLISION ERROR'],
    },
]


TEST_DIR = Path("input/test_cases")
REPORT_PATH = Path("output/test_cases_report.txt")
RAW_DIR = Path("output/test_cases_actual")
TIMEOUT_SECONDS = 15.0
MAX_ACTUAL_LINES = 70


def main() -> int:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    total = len(CASES)

    for idx, case in enumerate(CASES, start=1):
        filename = case["file"]
        test_path = TEST_DIR / filename

        # some test cases require input; provide it if needed
        input_data = "Hello" if filename == "T15_scan_input.txt" else None

        print(f"[{idx}/{total}] Running {filename} ...")
        timed_out = False
        try:
            proc = subprocess.run(
                ["python", "main.py", str(test_path)],
                input=input_data,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=TIMEOUT_SECONDS,
            )
            actual_raw = (proc.stdout or "") + (proc.stderr or "")
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            actual_raw = (
                f"[TIMEOUT] Exceeded {TIMEOUT_SECONDS} seconds. Process terminated.\n"
                + stdout
                + stderr
            )
            exit_code = -999
        actual_capped = cap_output_lines(actual_raw, MAX_ACTUAL_LINES)
        (RAW_DIR / f"{Path(filename).stem}.actual.txt").write_text(actual_capped, encoding="utf-8")

        lines.append("=" * 50)
        lines.append(f"Test: {filename}")
        lines.append(f"ExitCode: {exit_code}")
        if timed_out:
            lines.append(f"TimedOut: True (>{TIMEOUT_SECONDS}s)")
        lines.append("Expected:")
        if case["mode"] == "exact":
            lines.append(case["expected"])
        else:
            for needle in case["expected"]:
                lines.append(f" - {needle}")
        lines.append("Actual:")
        lines.append(normalize_text(actual_capped))

    lines.append("=" * 50)
    lines.append(f"Finished {total} test case(s).")

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote report to {REPORT_PATH}")
    print(f"Wrote raw outputs to {RAW_DIR}")
    print(f"Finished {total} test case(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
