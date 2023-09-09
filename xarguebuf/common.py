import json
import sys
import typing as t
from pathlib import Path
from shutil import rmtree

import arguebuf
import attrs
import typed_settings as ts
from arg_services.mining.v1beta import adu_pb2, entailment_pb2, entailment_pb2_grpc


@ts.settings(frozen=True)
class GraphConfig:
    render: bool = ts.option(
        default=True,
        click={"param_decls": "--graph-render", "is_flag": True},
        help=(
            "If set, the graphs will be rendered and stored as PDF files besides the"
            " source. Note: Only works in Docker or if graphviz is installed on your"
            " system."
        ),
    )
    min_depth: int = ts.option(
        default=0,
        help=(
            "Minimum distance between the conversation start (i.e., the major claim) to"
            " leaf tweet. Conversation branches with fewer tweets are removed from the"
            " graph."
        ),
    )
    max_depth: int = ts.option(
        default=sys.maxsize,
        help=(
            "Maximum distance between the conversation start (i.e., the major claim) to"
            " leaf tweet. Conversation branches with more tweets are reduced to"
            " `max_depth`."
        ),
    )
    min_nodes: int = ts.option(
        default=2,
        help=(
            "Minimum number of nodes the graph should have after converting all tweets"
            " to nodes (including the major claim). If it has fewer nodes, the graph is"
            " not stored."
        ),
    )
    max_nodes: int = ts.option(
        default=sys.maxsize,
        help=(
            "Maximum number of nodes the graph should have after converting all tweets"
            " to nodes (including the major claim). If it has more nodes, the graph is"
            " not stored."
        ),
    )


# Remove nodes that do not match the depth criterions
def prune_graph(g: arguebuf.Graph, config: GraphConfig) -> arguebuf.Graph:
    mc = g.major_claim
    assert mc is not None

    for leaf in g.leaf_nodes:
        min_depth_valid = (
            arguebuf.traverse.node_distance(
                leaf, mc, g.incoming_atom_nodes, config.min_depth
            )
            is None
        )
        max_depth_valid = (
            config.max_depth is sys.maxsize
            or arguebuf.traverse.node_distance(
                leaf, mc, g.incoming_atom_nodes, config.max_depth
            )
            is not None
        )

        if not (min_depth_valid and max_depth_valid):
            nodes_to_remove: set[arguebuf.AbstractNode] = {leaf}

            while nodes_to_remove:
                node_to_remove = nodes_to_remove.pop()
                nodes_to_remove.update(g.outgoing_nodes(node_to_remove))

                if len(g.incoming_nodes(node_to_remove)) == 0:
                    g.remove_node(node_to_remove)

    g.clean_participants()

    return g


def prepare_output(
    folder: Path,
    config: attrs.AttrsInstance,
    ignored_attrs: t.Optional[t.Iterable[str]] = None,
) -> None:
    if folder.is_dir():
        rmtree(folder)

    folder.mkdir(parents=True, exist_ok=True)
    config_dict = attrs.asdict(config)

    for attr in ignored_attrs or []:
        del config_dict[attr]

    with (folder / "config.json").open("w") as fp:
        json.dump(config_dict, fp)


def serialize(
    g: arguebuf.Graph,
    output_folder: Path,
    config: GraphConfig,
    graph_id: str,
    user_id: t.Optional[str] = None,
) -> None:
    if not (
        len(g.atom_nodes) >= config.min_nodes and len(g.atom_nodes) <= config.max_nodes
    ):
        return

    p = output_folder

    if user_id:
        p = p / user_id / graph_id

    p = p / graph_id
    p.parent.mkdir(parents=True)

    arguebuf.dump.file(g, p.with_suffix(".json"))

    if config.render:
        try:
            arguebuf.render.graphviz(arguebuf.dump.graphviz(g), p.with_suffix(".pdf"))
        except Exception as e:
            print(f"Error when trying to render {p}:\n{e}")


def predict_schemes(
    g: arguebuf.Graph,
    language: str = "en",
    client: t.Optional[entailment_pb2_grpc.EntailmentServiceStub] = None,
) -> arguebuf.Graph:
    if client:
        res: entailment_pb2.EntailmentsResponse = client.Entailments(
            entailment_pb2.EntailmentsRequest(
                language=language,
                adus={
                    node.id: adu_pb2.Segment(text=node.plain_text)
                    for node in g.atom_nodes.values()
                },
                query=[
                    entailment_pb2.EntailmentQuery(
                        premise_id=next(iter(g.incoming_nodes(scheme))).id,
                        claim_id=next(iter(g.outgoing_nodes(scheme))).id,
                    )
                    for scheme in g.scheme_nodes.values()
                ],
            )
        )

        for scheme_node, entailment in zip(g.scheme_nodes.values(), res.entailments):
            if entailment.type == entailment_pb2.ENTAILMENT_TYPE_ENTAILMENT:
                scheme_node.scheme = arguebuf.Support.DEFAULT
            elif entailment.type == entailment_pb2.ENTAILMENT_TYPE_CONTRADICTION:
                scheme_node.scheme = arguebuf.Attack.DEFAULT

    return g
