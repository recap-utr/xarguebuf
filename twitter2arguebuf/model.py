import typing as t
from dataclasses import dataclass, field

from dataclasses_json import DataClassJsonMixin
from pytwitter.models.media import Media
from pytwitter.models.place import Place
from pytwitter.models.poll import Poll
from pytwitter.models.tweet import Tweet
from pytwitter.models.user import User


@dataclass
class Includes(DataClassJsonMixin):
    media: t.List[Media] = field(default_factory=list)
    places: t.List[Place] = field(default_factory=list)
    polls: t.List[Poll] = field(default_factory=list)
    tweets: t.List[Tweet] = field(default_factory=list)
    users: t.List[User] = field(default_factory=list)


@dataclass
class Conversation(DataClassJsonMixin):
    data: t.List[Tweet] = field(default_factory=list)
    includes: Includes = field(default_factory=Includes)
