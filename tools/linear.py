import importlib.util
import os

from helpers.tool import Tool, Response
from helpers import plugins

# Load LinearClient from the helpers directory adjacent to this tools directory.
# Standard `from plugins.linear.helpers...` only works for built-in plugins under
# plugins/, not for user plugins under usr/plugins/. This dynamic import handles both.
_helpers_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "helpers")
_spec = importlib.util.spec_from_file_location(
    "linear_client", os.path.join(_helpers_dir, "linear_client.py")
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
LinearClient = _mod.LinearClient
LinearAPIError = _mod.LinearAPIError


def _get_client(tool: Tool) -> LinearClient:
    config = plugins.get_plugin_config("linear", agent=tool.agent)
    return LinearClient(config.get("api_key", ""))


def _get_default_team(tool: Tool) -> str:
    config = plugins.get_plugin_config("linear", agent=tool.agent)
    return config.get("default_team", "")


def _format_issue_row(node: dict) -> str:
    identifier = node.get("identifier", "?")
    title = node.get("title", "Untitled")
    state = node.get("state", {})
    state_name = state.get("name", "Unknown") if state else "Unknown"
    assignee = node.get("assignee", {})
    assignee_name = assignee.get("name", "Unassigned") if assignee else "Unassigned"
    priority = node.get("priorityLabel", "None")
    return f"  {identifier}  {title}  [{state_name}]  assignee={assignee_name}  priority={priority}"


class Linear(Tool):
    async def execute(self, **kwargs) -> Response:
        try:
            method = self.method or ""
            if method == "list_teams":
                return await self._list_teams(**kwargs)
            elif method == "list_projects":
                return await self._list_projects(**kwargs)
            elif method == "list_states":
                return await self._list_states(**kwargs)
            elif method == "list_issues":
                return await self._list_issues(**kwargs)
            elif method == "get_issue":
                return await self._get_issue(**kwargs)
            elif method == "search_issues":
                return await self._search_issues(**kwargs)
            elif method == "create_issue":
                return await self._create_issue(**kwargs)
            elif method == "update_issue":
                return await self._update_issue(**kwargs)
            elif method == "add_comment":
                return await self._add_comment(**kwargs)
            else:
                return Response(
                    message=f"Unknown method 'linear:{method}'. "
                    f"Available: list_teams, list_projects, list_states, "
                    f"list_issues, get_issue, search_issues, create_issue, "
                    f"update_issue, add_comment",
                    break_loop=False,
                )
        except LinearAPIError as e:
            return Response(message=str(e), break_loop=False)
        except ValueError as e:
            return Response(message=f"Invalid argument: {e}", break_loop=False)
        except Exception as e:
            return Response(message=f"Linear connection error: {e}", break_loop=False)

    async def _list_teams(self, **kwargs) -> Response:
        client = _get_client(self)
        data = await client.execute("""
            query { teams { nodes { id name key } } }
        """)
        teams = data.get("teams", {}).get("nodes", [])
        if not teams:
            return Response(message="No teams found.", break_loop=False)
        lines = ["Teams:"]
        for t in teams:
            lines.append(f"  {t['key']}  {t['name']}  (id={t['id']})")
        return Response(message="\n".join(lines), break_loop=False)

    async def _list_projects(self, **kwargs) -> Response:
        client = _get_client(self)
        team = self.args.get("team", "")
        if team:
            data = await client.execute("""
                query($teamId: String!) {
                    team(id: $teamId) {
                        projects { nodes { id name state } }
                    }
                }
            """, {"teamId": team})
            projects = data.get("team", {}).get("projects", {}).get("nodes", [])
        else:
            data = await client.execute("""
                query { projects { nodes { id name state } } }
            """)
            projects = data.get("projects", {}).get("nodes", [])
        if not projects:
            return Response(message="No projects found.", break_loop=False)
        lines = ["Projects:"]
        for p in projects:
            lines.append(f"  {p['name']}  state={p.get('state', '?')}  (id={p['id']})")
        return Response(message="\n".join(lines), break_loop=False)

    async def _list_states(self, **kwargs) -> Response:
        client = _get_client(self)
        team = self.args.get("team", "") or _get_default_team(self)
        if not team:
            return Response(
                message="Team is required for list_states. "
                "Use linear:list_teams first to find team IDs, "
                "or set a default team in Settings > External > Linear.",
                break_loop=False,
            )
        data = await client.execute("""
            query($teamId: String!) {
                team(id: $teamId) {
                    states { nodes { id name type position } }
                }
            }
        """, {"teamId": team})
        states = data.get("team", {}).get("states", {}).get("nodes", [])
        if not states:
            return Response(message="No workflow states found.", break_loop=False)
        states.sort(key=lambda s: s.get("position", 0))
        lines = ["Workflow States:"]
        for s in states:
            lines.append(f"  {s['name']}  type={s.get('type', '?')}  (id={s['id']})")
        return Response(message="\n".join(lines), break_loop=False)

    async def _list_issues(self, **kwargs) -> Response:
        client = _get_client(self)
        limit = int(self.args.get("limit", "25"))

        filter_parts = {}
        team = self.args.get("team", "") or _get_default_team(self)
        if team:
            filter_parts["team"] = {"id": {"eq": team}}
        assignee = self.args.get("assignee", "")
        if assignee:
            filter_parts["assignee"] = {"name": {"containsIgnoreCase": assignee}}
        state = self.args.get("state", "")
        if state:
            filter_parts["state"] = {"name": {"containsIgnoreCase": state}}
        label = self.args.get("label", "")
        if label:
            filter_parts["labels"] = {"name": {"containsIgnoreCase": label}}

        data = await client.execute("""
            query($filter: IssueFilter, $first: Int) {
                issues(filter: $filter, first: $first, orderBy: updatedAt) {
                    nodes {
                        id identifier title
                        state { name type }
                        assignee { name }
                        priorityLabel
                    }
                }
            }
        """, {"filter": filter_parts if filter_parts else None, "first": limit})
        issues = data.get("issues", {}).get("nodes", [])
        if not issues:
            return Response(message="No issues found.", break_loop=False)
        lines = [f"Issues ({len(issues)}):"]
        for node in issues:
            lines.append(_format_issue_row(node))
        return Response(message="\n".join(lines), break_loop=False)

    async def _get_issue(self, **kwargs) -> Response:
        client = _get_client(self)
        issue_id = self.args.get("issue_id", "")
        if not issue_id:
            return Response(
                message="issue_id is required. Pass an identifier like ENG-123 or a UUID.",
                break_loop=False,
            )
        data = await client.execute("""
            query($id: String!) {
                issue(id: $id) {
                    id identifier title description url
                    state { name type }
                    assignee { name }
                    labels { nodes { name } }
                    project { name }
                    priorityLabel priority
                    createdAt updatedAt
                    comments {
                        nodes { body user { name } createdAt }
                    }
                }
            }
        """, {"id": issue_id})
        issue = data.get("issue")
        if not issue:
            return Response(message=f"Issue '{issue_id}' not found.", break_loop=False)

        state = issue.get("state", {})
        assignee = issue.get("assignee", {})
        labels = [l["name"] for l in issue.get("labels", {}).get("nodes", [])]
        project = issue.get("project", {})
        comments = issue.get("comments", {}).get("nodes", [])

        lines = [
            f"# {issue.get('identifier', '?')} — {issue.get('title', 'Untitled')}",
            f"URL: {issue.get('url', 'N/A')}",
            f"State: {state.get('name', '?')} ({state.get('type', '?')})",
            f"Assignee: {assignee.get('name', 'Unassigned') if assignee else 'Unassigned'}",
            f"Priority: {issue.get('priorityLabel', 'None')}",
            f"Labels: {', '.join(labels) if labels else 'None'}",
            f"Project: {project.get('name', 'None') if project else 'None'}",
            f"Created: {issue.get('createdAt', '?')}",
            f"Updated: {issue.get('updatedAt', '?')}",
            "",
            "## Description",
            issue.get("description") or "(No description)",
        ]

        if comments:
            lines.append("")
            lines.append(f"## Comments ({len(comments)})")
            for c in comments:
                user = c.get("user", {})
                lines.append(f"  [{user.get('name', '?')}] {c.get('body', '')}")

        return Response(message="\n".join(lines), break_loop=False)

    async def _search_issues(self, **kwargs) -> Response:
        client = _get_client(self)
        query = self.args.get("query", "")
        if not query:
            return Response(
                message="query is required for search_issues.",
                break_loop=False,
            )
        limit = int(self.args.get("limit", "25"))
        data = await client.execute("""
            query($query: String!, $first: Int) {
                searchIssues(query: $query, first: $first) {
                    nodes {
                        id identifier title
                        state { name type }
                        assignee { name }
                        priorityLabel
                    }
                }
            }
        """, {"query": query, "first": limit})
        issues = data.get("searchIssues", {}).get("nodes", [])
        if not issues:
            return Response(message=f"No issues matching '{query}'.", break_loop=False)
        lines = [f"Search results for '{query}' ({len(issues)}):"]
        for node in issues:
            lines.append(_format_issue_row(node))
        return Response(message="\n".join(lines), break_loop=False)

    async def _create_issue(self, **kwargs) -> Response:
        client = _get_client(self)
        title = self.args.get("title", "")
        if not title:
            return Response(
                message="title is required for create_issue.",
                break_loop=False,
            )
        team = self.args.get("team", "") or _get_default_team(self)
        if not team:
            return Response(
                message="team is required for create_issue. "
                "Use linear:list_teams first, or set a default team in settings.",
                break_loop=False,
            )

        input_data: dict = {"teamId": team, "title": title}
        description = self.args.get("description", "")
        if description:
            input_data["description"] = description
        assignee = self.args.get("assignee", "")
        if assignee:
            input_data["assigneeId"] = assignee
        state = self.args.get("state", "")
        if state:
            input_data["stateId"] = state
        priority = self.args.get("priority", "")
        if priority:
            input_data["priority"] = int(priority)
        label = self.args.get("label", "")
        if label:
            input_data["labelIds"] = [label]

        data = await client.execute("""
            mutation($input: IssueCreateInput!) {
                issueCreate(input: $input) {
                    success
                    issue { id identifier title url }
                }
            }
        """, {"input": input_data})
        result = data.get("issueCreate", {})
        if not result.get("success"):
            return Response(message="Failed to create issue.", break_loop=False)
        issue = result.get("issue", {})
        return Response(
            message=f"Created {issue.get('identifier', '?')}: {issue.get('title', '')}\n"
                    f"URL: {issue.get('url', 'N/A')}",
            break_loop=False,
        )

    async def _update_issue(self, **kwargs) -> Response:
        client = _get_client(self)
        issue_id = self.args.get("issue_id", "")
        if not issue_id:
            return Response(
                message="issue_id is required for update_issue.",
                break_loop=False,
            )

        input_data: dict = {}
        title = self.args.get("title", "")
        if title:
            input_data["title"] = title
        description = self.args.get("description", "")
        if description:
            input_data["description"] = description
        assignee = self.args.get("assignee", "")
        if assignee:
            input_data["assigneeId"] = assignee
        state = self.args.get("state", "")
        if state:
            input_data["stateId"] = state
        priority = self.args.get("priority", "")
        if priority:
            input_data["priority"] = int(priority)
        label = self.args.get("label", "")
        if label:
            input_data["labelIds"] = [label]

        if not input_data:
            return Response(
                message="No fields to update. Pass at least one of: title, description, "
                "assignee, state, priority, label.",
                break_loop=False,
            )

        data = await client.execute("""
            mutation($id: String!, $input: IssueUpdateInput!) {
                issueUpdate(id: $id, input: $input) {
                    success
                    issue { id identifier title state { name } }
                }
            }
        """, {"id": issue_id, "input": input_data})
        result = data.get("issueUpdate", {})
        if not result.get("success"):
            return Response(message=f"Failed to update issue '{issue_id}'.", break_loop=False)
        issue = result.get("issue", {})
        state_info = issue.get("state", {})
        return Response(
            message=f"Updated {issue.get('identifier', '?')}: {issue.get('title', '')}"
                    f"  [{state_info.get('name', '?')}]",
            break_loop=False,
        )

    async def _add_comment(self, **kwargs) -> Response:
        client = _get_client(self)
        issue_id = self.args.get("issue_id", "")
        body = self.args.get("body", "")
        if not issue_id:
            return Response(
                message="issue_id is required for add_comment.",
                break_loop=False,
            )
        if not body:
            return Response(
                message="body is required for add_comment.",
                break_loop=False,
            )

        data = await client.execute("""
            mutation($input: CommentCreateInput!) {
                commentCreate(input: $input) {
                    success
                    comment { id }
                }
            }
        """, {"input": {"issueId": issue_id, "body": body}})
        result = data.get("commentCreate", {})
        if not result.get("success"):
            return Response(message=f"Failed to add comment to '{issue_id}'.", break_loop=False)
        return Response(
            message=f"Comment added to {issue_id}.",
            break_loop=False,
        )
