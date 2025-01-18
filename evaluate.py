import json
import pandas as pd
from pathlib import Path
from typing import List, Set, Dict
from src.validator import ICD10Validator


def load_json_file(filepath: Path) -> dict:
    """Load and parse a JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def load_text_file(filepath: Path) -> str:
    """Load a text file."""
    with open(filepath, "r") as f:
        return f.read()


def compute_jaccard_similarity(set1: Set[str], set2: Set[str]) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set1 and not set2:  # If both sets are empty
        return 1.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0


def analyze_predictions(validator: ICD10Validator) -> List[Dict]:
    """
    Analyze predictions against ground truth outputs and validate ICD-10 codes.

    Returns:
        List of dictionaries containing analysis results for each file pair.
    """
    base_dir = Path("test_data")
    input_dir = base_dir / "inputs"
    output_dir = base_dir / "outputs"
    pred_dir = base_dir / "preds"

    results = []

    # Get all prediction files
    pred_files = sorted(pred_dir.glob("pred*.json"))

    for pred_file in pred_files:
        # Get corresponding input and output files
        file_num = pred_file.stem.replace("pred", "")
        input_file = input_dir / f"input{file_num}.txt"
        output_file = output_dir / f"output{file_num}.json"

        if not output_file.exists() or not input_file.exists():
            print(f"Warning: Missing corresponding files for {pred_file.name}")
            continue

        # Load all files
        note_text = load_text_file(input_file)
        pred_data = load_json_file(pred_file)["icd10_codes"]
        output_data = load_json_file(output_file)["icd10_codes"]

        # Extract code sets and their details
        pred_codes = set([x["code"] for x in pred_data])
        output_codes = set([x["code"] for x in output_data])

        # Compute sets for analysis
        pred_only = pred_codes - output_codes
        output_only = output_codes - pred_codes
        common_codes = pred_codes.intersection(output_codes)

        # Validate codes
        invalid_pred_codes = {
            code for code in pred_codes if not validator.check_code_validity(code)
        }
        invalid_output_codes = {
            code for code in output_codes if not validator.check_code_validity(code)
        }

        # Check billable status for valid codes
        non_billable_pred = {
            code
            for code in pred_codes - invalid_pred_codes
            if not validator.check_code_billable(code)
        }
        non_billable_output = {
            code
            for code in output_codes - invalid_output_codes
            if not validator.check_code_billable(code)
        }

        # Get details for mismatched codes
        pred_only_details = [x for x in pred_data if x["code"] in pred_only]

        output_only_details = [x for x in output_data if x["code"] in output_only]

        # Compute Jaccard similarity
        jaccard_sim = compute_jaccard_similarity(pred_codes, output_codes)

        # Compile results
        result = {
            "file_pair": f"{pred_file.name} - {output_file.name}",
            "note_text": note_text,
            "jaccard_similarity": jaccard_sim,
            "common_codes": list(common_codes),
            "codes_in_pred_only": pred_only_details,
            "codes_in_output_only": output_only_details,
            "invalid_codes": {
                "pred": list(invalid_pred_codes),
                "output": list(invalid_output_codes),
            },
            "non_billable_codes": {
                "pred": list(non_billable_pred),
                "output": list(non_billable_output),
            },
        }

        results.append(result)

    return results


def main():
    # Load ICD10 validator
    icd10_data = pd.read_csv("icd10_data/icd10_all_codes.tsv", delimiter="\t")[
        ["code", "description", "is_billable"]
    ].to_dict(orient="records")
    validator = ICD10Validator(icd10_data)

    # Run analysis
    results = analyze_predictions(validator)

    # Save results
    output_path = Path("analysis_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Analysis complete. Results saved to {output_path}")

    # Print summary statistics
    total_pairs = len(results)
    avg_jaccard = sum(r["jaccard_similarity"] for r in results) / total_pairs
    print(f"\nSummary:")
    print(f"Total file pairs analyzed: {total_pairs}")
    print(f"Average Jaccard similarity: {avg_jaccard:.3f}")


if __name__ == "__main__":
    main()
