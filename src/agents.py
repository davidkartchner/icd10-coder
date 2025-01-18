import json
import os
from collections import defaultdict
from .schemas import (
    ExplainedOutput,
)
from openai import OpenAI
from .utils import setup_loggers, write_json

openai_api_key = os.getenv("OPENAI_API_KEY")


logger = setup_loggers()
client = OpenAI(api_key=openai_api_key)


def openai_structured_output(
    client: OpenAI,
    system_instructions: str,
    prompt: str,
    response_format,
    openai_params={},
):
    """
    Generate structured output using OpenAI's chat API.

    Args:
        client (OpenAI): OpenAI client instance.
        system_instructions (str): System-level instructions for the model.
        prompt (str): User input to process.
        response_format: Expected response format.
        openai_params (dict): Additional OpenAI API parameters.

    Returns:
        dict: Parsed JSON output from the API response.
    """
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": prompt},
        ],
        response_format=response_format,
        **openai_params,
    )
    output = json.loads(completion.choices[0].message.parsed.json())
    return output


class Agent:
    """
    Base class for agents responsible for specific tasks using OpenAI and ICD-10 validation.

    Attributes:
        role (str): The agent's role.
        responsibilities (str): Description of the agent's responsibilities.
        output_schema: Schema for the expected output.
        client (OpenAI): OpenAI client instance.
        validator: Validator instance for checking ICD-10 codes.
        openai_parameters (dict): Parameters for OpenAI API calls.
    """

    def __init__(
        self,
        role,
        responsibilities,
        output_schema,
        client,
        icd10_validator,
        openai_parameters={"max_tokens": 1024, "temperature": 0.1},
    ):
        self.role = role
        self.responsibilities = responsibilities
        self.system_instructions = (
            f"Role: {self.role}\nResponsibilities: {self.responsibilities}"
        )
        self.output_schema = output_schema
        self.client = client
        self.validator = icd10_validator
        self.openai_parameters = openai_parameters

    def process(self, input_data):
        """
        Abstract method to process input data. Must be implemented by subclasses.

        Args:
            input_data: Input data for processing.

        Raises:
            NotImplementedError: If not implemented in a subclass.
        """
        raise NotImplementedError("Each agent must implement the process method.")

    def log(self, input_data, output_data):
        """
        Log inputs, outputs, and API call parameters for error tracing.

        Args:
            input_data: Input data to log.
            output_data: Output data to log.
        """
        log_entry = {
            "role": self.role,
            "input": input_data,
            "output": output_data,
            "openai_parameters": self.openai_parameters,
        }
        logger.debug(json.dumps(log_entry, indent=2))

    def get_structured_output(self, prompt, response_format):
        """
        Retrieve structured output from OpenAI API.

        Args:
            prompt (str): Input prompt for the model.
            response_format: Expected response format.

        Returns:
            dict: Structured output.
        """
        return openai_structured_output(
            self.client,
            self.system_instructions,
            prompt,
            response_format,
            openai_params=self.openai_parameters,
        )

    def validate_output(self, output):
        """
        Validate ICD-10 codes in the output.

        Args:
            output (dict): Output containing ICD-10 codes.

        Returns:
            dict: Validated ICD-10 codes with updated descriptions.
        """
        icd10_codes = output["icd10_codes"]
        validated_codes = []
        for code_with_evidence in icd10_codes:
            code = code_with_evidence["code"]
            description = code_with_evidence["description"]
            if not self.validator.check_code_validity(code):
                logger.info(
                    f"Code {code} with description '{description}' is not a valid ICD10-CM code. Dropping."
                )
            else:
                new_desc = self.validator.get_description(code)
                old_desc = description
                if new_desc != old_desc:
                    logger.debug(
                        f"Updating description based on ICD10-CM database. Code: {code}, Model provided description: {old_desc}, Updated description: {new_desc}"
                    )
                code_with_evidence["description"] = new_desc
                validated_codes.append(code_with_evidence)

        return {"icd10_codes": validated_codes}


class Coder(Agent):
    """
    Agent responsible for assigning ICD-10 codes to clinical notes.
    """

    def process(self, note):
        """
        Assign ICD-10 codes to the given clinical note.

        Args:
            note (str): Clinical note to process.

        Returns:
            dict: Validated ICD-10 codes with evidence and descriptions.
        """
        prompt = f"Assign as many ICD10-CM diagnosis codes as possible to this discharge summary. Include a minimal verbatim snippet from the note as evidence for each diagnosis code. Also return a description of each code. Return all output as a JSON with the specified format.\n\nClinical Note:\n{note}"

        structured_output = self.get_structured_output(prompt, self.output_schema)
        self.log(note, structured_output)
        validated_output = self.validate_output(structured_output)
        return validated_output


