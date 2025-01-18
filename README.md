# Instructions for use
## Environment Setup
Create and activate the conda environment with the following commands:
```bash
conda env create -f environment.yaml
conda activate icd10
```

Set OpenAI API Key environment variable
```bash
OPENAI_API_KEY=...
```

## Launch API
The multi-agent ICD10-CM coding system runs via FastAPI.  To launch the endpoint for processing notes through agents, run
```bash
uvicorn src.app:app --host 0.0.0.0 --port 8000
```

### Usage
**Process a clinical note**
`POST /process_note`
Process a clinical note to extract and validate ICD-10 codes.
**Request**
```json
{
    "note": "Patient presents with acute bronchitis and hypertension..."
}
```

## Run example files
A set of sample discharge summaries lives in `test_data/inputs`.  Their corresponding reference annotations are in `test_data/outputs`. Once the API has been launched, you can process all of the notes through it by running the command
```bash
python main.py
```
This will create files with model predictions in `test_data/preds`.  

### Evaluation
Once the output files are in place, you can generate a simple evaluation summary of the model predictions vs. references by running
```bash
python evaluate.py
```

# Questions
## 1. How would you improve this system in the future?
To improve this system, I would test the following:
* Improve heavily in an evaluation to ensure that the model output aligns with expert medical coders (see more in "Monitoring and improving over time" section below).  Good evaluation is necessary to determine what model performance even is so that it can be improved over time.  D
* Try the obvious: Use a more performant model (e.g. o1) and/or finetune a LLM specifically for the purpose of ICD-10 coding
* Try (meta-prompting)[https://platform.openai.com/docs/guides/prompt-generation] to allow LLM to iteratively design its own prompts for the task, aligned with prompting best practices  
* No tuning has been done to the retrieval system -- it is currently using off-the-shelf embeddings from a small LLM. I would tune embeddings to better match in-house labeled data.  Depending on performance, I would possibly augment with BM25 retrieval to ensure that the reviewer is always being presented with all relevant data to assign codes.  Improved retrieval will improve the review/validation of codes to make sure that each piece of evidence has been normalized to the correct code.
* Test an two-stage extract -> normalize approach, i.e. first extract free text corresponding to a diagnosis.  This has the potential benefits of reducing the number of LLM calls (2 instead of 5) and also simplifying the individual tasks that the LLM is expected to perform, resulting in more consistent results.  In my experience, it is relatively easy for an LLM to extract text corresponding to a diagnosis and also relatively easy to pick the correct normalization from a list of candidates.  Performance degrades when the LLM is asked to extract ICD-10 codes in a single pass and can lead to omissions/hallucinations.  Moreover, separate extraction and normalizaiton agents allow for more granular attribution of errors and simpler implementation of solutions.
* Try prompting multiple LLMs to extract/normalize codes and have a separate layer to aggregate the results, creating a "mixture of agents" model as described in [this paper](https://arxiv.org/abs/2406.04692)
* Reviewer could be asked to review each code individually instead of in bulk.  This would increase cost via more calls to the LLM backend but may improve precision.  
* Perform additional postprocessing to ensure taht Use includes/excludes sections of ICD-10 codes to make sure that we aren't getting conflicting codes from the same note.  This adjustment could be done via an additional call to the backend LLM.

## 2. Monitoring and improving over time
1. Create quality control pipeline to check extracted data for accuracy.  This pipeline would take diagnosis codes output by model and review + update them via clinical experts.  Not only does this allow us to quantitatively measure model performance, it also creates high-quality preference pairs for RHLF/DPO later on in the pipeline.
   1. It should be noted that simply using historical data for this purpose is likely not sufficient.  AI models frequently catch information that humans miss or annotate incorrectly, meaning historical annotations != gold standard.  
   2. Quality control should be supplemented by ongoing A/B testing of new vs. previous best model to confirm performance improvements "in the wild"
2. Analyze stage of model failure.  For errors discovered by model, check the source of the error. This will enable us to determine what models, data, or prompts need to be adjusted to correct the error.
   1. Did the evidence extracted by the model correspond to real text in the document?  
   2. If yes, should this text correspond to a diagnosis code?  
   3. If yes, the model normalize to the correct code (or retrieve the right code as possible candidates for normalization)?
   4. Was a diagnosis correctly coded by one agent but removed by another?
   5. Etc.
3. Train a specialized judge model to evaluate extracted data.  This model would be trained to evaluate whether a specific piece of extracted data was correct


# Evaluation on test data
A preliminary analysis of the results is contained in `analysis_results.json`.  For each note, this does the following:
* Lists which ICD-10 codes were shared between the predictions and provided ground truth examples
* Lists which codes were found only in one or the other, along with the evidence supporting each
* Lists any codes that were invalid or not billable


This preliminary analysis revealed that some codes in the test data are not billable and/or not diagnosis codes.
* The following codes in the test data ICD10-CM procedure codes (not diagnosis codes): ['3E03317', '0DTJ4ZZ']
* The following codes in the test data are ICD10-CM diagnosis codes but are not billable: ['E87.2', 'R51', 'I21.0', 'R51', 'K85.2']

For futher evaluation, I would use a high-end model such as o1 to compare the sets of codes upon which prediction disagreed with reference and adjudicate the decision.  I would also solicit feedback from a professional medical coder to check if the model's evaluation.  If the model's evaluation aligns with the expert, I would use it as a judge to evaluate the correctness of extracted codes moving forward.

# Limitations
* Many of the ICD codes in the evaluation data are not billable according to this [data]() and corresponding [data description]().  Depending on what flags are used, model may omit non-billable codes from the results.
* Evaluation data contains both ICD10-PCS procedure codes and ICD10-CM diagnosis codes.  Our framework only outputs ICD10-CM diagnosis codes.  Any ICD10-PCS procedure codes will be missed.  
* Current code does not have much error handling.  Before deployment, code should gracefully handle cases where OpenAI refuses to give a response.  It should also provide format validation to ensure that all produced codes are valid ICD-10 codes


