from pydantic import BaseModel
from typing import List
from enum import Enum


class ICD10Code(BaseModel):
    code: str
    description: str
    evidence: str


class ExplainedCode(ICD10Code):
    explanation: str


class ReviewedCode(ExplainedCode):
    old_code: str


class Recommendation(str, Enum):
    include = "include"
    reject = "reject"


class ExplainedCodeWithRecommendation(ExplainedCode):
    recommendation: Recommendation


class CodeOutput(BaseModel):
    icd10_codes: List[ICD10Code]


class ExplainedOutput(BaseModel):
    icd10_codes: List[ExplainedCode]


class ExplainedOutputWithRecommendation(BaseModel):
    icd10_codes: List[ExplainedCodeWithRecommendation]
