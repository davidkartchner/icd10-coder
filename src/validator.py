from typing import List


class ICD10Validator:
    def __init__(self, codes: List[dict]):
        for code in codes:
            assert "is_billable" in code
            assert "description" in code
        self.codes = {x["code"]: x for x in codes}

    def check_code_validity(self, code):
        if code in self.codes:
            return True
        else:
            return False

    def check_code_billable(self, code):
        metadata = self.codes[code]
        return metadata["is_billable"]

    def get_description(self, code):
        return self.codes[code]["description"]

    def get_all_data(self, code):
        return self.codes[code]
