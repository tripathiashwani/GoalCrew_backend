# app/modules/notifications/rules.py
from __future__ import annotations

from typing import TypedDict, Literal, Optional


ReceiverStrategy = Literal[
    "self",
    "reflection_owner",
    "pod_members_except_actor",
]


class NotificationRule(TypedDict):
    receiver_strategy: ReceiverStrategy
    title: str
    body: str
    entity_type: Optional[str]

class LogRule(TypedDict):
    details: str
    type: str
    action: Optional[str]


NOTIFICATION_RULES: dict[str, NotificationRule] = {
    "reflection_comment": {
        "receiver_strategy": "reflection_owner",
        "title": "New comment",
        "body": "{actor_name} commented on your reflection",
        "entity_type": "reflection",
    },
    "reflection_reaction": {
        "receiver_strategy": "reflection_owner",
        "title": "New reaction",
        "body": "{actor_name} reacted to your reflection",
        "entity_type": "reflection",
    },
    "pod_posted": {
        "receiver_strategy": "pod_members_except_actor",
        "title": "New pod update",
        "body": "{actor_name} posted in {pod_name}",
        "entity_type": "pod",
    },
    "daily_goal_reminder": {
        "receiver_strategy": "self",
        "title": "Ready for your check-in?",
        "body": "It only takes 2 minutes to show up today",
        "entity_type": "system",
    },
    "pod_member_join": {
        "receiver_strategy": "pod_members_except_actor",
        "title": "{actor_name} joined your pod",
        "body": "They just joined {pod_name}",
        "entity_type": "pod",
    },
    "daily_engagement_reminder":{
        "receiver_strategy":"self",
        "title":"Don't forget to check others progress",
        "body":"Check who posted their Goals updates",
        "entity_type":"system",
    }
}







LOG_RULES: dict[str, LogRule] = {
    "reflection_comment": {
        "details": "{commented",
        "type": "reaction",
        "action":"Commented"
    },
    "pod_created": {
        "details": "created new pod",
        "type": "pod",
        "action":"Created pod"
    },

    "pod_member_join": {
        "details": "joined pod",
        "type": "pod",
        "action":"Joined Pod"
    },
    "checked_in": {
        "details": "checked in",
        "type": "check-in",
        "action":"Checked in"
    },
    "pod_new_goal": {
        "details": "added goal",
        "type": "goal",
        "action":"Added goal"
    },
    "account_created": {
        "details": "New account created",
        "type": "account",
        "action":"New account created"
    }
}



