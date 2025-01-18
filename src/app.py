import os
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI

from src.schemas import (
    CodeOutput,
    ExplainedOutputWithRecommendation,
)
from src.retrievers import FaissDocumentRetriever
from src.agents import Coder, Reviewer, PatientOrPhysician, Adjustor, NotesProcessor
from src.utils import setup_loggers, read_json, write_json
from src.validator import ICD10Validator

openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize FastAPI app
app = FastAPI()

setup_loggers()

### Setup ###
# Helpers
icd10_data = pd.read_csv("icd10_data/icd10_all_codes.tsv", delimiter="\t")[
    ["code", "description", "is_billable"]
].to_dict(orient="records")
validator = ICD10Validator(icd10_data)

cache_dir = "retriever_cache"
files_to_check = [
    os.path.join("retriever_cache", x)
    for x in ["documents.json", "embeddings.npy", "index.faiss", "model_name.txt"]
]
if all(os.path.isfile(x) for x in files_to_check):
    retriever = FaissDocumentRetriever.load(cache_dir)
else:
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    retriever = FaissDocumentRetriever(documents=icd10_data, model_name=model_name)
    retriever.save(save_dir=cache_dir)

# Initialize agents
agent_definition_dict = read_json("agent_definitions.json")
client = OpenAI(api_key=openai_api_key)

# Coder
coder_definition = agent_definition_dict["coder"]
coder = Coder(
    role=coder_definition["role"],
    responsibilities=coder_definition["responsibilities"],
    output_schema=CodeOutput,
    icd10_validator=validator,
    client=client,
)

reviewer_definition = agent_definition_dict["reviewer"]
reviewer = Reviewer(
    role=reviewer_definition["role"],
    responsibilities=reviewer_definition["responsibilities"],
    icd10_validator=validator,
    client=client,
    retriever=retriever,
    num_candidates=10,
)

# Patient
patient_definition = agent_definition_dict["patient"]
patient = PatientOrPhysician(
    role=patient_definition["role"],
    responsibilities=patient_definition["responsibilities"],
    output_schema=ExplainedOutputWithRecommendation,
    icd10_validator=validator,
    client=client,
)

# Physician
physician_definition = agent_definition_dict["physician"]
physician = PatientOrPhysician(
    role=physician_definition["role"],
    responsibilities=physician_definition["responsibilities"],
    output_schema=ExplainedOutputWithRecommendation,
    icd10_validator=validator,
    client=client,
)

adjustor_definition = agent_definition_dict["adjustor"]
adjustor = Adjustor(
    role=adjustor_definition["role"],
    responsibilities=adjustor_definition["responsibilities"],
    icd10_validator=validator,
    client=client,
    retriever=retriever,
    num_candidates=10,
)

processor = NotesProcessor(coder, reviewer, patient, physician, adjustor)


# Request body model
class NoteInput(BaseModel):
    note: str


@app.post("/process_note")
async def process_note_endpoint(input_data: NoteInput):
    """
    Endpoint to process a clinical note and return ICD-10 codes.

    Args:
        input_data (NoteInput): Input data containing the note.

    Returns:
        dict: Final ICD-10 codes and related data.
    """
    try:
        result = processor.process_note(input_data.note)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
