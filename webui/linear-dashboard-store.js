import { createStore } from "/js/AlpineStore.js";
import * as API from "/js/api.js";
import { openModal, closeModal } from "/js/modals.js";
import { store as notificationStore } from "/components/notifications/notification-store.js";

const API_ENDPOINT = "/plugins/linear/linear_dashboard";

function toast(text, type = "info", timeout = 4) {
    notificationStore.addFrontendToastOnly(type, text, "", timeout);
}

const linearDashboardStore = {
    // Data
    issues: [],
    teams: [],
    states: [],
    members: [],

    // Filters
    selectedTeam: "",
    stateFilter: "",
    assigneeFilter: "",
    searchQuery: "",

    // Pagination
    currentPage: 1,
    itemsPerPage: 25,
    totalCount: 0,

    // UI state
    loading: false,
    error: null,
    expandedRow: null,
    detailIssue: null,
    commentText: "",

    // Config
    config: {},

    // Internal
    _initialized: false,
    _focusHandler: null,
    _searchDebounce: null,

    // ── Lifecycle ────────────────────────────────────

    init() {
        if (this._initialized) return;
        this._initialized = true;
    },

    async onOpen() {
        this.loading = true;
        this.error = null;
        this.expandedRow = null;
        this.commentText = "";
        this.currentPage = 1;

        try {
            // Load config
            const configRes = await API.callJsonApi(API_ENDPOINT, { action: "get_config" });
            if (configRes.success) {
                this.config = configRes.config;
                if (!this.selectedTeam && this.config.default_team) {
                    this.selectedTeam = this.config.default_team;
                }
            }

            // Load teams
            const teamsRes = await API.callJsonApi(API_ENDPOINT, { action: "list_teams" });
            if (teamsRes.success) {
                this.teams = teamsRes.teams;
            }

            // Load issues
            await this.loadIssues();

            // Load states and members for selected team
            if (this.selectedTeam) {
                await this.loadTeamData(this.selectedTeam);
            }

            // Set up focus refresh
            if (this.config.auto_refresh_on_focus) {
                this._focusHandler = () => this.loadIssues(true);
                window.addEventListener("focus", this._focusHandler);
            }
        } catch (e) {
            this.error = "Failed to connect to Linear. Check your API key in Settings > External > Linear.";
        } finally {
            this.loading = false;
        }
    },

    cleanup() {
        if (this._focusHandler) {
            window.removeEventListener("focus", this._focusHandler);
            this._focusHandler = null;
        }
        if (this._searchDebounce) {
            clearTimeout(this._searchDebounce);
            this._searchDebounce = null;
        }
        this.expandedRow = null;
        this.detailIssue = null;
        this.commentText = "";
    },

    // ── Data Loading ─────────────────────────────────

    async loadIssues(silent = false) {
        if (!silent) this.loading = true;
        this.error = null;
        try {
            let res;
            if (this.searchQuery) {
                res = await API.callJsonApi(API_ENDPOINT, {
                    action: "search_issues",
                    query: this.searchQuery,
                    limit: this.itemsPerPage,
                });
            } else {
                res = await API.callJsonApi(API_ENDPOINT, {
                    action: "list_issues",
                    team_id: this.selectedTeam,
                    state_filter: this.stateFilter,
                    assignee_filter: this.assigneeFilter,
                    limit: this.itemsPerPage,
                });
            }
            if (res.success) {
                this.issues = res.issues;
                this.totalCount = res.total_count;
            } else {
                if (!silent) this.error = res.error;
            }
        } catch (e) {
            if (!silent) this.error = "Failed to load issues.";
        } finally {
            if (!silent) this.loading = false;
        }
    },

    async loadTeamData(teamId) {
        try {
            const [statesRes, membersRes] = await Promise.all([
                API.callJsonApi(API_ENDPOINT, { action: "list_states", team_id: teamId }),
                API.callJsonApi(API_ENDPOINT, { action: "list_members", team_id: teamId }),
            ]);
            if (statesRes.success) this.states = statesRes.states;
            if (membersRes.success) this.members = membersRes.members;
        } catch (e) {
            // Non-critical, dropdowns just won't populate
        }
    },

    async loadIssueDetail(issueId) {
        try {
            const res = await API.callJsonApi(API_ENDPOINT, {
                action: "get_issue",
                issue_id: issueId,
            });
            if (res.success) {
                this.detailIssue = res.issue;
                openModal("../plugins/linear/webui/linear-issue-detail.html");
            } else {
                toast(res.error || "Failed to load issue", "error");
            }
        } catch (e) {
            toast("Failed to load issue details", "error");
        }
    },

    // ── Filter Actions ───────────────────────────────

    async onTeamChange() {
        this.currentPage = 1;
        this.stateFilter = "";
        this.assigneeFilter = "";
        this.expandedRow = null;
        await Promise.all([
            this.loadIssues(),
            this.loadTeamData(this.selectedTeam),
        ]);
    },

    async onFilterChange() {
        this.currentPage = 1;
        this.expandedRow = null;
        await this.loadIssues();
    },

    onSearchInput() {
        if (this._searchDebounce) clearTimeout(this._searchDebounce);
        this._searchDebounce = setTimeout(() => {
            this.currentPage = 1;
            this.expandedRow = null;
            this.loadIssues();
        }, 400);
    },

    async refresh() {
        await this.loadIssues();
        toast("Refreshed", "info", 2);
    },

    // ── Row Actions ──────────────────────────────────

    toggleRow(issueId) {
        this.expandedRow = this.expandedRow === issueId ? null : issueId;
        this.commentText = "";
    },

    // ── Quick Actions ────────────────────────────────

    async updateIssueStatus(issueId, stateId) {
        try {
            const res = await API.callJsonApi(API_ENDPOINT, {
                action: "update_issue",
                issue_id: issueId,
                state_id: stateId,
            });
            if (res.success) {
                toast("Status updated", "success", 2);
                await this.loadIssues(true);
                if (this.detailIssue?.id === issueId) await this._refreshDetailIssue(issueId);
            } else {
                toast(res.error || "Failed to update status", "error");
            }
        } catch (e) {
            toast("Failed to update status", "error");
        }
    },

    async assignIssue(issueId, assigneeId) {
        try {
            const res = await API.callJsonApi(API_ENDPOINT, {
                action: "update_issue",
                issue_id: issueId,
                assignee_id: assigneeId,
            });
            if (res.success) {
                toast("Assignee updated", "success", 2);
                await this.loadIssues(true);
                if (this.detailIssue?.id === issueId) await this._refreshDetailIssue(issueId);
            } else {
                toast(res.error || "Failed to assign", "error");
            }
        } catch (e) {
            toast("Failed to assign issue", "error");
        }
    },

    async addComment(issueId) {
        if (!this.commentText.trim()) return;
        try {
            const res = await API.callJsonApi(API_ENDPOINT, {
                action: "add_comment",
                issue_id: issueId,
                body: this.commentText,
            });
            if (res.success) {
                toast("Comment added", "success", 2);
                this.commentText = "";
                if (this.detailIssue?.id === issueId) await this._refreshDetailIssue(issueId);
            } else {
                toast(res.error || "Failed to add comment", "error");
            }
        } catch (e) {
            toast("Failed to add comment", "error");
        }
    },

    async _refreshDetailIssue(issueId) {
        try {
            const res = await API.callJsonApi(API_ENDPOINT, {
                action: "get_issue",
                issue_id: issueId,
            });
            if (res.success) this.detailIssue = res.issue;
        } catch (e) {
            // Non-critical; detail will show stale data
        }
    },

    // ── Create Issue ─────────────────────────────────

    // Create issue form state (used by create modal)
    createForm: {
        title: "",
        description: "",
        team_id: "",
        state_id: "",
        assignee_id: "",
        priority: "",
    },

    openCreateModal() {
        this.createForm = {
            title: "",
            description: "",
            team_id: this.selectedTeam,
            state_id: "",
            assignee_id: "",
            priority: "",
        };
        openModal("../plugins/linear/webui/linear-create-issue.html");
    },

    async submitCreateIssue() {
        if (!this.createForm.title.trim()) {
            toast("Title is required", "warning");
            return;
        }
        if (!this.createForm.team_id) {
            toast("Team is required", "warning");
            return;
        }
        try {
            const payload = {
                action: "create_issue",
                title: this.createForm.title,
                team_id: this.createForm.team_id,
            };
            if (this.createForm.description) payload.description = this.createForm.description;
            if (this.createForm.state_id) payload.state_id = this.createForm.state_id;
            if (this.createForm.assignee_id) payload.assignee_id = this.createForm.assignee_id;
            if (this.createForm.priority) payload.priority = parseInt(this.createForm.priority);

            const res = await API.callJsonApi(API_ENDPOINT, payload);
            if (res.success) {
                toast(`Created ${res.issue?.identifier || "issue"}`, "success");
                closeModal("../plugins/linear/webui/linear-create-issue.html");
                await this.loadIssues();
            } else {
                toast(res.error || "Failed to create issue", "error");
            }
        } catch (e) {
            toast("Failed to create issue", "error");
        }
    },

    // ── Pagination ───────────────────────────────────

    get totalPages() {
        return Math.max(1, Math.ceil(this.totalCount / this.itemsPerPage));
    },

    get paginatedIssues() {
        const start = (this.currentPage - 1) * this.itemsPerPage;
        return this.issues.slice(start, start + this.itemsPerPage);
    },

    prevPage() {
        if (this.currentPage > 1) {
            this.currentPage--;
            this.expandedRow = null;
        }
    },

    nextPage() {
        if (this.currentPage < this.totalPages) {
            this.currentPage++;
            this.expandedRow = null;
        }
    },

    // ── Helpers ──────────────────────────────────────

    priorityIcon(priority) {
        const icons = { 1: "!!!!", 2: "!!!", 3: "!!", 4: "!" };
        return icons[priority] || "—";
    },

    stateColor(type) {
        const colors = {
            backlog: "var(--color-text-secondary, #888)",
            unstarted: "var(--color-text, #e0e0e0)",
            triage: "var(--color-warning, #f59e0b)",
            started: "var(--color-accent, #3b82f6)",
            completed: "var(--color-success, #22c55e)",
            canceled: "var(--color-error, #ef4444)",
        };
        return colors[type] || "var(--color-text-secondary, #888)";
    },

    timeAgo(dateStr) {
        if (!dateStr) return "—";
        const diff = Date.now() - new Date(dateStr).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 60) return `${mins}m ago`;
        const hours = Math.floor(mins / 60);
        if (hours < 24) return `${hours}h ago`;
        const days = Math.floor(hours / 24);
        return `${days}d ago`;
    },

    truncate(text, len = 200) {
        if (!text) return "";
        return text.length > len ? text.substring(0, len) + "..." : text;
    },
};

export const store = createStore("linearDashboardStore", linearDashboardStore);
