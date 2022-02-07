import itertools
import json
import typing as t
from dataclasses import dataclass, field
from pathlib import Path

import arguebuf
import typer
from dataclasses_json import DataClassJsonMixin

app = typer.Typer()


@dataclass
class SchemeAnnotation(DataClassJsonMixin):
    premise: str
    claim: str
    label: str = ""


@dataclass
class GraphAnnotation(DataClassJsonMixin):
    mc: str = ""
    schemes: t.Dict[str, SchemeAnnotation] = field(default_factory=dict)


@dataclass
class CaseBase(DataClassJsonMixin):
    graphs: t.Dict[str, GraphAnnotation] = field(default_factory=dict)


@app.command()
def to_json(
    input_folder: Path,
    input_pattern: str,
    annotations_file: Path = Path("annotations/dataset.json"),
):
    casebase = CaseBase()
    annotations = 0

    for file in input_folder.glob(input_pattern):
        graph = arguebuf.Graph.from_file(file)
        mc = graph.major_claim

        graph_ann = GraphAnnotation(mc.plain_text if mc else "")
        casebase.graphs[str(file.relative_to(input_folder))] = graph_ann

        for scheme_id, scheme_node in graph.scheme_nodes.items():
            for premise, claim in itertools.product(
                graph.incoming_nodes(scheme_node), graph.outgoing_nodes(scheme_node)
            ):
                if isinstance(premise, arguebuf.AtomNode) and isinstance(
                    claim, arguebuf.AtomNode
                ):
                    graph_ann.schemes[scheme_id] = SchemeAnnotation(
                        premise.plain_text, claim.plain_text
                    )
                    annotations += 1

    typer.echo(f"Total annotations: {annotations}")

    with annotations_file.open("w", encoding="utf-8") as f:
        json.dump(casebase.to_dict(), f)


@app.command()
def from_json(
    input_folder: Path, annotations_file: Path = Path("annotations/dataset.json")
):
    with annotations_file.open("r", encoding="utf-8") as f:
        casebase = CaseBase.from_dict(json.load(f))

    for relative_path, graph_ann in casebase.graphs.items():
        file = input_folder / relative_path
        graph = arguebuf.Graph.from_file(file)

        for scheme_id, scheme_ann in graph_ann.schemes.items():
            scheme_node = graph.scheme_nodes[scheme_id]
            label = scheme_ann.label

            if label == "a":
                scheme_node.type = arguebuf.SchemeType.ATTACK
            elif label == "s":
                scheme_node.type = arguebuf.SchemeType.SUPPORT
            else:
                print("Scheme not recognized. Skipping.")

        graph.to_file(file)
