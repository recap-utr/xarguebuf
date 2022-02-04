from __future__ import annotations

import json
import typing as t
from dataclasses import dataclass
from pathlib import Path

# @dataclass
# class Annotation:
#     scheme_id: str
#     claim: str
#     premise: str
#     label: str

#     @classmethod
#     def from_dict(cls, d: t.Mapping[str, t.Any]):
#         return cls(d["scheme_id"], d["claim"], d[""])


def prompt() -> str:
    return input("support/attack (s/a): ")


file = Path("annotations.json")
with file.open("r", encoding="utf-8") as f:
    annotations = json.load(f)

print(
    "You will be presented with premises and claims along with the root node of the graph (i.e., the major claim)."
)
print(
    "Please state for each pair, if the premise supports or attacks the claim. The major claim is only shown to provide some context."
)
print("Enter either 's' for support and 'a' for attack.")
print(
    "Your results are saved after each pair, so you can exit the program at any time and resume later without losing your progress."
)

for graph_name, graph_ann in annotations["graphs"].items():
    print()
    print()
    print(f"Now working on file '{graph_name}'")
    print(f"It has the following major claim:\n{graph_ann['mc']}")
    for scheme_id, scheme_ann in graph_ann["schemes"].items():
        if not scheme_ann["label"]:
            print()
            print()
            print(f"Claim: {scheme_ann['claim']}")
            print(f"Premise: {scheme_ann['premise']}")
            print()
            label = input("(s)upport / (a)ttack: ")

            while label not in ("s", "a"):
                label = input("Only 's' and 'a' are valid. Please try again: ")

            scheme_ann["label"] = label

            with file.open("w", encoding="utf-8") as f:
                json.dump(annotations, f)

    print()
    print(f"Finished with file '{graph_name}'")

print()
print("All pairs annotated, thank you!")
