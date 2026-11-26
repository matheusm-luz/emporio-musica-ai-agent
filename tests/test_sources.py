"""Guards the sources of truth: the files in data/ are used as delivered and never modified."""

import hashlib
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
P = "desafio_tecnico_ai_eng - "

ORIGINAL_SHA256 = {
    f"{P}categories.csv": "7a7901e16c8c6357a956031ada45a6fd6a4cc9bd7bc1edc05448cc55b01b0a9e",
    f"{P}customers.csv": "1cd724dc86eac6258913cc890abf23d3893c57a99c9325ebfb91dfad3c7b0f37",
    f"{P}order_items.csv": "7656eb681821d48e0c932f61d3188309b955c25446578235f2d8e69604b0f0bc",
    f"{P}orders.csv": "deb9c2480605d8d22117d569f0045fd156c5e9a58ffeebb847ff61b3b9512fd5",
    f"{P}products.csv": "78d911d96ee891abb163b6c858e895025aa530ab27d0290540f05d5098377c12",
    f"{P}promotions.csv": "cbe08c7e91b00437c0c00a7ef1486deba73de52d23e3f97f51a7dbd557d759e0",
    "políticas_da_loja.pdf": "b7527f96896929f4ba929de117651c6717e25b7a3b92b34bc54d5ba32f6156f7",
}


def test_original_data_files_are_unchanged() -> None:
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in DATA_DIR.iterdir()
        if path.is_file()
    }
    assert actual == ORIGINAL_SHA256
