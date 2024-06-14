"""Implementation derived from https://github.com/tloen/alpaca-lora"""
import sys
from pathlib import Path

# support running without installing as a package
wd = Path(__file__).parent.parent.resolve()
sys.path.append(str(wd))

import torch
import requests
import json
from torch.utils.data import random_split
# from lit_llama.tokenizer import Tokenizer
from tqdm import tqdm
import pandas as pd

DATA_FILE = "https://raw.githubusercontent.com/tloen/alpaca-lora/main/alpaca_data_cleaned_archive.json"
DATA_FILE_NAME = "alpaca_data_cleaned_archive.json"
IGNORE_INDEX = -1


def prepare(
    destination_path: Path = Path("/media/gaurish/angela1/projects/code-mixed-24/Data"), 
    tokenizer_path: Path = Path("checkpoints/lit-llama/tokenizer.model"),
    test_split_size: int = 2000,
    max_seq_length: int = 256,
    seed: int = 42,
    mask_inputs: bool = False,  # as in alpaca-lora
    data_file_name: str = DATA_FILE_NAME
) -> None:
    """Prepare the Alpaca dataset for instruction tuning.
    
    The output is a training and validation dataset saved as `train.pt` and `val.pt`,
    which stores the preprocessed and tokenized prompts and labels.
    """
    
    destination_path.mkdir(parents=True, exist_ok=True)
    file_path = destination_path / data_file_name
    download(file_path)

    # TODO: If we don't have the Meta weights, where do we get the tokenizer from?
    tokenizer = None #Tokenizer(tokenizer_path)
    df_train = pd.read_csv(destination_path / "Training/train_Hindi.csv")
    df_test = pd.read_csv(destination_path / "Validation/valid_Hindi.csv")

    df_train = df_train.rename(columns={'sentence': 'input', 'sentiment': 'output'})
    df_test = df_test.rename(columns={'sentence': 'input', 'sentiment': 'output'})
    
    df_train["instruction"]= "Classify the given article as either positive or negative or neutral or mix sentiment."
    df_test["instruction"]= "Classify the given article as either positive or negative  or neutral or mix sentiment."

    train_set =  json.loads(json.dumps(list(df_train.T.to_dict().values()))) #df_train.to_json(orient="records")
    print(train_set)
    test_set =  json.loads(json.dumps(list(df_test.T.to_dict().values())))#df_test.to_json(orient="records")  
    # "instruction": "Classify the given article as either positive or negative sentiment.",
    # "input": "The new car is a disappointment. The breaks are terrible and cost way too much for the features offered.",
    # "output": "Negative"
    # # create json from pandas datafrmae
    
    # with open(file_path, "r") as file:
    #     data = json.load(file)

    # # Partition the dataset into train and test
    # train_split_size = len(data) - test_split_size
    # train_set, test_set = random_split(
    #     data, 
    #     lengths=(train_split_size, test_split_size),
    #     generator=torch.Generator().manual_seed(seed),
    # )
    train_set, test_set = list(train_set), list(test_set)

    print(f"train has {len(train_set):,} samples")
    print(f"val has {len(test_set):,} samples")

    print("Processing train split ...")
    train_set = [prepare_sample(sample, tokenizer, max_seq_length, mask_inputs) for sample in tqdm(train_set)]
    torch.save(train_set, file_path.parent / "train.pt")

    print("Processing test split ...")
    test_set = [prepare_sample(sample, tokenizer, max_seq_length, mask_inputs) for sample in tqdm(test_set)]
    torch.save(test_set, file_path.parent / "test.pt")


def download(file_path: Path):
    """Downloads the raw json data file and saves it in the given destination."""
    if file_path.exists():
        return
    with open(file_path, "w") as f:
        f.write(requests.get(DATA_FILE).text)


def prepare_sample(example: dict, tokenizer:str, max_length: int, mask_inputs: bool = True):
    """Processes a single sample.
    
    Each sample in the dataset consists of:
    - instruction: A string describing the task
    - input: A string holding a special input value for the instruction.
        This only applies to some samples, and in others this is empty.
    - output: The response string

    This function processes this data to produce a prompt text and a label for
    supervised training. The input text is formed as a single message including all
    the instruction, the input (optional) and the response.
    The label/target is the same message but can optionally have the instruction + input text
    masked out (mask_inputs=True).

    Finally, both the prompt and the label get tokenized. If desired, all tokens
    in the label that correspond to the original input prompt get masked out (default).
    """
    full_prompt = generate_prompt(example)
    full_prompt_and_response = full_prompt + example["output"]
    encoded_full_prompt = tokenize(tokenizer, full_prompt, max_length=max_length, eos=False)
    encoded_full_prompt_and_response = tokenize(tokenizer, full_prompt_and_response, eos=True, max_length=max_length)

    # The labels are the full prompt with response, but with the prompt masked out
    labels = encoded_full_prompt_and_response.clone()
    if mask_inputs:
        labels[:len(encoded_full_prompt)] = IGNORE_INDEX

    return {**example, "input_ids": encoded_full_prompt_and_response, "input_ids_no_response": encoded_full_prompt, "labels": labels}


def tokenize(tokenizer, string: str, max_length: int, eos=True) -> torch.Tensor:
    return tokenizer.encode(string, bos=True, eos=eos, max_length=max_length)


def generate_prompt(example):
    """Generates a standardized message to prompt the model with an instruction, optional input and a
    'response' field."""

    if example["input"]:
        return (
            "Below is an instruction that describes a task, paired with an input that provides further context. "
            "Write a response that appropriately completes the request.\n\n"
            f"### Instruction:\n{example['instruction']}\n\n### Input:\n{example['input']}\n\n### Response:"
        )
    return (
        "Below is an instruction that describes a task. "
        "Write a response that appropriately completes the request.\n\n"
        f"### Instruction:\n{example['instruction']}\n\n### Response:"
    )


if __name__ == "__main__":
    from jsonargparse import CLI

    CLI(prepare)
