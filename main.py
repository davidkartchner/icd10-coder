import json
import aiohttp
import asyncio
from pathlib import Path
from src.utils import write_json


async def process_single_note(session, note_text, api_url):
    """
    Process a single note through the API endpoint.

    Args:
        session (aiohttp.ClientSession): Active HTTP session
        note_text (str): The note text to process
        api_url (str): The API endpoint URL

    Returns:
        dict: The API response
    """
    async with session.post(api_url, json={"note": note_text}) as response:
        if response.status != 200:
            error_text = await response.text()
            raise Exception(
                f"API call failed with status {response.status}: {error_text}"
            )
        return await response.json()


async def process_all_notes():
    # Configure paths
    base_dir = Path("test_data")
    input_dir = base_dir / "inputs"
    pred_dir = base_dir / "preds"

    # Create predictions directory if it doesn't exist
    pred_dir.mkdir(exist_ok=True)

    # API endpoint URL - modify as needed
    api_url = "http://0.0.0.0:8000/process_note"

    # Get all input files
    input_files = input_dir.glob("input*.txt")

    async with aiohttp.ClientSession() as session:
        for input_file in input_files:
            try:
                # Extract file number from input filename
                file_num = input_file.stem.replace("input", "")
                pred_file = pred_dir / f"pred{file_num}.json"

                # Read input note
                with open(input_file, "r") as f:
                    note_text = f.read()

                print(f"Processing {input_file.name}...")

                # Get prediction from API
                result = await process_single_note(session, note_text, api_url)
                print(result)

                write_json(result, pred_file)

                print(f"Successfully processed {input_file.name} -> {pred_file.name}")

            except Exception as e:
                print(f"Error processing {input_file.name}: {str(e)}")


def main():
    asyncio.run(process_all_notes())


if __name__ == "__main__":
    main()
