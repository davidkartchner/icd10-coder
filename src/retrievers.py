# Import necessary libraries
from typing import List, Dict
from rapidfuzz import fuzz
from rapidfuzz.process import extract

import faiss
import numpy as np
import json
import os
from sentence_transformers import SentenceTransformer
from .utils import setup_loggers

logger = setup_loggers()


# Updated code to include model_name saving/loading


class FaissDocumentRetriever:
    def __init__(self, documents: List[Dict], model_name: str, embed_docs=True):
        """
        Initializes the retriever with a set of documents and generates their embeddings.

        Args:
            documents (List[Dict]): List of JSON objects with 'code', 'description', and 'is_billable' fields.
            model_name (str): The name of the SentenceTransformer model to use.
        """
        self.documents = {
            doc["code"]: {
                "description": doc["description"],
                "is_billable": doc["is_billable"],
            }
            for doc in documents
        }
        self.codes = [doc["code"] for doc in documents]
        self.model_name = model_name

        # Generate embeddings using SentenceTransformer
        self.model = SentenceTransformer(model_name)
        descriptions = [doc["description"] for doc in documents]

        if embed_docs:
            logger.info("Computing index of documents. This may take a minute.")
            embeddings = self.model.encode(descriptions)

            # Create FAISS index
            self.index = faiss.IndexFlatL2(embeddings.shape[1])
            self.index.add(embeddings.astype(np.float32))

    def retrieve(self, query: str, k: int = 10) -> List[Dict]:
        """
        Retrieves the top-k documents for a given query string.

        Args:
            query (str): The query string to search for similar documents.
            k (int): The number of top candidates to retrieve.

        Returns:
            List[Dict]: A list of the top-k documents with their 'code', 'description', and 'is_billable' fields.
        """
        # Generate query embedding
        query_embedding = self.model.encode(query, convert_to_numpy=True)[np.newaxis, :]

        # Search for the top-k nearest neighbors
        distances, indices = self.index.search(query_embedding.astype(np.float32), k)

        # Map indices to document codes and descriptions
        results = []
        for idx in indices[0]:
            code = self.codes[idx]
            doc = self.documents[code]
            results.append(
                {
                    "code": code,
                    "description": doc["description"],
                    "is_billable": doc["is_billable"],
                }
            )

        return results

    def save(self, save_dir: str):
        """
        Saves the documents, model_name, and FAISS index to a specified directory.

        Args:
            save_dir (str): Directory where the objects will be saved. Files will be named:
                           - documents.json
                           - model_name.txt
                           - index.faiss
        """
        os.makedirs(save_dir, exist_ok=True)

        document_path = os.path.join(save_dir, "documents.json")
        model_name_path = os.path.join(save_dir, "model_name.txt")
        index_path = os.path.join(save_dir, "index.faiss")
        embedding_path = os.path.join(save_dir, "embeddings.npy")

        with open(document_path, "w") as doc_file:
            json.dump(
                [
                    {
                        "code": code,
                        "description": doc["description"],
                        "is_billable": doc["is_billable"],
                    }
                    for code, doc in self.documents.items()
                ],
                doc_file,
            )

        with open(model_name_path, "w") as model_file:
            model_file.write(self.model_name)

        faiss.write_index(self.index, index_path)
        np.save(embedding_path, self.index.reconstruct_n(0, self.index.ntotal))
        logger.info(f"Cached retriever saved to {save_dir}")

    @classmethod
    def load(cls, save_dir: str):
        """
        Loads the retriever from the specified directory.

        Args:
            save_dir (str): Directory containing the saved files:
                           - documents.json
                           - model_name.txt
                           - index.faiss

        Returns:
            FaissDocumentRetriever: The loaded FaissDocumentRetriever instance.
        """
        logger.info(f"Loading cached retriever from {save_dir}")

        document_path = os.path.join(save_dir, "documents.json")
        model_name_path = os.path.join(save_dir, "model_name.txt")
        index_path = os.path.join(save_dir, "index.faiss")
        embedding_path = os.path.join(save_dir, "embeddings.npy")

        with open(document_path, "r") as doc_file:
            documents = json.load(doc_file)

        with open(model_name_path, "r") as model_file:
            model_name = model_file.read().strip()

        index = faiss.read_index(index_path)
        embeddings = np.load(embedding_path)

        retriever = cls(documents, model_name, embed_docs=False)
        retriever.index = index
        retriever.index.add(embeddings.astype(np.float32))

        return retriever


# Define the Document class
class Doc:
    def __init__(self, text: str, metadata: Dict[str, str]):
        self.text = text
        self.metadata = metadata


# Define the FuzzyDocumentRetriever class
class FuzzyICD10Retriever:
    def __init__(self, documents: List[Doc]):
        self.documents = documents
        # self.text_to_index = {document.text:i for i, document in enumerate(self.documents)}
        self.doc_texts = [document.text for document in self.documents]

    def retrieve(
        self, query: str, top_k: int = 10, score_cutoff=50, scorer=fuzz.partial_ratio
    ) -> List[Doc]:
        # Calculate similarity scores between the query and each document's text
        outputs = extract(
            query, self.doc_texts, limit=top_k, score_cutoff=score_cutoff, scorer=scorer
        )
        inds = [x[2] for x in outputs]

        output_docs = [self.documents[ind] for ind in inds]
        return output_docs

    def get_code_by_id(
        self,
    ):
        pass
