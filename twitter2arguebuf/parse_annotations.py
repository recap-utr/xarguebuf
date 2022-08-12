import itertools
import json
import typing as t
from dataclasses import dataclass, field
from pathlib import Path

import arguebuf
import typer
from dataclasses_json import DataClassJsonMixin
from nltk.metrics.agreement import AnnotationTask
from rich import print

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
    annotations_file: Path,
    input_folder: Path,
    input_pattern: str,
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

    print(f"Total annotations: {annotations}")

    with annotations_file.open("w", encoding="utf-8") as f:
        json.dump(casebase.to_dict(), f)


@app.command()
def from_json(
    annotations_file: Path,
    input_folder: Path,
    output_folder: t.Optional[Path] = None,
    render: bool = False,
):
    if not output_folder:
        output_folder = input_folder

    with annotations_file.open("r", encoding="utf-8") as f:
        casebase = CaseBase.from_dict(json.load(f))

    for relative_path, graph_ann in casebase.graphs.items():
        file = input_folder / relative_path
        graph = arguebuf.Graph.from_file(file)

        missing_in_annotation = set(graph.scheme_nodes.keys()).difference(
            graph_ann.schemes.keys()
        )
        missing_in_graph = set(graph_ann.schemes.keys()).difference(
            graph.scheme_nodes.keys()
        )

        assert not missing_in_annotation, missing_in_graph

        for scheme_id, scheme_ann in graph_ann.schemes.items():
            scheme_node = graph.scheme_nodes[scheme_id]
            label = scheme_ann.label

            if label == "a":
                scheme_node.scheme = arguebuf.Attack.DEFAULT
            elif label == "s":
                scheme_node.scheme = arguebuf.Support.DEFAULT
            else:
                print("Scheme not recognized. Skipping.")

        output_file = output_folder / relative_path
        output_file.parent.mkdir(parents=True, exist_ok=True)
        graph.to_file(output_file)

        if render:
            arguebuf.render(graph.to_gv("svg"), output_file.with_suffix(".svg"))


@app.command()
def agreement(template_file: Path, files: t.List[Path]):
    with template_file.open("r", encoding="utf-8") as f:
        template = json.load(f)

    annotations: list[t.Mapping[str, t.Any]] = []
    data: list[tuple[int, str, str]] = []

    for file in files:
        with file.open("r", encoding="utf-8") as f:
            annotations.append(json.load(f))

    for graph_id, graph in template["graphs"].items():
        data.extend(
            (
                annotator_id,
                graph_id + scheme_id,
                annotation["graphs"][graph_id]["schemes"][scheme_id]["label"],
            )
            for scheme_id, (annotator_id, annotation) in itertools.product(
                graph["schemes"].keys(), enumerate(annotations)
            )
        )

    task = AnnotationTask(data)

    print(f"Annotations: {len(data)}")
    print(f"Bennett's S: {task.S()}")
    print(f"Scott's Pi: {task.pi()}")
    print(f"Fleiss's Kappa: {task.multi_kappa()}")
    print(f"Cohen's Kappa: {task.kappa()}")
    print(f"Cohen's Weighted Kappa: {task.weighted_kappa()}")
    print(f"Krippendorff's Alpha: {task.alpha()}")
