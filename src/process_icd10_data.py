import pandas as pd
from .utils import write_json


def process_code(code):
    if len(code) > 3:
        code = code[:3] + "." + code[3:]
        return code
    else:
        return code


def read_code_line(line):
    # raw_code = line.strip().split()[0]
    raw_code = line[6:13].strip()
    # print(line[5:14])
    is_billable = line[14]
    short_desc = line[16:76]
    long_desc = line[77:]

    code = process_code(raw_code)
    # desc = ' '.join(line.split()[1:])
    return {
        "code": code,
        "short_desc": short_desc.strip(),
        "description": long_desc.strip(),
        "is_billable": int(is_billable.strip()),
    }


code_records = []
for line in open("icd10_data_files/icd10cm_order_2025.txt").readlines():
    code_records.append(read_code_line(line))

full_df = pd.DataFrame.from_records(code_records)
full_df["is_billable"] = full_df["is_billable"].astype(bool)
full_df.to_csv("icd10_data_files/icd10_all_codes.tsv", sep="\t", index=False)
write_json(
    full_df[["code", "description"]].set_index("code").to_dict()["description"],
    "icd10_data_files/icd10_all_codes.json",
)

df = full_df.query("is_billable == 1").reset_index(drop=True)
df.to_csv("icd10_data_files/icd10_billable_codes.tsv", sep="\t", index=False)
