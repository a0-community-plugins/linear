import httpx


class LinearAPIError(Exception):
    """Raised when the Linear GraphQL API returns an error."""
    pass


class LinearClient:
    """Thin async GraphQL client for the Linear API."""

    ENDPOINT = "https://api.linear.app/graphql"

    def __init__(self, api_key: str):
        if not api_key:
            raise LinearAPIError(
                "Linear API key not configured. "
                "Set it in Settings > External > Linear."
            )
        self.api_key = api_key

    async def execute(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query/mutation and return the data dict."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        headers = {
            "Content-Type": "application/json",
            "Authorization": self.api_key,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.ENDPOINT, json=payload, headers=headers
            )

            if response.status_code != 200:
                raise LinearAPIError(
                    f"Linear API HTTP {response.status_code}: {response.text}"
                )

            body = response.json()

            if "errors" in body:
                messages = [e.get("message", str(e)) for e in body["errors"]]
                raise LinearAPIError(
                    f"Linear API error: {'; '.join(messages)}"
                )

            return body.get("data", {})
