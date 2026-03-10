import importlib.util
import os

from helpers.api import ApiHandler, Request, Response
from helpers import plugins

# Dynamic import of LinearClient (same pattern as tools/linear.py)
_helpers_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "helpers")
_spec = importlib.util.spec_from_file_location(
    "linear_client", os.path.join(_helpers_dir, "linear_client.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
LinearClient = _mod.LinearClient
LinearAPIError = _mod.LinearAPIError


def _get_config():
    """Get Linear plugin config (no agent context needed for dashboard)."""
    return plugins.get_plugin_config("linear")


def _get_client() -> "LinearClient":
    """Instantiate LinearClient from plugin config."""
    config = _get_config()
    return LinearClient(config.get("api_key", ""))


class LinearDashboard(ApiHandler):

    async def process(self, input: dict, request: Request) -> dict | Response:
        action = input.get("action", "list_issues")
        try:
            if action == "get_config":
                return self._get_safe_config()
            elif action == "list_teams":
                return await self._list_teams()
            elif action == "list_states":
                return await self._list_states(input)
            elif action == "list_members":
                return await self._list_members(input)
            elif action == "list_issues":
                return await self._list_issues(input)
            elif action == "get_issue":
                return await self._get_issue(input)
            elif action == "search_issues":
                return await self._search_issues(input)
            elif action == "create_issue":
                return await self._create_issue(input)
            elif action == "update_issue":
                return await self._update_issue(input)
            elif action == "add_comment":
                return await self._add_comment(input)
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        except LinearAPIError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {e}"}

    def _get_safe_config(self) -> dict:
        """Return non-sensitive config (no API key)."""
        config = _get_config()
        return {
            "success": True,
            "config": {
                "default_team": config.get("default_team", ""),
                "show_sidebar_button": config.get("show_sidebar_button", True),
                "auto_refresh_on_focus": config.get("auto_refresh_on_focus", True),
            },
        }

    async def _list_teams(self) -> dict:
        client = _get_client()
        data = await client.execute("""
            query { teams { nodes { id name key } } }
        """)
        return {
            "success": True,
            "teams": data.get("teams", {}).get("nodes", []),
        }

    async def _list_states(self, input: dict) -> dict:
        client = _get_client()
        team_id = input.get("team_id", "")
        if not team_id:
            return {"success": False, "error": "team_id is required"}
        data = await client.execute("""
            query($teamId: String!) {
                team(id: $teamId) {
                    states { nodes { id name type position } }
                }
            }
        """, {"teamId": team_id})
        states = data.get("team", {}).get("states", {}).get("nodes", [])
        states.sort(key=lambda s: s.get("position", 0))
        return {"success": True, "states": states}

    async def _list_members(self, input: dict) -> dict:
        client = _get_client()
        team_id = input.get("team_id", "")
        if not team_id:
            return {"success": False, "error": "team_id is required"}
        data = await client.execute("""
            query($teamId: String!) {
                team(id: $teamId) {
                    members { nodes { id name displayName } }
                }
            }
        """, {"teamId": team_id})
        members = data.get("team", {}).get("members", {}).get("nodes", [])
        return {"success": True, "members": members}

    async def _list_issues(self, input: dict) -> dict:
        client = _get_client()
        limit = input.get("limit", 25)
        filter_parts = {}
        team_id = input.get("team_id", "")
        if team_id:
            filter_parts["team"] = {"id": {"eq": team_id}}
        state_filter = input.get("state_filter", "")
        if state_filter:
            filter_parts["state"] = {"name": {"containsIgnoreCase": state_filter}}
        assignee_filter = input.get("assignee_filter", "")
        if assignee_filter:
            filter_parts["assignee"] = {"name": {"containsIgnoreCase": assignee_filter}}

        data = await client.execute("""
            query($filter: IssueFilter, $first: Int) {
                issues(filter: $filter, first: $first, orderBy: updatedAt) {
                    nodes {
                        id identifier title description url
                        state { id name type }
                        assignee { id name }
                        labels { nodes { id name color } }
                        project { name }
                        priorityLabel priority
                        createdAt updatedAt
                    }
                }
            }
        """, {"filter": filter_parts if filter_parts else None, "first": limit})
        issues = data.get("issues", {}).get("nodes", [])
        return {"success": True, "issues": issues, "total_count": len(issues)}

    async def _get_issue(self, input: dict) -> dict:
        client = _get_client()
        issue_id = input.get("issue_id", "")
        if not issue_id:
            return {"success": False, "error": "issue_id is required"}
        data = await client.execute("""
            query($id: String!) {
                issue(id: $id) {
                    id identifier title description url
                    state { id name type }
                    assignee { id name }
                    labels { nodes { id name color } }
                    project { name }
                    priorityLabel priority
                    createdAt updatedAt
                    comments {
                        nodes { id body createdAt user { name } }
                    }
                }
            }
        """, {"id": issue_id})
        issue = data.get("issue")
        if not issue:
            return {"success": False, "error": f"Issue '{issue_id}' not found"}
        return {"success": True, "issue": issue}

    async def _search_issues(self, input: dict) -> dict:
        client = _get_client()
        query = input.get("query", "")
        if not query:
            return {"success": False, "error": "query is required"}
        limit = input.get("limit", 25)
        data = await client.execute("""
            query($query: String!, $first: Int) {
                searchIssues(query: $query, first: $first) {
                    nodes {
                        id identifier title description url
                        state { id name type }
                        assignee { id name }
                        labels { nodes { id name color } }
                        project { name }
                        priorityLabel priority
                        createdAt updatedAt
                    }
                }
            }
        """, {"query": query, "first": limit})
        issues = data.get("searchIssues", {}).get("nodes", [])
        return {"success": True, "issues": issues, "total_count": len(issues)}

    async def _create_issue(self, input: dict) -> dict:
        client = _get_client()
        title = input.get("title", "")
        team_id = input.get("team_id", "")
        if not title:
            return {"success": False, "error": "title is required"}
        if not team_id:
            return {"success": False, "error": "team_id is required"}

        issue_input = {"teamId": team_id, "title": title}
        if input.get("description"):
            issue_input["description"] = input["description"]
        if input.get("assignee_id"):
            issue_input["assigneeId"] = input["assignee_id"]
        if input.get("state_id"):
            issue_input["stateId"] = input["state_id"]
        if input.get("priority") is not None:
            issue_input["priority"] = int(input["priority"])

        data = await client.execute("""
            mutation($input: IssueCreateInput!) {
                issueCreate(input: $input) {
                    success
                    issue { id identifier title url state { id name type } }
                }
            }
        """, {"input": issue_input})
        result = data.get("issueCreate", {})
        return {
            "success": result.get("success", False),
            "issue": result.get("issue"),
        }

    async def _update_issue(self, input: dict) -> dict:
        client = _get_client()
        issue_id = input.get("issue_id", "")
        if not issue_id:
            return {"success": False, "error": "issue_id is required"}

        update_input = {}
        if input.get("title"):
            update_input["title"] = input["title"]
        if input.get("state_id"):
            update_input["stateId"] = input["state_id"]
        if input.get("assignee_id"):
            update_input["assigneeId"] = input["assignee_id"]
        if input.get("priority") is not None:
            update_input["priority"] = int(input["priority"])

        if not update_input:
            return {"success": False, "error": "No fields to update"}

        data = await client.execute("""
            mutation($id: String!, $input: IssueUpdateInput!) {
                issueUpdate(id: $id, input: $input) {
                    success
                    issue {
                        id identifier title url
                        state { id name type }
                        assignee { id name }
                        priorityLabel priority
                    }
                }
            }
        """, {"id": issue_id, "input": update_input})
        result = data.get("issueUpdate", {})
        return {
            "success": result.get("success", False),
            "issue": result.get("issue"),
        }

    async def _add_comment(self, input: dict) -> dict:
        client = _get_client()
        issue_id = input.get("issue_id", "")
        body = input.get("body", "")
        if not issue_id:
            return {"success": False, "error": "issue_id is required"}
        if not body:
            return {"success": False, "error": "body is required"}

        data = await client.execute("""
            mutation($input: CommentCreateInput!) {
                commentCreate(input: $input) {
                    success
                    comment { id body createdAt user { name } }
                }
            }
        """, {"input": {"issueId": issue_id, "body": body}})
        result = data.get("commentCreate", {})
        return {
            "success": result.get("success", False),
            "comment": result.get("comment"),
        }
