from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from common.utils import env_value
from config import CNINFO_DATASETS, REQUEST_TIMEOUT


class CninfoClient:
    def __init__(self, *, timeout: int = REQUEST_TIMEOUT, datasets: Optional[Iterable[str]] = None) -> None:
        self.timeout = timeout
        self.datasets = tuple(datasets or CNINFO_DATASETS)
        self.api_token = env_value("CNINFO_API_TOKEN")

    def fetch_selected_datasets(self, start_date: str, end_date: str) -> Dict[str, List[Dict[str, str]]]:
        if not self.api_token:
            print("Missing CNINFO_API_TOKEN; skip CNINFO API datasets.")
            return {}

        outputs: Dict[str, List[Dict[str, str]]] = {}
        for dataset in self.datasets:
            outputs[dataset] = self.fetch_dataset(dataset, start_date, end_date)
        return outputs

    def fetch_dataset(self, dataset: str, start_date: str, end_date: str) -> List[Dict[str, str]]:
        print(f"CNINFO dataset '{dataset}' is registered but the request mapping is not wired yet.")
        return []
