import math
# pyrefly: ignore [missing-import]
from transformers import Trainer, TrainingArguments
# pyrefly: ignore [missing-import]
from torch.utils.data import Dataset
# pyrefly: ignore [missing-import]
import torch

class MockDataset(Dataset):
    def __init__(self, length):
        self.length = length
    def __len__(self):
        return self.length
    def __getitem__(self, idx):
        return {"input_ids": torch.tensor([1,2,3]), "labels": torch.tensor(1)}

def test_trainer_steps(length, batch_size, epochs):
    args = TrainingArguments(
        output_dir="tmp",
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
    )
    dataset = MockDataset(length)
    trainer = Trainer(
        model=torch.nn.Linear(1,1),
        args=args,
        train_dataset=dataset,
    )
    return trainer.get_train_dataloader()

dataloader = test_trainer_steps(674068, 8, 3)
print("Steps per epoch:", len(dataloader))
print("Total steps:", len(dataloader) * 3)