class ReviewerOrAdjustor(Agent):
    """
    Base class for reviewing and adjusting ICD-10 codes.

    Attributes:
        retriever: Instance to retrieve relevant codes or data from external sources.
        num_candidates (int): Number of alternative codes to retrieve.
        reviewed_codes (list): List of reviewed ICD-10 codes.
    """

    def __init__(
        self,
        role,
        responsibilities,
        retriever,
        client,
        icd10_validator,
        num_candidates=10,
        openai_parameters={"max_tokens": 1024, "temperature": 0.1},
    ):
        super().__init__(
            role,
            responsibilities,
            output_schema=ExplainedOutput,
            client=client,
            icd10_validator=icd10_validator,
            openai_parameters=openai_parameters,
        )
        self.retriever = retriever
        self.num_candidates = num_candidates
        self.reviewed_codes = []

    def retrieve_codes(self, code_list, k=None):
        """
        Retrieve relevant ICD-10 codes from the database.

        Args:
            code_list (list): List of codes to retrieve related alternatives for.
            k (int, optional): Number of alternatives to retrieve. Defaults to num_candidates.

        Returns:
            list: Retrieved alternative codes.
        """
        if not k:
            k = self.num_candidates
        related_codes = [
            x
            for code in code_list
            for x in self.retriever.retrieve(
                query=code["evidence"],
                k=k,
            )
        ]

        logger.debug(f"Retrieved codes:\n{related_codes}")

        return related_codes

    def code_feedback(self, codes):
        """
        Provide feedback on ICD-10 codes' validity and billability.

        Args:
            codes (list): List of ICD-10 codes to validate.

        Returns:
            str: Feedback on the validity and billability of the codes.
        """
        output = defaultdict(list)
        feedback = ""
        for code in codes:
            if not self.validator.check_code_validity(code):
                output["invalid"].append(code)
            elif not self.validator.check_code_billable(code):
                output["not_billable"].append(code)
            else:
                output["valid"].append(json.dumps(self.validator.get_all_data(code)))

        if "invalid" in output:
            invalid = output["invalid"]
            feedback += f"The following are not valid ICD-10 codes: {invalid}\n\n"
        if "not_billable" in output:
            not_billable = output["not_billable"]
            feedback += f"The following ICD-10 codes are valid but not billable: {not_billable}\n\n"
        if "valid" in output:
            valid = output["valid"]
            joined_valid = "\n".join(valid)
            feedback += f"Definitions of remaining ICD-10 codes that are both valid and billable:\n{joined_valid}\n"

        return feedback


class Reviewer(ReviewerOrAdjustor):
    """
    Agent responsible for reviewing ICD-10 codes and providing feedback.
    """

    def process(self, data, k=10):
        """
        Review and refine ICD-10 codes for a given note.

        Args:
            data (dict): Input data containing a clinical note and codes from the Coder.
            k (int): Number of alternative codes to retrieve. Defaults to 10.

        Returns:
            dict: Validated ICD-10 codes with evidence and descriptions.
        """
        note = data["note"]
        codes_with_evidence = data["coder"]["icd10_codes"]
        code_list = [x["code"] for x in codes_with_evidence]
        code_lookup_feedback = self.code_feedback(code_list)
        related_codes = self.retrieve_codes(codes_with_evidence, k=k)

        prompt = f"Assign as many ICD10-CM diagnosis codes as possible to this discharge summary. Include a minimal verbatim snippet from the note as evidence for each diagnosis code. Also return a description of each code. Please only use billable codes.\n\nDischarge Summary:\n{note}\n\nCodes from Coder Agent:\n{json.dumps(codes_with_evidence, indent=2)}\n\nFeedback from ICD-10 database lookup of codes: {code_lookup_feedback}\n\nThe following are alternative ICD-10 codes that are related to the diagnoses and evidence presented here. You may consider if any would be a good replacement or addition to those already billed:\n{related_codes}"

        structured_output = self.get_structured_output(prompt, self.output_schema)
        self.log(note, structured_output)
        validated_output = self.validate_output(structured_output)
        return validated_output


