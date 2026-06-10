import io
import zipfile

import pandas as pd


def extract_amount_csv(response):
    amount = None

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for file_name in archive.namelist():
            if not file_name.lower().endswith(".csv"):
                continue
            with archive.open(file_name) as handle:
                if "amount" in file_name.lower():
                    amount = pd.read_csv(handle)

    if amount is None:
        raise RuntimeError("Unable to find amount CSV in usage export zip.")

    return amount
