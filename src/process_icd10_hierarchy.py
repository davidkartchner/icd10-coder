import xml.etree.ElementTree as ET
from .utils import write_json


def process_diagnostic_code(diag_elem):
    # Skip empty diagnostic elements
    code = diag_elem.find("name").text
    desc = diag_elem.find("desc").text
    if not code or not desc:
        print("early exit")
        return None

    code = diag_elem.find("name").text
    desc = diag_elem.find("desc").text

    # Extract includes and inclusionTerms
    includes = []

    # Get regular includes
    includes_elem = diag_elem.find("includes")
    if includes_elem is not None:
        includes.extend(extract_notes(includes_elem, ["note"]) or [])

    # Get inclusion terms
    inclusion_terms = extract_notes(diag_elem, ["inclusionTerm"])
    if inclusion_terms:
        includes.extend(inclusion_terms)

    # Extract excludes1
    excludes1_elem = diag_elem.find("excludes1")
    excludes_1 = extract_notes(excludes1_elem, ["note"])

    # Extract excludes2
    excludes2_elem = diag_elem.find("excludes2")
    excludes_2 = extract_notes(excludes2_elem, ["note"])

    result = {"code": code, "desc": desc}

    if includes:
        result["includes"] = includes
    if excludes_1:
        result["excludes_1"] = excludes_1
    if excludes_2:
        result["excludes_2"] = excludes_2

    return result


def extract_notes(element, note_types):
    # Find all notes within the given element and note_types
    notes = []
    if element is not None:
        # Handle multiple types of note elements
        for note_type in note_types:
            for note_elem in element.findall(f".//{note_type}/note"):
                if note_elem.text:
                    notes.append(note_elem.text)
    return notes if notes else None


def process_element(element):
    codes = []
    if element.tag == "diag":
        code_data = process_diagnostic_code(element)
        # print(code_data)
        if code_data:
            codes.append(code_data)

    # Process all child diag elements
    for child in element.findall(".//diag"):
        # print(child)
        codes.extend(process_element(child))

    return codes


def parse_icd10_xml(xml_string):
    root = ET.fromstring(xml_string)
    codes = []

    def process_element(element):
        if element.tag == "diag":
            code_data = process_diagnostic_code(element)
            if code_data:
                codes.append(code_data)

            # Process immediate child diag elements
            for child in element.findall(
                "./diag"
            ):  # Note: changed from .//diag to ./diag
                process_element(child)  # Recursively process each child
        else:
            # For non-diag elements, just recurse into their children
            for child in element:
                process_element(child)

    # Start processing from the root
    process_element(root)

    return codes

def alternative_parser(xml_content):
    root = ET.fromstring(xml_content)

    process_element(root)

    my_codes = []

    for node in root.findall('.//diag'):
        my_codes.append(process_diagnostic_code(node))

    return my_codes


# Example usage:
def main():
    with open("icd10cm_tabular_2025.xml", "r", encoding="utf-8") as file:
        xml_content = file.read()

    codes = parse_icd10_xml(xml_content)
    return codes


if __name__ == "__main__":
    codes = main()
    write_json(codes, "icd10_data_files/icd10_codes_with_metadata.json")