class PatientOrPhysician(Agent):
    """
    Agent acting as a Patient or Physician to review assigned codes.
    """

    def process(self, data):
        """
        Review the assigned ICD-10 codes for correctness.

        Args:
            data (dict): Input data containing a clinical note and reviewer-assigned codes.

        Returns:
            dict: Validated ICD-10 codes with feedback.
        """
        note = data["note"]
        assigned_codes = data["reviewer"]["icd10_codes"]

        prompt = f"Review the assigned ICD-10 codes to determine if they are correct or incorrect for the described visit. If incorrect, provide an explanation as to why. Return your answer as a JSON object containing the ICD-10 code, its description, evidence from the discharge summary to support that code, a recommendation to either 'include' or 'reject' the code, and an explanation of your reasoning.\n\nDischarge Summary:\n{note}\n\nReviewer Assigned Codes:\n{assigned_codes}"

        structured_output = self.get_structured_output(prompt, self.output_schema)
        self.log(note, structured_output)
        validated_output = self.validate_output(structured_output)
        return validated_output


class Adjustor(ReviewerOrAdjustor):
    """
    Agent responsible for final adjustments to ICD-10 codes after review by all parties.
    """

    def process(self, data):
        """
        Process and finalize ICD-10 codes based on inputs from all agents.

        Args:
            data (dict): Input data containing notes and codes from all agents.

        Returns:
            dict: Final validated ICD-10 codes.
        """
        note = data["note"]
        reviewer_codes = data["reviewer"]["icd10_codes"]
        physician_codes = data["physician"]["icd10_codes"]
        patient_codes = data["patient"]["icd10_codes"]
        all_codes = reviewer_codes + physician_codes + patient_codes

        unique_codes = list(set([x["code"] for x in all_codes]))
        code_lookup_feedback = self.code_feedback(unique_codes)

        related_codes = self.retrieve_codes(all_codes)

        prompt = f"Assign as many ICD10-CM diagnosis codes as possible to this discharge summary. Include a minimal verbatim snippet from the note as evidence for each diagnosis code. Also return a description of each code.\n\nDischarge Summary:\n{note}\n\nReviewed Codes:\n{reviewer_codes}\n\nPhysician comments on codes:\n{physician_codes}\n\nPatient comments on codes:\n{patient_codes}\n\nFeedback from database on codes from all parties:\n{code_lookup_feedback}\n\nThe following are alternative ICD-10 codes that are related to the diagnoses and evidence presented here. You may consider if any would be a good replacement or addition to those already billed:\n{related_codes}"

        structured_output = self.get_structured_output(prompt, self.output_schema)
        self.log(note, structured_output)
        validated_output = self.validate_output(structured_output)
        return validated_output

    def postprocess(self, validated_output):
        """
        Postprocess output into the desired format.

        Args:
            validated_output (dict): Validated ICD-10 codes.

        Returns:
            str: Final formatted output.
        """
        validated_codes = validated_output["icd10_codes"]
        output = {"icd10_codes": []}
        for code_obj in validated_codes:
            code = code_obj["code"]
            evidence = code_obj["evidence"]
            description = code_obj["description"]
            output["icd10_codes"].append(
                {"code": code, "evidence": evidence, "description": description}
            )
        return output


class NotesProcessor:
    """
    Class for processing notes and orchestrating interactions between agents.

    Attributes:
        coder (Coder): Coder agent instance.
        reviewer (Reviewer): Reviewer agent instance.
        physician (PatientOrPhysician): Physician agent instance.
        patient (PatientOrPhysician): Patient agent instance.
        adjustor (Adjustor): Adjustor agent instance.
    """

    def __init__(self, coder, reviewer, physician, patient, adjustor):
        self.coder = coder
        self.reviewer = reviewer
        self.physician = physician
        self.patient = patient
        self.adjustor = adjustor

    def process_note(self, note):
        """
        Process a clinical note through all agent stages.

        Args:
            note (str): Clinical note to process.

        Returns:
            dict: Final ICD-10 codes from all stages.
        """
        coder_output = self.coder.process(note)
        reviewer_output = self.reviewer.process({"note": note, "coder": coder_output})
        physician_output = self.physician.process(
            {"note": note, "reviewer": reviewer_output}
        )
        patient_output = self.patient.process(
            {"note": note, "reviewer": reviewer_output}
        )
        adjustor_output = self.adjustor.process(
            {
                "note": note,
                "coder": coder_output,
                "reviewer": reviewer_output,
                "physician": physician_output,
                "patient": patient_output,
            }
        )
        final_output = self.adjustor.postprocess(adjustor_output)
        return final_output
