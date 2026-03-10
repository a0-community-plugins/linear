### linear
Manage Linear issues, projects, and teams.
Use linear:list_teams first to discover team IDs before creating issues.
Use linear:list_states to discover workflow state IDs before setting issue status.

#### linear:list_teams
List all teams in the workspace.
No arguments required.
~~~json
{ "tool_name": "linear", "tool_method": "list_teams", "tool_args": {} }
~~~

#### linear:list_projects
List projects, optionally filtered by team.
~~~json
{ "tool_name": "linear", "tool_method": "list_projects", "tool_args": { "team": "team-uuid (optional)" } }
~~~

#### linear:list_states
List workflow states for a team. Required to set issue status.
~~~json
{ "tool_name": "linear", "tool_method": "list_states", "tool_args": { "team": "team-uuid or key" } }
~~~

#### linear:list_issues
List issues with optional filters. Defaults to 25 results.
~~~json
{ "tool_name": "linear", "tool_method": "list_issues", "tool_args": {
  "team": "team-uuid (optional, uses default if set)",
  "assignee": "name substring (optional)",
  "state": "state name substring (optional)",
  "label": "label name substring (optional)",
  "limit": "25 (optional)"
} }
~~~

#### linear:get_issue
Get full details of a single issue including description and comments.
~~~json
{ "tool_name": "linear", "tool_method": "get_issue", "tool_args": { "issue_id": "ENG-123 or uuid" } }
~~~

#### linear:search_issues
Full-text search across issues.
~~~json
{ "tool_name": "linear", "tool_method": "search_issues", "tool_args": {
  "query": "search text",
  "limit": "25 (optional)"
} }
~~~

#### linear:create_issue
Create a new issue. Requires title and team (or default team in settings).
~~~json
{ "tool_name": "linear", "tool_method": "create_issue", "tool_args": {
  "title": "Issue title (required)",
  "team": "team-uuid (required if no default)",
  "description": "markdown body (optional)",
  "assignee": "user-uuid (optional)",
  "state": "state-uuid (optional, defaults to Backlog/Triage)",
  "priority": "0-4 integer (optional, 0=none 1=urgent 4=low)",
  "label": "label-uuid (optional)"
} }
~~~

#### linear:update_issue
Update fields on an existing issue.
~~~json
{ "tool_name": "linear", "tool_method": "update_issue", "tool_args": {
  "issue_id": "ENG-123 or uuid (required)",
  "title": "new title (optional)",
  "description": "new description (optional)",
  "assignee": "user-uuid (optional)",
  "state": "state-uuid (optional)",
  "priority": "0-4 integer (optional)",
  "label": "label-uuid (optional)"
} }
~~~

#### linear:add_comment
Add a comment to an issue.
~~~json
{ "tool_name": "linear", "tool_method": "add_comment", "tool_args": {
  "issue_id": "ENG-123 or uuid (required)",
  "body": "comment text in markdown (required)"
} }
~~~
